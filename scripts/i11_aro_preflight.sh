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
command -v python >/dev/null || { echo "Python is required for semantic Azure CLI version validation" >&2; exit 3; }

MIN_AZ_CLI_VERSION="${MIN_AZ_CLI_VERSION:-2.84.0}"
CURRENT_AZ_CLI_VERSION="$(az version --query '"azure-cli"' -o tsv)"
python - "$CURRENT_AZ_CLI_VERSION" "$MIN_AZ_CLI_VERSION" <<'PY'
import sys


def version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))

current, minimum = sys.argv[1], sys.argv[2]
if version(current) < version(minimum):
    raise SystemExit(
        f"Azure CLI {current} is too old for the managed-identity ARO lab; required >= {minimum}"
    )
PY

az account set --subscription "$AZURE_SUBSCRIPTION_ID"

for provider in Microsoft.RedHatOpenShift Microsoft.Compute Microsoft.Storage Microsoft.Authorization; do
  state="$(az provider show --namespace "$provider" --query registrationState -o tsv)"
  if [[ "$state" != "Registered" ]]; then
    echo "$provider provider is not registered (state=$state)" >&2
    exit 4
  fi
done

if ! az aro get-versions --location "$AZURE_LOCATION" -o tsv | grep -qx "$ARO_VERSION"; then
  echo "ARO version ${ARO_VERSION} is not offered in ${AZURE_LOCATION}" >&2
  exit 5
fi

ARO_MIN_REGIONAL_VCPUS="${ARO_MIN_REGIONAL_VCPUS:-52}"
ARO_MIN_DSV5_VCPUS="${ARO_MIN_DSV5_VCPUS:-52}"

read -r REGIONAL_CURRENT REGIONAL_LIMIT <<<"$(
  az vm list-usage --location "$AZURE_LOCATION" \
    --query "[?name.value=='cores'].[currentValue,limit] | [0]" -o tsv
)"
read -r DSV5_CURRENT DSV5_LIMIT <<<"$(
  az vm list-usage --location "$AZURE_LOCATION" \
    --query "[?contains(name.value, 'standardDSv5Family')].[currentValue,limit] | [0]" -o tsv
)"

if [[ -z "${REGIONAL_LIMIT:-}" || -z "${DSV5_LIMIT:-}" ]]; then
  echo "Unable to read Azure regional or Standard DSv5 quota for ${AZURE_LOCATION}" >&2
  exit 6
fi

REGIONAL_AVAILABLE=$((REGIONAL_LIMIT - REGIONAL_CURRENT))
DSV5_AVAILABLE=$((DSV5_LIMIT - DSV5_CURRENT))

printf 'ARO quota preflight: regional_available=%s regional_required=%s dsv5_available=%s dsv5_required=%s\n' \
  "$REGIONAL_AVAILABLE" "$ARO_MIN_REGIONAL_VCPUS" "$DSV5_AVAILABLE" "$ARO_MIN_DSV5_VCPUS"

if (( REGIONAL_AVAILABLE < ARO_MIN_REGIONAL_VCPUS )); then
  echo "Insufficient regional vCPU quota in ${AZURE_LOCATION}: available=${REGIONAL_AVAILABLE}, required>=${ARO_MIN_REGIONAL_VCPUS}" >&2
  exit 6
fi
if (( DSV5_AVAILABLE < ARO_MIN_DSV5_VCPUS )); then
  echo "Insufficient Standard DSv5 family vCPU quota in ${AZURE_LOCATION}: available=${DSV5_AVAILABLE}, required>=${ARO_MIN_DSV5_VCPUS}" >&2
  exit 6
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
