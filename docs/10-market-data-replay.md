# I1 — Canonical market data and deterministic replay

## Scope

Iteration 1 establishes trustworthy market input before indicators, patterns, ML or agents.

Implemented components:

- `MarketEvent` canonical model with UTC event/ingest timestamps, bid/ask/last, spread,
  market status, source, latency, staleness and metadata;
- IG REST v2 session authentication and v3 historical `/prices/{epic}` adapter;
- IG Lightstreamer `PRICE:{account}:{epic}` adapter using the `Pricing` data adapter and
  `BIDPRICE1`, `ASKPRICE1`, `TIMESTAMP`, `DLG_FLAG` fields;
- data-quality engine for stale, duplicate, out-of-order, future timestamp, missing price and
  invalid spread events;
- deterministic replay clock and JSONL capture/replay support;
- JSON Schema for the canonical event;
- versioned replay fixture and tests.

## IG configuration

Use an IG **demo** account first. Never commit credentials.

```bash
export IG_API_KEY='...'
export IG_IDENTIFIER='...'
export IG_PASSWORD='...'
```

REST demo base URL:

```text
https://demo-api.ig.com/gateway/deal
```

The adapter uses POST `/session` version 2 to obtain CST and X-SECURITY-TOKEN, then GET
`/prices/{epic}` version 3 for historical data. The Lightstreamer endpoint returned by the
session response is used dynamically and is never hard-coded.

## Replay demo

```bash
python scripts/demo_market_replay.py
```

Expected fixture result:

```text
accepted=2 rejected=0
```

## Tests

```bash
pytest -q tests/test_market_data_i1.py
```

The tests do not require real IG credentials. HTTP and Lightstreamer transports are replaced
with deterministic fakes so protocol mapping, canonicalisation and quality rules are reproducible.

## Evidence boundary

Implemented and locally validated in I1:

- canonical model;
- REST protocol mapping with mocked IG responses;
- Lightstreamer PRICE subscription mapping with a fake SDK client;
- stale/bad-spread/duplicate/out-of-order tests;
- deterministic replay tests.

Not claimed without user credentials/network evidence:

- successful authentication against an actual IG demo account;
- live Lightstreamer connection;
- measured real-world market-data latency.

Those live checks should be captured as separate evidence before any "live input validated" claim.
