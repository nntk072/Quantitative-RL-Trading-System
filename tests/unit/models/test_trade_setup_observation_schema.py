from __future__ import annotations

from types import SimpleNamespace

import pytest

from decisioning.trade_setup import (
    LEGACY_THESIS_ACTION_VERSION,
    TRADE_SETUP_ACTION_VERSION,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    build_legacy_thesis_action_schema,
    build_trade_setup_action_schema,
    legacy_thesis_observation_schema,
    trade_setup_candidate,
    trade_setup_observation_schema,
    translate_legacy_thesis_action_schema,
    translate_legacy_thesis_observation_schema,
    validate_thesis_observation_schema,
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
    )

    manifest = observation_schema_manifest(env)

    assert manifest is not None
    assert manifest["version"] == "account-state-v1"
    assert manifest["trade_setup_observation"] == trade_setup_observation_schema()


def test_legacy_thesis_observation_metadata_remains_exact_and_readable() -> None:
    expected = legacy_thesis_observation_schema()
    validate_thesis_observation_schema(expected, expected)
    with pytest.raises(ValueError, match="thesis observation schema"):
        validate_thesis_observation_schema(trade_setup_observation_schema(), expected)
    assert translate_legacy_thesis_observation_schema(expected) == trade_setup_observation_schema()


def test_109_candidate_ids_and_action_coordinates_are_unchanged_by_name_migration() -> None:
    assert TRADE_SETUP_CATEGORY_COUNT == len(TRADE_SETUP_CANDIDATES) == 109
    assert trade_setup_candidate(0).is_no_trade
    legacy = build_legacy_thesis_action_schema(
        has_sl_mode=True, has_multi_tp=True, has_simplex=True
    )
    canonical = build_trade_setup_action_schema(
        has_sl_mode=True, has_multi_tp=True, has_simplex=True
    )
    assert legacy.version == LEGACY_THESIS_ACTION_VERSION
    assert canonical.version == TRADE_SETUP_ACTION_VERSION
    assert legacy.width == canonical.width
    assert legacy.names[1:] == canonical.names[1:]
    assert legacy.indices["thesis"] == canonical.indices["trade_setup"] == 0
    assert translate_legacy_thesis_action_schema(legacy.to_dict()) == canonical.to_dict()
