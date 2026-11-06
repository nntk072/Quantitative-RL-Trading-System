"""Differential Sharpe Ratio (DSR) and PnL rewards.

Reference: Moody & Saffell (2001) "Learning to trade via direct reinforcement".
Reward = dS_t / dF_t · ΔF_t  (first-order approximation)

We also add:
- Soft penalty for FTMO daily-loss proximity
- Soft penalty for year max-loss proximity (loss_from_initial)
- Cost term (already captured in PnL but can be explicit)
- Hard breach → terminal negative reward
"""

from __future__ import annotations

import numpy as np

REWARD_PART_KEYS: tuple[str, ...] = (
    "pnl",
    "dsr",
    "soft_daily",
    "soft_year",
    "soft_trailing",
    "strategy",
    "breach",
    "sweep",
    "peak_dd",
    "peak_eod_dd",
    "equity_growth",
    "survival",
)


def empty_reward_parts() -> dict[str, float]:
    """Zero split of one step reward. The keys sum to the returned reward.

    Returns:
        Mapping from ``str`` keys to ``float`` values.
    """
    return {key: 0.0 for key in REWARD_PART_KEYS}


class SurvivalReward:
    """Reward complete breach-free paths and make a hard breach infeasible.

    Intermediate transitions carry no portfolio objective. The environment
    supplies the path outcome at its terminal boundary: a hard breach is -1,
    a complete breach-free split is +1, and all other transitions are 0.
    """

    def __init__(self) -> None:
        """Initialize empty per-component reward attribution."""
        self.last_parts: dict[str, float] = empty_reward_parts()

    def reset(self) -> None:
        """Clear the component breakdown for the next episode."""
        self.last_parts = empty_reward_parts()

    def __call__(self, *, breached: bool, completed_data_split: bool) -> float:
        """Score one path transition using account outcome, never profit.

        Args:
            breached: Whether the account breached a hard risk limit.
            completed_data_split: Whether the path completed the full data split.

        Returns:
            Survival reward: negative on breach, positive on full completion, otherwise zero.
        """
        reward = -1.0 if breached else 1.0 if completed_data_split else 0.0
        self.last_parts = fit_reward_parts({"survival": reward}, reward, reward)
        return reward


def fit_reward_parts(parts: dict[str, float], raw: float, clipped: float) -> dict[str, float]:
    """Scale a split so it sums to the clipped reward the agent receives.

    Args:
        parts: Key-value data used for the parts.
        raw: Numeric value used for the raw.
        clipped: Numeric value used for the clipped.

    Returns:
        Mapping from ``str`` keys to ``float`` values.
    """
    out = empty_reward_parts()
    out.update({key: float(value) for key, value in parts.items()})
    if raw != 0.0 and clipped != raw:
        scale = clipped / raw
        out = {key: float(value) * scale for key, value in out.items()}
    return out


def _soft_band_penalty(
    value: float,
    soft: float | None,
    hard: float,
    *,
    weight: float = 0.5,
) -> float:
    """Linear penalty in ``(soft, hard]``; 0 below soft.

    Args:
        value: Value to process.
        soft: Soft used by the operation described above.
        hard: Numeric value used for the hard.
        weight: Numeric value used for the weight.

    Returns:
        Numeric result returned by ``_soft_band_penalty``.
    """
    soft_v = float(soft) if soft is not None and soft > 0.0 else 0.0
    if soft_v <= 0.0 or hard <= soft_v or value <= soft_v:
        return 0.0
    excess = (value - soft_v) / (hard - soft_v + 1e-9)
    return weight * float(np.clip(excess, 0.0, 1.0))


def _fresh_band_state() -> dict[str, bool]:
    """Process band state.

    Returns:
        Whether fresh band state meets the requested condition.
    """
    return {"soft_daily": False, "soft_year": False, "soft_trailing": False}


