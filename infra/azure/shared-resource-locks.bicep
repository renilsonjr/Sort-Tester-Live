// Audit Task 20 / issue #196. Deploy only after owner-reviewed what-if.
// Independent of the app template: the only writes are three resource locks.
targetScope = 'resourceGroup'

@description('Existing PostgreSQL Flexible Server name in this resource group, checked against the private inventory.')
@minLength(3)
param postgresServerName string

@description('Existing Application Insights component name in this resource group, checked against the private inventory.')
@minLength(1)
param appInsightsName string

@description('Existing Log Analytics workspace name in this resource group, checked against the private inventory.')
@minLength(4)
param logAnalyticsName string

var lockName = 'sort-tester-prevent-delete'
var lockNotes = 'Protect this shared staging resource from accidental control-plane deletion (audit Task 20 / issue #196). Remove only for an owner-reviewed change. This lock is not a backup or data-plane protection.'

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: postgresServerName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsName
}

resource postgresDeleteLock 'Microsoft.Authorization/locks@2020-05-01' = {
  name: lockName
  scope: postgresServer
  properties: {
    level: 'CanNotDelete'
    notes: lockNotes
  }
}

resource appInsightsDeleteLock 'Microsoft.Authorization/locks@2020-05-01' = {
  name: lockName
  scope: appInsights
  properties: {
    level: 'CanNotDelete'
    notes: lockNotes
  }
}

resource logAnalyticsDeleteLock 'Microsoft.Authorization/locks@2020-05-01' = {
  name: lockName
  scope: logAnalytics
  properties: {
    level: 'CanNotDelete'
    notes: lockNotes
  }
}

output lockIds array = [
  postgresDeleteLock.id
  appInsightsDeleteLock.id
  logAnalyticsDeleteLock.id
]
