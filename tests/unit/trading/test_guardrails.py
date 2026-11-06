"""Tests: FTMO guardrail breach detection."""

from __future__ import annotations

import pytest

from trading.account.account_state import AccountState
from trading.risk.guardrails import (
    FTMOGuardrails,
    adverse_position_loss_limit_usd,
    guardrail_breach_scope,
)


def _make(daily_loss: float = 0.0, max_dd: float = 0.0) -> AccountState:
    acc = AccountState(initial_balance=100_000.0)
    acc.daily_loss = daily_loss
    acc.max_drawdown = max_dd
    acc.equity = acc.session_start_equity - daily_loss
    acc.balance = acc.equity
    return acc


def test_no_breach():
    g = FTMOGuardrails()
    acc = _make(daily_loss=1000.0, max_dd=500.0)
    assert not g.any_breach(acc)
    assert g.breach_reason(acc) is None


@pytest.mark.parametrize(
    ("reason", "expected_scope"),
    [
        (None, None),
        ("daily_loss", "rollout"),
        ("max_drawdown", "rollout"),
        ("trailing_dd", "rollout"),
    ],
)
def test_guardrail_breach_scope_is_shared_and_explicit(
    reason: str | None,
    expected_scope: str | None,
) -> None:
    assert guardrail_breach_scope(reason) == expected_scope


def test_guardrail_breach_scope_rejects_unknown_reason() -> None:
    with pytest.raises(ValueError, match="unsupported hard guardrail"):
        guardrail_breach_scope("unknown")


@pytest.mark.parametrize(
    ("configured", "planned", "respect", "multiplier", "expected"),
    [
        (500.0, 1_000.0, True, 1.1, 1_100.0),
        (500.0, 1_000.0, False, 1.1, 500.0),
        (500.0, 0.0, True, 1.1, 500.0),
    ],
)
def test_shared_adverse_position_loss_limit(
    configured: float,
    planned: float,
    respect: bool,
    multiplier: float,
    expected: float,
) -> None:
    assert (
        adverse_position_loss_limit_usd(
            configured,
            planned,
            respect_planned_risk=respect,
            planned_risk_multiplier=multiplier,
        )
        == expected
    )


def test_adverse_position_loss_limit_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        adverse_position_loss_limit_usd(
            float("inf"),
            0.0,
            respect_planned_risk=True,
            planned_risk_multiplier=1.0,
        )


def test_daily_loss_equality_is_allowed_and_breach_occurs_below_floor():
    g = FTMOGuardrails()
    acc = _make(daily_loss=5000.0)
    assert not g.check_daily(acc)
    acc.daily_loss = 5_000.01
    acc.equity = acc.session_start_equity - 5_000.01
    acc.balance = acc.equity
    assert g.check_daily(acc)
    assert g.any_breach(acc)
    assert g.breach_reason(acc) == "daily_loss"


def test_max_drawdown_breach():
    g = FTMOGuardrails(max_loss_limit=10_000.0, trailing_dd_limit=0.0)
    acc = _make()
    acc.equity = 90_000.0  # Equality at the static floor remains allowed.
    assert not g.check_max_drawdown(acc)
    acc.equity = 89_999.99  # Static max loss fails only below its floor.
    assert g.check_max_drawdown(acc)
    assert g.breach_reason(acc) == "max_drawdown"


def test_max_loss_not_trailing_hwm():
    """Profits raise equity; max-loss still measured from initial, not peak."""
    g = FTMOGuardrails(max_loss_limit=10_000.0, trailing_dd_limit=0.0)
    acc = AccountState(initial_balance=100_000.0)
    acc.update_equity(8_000.0)  # peak 108k
    acc.balance = 100_000.0
    acc.update_equity(-5_000.0)  # equity 95k — only $5k from initial
    assert not g.check_max_drawdown(acc)
    acc.balance = 100_000.0
    acc.update_equity(-10_000.0)  # equity 90k
    assert not g.check_max_drawdown(acc)
    acc.balance = 100_000.0
    acc.update_equity(-10_000.01)
    assert g.check_max_drawdown(acc)


