targetScope = 'subscription'

@minLength(1)
param environmentName string
param location string = 'brazilsouth'
param foundryEndpoint string
param foundryDeployment string
@secure()
param foundryApiKey string
@secure()
@description('Shared key for /scenario, /ask and POST /jobs (required)')
param accessKey string
param budgetEmail string = ''
param budgetAmount int = 10
param budgetStartDate string = '2026-10-01'
@description('Real job image once pushed by the postprovision hook; empty = placeholder')
param jobImage string = ''
@description('Real API image once deployed by azd; empty = placeholder')
param apiImage string = ''

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: { 'azd-env-name': environmentName }
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    foundryEndpoint: foundryEndpoint
    foundryDeployment: foundryDeployment
    foundryApiKey: foundryApiKey
    jobImage: jobImage
    apiImage: apiImage
    accessKey: accessKey
    budgetEmail: budgetEmail
    budgetAmount: budgetAmount
    budgetStartDate: budgetStartDate
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.AZURE_CONTAINER_REGISTRY_NAME
output AZURE_RESOURCE_GROUP string = rg.name
output TAI_JOB_NAME string = resources.outputs.TAI_JOB_NAME
output AZURE_STORAGE_ACCOUNT string = resources.outputs.AZURE_STORAGE_ACCOUNT
output API_URI string = resources.outputs.API_URI
