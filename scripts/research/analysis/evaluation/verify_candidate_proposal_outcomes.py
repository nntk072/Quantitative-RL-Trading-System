#!/usr/bin/env python3
"""Verify packet identity, independent full-row replay, arithmetic, and a sample.

The array-level reference implementation independently recalculates every
outcome row under the recorded zero-latency contract. A stratified sample also
checks the production replay implementation as a differential control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf
from scripts.research.analysis.evaluation.candidate_outcome_reference import (
    independently_replay_outcomes,
)

from configuration.configuration_loader import load_config
from configuration.paths import repository_root
from evaluation.candidate_quote_coverage import CandidateQuoteCoverage
from market_data.loading import build_tick_books

ROOT = repository_root(__file__)
DEFAULT_CONFIG = ROOT / "config/research/trade_setup_mtf_reasoning_2m.yaml"
DEFAULT_PROPOSALS = ROOT / "evidence/research/candidate_proposals"
DEFAULT_COVERAGE = ROOT / "evidence/research/tick_quote_coverage"
DEFAULT_OUTCOMES = ROOT / "evidence/research/candidate_outcomes"
OUTCOME_SOURCE_FILES = {
    "evaluation/candidate_execution.py",
    "evaluation/candidate_outcomes.py",
    "evaluation/candidate_proposals.py",
    "evaluation/candidate_quote_coverage.py",
    "market_data/loading/ticks.py",
    "scripts/research/analysis/evaluation/replay_candidate_proposal_outcomes.py",
    "trading/execution/quotes.py",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Return row records with string keys for the parquet schema."""
    return [
        {str(key): value for key, value in record.items()} for record in frame.to_dict("records")
    ]


def _limit_fill_price_bound_audit(
    proposals: pd.DataFrame, outcomes: pd.DataFrame
) -> dict[str, Any]:
    """Independently verify that every known limit fill respects its submitted price."""
    limit_proposals = proposals.loc[
        proposals["entry_type"].astype(str).eq("limit"),
        ["proposal_id", "direction", "proposed_entry_price"],
    ]
    known_fills = outcomes.loc[outcomes["fill_price"].notna(), ["proposal_id", "fill_price"]].merge(
        limit_proposals, on="proposal_id", how="inner", validate="many_to_one"
    )
    fill_price = pd.to_numeric(known_fills["fill_price"], errors="coerce")
    limit_price = pd.to_numeric(known_fills["proposed_entry_price"], errors="coerce")
    direction = pd.to_numeric(known_fills["direction"], errors="coerce")
    violations = (direction.eq(1) & fill_price.gt(limit_price)) | (
        direction.eq(-1) & fill_price.lt(limit_price)
    )
    examples = known_fills.loc[violations, ["proposal_id", "fill_price", "proposed_entry_price"]]
    return {
        "known_limit_fills_checked": int(len(known_fills)),
        "price_bound_violations": int(violations.sum()),
        "examples": examples.head(5).to_dict(orient="records"),
    }


