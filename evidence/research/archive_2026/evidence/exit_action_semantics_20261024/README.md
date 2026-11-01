# Exit-action semantics evidence packet

This packet records the frozen-checkpoint v2 versus structural-neutral v3 replay requested in the original proposal. No training was run and the 2026 split was not evaluated.

## Current evidence decision

- G0 passed for the selected 2025 training partition, with the full raw-tick identity caveat recorded in the findings report.
- G1 passed for the frozen closed-loop decoder contrast.
- G2 was not met: the full fixed-v2-entry shadow is incomplete, so the report recommends no fresh 2M run yet.
- G3 was not reached; no 20M campaign was run.

The 53 exact same-entry comparisons are a small, post-divergence-selected subset and do not establish that either decoder is economically superior. The next planning question is whether the proposed fixed-entry shadow is the minimum sufficient analysis to separate exit treatment from changed entry eligibility and sequential feedback, and what acceptance criteria should precede any new training.

## Files

- `original_exit_action_semantics_proposal.md`: original planning request, preserved as supplied.
- `exit_semantics_findings.md`: complete interpretation, metrics, limitations, and gate decision.
- `provenance.json`, `decision_gates.json`, `config.yaml`: identities and resolved run settings.
- `exit_semantics_equity_v2_vs_v3_train2025.png`: training-split equity and drawdown figure.
- `phase2_fixed_v2_entry_cohort.csv` and its summary: full frozen v2 entry cohort and current sequential-v3 alignment.
- Other CSV/JSON files: comparison, action, exit, time-slice, and unmatched-cohort diagnostics.
- `counterfactual_patch.diff`: exact temporary decoder and CSV-export changes used in the archived-source replay.
- `*.py.txt`: text snapshots of the analysis scripts used to produce this packet.

This is evidence for planning and review. It does not authorize code changes, training, or use of the exposed 2026 split. Per-arm full ledgers and raw tick data remain in the original run locations; see `provenance.json`.
