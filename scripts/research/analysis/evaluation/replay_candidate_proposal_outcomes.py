#!/usr/bin/env python3
"""Build a training-only conditional outcome ledger for candidate proposals.

Each proposal is replayed independently for every permitted stop/target pair.
The result is conditional fixed-entry evidence; it does not replay a policy or
an account. Local quote-coverage gaps truncate the replay and remain explicit
unresolved-data outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from omegaconf import OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from evaluation.candidate_execution import replay_candidate_proposal
from evaluation.candidate_proposals import CandidateProposal
from evaluation.candidate_quote_coverage import CandidateQuoteCoverage
from market_data.loading import build_tick_books

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_PROPOSALS = ROOT / "evidence/research/candidate_proposals"
DEFAULT_COVERAGE = ROOT / "evidence/research/tick_quote_coverage"
DEFAULT_OUTPUT = ROOT / "evidence/research/candidate_outcomes"
DATA_MANIFEST = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json"
)
OUTCOME_SOURCE_FILES = (
    "evaluation/candidate_execution.py",
    "evaluation/candidate_outcomes.py",
    "evaluation/candidate_proposals.py",
    "evaluation/candidate_quote_coverage.py",
    "market_data/loading/ticks.py",
    "scripts/research/analysis/evaluation/replay_candidate_proposal_outcomes.py",
    "trading/execution/quotes.py",
)


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
            raise ValueError(f"input packet checksum mismatch: {packet / name.strip()}")


def _decode_sequence(value: Any) -> tuple[Any, ...]:
    decoded = json.loads(value) if isinstance(value, str) else value
    return tuple(tuple(item) if isinstance(item, (list, tuple)) else item for item in decoded)


def _proposal(record: dict[str, Any]) -> CandidateProposal:
    prepared = dict(record)
    for column in (
        "source_zone_low",
        "source_zone_high",
        "atr_scale",
        "spread_at_proposal",
        "latency_estimate_ms",
        "estimated_round_trip_cost_points",
    ):
        value = prepared.get(column)
        if value is not None and pd.isna(value):
            prepared[column] = None
    for column in (
        "permissible_stop_choices",
        "permissible_target_choices",
        "evidence_quality_flags",
        "causal_feature_availability",
    ):
        prepared[column] = _decode_sequence(prepared[column])
    return CandidateProposal(**prepared)


def _write_records(
    writer: pq.ParquetWriter | None, path: Path, records: list[dict[str, Any]]
) -> pq.ParquetWriter:
    table = pa.Table.from_pandas(pd.DataFrame.from_records(records), preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(path, table.schema, compression="zstd")
    elif not writer.schema.equals(table.schema, check_metadata=False):
        table = table.cast(writer.schema.remove_metadata())
    writer.write_table(table)
    return writer


def build_outcome_ledger(
    *,
    config_path: Path,
    proposal_dir: Path,
    coverage_dir: Path,
    output_dir: Path,
    max_proposals: int | None = None,
    batch_proposals: int = 128,
) -> dict[str, Any]:
    if batch_proposals <= 0:
        raise ValueError("batch_proposals must be positive")
    _verify_packet(proposal_dir)
    _verify_packet(coverage_dir)
    cfg = load_config(config_path=config_path)
    # Reproduce the proposal builder's resolved research configuration.
    cfg.features.entry_ideas.enabled = True
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    resolved_config = OmegaConf.to_yaml(cfg, resolve=True)
    proposal_manifest = json.loads(
        (proposal_dir / "proposal_ledger_manifest.json").read_text(encoding="utf-8")
    )
    resolved_config_sha256 = hashlib.sha256(resolved_config.encode()).hexdigest()
    proposal_config_sha256 = str(proposal_manifest["resolved_config_sha256"])
    config_relationship = (
        "same_resolved_config"
        if resolved_config_sha256 == proposal_config_sha256
        else "proposal_artifacts_replayed_under_current_execution_config"
    )
    proposals_path = proposal_dir / "candidate_proposals.parquet"
    proposals = pd.read_parquet(proposals_path)
    if max_proposals is not None:
        if max_proposals <= 0:
            raise ValueError("max_proposals must be positive")
        proposals = proposals.head(max_proposals).copy()
    quote_coverage = CandidateQuoteCoverage.from_csv(
        coverage_dir / "minute_quote_coverage.csv", timezone=str(cfg.data.tz)
    )
    primary_symbol = str(cfg.data.primary)
    tickbook = build_tick_books(
        cfg,
        symbols=[primary_symbol],
        datasets=["training"],
    ).get(primary_symbol)
    if tickbook is None:
        raise ValueError("candidate outcome replay requires the configured training TickBook")
    if tickbook.content_sha256() != proposal_manifest["tickbook_sha256"]:
        raise ValueError("replay TickBook does not match the proposal packet identity")

    cutoff_local = pd.Timestamp(str(cfg.data.split.train_end)) + pd.Timedelta(days=1)
    training_cutoff = cutoff_local.tz_localize(str(cfg.data.tz)).tz_convert("UTC")
    commission = float(cfg.costs.commission_per_lot)
    contract_size = float(cfg.account.contract_size)
    slippage = float(cfg.costs.slippage_points)
    max_quote_wait_ms = int(cfg.execution.max_tick_quote_wait_ms)
    randomized_latency_ms = float(cfg.execution.randomized_fill_latency_ms)
    limit_require_trade_through = bool(cfg.execution.limit_order_require_trade_through)
    execution_seed = 0

    output_dir.mkdir(parents=True, exist_ok=False)
    temporary_path = output_dir / ".conditional_outcomes.parquet.tmp"
    output_path = output_dir / "conditional_outcomes.parquet"
    writer: pq.ParquetWriter | None = None
    status_counts: Counter[str] = Counter()
    outcome_count = 0
    batch: list[dict[str, Any]] = []
    processed = 0
    try:
        for record in proposals.to_dict(orient="records"):
            proposal = _proposal({str(key): value for key, value in record.items()})
            if proposal.eligible_action_fill_time is None or proposal.session_close_time is None:
                raise ValueError(f"proposal {proposal.proposal_id} is missing replay timestamps")
            start = pd.Timestamp(proposal.eligible_action_fill_time)
            session_close = pd.Timestamp(proposal.session_close_time)
            replay_end = min(training_cutoff, session_close)
            coverage_cutoff = quote_coverage.first_incomplete_minute(start, replay_end)
            for stop_choice, _stop_price in proposal.permissible_stop_choices:
                for target_choice, _target_price in proposal.permissible_target_choices:
                    outcome = replay_candidate_proposal(
                        proposal,
                        tickbook,
                        stop_choice=stop_choice,
                        target_choice=target_choice,
                        observed_until=training_cutoff,
                        exit_horizon=session_close,
                        max_quote_wait_ms=max_quote_wait_ms,
                        randomized_fill_latency_ms=randomized_latency_ms,
                        limit_require_trade_through=limit_require_trade_through,
                        tick_fill_slippage_points=slippage,
                        commission_per_lot=commission,
                        contract_size=contract_size,
                        execution_seed=execution_seed,
                        quote_coverage_cutoff=coverage_cutoff,
                    )
                    batch.append(outcome.to_record())
                    status_counts[outcome.status] += 1
                    outcome_count += 1
            processed += 1
            if processed % batch_proposals == 0 or processed == len(proposals):
                writer = _write_records(writer, temporary_path, batch)
                batch.clear()
                print(
                    f"proposals={processed}/{len(proposals)} outcomes={outcome_count} "
                    f"statuses={dict(sorted(status_counts.items()))}",
                    flush=True,
                )
    finally:
        if writer is not None:
            writer.close()
    if processed == 0 or not temporary_path.exists():
        raise ValueError("no candidate proposals were replayed")
    os.replace(temporary_path, output_path)

    manifest: dict[str, Any] = {
        "schema_version": "training-candidate-conditional-outcomes-v1",
        "status": (
            "pilot_incomplete_not_evidence"
            if max_proposals is not None
            else "training_conditional_outcomes_with_coverage_dispositions"
        ),
        "estimand": "conditional_fixed_entry",
        "policy_value_claim": False,
        "account_state_evaluated": False,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "config": str(config_path.resolve().relative_to(ROOT)),
        "resolved_config_sha256": resolved_config_sha256,
        "proposal_resolved_config_sha256": proposal_config_sha256,
        "config_relationship": config_relationship,
        "proposal_manifest_sha256": _sha256(proposal_dir / "proposal_ledger_manifest.json"),
        "local_data_manifest_sha256": proposal_manifest["local_data_manifest_sha256"],
        "proposal_parquet_sha256": _sha256(proposals_path),
        "quote_coverage_manifest_sha256": _sha256(coverage_dir / "coverage_manifest.json"),
        "quote_coverage_rule": json.loads(
            (coverage_dir / "coverage_manifest.json").read_text(encoding="utf-8")
        )["coverage_rule"],
        "tickbook_sha256": tickbook.content_sha256(),
        "training_cutoff_utc_exclusive": training_cutoff.isoformat(),
        "execution_parameters": {
            "max_quote_wait_ms": max_quote_wait_ms,
            "randomized_fill_latency_ms": randomized_latency_ms,
            "randomized_fill_latency_scope": "entry_requests_only",
            "protective_exit_execution": "server_side_attached_first_trigger_quote",
            "protective_exit_network_latency_ms": 0.0,
            "limit_require_trade_through": limit_require_trade_through,
            "limit_fill_assumption": (
                "strict_trade_through" if limit_require_trade_through else "exact_touch"
            ),
            "tick_fill_slippage_points": slippage,
            "commission_per_lot": commission,
            "contract_size": contract_size,
            "execution_seed": execution_seed,
        },
        "proposal_rows_replayed": processed,
        "conditional_outcome_rows": outcome_count,
        "outcome_status_counts": dict(sorted(status_counts.items())),
        "source_sha256": {relative: _sha256(ROOT / relative) for relative in OUTCOME_SOURCE_FILES},
        "output_sha256": {output_path.name: _sha256(output_path)},
    }
    manifest_path = output_dir / "outcome_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        "# Candidate conditional outcomes\n\n"
        "This training-only packet replays each statically eligible candidate proposal independently for every permitted stop/target pair. It is a conditional fixed-entry estimand and excludes account state, portfolio contention, policy action, and closed-loop policy value. Incomplete local quote coverage truncates the replay; those records are unresolved rather than labeled as no-touch or no-exit. Administrative censoring at the training cutoff remains right-censored.\n\n"
        "Limit fills respect the submitted price bound and record the configured exact-touch or strict trade-through assumption in the execution parameters. Market slippage applies only to market entries. Fixed Stop Loss and Take Profit levels are treated as already attached server-side protective orders and execute on the first source-ordered triggering quote without a second EA/network latency draw.\n\n"
        "`outcome_manifest.json` identifies the proposal, coverage, config, TickBook, source, execution parameters, outcome counts, and output hash.\n",
        encoding="utf-8",
    )
    outputs = (output_path, manifest_path, readme_path)
    (output_dir / "OUTPUT_SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in outputs), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--coverage-dir", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-proposals", type=int)
    parser.add_argument("--batch-proposals", type=int, default=128)
    args = parser.parse_args()
    resolved = [
        value if value.is_absolute() else ROOT / value
        for value in (args.config, args.proposal_dir, args.coverage_dir, args.output_dir)
    ]
    build_outcome_ledger(
        config_path=resolved[0],
        proposal_dir=resolved[1],
        coverage_dir=resolved[2],
        output_dir=resolved[3],
        max_proposals=args.max_proposals,
        batch_proposals=args.batch_proposals,
    )


if __name__ == "__main__":
    main()
