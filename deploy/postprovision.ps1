# Builds tai-job from the local tai-engine image, pushes it to the ACR and points the Container Apps Job at it.
$ErrorActionPreference = 'Stop'
$expected = $env:AZURE_SUBSCRIPTION_ID
if (-not $expected) {
  Write-Error "AZURE_SUBSCRIPTION_ID is empty in the azd environment. Aborting."
  exit 1
}
$current = az account show --query id -o tsv
if ($current -ne $expected) {
  Write-Error "The CLI subscription ($current) is not the azd environment's ($expected). Aborting."
  exit 1
}
$image = "$env:AZURE_CONTAINER_REGISTRY_ENDPOINT/tai-job:$(Get-Date -Format yyyyMMddHHmmss)"
az acr login --name $env:AZURE_CONTAINER_REGISTRY_NAME; if ($LASTEXITCODE) { exit 1 }
docker build -f deploy/job.Dockerfile -t $image .; if ($LASTEXITCODE) { exit 1 }
docker push $image; if ($LASTEXITCODE) { exit 1 }
az containerapp job update --name $env:TAI_JOB_NAME --resource-group $env:AZURE_RESOURCE_GROUP --image $image; if ($LASTEXITCODE) { exit 1 }
azd env set TAI_JOB_IMAGE $image
