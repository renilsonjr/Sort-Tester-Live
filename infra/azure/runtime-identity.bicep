// Prepare runtime access before attaching the identity to the Container App.
// This template grants access; it requires a separate owner-approved what-if.
targetScope = 'resourceGroup'

@allowed(['northcentralus'])
param location string = 'northcentralus'

@description('UTC review date YYYY-MM-DD; reminder only, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

@description('Which environment this deployment is. It sets the resource names and the environment tag. The default is the staging that already exists: leave it out there and nothing changes.')
@allowed(['stg', 'pilot'])
param environmentSuffix string = 'stg'

@description('What kind of data the environment holds, recorded as a tag. Staging holds fictional data only. The pilot value marks real employee data.')
@allowed(['fictional-only', 'employee-pilot'])
param dataClassification string = 'fictional-only'

@description('Name of the registry the app pulls from. The default is the registry in this resource group, which belongs to staging.')
param registryName string = 'acrsortstg${uniqueString(resourceGroup().id)}'

@description('Resource group of that registry when it is NOT this one, so a second environment can pull from the registry staging already has. Empty means this resource group.')
param registryResourceGroup string = ''

@description('Grant the identity read access to the Key Vault in this resource group. False for an environment that has no vault: the app signs in to its database as this identity and holds no password to store.')
param grantVaultRead bool = true

// The tag kept its long form for staging so existing resources do not change.
var environmentTag = environmentSuffix == 'stg' ? 'staging' : environmentSuffix

var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var secretsUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' existing = {
  name: 'kv-sortstg-${uniqueString(resourceGroup().id)}'
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-sort-app-${environmentSuffix}'
  location: location
  tags: {
    project: 'sort-tester-live'
    environment: environmentTag
    'data-classification': dataClassification
    purpose: 'runtime-registry-and-vault-read'
    'expires-on': expiresOn
  }
}

// Same resource group: the assignment is made here, exactly as before.
resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(registryResourceGroup)) {
  name: guid(registry.id, runtimeIdentity.id, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Another resource group: a role assignment can only be written by a
// deployment in the resource group that holds its target, hence the module.
module registryPullElsewhere 'registry-pull-role.bicep' = if (!empty(registryResourceGroup)) {
  name: 'registry-pull-${environmentSuffix}'
  scope: resourceGroup(registryResourceGroup)
  params: {
    registryName: registryName
    principalId: runtimeIdentity.properties.principalId
    assignmentSeed: runtimeIdentity.id
  }
}

resource vaultRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (grantVaultRead) {
  name: guid(vault.id, runtimeIdentity.id, secretsUserRoleId)
  scope: vault
  properties: {
    roleDefinitionId: secretsUserRoleId
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output runtimeIdentityId string = runtimeIdentity.id
output runtimePrincipalId string = runtimeIdentity.properties.principalId
output runtimeClientId string = runtimeIdentity.properties.clientId
output registryPullAssignmentId string = empty(registryResourceGroup) ? registryPull!.id : registryPullElsewhere!.outputs.assignmentId
output vaultReadAssignmentId string = grantVaultRead ? vaultRead!.id : ''
