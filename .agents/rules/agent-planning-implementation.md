# Agent planning and implementation workflow

These rules apply to every coding agent and model working in this repository.
Use one consistent process so results do not depend on which agent receives the task.

## Before changing files

1. Read the repository `AGENTS.md`, the relevant domain map, and the rule for the task.
2. Inspect the current branch, worktree changes, active experiment runs, and the actual files involved. Treat attachments and copied plans as context; the user's current request determines the authorized work.
3. Trace the existing implementation and its callers before proposing a new module or parallel workflow. Reuse the current configuration, artifact, checkpoint, and reporting paths when they fit.
4. For a substantial task, write a short plan outside the repository under
   `/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/`.
   Do not add agent implementation plans, working notes, or handoff plans to
   the repository. The operational thesis queue remains
   `docs/thesis/master_project_execution_plan.md`.
5. Name files and user-facing choices for their function. Avoid opaque
   letter-number codes, work-package numbers, generic stage numbers, and words
   such as “new” or “final” when they stand alone. Use abbreviations only when
   they are standard in the domain and explained at first use. Keep legacy
   identifiers only when a concrete compatibility or evidence-lineage need
   requires them; give them a clear display name and document the mapping.
6. Proceed with clear, reversible work without asking for repeated approval.
   Ask only when required information is missing or a repository, resource, or
   external-action rule requires approval. Continue independent work while
   approval is pending.

## While implementing

- Make the smallest complete change that satisfies the request. Do not add a
  second registry, duplicate configuration, generic wrapper, or speculative
  infrastructure when the existing design can be extended.
- Keep each module, test, configuration, report, and artifact name specific to
  the behavior it owns. Consolidate duplicated behavior and tests when their
  contracts are the same; retain separate coverage when the behaviors differ.
- Organize tests by execution scope first: unit tests mirror source packages
  under `tests/unit/<package>/`; integration tests cover cross-package workflows
  under `tests/integration/`; architecture and research-protocol checks stay in
  their dedicated suites. For a module that mixes scopes around a shared
  workflow, mark the individual cases explicitly and split the file only when
  the split improves selection without duplicating fixtures. Do not add a
  second `tests/test_<package>/` layout.
- Preserve user changes, experiment fingerprints, running workers, allocations,
  checkpoints, and result evidence. Follow `.agents/rules/triton-slurm.md` for
  all compute and scheduler actions.
- Keep comments focused on non-obvious behavior, invariants, and rationale.
  Remove stale comments when the code changes; do not narrate obvious syntax.
- Do not change historical result records to improve presentation. Label
  measured results, exploratory results, and unverified claims distinctly.

## Verification and handoff

- Run focused checks for the changed behavior. Do not run the full test suite
  unless the user or repository gate requires it.
- Before commit or push, follow `.agents/rules/ci-verification.md` and
  `.agents/rules/git-commit-rules.md` exactly.
- Review the final diff for accidental data, output, cache, checkpoint, or
  plan-file changes. Confirm generated files are reproducible where applicable.
- Report what changed, why, exact checks and outcomes, remaining limitations,
  and the relevant repository paths. Do not claim a gate passed unless it ran.
- When work is blocked on a resource or approval, preserve the current state,
  give the concrete estimate and requirement, and continue independent work
  without duplicating the blocked task.
