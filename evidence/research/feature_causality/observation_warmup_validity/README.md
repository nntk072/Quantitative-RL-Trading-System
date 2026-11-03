# Observation feature warmup and validity audit

This packet measures non-finite values in the current configured model-facing feature columns over the local training split. M1 rows and higher-timeframe completed-candle boundaries are sampled from the same feature pipeline and timeframe-start rule used by the environment.

`column_warmup.csv` reports each stream feature's sampled row count, finite/non-finite values, leading and interior missing counts, finite zero count, and whether a finite zero collides with missing values. Finite values in zero-variance normalization windows map to zero; unavailable source values and fit statistics remain nonfinite and are later zero-filled by observation construction. Representative producer causes and validity signals are reviewed in [`missingness_semantics.md`](missingness_semantics.md); the full feature-by-feature validity gate remains open.

This is input-contract evidence, not a learned-policy or economic result. The configured input manifest, resolved config, and source identities are recorded in `warmup_validity_summary.json`.

## Regeneration

`.venv/bin/python scripts/research/analysis/features/audit_observation_warmup_validity.py --config config/research/trade_setup_mtf_reasoning_2m.yaml --output-dir evidence/research/feature_causality/observation_warmup_validity --cache-dir /scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/observation_warmup_cache`
