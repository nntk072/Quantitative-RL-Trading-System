"""FTMO guardrail checks.

Hard daily and maximum-loss thresholds are configured as percentages of
initial equity. The daily allowance is applied to each session's
starting-equity anchor. ``limit_value_mode`` controls the per-trade risk limit;
historical dollar-valued loss fields remain accepted as compatibility inputs
but do not change the percentage-based loss rules. ``trailing_dd_limit`` is an
optional PPO-only cap from peak (0 = off). Soft bricks
(``soft_daily_loss_limit``, ``soft_trailing_dd_limit``) block new entries /
add reward pressure only — they do **not** force-close or end the day.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from trading.account import AccountState

GuardrailBreachScope = Literal["session", "rollout"]
MaximumLossDrawdownMode = Literal["static", "eod", "intraday_trailing"]


def guardrail_breach_scope(reason: str | None) -> GuardrailBreachScope | None:
    """Return the lifecycle scope for a hard account-guardrail breach.

    Any hard account-loss breach fails the full evaluation. Daily loss remains
    measured against the supplied session anchor, but crossing that floor
    latches the account failure across later sessions.

    Args:
        reason: Stable reason returned by ``FTMOGuardrails.breach_reason``.

    Returns:
        ``"rollout"`` for a hard loss breach, or ``None`` when no breach
        occurred.

    Raises:
        ValueError: If a non-null reason is not a recognized hard breach.
    """
    if reason is None:
        return None
    if reason in {"daily_loss", "max_drawdown", "trailing_dd"}:
        return "rollout"
    raise ValueError(f"unsupported hard guardrail breach reason: {reason!r}")


def adverse_position_loss_limit_usd(
    configured_limit_usd: float,
    planned_risk_usd: float,
    *,
    respect_planned_risk: bool,
    planned_risk_multiplier: float,
) -> float:
    """Resolve the adverse-excursion cutoff without placing it inside planned risk.

    Args:
        configured_limit_usd: Configured dollar floor for adverse excursion.
        planned_risk_usd: Entry risk at the structural stop, if known.
        respect_planned_risk: Whether the cutoff must include planned risk.
        planned_risk_multiplier: Multiplier applied to planned risk.

    Returns:
        The adverse-excursion cutoff in account currency.

    Raises:
        ValueError: If a limit or multiplier is non-finite or negative.
    """
    configured = float(configured_limit_usd)
    planned = float(planned_risk_usd)
    multiplier = float(planned_risk_multiplier)
    if not all(math.isfinite(value) for value in (configured, planned, multiplier)):
        raise ValueError("adverse-loss limits must be finite")
    if configured < 0.0 or planned < 0.0 or multiplier < 0.0:
        raise ValueError("adverse-loss limits and planned-risk multiplier must be nonnegative")
    if not respect_planned_risk or planned <= 0.0:
        return configured
    return max(configured, multiplier * planned)


@dataclass(frozen=True)
class FTMOGuardrails:
    """Training-compatible account guardrails for daily and total loss limits.

    Attributes:
        max_loss_limit: Maximum permitted total account loss.
        risk_per_trade_limit: Maximum risk budget for one trade.
    """

    # Dollar-valued threshold fields below are retained for source compatibility;
    # loss-floor calculations always use the percentage fields.
    daily_loss_limit: float = 5_000.0
    max_loss_limit: float = 10_000.0
    risk_per_trade_limit: float = 1_000.0
    soft_daily_loss_limit: float = 5_000.0
    # Matches the hard limit, so there is no earlier soft shaping band.
    soft_max_loss_limit: float = 10_000.0
    # Optional PPO-only fraction of *initial* balance as a dollar cap from peak.
    trailing_dd_limit: float = 0.0
    soft_trailing_dd_limit: float = 0.0
    limit_value_mode: str = "percent_equity"
    risk_per_trade_limit_pct: float = 0.01
    daily_loss_limit_pct: float = 0.05
    soft_daily_loss_limit_pct: float = 0.05
    max_loss_limit_initial_pct: float = 0.10
    soft_max_loss_limit_initial_pct: float = 0.10
    max_drawdown_mode: MaximumLossDrawdownMode = "static"

    def __post_init__(self) -> None:
        """Validate and initialize FTMOGuardrails after construction."""
        if self.limit_value_mode not in {"fixed_usd", "percent_equity"}:
            raise ValueError("ftmo.limit_value_mode must be 'fixed_usd' or 'percent_equity'")
        if self.max_drawdown_mode not in {"static", "eod", "intraday_trailing"}:
            raise ValueError(
                "ftmo.max_drawdown_mode must be 'static', 'eod', or 'intraday_trailing'"
            )
        percentages = (
            self.risk_per_trade_limit_pct,
            self.daily_loss_limit_pct,
            self.soft_daily_loss_limit_pct,
            self.max_loss_limit_initial_pct,
            self.soft_max_loss_limit_initial_pct,
        )
        if any(not math.isfinite(float(value)) or float(value) < 0.0 for value in percentages):
            raise ValueError("FTMO percentage limits must be finite and non-negative")
        if any(float(value) > 1.0 for value in percentages):
            raise ValueError("FTMO percentage limits must be fractions in [0, 1]")

    def daily_limit_for(self, acc: AccountState) -> float:
        """Derive the hard daily-loss threshold from initial equity only.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``daily_limit_for``.
        """
        return max(0.0, float(acc.initial_balance)) * float(self.daily_loss_limit_pct)

    def soft_daily_limit_for(self, acc: AccountState) -> float:
        """Derive the soft daily threshold from initial equity only.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``soft_daily_limit_for``.
        """
        return max(0.0, float(acc.initial_balance)) * float(self.soft_daily_loss_limit_pct)

    def max_loss_limit_for(self, acc: AccountState) -> float:
        """Derive the maximum-loss allowance from initial equity only.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``max_loss_limit_for``.
        """
        return max(0.0, float(acc.initial_balance)) * float(self.max_loss_limit_initial_pct)

    def max_loss_floor_for(self, acc: AccountState) -> float:
        """Return the active maximum-loss floor, capped at initial equity.

        Static drawdown uses the initial-equity floor. EOD drawdown ratchets
        from completed-session highs; intraday trailing drawdown ratchets from
        the running equity high. Both use the same initial-equity loss
        allowance and stop ratcheting once the floor reaches initial equity.

        Args:
            acc: Account state containing initial and reference equity values.

        Returns:
            Active maximum-loss equity floor, capped at initial balance.
        """
        initial = float(acc.initial_balance)
        allowance = self.max_loss_limit_for(acc)
        floor = initial - allowance
        if self.max_drawdown_mode == "eod":
            floor = max(floor, float(acc.peak_eod_equity) - allowance)
        elif self.max_drawdown_mode == "intraday_trailing":
            floor = max(floor, float(acc.peak_equity) - allowance)
        if self.max_drawdown_mode != "static" and acc.payout_drawdown_floor is not None:
            floor = max(floor, float(acc.payout_drawdown_floor))
        return min(initial, floor)

    def max_drawdown_from_reference(self, acc: AccountState) -> float:
        """Return current loss from the reference equity for the selected mode.

        Args:
            acc: Account state containing current and reference equity values.

        Returns:
            Nonnegative drawdown amount from the mode-specific reference.
        """
        if self.max_drawdown_mode == "eod":
            reference = float(acc.peak_eod_equity)
        elif self.max_drawdown_mode == "intraday_trailing":
            reference = float(acc.peak_equity)
        else:
            reference = float(acc.initial_balance)
        return max(0.0, reference - float(acc.equity))

    def soft_max_loss_limit_for(self, acc: AccountState) -> float:
        """Derive the soft maximum-loss threshold from initial equity only.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``soft_max_loss_limit_for``.
        """
        return max(0.0, float(acc.initial_balance)) * float(self.soft_max_loss_limit_initial_pct)

    def risk_per_trade_limit_for(self, acc: AccountState) -> float:
        """Resolve the hard per-trade threshold from current equity if selected.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``risk_per_trade_limit_for``.
        """
        if self.limit_value_mode == "percent_equity":
            return max(0.0, float(acc.equity)) * float(self.risk_per_trade_limit_pct)
        return float(self.risk_per_trade_limit)

    def check_daily(self, acc: AccountState) -> bool:
        """Return True (breached) if daily loss exceeds the hard limit.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Whether check daily meets the requested condition.
        """
        risk_state = acc.to_risk_state(daily_loss_limit=self.daily_limit_for(acc))
        return risk_state.daily_pnl < -risk_state.daily_loss_limit

    def check_soft_daily(self, acc: AccountState) -> bool:
        """Return True when the soft brick is active (no new entries).

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Whether check soft daily meets the requested condition.
        """
        soft = self.soft_daily_limit_for(acc)
        if soft <= 0.0:
            return False
        risk_state = acc.to_risk_state(daily_loss_limit=soft)
        return risk_state.daily_pnl <= -risk_state.daily_loss_limit

    def check_max_drawdown(self, acc: AccountState) -> bool:
        """Return True when equity breaches the configured maximum-loss floor.

        Every maximum-loss mode allows equity to touch its floor. A breach
        occurs only after equity moves below the active floor.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Whether check max drawdown meets the requested condition.
        """
        floor = self.max_loss_floor_for(acc)
        return float(acc.equity) < floor

    def check_trailing_dd(self, acc: AccountState) -> bool:
        """Return True if enabled peak-to-trough DD reaches its initial-balance cap.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Whether check trailing dd meets the requested condition.
        """
        hard = float(self.trailing_dd_limit)
        if hard <= 0.0:
            return False
        cap = hard * float(acc.initial_balance)
        return (acc.peak_equity - acc.equity) >= cap

    def check_soft_trailing_dd(self, acc: AccountState) -> bool:
        """Return True when the trailing-DD soft brick is active.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Whether check soft trailing dd meets the requested condition.
        """
        soft = float(self.soft_trailing_dd_limit)
        if soft <= 0.0:
            return False
        cap = soft * float(acc.initial_balance)
        return (acc.peak_equity - acc.equity) >= cap

    def check_trade_risk(self, risk: float, acc: AccountState | None = None) -> bool:
        """Return True (breached) if *risk* $ per trade exceeds the limit.

        Args:
            risk: Numeric value used for the risk.
            acc: Acc used by the operation described above.

        Returns:
            Whether check trade risk meets the requested condition.
        """
        limit = self.risk_per_trade_limit if acc is None else self.risk_per_trade_limit_for(acc)
        # Allow equality, including the final floating-point ulp introduced by
        # converting an affordable stepped lot count back into dollar risk.
        return float(risk) > float(limit) + 1e-9

    def any_breach(self, acc: AccountState) -> bool:
        """Return whether any configured account guardrail is breached.

        Args:
            acc: Current account state to evaluate.

        Returns:
            True when a daily, total-loss, or trade-risk limit is exceeded.
        """
        return self.check_trailing_dd(acc) or self.check_daily(acc) or self.check_max_drawdown(acc)

    def breach_reason(self, acc: AccountState) -> str | None:
        """Return the first breached guardrail name, or None when all pass.

        Args:
            acc: Current account state to evaluate.

        Returns:
            Stable reason code for the first breach, otherwise None.
        """
        if self.check_trailing_dd(acc):
            return "trailing_dd"
        if self.check_max_drawdown(acc):
            return "max_drawdown"
        if self.check_daily(acc):
            return "daily_loss"
        return None
