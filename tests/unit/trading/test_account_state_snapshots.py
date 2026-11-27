"""Stable account trace fields for evaluations and research evidence."""

import pytest

from trading.account import AccountState
from trading.account.snapshots import account_state_snapshot
from trading.execution.broker import Position


def test_account_state_rejects_invalid_policy_and_payout_modes() -> None:
    with pytest.raises(ValueError, match="unsupported daily PnL basis override"):
        AccountState(daily_pnl_basis_override="unknown")  # type: ignore[arg-type]

    account = AccountState()
    with pytest.raises(ValueError, match="unsupported max_drawdown_mode"):
        account.reset_operating_balance(90_000.0, max_drawdown_mode="trailing")


@pytest.mark.parametrize("value", [True, "not-a-number", float("inf")])
def test_account_state_rejects_non_finite_or_non_numeric_money(value: object) -> None:
    with pytest.raises(ValueError, match="open_pnl must be finite"):
        AccountState().update_equity(value)  # type: ignore[arg-type]


def test_account_state_observation_and_drawdown_fallbacks() -> None:
    account = AccountState(initial_balance=100_000.0)
    account.update_equity(1_000.0)
    account.update_equity(-500.0)
    assert account.trailing_drawdown_pct() == pytest.approx(1_500 / 101_000)
    assert account.to_array() == pytest.approx([0.0, -0.005, -0.005, 0.0, 0.005])

    account.peak_equity = 0.0
    assert account.trailing_drawdown_pct() == 0.0
    account.initial_balance = 0.0
    assert account.drawdown_pct() == 0.0


def test_account_state_snapshot_records_position_and_limit_order_lifecycle() -> None:
    account = AccountState(initial_balance=100_000.0)
    account.update_equity(125.0)
    position = Position(
        direction=1,
        size=0.5,
        entry_price=20_000.0,
        margin_used=2_000.0,
        mark_price=20_000.0,
        sl_price=19_900.0,
        tp_price=20_200.0,
    )
    snapshot = account_state_snapshot(
        account,
        valuation_time="2025-01-06T16:31:00Z",
        decision_time="2025-01-06T16:30:00Z",
        session_id=7,
        daily_loss_limit_usd=5_000.0,
        soft_daily_loss_limit_usd=4_000.0,
        max_loss_limit_usd=10_000.0,
        max_loss_floor_equity=90_000.0,
        max_drawdown_mode="static",
        max_drawdown_from_reference_usd=0.0,
        soft_max_loss_limit_usd=9_000.0,
        trailing_drawdown_limit_usd=10_000.0,
        soft_trailing_drawdown_limit_usd=9_000.0,
        risk_per_trade_limit_usd=900.0,
        position=position,
        trade_event_count=4,
        contract_size=1.0,
        point_value=2.5,
        pending_order={
            "order_id": "entry-1",
            "order_type": "limit",
            "action": -1,
            "limit_price": 19_950.0,
            "order_submission_time": "2025-01-06T16:30:00Z",
            "expiry_time": "2025-01-06T16:45:00Z",
            "decision_id": "decision-1",
            "risk_frac": 0.005,
            "rr_ratio": 2.0,
        },
    )

    assert snapshot["schema_version"] == "account_state_trace.v3"
    assert snapshot["point_value"] == 2.5
    assert snapshot["equity"] == 100_125.0
    assert snapshot["position_direction"] == 1
    assert snapshot["position_stop_price"] == 19_900.0
    assert snapshot["pending_order_id"] == "entry-1"
    assert snapshot["pending_order_type"] == "limit"
    assert snapshot["pending_order_direction"] == -1
    assert snapshot["pending_order_limit_price"] == 19_950.0
    assert snapshot["pending_order_expiry_time"] == "2025-01-06T16:45:00Z"
    assert snapshot["trade_event_count"] == 4
    assert snapshot["position_mark_price"] == 20_000.0
