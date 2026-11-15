# QA: Neural encoders and multitimeframe observations

**Status:** pinned source claims reviewed at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15. Current dirty-source-only behavior was not verified.

## Five source claims

1. `encoder_for` rejects unknown architecture IDs.
2. `_MTF_STREAMS` defines sequence/mask pairs; constructor rejects a missing mask.
3. `MTFEncoder.__init__` requires `seq` and creates a branch per present stream.
4. `_CausalTCN.forward` derives valid lengths and encodes valid suffixes.
5. `MTFEncoder.forward` fuses timeframe latents before concatenating account embedding.

## Document and notebook checks

The hub has 171 lines and all required sections: summary, terms, explanation, worked example, tasks, contract, verify, limits, change checklist, review procedure, and maintainer note. All 7 hub and 2 reference Markdown links resolve locally; the hidden toctree notebook exists. The reference has five contract rows.

The paired notebook has a title and first Markdown title cell, Python 3 kernel, Tier A/CPU/bundled deterministic data/under-60-second/subject/owner metadata, and forced MyST execution. Its one code cell has execution count 1, 1 saved output, and 0 saved errors. Code has an assertion. QA inspected saved state and did not rerun it. Saved result: `Last valid rows: {'m1': 2.0, 'm5': 8.0}`.

## Evidence limit

Mask selection is not a learned activation check; upstream availability and trading quality remain unmeasured. This page and notebook are teaching material, not OOS, survival, or economic evidence. The exposed 2026 reporting interval is not a selection source.
