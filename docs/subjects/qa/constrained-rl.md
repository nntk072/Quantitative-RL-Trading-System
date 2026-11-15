# QA: Constrained RL

**Status:** pinned source claims reviewed at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15. Current dirty-source-only behavior was not verified.

## Five source claims

1. `_episode_cost` scales daily/trailing increments to max-loss units and floors breaches at 1.
2. `_on_step` mutates rollout rewards by lambda times cost and checks batch lengths.
3. `_on_rollout_end` updates the bounded multiplier only with completed costs.
4. `_on_training_start` compares saved config and enforces lambda bounds.
5. Step constraint runtime applies account guardrails independently of callback reward shaping.

## Document and notebook checks

The hub has 171 lines and all required sections: summary, terms, explanation, worked example, tasks, contract, verify, limits, change checklist, review procedure, and maintainer note. All 7 hub and 2 reference Markdown links resolve locally; the hidden toctree notebook exists. The reference has five contract rows.

The paired notebook has a title and first Markdown title cell, Python 3 kernel, Tier A/CPU/bundled deterministic data/under-60-second/subject/owner metadata, and forced MyST execution. Its one code cell has execution count 1, 1 saved output, and 0 saved errors. Code has an assertion. QA inspected saved state and did not rerun it. Saved result: `Multiplier after completed episodes: [0.05, 0.15, 0.1]`.

## Evidence limit

Dual updates in bundled toy costs do not establish hard-risk safety or policy survival. This page and notebook are teaching material, not OOS, survival, or economic evidence. The exposed 2026 reporting interval is not a selection source.
