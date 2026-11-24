"""Overlapped PPO collection: rollout k+1 is sampled on a policy snapshot while the learner updates on rollout k.

Data timing: rollout k+1 is sampled with the learner weights from before update k, so update k+1 trains on data
that is exactly one update behind the learner. PPO's importance ratio uses the logged behaviour log-probs, so the
objective stays well defined. The collection loop mirrors SB3's ``OnPolicyAlgorithm.collect_rollouts``, but it
samples from a separate snapshot policy (never the learner's parameters) and runs on the default CUDA stream.
A separate collection stream hung with the CUDA graphs enabled, so collection shares the default stream.

Off by default (``ppo.overlap_collect``). The sequential path is unchanged when the flag is off.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import numpy as np
import torch
from stable_baselines3.common.utils import obs_as_tensor

from learning.rl.rollout_buffer import install_single_copy_add


class OverlapCollector:
    """Owns the snapshot policy, the second rollout buffer, and the one background collection thread."""

    def __init__(self, model: Any, snapshot_model: Any) -> None:
        """Bind the learner to a snapshot model whose policy performs all collection.

        Args:
            model: Learner PPO model (its policy is updated, its env is stepped by the collector).
            snapshot_model: Model built from the same configuration; only its policy is used.
        """
        self.model = model
        self.snapshot_policy = snapshot_model.policy
        # The rollout graph covers the forward; predict_values stays eager (variable batch sizes).
        self.snapshot_policy._feature_graph = None
        self.device = model.device
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="overlap-collect")
        self._spare = self._new_buffer(model.rollout_buffer)
        self._pending: Future[bool] | None = None
        self._pending_buffer: Any = None
        self._obs: Any = None
        self._starts: Any = None
        self.callback: Any = None
        self.train_calls = 0

    @staticmethod
    def _new_buffer(template: Any) -> Any:
        """Create a second buffer with the learner buffer's shape and PPO constants.

        Args:
            template: Learner rollout buffer.

        Returns:
            Empty buffer of the same class.
        """
        fresh = type(template)(
            template.buffer_size,
            template.observation_space,
            template.action_space,
            template.device,
            gae_lambda=template.gae_lambda,
            gamma=template.gamma,
            n_envs=template.n_envs,
        )
        install_single_copy_add(fresh)
        return fresh

    def sync_weights(self) -> None:
        """Copy the learner's current parameters into the snapshot policy, in place."""
        with torch.no_grad():
            for dst, src in zip(
                self.snapshot_policy.parameters(), self.model.policy.parameters(), strict=True
            ):
                dst.copy_(src)

    def _init_state(self) -> None:
        """Start the collector from the learner's current observation, once."""
        if self._obs is None:
            self._obs = self.model._last_obs
            self._starts = self.model._last_episode_starts

    def _collect(self, env: Any, callback: Any, buffer: Any, n_steps: int) -> bool:
        """Fill ``buffer`` with ``n_steps`` vector steps sampled from the snapshot policy.

        Args:
            env: Vector environment (already wrapped by the host mask check when enabled).
            callback: SB3 callback, called per step as in SB3's collector.
            buffer: Rollout buffer to fill.
            n_steps: Steps per environment.

        Returns:
            False if a callback stopped collection early, True otherwise.
        """
        policy = self.snapshot_policy
        model = self.model
        policy.set_training_mode(False)
        policy._collecting_rollout = True
        try:
            obs, starts = self._obs, self._starts
            buffer.reset()
            steps = 0
            new_obs, dones = obs, starts
            while steps < n_steps:
                with torch.no_grad():
                    obs_tensor = obs_as_tensor(obs, self.device)
                    actions, values, log_probs = policy(obs_tensor)
                actions_np = actions.cpu().numpy()
                clipped = np.clip(actions_np, model.action_space.low, model.action_space.high)
                new_obs, rewards, dones, infos = env.step(clipped)
                model.num_timesteps += env.num_envs
                callback.update_locals(locals())
                if not callback.on_step():
                    return False
                model._update_info_buffer(infos, dones)
                steps += 1
                for idx, done in enumerate(dones):
                    if (
                        done
                        and infos[idx].get("terminal_observation") is not None
                        and infos[idx].get("TimeLimit.truncated", False)
                    ):
                        terminal_obs = policy.obs_to_tensor(infos[idx]["terminal_observation"])[0]
                        with torch.no_grad():
                            terminal_value = policy.predict_values(terminal_obs)[0]
                        rewards[idx] += model.gamma * terminal_value
                buffer.add(obs, actions_np, rewards, starts, values, log_probs)
                obs, starts = new_obs, dones
            with torch.no_grad():
                last_values = policy.predict_values(obs_as_tensor(new_obs, self.device))
            buffer.compute_returns_and_advantage(last_values=last_values, dones=dones)
            self._obs, self._starts = new_obs, dones
            callback.update_locals(locals())
            return True
        finally:
            policy._collecting_rollout = False

    def collect_sync(self, env: Any, callback: Any, buffer: Any, n_steps: int) -> bool:
        """Collect on the calling thread, used for the first rollouts before overlap starts.

        Args:
            env: Vector environment.
            callback: SB3 callback.
            buffer: Buffer to fill.
            n_steps: Steps per environment.

        Returns:
            Whether collection completed.
        """
        self.sync_weights()
        self._init_state()
        callback.on_rollout_start()
        ok = self._collect(env, callback, buffer, n_steps)
        if ok:
            callback.on_rollout_end()
        return ok

    def submit(self, env: Any, callback: Any, n_steps: int) -> None:
        """Start collecting the next rollout in the background, into the spare buffer.

        Args:
            env: Vector environment.
            callback: SB3 callback.
            n_steps: Steps per environment.
        """
        if self._pending is not None:
            raise RuntimeError("a background collection is already pending")
        self.sync_weights()
        self._init_state()
        target = self._spare

        def job() -> bool:
            """Collect the next rollout on the background thread.

            Returns:
                Whether the background collection completed.
            """
            callback.on_rollout_start()
            ok = self._collect(env, callback, target, n_steps)
            return ok

        self._pending_buffer = target
        self._pending = self._executor.submit(job)

    def take(self) -> bool:
        """Wait for the background rollout and make it the learner's buffer.

        Returns:
            Whether the background collection completed.
        """
        if self._pending is None:
            raise RuntimeError("no background collection to take")
        ok = self._pending.result()
        self._pending = None
        if ok:
            previous = self.model.rollout_buffer
            self.model.rollout_buffer = self._pending_buffer
            self._spare = previous
            self.callback.on_rollout_end()
        return ok

    def drain(self) -> None:
        """Wait for any pending background collection so no thread outlives ``learn``."""
        if self._pending is not None:
            self._pending.result()
            self._pending = None


