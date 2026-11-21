// Task 5 preparation only: no app mutation, secrets, identities or grants.
// Review exact names, cost and what-if before any deployment.
targetScope = 'resourceGroup'

@allowed(['northcentralus'])
param location string = 'northcentralus'

@description('UTC review date YYYY-MM-DD; reminder only, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

var tags = {
  project: 'sort-tester-live'
  environment: 'production'
  'data-classification': 'employee-pilot'
  purpose: 'security-foundation'
  'expires-on': expiresOn
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: 'acrsortstg${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  // The subscription's unused student allowance covers one Standard registry.
  sku: { name: 'Standard' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: 'kv-sortstg-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    accessPolicies: []
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // Azure rejects an explicit false; leave purge protection unset.
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: false
    publicNetworkAccess: 'Enabled'
  }
}

output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output vaultName string = vault.name
output vaultUri string = vault.properties.vaultUri
