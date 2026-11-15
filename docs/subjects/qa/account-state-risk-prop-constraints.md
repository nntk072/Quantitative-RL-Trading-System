# QA: Account state, risk, prop constraints

**Status:** source claims checked. Reviewed against source commit `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15; no tests or notebooks were rerun by QA.

## Source claims checked

1. Equity is balance plus open PnL, validated before mutation: confirmed in `trading/account/account_state.py::update_equity`.
2. Session anchors reset and canonical daily loss follows the selected PnL basis: confirmed in `trading/account/account_state.py::reset_daily`, `to_risk_state`, and `canonical_daily_loss`.
3. The versioned risk state rejects unsupported versions/bases, nonfinite money, and negative open risk or daily limit: confirmed in `trading/risk/contracts.py::RiskState`.
4. Dynamic approval caps requested risk by policy and both remaining capacities, then subtracts the nonnegative execution reserve: confirmed in `trading/risk/budget.py::approve_dynamic_risk`.
5. Hard daily, maximum, and trailing loss reasons have rollout breach scope; daily hard allowance is a percentage of initial balance: confirmed in `trading/risk/guardrails.py::guardrail_breach_scope` and `FTMOGuardrails.daily_limit_for`.

## Document and notebook checks

The hub has 154 lines and all required sections: Summary, Key terms, Explanation, Worked example, Tasks, Contract, Verify, Limits, Review procedure, Diagnostic cases, and Maintainer note. All 10 local Markdown links resolve; the hidden toctree notebook exists. The paired notebook has a title, Tier A/CPU/deterministic data/under-60-second/subject/owner metadata and forced MyST execution. Its one code cell has execution count 1, one saved output, and no saved error. The output reports equity `$99,750`, daily floor `$95,000`, and approved risk `$972.50`.

This fixture does not certify prop-firm compliance or model actual slippage. Current `trading/risk/contracts.py` differs from the pinned source only in a breach-event comment; the claim check used the pinned contract, not a current-code test run.
