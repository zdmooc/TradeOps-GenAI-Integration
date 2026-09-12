# O3 — Live multi-source market replay evidence

## Objective

Close the `LIVE_MULTI_SOURCE_REPLAY` graduation criterion with retained operational evidence from two independent real market-data sources while preserving the deterministic I1 canonical model and replay engine.

The O3 flow is data-only. It does not place orders and does not enable autonomous execution.

## Sources

### Source 1 — IG REST

The existing `IGRestClient` is reused. O3 authenticates to an IG account and retrieves recent one-minute bars through the REST price endpoint. Use `IG_ENV=demo` first.

Default crypto epic:

```text
CS.D.BITCOIN.CFD.IP
```

Credentials are supplied only through environment variables and are never written to the evidence directory:

```bash
export IG_ENV=demo
export IG_API_KEY='...'
export IG_IDENTIFIER='...'
export IG_PASSWORD='...'
```

Do not paste or commit these values.

### Source 2 — Kraken public Spot REST

`services/market_data/kraken_rest.py` adds a second independent provider using Kraken's public OHLC endpoint. It requires no API key.

Default pair:

```text
XBTUSD
```

O3 captures committed one-minute bars only. Kraken documents that the final OHLC row is the current, not-yet-committed interval, so the adapter removes that row for deterministic replay evidence.

## Evidence flow

Run:

```bash
bash scripts/o3_live_multi_source_replay.sh
```

Optional controls:

```bash
export IG_EPIC='CS.D.BITCOIN.CFD.IP'
export KRAKEN_PAIR='XBTUSD'
export O3_POINTS=20
export O3_MAX_SOURCE_AGE_SECONDS=1800
```

The script:

1. authenticates to IG without logging credentials or session tokens;
2. captures recent IG one-minute bars;
3. captures recent committed Kraken one-minute bars;
4. requires exactly two canonical source identifiers: `IG_REST` and `KRAKEN_REST`;
5. rejects stale captures older than the configured live-evidence threshold;
6. writes both captures and one combined canonical JSONL file;
7. replays the combined file twice through `ReplayEngine`;
8. requires every captured event to pass the deterministic data-quality gate;
9. requires both replay runs to be byte-equivalent at the canonical event level;
10. scans retained evidence for the IG API key, identifier and password values;
11. emits `LIVE_MULTI_SOURCE_REPLAY_PASS` only after every check succeeds.

## Expected terminal evidence

```text
O3_LIVE_ACQUISITION_PASS sources=2 ...
O3_DETERMINISTIC_REPLAY_PASS ... rejected=0
O3_SECRET_SCAN_PASS
LIVE_MULTI_SOURCE_REPLAY_PASS
Evidence directory: .../evidence/graduation/live/market-data/<UTC timestamp>
```

The evidence directory contains provider-specific canonical captures, the combined replay file, acquisition/replay summaries and a secret-scan result.

## Evidence boundary

A successful O3 run proves that two independent external providers were actually queried, their real market bars were normalized to the same canonical model, freshness was checked, and the retained capture replays deterministically.

It does not prove execution quality, real-money profitability, broker fill quality, or low-latency co-location. Paper/shadow outcome graduation remains a separate gate.
