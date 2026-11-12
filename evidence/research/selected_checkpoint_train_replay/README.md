# Selected checkpoint training replay

**Status: withdrawn historical result.** The seed-50 A4A/A4B replay metrics and
survival outcomes are removed from current performance presentation. The
tracked JSON is a provenance stub preserving source, run, input, and replay
report hashes. The prior result payload remains in Git history; external replay
reports and raw logs remain archive provenance only.

The reports use the pinned training source commit
`0d056dcd3ab42165eec183a2f44cfe7e441edd39`. Its reanalysis CLI received one
narrow guard change so a train-only screen may use stochastic actions only
when a seed is explicit or recorded. The changed runner file is separately
hashed in `SOURCE_SHA256SUMS`; current CLI behavior and its focused regression
are covered by the repository's reanalysis tests.

The full JSON screens and raw logs remain outside the repository at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/checkpoint_replay_a4_pinned_0d056dc/`.
Their output hashes and source run/input identities are retained in the
withdrawal stub. Do not cite those reports as current performance evidence or
model-selection results. The A4B raw log contains an interrupted duplicate
process entry; that historical operational detail is retained in the archive.

The replayed train interval contains 351,432 bars from 2024-12-30 through
2025-12-31. Each output explicitly records `test_split_evaluated: false`.
The rebuilt train-bar and train-feature digests match both source run
manifests. The report records a rebuilt-cache digest check and labels raw tick
identity as not reloaded, so this packet does not claim full raw-tick or
cross-version dataset parity. No new policy training occurred.
