from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import torch
from gymnasium import spaces
from scripts.research.benchmarks.ppo_cohort_pipeline import (
    CohortPolicyDispatch,
    ParentIPCProbe,
    summarize_cpu_gpu_overlap,
)


class _Remote:
    def __init__(self, index: int) -> None:
        self.index = index
        self.messages: list[tuple[str, Any]] = []

    def send(self, message: tuple[str, Any]) -> None:
        self.messages.append(message)


class _FakeVecEnv:
    def __init__(self, count: int) -> None:
        self.num_envs = count
        self.remotes = [_Remote(index) for index in range(count)]
        self.waiting = False

    def step_async(self, actions: np.ndarray[Any, Any]) -> None:
        del actions
        raise AssertionError("pipeline dispatch should replace the stock async call")

    def step_wait(
        self,
    ) -> tuple[
        np.ndarray[Any, Any],
        np.ndarray[Any, Any],
        np.ndarray[Any, Any],
        list[dict[str, Any]],
    ]:
        self.waiting = False
        return (
            np.zeros((self.num_envs, 1)),
            np.zeros(self.num_envs),
            np.zeros(self.num_envs, dtype=bool),
            [{} for _ in range(self.num_envs)],
        )


class _FakePolicy:
    squash_output = False

    def __init__(self) -> None:
        self.calls: list[int] = []
        self.last_thesis_entropy: torch.Tensor | None = None

    def forward(
        self, observations: dict[str, torch.Tensor], deterministic: bool = False
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        del deterministic
        marker = observations["marker"]
        self.calls.append(int(marker.shape[0]))
        actions = torch.full((marker.shape[0], 1), 0.25)
        values = marker[:, :1] + 1.0
        log_probs = marker[:, 0]
        return actions, values, log_probs


def test_dispatches_two_cohorts_and_preserves_sb3_row_order() -> None:
    vec_env = _FakeVecEnv(8)
    policy = _FakePolicy()
    pipeline = CohortPolicyDispatch(
        vec_env,
        policy,
        cohort_count=2,
        action_space=spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32),
    )

    observations = {"marker": torch.arange(8, dtype=torch.float32).reshape(8, 1)}
    actions, values, log_probs = policy.forward(observations)

    assert policy.calls == [4, 4]
    assert values[:, 0].tolist() == list(range(1, 9))
    assert log_probs.tolist() == list(range(8))
    assert actions.shape == (8, 1)
    assert [remote.messages[0][0] for remote in vec_env.remotes] == ["step"] * 8
    assert [float(remote.messages[0][1][0]) for remote in vec_env.remotes] == [0.25] * 8

    vec_env.step_async(actions.detach().cpu().numpy())
    assert vec_env.waiting
    vec_env.step_wait()
    report = pipeline.report()
    assert report["sb3_steps_accepted"] == 1
    assert report["transition_batches"] == 1
    assert report["transition_rows"] == 8
    assert report["nonfinite_rewards"] == 0
    assert report["observation_rows_mismatch"] == 0
    pipeline.close()


def test_dispatch_rejects_sb3_actions_that_differ_from_dispatched_actions() -> None:
    vec_env = _FakeVecEnv(8)
    policy = _FakePolicy()
    pipeline = CohortPolicyDispatch(
        vec_env,
        policy,
        cohort_count=2,
        action_space=spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32),
    )
    actions, _, _ = policy.forward({"marker": torch.zeros((8, 1))})

    with np.testing.assert_raises_regex(RuntimeError, "clipped actions differ"):
        vec_env.step_async(actions.detach().cpu().numpy() + 0.1)
    pipeline.close()


def test_thesis_dispatch_checks_selected_candidate_against_each_mask() -> None:
    class ThesisPolicy(_FakePolicy):
        def forward(
            self, observations: dict[str, torch.Tensor], deterministic: bool = False
        ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            del deterministic
            count = observations["marker"].shape[0]
            action = torch.zeros((count, 1), dtype=torch.float32)
            action[:, 0] = -0.5
            return action, torch.ones((count, 1)), torch.zeros(count)

    vec_env = _FakeVecEnv(8)
    policy = ThesisPolicy()
    pipeline = CohortPolicyDispatch(
        vec_env,
        policy,
        cohort_count=2,
        action_space=spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32),
        action_coordinates=("thesis",),
        thesis_centers=(-0.5, 0.5),
        validate_thesis_actions=True,
    )
    observations = {
        "marker": torch.zeros((8, 1)),
        "thesis_mask": torch.tensor([[1.0, 0.0]] * 8),
    }
    actions, _, _ = policy.forward(observations)
    vec_env.step_async(actions.detach().cpu().numpy())
    vec_env.step_wait()
    pipeline.record_rollout_completion(
        version=0,
        accepted_steps=1,
        expected_steps=1,
        buffer_full=True,
        gae_finite=True,
        rollout_buffer=SimpleNamespace(actions=actions.detach().cpu().numpy()[None, ...]),
    )
    pipeline.mark_policy_update_complete()
    result = pipeline.report()
    assert result["thesis_selected"] == 8
    assert result["thesis_valid"] == 8
    assert result["thesis_invalid"] == 0
    assert result["rollout_action_order_checks"] == 1
    assert result["policy_version"] == 1
    assert result["completed_rollouts"][0]["policy_version"] == 0
    pipeline.close()


def test_thesis_dispatch_rejects_invalid_candidate_selection() -> None:
    class ThesisPolicy(_FakePolicy):
        def forward(
            self, observations: dict[str, torch.Tensor], deterministic: bool = False
        ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            del observations, deterministic
            return torch.full((4, 1), 0.5), torch.ones((4, 1)), torch.zeros(4)

    vec_env = _FakeVecEnv(8)
    policy = ThesisPolicy()
    pipeline = CohortPolicyDispatch(
        vec_env,
        policy,
        cohort_count=2,
        action_space=spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32),
        action_coordinates=("thesis",),
        thesis_centers=(-0.5, 0.5),
        validate_thesis_actions=True,
    )

    with np.testing.assert_raises_regex(RuntimeError, "invalid or non-categorical"):
        policy.forward(
            {
                "marker": torch.zeros((8, 1)),
                "thesis_mask": torch.tensor([[1.0, 0.0]] * 8),
            }
        )
    pipeline.close()


def test_overlap_uses_same_rollout_step_and_only_earlier_cohorts() -> None:
    result = summarize_cpu_gpu_overlap(
        inference_intervals_ns=[(0, 1, 0, 20, 40), (0, 2, 0, 10, 30)],
        env_step_intervals_ns=[
            (0, 0, 10, 30),
            (1, 0, 11, 31),
            (4, 0, 0, 45),
        ],
        cohort_count=4,
        cohort_size=2,
    )

    later = result["by_later_cohort"][1]
    assert later["samples"] == 1
    assert later["mean_fraction_with_earlier_cpu_step_active"] == 0.55
    assert result["by_later_cohort"][2]["samples"] == 1


def test_parent_ipc_probe_reports_transport_boundary() -> None:
    probe = ParentIPCProbe()
    report = probe.report()
    assert report["send_calls"] == 0
    assert report["recv_calls"] == 0
    assert report["send_bytes"] == 0
    assert "pickle serialization" in report["limitations"]
