from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces

from decisioning.trade_setup import TRADE_SETUP_CATEGORY_COUNT, trade_setup_center
from learning.rl.callbacks import (
    ClipLogStdCallback,
    EarlyAbortCallback,
    EpisodeEquityCallback,
    LagrangianRiskCallback,
    LearningDiagnosticsCallback,
    PeriodicCheckpointCallback,
    TrainingProgressCallback,
    _action_coordinate_names,
    _record_action_coordinates,
    _summarize_action_coordinates,
)


class _Logger:
    def __init__(self) -> None:
        self.values: dict[str, float] = {}

    def record(self, key: str, value: float) -> None:
        self.values[key] = float(value)


class _FakeModel:
    def __init__(self, *, action_space: spaces.Space[Any] | None = None) -> None:
        self.num_timesteps = 0
        self.action_space = action_space or spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
        self.observation_space = spaces.Box(-1.0, 1.0, shape=(1,), dtype=np.float32)
        self.logger = _Logger()
        self.rollout_buffer: Any = None
        self._action_schema = {"coordinates": ["trade_setup", "entry_execution"]}
        distribution = SimpleNamespace(
            categorical_coordinate_entropy=lambda name: (
                np.array([0.4, np.nan]) if name == "entry_execution" else None
            )
        )
        self.policy = SimpleNamespace(
            last_trade_setup_entropy=np.array([0.2, np.nan]),
            hybrid_distribution=distribution,
        )

    def get_env(self) -> None:
        return None


def test_action_coordinate_diagnostics_keep_only_finite_values() -> None:
    env = SimpleNamespace(action_schema=SimpleNamespace(to_dict=lambda: {"coordinates": ["risk"]}))
    totals: dict[str, dict[str, float]] = {}

    assert _action_coordinate_names(env, 1) == ["risk"]
    assert _action_coordinate_names(env, 2) == ["coordinate_0", "coordinate_1"]
    _record_action_coordinates(totals, [0.25, 0.5], ["risk"])
    _record_action_coordinates(totals, [0.25, np.nan], ["risk", "unused"])

    summary = _summarize_action_coordinates(totals)
    assert summary["risk"]["n"] == 1
    assert summary["risk"]["nonfinite_n"] == 0
    assert summary["risk"]["mean"] == pytest.approx(0.25)
    assert summary["unused"]["n"] == 0
    assert summary["unused"]["nonfinite_n"] == 1


def test_training_progress_callback_logs_on_cadence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = TrainingProgressCallback(log_every=4, total_timesteps=10)
    model = _FakeModel()
    callback.init_callback(model)  # type: ignore[arg-type]
    ticks = iter((10.0, 12.0))
    messages: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr("learning.rl.callbacks.time.monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        "learning.rl.callbacks.log.info",
        lambda message, *args: messages.append((message, args)),
    )

    model.num_timesteps = 1
    callback.on_training_start({}, {})
    model.num_timesteps = 3
    assert callback.on_step()
    assert messages == []
    model.num_timesteps = 4
    assert callback.on_step()

    assert messages == [
        ("TRAIN_PROGRESS step=%d/%d recent_fps=%.1f eta_seconds=%.0f", (4, 10, 1.5, 4.0))
    ]
    assert callback._next_log == 8


