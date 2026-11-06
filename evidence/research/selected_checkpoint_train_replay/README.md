# Selected checkpoint training replay

This packet records seeded stochastic, training-split-only replays of the two
selected seed-50 A4 checkpoints. Both replay reports reproduce the saved
training metrics for trade count, return, Sharpe, maximum drawdown, and breach
count. Both paths failed the full-evaluation survival gate. This verifies the
serialized checkpoint execution for the recorded training mode; it does not
repair the failed candidate, authorize another training campaign, establish
causal failure attribution, or evaluate the report-period split.

The reports use the pinned training source commit
`0d056dcd3ab42165eec183a2f44cfe7e441edd39`. Its reanalysis CLI received one
narrow guard change so a train-only screen may use stochastic actions only
when a seed is explicit or recorded. The changed runner file is separately
hashed in `SOURCE_SHA256SUMS`; current CLI behavior and its focused regression
are covered by the repository's reanalysis tests.

The full JSON screens and raw logs remain outside the repository at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/checkpoint_replay_a4_pinned_0d056dc/`.
Their output hashes, source run identities, input identities, and exact
replayed metrics are summarized in `replay_verification.json`. The A4B raw log
contains an interrupted duplicate process entry; the successful output JSON
was separately validated against its source run and is the evidence artifact.

The replayed train interval contains 351,432 bars from 2024-12-30 through
2025-12-31. Each output explicitly records `test_split_evaluated: false`.
The rebuilt train-bar and train-feature digests match both source run
manifests. The report records a rebuilt-cache digest check and labels raw tick
identity as not reloaded, so this packet does not claim full raw-tick or
cross-version dataset parity. No new policy training occurred.