def _verify_packet(packet: Path) -> None:
    for line in (packet / "OUTPUT_SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        if _sha256(packet / name.strip()) != expected:
            raise ValueError(f"packet checksum mismatch: {packet / name.strip()}")


def _independently_recompute_resolved_values(
    proposals: pd.DataFrame,
    outcomes: pd.DataFrame,
    tick_times_ns: np.ndarray[Any, Any],
    bids: np.ndarray[Any, Any],
    asks: np.ndarray[Any, Any],
    *,
    tickbook_sha256: str,
    slippage_points: float,
    commission_per_lot: float,
    contract_size: float,
    limit_require_trade_through: bool = False,
    server_side_protective_orders: bool = False,
) -> dict[str, Any]:
    """Check every resolved fill against source quotes and independently recompute net R."""
    resolved = outcomes.loc[outcomes["status"].eq("filled_resolved")].copy()
    if resolved.empty:
        raise ValueError("independent arithmetic audit requires resolved outcomes")
    if not tick_times_ns.size or not (len(tick_times_ns) == len(bids) == len(asks)):
        raise ValueError("TickBook arrays have inconsistent lengths")
    proposal_direction: dict[str, int] = {}
    proposal_entry_type: dict[str, str] = {}
    proposal_entry_price: dict[str, float] = {}
    stop_prices: dict[tuple[str, str], float] = {}
    target_prices: dict[tuple[str, str], float] = {}
    for proposal_record in _records(proposals):
        proposal_id = str(proposal_record["proposal_id"])
        proposal_direction[proposal_id] = int(proposal_record["direction"])
        proposal_entry_type[proposal_id] = str(proposal_record["entry_type"])
        proposal_entry_price[proposal_id] = float(proposal_record["proposed_entry_price"])
        choices = proposal_record.get("permissible_stop_choices", [])
        if isinstance(choices, str):
            choices = json.loads(choices)
        if not isinstance(choices, list):
            raise ValueError(f"proposal {proposal_id} has invalid stop-choice data")
        for choice_record in choices:
            if not isinstance(choice_record, (list, tuple)) or len(choice_record) != 2:
                raise ValueError(f"proposal {proposal_id} has an invalid stop choice")
            choice, price = choice_record
            stop_prices[(proposal_id, str(choice))] = float(price)
        targets = proposal_record.get("permissible_target_choices", [])
        if isinstance(targets, str):
            targets = json.loads(targets)
        if not isinstance(targets, list):
            raise ValueError(f"proposal {proposal_id} has invalid target-choice data")
        for choice_record in targets:
            if not isinstance(choice_record, (list, tuple)) or len(choice_record) != 2:
                raise ValueError(f"proposal {proposal_id} has an invalid target choice")
            choice, price = choice_record
            target_prices[(proposal_id, str(choice))] = float(price)

    proposal_ids = resolved["proposal_id"].astype(str).to_numpy()
    directions = np.fromiter(
        (proposal_direction[value] for value in proposal_ids), dtype=np.int8, count=len(resolved)
    )
    entry_types = np.fromiter(
        (proposal_entry_type[value] for value in proposal_ids), dtype=object, count=len(resolved)
    )
    entry_prices = np.fromiter(
        (proposal_entry_price[value] for value in proposal_ids),
        dtype=np.float64,
        count=len(resolved),
    )
    stops = np.fromiter(
        (
            stop_prices[(proposal_id, str(choice))]
            for proposal_id, choice in zip(proposal_ids, resolved["stop_choice"], strict=True)
        ),
        dtype=np.float64,
        count=len(resolved),
    )
    targets = (
        np.fromiter(
            (
                target_prices[(proposal_id, str(choice))]
                for proposal_id, choice in zip(proposal_ids, resolved["target_choice"], strict=True)
            ),
            dtype=np.float64,
            count=len(resolved),
        )
        if "target_choice" in resolved
        else np.full(len(resolved), np.nan, dtype=np.float64)
    )
    fill_ns = (
        pd.to_datetime(resolved["fill_time"], format="ISO8601", utc=True).astype("int64").to_numpy()
    )
    exit_ns = (
        pd.to_datetime(resolved["exit_time"], format="ISO8601", utc=True).astype("int64").to_numpy()
    )
    fill_ix = np.searchsorted(tick_times_ns, fill_ns, side="left")
    exit_ix = np.searchsorted(tick_times_ns, exit_ns, side="left")
    fill_found = (fill_ix < len(tick_times_ns)) & (
        tick_times_ns[np.minimum(fill_ix, len(tick_times_ns) - 1)] == fill_ns
    )
    exit_found = (exit_ix < len(tick_times_ns)) & (
        tick_times_ns[np.minimum(exit_ix, len(tick_times_ns) - 1)] == exit_ns
    )
    stored_fill = pd.to_numeric(resolved["fill_price"], errors="raise").to_numpy(dtype=np.float64)
    stored_exit = pd.to_numeric(resolved["exit_price"], errors="raise").to_numpy(dtype=np.float64)
    expected_fill = np.full(len(resolved), np.nan, dtype=np.float64)
    selected_fill_ix = fill_ix.copy()
    expected_exit = np.full(len(resolved), np.nan, dtype=np.float64)
    selected_exit_ix = exit_ix.copy()
    exit_trigger_found = exit_found.copy()
    valid_fill = fill_found
    valid_exit = exit_found
    long_fill = valid_fill & (directions == 1)
    short_fill = valid_fill & (directions == -1)
    long_exit = valid_exit & (directions == 1)
    short_exit = valid_exit & (directions == -1)
    expected_fill[long_fill] = asks[fill_ix[long_fill]] + slippage_points
    expected_fill[short_fill] = bids[fill_ix[short_fill]] - slippage_points
    for index in np.flatnonzero(fill_found & (entry_types == "limit")):
        tie_end = int(np.searchsorted(tick_times_ns, fill_ns[index], side="right"))
        tie_rows = np.arange(int(fill_ix[index]), tie_end)
        if directions[index] == 1:
            quote_prices = asks[tie_rows]
            executable = (
                quote_prices < entry_prices[index]
                if limit_require_trade_through
                else quote_prices <= entry_prices[index]
            )
            executable_prices = np.minimum(quote_prices, entry_prices[index])
        else:
            quote_prices = bids[tie_rows]
            executable = (
                quote_prices > entry_prices[index]
                if limit_require_trade_through
                else quote_prices >= entry_prices[index]
            )
            executable_prices = np.maximum(quote_prices, entry_prices[index])
        qualifying = np.flatnonzero(executable)
        if qualifying.size:
            selected = int(qualifying[0])
            selected_fill_ix[index] = tie_rows[selected]
            expected_fill[index] = executable_prices[selected]
    if server_side_protective_orders:
        exit_reasons = (
            resolved["exit_reason"].astype(str).to_numpy()
            if "exit_reason" in resolved
            else np.full(len(resolved), "", dtype=object)
        )
        for index in np.flatnonzero(exit_found & np.isin(exit_reasons, ("sl", "tp"))):
            tie_end = int(np.searchsorted(tick_times_ns, exit_ns[index], side="right"))
            tie_rows = np.arange(int(exit_ix[index]), tie_end)
            side_prices = bids[tie_rows] if directions[index] == 1 else asks[tie_rows]
            if exit_reasons[index] == "sl":
                hit = (
                    side_prices <= stops[index]
                    if directions[index] == 1
                    else side_prices >= stops[index]
                )
            else:
                hit = (
                    side_prices >= targets[index]
                    if directions[index] == 1
                    else side_prices <= targets[index]
                )
            qualifying = np.flatnonzero(hit)
            if qualifying.size:
                selected_exit_ix[index] = tie_rows[int(qualifying[0])]
            else:
                exit_trigger_found[index] = False
    long_exit = exit_trigger_found & (directions == 1)
    short_exit = exit_trigger_found & (directions == -1)
    expected_exit[long_exit] = bids[selected_exit_ix[long_exit]] - slippage_points
    expected_exit[short_exit] = asks[selected_exit_ix[short_exit]] + slippage_points
    fill_match = (
        valid_fill
        & np.isfinite(expected_fill)
        & np.isclose(stored_fill, expected_fill, rtol=1e-12, atol=1e-12)
    )
    exit_match = exit_trigger_found & np.isclose(stored_exit, expected_exit, rtol=1e-12, atol=1e-12)
    risk = np.abs(stored_fill - stops)
    arithmetic_valid = risk > 0.0
    expected_net_r = np.full(len(resolved), np.nan, dtype=np.float64)
    arithmetic_valid &= np.isfinite(risk)
    expected_net_r[arithmetic_valid] = directions[arithmetic_valid] * (
        stored_exit[arithmetic_valid] - stored_fill[arithmetic_valid]
    ) / risk[arithmetic_valid] - 2.0 * commission_per_lot / (contract_size * risk[arithmetic_valid])
    stored_net_r = pd.to_numeric(resolved["net_r"], errors="raise").to_numpy(dtype=np.float64)
    net_r_match = arithmetic_valid & np.isclose(
        stored_net_r, expected_net_r, rtol=1e-12, atol=1e-12
    )
    mismatch = ~(fill_match & exit_match & net_r_match)
    first_mismatches = resolved.loc[mismatch, "outcome_id"].astype(str).head(5).tolist()
    fill_mismatch_ix = np.flatnonzero(~fill_match)[:5]
    fill_mismatch_examples = []
    for index in fill_mismatch_ix:
        source_index = min(int(selected_fill_ix[index]), len(tick_times_ns) - 1)
        fill_mismatch_examples.append(
            {
                "outcome_id": str(resolved.iloc[index]["outcome_id"]),
                "entry_type": proposal_entry_type[proposal_ids[index]],
                "fill_time": str(resolved.iloc[index]["fill_time"]),
                "source_time": pd.Timestamp(
                    int(tick_times_ns[source_index]), unit="ns", tz="UTC"
                ).isoformat(),
                "source_event_at_fill_time": bool(fill_found[index]),
                "source_bid": float(bids[source_index]),
                "source_ask": float(asks[source_index]),
                "stored_fill_price": float(stored_fill[index]),
                "expected_fill_price": (
                    None if not np.isfinite(expected_fill[index]) else float(expected_fill[index])
                ),
            }
        )
    return {
        "status": "verified" if not mismatch.any() else "mismatch",
        "rows_checked": int(len(resolved)),
        "fill_source_quote_matches": int(fill_match.sum()),
        "exit_source_quote_matches": int(exit_match.sum()),
        "net_r_recalculations_match": int(net_r_match.sum()),
        "fill_source_quote_mismatches": int((~fill_match).sum()),
        "fill_event_not_found_rows": int((~fill_found).sum()),
        "fill_price_mismatch_rows": int(
            (fill_found & ~np.isclose(stored_fill, expected_fill, rtol=1e-12, atol=1e-12)).sum()
        ),
        "exit_source_quote_mismatches": int((~exit_match).sum()),
        "net_r_recalculation_mismatches": int((~net_r_match).sum()),
        "mismatch_rows": int(mismatch.sum()),
        "first_mismatch_outcome_ids": first_mismatches,
        "first_fill_mismatch_examples": fill_mismatch_examples,
        "tickbook_sha256": tickbook_sha256,
        "scope": "reported resolved event times; source quote prices and net R only",
    }


def verify_outcome_packet(
    *, config_path: Path, proposal_dir: Path, coverage_dir: Path, outcome_dir: Path
) -> dict[str, Any]:
    _verify_packet(proposal_dir)
    _verify_packet(coverage_dir)
    _verify_packet(outcome_dir)
    proposal_manifest = json.loads(
        (proposal_dir / "proposal_ledger_manifest.json").read_text(encoding="utf-8")
    )
    outcome_manifest = json.loads(
        (outcome_dir / "outcome_manifest.json").read_text(encoding="utf-8")
    )
    proposal_config_hash = str(proposal_manifest["resolved_config_sha256"])
    replay_config_hash = str(outcome_manifest["resolved_config_sha256"])
    expected_config_relationship = (
        "same_resolved_config"
        if replay_config_hash == proposal_config_hash
        else "proposal_artifacts_replayed_under_current_execution_config"
    )
    if (
        outcome_manifest.get("proposal_resolved_config_sha256") != proposal_config_hash
        or outcome_manifest.get("config_relationship") != expected_config_relationship
    ):
        raise ValueError("outcome packet does not transparently identify its config relationship")
    if outcome_manifest["status"] != "training_conditional_outcomes_with_coverage_dispositions":
        raise ValueError("outcome packet is a pilot or has an unsupported status")
    if outcome_manifest["proposal_manifest_sha256"] != _sha256(
        proposal_dir / "proposal_ledger_manifest.json"
    ):
        raise ValueError("outcome packet references a different proposal manifest")
    proposal_path = proposal_dir / "candidate_proposals.parquet"
    if outcome_manifest["proposal_parquet_sha256"] != _sha256(proposal_path):
        raise ValueError("outcome packet references a different proposal table")
    if outcome_manifest["quote_coverage_manifest_sha256"] != _sha256(
        coverage_dir / "coverage_manifest.json"
    ):
        raise ValueError("outcome packet references a different quote-coverage manifest")
    proposal_manifest = json.loads(
        (proposal_dir / "proposal_ledger_manifest.json").read_text(encoding="utf-8")
    )
    if outcome_manifest["tickbook_sha256"] != proposal_manifest["tickbook_sha256"]:
        raise ValueError("outcome TickBook identity differs from the proposal packet")

    cfg = load_config(config_path=config_path)
    cfg.features.entry_ideas.enabled = True
    cfg.data.cache_dir = str(ROOT / "cache/trade_setup_opportunity_census")
    resolved_config_sha256 = hashlib.sha256(
        OmegaConf.to_yaml(cfg, resolve=True).encode()
    ).hexdigest()
    if outcome_manifest["resolved_config_sha256"] != resolved_config_sha256:
        raise ValueError("outcome packet resolved config hash does not verify")
    if (
        outcome_manifest["local_data_manifest_sha256"]
        != proposal_manifest["local_data_manifest_sha256"]
    ):
        raise ValueError("outcome packet local-data manifest differs from proposal input")
    cutoff = (
        (pd.Timestamp(str(cfg.data.split.train_end)) + pd.Timedelta(days=1))
        .tz_localize(str(cfg.data.tz))
        .tz_convert("UTC")
    )
    if outcome_manifest["training_cutoff_utc_exclusive"] != cutoff.isoformat():
        raise ValueError("outcome packet uses an unexpected training cutoff")

    outcome_path = outcome_dir / "conditional_outcomes.parquet"
    proposals = pd.read_parquet(proposal_path)
    outcomes = pd.read_parquet(outcome_path)
    limit_fill_price_audit = _limit_fill_price_bound_audit(proposals, outcomes)
    if limit_fill_price_audit["price_bound_violations"]:
        raise ValueError(
            "limit fill price exceeds the submitted price bound: "
            f"{limit_fill_price_audit['examples']}"
        )
    replay_comparison_path = outcome_dir / "full_replay_value_comparison.json"
    replay_comparison_artifact: str | None = None
    replay_comparison_rows: int | None = None
    if replay_comparison_path.is_file():
        replay_comparison = json.loads(replay_comparison_path.read_text(encoding="utf-8"))
        if (
            replay_comparison.get("schema_version")
            != "candidate-outcome-full-replay-value-comparison-v1"
            or replay_comparison.get("status") != "all_rows_exactly_equal"
            or replay_comparison.get("first_mismatch") is not None
            or replay_comparison.get("reference_sha256") != _sha256(outcome_path)
            or replay_comparison.get("reference_rows") != len(outcomes)
            or replay_comparison.get("replay_rows") != len(outcomes)
            or replay_comparison.get("rows_compared") != len(outcomes)
        ):
            raise ValueError("full replay value comparison does not match the canonical packet")
        replay_comparison_artifact = _sha256(replay_comparison_path)
        replay_comparison_rows = int(replay_comparison["rows_compared"])
    disposition_summary_path = outcome_dir / "outcome_disposition_summary.json"
    replay_sample_path = outcome_dir / "outcome_replay_sample_verification.json"
    disposition_outputs: list[Path] = []
    disposition_artifacts: dict[str, str] = {}
    if disposition_summary_path.is_file():
        disposition_summary = json.loads(disposition_summary_path.read_text(encoding="utf-8"))
        plot_source = (
            ROOT / "scripts/research/analysis/evaluation/plot_candidate_outcome_coverage.py"
        )
        if disposition_summary["plot_script_sha256"] != _sha256(plot_source):
            raise ValueError("candidate outcome coverage plot source hash does not verify")
        for name, expected_hash in disposition_summary["output_sha256"].items():
            artifact_path = outcome_dir / name
            if _sha256(artifact_path) != expected_hash:
                raise ValueError(f"candidate outcome coverage output hash does not verify: {name}")
            disposition_outputs.append(artifact_path)
            disposition_artifacts[name] = expected_hash
        disposition_artifacts["outcome_disposition_summary.json"] = _sha256(
            disposition_summary_path
        )
    replay_sample_artifact: str | None = None
    replay_sample_method: str | None = None
    if replay_sample_path.is_file():
        replay_sample = json.loads(replay_sample_path.read_text(encoding="utf-8"))
        replay_script = (
            ROOT / "scripts/research/analysis/evaluation/audit_candidate_outcome_replay_sample.py"
        )
        if replay_sample.get("status") != "verified_stratified_replay_sample":
            raise ValueError("candidate outcome stratified replay sample did not pass")
        if replay_sample.get("script_sha256") != _sha256(replay_script):
            raise ValueError("candidate outcome replay sample source hash does not verify")
        if replay_sample.get("outcome_manifest_sha256") != _sha256(
            outcome_dir / "outcome_manifest.json"
        ) or replay_sample.get("outcome_parquet_sha256") != _sha256(outcome_path):
            raise ValueError("candidate outcome replay sample references different packet inputs")
        if (
            replay_sample.get("proposal_manifest_sha256")
            != _sha256(proposal_dir / "proposal_ledger_manifest.json")
            or replay_sample.get("tickbook_sha256") != outcome_manifest["tickbook_sha256"]
        ):
            raise ValueError(
                "candidate outcome replay sample has different proposal or TickBook input"
            )
        if replay_sample.get("source_sha256") != outcome_manifest["source_sha256"]:
            raise ValueError(
                "candidate outcome replay sample source inventory differs from the full run"
            )
        if (
            int(replay_sample.get("sampled_rows", 0)) <= 0
            or replay_sample.get("sampled_rows") != replay_sample.get("exact_rows_matched")
            or replay_sample.get("mismatches")
        ):
            raise ValueError(
                "candidate outcome replay sample does not contain exact passing matches"
            )
        replay_sample_artifact = _sha256(replay_sample_path)
        replay_sample_method = str(replay_sample.get("method", "unspecified"))
    coverage = CandidateQuoteCoverage.from_csv(
        coverage_dir / "minute_quote_coverage.csv", timezone=str(cfg.data.tz)
    )
    allowed: dict[str, tuple[set[str], set[str]]] = {}
    expected_rows = 0
    proposal_sessions: dict[str, tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]] = {}
    replay_coverage_cutoffs: dict[str, pd.Timestamp | None] = {}
    for row in proposals.to_dict(orient="records"):
        proposal_id = str(row["proposal_id"])
        stops = json.loads(row["permissible_stop_choices"])
        targets = json.loads(row["permissible_target_choices"])
        allowed[proposal_id] = (
            {str(choice[0]) for choice in stops},
            {str(choice[0]) for choice in targets},
        )
        expected_rows += len(stops) * len(targets)
        proposal_sessions[proposal_id] = (
            pd.Timestamp(row["eligible_action_fill_time"]),
            pd.Timestamp(row["expires_at"]),
            pd.Timestamp(row["session_close_time"]),
        )
        replay_coverage_cutoffs[proposal_id] = coverage.first_incomplete_minute(
            proposal_sessions[proposal_id][0], min(cutoff, proposal_sessions[proposal_id][2])
        )
    if len(outcomes) != expected_rows:
        raise ValueError(f"outcome row count {len(outcomes)} != expected {expected_rows}")
    if outcomes["outcome_id"].isna().any() or not outcomes["outcome_id"].is_unique:
        raise ValueError("outcome IDs must be present and unique")
    key_columns = ["proposal_id", "stop_choice", "target_choice"]
    if outcomes.duplicated(key_columns).any():
        raise ValueError("proposal/bracket outcome keys must be unique")
    if set(outcomes["proposal_id"].astype(str)) != set(allowed):
        raise ValueError("outcome rows do not cover exactly the proposal IDs")
    expected_by_proposal = pd.Series(
        {
            proposal_id: len(stops) * len(targets)
            for proposal_id, (stops, targets) in allowed.items()
        },
        dtype="int64",
    )
    actual_by_proposal = outcomes.groupby("proposal_id", sort=False).size()
    actual_by_proposal.index = actual_by_proposal.index.astype(str)
    if not expected_by_proposal.sort_index().equals(actual_by_proposal.sort_index()):
        raise ValueError("per-proposal outcome counts do not match the permitted bracket grid")

    status_counts = Counter(outcomes["status"].astype(str))
    unresolved_reason_counts = Counter(
        outcomes.loc[outcomes["status"].eq("unresolved_data"), "unresolved_reason"]
        .fillna("missing_reason")
        .astype(str)
    )
    if int(outcome_manifest["proposal_rows_replayed"]) != len(proposals):
        raise ValueError("outcome manifest proposal count does not match proposal packet")
    if int(outcome_manifest["conditional_outcome_rows"]) != len(outcomes):
        raise ValueError("outcome manifest row count does not match outcome parquet")
    if dict(sorted(status_counts.items())) != outcome_manifest["outcome_status_counts"]:
        raise ValueError("outcome manifest status counts do not match parquet")
    if outcome_manifest["output_sha256"].get("conditional_outcomes.parquet") != _sha256(
        outcome_path
    ):
        raise ValueError("outcome manifest parquet hash does not verify")
    if set(outcome_manifest["source_sha256"]) != OUTCOME_SOURCE_FILES:
        raise ValueError("outcome manifest source inventory is incomplete or unexpected")
    for relative, expected_hash in outcome_manifest["source_sha256"].items():
        if _sha256(ROOT / relative) != expected_hash:
            raise ValueError(f"outcome source hash mismatch: {relative}")
    record_violations: list[str] = []
    allowed_statuses = {
        "filled_resolved",
        "unfilled_expired",
        "censored_order_horizon",
        "censored_exit_horizon",
        "unresolved_data",
    }
    if set(status_counts).difference(allowed_statuses):
        record_violations.append("unsupported outcome status")
    if set(outcomes["schema_version"].astype(str)) != {"candidate-conditional-outcome-v2"}:
        record_violations.append("unexpected outcome schema version")
    if set(outcomes["estimand"].astype(str)) != {"conditional_fixed_entry"}:
        record_violations.append("unexpected outcome estimand")
    for outcome_record in _records(outcomes):
        proposal_id = str(outcome_record["proposal_id"])
        stops, targets = allowed.get(proposal_id, (set(), set()))
        stop_choice = str(outcome_record["stop_choice"])
        target_choice = str(outcome_record["target_choice"])
        schema_version = str(outcome_record["schema_version"])
        if stop_choice not in stops or target_choice not in targets:
            record_violations.append("outcome refers to an unpermitted bracket choice")
            break
        identity = {
            "proposal_id": proposal_id,
            "stop_choice": stop_choice,
            "target_choice": target_choice,
            "schema_version": schema_version,
        }
        expected_id = (
            "co2-"
            + hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:24]
        )
        if str(outcome_record["outcome_id"]) != expected_id:
            record_violations.append("outcome ID does not match its semantic key")
            break
    resolved = outcomes["status"].eq("filled_resolved")
    no_return = outcomes["status"].ne("filled_resolved")
    net_r = pd.to_numeric(outcomes["net_r"], errors="coerce")
    if net_r[resolved].isna().any() or not np.isfinite(net_r[resolved].to_numpy()).all():
        record_violations.append("resolved rows must have finite net R")
    if net_r[no_return].notna().any():
        record_violations.append("non-resolved rows must not have return labels")
    if (
        outcomes.loc[
            resolved, ["fill_time", "fill_price", "exit_time", "exit_price", "exit_reason"]
        ]
        .isna()
        .any()
        .any()
    ):
        record_violations.append("resolved rows require complete fill and exit fields")
    for field in ("exit_time", "exit_price", "exit_reason"):
        if outcomes.loc[no_return, field].notna().any():
            record_violations.append(f"non-resolved rows carry {field}")
    no_fill_status = outcomes["status"].isin({"unfilled_expired", "censored_order_horizon"})
    if outcomes.loc[no_fill_status, ["fill_time", "fill_price"]].notna().any().any():
        record_violations.append("unfilled or order-censored rows carry fill metadata")
    if outcomes.loc[outcomes["status"].eq("unresolved_data"), "unresolved_reason"].isna().any():
        record_violations.append("unresolved rows require an explicit reason")
    if record_violations:
        raise ValueError("; ".join(sorted(set(record_violations))))

    fill_times = pd.to_datetime(outcomes["fill_time"], format="ISO8601", utc=True, errors="coerce")
    exit_times = pd.to_datetime(outcomes["exit_time"], format="ISO8601", utc=True, errors="coerce")
    evaluated_times = pd.to_datetime(
        outcomes["evaluated_until"], format="ISO8601", utc=True, errors="raise"
    )
    if (fill_times.notna() & (fill_times > cutoff)).any():
        raise ValueError("an outcome fill occurs after the training cutoff")
    if (exit_times.notna() & (exit_times > cutoff)).any():
        raise ValueError("an outcome exit occurs after the training cutoff")
    if (evaluated_times > cutoff).any():
        raise ValueError("an outcome observation exceeds the training cutoff")
    chronology = fill_times.notna() & exit_times.notna() & (exit_times < fill_times)
    if chronology.any():
        raise ValueError("an outcome exit precedes its fill")

    session_close_exits = outcomes.loc[
        resolved & outcomes["exit_reason"].eq("session_close"), "exit_time"
    ]
    for value in session_close_exits:
        close_minute = pd.Timestamp(value).floor("min")
        if (
            coverage.first_incomplete_minute(close_minute, close_minute + pd.Timedelta(minutes=1))
            is not None
        ):
            raise ValueError("session-close exit uses a minute with incomplete quote coverage")

    gap_dispositions: Counter[str] = Counter()
    unfilled_proposal_ids = set(
        outcomes.loc[outcomes["status"].eq("unfilled_expired"), "proposal_id"].astype(str)
    )
    for proposal_record in _records(proposals):
        proposal_id = str(proposal_record["proposal_id"])
        action_start, expiry, session_close = proposal_sessions[proposal_id]
        order_end = min(expiry, session_close, cutoff)
        order_gap = coverage.first_incomplete_minute(action_start, order_end)
        if order_gap is None:
            gap_dispositions["order_life_quote_complete"] += 1
        else:
            gap_dispositions["order_life_quote_incomplete"] += 1
        if proposal_id in unfilled_proposal_ids and order_gap is not None:
            raise ValueError("unfilled-expired outcome has an incomplete order interval")

    symbol = str(cfg.data.primary)
    tickbook = build_tick_books(cfg, symbols=[symbol], datasets=["training"]).get(symbol)
    if tickbook is None or tickbook.content_sha256() != outcome_manifest["tickbook_sha256"]:
        raise ValueError("independent arithmetic audit TickBook does not match the outcome packet")
    execution = outcome_manifest["execution_parameters"]
    independent_arithmetic = _independently_recompute_resolved_values(
        proposals,
        outcomes,
        tickbook._ts,
        tickbook._bid,
        tickbook._ask,
        tickbook_sha256=tickbook.content_sha256(),
        slippage_points=float(execution["tick_fill_slippage_points"]),
        commission_per_lot=float(execution["commission_per_lot"]),
        contract_size=float(execution["contract_size"]),
        limit_require_trade_through=bool(execution.get("limit_require_trade_through", False)),
        server_side_protective_orders=(
            execution.get("protective_exit_execution") == "server_side_attached_first_trigger_quote"
        ),
    )
    if independent_arithmetic["status"] != "verified":
        raise ValueError(
            "independent resolved arithmetic mismatch: "
            f"{independent_arithmetic['mismatch_rows']} rows; "
            f"fill={independent_arithmetic['fill_source_quote_mismatches']}, "
            f"exit={independent_arithmetic['exit_source_quote_mismatches']}, "
            f"net_r={independent_arithmetic['net_r_recalculation_mismatches']}; "
            f"missing_fill_events={independent_arithmetic['fill_event_not_found_rows']}, "
            f"fill_price_only={independent_arithmetic['fill_price_mismatch_rows']}; "
            f"fill_examples={json.dumps(independent_arithmetic['first_fill_mismatch_examples'])}; "
            f"examples={independent_arithmetic['first_mismatch_outcome_ids']}"
        )

    independent_full_replay = independently_replay_outcomes(
        proposals,
        outcomes,
        tickbook._ts,
        tickbook._bid,
        tickbook._ask,
        coverage_cutoffs=replay_coverage_cutoffs,
        training_cutoff=cutoff,
        slippage_points=float(execution["tick_fill_slippage_points"]),
        commission_per_lot=float(execution["commission_per_lot"]),
        contract_size=float(execution["contract_size"]),
        max_quote_wait_ms=int(execution["max_quote_wait_ms"]),
        randomized_fill_latency_ms=float(execution["randomized_fill_latency_ms"]),
        limit_require_trade_through=bool(execution.get("limit_require_trade_through", False)),
        server_side_protective_orders=(
            execution.get("protective_exit_execution") == "server_side_attached_first_trigger_quote"
        ),
    )

    report = {
        "schema_version": "candidate-conditional-outcome-verification-v2",
        "status": "verified_training_conditional_outcome_packet",
        "estimand": "conditional_fixed_entry",
        "policy_value_claim": False,
        "account_state_evaluated": False,
        "numerical_verification_scope": {
            "full_row_independent_recalculation": independent_full_replay["status"] == "verified",
            "same_implementation_full_replay_exact_match_rows": replay_comparison_rows,
            "full_replay_comparison_sha256": replay_comparison_artifact,
            "independent_resolved_arithmetic": independent_arithmetic,
            "independent_full_row_replay": independent_full_replay,
            "stratified_sample_rows": (
                None if replay_sample_artifact is None else int(replay_sample["sampled_rows"])
            ),
            "stratified_sample_method": replay_sample_method,
            "same_production_replay_function_used_for_sample": replay_sample_artifact is not None,
        },
        "proposal_rows": int(len(proposals)),
        "expected_bracket_rows": int(expected_rows),
        "outcome_rows": int(len(outcomes)),
        "unique_outcome_ids": int(outcomes["outcome_id"].nunique()),
        "outcome_status_counts": dict(sorted(status_counts.items())),
        "limit_fill_price_bound_audit": limit_fill_price_audit,
        "unresolved_reason_counts": dict(sorted(unresolved_reason_counts.items())),
        "verified_session_close_exit_rows": int(len(session_close_exits)),
        "order_coverage_dispositions_by_proposal": dict(sorted(gap_dispositions.items())),
        "source_provenance": {
            "proposal_generation_commit": proposal_manifest["source_commit"],
            "outcome_replay_commit": outcome_manifest["source_commit"],
            "proposal_inputs_pinned_by_sha256": True,
        },
        "proposal_manifest_sha256": _sha256(proposal_dir / "proposal_ledger_manifest.json"),
        "coverage_manifest_sha256": _sha256(coverage_dir / "coverage_manifest.json"),
        "outcome_manifest_sha256": _sha256(outcome_dir / "outcome_manifest.json"),
        "outcome_parquet_sha256": _sha256(outcome_path),
        "stratified_replay_sample_sha256": replay_sample_artifact,
        "disposition_artifacts_sha256": disposition_artifacts,
        "source_sha256": {
            "scripts/research/analysis/evaluation/verify_candidate_proposal_outcomes.py": _sha256(
                ROOT / "scripts/research/analysis/evaluation/verify_candidate_proposal_outcomes.py"
            ),
            "scripts/research/analysis/evaluation/candidate_outcome_reference.py": _sha256(
                ROOT / "scripts/research/analysis/evaluation/candidate_outcome_reference.py"
            ),
        },
    }
    if independent_full_replay["status"] != "verified":
        report["status"] = "candidate_outcome_packet_verification_mismatch"
    report_path = outcome_dir / "independent_verification.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    packet_files = [
        outcome_dir / "conditional_outcomes.parquet",
        outcome_dir / "outcome_manifest.json",
        outcome_dir / "README.md",
        *disposition_outputs,
        *([disposition_summary_path] if disposition_summary_path.is_file() else []),
        *([replay_sample_path] if replay_sample_path.is_file() else []),
        *([replay_comparison_path] if replay_comparison_artifact is not None else []),
        report_path,
    ]
    (outcome_dir / "OUTPUT_SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in packet_files), encoding="utf-8"
    )
    if independent_full_replay["status"] != "verified":
        raise ValueError(
            "independent full-row replay mismatch: "
            f"{independent_full_replay['mismatch_rows']} rows; "
            f"fields={independent_full_replay['mismatch_fields']}; "
            f"examples={independent_full_replay['first_mismatch_examples']}"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--proposal-dir", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--coverage-dir", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--outcome-dir", type=Path, default=DEFAULT_OUTCOMES)
    args = parser.parse_args()
    paths = [
        value if value.is_absolute() else ROOT / value
        for value in (args.config, args.proposal_dir, args.coverage_dir, args.outcome_dir)
    ]
    print(
        json.dumps(
            verify_outcome_packet(
                config_path=paths[0],
                proposal_dir=paths[1],
                coverage_dir=paths[2],
                outcome_dir=paths[3],
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
