# Orchestra — Multi-Model Coding Pipeline

Orchestra coordinates multiple CLI-based coding agents through a structured
workflow: triage → plan → implement → verify. Implementers run scoped tests only.
Phase 9 delegates to the canonical `./tools/check full` dispatcher. GitHub
Actions invokes the same named gates independently and aggregates their status.

## Quick start

```bash
# Tier-0 health check (no inference)
orchestra doctor

# Full pipeline on a task
orchestra run "add unit tests for purged_walk_forward"

# Dry run (show plan without spawning agents)
orchestra run "refactor risk module" --dry-run
```

## Pipeline phases

| Phase | Purpose |
|-------|---------|
| 1. Triage | Classify task complexity and tier |
| 2. Planning | Parallel planners produce implementation plans |
| 3. Critique | Critics review plans |
| 4. Synthesis | Merge plans into a single plan |
| 5. Implementation | Implementer applies changes |
| 6. Review | Reviewers check the diff |
| 7. Review synthesis | Merge review feedback |
| 8. Fixing | Address review findings (up to `max_fixes`) |
| 9. Verification | Run CI gate (`CI_CHECKS`) |

Runtime state, logs, backups, and reports are persisted under
`outputs/orchestra/state/` per task. This keeps generated state out of the
source package.

## CI verification gate

The Orchestra adapter in `orchestra/ci_gate.py` has one responsibility: invoke
the shared full dispatcher. The names and commands for hosted and local checks
are defined in `tools/check` and `.github/workflows/ci.yml`:

```bash
./tools/check full
```

Orchestra phase 9 runs the full dispatcher. Implementers use scoped checks;
agent commit checks use full-tree Ruff and Mypy with scoped pytest. Nightly
workflows are not part of the normal merge bar.

## Package layout

```
orchestra/
  cli.py                     CLI entry point (orchestra doctor / run)
  task_orchestration.py      Pipeline phase execution
  task_state_store.py        Persisted task and phase state
  model_provider_registry.py Model/provider contracts
  ci_gate.py                 Adapter to ./tools/check full
  router.py                  Model selection and routing
  health.py                  Tier-0/Tier-1 health probes
  agent_runner.py            Spawn and capture agent CLI sessions
  prompts/                   Phase prompt templates
  docs/
    probe-matrix.md  CLI probe evidence and tier gates
```

## Configuration

- Model definitions: `orchestra/models.yaml`
- Probe matrix and tier gates: [docs/probe-matrix.md](docs/probe-matrix.md)
- Agent rules: `.agents/rules/ci-verification.md`

## References

- [AGENTS.md](../AGENTS.md) — agent guide (orchestra section)
- [docs/operations/RUNNING_COMMANDS.md](../docs/operations/RUNNING_COMMANDS.md) — orchestra commands
- [docs/architecture.md](../docs/architecture.md) — repository architecture
