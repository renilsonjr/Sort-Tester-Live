targetScope = 'resourceGroup'

@description('Azure region selected by the reviewed read-only preflight.')
@allowed([
  'eastus2'
  'eastus'
  'northcentralus'
])
param location string = 'eastus2'

@description('Short lowercase suffix used only to prevent global-name collisions.')
@minLength(4)
@maxLength(12)
param deploymentSuffix string

@description('Display name or user principal name of the owner Entra administrator.')
param entraAdministratorPrincipalName string

@description('Object ID of the owner Entra administrator.')
param entraAdministratorObjectId string

@description('Owner Entra administrator principal type.')
@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
param entraAdministratorPrincipalType string = 'User'

@description('Tenant ID containing the owner Entra administrator.')
param entraTenantId string

@description('Email address that receives the staging budget notifications.')
param budgetContactEmail string

var requiredTags = {
  'project': 'sort-tester-live'
  'environment': 'staging'
  'data-classification': 'fictional-only'
  'expires-on': '2027-10-09'
}
var appServicePlanName = 'asp-sort-tester-${deploymentSuffix}'
var webAppName = 'app-sort-tester-${deploymentSuffix}'
var postgresServerName = 'pg-sort-tester-${deploymentSuffix}'
var workspaceName = 'law-sort-tester-${deploymentSuffix}'
var applicationInsightsName = 'appi-sort-tester-${deploymentSuffix}'

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: appServicePlanName
  location: location
  tags: requiredTags
  kind: 'linux'
  sku: {
    name: 'F1'
    tier: 'Free'
    size: 'F1'
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2024-04-01' = {
  name: webAppName
  location: location
  tags: requiredTags
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      alwaysOn: false
      ftpsState: 'Disabled'
      http20Enabled: true
      linuxFxVersion: 'PYTHON|3.14'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
    }
  }
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2026-10-01' = {
  name: postgresServerName
  location: location
  tags: requiredTags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: entraTenantId
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
      immutableBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    storage: {
      autoGrow: 'Disabled'
      storageSizeGB: 32
      type: 'Premium_LRS'
    }
    version: '18'
  }
}

resource postgresRequireTls 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-08-01' = {
  parent: postgresServer
  name: 'require_secure_transport'
  properties: {
    source: 'user-override'
    value: 'on'
  }
}

resource postgresMinimumTls 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-08-01' = {
  parent: postgresServer
  name: 'ssl_min_protocol_version'
  properties: {
    source: 'user-override'
    value: 'TLSv1.2'
  }
}

resource postgresAdministrator 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2025-08-01' = {
  parent: postgresServer
  name: entraAdministratorObjectId
  properties: {
    principalName: entraAdministratorPrincipalName
    principalType: entraAdministratorPrincipalType
    tenantId: entraTenantId
  }
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: workspaceName
  location: location
  tags: requiredTags
  properties: {
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    workspaceCapping: {
      dailyQuotaGb: json('0.1')
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  tags: requiredTags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    DisableIpMasking: false
    DisableLocalAuth: true
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
}

resource stagingBudget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: 'budget-sort-tester-staging'
  properties: {
    amount: 5
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-11-01T00:00:00Z'
      endDate: '2027-11-01T00:00:00Z'
    }
    notifications: {
      Actual_GreaterThan_50_Percent: {
        contactEmails: [
          budgetContactEmail
        ]
        contactGroups: []
        contactRoles: []
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        thresholdType: 'Actual'
      }
      Actual_GreaterThan_80_Percent: {
        contactEmails: [
          budgetContactEmail
        ]
        contactGroups: []
        contactRoles: []
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Actual'
      }
      Actual_GreaterThan_100_Percent: {
        contactEmails: [
          budgetContactEmail
        ]
        contactGroups: []
        contactRoles: []
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Actual'
      }
    }
  }
}

output deployedWebAppName string = webApp.name
output webAppId string = webApp.id
output webAppManagedIdentityPrincipalId string = webApp.identity.principalId
output deployedPostgresServerName string = postgresServer.name
output postgresServerId string = postgresServer.id
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id
output applicationInsightsId string = applicationInsights.id
output deploymentManifest array = [
  {
    id: appServicePlan.id
    name: appServicePlan.name
    type: appServicePlan.type
  }
  {
    id: webApp.id
    name: webApp.name
    type: webApp.type
  }
  {
    id: postgresServer.id
    name: postgresServer.name
    type: postgresServer.type
  }
  {
    id: postgresRequireTls.id
    name: postgresRequireTls.name
    type: postgresRequireTls.type
  }
  {
    id: postgresMinimumTls.id
    name: postgresMinimumTls.name
    type: postgresMinimumTls.type
  }
  {
    id: postgresAdministrator.id
    name: postgresAdministrator.name
    type: postgresAdministrator.type
  }
  {
    id: logAnalyticsWorkspace.id
    name: logAnalyticsWorkspace.name
    type: logAnalyticsWorkspace.type
  }
  {
    id: applicationInsights.id
    name: applicationInsights.name
    type: applicationInsights.type
  }
  {
    id: stagingBudget.id
    name: stagingBudget.name
    type: stagingBudget.type
  }
]

