"""Unit tests for evaluation.reporting.run_summary."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from evaluation import PerformanceMetrics, compute_metrics
from evaluation.reporting.run_summary import (
    aggregate_seeds,
    build_comparison_table,
    build_run_report,
    build_summary_table,
    save_metrics_json,
)


def _metrics(total_pnl: float, n_trades: int) -> PerformanceMetrics:
    equity = [100_000.0, 100_000.0 + total_pnl]
    pnls = [total_pnl / n_trades] * n_trades if n_trades else []
    return compute_metrics(equity, initial_balance=100_000.0, trade_pnls=pnls)


@pytest.mark.unit
class TestAggregateSeeds:
    def test_one_row_per_seed(self) -> None:
        # Arrange
        results = [_metrics(100.0, 2), _metrics(-50.0, 3), _metrics(0.0, 0)]

        # Act
        df = aggregate_seeds(results)

        # Assert
        assert len(df) == 3
        assert list(df["seed"]) == [0, 1, 2]
        assert list(df["activity_status"]) == ["ACTIVE", "ACTIVE", "INACTIVE"]
        assert {"sharpe", "max_drawdown", "n_trades", "breach_rate"} <= set(df.columns)

    def test_rejects_non_metrics(self) -> None:
        with pytest.raises(ValueError, match="PerformanceMetrics"):
            aggregate_seeds([{"sharpe": 1.0}])  # type: ignore[list-item]

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            aggregate_seeds([])


@pytest.mark.unit
class TestReportTables:
    def test_summary_table_contains_key_rows(self) -> None:
        # Act
        table = build_summary_table(_metrics(150.0, 2))

        # Assert
        for label in (
            "Sharpe",
            "Max Drawdown",
            "Breach Events",
            "Breached Sessions",
            "Breached Session Rate",
            "Max Consec Loss",
            "Turnover",
        ):
            assert label in table
        assert "Completed Positions" in table

    def test_total_return_is_not_scaled_twice(self) -> None:
        # 1015.58 / 100_000 * 100 = 1.01558 percent, which prints as 1.02%.
        table = build_summary_table(_metrics(1015.58, 2))
        assert "1.02%" in table
        assert "101.56%" not in table

    def test_comparison_table_train_and_test_columns(self) -> None:
        # Act
        table = build_comparison_table(_metrics(100.0, 2), _metrics(-30.0, 1))

        # Assert
        assert "Train" in table
        assert "Test" in table
        assert "Sharpe" in table

    def test_save_metrics_json_roundtrip(self, tmp_path: Path) -> None:
        # Arrange
        path = tmp_path / "metrics.json"

        # Act
        save_metrics_json(
            _metrics(120.0, 2),
            path,
            initial_balance=100_000.0,
            final_equity=100_120.0,
        )
        data = json.loads(path.read_text())

        # Assert
        assert data["n_trades"] == 2
        assert data["periods_per_year"] == 6048
        assert data["metric_definition_version"] == "qrl.performance_metrics.v4"
        assert "breach_rate" in data
        assert data["breach_event_count"] == 0
        assert "turnover" in data
        assert data["initial_balance"] == pytest.approx(100_000.0)
        assert data["final_equity"] == pytest.approx(100_120.0)

    def test_metrics_json_separates_breach_events_from_breached_sessions(
        self, tmp_path: Path
    ) -> None:
        metrics = compute_metrics(
            [100_000.0, 99_000.0],
            initial_balance=100_000.0,
            breach_count=3,
            n_sessions=4,
            breach_events=[
                {"session_id": 1},
                {"session_id": 1},
                {"session_id": 3},
            ],
        )
        path = tmp_path / "breach_metrics.json"

        save_metrics_json(metrics, path, initial_balance=100_000.0, final_equity=99_000.0)
        payload = json.loads(path.read_text())

        assert payload["breach_event_count"] == 3
        assert payload["breach_session_count"] == 2
        assert payload["breach_rate"] == pytest.approx(0.5)

    def test_zero_trade_metrics_are_labeled_inactive(self, tmp_path: Path) -> None:
        metrics = _metrics(0.0, 0)
        table = build_summary_table(metrics)
        path = tmp_path / "inactive_metrics.json"
        save_metrics_json(metrics, path)
        report = build_run_report(metrics)
        saved_metrics = json.loads(path.read_text())

        assert "INACTIVE" in table
        assert saved_metrics["activity_status"] == "INACTIVE"
        assert report["activity_status"] == "INACTIVE"
        assert "N/A" in table
        assert saved_metrics["metric_availability"]["win_rate"] == (
            "not_applicable_no_completed_positions"
        )
        assert saved_metrics["profit_factor"] is None
        assert saved_metrics["win_rate"] is None
        assert saved_metrics["daily_return_mean_pct"] is None
        assert saved_metrics["metric_availability"]["daily_return_mean_pct"] == (
            "account_state_trace_missing_or_invalid"
        )
        assert saved_metrics["time_to_ruin_sessions"] is None
        assert saved_metrics["metric_availability"]["time_to_ruin_sessions"] == (
            "account_state_trace_missing_or_invalid"
        )
        json.dumps(report, allow_nan=False)

    def test_unbounded_profit_factor_uses_json_null_and_reason(self, tmp_path: Path) -> None:
        metrics = _metrics(100.0, 1)
        path = tmp_path / "unbounded_profit_factor.json"

        save_metrics_json(metrics, path)
        report = build_run_report(metrics)
        saved = json.loads(path.read_text())

        assert metrics.profit_factor == float("inf")
        assert saved["profit_factor"] is None
        assert saved["metric_availability"]["profit_factor"] == (
            "unbounded_no_losses_with_positive_gains"
        )
        assert "N/A" in build_summary_table(metrics)
        assert "Infinity" not in path.read_text()
        json.dumps(report, allow_nan=False)

    def test_all_breakeven_profit_factor_is_na_with_zero_denominator_reason(
        self, tmp_path: Path
    ) -> None:
        metrics = compute_metrics(
            [100.0, 100.0, 100.0], initial_balance=100.0, trade_pnls=[0.0, 0.0]
        )
        path = tmp_path / "breakeven_metrics.json"

        save_metrics_json(metrics, path)
        saved = json.loads(path.read_text())

        assert saved["profit_factor"] is None
        assert saved["metric_availability"]["profit_factor"] == ("undefined_no_gains_or_losses")
        assert saved["win_rate"] == 0.0
        assert saved["expectancy"] == 0.0
        assert "N/A" in build_summary_table(metrics)
        json.dumps(build_run_report(metrics), allow_nan=False)

    def test_overflowed_annualized_ratio_is_unavailable_in_json(self, tmp_path: Path) -> None:
        metrics = compute_metrics(
            [110.0, 105.0],
            initial_balance=100.0,
            periods_per_year=252 * 390,
        )
        path = tmp_path / "overflowed_annualization.json"

        save_metrics_json(metrics, path)
        saved = json.loads(path.read_text())

        assert math.isinf(metrics.calmar)
        assert saved["calmar"] is None
        assert saved["metric_availability"]["calmar"] == "non_finite_metric_result"
        assert "N/A" in build_summary_table(metrics)
        json.dumps(build_run_report(metrics), allow_nan=False)


@pytest.mark.unit
class TestBuildRunReport:
    def test_merges_metrics_delay_and_context(self) -> None:
        # Arrange
        trade_log = [{"type": "open", "sweep_delay_s": 5.0, "level_type": "london_high"}]

        # Act
        report = build_run_report(_metrics(80.0, 1), trade_log, run_name="r1")

        # Assert
        assert report["run_name"] == "r1"
        assert report["metric_definition_version"] == "qrl.performance_metrics.v4"
        assert report["total_pnl"] == pytest.approx(80.0)
        assert report["sweep_delay"]["sweep_delay_mean_s"] == pytest.approx(5.0)
        assert report["sweep_delay"]["n_entries"] == 1

    def test_none_trade_log_is_safe(self) -> None:
        report = build_run_report(_metrics(0.0, 0), None)
        assert report["sweep_delay"]["n_entries"] == 0
        assert report["sweep_delay"]["sweep_delay_mean_s"] is None
        assert report["sweep_delay"]["london_pct"] is None
