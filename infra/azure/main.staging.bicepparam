using './main.bicep'

param location = 'eastus2'
param deploymentSuffix = 'replace-me'
param entraAdministratorPrincipalName = 'replace-with-owner-principal-name'
param entraAdministratorObjectId = '00000000-0000-0000-0000-000000000000'
param entraAdministratorPrincipalType = 'User'
param entraTenantId = '00000000-0000-0000-0000-000000000000'
param budgetContactEmail = 'replace-with-owner-email@example.invalid'

