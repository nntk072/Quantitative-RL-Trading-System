"""Unit tests for evaluation.metrics (hand-computed fixtures)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import pytest

from evaluation.metrics import (
    PerformanceMetrics,
    account_path_metric_inputs,
    calculate_metrics,
    compute_metrics,
    evaluation_periods_per_year,
    max_drawdown,
    sweep_delay_breakdown,
)
from evaluation.metrics.bootstrap import (
    max_drawdown_stat,
    sharpe_stat,
    sortino_stat,
    win_rate_stat,
)
from evaluation.metrics.performance import completed_position_trade_pnls


@pytest.mark.parametrize("completion", ["maybe", 2])
def test_malformed_position_completion_does_not_infer_a_completed_trade(
    completion: object,
) -> None:
    pnls, fill_count, incomplete_positions = completed_position_trade_pnls(
        [
            {
                "type": "close",
                "position_id": "p1",
                "net_pnl": 12.0,
                "position_complete": completion,
            }
        ]
    )

    assert pnls == []
    assert fill_count == 1
    assert incomplete_positions == 1


def test_legacy_final_close_without_completion_marker_remains_inferred() -> None:
    pnls, fill_count, incomplete_positions = completed_position_trade_pnls(
        [{"type": "close", "position_id": "p1", "net_pnl": 12.0}]
    )

    assert pnls == [12.0]
    assert fill_count == 1
    assert incomplete_positions == 0


@pytest.mark.parametrize(
    "record",
    [
        {
            "type": "close",
            "position_id": "p1",
            "net_pnl": True,
            "position_complete": True,
        },
        {
            "type": "close",
            "position_id": "p1",
            "net_pnl": np.bool_(True),
            "pnl": 12.0,
            "position_complete": True,
        },
    ],
)
def test_boolean_net_pnl_does_not_become_a_dollar_amount(record: dict[str, object]) -> None:
    pnls, fill_count, incomplete_positions = completed_position_trade_pnls([record])

    assert pnls == []
    assert fill_count == 0
    assert incomplete_positions == 1


@pytest.mark.unit
class TestSweepDelayBreakdown:
    def test_summarises_delays_and_level_split(self) -> None:
        # Arrange
        trade_log: list[dict[str, Any]] = [
            {"type": "open", "sweep_delay_s": 10.0, "level_type": "london_high"},
            {"type": "close", "pnl": 100.0},
            {"type": "open", "sweep_delay_s": 30.0, "level_type": "asian_low"},
            {"type": "open", "sweep_delay_s": float("nan"), "level_type": "asian_high"},
            {"type": "open", "level_type": None},  # entry without level info
        ]

        # Act
        stats = sweep_delay_breakdown(trade_log)

        # Assert
        assert stats["n_entries"] == 4
        assert stats["sweep_delay_mean_s"] == pytest.approx(20.0)
        assert stats["sweep_delay_median_s"] == pytest.approx(20.0)
        assert stats["london_pct"] == pytest.approx(100.0 / 3.0)
        assert stats["asian_pct"] == pytest.approx(200.0 / 3.0)

    def test_empty_log_marks_unobserved_statistics_unavailable(self) -> None:
        # Act
        stats = sweep_delay_breakdown([])

        # Assert
        assert stats["n_entries"] == 0
        assert stats["sweep_delay_mean_s"] is None
        assert stats["sweep_delay_median_s"] is None
        assert stats["london_pct"] is None
        assert stats["asian_pct"] is None

    def test_entries_without_observed_delays_keep_count_but_mark_delay_na(self) -> None:
        stats = sweep_delay_breakdown(
            [{"type": "open", "level_type": "london_high"}, {"type": "open"}]
        )

        assert stats["n_entries"] == 2
        assert stats["sweep_delay_mean_s"] is None
        assert stats["sweep_delay_median_s"] is None
        assert stats["london_pct"] == 100.0
        assert stats["asian_pct"] == 0.0


@pytest.mark.unit
class TestMaxDrawdown:
    def test_zero_when_equity_only_rises(self) -> None:
        # Arrange
        equity = [100.0, 110.0, 120.0]

        # Act
        mdd = max_drawdown(equity)

        # Assert
        assert mdd == 0.0

    def test_peak_to_trough_decline(self) -> None:
        # Arrange
        equity = [100.0, 120.0, 90.0, 95.0]

        # Act
        mdd = max_drawdown(equity)

        # Assert
        assert mdd == pytest.approx(0.25)


@pytest.mark.unit
class TestComputeMetrics:
    def test_flat_equity_gives_zero_sharpe_and_no_trades(self) -> None:
        # Arrange
        equity = [100_000.0] * 10

        # Act
        metrics = compute_metrics(equity, initial_balance=100_000.0)

        # Assert
        assert metrics.sharpe == 0.0
        assert metrics.total_pnl == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.n_trades == 0

    def test_all_breakeven_positions_have_undefined_profit_factor(self) -> None:
        metrics = compute_metrics(
            [100.0, 100.0, 100.0], initial_balance=100.0, trade_pnls=[0.0, 0.0]
        )

        assert math.isnan(metrics.profit_factor)
        assert metrics.win_rate == 0.0
        assert metrics.expectancy == 0.0
        assert metrics.n_trades == 2

    def test_bootstrap_statistics_match_canonical_metric_definitions(self) -> None:
        equity = np.asarray([100.0, 102.0, 98.0, 104.0, 103.0])
        trade_pnls = [20.0, -10.0, 0.0, 5.0]
        returns = equity[1:] / equity[:-1] - 1.0
        canonical = compute_metrics(
            equity,
            initial_balance=100.0,
            trade_pnls=trade_pnls,
            periods_per_year=12,
        )

        assert sharpe_stat(returns, periods_per_year=12) == pytest.approx(canonical.sharpe)
        assert sortino_stat(returns, periods_per_year=12) == pytest.approx(canonical.sortino)
        assert max_drawdown_stat(equity) == pytest.approx(canonical.max_drawdown)
        assert win_rate_stat(np.asarray(trade_pnls, dtype=np.float64)) == pytest.approx(
            canonical.win_rate
        )

    def test_bootstrap_statistics_keep_empty_sample_conventions(self) -> None:
        empty = np.asarray([], dtype=np.float64)

        assert sharpe_stat(empty) == 0.0
        assert sortino_stat(empty) == 0.0
        assert math.isnan(max_drawdown_stat(empty))
        assert math.isnan(win_rate_stat(empty))

    def test_total_pnl_and_return(self) -> None:
        # Arrange
        equity = [100_000.0, 101_000.0, 102_000.0]

        # Act
        metrics = compute_metrics(equity, initial_balance=100_000.0)

        # Assert
        assert metrics.total_pnl == pytest.approx(2_000.0)
        assert metrics.total_return_pct == pytest.approx(2.0)

    def test_first_valuation_loss_counts_toward_drawdown(self) -> None:
        # The input can contain end-of-bar valuations only.  Its initial
        # capital is known separately and must be present for drawdown.
        metrics = compute_metrics([90_000.0, 95_000.0], initial_balance=100_000.0)
        assert metrics.max_drawdown == pytest.approx(0.10)

    def test_calmar_uses_return_intervals_with_or_without_initial_equity_point(self) -> None:
        with_initial = compute_metrics(
            [100.0, 95.0, 110.0], initial_balance=100.0, periods_per_year=2
        )
        without_initial = compute_metrics([95.0, 110.0], initial_balance=100.0, periods_per_year=2)

        assert with_initial.calmar == pytest.approx(2.0)
        assert without_initial.calmar == pytest.approx(with_initial.calmar)

    def test_nonpositive_periods_per_year_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="periods_per_year must be positive"):
            compute_metrics([100.0, 101.0], initial_balance=100.0, periods_per_year=0)

    @pytest.mark.parametrize("value", [True, 2.5])
    def test_malformed_periods_per_year_is_rejected(self, value: Any) -> None:
        with pytest.raises(ValueError, match="periods_per_year must be positive"):
            compute_metrics([100.0, 101.0], initial_balance=100.0, periods_per_year=value)

    @pytest.mark.parametrize("trade_pnls", [[True], [float("nan")], ["1.0"]])
    def test_malformed_trade_pnls_are_rejected(self, trade_pnls: list[Any]) -> None:
        with pytest.raises(ValueError, match="trade_pnls values must be finite numbers"):
            compute_metrics([100.0, 101.0], initial_balance=100.0, trade_pnls=trade_pnls)

    def test_boolean_equity_and_initial_balance_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="equity_curve values must be finite numbers"):
            compute_metrics([True, 101.0], initial_balance=100.0)
        with pytest.raises(ValueError, match="equity_curve values must be finite numbers"):
            malformed_equity: Any = ["100.0", 101.0]
            compute_metrics(malformed_equity, initial_balance=100.0)
        with pytest.raises(ValueError, match="initial_balance must be positive"):
            compute_metrics([100.0, 101.0], initial_balance=True)

    def test_non_finite_equity_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            compute_metrics([100_000.0, float("nan")], initial_balance=100_000.0)

    def test_trade_stats_mixed_outcomes(self) -> None:
        # Arrange
        equity = [100_000.0, 101_000.0]
        trades = [500.0, -200.0, 300.0, -100.0]

        # Act
        metrics = compute_metrics(equity, initial_balance=100_000.0, trade_pnls=trades)

        # Assert
        assert metrics.n_trades == 4
        assert metrics.win_rate == pytest.approx(0.5)
        assert metrics.expectancy == pytest.approx(125.0)
        assert metrics.profit_factor == pytest.approx(800.0 / 300.0)

    def test_profit_factor_infinite_without_losses(self) -> None:
        # Arrange
        equity = [100_000.0, 100_500.0]

        # Act
        metrics = compute_metrics(equity, initial_balance=100_000.0, trade_pnls=[250.0])

        # Assert
        assert math.isinf(metrics.profit_factor)

    def test_breach_count_is_propagated(self) -> None:
        # Arrange
        equity = [100_000.0, 90_000.0]

        # Act
        metrics = compute_metrics(
            equity,
            initial_balance=100_000.0,
            breach_count=1,
        )

        # Assert
        assert metrics.breach_count == 1

    def test_extras_are_merged(self) -> None:
        # Arrange
        equity = [100_000.0, 100_001.0]

        # Act
        metrics = compute_metrics(
            equity,
            initial_balance=100_000.0,
            extras={"sweep_delay_s": 2.5},
        )

        # Assert
        assert metrics.extras["sweep_delay_s"] == pytest.approx(2.5)

    def test_session_returns_and_right_censored_time_to_ruin(self) -> None:
        trace = [
            {
                "session_id": 10,
                "session_start_equity": 100.0,
                "equity": 101.0,
                "cumulative_payouts": 0.0,
            },
            {
                "session_id": 10,
                "session_start_equity": 100.0,
                "equity": 102.0,
                "cumulative_payouts": 0.0,
            },
            {
                "session_id": 11,
                "session_start_equity": 102.0,
                "equity": 100.0,
                "cumulative_payouts": 0.0,
            },
        ]
        metrics = compute_metrics(
            [100.0, 102.0, 100.0],
            initial_balance=100.0,
            n_sessions=2,
            account_state_trace=trace,
            breach_events=[],
            completed_data_split=True,
        )

        assert metrics.daily_return_count == 2
        assert metrics.daily_return_mean_pct == pytest.approx((2.0 - (2.0 / 102.0 * 100.0)) / 2)
        assert metrics.daily_return_min_pct == pytest.approx(-2.0 / 102.0 * 100.0)
        assert metrics.daily_return_max_pct == pytest.approx(2.0)
        assert metrics.daily_return_std_pct is not None
        assert metrics.time_to_ruin_sessions == 2
        assert metrics.ruin_event_observed is False
        assert metrics.ruin_time_censored is True

        missing_event_time = compute_metrics(
            [100.0, 102.0, 100.0],
            initial_balance=100.0,
            breach_count=1,
            account_state_trace=trace,
            breach_events=[],
            completed_data_split=True,
        )
        assert missing_event_time.time_to_ruin_sessions is None
        assert missing_event_time.time_to_ruin_availability == "breach_count_without_event_timing"

    def test_time_to_ruin_uses_first_breached_session_and_excludes_partial_day(self) -> None:
        trace = [
            {
                "session_id": 10,
                "session_start_equity": 100.0,
                "equity": 102.0,
                "cumulative_payouts": 0.0,
            },
            {
                "session_id": 11,
                "session_start_equity": 102.0,
                "equity": 95.0,
                "cumulative_payouts": 0.0,
            },
        ]
        metrics = compute_metrics(
            [100.0, 102.0, 95.0],
            initial_balance=100.0,
            n_sessions=2,
            breach_count=1,
            account_state_trace=trace,
            breach_events=[{"session_id": 11, "reason": "daily_loss"}],
            completed_data_split=False,
        )

        assert metrics.daily_return_count == 1
        assert metrics.daily_return_mean_pct == pytest.approx(2.0)
        assert metrics.time_to_ruin_sessions == 2
        assert metrics.ruin_event_observed is True
        assert metrics.ruin_time_censored is False

    def test_time_to_ruin_uses_earliest_traced_session_not_event_row_order(self) -> None:
        trace = [
            {
                "session_id": session_id,
                "session_start_equity": 100.0,
                "equity": 99.0,
                "cumulative_payouts": 0.0,
            }
            for session_id in (10, 11, 12)
        ]
        events = [
            {"session_id": 12, "reason": "max_drawdown"},
            {"session_id": 10, "reason": "daily_loss"},
        ]

        metrics = compute_metrics(
            [100.0, 99.0],
            initial_balance=100.0,
            breach_count=len(events),
            n_sessions=3,
            account_state_trace=trace,
            breach_events=events,
            completed_data_split=True,
        )

        assert metrics.time_to_ruin_sessions == 1
        assert metrics.ruin_event_observed is True
        assert metrics.breach_session_count == 2

    def test_malformed_breach_event_keeps_path_metrics_unavailable(self) -> None:
        trace = [
            {
                "session_id": 10,
                "session_start_equity": 100.0,
                "equity": 99.0,
                "cumulative_payouts": 0.0,
            }
        ]

        metrics = compute_metrics(
            [100.0, 99.0],
            initial_balance=100.0,
            breach_count=1,
            account_state_trace=trace,
            breach_events=["not-an-event"],  # type: ignore[list-item]
            completed_data_split=True,
        )

        assert metrics.breach_rate is None
        assert metrics.time_to_ruin_sessions is None
        assert metrics.time_to_ruin_availability == "breach_event_history_malformed"

    def test_non_sequence_breach_history_is_unavailable(self) -> None:
        metrics = compute_metrics(
            [100.0, 99.0],
            initial_balance=100.0,
            breach_count=1,
            account_state_trace=[],
            breach_events=iter([{"session_id": 1}]),  # type: ignore[arg-type]
        )

        assert metrics.breach_event_count is None
        assert metrics.breach_session_count is None
        assert metrics.breach_rate is None
        assert metrics.breach_rate_availability == "breach_event_history_malformed"

    def test_session_return_counts_in_session_payout_and_marks_boundary_ambiguity(self) -> None:
        trace = [
            {
                "session_id": 10,
                "session_start_equity": 100.0,
                "equity": 100.0,
                "cumulative_payouts": 0.0,
            },
            {
                "session_id": 10,
                "session_start_equity": 100.0,
                "equity": 90.0,
                "cumulative_payouts": 10.0,
            },
        ]
        metrics = compute_metrics(
            [100.0, 90.0],
            initial_balance=100.0,
            account_state_trace=trace,
            breach_events=[],
            completed_data_split=True,
        )
        assert metrics.daily_return_mean_pct == pytest.approx(0.0)

        payout_reset = [
            {
                "session_id": 10,
                "session_start_equity": 100.0,
                "equity": 110.0,
                "cumulative_payouts": 0.0,
            },
            {
                "session_id": 10,
                "session_start_equity": 105.0,
                "equity": 105.0,
                "cumulative_payouts": 5.0,
            },
        ]
        payout_reset_metrics = compute_metrics(
            [100.0, 105.0],
            initial_balance=100.0,
            account_state_trace=payout_reset,
            breach_events=[],
            completed_data_split=True,
        )
        assert payout_reset_metrics.daily_return_count == 1
        assert payout_reset_metrics.daily_return_mean_pct == pytest.approx(10.0)

        ambiguous = [
            {
                "session_id": 10,
                "session_start_equity": 90.0,
                "equity": 90.0,
                "cumulative_payouts": 10.0,
            }
        ]
        unavailable = compute_metrics(
            [100.0, 90.0],
            initial_balance=100.0,
            account_state_trace=ambiguous,
            breach_events=[],
            completed_data_split=True,
        )
        assert unavailable.daily_return_count == 0
        assert unavailable.daily_return_mean_pct is None
        assert unavailable.daily_return_availability == "payout_boundary_attribution_ambiguous"

    def test_incomplete_account_trace_is_not_used_as_path_evidence(self) -> None:
        inputs = account_path_metric_inputs(
            {
                "account_state_trace": [{"session_id": 1}],
                "account_state_trace_complete": False,
                "breach_events": [],
                "completed_data_split": True,
            }
        )
        assert inputs["account_state_trace"] is None
        assert inputs["breach_events"] == []
        assert inputs["completed_data_split"] is True

    def test_empty_curve_raises(self) -> None:
        # Act / Assert
        with pytest.raises(ValueError, match="equity_curve"):
            compute_metrics([], initial_balance=100_000.0)

    def test_non_positive_balance_raises(self) -> None:
        # Act / Assert
        with pytest.raises(ValueError, match="initial_balance"):
            compute_metrics([1.0], initial_balance=0.0)

    def test_result_is_immutable(self) -> None:
        # Arrange
        metrics = compute_metrics([100_000.0], initial_balance=100_000.0)

        # Act / Assert
        assert isinstance(metrics, PerformanceMetrics)
        with pytest.raises(AttributeError):
            metrics.sharpe = 1.0  # type: ignore[misc]

    def test_legacy_fields_are_populated(self) -> None:
        # Arrange — 2 losses, 1 win, 2 losses in a row at the end
        equity = [100_000.0, 100_000.0, 100_000.0, 100_000.0, 100_000.0, 100_000.0]
        trades = [-100.0, 200.0, -50.0, -30.0]

        # Act
        metrics = compute_metrics(
            equity,
            initial_balance=100_000.0,
            trade_pnls=trades,
            breach_count=2,
            n_breach_sessions=2,
            n_sessions=4,
        )

        # Assert
        assert metrics.max_consec_loss == 2
        assert metrics.avg_trade == pytest.approx(metrics.expectancy)
        assert metrics.turnover == pytest.approx(4 / 6)
        assert metrics.breach_rate == pytest.approx(2 / 4)
        assert metrics.breach_session_count == 2

    def test_breach_rate_zero_sessions_is_safe(self) -> None:
        # Act
        metrics = compute_metrics(
            [100_000.0, 100_001.0], initial_balance=100_000.0, breach_count=1, n_sessions=0
        )

        # Assert
        assert metrics.breach_rate is None
        assert metrics.breach_count == 1

    def test_breach_rate_is_distinct_breached_sessions_not_event_count(self) -> None:
        events = [
            {"session_id": 4, "event_type": "daily_loss"},
            {"session_id": 4, "event_type": "max_drawdown"},
            {"session_id": 6, "event_type": "daily_loss"},
        ]

        metrics = compute_metrics(
            [100_000.0, 99_000.0],
            initial_balance=100_000.0,
            breach_count=len(events),
            n_sessions=4,
            breach_events=events,
        )

        assert metrics.breach_count == 3
        assert metrics.breach_session_count == 2
        assert metrics.breach_rate == pytest.approx(2 / 4)
        assert metrics.breach_rate_availability is None

    def test_breach_rate_is_unavailable_without_distinct_session_evidence(self) -> None:
        metrics = compute_metrics(
            [100_000.0, 99_000.0],
            initial_balance=100_000.0,
            breach_count=2,
            n_sessions=4,
        )

        assert metrics.breach_rate is None
        assert metrics.breach_session_count is None
        assert metrics.breach_rate_availability == ("distinct_breach_session_count_unavailable")

    def test_breach_rate_rejects_breached_session_count_mismatch(self) -> None:
        metrics = compute_metrics(
            [100_000.0, 99_000.0],
            initial_balance=100_000.0,
            breach_count=1,
            n_sessions=4,
            n_breach_sessions=2,
            breach_events=[{"session_id": 4}],
        )

        assert metrics.breach_rate is None
        assert metrics.breach_rate_availability == "breach_session_count_disagrees_with_events"

    @pytest.mark.parametrize("field_name", ["breach_count", "n_sessions", "n_breach_sessions"])
    @pytest.mark.parametrize("value", [False, "0", 0.0, -1])
    def test_compute_metrics_rejects_malformed_counts(self, field_name: str, value: Any) -> None:
        kwargs = {field_name: value}
        with pytest.raises(ValueError, match=f"{field_name} must be a nonnegative integer"):
            compute_metrics([100_000.0, 100_001.0], initial_balance=100_000.0, **kwargs)


@pytest.mark.unit
class TestCalculateMetricsAdapter:
    def test_accepts_pandas_series_and_trade_frame(self) -> None:
        # Arrange
        equity = pd.Series([100_000.0, 100_500.0, 100_200.0])
        trades = pd.DataFrame({"pnl": [600.0, -400.0, 100.0]})

        # Act
        metrics = calculate_metrics(equity, trades=trades, n_sessions=2, n_breach_sessions=1)

        # Assert
        assert metrics.total_pnl == pytest.approx(200.0)
        assert metrics.n_trades == 3
        assert metrics.win_rate == pytest.approx(2 / 3)
        assert metrics.max_consec_loss == 1
        assert metrics.breach_rate == pytest.approx(0.5)

    @pytest.mark.parametrize("breach_count", [False, "0", 0.0, -1])
    def test_rejects_malformed_breach_session_counts(self, breach_count: Any) -> None:
        with pytest.raises(ValueError, match="n_breach_sessions must be a nonnegative integer"):
            calculate_metrics(pd.Series([100_000.0, 100_001.0]), n_breach_sessions=breach_count)

    def test_m1_annualisation_default_is_preserved(self) -> None:
        # The adapter keeps the legacy 252*390 default so migrated runners
        # produce the same annualised numbers as before the unification.
        from evaluation.metrics import LEGACY_M1_PERIODS_PER_YEAR

        assert LEGACY_M1_PERIODS_PER_YEAR == 252 * 390

    def test_evaluation_periods_per_year_uses_config_and_legacy_fallback(self) -> None:
        assert evaluation_periods_per_year({}) == 252 * 390
        assert evaluation_periods_per_year({"evaluation": {"periods_per_year": 12}}) == 12
        with pytest.raises(ValueError, match="positive integer"):
            evaluation_periods_per_year({"evaluation": {"periods_per_year": 0}})

    def test_none_trades_gives_no_trade_stats(self) -> None:
        # Act
        metrics = calculate_metrics(pd.Series([100.0, 101.0]))

        # Assert
        assert metrics.n_trades == 0
        assert metrics.max_consec_loss == 0
