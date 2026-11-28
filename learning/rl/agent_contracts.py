"""Action and observation schema contracts for RL checkpoints and policies."""

from __future__ import annotations

from typing import Any

from gymnasium import spaces

from decisioning.actions import SCHEMA_VERSION, ActionSchema, DiscreteActionSchema
from decisioning.trade_setup import (
    TradeSetupActionSchema,
    validate_candidate_geometry_observation_schema,
    validate_trade_setup_observation_schema,
)
from learning.rl.ppo import _layout_key


def bind_discrete_action_schema(model: Any, schema: DiscreteActionSchema) -> None:
    """Persist a categorical schema on both SB3 model and policy metadata.

    Args:
        model: Model used for this operation.
        schema: Schema used by the operation described above.
    """
    action_space = getattr(model, "action_space", None)
    if not isinstance(action_space, spaces.Discrete) or action_space.n != schema.width:
        raise ValueError("discrete action schema width differs from the model action space")
    manifest = schema.to_dict()
    model._action_schema_version = schema.version
    model._action_layout_key = schema.key
    model._action_schema = manifest
    policy = getattr(model, "policy", None)
    if policy is not None:
        policy._action_schema_version = schema.version
        policy._action_layout_key = schema.key
        policy._action_schema = manifest


def persist_action_schema(model: Any, env: Any) -> None:
    """Persist the environment's action semantics on an SB3 model and policy.

    Args:
        model: Model used for this operation.
        env: Environment whose state is read or updated.
    """
    action_space = env.action_space
    policy = getattr(model, "policy", None)
    if isinstance(action_space, spaces.Box):
        width = int(action_space.shape[0])
        schema = getattr(env, "action_schema", None)
        if isinstance(schema, (ActionSchema, TradeSetupActionSchema)):
            if width != schema.width:
                raise ValueError(
                    f"action space width {width} disagrees with declared schema width "
                    f"{schema.width}"
                )
            layout_key = schema.key
            schema_manifest = schema.to_dict()
        elif width == 1 and not bool(getattr(env, "strategy_actions", False)):
            # The scalar Box belongs to the continuous directional action mode,
            # not to the strategy-overlay coordinate schema.
            layout_key = _layout_key(width)
            schema_manifest = None
        else:
            raise ValueError(
                "Box strategy actions require a declarative ActionSchema; "
                "action width alone cannot identify coordinate meanings"
            )

        model._action_layout_key = layout_key
        schema_version = schema.version if schema is not None else SCHEMA_VERSION
        model._action_schema_version = schema_version
        if policy is not None:
            policy._action_layout_key = layout_key
            policy._action_schema_version = schema_version
        if schema_manifest is not None:
            model._action_schema = schema_manifest
            if policy is not None:
                policy._action_schema = schema_manifest
    elif isinstance(action_space, spaces.Discrete):
        schema = getattr(env, "action_schema", None)
        if not isinstance(schema, DiscreteActionSchema):
            raise ValueError(
                "discrete trading actions require a declared categorical action schema"
            )
        bind_discrete_action_schema(model, schema)


