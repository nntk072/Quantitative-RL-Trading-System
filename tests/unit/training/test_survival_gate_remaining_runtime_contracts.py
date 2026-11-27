from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest
from omegaconf import OmegaConf

from decisioning.observations import OBSERVATION_SCHEMA_V2
from training.configuration.survival_gate import (
    _survival_candidate_timeframes,
    _validate_qualification_manifest,
    survival_config_identity,
    validate_portfolio_gate,
)


def _portfolio_config(gate_path: Path):
    return OmegaConf.create(
        {
            "env": {
                "reward_mode": "dsr",
                "observation_schema_version": OBSERVATION_SCHEMA_V2,
                "feature_validity_channels": True,
                "reachable_r_validity_mask": True,
                "strict_research_eligibility": True,
            },
            "training": {"survival_gate_manifest": str(gate_path)},
            "ppo": {"total_timesteps": 1000},
        }
    )


def _gate_header(*, config_identity: str = "not-the-current-config") -> dict[str, object]:
    seeds = [42, 43, 44, 45, 46, 47]
    return {
        "schema_version": 1,
        "priority": "survival_before_portfolio_optimization",
        "status": "pass",
        "seeds": seeds,
        "evidence": [{"seed": seed} for seed in seeds],
        "walk_forward_splits": 5,
        "minimum_seed_count": 6,
        "minimum_walk_forward_splits": 5,
        "config_identity": config_identity,
    }


def _portfolio_args() -> Namespace:
    return Namespace(
        algo="ppo",
        arch="tcn",
        strategy="baseline",
        reward="dsr",
        resume_checkpoint="seed42/model.zip",
        seed=42,
        seeds=[42],
        allow_locked_oos_for_selection=False,
    )


def test_candidate_timeframe_scope_rejects_non_mapping_environment() -> None:
    assert _survival_candidate_timeframes({"env": []}) is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("reward", []),
        ("walk_forward", "enabled"),
        ("constrained_rl", None),
    ],
)
def test_qualification_manifest_rejects_malformed_nested_protocol_metadata(
    key: str, value: object
) -> None:
    protocol: dict[str, object] = {
        "training_phase": "survival_qualification",
        "reward": {"mode": "survival", "selector": "dsr"},
        "walk_forward": {"enabled": True, "folds": 5},
        "constrained_rl": {"enabled": False},
    }
    protocol[key] = value

    with pytest.raises(ValueError, match="qualification metadata must be objects"):
        _validate_qualification_manifest(
            manifest={"seed": 42, "training_protocol": protocol},
            cfg={},
            args=Namespace(),
            seed=42,
        )


def test_portfolio_gate_rejects_evidence_seed_set_that_differs_from_gate_seeds(
    tmp_path: Path,
) -> None:
    gate = _gate_header()
    gate["evidence"] = [{"seed": seed} for seed in [42, 43, 44, 45, 46, 48]]
    gate_path = tmp_path / "survival-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    with pytest.raises(SystemExit, match="seed list and evidence set do not match"):
        validate_portfolio_gate(cfg=_portfolio_config(gate_path), args=_portfolio_args())


def test_portfolio_gate_rejects_behavior_config_different_from_qualification(
    tmp_path: Path,
) -> None:
    gate_path = tmp_path / "survival-gate.json"
    gate_path.write_text(json.dumps(_gate_header()), encoding="utf-8")
    cfg = _portfolio_config(gate_path)
    gate = _gate_header(config_identity=survival_config_identity(cfg))
    gate["reward_selector"] = "dsr"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    cfg.env.risk_mode = "fixed"

    with pytest.raises(SystemExit, match="behavior config"):
        validate_portfolio_gate(cfg=cfg, args=_portfolio_args())
