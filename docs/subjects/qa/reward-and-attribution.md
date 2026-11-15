# QA: Reward and attribution

**Status:** source claims checked. Reviewed against source commit `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15; no tests or notebooks were rerun by QA.

## Source claims checked

1. Step PnL is current equity plus payout withdrawn this step minus prior equity: confirmed in `simulation/environment/step_accounting_runtime.py::_record_step_accounting`.
2. Close fills receive unique records and aggregate into one position lifecycle: confirmed in `simulation/environment/trade_accounting_runtime.py::_stamp_exit`; `_note_close` retains the first realized close value for step reward use.
3. Equity-delta reward divides step PnL by positive finite fixed dollar risk and substitutes a hard-breach penalty: confirmed in `simulation/environment/rewards.py::EquityDeltaReward`.
4. Equity-log-growth reward uses supplied after-cost equity endpoints without a second cost deduction: confirmed in `simulation/environment/rewards.py::EquityLogGrowthReward`.
5. The named component keys exist, and nonzero raw rewards are rescaled on clipping to match the returned signal: confirmed in `simulation/environment/rewards.py::REWARD_PART_KEYS` and `fit_reward_parts`.

## Document and notebook checks

The hub has 158 lines and all required sections: Summary, Key terms, Explanation, Worked example, Tasks, Contract, Verify, Limits, Review procedure, Diagnostic cases, and Maintainer note. All 11 local Markdown links resolve; the hidden toctree notebook exists. The paired notebook has a title, Tier A/CPU/deterministic data/under-60-second/subject/owner metadata and forced MyST execution. Its one code cell has execution count 1, one saved output, and no saved error. The output reports step rewards `[0.25, -0.35, 0.9]`, path sum `0.8`, and breach component `-10.0`.

The fixture does not establish policy quality or OOS survival. Current `simulation/environment/rewards.py` differs from the pinned source only in a `PnLReward` docstring; this review checked pinned behavior and did not rerun tests.
