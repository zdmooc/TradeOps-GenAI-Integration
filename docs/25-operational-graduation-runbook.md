# Operational Graduation Runbook

This runbook starts the post-I12 operational evidence phase. It does not create an Iteration 13.

## O1 — CRC / OpenShift Local live deployment

Goal: convert the I9 status from CI-validated packaging to captured LIVE_OPERATIONAL evidence on the actual CRC cluster.

### Preconditions

- repository checked out on the workstation;
- CRC running;
- `oc` authenticated to the CRC cluster;
- Helm available;
- sufficient CRC disk/RAM for the TradeOps target slice.

The runner deliberately requires passwords through environment variables and never persists their values in evidence files.

### Windows Git Bash sequence

```bash
git checkout main
git pull --ff-only
crc status
oc whoami

export POSTGRES_PASSWORD='SET-A-LOCAL-LAB-PASSWORD'
export GRAFANA_ADMIN_PASSWORD='SET-A-LOCAL-LAB-PASSWORD'
export DEPLOY_MODE=direct

bash scripts/o1_crc_graduation.sh
```

Do not commit the password values. After the run, clear them from the current shell:

```bash
unset POSTGRES_PASSWORD
unset GRAFANA_ADMIN_PASSWORD
```

### Successful exit condition

The command must end with:

```text
O1_CRC_LIVE_EVIDENCE_PASS
```

The underlying I9 verifier must also emit:

```text
I9_CRC_VERIFY_PASS
```

### Evidence generated

The runner writes only non-secret operational evidence under:

```text
evidence/graduation/live/crc/<UTC_TIMESTAMP>/
```

Evidence includes:

- CRC status;
- client/server OpenShift version;
- nodes;
- deployment transcript;
- rollout verification;
- pods/workloads;
- routes/services;
- quotas, LimitRanges and NetworkPolicies;
- Helm release inventory;
- pod/node metrics when available;
- agent-controller `/health` response;
- summary containing timestamp, exact Git commit and evidence class.

### Failure handling

If O1 fails, do not mark the graduation criterion satisfied. Preserve the terminal output and diagnose the first failing stage before retrying.

Useful diagnostics:

```bash
oc -n tradeops get pods -o wide
oc -n tradeops get events --sort-by=.lastTimestamp | tail -80
oc -n tradeops describe pod <FAILED_POD>
oc -n tradeops logs <FAILED_POD> --all-containers --tail=200
oc describe node crc | sed -n '/Allocated resources:/,/Events:/p'
crc status
```

## O2 — Live multi-source market evidence

Starts only after O1 is stable. Capture IG plus one independent real source, preserve provenance and data quality, then create a deterministic replay corpus from the captured data.

## O3 — 100 PAPER/SHADOW outcomes

Starts after real-market input is stable. Only `LIVE_MARKET` or `RECORDED_REAL_MARKET` closed outcomes count. Synthetic fixtures never count toward the 100-outcome graduation criterion.

## O4 — Live observability/security

Capture retained OpenTelemetry traces, metrics, alerts and active identity/tool-policy evidence from a deployed environment.

## O5 — Resilience / FinOps / GreenOps and Azure/ARO verification

Perform measured recovery exercises and collect cost/resource/carbon evidence. Execute and verify the selected Azure/ARO slice without claiming what has not been deployed.

## Final graduation command

Only after all operational blockers have valid evidence:

```bash
python scripts/i12_graduation_check.py --require-graduated
```
