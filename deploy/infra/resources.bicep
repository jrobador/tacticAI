param environmentName string
param location string
param foundryEndpoint string
param foundryDeployment string
@secure()
param foundryApiKey string
param jobImage string
param apiImage string
@secure()
param accessKey string
param budgetEmail string = ''
param budgetAmount int = 10
@description('First day of a month; budgets require it')
param budgetStartDate string = '2026-10-01'

var token = toLower(uniqueString(subscription().id, environmentName))
var placeholder = 'mcr.microsoft.com/k8se/quickstart:latest'
var jobName = 'job'
var jobCommand = 'xvfb-run -a -s "-screen 0 1280x720x24" python3 -m tacticai.orchestration start'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${token}'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${token}'
  location: location
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acr${token}'
  location: location
  sku: { name: 'Standard' }
  properties: { adminUserEnabled: false }
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-pull-${token}'
  location: location
}

// 7f951dda-... = built-in AcrPull
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, pullIdentity.id, 'acrpull')
  scope: acr
  properties: {
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${token}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: 'tai-data'
  properties: { shareQuota: 100 }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${token}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}

resource envStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: 'taidata'
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys().keys[0].value
      shareName: share.name
      accessMode: 'ReadWrite'
    }
  }
}

var registries = [{ server: acr.properties.loginServer, identity: pullIdentity.id }]
var volumes = [{ name: 'data', storageType: 'AzureFile', storageName: envStorage.name }]
var volumeMounts = [{ volumeName: 'data', mountPath: '/data' }]
var secrets = [{ name: 'foundry-api-key', value: foundryApiKey }]
var foundryEnv = [
  { name: 'FOUNDRY_ENDPOINT', value: foundryEndpoint }
  { name: 'FOUNDRY_DEPLOYMENT', value: foundryDeployment }
  { name: 'FOUNDRY_API_KEY', secretRef: 'foundry-api-key' }
  { name: 'TAI_OUTPUT_DIR', value: '/data' }
]

resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${pullIdentity.id}': {} } }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 3600
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: registries
      secrets: secrets
    }
    template: {
      volumes: volumes
      containers: [
        {
          name: 'job'
          image: empty(jobImage) ? placeholder : jobImage
          command: ['sh']
          args: ['-c', jobCommand]
          resources: { cpu: json('4'), memory: '8Gi' }
          volumeMounts: volumeMounts
          env: concat(foundryEnv, [{ name: 'TAI_WORKERS', value: '4' }])
        }
      ]
    }
  }
  dependsOn: [acrPull]
}

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'api'
  location: location
  tags: { 'azd-service-name': 'api' }
  identity: { type: 'SystemAssigned, UserAssigned', userAssignedIdentities: { '${pullIdentity.id}': {} } }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8000, transport: 'auto' }
      registries: registries
      secrets: concat(secrets, [{ name: 'tai-access-key', value: accessKey }])
    }
    template: {
      volumes: volumes
      scale: { minReplicas: 1, maxReplicas: 1 }
      containers: [
        {
          name: 'api'
          image: empty(apiImage) ? placeholder : apiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          volumeMounts: volumeMounts
          env: concat(foundryEnv, [
            { name: 'TAI_RUNNER', value: 'aca' }
            { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
            { name: 'AZURE_RESOURCE_GROUP', value: resourceGroup().name }
            { name: 'TAI_JOB_NAME', value: jobName }
            { name: 'TAI_ACCESS_KEY', secretRef: 'tai-access-key' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
          ])
        }
      ]
    }
  }
  dependsOn: [acrPull]
}

resource startRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'tai-job-starter')
  properties: {
    roleName: 'tai-job-starter-${environmentName}'
    description: 'Start and read the tacticAI Container Apps Job'
    type: 'CustomRole'
    permissions: [
      {
        actions: [
          'Microsoft.App/jobs/start/action'
          'Microsoft.App/jobs/read'
          'Microsoft.App/jobs/executions/read'
        ]
      }
    ]
    assignableScopes: [resourceGroup().id]
  }
}

resource startAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(job.id, api.id, 'starter')
  scope: job
  properties: {
    principalId: api.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: startRole.id
  }
}

// Budget scope = this resource group (the module is deployed into it). It only alerts, it does not stop anything.
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = if (!empty(budgetEmail)) {
  name: 'budget-${environmentName}'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStartDate }
    notifications: {
      actual50: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 50, thresholdType: 'Actual', contactEmails: [budgetEmail] }
      actual90: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 90, thresholdType: 'Actual', contactEmails: [budgetEmail] }
    }
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = acr.name
output TAI_JOB_NAME string = job.name
output AZURE_STORAGE_ACCOUNT string = storage.name
output API_URI string = 'https://${api.properties.configuration.ingress.fqdn}'
