# Observation validity priorities

This packet aggregates the profile-wide observation-validity table by timeframe and feature. Flags identify all-group missingness, interior missing values, cross-group differences, and missing/finite-zero collisions. They are triage signals only; they do not establish the producer-level cause or economic meaning.

Input SHA-256: `f71f31c086073b3ea866e370a44d0ae8946421f0ceeb8ec729889a8eb6457fd5`. Analyzer SHA-256: `ddab6b21c44d56e62387b752017436eb2eccb01be437296d8a6cd4a9da92f53b`.

Regenerate with:

```bash
.venv/bin/python scripts/research/analysis/features/summarize_observation_validity.py
```.
