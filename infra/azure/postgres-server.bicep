// The PostgreSQL Flexible Server of an environment (issue #13).
//
// Staging's server was created by hand before any of these templates
// existed and is NOT managed by this file: do not deploy this against it.
// This is for creating a new environment's server, with the choices that
// can only be made at creation written down.
//
// Owner decisions it encodes (2026-11-20):
//   - backups are kept 7 days and in one region. The deletion list
//     (deletion-list-storage.bicep) covers exactly that window and lives in
//     that region, so a longer window or a geo copy could bring back an
//     erased account with no note left to re-apply.
//   - the server accepts Microsoft Entra sign-in and passwords. The app uses
//     neither password: it signs in as its managed identity. The
//     administrator password exists for the migration only.
//
// It creates the server, its Entra administrator and one empty database.
// It creates no network path: the server is closed to the internet from the
// first moment, and network.bicep gives it a private endpoint afterwards.
// Roles and grants inside the database are db-runtime-role.md, not this.
//
// Requires a separate owner-approved what-if before any deployment.
targetScope = 'resourceGroup'

@allowed(['northcentralus'])
param location string = 'northcentralus'

@description('UTC review date YYYY-MM-DD; reminder only, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

@description('Which environment this server belongs to. There is no default and staging is not allowed: its server is not managed here.')
@allowed(['pilot'])
param environmentSuffix string

@description('What kind of data the environment holds, recorded as a tag.')
@allowed(['fictional-only', 'employee-pilot'])
param dataClassification string

@description('Globally unique server name. Pick a new one: the name of a deleted server stays reserved for a while.')
@minLength(3)
@maxLength(63)
param serverName string

@description('PostgreSQL major version. Staging runs 18.')
param postgresVersion string = '18'

@description('Name of the application database. It is created empty; the guarded migration fills it.')
param databaseName string = 'sort_tester_app'

@description('Login name of the password administrator, used for the migration only.')
@minLength(1)
param administratorLogin string

@description('Its password. Never put it on a command line or in a file that is kept: pass it from a prompt.')
@secure()
@minLength(16)
param administratorLoginPassword string

@description('Object id of the person who administers the server through Microsoft Entra.')
@minLength(36)
@maxLength(36)
param entraAdminObjectId string

@description('That person\'s sign-in name, as Entra shows it.')
@minLength(3)
param entraAdminName string

var tags = {
  project: 'sort-tester-live'
  environment: environmentSuffix
  'data-classification': dataClassification
  purpose: 'application-database'
  'expires-on': expiresOn
}

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  tags: tags
  sku: {
    // The size staging runs, and the smallest there is.
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: postgresVersion
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      // Both lines are owner decisions, not defaults: see the header.
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      // Closed from creation. Nothing reaches the server until
      // network.bicep adds the private endpoint.
      publicNetworkAccess: 'Disabled'
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: tenant().tenantId
    }
  }
}

resource entraAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: server
  name: entraAdminObjectId
  properties: {
    principalType: 'User'
    principalName: entraAdminName
    tenantId: tenant().tenantId
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
  // One change to the server at a time: a database created while the
  // administrator is still being set fails with a busy-server error.
  dependsOn: [entraAdmin]
}

@description('Pass this to network.bicep as postgresServerName, and to container-apps-app.bicep as databaseServerName.')
output serverName string = server.name
output serverId string = server.id
output databaseName string = database.name
