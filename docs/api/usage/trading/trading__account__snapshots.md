# Trading · `account.snapshots`

This page contains 1 public callable records owned by `trading.account.snapshots`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `account_state_snapshot`

**Kind:** function · **Status:** stable · **Owner:** `trading.account.snapshots`

**Purpose:** Build a self-contained account state row at one valuation boundary.

**Exact API:** {py:obj}`trading.account.snapshots.account_state_snapshot` · **Source:** [trading/account/snapshots.py:12](../../../../trading/account/snapshots.py#L12)

**Inputs and outputs:**

- **Args:**

  ```text
  account: Account state at the requested valuation boundary.
  valuation_time: Timestamp used to value equity and open exposure.
  decision_time: Timestamp at which the policy may observe account state.
  session_id: Active session identifier, when one is available.
  state_phase: Label identifying the side of an action represented by the row.
  daily_loss_limit_usd: Hard daily-loss allowance in dollars.
  soft_daily_loss_limit_usd: Soft daily-loss threshold in dollars.
  max_loss_limit_usd: Hard maximum-loss allowance in dollars.
  max_loss_floor_equity: Equity floor implied by the maximum-loss policy.
  max_drawdown_mode: Selected static, EOD, or intraday trailing mode.
  max_drawdown_from_reference_usd: Current drawdown from the policy reference.
  soft_max_loss_limit_usd: Soft maximum-loss threshold in dollars.
  trailing_drawdown_limit_usd: Hard trailing drawdown allowance in dollars.
  soft_trailing_drawdown_limit_usd: Soft trailing drawdown threshold in dollars.
  risk_per_trade_limit_usd: Maximum permitted risk for one trade.
  position: Open position snapshot, if a position is active.
  pending_order: Pending entry-order fields, if an order is active.
  cumulative_payouts: Total payouts already withdrawn from the account.
  cycle_count: Repeated-payout cycle number.
  breach_reason: Risk-breach reason attached to this state, if any.
  trade_event_count: Number of trade events recorded so far.
  contract_size: Instrument contract size used in the account valuation.
  ```

- **Returns:**

  ```text
  Versioned mapping of account equity, guardrails, position, and order state.
  ```

**Observed usage:**

1. [test fixture: `_write_complete_trace_split`](../../../../tests/unit/research/test_numerical_report_verifier.py#L396)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    from trading.account.snapshots import account_state_snapshot

    account = AccountState(initial_balance=100.0)
    trace = pd.DataFrame(
        [
            account_state_snapshot(
                account,
                valuation_time="2025-01-01T00:00:00Z",
                decision_time="2025-01-01T00:00:00Z",
                session_id=1,
                daily_loss_limit_usd=5.0,
                soft_daily_loss_limit_usd=5.0,
                max_loss_limit_usd=10.0,
                max_loss_floor_equity=90.0,
                max_drawdown_mode="static",
                max_drawdown_from_reference_usd=0.0,
                soft_max_loss_limit_usd=10.0,
                trailing_drawdown_limit_usd=10.0,
                soft_trailing_drawdown_limit_usd=10.0,
                risk_per_trade_limit_usd=1.0,
                trade_event_count=0,
                contract_size=1.0,
            )
        ]
    )
    equity = pd.Series([100.0, 100.0, 100.0], index=pd.RangeIndex(3))
    trades = pd.DataFrame(
        columns=["type", "position_id", "direction", "time", "price", "fill_quote_source"]
# … caller assertions omitted …
```

2. [test fixture: `test_account_state_snapshot_records_position_and_limit_order_lifecycle`](../../../../tests/unit/trading/test_account_state_snapshots.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
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

    assert snapshot["schema_version"] == "account_state_trace.v2"
    assert snapshot["equity"] == 100_125.0
    assert snapshot["position_direction"] == 1
    assert snapshot["position_stop_price"] == 19_900.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
