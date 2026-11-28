"""Checkpoint action schemas fail closed and record explicit legacy migrations."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from gymnasium import spaces

from decisioning.actions import (
    build_action_schema,
    build_discrete_trading_action_schema,
)
from decisioning.observations import OBSERVATION_SCHEMA_V2, build_observation_schema
from decisioning.trade_setup import build_trade_setup_action_schema
from learning.rl.agent import (
    validate_model_action_schema,
    validate_model_discrete_action_schema,
    validate_model_observation_schema,
)
from learning.rl.agent_contracts import (
    persist_action_schema,
    validate_model_trade_setup_observation_schema,
)
from learning.rl.agent_contracts import (
    validate_model_action_schema as validate_contract_action_schema,
)
from learning.rl.agent_contracts import (
    validate_model_discrete_action_schema as validate_contract_discrete_action_schema,
)


def _continuous_model(width: int, **metadata: Any) -> Any:
    return SimpleNamespace(
        action_space=spaces.Box(-1.0, 1.0, (width,)),
        policy=SimpleNamespace(),
        **metadata,
    )


def test_legacy_action_checkpoint_requires_opt_in_and_explicit_layout() -> None:
    schema = build_action_schema()
    model = _continuous_model(schema.width)

    with pytest.raises(ValueError, match="explicit legacy opt-in"):
        validate_model_action_schema(model, schema)
    with pytest.raises(ValueError, match="explicit legacy layout key"):
        validate_model_action_schema(model, schema, allow_legacy=True)
    with pytest.raises(ValueError, match="differs from expected"):
        validate_model_action_schema(model, schema, allow_legacy=True, legacy_layout_key="6_dir")


def test_legacy_four_coordinate_checkpoint_records_the_documented_migration() -> None:
    schema = build_action_schema()
    model = _continuous_model(4)

    migration = validate_model_action_schema(
        model,
        schema,
        allow_legacy=True,
        legacy_layout_key="legacy4_no_exit_v1",
    )

    assert migration == "legacy4_no_exit_v1_to_overlay-action-v2-5"
    assert model._action_schema["checkpoint_metadata"] == "legacy_unversioned"
    assert model._action_schema["migration"] == migration
    assert model.policy._action_schema == model._action_schema


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (
            {"_action_schema_version": "old", "_action_layout_key": "5"},
            r"action schema version .* differs from",
        ),
        (
            {"_action_schema_version": "overlay-action-v2", "_action_layout_key": "6_dir"},
            "layout.*differs",
        ),
    ],
)
def test_versioned_continuous_checkpoint_rejects_mismatched_schema_metadata(
    metadata: dict[str, str], message: str
) -> None:
    schema = build_action_schema()
    model = _continuous_model(schema.width, **metadata)

    with pytest.raises(ValueError, match=message):
        validate_model_action_schema(model, schema)


def test_versioned_continuous_checkpoint_restores_policy_layout_metadata() -> None:
    schema = build_action_schema()
    model = _continuous_model(
        schema.width,
        _action_schema_version=schema.version,
        _action_layout_key=schema.key,
    )

    assert validate_model_action_schema(model, schema) is None
    assert model.policy._action_schema_version == schema.version
    assert model.policy._action_layout_key == schema.key


def test_discrete_legacy_schema_needs_exact_layout_opt_in_and_is_labeled() -> None:
    schema = build_discrete_trading_action_schema()
    model = SimpleNamespace(action_space=spaces.Discrete(schema.width), policy=SimpleNamespace())

    with pytest.raises(ValueError, match="exact discrete layout key"):
        validate_model_discrete_action_schema(model, schema, source_schema=None)

    disposition = validate_model_discrete_action_schema(
        model,
        schema,
        source_schema=None,
        allow_legacy=True,
        legacy_layout_key=schema.key,
    )

    assert disposition == "legacy_unverified"
    assert model._action_schema["checkpoint_metadata"] == disposition
    assert model.policy._action_schema == model._action_schema


def test_discrete_schema_rejects_checkpoint_with_wrong_action_count() -> None:
    schema = build_discrete_trading_action_schema()
    model = SimpleNamespace(action_space=spaces.Discrete(schema.width - 1), policy=None)

    with pytest.raises(ValueError, match="discrete action count disagrees"):
        validate_model_discrete_action_schema(model, schema, source_schema=schema.to_dict())


def test_observation_checkpoint_schema_is_required_and_restored_after_validation() -> None:
    schema = build_observation_schema(OBSERVATION_SCHEMA_V2)
    model = SimpleNamespace(_observation_schema=schema.to_dict())

    validate_model_observation_schema(model, schema)

    assert model._observation_schema == schema.to_dict()
    with pytest.raises(ValueError, match="observation schema differs"):
        validate_model_observation_schema(
            SimpleNamespace(_observation_schema={"version": OBSERVATION_SCHEMA_V2}), schema
        )


def test_action_contract_rejects_incompatible_legacy_and_checkpoint_metadata() -> None:
    schema = build_action_schema()

    action_space: spaces.Space[Any] = spaces.Discrete(3)
    with pytest.raises(ValueError, match="declared categorical action schema"):
        persist_action_schema(
            SimpleNamespace(action_space=action_space, policy=None),
            SimpleNamespace(action_space=action_space),
        )

    with pytest.raises(ValueError, match="legacy action layout .* differs"):
        validate_model_action_schema(
            _continuous_model(schema.width, _action_layout_key="6_dir"),
            schema,
            allow_legacy=True,
            legacy_layout_key=schema.key,
        )

    with pytest.raises(ValueError, match="trade-setup action checkpoints require versioned"):
        setup_schema = build_trade_setup_action_schema()
        validate_model_action_schema(
            _continuous_model(setup_schema.width),
            setup_schema,
            allow_legacy=True,
            legacy_layout_key=setup_schema.key,
        )

    with pytest.raises(ValueError, match="legacy4_no_exit_v1 requires a 4D checkpoint"):
        validate_contract_action_schema(
            _continuous_model(schema.width),
            schema,
            allow_legacy=True,
            legacy_layout_key="legacy4_no_exit_v1",
        )

    with pytest.raises(ValueError, match="legacy action width"):
        validate_contract_action_schema(
            _continuous_model(schema.width - 1),
            schema,
            allow_legacy=True,
            legacy_layout_key=schema.key,
        )

    with pytest.raises(ValueError, match="checkpoint action width"):
        validate_model_action_schema(
            _continuous_model(
                schema.width - 1,
                _action_schema_version=schema.version,
                _action_layout_key=schema.key,
            ),
            schema,
        )

    with pytest.raises(ValueError, match="action schema version .* differs"):
        validate_model_action_schema(
            _continuous_model(
                schema.width,
                _action_schema_version="old",
                _action_layout_key=schema.key,
            ),
            schema,
        )

    with pytest.raises(ValueError, match="trade setup observation schema differs"):
        validate_model_trade_setup_observation_schema(
            SimpleNamespace(_trade_setup_observation_schema={"version": "old"}), {"version": "new"}
        )


def test_action_schema_can_be_restored_from_compatibility_policy_metadata() -> None:
    schema = build_action_schema()
    model = _continuous_model(schema.width)
    model.policy._action_schema_version = schema.version
    model.policy._action_layout_key = schema.key

    assert validate_contract_action_schema(model, schema) is None
    assert model.policy._action_schema_version == schema.version
    assert model.policy._action_layout_key == schema.key
    assert model._action_schema["checkpoint_metadata"] == "versioned"


def test_discrete_checkpoint_requires_matching_run_manifest_and_metadata() -> None:
    schema = build_discrete_trading_action_schema()
    action_space: spaces.Space[Any] = spaces.Discrete(schema.width)
    conflicting_manifest = schema.to_dict()
    conflicting_manifest["key"] = "other-layout"
    valid_metadata = {
        "_action_schema_version": schema.version,
        "_action_layout_key": schema.key,
        "_action_schema": schema.to_dict(),
    }

    with pytest.raises(ValueError, match="source run manifest discrete action schema differs"):
        validate_contract_discrete_action_schema(
            SimpleNamespace(action_space=action_space, **valid_metadata),
            schema,
            source_schema=conflicting_manifest,
        )

    with pytest.raises(ValueError, match="unversioned discrete action checkpoint"):
        validate_contract_discrete_action_schema(
            SimpleNamespace(action_space=action_space, policy=None),
            schema,
            source_schema=schema.to_dict(),
        )

    with pytest.raises(ValueError, match="checkpoint discrete action schema differs"):
        validate_contract_discrete_action_schema(
            SimpleNamespace(
                action_space=action_space,
                _action_schema_version="old",
                _action_layout_key=schema.key,
                _action_schema=schema.to_dict(),
            ),
            schema,
            source_schema=schema.to_dict(),
        )

    assert (
        validate_contract_discrete_action_schema(
            SimpleNamespace(action_space=action_space, policy=SimpleNamespace(), **valid_metadata),
            schema,
            source_schema=schema.to_dict(),
        )
        == "verified"
    )
