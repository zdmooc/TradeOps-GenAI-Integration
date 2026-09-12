#!/usr/bin/env bash
set -euo pipefail

command -v crc >/dev/null || { echo "crc is required"; exit 1; }
command -v oc >/dev/null || { echo "oc is required"; exit 1; }
command -v helm >/dev/null || { echo "helm is required"; exit 1; }

crc status
oc whoami >/dev/null
oc version
oc get nodes

echo "I9_CRC_PREFLIGHT_PASS"
