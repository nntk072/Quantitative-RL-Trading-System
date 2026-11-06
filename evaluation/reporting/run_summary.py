"""Multi-seed aggregation, report tables and run-report building.

Consumes :class:`~evaluation.metrics.PerformanceMetrics` instances
only — this is the canonical report layer after the two evaluation stacks
were unified (W9 eval-metrics plan, §1).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pandas as pd

from artifacts.atomic import write_text_atomic
from evaluation.metrics.performance import (
    METRIC_DEFINITION_VERSION,
    PerformanceMetrics,
    sweep_delay_breakdown,
)

_TRADE_METRICS_REQUIRING_COMPLETED_POSITIONS = {
    "profit_factor",
    "win_rate",
    "expectancy",
    "avg_trade",
}

# Metric rows shown in the summary / comparison tables, in display order.
_TABLE_ROWS: tuple[tuple[str, str], ...] = (
    ("Sharpe", "sharpe"),
    ("Sortino", "sortino"),
    ("Calmar", "calmar"),
    ("Max Drawdown", "max_drawdown"),
    ("Total Return", "total_return_pct"),
    ("Profit Factor", "profit_factor"),
    ("Expectancy", "expectancy"),
    ("Win Rate", "win_rate"),
    ("Completed Positions", "n_trades"),
    ("Total PnL", "total_pnl"),
    ("Avg Trade PnL", "avg_trade"),
    ("Max Consec Loss", "max_consec_loss"),
    ("Turnover", "turnover"),
    ("Breach Events", "breach_event_count"),
    ("Breached Sessions", "breach_session_count"),
    ("Breached Session Rate", "breach_rate"),
    ("Daily Return Samples", "daily_return_count"),
    ("Mean Daily Return", "daily_return_mean_pct"),
    ("Daily Return Volatility", "daily_return_std_pct"),
    ("Worst Daily Return", "daily_return_min_pct"),
    ("Best Daily Return", "daily_return_max_pct"),
    ("Ruin Time (Sessions)", "time_to_ruin_sessions"),
)


def aggregate_seeds(results: Sequence[PerformanceMetrics]) -> pd.DataFrame:
    """Aggregate per-seed :class:`PerformanceMetrics` into a summary DataFrame.

    Args:
        results: One ``PerformanceMetrics`` instance per seed/run.

    Returns:
        DataFrame with one row per seed and one column per metric.

    Raises:
        ValueError: If *results* is empty or contains a non-metrics object.
    """
    rows: list[dict[str, Any]] = []
    for seed, m in enumerate(results):
        if not isinstance(m, PerformanceMetrics):
            raise ValueError(
                f"result at index {seed} is {type(m).__name__}; expected PerformanceMetrics"
            )
        row: dict[str, Any] = {"seed": seed}
        for _, attr in _TABLE_ROWS:
            row[attr] = getattr(m, attr)
        row["activity_status"] = activity_status(m)
        rows.append(row)
    if not rows:
        raise ValueError("aggregate_seeds requires at least one result")
    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame) -> None:
    """Print a describe()-style summary of an aggregated seed DataFrame.

    Args:
        df: Input DataFrame supplying the rows used by this calculation.
    """
    print("\n=== Multi-Seed Report ===")
    print(df.describe().round(4).to_string())
    print()


def _format_value(label: str, value: float) -> str:
    """Format value.

    Args:
        label: Text or path value identifying the label.
        value: Value to process.

    Returns:
        Text returned by ``_format_value``.
    """
    if label in (
        "Completed Positions",
        "Max Consec Loss",
        "Breach Events",
        "Breached Sessions",
    ):
        return str(int(value))
    if label == "Total Return":
        # total_return_pct is already percent (pnl / balance * 100).
        return f"{value:.2f}%"
    if label in (
        "Mean Daily Return",
        "Daily Return Volatility",
        "Worst Daily Return",
        "Best Daily Return",
    ):
        return f"{value:.3f}%"
    if label in ("Max Drawdown", "Win Rate", "Breached Session Rate"):
        return f"{value * 100:.2f}%"
    if label == "Turnover":
        return f"{value:.6f}"
    if label in ("Daily Return Samples", "Ruin Time (Sessions)"):
        return str(int(value))
    if label == "Total PnL":
        return f"{value:.2f}"
    return f"{value:.4f}"


def activity_status(metrics: PerformanceMetrics) -> str:
    """Zero completed trades means the run was inactive, not profitable.

    Args:
        metrics: Metrics used by the operation described above.

    Returns:
        Text returned by ``activity_status``.
    """
    return "INACTIVE" if metrics.n_trades == 0 else "ACTIVE"


def _metric_availability(metrics: PerformanceMetrics) -> dict[str, str]:
    """Explain trade metrics that cannot be estimated without completed positions.

    Args:
        metrics: Performance summary whose completed-position count is checked.

    Returns:
        Metric names mapped to an unavailable reason, or an empty mapping when
        at least one position completed.
    """
    availability = (
        {
            name: "not_applicable_no_completed_positions"
            for name in sorted(_TRADE_METRICS_REQUIRING_COMPLETED_POSITIONS)
        }
        if metrics.n_trades == 0
        else {}
    )
    if math.isnan(metrics.profit_factor):
        availability.setdefault("profit_factor", "undefined_no_gains_or_losses")
    elif math.isinf(metrics.profit_factor):
        availability.setdefault("profit_factor", "unbounded_no_losses_with_positive_gains")
    for name, value in asdict(metrics).items():
        if isinstance(value, float) and not math.isfinite(value):
            availability.setdefault(name, "non_finite_metric_result")
    if metrics.breach_event_count is None:
        availability["breach_event_count"] = (
            metrics.breach_event_count_availability or "breach_event_count_unavailable"
        )
    daily_fields = (
        "daily_return_count",
        "daily_return_mean_pct",
        "daily_return_std_pct",
        "daily_return_min_pct",
        "daily_return_max_pct",
    )
    if metrics.daily_return_availability is not None:
        for name in daily_fields:
            if getattr(metrics, name) is None:
                availability[name] = metrics.daily_return_availability
    if metrics.daily_return_count == 1 and metrics.daily_return_std_pct is None:
        availability["daily_return_std_pct"] = "fewer_than_two_complete_sessions"
    if metrics.breach_rate is None:
        availability["breach_rate"] = (
            metrics.breach_rate_availability or "breach_session_rate_unavailable"
        )
    if metrics.breach_session_count is None:
        availability["breach_session_count"] = (
            metrics.breach_rate_availability or "breach_session_count_unavailable"
        )
    ruin_fields = (
        "time_to_ruin_sessions",
        "ruin_event_observed",
        "ruin_time_censored",
    )
    if metrics.time_to_ruin_availability is not None:
        for name in ruin_fields:
            if getattr(metrics, name) is None:
                availability[name] = metrics.time_to_ruin_availability
    return availability


def _json_safe(value: Any) -> Any:
    """Replace non-finite floats recursively so reports use standard JSON.

    Args:
        value: JSON-like value to sanitize.

    Returns:
        A structure with non-finite floating-point values replaced by ``None``.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def performance_metrics_payload(metrics: PerformanceMetrics) -> dict[str, Any]:
    """Build a JSON-safe metric record with explicit unavailable-value reasons.

    Args:
        metrics: Canonical aggregate metrics to serialize.

    Returns:
        Metric values, activity state, and reasons for unavailable statistics.
    """
    payload = asdict(metrics)
    availability = _metric_availability(metrics)
    for name in availability:
        if name in payload:
            payload[name] = None
    payload = cast(dict[str, Any], _json_safe(payload))
    payload["activity_status"] = activity_status(metrics)
    payload["metric_availability"] = availability
    payload["metric_definition_version"] = METRIC_DEFINITION_VERSION
    return payload