def _charge_band_once(
    state: dict[str, bool],
    key: str,
    value: float,
    soft: float | None,
    hard: float,
    *,
    weight: float = 0.5,
) -> float:
    """Penalise the bar that enters the band. Later bars inside it pay nothing.

    Args:
        state: State object read or updated by the operation.
        key: Text or path value identifying the key.
        value: Value to process.
        soft: Soft used by the operation described above.
        hard: Numeric value used for the hard.
        weight: Numeric value used for the weight.

    Returns:
        Numeric result returned by ``_charge_band_once``.
    """
    penalty = _soft_band_penalty(value, soft, hard, weight=weight)
    inside = penalty > 0.0
    entered = inside and not state[key]
    state[key] = inside
    return -penalty if entered else 0.0


class DSRReward:
    """Online differential Sharpe reward with FTMO soft penalties."""

    def __init__(self, eta: float = 0.01, *, breach_penalty: float = -1.0) -> None:
        """Initialize DSRReward and its owned state.

        Args:
            eta: Numeric value used for the eta.
            breach_penalty: Numeric value used for the breach penalty.
        """
        self.eta = eta  # EMA damping for A and B estimates
        self.breach_penalty = float(breach_penalty)
        self._A: float = 0.0  # EMA of returns
        self._B: float = 0.0  # EMA of squared returns
        self._band_inside = _fresh_band_state()
        self.last_parts: dict[str, float] = empty_reward_parts()

    def reset(self) -> None:
        """Clear the DSR moving moments and once-per-band penalty state."""
        self._A = 0.0
        self._B = 0.0
        self._band_inside = _fresh_band_state()

    def __call__(
        self,
        step_pnl: float,
        *,
        daily_loss: float = 0.0,
        daily_loss_limit: float = 5_000.0,
        soft_daily_loss_limit: float | None = 5_000.0,
        loss_from_initial: float = 0.0,
        soft_max_loss_limit: float | None = 10_000.0,
        max_loss_limit: float = 10_000.0,
        trailing_dd: float = 0.0,
        soft_trailing_dd_limit: float | None = 0.0,
        trailing_dd_limit: float = 0.0,
        initial_balance: float = 100_000.0,
        breach: bool = False,
        realized_close_pnl: float | None = None,  # noqa: ARG002
        realized_r: float | None = None,  # noqa: ARG002
        equity: float | None = None,  # noqa: ARG002
    ) -> float:
        """Compute the DSR reward for one step.

        Args:
            step_pnl: Realised + unrealised P&L change for this bar.
            daily_loss: Current daily loss in account currency.
            daily_loss_limit: Hard daily-loss threshold.
            soft_daily_loss_limit: Optional start of the soft daily-loss penalty ramp.
            loss_from_initial: Loss measured from initial account balance.
            soft_max_loss_limit: Optional start of the total-loss penalty ramp.
            max_loss_limit: Hard total-loss threshold.
            trailing_dd: Current drawdown from the running equity peak.
            soft_trailing_dd_limit: Optional start of the trailing-drawdown penalty ramp.
            trailing_dd_limit: Hard trailing-drawdown threshold; zero disables the check.
            initial_balance: For normalisation.
            breach: Hard FTMO guardrail breached → large negative terminal reward.
            realized_close_pnl: Optional realized P&L metadata; not used by this reward.
            realized_r: Optional realized R-multiple metadata; not used by this reward.
            equity: Optional account-equity metadata; not used by this reward.

        Returns:
            Numeric result returned by ``__call__``.
        """
        if breach:
            penalty = self.breach_penalty
            self.last_parts = fit_reward_parts({"breach": penalty}, penalty, penalty)
            return penalty

            # Normalise P&L to relative return
        r = step_pnl / initial_balance

        # Update EMA estimates
        A_prev = self._A
        B_prev = self._B
        self._A = A_prev + self.eta * (r - A_prev)
        self._B = B_prev + self.eta * (r**2 - B_prev)

        denom = self._B - self._A**2
        if denom <= 1e-10:
            dsr = 0.0
        else:
            dsr = (self._B * (r - A_prev) - 0.5 * self._A * (r**2 - B_prev)) / (denom**1.5)

            # Soft brick → hard limit: linear penalty between soft and hard daily loss.
        soft = (
            float(soft_daily_loss_limit)
            if soft_daily_loss_limit is not None and soft_daily_loss_limit > 0.0
            else 0.8 * daily_loss_limit
        )
        soft_daily = _charge_band_once(
            self._band_inside, "soft_daily", daily_loss, soft, daily_loss_limit
        )
        soft_year = _charge_band_once(
            self._band_inside, "soft_year", loss_from_initial, soft_max_loss_limit, max_loss_limit
        )
        soft_trailing = _charge_band_once(
            self._band_inside,
            "soft_trailing",
            trailing_dd,
            soft_trailing_dd_limit,
            trailing_dd_limit,
        )
        raw = dsr + soft_daily + soft_year + soft_trailing
        clipped = float(np.clip(raw, -10.0, 10.0))
        self.last_parts = fit_reward_parts(
            {
                "dsr": dsr,
                "soft_daily": soft_daily,
                "soft_year": soft_year,
                "soft_trailing": soft_trailing,
            },
            raw,
            clipped,
        )
        return clipped


