from __future__ import annotations

from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import pandas as pd

from decisioning.observations import OBSERVATION_SCHEMA_V1
from market_data.loading.ticks import TickBook
from simulation.contracts import SimulationTransition
from simulation.environment.diagnostics import DebugStepError
from trading.execution import COST_US100, CostModel
from trading.strategies import TradingStrategy

from .action_runtime import ActionDecodingMixin
from .diagnostics_runtime import DiagnosticsRuntimeMixin
from .entry_execution_runtime import EntryExecutionRuntimeMixin
from .entry_runtime import EntryRuntimeMixin
from .episode_runtime import EpisodeRuntimeMixin
from .execution_runtime import ExecutionRuntimeMixin
from .initialization_runtime import InitializationRuntimeMixin
from .market_access import MarketAccessMixin
from .observation_runtime import ObservationRuntimeMixin
from .position_runtime import PositionRuntimeMixin
from .risk_runtime import RiskRuntimeMixin
from .step_runtime import StepRuntimeMixin

__all__ = ["TradingEnv"]


class TradingEnv(
    InitializationRuntimeMixin,
    MarketAccessMixin,
    RiskRuntimeMixin,
    ExecutionRuntimeMixin,
    ActionDecodingMixin,
    EntryExecutionRuntimeMixin,
    EntryRuntimeMixin,
    DiagnosticsRuntimeMixin,
    StepRuntimeMixin,
    EpisodeRuntimeMixin,
    PositionRuntimeMixin,
    ObservationRuntimeMixin,
    gym.Env[Any, np.ndarray[Any, Any]],
):
    """RL trading environment with structure-aware SL/TP and hybrid action space."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        bars: pd.DataFrame | None,
        features: pd.DataFrame | None,
        obs_window: int = 60,
        initial_balance: float = 100_000.0,
        cost_model: CostModel = COST_US100,
        broker_kwargs: dict[str, Any] | None = None,
        guardrail_kwargs: dict[str, Any] | None = None,
        risk_frac_range: tuple[float, float] = (0.005, 0.02),
        rr_ratio_range: tuple[float, float] = (1.0, 3.0),
        swing_buffer_pts: float = 1.0,
        sl_mode: str = "fixed",
        min_lot: float = 0.01,
        max_lot: float = 100.0,
        contract_size: float = 1.0,
        max_loss_per_trade_usd: float = 100.0,
        dsr_eta: float = 0.01,
        episodic: bool = True,
        use_sweep_reward: bool = False,
        sweep_alpha: float = 0.1,
        sweep_beta: float = 0.01,
        sweep_hold_bars: int = 3,
        dsr_weight: float = 0.3,
        sweep_weight: float = 0.7,
        continuous_actions: bool = False,
        max_risk_frac: float = 0.01,
        use_vae: bool = False,
        vae: Any | None = None,
        pre_ny_data: pd.DataFrame | None = None,
        pre_ny_by_date: dict[Any, np.ndarray[Any, Any]] | None = None,
        ny_session_start_idx: int | None = None,
        fill_latency_bars: int = 0,
        max_episode_steps: int | None = None,
        normalize_account: bool = True,
        strategy: TradingStrategy | None = None,
        strategy_actions: bool = False,
        thesis_actions: bool = False,
        trade_setup_actions: bool = False,
        trader_actions: bool | None = None,
        sl_buffer_pts: float = 0.0,
        strategy_reward: Any = None,
        strategy_weight: float = 0.0,
        block_overnight: bool = True,
        eod_risk: dict[str, Any] | None = None,
        min_sl_atr_mult: float = 0.5,
        min_sl_points: float = 0.0,
        max_entries_per_session: int = 0,
        open_manipulation_bars: int = 10,
        entry_cooldown_bars: int = 0,
        reward_mode: str = "dsr",
        equity_log_growth_scale: float = 100.0,
        fixed_risk_usd: float = 0.0,
        risk_band_max_usd: float = 0.0,
        risk_band_hold_below_usd: float = 0.0,
        allow_ema_exit: bool = True,
        ema_runner_fraction: float = 0.0,
        risk_mode: str = "dynamic",
        entry_intensity_threshold: float = 0.0,
        obs_features_mmap: str | None = None,
        peak_trailing_dd_limit: float = 0.0,
        tickbook: TickBook | None = None,
        tick_execution_required: bool = False,
        fill_delay_ms: int = 0,
        randomized_fill_latency_ms: float = 0.0,
        max_tick_quote_wait_ms: int = 60_000,
        tick_fill_slippage_points: float = 0.0,
        agent_direction_control: bool = False,
        direction_override_threshold: float = 0.0,
        risk_floor: float = 0.0005,
        allow_agent_sl_mode: bool = True,
        sl_mode_defer_threshold: float = 0.1,
        allow_agent_tp_mode: bool = False,
        tp_mode_defer_threshold: float = 0.1,
        allow_multi_tp: bool = False,
        tp_breakeven_alpha: float = 0.5,
        tp_mode: str = "fixed",
        tp_reference: str = "structural",
        allow_simplex: bool = True,
        mtf: bool = False,
        mtf_windows: dict[str, int] | None = None,
        target_timeframes: tuple[str, ...] = ("M5", "M15", "H1"),
        scheduled_session_closes: dict[str, str] | None = None,
        session_start: str = "16:30",
        regime_observation: bool = False,
        entry_state_machine: bool = False,
        candidate_max_age_bars: int = 5,
        arm_requires_retest: bool = False,
        entry_state_observation: bool = True,
        observation_schema_version: str = OBSERVATION_SCHEMA_V1,
        observation_age_scale_bars: float = 60.0,
        bundle_data: Any | None = None,
        strict_research_eligibility: bool = False,
        legacy_sequence_columns: bool | None = None,
        trading_policy: dict[str, Any] | None = None,
    ):
        """Initialize the trading environment through semantic runtime stages.

        The public constructor remains stable for saved configs and checkpoints while
        initialization mechanics live outside the Gymnasium facade.
        """
        self._initialize_market_source(bars, features, bundle_data, strict_research_eligibility)
        self._initialize_account_policy(
            obs_window,
            initial_balance,
            cost_model,
            broker_kwargs,
            trading_policy,
            guardrail_kwargs,
            risk_frac_range,
            rr_ratio_range,
            sl_buffer_pts,
            sl_mode,
            tp_mode,
            tp_reference,
            min_lot,
            max_lot,
            contract_size,
            max_loss_per_trade_usd,
            block_overnight,
            eod_risk,
        )
        self._initialize_risk_and_entry_controls(
            episodic,
            legacy_sequence_columns,
            use_sweep_reward,
            min_sl_atr_mult,
            min_sl_points,
            max_entries_per_session,
            risk_mode,
            fixed_risk_usd,
            risk_band_max_usd,
            risk_band_hold_below_usd,
            open_manipulation_bars,
            entry_cooldown_bars,
            allow_ema_exit,
            ema_runner_fraction,
            reward_mode,
            entry_intensity_threshold,
            peak_trailing_dd_limit,
            agent_direction_control,
            direction_override_threshold,
            allow_agent_sl_mode,
            sl_mode_defer_threshold,
            allow_agent_tp_mode,
            tp_mode_defer_threshold,
            allow_multi_tp,
            tp_breakeven_alpha,
            allow_simplex,
            entry_state_machine,
            candidate_max_age_bars,
            arm_requires_retest,
            entry_state_observation,
            observation_schema_version,
            observation_age_scale_bars,
            risk_floor,
        )
        self._initialize_execution_controls(
            tickbook,
            tick_execution_required,
            fill_delay_ms,
            randomized_fill_latency_ms,
            max_tick_quote_wait_ms,
            tick_fill_slippage_points,
        )
        resolved_strategy_actions = self._initialize_reward_runtime(
            trader_actions,
            strategy_actions,
            use_sweep_reward,
            strategy_reward,
            dsr_eta,
            sweep_alpha,
            sweep_beta,
            sweep_hold_bars,
            dsr_weight,
            sweep_weight,
            strategy_weight,
            equity_log_growth_scale,
        )
        if thesis_actions and trade_setup_actions:
            raise ValueError(
                "configure either legacy thesis_actions or trade_setup_actions, not both"
            )
        if (thesis_actions or trade_setup_actions) and not resolved_strategy_actions:
            raise ValueError("trade setup actions require strategy_actions=true")
        self.legacy_thesis_contract = bool(thesis_actions)
        self.trade_setup_actions = bool(thesis_actions or trade_setup_actions)
        # Runtime compatibility alias; persisted config key remains readable.
        self.thesis_actions = bool(thesis_actions)
        self._initialize_strategy_runtime(
            strategy, resolved_strategy_actions, sl_buffer_pts, bundle_data, bars, features
        )
        self._initialize_observation_arrays(
            bundle_data,
            bars,
            features,
            legacy_sequence_columns,
            episodic,
            obs_features_mmap,
            mtf,
            mtf_windows,
            target_timeframes,
            scheduled_session_closes,
            session_start,
            regime_observation,
            self.trade_setup_actions,
        )
        self._initialize_action_and_episode_contracts(
            continuous_actions,
            max_risk_frac,
            use_vae,
            vae,
            pre_ny_by_date,
            pre_ny_data,
            fill_latency_bars,
            max_episode_steps,
            normalize_account,
        )
        self._initialize_episode_spaces(
            ny_session_start_idx, bars, bundle_data, use_vae, vae, obs_window
        )
        self.reset()

    @classmethod
    def from_bundle(cls, bundle_path: str | Path, **kwargs: Any) -> TradingEnv:
        """Create an environment whose persistent market arrays are read-only mmaps."""
        from datetime import date

        from .shared_bundle import load_bundle

        bundle = load_bundle(bundle_path)
        arrays = {name: np.asarray(array) for name, array in bundle.arrays.items()}
        manifest = bundle.manifest
        labels = manifest.get("labels", {})
        pre_ny_by_date = {
            date.fromisoformat(day): arrays["pre_ny_seq"][row]
            for day, row in labels.get("pre_ny_day_to_row", {}).items()
        }
        env = cls(
            bars=None,
            features=None,
            bundle_data=bundle,
            pre_ny_by_date=pre_ny_by_date,
            tickbook=TickBook(arrays["tick_ts"], arrays["tick_bid"], arrays["tick_ask"]),
            **kwargs,
        )
        return env

    def step(
        self,
        action: int | float | np.ndarray[Any, Any],
    ) -> tuple[dict[str, np.ndarray[Any, Any]], float, bool, bool, dict[str, Any]]:
        """Gymnasium adapter for :meth:`transition`."""
        return self.transition(action).as_gymnasium()

    def transition(
        self,
        action: int | float | np.ndarray[Any, Any],
    ) -> SimulationTransition[dict[str, np.ndarray[Any, Any]]]:
        """Advance the simulator through its framework-neutral transition API."""
        if not self._debug_trace:
            return self._step_untraced(action)
        try:
            return self._step_untraced(action)
        except DebugStepError:
            raise
        except Exception as exc:
            position = self.position
            raise DebugStepError(
                "exception",
                {
                    "action": action.tolist() if isinstance(action, np.ndarray) else action,
                    "reward": None,
                    "reward_parts": {},
                    "position": position is not None,
                    "position_direction": 0 if position is None else int(position.direction),
                },
                exc,
            ) from exc