@pytest.mark.parametrize(
    ("mode", "peak", "equity", "expected_floor", "breached"),
    [
        ("static", 120_000.0, 95_000.0, 90_000.0, False),
        ("eod", 110_000.0, 100_000.0, 100_000.0, False),
        ("eod", 120_000.0, 101_000.0, 100_000.0, False),
        ("intraday_trailing", 110_000.0, 100_000.0, 100_000.0, False),
        ("intraday_trailing", 120_000.0, 101_000.0, 100_000.0, False),
        ("eod", 105_000.0, 95_000.0, 95_000.0, False),
        ("eod", 105_000.0, 94_999.99, 95_000.0, True),
        ("intraday_trailing", 105_000.0, 95_000.0, 95_000.0, False),
        ("intraday_trailing", 105_000.0, 94_999.99, 95_000.0, True),
    ],
)
def test_max_loss_floor_modes_share_initial_allowance_and_cap_at_initial(
    mode: str,
    peak: float,
    equity: float,
    expected_floor: float,
    breached: bool,
) -> None:
    guardrails = FTMOGuardrails(
        max_loss_limit=50_000.0,
        limit_value_mode="fixed_usd",
        max_loss_limit_initial_pct=0.10,
        max_drawdown_mode=mode,  # type: ignore[arg-type]
    )
    account = AccountState(initial_balance=100_000.0)
    account.peak_equity = peak
    account.peak_eod_equity = peak
    account.equity = equity

    assert guardrails.max_loss_floor_for(account) == expected_floor
    assert guardrails.check_max_drawdown(account) is breached


def test_trade_risk_check():
    g = FTMOGuardrails(risk_per_trade_limit=1000.0)
    assert g.check_trade_risk(999.0) is False
    assert g.check_trade_risk(1_000.0 + 5e-10) is False
    assert g.check_trade_risk(1001.0) is True


def test_percentage_limits_use_initial_equity_for_daily_and_max_loss() -> None:
    g = FTMOGuardrails(
        limit_value_mode="percent_equity",
        risk_per_trade_limit_pct=0.01,
        daily_loss_limit_pct=0.05,
        soft_daily_loss_limit_pct=0.05,
        max_loss_limit_initial_pct=0.10,
        soft_max_loss_limit_initial_pct=0.10,
    )
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.soft_daily_limit_for(acc) == 5_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

    acc.equity = 80_000.0
    assert g.risk_per_trade_limit_for(acc) == 800.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0


def test_daily_loss_threshold_uses_percentage_even_in_fixed_other_limits_mode() -> None:
    guardrails = FTMOGuardrails(
        limit_value_mode="fixed_usd",
        daily_loss_limit=1.0,
        soft_daily_loss_limit=2.0,
        daily_loss_limit_pct=0.05,
        soft_daily_loss_limit_pct=0.02,
    )
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = account.equity = 102_000.0
    account.session_start_balance = account.session_start_equity = 102_000.0

    assert guardrails.daily_limit_for(account) == pytest.approx(5_000.0)
    assert guardrails.soft_daily_limit_for(account) == pytest.approx(2_000.0)
    assert account.daily_floor(guardrails.daily_limit_for(account)) == pytest.approx(97_000.0)


@pytest.mark.parametrize("mode", ["static", "eod", "intraday_trailing"])
def test_daily_percentage_allowance_stays_fixed_for_all_max_drawdown_modes(
    mode: str,
) -> None:
    g = FTMOGuardrails(limit_value_mode="percent_equity", max_drawdown_mode=mode)  # type: ignore[arg-type]
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 95_000.0
    acc.balance = acc.equity
    acc.daily_loss = 5_000.0
    assert not g.check_daily(acc)
    acc.balance = acc.equity = 94_999.99
    acc.daily_loss = 5_000.01
    assert g.check_daily(acc)
    acc.balance = acc.equity = 95_001.0
    acc.daily_loss = 4_999.0
    assert not g.check_daily(acc)

    acc.equity = 91_000.0
    assert not g.check_max_drawdown(acc)
    acc.equity = 90_000.0
    assert not g.check_max_drawdown(acc)
    acc.equity = 89_999.99
    assert g.check_max_drawdown(acc)


def test_daily_percentage_floor_reanchors_to_each_session_opening_equity() -> None:
    guardrails = FTMOGuardrails(
        limit_value_mode="percent_equity",
        daily_loss_limit_pct=0.05,
    )
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")

    assert account.daily_floor(guardrails.daily_limit_for(account)) == 95_000.0
    account.equity = 95_000.0
    assert not guardrails.check_daily(account)
    account.equity = 94_999.99
    assert guardrails.check_daily(account)

    account.equity = 102_000.0
    account.reset_daily()
    assert account.daily_floor(guardrails.daily_limit_for(account)) == 97_000.0
    assert guardrails.daily_limit_for(account) == 5_000.0
    account.equity = 97_000.0
    assert not guardrails.check_daily(account)
    account.equity = 96_999.99
    assert guardrails.check_daily(account)

    account.equity = 101_000.0
    account.reset_daily()
    assert account.daily_floor(guardrails.daily_limit_for(account)) == 96_000.0
    assert guardrails.daily_limit_for(account) == 5_000.0
    account.equity = 96_000.0
    assert not guardrails.check_daily(account)
    account.equity = 95_999.99
    assert guardrails.check_daily(account)