class PnLReward:
    """Realized-PnL reward with soft daily-loss penalty from 1% of equity.

    Used for Idea 1/2 trader-like training (``env.reward_mode: pnl``).
    Baseline Idea 3 keeps :class:`DSRReward`.
    """

    def __init__(
        self,
        *,
        soft_loss_frac: float = 0.01,
        dsr_weight: float = 0.0,
        breach_penalty: float = -1.0,
        soft_band_weight: float = 0.05,
    ) -> None:
        """Initialize PnLReward and its owned state.

        Args:
            soft_loss_frac: Numeric value used for the soft loss frac.
            dsr_weight: Numeric value used for the dsr weight.
            breach_penalty: Numeric value used for the breach penalty.
            soft_band_weight: Numeric value used for the soft band weight.
        """
        self.soft_loss_frac = soft_loss_frac
        self.dsr_weight = float(dsr_weight)
        self.breach_penalty = float(breach_penalty)
        self.soft_band_weight = float(soft_band_weight)
        self._dsr = DSRReward(breach_penalty=self.breach_penalty) if self.dsr_weight > 0 else None
        self._band_inside = _fresh_band_state()
        self.last_parts: dict[str, float] = empty_reward_parts()

    def reset(self) -> None:
        """Clear penalty-band state and reset the optional DSR component."""
        self._band_inside = _fresh_band_state()
        if self._dsr is not None:
            self._dsr.reset()

    def __call__(
        self,
        step_pnl: float,
        *,
        daily_loss: float = 0.0,
        daily_loss_limit: float = 5_000.0,
        soft_daily_loss_limit: float | None = 5_000.0,
        loss_from_initial: float = 0.0,
        soft_max_loss_limit: float | None = 10_000.0,
        max_loss_limit: float = 10_000.0,
        trailing_dd: float = 0.0,
        soft_trailing_dd_limit: float | None = 0.0,
        trailing_dd_limit: float = 0.0,
        initial_balance: float = 100_000.0,
        breach: bool = False,
        realized_close_pnl: float | None = None,
        realized_r: float | None = None,
        equity: float | None = None,
    ) -> float:
        """Process PnLReward.

        Args:
            step_pnl: Numeric value used for the step pnl.
            daily_loss: Numeric value used for the daily loss.
            daily_loss_limit: Numeric value used for the daily loss limit.
            soft_daily_loss_limit: Soft daily loss limit used by the operation described above.
            loss_from_initial: Numeric value used for the loss from initial.
            soft_max_loss_limit: Soft max loss limit used by the operation described above.
            max_loss_limit: Numeric value used for the max loss limit.
            trailing_dd: Numeric value used for the trailing dd.
            soft_trailing_dd_limit: Soft trailing dd limit used by the operation described above.
            trailing_dd_limit: Numeric value used for the trailing dd limit.
            initial_balance: Numeric value used for the initial balance.
            breach: Whether to enable or require the breach.
            realized_close_pnl: Realized close pnl used by the operation described above.
            realized_r: Realized r used by the operation described above.
            equity: Current account equity in account currency.

        Returns:
            Numeric result returned by ``__call__``.
        """
        if breach:
            penalty = self.breach_penalty
            self.last_parts = fit_reward_parts({"breach": penalty}, penalty, penalty)
            return penalty

        parts = empty_reward_parts()
        if realized_close_pnl is not None:
            parts["pnl"] = float(realized_close_pnl) / initial_balance

        eq = float(equity) if equity is not None else initial_balance
        soft_start = (
            float(soft_daily_loss_limit)
            if soft_daily_loss_limit is not None and soft_daily_loss_limit > 0.0
            else self.soft_loss_frac * max(eq, 1.0)
        )
        parts["soft_daily"] = _charge_band_once(
            self._band_inside,
            "soft_daily",
            daily_loss,
            soft_start,
            daily_loss_limit,
            weight=self.soft_band_weight,
        )
        parts["soft_year"] = _charge_band_once(
            self._band_inside,
            "soft_year",
            loss_from_initial,
            soft_max_loss_limit,
            max_loss_limit,
            weight=self.soft_band_weight,
        )
        parts["soft_trailing"] = _charge_band_once(
            self._band_inside,
            "soft_trailing",
            trailing_dd,
            soft_trailing_dd_limit,
            trailing_dd_limit,
            weight=self.soft_band_weight,
        )

        if self._dsr is not None:
            self._dsr(
                step_pnl,
                daily_loss=daily_loss,
                daily_loss_limit=daily_loss_limit,
                soft_daily_loss_limit=soft_daily_loss_limit,
                loss_from_initial=loss_from_initial,
                soft_max_loss_limit=soft_max_loss_limit,
                max_loss_limit=max_loss_limit,
                trailing_dd=trailing_dd,
                soft_trailing_dd_limit=soft_trailing_dd_limit,
                trailing_dd_limit=trailing_dd_limit,
                initial_balance=initial_balance,
                breach=False,
            )
            for key, value in self._dsr.last_parts.items():
                parts[key] = parts.get(key, 0.0) + self.dsr_weight * float(value)

        raw = float(sum(parts.values()))
        clipped = float(np.clip(raw, -10.0, 10.0))
        self.last_parts = fit_reward_parts(parts, raw, clipped)
        return clipped


