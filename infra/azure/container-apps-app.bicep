// Single-origin app on Azure Container Apps (issue #41).
//
// One container serves the frontend and /api (see backend/main.py) and
// connects to the PostgreSQL Flexible Server that already exists in this
// resource group. The template creates NOTHING else: no database server,
// no Log Analytics, no networking. Fictional data only.
//
// The database schema is NOT created here. Run the guarded migration
// first: python -m backend.db.upgrade_app --confirm <database>
targetScope = 'resourceGroup'

@allowed([
  'northcentralus'
])
param location string = 'northcentralus'

@description('UTC review date, YYYY-MM-DD. This tag is an owner reminder, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

@description('Which environment this deployment is. It sets the resource names and the environment tag. The default is the staging that already exists: leave it out there and nothing changes.')
@allowed(['stg', 'pilot'])
param environmentSuffix string = 'stg'

@description('What kind of data the environment holds, recorded as a tag. Staging holds fictional data only. The pilot value marks real employee data.')
@allowed(['fictional-only', 'employee-pilot'])
param dataClassification string = 'fictional-only'

@description('Image digest to deploy, without the sha256: prefix. Built and published by the App image publish workflow; a mutable tag is never accepted.')
@minLength(64)
@maxLength(64)
param imageSha256 string

@description('Private registry host holding the image, such as <name>.azurecr.io.')
param registryServer string

@description('Repository path of the image inside that registry. The default is where the runbook\'s az acr import puts it; note it carries no account prefix, because that prefix belongs to GHCR and not to a registry of our own.')
param imageRepository string = 'sort-tester-live-app'

@description('Resource id of the user-assigned identity that pulls the image, from runtime-identity.bicep. It holds AcrPull on that registry and nothing wider (audit H-5).')
param runtimeIdentityId string

@description('postgresql:// URL of the application database, already migrated. Leave empty and give databaseUrlSecretUri instead: the URL is then never part of a deployment at all. Kept only as the way back while the vault path is being proven (audit §3 P0-1).')
@secure()
param databaseUrl string = ''

@description('Versionless Key Vault URI of the secret holding that URL, such as https://<vault>.vault.azure.net/secrets/database-url. Given, the app reads the URL from the vault as the runtime identity, and its own configuration holds only this address (audit §3 P0-1). Versionless so a rotated secret is picked up without a redeployment.')
param databaseUrlSecretUri string = ''

@description('Public origin, such as https://example.com, once it is known. Empty is correct on the first deployment: writes are then checked against the app own ingress host.')
param appOrigin string = ''

@description('Resource id of the subnet the environment is injected into, from network.bicep\'s appSubnetId output (audit H-4). Empty keeps the old public-only environment, which can reach the database only through a public firewall rule.')
param appSubnetId string = ''

@description('One trusted Container Apps ingress hop, verified in the staging runbook (issue #78). Other values are rejected so deploys cannot group clients or trust a forged client address.')
@allowed([
  '1'
])
param trustedProxies string = '1'

@description('1 keeps one replica always on (the default, and what staging runs). 0 lets the app stop when idle, which costs less but gives up both reasons for always-on: the sign-up rate limiter counts in memory and is forgotten on every stop, and the first request after a stop waits for a cold start.')
@allowed([0, 1])
param minReplicas int = 1

// The tag kept its long form for staging so existing resources do not change.
var environmentTag = environmentSuffix == 'stg' ? 'staging' : environmentSuffix

var appTags = {
  project: 'sort-tester-live'
  environment: environmentTag
  'data-classification': dataClassification
  purpose: 'single-origin-app-container-apps'
  'expires-on': expiresOn
}

resource appEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-sort-app-${environmentSuffix}'
  location: location
  tags: appTags
  properties: {
    zoneRedundant: false
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    // An environment cannot be moved into a network after it is created,
    // so switching this on recreates the environment and the app, and the
    // app's address changes with it (runbook §5a). `internal: false` keeps
    // the ingress public: it is the database that goes private here, not
    // the website.
    vnetConfiguration: empty(appSubnetId) ? null : {
      infrastructureSubnetId: appSubnetId
      internal: false
    }
  }
}

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-sort-app-${environmentSuffix}'
  location: location
  tags: appTags
  // The app pulls as itself. Before this it used an account-scoped GHCR
  // token, which could read every private package the account can see --
  // and the token had to be typed into a deployment to get there (audit
  // H-5). The identity's AcrPull is on one registry and expires with
  // nothing to leak.
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${runtimeIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: appEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      // One secret, two ways of filling it. With a vault URI the app's own
      // configuration holds only that address, so reading the configuration
      // reveals nothing: seeing the URL then needs data access to the vault,
      // which is a separate grant (audit §3 P0-1). Without one the URL is
      // stored in the configuration as before -- the way back, kept until
      // the vault path has been through a deployment.
      //
      // Both empty is an operator mistake the template cannot refuse: the
      // app starts with no database URL and exits on its own configuration
      // check. §5c says to read the what-if's secrets block before deploying.
      secrets: [
        empty(databaseUrlSecretUri) ? {
          name: 'database-url'
          value: databaseUrl
        } : {
          name: 'database-url'
          keyVaultUrl: databaseUrlSecretUri
          identity: runtimeIdentityId
        }
      ]
      registries: [
        {
          server: registryServer
          identity: runtimeIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'sort-app'
          image: '${registryServer}/${imageRepository}@sha256:${imageSha256}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'SORT_TESTER_DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              // The ingress terminates TLS, so the session cookie is Secure.
              name: 'SORT_TESTER_COOKIE_SECURE'
              value: 'true'
            }
            {
              name: 'SORT_TESTER_APP_ORIGIN'
              value: appOrigin
            }
            {
              name: 'SORT_TEST_TRUST_PROXY'
              value: trustedProxies
            }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 3
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        // Exactly one replica, always on, for two reasons: the sign-up rate
        // limiter counts in memory per instance, and a cold start would eat
        // into the ten-second ranked question clock. This is the "always on"
        // cost in the estimate; it is not free-grant-only usage.
        // minReplicas may be set to 0 by an explicit owner decision only: see
        // the parameter's description for what that gives up.
        minReplicas: minReplicas
        maxReplicas: 1
      }
    }
  }
}

output appId string = app.id
output appEnvironmentId string = appEnvironment.id
output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output appOriginToConfigure string = 'https://${app.properties.configuration.ingress.fqdn}'
