# Real-market prefix source reconciliation

The all-profile result in
[`real_market_feature_prefix_invariance_v39.json`](real_market_feature_prefix_invariance_v39.json)
records 57/57 passing comparisons across 19 feature-builder groups and three
cutoffs, with no changed features and a maximum absolute delta of 0.0. Its
current runner, merger, profile inventory, and all four M1 input hashes verify
against the checkout. Of the 78 recorded source hashes, 75 still match the
current files. The other three recorded hashes match the corresponding files
at the starting commit `367561a7717a3367fbb280084ffcf0781f57119c`.

The three later worktree changes were reviewed against the audit call path:

| Source | Recorded SHA-256 | Current SHA-256 | Change and relevance |
|---|---|---|---|
| `features/po3/setup_lifecycle.py` | `07abc7c5a6a5a762920311568d5b610ecfef688219ca79ed803b4187d8e95dd0` | `c1ed3324772ab4f0fc1ebbf2df884d15c4bc7d2aedeb84068391bb447d01460f` | Adds docstrings to two helpers; executable statements are unchanged. |
| `market_data/loading/bars.py` | `47d90773b0db0948bf301759cf877f92ff09f77ca8831c5a104f925177c4b7a6` | `78ec2e0aae8c86f85cf1fe8d7455bba94c8e601200eb3f66e7768017a2216962` | Changes the separate tick-chunk parser from float32 to float64; the prefix runner loads M1 bars through `load_bars` and does not call this tick parser. |
| `market_data/loading/ticks.py` | `5aefa10efa67f267c752c53a9d2832fe54c743cf4deda1dd1bb83b268df71a95` | `6973db5a21d0adeebfd7f44c808525efc77dfdbb61333170219c37c850f51a31` | Changes TickBook quote precision and cache identity; the prefix runner does not construct or read a TickBook. |

At the time of this reconciliation, the measured M1 feature matrices remained
applicable to current feature-producing code. This did not extend prefix
evidence to tick execution, quote selection, labels, candidate-to-action
linkage, or model selection. The original report is preserved unchanged so its
recorded source identities remain auditable.

## Subsequent SMT source correction — 2026-11-04

`features/context/smt.py` now detects secondary-symbol pivots on observed
source rows. The prior implementation forward-filled secondary OHLC onto the
primary index before pivot detection, so a missing confirmation row became a
duplicate bar and could suppress a valid confirmed pivot. Forward-fill remains
for the secondary close used by spread and rolling-correlation features. A
focused synthetic regression reproduces the prior missing divergence and
passes with the corrected source. The feature cache identity advanced to
`v38-smt-observed-pivots`, and the source-linked feature matrix was regenerated.

The prior all-profile market prefix result remains 57/57 for its recorded
sources, but its recorded `features/context/smt.py` hash
`8cb98e0dcc80374250855f333a4e199b2461b5c6c539089b60091b1b4348bf03` no longer
matches current source
`8b669f666fe119b3dd8d1f7d953a440f709097839c1f50b940bd1a87e96b224e`. Because
SMT participates in some resolved profiles, the old aggregate cannot close
current-source prefix acceptance. Regenerate the all-profile audit and verify
the changed feature outputs in an eligible GH200 allocation before closing the
Stage D prefix gate.

## Current-source rerun — `v39-feature-validity-semantics`

The current all-profile rerun used the existing one-GH200 allocation
`21390062` on gpuarm1. The strict four-shard merger covered all 130 profiles
across 19 feature-builder groups and passed 57/57 cutoff comparisons, with no
failed comparisons and zero maximum absolute delta. It records 78 source hashes
and four local input hashes, all matching the run's source and input snapshot.
The regenerated report is
[`real_market_feature_prefix_invariance_current_source/report.json`](real_market_feature_prefix_invariance_current_source/report.json);
the pre-v39 JSON is preserved in the external agent-plan superseded-evidence
archive.

This run includes the SMT observed-pivot correction and v39 validity semantics:
outside-session `po3_phase` uses the `-1` sentinel, and a valid zero-range
candle has zero upper-wick ratio. This establishes prefix invariance for the
resolved local inventory and three tested cutoffs. It does not establish source
publication time, external session/calendar authority, logical-event
cardinality, untested configurations, execution/label paths, or model-selection
behavior; these remain separate Stage D gates.

## Final current-source rerun — v40 IFVG missing-ATR distance

The subsequent feature cache identity is
`v40-ifvg-missing-atr-distance`. The full all-profile audit ran in GH200 job
`21405414` on 2026-11-04 and passed all 57 cutoffs across 19 builder groups
and 130 resolved profiles, comparing 21,741,766,365 values with zero changed
values and zero maximum absolute delta. The strict merger completed full
shard/profile/group/cutoff validation. An independent post-run hash check
matched all 78 recorded sources, the feature inventory, and all four local M1
inputs to current bytes. The current packet is
[`real_market_feature_prefix_invariance_current_source/`](real_market_feature_prefix_invariance_current_source/).

This closes real-market prefix invariance for that inventory, source snapshot,
and three cutoffs. It does not close source-event identity, publication timing,
logical-event cardinality, execution, labels, or model selection.
