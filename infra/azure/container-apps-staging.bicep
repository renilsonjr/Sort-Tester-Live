targetScope = 'resourceGroup'

@allowed([
  'northcentralus'
])
param location string = 'northcentralus'

@description('UTC review date, YYYY-MM-DD. This tag is an owner reminder, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

@description('Only the image digest verified by the November 10 fictional-data spike is accepted.')
@allowed([
  '2efc496c42d6302260ce297b228581511bc73ec0a181671644170cf3255638cf'
])
param imageSha256 string = '2efc496c42d6302260ce297b228581511bc73ec0a181671644170cf3255638cf'

var stagingTags = {
  'project': 'sort-tester-live'
  'environment': 'staging'
  'data-classification': 'fictional-only'
  'purpose': 'api-only-container-apps-staging'
  'expires-on': expiresOn
}

resource stagingEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-sort-api-stg'
  location: location
  tags: stagingTags
  properties: {
    // API 2025-01-01 rejects appLogsConfiguration.destination = 'none'.
    zoneRedundant: false
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource stagingApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-sort-api-stg'
  location: location
  tags: stagingTags
  properties: {
    managedEnvironmentId: stagingEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'health-api'
          image: 'ghcr.io/renilsonjr/sort-tester-live-api-spike@sha256:${imageSha256}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
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
        minReplicas: 0
        maxReplicas: 1
        rules: [
          {
            name: 'http'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

output stagingAppId string = stagingApp.id
output stagingEnvironmentId string = stagingEnvironment.id
output healthUrl string = 'https://${stagingApp.properties.configuration.ingress.fqdn}/health'
