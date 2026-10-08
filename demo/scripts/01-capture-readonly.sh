#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
bash demo/scripts/00-preflight.sh

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$ROOT/.runtime/tradeops-demo/$timestamp"
mkdir -p "$out"
commands=0
nonzero=0

capture() {
  local name="$1"
  shift
  local rc=0
  {
    printf 'COMMAND: '
    printf '%q ' "$@"
    printf '\n'
    "$@" || rc=$?
    printf '\nEXIT_CODE=$rc\n'
  } > "$out/$name.txt" 2>&1
  commands=$((commands + 1))
  if (( rc != 0 )); then
    nonzero=$((nonzero + 1))
    printf '%s\t%s\n' "$name" "$rc" >> "$out/nonzero.txt"
  fi
}

capture 01-clusterversion oc get clusterversion version
capture 02-clusteroperators oc get clusteroperators
capture 03-nodes oc get nodes -o wide
capture 04-node-top oc adm top nodes
capture 05-node-capacity oc describe node crc
capture 06-namespaces oc get namespace tradeops
capture 07-workloads oc -n tradeops get deployments,statefulsets,pods -o wide
capture 08-pod-top oc adm top pods -n tradeops
capture 09-hpa-pdb-cronjobs oc -n tradeops get hpa,pdb,cronjob
capture 10-routes-services oc -n tradeops get routes,services
capture 11-endpointslices oc -n tradeops get endpointslices.discovery.k8s.io
capture 12-networkpolicies oc -n tradeops get networkpolicies
capture 13-rbac oc -n tradeops get serviceaccounts,roles,rolebindings
capture 14-quotas-limits oc -n tradeops get resourcequotas,limitranges
capture 15-pvc oc -n tradeops get pvc
capture 16-storageclass oc get storageclass
capture 17-gitops-applications oc get applications.argoproj.io -A
capture 18-gitops-pods oc -n openshift-gitops get pods
capture 19-platform-consumption oc get capabilityconsumptions -A
capture 20-platform-operator oc -n shared-platform-services get deployment,pods
capture 21-olm-csv oc get clusterserviceversions.operators.coreos.com -A
capture 22-monitoring-pods oc -n openshift-monitoring get pods
capture 23-events-tradeops oc -n tradeops get events --sort-by=.metadata.creationTimestamp
capture 24-events-warning oc get events -A --field-selector=type=Warning
capture 25-mq-reference oc -n mayabank-mq-local get deployments,statefulsets,pods,services
capture 26-git-commit git rev-parse HEAD

{
  echo "TRADEOPS_DEMO_CAPTURE=COMPLETE"
  echo "timestamp_utc=$timestamp"
  echo "commands_executed=$commands"
  echo "commands_nonzero=$nonzero"
  echo "evidence_directory=$out"
  echo "mode=READ_ONLY"
  echo "note=Nonzero means command failed, not necessarily a live application incident"
  echo "privacy=Review files before sharing; environment metadata and internal addresses may appear"
} > "$out/00-summary.txt"
cat "$out/00-summary.txt"
