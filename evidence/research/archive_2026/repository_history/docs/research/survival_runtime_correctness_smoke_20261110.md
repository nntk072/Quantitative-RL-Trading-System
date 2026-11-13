# Survival runtime correctness smoke — 2026-11-10

## Purpose and boundary

This run checked that the configured survival policy path can build its
observation and action contracts, perform a bounded PPO update, save and reload
a checkpoint, replay through the evaluator, respect setup masks, and emit the
terminal survival reward. It used synthetic bars only. It is implementation
correctness evidence, not an economic result, and it grants no model-selection
or scientific-training authorization.

## Source and inputs

- Source commit: `11aebfca7a694430be1bc149112f272e4ee108ba` on local `main`.
- Config: `config/research/survival_trade_setup_mtf_conditioned.yaml`.
- Config SHA-256: `e713886878c97ac95aee1e59ac7edc5b3849d490ff6bf419713142e8c2d685d8`.
- Synthetic fixture: 240 bars across two 2025 sessions, with bar-local
  structure placeholders, a quote at every bar timestamp, inactive phase
  flags, and no real market outcomes.
- Frozen bundle source was clean and pinned to the same commit. It explicitly
  recorded `scientific_training_authorized: false` and `selection_allowed: false`.

## Results

- PPO completed 256 synthetic steps with finite policy-gradient loss.
- Observation space was accepted; action width was 6 and the setup mask had
  109 entries, including the always-eligible `NO_TRADE` choice.
- Checkpoint save/reload produced exact deterministic CPU action parity.
- The evaluator completed the synthetic split in 60 steps with finite equity.
- All 60 selected setup actions were legal under their masks; `NO_TRADE` was
  available at every decision.
- A breach-free completed synthetic split emitted terminal reward `+1`.
- Runtime profile: 30.65 seconds elapsed, maximum resident set size 3,228,824
  KiB, and no swapping. This is host resident memory; GPU memory was not
  measured.
- Full-tree static gates passed: Ruff format check, Ruff lint, and Mypy.
- Focused tests passed: 7 tests across the smoke contract and frozen-bundle
  authorization suites.

## Promotion decision

The smoke passed, but canonical training and selection remain blocked. The
only inspected readiness manifest is pinned to older source
`332ba0f17b4efc6f7b5908f09b6ca2be739d2e63` and sets
`scientific_training_authorized: false`. Required readiness gates must be
renewed and reviewed against current source before any scientific training.
The smoke does not satisfy those gates.

## Naming and responsibility

The runtime entry point is named for its purpose,
`run_survival_correctness_smoke`. Its fixture and assertions exercise the
configured runtime rather than bypassing tick execution, strategy features,
or evaluator action-shape handling. Production source review found two legacy
versioned wire identifiers in runtime packages: `account-state-v3-repeated-payout`
is accepted by the checkpoint observation-schema compatibility branch, and
`trade-setup-event-identity-v3` is embedded in persisted event identities.
Both remain stable for checkpoint/event compatibility. The scan found no other
version-tagged identifiers in the runtime packages inspected. Plan labels do
not define runtime behavior.

## Reproducibility artifacts

The full bundle, execution manifest, summary, logs, checkpoint, and hash-pinned
promotion review are stored under
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/` on the
Triton filesystem. Their principal hashes are:

- Frozen bundle: `aafa01fe8c512287409a5f3400fd2f4b3ee6e691968e7c4aeafc9265303cf3a9`
- Execution manifest: `9f122668627a04a3185d4d65640e41e1a6775778208d0f89fadaeacb649b4e5a`
- Smoke summary: `6400a6621114ce7810a8a624caa975c68b8ca0896dd79a9b0181c9b03e265322`
- Promotion review: `bca9416af872cc5da6453c538c7b85ae9ae0c1c08a6f8edf68c043fcf95684f3`
