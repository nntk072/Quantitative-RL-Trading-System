"""Host-side eligibility check on the training vector env, so rollouts need no device sync.

The trade-setup eligibility mask is validated on every observation batch the vector env
returns, before the policy can read it. That is the same condition the per-call device check
enforces, performed on numpy data with no GPU synchronisation. The rollout collector then runs
with the per-call device check relaxed, and only for this environment.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import numpy as np
from stable_baselines3.common.vec_env.base_vec_env import VecEnv, VecEnvWrapper

from learning.rl.hybrid import _trade_setup_logits_width, masks_prevalidated


class EligibilityCheckedVecEnv(VecEnvWrapper):
    """Pass-through vector env that fails closed on a bad trade-setup eligibility mask."""

    def __init__(self, venv: VecEnv, mask_key: str, logits_width: int) -> None:
        """Wrap ``venv`` and record which observation key and width to check.

        Args:
            venv: Vector environment whose observations feed the policy.
            mask_key: Observation key holding the trade-setup eligibility mask.
            logits_width: Number of trade-setup categories the mask must cover.
        """
        super().__init__(venv)
        self._mask_key = mask_key
        self._logits_width = int(logits_width)

    def reset(self) -> Any:
        """Reset the wrapped environments and check the first observations.

        Returns:
            Observations from the wrapped environment.
        """
        obs = self.venv.reset()
        self._check(obs)
        return obs

    def step_async(self, actions: np.ndarray[Any, Any]) -> None:
        """Forward actions to the wrapped environment.

        Args:
            actions: Actions for every environment.
        """
        self.venv.step_async(actions)

    def step_wait(self) -> Any:
        """Collect the step results and check the observations they carry.

        Returns:
            Step results from the wrapped environment.
        """
        obs, rewards, dones, infos = self.venv.step_wait()
        self._check(obs)
        return obs, rewards, dones, infos

    def _check(self, obs: Any) -> None:
        """Raise when a mask is non-finite or leaves a row with no eligible category.

        Args:
            obs: Observation dict from the wrapped environment.

        Raises:
            ValueError: If the mask is non-finite, has the wrong width, or has an empty row.
        """
        mask = np.asarray(obs[self._mask_key])
        if not np.isfinite(mask).all():
            raise ValueError("setup eligibility mask must contain only finite values")
        if mask.shape[-1] != self._logits_width or not (mask > 0.0).any(axis=-1).all():
            raise ValueError("setup eligibility mask must match logits and allow a category")


def install_host_mask_check(model: Any) -> None:
    """Check trade-setup masks on the host and relax the per-call device check in rollouts.

    Args:
        model: PPO model whose policy is the trade-setup conditioned policy.

    Raises:
        ValueError: If the policy does not expose a trade-setup mask contract.
    """
    policy = model.policy
    if not callable(getattr(policy, "validate_rollout_masks", None)) or not hasattr(
        policy, "trade_setup_mask_key"
    ):
        raise ValueError("ppo.rollout_host_mask_check requires the trade-setup policy")
    width = _trade_setup_logits_width(policy.action_net)
    model.env = EligibilityCheckedVecEnv(model.env, policy.trade_setup_mask_key, width)
    model.collect_rollouts = _prevalidated(model.collect_rollouts, policy)


def _prevalidated(collect: Callable[..., Any], policy: Any) -> Callable[..., Any]:
    """Run a rollout collection with the per-call device mask check relaxed.

    Args:
        collect: Original ``collect_rollouts`` bound method.
        policy: Policy whose rollout forward may be replayed from a graph during collection.

    Returns:
        Wrapped collector.
    """

    def _collect(*args: Any, **kwargs: Any) -> Any:
        """Collect a rollout under the prevalidated-mask context.

        Args:
            *args: Positional arguments for ``collect_rollouts``.
            **kwargs: Keyword arguments for ``collect_rollouts``.

        Returns:
            Whatever ``collect_rollouts`` returns.
        """
        policy._collecting_rollout = True
        try:
            with _no_device_mask_check():
                return collect(*args, **kwargs)
        finally:
            policy._collecting_rollout = False

    return _collect


@contextmanager
def _no_device_mask_check() -> Iterator[None]:
    """Enter the prevalidated-mask context; the host check covers these observations.

    Yields:
        Control returns to the caller inside the context.
    """
    with masks_prevalidated():
        yield


__all__ = ["EligibilityCheckedVecEnv", "install_host_mask_check"]
