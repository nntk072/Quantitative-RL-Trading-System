# Evaluation · `metrics.limit_execution_sensitivity`

This page contains 1 public callable records owned by `evaluation.metrics.limit_execution_sensitivity`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `compare_limit_execution_sensitivity`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.limit_execution_sensitivity`

**Purpose:** Compare paired backtests that differ only in limit-fill conservatism.

**Exact API:** {py:obj}`evaluation.metrics.limit_execution_sensitivity.compare_limit_execution_sensitivity` · **Source:** [evaluation/metrics/limit_execution_sensitivity.py:301](../../../../evaluation/metrics/limit_execution_sensitivity.py#L301)

**Inputs and outputs:**

- **Args:**

  ```text
  exact_touch_result: Backtest using the exact-touch limit fill assumption.
  trade_through_result: Backtest requiring price trade through the limit.
  ```

- **Returns:**

  ```text
  Paired sensitivity report covering contracts, decisions, orders, and outcomes.
  ```

**Observed usage:**

1. [test fixture: `test_limit_touch_and_trade_through_assumptions_are_explicit_sensitivities`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L637)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    assert conservative_result["execution_contract"]["limit_order"]["require_trade_through"] is True
    assert conservative_result["execution_contract"]["limit_order"]["fill_rule"] == (
        "strict_executable_quote_trade_through"
    )
    sensitivity = compare_limit_execution_sensitivity(exact_result, conservative_result)
    assert sensitivity["status"] == "execution_contracts_match"
    assert sensitivity["limit_order_counts"]["paired"] == 1
    assert sensitivity["paired_limit_outcomes"][0]["exact_touch"]["status"] == "filled"
    assert sensitivity["paired_limit_outcomes"][0]["trade_through"]["status"] == "cancelled"
    exact_events = exact_result["trades"].to_dict("records")
# … caller assertions omitted …
```

2. [test fixture: `test_limit_sensitivity_pairs_fill_and_cancellation_under_matching_inputs`](../../../../tests/unit/evaluation/test_limit_execution_sensitivity.py#L106)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                "reason": "limit_ttl_expired",
            },
        ],
    )

    report = compare_limit_execution_sensitivity(exact, strict)

    assert report["status"] == "execution_contracts_match"
    assert report["other_run_provenance_verified"] is False
    assert report["decision_counts"]["common"] == 1
    assert report["limit_order_counts"]["paired"] == 1
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
