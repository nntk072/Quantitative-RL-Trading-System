"""Source-bound scientific review and training-readiness contracts."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from artifacts.atomic import write_json_atomic
from artifacts.identity import file_sha256
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_READINESS = ROOT / "config/research/scientific_readiness.yaml"


def _object(path: Path) -> dict[str, Any]:
    """Load one JSON object from disk.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _source_state() -> tuple[str, bool]:
    """Return the current source commit and clean-tree state.

    Returns:
        Result produced by _source_state.
    """
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    return commit, not dirty


def load_readiness_contract(path: str | Path = DEFAULT_READINESS) -> dict[str, Any]:
    """Load the active scientific-readiness contract.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by load_readiness_contract.
    """
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("unsupported scientific-readiness contract")
    for key in ("required_experiments", "common_reviews", "price_reviews"):
        rows = value.get(key)
        if not isinstance(rows, list) or not all(
            isinstance(item, str) and item.strip() for item in rows
        ):
            raise ValueError(f"{key} must be a string list")
        if len(rows) != len(set(rows)):
            raise ValueError(f"{key} contains duplicate identifiers")
    if set(value["common_reviews"]) & set(value["price_reviews"]):
        raise ValueError("common and candidate-geometry reviews must be disjoint")
    prohibited = value.get("prohibited_states")
    if not isinstance(prohibited, dict) or not prohibited:
        raise ValueError("scientific-readiness contract requires prohibited states")
    return value


def record_review(
    *,
    review_id: str,
    status: str,
    reviewed_by: str,
    note: str,
    evidence: Iterable[Path],
    output: Path,
) -> dict[str, Any]:
    """Record one human scientific review with immutable evidence identities.

    Args:
        review_id: Stable scientific review identifier.
        status: Recorded review or execution status.
        reviewed_by: Reviewer identity recorded with the evidence.
        note: Human-readable review rationale.
        evidence: Evidence files supporting the recorded review.
        output: Destination path for the generated artifact.

    Returns:
        Result produced by record_review.
    """
    if status not in {"pass", "fail"}:
        raise ValueError("review status must be pass or fail")
    if not review_id.strip() or not reviewed_by.strip() or not note.strip():
        raise ValueError("review id, reviewer, and rationale must be non-empty")
    source_commit, source_clean = _source_state()
    if not source_clean:
        raise ValueError("scientific review requires a clean source tree")
    evidence_rows: list[dict[str, str]] = []
    for raw in evidence:
        path = raw.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        evidence_rows.append({"path": str(path), "sha256": file_sha256(path)})
    if not evidence_rows:
        raise ValueError("scientific review requires at least one evidence file")
    record = {
        "schema_version": 1,
        "review_id": review_id.strip(),
        "source_commit": source_commit,
        "status": status,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at_utc": datetime.now(UTC).isoformat(),
        "note": note.strip(),
        "prohibited_states": {
            "exposed_report_period_used_for_selection": False,
            "candidate_realized_outcomes_used_as_policy_inputs": False,
            "preregistered_thresholds_changed_post_hoc": False,
        },
        "evidence": evidence_rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output, record)
    return record


def _review_errors(
    record: dict[str, Any],
    *,
    review_id: str,
    source_commit: str,
) -> list[str]:
    """Return validation errors for one scientific review record.

    Args:
        record: Value used for record.
        review_id: Stable scientific review identifier.
        source_commit: Git commit binding the research artifacts.

    Returns:
        Result produced by _review_errors.
    """
    errors: list[str] = []
    if record.get("schema_version") != 1:
        errors.append("schema mismatch")
    if record.get("review_id") != review_id:
        errors.append("review identity mismatch")
    if record.get("source_commit") != source_commit:
        errors.append("source commit mismatch")
    if record.get("status") != "pass":
        errors.append("review did not pass")
    if not isinstance(record.get("reviewed_by"), str) or not record["reviewed_by"].strip():
        errors.append("reviewer is missing")
    try:
        timestamp = datetime.fromisoformat(str(record.get("reviewed_at_utc")))
        if timestamp.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append("review timestamp is invalid")
    if not isinstance(record.get("note"), str) or not record["note"].strip():
        errors.append("review rationale is missing")
    prohibited = record.get("prohibited_states")
    if not isinstance(prohibited, dict) or any(
        prohibited.get(key) is not False
        for key in (
            "exposed_report_period_used_for_selection",
            "candidate_realized_outcomes_used_as_policy_inputs",
            "preregistered_thresholds_changed_post_hoc",
        )
    ):
        errors.append("review declares a prohibited scientific state")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("review evidence is missing")
    else:
        for item in evidence:
            if not isinstance(item, dict):
                errors.append("review evidence row is invalid")
                continue
            path_value = item.get("path")
            digest = item.get("sha256")
            if not isinstance(path_value, str) or not isinstance(digest, str):
                errors.append("review evidence identity is invalid")
                continue
            path = Path(path_value)
            if not path.is_file():
                errors.append(f"review evidence is missing: {path}")
            elif file_sha256(path) != digest:
                errors.append(f"review evidence changed: {path}")
    return errors


