#!/usr/bin/env python3
"""Fail closed unless every portfolio-training seed remains hard-risk safe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify_run(run_dir: Path) -> dict[str, Any]:
    """Verify one portfolio run's persisted hard-risk evidence."""
    summary_path = run_dir / "evaluations/summary.json"
    train_path = run_dir / "evaluations/train_in_sample.json"
    if not summary_path.is_file() or not train_path.is_file():
        raise FileNotFoundError(f"portfolio evaluation artifacts missing under {run_dir}")
    summary = _object(summary_path)
    train = _object(train_path)
    gate = summary.get("train_equity_gate")
    if not isinstance(gate, dict):
        raise ValueError(f"{summary_path} lacks train_equity_gate")
    breaches = train.get("breach_events")
    safe = (
        summary.get("training_phase") == "portfolio_training"
        and summary.get("training_completed") is True
        and gate.get("hard_risk_ok") is True
        and gate.get("breached") is False
        and train.get("completed_data_split") is True
        and isinstance(breaches, int)
        and not isinstance(breaches, bool)
        and breaches == 0
    )
    return {
        "run_dir": str(run_dir.resolve()),
        "status": "pass" if safe else "fail",
        "seed": summary.get("seed"),
        "training_phase": summary.get("training_phase"),
        "training_completed": summary.get("training_completed"),
        "hard_risk_ok": gate.get("hard_risk_ok"),
        "breached": gate.get("breached"),
        "completed_data_split": train.get("completed_data_split"),
        "breach_events": breaches,
        "summary": str(summary_path.resolve()),
        "summary_sha256": file_sha256(summary_path),
        "train_evaluation": str(train_path.resolve()),
        "train_evaluation_sha256": file_sha256(train_path),
    }


def verify_runs(run_dirs: list[Path]) -> dict[str, Any]:
    """Verify all configured portfolio seeds; one failure makes the candidate ineligible."""
    if not run_dirs:
        raise ValueError("at least one portfolio run directory is required")
    rows = [verify_run(path.expanduser().resolve()) for path in run_dirs]
    seeds = [row["seed"] for row in rows]
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
        raise ValueError("portfolio evaluation summaries require integer seeds")
    if len(seeds) != len(set(seeds)):
        raise ValueError("portfolio run list contains duplicate seeds")
    return {
        "schema_version": "v3-portfolio-hard-risk-review-v1",
        "status": "pass" if all(row["status"] == "pass" for row in rows) else "fail",
        "seed_count": len(rows),
        "all_paths_hard_risk_safe": all(row["status"] == "pass" for row in rows),
        "runs": rows,
        "interpretation": "Any hard breach makes the candidate ineligible; failures are not averaged.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = verify_runs(args.run_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
