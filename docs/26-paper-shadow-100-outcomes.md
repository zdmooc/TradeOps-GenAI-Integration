# O4 — 100 paper/shadow outcomes on recorded real-market data

## Goal

Close the `PAPER_SHADOW_100_OUTCOMES` graduation blocker without using synthetic fixtures or sending broker orders.

O4 uses committed Kraken 1-minute OHLC bars as recorded real-market input. It generates deterministic SHADOW signals and closes each signal after a fixed future-bar horizon. The resulting JSONL records are written to the graduation gate's canonical path:

```text
evidence/graduation/paper-shadow-records.jsonl
```

## Safety boundary

O4 is observation-only:

- no broker order endpoint is called;
- no IG credentials are required;
- execution mode is `SHADOW_ONLY_NO_BROKER_ORDERS`;
- source classification is `RECORDED_REAL_MARKET`;
- every counted signal is closed from an actual later committed market bar.

This is evidence of pipeline operation, not evidence of trading profitability.

## Deterministic strategy

For each eligible committed bar:

1. compare the current close with the close three bars earlier;
2. classify direction as `LONG` or `SHORT`;
3. use the mean high-low range of the previous ten bars as an ATR-like risk unit, floored at 5 bps of entry price;
4. close the shadow signal three committed bars later;
5. compute realized-R as signed price change divided by the risk unit.

Strategy identifier:

```text
MOMENTUM_3BAR_ATR10_V1
```

The same captured bars always produce the same signal IDs and realized-R values.

## Run

From the repository root:

```bash
export O4_KRAKEN_PAIR='XBTUSD'
export O4_POINTS=240
export O4_OUTCOMES=100
export O4_HORIZON_BARS=3
export O4_WARMUP=10

bash scripts/o4_paper_shadow_100.sh
```

Expected terminal markers:

```text
O4_REAL_MARKET_CAPTURE_PASS
O4_PAPER_SHADOW_100_PASS
PAPER_SHADOW_100_OUTCOMES_PASS
```

## Evidence produced

Each run creates:

```text
evidence/graduation/live/paper-shadow/<timestamp>/00-summary.txt
evidence/graduation/live/paper-shadow/<timestamp>/01-kraken-real-market-capture.jsonl
evidence/graduation/live/paper-shadow/<timestamp>/02-paper-shadow-records.jsonl
evidence/graduation/live/paper-shadow/<timestamp>/03-summary.json
```

and updates:

```text
evidence/graduation/paper-shadow-records.jsonl
```

Each counted line includes the graduation-required fields:

- unique `signal_id`;
- `mode=SHADOW`;
- `source=RECORDED_REAL_MARKET`;
- `state=CLOSED`;
- timezone-aware `observed_at` and `closed_at`;
- finite numeric `realized_r`;
- non-empty `evidence_ref` pointing to the retained real-market capture.

After the run, execute:

```bash
python scripts/i12_graduation_check.py --expect-status NOT_GRADUATED
```

Before the manifest itself is promoted, the report should show `paper_shadow_valid_outcomes: 100` while `PAPER_SHADOW_100_OUTCOMES` remains a blocker. The manifest is changed to `SATISFIED` only after the live evidence and canonical records are committed and verified.
