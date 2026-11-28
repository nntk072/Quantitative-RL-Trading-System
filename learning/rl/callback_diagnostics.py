"""Rollout action and learning diagnostics for SB3 PPO."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from gymnasium import spaces

try:
    from stable_baselines3.common.callbacks import BaseCallback as _Base
except ImportError:
    _Base = object  # type: ignore[assignment,misc]
    _SB3_AVAILABLE = False
else:
    _SB3_AVAILABLE = True

log = logging.getLogger("learning.rl.callbacks")


if _SB3_AVAILABLE:

    class LearningDiagnosticsCallback(_Base):
        """Write per-PPO-rollout action, advantage, reward, and funnel diagnostics."""

        def __init__(self, log_path: str | Path, verbose: int = 0) -> None:
            """Initialize LearningDiagnosticsCallback and its owned state.

            Args:
                log_path: Path or filename identifying the log.
                verbose: Numeric value used for the verbose.
            """
            super().__init__(verbose=verbose)
            self._log_path = Path(log_path)
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._rows: list[dict[str, float]] = []
            self._funnel: dict[str, float] = {}
            self._reward_parts: dict[str, float] = {}
            self._constraints: dict[str, float] = {}
            self._window_steps = 0
            self._trade_setup_entropy_sum: Any = 0.0
            self._trade_setup_entropy_count: Any = 0
            self._entry_execution_entropy_sum: Any = 0.0
            self._entry_execution_entropy_count: Any = 0

        def _on_step(self) -> bool:
            """Process step.

            Returns:
                Whether on step meets the requested condition.
            """
            infos = self.locals.get("infos") or []
            for info in infos:
                if not isinstance(info, dict):
                    continue
                self._window_steps += 1
                funnel = info.get("entry_funnel", {})
                if isinstance(funnel, dict):
                    for key, value in funnel.items():
                        self._funnel[str(key)] = self._funnel.get(str(key), 0.0) + float(value)
                parts = info.get("reward_parts", {})
                if isinstance(parts, dict):
                    for key, value in parts.items():
                        self._reward_parts[str(key)] = self._reward_parts.get(
                            str(key), 0.0
                        ) + float(value)
                constraints = info.get("constraints", {})
                if isinstance(constraints, dict):
                    for key, value in constraints.items():
                        if isinstance(value, (int, float, np.integer, np.floating)):
                            metric_key = str(key)
                            self._constraints[metric_key] = self._constraints.get(
                                metric_key, 0.0
                            ) + float(value)
            policy_entropy = getattr(
                getattr(self.model, "policy", None), "last_trade_setup_entropy", None
            )
            if policy_entropy is not None:
                detach = getattr(policy_entropy, "detach", None)
                if callable(detach):
                    # Keep this reduction on the policy device. Copying entropy
                    # to CPU on every vector step synchronizes CUDA and can
                    # dominate short-rollout training throughput.
                    entropy_values = detach().reshape(-1)
                    import torch

                    finite_mask = torch.isfinite(entropy_values)
                    self._trade_setup_entropy_sum = (
                        self._trade_setup_entropy_sum
                        + torch.where(
                            finite_mask, entropy_values, torch.zeros_like(entropy_values)
                        ).sum()
                    )
                    self._trade_setup_entropy_count = (
                        self._trade_setup_entropy_count + finite_mask.sum()
                    )
                else:
                    entropy_values = np.asarray(policy_entropy, dtype=np.float64).reshape(-1)
                    finite = entropy_values[np.isfinite(entropy_values)]
                    self._trade_setup_entropy_sum += float(finite.sum())
                    self._trade_setup_entropy_count += int(finite.size)
            policy = getattr(self.model, "policy", None)
            execution_distribution = getattr(policy, "hybrid_distribution", None)
            if execution_distribution is None:
                execution_distribution = getattr(policy, "conditioned_distribution", None)
            if execution_distribution is None:
                execution_distribution = getattr(policy, "candidate_distribution", None)
            entropy_fn = getattr(execution_distribution, "categorical_coordinate_entropy", None)
            execution_entropy = entropy_fn("entry_execution") if callable(entropy_fn) else None
            if execution_entropy is not None:
                detach = getattr(execution_entropy, "detach", None)
                if callable(detach):
                    entropy_values = detach().reshape(-1)
                    import torch

                    finite_mask = torch.isfinite(entropy_values)
                    self._entry_execution_entropy_sum = (
                        self._entry_execution_entropy_sum
                        + torch.where(
                            finite_mask, entropy_values, torch.zeros_like(entropy_values)
                        ).sum()
                    )
                    self._entry_execution_entropy_count = (
                        self._entry_execution_entropy_count + finite_mask.sum()
                    )
                else:
                    entropy_values = np.asarray(execution_entropy, dtype=np.float64).reshape(-1)
                    finite = entropy_values[np.isfinite(entropy_values)]
                    self._entry_execution_entropy_sum += float(finite.sum())
                    self._entry_execution_entropy_count += int(finite.size)
            return True

        def _on_rollout_end(self) -> None:
            """Process rollout end."""
            model: Any = self.model
            buffer = model.rollout_buffer
            entropy_sum = self._trade_setup_entropy_sum
            if hasattr(entropy_sum, "item"):
                entropy_sum = float(entropy_sum.item())
            entropy_count = self._trade_setup_entropy_count
            if hasattr(entropy_count, "item"):
                entropy_count = int(entropy_count.item())
            entropy_mean = (
                float(entropy_sum) / int(entropy_count) if entropy_count else float("nan")
            )
            self._trade_setup_entropy_sum = 0.0
            self._trade_setup_entropy_count = 0
            execution_entropy_sum = self._entry_execution_entropy_sum
            if hasattr(execution_entropy_sum, "item"):
                execution_entropy_sum = float(execution_entropy_sum.item())
            execution_entropy_count = self._entry_execution_entropy_count
            if hasattr(execution_entropy_count, "item"):
                execution_entropy_count = int(execution_entropy_count.item())
            self._entry_execution_entropy_sum = 0.0
            self._entry_execution_entropy_count = 0
            raw_actions = np.asarray(buffer.actions, dtype=np.float64)
            if isinstance(model.action_space, spaces.Box):
                actions = raw_actions.reshape(-1, raw_actions.shape[-1])
            else:
                actions = raw_actions.reshape(-1, 1)
            rewards = np.asarray(buffer.rewards, dtype=np.float64)
            advantages = np.asarray(buffer.advantages, dtype=np.float64)
            row: dict[str, float] = {
                "timestep": float(self.num_timesteps),
                "rollout/reward_mean": float(np.mean(rewards)),
                "rollout/reward_std": float(np.std(rewards)),
                "advantages/mean": float(np.mean(advantages)),
                "advantages/std": float(np.std(advantages)),
                "action/saturation_fraction": float(np.mean(np.abs(actions) >= 0.99)),
                "action/near_minus_one_fraction": float(np.mean(actions <= -0.95)),
                "action/near_plus_one_fraction": float(np.mean(actions >= 0.95)),
            }
            if execution_entropy_count:
                row["entry_execution/entropy_mean_nats"] = float(execution_entropy_sum) / int(
                    execution_entropy_count
                )
                model.logger.record(
                    "entry_execution/entropy_mean_nats",
                    row["entry_execution/entropy_mean_nats"],
                )
            schema = getattr(model, "_action_schema", {})
            raw_names = (
                schema.get("coordinates", schema.get("names", []))
                if isinstance(schema, dict)
                else []
            )
            if not raw_names:
                raw_names = getattr(getattr(model, "policy", None), "hybrid_action_coordinates", [])
            names = raw_names if isinstance(raw_names, list) else []
            if isinstance(raw_names, tuple):
                names = list(raw_names)
            if len(names) != actions.shape[1]:
                names = [f"coordinate_{index}" for index in range(actions.shape[1])]
            for index, name in enumerate(names):
                coordinate = actions[:, index]
                row[f"action/{name}_mean"] = float(np.mean(coordinate))
                row[f"action/{name}_std"] = float(np.std(coordinate))
                if "mode" in str(name) or "exit" in str(name):
                    bins = np.digitize(coordinate, [-1.0 / 3.0, 1.0 / 3.0])
                    for bin_index, label in enumerate(("low", "mid", "high")):
                        row[f"action/{name}_hist/{label}"] = float(np.mean(bins == bin_index))
            setup_coordinate = "trade_setup" if "trade_setup" in names else None
            setup_index = names.index(setup_coordinate) if setup_coordinate is not None else None
            setup_prefix = "trade_setup"
            observations = getattr(buffer, "observations", {})
            setup_mask = (
                observations.get("trade_setup_mask") if isinstance(observations, dict) else None
            )
            if setup_index is not None and setup_mask is not None:
                from decisioning.trade_setup import (
                    TRADE_SETUP_CANDIDATES,
                    TRADE_SETUP_CATEGORY_COUNT,
                )

                setup_ids = np.floor(
                    np.clip((actions[:, setup_index] + 1.0) * 0.5, 0.0, 1.0)
                    * TRADE_SETUP_CATEGORY_COUNT
                ).astype(np.int64)
                setup_ids = np.clip(setup_ids, 0, TRADE_SETUP_CATEGORY_COUNT - 1)
                masks = np.asarray(setup_mask, dtype=np.float32).reshape(
                    -1, TRADE_SETUP_CATEGORY_COUNT
                )
                if len(masks) != len(setup_ids):
                    raise ValueError("rollout setup mask and setup action counts differ")
                valid = masks[np.arange(len(masks)), setup_ids] > 0.0
                no_trade = setup_ids == 0
                execution_index = (
                    names.index("entry_execution") if "entry_execution" in names else None
                )
                selected_trade_rows = ~no_trade
                if execution_index is not None and bool(selected_trade_rows.any()):
                    market_selected = actions[selected_trade_rows, execution_index] < 0.0
                    row["entry_execution/market_selection_rate"] = float(np.mean(market_selected))
                    row["entry_execution/limit_selection_rate"] = float(np.mean(~market_selected))
                    model.logger.record(
                        "entry_execution/market_selection_rate",
                        row["entry_execution/market_selection_rate"],
                    )
                    model.logger.record(
                        "entry_execution/limit_selection_rate",
                        row["entry_execution/limit_selection_rate"],
                    )
                trade_ids = setup_ids[~no_trade]
                trade_eligible_steps = masks[:, 1:].sum(axis=1) > 0
                selected_ideas = {
                    TRADE_SETUP_CANDIDATES[int(candidate_id)].idea for candidate_id in trade_ids
                }
                selected_timeframes = {
                    TRADE_SETUP_CANDIDATES[int(candidate_id)].setup_timeframe
                    for candidate_id in trade_ids
                }
                eligible_counts = masks[:, 1:].sum(axis=1)
                row.update(
                    {
                        f"{setup_prefix}/entropy_mean_nats": (entropy_mean),
                        f"{setup_prefix}/no_trade_rate": float(np.mean(no_trade)),
                        f"{setup_prefix}/no_trade_rate_when_eligible": float(
                            np.sum(no_trade & trade_eligible_steps)
                            / max(1, int(np.sum(trade_eligible_steps)))
                        ),
                        f"{setup_prefix}/trade_eligible_step_rate": float(
                            np.mean(trade_eligible_steps)
                        ),
                        f"{setup_prefix}/no_trade_count": float(np.sum(no_trade)),
                        f"{setup_prefix}/selected_trade_count": float(len(trade_ids)),
                        f"{setup_prefix}/selected_idea_count": float(len(selected_ideas)),
                        f"{setup_prefix}/selected_timeframe_count": float(len(selected_timeframes)),
                        f"{setup_prefix}/eligible_trade_candidate_mean": float(
                            np.mean(eligible_counts)
                        ),
                        f"{setup_prefix}/invalid_selection_count": float(np.sum(~valid)),
                    }
                )
                for idea in sorted(item for item in selected_ideas if item is not None):
                    row[f"{setup_prefix}/selected_idea/{idea}_count"] = float(
                        sum(
                            TRADE_SETUP_CANDIDATES[int(candidate_id)].idea == idea
                            for candidate_id in trade_ids
                        )
                    )
                for timeframe in sorted(item for item in selected_timeframes if item is not None):
                    row[f"{setup_prefix}/selected_timeframe/{timeframe}_count"] = float(
                        sum(
                            TRADE_SETUP_CANDIDATES[int(candidate_id)].setup_timeframe == timeframe
                            for candidate_id in trade_ids
                        )
                    )
                model.logger.record(
                    f"{setup_prefix}/entropy_mean_nats", row[f"{setup_prefix}/entropy_mean_nats"]
                )
                model.logger.record(
                    f"{setup_prefix}/no_trade_rate", row[f"{setup_prefix}/no_trade_rate"]
                )
                model.logger.record(
                    f"{setup_prefix}/invalid_selection_count",
                    row[f"{setup_prefix}/invalid_selection_count"],
                )
            for key, value in self._funnel.items():
                row[f"entry_funnel/{key}"] = float(value)
                model.logger.record(f"entry_funnel/{key}", float(value))
            for key, value in self._reward_parts.items():
                row[f"reward_parts/cumulative_{key}"] = float(value)
                row[f"reward_parts/mean_{key}"] = float(value / max(1, self._window_steps))
                model.logger.record(f"reward_parts/cumulative_{key}", float(value))
                model.logger.record(
                    f"reward_parts/mean_{key}", float(value / max(1, self._window_steps))
                )
            for key, value in self._constraints.items():
                row[f"constraints/sum_{key}"] = float(value)
                row[f"constraints/mean_{key}"] = float(value / max(1, self._window_steps))
                model.logger.record(
                    f"constraints/mean_{key}", float(value / max(1, self._window_steps))
                )
            for key, value in row.items():
                if key.startswith(("action/", "rollout/", "advantages/")):
                    model.logger.record(f"quality/{key}", value)
            self._rows.append(row)
            self._funnel.clear()
            self._reward_parts.clear()
            self._constraints.clear()
            self._window_steps = 0
            self._trade_setup_entropy_sum = 0.0
            self._trade_setup_entropy_count = 0

        def _on_training_end(self) -> None:
            """Process training end."""
            if self._rows:
                pd.DataFrame(self._rows).to_csv(self._log_path, index=False)
else:

    class LearningDiagnosticsCallback:  # type: ignore[no-redef]
        """Stub — stable-baselines3 is not installed."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Reject construction when stable-baselines3 is unavailable.

            Args:
                *args: Positional callback configuration, ignored by this stub.
                **kwargs: Named callback configuration, ignored by this stub.
            """
            del args, kwargs
            raise ImportError("stable-baselines3 is required for LearningDiagnosticsCallback")
