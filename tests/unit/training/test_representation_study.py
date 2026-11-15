from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from training.configuration.representation_study import (
    load_representation_study,
    validate_representation_study,
)

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "config/research/representation_study.yaml"


def test_representation_study_registers_c_minus_b_and_separate_q0() -> None:
    study = load_representation_study(STUDY)

    assert study["primary"]["contrast"] == "C_minus_B"
    assert study["primary"]["selection_exposure"] == "development"
    assert study["q0"]["payload_schema"] == "aalto.paired_seed_metrics.v2"
    assert study["arms"]["B"]["history_availability"] == "masked"
    assert study["arms"]["C"]["history_availability"] == "completed_htf"
    assert study["periods"]["exposed_report_only"]["selectable"] is False


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("schema_version",), "representation-study-v3", "schema version"),
        (("primary", "contrast"), "B_minus_C", "C−B"),
        (("q0", "payload_schema"), "aalto.representation_paired_seed_metrics.v1", "Q0"),
        (("periods", "timezone"), "UTC", "Etc/GMT-3"),
        (("periods", "exposed_report_only", "selectable"), True, "not be selectable"),
        (
            ("outcomes", "hard_risk_gate_consistency", "completed_after_liquidation"),
            "must_fail",
            "consistency",
        ),
    ],
)
def test_representation_study_rejects_protocol_drift(
    path: tuple[str, ...], value: object, message: str
) -> None:
    study = load_representation_study(STUDY)
    changed = deepcopy(study)
    node = changed
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value

    with pytest.raises(ValueError, match=message):
        validate_representation_study(changed)
