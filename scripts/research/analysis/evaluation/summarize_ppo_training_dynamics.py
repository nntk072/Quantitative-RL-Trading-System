"""Summarize recorded PPO optimizer metrics without replaying a checkpoint.

Accepts one or more ``NAME=training_log.csv`` inputs and writes a
hash-identified descriptive summary. Missing or non-finite values are retained
as counts; this tool does not define PPO health thresholds or infer causality.
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

PPO_METRIC_COLUMNS = (
    "train/entropy_loss",
    "train/policy_gradient_loss",
    "train/value_loss",
    "train/approx_kl",
    "train/clip_fraction",
    "train/loss",
    "train/explained_variance",
)
STEP_COLUMNS = ("timestep", "time/total_timesteps", "total_timesteps", "steps")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _step_value(value: Any) -> int | float | None:
    """Return a JSON-safe numeric step while preserving integer steps."""
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def summarize_metric(values: pd.Series, steps: pd.Series | None = None) -> dict[str, Any]:
    """Summarize a numeric metric and distinguish absent, invalid, and infinite rows."""
    numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype=np.float64)
    finite = np.isfinite(numeric)
    valid = numeric[finite]
    original_missing = values.isna().to_numpy()
    nonnumeric = np.isnan(numeric) & ~original_missing

    result: dict[str, Any] = {
        "row_count": int(len(values)),
        "finite_count": int(finite.sum()),
        "missing_count": int(original_missing.sum()),
        "nonnumeric_count": int(nonnumeric.sum()),
        "positive_infinity_count": int(np.isposinf(numeric).sum()),
        "negative_infinity_count": int(np.isneginf(numeric).sum()),
    }
    if not valid.size:
        result["status"] = "no_finite_values"
        return result

    percentiles = np.quantile(valid, [0.05, 0.5, 0.95])
    result.update(
        {
            "status": "summarized",
            "first_finite": float(valid[0]),
            "last_finite": float(valid[-1]),
            "minimum": float(valid.min()),
            "maximum": float(valid.max()),
            "mean": float(valid.mean()),
            "p05": float(percentiles[0]),
            "median": float(percentiles[1]),
            "p95": float(percentiles[2]),
        }
    )
    if steps is not None:
        step_values = pd.to_numeric(steps, errors="coerce").to_numpy(dtype=np.float64)
        finite_steps = step_values[finite & np.isfinite(step_values)]
        result["first_finite_step"] = _step_value(finite_steps[0]) if finite_steps.size else None
        result["last_finite_step"] = _step_value(finite_steps[-1]) if finite_steps.size else None
    return result


def summarize_training_log(path: Path) -> dict[str, Any]:
    """Read one PPO training log and summarize known optimizer metrics."""
    frame = pd.read_csv(path, low_memory=False)
    step_column = next((column for column in STEP_COLUMNS if column in frame.columns), None)
    steps = None if step_column is None else frame[step_column]
    metrics: dict[str, Any] = {}
    for column in PPO_METRIC_COLUMNS:
        if column not in frame.columns:
            metrics[column] = {"status": "missing_column", "row_count": int(len(frame))}
        else:
            metrics[column] = summarize_metric(frame[column], steps)

    numeric_step_values: list[int | float] = []
    if steps is not None:
        parsed_steps = pd.to_numeric(steps, errors="coerce").to_numpy(dtype=np.float64)
        numeric_step_values = [
            step for raw in parsed_steps if (step := _step_value(raw)) is not None
        ]
    return {
        "source_path": str(path.resolve()),
        "source_sha256": _sha256(path),
        "row_count": int(len(frame)),
        "step_column": step_column,
        "step_min": min(numeric_step_values) if numeric_step_values else None,
        "step_max": max(numeric_step_values) if numeric_step_values else None,
        "available_columns": [column for column in PPO_METRIC_COLUMNS if column in frame.columns],
        "metrics": metrics,
    }


def _parse_named_path(value: str) -> tuple[str, Path]:
    """Parse ``NAME=PATH`` while preserving equals signs inside the path."""
    name, separator, path_value = value.partition("=")
    if not separator or not name.strip() or not path_value.strip():
        raise argparse.ArgumentTypeError("expected NAME=PATH")
    return name.strip(), Path(path_value.strip())


def build_report(inputs: list[tuple[str, Path]]) -> dict[str, Any]:
    """Build the descriptive multi-arm summary and validate each source."""
    if not inputs:
        raise ValueError("at least one named training log is required")
    names = [name for name, _ in inputs]
    if len(names) != len(set(names)):
        raise ValueError("training log names must be unique")
    missing = [str(path) for _, path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"training log inputs are missing: {missing}")
    return {
        "schema_version": 1,
        "evidence_class": "descriptive_training_telemetry",
        "thresholds_applied": False,
        "quantile_method": "numpy.quantile default linear",
        "analysis_tool_path": str(Path(__file__).resolve()),
        "analysis_tool_sha256": _sha256(Path(__file__).resolve()),
        "arms": {name: summarize_training_log(path) for name, path in inputs},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm",
        action="append",
        type=_parse_named_path,
        default=[],
        metavar="NAME=CSV",
        help="training log input; repeat once per arm",
    )
    parser.add_argument("--out", type=Path, required=True, help="JSON output path")
    args = parser.parse_args()
    try:
        report = build_report(args.arm)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out.resolve()} ({len(report['arms'])} arms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
