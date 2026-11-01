# Thesis figure and table index

This index links only existing evidence. It does not invent plots for gates
that have not been measured.

| Proposed thesis item | Existing source | Current status and limitation |
|---|---|---|
| Research evidence and reproduction grades | `docs/reproduce/result_registry.md` | Available; R1/R2 scope only, no research R3/R4. |
| P6 monthly trade count and outcome decomposition | `docs/research/p6_monthly_entry_exit.md`; `docs/reproduce/p6_monthly_exit_decomposition.ipynb` | Recomputed from paired rows; one seed, includes zero intervals, not causal. |
| 100k full-year policy equity | `docs/research/figures/setup_conditioned_policy_replay_equity.png` | Negative one-seed screen; both policies breached maximum loss. |
| Setup opportunity counts | `docs/research/entry_idea_opportunity_counts.md`; `docs/reproduce/entry_idea_opportunity_counts.ipynb` | Aggregate evidence; timestamp-level source/cache is not tracked. |
| Entry-context examples | `docs/research/order_block_and_multitimeframe_context.md` | Static previews; not strategy evidence. |
| Current data quality by month/timeframe | No valid current-source figure | Blocked by stale source hashes, incomplete timeframe parity, and unresolved calendar. |
| Matched baselines, independent seeds, and robustness | No complete comparable figure | Not established; do not fill with illustrative values. |

All plots intended for final thesis use must be regenerated from verified
source records after the corresponding gates pass. Provide vector and raster
exports, data tables, labels/units, sample denominators, uncertainty, and exact
manifest references at that time.