def _execution_errors(
    manifest: dict[str, Any],
    *,
    experiment_id: str,
    source_commit: str,
) -> list[str]:
    """Return validation errors for one prerequisite execution record.

    Args:
        manifest: Value used for manifest.
        experiment_id: Registered research experiment identifier.
        source_commit: Git commit binding the research artifacts.

    Returns:
        Result produced by _execution_errors.
    """
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema mismatch")
    if manifest.get("source_commit") != source_commit:
        errors.append("source commit mismatch")
    if manifest.get("experiment_id") != experiment_id:
        errors.append("experiment identity mismatch")
    if manifest.get("status") != "passed":
        errors.append("experiment execution did not pass")
    commands = manifest.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("execution has no command records")
    elif any(not isinstance(row, dict) or row.get("status") != "passed" for row in commands):
        errors.append("one or more execution commands did not pass")
    return errors


def build_readiness(
    *,
    contract: dict[str, Any],
    execution_manifests: dict[str, dict[str, Any]],
    reviews: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build the source-bound authorization record for scientific training.

    Args:
        contract: Scientific-readiness contract.
        execution_manifests: Source-bound prerequisite execution records.
        reviews: Source-bound scientific review records.

    Returns:
        Result produced by build_readiness.
    """
    source_commit, source_clean = _source_state()
    required_experiments = tuple(str(item) for item in contract["required_experiments"])
    common_reviews = tuple(str(item) for item in contract["common_reviews"])
    price_reviews = tuple(str(item) for item in contract["price_reviews"])
    errors: list[str] = []
    if not source_clean:
        errors.append("current source tree is dirty")

    execution_status: dict[str, dict[str, Any]] = {}
    for experiment_id in required_experiments:
        manifest = execution_manifests.get(experiment_id)
        experiment_errors = (
            ["execution manifest missing"]
            if manifest is None
            else _execution_errors(
                manifest,
                experiment_id=experiment_id,
                source_commit=source_commit,
            )
        )
        execution_status[experiment_id] = {
            "status": "pass" if not experiment_errors else "fail",
            "errors": experiment_errors,
        }
        errors.extend(f"{experiment_id}: {error}" for error in experiment_errors)

    review_status: dict[str, dict[str, Any]] = {}
    for review_id in (*common_reviews, *price_reviews):
        record = reviews.get(review_id)
        review_errors = (
            ["review record missing"]
            if record is None
            else _review_errors(
                record,
                review_id=review_id,
                source_commit=source_commit,
            )
        )
        review_status[review_id] = {
            "status": "pass" if not review_errors else "fail",
            "errors": review_errors,
        }

    executions_ready = all(
        execution_status[item]["status"] == "pass" for item in required_experiments
    )
    common_ready = (
        source_clean
        and executions_ready
        and all(review_status[item]["status"] == "pass" for item in common_reviews)
    )
    price_ready = common_ready and all(
        review_status[item]["status"] == "pass" for item in price_reviews
    )
    if not common_ready:
        errors.append("common scientific readiness is incomplete")

    return {
        "schema_version": 1,
        "status": "pass" if common_ready else "fail",
        "source_commit": source_commit,
        "source_clean": source_clean,
        "scientific_training_authorized": common_ready,
        "price_training_authorized": price_ready,
        "execution_status": execution_status,
        "review_status": review_status,
        "errors": errors,
    }


__all__ = [
    "DEFAULT_READINESS",
    "build_readiness",
    "load_readiness_contract",
    "record_review",
]
