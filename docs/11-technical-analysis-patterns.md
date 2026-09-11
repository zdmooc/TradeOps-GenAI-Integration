# I2 — Deterministic technical and pattern engines

## Scope

Iteration 2 adds deterministic market-analysis capabilities on top of the canonical market-data/replay
foundation from I1. No LLM or ML model is used for indicator values, market structure or pattern
detection.

## Package

`services/technical_analysis/`

### Canonical bar model and multi-timeframe aggregation

`models.py` defines validated OHLCV `Bar`, indicator, market-structure and pattern contracts.

`aggregation.py` provides:

- conversion of IG historical `MarketEvent` BAR events to canonical OHLCV bars;
- tick/event aggregation into M1/M5/M15/M30/H1/H4/D1 bars;
- deterministic resampling from finer to coarser bars;
- multi-timeframe views with OHLCV conservation.

### Indicators

`indicators.py` implements directly in deterministic Python:

- EMA;
- VWAP;
- ATR with Wilder smoothing;
- ADX, +DI and -DI;
- RSI with Wilder smoothing;
- MACD and signal/histogram;
- Bollinger middle/upper/lower bands.

The purpose is transparency and reproducibility. These functions are not delegated to an LLM.

### Market structure

`structure.py` detects confirmed swing highs/lows using configurable left/right windows and labels:

- `HH` — Higher High;
- `HL` — Higher Low;
- `LH` — Lower High;
- `LL` — Lower Low.

A structure is classified BULLISH when the last two confirmed swing highs and lows both rise, BEARISH
when both fall, RANGE when they disagree, and UNKNOWN when there is insufficient confirmed structure.

### Patterns

`patterns.py` implements deterministic rules for:

- breakout + retest;
- failed breakout;
- pullback;
- support/resistance rejection;
- compression -> expansion;
- gap;
- liquidity sweep.

Every emitted `PatternSignal` includes:

- direction;
- timeframe;
- entry reference;
- numeric invalidation level;
- explicit preconditions;
- human-readable invalidation rule;
- machine-readable evidence;
- lookback used.

The contract is versioned in `schemas/events/technical.pattern.schema.json`.

## Replay-labelled examples

`data/replay/i2_labelled_patterns.json` contains deterministic labelled OHLCV examples. They are not
claims about market profitability. They are fixtures proving that a given formal rule produces the
expected label.

Run:

```bash
python scripts/demo_technical_analysis.py
```

Expected logical result:

```text
breakout_retest_long ... matched=True
failed_breakout_short ... matched=True
```

## Tests

Dedicated suite:

```bash
pytest -q tests/test_technical_analysis_i2.py
```

Coverage includes:

- indicator determinism and bounds/invariants;
- multi-timeframe OHLCV aggregation;
- HH/HL bullish structure;
- breakout/retest;
- failed breakout;
- pullback;
- support rejection;
- compression/expansion;
- gap;
- liquidity sweep;
- labelled replay examples and formal pattern evidence.

The full repository CI remains authoritative after push.

## Architecture boundary

I2 produces deterministic technical evidence. It does **not** yet:

- classify market regime (I3);
- implement the target deterministic risk gate (I3);
- prove strategy profitability/backtesting quality (I4);
- produce calibrated ML probabilities (I5);
- use agents to decide patterns (I6);
- authorize live-money execution.

The existing legacy demo `signal_engine` is not considered the I2 implementation and its arbitrary
fractional-price BUY/SELL rule remains outside the target architecture until it is removed/replaced in
the appropriate integration step.
