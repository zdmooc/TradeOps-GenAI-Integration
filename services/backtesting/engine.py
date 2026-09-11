from __future__ import annotations

from dataclasses import asdict
from collections.abc import Sequence

from services.technical_analysis.models import Bar

from .dataset import canonical_sha256
from .execution import buy_and_hold_baseline, entry_fill, exit_fill
from .metrics import breakdown_metrics, compute_metrics
from .models import BacktestConfig, BacktestReport, BacktestSignal, TradeResult


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(
        self,
        bars: Sequence[Bar],
        signals: Sequence[BacktestSignal],
        dataset_id: str,
        dataset_sha256: str | None = None,
    ) -> BacktestReport:
        ordered_bars = sorted(bars, key=lambda bar: bar.start_time)
        if not ordered_bars:
            raise ValueError("at least one bar is required")
        if any(not bar.complete for bar in ordered_bars):
            raise ValueError("backtest requires complete bars")

        dataset_hash = dataset_sha256 or canonical_sha256(
            [bar.to_dict() for bar in ordered_bars]
        )
        config_hash = canonical_sha256(asdict(self.config))
        trades: list[TradeResult] = []
        skipped: list[str] = []

        for signal in sorted(signals, key=lambda item: (item.generated_at, item.signal_id)):
            if signal.risk_status != "APPROVED":
                skipped.append(f"{signal.signal_id}:RISK_{signal.risk_status}")
                continue
            instrument_bars = [
                bar for bar in ordered_bars if bar.instrument == signal.instrument
            ]
            entry_index = next(
                (
                    index
                    for index, bar in enumerate(instrument_bars)
                    if bar.start_time >= signal.generated_at
                ),
                None,
            )
            if entry_index is None:
                skipped.append(f"{signal.signal_id}:NO_ENTRY_BAR")
                continue
            entry_bar = instrument_bars[entry_index]
            entry_reference = entry_bar.open
            if signal.side == "LONG" and not (
                signal.stop < entry_reference < signal.target
            ):
                skipped.append(f"{signal.signal_id}:INVALID_LEVELS_AT_ENTRY")
                continue
            if signal.side == "SHORT" and not (
                signal.target < entry_reference < signal.stop
            ):
                skipped.append(f"{signal.signal_id}:INVALID_LEVELS_AT_ENTRY")
                continue

            filled_entry = entry_fill(entry_reference, signal.side, self.config)
            stop_fill = exit_fill(signal.stop, signal.side, self.config)
            stop_gross = self._signed_move(
                filled_entry,
                stop_fill,
                signal.side,
                signal.quantity,
                signal.point_value,
            )
            risk_amount = abs(stop_gross - 2.0 * self.config.commission_per_order)
            if risk_amount <= 0:
                skipped.append(f"{signal.signal_id}:ZERO_RISK")
                continue

            trade = self._run_trade(
                instrument_bars,
                entry_index,
                signal,
                entry_reference,
                filled_entry,
                risk_amount,
            )
            trades.append(trade)

        metrics = compute_metrics(trades, self.config.initial_equity)
        breakdowns = breakdown_metrics(trades, self.config.initial_equity)
        baseline = buy_and_hold_baseline(
            ordered_bars[0].open,
            ordered_bars[-1].close,
            self.config,
        )
        return BacktestReport(
            dataset_id=dataset_id,
            dataset_sha256=dataset_hash,
            config_sha256=config_hash,
            trades=tuple(trades),
            skipped_signals=tuple(skipped),
            metrics=metrics,
            breakdowns=breakdowns,
            baseline=baseline,
        )

    def _run_trade(
        self,
        bars: list[Bar],
        entry_index: int,
        signal: BacktestSignal,
        entry_reference: float,
        filled_entry: float,
        risk_amount: float,
    ) -> TradeResult:
        exit_reference = bars[-1].close
        exit_reason = "END_OF_DATA"
        exit_index = len(bars) - 1
        best_points = 0.0
        adverse_points = 0.0

        for index in range(entry_index, len(bars)):
            bar = bars[index]
            if signal.side == "LONG":
                best_points = max(best_points, bar.high - filled_entry)
                adverse_points = max(adverse_points, filled_entry - bar.low)
                stop_hit = bar.low <= signal.stop
                target_hit = bar.high >= signal.target
            else:
                best_points = max(best_points, filled_entry - bar.low)
                adverse_points = max(adverse_points, bar.high - filled_entry)
                stop_hit = bar.high >= signal.stop
                target_hit = bar.low <= signal.target

            if stop_hit and target_hit:
                if self.config.ambiguity_policy == "STOP_FIRST":
                    exit_reference = signal.stop
                    exit_reason = "STOP_AMBIGUOUS"
                else:
                    exit_reference = signal.target
                    exit_reason = "TARGET_AMBIGUOUS"
                exit_index = index
                break
            if stop_hit:
                exit_reference = signal.stop
                exit_reason = "STOP"
                exit_index = index
                break
            if target_hit:
                exit_reference = signal.target
                exit_reason = "TARGET"
                exit_index = index
                break

        filled_exit = exit_fill(exit_reference, signal.side, self.config)
        pnl = self._signed_move(
            filled_entry,
            filled_exit,
            signal.side,
            signal.quantity,
            signal.point_value,
        ) - 2.0 * self.config.commission_per_order
        scale = signal.quantity * signal.point_value / risk_amount
        return TradeResult(
            signal_id=signal.signal_id,
            instrument=signal.instrument,
            side=signal.side,
            pattern=signal.pattern,
            regime=signal.regime,
            session=signal.session,
            timeframe=signal.timeframe,
            entry_time=bars[entry_index].start_time,
            exit_time=bars[exit_index].end_time,
            entry_reference=entry_reference,
            entry_fill=filled_entry,
            exit_reference=exit_reference,
            exit_fill=filled_exit,
            quantity=signal.quantity,
            point_value=signal.point_value,
            pnl=pnl,
            r_multiple=pnl / risk_amount,
            mfe_r=best_points * scale,
            mae_r=-adverse_points * scale,
            exit_reason=exit_reason,
            bars_held=exit_index - entry_index + 1,
        )

    @staticmethod
    def _signed_move(
        entry: float,
        exit_value: float,
        side: str,
        quantity: float,
        point_value: float,
    ) -> float:
        direction = 1.0 if side == "LONG" else -1.0
        return (exit_value - entry) * direction * quantity * point_value
