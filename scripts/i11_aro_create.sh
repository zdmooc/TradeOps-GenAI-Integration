#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?required}"
: "${AZURE_LOCATION:?required}"
: "${ARO_RESOURCE_GROUP:?required}"
: "${ARO_CLUSTER_NAME:?required}"
: "${ARO_VERSION:?required}"
: "${ARO_VNET:?required}"
: "${ARO_MASTER_SUBNET:?required}"
: "${ARO_WORKER_SUBNET:?required}"

az account set --subscription "$AZURE_SUBSCRIPTION_ID"

az aro create \
  --resource-group "$ARO_RESOURCE_GROUP" \
  --name "$ARO_CLUSTER_NAME" \
  --location "$AZURE_LOCATION" \
  --vnet "$ARO_VNET" \
  --master-subnet "$ARO_MASTER_SUBNET" \
  --worker-subnet "$ARO_WORKER_SUBNET" \
  --version "$ARO_VERSION" \
  --enable-mi true \
  --apiserver-visibility Private \
  --ingress-visibility Private \
  --tags workload=tradeops-agentic-ai environment=lab managed_by=azure-cli architecture_stage=i11

echo "ARO creation requested. Capture az aro show, oc health, workload identity and monitoring evidence before claiming DEPLOYED."
