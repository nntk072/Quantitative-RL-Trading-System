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
        trade_setup_actions: bool = False,
        candidate_geometry_actions: bool = False,
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
        server_side_protective_orders: bool = False,
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
        reachable_r_validity_mask: bool = False,
        bundle_data: Any | None = None,
        strict_research_eligibility: bool = False,
        legacy_sequence_columns: bool | None = None,
        trading_policy: dict[str, Any] | None = None,
        feature_validity_channels: bool = False,
        sequence_columns_override: tuple[str, ...] | None = None,
        agent_entry_execution: bool = False,
        limit_order_max_offset_atr: float = 1.0,
        limit_order_max_ttl_bars: int = 60,
        limit_order_require_trade_through: bool = False,
        lot_step: float = 0.01,
    ):
        """Initialize the trading environment through semantic runtime stages.

        The public constructor remains stable for saved configs and checkpoints while
        initialization mechanics live outside the Gymnasium facade.

        Args:
            bars: Market bars to process.
            features: Feature values supplied to the operation.
            obs_window: Numeric value used for the obs window.
            initial_balance: Numeric value used for the initial balance.
            cost_model: Cost model used by the operation described above.
            broker_kwargs: Key-value data used for the broker kwargs.
            guardrail_kwargs: Key-value data used for the guardrail kwargs.
            risk_frac_range: Items supplied for the risk frac range, in input order.
            rr_ratio_range: Items supplied for the rr ratio range, in input order.
            swing_buffer_pts: Numeric value used for the swing buffer pts.
            sl_mode: Text or path value identifying the sl mode.
            min_lot: Numeric value used for the min lot.
            max_lot: Numeric value used for the max lot.
            lot_step: Broker volume increment used for risk-based sizing.
            contract_size: Number specifying the contract size for this operation.
            max_loss_per_trade_usd: Numeric value used for the max loss per trade usd.
            dsr_eta: Numeric value used for the dsr eta.
            episodic: Whether to enable or require the episodic.
            use_sweep_reward: Whether to enable or require the use sweep reward.
            sweep_alpha: Numeric value used for the sweep alpha.
            sweep_beta: Numeric value used for the sweep beta.
            sweep_hold_bars: Market bar or price data used for initialize the trading environment through semantic runtime stages.
            dsr_weight: Numeric value used for the dsr weight.
            sweep_weight: Numeric value used for the sweep weight.
            continuous_actions: Whether to enable or require the continuous actions.
            max_risk_frac: Numeric value used for the max risk frac.
            use_vae: Whether to enable or require the use vae.
            vae: Vae used by the operation described above.
            pre_ny_data: Tabular data used for the pre ny data.
            pre_ny_by_date: Key-value data used for the pre ny by date.
            ny_session_start_idx: Ny session start idx used by the operation described above.
            fill_latency_bars: Whole-M1-bar delay for entry orders after the initial next-bar fill.
            agent_entry_execution: Whether the action schema includes market-versus-limit entry.
            limit_order_max_offset_atr: Maximum policy-selected limit distance in ATR units.
            limit_order_max_ttl_bars: Maximum lifetime of a policy-selected limit order in bars.
            limit_order_require_trade_through: Require quotes to trade through the limit to fill.
            max_episode_steps: Number specifying the max episode steps for this operation.
            normalize_account: Whether to enable or require the normalize account.
            strategy: Strategy used to select or evaluate trades.
            strategy_actions: Whether to enable or require the strategy actions.
            trade_setup_actions: Whether to enable or require the trade setup actions.
            candidate_geometry_actions: Whether to expose causal candidate-geometry observations.
            trader_actions: Trader actions used by the operation described above.
            sl_buffer_pts: Numeric value used for the sl buffer pts.
            strategy_reward: Strategy reward used by the operation described above.
            strategy_weight: Numeric value used for the strategy weight.
            block_overnight: Whether to enable or require the block overnight.
            eod_risk: Key-value data used for the eod risk.
            min_sl_atr_mult: Numeric value used for the min sl atr mult.
            min_sl_points: Numeric value used for the min sl points.
            max_entries_per_session: Numeric value used for the max entries per session.
            open_manipulation_bars: Market bar or price data used for initialize the trading environment through semantic runtime stages.
            entry_cooldown_bars: Market bar or price data used for initialize the trading environment through semantic runtime stages.
            reward_mode: Text or path value identifying the reward mode.
            equity_log_growth_scale: Numeric value used for the equity log growth scale.
            fixed_risk_usd: Numeric value used for the fixed risk usd.
            risk_band_max_usd: Numeric value used for the risk band max usd.
            risk_band_hold_below_usd: Numeric value used for the risk band hold below usd.
            allow_ema_exit: Whether to enable or require the allow ema exit.
            ema_runner_fraction: Numeric value used for the ema runner fraction.
            risk_mode: Text or path value identifying the risk mode.
            entry_intensity_threshold: Numeric value used for the entry intensity threshold.
            obs_features_mmap: Obs features mmap used by the operation described above.
            peak_trailing_dd_limit: Numeric value used for the peak trailing dd limit.
            tickbook: Tickbook used by the operation described above.
            tick_execution_required: Whether to enable or require the tick execution required.
            fill_delay_ms: Numeric value used for the fill delay ms.
            randomized_fill_latency_ms: Numeric value used for the randomized fill latency ms.
            max_tick_quote_wait_ms: Numeric value used for the max tick quote wait ms.
            server_side_protective_orders: Execute attached SL/TP orders on their
                triggering tick without sampling a new EA/network latency.
            tick_fill_slippage_points: Numeric value used for the tick fill slippage points.
            agent_direction_control: Whether to enable or require the agent direction control.
            direction_override_threshold: Numeric value used for the direction override threshold.
            risk_floor: Numeric value used for the risk floor.
            allow_agent_sl_mode: Whether to enable or require the allow agent sl mode.
            sl_mode_defer_threshold: Numeric value used for the sl mode defer threshold.
            allow_agent_tp_mode: Whether to enable or require the allow agent tp mode.
            tp_mode_defer_threshold: Numeric value used for the tp mode defer threshold.
            allow_multi_tp: Whether to enable or require the allow multi tp.
            tp_breakeven_alpha: Numeric value used for the tp breakeven alpha.
            tp_mode: Text or path value identifying the tp mode.
            tp_reference: Text or path value identifying the tp reference.
            allow_simplex: Whether to enable or require the allow simplex.
            mtf: Whether to enable or require the mtf.
            mtf_windows: Key-value data used for the mtf windows.
            target_timeframes: Items supplied for the target timeframes, in input order.
            scheduled_session_closes: Key-value data used for the scheduled session closes.
            session_start: Text or path value identifying the session start.
            regime_observation: Whether to enable or require the regime observation.
            entry_state_machine: Whether to enable or require the entry state machine.
            candidate_max_age_bars: Market bar or price data used for initialize the trading environment through semantic runtime stages.
            arm_requires_retest: Whether to enable or require the arm requires retest.
            entry_state_observation: Whether to enable or require the entry state observation.
            observation_schema_version: Text or path value identifying the observation schema version.
            observation_age_scale_bars: Market bar or price data used for initialize the trading environment through semantic runtime stages.
            reachable_r_validity_mask: Whether to append the reachability-validity sequence feature.
            bundle_data: Bundle data used by the operation described above.
            strict_research_eligibility: Whether to enable or require the strict research eligibility.
            legacy_sequence_columns: Legacy sequence columns used by the operation described above.
            trading_policy: Key-value data used for the trading policy.
            feature_validity_channels: Whether to append per-feature finite-value masks.
            sequence_columns_override: Exact saved feature order for a bounded replay.
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
            lot_step,
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
        if not isinstance(server_side_protective_orders, bool):
            raise ValueError("server_side_protective_orders must be boolean")
        if server_side_protective_orders and not tick_execution_required:
            raise ValueError("server-side protective fills require tick-only execution")
        self.server_side_protective_orders = server_side_protective_orders
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
        if trade_setup_actions and not resolved_strategy_actions:
            raise ValueError("trade setup actions require strategy_actions=true")
        if candidate_geometry_actions and not trade_setup_actions:
            raise ValueError("candidate_geometry_actions requires trade_setup_actions=true")
        if candidate_geometry_actions and not agent_entry_execution:
            raise ValueError("candidate_geometry_actions requires agent_entry_execution=true")
        self.trade_setup_actions = bool(trade_setup_actions)
        self.candidate_geometry_actions = bool(candidate_geometry_actions)
        self._initialize_strategy_runtime(
            strategy, resolved_strategy_actions, sl_buffer_pts, bundle_data, bars, features
        )
        self._initialize_observation_arrays(
            bundle_data,
            bars,
            features,
            legacy_sequence_columns,
            sequence_columns_override,
            episodic,
            obs_features_mmap,
            mtf,
            mtf_windows,
            target_timeframes,
            scheduled_session_closes,
            session_start,
            regime_observation,
            self.trade_setup_actions,
            reachable_r_validity_mask,
            feature_validity_channels,
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
            agent_entry_execution,
            limit_order_max_offset_atr,
            limit_order_max_ttl_bars,
            limit_order_require_trade_through,
        )
        self._initialize_episode_spaces(
            ny_session_start_idx, bars, bundle_data, use_vae, vae, obs_window
        )
        self.reset()

    @classmethod
    def from_bundle(cls, bundle_path: str | Path, **kwargs: Any) -> TradingEnv:
        """Create an environment whose persistent market arrays are read-only mmaps.

        Args:
            bundle_path: Path or filename identifying the bundle.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of create an environment whose persistent market arrays are read-only mmaps.
        """
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
        """Gymnasium adapter for :meth:`transition`.

        Args:
            action: Action to apply to the current state.

        Returns:
            Whether step meets the requested condition.
        """
        return self.transition(action).as_gymnasium()

    def transition(
        self,
        action: int | float | np.ndarray[Any, Any],
    ) -> SimulationTransition[dict[str, np.ndarray[Any, Any]]]:
        """Advance the simulator through its framework-neutral transition API.

        Args:
            action: Action to apply to the current state.

        Returns:
            Mapping from ``str`` keys to ``np.ndarray[Any, Any]]`` values.
        """
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
