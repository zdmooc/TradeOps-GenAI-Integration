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

ARO_MASTER_VM_SIZE="${ARO_MASTER_VM_SIZE:-Standard_D8s_v5}"
ARO_WORKER_VM_SIZE="${ARO_WORKER_VM_SIZE:-Standard_D4s_v5}"
ARO_WORKER_COUNT="${ARO_WORKER_COUNT:-3}"
ARO_WORKER_DISK_GB="${ARO_WORKER_DISK_GB:-128}"

if ! [[ "$ARO_WORKER_COUNT" =~ ^[0-9]+$ ]] || (( ARO_WORKER_COUNT < 3 )); then
  echo "ARO_WORKER_COUNT must be an integer >= 3." >&2
  exit 2
fi
if ! [[ "$ARO_WORKER_DISK_GB" =~ ^[0-9]+$ ]] || (( ARO_WORKER_DISK_GB < 128 )); then
  echo "ARO_WORKER_DISK_GB must be an integer >= 128." >&2
  exit 2
fi

cat <<EOF
ARO PAID DEPLOYMENT PLAN
subscription=${AZURE_SUBSCRIPTION_ID}
location=${AZURE_LOCATION}
resource_group=${ARO_RESOURCE_GROUP}
cluster=${ARO_CLUSTER_NAME}
version=${ARO_VERSION}
master_nodes=3
master_vm_size=${ARO_MASTER_VM_SIZE}
worker_nodes=${ARO_WORKER_COUNT}
worker_vm_size=${ARO_WORKER_VM_SIZE}
worker_disk_gb=${ARO_WORKER_DISK_GB}
api_visibility=Private
ingress_visibility=Private
EOF

if [[ "${ALLOW_AZURE_COST:-0}" != "1" ]]; then
  echo "Refusing paid Azure creation. Review the current Azure estimate, then set ALLOW_AZURE_COST=1 only after explicit approval." >&2
  exit 2
fi

az account set --subscription "$AZURE_SUBSCRIPTION_ID"

if az aro show --resource-group "$ARO_RESOURCE_GROUP" --name "$ARO_CLUSTER_NAME" >/dev/null 2>&1; then
  echo "Refusing creation because ARO cluster already exists: ${ARO_RESOURCE_GROUP}/${ARO_CLUSTER_NAME}" >&2
  exit 2
fi

AVAILABLE_VERSION="$(az aro get-versions --location "$AZURE_LOCATION" -o tsv | awk -v wanted="$ARO_VERSION" '$0 == wanted {print; exit}')"
if [[ "$AVAILABLE_VERSION" != "$ARO_VERSION" ]]; then
  echo "Requested ARO version is not currently offered in ${AZURE_LOCATION}: ${ARO_VERSION}" >&2
  exit 2
fi

az aro validate \
  --resource-group "$ARO_RESOURCE_GROUP" \
  --name "$ARO_CLUSTER_NAME" \
  --location "$AZURE_LOCATION" \
  --vnet "$ARO_VNET" \
  --master-subnet "$ARO_MASTER_SUBNET" \
  --worker-subnet "$ARO_WORKER_SUBNET" \
  --version "$ARO_VERSION"

az aro create \
  --resource-group "$ARO_RESOURCE_GROUP" \
  --name "$ARO_CLUSTER_NAME" \
  --location "$AZURE_LOCATION" \
  --vnet "$ARO_VNET" \
  --master-subnet "$ARO_MASTER_SUBNET" \
  --worker-subnet "$ARO_WORKER_SUBNET" \
  --version "$ARO_VERSION" \
  --master-vm-size "$ARO_MASTER_VM_SIZE" \
  --worker-vm-size "$ARO_WORKER_VM_SIZE" \
  --worker-count "$ARO_WORKER_COUNT" \
  --worker-vm-disk-size-gb "$ARO_WORKER_DISK_GB" \
  --enable-mi true \
  --apiserver-visibility Private \
  --ingress-visibility Private \
  --tags workload=tradeops-agentic-ai environment=lab managed_by=azure-cli architecture_stage=i11

echo "ARO creation completed. Capture az aro show, oc health, workload identity and monitoring evidence before claiming DEPLOYED."
