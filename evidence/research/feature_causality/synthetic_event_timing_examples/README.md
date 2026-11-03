# Synthetic event-timing examples

These four SVGs make the causal timing explicit with synthetic UTC timestamps:

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

The timestamps and prices are illustrative fixture values, not market
observations, provider timestamps, or a strategy result. The retest and session
examples explain configured semantics only. They do not establish external
calendar authority, feed publication timing, or correctness across all active
event families. The source fixture is
`tests/fixtures/research/idea12/synthetic_examples.json`.

Reproduce from the repository root:

```bash
.venv/bin/python scripts/research/analysis/features/plot_synthetic_entry_timing_examples.py \
  --fixture tests/fixtures/research/idea12/synthetic_examples.json \
  --output-dir evidence/research/feature_causality/synthetic_event_timing_examples
```

`run_metadata.json` records the fixture, renderer, and test hashes; `run_output.txt`
preserves the focused format/lint, test, and generation output.
