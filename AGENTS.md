# Quantitative RL Trading System

Research and broker-neutral software for intraday US100/US500 trading. PPO/SAC
agents use causal market structure and execute through explicit risk and ledger
contracts.

## Research and evidence

Use [`docs/research/README.md`](docs/research/README.md) for research methods,
validity limits, and current evidence status. Record each study's frozen design
with its run artifacts and registered configuration. Keep transient task plans,
agent handoffs, and logs in the ignored
`logs/agents/<canonical_role_id>/<date>_<task>/` tree.

Every research claim must trace to current source, config, data, run identity,
and immutable artifacts. Preserve provenance and invalid, negative, breached,
no-trade, and incomplete outcomes. Never select on the exposed 2026 reporting
interval or describe a smoke/pilot as scientific evidence.

## Non-negotiable invariants

- **Causality:** no future inputs. Higher-timeframe values become available
  only after close and use forward alignment, never backward fill.
- **Train-only fitting:** normalization and fitted feature state use training
  rows only; later rows use the last available training state.
- **Chronology:** `purged_walk_forward()` has non-overlapping test folds,
  purge includes label horizon, and embargo precedes each test fold.
- **Session semantics:** session is an eligibility mask; never remove bars
  from the feature dataset to enforce session eligibility.
- **Configuration:** `config/base/default.yaml` is the single source of truth;
  add a YAML key before reading a new setting.
- **Cache identity:** cache identity includes the feature version and content
  hash; a manual version bump alone is insufficient.
- **Risk parity:** live risk overrides remain aligned with the configured
  training/account dollar limits. Never weaken a hard floor or breach latch.
- **Locked OOS:** do not select models, checkpoints, or thresholds on the
  locked report period; see [`validation_protocol.md`](docs/research/validation_protocol.md).

## Architecture

```text
configuration → market_data → features → simulation
                                 ↓          ↑
decisioning → models → learning → training → evaluation → artifacts
                            ↑         experiments       ↑
                          compute                      reports
live → integrations/mt5
```

Use [`.agents/architecture.md`](.agents/architecture.md) for package direction
and [`.agents/domain_maps/`](.agents/domain_maps/) for task-specific ownership.
Verify implementation behavior in source and tests; indexes and plans are
navigation aids, not authoritative behavior.

## Universal safety

- Preserve unrelated dirty work, active jobs, checkpoints, logs, and evidence.
- Inspect current source and callers before changing behavior. Do not infer
  absence from an empty or truncated index result.
- Do not fabricate verification or claim a gate passed unless it ran.
- Do not perform destructive filesystem, Git history, external-service, or
  publication actions without user authorization.
- Do not commit or push without explicit user authorization. Stage only owned
  task files and follow the repository commit rules.

## Conditional rules

| Work | Read |
|---|---|
| General implementation | [core-execution.md](.agents/rules/core-execution.md) |
| Delegation or parallel work | [delegation.md](.agents/rules/delegation.md), then [reasoning-effort.md](.agents/rules/reasoning-effort.md) |
| Retrieval and optional tools | [extension-routing.md](.agents/rules/extension-routing.md), [extensions.md](.agents/extensions.md) |
| Shared context and handoffs | [context-management.md](.agents/rules/context-management.md) |
| Tests, static checks, review | [validation-routing.md](.agents/rules/validation-routing.md), [testing-rules.md](.agents/rules/testing-rules.md) |
| Python changes | [python-coding-standards.md](.agents/rules/python-coding-standards.md) |
| Security-sensitive work | [security-rules.md](.agents/rules/security-rules.md) |
| Research and evidence | [research-integrity.md](.agents/rules/research-integrity.md) |
| Commit or push | [ci-verification.md](.agents/rules/ci-verification.md), [git-commit-rules.md](.agents/rules/git-commit-rules.md) |
| Triton, CPU/GPU allocations, or long polling | [triton-slurm.md](.agents/rules/triton-slurm.md) |

The canonical specialist roster and ownership live in
[`.agents/rules/delegation.md`](.agents/rules/delegation.md). Codex, Claude
Code, and Antigravity files are platform adapters; they do not redefine role
ownership. Project-local tool setup is documented in
[`.agents/rules/agent-tools.md`](.agents/rules/agent-tools.md).

## Compute and Git

For Triton, use the canonical scratch checkout and follow `triton-slurm.md`:
reuse allocations first, inspect live CPU/RAM/GPU inventory before a new
request, avoid short job/step fan-out, and never run `scancel`. Do not perform
training or other heavy data/compute work on the normal login host.

Before an authorized commit, run full-tree Ruff format, Ruff lint, full-tree
Mypy, and relevant scoped pytest as required by `ci-verification.md`. The full
merge gate is not an agent default; use it only when requested or required by
the active workflow.