def test_learning_diagnostics_aggregate_rollout_and_write_csv(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "diagnostics.csv"
    callback = LearningDiagnosticsCallback(output)
    model = _FakeModel()
    legal = np.ones(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    legal[0] = 0.0
    legal[1] = 0.0
    model.rollout_buffer = SimpleNamespace(
        actions=np.asarray([[trade_setup_center(1), -0.5], [trade_setup_center(2), 0.5]]),
        rewards=np.asarray([1.0, -0.5]),
        advantages=np.asarray([0.25, -0.25]),
        observations={"trade_setup_mask": np.stack((legal, legal))},
    )
    callback.init_callback(model)  # type: ignore[arg-type]
    callback.locals = {
        "infos": [
            {
                "entry_funnel": {"eligible": 2},
                "reward_parts": {"pnl": 1.5},
                "constraints": {"daily_cost": 0.25, "ignored": "not numeric"},
            },
            None,
            {"entry_funnel": {"eligible": 1}, "constraints": {"daily_cost": 0.5}},
        ]
    }

    assert callback._on_step()
    model.num_timesteps = 2
    callback._on_rollout_end()
    callback._on_training_end()

    result = pd.read_csv(output)
    assert result.loc[0, "entry_funnel/eligible"] == 3.0
    assert result.loc[0, "constraints/mean_daily_cost"] == pytest.approx(0.375)
    assert result.loc[0, "trade_setup/selected_trade_count"] == 2.0
    assert result.loc[0, "trade_setup/invalid_selection_count"] == 1.0
    assert result.loc[0, "entry_execution/entropy_mean_nats"] == pytest.approx(0.4)
    assert result.loc[0, "trade_setup/entropy_mean_nats"] == pytest.approx(0.2)
    assert callback._window_steps == 0


def test_learning_diagnostics_reject_setup_mask_action_count_mismatch(tmp_path: Path) -> None:
    callback = LearningDiagnosticsCallback(tmp_path / "diagnostics.csv")
    model = _FakeModel()
    legal = np.ones(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    model.rollout_buffer = SimpleNamespace(
        actions=np.asarray([[trade_setup_center(1), 0.25]]),
        rewards=np.asarray([1.0]),
        advantages=np.asarray([0.5]),
        observations={"trade_setup_mask": np.stack((legal, legal))},
    )
    callback.init_callback(model)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="setup mask and setup action counts differ"):
        callback._on_rollout_end()


def test_lagrangian_callback_shapes_reward_updates_multiplier_and_persists_state() -> None:
    callback = LagrangianRiskCallback(
        episode_cost_budget=0.1,
        dual_learning_rate=0.5,
        lambda_initial=2.0,
        lambda_max=3.0,
        gamma=1.0,
        daily_loss_limit_usd=5_000.0,
        max_loss_limit_usd=10_000.0,
    )
    model = SimpleNamespace(n_envs=1, logger=_Logger())
    callback.init_callback(model)  # type: ignore[arg-type]
    callback._on_training_start()
    rewards = np.asarray([1.0], dtype=np.float32)
    callback.locals = {
        "rewards": rewards,
        "dones": np.asarray([True]),
        "infos": [{"constraints": {"daily_cost": 0.4}}],
    }

    assert callback._on_step()
    callback._on_rollout_end()

    assert rewards[0] == pytest.approx(0.6)
    assert model.logger.values["constrained_rl/environment_reward_mean"] == pytest.approx(1.0)
    assert model.logger.values["constrained_rl/penalty_sum"] == pytest.approx(0.4)
    assert model.logger.values["constrained_rl/mean_completed_episode_cost"] == pytest.approx(0.2)
    assert callback.lagrange_multiplier == pytest.approx(2.05)
    assert callback._dual_updates == 1
    assert model._constrained_rl_state["lagrange_multiplier"] == pytest.approx(2.05)
    assert model._constrained_rl_state["dual_updates"] == 1


def test_lagrangian_callback_restores_only_bounded_state_and_scores_enabled_costs() -> None:
    callback = LagrangianRiskCallback(
        lambda_initial=0.2,
        lambda_max=1.0,
        daily_loss_limit_usd=5_000.0,
        max_loss_limit_usd=10_000.0,
        trailing_dd_limit_usd=5_000.0,
    )
    model = SimpleNamespace(n_envs=1)
    callback.init_callback(model)  # type: ignore[arg-type]
    model._constrained_rl_state = {
        **callback._config_state(),
        "lagrange_multiplier": 1.1,
        "dual_updates": 4,
    }

    with pytest.raises(ValueError, match="outside configured bounds"):
        callback._on_training_start()

    assert callback._episode_cost(None) == 0.0
    assert callback._episode_cost({"constraints": []}) == 0.0
    assert callback._episode_cost(
        {"constraints": {"daily_cost": 0.2, "max_loss_cost": 0.05, "trailing_cost": 0.3}}
    ) == pytest.approx(0.15)
    assert callback._episode_cost({"constraints": {"daily_breach": True}}) == 1.0


def test_clip_callback_runs_at_update_boundaries_and_keeps_step_nonblocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, float, float]] = []
    model = SimpleNamespace(policy=object())
    callback = ClipLogStdCallback(log_std_min=-0.8, log_std_max=0.1)
    callback.init_callback(model)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "learning.rl.callbacks.clip_policy_log_std",
        lambda policy, lower, upper: calls.append((policy, lower, upper)),
    )

    callback._on_training_start()
    callback._on_rollout_start()
    assert callback._on_step()
    callback._on_training_end()

    assert calls == [(model.policy, -0.8, 0.1)] * 3


def test_periodic_checkpoint_resumes_on_next_boundary_and_coalesces_crossed_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saves: list[Path] = []
    monkeypatch.setattr(
        "learning.rl.callbacks.save_ppo_checkpoint",
        lambda _model, path: saves.append(Path(path)),
    )
    model = SimpleNamespace(num_timesteps=17)
    callback = PeriodicCheckpointCallback(save_freq=10, save_path=tmp_path, verbose=0)
    callback.init_callback(model)  # type: ignore[arg-type]

    callback.num_timesteps = 19
    assert callback._on_step()
    assert saves == []
    callback.num_timesteps = 21
    assert callback._on_step()
    assert callback._next_save == 30
    callback.num_timesteps = 46
    assert callback._on_step()

    assert callback._next_save == 50
    assert saves == [
        tmp_path / "ppo_ckpt_21_steps",
        tmp_path / "ppo_latest",
        tmp_path / "ppo_ckpt_46_steps",
        tmp_path / "ppo_latest",
    ]


def test_early_abort_ignores_explained_variance_nan_but_stops_on_other_nonfinite_metrics() -> None:
    callback = EarlyAbortCallback(min_timesteps=100, window=2)
    model = SimpleNamespace(
        num_timesteps=1,
        logger=SimpleNamespace(
            name_to_value={
                "train/explained_variance": float("nan"),
                "train/metadata": "not numeric",
                "train/loss": float("inf"),
            }
        ),
    )
    callback.init_callback(cast(Any, model))

    callback._on_rollout_end()

    assert callback._nonfinite
    assert not callback._on_step()
    assert callback.reason is not None
    assert "nonfinite" in callback.reason


def test_early_abort_marks_non_numeric_episode_evidence_invalid() -> None:
    callback = EarlyAbortCallback(min_timesteps=100)

    callback._note_episode({"end_equity": "unavailable"})

    assert callback._nonfinite
    assert callback._episodes == [{"end_equity": "unavailable"}]


def test_episode_callback_writes_empty_header_when_no_episode_ever_finishes(tmp_path: Path) -> None:
    path = tmp_path / "episode_equity.csv"
    callback = EpisodeEquityCallback(path)
    callback.init_callback(SimpleNamespace(num_timesteps=0))  # type: ignore[arg-type]
    callback.locals = {"dones": None, "infos": []}

    assert callback._on_step()
    callback._on_training_end()

    assert path.read_text(encoding="utf-8").startswith("timestep,environment_index,end_equity")
