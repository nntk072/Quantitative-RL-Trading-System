from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from decisioning.trade_setup import (
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    build_trade_setup_action_schema,
    trade_setup_observation_schema,
    validate_trade_setup_observation_schema,
)
from training.artifacts.manifests import observation_schema_manifest


def test_trade_setup_observation_schema_is_checkpoint_checked() -> None:
    expected = trade_setup_observation_schema()
    model = SimpleNamespace(_trade_setup_observation_schema=expected)
    validate_trade_setup_observation_schema(model._trade_setup_observation_schema, expected)
    validate_trade_setup_observation_schema(None, None)

    with pytest.raises(ValueError, match="trade setup observation schema"):
        validate_trade_setup_observation_schema(None, expected)
    with pytest.raises(ValueError, match="trade setup observation schema"):
        validate_trade_setup_observation_schema(model._trade_setup_observation_schema, None)


def test_training_observation_manifest_records_trade_setup_mask_schema() -> None:
    account_schema = SimpleNamespace(to_dict=lambda: {"version": "account-state-v1"})
    env = SimpleNamespace(
        observation_schema=account_schema,
        regime_observation_schema=None,
        trade_setup_observation_schema=trade_setup_observation_schema(),
        candidate_geometry_observation_schema=None,
        _obs_columns=("close", "M3_close"),
        mtf=True,
        trade_setup_actions=True,
        completed_htf_history_enabled=True,
        feature_validity_channels=False,
    )

    manifest = observation_schema_manifest(env)

    assert manifest is not None
    assert manifest["version"] == "account-state-v1"
    assert manifest["trade_setup_observation"] == trade_setup_observation_schema()
    assert manifest["effective_policy_input_schema"]["version"] == "policy-input-streams-v1"


@pytest.mark.parametrize(
    ("candidate_timeframes", "mtf", "history_enabled", "expected_history", "expected_keys"),
    [
        (("M1",), False, True, False, ["seq"]),
        (
            ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"),
            True,
            False,
            False,
            [
                "seq",
                "seq_m3",
                "seq_m5",
                "seq_m10",
                "seq_m15",
                "seq_m30",
                "seq_h1",
                "seq_h4",
                "seq_d1",
            ],
        ),
        (
            ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"),
            True,
            True,
            True,
            [
                "seq",
                "seq_m3",
                "seq_m5",
                "seq_m10",
                "seq_m15",
                "seq_m30",
                "seq_h1",
                "seq_h4",
                "seq_d1",
            ],
        ),
    ],
)
def test_effective_policy_input_manifest_records_a_bc_runtime_streams(
    candidate_timeframes: tuple[str, ...],
    mtf: bool,
    history_enabled: bool,
    expected_history: bool,
    expected_keys: list[str],
) -> None:
    schema = trade_setup_observation_schema(
        candidate_timeframes, completed_htf_history_enabled=history_enabled
    )
    env = SimpleNamespace(
        observation_schema=SimpleNamespace(to_dict=lambda: {"version": "account-state-v2"}),
        regime_observation_schema=None,
        trade_setup_observation_schema=schema,
        candidate_geometry_observation_schema=None,
        _obs_columns=("close", "M3_close", "M5_close"),
        mtf=mtf,
        trade_setup_actions=True,
        completed_htf_history_enabled=history_enabled,
        feature_validity_channels=True,
    )

    manifest = observation_schema_manifest(env)
    assert manifest is not None
    effective = manifest["effective_policy_input_schema"]

    assert effective["completed_htf_history_enabled"] is expected_history
    assert [stream["sequence_key"] for stream in effective["streams"]] == expected_keys
    assert manifest["trade_setup_observation"]["completed_htf_history_enabled"] is expected_history
    if mtf:
        assert "M3_close" in sequence_columns_for_key(effective, "seq_m3")
        assert "M3_close" not in sequence_columns_for_key(effective, "seq")
    else:
        assert effective["streams"][0]["columns"] == ["close"]


def sequence_columns_for_key(effective_schema: dict[str, Any], key: str) -> list[str]:
    return next(
        stream["columns"] for stream in effective_schema["streams"] if stream["sequence_key"] == key
    )


def test_action_schema_has_one_setup_coordinate_and_full_category_catalog() -> None:
    assert TRADE_SETUP_CATEGORY_COUNT == len(TRADE_SETUP_CANDIDATES) == 109
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_multi_tp=True, has_simplex=True)
    assert schema.names.count("trade_setup") == 1
    assert schema.names[0] == "trade_setup"
    assert schema.indices["trade_setup"] == 0
    assert schema.to_dict()["trade_setup_category_count"] == TRADE_SETUP_CATEGORY_COUNT