def _format_metric(metrics: PerformanceMetrics, label: str, attr: str) -> str:
    """Format a metric without turning an empty trade sample into numeric zero.

    Args:
        metrics: Performance summary containing the metric value.
        label: Human-readable metric label used by the value formatter.
        attr: Attribute name on ``metrics`` containing the numeric value.

    Returns:
        ``N/A`` for unavailable trade-only statistics, otherwise formatted text.
    """
    metric_value = getattr(metrics, attr)
    if metric_value is None:
        return "N/A"
    if metrics.n_trades == 0 and attr in _TRADE_METRICS_REQUIRING_COMPLETED_POSITIONS:
        return "N/A"
    if not math.isfinite(float(metric_value)):
        return "N/A"
    return _format_value(label, float(metric_value))


def build_summary_table(m: PerformanceMetrics) -> str:
    """Return a human-readable text table of a single PerformanceMetrics.

    Args:
        m: M used by the operation described above.

    Returns:
        Text returned by ``build_summary_table``.
    """
    lines = [
        "=" * 42,
        f"  {'Metric':<22} {'Value':>12}",
        "-" * 42,
        f"  {'Activity Status':<22} {activity_status(m):>12}",
    ]
    for label, attr in _TABLE_ROWS:
        lines.append(f"  {label:<22} {_format_metric(m, label, attr):>12}")
    lines.append("=" * 42)
    return "\n".join(lines)


