"""Input and provenance boundaries for immutable matched-baseline bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from evaluation.reporting import matched_setup_baseline_bundle as bundle


def _common_inputs(tmp_path: Path) -> dict[str, Any]:
    repository = tmp_path / "source"
    repository.mkdir(exist_ok=True)
    config_path = repository / "study.yaml"
    config_path.write_text("account: {initial_balance: 100.0}\n", encoding="utf-8")
    (repository / "protocol.md").write_text("frozen test protocol\n", encoding="utf-8")
    artifact_root = tmp_path / "artifacts"
    index = pd.date_range("2025-02-03 15:00", periods=1, freq="min", tz="UTC")
    cfg = {"account": {"initial_balance": 100.0}}
    return {
        "cfg": cfg,
        "bars": pd.DataFrame({"close": [100.0]}, index=index),
        "features": pd.DataFrame({"atr": [1.0]}, index=index),
        "output_root": artifact_root / "matched",
        "artifact_root": artifact_root,
        "source_repository": repository,
        "config_path": config_path,
        "protocol_path": "protocol.md",
        "regeneration_command": "python -m evaluation.baselines",
    }


def _arm(cfg: dict[str, Any], *, period_role: str = "synthetic") -> dict[str, Any]:
    return {
        "policy_metadata": {
            "period_role": period_role,
            "resolved_config_sha256": bundle._canonical_sha256(cfg),
            "action_schema": {"version": "setup-v1"},
        }
    }


def _write(tmp_path: Path, outputs: dict[str, dict[str, Any]], **overrides: Any) -> Path:
    options = _common_inputs(tmp_path)
    options.update(overrides)
    return bundle.write_matched_setup_baseline_bundle(
        outputs,
        options["cfg"],
        options["bars"],
        options["features"],
        None,
        output_root=options["output_root"],
        artifact_root=options["artifact_root"],
        source_repository=options["source_repository"],
        config_path=options["config_path"],
        protocol_path=options["protocol_path"],
        regeneration_command=options["regeneration_command"],
        source_files=options.get("source_files"),
    )


def test_bundle_requires_at_least_one_completed_policy_arm(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one completed policy arm"):
        _write(tmp_path, {})

    assert not (tmp_path / "artifacts").exists()


def test_bundle_rejects_noncanonical_policy_names_before_output_creation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="lowercase identifiers"):
        _write(tmp_path, {"Candidate-A": {}})

    assert not (tmp_path / "artifacts").exists()


def test_bundle_requires_existing_source_config(tmp_path: Path) -> None:
    options = _common_inputs(tmp_path)
    missing_config = options["source_repository"] / "missing.yaml"

    with pytest.raises(FileNotFoundError, match="source config is missing"):
        _write(
            tmp_path,
            {"always_no_trade": _arm(options["cfg"])},
            config_path=missing_config,
        )

    assert not options["artifact_root"].exists()


@pytest.mark.parametrize("field", ["protocol_path", "regeneration_command"])
def test_bundle_requires_regeneration_provenance_fields(tmp_path: Path, field: str) -> None:
    options = _common_inputs(tmp_path)
    outputs = {"always_no_trade": _arm(options["cfg"])}

    with pytest.raises(ValueError, match="must be recorded"):
        _write(tmp_path, outputs, **{field: ""})

    assert not options["artifact_root"].exists()


def test_bundle_rejects_protocol_paths_outside_the_source_repository(tmp_path: Path) -> None:
    options = _common_inputs(tmp_path)

    with pytest.raises(ValueError, match="inside source_repository"):
        _write(
            tmp_path,
            {"always_no_trade": _arm(options["cfg"])},
            protocol_path="../outside/protocol.md",
        )

    assert not options["artifact_root"].exists()


def test_bundle_rejects_an_output_root_outside_its_artifact_root(tmp_path: Path) -> None:
    options = _common_inputs(tmp_path)

    with pytest.raises(ValueError, match="inside artifact_root"):
        _write(
            tmp_path,
            {"always_no_trade": _arm(options["cfg"])},
            output_root=tmp_path / "outside",
        )

    assert not (tmp_path / "outside").exists()


def test_bundle_requires_matched_policies_to_share_period_role_and_schema(tmp_path: Path) -> None:
    options = _common_inputs(tmp_path)
    outputs = {
        "always_no_trade": _arm(options["cfg"]),
        "random_eligible_setup": _arm(options["cfg"], period_role="development"),
    }

    with pytest.raises(ValueError, match="share period role, resolved config, and action schema"):
        _write(tmp_path, outputs)

    assert not options["artifact_root"].exists()


def test_bundle_rejects_missing_named_source_files(tmp_path: Path) -> None:
    options = _common_inputs(tmp_path)
    missing_source = options["source_repository"] / "checkpoint.zip"

    with pytest.raises(FileNotFoundError, match="baseline source file is missing"):
        _write(
            tmp_path,
            {"always_no_trade": _arm(options["cfg"])},
            source_files={"candidate_checkpoint": missing_source},
        )

    assert not options["artifact_root"].exists()


def test_bundle_rejects_checkpoint_claim_on_a_deterministic_rule(tmp_path: Path) -> None:
    options = _common_inputs(tmp_path)
    arm = _arm(options["cfg"])
    arm["policy_metadata"].update(
        {"policy_source": "deterministic_rule", "checkpoint_sha256": "a" * 64}
    )

    with pytest.raises(ValueError, match="deterministic rule must not claim a checkpoint"):
        _write(tmp_path, {"candidate_rule": arm})

    assert not options["artifact_root"].exists()


def test_bundle_requires_trained_checkpoint_hash_to_match_its_named_source(
    tmp_path: Path,
) -> None:
    options = _common_inputs(tmp_path)
    checkpoint = options["source_repository"] / "candidate.zip"
    checkpoint.write_bytes(b"synthetic checkpoint bytes")
    arm = _arm(options["cfg"])
    arm["policy_metadata"].update(
        {
            "policy_source": "trained_checkpoint",
            "checkpoint_sha256": "a" * 64,
            "checkpoint_source_key": "candidate_checkpoint",
        }
    )

    with pytest.raises(ValueError, match="checkpoint hash must match its named source file"):
        _write(
            tmp_path,
            {"trained_candidate": arm},
            source_files={"candidate_checkpoint": checkpoint},
        )

    assert not options["artifact_root"].exists()