class RMultipleReward:
    """Reward on realized R-multiples: maximise cumulative R, not Sharpe.

    ``reward_mode: rr``. Each closed trade contributes its realized R, so the
    agent is scored on the sum of R rather than on a risk-adjusted return or a
    dollar P&L that is silently tied to position size.

    This only means anything when sizing is fixed. Under fractional compounding
    the same edge produces different dollar P&L as equity drifts, and the reward
    would partly reward position size rather than decisions. With
    ``env.fixed_risk_usd`` set, 1R is a known dollar amount, so cumulative R is
    a clean, comparable objective.

    A losing trade costs -1R by construction, so the agent is pushed toward a
    positive hit rate rather than toward large positions.
    """

    def __init__(self, *, breach_penalty: float = -1.0, soft_band_weight: float = 0.05) -> None:
        """Initialize RMultipleReward and its owned state.

        Args:
            breach_penalty: Numeric value used for the breach penalty.
            soft_band_weight: Numeric value used for the soft band weight.
        """
        self.breach_penalty = float(breach_penalty)
        self.soft_band_weight = float(soft_band_weight)
        self._band_inside = _fresh_band_state()
        self.cumulative_r = 0.0
        self.last_parts: dict[str, float] = empty_reward_parts()

    def reset(self) -> None:
        """Clear penalty-band state and the accumulated realized R multiple."""
        self._band_inside = _fresh_band_state()
        self.cumulative_r = 0.0

    def __call__(
        self,
        step_pnl: float,
        *,
        daily_loss: float = 0.0,
        daily_loss_limit: float = 5_000.0,
        soft_daily_loss_limit: float | None = 5_000.0,
        loss_from_initial: float = 0.0,
        soft_max_loss_limit: float | None = 10_000.0,
        max_loss_limit: float = 10_000.0,
        trailing_dd: float = 0.0,
        soft_trailing_dd_limit: float | None = 0.0,
        trailing_dd_limit: float = 0.0,
        initial_balance: float = 100_000.0,
        breach: bool = False,
        realized_close_pnl: float | None = None,
        realized_r: float | None = None,
        equity: float | None = None,
    ) -> float:
        """Process RMultipleReward.

        Args:
            step_pnl: Numeric value used for the step pnl.
            daily_loss: Numeric value used for the daily loss.
            daily_loss_limit: Numeric value used for the daily loss limit.
            soft_daily_loss_limit: Soft daily loss limit used by the operation described above.
            loss_from_initial: Numeric value used for the loss from initial.
            soft_max_loss_limit: Soft max loss limit used by the operation described above.
            max_loss_limit: Numeric value used for the max loss limit.
            trailing_dd: Numeric value used for the trailing dd.
            soft_trailing_dd_limit: Soft trailing dd limit used by the operation described above.
            trailing_dd_limit: Numeric value used for the trailing dd limit.
            initial_balance: Numeric value used for the initial balance.
            breach: Whether to enable or require the breach.
            realized_close_pnl: Realized close pnl used by the operation described above.
            realized_r: Realized r used by the operation described above.
            equity: Current account equity in account currency.

        Returns:
            Numeric result returned by ``__call__``.
        """
        if breach:
            penalty = self.breach_penalty
            self.last_parts = fit_reward_parts({"breach": penalty}, penalty, penalty)
            return penalty

        parts = empty_reward_parts()
        # Only the close bar carries the trade's realized R; holding bars score 0,
        # so the agent is never paid for sitting still.
        if realized_r is not None and np.isfinite(realized_r):
            parts["pnl"] = float(realized_r)
            self.cumulative_r += float(realized_r)

        eq = float(equity) if equity is not None else initial_balance
        soft_start = (
            float(soft_daily_loss_limit)
            if soft_daily_loss_limit is not None and soft_daily_loss_limit > 0.0
            else 0.01 * max(eq, 1.0)
        )
        # Soft penalties stay in dollars and are rescaled to R units via the fixed
        # risk, so the trade term and the guardrail term share one scale.
        parts["soft_daily"] = _charge_band_once(
            self._band_inside,
            "soft_daily",
            daily_loss,
            soft_start,
            daily_loss_limit,
            weight=self.soft_band_weight,
        )
        parts["soft_year"] = _charge_band_once(
            self._band_inside,
            "soft_year",
            loss_from_initial,
            soft_max_loss_limit,
            max_loss_limit,
            weight=self.soft_band_weight,
        )
        parts["soft_trailing"] = _charge_band_once(
            self._band_inside,
            "soft_trailing",
            trailing_dd,
            soft_trailing_dd_limit,
            trailing_dd_limit,
            weight=self.soft_band_weight,
        )

        raw = float(sum(parts.values()))
        clipped = float(np.clip(raw, -10.0, 10.0))
        self.last_parts = fit_reward_parts(parts, raw, clipped)
        return clipped


