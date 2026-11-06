# Candidate conditional outcomes

This training-only packet replays each statically eligible candidate proposal independently for every permitted stop/target pair. It is a conditional fixed-entry estimand and excludes account state, portfolio contention, policy action, and closed-loop policy value. Incomplete local quote coverage truncates the replay; those records are unresolved rather than labeled as no-touch or no-exit. Administrative censoring at the training cutoff remains right-censored.

Limit fills respect the submitted price bound and record the configured exact-touch or strict trade-through assumption in the execution parameters. Market slippage applies only to market entries.

`outcome_manifest.json` identifies the proposal, coverage, config, TickBook, source, execution parameters, outcome counts, and output hash.
