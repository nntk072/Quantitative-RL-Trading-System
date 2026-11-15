# QA: PPO and rollout geometry

**Status:** pinned source claims reviewed at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15. Current dirty-source-only behavior was not verified.

## Five source claims

1. `build_agent` divides configured steps by logical environments only with a factory and more than one environment; direct formula test absent.
2. Builder forwards PPO optimization settings; Box policy paths use `ent_coef_continuous`, while discrete keeps `ent_coef`.
3. Builder checks Box/ActionSchema for semantic heads; helper chooses policy class from action space and distribution.
4. Device rollout buffer stages NumPy arrays on device for minibatch indexing.
5. `SB3Learner.fit` saves bytes and returns actual steps and SHA-256; direct learner contract test exists.

## Document and notebook checks

The hub has 171 lines and all required sections: summary, terms, explanation, worked example, tasks, contract, verify, limits, change checklist, review procedure, and maintainer note. All 7 hub and 2 reference Markdown links resolve locally; the hidden toctree notebook exists. The reference has five contract rows.

The paired notebook has a title and first Markdown title cell, Python 3 kernel, Tier A/CPU/bundled deterministic data/under-60-second/subject/owner metadata, and forced MyST execution. Its one code cell has execution count 1, 1 saved output, and 0 saved errors. Code has an assertion. QA inspected saved state and did not rerun it. Saved result: `per environment: 3; aggregate: 9; minibatches: [4, 4, 1]`.

## Evidence limit

Toy sample arithmetic does not model SB3 optimization scheduling or policy quality. This page and notebook are teaching material, not OOS, survival, or economic evidence. The exposed 2026 reporting interval is not a selection source.
