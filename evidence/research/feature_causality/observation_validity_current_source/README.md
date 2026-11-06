# Observation validity across configured feature profiles

This packet measures the configured model-facing training observations for each effective feature and observation contract in the feature inventory. It reports sampled, finite, non-finite, leading-warmup, and finite-zero counts by profile group, timeframe, and feature.

`column_warmup_all_profiles.csv` is the consolidated per-feature table. Each `profiles/` subdirectory contains its resolved runtime configuration, source summary, per-feature table, and run log. `run_plan.json` records the inventory identity and group progress; `observation_warmup_validity_all_profiles.json` is the aggregate manifest.

The packet measures feature validity, not the semantic cause of every missing value, learned-policy behavior, or economic performance. Producer-specific cause attribution remains a separate review.

## Regeneration

`.venv/bin/python scripts/research/analysis/features/audit_observation_warmup_validity_profiles.py --inventory evidence/research/feature_causality/feature_configuration_inventory.json --output-dir evidence/research/feature_causality/observation_validity_current_source --cache-dir /scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/observation_validity_current_source_cache --workers 4`
