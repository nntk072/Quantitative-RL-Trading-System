"""FTMO guardrail checks.

Hard limits (``daily_loss_limit``, ``max_loss_limit``) are FTMO kill-switches.
``trailing_dd_limit`` is an optional PPO-only dollar cap from peak (0 = off).
The selected ``limit_value_mode`` can use fixed dollars or percentages. In
percentage mode, per-trade and daily values use current equity, while max loss
uses initial equity. Soft bricks
(``soft_daily_loss_limit``, ``soft_trailing_dd_limit``) block new entries /
add reward pressure only — they do **not** force-close or end the day.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from trading.account import AccountState

GuardrailBreachScope = Literal["session", "rollout"]


def guardrail_breach_scope(reason: str | None) -> GuardrailBreachScope | None:
    """Return the lifecycle scope for a hard account-guardrail breach.

    Daily loss blocks the supplied session and may recover at the next session
    boundary. Maximum-loss and trailing-drawdown breaches remain latched for
    the rest of a non-episodic rollout. Episodic and repeated-payout runtimes
    retain their own termination/cycle behavior around this shared scope.

    Args:
        reason: Stable reason returned by ``FTMOGuardrails.breach_reason``.

    Returns:
        ``"session"`` for daily loss, ``"rollout"`` for max/trailing loss,
        or ``None`` when no breach occurred.

    Raises:
        ValueError: If a non-null reason is not a recognized hard breach.
    """
    if reason is None:
        return None
    if reason == "daily_loss":
        return "session"
    if reason in {"max_drawdown", "trailing_dd"}:
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

    daily_loss_limit: float = 5_000.0
    max_loss_limit: float = 10_000.0
    risk_per_trade_limit: float = 1_000.0
    soft_daily_loss_limit: float = 5_000.0
    # Matches the hard limit, so there is no earlier soft shaping band.
    soft_max_loss_limit: float = 10_000.0
    # Optional PPO-only fraction of *initial* balance as a dollar cap from peak.
    trailing_dd_limit: float = 0.0
    soft_trailing_dd_limit: float = 0.0
    limit_value_mode: str = "fixed_usd"
    risk_per_trade_limit_pct: float = 0.01
    daily_loss_limit_pct: float = 0.05
    soft_daily_loss_limit_pct: float = 0.05
    max_loss_limit_initial_pct: float = 0.10
    soft_max_loss_limit_initial_pct: float = 0.10

    def __post_init__(self) -> None:
        """Validate and initialize FTMOGuardrails after construction."""
        if self.limit_value_mode not in {"fixed_usd", "percent_equity"}:
            raise ValueError("ftmo.limit_value_mode must be 'fixed_usd' or 'percent_equity'")
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
        """Resolve the hard daily-loss threshold from the selected value mode.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``daily_limit_for``.
        """
        if self.limit_value_mode == "percent_equity":
            return max(0.0, float(acc.equity)) * float(self.daily_loss_limit_pct)
        return float(self.daily_loss_limit)

    def soft_daily_limit_for(self, acc: AccountState) -> float:
        """Resolve the soft daily threshold from current equity when requested.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``soft_daily_limit_for``.
        """
        if self.limit_value_mode == "percent_equity":
            return max(0.0, float(acc.equity)) * float(self.soft_daily_loss_limit_pct)
        return float(self.soft_daily_loss_limit)

    def max_loss_limit_for(self, acc: AccountState) -> float:
        """Resolve the maximum-loss threshold; percentage mode uses initial equity.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``max_loss_limit_for``.
        """
        if self.limit_value_mode == "percent_equity":
            return max(0.0, float(acc.initial_balance)) * float(self.max_loss_limit_initial_pct)
        return float(self.max_loss_limit)

    def soft_max_loss_limit_for(self, acc: AccountState) -> float:
        """Resolve the soft maximum-loss threshold from initial equity.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Numeric result returned by ``soft_max_loss_limit_for``.
        """
        if self.limit_value_mode == "percent_equity":
            return max(0.0, float(acc.initial_balance)) * float(
                self.soft_max_loss_limit_initial_pct
            )
        return float(self.soft_max_loss_limit)

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
        return risk_state.daily_pnl <= -risk_state.daily_loss_limit

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
        """Return True if absolute loss from *initial* balance ≥ ``max_loss_limit``.

        This is FTMO-style max loss (fixed from deposit), **not** trailing
        high-water-mark drawdown from peak equity.

        Args:
            acc: Acc used by the operation described above.

        Returns:
            Whether check max drawdown meets the requested condition.
        """
        return acc.loss_from_initial() >= self.max_loss_limit_for(acc)

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
        return risk > limit

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
