#!/usr/bin/env python3
"""Attribute a saved training trade ledger to causal, completed-D1 regimes.

This is a descriptive development analysis. It does not tune a policy, use the
2026 report interval, or claim that a regime association is causal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_data.transforms.align import timeframe_close_times

TECHNICAL_D1_FEATURES = (
    "D1_ret_5",
    "D1_ret_30",
    "D1_ema_21_dist",
    "D1_ema_50_dist",
    "D1_ema_200_dist",
    "D1_adx",
    "D1_realized_vol",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_completed_daily_context(daily_bars: pd.DataFrame) -> pd.DataFrame:
    """Build simple daily states and mark when each completed bar is usable."""
    if "close" not in daily_bars:
        raise ValueError("daily bars must contain a close column")
    if not isinstance(daily_bars.index, pd.DatetimeIndex) or daily_bars.index.tz is None:
        raise ValueError("daily bars require a timezone-aware DatetimeIndex")
    bars = daily_bars.sort_index()
    close = pd.to_numeric(bars["close"], errors="coerce")
    log_return = np.log(close.where(close > 0)).diff()
    context = pd.DataFrame(index=bars.index)
    context["ret_5d"] = np.log(close / close.shift(5))
    context["ret_20d"] = np.log(close / close.shift(20))
    context["ret_60d"] = np.log(close / close.shift(60))
    context["realized_vol_20d"] = log_return.rolling(20, min_periods=20).std(ddof=0)

    both_trends = context["ret_20d"].notna() & context["ret_60d"].notna()
    context["trend_regime"] = "warmup"
    context.loc[both_trends, "trend_regime"] = "mixed"
    context.loc[
        both_trends & (context["ret_20d"] > 0) & (context["ret_60d"] > 0), "trend_regime"
    ] = "bull"
    context.loc[
        both_trends & (context["ret_20d"] < 0) & (context["ret_60d"] < 0), "trend_regime"
    ] = "bear"

    # Volatility cutoffs use only earlier completed daily observations.
    prior_vol = context["realized_vol_20d"].shift(1)
    low_cut = prior_vol.expanding(min_periods=60).quantile(1.0 / 3.0)
    high_cut = prior_vol.expanding(min_periods=60).quantile(2.0 / 3.0)
    context["volatility_regime"] = "warmup"
    valid_vol = context["realized_vol_20d"].notna() & low_cut.notna() & high_cut.notna()
    context.loc[valid_vol, "volatility_regime"] = "mid"
    context.loc[valid_vol & (context["realized_vol_20d"] <= low_cut), "volatility_regime"] = "low"
    context.loc[valid_vol & (context["realized_vol_20d"] >= high_cut), "volatility_regime"] = "high"

    context["available_at"] = timeframe_close_times(bars, "D1").to_numpy()
    return context.reset_index(names="daily_bar_open")


def attach_completed_context(timestamps: pd.Series, daily_context: pd.DataFrame) -> pd.DataFrame:
    """As-of join the last completed daily state to each decision timestamp."""
    decisions = pd.to_datetime(timestamps, utc=True, errors="coerce")
    available = daily_context.copy()
    available["available_at"] = pd.to_datetime(available["available_at"], utc=True)
    available = available.sort_values("available_at")
    query = pd.DataFrame({"decision_time": decisions, "row_order": np.arange(len(decisions))})
    valid = query.loc[query["decision_time"].notna()].sort_values("decision_time")
    joined = pd.merge_asof(
        valid,
        available,
        left_on="decision_time",
        right_on="available_at",
        direction="backward",
        allow_exact_matches=True,
    )
    return joined.sort_values("row_order").reset_index(drop=True)


def _group_summary(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    grouped = frame.groupby(keys, dropna=False, observed=True)
    result = grouped.agg(
        trades=("net_pnl", "size"),
        net_pnl_usd=("net_pnl", "sum"),
        mean_net_r=("net_r", "mean"),
        median_net_r=("net_r", "median"),
        win_rate=("net_pnl", lambda values: float((values > 0).mean())),
        mean_risk_usd=("risk_cash", "mean"),
    )
    return result.reset_index()


def _markdown_table(frame: pd.DataFrame, limit: int = 80) -> str:
    if frame.empty:
        return "_(No rows.)_"
    shown = frame.head(limit).copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(
                lambda value: "" if pd.isna(value) else f"{value:.4f}"
            )
    headers = [str(column) for column in shown.columns]
    rows = [
        ["" if pd.isna(value) else str(value).replace("|", "\\|") for value in values]
        for values in shown.itertuples(index=False, name=None)
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _decision_intent_summary(trades: pd.DataFrame) -> pd.DataFrame:
    """Summarize logged open/reject intents, not every policy action."""
    intents = trades.loc[trades["type"].isin(["open", "reject"])].copy()
    time_values = intents["decision_time"].where(intents["decision_time"].notna(), intents["time"])
    intents["month"] = pd.to_datetime(time_values, utc=True, errors="coerce").dt.strftime("%Y-%m")
    intents = intents.loc[intents["month"].notna()]
    rows: list[dict[str, Any]] = []
    for month, group in intents.groupby("month", sort=True):
        direction = pd.to_numeric(group["action_direction"], errors="coerce")
        intensity = pd.to_numeric(group["action_intensity"], errors="coerce")
        risk = pd.to_numeric(group["action_risk"], errors="coerce")
        opened = int(group["type"].eq("open").sum())
        rejected = int(group["type"].eq("reject").sum())
        rows.append(
            {
                "month": month,
                "logged_entry_intents": int(len(group)),
                "opened": opened,
                "rejected": rejected,
                "open_event_share": opened / len(group) if len(group) else np.nan,
                "long_intent_share": float((direction > 0).mean()),
                "short_intent_share": float((direction < 0).mean()),
                "neutral_intent_share": float((direction == 0).mean()),
                "mean_action_intensity": float(intensity.mean()),
                "mean_action_risk": float(risk.mean()),
            }
        )
    return pd.DataFrame(rows)


def _load_and_join(
    run_dir: Path, daily_bars_path: Path
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    trades_path = run_dir / "training" / "trades.csv"
    positions_path = run_dir / "training" / "positions.csv"
    manifest_path = run_dir / "run_manifest.json"
    trades = pd.read_csv(trades_path, low_memory=False)
    decision_summary = _decision_intent_summary(trades)
    positions = pd.read_csv(positions_path, low_memory=False)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    opens = trades.loc[trades["type"].eq("open")].copy()
    open_rows = opens.drop_duplicates("position_id", keep="first")
    outcomes = positions.drop_duplicates("position_id", keep="last")
    joined = open_rows.merge(
        outcomes, on="position_id", how="inner", suffixes=("_entry", "_outcome")
    )
    if len(joined) != len(open_rows):
        raise ValueError(f"joined {len(joined)} outcomes for {len(open_rows)} open rows")
    pnl_column = "net_pnl_outcome" if "net_pnl_outcome" in joined else "net_pnl"
    if pnl_column not in joined:
        pnl_column = "position_net_pnl_outcome"
    if pnl_column not in joined:
        raise ValueError("positions ledger has no net PnL column")
    joined["net_pnl"] = pd.to_numeric(joined[pnl_column], errors="coerce")
    joined["risk_cash"] = pd.to_numeric(joined["risk_cash"], errors="coerce")
    joined["net_r"] = joined["net_pnl"] / joined["risk_cash"].where(joined["risk_cash"] > 0)
    direction_column = "direction_entry" if "direction_entry" in joined else "direction"
    joined["side"] = np.where(
        pd.to_numeric(joined[direction_column], errors="coerce") > 0, "long", "short"
    )
    joined["decision_time"] = pd.to_datetime(joined["decision_time"], utc=True, errors="coerce")
    joined["month"] = joined["decision_time"].dt.strftime("%Y-%m")
    daily_bars = pd.read_parquet(daily_bars_path)
    context = build_completed_daily_context(daily_bars)
    attached = attach_completed_context(joined["decision_time"], context)
    for column in (
        "ret_5d",
        "ret_20d",
        "ret_60d",
        "realized_vol_20d",
        "trend_regime",
        "volatility_regime",
    ):
        joined[column] = attached[column].to_numpy()
    for column in ("trend_regime", "volatility_regime"):
        joined[column] = joined[column].fillna("unavailable")
    joined["combined_regime"] = (
        joined["trend_regime"].astype(str) + "/" + joined["volatility_regime"].astype(str)
    )
    provenance = {
        "run_dir": str(run_dir.resolve()),
        "training_trades_sha256": sha256_file(trades_path),
        "training_positions_sha256": sha256_file(positions_path),
        "run_manifest_sha256": sha256_file(manifest_path),
        "daily_bars_path": str(daily_bars_path.resolve()),
        "daily_bars_sha256": sha256_file(daily_bars_path),
        "feature_cache": manifest.get("feature_cache", {}),
        "split": manifest.get("split", {}),
        "trade_count": int(len(joined)),
    }
    return joined, provenance, decision_summary


def _feature_exposure(run_manifest: dict[str, Any], entries: pd.DataFrame) -> pd.DataFrame:
    cache_path = Path(str(run_manifest["feature_cache"]["path"]))
    selected = [*TECHNICAL_D1_FEATURES, "D1_dist_to_swing_high_atr", "D1_dist_to_swing_low_atr"]
    available = pd.read_parquet(cache_path, columns=selected)
    query_times = pd.DatetimeIndex(
        pd.to_datetime(entries["decision_time"], utc=True, errors="coerce")
    )
    positions = pd.DatetimeIndex(available.index).tz_convert("UTC").get_indexer(query_times)
    rows = []
    for name in selected:
        values = pd.to_numeric(available[name], errors="coerce").to_numpy()
        valid_entry = (positions >= 0) & pd.notna(values[np.maximum(positions, 0)])
        rows.append(
            {
                "feature": name,
                "finite_at_decisions": int(valid_entry.sum()),
                "trades": int(len(entries)),
                "unique_finite_entry_values": int(
                    pd.Series(values[np.maximum(positions, 0)][valid_entry]).nunique()
                ),
            }
        )
    return pd.DataFrame(rows)


def generate_report(
    run_dir: Path,
    daily_bars_path: Path,
    report_path: Path,
    output_dir: Path,
    feature_rebuild_check: Path | None = None,
) -> None:
    joined, provenance, decisions = _load_and_join(run_dir, daily_bars_path)
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    exposure = _feature_exposure(manifest, joined)
    feature_comparison = pd.DataFrame()
    feature_check: dict[str, Any] | None = None
    if feature_rebuild_check is not None:
        feature_check = json.loads(feature_rebuild_check.read_text(encoding="utf-8"))
        feature_comparison = pd.DataFrame(
            [
                {
                    "feature": feature,
                    "entries": feature_check["entry_count"],
                    "baseline_finite": feature_check["baseline_availability"][feature][
                        "finite_at_entries"
                    ],
                    "source_normalized_finite": feature_check["treatment_availability"][feature][
                        "finite_at_entries"
                    ],
                    "source_normalized_unique": feature_check["treatment_availability"][feature][
                        "unique_finite_values"
                    ],
                }
                for feature in TECHNICAL_D1_FEATURES
            ]
        )
        provenance["feature_rebuild_check_path"] = str(feature_rebuild_check.resolve())
        provenance["feature_rebuild_check_sha256"] = sha256_file(feature_rebuild_check)
        provenance["treatment_feature_cache_sha256"] = feature_check[
            "treatment_feature_cache_sha256"
        ]
    monthly = _group_summary(joined, ["month", "side"])
    by_trend_side = _group_summary(joined, ["trend_regime", "side"])
    by_vol_side = _group_summary(joined, ["volatility_regime", "side"])
    by_joint = _group_summary(joined, ["combined_regime", "side"])
    output_dir.mkdir(parents=True, exist_ok=True)
    trade_columns = [
        "position_id",
        "decision_time",
        "month",
        "side",
        "trend_regime",
        "volatility_regime",
        "ret_5d",
        "ret_20d",
        "ret_60d",
        "realized_vol_20d",
        "risk_cash",
        "net_pnl",
        "net_r",
    ]
    csv_outputs = {
        "trade_regimes.csv": joined[trade_columns],
        "decision_intents_by_month.csv": decisions,
        "monthly_by_side.csv": monthly,
        "trend_by_side.csv": by_trend_side,
        "volatility_by_side.csv": by_vol_side,
        "trend_volatility_by_side.csv": by_joint,
        "d1_feature_exposure.csv": exposure,
    }
    if not feature_comparison.empty:
        csv_outputs["d1_feature_normalization_comparison.csv"] = feature_comparison
    for name, frame in csv_outputs.items():
        frame.to_csv(output_dir / name, index=False)
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    month_table = monthly.sort_values(["month", "side"])
    lines = [
        "# Causal regime attribution — completed 2025 DSR training replay",
        "",
        "**Scope:** descriptive attribution of the completed seed-50 DSR PPO training replay. The report uses only completed daily bars available before each entry. It does not use the 2026 report interval and does not select or tune a policy.",
        "",
        "## Reproduction",
        "",
        "Run `scripts/research/thesis/regime_attribution.py` with the same saved `training/trades.csv`, `training/positions.csv`, `run_manifest.json`, and training D1 bar file. The compact CSV outputs beside this report are generated by that command.",
        "",
        "## Source identity",
        "",
        f"- Run directory: `{provenance['run_dir']}`",
        f"- Trades SHA-256: `{provenance['training_trades_sha256']}`",
        f"- Positions SHA-256: `{provenance['training_positions_sha256']}`",
        f"- Manifest SHA-256: `{provenance['run_manifest_sha256']}`",
        f"- Daily bars SHA-256: `{provenance['daily_bars_sha256']}`",
        f"- Completed positions joined: {provenance['trade_count']:,}",
        "",
        "## Monthly outcomes by side",
        "",
        "Net R is position net PnL divided by the recorded filled-stop risk (`risk_cash`). PnL is the saved after-execution outcome; this ledger does not isolate mid-price gross PnL from spread/slippage costs.",
        "",
        _markdown_table(month_table),
        "",
        "## Outcomes by causal D1 trend and volatility state",
        "",
        "Trend is bull/bear only when completed 20-day and 60-day log returns agree; otherwise it is mixed. It is `warmup` until both are available. Volatility is split by expanding terciles of prior completed 20-day realized volatility, with at least 60 prior observations; it remains `warmup` before that.",
        "",
        "### Trend × side",
        "",
        _markdown_table(by_trend_side),
        "",
        "### Volatility × side",
        "",
        _markdown_table(by_vol_side),
        "",
        "### Trend × volatility × side",
        "",
        _markdown_table(by_joint),
        "",
        "## Logged policy entry-intent behavior",
        "",
        "The training ledger saves action vectors on `open` and `reject` entry-intent events. It does not save no-op decisions or actions taken while a position is open, so these are entry-intent summaries rather than the full policy action distribution.",
        "",
        "`open_event_share` is an event conversion rate, not a learned abstention rate: reject rows include environment/setup eligibility failures. The account hard-loss gate was reached on November 13; zero open events in December are therefore gate blocking, not evidence that the PPO learned to stay flat.",
        "",
        _markdown_table(decisions),
        "",
        "## What the model received",
        "",
        "The saved sequence schema lists 74 D1 columns, but the technical momentum/trend channels below were missing at all 1,110 accepted-entry decision times in the cached feature matrix. The 60 previous M1 rows in the actual TCN observation therefore could not recover those values at entry. Some D1 structural and swing-distance channels remained populated; this does not mean the model had no D1 information at all.",
        "",
        _markdown_table(exposure),
        "",
        "### Real-data cache comparison after the minimal repair",
        "",
        (
            "The repeatable cache check rebuilt features from the saved run configuration and the same native training/testing bars, with only `features.normalize_d1_technical_on_source` enabled. The original cache had zero finite values for these seven D1 technical columns at all 1,110 entry decisions; the treatment cache restores the following completed-D1 values. Early missing values remain expected for warmup or incomplete histories. This verifies input availability, not that PPO performance improves."
            if feature_check is not None
            else "No repaired-cache comparison was supplied for this report."
        ),
        "",
        _markdown_table(feature_comparison),
        "",
        (
            f"Treatment cache identity: `{feature_check['treatment_cache_hash_sidecar']}`; SHA-256: `{feature_check['treatment_feature_cache_sha256']}`. The full cache check and input identities are in `d1_feature_rebuild_check.json`."
            if feature_check is not None
            else ""
        ),
        "",
        "The reproducible source path is: higher-timeframe bars are causally aligned to the M1 spine, then the shared 252-row z-score is applied after alignment. A D1 value is constant across M1 rows between daily updates. Once the rolling window contains only the same D1 value, its standard deviation is zero; `rolling_zscore` replaces zero standard deviation with missing, and the observation builder converts missing values to zero. A direct June 2, 2025 reproduction retained a D1 return for 251 M1 rows and produced missing values from 05:16 local time onward, including the NY trading session.",
        "",
        "## Finding and limits",
        "",
        "1. The existing `trend_regime` field is not a slow trend label: the open ledger records it as `flat` for every accepted trade. It is derived from same-day Asia/London premium-discount bias.",
        "2. The policy did not receive the cached normalized D1 momentum/trend indicators during its NY entry decisions, despite those columns appearing in the feature schema. This is a demonstrated feature-normalization defect, not proof that it alone caused the equity decline.",
        "3. The regime/side tables show whether observed trade expectancy is concentrated by the causal D1 labels. They remain descriptive single-seed, in-sample associations; low-count cells and the hard-loss stop limit inference.",
        "4. This analysis cannot isolate transaction-cost drag because the saved position outcomes do not provide a comparable mid-price gross counterfactual. Do not attribute the loss to costs from this report.",
        "5. The minimum justified next experiment is a matched TCN run that corrects only D1 technical-feature normalization on the D1 source index before alignment. Keep the PPO, action schema, risk limits, and training protocol fixed; defer a new encoder and extra indicator family unless the repaired-input results justify them.",
        "",
        "## Provenance outputs",
        "",
        "See `provenance.json`, `trade_regimes.csv`, `decision_intents_by_month.csv`, `monthly_by_side.csv`, `trend_by_side.csv`, `volatility_by_side.csv`, `trend_volatility_by_side.csv`, `d1_feature_exposure.csv`, and (when available) `d1_feature_normalization_comparison.csv` beside this report.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--daily-bars", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--feature-rebuild-check", type=Path)
    args = parser.parse_args()
    generate_report(
        args.run_dir,
        args.daily_bars,
        args.report,
        args.output_dir,
        feature_rebuild_check=args.feature_rebuild_check,
    )
    print(f"wrote {args.report} and machine-readable outputs under {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
