"""Summarize existing per-position excursion ledgers by recorded exit reason.

This is a descriptive cohort analysis of already-reconstructed trade paths. It
does not replay a policy, estimate an alternative exit, or infer causality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = (
    "position_id",
    "exit_reason",
    "position_net_pnl_usd",
    "realized_r",
    "mfe_r_lower",
    "mae_r_lower",
    "mfe_lower_r_reaches_one",
    "holding_seconds",
    "entry_timestamp_tie_rows",
    "exit_timestamp_tie_rows",
)
METRIC_COLUMNS = (
    "position_net_pnl_usd",
    "realized_r",
    "mfe_r_lower",
    "mae_r_lower",
    "holding_seconds",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_named_path(value: str) -> tuple[str, Path]:
    name, separator, path_value = value.partition("=")
    if not separator or not name.strip() or not path_value.strip():
        raise argparse.ArgumentTypeError("expected NAME=CSV")
    return name.strip(), Path(path_value.strip())


def summarize_arm(name: str, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return source identity and exit-reason cohorts for one position ledger."""
    frame = pd.read_csv(path, low_memory=False)
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")
    if frame["position_id"].isna().any() or frame["position_id"].duplicated().any():
        raise ValueError(f"{path} must have one row per non-null position_id")
    if frame["exit_reason"].isna().any():
        raise ValueError(f"{path} contains positions without an exit_reason")

    rows: list[dict[str, Any]] = []
    for reason, cohort in frame.groupby("exit_reason", sort=True, dropna=False):
        row: dict[str, Any] = {
            "arm": name,
            "exit_reason": str(reason),
            "position_count": int(len(cohort)),
            "net_pnl_usd_sum": float(pd.to_numeric(cohort["position_net_pnl_usd"]).sum()),
            "one_r_mfe_share": float(
                pd.to_numeric(cohort["mfe_lower_r_reaches_one"], errors="coerce")
                .fillna(0)
                .astype(bool)
                .mean()
            ),
            "entry_timestamp_tie_positions": int(
                (pd.to_numeric(cohort["entry_timestamp_tie_rows"], errors="coerce") > 1).sum()
            ),
            "exit_timestamp_tie_positions": int(
                (pd.to_numeric(cohort["exit_timestamp_tie_rows"], errors="coerce") > 1).sum()
            ),
        }
        for column in METRIC_COLUMNS:
            values = pd.to_numeric(cohort[column], errors="coerce").to_numpy(dtype=np.float64)
            values = values[np.isfinite(values)]
            key = column.removesuffix("_seconds").removesuffix("_usd")
            row[f"{key}_finite_count"] = int(values.size)
            row[f"{key}_mean"] = float(values.mean()) if values.size else None
            row[f"{key}_median"] = float(np.median(values)) if values.size else None
            if column == "holding_seconds":
                row["holding_hours_p90"] = (
                    float(np.quantile(values, 0.9) / 3600.0) if values.size else None
                )
        rows.append(row)

    identity = {
        "source_path": str(path.resolve()),
        "source_sha256": _sha256(path),
        "position_count": int(len(frame)),
        "exit_reasons": sorted(frame["exit_reason"].astype(str).unique().tolist()),
    }
    return identity, rows


def build_report(inputs: list[tuple[str, Path]]) -> tuple[dict[str, Any], pd.DataFrame]:
    """Build a multi-arm report without treating separate cohorts as paired."""
    if not inputs:
        raise ValueError("at least one named position ledger is required")
    names = [name for name, _ in inputs]
    if len(names) != len(set(names)):
        raise ValueError("arm names must be unique")
    missing = [str(path) for _, path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"position ledgers are missing: {missing}")

    identities: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for name, path in inputs:
        identities[name], arm_rows = summarize_arm(name, path)
        rows.extend(arm_rows)
    report = {
        "schema_version": 1,
        "evidence_class": "descriptive_exit_reason_cohorts",
        "causal_attribution": False,
        "policy_replay_performed": False,
        "cohorts_are_paired": False,
        "realized_r_basis": "position net PnL divided by initial modeled stop risk",
        "excursion_basis": "lower timestamp-bound price excursion divided by initial stop distance",
        "cost_r_available": False,
        "interpretation_limit": (
            "Separate historical cohorts; descriptive outcomes do not estimate feasible alternative exits. "
            "Realized net R and price-only MFE/MAE use different numerators."
        ),
        "analysis_tool_path": str(Path(__file__).resolve()),
        "analysis_tool_sha256": _sha256(Path(__file__).resolve()),
        "arms": identities,
    }
    return report, pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm", action="append", type=_parse_named_path, default=[], metavar="NAME=CSV"
    )
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--csv-out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report, frame = build_report(args.arm)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        parser.error(str(exc))
    for path in (args.json_out, args.csv_out):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    frame.to_csv(args.csv_out, index=False, float_format="%.12g")
    print(f"wrote {args.json_out.resolve()} and {args.csv_out.resolve()} ({len(frame)} cohorts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