class EquityDeltaReward:
    """Dense incremental R reward using mark-to-market equity changes."""

    def __init__(self, fixed_risk_usd: float, *, breach_penalty: float = -10.0) -> None:
        """Initialize EquityDeltaReward and its owned state.

        Args:
            fixed_risk_usd: Numeric value used for the fixed risk usd.
            breach_penalty: Numeric value used for the breach penalty.
        """
        if not np.isfinite(fixed_risk_usd) or fixed_risk_usd <= 0.0:
            raise ValueError("equity_delta_r requires fixed_risk_usd > 0")
        self.fixed_risk_usd = float(fixed_risk_usd)
        self.breach_penalty = float(breach_penalty)
        self.last_parts: dict[str, float] = empty_reward_parts()

    def reset(self) -> None:
        """Clear the component breakdown for the next episode."""
        self.last_parts = empty_reward_parts()

    def __call__(self, step_pnl: float, *, breach: bool = False, **_: object) -> float:
        """Process EquityDeltaReward.

        Args:
            step_pnl: Numeric value used for the step pnl.
            breach: Whether to enable or require the breach.
            **_: _ used by the operation described above.

        Returns:
            Numeric result returned by ``__call__``.
        """
        if breach:
            reward = self.breach_penalty
            self.last_parts = fit_reward_parts({"breach": reward}, reward, reward)
            return reward
        raw = float(step_pnl) / self.fixed_risk_usd
        if not np.isfinite(raw):
            raise ValueError("equity_delta_r received a non-finite equity change")
        reward = raw
        self.last_parts = fit_reward_parts({"pnl": raw}, raw, reward)
        return reward


