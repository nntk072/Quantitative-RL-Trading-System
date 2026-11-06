"""Focused simulation initialization service."""

from __future__ import annotations

from typing import Any

from trading.execution import Broker, CostModel
from trading.policy import TradingPolicyConfig
from trading.risk import FTMOGuardrails

from .mixin_base import RuntimeMixinBase
from .position_constants import _SL_MODE_RANK, _TP_MODE_RANK


class AccountPolicyInitializationMixin(RuntimeMixinBase):
    """Initialize account constraints, broker costs, and the trading policy."""

    def _initialize_account_policy(
        self,
        obs_window: int,
        initial_balance: float,
        cost_model: CostModel,
        broker_kwargs: dict[str, Any] | None,
        trading_policy: dict[str, Any] | None,
        guardrail_kwargs: dict[str, Any] | None,
        risk_frac_range: tuple[float, float],
        rr_ratio_range: tuple[float, float],
        sl_buffer_pts: float,
        sl_mode: str,
        tp_mode: str,
        tp_reference: str,
        min_lot: float,
        max_lot: float,
        lot_step: float,
        contract_size: float,
        max_loss_per_trade_usd: float,
        block_overnight: bool,
        eod_risk: dict[str, Any] | None,
    ) -> None:
        """Initialize account policy.

        Args:
            obs_window: Numeric value used for the obs window.
            initial_balance: Numeric value used for the initial balance.
            cost_model: Cost model used by the operation described above.
            broker_kwargs: Key-value data used for the broker kwargs.
            trading_policy: Key-value data used for the trading policy.
            guardrail_kwargs: Key-value data used for the guardrail kwargs.
            risk_frac_range: Items supplied for the risk frac range, in input order.
            rr_ratio_range: Items supplied for the rr ratio range, in input order.
            sl_buffer_pts: Numeric value used for the sl buffer pts.
            sl_mode: Text or path value identifying the sl mode.
            tp_mode: Text or path value identifying the tp mode.
            tp_reference: Text or path value identifying the tp reference.
            min_lot: Numeric value used for the min lot.
            max_lot: Numeric value used for the max lot.
            lot_step: Broker volume increment for risk-based sizing.
            contract_size: Number specifying the contract size for this operation.
            max_loss_per_trade_usd: Numeric value used for the max loss per trade usd.
            block_overnight: Whether to enable or require the block overnight.
            eod_risk: Key-value data used for the eod risk.
        """
        self.obs_window = obs_window
        self.initial_balance = initial_balance
        self.cost_model = cost_model
        self.broker = Broker(cost_model=cost_model, **(broker_kwargs or {}))
        policy_values = dict(trading_policy or {})
        self.trading_policy = TradingPolicyConfig(**policy_values).validate()
        self.repeated_payout_policy = self.trading_policy.repeated_payout
        if (
            self.repeated_payout_policy
            and abs(float(initial_balance) - self.trading_policy.operating_balance) > 1e-9
        ):
            raise ValueError("repeated-payout initial balance must equal operating_balance")
        resolved_guardrails = dict(guardrail_kwargs or {})
        if self.repeated_payout_policy:
            if self.trading_policy.max_loss_limit_initial_pct is None:
                raise ValueError("maximum-loss percentage is required for repeated payouts")
            resolved_guardrails.update(
                risk_per_trade_limit=self.trading_policy.operating_balance
                * self.trading_policy.max_agent_risk_frac,
                trailing_dd_limit=0.0,
                soft_trailing_dd_limit=0.0,
                limit_value_mode="percent_equity",
                risk_per_trade_limit_pct=self.trading_policy.max_agent_risk_frac,
                daily_loss_limit_pct=self.trading_policy.daily_loss_limit_pct,
                soft_daily_loss_limit_pct=0.0,
                max_loss_limit_initial_pct=float(self.trading_policy.max_loss_limit_initial_pct),
                soft_max_loss_limit_initial_pct=0.0,
            )
        self.guardrails = FTMOGuardrails(**resolved_guardrails)

        self.risk_frac_range = (
            (0.0, self.trading_policy.max_agent_risk_frac)
            if self.repeated_payout_policy
            else risk_frac_range
        )
        self.rr_ratio_range = rr_ratio_range
        self.swing_buffer_pts = float(sl_buffer_pts)
        self.sl_mode = str(sl_mode or "fixed").lower()
        if self.sl_mode not in _SL_MODE_RANK:
            raise ValueError(f"Unknown sl_mode: {self.sl_mode!r}")
        self.tp_mode = str(tp_mode or "fixed").lower()
        if self.tp_mode not in _TP_MODE_RANK:
            raise ValueError(f"Unknown tp_mode: {self.tp_mode!r}")
        self.tp_reference = str(tp_reference or "structural")
        self.min_lot = min_lot
        self.max_lot = max_lot
        if not 0.0 < float(lot_step) < float("inf"):
            raise ValueError("lot_step must be finite and positive")
        self.lot_step = float(lot_step)
        self.contract_size = contract_size
        self.max_loss_per_trade_usd = max_loss_per_trade_usd
        self.block_overnight = bool(block_overnight)
        eod = dict(eod_risk or {})
        self._eod_max_loss_usd = float(eod.get("max_loss_usd", 500.0))
        self._eod_max_age_hours = float(eod.get("max_age_hours", 8.0))
        self._eod_stale_bars = int(eod.get("stale_bars", 60))
        self._eod_progress_atr = float(eod.get("progress_threshold_atr", 0.25))
        # Optional account policy: a fixed dollar trailing loss measured from
        # the highest completed NY-session equity. The environment checks it
        # only at session end and holds new entries until an EOD high is made.
        self._peak_eod_trailing_dd_limit_usd = float(eod.get("peak_trailing_dd_limit_usd", 0.0))
        if self._peak_eod_trailing_dd_limit_usd < 0.0:
            raise ValueError("eod_risk.peak_trailing_dd_limit_usd must be nonnegative")
        self._peak_eod_dd_locked = False
        # Risk/sizing alignment: the intraday adverse-excursion cut never
        # fires closer than the trade's own planned loss at the structural
        # stop. Without this, a $500 cutoff flattens a position sized to
        # risk $1,000 and the structural stop never gets a chance to act.
        self._eod_respect_planned_risk = bool(eod.get("respect_planned_risk", True))
        self._eod_planned_risk_mult = float(eod.get("planned_risk_mult", 1.1))
        # Breakeven management: once favorable excursion reaches this many
        # stop distances, the stop moves to the entry plus a small buffer.
        # 0 disables the rewrite.
        self._breakeven_trigger_r = float(eod.get("breakeven_trigger_r", 0.0))
        self._breakeven_buffer_pts = float(eod.get("breakeven_buffer_pts", 2.0))


__all__ = ["AccountPolicyInitializationMixin"]
