// AcrPull on one registry for one identity, deployed into the registry's own
// resource group. Used by runtime-identity.bicep when a second environment
// pulls from a registry that lives elsewhere. It grants nothing else.
targetScope = 'resourceGroup'

@description('Name of the registry in this resource group.')
param registryName string

@description('Principal id of the identity that may pull.')
param principalId string

@description('Resource id of that identity. Only used to name the assignment, so the same pair always produces the same name.')
param assignmentSeed string

var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, assignmentSeed, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output assignmentId string = registryPull.id
