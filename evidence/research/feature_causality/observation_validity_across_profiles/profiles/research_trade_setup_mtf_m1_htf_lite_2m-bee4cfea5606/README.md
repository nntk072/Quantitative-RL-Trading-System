# Observation feature warmup and validity audit

This packet measures non-finite values in the current configured model-facing feature columns over the local training split. M1 rows and higher-timeframe completed-candle boundaries are sampled from the same feature pipeline and timeframe-start rule used by the environment.

`column_warmup.csv` reports each stream feature's sampled row count, finite/non-finite values, leading and interior missing counts, finite zero count, and whether a finite zero collides with missing values. Finite values in zero-variance normalization windows map to zero; unavailable source values and fit statistics remain nonfinite and are later zero-filled by observation construction. The report does not assign every missing value a cause without producer-specific review.

This is input-contract evidence, not a learned-policy or economic result. The configured input manifest, resolved config, and source identities are recorded in `warmup_validity_summary.json`.

## Regeneration

`.venv/bin/python scripts/research/analysis/features/audit_observation_warmup_validity_profiles.py --inventory evidence/research/feature_causality/feature_configuration_inventory.json --output-dir evidence/research/feature_causality/observation_validity_across_profiles --cache-dir /scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/observation_warmup_cache_all_profiles --workers 4`
