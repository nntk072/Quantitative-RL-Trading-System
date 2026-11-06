"""Checkpoint compatibility operations for the SB3 learning backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from zipfile import ZipFile

import torch
from gymnasium import spaces
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.save_util import json_to_data


def _install_pre_reorganization_checkpoint_modules() -> None:
    """Expose moved class modules while reading checkpoints saved before the package move."""
    import importlib
    import sys
    from types import ModuleType

    legacy_packages = ("quant_rl", "quant_rl.models")
    for name in legacy_packages:
        module = sys.modules.get(name)
        if module is None:
            module = ModuleType(name)
            module.__path__ = []
            sys.modules[name] = module
        parent_name, _, attribute = name.rpartition(".")
        if parent_name:
            setattr(sys.modules[parent_name], attribute, module)

    moved_modules = {
        "quant_rl.models.encoder": "models.encoders.tcn",
        "quant_rl.models.ppo_policy": "learning.rl.ppo",
        "quant_rl.models.rollout_buffer": "learning.rl.rollout_buffer",
    }
    for legacy_name, current_name in moved_modules.items():
        module = importlib.import_module(current_name)
        sys.modules[legacy_name] = module
        parent_name, _, attribute = legacy_name.rpartition(".")
        setattr(sys.modules[parent_name], attribute, module)


def load_sb3_checkpoint(
    path: Path,
    *,
    legacy_layout_key: str | None = None,
    device: Any = "auto",
    algo: str = "ppo",
) -> Any:
    """Load an SB3 checkpoint with only the explicitly selected legacy migration.

    Args:
        path: Path to the input file or directory.
        legacy_layout_key: Legacy layout key used by the operation described above.
        device: Compute device on which to perform the operation.
        algo: Stable-Baselines3 algorithm stored in the checkpoint.

    Returns:
        Result of load an SB3 checkpoint with only the explicitly selected legacy migration.
    """
    _install_pre_reorganization_checkpoint_modules()
    from learning.rl.ppo import LegacyClampedStdMultiInputPolicy
    from models.encoders import LegacyTCNEncoderV1, TCNEncoder

    normalized_algo = str(algo).strip().lower()
    algorithm = {"ppo": PPO, "sac": SAC}.get(normalized_algo)
    if algorithm is None:
        raise ValueError(f"unsupported SB3 checkpoint algorithm: {algo!r}")
    if legacy_layout_key != "legacy4_no_exit_v1":
        return cast(Any, algorithm).load(path, device=device)
    if normalized_algo != "ppo":
        raise ValueError("legacy4_no_exit_v1 migration is supported only for PPO checkpoints")
    with ZipFile(path) as archive:
        if "data" not in archive.namelist():
            raise ValueError(f"legacy checkpoint has no SB3 data record: {path}")
        data = json_to_data(archive.read("data").decode("utf-8"))
    action_space = data.get("action_space")
    if getattr(action_space, "shape", None) != (4,):
        raise ValueError("legacy4_no_exit_v1 requires a saved 4D action space")
    policy_kwargs = data.get("policy_kwargs")
    if not isinstance(policy_kwargs, dict):
        raise ValueError("legacy 4D checkpoint has no readable policy kwargs")
    extractor = policy_kwargs.get("features_extractor_class")
    if extractor not in (TCNEncoder, LegacyTCNEncoderV1):
        raise ValueError("legacy4_no_exit_v1 migration is defined only for the archived TCN family")
    migrated_kwargs = dict(policy_kwargs)
    if extractor is TCNEncoder:
        migrated_kwargs["features_extractor_class"] = LegacyTCNEncoderV1
    return PPO.load(
        path,
        device="cpu",
        custom_objects={
            "policy_class": LegacyClampedStdMultiInputPolicy,
            "policy_kwargs": migrated_kwargs,
        },
    )


def load_sb3_training_checkpoint(path: Path, *, env: Any, device: Any, algo: str = "ppo") -> Any:
    """Resume an SB3 training checkpoint on the caller's prepared environment.

    Args:
        path: Path to the input file or directory.
        env: Environment whose state is read or updated.
        device: Compute device on which to perform the operation.
        algo: Stable-Baselines3 algorithm stored in the checkpoint.

    Returns:
        Result of resume an SB3 training checkpoint on the caller's prepared environment.
    """
    _install_pre_reorganization_checkpoint_modules()
    algorithm = {"ppo": PPO, "sac": SAC}.get(str(algo).strip().lower())
    if algorithm is None:
        raise ValueError(f"unsupported SB3 training checkpoint algorithm: {algo!r}")
    return cast(Any, algorithm).load(path, env=env, device=device)


def seed_sb3(seed: int) -> None:
    """Seed Torch for reproducible stochastic SB3 inference.

    Args:
        seed: Random seed used to make sampling reproducible.
    """
    torch.manual_seed(seed)


def validate_sb3_observation_schema(
    model: Any, expected_schema: Any, *, allow_legacy_v1: bool
) -> None:
    """Validate and bind the expected observation schema on a loaded SB3 model.

    Args:
        model: Loaded policy or algorithm instance.
        expected_schema: Required observation coordinate contract.
        allow_legacy_v1: Permit the explicitly supported legacy schema migration.
    """
    from learning.rl.agent import validate_model_observation_schema

    validate_model_observation_schema(model, expected_schema, allow_legacy_v1=allow_legacy_v1)


def validate_sb3_overlay_action_schema(
    model: Any,
    expected_schema: Any,
    *,
    allow_legacy: bool,
    legacy_layout_key: str | None,
) -> Any:
    """Validate Box overlay metadata and adapt the supported legacy layout.

    Args:
        model: Loaded SB3 model to validate.
        expected_schema: Current overlay-action schema required by the run.
        allow_legacy: Permit an explicitly identified legacy checkpoint.
        legacy_layout_key: Exact legacy layout to accept when migration is enabled.

    Returns:
        The original model or its compatibility adapter.
    """
    from learning.rl.agent import LegacyFourToFiveActionAdapter, validate_model_action_schema

    if not isinstance(getattr(model, "action_space", None), spaces.Box):
        raise ValueError("checkpoint action space must be Box for strategy overlay")
    migration = validate_model_action_schema(
        model,
        expected_schema,
        allow_legacy=allow_legacy,
        legacy_layout_key=legacy_layout_key,
    )
    if migration == "legacy4_no_exit_v1_to_overlay-action-v2-5":
        return LegacyFourToFiveActionAdapter(model)
    return model


def validate_sb3_discrete_action_schema(
    model: Any,
    expected_schema: Any,
    manifest_schema: dict[str, Any] | None,
    *,
    allow_legacy: bool,
    legacy_layout_key: str | None,
) -> None:
    """Validate discrete action-space width and persisted category meanings.

    Args:
        model: Loaded SB3 model to validate.
        expected_schema: Discrete action contract required by the run.
        manifest_schema: Action contract recorded in the source run manifest.
        allow_legacy: Permit the explicit legacy-checkpoint path.
        legacy_layout_key: Exact legacy layout key required for that path.
    """
    from learning.rl.agent import validate_model_discrete_action_schema

    if not isinstance(getattr(model, "action_space", None), spaces.Discrete):
        raise ValueError("checkpoint must use a Discrete action space")
    validate_model_discrete_action_schema(
        model,
        expected_schema,
        manifest_schema,
        allow_legacy=allow_legacy,
        legacy_layout_key=legacy_layout_key,
    )


def is_sb3_box_model(model: Any) -> bool:
    """Return whether a loaded SB3 model declares a Box action space.

    Args:
        model: Model used for this operation.

    Returns:
        Whether is sb3 box model meets the requested condition.
    """
    return isinstance(getattr(model, "action_space", None), spaces.Box)


def is_sb3_discrete_model(model: Any) -> bool:
    """Return whether a loaded SB3 model declares a Discrete action space.

    Args:
        model: Model used for this operation.

    Returns:
        Whether is sb3 discrete model meets the requested condition.
    """
    return isinstance(getattr(model, "action_space", None), spaces.Discrete)


__all__ = [
    "is_sb3_box_model",
    "is_sb3_discrete_model",
    "load_sb3_checkpoint",
    "load_sb3_training_checkpoint",
    "seed_sb3",
    "validate_sb3_discrete_action_schema",
    "validate_sb3_observation_schema",
    "validate_sb3_overlay_action_schema",
]
