# I4 — Backtesting and experiment discipline

Iteration 4 adds a deterministic event-driven backtest slice to validate execution mechanics and experiment hygiene before ML or agentic decisioning.

## Core rules

- signals are assumed to be emitted at bar close;
- execution is allowed only from the next available bar open;
- no random shuffle is used for time-series validation;
- only signals with `risk_status=APPROVED` are executable;
- spread, slippage and commission are explicit config inputs;
- LONG entries pay ask-side cost and LONG exits receive bid-side cost; SHORT is symmetric;
- stop/target ambiguity inside one OHLC bar defaults to conservative `STOP_FIRST`;
- open trades are closed at the final available bar and labelled `END_OF_DATA`;
- gaps that make stop/target levels invalid at entry are skipped rather than silently repaired.

## Versioned inputs

- dataset fixture: `data/replay/i4_backtest_dataset.json`;
- protocol: `experiments/i4_backtest_protocol.json`;
- result schema: `schemas/events/backtest.result.schema.json`;
- CLI demonstration: `python scripts/demo_backtest.py`.

The report records both `dataset_sha256` and `config_sha256`, so a result can be tied to data, assumptions and Git commit.

## Metrics

The engine reports:

- trade count and win rate;
- total and average PnL;
- average R / expectancy R;
- gross profit / gross loss and profit factor;
- maximum drawdown and maximum drawdown percentage;
- MFE and MAE in R on each trade;
- breakdowns by regime, session, timeframe and pattern;
- buy-and-hold baseline using the same spread/slippage/commission model.

Sharpe/Sortino are intentionally not emitted from the tiny synthetic fixture because irregular or statistically insignificant samples would create misleading precision. They can be added when I4 is run on a sufficiently large historical series with an explicit return-frequency convention.

## Out-of-sample and walk-forward

`chronological_split` creates a strictly ordered train/test partition. `walk_forward_windows` creates rolling windows where every training interval ends before its corresponding test interval starts. No future observation is made available to the train interval.

The synthetic I4 fixture is only a mechanics test. It is not a training set and it is not evidence that any pattern is profitable.

## Reference engines

The internal I4 engine is deliberately small and transparent so execution assumptions are reviewable. It does not replace independent validation against a mature trading engine.

As reviewed on 2026-09-11:

- NautilusTrader documentation recommends the config-driven `BacktestNode` workflow for production-style backtesting and reuse of strategy components in live operation. The current release line includes `2.0.0rc4`, so any comparison POC must pin an exact tested release rather than silently following a release candidate.
- QuantConnect LEAN remains an event-driven open-source engine and supports local backtesting through its CLI. It is retained as an independent comparison option.

Reference URLs:

- https://nautilustrader.io/docs/latest/getting_started/backtest_high_level/
- https://github.com/nautechsystems/nautilus_trader/releases
- https://github.com/QuantConnect/Lean
- https://www.quantconnect.com/docs/v2/lean-cli/api-reference/lean-backtest

No NautilusTrader or LEAN run is claimed by I4 itself.

## Explicit non-claims

Iteration 4 does **not** claim:

- profitability on real historical markets;
- statistically significant expectancy;
- real IG spread/slippage distributions;
- out-of-sample alpha;
- calibrated probabilities;
- live execution readiness.

Those claims require pinned real historical data, repeated out-of-sample/walk-forward runs and evidence retained per dataset/config/commit.
