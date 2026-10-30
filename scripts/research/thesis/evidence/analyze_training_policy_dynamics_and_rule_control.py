#!/usr/bin/env python3
"""Summarize P6 training-year policy behavior and a causal rule baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from scripts.research.thesis.evidence.analyze_monthly_trade_expectancy_and_exit_decomposition import (
    ARMS,
    EXPERIMENT_RUN,
    REANALYSIS,
)

from decisioning.actions import ActionSchema
from evaluation.metrics.performance import completed_position_trade_pnls
from market_data.loading.ticks import TickBook
from simulation.environment import make_env
from trading.baselines import SessionMomentumStrategy


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _month_series(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, utc=True, errors="coerce")
    return parsed.dt.tz_convert("Etc/GMT-3").dt.strftime("%Y-%m")


def _policy_monthly(arm: str, root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    arm_dir = root / REANALYSIS / arm
    training = arm_dir / "training"
    events = pd.read_csv(training / "trades.csv", low_memory=False)
    equity = pd.read_csv(training / "equity.csv")
    if not str(equity.columns[0]).startswith("Unnamed") or "equity" not in equity:
        raise ValueError(f"unexpected equity curve schema for {arm}")
    diagnostics = json.loads((training / "evaluation_diagnostics.json").read_text(encoding="utf-8"))
    if len(equity) - 1 != int(diagnostics["n_steps"]):
        raise ValueError(f"equity curve rows do not reconcile to evaluation steps for {arm}")
    equity_time = pd.to_datetime(equity.iloc[1:, 0], format="mixed", errors="raise")
    step_frame = pd.DataFrame({"month": equity_time.dt.strftime("%Y-%m")})
    steps = step_frame.groupby("month").size()

    intents = events.loc[events["type"].isin(["open", "reject"])].copy()
    intents["decision_time_for_month"] = intents["decision_time"].where(
        intents["decision_time"].notna(), intents["time"]
    )
    intents["month"] = _month_series(intents["decision_time_for_month"])
    intents = intents.loc[intents["month"].str.startswith("2025-") | intents["month"].eq("2024-12")]
    opens = intents.loc[intents["type"].eq("open")]
    rejects = intents.loc[intents["type"].eq("reject")]
    intents_by_month = intents.groupby("month", sort=True)
    opens_by_month = opens.groupby("month", sort=True).size()
    rejects_by_month = rejects.groupby("month", sort=True).size()
    rows: list[dict[str, Any]] = []
    for month in sorted(set(steps.index) | set(intents["month"].dropna())):
        count_steps = int(steps.get(month, 0))
        group = (
            intents_by_month.get_group(month)
            if month in intents_by_month.groups
            else intents.iloc[:0]
        )
        n_open = int(opens_by_month.get(month, 0))
        n_reject = int(rejects_by_month.get(month, 0))
        n_intent = n_open + n_reject
        direction = pd.to_numeric(
            group.get("action_direction", pd.Series(dtype=float)), errors="coerce"
        )
        intensity = pd.to_numeric(
            group.get("action_intensity", pd.Series(dtype=float)), errors="coerce"
        )
        row = {
            "month": month,
            "policy_steps": count_steps,
            "entry_intents": n_intent,
            "trades_opened": n_open,
            "rejected_entry_intents": n_reject,
            "entry_intents_per_1000_steps": 1000.0 * n_intent / count_steps
            if count_steps
            else None,
            "trades_per_1000_steps": 1000.0 * n_open / count_steps if count_steps else None,
            "intent_acceptance_rate": n_open / n_intent if n_intent else None,
            "long_intent_share": float((direction > 0).mean())
            if not direction.dropna().empty
            else None,
            "short_intent_share": float((direction < 0).mean())
            if not direction.dropna().empty
            else None,
            "neutral_intent_share": float((direction == 0).mean())
            if not direction.dropna().empty
            else None,
            "mean_action_intensity_on_intents": float(intensity.mean())
            if not intensity.dropna().empty
            else None,
        }
        for column in (
            "action_risk",
            "action_stop",
            "action_target",
            "action_exit",
            "action_sl_mode",
        ):
            values = pd.to_numeric(
                group.get(column, pd.Series(dtype=float)), errors="coerce"
            ).dropna()
            row[f"mean_{column}_on_intents"] = float(values.mean()) if not values.empty else None
        rows.append(row)
    report = {
        "policy_entry_intents": "Only rows recorded as open or reject are available; no-op and in-position action vectors are not in trades.csv.",
        "policy_steps_source": str(training / "equity.csv"),
        "policy_steps_are_monthly_equity_rows": True,
        "training_trade_ledger_sha256": _sha256(training / "trades.csv"),
        "training_equity_sha256": _sha256(training / "equity.csv"),
        "evaluation_steps": int(diagnostics["n_steps"]),
        "training_terminal_time": diagnostics.get("fail_time"),
    }
    return pd.DataFrame(rows), report


def _p6_net_expectancy(root: Path) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for arm in ARMS:
        path = (
            root
            / "docs/thesis/evidence/p6_monthly_entry_exit_20261025"
            / f"{arm}_paired_trades.csv"
        )
        trades = pd.read_csv(path)
        trades["entry_month"] = (
            pd.to_datetime(trades["decision_time"], utc=True)
            .dt.tz_convert("Etc/GMT-3")
            .dt.strftime("%Y-%m")
        )
        net = pd.to_numeric(trades["actual_historical_net_r"], errors="raise")
        q1 = trades["entry_month"].str.startswith("2025-") & trades["entry_month"].isin(
            ["2025-01", "2025-02", "2025-03"]
        )
        after_q1 = trades["entry_month"].gt("2025-03")
        summaries[arm] = {
            "available_trade_count": int(len(trades)),
            "first_entry_month": str(trades["entry_month"].min()),
            "last_entry_month": str(trades["entry_month"].max()),
            "full_available_window_mean_net_r": float(net.mean()),
            "q1_2025_trade_count": int(q1.sum()),
            "q1_2025_mean_net_r": float(net.loc[q1].mean()),
            "post_q1_trade_count": int(after_q1.sum()),
            "post_q1_mean_net_r": float(net.loc[after_q1].mean()),
        }
    return summaries


def _load_training_data(
    root: Path,
) -> tuple[Any, pd.DataFrame, pd.DataFrame, TickBook, Path, Path, Path]:
    control_arm = ARMS[1]
    run_manifest = next(
        (root / EXPERIMENT_RUN / "runs/attempts").rglob(
            f"{control_arm}__seed50/attempt1/**/run_manifest.json"
        )
    )
    run_dir = run_manifest.parent
    manifest = json.loads(run_manifest.read_text(encoding="utf-8"))
    cfg = OmegaConf.load(run_dir / "config.yaml")
    symbol = str(cfg.data.primary)
    cache_dir = root / str(cfg.data.cache_dir)
    bars_path = cache_dir / "training" / f"{symbol}_M1_v3-native-timeframes.parquet"
    ticks_path = (
        cache_dir
        / "training"
        / (f"{symbol}_ticks_v3-validated-full-day_grid_nearest_half_away_from_zero_0p25.parquet")
    )
    feature_path = Path(str(manifest["feature_cache"]["path"]))
    if not feature_path.is_absolute():
        feature_path = root / feature_path
    bars = pd.read_parquet(bars_path)
    bar_index = pd.DatetimeIndex(bars.index)
    local_end = pd.Timestamp("2026-01-01", tz=bar_index.tz)
    features = pd.read_parquet(feature_path, filters=[("datetime", "<", local_end)])
    features = features.reindex(bars.index)
    if not features.index.equals(bars.index) or features.isna().all(axis=1).any():
        raise ValueError("training features do not align with the 2025 training bars")
    tick_frame = pd.read_parquet(ticks_path)
    timestamp_key = "ts_ns" if "ts_ns" in tick_frame else "timestamp_ns"
    timestamps = tick_frame[timestamp_key].to_numpy(dtype=np.int64)
    if not timestamps.size or timestamps.max() >= local_end.tz_convert("UTC").value:
        raise ValueError("tick book is empty or extends beyond the training split")
    book = TickBook(
        timestamps,
        tick_frame["bid"].to_numpy(dtype=np.float64),
        tick_frame["ask"].to_numpy(dtype=np.float64),
    )
    del tick_frame
    return cfg, bars, features, book, run_manifest, bars_path, ticks_path


def _run_rule_control(
    cfg: Any, bars: pd.DataFrame, features: pd.DataFrame, book: TickBook
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    env = make_env(
        bars,
        features,
        cfg,
        algo="ppo",
        reward=str(cfg.env.get("reward_mode", "dsr")),
        episodic=False,
        tickbook=book,
        arch=str(cfg.agent.get("arch", "tcn")),
    )
    if not isinstance(env.action_schema, ActionSchema):
        raise ValueError("the P6 PPO training config must use a continuous overlay schema")
    strategy = SessionMomentumStrategy(bars)
    strategy.fast_forward(int(env.obs_window))
    observation, _ = env.reset(seed=50)
    actions: list[dict[str, Any]] = []
    done = truncated = False
    steps = 0
    max_steps = len(bars) + 5
    while not (done or truncated) and steps < max_steps:
        timestamp = env._bar_time(env.step_idx)
        action = float(strategy.act(observation))
        actions.append({"time": pd.Timestamp(timestamp).isoformat(), "action": action})
        action_vector = np.zeros(env.action_schema.width, dtype=np.float32)
        direction_index = env.action_schema.indices.get("direction")
        if direction_index is None:
            raise ValueError("the P6 overlay action schema has no direction coordinate")
        action_vector[direction_index] = action
        observation, _, done, truncated, _ = env.step(action_vector)
        steps += 1
    if not actions:
        raise ValueError("non-PPO control made no environment decisions")
    action_frame = pd.DataFrame(actions)
    action_frame["month"] = _month_series(action_frame["time"])
    action_frame = action_frame.loc[
        action_frame["month"].str.startswith("2025-") | action_frame["month"].eq("2024-12")
    ]
    logs = pd.DataFrame(env.trade_log)
    completed_pnls, fill_count, incomplete_positions = completed_position_trade_pnls(env.trade_log)
    opens = logs.loc[logs.get("type", pd.Series(index=logs.index, dtype=str)).eq("open")].copy()
    opens["month"] = _month_series(opens.get("time", pd.Series(index=opens.index, dtype=str)))
    if not opens.empty:
        opens = opens.loc[opens["month"].str.startswith("2025-") | opens["month"].eq("2024-12")]
    fill_rows = logs.loc[
        logs.get("fill_id", pd.Series(index=logs.index, dtype=float)).notna()
        & logs.get("position_complete", pd.Series(index=logs.index, dtype=float)).notna()
    ].copy()
    if not fill_rows.empty and not fill_rows["fill_quote_source"].eq("tick").all():
        raise ValueError("non-PPO control produced a non-tick close fill")
    trade_rows: list[dict[str, Any]] = []
    if not opens.empty:
        if not {"position_id", "modeled_stop_risk_usd"}.issubset(opens.columns):
            raise ValueError("non-PPO control open events lack position identity or initial risk")
        for _, opened_row in opens.iterrows():
            pid = str(opened_row["position_id"])
            closes = fill_rows.loc[fill_rows["position_id"].astype(str).eq(pid)]
            if closes.empty:
                continue
            risk = float(opened_row["modeled_stop_risk_usd"])
            pnl = float(pd.to_numeric(closes["net_pnl"], errors="raise").sum())
            trade_rows.append(
                {
                    "position_id": pid,
                    "entry_time": str(opened_row.get("time")),
                    "month": str(opened_row["month"]),
                    "direction": int(opened_row["direction"]),
                    "initial_risk_usd": risk,
                    "net_pnl_usd": pnl,
                    "net_r": pnl / risk if risk > 0 else None,
                    "fill_count": int(len(closes)),
                    "exit_reasons": "|".join(str(value) for value in closes["reason"].tolist()),
                }
            )
    baseline_trades = pd.DataFrame(trade_rows)
    by_month = action_frame.groupby("month", sort=True)
    open_counts = opens.groupby("month", sort=True).size()
    closed_by_month = (
        baseline_trades.groupby("month", sort=True) if not baseline_trades.empty else None
    )
    rows: list[dict[str, Any]] = []
    for month, group in by_month:
        step_count = len(group)
        long_n = int((group["action"] > 0).sum())
        short_n = int((group["action"] < 0).sum())
        flat_n = int((group["action"] == 0).sum())
        opened_count = int(open_counts.get(month, 0))
        closed = (
            closed_by_month.get_group(month)
            if closed_by_month is not None and month in closed_by_month.groups
            else baseline_trades.iloc[:0]
        )
        rows.append(
            {
                "month": month,
                "control_steps": step_count,
                "control_trades_opened": opened_count,
                "control_trades_per_1000_steps": 1000.0 * opened_count / step_count
                if step_count
                else None,
                "long_action_share": long_n / step_count if step_count else None,
                "short_action_share": short_n / step_count if step_count else None,
                "flat_action_share": flat_n / step_count if step_count else None,
                "mean_action": float(group["action"].mean()),
                "completed_trade_count": int(len(closed)),
                "mean_completed_trade_net_r": (
                    float(closed["net_r"].mean()) if not closed.empty else None
                ),
                "completed_trade_net_pnl_usd": (
                    float(closed["net_pnl_usd"].sum()) if not closed.empty else 0.0
                ),
                "completed_trade_win_rate": (
                    float((closed["net_pnl_usd"] > 0).mean()) if not closed.empty else None
                ),
            }
        )
    metrics = {
        "strategy": "SessionMomentumStrategy",
        "description": "Direction is the sign of the previous completed NY session return; same P6 A4B TradingEnv, bars, features, bid/ask tickbook, risk settings, and seeded latency.",
        "seed": 50,
        "steps_executed": steps,
        "done": bool(done),
        "truncated": bool(truncated),
        "opened_trades": int(len(opens)),
        "completed_trade_count_from_environment_metric": int(len(completed_pnls)),
        "fill_count": int(fill_count),
        "incomplete_positions": int(incomplete_positions),
        "trade_log_rows": len(logs),
        "completed_trade_ledger_rows": len(baseline_trades),
        "end_equity": float(env.account.equity),
        "ending_balance": float(env.account.balance),
        "breach_events": getattr(env, "breach_events", []),
        "limitation": "Rule baseline is exposed to the same training interval and simulator; it is an in-sample descriptive reference, not an out-of-sample benchmark or a matched-entry experiment.",
    }
    return pd.DataFrame(rows), baseline_trades, metrics


def run(root: Path, out: Path) -> dict[str, Any]:
    policy_frames: list[pd.DataFrame] = []
    policy_notes: dict[str, Any] = {}
    for arm in ARMS:
        frame, note = _policy_monthly(arm, root)
        frame.insert(0, "variant", arm)
        policy_frames.append(frame)
        policy_notes[arm] = note
    policy_monthly = pd.concat(policy_frames, ignore_index=True)

    cfg, bars, features, book, manifest_path, bars_path, ticks_path = _load_training_data(root)
    control_monthly, control_trades, control_metrics = _run_rule_control(cfg, bars, features, book)
    shared_months = set(policy_monthly["month"])
    if not set(control_monthly["month"]).issubset(shared_months):
        raise ValueError("rule control contains a month absent from the P6 training ledgers")
    out.mkdir(parents=True, exist_ok=True)
    policy_monthly.to_csv(out / "p6_policy_monthly_dynamics.csv", index=False)
    control_monthly.to_csv(out / "p6_session_momentum_monthly_control.csv", index=False)
    control_trades.to_csv(out / "p6_session_momentum_trade_ledger.csv", index=False)
    result = {
        "experiment_run_fingerprint": "b37580606ca374326bce7207fb7eef118cede36cf0eaad25d37be9465bb4e1e4",
        "period": "training partition 2024-12-30 through 2025-12-31; no 2026 bars or ticks",
        "policy_monthly_notes": policy_notes,
        "control": control_metrics,
        "p6_net_expectancy": _p6_net_expectancy(root),
        "inputs": {
            "run_manifest": str(manifest_path),
            "run_manifest_sha256": _sha256(manifest_path),
            "training_bars_sha256": _sha256(bars_path),
            "training_ticks_sha256": _sha256(ticks_path),
            "policy_trades_sha256": {
                arm: note["training_trade_ledger_sha256"] for arm, note in policy_notes.items()
            },
            "policy_equity_sha256": {
                arm: note["training_equity_sha256"] for arm, note in policy_notes.items()
            },
        },
        "analysis_script_sha256": _sha256(
            root
            / "scripts/research/thesis/evidence/analyze_training_policy_dynamics_and_rule_control.py"
        ),
    }
    (out / "p6_training_dynamics_control.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return result


def _markdown(result: dict[str, Any], policy_monthly: pd.DataFrame, control: pd.DataFrame) -> str:
    lines = [
        "# P6 Training-Year Policy Dynamics and Non-PPO Control",
        "",
        "This report describes the P6 training partition from 2024-12-30 through 2025-12-31. It does not use the 2026 report split. The non-PPO control is the repository’s causal `SessionMomentumStrategy`, run on the same A4B environment, training bars, features, bid/ask tickbook, risk configuration, and seeded execution latency. It is an in-sample rule reference, not a fresh holdout or matched-entry ablation.",
        "",
        "The PPO ledger records only entry-intent decisions as `open` or `reject`; no-op actions and actions taken while a position is open are not written in the trade ledger. Therefore PPO action mix below means action mix on logged entry intents, not on every policy decision. Monthly decision denominators come from the saved policy equity curve rows. The rule control action mix counts every environment decision.",
        "",
        "## Monthly PPO entry behavior",
        "",
        "| Variant | Month | Steps | Intents | Trades opened | Rejects | Intents / 1k steps | Trades / 1k steps | Intent acceptance | Long / short / neutral intent share | Mean intensity | Mean risk action |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in policy_monthly.iterrows():
        lines.append(
            f"| `{row.variant}` | {row.month} | {int(row.policy_steps)} | {int(row.entry_intents)} | {int(row.trades_opened)} | {int(row.rejected_entry_intents)} | {row.entry_intents_per_1000_steps:.2f} | {row.trades_per_1000_steps:.2f} | {row.intent_acceptance_rate:.1%} | {row.long_intent_share:.1%} / {row.short_intent_share:.1%} / {row.neutral_intent_share:.1%} | {row.mean_action_intensity_on_intents:.3f} | {row.mean_action_risk_on_intents:.3f} |"
        )
    lines += [
        "",
        "## Monthly non-PPO reference",
        "",
        "| Month | Steps | Trades opened | Completed trades | Trades / 1k steps | Long / short / flat action share | Mean net R | Net P&L | Win rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in control.iterrows():
        lines.append(
            f"| {row.month} | {int(row.control_steps)} | {int(row.control_trades_opened)} | {int(row.completed_trade_count)} | {row.control_trades_per_1000_steps:.2f} | {row.long_action_share:.1%} / {row.short_action_share:.1%} / {row.flat_action_share:.1%} | {row.mean_completed_trade_net_r if pd.notna(row.mean_completed_trade_net_r) else float('nan'):.4f} | ${row.completed_trade_net_pnl_usd:.2f} | {row.completed_trade_win_rate if pd.notna(row.completed_trade_win_rate) else float('nan'):.1%} |"
        )
    lines += [
        "",
        "The per-trade rule ledger is tick sourced; monthly net R and P&L for completed positions are in `p6_session_momentum_monthly_control.csv`.",
        "",
        "## P6 net expectancy as observed",
        "",
        "| Variant | Trades | Available window | Full-window mean net R | Q1 2025 mean net R | Post-Q1 mean net R |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for arm, summary in result["p6_net_expectancy"].items():
        lines.append(
            f"| `{arm}` | {summary['available_trade_count']} | {summary['first_entry_month']}–{summary['last_entry_month']} | {summary['full_available_window_mean_net_r']:.4f} | {summary['q1_2025_mean_net_r']:.4f} | {summary['post_q1_mean_net_r']:.4f} |"
        )
    lines += [
        "",
        "## Control run status",
        "",
        f"The rule control executed {result['control']['steps_executed']:,} steps and opened {result['control']['opened_trades']} positions. Ending equity was ${result['control']['end_equity']:,.2f}; the environment ended with done={result['control']['done']} and truncated={result['control']['truncated']}. Fill-level P&L ledger: [`p6_session_momentum_trade_ledger.csv`](p6_session_momentum_trade_ledger.csv).",
        "",
        "## Reproducibility",
        "",
        f"- Experiment run fingerprint: `{result['experiment_run_fingerprint']}`.",
        f"- Analysis script SHA-256: `{result['analysis_script_sha256']}`.",
        "- Inputs, data hashes, and control diagnostics: `p6_training_dynamics_control.json`.",
        "- Monthly table: `p6_policy_monthly_dynamics.csv` and `p6_session_momentum_monthly_control.csv`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/thesis/evidence/p6_monthly_entry_exit_20261025"),
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    out = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    result = run(root, out)
    policy = pd.read_csv(out / "p6_policy_monthly_dynamics.csv")
    control = pd.read_csv(out / "p6_session_momentum_monthly_control.csv")
    report = out / "p6_training_dynamics_control.md"
    report.write_text(_markdown(result, policy, control), encoding="utf-8")
    result["report_sha256"] = _sha256(report)
    (out / "p6_training_dynamics_control.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({"report": str(report), "control": result["control"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
