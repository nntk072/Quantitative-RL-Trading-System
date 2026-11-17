#!/usr/bin/env python3
"""Measure configured M1 policy-action eligibility over the training split."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from omegaconf import OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from evaluation.candidate_eligibility import CandidateActionEligibilityIndex
from market_data.loading.bars import load_bars
from market_data.transforms.sessions import ny_session_mask

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_OUTPUT = ROOT / "evidence/research/candidate_action_eligibility"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_training_eligibility(
    config_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write a local-data census of NY/session/fill-bar eligibility."""
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite eligibility packet: {output_dir}")
    cfg = load_config(config_path=config_path)
    primary = str(cfg.data.primary)
    data_spec = cfg.data.datasets.training
    relative_m1 = Path(str(data_spec.m1_files[primary]))
    raw_dir = Path(str(data_spec.raw_dir))
    m1_path = (ROOT / raw_dir / relative_m1).resolve()
    bars = load_bars(m1_path)
    timezone = str(cfg.data.tz)
    bars.index = pd.DatetimeIndex(bars.index).tz_localize(timezone)
    train_start = pd.Timestamp(str(cfg.data.split.train_start), tz=timezone)
    train_end = pd.Timestamp(str(cfg.data.split.train_end), tz=timezone) + pd.Timedelta(days=1)
    bars = bars.loc[(bars.index >= train_start) & (bars.index < train_end)]
    if bars.empty or not bars.index.is_unique or not bars.index.is_monotonic_increasing:
        raise ValueError("training M1 bars must be non-empty, sorted, and unique")

    session_start = str(cfg.session.start)
    session_end = str(cfg.session.end)
    bar_index = pd.DatetimeIndex(bars.index)
    ny_mask = ny_session_mask(bar_index, start=session_start, end=session_end)
    labels = pd.Series("closed", index=bars.index, dtype=str)
    labels.loc[ny_mask] = "ny"
    session_ids = pd.Series(
        bar_index.normalize().to_numpy(dtype="datetime64[ns]").view("i8"), index=bar_index
    )
    eligibility = CandidateActionEligibilityIndex(
        bar_index,
        labels,
        session_ids=session_ids,
        fill_latency_bars=int(cfg.execution.get("fill_latency_bars", 0)),
        open_manipulation_bars=int(cfg.env.get("open_manipulation_bars", 0)),
        block_overnight=bool(cfg.env.get("block_overnight", True)),
    )

    reason_counts: Counter[str] = Counter()
    session_counts: dict[str, Counter[str]] = defaultdict(Counter)
    fill_position_count = 0
    for position, timestamp in enumerate(bars.index):
        result = eligibility.classify(position)
        reason_counts[result.reason] += 1
        session_counts[timestamp.strftime("%Y-%m-%d")][result.reason] += 1
        if result.fill_position is not None:
            fill_position_count += 1

    session_rows = []
    for date, counts in sorted(session_counts.items()):
        total = sum(counts.values())
        session_rows.append(
            {
                "session_date": date,
                "m1_rows": total,
                "eligible_action_rows": counts["eligible"],
                **{f"reason_{key}": value for key, value in sorted(counts.items())},
            }
        )

    eligibility_path = output_dir / "training_action_eligibility_by_session.csv"
    summary_path = output_dir / "training_action_eligibility_summary.json"
    output_dir.mkdir(parents=True)
    pd.DataFrame.from_records(session_rows).to_csv(eligibility_path, index=False)
    summary = {
        "status": "configured_training_bar_eligibility_census",
        "schema_version": "training-action-eligibility-census-v1",
        "primary_symbol": primary,
        "training_window": {
            "start_inclusive": train_start.isoformat(),
            "end_exclusive": train_end.isoformat(),
        },
        "m1_row_count": len(bars),
        "ny_session_row_count": int(ny_mask.sum()),
        "action_eligible_row_count": reason_counts["eligible"],
        "action_eligible_fraction": reason_counts["eligible"] / len(bars),
        "fill_position_count": fill_position_count,
        "eligibility_reason_counts": dict(sorted(reason_counts.items())),
        "execution_controls": {
            "fill_latency_bars": int(cfg.execution.get("fill_latency_bars", 0)),
            "open_manipulation_bars": int(cfg.env.get("open_manipulation_bars", 0)),
            "block_overnight": bool(cfg.env.get("block_overnight", True)),
            "session_start": session_start,
            "session_end": session_end,
        },
        "scope_limit": (
            "bar-level static eligibility only; not active feature candidates, "
            "account-state eligibility, proposal counts, fills, or policy actions"
        ),
        "input": {
            "path": m1_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(m1_path),
            "size_bytes": m1_path.stat().st_size,
        },
        "resolved_config_sha256": hashlib.sha256(
            OmegaConf.to_yaml(cfg, resolve=True).encode()
        ).hexdigest(),
        "sources": {
            path: _sha256(ROOT / path)
            for path in (
                "scripts/research/analysis/evaluation/audit_candidate_action_eligibility.py",
                "evaluation/candidate_eligibility.py",
                "market_data/loading/bars.py",
                "market_data/transforms/sessions.py",
            )
        },
        "outputs": {
            eligibility_path.name: _sha256(eligibility_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        "# Candidate action eligibility census\n\n"
        "This packet measures configured bar-level NY/session and entry-fill eligibility "
        "on local training M1 bars. It is a denominator and environment-rule check; "
        "it does not count active setup features, proposals, fills, account-state "
        "constraints, or policy actions. See the JSON summary for hashes and limits.\n",
        encoding="utf-8",
    )
    checksum_paths = (eligibility_path, summary_path, readme_path)
    sums = "\n".join(f"{_sha256(path)}  {path.name}" for path in checksum_paths) + "\n"
    (output_dir / "OUTPUT_SHA256SUMS").write_text(sums, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    print(json.dumps(audit_training_eligibility(config_path, output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
