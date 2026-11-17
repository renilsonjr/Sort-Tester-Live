// Private network for the app and the database (audit H-4, Task 6).
//
// Today the Flexible Server is reached over the public internet with an
// `allow-azure-services` rule: every Azure tenant can open TCP 5432 on it
// and the password is the only barrier. This template builds the network
// that replaces that rule -- a virtual network the Container Apps
// environment sits inside, and a private endpoint that gives the database
// an address only reachable from in there.
//
// It creates NO app resources and changes nothing about the server itself.
// Deleting the public firewall rule and disabling public access are
// separate, deliberate steps in container-apps-app.md §5a, taken only
// after the app has been seen working over the private endpoint.
//
// The owner chose 10.20.0.0/16 on 2026-11-16, there being no other virtual
// network in this subscription to collide with.
targetScope = 'resourceGroup'

@allowed(['northcentralus'])
param location string = 'northcentralus'

@description('UTC review date YYYY-MM-DD; reminder only, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

@description('Name of the PostgreSQL Flexible Server that already exists in this resource group. It is not created or modified here; the private endpoint points at it.')
param postgresServerName string

@description('Address space of the virtual network.')
param vnetAddressPrefix string = '10.20.0.0/16'

@description('Subnet the Container Apps environment is injected into. Delegated to Microsoft.App/environments, which may hold nothing else. A workload-profiles environment needs /27 or larger.')
param appSubnetPrefix string = '10.20.1.0/27'

@description('Subnet holding the database private endpoint. It is not delegated and holds no compute.')
param dataSubnetPrefix string = '10.20.2.0/28'

var tags = {
  project: 'sort-tester-live'
  environment: 'staging'
  'data-classification': 'fictional-only'
  purpose: 'private-network'
  'expires-on': expiresOn
}

// The zone name is fixed by Azure: a private endpoint for a Flexible
// Server is only resolved through exactly this name. "privatelink", not
// "privelink" -- a misspelling here resolves to nothing and the app simply
// cannot reach its database.
var postgresPrivateDnsZoneName = 'privatelink.postgres.database.azure.com'

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-sort-stg'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressPrefix]
    }
    subnets: [
      {
        name: 'snet-app'
        properties: {
          addressPrefix: appSubnetPrefix
          delegations: [
            {
              name: 'aca'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'snet-data'
        properties: {
          addressPrefix: dataSubnetPrefix
          // A private endpoint needs these policies off in its own subnet.
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource postgresPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: postgresPrivateDnsZoneName
  // A private DNS zone is a global resource; only its links are regional.
  location: 'global'
  tags: tags
}

// Without this link the zone exists but nothing in the network consults it,
// so the server name still resolves to its public address.
resource postgresZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: postgresPrivateDnsZone
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

// The server itself is pre-existing and stays outside this template: this
// is only a reference, so the endpoint knows what to point at.
resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: postgresServerName
}

resource postgresPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-sort-postgres'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/snet-data'
    }
    privateLinkServiceConnections: [
      {
        name: 'postgres'
        properties: {
          privateLinkServiceId: postgresServer.id
          // The group a Flexible Server answers on. Any other value leaves
          // the endpoint created but connected to nothing.
          groupIds: ['postgresqlServer']
        }
      }
    ]
  }
  // No dependsOn: the subnet id above references vnet.id, so Bicep
  // already orders this after the network. Stating it again implies the
  // ordering would not happen otherwise, which is the opposite of true.
}

// Writes the server's private address into the zone, so inside the network
// the server's own FQDN resolves to it. The connection string therefore
// does not change: the same host name, answered privately.
resource postgresDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: postgresPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'postgres'
        properties: {
          privateDnsZoneId: postgresPrivateDnsZone.id
        }
      }
    ]
  }
}

@description('Pass this to container-apps-app.bicep as appSubnetId.')
output appSubnetId string = '${vnet.id}/subnets/snet-app'
output vnetId string = vnet.id
output privateEndpointId string = postgresPrivateEndpoint.id
output postgresPrivateDnsZoneName string = postgresPrivateDnsZoneName