def validate_model_action_schema(
    model: Any,
    expected_schema: ActionSchema | TradeSetupActionSchema,
    *,
    allow_legacy: bool = False,
    legacy_layout_key: str | None = None,
) -> str | None:
    """Validate action semantics before using a checkpoint for evaluation.

    SB3 reconstructs the policy when loading, so its constructor default key
    cannot prove the saved layout. Versioned metadata belongs on the PPO model
    (included in SB3's serialized model data). Unversioned checkpoints require
    an explicit legacy opt-in plus an explicit layout selection. Width alone
    cannot distinguish layouts such as ``6_dir`` and ``6_sl``. The one
    supported width migration is the documented 4D no-exit layout to the
    current 5D base layout, with a structural-exit coordinate appended at
    inference time.

    Args:
        model: Model used for this operation.
        expected_schema: Expected schema used by the operation described above.
        allow_legacy: Whether to enable or require the allow legacy.
        legacy_layout_key: Legacy layout key used by the operation described above.

    Returns:
        Result of validate action semantics before using a checkpoint for evaluation.
    """
    shape = getattr(getattr(model, "action_space", None), "shape", None)
    actual_width = int(shape[0]) if shape and len(shape) == 1 else None
    policy = getattr(model, "policy", None)
    version = getattr(model, "_action_schema_version", None)
    layout = getattr(model, "_action_layout_key", None)
    # Accept policy-only metadata from lightweight compatibility adapters;
    # a freshly reconstructed SB3 policy's default key has no version and is
    # therefore never trusted as proof of its original layout.
    if version is None:
        version = getattr(policy, "_action_schema_version", None)
        if version is not None and layout is None:
            layout = getattr(policy, "_action_layout_key", None)

    if version is None:
        if not allow_legacy:
            raise ValueError("unversioned action checkpoint needs explicit legacy opt-in")
        if legacy_layout_key is None:
            raise ValueError("unversioned action checkpoint needs an explicit legacy layout key")
        if layout is not None and layout != expected_schema.key:
            raise ValueError(
                f"legacy action layout {layout!r} differs from {expected_schema.key!r}"
            )
        migration: str | None = None
        if isinstance(expected_schema, TradeSetupActionSchema):
            raise ValueError("trade-setup action checkpoints require versioned schema metadata")
        if legacy_layout_key == "legacy4_no_exit_v1":
            if actual_width != 4 or expected_schema.key != "5":
                raise ValueError(
                    "legacy4_no_exit_v1 requires a 4D checkpoint and the current 5D base layout"
                )
            migration = "legacy4_no_exit_v1_to_overlay-action-v2-5"
        elif legacy_layout_key != expected_schema.key:
            raise ValueError(
                f"explicit legacy layout {legacy_layout_key!r} differs from "
                f"expected {expected_schema.key!r}"
            )
        elif actual_width != expected_schema.width:
            raise ValueError(
                f"legacy action width {actual_width} disagrees with "
                f"selected layout {legacy_layout_key!r} width {expected_schema.width}"
            )
        manifest = expected_schema.to_dict()
        manifest["checkpoint_metadata"] = "legacy_unversioned"
        manifest["legacy_layout_key"] = legacy_layout_key
        manifest["migration"] = migration
        model._action_schema = manifest
        if policy is not None:
            policy._action_schema = manifest
        return migration

    if actual_width != expected_schema.width:
        raise ValueError(
            f"checkpoint action width {actual_width} disagrees with "
            f"expected width {expected_schema.width}"
        )

    if version != expected_schema.version:
        raise ValueError(
            f"action schema version {version!r} differs from {expected_schema.version!r}"
        )
    if layout != expected_schema.key:
        raise ValueError(f"action layout {layout!r} differs from {expected_schema.key!r}")
        # The policy rebuilt by SB3 starts with a constructor default. Restore
        # the validated layout for correct mode-prior coordinates after loading.
    if policy is not None:
        policy._action_layout_key = layout
        policy._action_schema_version = version
        # The validated decoder contract is useful to dashboards and exports;
        # it does not change the serialized policy's action coordinates.
    manifest = expected_schema.to_dict()
    manifest["checkpoint_metadata"] = "versioned"
    model._action_schema = manifest
    if policy is not None:
        policy._action_schema = manifest
    return None


