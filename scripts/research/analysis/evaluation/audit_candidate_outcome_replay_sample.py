#!/usr/bin/env python3
"""Recompute a deterministic sample of candidate bracket outcomes by disposition."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
from scripts.research.analysis.evaluation.replay_candidate_proposal_outcomes import (
    _proposal,
)

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from evaluation.candidate_execution import replay_candidate_proposal
from evaluation.candidate_quote_coverage import CandidateQuoteCoverage
from market_data.loading import build_tick_books

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_PROPOSALS = ROOT / "evidence/research/candidate_proposals"
DEFAULT_COVERAGE = ROOT / "evidence/research/tick_quote_coverage"
DEFAULT_OUTCOMES = ROOT / "evidence/research/candidate_outcomes"
SOURCE_FILES = (
    "evaluation/candidate_execution.py",
    "evaluation/candidate_outcomes.py",
    "evaluation/candidate_proposals.py",
    "evaluation/candidate_quote_coverage.py",
    "market_data/loading/ticks.py",
    "scripts/research/analysis/evaluation/replay_candidate_proposal_outcomes.py",
    "trading/execution/quotes.py",
)
REPORT_NAME = "outcome_replay_sample_verification.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_packet(packet: Path) -> None:
    for line in (packet / "OUTPUT_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        if _sha256(packet / name.strip()) != expected:
            raise ValueError(f"packet checksum mismatch: {packet / name.strip()}")


def _matches(expected: Any, actual: Any) -> bool:
    if expected is None:
        return bool(pd.isna(actual))
    if isinstance(expected, (float, int)) and not isinstance(expected, bool):
        try:
            return math.isclose(float(expected), float(actual), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError):
            return False
    return str(expected) == str(actual)


def audit_sample(
    *,
    config_path: Path,
    proposal_dir: Path,
    coverage_dir: Path,
    outcome_dir: Path,
    per_stratum: int = 1,
) -> dict[str, Any]:
    if per_stratum <= 0:
        raise ValueError("per_stratum must be positive")
    _verify_packet(proposal_dir)
    _verify_packet(coverage_dir)
    _verify_packet(outcome_dir)
    proposal_manifest_path = proposal_dir / "proposal_ledger_manifest.json"
    outcome_manifest_path = outcome_dir / "outcome_manifest.json"
    outcome_path = outcome_dir / "conditional_outcomes.parquet"
    outcome_manifest = json.loads(outcome_manifest_path.read_text(encoding="utf-8"))
    if outcome_manifest.get("status") != "training_conditional_outcomes_with_coverage_dispositions":
        raise ValueError("outcome packet is not a complete training replay")
    if outcome_manifest["proposal_manifest_sha256"] != _sha256(proposal_manifest_path):
        raise ValueError("outcome packet references a different proposal manifest")
    if outcome_manifest["output_sha256"]["conditional_outcomes.parquet"] != _sha256(outcome_path):
        raise ValueError("outcome parquet does not match its manifest")
    for relative in SOURCE_FILES:
        if outcome_manifest["source_sha256"].get(relative) != _sha256(ROOT / relative):
            raise ValueError(f"outcome source changed since replay: {relative}")

    cfg = load_config(config_path=config_path)
    cfg.features.entry_ideas.enabled = True
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    proposals = pd.read_parquet(proposal_dir / "candidate_proposals.parquet")
    outcomes = pd.read_parquet(outcome_path)
    proposal_lookup = {str(row["proposal_id"]): row for row in proposals.to_dict(orient="records")}
    proposal_types = proposals[["proposal_id", "entry_type"]].copy()
    sampled = outcomes.merge(proposal_types, on="proposal_id", how="left", validate="many_to_one")
    if sampled["entry_type"].isna().any():
        raise ValueError("outcome sample contains an unknown proposal ID")
    sample_rows = (
        sampled.sort_values("outcome_id", kind="stable")
        .groupby(["entry_type", "status", "unresolved_reason"], dropna=False, sort=True)
        .head(per_stratum)
        .sort_values(["entry_type", "status", "unresolved_reason", "outcome_id"], kind="stable")
    )

    coverage = CandidateQuoteCoverage.from_csv(
        coverage_dir / "minute_quote_coverage.csv", timezone=str(cfg.data.tz)
    )
    symbol = str(cfg.data.primary)
    tickbook = build_tick_books(cfg, symbols=[symbol], datasets=["training"]).get(symbol)
    if tickbook is None or tickbook.content_sha256() != outcome_manifest["tickbook_sha256"]:
        raise ValueError("sample replay TickBook does not match the outcome packet")
    cutoff = (
        (pd.Timestamp(str(cfg.data.split.train_end)) + pd.Timedelta(days=1))
        .tz_localize(str(cfg.data.tz))
        .tz_convert("UTC")
    )
    execution = outcome_manifest["execution_parameters"]
    mismatches: list[dict[str, str]] = []
    strata_counts: dict[str, int] = {}
    for row_values in sample_rows.itertuples(index=False, name=None):
        row = dict(zip(sample_rows.columns, row_values, strict=True))
        proposal_record = proposal_lookup[str(row["proposal_id"])]
        proposal = _proposal({str(key): value for key, value in proposal_record.items()})
        if proposal.eligible_action_fill_time is None or proposal.session_close_time is None:
            raise ValueError(f"proposal {proposal.proposal_id} is missing replay timestamps")
        start = pd.Timestamp(proposal.eligible_action_fill_time)
        session_close = pd.Timestamp(proposal.session_close_time)
        coverage_cutoff = coverage.first_incomplete_minute(start, min(cutoff, session_close))
        expected = replay_candidate_proposal(
            proposal,
            tickbook,
            stop_choice=str(row["stop_choice"]),
            target_choice=str(row["target_choice"]),
            observed_until=cutoff,
            exit_horizon=session_close,
            max_quote_wait_ms=int(execution["max_quote_wait_ms"]),
            randomized_fill_latency_ms=float(execution["randomized_fill_latency_ms"]),
            limit_require_trade_through=bool(execution.get("limit_require_trade_through", False)),
            tick_fill_slippage_points=float(execution["tick_fill_slippage_points"]),
            commission_per_lot=float(execution["commission_per_lot"]),
            contract_size=float(execution["contract_size"]),
            execution_seed=int(execution["execution_seed"]),
            quote_coverage_cutoff=coverage_cutoff,
        ).to_record()
        actual = row
        stratum = "|".join(
            str(value) for value in (row["entry_type"], row["status"], row["unresolved_reason"])
        )
        strata_counts[stratum] = strata_counts.get(stratum, 0) + 1
        for field, expected_value in expected.items():
            if not _matches(expected_value, actual[field]):
                mismatches.append(
                    {
                        "outcome_id": str(row["outcome_id"]),
                        "field": field,
                        "expected": str(expected_value),
                        "actual": str(actual[field]),
                    }
                )

    report: dict[str, Any] = {
        "schema_version": "candidate-outcome-replay-sample-verification-v1",
        "status": "verified_stratified_replay_sample" if not mismatches else "failed",
        "method": "deterministic replay sample through the versioned production execution function",
        "per_stratum_limit": per_stratum,
        "sampled_rows": int(len(sample_rows)),
        "exact_rows_matched": int(len(sample_rows)) if not mismatches else None,
        "mismatches": mismatches,
        "strata_counts": strata_counts,
        "proposal_manifest_sha256": _sha256(proposal_manifest_path),
        "outcome_manifest_sha256": _sha256(outcome_manifest_path),
        "outcome_parquet_sha256": _sha256(outcome_path),
        "tickbook_sha256": tickbook.content_sha256(),
        "source_sha256": {relative: _sha256(ROOT / relative) for relative in SOURCE_FILES},
        "script_sha256": _sha256(Path(__file__).resolve()),
    }
    report_path = outcome_dir / REPORT_NAME
    temporary_path = report_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_path.replace(report_path)
    if mismatches:
        raise ValueError(f"{len(mismatches)} sampled outcome fields did not reproduce")

    checksums = {
        line.split(maxsplit=1)[1].strip(): line.split(maxsplit=1)[0]
        for line in (outcome_dir / "OUTPUT_SHA256SUMS").read_text(encoding="utf-8").splitlines()
    }
    checksums[REPORT_NAME] = _sha256(report_path)
    (outcome_dir / "OUTPUT_SHA256SUMS").write_text(
        "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums)),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--coverage-dir", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--outcome-dir", type=Path, default=DEFAULT_OUTCOMES)
    parser.add_argument("--per-stratum", type=int, default=1)
    args = parser.parse_args()
    paths = [
        value if value.is_absolute() else ROOT / value
        for value in (args.config, args.proposal_dir, args.coverage_dir, args.outcome_dir)
    ]
    report = audit_sample(
        config_path=paths[0],
        proposal_dir=paths[1],
        coverage_dir=paths[2],
        outcome_dir=paths[3],
        per_stratum=args.per_stratum,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
