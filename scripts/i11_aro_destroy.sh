#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?required}"
: "${ARO_RESOURCE_GROUP:?required}"
: "${ARO_CLUSTER_NAME:?required}"

if [[ "${ALLOW_AZURE_DESTROY:-0}" != "1" ]]; then
  echo "Refusing Azure deletion. Set ALLOW_AZURE_DESTROY=1 only when the target cluster has been verified." >&2
  exit 2
fi

if [[ "${DESTROY_FOUNDATION:-0}" == "1" ]]; then
  : "${TF_VAR_subscription_id:?required when DESTROY_FOUNDATION=1}"
  : "${TF_VAR_tenant_id:?required when DESTROY_FOUNDATION=1}"
  if [[ "${ALLOW_AZURE_FOUNDATION_DESTROY:-0}" != "1" ]]; then
    echo "Refusing foundation deletion. Set ALLOW_AZURE_FOUNDATION_DESTROY=1 after reviewing terraform plan -destroy." >&2
    exit 2
  fi
fi

az account set --subscription "$AZURE_SUBSCRIPTION_ID"

if az aro show --resource-group "$ARO_RESOURCE_GROUP" --name "$ARO_CLUSTER_NAME" >/dev/null 2>&1; then
  az aro delete --resource-group "$ARO_RESOURCE_GROUP" --name "$ARO_CLUSTER_NAME" --yes
else
  echo "ARO cluster is already absent: ${ARO_RESOURCE_GROUP}/${ARO_CLUSTER_NAME}"
fi

if az aro show --resource-group "$ARO_RESOURCE_GROUP" --name "$ARO_CLUSTER_NAME" >/dev/null 2>&1; then
  echo "ARO cluster still exists after delete request; refusing to continue with foundation destroy." >&2
  exit 1
fi

echo "ARO cluster deletion verified."

if [[ "${DESTROY_FOUNDATION:-0}" == "1" ]]; then
  terraform -chdir=infra/azure-enterprise/terraform init -input=false
  terraform -chdir=infra/azure-enterprise/terraform plan -destroy -input=false -out=destroy.tfplan
  terraform -chdir=infra/azure-enterprise/terraform apply -input=false -auto-approve destroy.tfplan
  rm -f infra/azure-enterprise/terraform/destroy.tfplan
  echo "Terraform-managed Azure foundation destroy completed. Verify the resource group and any soft-deleted Key Vault separately."
else
  echo "Foundation resources were intentionally retained. Set DESTROY_FOUNDATION=1 plus ALLOW_AZURE_FOUNDATION_DESTROY=1 for the Terraform-managed foundation cleanup."
fi
