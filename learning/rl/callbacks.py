"""SB3 training callbacks for progress logging and best-checkpoint eval."""

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from learning.rl.callback_action_stats import (
    _action_coordinate_names as _action_coordinate_names,
)
from learning.rl.callback_action_stats import (
    _record_action_coordinates as _record_action_coordinates,
)
from learning.rl.callback_action_stats import (
    _summarize_action_coordinates as _summarize_action_coordinates,
)
from learning.rl.learner import save_sb3_checkpoint
from learning.rl.ppo import clip_policy_log_std
from learning.rl.stopping import decide_early_abort

log = logging.getLogger(__name__)


def save_ppo_checkpoint(model: Any, path: str | Path) -> None:
    """Compatibility entry point for callback-owned checkpoint saves.

    Args:
        model: Model used for this operation.
        path: Path to the input file or directory.
    """
    save_sb3_checkpoint(model, path)


try:
    from stable_baselines3.common.callbacks import BaseCallback as _Base

    _SB3_AVAILABLE = True
except ImportError:
    _Base = object  # type: ignore[assignment,misc]
    _SB3_AVAILABLE = False
else:
    from learning.rl.callback_diagnostics import (
        LearningDiagnosticsCallback as LearningDiagnosticsCallback,
    )
    from learning.rl.lagrangian_callback import LagrangianRiskCallback as LagrangianRiskCallback


