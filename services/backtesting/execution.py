from __future__ import annotations

from .models import BacktestConfig


def entry_fill(price: float, side: str, config: BacktestConfig) -> float:
    half_spread = config.spread_bps / 2.0
    cost_fraction = (half_spread + config.slippage_bps) / 10_000.0
    return price * (1.0 + cost_fraction) if side == "LONG" else price * (1.0 - cost_fraction)


def exit_fill(price: float, side: str, config: BacktestConfig) -> float:
    half_spread = config.spread_bps / 2.0
    cost_fraction = (half_spread + config.slippage_bps) / 10_000.0
    return price * (1.0 - cost_fraction) if side == "LONG" else price * (1.0 + cost_fraction)


def buy_and_hold_baseline(open_price: float, close_price: float, config: BacktestConfig) -> dict[str, float]:
    entry = entry_fill(open_price, "LONG", config)
    exit_value = exit_fill(close_price, "LONG", config)
    pnl = exit_value - entry - 2.0 * config.commission_per_order
    return {
        "entry_fill": entry,
        "exit_fill": exit_value,
        "pnl_per_unit": pnl,
        "return_pct": pnl / entry * 100.0,
    }
