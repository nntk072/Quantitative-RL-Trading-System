# Synthetic event-timing examples

These seven SVGs make the causal timing explicit with synthetic UTC timestamps:

- `confirmed_po3_ifvg_entry_timing.svg`: pivot availability, sweep/reclaim,
  IFVG confirmation close, submission, and earliest next-bar fill.
- `incorrect_same_bar_ifvg_entry.svg`: an invalid fill at the confirmation
  bar's open, before that bar's IFVG confirmation close, beside the valid
  next-bar open.
- `previous_session_premium_gate.svg`: a synthetic previous-session premium
  rejection. Its session labels are configured-example labels; no external
  schedule claim is made.
- `confirmed_ifvg_retest_timing.svg`: the optional confirmed-retest path,
  separated from the main first-eligible entry.
- `swing_confirmation_timing.svg`: the candidate pivot time and the later time
  when two right-side bars make that swing observable; acting at the pivot time
  would use future bars.
- `order_block_retest_timing.svg`: zone availability, first overlap, later
  close-confirmed retest, and earliest next-bar action. An overlap alone does
  not satisfy the tested retest contract.
- `smt_secondary_bar_availability.svg`: a missing secondary-symbol bar uses
  the last available close; the next close is not visible early through a
  backward fill.

The timestamps and prices are illustrative fixture values, not market
observations, provider timestamps, or a strategy result. The retest and session
examples explain configured semantics only. They do not establish external
calendar authority, feed publication timing, or correctness across all active
event families. The swing timing follows the pivot-confirmation contract tested
in `tests/unit/features/test_pivots_swings.py`; the order-block sequence follows
the later-close contract in `tests/unit/features/test_order_blocks.py`; the SMT
availability example follows the forward-fill contract in
`tests/unit/features/test_smt.py`, including a regression that confirms a
missing secondary row does not become a duplicate pivot-confirmation bar. The
SMT implementation now detects pivots on observed secondary rows and only
forward-fills the close used for synchronized spread/correlation. The source fixture is
`tests/fixtures/research/idea12/synthetic_examples.json`.

Reproduce from the repository root:

```bash
.venv/bin/python scripts/research/analysis/features/plot_synthetic_entry_timing_examples.py \
  --fixture tests/fixtures/research/idea12/synthetic_examples.json \
  --output-dir evidence/research/feature_causality/synthetic_event_timing_examples
```

`run_metadata.json` records the fixture, renderer, and test hashes; `run_output.txt`
preserves the focused format/lint, test, and generation output.
