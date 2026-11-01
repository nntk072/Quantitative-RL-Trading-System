# Exit-action semantics

**Status:** Exploratory. **Result class:** frozen checkpoint decoder contrast plus selected common-entry cohort. **Period:** 2025 training partition. **Reproduction:** R2 for the tracked 53-row exact-common-entry cohort; the complete closed-loop replay is not reproducible from this bundle.

The evidence packet compares frozen v2 and structural-neutral v3 behavior. It records a small exact-common-entry intersection and diagnostics around changed entry/exit behavior. The archived review states that the exact matches are post-divergence selected and do not isolate a causal decoder effect. Gate G2 was not met, the fixed-entry shadow is incomplete, and no fresh training campaign is authorized by this evidence packet.

The reproduction notebook recomputes tracked cohort totals and a monthly comparison figure from CSV/JSON. Full per-arm ledgers, raw tick data, and checkpoints are not included, so the notebook does not reproduce the full replay.

- **Method:** [frozen evidence findings](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/evidence/exit_action_semantics_20261024/exit_semantics_findings.md)
- **Evidence:** [archive README](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/evidence/exit_action_semantics_20261024/README.md)
- **Limitations:** exact cohort is 53 selected common entries; later account state and action streams differ after the first divergence.
- **Reproduction:** [R2 cohort notebook](../reproduce/exit_action_semantics.ipynb)
- **Registry:** [result registry](../reproduce/result_registry)
