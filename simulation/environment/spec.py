"""Small, pickleable description of one bundle-backed environment worker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omegaconf import DictConfig, OmegaConf


@dataclass(frozen=True)
class EnvSpec:
    """Configuration needed to recreate an env without shipping training data."""

    bundle_dir: str
    algo: str
    reward: str
    arch: str
    config: Mapping[str, Any]
    episodic: bool = True
    use_vae: bool = False
    evaluation: bool = False

    @classmethod
    def from_cfg(
        cls,
        cfg: Mapping[str, Any] | DictConfig,
        *,
        algo: str,
        reward: str,
        arch: str,
        bundle_dir: str,
        episodic: bool = True,
        use_vae: bool = False,
        evaluation: bool = False,
    ) -> EnvSpec:
        """Copy resolved config primitives into a compact immutable worker spec.

        Args:
            cfg: Run configuration used by this operation.
            algo: Text or path value identifying the algo.
            reward: Text or path value identifying the reward.
            arch: Text or path value identifying the arch.
            bundle_dir: Text or path value identifying the bundle dir.
            episodic: Whether to enable or require the episodic.
            use_vae: Whether to enable or require the use vae.
            evaluation: Whether to enable or require the evaluation.

        Returns:
            Result of copy resolved config primitives into a compact immutable worker spec.
        """
        raw = OmegaConf.to_container(cfg, resolve=True) if isinstance(cfg, DictConfig) else cfg
        if not isinstance(raw, Mapping):
            raise TypeError("environment config must be a mapping")
        return cls(
            bundle_dir=str(bundle_dir),
            algo=str(algo),
            reward=str(reward),
            arch=str(arch),
            config={str(key): value for key, value in raw.items()},
            episodic=bool(episodic),
            use_vae=bool(use_vae),
            evaluation=bool(evaluation),
        )