def install_overlap_collect(model: Any, snapshot_model: Any) -> OverlapCollector:
    """Route ``learn`` through the overlapped collector.

    Args:
        model: Learner PPO model.
        snapshot_model: Model built from the same configuration, used only for collection.

    Returns:
        The installed collector.
    """
    collector = OverlapCollector(model, snapshot_model)
    original_learn = model.learn
    original_train = model.train
    state: dict[str, Any] = {"total": None}

    def learn(total_timesteps: int, *args: Any, **kwargs: Any) -> Any:
        """Remember the timestep budget, then run SB3's learn with overlapped collection.

        Args:
            total_timesteps: Timestep budget for this learn call.
            *args: Positional arguments forwarded to SB3's learn.
            **kwargs: Keyword arguments forwarded to SB3's learn.

        Returns:
            The model returned by SB3's learn.
        """
        state["total"] = int(total_timesteps)
        try:
            return original_learn(total_timesteps, *args, **kwargs)
        finally:
            collector.drain()

    def collect_rollouts(
        env: Any, callback: Any, rollout_buffer: Any, n_rollout_steps: int
    ) -> bool:
        """Take the pending rollout, or collect synchronously for the first ones.

        Args:
            env: Vector environment.
            callback: SB3 callback.
            rollout_buffer: Buffer SB3 expects to fill when collecting synchronously.
            n_rollout_steps: Steps per environment.

        Returns:
            Whether collection completed.
        """
        collector.callback = callback
        if collector._pending is not None:
            return collector.take()
        return collector.collect_sync(env, callback, rollout_buffer, n_rollout_steps)

    def train() -> None:
        """Start the next rollout's collection, then run the learner's update.

        Returns:
            None.
        """
        if collector.train_calls >= 1:
            remaining = (state["total"] or 0) - model.num_timesteps
            if remaining >= model.n_steps * model.env.num_envs:
                collector.submit(model.env, collector.callback, model.n_steps)
        collector.train_calls += 1
        original_train()

    model.learn = learn
    model.collect_rollouts = collect_rollouts
    model.train = train
    return collector


__all__: list[str] = ["OverlapCollector", "install_overlap_collect"]
