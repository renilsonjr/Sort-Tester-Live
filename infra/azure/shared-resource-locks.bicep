// Audit Task 20 / issue #196. Deploy only after owner-reviewed what-if.
// Independent of the app template: the only writes are resource locks, three
// always and a fourth when the deletion-list storage account is named.
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

@description('Existing storage account holding the deletion list (issue #13). Empty adds no lock for it and leaves the three older locks exactly as they are.')
param deletionListStorageAccountName string = ''

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

// Without this account a database restore cannot tell which erased accounts
// to erase again. The lock stops the account and its container from being
// deleted through Azure's management side. It does NOT stop the app or the
// lifecycle rule from deleting notes: those are data operations, and the
// 7-day expiry must keep working.
var deletionListLockNotes = 'Protect the deletion list from accidental control-plane deletion (issue #13): a restore needs it to re-apply erasures. Remove only for an owner-reviewed change. This lock is not a backup and does not stop notes from expiring.'

resource deletionListAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = if (!empty(deletionListStorageAccountName)) {
  name: deletionListStorageAccountName
}

resource deletionListDeleteLock 'Microsoft.Authorization/locks@2020-05-01' = if (!empty(deletionListStorageAccountName)) {
  name: lockName
  scope: deletionListAccount
  properties: {
    level: 'CanNotDelete'
    notes: deletionListLockNotes
  }
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

output lockIds array = concat([
  postgresDeleteLock.id
  appInsightsDeleteLock.id
  logAnalyticsDeleteLock.id
], empty(deletionListStorageAccountName) ? [] : [deletionListDeleteLock!.id])
