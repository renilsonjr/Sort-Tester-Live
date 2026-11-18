// The identity CI publishes with, and nothing else (audit H-5, step 2).
//
// Today every deployment needs a person to copy the image into the
// registry by hand, with a GitHub token that can read every private
// package the account can see. That token is the finding H-5 closed for
// the running app; this closes it for the path that puts images there.
//
// Nothing is stored in GitHub. The workflow proves who it is with the
// token GitHub mints for that run, the federated credential below says
// which repository and which branch that token must name, and Azure
// answers with an access token that lives for minutes. There is no
// secret to leak and none to rotate.
//
// Scope: AcrPush on one registry. Not AcrPull as well -- pulling is the
// app's job, with its own identity -- and nothing outside that registry.
targetScope = 'resourceGroup'

@allowed(['northcentralus'])
param location string = 'northcentralus'

@description('UTC review date YYYY-MM-DD; reminder only, not automatic cleanup.')
@minLength(10)
@maxLength(10)
param expiresOn string

@description('The GitHub repository allowed to publish, as owner/name.')
param repository string

@description('The subject GitHub actually presents, copied from a run. A federated credential matches it exactly, so a second branch or environment needs a second credential and a second review.')
param federatedSubject string

// AcrPush: push and pull images. Verified against Microsoft's published
// built-in role list; AcrPull on the same page matches the GUID already
// used by runtime-identity.bicep, which is the cross-check that this one
// was read correctly.
var acrPushRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: 'acrsortstg${uniqueString(resourceGroup().id)}'
}

resource publishIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-sort-publish-ci'
  location: location
  tags: {
    project: 'sort-tester-live'
    environment: 'staging'
    'data-classification': 'fictional-only'
    purpose: 'ci-registry-push'
    'expires-on': expiresOn
  }
}

// Which token Azure will believe. `subject` is matched exactly: a token
// from another repository, another branch, or a pull request from a fork
// does not match, and no amount of workflow editing changes that -- the
// rule lives here, not in the workflow.
resource federated 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = {
  parent: publishIdentity
  name: 'github-publish'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    // Not built from the repository name, because two things change it
    // and neither is guessable from the outside:
    //
    //   * a job with `environment:` gets `:environment:<name>` in place
    //     of `:ref:refs/heads/<branch>` -- so the publish gate added in
    //     Task 8 changed the identity CI presents;
    //   * an account using immutable claims gets numeric ids folded in,
    //     as `owner@<id>/repo@<id>`, which is better (a rename cannot
    //     inherit the trust) but is not the form the docs show.
    //
    // Read it from a run instead of predicting it: Azure's refusal
    // prints 'No matching federated identity record found for presented
    // assertion subject ...', and that string is the value to pass here.
    subject: federatedSubject
    audiences: ['api://AzureADTokenExchange']
  }
}

resource registryPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, publishIdentity.id, acrPushRoleId)
  scope: registry
  properties: {
    roleDefinitionId: acrPushRoleId
    principalId: publishIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output publishIdentityId string = publishIdentity.id
output publishClientId string = publishIdentity.properties.clientId
output publishPrincipalId string = publishIdentity.properties.principalId
output federatedSubject string = federated.properties.subject
