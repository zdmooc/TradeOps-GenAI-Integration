#!/usr/bin/env bash
set -euo pipefail

command -v trivy >/dev/null || { echo "trivy is required"; exit 1; }
: "${IMAGE_REF:?set IMAGE_REF to an externally reachable TradeOps runtime image reference}"

trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$IMAGE_REF"
echo "I9_IMAGE_SCAN_PASS"
