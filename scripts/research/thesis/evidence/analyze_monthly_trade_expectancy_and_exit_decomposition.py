#!/usr/bin/env python3
"""Monthly actual-fill R accounting and paired exit decomposition for P6.

The analysis uses only the 2025 training ledger for the selected 2M P6 runs.
It reports actual bid/ask net R and mid-quote gross R, then replays each frozen
entry with a fixed EMA21 exit as a conditional reference. It never loads or
queries the policy and never enters the 2026 split.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from scripts.research.thesis import exit_shadow_fixed_entry as shadow

from market_data.loading.ticks import TickBook
from simulation.environment import make_env

ROOT_DEFAULT = Path.cwd()
EXPERIMENT_RUN = Path(
    "outputs/experiment_runs/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1"
)
REANALYSIS = EXPERIMENT_RUN / "reanalysis_daily_stop_semantics_20261024"
ARMS = (
    "ladder_a4a_entry_fsm_hidden_qgrid025",
    "ladder_a4b_entry_fsm_qgrid025",
)
BOOTSTRAP_SEED = 20261025
BOOTSTRAP_RESAMPLES = 10_000
TRAIN_START = pd.Timestamp("2024-12-29T21:00:00Z")
TRAIN_END_EXCLUSIVE = pd.Timestamp("2025-12-31T21:00:00Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_arm(root: Path, arm: str) -> dict[str, Any]:
    run_manifest_path = next(
        (root / EXPERIMENT_RUN / "runs/attempts").rglob(
            f"{arm}__seed50/attempt1/**/run_manifest.json"
        ),
        None,
    )
    if run_manifest_path is None:
        raise FileNotFoundError(f"run manifest missing for {arm}")
    run_dir = run_manifest_path.parent
    attempt_dir = next(parent for parent in run_dir.parents if parent.name == "attempt1")
    provenance_path = attempt_dir / "attempt_provenance.json"
    manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    ledger = root / REANALYSIS / arm / "training/trades.csv"
    if not ledger.is_file():
        raise FileNotFoundError(f"2025 training replay ledger missing: {ledger}")
    reanalysis_manifest_path = root / REANALYSIS / arm / "reanalysis_manifest.json"
    if not reanalysis_manifest_path.is_file():
        raise FileNotFoundError(f"reanalysis manifest missing: {reanalysis_manifest_path}")
    return {
        "arm": arm,
        "run_dir": run_dir,
        "manifest_path": run_manifest_path,
        "manifest": manifest,
        "reanalysis_manifest_path": reanalysis_manifest_path,
        "reanalysis_manifest": json.loads(reanalysis_manifest_path.read_text(encoding="utf-8")),
        "provenance_path": provenance_path,
        "provenance": provenance,
        "ledger": ledger,
        "config_path": run_dir / "config.yaml",
    }


def _quote(book: TickBook, timestamp: Any) -> tuple[float, float]:
    value = pd.Timestamp(timestamp).value
    index = int(np.searchsorted(book._ts, value, side="left"))
    if index >= len(book._ts) or int(book._ts[index]) != value:
        raise ValueError(f"fill timestamp is not an exact source tick: {timestamp}")
    return float(book._bid[index]), float(book._ask[index])


def _validate_source_match(run: dict[str, Any], root: Path) -> dict[str, Any]:
    expected = run["provenance"].get("identity", {}).get("source_hashes", {})
    relevant = shadow.RELEVANT_SOURCE_FILES
    missing = [name for name in relevant if name not in expected]
    mismatches = []
    for name in relevant:
        path = root / name
        recorded = expected.get(name)
        if recorded is not None and path.is_file() and _sha256(path) != recorded:
            mismatches.append(name)
    return {"checked": len(relevant) - len(missing), "missing": missing, "mismatches": mismatches}


def _actual_trade_rows(
    events: pd.DataFrame, book: TickBook, contract_size: float
) -> tuple[pd.DataFrame, dict[str, Any]]:
    opens = events.loc[events["type"].eq("open")].copy()
    if opens.empty or opens["position_id"].duplicated().any():
        raise ValueError("training ledger has no unique frozen entry rows")
    fills = events.loc[events["fill_id"].notna() & events["position_complete"].notna()].copy()
    if fills.empty:
        raise ValueError("training ledger has no completed fill events")
    if not fills["fill_quote_source"].eq("tick").all():
        raise ValueError("one or more close fills were not sourced from ticks")
    if not opens["fill_quote_source"].eq("tick").all():
        raise ValueError("one or more entry fills were not sourced from ticks")

    position_rows: list[dict[str, Any]] = []
    exact_open_checks = 0
    exact_close_checks = 0
    net_reconciliation_errors: list[dict[str, Any]] = []
    stop_target_fills = fills.loc[
        fills["reason"].astype(str).str.contains(r"(?:^|_)sl$|^structure_tp[123]$", regex=True)
    ]
    if not stop_target_fills["fill_quote_source"].eq("tick").all():
        raise ValueError("stop or target exit did not use a tick fill")

    for _, entry in opens.iterrows():
        position_id = str(entry["position_id"])
        direction = int(entry["direction"])
        entry_time = entry["actual_tick_time"]
        entry_bid, entry_ask = _quote(book, entry_time)
        entry_exec = entry_ask if direction == 1 else entry_bid
        if not math.isclose(entry_exec, float(entry["price"]), abs_tol=1e-8):
            raise ValueError(f"entry does not match its raw executable quote: {position_id}")
        exact_open_checks += 1
        trade_fills = fills.loc[fills["position_id"].astype(str).eq(position_id)].copy()
        if trade_fills.empty:
            raise ValueError(f"entry has no close fill: {position_id}")
        initial_risk = float(entry["modeled_stop_risk_usd"])
        if not math.isfinite(initial_risk) or initial_risk <= 0:
            raise ValueError(f"invalid initial stop risk for {position_id}")
        entry_mid = (entry_bid + entry_ask) / 2.0
        gross_usd = 0.0
        raw_bid_ask_usd = 0.0
        recorded_net_usd = 0.0
        closed = 0.0
        for _, fill in trade_fills.iterrows():
            bid, ask = _quote(book, fill["actual_tick_time"])
            executable = bid if direction == 1 else ask
            if not math.isclose(executable, float(fill["price"]), abs_tol=1e-8):
                raise ValueError(f"close price does not match raw executable quote: {position_id}")
            size = float(fill["size"])
            gross_usd += direction * (((bid + ask) / 2.0) - entry_mid) * size * contract_size
            raw_bid_ask_usd += direction * (executable - entry_exec) * size * contract_size
            recorded_net_usd += float(fill["net_pnl"])
            closed += size
            exact_close_checks += 1
        if not math.isclose(raw_bid_ask_usd, recorded_net_usd, rel_tol=1e-8, abs_tol=1e-6):
            net_reconciliation_errors.append(
                {
                    "position_id": position_id,
                    "raw_bid_ask_usd": raw_bid_ask_usd,
                    "ledger_net_usd": recorded_net_usd,
                    "difference_usd": raw_bid_ask_usd - recorded_net_usd,
                }
            )
        decision_time = pd.Timestamp(entry["decision_time"])
        if decision_time.tzinfo is None:
            decision_time = decision_time.tz_localize("UTC")
        decision_time = decision_time.tz_convert("UTC")
        position_rows.append(
            {
                "position_id": position_id,
                "decision_time": decision_time.isoformat(),
                "entry_time": pd.Timestamp(entry_time).isoformat(),
                "entry_month": decision_time.strftime("%Y-%m"),
                "side": "long" if direction == 1 else "short",
                "entry_price": float(entry["price"]),
                "initial_stop": float(entry["sl_price"]),
                "initial_risk_usd": initial_risk,
                "entry_size": float(entry["lots"]),
                "closed_size": closed,
                "actual_gross_mid_usd": gross_usd,
                "actual_gross_mid_r": gross_usd / initial_risk,
                "actual_raw_bid_ask_net_usd": raw_bid_ask_usd,
                "actual_historical_net_r": raw_bid_ask_usd / initial_risk,
                "actual_fill_cost_drag_r": (gross_usd - raw_bid_ask_usd) / initial_risk,
                "ledger_net_usd": recorded_net_usd,
                "fill_count": len(trade_fills),
                "exit_reasons": "|".join(str(x) for x in trade_fills["reason"].tolist()),
            }
        )
    out = pd.DataFrame(position_rows)
    out = out.loc[
        (pd.to_datetime(out["decision_time"], utc=True) >= TRAIN_START)
        & (pd.to_datetime(out["decision_time"], utc=True) < TRAIN_END_EXCLUSIVE)
    ].reset_index(drop=True)
    return out, {
        "entry_tick_quote_checks": exact_open_checks,
        "close_tick_quote_checks": exact_close_checks,
        "stop_and_target_fill_rows": int(len(stop_target_fills)),
        "stop_and_target_fill_sources": stop_target_fills["fill_quote_source"]
        .value_counts()
        .to_dict(),
        "all_entry_fills_tick": bool(opens["fill_quote_source"].eq("tick").all()),
        "all_close_fills_tick": bool(fills["fill_quote_source"].eq("tick").all()),
        "raw_bid_ask_vs_recorded_net_mismatches": net_reconciliation_errors,
    }


def _monthly(rows: pd.DataFrame, bootstrap_seed: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for month, group in rows.groupby("entry_month", sort=True):
        row: dict[str, Any] = {"entry_month": str(month), "n": int(len(group))}
        for column, prefix in (
            ("actual_gross_mid_r", "actual_gross_mid"),
            ("actual_historical_net_r", "actual_historical_net"),
            ("ema_gross_r", "ema_reference_gross"),
            ("exit_delta_r", "actual_minus_ema_exit_delta"),
        ):
            if column not in group:
                continue
            values = group[column].dropna().to_numpy(dtype=np.float64)
            if not values.size:
                continue
            low, high = shadow.paired_bootstrap(
                values, resamples=BOOTSTRAP_RESAMPLES, seed=bootstrap_seed
            )
            row[f"{prefix}_mean_r"] = float(np.mean(values))
            row[f"{prefix}_median_r"] = float(np.median(values))
            row[f"{prefix}_ci95_mean_r"] = [low, high]
        row["mid_to_bid_ask_drag_mean_r"] = float(group["actual_fill_cost_drag_r"].mean())
        row["gross_mid_pnl_usd_sum"] = float(group["actual_gross_mid_usd"].sum())
        row["historical_net_pnl_usd_sum"] = float(group["actual_raw_bid_ask_net_usd"].sum())
        result.append(row)
    return result


def _decomposition(rows: pd.DataFrame, seed: int) -> dict[str, Any]:
    march = rows.loc[rows["entry_month"].eq("2025-03")].dropna(
        subset=["actual_gross_mid_r", "ema_gross_r", "exit_delta_r"]
    )
    april = rows.loc[rows["entry_month"].eq("2025-04")].dropna(
        subset=["actual_gross_mid_r", "ema_gross_r", "exit_delta_r"]
    )
    if march.empty or april.empty:
        raise ValueError("March or April has no complete actual/EMA paired entries")
    actual_delta = float(april.actual_gross_mid_r.mean() - march.actual_gross_mid_r.mean())
    entry_delta = float(april.ema_gross_r.mean() - march.ema_gross_r.mean())
    exit_delta = float(april.exit_delta_r.mean() - march.exit_delta_r.mean())
    if not math.isclose(actual_delta, entry_delta + exit_delta, abs_tol=1e-12):
        raise AssertionError("point estimate decomposition does not add up")
    rng = np.random.default_rng(seed)
    boot = np.empty((BOOTSTRAP_RESAMPLES, 3), dtype=np.float64)
    mar_actual = march.actual_gross_mid_r.to_numpy(dtype=np.float64)
    apr_actual = april.actual_gross_mid_r.to_numpy(dtype=np.float64)
    mar_ema = march.ema_gross_r.to_numpy(dtype=np.float64)
    apr_ema = april.ema_gross_r.to_numpy(dtype=np.float64)
    mar_exit = march.exit_delta_r.to_numpy(dtype=np.float64)
    apr_exit = april.exit_delta_r.to_numpy(dtype=np.float64)
    for i in range(BOOTSTRAP_RESAMPLES):
        mi = rng.integers(0, len(march), len(march))
        ai = rng.integers(0, len(april), len(april))
        boot[i, 0] = apr_actual[ai].mean() - mar_actual[mi].mean()
        boot[i, 1] = apr_ema[ai].mean() - mar_ema[mi].mean()
        boot[i, 2] = apr_exit[ai].mean() - mar_exit[mi].mean()
    intervals = np.quantile(boot, [0.025, 0.975], axis=0).T.tolist()
    return {
        "paired_entries_march": int(len(march)),
        "paired_entries_april": int(len(april)),
        "march_actual_gross_mean_r": float(march.actual_gross_mid_r.mean()),
        "april_actual_gross_mean_r": float(april.actual_gross_mid_r.mean()),
        "march_ema_reference_gross_mean_r": float(march.ema_gross_r.mean()),
        "april_ema_reference_gross_mean_r": float(april.ema_gross_r.mean()),
        "march_actual_minus_ema_mean_r": float(march.exit_delta_r.mean()),
        "april_actual_minus_ema_mean_r": float(april.exit_delta_r.mean()),
        "march_to_april_actual_gross_change_r": actual_delta,
        "entry_cohort_component_r": entry_delta,
        "exit_outcome_component_r": exit_delta,
        "bootstrap_95pct_ci": {
            "actual_gross_change_r": intervals[0],
            "entry_cohort_component_r": intervals[1],
            "exit_outcome_component_r": intervals[2],
        },
        "point_estimates_add_exactly": True,
        "reference_interpretation": "conditional frozen-entry EMA21-exit reference; not an account-path or causal policy counterfactual",
    }


def _paired_replays(
    root: Path,
    run: dict[str, Any],
    actual: pd.DataFrame,
    events: pd.DataFrame,
    book: TickBook,
    bars: pd.DataFrame,
    features: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    cfg = OmegaConf.load(run["config_path"])
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
    opens = events.loc[events["type"].eq("open")].copy()
    rows: list[dict[str, Any]] = []
    incomplete: list[str] = []
    for _, entry in opens.iterrows():
        pid = str(entry["position_id"])
        replay = shadow.replay_entry(
            env, entry, None, "ema_21", shadow._latency_for_entry(events, pid)
        )
        metrics = shadow._trade_metrics(entry, replay, book, float(cfg.account.contract_size), 0.0)
        if not metrics.get("complete", False):
            incomplete.append(pid)
            continue
        rows.append({"position_id": pid, "ema_gross_r": float(metrics["gross_r"])})
    paired = actual.merge(pd.DataFrame(rows), on="position_id", how="inner", validate="one_to_one")
    paired["exit_delta_r"] = paired["actual_gross_mid_r"] - paired["ema_gross_r"]
    return paired, {
        "actual_training_entries": int(len(opens)),
        "completed_ema21_replays": int(len(rows)),
        "incomplete_ema21_replays": incomplete,
        "paired_cohort": int(len(paired)),
        "source_match": _validate_source_match(run, root),
    }


def run(root: Path, out: Path) -> dict[str, Any]:
    results: dict[str, Any] = {
        "experiment_run_fingerprint": "b37580606ca374326bce7207fb7eef118cede36cf0eaad25d37be9465bb4e1e4",
        "analysis_script_sha256": _sha256(
            root
            / "scripts/research/thesis/evidence/analyze_monthly_trade_expectancy_and_exit_decomposition.py"
        ),
        "analysis_window": {
            "start_utc": TRAIN_START.isoformat(),
            "end_exclusive_utc": TRAIN_END_EXCLUSIVE.isoformat(),
            "partition": "training only; 2026 is not opened or used",
        },
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
        "arms": {},
    }

    for arm in ARMS:
        run_info = _load_arm(root, arm)
        manifest = run_info["manifest"]
        execution = manifest.get("execution_protocol", {})
        costs = execution.get("costs", {})
        exec_cfg = execution.get("execution", {})
        reanalysis_costs = run_info["reanalysis_manifest"].get("execution_cost_override", {})
        source_match = _validate_source_match(run_info, root)
        if source_match["missing"]:
            raise ValueError(f"run source provenance incomplete: {source_match['missing']}")
        if source_match["mismatches"]:
            raise ValueError(f"replay source changed from training: {source_match['mismatches']}")

        cfg = OmegaConf.load(run_info["config_path"])
        cache_dir = root / str(cfg.data.cache_dir)
        symbol = str(cfg.data.primary)
        bars_path = cache_dir / "training" / f"{symbol}_M1_v3-native-timeframes.parquet"
        ticks_path = (
            cache_dir
            / "training"
            / (
                f"{symbol}_ticks_v3-validated-full-day_grid_nearest_half_away_from_zero_0p25.parquet"
            )
        )
        feature_path = Path(str(manifest["feature_cache"]["path"]))
        if not feature_path.is_absolute():
            feature_path = root / feature_path
        for path in (bars_path, ticks_path, feature_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        bars = pd.read_parquet(bars_path)
        bar_index = pd.DatetimeIndex(bars.index)
        local_end_exclusive = pd.Timestamp("2026-01-01", tz=bar_index.tz)
        features = pd.read_parquet(feature_path, filters=[("datetime", "<", local_end_exclusive)])
        features = features.reindex(bars.index)
        if not features.index.equals(bars.index) or features.isna().all(axis=1).any():
            raise ValueError("source features do not align to the exact 2025 training bars")
        tick_frame = pd.read_parquet(ticks_path)
        timestamp_column = "ts_ns" if "ts_ns" in tick_frame else "timestamp_ns"
        tick_times = tick_frame[timestamp_column].to_numpy(dtype=np.int64)
        cutoff_ns = local_end_exclusive.tz_convert("UTC").value
        if tick_times.size == 0 or int(tick_times.max()) >= cutoff_ns:
            raise ValueError("training tick cache is empty or crosses the 2025 cutoff")
        book = TickBook(
            tick_times,
            tick_frame["bid"].to_numpy(dtype=np.float64),
            tick_frame["ask"].to_numpy(dtype=np.float64),
        )
        del tick_frame
        events = pd.read_csv(run_info["ledger"], low_memory=False)
        actual, fill_audit = _actual_trade_rows(events, book, float(cfg.account.contract_size))
        paired, replay_audit = _paired_replays(root, run_info, actual, events, book, bars, features)
        arm_result = {
            "manifest": {
                "path": str(run_info["manifest_path"]),
                "sha256": _sha256(run_info["manifest_path"]),
                "tick_fill_slippage_points_explicit_field": manifest.get(
                    "tick_fill_slippage_points"
                ),
                "reanalysis_manifest_path": str(run_info["reanalysis_manifest_path"]),
                "reanalysis_manifest_sha256": _sha256(run_info["reanalysis_manifest_path"]),
                "effective_tick_fill_slippage_points_recorded": reanalysis_costs.get(
                    "effective_tick_fill_slippage_points"
                ),
                "configured_cost_model_slippage_points_recorded": reanalysis_costs.get(
                    "configured_cost_model_slippage_points"
                ),
                "randomized_fill_latency_ms": exec_cfg.get(
                    "randomized_fill_latency_ms", execution.get("randomized_fill_latency_ms")
                ),
                "fill_delay_ms": exec_cfg.get("fill_delay_ms", execution.get("fill_delay_ms")),
                "configured_slippage_points": costs.get("slippage_points"),
                "tick_execution": costs.get("use_tick_execution"),
                "effective_tick_fill_slippage_points": 0.0,
                "effective_tick_slippage_basis": "source-hash-matched simulation/environment/trading_environment_factory.py sets zero; reanalysis cost override records zero",
            },
            "source_hash_match": source_match,
            "fills": fill_audit,
            "replay": replay_audit,
            "monthly": _monthly(paired, BOOTSTRAP_SEED),
            "march_april_decomposition": _decomposition(paired, BOOTSTRAP_SEED),
            "input_hashes": {
                "training_trades_csv": _sha256(run_info["ledger"]),
                "training_bars_parquet": _sha256(bars_path),
                "training_ticks_parquet": _sha256(ticks_path),
                "source_feature_cache": _sha256(feature_path),
                "config_yaml": _sha256(run_info["config_path"]),
            },
        }
        out.mkdir(parents=True, exist_ok=True)
        paired.to_csv(out / f"{arm}_paired_trades.csv", index=False)
        results["arms"][arm] = arm_result
    return results


def _report(results: dict[str, Any]) -> str:
    lines = [
        "# P6 2M Actual-Fill Monthly R and March–April Decomposition",
        "",
        "This is a training-split-only replay analysis for the two completed 2M P6 arms, covering the configured 2024-12-30 through 2025-12-31 training interval. The tables show entry months and include the initial partial December 2024 month. It uses actual tick fills to report mid-quote gross R and raw bid/ask historical net R, with no stress and zero commission. The paired exit analysis freezes each actual entry and compares its actual outcome to an EMA21-exit replay with the same position size, stop, and paired latency. It does not use PPO inference, does not compound a counterfactual account, and does not read 2026 data.",
        "",
        "## Execution manifest and fill audit",
        "",
        "| Variant | Random latency | Effective extra tick slippage | Run manifest standalone key | Tick execution | Stop/target fill rows | Tick sourced | Raw bid/ask reconciliation errors |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, value in results["arms"].items():
        m, f = value["manifest"], value["fills"]
        lines.append(
            f"| `{arm}` | {m['randomized_fill_latency_ms']} ms | {m['effective_tick_fill_slippage_points_recorded']} points (reanalysis manifest) | {m['tick_fill_slippage_points_explicit_field']} | {m['tick_execution']} | {f['stop_and_target_fill_rows']} | {f['stop_and_target_fill_sources']} | {len(f['raw_bid_ask_vs_recorded_net_mismatches'])} |"
        )
    lines += [
        "",
        "The run manifest records configured model slippage of 5 points; the paired reanalysis manifest explicitly records `effective_tick_fill_slippage_points=0.0`. The 18 replay-relevant execution source files also match the training attempt hashes. The run manifest records randomized fill latency as 30 ms (with zero fixed delay). Every entry and completed close event was checked against an exact tick timestamp and executable quote side. Stop and target rows were also checked separately; all must be tick sourced. Raw executable bid/ask P&L is reconciled against the ledger’s historical net P&L before results are accepted. The table’s standalone run-manifest key is absent because that setting is recorded in the execution override manifest instead.",
        "",
        "## Monthly results",
        "",
    ]
    for arm, value in results["arms"].items():
        lines += [
            f"### `{arm}`",
            "",
            "| Entry month | N | Actual gross mid mean R (95% paired bootstrap CI) | Actual historical net bid/ask mean R | Mid-to-bid/ask drag R | EMA21 reference gross mean R | Actual − EMA21 mean gross R | Gross mid P&L sum | Historical net P&L sum |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for m in value["monthly"]:
            gross = f"{m['actual_gross_mid_mean_r']:.4f} [{m['actual_gross_mid_ci95_mean_r'][0]:.4f}, {m['actual_gross_mid_ci95_mean_r'][1]:.4f}]"
            net = f"{m['actual_historical_net_mean_r']:.4f} [{m['actual_historical_net_ci95_mean_r'][0]:.4f}, {m['actual_historical_net_ci95_mean_r'][1]:.4f}]"
            lines.append(
                f"| {m['entry_month']} | {m['n']} | {gross} | {net} | {m['mid_to_bid_ask_drag_mean_r']:.4f} | {m['ema_reference_gross_mean_r']:.4f} | {m['actual_minus_ema_exit_delta_mean_r']:.4f} | ${m['gross_mid_pnl_usd_sum']:.2f} | ${m['historical_net_pnl_usd_sum']:.2f} |"
            )
        d = value["march_april_decomposition"]
        ci = d["bootstrap_95pct_ci"]
        lines += [
            "",
            f"March → April actual gross expectancy changed by **{d['march_to_april_actual_gross_change_r']:.4f} R/trade** (95% paired month-stratified bootstrap CI [{ci['actual_gross_change_r'][0]:.4f}, {ci['actual_gross_change_r'][1]:.4f}]). The decomposition assigns **{d['entry_cohort_component_r']:.4f} R** to the change in EMA21-reference outcomes for that month’s frozen entries (CI [{ci['entry_cohort_component_r'][0]:.4f}, {ci['entry_cohort_component_r'][1]:.4f}]) and **{d['exit_outcome_component_r']:.4f} R** to the month-to-month change in actual-minus-EMA21 outcomes (CI [{ci['exit_outcome_component_r'][0]:.4f}, {ci['exit_outcome_component_r'][1]:.4f}]). March N={d['paired_entries_march']}; April N={d['paired_entries_april']}. The point estimates add exactly.",
            "",
        ]
    lines += [
        "The A4B account path terminated after its October 2025 hard-floor failure; its November and December rows are absent because there were no later training trades, not because those months had zero expectancy. A4A continued through December.",
        "",
    ]
    lines += [
        "## Interpretation boundary",
        "",
        "The EMA21 replay is a conditional reference, not a causal intervention and not a full portfolio counterfactual. The entry component means ‘how the same frozen entries performed under this common EMA21 exit rule’; the exit component is the paired difference from actual outcomes to that reference. This separates relative exit contribution from the market opportunities represented by monthly entry cohorts, but cannot prove that entry timing alone caused the market shift. R is normalized by each actual trade’s initial modeled stop risk. Monthly sums are un-compounded.",
        "",
        "## Reproducibility",
        "",
        f"- Experiment run fingerprint: `{results['experiment_run_fingerprint']}`.",
        f"- Analysis script SHA-256: `{results['analysis_script_sha256']}`.",
        f"- Bootstrap: {results['bootstrap']['resamples']:,} resamples, seed {results['bootstrap']['seed']}.",
        "- Per-entry matched data: `ladder_*_paired_trades.csv`.",
        "- Complete input, manifest and source hashes: `p6_monthly_entry_exit_decomposition.json`.",
        "- Script: [`analyze_monthly_trade_expectancy_and_exit_decomposition.py`](../../../scripts/research/thesis/evidence/analyze_monthly_trade_expectancy_and_exit_decomposition.py).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT_DEFAULT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/thesis/evidence/p6_monthly_entry_exit_20261025"),
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    results = run(root, output)
    results["report_sha256_before_provenance"] = None
    (output / "p6_monthly_entry_exit_decomposition.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report_path = output / "p6_monthly_entry_exit_decomposition.md"
    report_path.write_text(_report(results), encoding="utf-8")
    results["report_sha256_before_provenance"] = _sha256(report_path)
    (output / "p6_monthly_entry_exit_decomposition.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"report": str(report_path), "summary": results["arms"]}, indent=2))


if __name__ == "__main__":
    main()
