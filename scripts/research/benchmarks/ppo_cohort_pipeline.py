"""Inference/CPU-step overlap probe for one on-policy PPO rollout."""

from __future__ import annotations

import time
from contextlib import AbstractContextManager
from multiprocessing.connection import Connection
from types import TracebackType
from typing import Any

import numpy as np


class ParentIPCProbe(AbstractContextManager["ParentIPCProbe"]):
    """Count serialized pipe transport bytes and time on the PPO parent process."""

    def __init__(self) -> None:
        self.send_bytes = 0
        self.recv_bytes = 0
        self.send_ms: list[float] = []
        self.recv_ms: list[float] = []
        self.send_calls = 0
        self.recv_calls = 0
        self._original_send: Any = getattr(Connection, "_send_bytes")
        self._original_recv: Any = getattr(Connection, "_recv_bytes")

    @staticmethod
    def _length(value: Any) -> int:
        try:
            return len(value)
        except TypeError:
            getbuffer = getattr(value, "getbuffer", None)
            return int(getbuffer().nbytes) if callable(getbuffer) else 0

    def __enter__(self) -> ParentIPCProbe:
        original_send = self._original_send
        original_recv = self._original_recv
        probe = self

        def timed_send(connection: Any, payload: Any, *args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            result = original_send(connection, payload, *args, **kwargs)
            probe.send_ms.append((time.perf_counter() - started) * 1000.0)
            probe.send_bytes += probe._length(payload)
            probe.send_calls += 1
            return result

        def timed_recv(connection: Any, *args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            payload = original_recv(connection, *args, **kwargs)
            probe.recv_ms.append((time.perf_counter() - started) * 1000.0)
            probe.recv_bytes += probe._length(payload)
            probe.recv_calls += 1
            return payload

        setattr(Connection, "_send_bytes", timed_send)
        setattr(Connection, "_recv_bytes", timed_recv)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        setattr(Connection, "_send_bytes", self._original_send)
        setattr(Connection, "_recv_bytes", self._original_recv)

    @staticmethod
    def _summary(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"count": 0, "total_ms": 0.0, "p50_ms": None, "p95_ms": None}
        array = np.asarray(values, dtype=np.float64)
        return {
            "count": int(array.size),
            "total_ms": float(array.sum()),
            "p50_ms": float(np.percentile(array, 50)),
            "p95_ms": float(np.percentile(array, 95)),
        }

    def report(self) -> dict[str, Any]:
        return {
            "scope": "PPO parent-process multiprocessing Connection transport",
            "send_calls": self.send_calls,
            "recv_calls": self.recv_calls,
            "send_bytes": self.send_bytes,
            "recv_bytes": self.recv_bytes,
            "send_transport_latency": self._summary(self.send_ms),
            "recv_transport_latency": self._summary(self.recv_ms),
            "limitations": (
                "Counts serialized byte buffers at the parent Connection transport boundary. "
                "Does not include pickle serialization/deserialization CPU time or child-side "
                "step execution."
            ),
        }


class CohortPolicyDispatch:
    """Split rollout inference and dispatch each env cohort before the next forward.

    SB3 still owns rollout collection, callback order, buffer insertion, GAE, and
    every PPO update. This object only overlaps CPU simulator work for an earlier
    cohort with policy inference for a later cohort.
    """

    def __init__(
        self,
        vec_env: Any,
        policy: Any,
        *,
        cohort_count: int,
        action_space: Any,
        action_coordinates: tuple[str, ...] = (),
        thesis_mask_key: str = "thesis_mask",
        thesis_centers: tuple[float, ...] = (),
        validate_thesis_actions: bool = True,
    ) -> None:
        remotes = getattr(vec_env, "remotes", None)
        if remotes is None or len(remotes) != int(vec_env.num_envs):
            raise TypeError("cohort dispatch requires a SubprocVecEnv with one remote per env")
        if cohort_count not in {2, 4}:
            raise ValueError("cohort_count must be 2 or 4")
        if vec_env.num_envs % cohort_count:
            raise ValueError("logical env count must be divisible by cohort_count")
        if not action_coordinates and thesis_centers:
            raise ValueError("thesis centers require declared action coordinates")

        self.vec_env = vec_env
        self.policy = policy
        self.action_space = action_space
        self.cohort_count = cohort_count
        self.cohort_size = int(vec_env.num_envs) // cohort_count
        self.action_coordinates = action_coordinates
        self.thesis_mask_key = thesis_mask_key
        self.thesis_centers = thesis_centers
        self.validate_thesis_actions = validate_thesis_actions
        self.thesis_index = (
            action_coordinates.index("thesis") if "thesis" in action_coordinates else None
        )
        if self.thesis_index is not None and not thesis_centers:
            raise ValueError("thesis action coordinate requires candidate centers")

        self._original_forward = policy.forward
        self._original_step_async = vec_env.step_async
        self._original_step_wait = vec_env.step_wait
        self._pending_actions: np.ndarray[Any, Any] | None = None
        self._dispatched = [False] * cohort_count
        self._rollout_step = 0
        self._accepted_steps = 0
        self.policy_version = 0
        self._dispatch_seconds = [0.0] * cohort_count
        self._dispatch_counts = [0] * cohort_count
        self._forward_ms: list[list[float]] = [[] for _ in range(cohort_count)]
        self._forward_intervals_ns: list[tuple[int, int, int, int, int]] = []
        self._step_wait_ms: list[float] = []
        self._step_wait_idle_intervals_ns: list[tuple[int, int, int]] = []
        self._thesis_selected = 0
        self._thesis_valid = 0
        self._thesis_bad_center = 0
        self._completed_rollouts: list[dict[str, int | bool]] = []
        self._transition_batches = 0
        self._transition_rows = 0
        self._reward_nonfinite = 0
        self._observation_rows_mismatch = 0
        self._terminated_rows = 0
        self._rollout_transition_batches = 0
        self._rollout_transition_rows = 0
        self._rollout_raw_actions: list[np.ndarray[Any, Any]] = []
        self._rollout_action_order_checks = 0

        def pipelined_forward(
            observations: Any, deterministic: bool = False
        ) -> tuple[Any, Any, Any]:
            return self._forward_cohorts(observations, deterministic)

        def dispatch_aware_step_async(actions: np.ndarray[Any, Any]) -> None:
            self._accept_sb3_dispatch(actions)

        def timed_step_wait() -> Any:
            started_ns = time.monotonic_ns()
            result = self._original_step_wait()
            finished_ns = time.monotonic_ns()
            self._step_wait_ms.append((finished_ns - started_ns) / 1_000_000.0)
            self._step_wait_idle_intervals_ns.append(
                (self._rollout_step - 1, started_ns, finished_ns)
            )
            if not isinstance(result, tuple) or len(result) != 4:
                raise RuntimeError("SubprocVecEnv returned an unexpected step transition")
            observations, rewards, dones, _infos = result
            reward_array = np.asarray(rewards)
            done_array = np.asarray(dones)
            if reward_array.shape != (self.vec_env.num_envs,):
                raise RuntimeError("SubprocVecEnv rewards lost environment row alignment")
            if done_array.shape != (self.vec_env.num_envs,):
                raise RuntimeError("SubprocVecEnv terminations lost environment row alignment")
            if not np.issubdtype(done_array.dtype, np.bool_):
                raise RuntimeError("SubprocVecEnv termination array is not boolean")
            observation_rows = (
                {np.asarray(value).shape[0] for value in observations.values()}
                if isinstance(observations, dict)
                else {np.asarray(observations).shape[0]}
            )
            if observation_rows != {self.vec_env.num_envs}:
                self._observation_rows_mismatch += 1
                raise RuntimeError("SubprocVecEnv observations lost environment row alignment")
            self._reward_nonfinite += int((~np.isfinite(reward_array)).sum())
            if self._reward_nonfinite:
                raise RuntimeError("SubprocVecEnv produced nonfinite rewards")
            self._transition_batches += 1
            self._transition_rows += int(reward_array.size)
            self._terminated_rows += int(done_array.sum())
            self._rollout_transition_batches += 1
            self._rollout_transition_rows += int(reward_array.size)
            return result

        policy.forward = pipelined_forward
        vec_env.step_async = dispatch_aware_step_async
        vec_env.step_wait = timed_step_wait

    def _slice_observation(self, observations: Any, start: int, end: int) -> Any:
        if isinstance(observations, dict):
            return {key: value[start:end] for key, value in observations.items()}
        return observations[start:end]

    def _clip(self, actions: Any) -> np.ndarray[Any, Any]:
        values = actions.detach().cpu().numpy()
        if hasattr(self.action_space, "low") and hasattr(self.action_space, "high"):
            if bool(getattr(self.policy, "squash_output", False)):
                values = self.policy.unscale_action(values)
            else:
                values = np.clip(values, self.action_space.low, self.action_space.high)
        return np.asarray(values)

    def _check_thesis_mask(self, actions: Any, observations: Any) -> None:
        if self.thesis_index is None:
            return
        if not isinstance(observations, dict) or self.thesis_mask_key not in observations:
            raise ValueError("thesis policy observations are missing the candidate mask")
        action_values = actions[:, self.thesis_index].detach()
        centers = action_values.new_tensor(self.thesis_centers)
        distances = (action_values[:, None] - centers[None, :]).abs()
        nearest_distance, selected = distances.min(dim=1)
        mask = observations[self.thesis_mask_key] > 0.0
        if mask.shape != distances.shape:
            raise ValueError("thesis mask shape does not match categorical action width")
        selected_valid = mask.gather(1, selected[:, None]).squeeze(1)
        self._thesis_selected += int(selected.numel())
        self._thesis_valid += int(selected_valid.sum().item())
        self._thesis_bad_center += int((nearest_distance > 2e-6).sum().item())
        if not bool(selected_valid.all()) or bool((nearest_distance > 2e-6).any()):
            raise RuntimeError("rollout sampled an invalid or non-categorical thesis action")

    def _forward_cohorts(self, observations: Any, deterministic: bool) -> tuple[Any, Any, Any]:
        import torch

        actions_by_cohort: list[Any] = []
        values_by_cohort: list[Any] = []
        log_probs_by_cohort: list[Any] = []
        thesis_entropy_by_cohort: list[Any] = []
        clipped_by_cohort: list[np.ndarray[Any, Any]] = []
        started_step = self._rollout_step

        for cohort in range(self.cohort_count):
            start = cohort * self.cohort_size
            end = start + self.cohort_size
            cohort_observations = self._slice_observation(observations, start, end)
            forward_started_ns = time.monotonic_ns()
            cohort_actions, cohort_values, cohort_log_probs = self._original_forward(
                cohort_observations, deterministic=deterministic
            )
            clipped = self._clip(cohort_actions)
            forward_finished_ns = time.monotonic_ns()
            self._forward_ms[cohort].append(
                (forward_finished_ns - forward_started_ns) / 1_000_000.0
            )
            self._forward_intervals_ns.append(
                (
                    started_step,
                    cohort,
                    self.policy_version,
                    forward_started_ns,
                    forward_finished_ns,
                )
            )
            if self.validate_thesis_actions:
                self._check_thesis_mask(cohort_actions, cohort_observations)

            dispatch_started = time.perf_counter()
            for remote, action in zip(self.vec_env.remotes[start:end], clipped, strict=True):
                remote.send(("step", action))
            self._dispatch_seconds[cohort] += time.perf_counter() - dispatch_started
            self._dispatch_counts[cohort] += 1
            self._dispatched[cohort] = True

            actions_by_cohort.append(cohort_actions)
            values_by_cohort.append(cohort_values)
            log_probs_by_cohort.append(cohort_log_probs)
            entropy = getattr(self.policy, "last_thesis_entropy", None)
            if entropy is not None:
                thesis_entropy_by_cohort.append(entropy.detach())
            clipped_by_cohort.append(clipped)

        self._pending_actions = np.concatenate(clipped_by_cohort, axis=0)
        if self.validate_thesis_actions:
            self._rollout_raw_actions.append(
                torch.cat(actions_by_cohort, dim=0).detach().cpu().numpy().copy()
            )
        self._rollout_step += 1
        if thesis_entropy_by_cohort:
            self.policy.last_thesis_entropy = torch.cat(thesis_entropy_by_cohort, dim=0)
        return (
            torch.cat(actions_by_cohort, dim=0),
            torch.cat(values_by_cohort, dim=0),
            torch.cat(log_probs_by_cohort, dim=0),
        )

    def _accept_sb3_dispatch(self, actions: np.ndarray[Any, Any]) -> None:
        if self._pending_actions is None:
            raise RuntimeError("SB3 requested env.step before the cohort policy dispatched")
        if not np.array_equal(np.asarray(actions), self._pending_actions):
            raise RuntimeError("SB3 clipped actions differ from actions already dispatched")
        if not all(self._dispatched):
            raise RuntimeError("not every cohort was dispatched before the SB3 step barrier")
        self._pending_actions = None
        self._dispatched = [False] * self.cohort_count
        self._accepted_steps += 1
        self.vec_env.waiting = True

    def close(self) -> None:
        self.policy.forward = self._original_forward
        self.vec_env.step_async = self._original_step_async
        self.vec_env.step_wait = self._original_step_wait

    def mark_policy_update_complete(self) -> None:
        """Advance version only after the stock PPO update returns successfully."""
        self.policy_version += 1

    def record_rollout_completion(
        self,
        *,
        version: int,
        accepted_steps: int,
        expected_steps: int,
        buffer_full: bool,
        gae_finite: bool,
        rollout_buffer: Any,
    ) -> None:
        if accepted_steps != expected_steps or not buffer_full or not gae_finite:
            raise RuntimeError("stock PPO rollout did not complete buffer/GAE before update")
        expected_rows = expected_steps * int(self.vec_env.num_envs)
        if (
            self._rollout_transition_batches != accepted_steps
            or self._rollout_transition_rows != expected_rows
        ):
            raise RuntimeError("worker transitions and PPO rollout rows are misaligned")
        if self.validate_thesis_actions:
            expected_actions = np.stack(self._rollout_raw_actions, axis=0)
            buffered_actions = rollout_buffer.actions
            if hasattr(buffered_actions, "detach"):
                buffered_actions = buffered_actions.detach().cpu().numpy()
            buffered_actions_array = np.asarray(buffered_actions)
            if not np.array_equal(expected_actions, buffered_actions_array):
                raise RuntimeError("PPO buffer action row order differs from cohort policy order")
            self._rollout_action_order_checks += 1
            self._rollout_raw_actions.clear()
        if self.policy_version != version:
            raise RuntimeError("policy version changed during an on-policy rollout")
        self._completed_rollouts.append(
            {
                "policy_version": version,
                "vector_steps": accepted_steps,
                "expected_vector_steps": expected_steps,
                "rollout_buffer_full": buffer_full,
                "gae_finite": gae_finite,
            }
        )
        self._rollout_transition_batches = 0
        self._rollout_transition_rows = 0

    @staticmethod
    def _summary(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
        array = np.asarray(values, dtype=np.float64)
        return {
            "count": int(array.size),
            "p50_ms": float(np.percentile(array, 50)),
            "p95_ms": float(np.percentile(array, 95)),
            "mean_ms": float(array.mean()),
        }

    def report(self) -> dict[str, Any]:
        return {
            "cohort_count": self.cohort_count,
            "cohort_size": self.cohort_size,
            "aggregate_envs": self.cohort_count * self.cohort_size,
            "policy_version": self.policy_version,
            "policy_version_semantics": (
                "The policy is frozen throughout each SB3 collect_rollouts call; the stock "
                "on-policy collector completes the rollout and GAE before model.train updates it."
            ),
            "cohort_dispatches": list(self._dispatch_counts),
            "cohort_dispatch_wall_ms_total": [value * 1000.0 for value in self._dispatch_seconds],
            "cohort_inference_latency": [self._summary(values) for values in self._forward_ms],
            "step_wait_latency": self._summary(self._step_wait_ms),
            "sb3_steps_accepted": self._accepted_steps,
            "transition_batches": self._transition_batches,
            "transition_rows": self._transition_rows,
            "terminated_rows": self._terminated_rows,
            "nonfinite_rewards": self._reward_nonfinite,
            "observation_rows_mismatch": self._observation_rows_mismatch,
            "rollout_action_order_checks": self._rollout_action_order_checks,
            "completed_rollouts": self._completed_rollouts,
            "policy_versions_used": sorted({item[2] for item in self._forward_intervals_ns}),
            "thesis_validation_enabled": self.validate_thesis_actions,
            "thesis_selected": self._thesis_selected if self.validate_thesis_actions else None,
            "thesis_valid": self._thesis_valid if self.validate_thesis_actions else None,
            "thesis_invalid": (
                self._thesis_selected - self._thesis_valid if self.validate_thesis_actions else None
            ),
            "thesis_bad_center": (
                self._thesis_bad_center if self.validate_thesis_actions else None
            ),
            "inference_intervals_ns": [list(item) for item in self._forward_intervals_ns],
            "step_wait_idle_intervals_ns": [
                list(item) for item in self._step_wait_idle_intervals_ns
            ],
        }


def summarize_cpu_gpu_overlap(
    inference_intervals_ns: list[tuple[int, int, int, int, int]],
    env_step_intervals_ns: list[tuple[int, int, int, int]],
    *,
    cohort_count: int,
    cohort_size: int,
) -> dict[str, Any]:
    """Measure earlier-cohort CPU stepping overlapping later GPU inference."""
    by_step: dict[int, list[tuple[int, int, int]]] = {}
    for env_index, step_index, start_ns, end_ns in env_step_intervals_ns:
        by_step.setdefault(step_index, []).append((env_index, start_ns, end_ns))

    by_cohort: list[list[float]] = [[] for _ in range(cohort_count)]
    for step_index, cohort, _version, inference_start, inference_end in inference_intervals_ns:
        if cohort == 0:
            continue
        earlier = [
            (start, end)
            for env_index, start, end in by_step.get(step_index, [])
            if env_index // cohort_size < cohort
        ]
        clipped = sorted(
            (max(start, inference_start), min(end, inference_end))
            for start, end in earlier
            if end > inference_start and start < inference_end
        )
        covered_ns = 0
        union_end = inference_start
        for start, end in clipped:
            if end <= union_end:
                continue
            covered_ns += end - max(start, union_end)
            union_end = end
        duration_ns = max(inference_end - inference_start, 1)
        by_cohort[cohort].append(min(covered_ns / duration_ns, 1.0))

    return {
        "method": "same-host monotonic env.step intervals overlapping later cohort policy.forward",
        "by_later_cohort": [
            {
                "cohort": cohort,
                "samples": len(values),
                "mean_fraction_with_earlier_cpu_step_active": (
                    float(np.mean(values)) if values else None
                ),
                "p50_fraction": float(np.percentile(values, 50)) if values else None,
                "p95_fraction": float(np.percentile(values, 95)) if values else None,
            }
            for cohort, values in enumerate(by_cohort)
        ],
    }


__all__ = ["CohortPolicyDispatch", "ParentIPCProbe", "summarize_cpu_gpu_overlap"]
