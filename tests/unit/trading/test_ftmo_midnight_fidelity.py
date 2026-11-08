"""FTMO 2-Step balance-at-midnight daily-loss reference checks."""

from __future__ import annotations

import pytest

from trading.account import AccountState
from trading.policy import TradingPolicyConfig
from trading.risk.ftmo_clock import ftmo_trading_day


def test_prague_midnight_uses_winter_and_summer_offsets() -> None:
    assert str(ftmo_trading_day("2026-01-08T22:59:59Z")) == "2026-01-08"
    assert str(ftmo_trading_day("2026-01-08T23:00:00Z")) == "2026-01-09"
    assert str(ftmo_trading_day("2026-07-08T21:59:59Z")) == "2026-07-08"
    assert str(ftmo_trading_day("2026-07-08T22:00:00Z")) == "2026-07-09"


def test_prague_midnight_tracks_dst_transition_boundaries() -> None:
    assert str(ftmo_trading_day("2026-03-28T22:59:59Z")) == "2026-03-28"
    assert str(ftmo_trading_day("2026-03-28T23:00:00Z")) == "2026-03-29"
    assert str(ftmo_trading_day("2026-03-29T21:59:59Z")) == "2026-03-29"
    assert str(ftmo_trading_day("2026-03-29T22:00:00Z")) == "2026-03-30"
    assert str(ftmo_trading_day("2026-10-24T21:59:59Z")) == "2026-10-24"
    assert str(ftmo_trading_day("2026-10-24T22:00:00Z")) == "2026-10-25"
    assert str(ftmo_trading_day("2026-10-25T22:59:59Z")) == "2026-10-25"
    assert str(ftmo_trading_day("2026-10-25T23:00:00Z")) == "2026-10-26"


def test_naive_broker_timestamp_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ftmo_trading_day("2026-01-08T23:00:00")


def test_open_loss_at_midnight_does_not_lower_balance_based_daily_floor() -> None:
    account = AccountState(daily_pnl_basis_override="ftmo_midnight_balance")
    account.update_equity(-3_000.0)
    account.reset_daily()
    assert account.session_start_balance == 100_000.0
    assert account.session_start_equity == 97_000.0
    assert account.daily_floor(5_000.0) == 95_000.0
    assert account.remaining_daily_capacity(5_000.0) == 2_000.0
    assert account.to_risk_state(daily_loss_limit=5_000.0).daily_pnl == -3_000.0


def test_account_policy_requires_matched_reset_and_risk_basis() -> None:
    TradingPolicyConfig(
        daily_pnl_basis="ftmo_midnight_balance",
        daily_loss_reset_source="prague_midnight",
        daily_loss_includes_open_pnl=True,
    ).validate()
    with pytest.raises(ValueError, match="Prague-midnight"):
        TradingPolicyConfig(daily_loss_reset_source="prague_midnight").validate()
