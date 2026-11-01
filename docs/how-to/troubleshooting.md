# Troubleshooting by symptom

Start from the earliest failing boundary and keep the run's resolved config,
logs, and artifact identity together. Do not repair a symptom by changing
multiple experiment factors at once.

## No trades

1. Confirm the episode contains valid bars and expected timestamps/sessions.
2. Inspect action frequencies and whether the policy chooses `NO_TRADE` or
   another non-entry action.
3. Inspect entry eligibility masks, active setup candidates, blackout/session
   rules, and rejection counters in the step/run diagnostics.
4. If intents are emitted, inspect stop/target availability, requested risk,
   account limits, and modeled execution reserve.
5. Verify feature values and validity masks at the exact attempted timestamp.

Useful pages: [trade lifecycle](../concepts/trade_lifecycle.md),
[trade setup catalog](../reference/trade_setup_catalog.md),
[zero-trade diagnostics](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/simulation/environment/README.md#entry-diagnostics).

## NaN or non-finite values

Trace the first non-finite value, not only the final metric. Check raw OHLCV,
feature denominators, normalization fit scope, padding/masks, reward components,
policy logits, and account equity after each boundary. Keep the timestamp,
feature name, and resolved config. Use existing assertions and tests for the
specific pipeline; do not replace NaNs with zero unless the feature contract
defines that fallback and its validity mask is preserved.

## Slow training

Separate input construction, environment stepping, policy forward/backward,
rollout transfer, logging, and checkpoint writing. Measure environment steps
per second and GPU utilization in the allocation; a GPU model does not prove
that the GPU is the bottleneck. Compare the exact `n_envs`, rollout geometry,
sequence size, and device path. See [performance engineering](../operations/performance.md)
and the [throughput audit](../research/gh200_throughput_audit.md).

## Checkpoint mismatch

Compare serialized and current observation/action schema versions, feature
columns/order, encoder class/config, algorithm, policy head, library versions,
and saved resolved config. Use the
[checkpoint compatibility](../reference/checkpoint_compatibility.md) guide
and the migration record linked there. Do not force-load by ignoring a schema
mismatch: tensor shape compatibility does not establish semantic compatibility.

## Out of memory

Record host RAM and device memory separately. Reduce one documented resource
driver at a time: environment count, observation window, batch size, encoder
width, or on-device rollout staging. Confirm that a resource adjustment does
not violate a frozen experiment's required rollout geometry. Follow the
[Triton environment guide](../operations/triton.md) for node/venv matching and
the [hardware matrix](../operations/hardware.md) for known constraints.

## Risk rejection or unexpected forced close

Inspect the reported guardrail/rejection reason, account equity, daily and
trailing drawdown values, planned stop risk, position size, execution reserve,
and current open exposure. Distinguish the strategy stop, account-level hard
loss backstop, and episode termination. See
[risk/account limits](../concepts/risk_and_account_limits.md) and
[risk/execution reference](../reference/risk_and_execution.md).

## Bad or stale feature cache

Compare cache manifest/content hash with feature config, primary/secondary
input identities, timeframe bars, training mask, normalization mode, and
timezone/session schedule. Rebuild through
[the cache how-to](build_feature_cache.md) only after identifying the changed
input. The cache version and content hash work together.

## Escalation record

For a reproducible issue, attach the source SHA, command, resolved config,
input/cache identities, timestamps, exact first failing boundary, relevant
log excerpt, and a minimal test or synthetic trace. Never attach secrets or
private broker credentials.
