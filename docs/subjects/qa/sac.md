# QA: SAC

**Status:** pinned source claims reviewed at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15. Current dirty-source-only behavior was not verified.

## Five source claims

1. Builder rejects non-Box action spaces before constructing SAC.
2. Builder uses `pi`/`qf` head lists and `MultiInputPolicy`; SAC actor/critic extractors are separate.
3. Builder forwards SAC replay/update settings from configured values or defaults.
4. `persist_action_schema` binds declared Box action semantics to model and policy.
5. Checkpoint loader chooses PPO/SAC from explicit `algo` and binds the supplied environment.

## Document and notebook checks

The hub has 171 lines and all required sections: summary, terms, explanation, worked example, tasks, contract, verify, limits, change checklist, review procedure, and maintainer note. All 7 hub and 2 reference Markdown links resolve locally; the hidden toctree notebook exists. The reference has five contract rows.

The paired notebook has a title and first Markdown title cell, Python 3 kernel, Tier A/CPU/bundled deterministic data/under-60-second/subject/owner metadata, and forced MyST execution. Its one code cell has execution count 1, 1 saved output, and 0 saved errors. Code has an assertion. QA inspected saved state and did not rerun it. Saved result: `Fixed replay sample: [1.0, 0.25, 1.0]`.

## Evidence limit

Repeated indices illustrate replay reuse only; no Bellman update, entropy optimization, or return is measured. This page and notebook are teaching material, not OOS, survival, or economic evidence. The exposed 2026 reporting interval is not a selection source.
