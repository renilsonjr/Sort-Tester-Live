targetScope = 'resourceGroup'

@allowed([
  'northcentralus'
])
param location string = 'northcentralus'

@minLength(4)
@maxLength(12)
param deploymentSuffix string

@description('SHA-256 hexadecimal digest of the separately reviewed public GHCR image; no tag accepted.')
@minLength(64)
@maxLength(64)
param imageSha256 string

var spikeTags = {
  'project': 'sort-tester-live'
  'environment': 'staging'
  'data-classification': 'fictional-only'
  'expires-on': '2027-10-09'
  'purpose': 'api-only-container-apps-spike'
}

resource spikeEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-sort-spike-${deploymentSuffix}'
  location: location
  tags: spikeTags
  properties: {
    appLogsConfiguration: {
      destination: 'none'
    }
    zoneRedundant: false
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource spikeApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-sort-spike-${deploymentSuffix}'
  location: location
  tags: spikeTags
  properties: {
    managedEnvironmentId: spikeEnvironment.id
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

output spikeAppId string = spikeApp.id
output spikeEnvironmentId string = spikeEnvironment.id
output healthUrl string = 'https://${spikeApp.properties.configuration.ingress.fqdn}/health'
