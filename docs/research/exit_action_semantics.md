# Exit-action semantics

**Status:** Exploratory. **Result class:** frozen checkpoint decoder contrast plus selected common-entry cohort. **Period:** 2025 training partition. **Reproduction:** R2 for the tracked 53-row exact-common-entry cohort; the complete closed-loop replay is not reproducible from this bundle.

The evidence packet compares frozen v2 and structural-neutral v3 behavior. It records a small exact-common-entry intersection and diagnostics around changed entry/exit behavior. The review states that the exact matches are post-divergence selected and do not isolate a causal decoder effect. The fixed-entry shadow is conditional trade-level analysis, not a full replay; these results do not justify a new training campaign.

The reproduction notebook recomputes tracked cohort totals and a monthly comparison figure from CSV/JSON. Full per-arm ledgers, raw tick data, and checkpoints are not included, so the notebook does not reproduce the full replay.

- **Method and interpretation:** [decoder behavior comparison](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/exit_action_semantics/decoder_behavior_comparison.md)
- **Evidence:** [semantic packet](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/exit_action_semantics/README.md) and [checksum manifest](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/exit_action_semantics/evidence_manifest.json)
- **Limitations:** exact cohort is 53 selected common entries; later account state and action streams differ after the first divergence.
- **Reproduction:** [R2 cohort notebook](../reproduce/exit_action_semantics.ipynb)
- **Registry:** [result registry](../reproduce/result_registry)
