# QA: Training seeds, resume, and checkpoints

**Status:** pinned source claims reviewed at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15. Current dirty-source-only behavior was not verified.

## Five source claims

1. `SeedRunner.prepare_training` seeds RNG and creates per-seed output paths for multi-seed runs.
2. Runner checks checkpoint existence, loads prepared environment, validates schemas, and rejects excess steps; cited loader test is only adjacent.
3. Runner subtracts completed from requested steps and checks stop-candidate schema; cited periodic callback test does not cover this branch.
4. `SB3Learner.fit` streams saved bytes through SHA-256 and returns actual steps; learner contract test covers this.
5. `latest_resumable_checkpoint` checks attempt provenance/ZIP; `validate_initial_checkpoints` checks explicit parent lineage and hashes.

## Document and notebook checks

The hub has 170 lines and all required sections: summary, terms, explanation, worked example, tasks, contract, verify, limits, change checklist, review procedure, and maintainer note. All 7 hub and 2 reference Markdown links resolve locally; the hidden toctree notebook exists. The reference has five contract rows.

The paired notebook has a title and first Markdown title cell, Python 3 kernel, Tier A/CPU/bundled deterministic data/under-60-second/subject/owner metadata, and forced MyST execution. Its one code cell has execution count 1, 1 saved output, and 0 saved errors. Code has an assertion. QA inspected saved state and did not rerun it. Saved result: `Rejected: checkpoint steps exceed requested total | Remaining steps: 60 example digest: 29771b6443b5`.

## Evidence limit

The toy digest is over bundled bytes; it does not load, validate, or resume a production checkpoint. This page and notebook are teaching material, not OOS, survival, or economic evidence. The exposed 2026 reporting interval is not a selection source.
