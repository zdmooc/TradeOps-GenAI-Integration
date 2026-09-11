from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.backtesting import (
    BacktestConfig,
    BacktestEngine,
    BacktestSignal,
    chronological_split,
    load_experiment,
    walk_forward_windows,
)
from services.technical_analysis.models import Bar


UTC = timezone.utc
BASE = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
FIXTURE = Path(__file__).resolve().parents[1] / "data/replay/i4_backtest_dataset.json"


def test_fixture_contract_and_hash_are_stable():
    experiment = load_experiment(FIXTURE)
    assert experiment.dataset_id == "i4-synthetic-dax-m1-v1"
    assert len(experiment.bars) == 12
    assert len(experiment.signals) == 5
    assert len(experiment.dataset_sha256) == 64
    assert experiment.dataset_sha256 == load_experiment(FIXTURE).dataset_sha256


def test_next_bar_execution_avoids_same_bar_lookahead():
    experiment = load_experiment(FIXTURE)
    report = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    )
    first = next(trade for trade in report.trades if trade.signal_id == "I4-S1")
    assert first.entry_time == datetime(2026, 9, 11, 12, 1, tzinfo=UTC)
    assert first.entry_reference == pytest.approx(100.2)


def test_labelled_fixture_produces_expected_exit_reasons():
    experiment = load_experiment(FIXTURE)
    report = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    )
    reasons = {trade.signal_id: trade.exit_reason for trade in report.trades}
    assert reasons == {
        "I4-S1": "TARGET",
        "I4-S2": "STOP",
        "I4-S3": "TARGET",
        "I4-S4": "TARGET",
    }


def test_i3_vetoed_signal_is_never_traded():
    experiment = load_experiment(FIXTURE)
    report = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    )
    assert all(trade.signal_id != "I4-VETO" for trade in report.trades)
    assert "I4-VETO:RISK_VETOED" in report.skipped_signals
    assert report.metrics.trade_count == 4


def test_costs_reduce_reported_performance():
    experiment = load_experiment(FIXTURE)
    with_costs = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    )
    zero_cost = BacktestEngine(
        BacktestConfig(
            initial_equity=10_000.0,
            spread_bps=0.0,
            slippage_bps=0.0,
            commission_per_order=0.0,
        )
    ).run(experiment.bars, experiment.signals, experiment.dataset_id)
    assert with_costs.metrics.total_pnl < zero_cost.metrics.total_pnl


def test_report_is_deterministic_for_same_data_and_config():
    experiment = load_experiment(FIXTURE)
    engine = BacktestEngine(experiment.config)
    one = engine.run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    ).to_dict()
    two = engine.run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    ).to_dict()
    assert one == two


def test_metrics_include_drawdown_expectancy_and_profit_factor():
    experiment = load_experiment(FIXTURE)
    metrics = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    ).metrics
    assert metrics.trade_count == 4
    assert metrics.win_rate_pct == pytest.approx(75.0)
    assert metrics.max_drawdown > 0
    assert metrics.max_drawdown_pct > 0
    assert metrics.expectancy_r == pytest.approx(metrics.average_r)
    assert metrics.profit_factor is not None


def test_breakdowns_cover_required_dimensions():
    experiment = load_experiment(FIXTURE)
    report = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    )
    assert set(report.breakdowns) == {"regime", "session", "timeframe", "pattern"}
    assert "TREND_UP" in report.breakdowns["regime"]
    assert "RANGE" in report.breakdowns["regime"]
    assert "M1" in report.breakdowns["timeframe"]


def test_chronological_split_has_no_temporal_leakage():
    experiment = load_experiment(FIXTURE)
    split = chronological_split(list(experiment.bars), train_fraction=0.75)
    assert split.train_end <= split.test_start
    assert split.train_indices[1] < split.test_indices[0]


def test_walk_forward_windows_keep_train_before_test():
    experiment = load_experiment(FIXTURE)
    windows = walk_forward_windows(list(experiment.bars), 6, 3, 3)
    assert len(windows) == 2
    for window in windows:
        assert window.train_end <= window.test_start
        assert window.train_indices[1] < window.test_indices[0]


def test_ambiguous_bar_uses_conservative_stop_first_policy():
    bar = Bar(
        instrument="TEST",
        timeframe="M1",
        start_time=BASE,
        end_time=BASE + timedelta(minutes=1),
        open=100.0,
        high=102.0,
        low=98.0,
        close=100.0,
    )
    signal = BacktestSignal(
        signal_id="AMB",
        instrument="TEST",
        side="LONG",
        generated_at=BASE,
        stop=99.0,
        target=101.0,
        quantity=1.0,
    )
    report = BacktestEngine(BacktestConfig(ambiguity_policy="STOP_FIRST")).run(
        [bar], [signal], "ambiguous"
    )
    assert report.trades[0].exit_reason == "STOP_AMBIGUOUS"
    assert report.trades[0].pnl < 0


def test_end_of_data_closes_open_trade():
    bar = Bar(
        instrument="TEST",
        timeframe="M1",
        start_time=BASE,
        end_time=BASE + timedelta(minutes=1),
        open=100.0,
        high=100.5,
        low=99.5,
        close=100.2,
    )
    signal = BacktestSignal(
        signal_id="EOD",
        instrument="TEST",
        side="LONG",
        generated_at=BASE,
        stop=98.0,
        target=103.0,
        quantity=1.0,
    )
    report = BacktestEngine().run([bar], [signal], "eod")
    assert report.trades[0].exit_reason == "END_OF_DATA"


def test_gap_that_invalidates_levels_is_skipped():
    bar = Bar(
        instrument="TEST",
        timeframe="M1",
        start_time=BASE,
        end_time=BASE + timedelta(minutes=1),
        open=104.0,
        high=105.0,
        low=103.0,
        close=104.5,
    )
    signal = BacktestSignal(
        signal_id="GAP",
        instrument="TEST",
        side="LONG",
        generated_at=BASE,
        stop=99.0,
        target=103.0,
        quantity=1.0,
    )
    report = BacktestEngine().run([bar], [signal], "gap")
    assert not report.trades
    assert "GAP:INVALID_LEVELS_AT_ENTRY" in report.skipped_signals


def test_baseline_uses_same_cost_model():
    experiment = load_experiment(FIXTURE)
    report = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    )
    assert set(report.baseline) == {"entry_fill", "exit_fill", "pnl_per_unit", "return_pct"}
    assert report.baseline["entry_fill"] > experiment.bars[0].open
    assert report.baseline["exit_fill"] < experiment.bars[-1].close


def test_backtest_config_rejects_negative_costs():
    with pytest.raises(ValueError):
        BacktestConfig(spread_bps=-1.0)


def test_backtest_signal_rejects_invalid_direction_levels():
    with pytest.raises(ValueError):
        BacktestSignal(
            signal_id="BAD",
            instrument="TEST",
            side="LONG",
            generated_at=BASE,
            stop=102.0,
            target=101.0,
            quantity=1.0,
        )
