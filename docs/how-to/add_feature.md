# Add a feature

Add a feature when it provides a causal, well-defined measurement to the
observation contract. Keep feature calculation separate from trade execution
and policy preference.

1. Specify the quantity, units, source timeframe, availability time, warm-up
behavior, missing-value behavior, and invalidation rules.
2. Implement it in the owning `features/` subdomain and expose configuration
   through the canonical configuration schema when it is optional.
3. Align a higher-timeframe value only after its source bar is complete. Fit
   learned or rolling normalization on training rows only.
4. Add focused tests for values, boundaries, missing inputs, causal prefix
   invariance, and train/test normalization behavior.
5. Include the feature definition and relevant settings in cache identity.
6. Update the feature and configuration documentation, then run the focused
   feature tests and docs checks.

Read [feature architecture](../modules/features.md),
[causal feature concepts](../concepts/market_structure.md), and
[configuration ownership](../config.md) before editing.