def build_comparison_table(
    train_m: PerformanceMetrics, test_m: PerformanceMetrics | None = None
) -> str:
    """Return a two-column Train vs Test comparison table.

    Args:
        train_m: Train m used by the operation described above.
        test_m: Test m used by the operation described above.

    Returns:
        Text returned by ``build_comparison_table``.
    """
    has_test = test_m is not None
    width = 62 if has_test else 42
    sep = "=" * width
    mid = "-" * width

    def row(label: str, train_val: str, test_val: str = "") -> str:
        """Format one metric row for the train/test comparison table.

        Args:
            label: Text or path value identifying the label.
            train_val: Text or path value identifying the train val.
            test_val: Text or path value identifying the test val.

        Returns:
            Text returned by ``row``.
        """
        base = f"  {label:<22} {train_val:>14}"
        return base + (f"  {test_val:>14}" if has_test else "")

    header = f"  {'Metric':<22} {'Train':>14}" + (f"  {'Test':>14}" if has_test else "")

    lines = [sep, header, mid]
    for label, attr in _TABLE_ROWS:
        train_val = _format_metric(train_m, label, attr)
        test_val = _format_metric(test_m, label, attr) if test_m else ""
        lines.append(row(label, train_val, test_val))
    lines.append(sep)
    return "\n".join(lines)


def save_metrics_json(
    m: PerformanceMetrics,
    path: Path | str,
    *,
    initial_balance: float | None = None,
    final_equity: float | None = None,
) -> None:
    """Persist metrics plus account endpoints when supplied by the evaluator.

    Args:
        m: M used by the operation described above.
        path: Path to the input file or directory.
        initial_balance: Initial balance used by the operation described above.
        final_equity: Final equity used by the operation described above.
    """
    payload = performance_metrics_payload(m)
    if initial_balance is not None:
        payload["initial_balance"] = float(initial_balance)
    if final_equity is not None:
        payload["final_equity"] = float(final_equity)
    write_text_atomic(Path(path), json.dumps(payload, indent=2, allow_nan=False))


def build_run_report(
    metrics: PerformanceMetrics,
    trade_log: Sequence[dict[str, Any]] | None = None,
    **context: Any,
) -> dict[str, Any]:
    """Build the JSON-serialisable report block for one evaluation run.

    Merges all :class:`PerformanceMetrics` fields with the Sweep Delay
    breakdown of the run's trade log, plus any caller context (e.g. the
    run name or split configuration).  This replaces the hand-rolled
    per-script dict merging that used to be duplicated between
    ``train_rl.py`` and ``compare_encoders.py``.

    Args:
        metrics: Metrics returned by :func:`run_episode`.
        trade_log: The environment's ``trade_log`` list, if available.
        **context: Extra key/value pairs merged into the report.

    Returns:
        A dict safe to pass to ``json.dumps``.
    """
    report = performance_metrics_payload(metrics)
    report["sweep_delay"] = sweep_delay_breakdown(trade_log or [])
    report.update(context)
    return report