if _SB3_AVAILABLE:

    class TrainingProgressCallback(_Base):
        """Log a cheap step/FPS heartbeat without running dashboard work."""

        def __init__(self, log_every: int, total_timesteps: int, verbose: int = 0) -> None:
            """Initialize TrainingProgressCallback and its owned state.

            Args:
                log_every: Numeric value used for the log every.
                total_timesteps: Numeric value used for the total timesteps.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            self.log_every = max(0, int(log_every))
            self.total_timesteps = max(0, int(total_timesteps))
            self._started_at = 0.0
            self._started_step = 0
            self._last_logged_at = 0.0
            self._last_logged_step = 0
            self._next_log = self.log_every

        def _on_training_start(self) -> None:
            """Process training start."""
            self._started_at = time.monotonic()
            self._started_step = int(self.num_timesteps)
            self._last_logged_at = self._started_at
            self._last_logged_step = self._started_step

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            step = int(self.num_timesteps)
            if self.log_every <= 0 or step < self._next_log:
                return True
            now = time.monotonic()
            interval_seconds = max(now - self._last_logged_at, 1e-9)
            interval_steps = max(step - self._last_logged_step, 0)
            recent_fps = interval_steps / interval_seconds
            total_seconds = max(now - self._started_at, 1e-9)
            average_fps = max(step - self._started_step, 0) / total_seconds
            remaining_steps = max(self.total_timesteps - step, 0)
            eta_seconds = remaining_steps / average_fps if average_fps > 0 else float("inf")
            log.info(
                "TRAIN_PROGRESS step=%d/%d recent_fps=%.1f eta_seconds=%.0f",
                step,
                self.total_timesteps,
                recent_fps,
                eta_seconds,
            )
            self._last_logged_at = now
            self._last_logged_step = step
            self._next_log = self.log_every * (1 + step // self.log_every)
            return True

    class ProgressLoggerCallback(_Base):
        """Record per-rollout training metrics and save them to a CSV.

        Captures ``model.logger.name_to_value`` after each rollout collection.
        Note: ``train/*`` metrics in a given row reflect the *previous* training
        step (they are computed after rollout collection, not before); this
        one-rollout lag is negligible for visualisation purposes.

        The CSV is written to *log_path* when training ends.
        """

        def __init__(self, log_path: str | Path, verbose: int = 0) -> None:
            """Initialize ProgressLoggerCallback and its owned state.

            Args:
                log_path: Path or filename identifying the log.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            self._log_path = Path(log_path)
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._rows: list[dict[str, Any]] = []

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            return True

        def _on_rollout_end(self) -> None:
            """Process rollout end."""
            row: dict[str, Any] = {"timestep": self.num_timesteps}
            for k, v in self.model.logger.name_to_value.items():
                with contextlib.suppress(TypeError, ValueError):
                    row[k] = float(v)
            self._rows.append(row)

        def _on_training_end(self) -> None:
            """Process training end."""
            if self._rows:
                pd.DataFrame(self._rows).to_csv(self._log_path, index=False)

    class EpisodeEquityCallback(_Base):
        """Write one row per finished training episode to ``episode_equity.csv``.

        Warns when the shaped reward sum is positive while end equity is
        below the episode start. That is the reward/equity mismatch.
        """

        def __init__(self, log_path: str | Path, verbose: int = 0) -> None:
            """Initialize EpisodeEquityCallback and its owned state.

            Args:
                log_path: Path or filename identifying the log.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            self._log_path = Path(log_path)
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._columns = [
                "timestep",
                "environment_index",
                "end_equity",
                "start_equity",
                "equity_delta",
                "reward_sum",
                "n_trades",
                "episode_steps",
                "completed_data_split",
                "episode_end_reason",
                "breach_reason",
            ]

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            dones = self.locals.get("dones")
            infos = self.locals.get("infos") or []
            if dones is None:
                return True
            rows: list[dict[str, Any]] = []
            for i, done in enumerate(np.asarray(dones).reshape(-1)):
                if not done or i >= len(infos):
                    continue
                ep = infos[i].get("episode_equity") if isinstance(infos[i], dict) else None
                if not ep:
                    continue
                end_equity: float = float(ep["end_equity"])
                start_equity: float = float(ep["start_equity"])
                reward_sum: float = float(ep["reward_sum"])
                equity_delta = end_equity - start_equity
                row = {
                    "timestep": int(self.num_timesteps),
                    "environment_index": int(i),
                    "end_equity": end_equity,
                    "start_equity": start_equity,
                    "equity_delta": equity_delta,
                    "reward_sum": reward_sum,
                    "n_trades": int(ep["n_trades"]),
                    "episode_steps": int(ep.get("episode_steps", 0)),
                    "completed_data_split": bool(ep.get("completed_data_split", False)),
                    "episode_end_reason": str(ep.get("episode_end_reason") or ""),
                    "breach_reason": str(ep.get("breach_reason") or ""),
                }
                rows.append(row)
                if reward_sum > 0.0 and end_equity < start_equity:
                    log.warning(
                        "episode reward %.4f is positive but equity fell %.2f (breach=%s)",
                        reward_sum,
                        -equity_delta,
                        row["breach_reason"] or "none",
                    )
            if rows:
                pd.DataFrame(rows, columns=self._columns).to_csv(
                    self._log_path,
                    mode="a",
                    header=not self._log_path.exists(),
                    index=False,
                )
            return True

        def _on_training_end(self) -> None:
            """Process training end."""
            if not self._log_path.exists():
                pd.DataFrame(columns=self._columns).to_csv(self._log_path, index=False)

    class BestCheckpointEvalCallback(_Base):
        """Save the policy with the highest end equity on a train-calendar rollout.

        The score is the account equity at the end of the rollout, not the
        shaped episode reward. A higher reward with a lower balance does not
        replace the saved checkpoint. The rollout uses deterministic actions
        so a repeated evaluation of a fixed policy and data slice is stable.

        Args:
            eval_env_factory (callable): ``() -> TradingEnv`` returning a *fresh* evaluation environment.
                Called every ``eval_freq`` rollouts; reusing the same env would
                leak rollout state between evals.
            eval_freq (int): Run an evaluation every ``eval_freq`` rollout steps.
            best_model_path (str | Path): File path to write the best model to (SB3 ``.save()`` format).
            n_eval_episodes (int): Number of independent rollouts to average over for the best-model
                decision. Defaults to 1, which is noisy but cheap; training runs
                should use 3–5 once ``eval_freq`` is tuned.
        """

        def __init__(
            self,
            eval_env_factory: Any,
            eval_freq: int = 5,
            best_model_path: str | Path = "best_model",
            n_eval_episodes: int = 1,
            verbose: int = 0,
            viability_eval_env_factory: Any | None = None,
            viability_eval_freq: int = 5_000_000,
            survival_objective: bool = False,
        ) -> None:
            """Initialize BestCheckpointEvalCallback and its owned state.

            Args:
                eval_env_factory: Eval env factory used by the operation described above.
                eval_freq: Numeric value used for the eval freq.
                best_model_path: Path or filename identifying the best model.
                n_eval_episodes: Numeric value used for the n eval episodes.
                verbose: Numeric value used for the verbose.
                viability_eval_env_factory: Viability eval env factory used by the operation described above.
                viability_eval_freq: Numeric value used for the viability eval freq.
                survival_objective: Whether this callback is used for survival qualification.
            """
            super().__init__(verbose=verbose)
            self._eval_env_factory = eval_env_factory
            self._eval_freq = int(eval_freq)
            self._best_model_path = Path(best_model_path)
            self._best_model_path.parent.mkdir(parents=True, exist_ok=True)
            self._n_eval_episodes = int(n_eval_episodes)
            self._next_eval_at = self._eval_freq
            self._viability_eval_env_factory = viability_eval_env_factory or eval_env_factory
            self._viability_eval_freq = int(viability_eval_freq)
            self._next_viability_eval_at = self._viability_eval_freq
            self._survival_objective = bool(survival_objective)
            self.viability_eval_history: list[dict[str, Any]] = []
            self.best_end_equity: float = -np.inf
            # Kept in sync with ``best_end_equity`` so older callers still read a score.
            self.best_mean_reward: float = -np.inf
            self.best_n_trades = 0
            self.best_checkpoint_status = (
                "SURVIVAL_FINAL_CHECKPOINT" if self._survival_objective else "NO_ACTIVE_CHECKPOINT"
            )
            self.consecutive_inactive_viability_evals = 0
            self.viability_failure_reason: str | None = None

        def _on_step(self) -> bool:
            # Use threshold crossings because vectorized PPO increments by
            # n_envs and may never land exactly on a requested interval.
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            if (
                not self._survival_objective
                and self._eval_freq > 0
                and self.num_timesteps >= self._next_eval_at
            ):
                self._run_eval()
                while self._next_eval_at <= self.num_timesteps:
                    self._next_eval_at += self._eval_freq
            if self._viability_eval_freq > 0 and self.num_timesteps >= self._next_viability_eval_at:
                self._run_viability_eval()
                while self._next_viability_eval_at <= self.num_timesteps:
                    self._next_viability_eval_at += self._viability_eval_freq
            return self.viability_failure_reason is None

        def _run_eval(self) -> None:
            """Run eval."""
            end_equities: list[float] = []
            completed_trades = 0
            survival_valid = True
            for _ in range(self._n_eval_episodes):
                env = self._eval_env_factory()
                obs, _ = env.reset()
                done = truncated = False
                while not (done or truncated):
                    action, _ = self.model.predict(obs, deterministic=True)
                    obs, _reward, done, truncated, _ = env.step(action)
                equity = float(env.account.equity)
                end_equities.append(equity)
                trade_log = getattr(env, "trade_log", ())
                closing_types = {
                    "close",
                    "eod_close",
                    "forced_close",
                    "stop_close",
                    "tp_close",
                }
                completed_trades += sum(
                    1 for trade in trade_log if trade.get("type") in closing_types
                )
                survival_valid = survival_valid and not bool(getattr(env, "breach_events", ()))
            end_equity = float(np.mean(end_equities))
            if completed_trades < 1 or not survival_valid or not np.isfinite(end_equity):
                self.best_checkpoint_status = "NO_ACTIVE_CHECKPOINT"
                if self.verbose:
                    print(
                        "[BestCheckpointEval] ineligible "
                        f"trades={completed_trades} survival_valid={survival_valid} "
                        f"end_equity_finite={np.isfinite(end_equity)}"
                    )
                return
            self.best_checkpoint_status = "ACTIVE_CHECKPOINT_AVAILABLE"
            if end_equity > self.best_end_equity:
                self.best_end_equity = end_equity
                self.best_mean_reward = end_equity
                self.best_n_trades = completed_trades
                save_ppo_checkpoint(self.model, self._best_model_path)
                if self.verbose:
                    print(
                        f"[BestCheckpointEval] new best end_equity={end_equity:.2f} at "
                        f"timestep={self.num_timesteps} → saved {self._best_model_path}"
                    )

        def _run_viability_eval(self) -> None:
            """Replay the complete training calendar for deterministic viability."""
            end_equities: list[float] = []
            completed_trades = 0
            survival_valid = True
            entry_state: dict[str, Any] = {}
            entry_funnel_diagnostics: dict[str, int] = {}
            action_coordinate_totals: dict[str, dict[str, float]] = {}
            action_coordinate_schema: list[str] | None = None
            action_coordinate_schema_mismatch = False
            for _ in range(self._n_eval_episodes):
                env = self._viability_eval_env_factory()
                try:
                    obs, _ = env.reset()
                    done = truncated = False
                    while not (done or truncated):
                        action, _ = self.model.predict(obs, deterministic=True)
                        action_values = np.asarray(action).reshape(-1)
                        names = _action_coordinate_names(env, int(action_values.size))
                        if action_coordinate_schema is None:
                            action_coordinate_schema = names
                        elif names != action_coordinate_schema:
                            action_coordinate_schema_mismatch = True
                        _record_action_coordinates(action_coordinate_totals, action, names)
                        obs, _reward, done, truncated, _ = env.step(action)
                    end_equities.append(float(env.account.equity))
                    trade_log = getattr(env, "trade_log", ())
                    closing_types = {
                        "close",
                        "eod_close",
                        "forced_close",
                        "stop_close",
                        "tp_close",
                    }
                    completed_trades += sum(
                        1 for trade in trade_log if trade.get("type") in closing_types
                    )
                    survival_valid = survival_valid and not bool(getattr(env, "breach_events", ()))
                    entry_diag = getattr(env, "_entry_diag", {})
                    if isinstance(entry_diag, dict):
                        for key, value in entry_diag.items():
                            if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
                                entry_funnel_diagnostics[str(key)] = entry_funnel_diagnostics.get(
                                    str(key), 0
                                ) + int(value)
                    state_fn = getattr(env, "entry_state_diagnostics", None)
                    if callable(state_fn):
                        state = state_fn()
                        if isinstance(state, dict):
                            for key, value in state.items():
                                if isinstance(value, (int, float, np.integer, np.floating)):
                                    entry_state[str(key)] = entry_state.get(str(key), 0) + value
                                else:
                                    entry_state[str(key)] = value
                finally:
                    close = getattr(env, "close", None)
                    if callable(close):
                        close()
            end_equity = float(np.mean(end_equities))
            finite_equity = bool(np.isfinite(end_equity))
            row: dict[str, Any] = {
                "timestep": int(self.num_timesteps),
                "deterministic_n_trades": int(completed_trades),
                "candidate_created": int(entry_state.get("candidate_created", 0)),
                "armed": int(entry_state.get("armed_bars", 0)),
                "trigger_requested": int(entry_state.get("trigger_requested", 0)),
                "trigger_refused": int(entry_state.get("trigger_refused", 0)),
                "opened": int(entry_state.get("entered", 0)),
                "closed": int(entry_state.get("closed", 0)),
                "entry_funnel_diagnostics": entry_funnel_diagnostics,
                "action_coordinate_schema": action_coordinate_schema or [],
                "action_coordinate_schema_mismatch": action_coordinate_schema_mismatch,
                "action_coordinate_diagnostics": _summarize_action_coordinates(
                    action_coordinate_totals
                ),
                "survival_valid": bool(survival_valid),
                "end_equity_finite": finite_equity,
                "entry_state_diagnostics": entry_state,
            }
            self.viability_eval_history.append(row)

            inactive = completed_trades == 0 and survival_valid and finite_equity
            self.consecutive_inactive_viability_evals = (
                self.consecutive_inactive_viability_evals + 1 if inactive else 0
            )
            if (
                not self._survival_objective
                and inactive
                and self.num_timesteps >= 5_000_000
                and bool(entry_state.get("entry_state_machine", False))
                and int(entry_state.get("candidate_created", 0)) == 0
            ):
                self.viability_failure_reason = (
                    "FAIL_ENTRY_PATH: full training replay created no entry candidates"
                )
            elif (
                not self._survival_objective
                and self.num_timesteps >= 10_000_000
                and self.consecutive_inactive_viability_evals >= 2
            ):
                self.viability_failure_reason = (
                    "FAIL_POLICY_COLLAPSE: full training replay has zero trades "
                    "at consecutive 5M checkpoints"
                )
            if self.verbose:
                print(
                    "[TrainingViabilityEval] "
                    f"step={self.num_timesteps} trades={completed_trades} "
                    f"survival_valid={survival_valid} "
                    f"end_equity_finite={finite_equity} "
                    f"entry_state={entry_state}"
                )

    class ClipLogStdCallback(_Base):
        """Clamp PPO Gaussian ``log_std`` after updates (no-op on Discrete)."""

        def __init__(
            self,
            log_std_min: float = -0.7,
            log_std_max: float = 0.0,
            verbose: int = 0,
        ) -> None:
            """Initialize ClipLogStdCallback and its owned state.

            Args:
                log_std_min: Numeric value used for the log std min.
                log_std_max: Numeric value used for the log std max.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            self.log_std_min = float(log_std_min)
            self.log_std_max = float(log_std_max)

        def _clip(self) -> None:
            """Process ClipLogStdCallback."""
            clip_policy_log_std(self.model.policy, self.log_std_min, self.log_std_max)

        def _on_training_start(self) -> None:
            """Process training start."""
            self._clip()

        def _on_rollout_start(self) -> None:
            """Process rollout start."""
            self._clip()

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            return True

        def _on_training_end(self) -> None:
            """Process training end."""
            self._clip()

    class PeriodicCheckpointCallback(_Base):
        """Save the policy every ``save_freq`` environment timesteps.

        SB3 ``CheckpointCallback`` counts VecEnv calls, so ``n_envs=64`` made
        bar-length intervals skip most of a 20M run. This uses
        ``model.num_timesteps`` and also refreshes ``ppo_latest.zip``.
        """

        def __init__(
            self,
            save_freq: int,
            save_path: str | Path,
            name_prefix: str = "ppo_ckpt",
            latest_name: str = "ppo_latest",
            verbose: int = 1,
        ) -> None:
            """Initialize PeriodicCheckpointCallback and its owned state.

            Args:
                save_freq: Numeric value used for the save freq.
                save_path: Path or filename identifying the save.
                name_prefix: Text or path value identifying the name prefix.
                latest_name: Text or path value identifying the latest name.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            self.save_freq = int(save_freq)
            self.save_path = Path(save_path)
            self.name_prefix = name_prefix
            self.latest_name = latest_name
            self._next_save = self.save_freq if self.save_freq > 0 else None

        def _init_callback(self) -> None:
            """Process callback."""
            self.save_path.mkdir(parents=True, exist_ok=True)
            current = int(getattr(self.model, "num_timesteps", 0))
            if self.save_freq > 0:
                self._next_save = (current // self.save_freq + 1) * self.save_freq

        def _save(self) -> None:
            """Save PeriodicCheckpointCallback."""
            ckpt = self.save_path / f"{self.name_prefix}_{self.num_timesteps}_steps"
            save_ppo_checkpoint(self.model, ckpt)
            save_ppo_checkpoint(self.model, self.save_path / self.latest_name)
            if self.verbose:
                print(f"[PeriodicCheckpoint] timestep={self.num_timesteps} → {ckpt}.zip")

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            if self._next_save is None or self.save_freq <= 0:
                return True
            if self.num_timesteps >= self._next_save:
                self._save()
                crossed = 1 + (self.num_timesteps - self._next_save) // self.save_freq
                self._next_save += self.save_freq * crossed
            return True

    class EarlyAbortCallback(_Base):
        """Stop ``learn()`` on invalid metrics or configured hard-risk conditions.

        Returning ``False`` from ``_on_step`` is the Stable-Baselines3 stop.
        Hard-risk and no-trade checks wait until ``min_timesteps``. A peak-DD
        policy miss is reported for policy fit and never stops optimization.
        A non-finite logged metric stops immediately.
        """

        def __init__(
            self,
            min_timesteps: int = 5_000_000,
            window: int = 4,
            stop_on_nonfinite: bool = True,
            stop_on_no_trades: bool = False,
            stop_on_equity_gate: bool = False,
            verbose: int = 0,
        ) -> None:
            """Initialize EarlyAbortCallback and its owned state.

            Args:
                min_timesteps: Numeric value used for the min timesteps.
                window: Numeric value used for the window.
                stop_on_nonfinite: Whether to enable or require the stop on nonfinite.
                stop_on_no_trades: Whether to enable or require the stop on no trades.
                stop_on_equity_gate: Whether to enable or require the stop on equity gate.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            self.min_timesteps = int(min_timesteps)
            self.window = int(window)
            self.stop_on_nonfinite = bool(stop_on_nonfinite)
            self.stop_on_no_trades = bool(stop_on_no_trades)
            self.stop_on_equity_gate = bool(stop_on_equity_gate)
            self._episodes: list[dict[str, Any]] = []
            self._nonfinite = False
            self.reason: str | None = None

        def _note_episode(self, ep: dict[str, Any]) -> None:
            """Process episode.

            Args:
                ep: Key-value data used for the ep.
            """
            for key in (
                "end_equity",
                "start_equity",
                "slope",
                "max_peak_trailing_dd",
                "peak_trailing_dd_limit",
                "reward_sum",
            ):
                if key not in ep:
                    continue
                try:
                    if not np.isfinite(float(ep[key])):
                        self._nonfinite = True
                except (TypeError, ValueError):
                    self._nonfinite = True
            self._episodes.append(ep)

        def _on_rollout_end(self) -> None:
            """Process rollout end."""
            if not self.stop_on_nonfinite:
                return
            logger = getattr(self.model, "logger", None)
            values = getattr(logger, "name_to_value", {}) if logger is not None else {}
            for key, value in values.items():
                # SB3 sets this to NaN when every return in the rollout is 0.
                if str(key).endswith("explained_variance"):
                    continue
                try:
                    if not np.isfinite(float(value)):
                        self._nonfinite = True
                        return
                except (TypeError, ValueError):
                    continue

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            dones = self.locals.get("dones")
            infos = self.locals.get("infos") or []
            if dones is not None:
                for i, done in enumerate(np.asarray(dones).reshape(-1)):
                    if not done or i >= len(infos):
                        continue
                    info = infos[i]
                    ep = info.get("episode_equity") if isinstance(info, dict) else None
                    if ep:
                        self._note_episode(ep)
            reason = decide_early_abort(
                self._episodes,
                num_timesteps=int(self.num_timesteps),
                min_timesteps=self.min_timesteps,
                window=self.window,
                nonfinite=self._nonfinite,
                stop_on_nonfinite=self.stop_on_nonfinite,
                stop_on_no_trades=self.stop_on_no_trades,
                stop_on_equity_gate=self.stop_on_equity_gate,
            )
            if reason is None:
                return True
            self.reason = reason
            log.error("EARLY_ABORT %s at timestep=%s", reason, self.num_timesteps)
            return False

else:

    class TrainingProgressCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize TrainingProgressCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError("stable-baselines3 is required for TrainingProgressCallback")

    class ProgressLoggerCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize ProgressLoggerCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError(
                "stable-baselines3 is required for ProgressLoggerCallback. "
                "Install it with: pip install stable-baselines3"
            )

    class LearningDiagnosticsCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize LearningDiagnosticsCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError("stable-baselines3 is required for LearningDiagnosticsCallback")

    class EpisodeEquityCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize EpisodeEquityCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError(
                "stable-baselines3 is required for EpisodeEquityCallback. "
                "Install it with: pip install stable-baselines3"
            )

    class BestCheckpointEvalCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize BestCheckpointEvalCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError(
                "stable-baselines3 is required for BestCheckpointEvalCallback. "
                "Install it with: pip install stable-baselines3"
            )

    class ClipLogStdCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize ClipLogStdCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError(
                "stable-baselines3 is required for ClipLogStdCallback. "
                "Install it with: pip install stable-baselines3"
            )

    class PeriodicCheckpointCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize PeriodicCheckpointCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError(
                "stable-baselines3 is required for PeriodicCheckpointCallback. "
                "Install it with: pip install stable-baselines3"
            )

    class LagrangianRiskCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize LagrangianRiskCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError("stable-baselines3 is required for LagrangianRiskCallback")

    class EarlyAbortCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialize EarlyAbortCallback and its owned state.

            Args:
                *args: Parsed command-line arguments for this operation.
                **kwargs: Kwargs used by the operation described above.
            """
            raise ImportError(
                "stable-baselines3 is required for EarlyAbortCallback. "
                "Install it with: pip install stable-baselines3"
            )
