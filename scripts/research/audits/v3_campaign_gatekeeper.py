#!/usr/bin/env python3
"""Compute the remaining V3 campaign state without starting experiments."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from scripts.research.audits.pretraining_scientific_readiness import (
    DEFAULT_PLAN as DEFAULT_READINESS_PLAN,
)
from scripts.research.audits.pretraining_scientific_readiness import (
    execution_errors,
    gate_errors,
)
from scripts.research.audits.pretraining_scientific_readiness import (
    load_plan as load_readiness_plan,
)
from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_PLAN = ROOT / "config/research/v3_remaining_execution.yaml"
PHASE_REVIEW_SCHEMAS = {"v3-phase-review-v1", "v3-phase-review-v2"}


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"expected JSON object: {path}")
    return {str(key): item for key, item in value.items()}


def load_plan(path: Path) -> dict[str, Any]:
    value = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    if (
        not isinstance(value, dict)
        or not all(isinstance(key, str) for key in value)
        or value.get("schema_version") != "v3-remaining-execution-plan-v3"
    ):
        raise ValueError("unsupported V3 remaining-plan schema")
    gates = value.get("post_survival_review_gates")
    if not isinstance(gates, list) or not gates or len(gates) != len(set(gates)):
        raise ValueError("post_survival_review_gates must be a unique non-empty list")
    return {str(key): item for key, item in value.items()}


def git_state() -> tuple[str, bool]:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return sha, not dirty


def review_errors(record: dict[str, Any], *, gate_id: str, source_commit: str) -> list[str]:
    errors: list[str] = []
    if record.get("schema_version") not in PHASE_REVIEW_SCHEMAS:
        errors.append("review schema mismatch")
    if record.get("gate_id") != gate_id:
        errors.append("gate_id mismatch")
    if record.get("source_commit") != source_commit:
        errors.append("source_commit mismatch")
    if record.get("status") != "pass":
        errors.append("review status is not pass")
    if not isinstance(record.get("reviewed_by"), str) or not record["reviewed_by"].strip():
        errors.append("reviewer is missing")
    reviewed_at = record.get("reviewed_at_utc")
    try:
        parsed_time = datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
        if parsed_time.tzinfo is None or parsed_time.utcoffset() != UTC.utcoffset(parsed_time):
            raise ValueError
    except ValueError:
        errors.append("review time must be UTC")
    if not isinstance(record.get("claim"), str) or not record["claim"].strip():
        errors.append("review claim is missing")
    if not isinstance(record.get("note"), str) or not record["note"].strip():
        errors.append("review rationale is missing")
    prohibited = record.get("prohibited_states")
    if not isinstance(prohibited, dict) or any(value is not False for value in prohibited.values()):
        errors.append("review declares a prohibited state")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("review has no evidence")
    else:
        for row in evidence:
            if not isinstance(row, dict):
                errors.append("malformed evidence row")
                continue
            path_text, digest = row.get("path"), row.get("sha256")
            if not isinstance(path_text, str) or not isinstance(digest, str):
                errors.append("malformed evidence identity")
                continue
            path = Path(path_text)
            if not path.is_file():
                errors.append(f"evidence file missing: {path}")
            elif file_sha256(path) != digest:
                errors.append(f"evidence hash mismatch: {path}")
    return errors


def survival_gate_errors(
    gate: dict[str, Any],
    *,
    required_seeds: list[int],
    minimum_folds: int,
    source_commit: str,
) -> list[str]:
    errors: list[str] = []
    if isinstance(gate.get("schema_version"), bool) or gate.get("schema_version") != 1:
        errors.append("survival gate schema mismatch")
    if gate.get("priority") != "survival_before_portfolio_optimization":
        errors.append("survival gate priority mismatch")
    config_identity = gate.get("config_identity")
    if (
        not isinstance(config_identity, str)
        or len(config_identity) != 64
        or any(character not in "0123456789abcdef" for character in config_identity)
    ):
        errors.append("survival gate config identity is invalid")
    if not isinstance(gate.get("data_identity"), dict) or not gate["data_identity"]:
        errors.append("survival gate data identity is missing")
    failures = gate.get("failures")
    if gate.get("status") == "fail" and (not isinstance(failures, list) or not failures):
        errors.append("failed survival gate lacks failure evidence")
    if gate.get("status") == "pass" and failures != []:
        errors.append("passing survival gate declares failures")
    minimum_seed_count = gate.get("minimum_seed_count")
    if (
        isinstance(minimum_seed_count, bool)
        or not isinstance(minimum_seed_count, int)
        or minimum_seed_count < len(required_seeds)
    ):
        errors.append("survival gate minimum seed count is below the protocol")
    minimum_walk_forward_splits = gate.get("minimum_walk_forward_splits")
    if (
        isinstance(minimum_walk_forward_splits, bool)
        or not isinstance(minimum_walk_forward_splits, int)
        or minimum_walk_forward_splits < minimum_folds
    ):
        errors.append("survival gate minimum walk-forward count is below the protocol")
    seeds = gate.get("seeds")
    evidence = gate.get("evidence")
    if seeds != required_seeds:
        errors.append("survival gate seeds differ from the frozen primary seed set")
    if not isinstance(evidence, list) or len(evidence) != len(seeds or []):
        errors.append("survival gate evidence count does not match seeds")
    folds = gate.get("walk_forward_splits")
    if isinstance(folds, bool) or not isinstance(folds, int) or folds < minimum_folds:
        errors.append("survival gate walk-forward count is insufficient")
    if isinstance(evidence, list):
        evidence_seeds: list[int] = []
        source_identities: list[Any] = []
        data_identities: list[Any] = []
        for row in evidence:
            if not isinstance(row, dict):
                errors.append("survival gate evidence row is malformed")
                continue
            seed = row.get("seed")
            if isinstance(seed, bool) or not isinstance(seed, int):
                errors.append("survival gate evidence seed is invalid")
            else:
                evidence_seeds.append(seed)
            source = row.get("source")
            if not isinstance(source, dict) or not source:
                errors.append("survival evidence lacks source identity")
            else:
                source_identities.append(source)
                if source.get("head") != source_commit or source.get("dirty_files") != []:
                    errors.append("survival evidence source is stale or dirty")
            data_identity = row.get("data_identity")
            if not isinstance(data_identity, dict) or not data_identity:
                errors.append("survival evidence lacks data identity")
            else:
                data_identities.append(data_identity)
                if data_identity != gate.get("data_identity"):
                    errors.append("survival evidence data identity differs from the gate")
            for hash_key, path_key in (
                ("checkpoint_sha256", "checkpoint"),
                ("run_manifest_sha256", "run_manifest"),
                ("train_gate_sha256", "train_gate"),
                ("train_path_outcome_sha256", "train_path_outcome"),
                ("walk_forward_sha256", "walk_forward"),
            ):
                path_text, digest = row.get(path_key), row.get(hash_key)
                if not isinstance(path_text, str) or not isinstance(digest, str):
                    errors.append(f"survival evidence missing {path_key}/{hash_key}")
                    continue
                path = Path(path_text)
                if not path.is_file():
                    errors.append(f"survival evidence missing: {path}")
                elif file_sha256(path) != digest:
                    errors.append(f"survival evidence hash mismatch: {path}")
        if sorted(evidence_seeds) != required_seeds:
            errors.append("survival evidence does not cover the frozen seed set exactly")
        if source_identities and any(
            source != source_identities[0] for source in source_identities[1:]
        ):
            errors.append("survival seed source identities differ")
        if data_identities and any(
            identity != data_identities[0] for identity in data_identities[1:]
        ):
            errors.append("survival seed data identities differ")
    return errors


def build_campaign_state(
    *,
    plan: dict[str, Any],
    scientific_readiness: dict[str, Any],
    survival_gate: dict[str, Any] | None,
    phase_reviews: dict[str, dict[str, Any]],
    source_commit: str,
    source_clean: bool,
) -> dict[str, Any]:
    expected_gates = [str(x) for x in plan["post_survival_review_gates"]]
    review_status: dict[str, dict[str, Any]] = {}
    for gate_id in expected_gates:
        record = phase_reviews.get(gate_id)
        errors = (
            ["review record missing"]
            if record is None
            else review_errors(record, gate_id=gate_id, source_commit=source_commit)
        )
        review_status[gate_id] = {
            "status": "pass" if not errors else "blocked",
            "errors": errors,
            "record": record,
        }

    readiness_errors: list[str] = []
    try:
        readiness_plan = load_readiness_plan(DEFAULT_READINESS_PLAN)
        expected_common = [str(value) for value in readiness_plan["common_gates"]]
        expected_price = [str(value) for value in readiness_plan["price_gates"]]
        expected_barriers = [str(value) for value in readiness_plan["required_execution_barriers"]]
    except (OSError, ValueError, KeyError, TypeError) as error:
        expected_common, expected_price, expected_barriers = [], [], []
        readiness_errors.append(f"scientific readiness plan is invalid: {error}")
    gate_results = scientific_readiness.get("gate_results")
    expected_gate_ids = expected_common + expected_price
    if scientific_readiness.get("common_gate_ids") != expected_common:
        readiness_errors.append("scientific readiness common gate IDs differ from plan")
    if scientific_readiness.get("price_gate_ids") != expected_price:
        readiness_errors.append("scientific readiness PRICE gate IDs differ from plan")
    if scientific_readiness.get("required_execution_barriers") != expected_barriers:
        readiness_errors.append("scientific readiness barriers differ from plan")
    if not isinstance(gate_results, dict) or set(gate_results) != set(expected_gate_ids):
        readiness_errors.append("scientific readiness gate result IDs differ from plan")
    else:
        for gate_id in expected_gate_ids:
            result = gate_results[gate_id]
            record = result.get("record") if isinstance(result, dict) else None
            errors = (
                ["gate record missing"]
                if not isinstance(record, dict)
                else gate_errors(record, expected_gate_id=gate_id, source_commit=source_commit)
            )
            if (
                not isinstance(result, dict)
                or result.get("status") != "pass"
                or result.get("errors") != []
                or errors
            ):
                readiness_errors.extend(
                    [f"{gate_id}: {error}" for error in errors or ["gate result is not pass"]]
                )
    execution = scientific_readiness.get("execution_manifest")
    if not isinstance(execution, dict):
        readiness_errors.append("scientific readiness execution manifest is missing")
    else:
        readiness_errors.extend(
            execution_errors(
                execution, source_commit=source_commit, required_barriers=expected_barriers
            )
        )
    common_gate_pass = isinstance(gate_results, dict) and all(
        isinstance(gate_results.get(gate_id), dict)
        and gate_results[gate_id].get("status") == "pass"
        for gate_id in expected_common
    )
    price_gate_pass = (
        common_gate_pass
        and isinstance(gate_results, dict)
        and all(
            isinstance(gate_results.get(gate_id), dict)
            and gate_results[gate_id].get("status") == "pass"
            for gate_id in expected_price
        )
    )
    science_ok = (
        source_clean
        and not readiness_errors
        and scientific_readiness.get("schema_version") == "pretraining-scientific-readiness-v1"
        and scientific_readiness.get("status") == "pass"
        and scientific_readiness.get("source_commit") == source_commit
        and scientific_readiness.get("source_clean") is True
        and scientific_readiness.get("scientific_training_authorized") is True
    )
    price_ok = (
        science_ok
        and price_gate_pass
        and scientific_readiness.get("price_training_authorized") is True
    )

    required_seeds = [int(seed) for seed in plan["survival_qualification"]["required_seeds"]]
    minimum_folds = int(plan["survival_qualification"]["minimum_walk_forward_splits"])
    survival_errors: list[str] = []
    survival_status = "missing"
    if survival_gate is not None:
        survival_errors = survival_gate_errors(
            survival_gate,
            required_seeds=required_seeds,
            minimum_folds=minimum_folds,
            source_commit=source_commit,
        )
        raw_status = survival_gate.get("status")
        if raw_status == "pass" and not survival_errors:
            survival_status = "pass"
        elif raw_status == "fail" and not survival_errors:
            survival_status = "fail"
        else:
            survival_status = "invalid"

    def passed(gate_id: str) -> bool:
        return bool(review_status[gate_id]["status"] == "pass")

    survival_pass = science_ok and survival_status == "pass"
    survival_fail = science_ok and survival_status == "fail"
    repeatability = passed("checkpoint_repeatability_review")
    portfolio_freeze = passed("portfolio_objective_freeze_review")
    primary = passed("primary_statistical_selection_review")
    robustness = passed("finalist_robustness_review")
    finalist_freeze = passed("finalist_freeze_review")
    report_once = passed("exposed_report_once_review")
    metrics = passed("metrics_evidence_refresh_review")
    thesis = passed("thesis_outputs_review")
    docs = passed("documentation_cleanup_review")
    final_release = passed("final_release_review")
    negative = passed("negative_result_release_review")

    portfolio_authorized = survival_pass and repeatability and portfolio_freeze
    robustness_authorized = portfolio_authorized and primary
    finalist_frozen = robustness_authorized and robustness and finalist_freeze
    report_only_authorized = finalist_frozen
    release_tail = metrics and thesis and docs and final_release
    positive_release_ready = report_only_authorized and report_once and release_tail
    negative_release_ready = survival_fail and negative and release_tail

    if not science_ok:
        phase = "pretraining_scientific_readiness"
    elif survival_status == "missing":
        phase = "survival_qualification"
    elif survival_status == "invalid":
        phase = "survival_gate_repair"
    elif survival_fail and not negative:
        phase = "negative_result_release_review"
    elif survival_fail and not metrics:
        phase = "metrics_evidence_refresh"
    elif survival_fail and not thesis:
        phase = "thesis_outputs"
    elif survival_fail and not docs:
        phase = "documentation_cleanup"
    elif survival_fail and not final_release:
        phase = "final_release"
    elif survival_fail:
        phase = "release_ready"
    elif not repeatability:
        phase = "checkpoint_repeatability"
    elif not portfolio_freeze:
        phase = "portfolio_objective_freeze"
    elif not primary:
        phase = "portfolio_and_primary_statistical_selection"
    elif not robustness:
        phase = "finalist_robustness"
    elif not finalist_freeze:
        phase = "finalist_freeze"
    elif not report_once:
        phase = "exposed_report_once"
    elif not metrics:
        phase = "metrics_evidence_refresh"
    elif not thesis:
        phase = "thesis_outputs"
    elif not docs:
        phase = "documentation_cleanup"
    elif not final_release:
        phase = "final_release"
    else:
        phase = "release_ready"

    return {
        "schema_version": "v3-campaign-state-v3",
        "source_commit": source_commit,
        "source_clean": source_clean,
        "current_phase": phase,
        "scientific_readiness_valid": science_ok,
        "scientific_readiness_errors": readiness_errors,
        "survival_qualification_authorized": science_ok,
        "price_survival_qualification_authorized": price_ok,
        "survival_phase_gate_status": survival_status,
        "survival_phase_gate_errors": survival_errors,
        "checkpoint_repeatability_passed": repeatability,
        "portfolio_objective_frozen": portfolio_freeze,
        "portfolio_phase_authorized": portfolio_authorized,
        "primary_statistical_selection_reviewable": portfolio_authorized,
        "finalist_robustness_authorized": robustness_authorized,
        "finalist_frozen": finalist_frozen,
        "exposed_report_once_authorized": report_only_authorized,
        "metrics_evidence_refresh_complete": metrics,
        "thesis_outputs_complete": thesis,
        "documentation_cleanup_complete": docs,
        "final_release_review_complete": final_release,
        "positive_result_release_ready": positive_release_ready,
        "negative_result_release_ready": negative_release_ready,
        "release_ready": positive_release_ready or negative_release_ready,
        "phase_reviews": review_status,
        "training_started_by_gatekeeper": False,
        "allocates_compute": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--scientific-readiness", type=Path, required=True)
    parser.add_argument("--survival-gate", type=Path)
    parser.add_argument("--phase-review", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan_path = args.plan if args.plan.is_absolute() else ROOT / args.plan
    plan = load_plan(plan_path)
    source_commit, clean = git_state()
    if not clean:
        raise SystemExit("V3 campaign state requires a clean source tree")
    readiness = _object(args.scientific_readiness.expanduser().resolve())
    survival = (
        None if args.survival_gate is None else _object(args.survival_gate.expanduser().resolve())
    )
    reviews: dict[str, dict[str, Any]] = {}
    for raw in args.phase_review:
        record = _object(Path(raw).expanduser().resolve())
        gate_id = str(record.get("gate_id", ""))
        if gate_id in reviews:
            raise ValueError(f"duplicate phase review: {gate_id}")
        reviews[gate_id] = record
    state = build_campaign_state(
        plan=plan,
        scientific_readiness=readiness,
        survival_gate=survival,
        phase_reviews=reviews,
        source_commit=source_commit,
        source_clean=clean,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.output, state)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
