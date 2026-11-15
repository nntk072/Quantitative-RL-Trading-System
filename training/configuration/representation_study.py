"""Validation for the additive C-versus-B representation study contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from training.configuration.research_protocol import (
    EXPECTED_TIMEFRAMES,
    load_research_protocol,
)

STUDY_SCHEMA_VERSION = "representation-study-v2"
PAYLOAD_SCHEMA = "aalto.representation_paired_seed_metrics.v3"
EXPECTED_SEEDS = (42, 43, 44, 45, 46, 47)
LOCAL_TIMEZONE = "Etc/GMT-3"
LOCAL_OFFSET = timedelta(hours=3)
DEVELOPMENT_PERIOD = ("2024-12-30T00:00:00+03:00", "2025-12-31T23:59:00+03:00")
EXPOSED_PERIOD = ("2026-01-01T00:00:00+03:00", "2026-10-16T23:59:00+03:00")
VALID_ECONOMIC_OUTCOMES = frozenset(
    {
        "completed_without_breach",
        "completed_after_hard_breach",
        "completed_after_liquidation",
    }
)
SCIENTIFIC_INVALID_REASONS = frozenset(
    {
        "corrupt_ledger",
        "unreconstructable_equity",
        "missing_quote_provenance",
        "incomplete_evaluation",
    }
)
EQUAL_FIELDS = (
    "dataset_sha256",
    "split_id",
    "features_sha256",
    "reward_sha256",
    "risk_sha256",
    "costs_sha256",
    "execution_sha256",
    "timesteps",
    "seed",
    "initial_capital",
    "model_settings_sha256",
    "evaluation_cohort_sha256",
    "decision_cohort_sha256",
    "evaluation_start",
    "evaluation_end",
    "candidate_opportunities_sha256",
    "legal_masks_sha256",
    "action_schema_sha256",
    "common_policy_contract_sha256",
    "source_identity_sha256",
)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Return a mapping or reject malformed study configuration values.

    Args:
        value: Candidate value to validate.
        name: Field name included in validation errors.

    Returns:
        The validated mapping.
    """
    if isinstance(value, Mapping):
        return value
    raise ValueError(f"{name} must be a mapping")


def parse_local_row_timestamp(value: Any, name: str) -> datetime:
    """Parse a canonical minute-row timestamp with the configured +03 offset.

    Args:
        value: Timestamp string to parse.
        name: Field name included in validation errors.

    Returns:
        The timezone-aware minute timestamp.
    """
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 timestamp string")
    canonical = value.replace(" ", "T", 1) if "T" not in value else value
    try:
        timestamp = datetime.fromisoformat(canonical)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp string") from error
    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() != LOCAL_OFFSET
        or timestamp.second != 0
        or timestamp.microsecond != 0
        or timestamp.isoformat(timespec="seconds") != canonical
    ):
        raise ValueError(f"{name} must use canonical Etc/GMT-3 minute precision")
    return timestamp


def load_representation_study(path: str | Path) -> dict[str, Any]:
    """Load the versioned representation study and validate its frozen contract.

    Args:
        path: YAML study configuration path.

    Returns:
        The validated study mapping.
    """
    raw = OmegaConf.to_container(OmegaConf.load(Path(path)), resolve=True)
    if not isinstance(raw, Mapping):
        raise ValueError("representation study root must be a mapping")
    study = dict(raw)
    validate_representation_study(study)
    return study


