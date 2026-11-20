// Storage for the deletion list (issue #13, Fatia B).
//
// A point-in-time database restore brings back accounts that players
// deleted after the restore point. The app therefore notes every accepted
// deletion OUTSIDE the database (backend/auth/deletion_list.py): one blob
// per deletion, named by the account id, containing the deletion time.
// This template is where those blobs live.
//
// Owner decisions it encodes (2026-11-20):
//   - account id and time only; nothing here widens that
//   - notes disappear after the 7-day backup window, enforced by Azure
//     (the lifecycle rule below), not by app code
//
// It creates NEW resources only. It does not modify the virtual network,
// the Container App or the identity; it only refers to them. Pointing the
// app at the container (SORT_TESTER_DELETION_LIST_URL) is a separate,
// deliberate step in deletion-list-storage.md.
//
// Requires a separate owner-approved what-if before any deployment.
targetScope = 'resourceGroup'

@allowed(['northcentralus'])
param location string = 'northcentralus'

@description('UTC review date YYYY-MM-DD; reminder only, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

var tags = {
  project: 'sort-tester-live'
  environment: 'staging'
  'data-classification': 'fictional-only'
  purpose: 'deletion-list'
  'expires-on': expiresOn
}

// Storage Blob Data Contributor: read, write and delete blobs. Assigned on
// the one container below, not on the account, so the app identity cannot
// touch any other container that might be added later.
var blobDataContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

// Fixed by Azure: a blob private endpoint is only resolved through this name.
var blobPrivateDnsZoneName = 'privatelink.blob.${environment().suffixes.storage}'

// Both pre-exist (runtime-identity.bicep, network.bicep); references only.
resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = {
  name: 'id-sort-app-stg'
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: 'vnet-sort-stg'
}

resource account 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: 'stsortdel${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: {
    // Locally redundant on purpose. Geo-replication would copy the notes to
    // a second region and make "gone after 7 days" harder to reason about.
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    // No anonymous reads, ever.
    allowBlobPublicAccess: false
    // No account keys and no SAS: Entra identities only. A leaked key
    // would otherwise read and rewrite the whole list.
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    allowCrossTenantReplication: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    // Reachable only through the private endpoint below.
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: account
  name: 'default'
  properties: {
    // All three stay OFF, deliberately. Soft delete and versioning keep a
    // recoverable copy of a blob after it is "deleted", which would quietly
    // extend how long a deletion note lives beyond the 7 days the owner
    // approved. Do not turn them on as a "safety" improvement.
    isVersioningEnabled: false
    deleteRetentionPolicy: {
      enabled: false
    }
    containerDeleteRetentionPolicy: {
      enabled: false
    }
  }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: 'deletions'
  properties: {
    publicAccess: 'None'
  }
}

// The 7-day promise. A note must outlive every restore point still inside
// the backup window, so it is removed only once it is OLDER than 7 days.
// Azure evaluates lifecycle rules about once a day and may take up to a
// further day to act, so a note can live to roughly 8-9 days. Never less
// than 7.
resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2024-01-01' = {
  parent: account
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'expire-deletion-notes'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['${container.name}/']
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterCreationGreaterThan: 7
                }
              }
            }
          }
        }
      ]
    }
  }
}

resource appMayWriteNotes 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(container.id, runtimeIdentity.id, blobDataContributorRoleId)
  scope: container
  properties: {
    roleDefinitionId: blobDataContributorRoleId
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource blobPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: blobPrivateDnsZoneName
  location: 'global'
  tags: tags
}

// Without this link the zone exists but nothing in the network consults it,
// and the account name resolves to a public address that refuses the app.
resource blobZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: blobPrivateDnsZone
  name: 'link-vnet-sort-stg'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource blobPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-sort-deletion-list'
  location: location
  tags: tags
  properties: {
    subnet: {
      // The same non-delegated subnet that holds the database endpoint.
      id: '${vnet.id}/subnets/snet-data'
    }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: account.id
          groupIds: ['blob']
        }
      }
    ]
  }
}

resource blobDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: blobPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: blobPrivateDnsZone.id
        }
      }
    ]
  }
}

@description('The value for SORT_TESTER_DELETION_LIST_URL on the Container App.')
output deletionListUrl string = '${account.properties.primaryEndpoints.blob}${container.name}'
output storageAccountName string = account.name
output privateEndpointId string = blobPrivateEndpoint.id
output roleAssignmentId string = appMayWriteNotes.id
