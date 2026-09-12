#!/usr/bin/env bash
set -euo pipefail

: "${ARO_RESOURCE_GROUP:?required}"
: "${ARO_CLUSTER_NAME:?required}"

az aro delete --resource-group "$ARO_RESOURCE_GROUP" --name "$ARO_CLUSTER_NAME" --yes

echo "ARO cluster deletion requested. Managed identities and shared foundation resources must be reviewed separately before deletion."