@pytest.mark.parametrize(
    ("mode", "expected_max_floor"),
    [("static", 90_000.0), ("eod", 100_000.0), ("intraday_trailing", 100_000.0)],
)
def test_payout_reanchors_daily_loss_and_locks_trailing_floor_at_initial(
    mode: str,
    expected_max_floor: float,
) -> None:
    guardrails = FTMOGuardrails(
        limit_value_mode="percent_equity",
        daily_loss_limit_pct=0.05,
        max_loss_limit_initial_pct=0.10,
        max_drawdown_mode=mode,  # type: ignore[arg-type]
    )
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = 108_000.0
    account.update_equity(0.0)
    account.peak_eod_equity = 108_000.0

    account.reset_operating_balance(100_000.0, max_drawdown_mode=mode)

    assert account.session_start_equity == 100_000.0
    assert guardrails.daily_limit_for(account) == 5_000.0
    assert account.daily_floor(guardrails.daily_limit_for(account)) == 95_000.0
    assert not guardrails.check_max_drawdown(account)
    account.update_equity(-4_999.0)
    assert not guardrails.check_daily(account)
    if mode == "static":
        assert not guardrails.check_max_drawdown(account)
    else:
        assert guardrails.check_max_drawdown(account)
    account.update_equity(-5_000.0)
    assert not guardrails.check_daily(account)
    account.update_equity(-5_000.01)
    assert guardrails.check_daily(account)
    assert guardrails.max_loss_floor_for(account) == expected_max_floor
    account.equity = expected_max_floor
    assert not guardrails.check_max_drawdown(account)
    account.equity = expected_max_floor - 0.01
    assert guardrails.check_max_drawdown(account)


@pytest.mark.parametrize("mode", ["eod", "intraday_trailing"])
def test_partial_payout_preserves_trade_buffer_above_locked_floor(mode: str) -> None:
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = 105_000.0
    account.equity = 105_000.0
    account.reset_operating_balance(102_500.0, max_drawdown_mode=mode)
    guardrails = FTMOGuardrails(max_drawdown_mode=mode)  # type: ignore[arg-type]

    assert account.balance == 102_500.0
    assert account.payout_drawdown_floor == 100_000.0
    assert guardrails.max_loss_floor_for(account) == 100_000.0
    assert not guardrails.check_max_drawdown(account)
    account.equity = 100_000.0
    assert not guardrails.check_max_drawdown(account)
    account.equity = 99_999.99
    assert guardrails.check_max_drawdown(account)


def test_account_state_records_drawdown_from_prior_eod_peak_once() -> None:
    acc = AccountState(initial_balance=100_000.0)
    acc.peak_eod_equity = 110_000.0
    acc.equity = 95_000.0

    assert acc.peak_eod_drawdown_usd == 15_000.0
    assert acc.record_eod_equity() == 15_000.0
    assert acc.max_peak_eod_drawdown_usd == 15_000.0
    assert acc.peak_eod_equity == 110_000.0

    acc.equity = 111_000.0
    assert acc.peak_eod_drawdown_usd == 0.0
    assert acc.record_eod_equity() == 0.0
    assert acc.peak_eod_equity == 111_000.0


def test_soft_daily_does_not_hard_breach():
    g = FTMOGuardrails(
        limit_value_mode="fixed_usd",
        daily_loss_limit_pct=0.05,
        soft_daily_loss_limit_pct=0.02,
    )
    acc = _make(daily_loss=2500.0)
    assert g.check_soft_daily(acc)
    assert not g.check_daily(acc)
    assert not g.any_breach(acc)
    assert g.breach_reason(acc) is None


def test_trailing_dd_is_dollar_from_peak_not_pct_of_peak():
    """PPO cap is 7% of *initial* ($7k) from peak, not 7% of current peak."""
    g = FTMOGuardrails(trailing_dd_limit=0.07, max_loss_limit=10_000.0)
    acc = AccountState(initial_balance=100_000.0)
    acc.update_equity(30_000.0)  # peak 130k
    acc.balance = 123_500.0
    acc.update_equity(0.0)  # $6.5k off peak — under $7k train cap
    assert not g.check_trailing_dd(acc)
    acc.balance = 122_000.0
    acc.update_equity(0.0)  # $8k off peak — over $7k train cap
    assert g.check_trailing_dd(acc)
    assert g.breach_reason(acc) == "trailing_dd"
    # 7% of $130k peak would wait until ~$120.9k; still above that here.
    assert acc.equity > 0.93 * acc.peak_equity
    assert not g.check_max_drawdown(acc)


def test_soft_trailing_dd_does_not_hard_breach():
    g = FTMOGuardrails(trailing_dd_limit=0.07, soft_trailing_dd_limit=0.04)
    acc = AccountState(initial_balance=100_000.0)
    acc.update_equity(10_000.0)
    acc.balance = 105_500.0  # $4.5k off 110k peak: above $4k soft, under $7k hard
    acc.update_equity(0.0)
    assert g.check_soft_trailing_dd(acc)
    assert not g.check_trailing_dd(acc)
    assert not g.any_breach(acc)