class EquityLogGrowthReward:
    """Scaled log change in after-cost account equity for one transition.

    The transition endpoints are supplied by the environment's equity ledger,
    so realized and unrealized PnL use the same valuation as the account and
    already include modeled execution costs. No cost is subtracted again here.
    """

    def __init__(self, scale: float = 100.0, *, breach_penalty: float = -10.0) -> None:
        """Initialize EquityLogGrowthReward and its owned state.

        Args:
            scale: Numeric value used for the scale.
            breach_penalty: Numeric value used for the breach penalty.
        """
        if isinstance(scale, bool) or not np.isfinite(scale) or scale <= 0.0:
            raise ValueError("equity_log_growth scale must be finite and positive")
        if not np.isfinite(breach_penalty) or breach_penalty >= 0.0:
            raise ValueError("equity_log_growth breach_penalty must be finite and negative")
        self.scale = float(scale)
        self.breach_penalty = float(breach_penalty)
        self.last_parts: dict[str, float] = empty_reward_parts()

    def reset(self) -> None:
        """Clear the component breakdown for the next episode."""
        self.last_parts = empty_reward_parts()

    def __call__(
        self,
        step_pnl: float,  # noqa: ARG002
        *,
        previous_equity: float | None = None,
        equity: float | None = None,
        **_: object,
    ) -> float:
        """Process EquityLogGrowthReward.

        Args:
            step_pnl: Numeric value used for the step pnl.
            previous_equity: Previous equity used by the operation described above.
            equity: Current account equity in account currency.
            **_: _ used by the operation described above.

        Returns:
            Numeric result returned by ``__call__``.
        """
        if previous_equity is None or equity is None:
            raise ValueError("equity_log_growth requires previous_equity and equity")
        before = float(previous_equity)
        after = float(equity)
        if not np.isfinite(before) or not np.isfinite(after):
            raise ValueError("equity_log_growth requires finite equity endpoints")
        if before <= 0.0:
            raise ValueError("equity_log_growth requires positive previous_equity")
        if after <= 0.0:
            self.last_parts = fit_reward_parts(
                {"breach": self.breach_penalty}, self.breach_penalty, self.breach_penalty
            )
            return self.breach_penalty

        reward = self.scale * float(np.log(after) - np.log(before))
        if not np.isfinite(reward):
            raise ValueError("equity_log_growth produced a non-finite reward")
        self.last_parts = fit_reward_parts({"equity_growth": reward}, reward, reward)
        return reward
