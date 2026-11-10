# Historical v40 all-profile feature prefix invariance (2026-11-06)

The 2026-11-06 source-current real-market prefix audit resolved all 130 inventoried profiles into 19 feature-builder groups. All 57 registered group/cutoff comparisons passed at the three cutoffs (2025-12-15, 2026-03-09, and 2026-06-15), with zero changed values and zero maximum absolute delta across 21,741,766,365 compared values. It used feature-cache identity `v40-ifvg-missing-atr-distance`.

The audit ran as four worker shards in Slurm job `21437787` on csl13 (32 CPUs, 128 GiB requested). Slurm recorded 1:57:08 wall time, 5:08:14 CPU time, 79.93 GiB peak RSS, and 2.63 average allocated cores used. The merged packet independently matches all 78 current source hashes and the 130-profile inventory identity. Its four local M1 input hashes match the existing checked input registry; no provider, licensing, or external calendar claim is made. The current audit's numeric results are identical to the prior source-snapshot packet, while eight source hashes changed and are now recorded here.

This establishes prefix invariance for the listed source snapshot, resolved profiles, local inputs, and cutoffs. It does not prove every execution, label, model-selection path, publication timestamp, or logical-event identity is leakage-free. This v40 result is superseded by the preliminary v43 audit below; the older v39 report remains at [`real_market_feature_prefix_invariance_v39.json`](../real_market_feature_prefix_invariance_v39.json).

## Superseded preliminary v43 audit (2026-11-10)

This run used source commit `332ba0f17b4efc6f7b5908f09b6ca2be739d2e63` and
feature-cache identity `v43-heldout-fit-state`. It passed all 57 cutoffs across
the 130 profiles in the then-current inventory, comparing 21,749,324,775 values
with zero maximum absolute delta. It covered 630,787 rows from 2024-12-30
through 2026-10-16, and its source and input hashes verified at run time.

The inventory was incomplete: it omitted nine valid runtime research overlays,
including `research/survival_qualification`. The refreshed inventory now has
141 profiles. This preliminary pass therefore does not close the current-source
prefix gate. Its merged report, shard reports, launch metadata, source hashes,
and scoped gate record are preserved with `_inventory_130` in their filenames.
The 2026 interval was used only for report-only prefix auditing, not for
candidate selection, model training, or threshold changes.

The expanded 141-profile audit is in progress. Its result will replace the
current gate disposition only after all shards and hashes verify. Prefix
invariance does not establish external feed publication timing or every
execution, label, or model-selection path; those remain separate review gates.

`CURRENT_INPUT_SHA256SUMS` permits independent raw-input hash checks from the
repository root. `SHA256SUMS` covers all packet files except itself.
