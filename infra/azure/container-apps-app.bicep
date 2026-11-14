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

@description('Image digest to deploy, without the sha256: prefix. Built and published by the App image publish workflow; a mutable tag is never accepted.')
@minLength(64)
@maxLength(64)
param imageSha256 string

@description('Private registry host holding the image.')
param registryServer string = 'ghcr.io'

@description('Repository path of the image inside that registry.')
param imageRepository string = 'renilsonjr/sort-tester-live-app'

@description('Username for the private registry.')
param registryUsername string

@description('Read-only token for the private registry.')
@secure()
param registryPassword string

@description('postgresql:// URL of the application database, already migrated.')
@secure()
param databaseUrl string

@description('Public origin, such as https://example.com, once it is known. Empty is correct on the first deployment: writes are then checked against the app own ingress host.')
param appOrigin string = ''

@description('Number of trusted proxies in front of the app, for reading the client address from X-Forwarded-For. Empty trusts none. Set to 1 only after the check in the runbook shows the ingress appends the real client address (issue #78).')
@allowed([
  ''
  '1'
  '2'
])
param trustedProxies string = ''

var appTags = {
  project: 'sort-tester-live'
  environment: 'staging'
  'data-classification': 'fictional-only'
  purpose: 'single-origin-app-container-apps'
  'expires-on': expiresOn
}

resource appEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-sort-app-stg'
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
  }
}

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-sort-app-stg'
  location: location
  tags: appTags
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
      secrets: [
        {
          name: 'registry-password'
          value: registryPassword
        }
        {
          name: 'database-url'
          value: databaseUrl
        }
      ]
      registries: [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'registry-password'
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
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output appId string = app.id
output appEnvironmentId string = appEnvironment.id
output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output appOriginToConfigure string = 'https://${app.properties.configuration.ingress.fqdn}'
