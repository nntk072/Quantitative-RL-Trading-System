from __future__ import annotations

from types import SimpleNamespace

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
    )

    manifest = observation_schema_manifest(env)

    assert manifest is not None
    assert manifest["version"] == "account-state-v1"
    assert manifest["trade_setup_observation"] == trade_setup_observation_schema()


def test_action_schema_has_one_setup_coordinate_and_full_category_catalog() -> None:
    assert TRADE_SETUP_CATEGORY_COUNT == len(TRADE_SETUP_CANDIDATES) == 109
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_multi_tp=True, has_simplex=True)
    assert schema.names.count("trade_setup") == 1
    assert schema.names[0] == "trade_setup"
    assert schema.indices["trade_setup"] == 0
    assert schema.to_dict()["trade_setup_category_count"] == TRADE_SETUP_CATEGORY_COUNT
