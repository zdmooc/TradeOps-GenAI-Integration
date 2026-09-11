from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import PerformanceMetrics, TradeResult


def compute_metrics(trades: Iterable[TradeResult], initial_equity: float) -> PerformanceMetrics:
    ordered = list(trades)
    if not ordered:
        return PerformanceMetrics(
            trade_count=0,
            win_rate_pct=0.0,
            total_pnl=0.0,
            average_pnl=0.0,
            average_r=0.0,
            expectancy_r=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            profit_factor=None,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
        )

    pnls = [trade.pnl for trade in ordered]
    r_values = [trade.r_multiple for trade in ordered]
    gross_profit = sum(value for value in pnls if value > 0)
    gross_loss = abs(sum(value for value in pnls if value < 0))
    equity = initial_equity
    peak = initial_equity
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = peak - equity
        drawdown_pct = drawdown / peak * 100.0 if peak else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

    winners = sum(1 for value in pnls if value > 0)
    average_r = sum(r_values) / len(r_values)
    return PerformanceMetrics(
        trade_count=len(ordered),
        win_rate_pct=winners / len(ordered) * 100.0,
        total_pnl=sum(pnls),
        average_pnl=sum(pnls) / len(pnls),
        average_r=average_r,
        expectancy_r=average_r,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=(gross_profit / gross_loss) if gross_loss > 0 else None,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
    )


def breakdown_metrics(
    trades: Iterable[TradeResult],
    initial_equity: float,
) -> dict[str, dict[str, PerformanceMetrics]]:
    ordered = list(trades)
    dimensions = ("regime", "session", "timeframe", "pattern")
    result: dict[str, dict[str, PerformanceMetrics]] = {}
    for dimension in dimensions:
        groups: dict[str, list[TradeResult]] = defaultdict(list)
        for trade in ordered:
            groups[str(getattr(trade, dimension))].append(trade)
        result[dimension] = {
            key: compute_metrics(group, initial_equity)
            for key, group in sorted(groups.items())
        }
    return result
