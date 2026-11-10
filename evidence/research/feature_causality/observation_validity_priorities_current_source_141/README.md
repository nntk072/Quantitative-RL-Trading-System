# Observation validity priorities

This packet aggregates the profile-wide observation-validity table by timeframe and feature. Flags identify all-group missingness, interior missing values, cross-group differences, and missing/finite-zero collisions. They are triage signals only; they do not establish the producer-level cause or economic meaning.

Input SHA-256: `1c8699f51db8f403ea8cb8c9b79fab11a28e970f48f9937038cbed04644aa888`. Analyzer SHA-256: `fbf9cb96c25877063a05f45165334e252b323d67db845c0894cc298c113e8d51`.

Regenerate with:

```bash
.venv/bin/python scripts/research/analysis/features/summarize_observation_validity.py --input /scratch/work/nguyenl37/Quantitative-RL-Trading-System/evidence/research/feature_causality/observation_validity_current_source_141/column_warmup_all_profiles.csv --output-dir /scratch/work/nguyenl37/Quantitative-RL-Trading-System/evidence/research/feature_causality/observation_validity_priorities_current_source_141
```.
