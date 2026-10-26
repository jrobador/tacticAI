#!/bin/sh
# Builds tai-job from the local tai-engine image, pushes it to the ACR and points the Container Apps Job at it.
set -eu
EXPECTED=${AZURE_SUBSCRIPTION_ID:-}
if [ -z "$EXPECTED" ]; then
  echo "AZURE_SUBSCRIPTION_ID is empty in the azd environment. Aborting." >&2
  exit 1
fi
CURRENT=$(az account show --query id -o tsv)
if [ "$CURRENT" != "$EXPECTED" ]; then
  echo "The CLI subscription ($CURRENT) is not the azd environment's ($EXPECTED). Aborting." >&2
  exit 1
fi
TAG=$(date +%Y%m%d%H%M%S)
IMAGE="$AZURE_CONTAINER_REGISTRY_ENDPOINT/tai-job:$TAG"
az acr login --name "$AZURE_CONTAINER_REGISTRY_NAME"
docker build -f deploy/job.Dockerfile -t "$IMAGE" .
docker push "$IMAGE"
az containerapp job update --name "$TAI_JOB_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --image "$IMAGE"
azd env set TAI_JOB_IMAGE "$IMAGE"
