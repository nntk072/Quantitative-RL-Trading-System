"""Selectable trading-policy configuration shared by train, workers, and evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


def _float_or_default(value: Any, default: float) -> float:
    """Process or default.

    Args:
        value: Value to process.
        default: Numeric value used for the default.

    Returns:
        Numeric result returned by ``_float_or_default``.
    """
    return default if value is None else float(value)


@dataclass(frozen=True)
class TradingPolicyConfig:
    """Resolved account and payout policy settings used by simulation and live strategies.

    Attributes:
        operating_balance: Account balance retained after a payout.
        profit_target_balance: Balance required to trigger payout eligibility.
        account_floor: Minimum permitted account equity.
        payout_amount: Optional configured payout amount.
        risk_state_schema_version: Version of the account risk-state contract.
        daily_pnl_basis: Signed daily-PnL basis consumed by risk checks.
        daily_loss_includes_open_pnl: Whether current unrealized PnL is included.
        daily_loss_reset_source: Dataset key that determines a daily reset.
    """

    mode: str = "legacy"
    operating_balance: float = 100_000.0
    profit_target_balance: float = 110_000.0
    account_floor: float = 90_000.0
    daily_loss_limit: float = 5_000.0
    min_agent_risk_frac: float = 0.0
    max_agent_risk_frac: float = 0.009
    execution_reserve_usd: float = 0.0
    payout_trigger: str = "realized_balance_flat"
    continue_after_payout: bool = True
    trailing_dd_limit: float = 0.0
    enforce_remaining_daily_capacity: bool = True
    enforce_remaining_account_capacity: bool = True
    repeated_eval: bool = True
    risk_state_schema_version: str = "risk-state-v1"
    daily_pnl_basis: str | None = None
    daily_loss_includes_open_pnl: bool | None = None
    daily_loss_reset_source: str = "supplied_session_id_transition"

    def __post_init__(self) -> None:
        """Resolve the explicit risk-state semantics from the selected policy."""
        if self.mode == "legacy":
            basis, includes_open_pnl = "legacy_gross_closed_losses", False
        elif self.mode == "repeated_payout":
            basis, includes_open_pnl = "session_net_equity", True
        else:
            return
        if self.daily_pnl_basis is None:
            object.__setattr__(self, "daily_pnl_basis", basis)
        if self.daily_loss_includes_open_pnl is None:
            object.__setattr__(self, "daily_loss_includes_open_pnl", includes_open_pnl)

    @property
    def repeated_payout(self) -> bool:
        """Return whether the account policy enables repeated payouts.

        Returns:
            Whether repeated payout meets the requested condition.
        """
        return self.mode == "repeated_payout"

    def validate(self) -> TradingPolicyConfig:
        """Validate payout thresholds and account-floor relationships.

        Returns:
            Result of validate payout thresholds and account-floor relationships.
        """
        if self.mode not in {"legacy", "repeated_payout"}:
            raise ValueError(f"unknown trading_policy.mode: {self.mode!r}")
        expected_basis, expected_open_pnl = (
            ("legacy_gross_closed_losses", False)
            if self.mode == "legacy"
            else ("session_net_equity", True)
        )
        if self.risk_state_schema_version != "risk-state-v1":
            raise ValueError("unsupported trading policy risk-state schema")
        if self.daily_pnl_basis != expected_basis:
            raise ValueError("daily PnL basis does not match trading_policy.mode")
        if self.daily_loss_includes_open_pnl is not expected_open_pnl:
            raise ValueError("open-PnL inclusion does not match the daily PnL basis")
        if self.daily_loss_reset_source != "supplied_session_id_transition":
            raise ValueError("daily-loss reset source must use supplied session_id transitions")
        if self.repeated_payout:
            if self.profit_target_balance <= self.operating_balance:
                raise ValueError("repeated payout target must exceed operating balance")
            if self.account_floor >= self.operating_balance:
                raise ValueError("repeated payout account floor must be below operating balance")
            if self.daily_loss_limit < 0.0:
                raise ValueError("repeated payout daily loss limit cannot be negative")
            if self.min_agent_risk_frac != 0.0:
                raise ValueError("repeated payout minimum agent risk must be zero")
            if not 0.0 <= self.max_agent_risk_frac < 0.01:
                raise ValueError("repeated payout max agent risk must be in [0, 0.01)")
            if self.execution_reserve_usd < 0.0:
                raise ValueError("execution reserve cannot be negative")
            if self.payout_trigger != "realized_balance_flat":
                raise ValueError("repeated payout trigger must be realized_balance_flat")
            if not self.continue_after_payout:
                raise ValueError("repeated payout evaluation must continue after payout")
            if self.trailing_dd_limit != 0.0:
                raise ValueError("repeated payout account trailing drawdown must be disabled")
            if not self.enforce_remaining_daily_capacity:
                raise ValueError("repeated payout must enforce remaining daily capacity")
            if not self.enforce_remaining_account_capacity:
                raise ValueError("repeated payout must enforce remaining account capacity")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return the policy settings as a JSON-compatible mapping.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        return asdict(self)


def resolve_trading_policy(cfg: Any) -> TradingPolicyConfig:
    """Resolve trading policy settings from an attribute-based configuration.

    Args:
        cfg: Configuration object containing the optional trading policy block.

    Returns:
        Validated policy settings with defaults applied.
    """
    block = cfg.get("trading_policy", {}) if hasattr(cfg, "get") else {}
    if block is None:
        block = {}
    mode = str(block.get("mode", "legacy")).strip().lower()
    repeated = block.get("repeated_payout", {}) or {}
    account = cfg.get("account", {}) if hasattr(cfg, "get") else {}
    initial = float(account.get("initial_balance", 100_000.0))
    result = TradingPolicyConfig(
        mode=mode,
        operating_balance=float(repeated.get("operating_balance", initial)),
        profit_target_balance=float(
            repeated.get("payout_target_balance", repeated.get("profit_target_balance", 110_000.0))
        ),
        account_floor=float(
            repeated.get("account_floor_equity", repeated.get("account_floor", 90_000.0))
        ),
        daily_loss_limit=float(repeated.get("daily_loss_limit", 5_000.0)),
        min_agent_risk_frac=_float_or_default(
            repeated.get("min_agent_risk_frac")
            if repeated.get("min_agent_risk_frac") is not None
            else repeated.get("agent_risk_min_frac"),
            0.0,
        ),
        max_agent_risk_frac=_float_or_default(
            repeated.get("max_agent_risk_frac")
            if repeated.get("max_agent_risk_frac") is not None
            else repeated.get("agent_risk_max_frac"),
            0.009,
        ),
        execution_reserve_usd=_float_or_default(
            repeated.get("execution_reserve_usd")
            if repeated.get("execution_reserve_usd") is not None
            else repeated.get("reserve_cost_buffer_usd"),
            0.0,
        ),
        payout_trigger=str(repeated.get("payout_trigger", "realized_balance_flat")),
        continue_after_payout=bool(repeated.get("continue_after_payout", True)),
        trailing_dd_limit=float(repeated.get("trailing_dd_limit", 0.0)),
        enforce_remaining_daily_capacity=bool(
            repeated.get("enforce_remaining_daily_capacity", True)
        ),
        enforce_remaining_account_capacity=bool(
            repeated.get("enforce_remaining_account_capacity", True)
        ),
        repeated_eval=bool(repeated.get("repeated_eval", True)),
    )
    return result.validate()


def resolve_trading_policy_mapping(cfg: Mapping[str, Any]) -> TradingPolicyConfig:
    """Resolve trading policy settings from a mapping configuration.

    Args:
        cfg: Configuration mapping containing the optional trading policy block.

    Returns:
        Validated policy settings with defaults applied.
    """
    return resolve_trading_policy(dict(cfg))
