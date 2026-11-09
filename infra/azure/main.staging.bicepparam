using './main.bicep'

// Candidate only: rerun preflight and review regional pricing before deployment.
// This does not relocate an existing resource group or resource.
param location = 'northcentralus'
param deploymentSuffix = 'replace-me'
param entraAdministratorPrincipalName = 'replace-with-owner-principal-name'
param entraAdministratorObjectId = '00000000-0000-0000-0000-000000000000'
param entraAdministratorPrincipalType = 'User'
param entraTenantId = '00000000-0000-0000-0000-000000000000'
param budgetContactEmail = 'replace-with-owner-email@example.invalid'

