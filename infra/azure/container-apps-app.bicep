// Single-origin app on Azure Container Apps (issue #41).
//
// One container serves the frontend and /api (see backend/main.py) and
// connects to a PostgreSQL Flexible Server that already exists, signing in
// as its own managed identity (issue #84). The template creates NOTHING
// else: no database server, no Log Analytics, no networking. The defaults
// describe the fictional-data staging.
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

@description('Client id of that same identity, from runtime-identity.bicep\'s runtimeClientId output. The app signs in to its database as this identity (issue #84): there is no database password anywhere in this template.')
@minLength(36)
@maxLength(36)
param runtimeIdentityClientId string

@description('Name of the PostgreSQL Flexible Server, without the domain. The server must already hold a role named after the runtime identity (db-runtime-role.md).')
param databaseServerName string

@description('Name of the application database on that server, already migrated.')
param databaseName string = 'sort_tester_app'

@description('Container URL of the deletion list, from deletion-list-storage.bicep\'s deletionListUrl output. Required: signing in as an identity, the app refuses to start without it, so that a restore can never silently lose a player\'s deletion (issue #13).')
@minLength(8)
param deletionListUrl string

@description('Public origin, such as https://example.com, once it is known. Empty is correct on the first deployment: writes are then checked against the app own ingress host.')
param appOrigin string = ''

@description('Custom host name already bound to this app, such as play.example.com. Empty means none. Once a domain is bound it MUST be passed on every deployment together with customDomainCertificateName: a deployment that leaves it out removes the domain from the app (seen on staging, 2026-11-20).')
param customDomainName string = ''

@description('Name of the managed certificate that already exists in this environment for that host name, as `az containerapp env certificate list` shows it. The first binding is done by command line, which creates the certificate; this template only keeps the binding in place.')
param customDomainCertificateName string = ''

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

// The database role is named after the identity, so the user in the URL is the
// identity's own name. The URL holds no password: the app fetches a short-lived
// token as that identity and presents it instead. `sslrootcert=system` is not
// optional -- without it libpq looks for a certificate file the image does not
// have and every connection fails (found the hard way in #84).
var runtimeIdentityName = last(split(runtimeIdentityId, '/'))
var databaseUrl = 'postgresql://${runtimeIdentityName}@${databaseServerName}.postgres.database.azure.com:5432/${databaseName}?sslmode=verify-full&sslrootcert=system'

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
        // Azure replaces this whole block on every deployment, so a domain
        // that is not written here is unbound. The certificate itself is a
        // separate resource and survives; only the binding is lost.
        customDomains: empty(customDomainName) ? [] : [
          {
            name: customDomainName
            bindingType: 'SniEnabled'
            certificateId: '${appEnvironment.id}/managedCertificates/${customDomainCertificateName}'
          }
        ]
      }
      // No secrets block: nothing here is secret. The database URL carries
      // no password, and the image is pulled by identity.
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
              value: databaseUrl
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
            {
              name: 'SORT_TESTER_DB_AUTH'
              value: 'managed_identity'
            }
            {
              // Which identity to ask a token for; the container could hold
              // more than one.
              name: 'SORT_TESTER_DB_IDENTITY_CLIENT_ID'
              value: runtimeIdentityClientId
            }
            {
              name: 'SORT_TESTER_DELETION_LIST_URL'
              value: deletionListUrl
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
@description('What to pass as appOrigin: the custom domain when one is bound, otherwise the address Azure assigned. Only this one address can then log in and play.')
output appOriginToConfigure string = empty(customDomainName) ? 'https://${app.properties.configuration.ingress.fqdn}' : 'https://${customDomainName}'
