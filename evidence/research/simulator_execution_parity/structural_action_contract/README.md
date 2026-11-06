# Structural action and entry contract

This packet records a bounded current-source check of environment decision
provenance and structural entry behavior. It is not historical-policy or
economic evidence.

The focused batch covered 76 cases across three modules and passed in the
existing GH200 allocation:

- Environment decision correlation: no-trade and inactive setup selection,
  plus decision identity carried through delayed order submission and fill.
- Backtest execution contract: structural stop execution, protective quote
  conversion, next-open fallback, and related execution invariants.
- Structural entry levels: valid long/short side behavior, invalid directions,
  source-timeframe floors, candidate geometry, and target filtering.

The first run found one stale fixture assumption: the delayed-fill provenance
test set its episode limit on the fill step, then expected the position to
remain open. The environment correctly liquidated at that truncation boundary.
The test now leaves one nonterminal step after the delayed fill; production
behavior was unchanged. The initial run had 75 passes and this one failure; the
corrected 76/76 run is preserved in the external validation log referenced by
`run_metadata.json`.

This closes only the listed test subcases. A later current-source regression
batch is recorded in
`timeframe_and_payout_boundary_regressions.json` and
`timeframe_and_payout_boundary_regressions_output.txt`. Across 98 cases it
also verifies that both structural menus reject unknown `M99` source labels,
and that payout events are absent at $90,000, $95,000, and exactly $100,000.
The $110,250 positive case remains a $10,250 withdrawal. The result reflects
the user's rule that realized losses and initial principal are not withdrawable.

All of this remains bounded current-source evidence. Empty-mask behavior
across both engines, limit-order behavior (unsupported by the current action
path), authoritative same-timestamp tick chronology, historical PPO action
linkage, and full Stage E parity remain open.

Reproduce inside a compatible existing GH200 allocation:

```bash
.venv/bin/python -m pytest \
  tests/unit/simulation/test_environment/test_decision_correlation.py \
  tests/integration/backtest/test_engine_execution_contract.py \
  tests/integration/backtest/test_entry_levels.py -q
```

The initial 76-case run used scoped formatting and lint checks. The later
98-case run also passed scoped Ruff format and lint checks. It ran in the
single GH200 allocation recorded in its run metadata; no training, policy
replay, or child Slurm step was run.
