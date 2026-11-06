# Observation validity priorities

This packet aggregates the profile-wide observation-validity table by timeframe and feature. Flags identify all-group missingness, interior missing values, cross-group differences, and missing/finite-zero collisions. They are triage signals only; they do not establish the producer-level cause or economic meaning.

Input SHA-256: `23985c8b9bff4aff95c74d627510255e2b12c7dc6edbd54b6d704ba1afa53537`. Analyzer SHA-256: `fbf9cb96c25877063a05f45165334e252b323d67db845c0894cc298c113e8d51`.

Regenerate with:

```bash
.venv/bin/python scripts/research/analysis/features/summarize_observation_validity.py
```.