def validate_representation_study(study: Mapping[str, Any]) -> None:
    """Reject changes to the registered C−B contrast, Q0 reference, or scope.

    Args:
        study: Representation study configuration to validate.

    Returns:
        None.
    """
    if study.get("schema_version") != STUDY_SCHEMA_VERSION:
        raise ValueError("unsupported representation study schema version")

    primary = _mapping(study.get("primary"), "primary")
    if primary != {
        "contrast": "C_minus_B",
        "metric": "net_return_initial_equity_pct",
        "survival_co_outcome": "hard_risk_survival",
        "selection_exposure": "development",
        "uncertainty": "paired_seed_sign_flip_and_bootstrap",
        "sign_flip_alternative": "two-sided",
        "bootstrap_draws": 10000,
        "rng_seed": 42,
    }:
        raise ValueError("primary representation estimand differs from the registered C−B contract")

    q0 = _mapping(study.get("q0"), "q0")
    if q0 != {
        "protocol_path": "config/research/prospective_research_protocol.yaml",
        "payload_schema": "aalto.paired_seed_metrics.v2",
        "question": "survival_and_net_value_against_always_no_trade",
    }:
        raise ValueError("Q0 must reference the frozen survival-versus-flat protocol")
    repo_root = Path(__file__).resolve().parents[2]
    q0_protocol = load_research_protocol(repo_root / str(q0["protocol_path"]))
    if q0_protocol.get("schema_version") != "research-execution-protocol-v2":
        raise ValueError("Q0 reference must remain research-execution-protocol-v2")

    arms = _mapping(study.get("arms"), "arms")
    expected_arms = {
        "B": {
            "config_path": "config/research/mtf_shared_opportunities_m1_history.yaml",
            "history_availability": "masked",
        },
        "C": {
            "config_path": "config/research/mtf_shared_opportunities_with_history.yaml",
            "history_availability": "completed_htf",
        },
    }
    if dict(arms) != expected_arms:
        raise ValueError("registered representation arms or history treatment differ")

    replication = _mapping(study.get("replication"), "replication")
    if tuple(replication.get("seeds", ())) != EXPECTED_SEEDS:
        raise ValueError("representation study seeds must be exactly 42..47")
    if replication.get("minimum_valid_pairs_for_inference") != len(EXPECTED_SEEDS):
        raise ValueError("representation inference requires all six valid seed pairs")

    periods = _mapping(study.get("periods"), "periods")
    if periods.get("timezone") != LOCAL_TIMEZONE:
        raise ValueError("representation study must use Etc/GMT-3 local time")
    development = _mapping(periods.get("development"), "periods.development")
    exposed = _mapping(periods.get("exposed_report_only"), "periods.exposed_report_only")
    if (development.get("start"), development.get("end_inclusive")) != DEVELOPMENT_PERIOD:
        raise ValueError("development period differs from the registered interval")
    if (exposed.get("start"), exposed.get("end_inclusive")) != EXPOSED_PERIOD:
        raise ValueError("exposed report period differs from the registered interval")
    if exposed.get("selectable") is not False:
        raise ValueError("exposed report period must not be selectable")

    outcomes = _mapping(study.get("outcomes"), "outcomes")
    if frozenset(outcomes.get("valid_economic", ())) != VALID_ECONOMIC_OUTCOMES:
        raise ValueError("registered economic outcome set differs")
    if outcomes.get("hard_risk_gate_consistency") != {
        "completed_without_breach": "must_pass",
        "completed_after_hard_breach": "must_fail",
        "completed_after_liquidation": "preserve_observed_boolean",
    }:
        raise ValueError("economic outcome hard-risk consistency differs")
    if frozenset(outcomes.get("scientific_invalid_reasons", ())) != SCIENTIFIC_INVALID_REASONS:
        raise ValueError("registered scientific-invalid reasons differ")

    matching = _mapping(study.get("matching"), "matching")
    if tuple(matching.get("equal_fields", ())) != EQUAL_FIELDS:
        raise ValueError("B/C shared-contract equality fields differ")
    if matching.get("intervention_field") != "environment_sha256":
        raise ValueError("history availability must be the only intervention")
    if matching.get("history_field") != "history_availability":
        raise ValueError("history availability field differs")


__all__ = [
    "DEVELOPMENT_PERIOD",
    "EQUAL_FIELDS",
    "EXPECTED_SEEDS",
    "EXPECTED_TIMEFRAMES",
    "EXPOSED_PERIOD",
    "LOCAL_OFFSET",
    "LOCAL_TIMEZONE",
    "PAYLOAD_SCHEMA",
    "SCIENTIFIC_INVALID_REASONS",
    "STUDY_SCHEMA_VERSION",
    "VALID_ECONOMIC_OUTCOMES",
    "load_representation_study",
    "parse_local_row_timestamp",
    "validate_representation_study",
]
