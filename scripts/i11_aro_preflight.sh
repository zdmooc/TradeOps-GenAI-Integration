#!/usr/bin/env bash
set -euo pipefail

required=(AZURE_SUBSCRIPTION_ID AZURE_LOCATION ARO_RESOURCE_GROUP ARO_CLUSTER_NAME ARO_VERSION ARO_VNET ARO_MASTER_SUBNET ARO_WORKER_SUBNET)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required environment variable: ${name}" >&2
    exit 2
  fi
done

command -v az >/dev/null || { echo "Azure CLI is required" >&2; exit 3; }

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az provider show --namespace Microsoft.RedHatOpenShift --query registrationState -o tsv | grep -qx Registered || {
  echo "Microsoft.RedHatOpenShift provider is not registered" >&2
  exit 4
}

if ! az aro get-versions --location "$AZURE_LOCATION" -o tsv | grep -q "^${ARO_VERSION}"; then
  echo "ARO version ${ARO_VERSION} is not offered in ${AZURE_LOCATION}" >&2
  exit 5
fi

az aro validate \
  --resource-group "$ARO_RESOURCE_GROUP" \
  --name "$ARO_CLUSTER_NAME" \
  --vnet "$ARO_VNET" \
  --master-subnet "$ARO_MASTER_SUBNET" \
  --worker-subnet "$ARO_WORKER_SUBNET" \
  --version "$ARO_VERSION" \
  --enable-mi true

echo "I11_ARO_PREFLIGHT_PASS"
