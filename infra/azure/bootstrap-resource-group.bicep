targetScope = 'subscription'

@description('Azure region selected by the reviewed read-only preflight.')
@allowed([
  'eastus2'
  'eastus'
])
param location string = 'eastus2'

var requiredTags = {
  'project': 'sort-tester-live'
  'environment': 'staging'
  'data-classification': 'fictional-only'
  'expires-on': '2027-10-09'
}

resource stagingResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-sort-tester-staging'
  location: location
  tags: requiredTags
}

output resourceGroupName string = stagingResourceGroup.name
output resourceGroupId string = stagingResourceGroup.id