def validate_model_discrete_action_schema(
    model: Any,
    expected_schema: DiscreteActionSchema,
    source_schema: dict[str, Any] | None,
    *,
    allow_legacy: bool = False,
    legacy_layout_key: str | None = None,
) -> str:
    """Validate the ordered categorical action meaning for a discrete checkpoint.

    Args:
        model: Model used for this operation.
        expected_schema: Expected schema used by the operation described above.
        source_schema: Key-value data used for the source schema.
        allow_legacy: Whether to enable or require the allow legacy.
        legacy_layout_key: Legacy layout key used by the operation described above.

    Returns:
        Text returned by ``validate_model_discrete_action_schema``.
    """
    action_space = getattr(model, "action_space", None)
    if not isinstance(action_space, spaces.Discrete) or action_space.n != expected_schema.width:
        actual_n = getattr(action_space, "n", None)
        raise ValueError(
            "checkpoint discrete action count disagrees with the run schema: "
            f"checkpoint={actual_n}, expected={expected_schema.width}"
        )

    expected = expected_schema.to_dict()
    if source_schema is None:
        if not allow_legacy or legacy_layout_key != expected_schema.key:
            raise ValueError(
                "source run manifest lacks the discrete action schema; explicit legacy opt-in "
                "and the exact discrete layout key are required"
            )
        disposition = "legacy_unverified"
    elif source_schema != expected:
        raise ValueError("source run manifest discrete action schema differs from the run config")
    else:
        disposition = "verified"

    version = getattr(model, "_action_schema_version", None)
    layout_key = getattr(model, "_action_layout_key", None)
    checkpoint_schema = getattr(model, "_action_schema", None)
    policy = getattr(model, "policy", None)
    if version is None and checkpoint_schema is None:
        if not allow_legacy or legacy_layout_key != expected_schema.key:
            raise ValueError(
                "unversioned discrete action checkpoint needs explicit legacy opt-in "
                "and the exact discrete layout key"
            )
        disposition = "legacy_unverified"
    elif (
        version != expected_schema.version
        or layout_key != expected_schema.key
        or checkpoint_schema != expected
    ):
        raise ValueError("checkpoint discrete action schema differs from the run config")

    manifest = dict(expected)
    manifest["checkpoint_metadata"] = (
        "versioned" if disposition == "verified" else "legacy_unverified"
    )
    bind_discrete_action_schema(model, expected_schema)
    model._action_schema = manifest
    if policy is not None:
        policy._action_schema = manifest
    return disposition


def validate_model_observation_schema(
    model: Any,
    expected_schema: Any,
    *,
    allow_legacy_v1: bool = False,
) -> None:
    """Reject checkpoints whose account-state coordinate meanings differ.

    Args:
        model: Model used for this operation.
        expected_schema: Expected schema used by the operation described above.
        allow_legacy_v1: Whether to enable or require the allow legacy v1.
    """
    from decisioning.observations import validate_observation_schema

    actual = getattr(model, "_observation_schema", None)
    validate_observation_schema(actual, expected_schema, allow_legacy_v1=allow_legacy_v1)
    model._observation_schema = expected_schema.to_dict()


def validate_model_trade_setup_observation_schema(
    model: Any, expected_schema: dict[str, Any] | None
) -> None:
    """Validate the checkpoint's canonical trade-setup mask metadata.

    Args:
        model: Model used for this operation.
        expected_schema: Key-value data used for the expected schema.
    """
    actual = getattr(model, "_trade_setup_observation_schema", None)
    validate_trade_setup_observation_schema(actual, expected_schema)


def validate_model_candidate_geometry_observation_schema(
    model: Any, expected_schema: dict[str, Any] | None
) -> None:
    """Validate checkpoint metadata for the price-aware candidate observation.

    Args:
        model: Loaded model carrying the persisted candidate schema.
        expected_schema: Candidate schema required by the configured environment.
    """
    actual = getattr(model, "_candidate_geometry_observation_schema", None)
    validate_candidate_geometry_observation_schema(actual, expected_schema)


__all__ = [
    "bind_discrete_action_schema",
    "persist_action_schema",
    "validate_model_action_schema",
    "validate_model_candidate_geometry_observation_schema",
    "validate_model_discrete_action_schema",
    "validate_model_observation_schema",
    "validate_model_trade_setup_observation_schema",
]
