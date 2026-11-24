# Trading · `policy.fixed_risk`

This page contains 1 public callable records owned by `trading.policy.fixed_risk`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `uses_fixed_risk_budget`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.fixed_risk`

**Purpose:** Return whether legacy settings require fixed risk sizing.

**Exact API:** {py:obj}`trading.policy.fixed_risk.uses_fixed_risk_budget` · **Source:** [trading/policy/fixed_risk.py:8](../../../../trading/policy/fixed_risk.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  risk_mode: Configured risk-sizing mode.
  repeated_payout: Whether repeated payouts are enabled.
  ```

- **Returns:**

  ```text
  True when the fixed-risk budget path is required.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = uses_fixed_risk_budget(risk_mode=..., repeated_payout=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
