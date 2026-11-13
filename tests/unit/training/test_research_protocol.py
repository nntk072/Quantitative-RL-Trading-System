from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from training.configuration.research_protocol import (
    EXPECTED_SEEDS,
    load_research_protocol,
    research_protocol_sha256,
    validate_research_protocol,
)

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def test_prospective_protocol_is_complete_and_stably_hashable() -> None:
    protocol = load_research_protocol(PROTOCOL)
    assert protocol["schema_version"] == 1
    assert tuple(protocol["replication"]["seeds"]) == EXPECTED_SEEDS
    digest = research_protocol_sha256(protocol)
    assert len(digest) == 64
    assert digest == research_protocol_sha256(protocol)


def test_protocol_rejects_exposed_period_selection() -> None:
    protocol = load_research_protocol(PROTOCOL)
    changed = deepcopy(protocol)
    changed["periods"]["exposed_report_only"]["selectable"] = True
    with pytest.raises(ValueError, match="must not be selectable"):
        validate_research_protocol(changed)


def test_protocol_rejects_changed_survival_threshold() -> None:
    protocol = load_research_protocol(PROTOCOL)
    changed = deepcopy(protocol)
    changed["survival_contract"]["daily_loss_limit_fraction"] = 0.04
    with pytest.raises(ValueError, match="daily_loss_limit_fraction"):
        validate_research_protocol(changed)


def test_protocol_rejects_changed_seed_set_and_compute_unit() -> None:
    protocol = load_research_protocol(PROTOCOL)
    changed = deepcopy(protocol)
    changed["replication"]["seeds"][-1] = 99
    with pytest.raises(ValueError, match="seed set"):
        validate_research_protocol(changed)
    changed = deepcopy(protocol)
    changed["compute"]["comparison_unit"] = "raw_fps"
    with pytest.raises(ValueError, match="full paths"):
        validate_research_protocol(changed)


def test_protocol_locks_candidate_history_config_identities() -> None:
    protocol = load_research_protocol(PROTOCOL)
    assert protocol["policy"]["candidate_history_ablation_configs"] == {
        "m1_reference": "config/research/m1_opportunity_reference.yaml",
        "shared_opportunities": "config/research/mtf_shared_opportunities_m1_history.yaml",
        "completed_history": "config/research/mtf_shared_opportunities_with_history.yaml",
    }
    changed = deepcopy(protocol)
    changed["policy"]["candidate_history_ablation_configs"]["completed_history"] = (
        "config/research/survival_trade_setup_mtf_conditioned.yaml"
    )
    with pytest.raises(ValueError, match="candidate-history config identities"):
        validate_research_protocol(changed)
