"""FTMO-style account state tracker.

Tracks equity, balance, daily P&L, and absolute loss from initial balance.
``max_drawdown`` here means peak loss from *initial* balance (not trailing HWM).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from trading.account.limits import (
    daily_floor as compute_daily_floor,
)
from trading.account.limits import (
    remaining_account_capacity as compute_remaining_account_capacity,
)
from trading.account.limits import (
    remaining_daily_capacity as compute_remaining_daily_capacity,
)

if TYPE_CHECKING:
    from trading.risk.contracts import RiskDailyPnlBasis, RiskState


@dataclass
class AccountState:
    """Mutable account state for the backtester / environment."""

    initial_balance: float = 100_000.0
    policy_mode: str = "legacy"
    daily_pnl_basis_override: RiskDailyPnlBasis | None = None
    balance: float = field(init=False)
    equity: float = field(init=False)
    peak_equity: float = field(init=False)  # informational HWM only
    peak_eod_equity: float = field(init=False)  # high-water mark at completed NY sessions
    max_peak_eod_drawdown_usd: float = field(init=False)
    session_start_balance: float = field(init=False)
    session_start_equity: float = field(init=False)
    daily_loss: float = field(init=False)  # positive = loss so far today
    max_drawdown: float = field(init=False)  # peak loss from initial (positive $)
    open_pnl: float = field(init=False)

    def __post_init__(self) -> None:
        """Validate and initialize AccountState after construction."""
        initial_balance = self._validated_amount(self.initial_balance, "initial_balance")
        if initial_balance <= 0.0:
            raise ValueError("initial_balance must be finite and positive")
        self.initial_balance = initial_balance
        if self.daily_pnl_basis_override not in {
            None,
            "session_net_equity",
            "legacy_gross_closed_losses",
        }:
            raise ValueError(
                f"unsupported daily PnL basis override: {self.daily_pnl_basis_override!r}"
            )
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.peak_equity = self.initial_balance
        self.peak_eod_equity = self.initial_balance
        self.max_peak_eod_drawdown_usd = 0.0
        self.session_start_balance = self.initial_balance
        self.session_start_equity = self.initial_balance
        self.daily_loss = 0.0
        self.max_drawdown = 0.0
        self.open_pnl = 0.0

    def _update_loss_from_initial(self) -> None:
        """Track peak absolute loss vs initial balance (FTMO max-loss, not trailing)."""
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        loss = self.loss_from_initial()
        if loss > self.max_drawdown:
            self.max_drawdown = loss

    def update_equity(self, open_pnl: float) -> None:
        """Recompute equity from balance + unrealised P&L.

        Args:
            open_pnl: Numeric value used for the open pnl.
        """
        pnl = self._validated_amount(open_pnl, "open_pnl")
        equity = self.balance + pnl
        if not math.isfinite(equity):
            raise ValueError("equity must remain finite")
        self.open_pnl = pnl
        self.equity = equity
        self._update_loss_from_initial()

    def close_trade(self, pnl: float) -> None:
        """Realise P&L from a closed trade.

        Args:
            pnl: Numeric value used for the pnl.
        """
        realized_pnl = self._validated_amount(pnl, "pnl")
        balance = self.balance + realized_pnl
        if not math.isfinite(balance):
            raise ValueError("balance must remain finite")
        daily_loss = self.daily_loss
        if realized_pnl < 0:
            daily_loss += abs(realized_pnl)
            if not math.isfinite(daily_loss):
                raise ValueError("daily_loss must remain finite")
        self.balance = balance
        self.open_pnl = 0.0
        self.equity = self.balance
        self._update_loss_from_initial()
        # Daily loss: only accumulates when it is a loss
        self.daily_loss = daily_loss

    def reset_daily(self) -> None:
        """Anchor a new session without changing legacy accounting semantics."""
        self.session_start_balance = self.balance
        self.session_start_equity = self.equity
        self.daily_loss = 0.0

    def canonical_daily_loss(self) -> float:
        """Daily loss used by the selected policy.

        Returns:
            Numeric result returned by ``canonical_daily_loss``.
        """
        state = self.to_risk_state(daily_loss_limit=0.0)
        return max(0.0, -state.daily_pnl)

    @property
    def daily_pnl_basis(self) -> RiskDailyPnlBasis:
        """Return the versioned daily-PnL basis selected by ``policy_mode``.

        Returns:
            The session-equity or legacy gross-closed-loss basis.
        """
        from trading.risk.contracts import (
            RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES,
            RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
        )

        if self.daily_pnl_basis_override is not None:
            return self.daily_pnl_basis_override
        if self.policy_mode == "repeated_payout":
            return RISK_DAILY_PNL_BASIS_SESSION_EQUITY
        if self.policy_mode == "legacy":
            return RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES
        raise ValueError(f"unknown account policy mode: {self.policy_mode!r}")

    def to_risk_state(self, *, daily_loss_limit: float, open_risk: float = 0.0) -> RiskState:
        """Build the versioned risk-policy view of the current account.

        ``RiskState.daily_pnl`` is signed: positive for session gains and
        negative for session losses. Legacy mode retains its historical
        gross-negative-close counter and does not offset winning closes.

        Args:
            daily_loss_limit: Current hard or soft daily-loss threshold.
            open_risk: Risk already committed to open positions.

        Returns:
            A validated ``risk-state-v1`` account snapshot.
        """
        from trading.risk.contracts import (
            RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
            RiskState,
        )

        basis = self.daily_pnl_basis
        daily_pnl = (
            float(self.equity) - float(self.session_start_equity)
            if basis == RISK_DAILY_PNL_BASIS_SESSION_EQUITY
            else -float(self.daily_loss)
        )
        return RiskState(
            equity=float(self.equity),
            daily_pnl=daily_pnl,
            open_risk=float(open_risk),
            daily_loss_limit=float(daily_loss_limit),
            daily_pnl_basis=basis,
        )

    def daily_floor(self, daily_loss_limit: float) -> float:
        """Fixed session floor for repeated-payout mode.

        Args:
            daily_loss_limit: Numeric value used for the daily loss limit.

        Returns:
            Numeric result returned by ``daily_floor``.
        """
        return compute_daily_floor(self.session_start_equity, daily_loss_limit)

    def remaining_daily_capacity(self, daily_loss_limit: float) -> float:
        """Return the remaining capacity before the daily loss limit is breached.

        Args:
            daily_loss_limit: Maximum daily loss in account currency.

        Returns:
            Nonnegative remaining daily capacity.
        """
        return compute_remaining_daily_capacity(
            self.session_start_equity, self.equity, daily_loss_limit
        )

    def remaining_account_capacity(self, account_floor: float) -> float:
        """Return equity capacity above the account floor.

        Args:
            account_floor: Minimum permitted account equity.

        Returns:
            Nonnegative remaining account capacity.
        """
        return compute_remaining_account_capacity(self.equity, account_floor)

    def reset_operating_balance(self, operating_balance: float) -> None:
        """Reset deployable capital after a payout while preserving global counters elsewhere.

        Args:
            operating_balance: Numeric value used for the operating balance.
        """
        balance = self._validated_amount(operating_balance, "operating_balance")
        if balance < 0.0:
            raise ValueError("operating_balance must be non-negative")
        self.balance = balance
        self.equity = balance
        self.open_pnl = 0.0
        self.peak_equity = max(self.peak_equity, self.equity)
        self.session_start_balance = self.balance
        self.session_start_equity = self.equity
        self.daily_loss = 0.0

    @staticmethod
    def _validated_amount(value: float, name: str) -> float:
        """Return a finite monetary input or fail before mutating account state."""
        if isinstance(value, bool):
            raise ValueError(f"{name} must be finite")
        try:
            amount = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(amount):
            raise ValueError(f"{name} must be finite")
        return amount

    def loss_from_initial(self) -> float:
        """Current absolute loss vs initial balance (0 if equity ≥ initial).

        Returns:
            Numeric result returned by ``loss_from_initial``.
        """
        return max(0.0, self.initial_balance - self.equity)

    def drawdown_pct(self) -> float:
        """Peak loss from initial as a fraction of initial balance.

        Returns:
            Numeric result returned by ``drawdown_pct``.
        """
        return self.max_drawdown / self.initial_balance if self.initial_balance else 0.0

    def trailing_drawdown_pct(self) -> float:
        """Current drawdown from peak equity (HWM) as a fraction of peak.

        Returns:
            Numeric result returned by ``trailing_drawdown_pct``.
        """
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.equity) / self.peak_equity)

    def record_eod_equity(self) -> float:
        """Record end-of-session equity and return drawdown from the prior EOD peak.

        Returns:
            Numeric result returned by ``record_eod_equity``.
        """
        drawdown_usd = self.peak_eod_drawdown_usd
        self.max_peak_eod_drawdown_usd = max(self.max_peak_eod_drawdown_usd, drawdown_usd)
        self.peak_eod_equity = max(self.peak_eod_equity, self.equity)
        return drawdown_usd

    @property
    def peak_eod_drawdown_usd(self) -> float:
        """Current dollar drawdown from the last completed-session equity peak.

        Returns:
            Numeric result returned by ``peak_eod_drawdown_usd``.
        """
        return max(0.0, self.peak_eod_equity - self.equity)

    def to_array(self) -> list[float]:
        """Return a fixed-length array for the env observation.

        Returns:
            Values returned by ``to_array``, in the declared order.
        """
        return [
            self.balance / self.initial_balance - 1.0,
            self.equity / self.initial_balance - 1.0,
            self.open_pnl / self.initial_balance,
            self.daily_loss / self.initial_balance,
            self.max_drawdown / self.initial_balance,
        ]
