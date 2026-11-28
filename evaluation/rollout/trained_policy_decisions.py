"""Action adaptation and decision-trace serialization for policy rollouts."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from numpy.typing import NDArray


def _setup_choice_probability_summary(
    raw_probabilities: Any, eligibility_mask: NDArray[np.float32], selected_id: int
) -> dict[str, float | int | None]:
    """Summarize one masked setup distribution without retaining its full vector.

    Args:
        raw_probabilities: Policy probabilities over setup candidates.
        eligibility_mask: Boolean-like mask identifying valid setup choices.
        selected_id: Setup ID selected by the evaluated policy action.

    Returns:
        Selected, no-trade, and maximum eligible probabilities with candidate identity.
    """
    names = (
        "trade_setup_selected_probability",
        "trade_setup_no_trade_probability",
        "trade_setup_max_trade_probability",
        "trade_setup_max_trade_candidate_id",
    )
    if raw_probabilities is None:
        return {name: None for name in names}

    values = raw_probabilities
    if hasattr(values, "detach"):
        values = values.detach().cpu().numpy()
    probabilities = np.asarray(values, dtype=np.float64)
    if probabilities.ndim == 2 and probabilities.shape[0] == 1:
        probabilities = probabilities[0]
    mask = np.asarray(eligibility_mask, dtype=np.float32).reshape(-1)
    if probabilities.shape != mask.shape:
        raise RuntimeError("setup probabilities must match the current eligibility mask")
    if not np.isfinite(probabilities).all() or np.any(probabilities < 0.0):
        raise RuntimeError("setup probabilities must be finite and non-negative")
    if not np.isclose(float(probabilities.sum()), 1.0, atol=1e-5, rtol=1e-5):
        raise RuntimeError("setup probabilities must sum to one")

    from decisioning.trade_setup import NO_TRADE_ID

    if not 0 <= selected_id < len(probabilities):
        raise RuntimeError("selected setup ID is outside the probability vector")
    eligible_trade_ids = np.flatnonzero(mask > 0.0)
    eligible_trade_ids = eligible_trade_ids[eligible_trade_ids != NO_TRADE_ID]
    if eligible_trade_ids.size:
        max_offset = int(np.argmax(probabilities[eligible_trade_ids]))
        max_candidate_id: int | None = int(eligible_trade_ids[max_offset])
        max_probability: float | None = float(probabilities[max_candidate_id])
    else:
        max_candidate_id = None
        max_probability = None
    return {
        "trade_setup_selected_probability": float(probabilities[selected_id]),
        "trade_setup_no_trade_probability": float(probabilities[NO_TRADE_ID]),
        "trade_setup_max_trade_probability": max_probability,
        "trade_setup_max_trade_candidate_id": max_candidate_id,
    }


def _candidate_geometry_action_trace(
    observation: dict[str, Any], selected_id: int, info: dict[str, Any]
) -> dict[str, Any]:
    """Serialize the selected candidate geometry and decoded action for one decision.

    Args:
        observation: The exact pre-step observation supplied to the policy.
        selected_id: Setup ID decoded from the policy action.
        info: Environment transition record for the same action.

    Returns:
        Versioned, JSON-safe candidate slot, geometry snapshot, and decoded intent.
    """
    from decisioning.trade_setup import (
        CANDIDATE_GEOMETRY_FEATURE_NAMES,
        CANDIDATE_GEOMETRY_FEATURE_VERSION,
        NO_TRADE_ID,
        TRADE_SETUP_SCHEMA_VERSION,
        candidate_geometry_observation_schema,
        candidate_geometry_slot,
        candidate_geometry_slot_count,
        candidate_geometry_slot_semantics,
    )

    required = ("candidate_ids", "candidate_features", "candidate_mask")
    missing = [key for key in required if key not in observation]
    if missing:
        raise RuntimeError(f"candidate-geometry rollout observation is missing keys: {missing}")
    schema = candidate_geometry_observation_schema()
    raw_candidate_ids = np.asarray(observation["candidate_ids"])
    if raw_candidate_ids.dtype not in (np.dtype(np.int32), np.dtype(np.int64)):
        raise RuntimeError("candidate-geometry rollout IDs must use an integer dtype")
    candidate_ids = raw_candidate_ids.astype(np.int64, copy=False).reshape(-1)
    candidate_features = np.asarray(observation["candidate_features"], dtype=np.float64)
    raw_candidate_mask = np.asarray(observation["candidate_mask"])
    if raw_candidate_mask.dtype != np.dtype(np.bool_):
        raise RuntimeError("candidate-geometry rollout mask must use boolean values")
    candidate_mask = raw_candidate_mask.reshape(-1)
    slot_count = candidate_geometry_slot_count()
    expected_shape = (slot_count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES))
    if candidate_ids.shape != (slot_count,):
        raise RuntimeError("candidate-geometry rollout IDs do not match the fixed slot schema")
    expected_ids = np.asarray(
        [candidate_geometry_slot_semantics(index)[0] for index in range(slot_count)],
        dtype=np.int64,
    )
    if not np.array_equal(candidate_ids, expected_ids):
        raise RuntimeError("candidate-geometry rollout IDs disagree with fixed slot semantics")
    if candidate_features.shape != expected_shape:
        raise RuntimeError("candidate-geometry rollout features do not match the fixed schema")
    if candidate_mask.shape != (slot_count,):
        raise RuntimeError("candidate-geometry rollout mask does not match the fixed slot schema")
    if not np.isfinite(candidate_features).all():
        raise RuntimeError("candidate-geometry rollout features must be finite")

    execution_type = str(info.get("execution_type", "market"))
    slot = (
        int(NO_TRADE_ID)
        if selected_id == NO_TRADE_ID
        else candidate_geometry_slot(selected_id, execution_type)
    )
    if not bool(candidate_mask[slot]):
        raise RuntimeError(
            "environment selected a candidate-geometry slot that was masked in the policy observation "
            f"(slot={slot})"
        )
    candidate_id_at_slot = int(candidate_ids[slot])
    if candidate_id_at_slot != selected_id:
        raise RuntimeError(
            "candidate-geometry slot semantics disagree with the selected setup "
            f"(slot={slot}, selected_id={selected_id}, slot_id={candidate_id_at_slot})"
        )
    entry_type = "market" if selected_id == NO_TRADE_ID else execution_type
    selected = candidate_features[slot]
    geometry_snapshot = {
        name: float(selected[index]) for index, name in enumerate(CANDIDATE_GEOMETRY_FEATURE_NAMES)
    }
    action_coordinates = {
        key: float(value)
        for key, value in info.items()
        if (key.startswith("action_") or key.endswith("_u"))
        and isinstance(value, (int, float, np.integer, np.floating))
        and np.isfinite(float(value))
    }
    decoded_action = {
        "schema_version": "candidate-geometry-decoded-action-v1",
        "action_schema_version": str(info.get("trade_setup_action_schema_version", "")),
        "candidate_id": selected_id,
        "entry_type": entry_type,
        "direction": int(info.get("trade_setup_selected_direction", 0)),
        "environment_action": int(info.get("action", 0)),
        "environment_execution_type": execution_type,
        "limit_offset_atr": float(info.get("limit_offset_atr", 0.0)),
        "limit_ttl_bars": int(info.get("limit_ttl_bars", 1)),
        "action_coordinates": action_coordinates,
    }
    return {
        "candidate_geometry_trace_schema_version": "candidate-geometry-action-trace-v1",
        "candidate_schema_version": TRADE_SETUP_SCHEMA_VERSION,
        "candidate_geometry_schema_version": str(schema["version"]),
        "candidate_geometry_feature_schema_version": CANDIDATE_GEOMETRY_FEATURE_VERSION,
        "candidate_geometry_slot": slot,
        "candidate_geometry_setup_id": selected_id,
        "candidate_geometry_entry_type": entry_type,
        "candidate_geometry_snapshot_json": json.dumps(
            geometry_snapshot, sort_keys=True, separators=(",", ":")
        ),
        "candidate_geometry_decoded_action_json": json.dumps(
            decoded_action, sort_keys=True, separators=(",", ":")
        ),
    }


def _pre_action_setup_identity(env: Any, candidate_id: int) -> dict[str, Any]:
    """Resolve setup provenance from the feature row before the environment steps.

    Args:
        env: Environment exposing the current feature row and step index.
        candidate_id: Candidate selected by the current typed decision.

    Returns:
        The selected candidate's event identity, or an explicit empty/status record.
    """
    from decisioning.trade_setup import NO_TRADE_ID
    from features.context.trade_setup_candidates import (
        trade_setup_candidate_event_identities,
        trade_setup_event_identity_record,
    )

    if candidate_id == NO_TRADE_ID:
        return {}
    row_at = getattr(env, "_feature_row_at", None)
    if not callable(row_at):
        return {
            "trade_setup_source_event_id": None,
            "trade_setup_source_event_identity_status": "identity_not_emitted",
            "trade_setup_source_event_times_ns": [],
        }
    identities = trade_setup_candidate_event_identities(
        row_at(int(env.step_idx)), candidate_ids=(candidate_id,)
    )
    if not identities:
        return {
            "trade_setup_source_event_id": None,
            "trade_setup_source_event_identity_status": "candidate_ineligible",
            "trade_setup_source_event_times_ns": [],
        }
    return trade_setup_event_identity_record(identities[0])


def _decision_result_record(model: Any, decision: Any) -> dict[str, Any]:
    """Serialize the typed provider result used to produce one environment action.

    Args:
        model: Provider whose metadata identifies the inference source.
        decision: Typed result returned by that provider inference.

    Returns:
        JSON-compatible provider, action, and schema metadata.
    """
    from decisioning.contracts import ContinuousAction, DiscreteAction, StructuredAction

    action = decision.action
    if isinstance(action, DiscreteAction):
        action_record = {"kind": "discrete", "index": int(action.index), "name": action.name}
    elif isinstance(action, ContinuousAction):
        action_record = {"kind": "continuous", "value": float(action.value)}
    elif isinstance(action, StructuredAction):
        action_record = {
            "kind": "structured",
            "coordinates": {str(name): float(value) for name, value in action.coordinates.items()},
        }
    else:
        raise TypeError(f"unsupported semantic decision action: {type(action).__name__}")
    schema = decision.action_schema
    return {
        "provider_id": str(model.metadata.provider_id),
        "action": action_record,
        "action_schema": {
            "version": schema.version,
            "key": schema.key,
            "kind": schema.kind,
            "coordinates": list(schema.coordinates),
        },
    }


def make_action_fn(
    model: Any,
    continuous_actions: bool = False,
    deterministic: bool = True,
    strategy_actions: bool = False,
    decision_callback: Any = None,
) -> Any:
    """Return an observation → action callable with explicit action typing.

    PPO trains on ``TradingEnv``'s discrete action space, so the policy's
    integer action id is passed through unchanged; SAC trains on the
    continuous Box space and yields a float position-sizing fraction.
    When ``strategy_actions`` is set (PO3 strategy controls), the full float32
    vector is returned so eval matches training.

    A backend-neutral DecisionProvider follows the same rollout path after its
    semantic output is validated and adapted to the environment action shape.

    This is the single shared implementation — ``scripts/train_rl.py`` and
    ``scripts/compare_encoders.py`` used to each carry private copies.

    Args:
        model: Model used for this operation.
        continuous_actions: Whether to enable or require the continuous actions.
        deterministic: Whether to enable or require the deterministic.
        strategy_actions: Whether to enable or require the strategy actions.
        decision_callback: Optional receiver for each typed provider result.

    Returns:
        Result of return an observation → action callable with explicit action typing.
    """
    if hasattr(model, "metadata") and hasattr(model, "predict"):
        from evaluation.rollout.provider import make_provider_action_fn

        return make_provider_action_fn(
            model,
            input_schema_version=model.metadata.input_schema_version,
            deterministic=deterministic,
            continuous_actions=continuous_actions,
            strategy_actions=strategy_actions,
            decision_callback=decision_callback,
        )

    def action_fn(obs: dict[str, Any]) -> Any:
        """Predict one rollout action and adapt it to the configured action shape.

        Args:
            obs: Key-value data used for the obs.

        Returns:
            Result of predict one rollout action and adapt it to the configured action shape.
        """
        action = model.predict(obs, deterministic=deterministic)[0]
        arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if strategy_actions:
            return arr.astype(np.float32, copy=False)
        scalar = arr[0]
        return float(scalar) if continuous_actions else int(scalar)

    return action_fn
