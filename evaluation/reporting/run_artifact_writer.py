"""Artifact export: save a complete run directory.

New layout (v2)
---------------
::

    outputs/<ts>_<name>/
        config.yaml          — OmegaConf config snapshot
        summary.txt          — Train vs Test comparison table
        training/            — in-sample  (≤ train_end)
            equity.csv, trades.csv, metrics.json
            fills.csv, positions.csv
            breach_events.csv, session_activity.json
            evaluation_diagnostics.json
            equity.png/html, drawdown.png/html, daily_pnl.png/html
            pnl_hist.png/html, returns_dist.png, monthly_heatmap.png/html
            hold_time_pnl, rolling_winrate, tod_heatmap, mae_mfe (.png/.html)
            pnl_distribution.json, pnl_dist_var.png, pnl_regime_box.png
            bootstrap_ci.json, calibration.json, reliability.png
            orders/          — one M1 candlestick per trade
                trade_NNNN_YYYYMMDD_HHMMopen_HHMMclose_{L|S}_{p|m}PnL.png
                trade_NNNN_…  .html
        testing/             — out-of-sample (≥ test_start)
            (same set)
        data/                — coverage, returns, session, features, PO3 sample
        model/               — RL runs only (populated by train_rl.py)
            ppo_*.zip, training_log.csv
            learning_curve.png/html, losses.png/html …

Usage::

    from evaluation.reporting.run_artifact_writer import save_run
    run_dir = save_run(
        out_dir="outputs", name="random",
        train_result=train_result, train_metrics=train_m, train_bars=train_bars,
        test_result=test_result,  test_metrics=test_m,  test_bars=test_bars,
        cfg=cfg,
    )
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, cast

import pandas as pd

from artifacts.atomic import write_json_atomic, write_text_atomic
from artifacts.config_snapshot import write_config_snapshot
from artifacts.layout import ArtifactLayout
from evaluation import PerformanceMetrics
from evaluation.reporting.evaluation_manifest import write_evaluation_manifest
from evaluation.reporting.run_summary import (
    build_comparison_table,
    build_summary_table,
    save_metrics_json,
)
from evaluation.reporting.trade_event_export import (
    _EMPTY_TRADE_COLUMNS,
    _fill_events,
    _position_summaries,
)

log = logging.getLogger(__name__)
_BREACH_EVENT_COLUMNS = ("time", "session_id", "reason", "equity", "fill_time")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_ftmo_limits(cfg: Any) -> tuple[float | None, float | None, float | None]:
    daily_loss_limit = max_loss_limit = profit_target = None
    if cfg is not None:
        try:
            daily_loss_limit = cfg.ftmo.daily_loss_limit
            max_loss_limit = cfg.ftmo.max_loss_limit
            profit_target = cfg.ftmo.profit_target
        except Exception:
            pass
    return daily_loss_limit, max_loss_limit, profit_target


def action_schema_manifest(cfg: Any) -> dict[str, Any] | None:
    """Serialize configured overlay coordinates for the exported run."""
    if cfg is None:
        return None
    try:
        env = cfg.env
        if not bool(env.get("strategy_actions", False)):
            return None
        schema: Any
        multi_tp = bool(env.get("allow_multi_tp", False))
        if bool(env.get("thesis_actions", False)) or bool(env.get("trade_setup_actions", False)):
            from decisioning.trade_setup import (
                build_legacy_thesis_action_schema,
                build_trade_setup_action_schema,
            )

            builder = (
                build_legacy_thesis_action_schema
                if bool(env.get("thesis_actions", False))
                else build_trade_setup_action_schema
            )
            schema = builder(
                has_sl_mode=bool(env.get("allow_agent_sl_mode", True)),
                has_tp_mode=bool(env.get("allow_agent_tp_mode", False)),
                has_multi_tp=multi_tp,
                has_simplex=multi_tp and bool(env.get("allow_simplex", True)),
            )
        else:
            from decisioning.actions import build_action_schema

            schema = build_action_schema(
                has_direction=bool(env.get("agent_direction_control", False)),
                has_sl_mode=bool(env.get("allow_agent_sl_mode", True)),
                has_tp_mode=bool(env.get("allow_agent_tp_mode", False)),
                has_multi_tp=multi_tp,
                has_simplex=multi_tp and bool(env.get("allow_simplex", True)),
            )
        return cast(dict[str, Any], schema.to_dict())
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _extract_trade_chart_config(cfg: Any) -> dict[str, Any]:
    """Extract trade chart configuration from OmegaConf."""
    config: dict[str, Any] = {
        "max_loss_per_trade_usd": None,
        "take_profit_per_trade_usd": None,
        "lots": 1.0,  # fallback only (per-trade lots are in trade log)
        "contract_size": 1.0,
        "show_mae_mfe": True,
        "show_sl_tp": True,
        "breakeven_buffer_pts": 0.0,
        "entry_idea_plot_config": None,
    }
    if cfg is not None:
        try:
            config["max_loss_per_trade_usd"] = cfg.backtest.validation.max_loss_per_trade_usd
            config["take_profit_per_trade_usd"] = cfg.backtest.validation.take_profit_per_trade_usd
            # Note: when structure SL/TP is used, per-trade lots are in trade log
            # This fallback is only used for legacy fixed-USD-TP mode
            if hasattr(cfg.account, "lots"):
                config["lots"] = cfg.account.lots
            config["contract_size"] = (
                cfg.account.contract_size if hasattr(cfg.account, "contract_size") else 1.0
            )
            config["show_mae_mfe"] = (
                cfg.output.trade_chart_show_mae_mfe
                if hasattr(cfg.output, "trade_chart_show_mae_mfe")
                else True
            )
            config["show_sl_tp"] = (
                cfg.output.trade_chart_show_sl_tp
                if hasattr(cfg.output, "trade_chart_show_sl_tp")
                else True
            )
            config["breakeven_buffer_pts"] = float(cfg.env.get("breakeven_buffer_pts", 0.0))
            from omegaconf import OmegaConf

            plot_config = OmegaConf.select(cfg, "evaluation.trade_idea_plots")
            if plot_config is not None:
                resolved = OmegaConf.to_container(plot_config, resolve=True)
                config["entry_idea_plot_config"] = resolved if isinstance(resolved, dict) else None
        except Exception:
            pass
    return config


# ---------------------------------------------------------------------------
# Per-split writer (all data + charts for one split go into one subfolder)
# ---------------------------------------------------------------------------


def _write_split(
    split_dir: Path,
    result: dict[str, Any],
    metrics: PerformanceMetrics,
    bars: pd.DataFrame | None,
    daily_loss_limit: float | None,
    max_loss_limit: float | None,
    save_plots: bool,
    save_html: bool,
    save_csv: bool,
    dpi: int,
    max_order_charts: int,
    profit_target: float | None = None,
    max_loss_per_trade_usd: float | None = None,
    take_profit_per_trade_usd: float | None = None,
    lots: float = 1.0,
    contract_size: float = 1.0,
    show_mae_mfe: bool = True,
    show_sl_tp: bool = True,
    breakeven_buffer_pts: float = 0.0,
    secondary_bars: pd.DataFrame | None = None,
    features: pd.DataFrame | None = None,
    phase_timings: dict[str, float] | None = None,
    phase_prefix: str = "",
    entry_idea_plot_config: dict[str, Any] | None = None,
) -> None:
    """Write all data + charts for one split into *split_dir*."""
    split_dir.mkdir(parents=True, exist_ok=True)

    equity: pd.Series = result.get("equity", pd.Series(dtype=float))
    trades: pd.DataFrame = result.get("trades", pd.DataFrame())
    breach_events: list[dict[str, Any]] = result.get("breach_events", [])
    n_sessions = int(result.get("n_sessions") or 0)
    n_breach_sessions = int(result.get("n_breach_sessions") or 0)
    n_sessions_with_trades = int(result.get("n_sessions_with_trades") or 0)
    n_sessions_skipped_value = result.get("n_sessions_skipped")
    n_sessions_skipped = (
        n_sessions - n_sessions_with_trades
        if n_sessions_skipped_value is None
        else int(n_sessions_skipped_value)
    )
    configured_initial_balance = result.get("initial_balance")
    if configured_initial_balance is None and not equity.empty:
        initial_balance = float(equity.iloc[-1]) - float(metrics.total_pnl)
    else:
        initial_balance = float(
            100_000.0 if configured_initial_balance is None else configured_initial_balance
        )

    phase_start = time.perf_counter()
    fill_events = _fill_events(trades)
    fill_source_values = (
        fill_events.get(
            "fill_quote_source", pd.Series("unknown", index=fill_events.index, dtype=object)
        )
        .fillna("unknown")
        .astype(str)
    )
    fill_quote_source_counts = {
        str(source): int(count)
        for source, count in sorted(fill_source_values.value_counts().items())
    }
    position_records = _position_summaries(trades)
    # ------------------------------------------------------------------
    # CSVs + diagnostics
    # ------------------------------------------------------------------
    if save_csv:
        if not equity.empty:
            equity.to_csv(split_dir / "equity.csv", header=["equity"])
        trades_for_csv = trades if not trades.empty else pd.DataFrame(columns=_EMPTY_TRADE_COLUMNS)
        trades_for_csv.to_csv(split_dir / "trades.csv", index=False)
        fill_events.to_csv(split_dir / "fills.csv", index=False)
        position_records.to_csv(split_dir / "positions.csv", index=False)
        if not trades.empty and "sl_ref" in trades.columns:
            from evaluation.reporting.diversity_artifacts import write_decision_artifacts
            from evaluation.reporting.geometry import geometry_summary

            geometry_summary(trades).to_csv(split_dir / "geometry_summary.csv", index=False)
            write_decision_artifacts(
                trades,
                split_dir,
                save_csv=True,
                save_plots=save_plots,
                dpi=dpi,
            )
        setup_decisions = result.get("trade_setup_decisions", result.get("thesis_decisions"))
        if isinstance(setup_decisions, pd.DataFrame):
            decision_filename = (
                "trade_setup_decisions.csv"
                if "trade_setup_candidate_id" in setup_decisions.columns
                else "thesis_decisions.csv"
            )
            setup_decisions.to_csv(split_dir / decision_filename, index=False)
        breach_frame = pd.DataFrame.from_records(breach_events, columns=_BREACH_EVENT_COLUMNS)
        breach_frame.to_csv(split_dir / "breach_events.csv", index=False)
        cycle_events = result.get("cycle_events")
        if isinstance(cycle_events, pd.DataFrame):
            cycle_events.to_csv(split_dir / "cycle_events.csv", index=False)
        payout_events = result.get("payout_events")
        if isinstance(payout_events, pd.DataFrame):
            payout_events.to_csv(split_dir / "payouts.csv", index=False)
        constraint_cost_summary = result.get("constraint_cost_summary")
        if constraint_cost_summary is not None:
            constraint_costs = result.get("constraint_costs")
            if not isinstance(constraint_costs, pd.DataFrame):
                raise ValueError("Q5 evaluation summary requires constraint_costs DataFrame")
            constraint_costs.to_csv(split_dir / "constraint_costs.csv", index=False)
        session_diag = {
            "n_sessions": n_sessions,
            "n_breach_sessions": n_breach_sessions,
            "n_sessions_with_trades": n_sessions_with_trades,
            "n_sessions_skipped": n_sessions_skipped,
        }
        write_text_atomic(split_dir / "session_activity.json", json.dumps(session_diag, indent=2))
        direction_diagnostics = result.get("direction_diagnostics")
        if direction_diagnostics:
            (split_dir / "direction_diagnostics.json").write_text(
                json.dumps(direction_diagnostics, indent=2)
            )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    final_equity = float(equity.iloc[-1]) if not equity.empty else float(initial_balance)
    save_metrics_json(
        metrics,
        split_dir / "metrics.json",
        initial_balance=initial_balance,
        final_equity=final_equity,
    )
    fail_time = result.get("fail_time")
    evaluation_diagnostics = {
        "n_steps": result.get("n_steps"),
        "exposure_bars": result.get("exposure_bars"),
        "exposure_fraction": result.get("exposure_fraction"),
        "exposure_measure": result.get("exposure_measure"),
        "survived_full_year": result.get("survived_full_year"),
        "completed_data_split": result.get("completed_data_split"),
        "episode_end_reason": result.get("episode_end_reason"),
        "fail_time": None if fail_time is None else str(fail_time),
        "n_sessions": n_sessions,
        "n_breach_sessions": n_breach_sessions,
        "n_sessions_with_trades": n_sessions_with_trades,
        "n_sessions_skipped": n_sessions_skipped,
        "action_counts": result.get("action_counts", {}),
        "execution_event_count": int(len(fill_events)),
        "fill_quote_source_event_count": int(sum(fill_quote_source_counts.values())),
        "fill_quote_source_counts": fill_quote_source_counts,
        "position_record_count": int(len(position_records)),
        "identified_position_count": int(
            position_records["reconstruction_status"].eq("identified_by_position_id").sum()
        )
        if not position_records.empty
        else 0,
        "unidentified_position_event_count": int(
            position_records["reconstruction_status"]
            .astype(str)
            .str.startswith("unidentified_event_")
            .sum()
        )
        if not position_records.empty
        else 0,
        "reward_attribution": result.get("reward_attribution", {}),
        "entry_funnel": result.get("entry_diag", {}),
        "entry_state_diagnostics": result.get("entry_state_diagnostics", {}),
        "trading_policy_mode": result.get("trading_policy_mode", "legacy"),
        "cumulative_payouts": float(result.get("cumulative_payouts", 0.0)),
        "total_economic_value": float(result.get("total_economic_value", final_equity)),
        "cycle_count": int(result.get("cycle_count", 0)),
        "cycle_successes": int(result.get("cycle_successes", 0)),
        "cycle_failures": int(result.get("cycle_failures", 0)),
    }
    setup_policy_metrics = result.get(
        "trade_setup_policy_metrics", result.get("thesis_policy_metrics")
    )
    if isinstance(setup_policy_metrics, dict):
        canonical_setup = setup_policy_metrics.get("wire_schema") == "trade_setup"
        file_prefix = "trade_setup" if canonical_setup else "thesis"
        diagnostics_key = "trade_setup_policy" if canonical_setup else "thesis_policy"
        evaluation_diagnostics[diagnostics_key] = setup_policy_metrics
        (split_dir / f"{file_prefix}_policy_metrics.json").write_text(
            json.dumps(setup_policy_metrics, indent=2)
        )
        for key, filename in (
            ("selection_by_idea", f"{file_prefix}_selection_by_idea.csv"),
            ("selection_by_timeframe", f"{file_prefix}_selection_by_timeframe.csv"),
            ("selection_matrix", f"{file_prefix}_selection_matrix.csv"),
            (
                "execution_action_by_trade_setup"
                if canonical_setup
                else "execution_action_by_thesis",
                f"{file_prefix}_action_by_idea_timeframe.csv",
            ),
            (
                "execution_by_opened_trade_setup"
                if canonical_setup
                else "execution_by_opened_thesis",
                f"{file_prefix}_execution_by_idea_timeframe.csv",
            ),
            ("performance_by_idea_timeframe", f"{file_prefix}_performance_by_idea_timeframe.csv"),
        ):
            rows = setup_policy_metrics.get(key)
            if isinstance(rows, list):
                pd.DataFrame.from_records(rows).to_csv(split_dir / filename, index=False)
    if result.get("constraint_cost_summary") is not None:
        evaluation_diagnostics["constraint_cost_summary"] = result["constraint_cost_summary"]
    (split_dir / "evaluation_diagnostics.json").write_text(
        json.dumps(evaluation_diagnostics, indent=2)
    )
    summary_text = build_summary_table(metrics)
    if isinstance(setup_policy_metrics, dict):
        canonical_setup = setup_policy_metrics.get("wire_schema") == "trade_setup"
        file_prefix = "trade_setup" if canonical_setup else "thesis"
        title = "TRADE SETUP POLICY DIAGNOSTICS" if canonical_setup else "THESIS POLICY DIAGNOSTICS"
        entropy_months = setup_policy_metrics.get(
            "trade_setup_entropy_by_month" if canonical_setup else "thesis_entropy_by_month", []
        )
        mean_entropy = setup_policy_metrics.get(
            "trade_setup_entropy_mean_nats" if canonical_setup else "thesis_entropy_mean_nats"
        )
        eligible_key = (
            "trade_setup_eligible_steps" if canonical_setup else "trade_thesis_eligible_steps"
        )
        eligible_rate_key = (
            "no_trade_rate_when_trade_setup_eligible"
            if canonical_setup
            else "no_trade_rate_when_trade_thesis_eligible"
        )
        conditioning_key = (
            "setup_conditioned_execution_active"
            if canonical_setup
            else "variant_d_execution_conditioning_active"
        )
        structure = setup_policy_metrics.get("structural_violations", {})
        monthly = (
            "\n".join(
                f"  {row['month']}: mean {row['mean']:.3f} nats (n={row['count']})"
                for row in entropy_months
            )
            or "  no entropy observations"
        )
        no_trade_rate = setup_policy_metrics.get("no_trade_rate")
        summary_text += (
            f"\n\n{title}\n"
            f"Policy: {setup_policy_metrics.get('policy_class', 'unknown')}; "
            "Setup-conditioned execution active: "
            f"{bool(setup_policy_metrics.get(conditioning_key, False))}\n"
            f"Decision bars: {setup_policy_metrics.get('decision_steps', 0)}; "
            f"NO_TRADE: {setup_policy_metrics.get('no_trade_count', 0)} "
            f"({float(no_trade_rate or 0.0):.1%}); "
            f"opened trades: {setup_policy_metrics.get('opened_trade_count', 0)}\n"
            f"Selected ideas/timeframes: {setup_policy_metrics.get('selected_idea_count', 0)} / "
            f"{setup_policy_metrics.get('selected_timeframe_count', 0)}; invalid setup choices: "
            f"{setup_policy_metrics.get('invalid_selection_count', 0)}\n"
            f"Eligible trade-setup steps: {setup_policy_metrics.get(eligible_key, 0)}; "
            f"NO_TRADE rate when eligible: "
            f"{float(setup_policy_metrics.get(eligible_rate_key) or 0.0):.1%}\n"
            f"Mean setup entropy: {float(mean_entropy or 0.0):.3f} nats\n"
            f"Structural violations: {structure.get('total', 0)} unique trades; "
            f"SL side/floor/SD-level-1 = {structure.get('sl_wrong_side', 0)}/"
            f"{structure.get('sl_below_primary_timeframe', 0)}/"
            f"{structure.get('standard_deviation_sl_not_level_1_on_setup_timeframe', 0)}; "
            f"TP wrong-side = {structure.get('tp_wrong_side', 0)}; allowed lower-timeframe TP refs = "
            f"{structure.get('tp_below_primary_timeframe', 0)}; semantic violations: "
            f"{setup_policy_metrics.get('semantic_violation_count', 0)}\n"
            f"Monthly setup entropy (see {file_prefix}_policy_metrics.json for detail):\n"
            f"{monthly}\n"
            f"Raw decision trace: {file_prefix}_decisions.csv; per-trade open rows: trades.csv."
        )
    (split_dir / "summary.txt").write_text(summary_text)
    if save_plots and isinstance(setup_policy_metrics, dict):
        from evaluation.reporting.trade_setup_plots import write_trade_setup_heatmaps

        write_trade_setup_heatmaps(setup_policy_metrics, split_dir, dpi)
        entropy_months = setup_policy_metrics.get(
            "trade_setup_entropy_by_month"
            if setup_policy_metrics.get("wire_schema") == "trade_setup"
            else "thesis_entropy_by_month",
            [],
        )
        if entropy_months:
            import matplotlib.pyplot as plt

            months = [str(row["month"]) for row in entropy_months]
            fig, left = plt.subplots(figsize=(12, 5))
            left.plot(
                months,
                [float(row["mean"]) for row in entropy_months],
                marker="o",
                color="#245c9f",
                label="Mean masked thesis entropy",
            )
            left.set_ylabel("Entropy (nats)")
            left.set_xlabel("Month")
            left.tick_params(axis="x", rotation=45)
            left.grid(True, alpha=0.25)
            right = left.twinx()
            right.plot(
                months,
                [float(row.get("no_trade_rate", 0.0)) for row in entropy_months],
                marker="s",
                color="#d17c00",
                label="NO_TRADE rate",
            )
            right.set_ylabel("NO_TRADE rate")
            handles_left, labels_left = left.get_legend_handles_labels()
            handles_right, labels_right = right.get_legend_handles_labels()
            left.legend(handles_left + handles_right, labels_left + labels_right, loc="best")
            fig.tight_layout()
            fig.savefig(split_dir / "thesis_policy_dynamics.png", dpi=dpi)
            plt.close(fig)
    if not trades.empty:
        opens = trades[trades.get("type", pd.Series(dtype=str)) == "open"]
        closes = trades[trades.get("type", pd.Series(dtype=str)).astype(str).str.contains("close")]
        direction_summary = {
            "long_trades": int((opens.get("direction", pd.Series(dtype=float)) == 1).sum()),
            "short_trades": int((opens.get("direction", pd.Series(dtype=float)) == -1).sum()),
            "long_pnl": 0.0,
            "short_pnl": 0.0,
        }
        if not closes.empty and not opens.empty:
            from evaluation.metrics.trade_pairs import pair_trades

            pairs = pair_trades(trades)
            for open_row, close_row in pairs:
                key = "long_pnl" if int(open_row.get("direction", 0)) == 1 else "short_pnl"
                direction_summary[key] += float(close_row.get("pnl", 0.0) or 0.0)
        write_text_atomic(
            split_dir / "direction_summary.json", json.dumps(direction_summary, indent=2)
        )

    if phase_timings is not None:
        phase_timings[f"{phase_prefix}numeric"] = time.perf_counter() - phase_start
    phase_start = time.perf_counter()
    # ------------------------------------------------------------------
    # Static PNG charts
    # ------------------------------------------------------------------
    if save_plots and not equity.empty:
        from evaluation.plotting import plots as _plt

        _plt.plot_equity_curve(
            equity,
            breach_events=breach_events,
            initial_balance=initial_balance,
            daily_loss_limit=daily_loss_limit,
            max_loss_limit=max_loss_limit,
            profit_target=profit_target,
            trades=trades,
            out_path=split_dir / "equity.png",
            dpi=dpi,
        )
        _plt.plot_drawdown(
            equity,
            out_path=split_dir / "drawdown.png",
            dpi=dpi,
            daily_loss_limit=daily_loss_limit,
        )
        _plt.plot_daily_pnl(
            equity,
            daily_loss_limit=daily_loss_limit,
            out_path=split_dir / "daily_pnl.png",
            dpi=dpi,
        )

        if not trades.empty:
            _plt.plot_trade_pnl_hist(trades, out_path=split_dir / "pnl_hist.png", dpi=dpi)
            _plt.plot_direction_summary(
                trades, out_path=split_dir / "direction_summary.png", dpi=dpi
            )

        _plt.plot_returns_dist(equity, out_path=split_dir / "returns_dist.png", dpi=dpi)
        _plt.plot_monthly_returns_heatmap(
            equity, out_path=split_dir / "monthly_heatmap.png", dpi=dpi
        )

        if bars is not None and not trades.empty and max_order_charts > 0:
            order_start = time.perf_counter()
            log.info("REPORT_PROGRESS %s order_png_start cap=%d", phase_prefix, max_order_charts)
            _plt.plot_per_trade_orders(
                bars,
                trades,
                orders_dir=split_dir / "orders",
                max_charts=max_order_charts,
                dpi=dpi,
                max_loss_per_trade_usd=max_loss_per_trade_usd,
                take_profit_per_trade_usd=take_profit_per_trade_usd,
                lots=lots,
                contract_size=contract_size,
                show_mae_mfe=show_mae_mfe,
                show_sl_tp=show_sl_tp,
                breakeven_buffer_pts=breakeven_buffer_pts,
                secondary_bars=secondary_bars,
                features=features,
                entry_idea_plot_config=entry_idea_plot_config,
            )
            if phase_timings is not None:
                phase_timings[f"{phase_prefix}order_png"] = time.perf_counter() - order_start
            log.info(
                "REPORT_PROGRESS %s order_png_done seconds=%.3f",
                phase_prefix,
                time.perf_counter() - order_start,
            )

    if phase_timings is not None:
        phase_timings[f"{phase_prefix}static_png_total"] = time.perf_counter() - phase_start
    phase_start = time.perf_counter()
    # ------------------------------------------------------------------
    # Interactive HTML charts
    # ------------------------------------------------------------------
    if save_html and not equity.empty:
        try:
            from evaluation.plotting import plots_interactive as _pi

            _pi.plot_equity_curve(
                equity,
                breach_events=breach_events,
                initial_balance=initial_balance,
                daily_loss_limit=daily_loss_limit,
                max_loss_limit=max_loss_limit,
                profit_target=profit_target,
                trades=trades,
                out_path=split_dir / "equity.html",
            )
            _pi.plot_drawdown(
                equity,
                out_path=split_dir / "drawdown.html",
                daily_loss_limit=daily_loss_limit,
            )
            _pi.plot_daily_pnl(
                equity,
                daily_loss_limit=daily_loss_limit,
                out_path=split_dir / "daily_pnl.html",
            )

            if not trades.empty:
                _pi.plot_trade_pnl_hist(trades, out_path=split_dir / "pnl_hist.html")

            _pi.plot_returns_dist(equity, out_path=split_dir / "returns_hist.html")
            _pi.plot_monthly_returns_heatmap(equity, out_path=split_dir / "monthly_heatmap.html")

            if bars is not None and not trades.empty and max_order_charts > 0:
                _pi.plot_per_trade_orders(
                    bars,
                    trades,
                    orders_dir=split_dir / "orders",
                    max_charts=max_order_charts,
                    max_loss_per_trade_usd=max_loss_per_trade_usd,
                    take_profit_per_trade_usd=take_profit_per_trade_usd,
                    lots=lots,
                    contract_size=contract_size,
                    show_mae_mfe=show_mae_mfe,
                    show_sl_tp=show_sl_tp,
                    secondary_bars=secondary_bars,
                    features=features,
                    entry_idea_plot_config=entry_idea_plot_config,
                )
        except ImportError:
            log.warning("plotly not available — skipping interactive HTML charts")

    if phase_timings is not None:
        phase_timings[f"{phase_prefix}interactive_html"] = time.perf_counter() - phase_start
    phase_start = time.perf_counter()
    if not trades.empty and (save_plots or save_html):
        from evaluation.plotting.trade_plots import write_trade_diagnostics

        write_trade_diagnostics(
            split_dir,
            trades,
            bars,
            dpi=dpi,
            save_plots=save_plots,
            save_html=save_html,
            lots=lots,
            contract_size=contract_size,
            max_loss_per_trade_usd=max_loss_per_trade_usd,
            take_profit_per_trade_usd=take_profit_per_trade_usd,
        )

    if not trades.empty:
        from evaluation.plotting.distribution_plots import write_distribution_artifacts
        from evaluation.reporting.diagnostics import (
            write_bootstrap_cis,
            write_calibration_artifacts,
        )

        write_distribution_artifacts(
            split_dir,
            trades,
            dpi=dpi,
            save_plots=save_plots,
        )
        if not equity.empty:
            try:
                write_bootstrap_cis(split_dir, equity, trades, initial_balance=initial_balance)
            except Exception as exc:
                log.warning("Bootstrap CIs skipped: %s", exc)
            try:
                write_calibration_artifacts(split_dir, trades, dpi=dpi, save_plots=save_plots)
            except Exception as exc:
                log.warning("Calibration diagram skipped: %s", exc)

    if phase_timings is not None:
        phase_timings[f"{phase_prefix}additional_diagnostics"] = time.perf_counter() - phase_start


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_run(
    out_dir: str | Path = "outputs",
    name: str = "run",
    run_dir: Path | None = None,
    train_result: dict[str, Any] | None = None,
    train_metrics: PerformanceMetrics | None = None,
    test_result: dict[str, Any] | None = None,
    test_metrics: PerformanceMetrics | None = None,
    train_bars: pd.DataFrame | None = None,
    test_bars: pd.DataFrame | None = None,
    train_secondary: pd.DataFrame | None = None,
    test_secondary: pd.DataFrame | None = None,
    train_features: pd.DataFrame | None = None,
    test_features: pd.DataFrame | None = None,
    cfg: Any | None = None,
    save_plots: bool = True,
    save_html: bool = False,
    save_csv: bool = True,
    dpi: int = 150,
    max_order_charts: int = 0,
    report_profile: str = "full",
) -> Path:
    """Persist a complete train + test run.

    Parameters
    ----------
    out_dir, name:
        Base directory and run label.  Creates ``<out_dir>/<ts>_<name>/``.
    run_dir:
        Explicit pre-created directory (overrides *out_dir* / *name* if set).
        Useful when the caller has already written model weights into the same
        directory (e.g. ``train_rl.py``).
    train_result, train_metrics, train_bars, train_secondary:
        In-sample backtest result dict, metrics, primary bars, and optional
        secondary-symbol bars (SMT overlays).
    test_result, test_metrics, test_bars, test_secondary:
        Out-of-sample equivalents.  Either split may be ``None``.

    Returns
    -------
    Path to the run directory.
    """
    if run_dir is None:
        run_dir = ArtifactLayout(Path(out_dir)).timestamped_run(name)
    run_dir.mkdir(parents=True, exist_ok=True)
    log.info("Saving run artifacts to %s", run_dir)

    daily_loss_limit, max_loss_limit, profit_target = _extract_ftmo_limits(cfg)

    # Config snapshot at root only
    if cfg is not None:
        write_config_snapshot(run_dir, cfg)

    if report_profile not in ("full", "experiment_run_fast"):
        raise ValueError(f"unknown report_profile: {report_profile}")
    # The fast profile affects presentation artifacts only. Every evaluation,
    # risk gate, trade, equity series, and mandatory report remains intact.
    deferred = []
    if report_profile == "experiment_run_fast":
        if max_order_charts > 0:
            deferred.append("per_trade_png")
        if save_html:
            deferred.append("interactive_html")
        max_order_charts = 0
        save_html = False
    phase_timings: dict[str, float] = {}
    export_started = time.perf_counter()
    split_kwargs: dict[str, Any] = dict(
        daily_loss_limit=daily_loss_limit,
        max_loss_limit=max_loss_limit,
        profit_target=profit_target,
        save_plots=save_plots,
        save_html=save_html,
        save_csv=save_csv,
        dpi=dpi,
        max_order_charts=max_order_charts,
        phase_timings=phase_timings,
    )

    # Add trade chart configuration from config
    trade_chart_config = _extract_trade_chart_config(cfg)
    split_kwargs.update(trade_chart_config)

    if train_result is not None and train_metrics is not None:
        _write_split(
            run_dir / "training",
            train_result,
            train_metrics,
            train_bars,
            secondary_bars=train_secondary,
            features=train_features,
            phase_prefix="training_",
            **split_kwargs,
        )

    if test_result is not None and test_metrics is not None:
        _write_split(
            run_dir / "testing",
            test_result,
            test_metrics,
            test_bars,
            secondary_bars=test_secondary,
            features=test_features,
            phase_prefix="testing_",
            **split_kwargs,
        )

    # Comparison summary at root
    if train_metrics is not None:
        write_text_atomic(
            run_dir / "summary.txt", build_comparison_table(train_metrics, test_metrics)
        )

    phase_timings["total_export"] = time.perf_counter() - export_started
    report = {
        "schema_version": 1,
        "action_schema": action_schema_manifest(cfg),
        "profile": report_profile,
        "deferred_artifacts": deferred,
        "phase_seconds": phase_timings,
        "max_order_charts": max_order_charts,
        "save_plots": save_plots,
        "save_html": save_html,
        "save_csv": save_csv,
    }
    write_json_atomic(run_dir / "report_export_timing.json", report, default=None)
    write_evaluation_manifest(run_dir)
    for phase, seconds in phase_timings.items():
        log.info("REPORT_TIMING %s=%.3f", phase, seconds)
    log.info("Run saved: %s", run_dir)
    return run_dir
