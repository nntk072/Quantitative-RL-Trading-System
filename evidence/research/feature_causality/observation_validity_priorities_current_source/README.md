# Observation validity priorities

This packet aggregates the profile-wide observation-validity table by timeframe and feature. Flags identify all-group missingness, interior missing values, cross-group differences, and missing/finite-zero collisions. They are triage signals only; they do not establish the producer-level cause or economic meaning.

Input SHA-256: `59ba4ce35570b18c59a1bf948f611a44ed2341dbdc3dc53ba5fac38fd254e46b`. Analyzer SHA-256: `fbf9cb96c25877063a05f45165334e252b323d67db845c0894cc298c113e8d51`.

Regenerate with:

```bash
.venv/bin/python scripts/research/analysis/features/summarize_observation_validity.py --input /scratch/work/nguyenl37/Quantitative-RL-Trading-System/evidence/research/feature_causality/observation_warmup_validity_current_source/column_warmup_all_profiles.csv --output-dir /scratch/work/nguyenl37/Quantitative-RL-Trading-System/evidence/research/feature_causality/observation_validity_priorities_current_source
```.
