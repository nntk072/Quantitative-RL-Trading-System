from __future__ import annotations

from dataclasses import dataclass

import pytest

from trading.account.account_state import AccountState
from trading.risk.contracts import (
    RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES,
    RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
    RISK_DECISION_SCHEMA_V1,
    RISK_STATE_SCHEMA_V1,
    RiskDecision,
    RiskPolicy,
    RiskState,
)


def test_account_state_exports_selected_daily_loss_basis_through_risk_state() -> None:
    legacy_mode = AccountState(policy_mode="legacy")
    legacy_mode.close_trade(-4_000.0)
    legacy_mode.close_trade(2_500.0)
    legacy_mode.close_trade(-1_000.0)
    session_state = legacy_mode.to_risk_state(daily_loss_limit=5_000.0, open_risk=125.0)

    assert session_state.daily_pnl_basis == RISK_DAILY_PNL_BASIS_SESSION_EQUITY
    assert session_state.daily_pnl == -2_500.0
    assert session_state.open_risk == 125.0
    assert legacy_mode.canonical_daily_loss() == 2_500.0

    historical = AccountState(
        policy_mode="legacy",
        daily_pnl_basis_override=RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES,
    )
    historical.close_trade(-4_000.0)
    historical.close_trade(2_500.0)
    historical.close_trade(-1_000.0)
    historical_state = historical.to_risk_state(daily_loss_limit=5_000.0)
    assert historical_state.daily_pnl_basis == RISK_DAILY_PNL_BASIS_LEGACY_GROSS_LOSSES
    assert historical_state.daily_pnl == -5_000.0

    repeated = AccountState(policy_mode="repeated_payout")
    repeated.update_equity(-2_000.0)
    repeated_state = repeated.to_risk_state(daily_loss_limit=5_000.0)

    assert repeated_state.daily_pnl_basis == RISK_DAILY_PNL_BASIS_SESSION_EQUITY
    assert repeated_state.daily_pnl == -2_000.0
    assert repeated.canonical_daily_loss() == 2_000.0


def test_account_state_rejects_unknown_policy_mode() -> None:
    import pytest

    account = AccountState(policy_mode="unsupported")

    with pytest.raises(ValueError, match="unknown account policy mode"):
        account.to_risk_state(daily_loss_limit=5_000.0)


def test_account_state_daily_pnl_basis_override_tracks_open_pnl_and_session_reset() -> None:
    account = AccountState(daily_pnl_basis_override=RISK_DAILY_PNL_BASIS_SESSION_EQUITY)
    account.close_trade(-100.0)
    account.close_trade(150.0)
    account.update_equity(-100.0)

    assert account.daily_loss == 100.0
    assert account.canonical_daily_loss() == 50.0

    account.reset_daily()
    account.update_equity(25.0)

    assert account.canonical_daily_loss() == 0.0
    assert account.to_risk_state(daily_loss_limit=500.0).daily_pnl == 125.0


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf"), True])
def test_account_state_rejects_invalid_initial_balance(value: float) -> None:
    with pytest.raises(ValueError, match="initial_balance"):
        AccountState(initial_balance=value)


def test_account_state_rejects_nonfinite_updates_without_mutating_state() -> None:
    account = AccountState()
    original = (account.balance, account.equity, account.open_pnl, account.daily_loss)

    for value in (float("nan"), float("inf"), float("-inf"), True):
        with pytest.raises(ValueError, match="finite"):
            account.update_equity(value)
        with pytest.raises(ValueError, match="finite"):
            account.close_trade(value)
        with pytest.raises(ValueError, match="finite"):
            account.reset_operating_balance(value)
        assert (account.balance, account.equity, account.open_pnl, account.daily_loss) == original

    with pytest.raises(ValueError, match="non-negative"):
        account.reset_operating_balance(-1.0)
    assert (account.balance, account.equity, account.open_pnl, account.daily_loss) == original


def test_account_state_rejects_finite_input_overflow_without_mutating_state() -> None:
    account = AccountState(initial_balance=1e308)
    equity_state = (account.balance, account.equity, account.open_pnl, account.daily_loss)
    with pytest.raises(ValueError, match="equity must remain finite"):
        account.update_equity(1e308)
    assert (account.balance, account.equity, account.open_pnl, account.daily_loss) == equity_state

    with pytest.raises(ValueError, match="balance must remain finite"):
        account.close_trade(1e308)
    assert (account.balance, account.equity, account.open_pnl, account.daily_loss) == equity_state

    account.close_trade(-1e308)
    account.close_trade(1e308)
    daily_state = (account.balance, account.equity, account.open_pnl, account.daily_loss)
    with pytest.raises(ValueError, match="daily_loss must remain finite"):
        account.close_trade(-1e308)
    assert (account.balance, account.equity, account.open_pnl, account.daily_loss) == daily_state


@dataclass(frozen=True)
class _FixedCapPolicy:
    cap: float

    def decide(self, state: RiskState, requested_risk: float) -> RiskDecision:
        del state
        amount = min(requested_risk, self.cap)
        return RiskDecision(allowed=amount > 0.0, risk_amount=amount)


class _DailyLossPolicy:
    def decide(self, state: RiskState, requested_risk: float) -> RiskDecision:
        remaining = state.daily_loss_limit + state.daily_pnl - state.open_risk
        if remaining <= 0.0:
            return RiskDecision(False, 0.0, "daily_loss_limit")
        amount = min(requested_risk, remaining)
        return RiskDecision(allowed=amount > 0.0, risk_amount=amount)


def test_two_risk_policies_consume_the_same_semantic_state() -> None:
    state = RiskState(
        equity=100_000.0,
        daily_pnl=-400.0,
        open_risk=100.0,
        daily_loss_limit=500.0,
        daily_pnl_basis=RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
    )
    policies: tuple[RiskPolicy, ...] = (_FixedCapPolicy(50.0), _DailyLossPolicy())

    decisions = tuple(policy.decide(state, requested_risk=200.0) for policy in policies)

    assert decisions == (
        RiskDecision(True, 50.0),
        RiskDecision(False, 0.0, "daily_loss_limit"),
    )


def test_risk_state_and_decision_declare_supported_schema_versions() -> None:
    state = RiskState(
        100_000.0,
        -400.0,
        100.0,
        500.0,
        RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
    )
    decision = RiskDecision(True, 50.0)

    assert state.schema_version == RISK_STATE_SCHEMA_V1
    assert decision.schema_version == RISK_DECISION_SCHEMA_V1


def test_risk_contract_rejects_unsupported_versions_and_invalid_amounts() -> None:
    import pytest

    with pytest.raises(ValueError, match="unsupported risk state schema"):
        RiskState(
            100_000.0,
            0.0,
            0.0,
            500.0,
            RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
            schema_version="risk-state-v2",
        )
    with pytest.raises(ValueError, match="open_risk"):
        RiskState(100_000.0, 0.0, -1.0, 500.0, RISK_DAILY_PNL_BASIS_SESSION_EQUITY)
    with pytest.raises(ValueError, match="daily PnL basis"):
        RiskState(100_000.0, 0.0, 0.0, 500.0, "implicit")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="denied risk decision"):
        RiskDecision(False, 1.0)
    with pytest.raises(ValueError, match="unsupported risk decision schema"):
        RiskDecision(True, 1.0, schema_version="risk-decision-v2")
