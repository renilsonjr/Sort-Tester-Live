targetScope = 'resourceGroup'

@allowed([
  'northcentralus'
])
param location string = 'northcentralus'

@description('Lands in resource names, where Azure allows a narrower alphabet than a string parameter does: lowercase letters and digits. Bicep cannot express that as a constraint, so the case is normalised below and anything else still fails at resource creation -- read this line before inventing a suffix.')
@minLength(4)
@maxLength(12)
param deploymentSuffix string

// Normalised rather than trusted: an uppercase letter here would be
// refused by Azure with an error naming the resource, not the parameter,
// which sends the reader looking in the wrong place. Characters outside
// the alphabet still fail there -- Bicep has no pattern constraint to
// catch them earlier.
var suffix = toLower(deploymentSuffix)

@description('SHA-256 hexadecimal digest of the separately reviewed public GHCR image; no tag accepted.')
@minLength(64)
@maxLength(64)
param imageSha256 string

var spikeTags = {
  project: 'sort-tester-live'
  environment: 'staging'
  'data-classification': 'fictional-only'
  'expires-on': '2027-10-09'
  purpose: 'api-only-container-apps-spike'
}

resource spikeEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-sort-spike-${suffix}'
  location: location
  tags: spikeTags
  properties: {
    // No appLogsConfiguration: API 2025-01-01 rejects destination 'none';
    // omitting the block leaves log ingestion unconfigured (zero ingestion).
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
  name: 'ca-sort-spike-${suffix}'
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
