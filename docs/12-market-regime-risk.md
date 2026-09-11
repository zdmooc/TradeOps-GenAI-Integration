# I3 — Market regime and deterministic risk v1

## Scope

Iteration 3 adds a deterministic regime classifier and a fail-closed risk gate on top of the
canonical market data and technical-analysis layers delivered by I1/I2.

No LLM or agent may override the risk decision.

## Market regimes

`services/market_regime/engine.py` classifies:

- `TREND_UP` and `TREND_DOWN` from I2 structure plus ADX;
- `RANGE` from range structure or low ADX;
- `HIGH_VOLATILITY` and `LOW_VOLATILITY` from ATR as a percentage of price;
- `BREAKOUT` from I2 breakout/compression-expansion patterns;
- `POST_EVENT` from an explicit high-impact-event time window;
- `RISK_ON` and `RISK_OFF` from an explicit external context flag;
- `UNKNOWN` when evidence is insufficient.

The precedence is deterministic: post-event -> explicit risk sentiment -> breakout -> volatility
-> trend -> range -> unknown. `UNKNOWN` has an empty strategy allowlist and therefore fails closed.

Each regime carries a strategy allowlist. The defaults are policy examples and are configurable;
they are not claims of profitability.

## Risk policy

`services/risk_engine/policy.py` evaluates a validated `TradeIntent`, `RiskState` and
`RegimeSnapshot`. Default gates cover:

- risk per trade;
- daily loss;
- gross exposure;
- instrument concentration;
- correlated exposure;
- ATR volatility;
- high-impact event blackout;
- spread;
- estimated slippage;
- market-data freshness;
- regime strategy allowlist;
- unknown-regime fail-closed behavior.

Circuit breakers are explicit for manual kill switch, degraded feed, daily-loss limit and maximum
consecutive losses. All triggered veto reasons are returned together in a stable deterministic
order.

Exposure calculations are deliberately conservative in I3: the proposed notional is added to
absolute existing exposure. Netting and portfolio optimization belong to later portfolio/risk
work and are not silently assumed here.

## Event adapter and legacy worker

`services/risk_engine/adapter.py` requires three explicit sections:

- `risk_intent`;
- `risk_state`;
- `regime`.

The Kafka worker now uses this adapter. Legacy `signals.generated` messages that do not provide
that I3 context are vetoed as `I3_CONTEXT_INVALID`; the old fixed `qty=100/MAX_QTY` placeholder
has been removed. This intentionally prevents the arbitrary legacy signal engine from being
accepted by the target risk gate without the required state.

## Schemas

- `schemas/events/market.regime.schema.json`
- `schemas/events/risk.decision.schema.json`

## Reproducible demo

```bash
python scripts/demo_risk_gate.py
```

The versioned scenarios contain one approved trade and one veto caused by stale market data plus
an excessive spread. They are policy-rule evidence only, not P&L evidence.

## Tests

```bash
pytest -q tests/test_market_regime_risk_i3.py
```

Dedicated tests include positive and negative cases for regimes, allowlists, all major risk gates,
circuit breakers, deterministic output and fail-closed event adaptation.

## Non-claims

I3 does not claim profitability, optimized position sizing, portfolio VaR, calibrated probability,
backtest expectancy, drawdown or walk-forward performance. Backtesting discipline belongs to I4.
Automated real-money execution remains outside scope.
