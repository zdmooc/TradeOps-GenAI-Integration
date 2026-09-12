# I12 graduation evidence intake

This directory is reserved for **real graduation evidence**. Synthetic fixtures must not be copied here and must not be relabelled as live evidence.

## Paper/shadow records

The graduation gate looks for `paper-shadow-records.jsonl`. The file is intentionally absent until real PAPER/SHADOW observations exist.

Every counted line must be one JSON object with:

- `signal_id`: unique identifier;
- `mode`: `PAPER` or `SHADOW`;
- `source`: `LIVE_MARKET` or `RECORDED_REAL_MARKET`;
- `state`: `CLOSED`;
- `observed_at`: timezone-aware ISO-8601 timestamp;
- `closed_at`: timezone-aware ISO-8601 timestamp;
- `realized_r`: finite numeric realized R multiple;
- `evidence_ref`: non-empty reference to the underlying decision/outcome evidence.

A duplicate `signal_id` counts once. Synthetic records, open records and records without realized outcome metrics count zero.

The program requires at least **100 unique valid outcomes** before `PAPER_SHADOW_100_OUTCOMES` can be satisfied.

## Live/deployment evidence

The following graduation criteria require `LIVE` or `OPERATIONAL` evidence plus a timezone-aware `verified_at` value before they can be marked `SATISFIED`:

- `LIVE_MULTI_SOURCE_REPLAY`;
- `OBSERVABILITY_SECURITY_LIVE`;
- `OPENSHIFT_AZURE_DEPLOYMENT`;
- `RESILIENCE_FINOPS_GREENOPS_VERIFIED`.

Examples of acceptable evidence include captured live feed/replay identifiers, retained trace correlation, deployment verification output, measured recovery exercise results, and measured FinOps/GreenOps reports. A design document or synthetic test alone is not enough.

## Graduation command

Audit current status without pretending success:

```bash
python scripts/i12_graduation_check.py --expect-status NOT_GRADUATED
```

Only after all real evidence is present and independently reviewed should the strict command be allowed to pass:

```bash
python scripts/i12_graduation_check.py --require-graduated
```
