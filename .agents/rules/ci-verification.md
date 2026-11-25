---
trigger: model_decision
description: "Use when selecting local checks, preparing a commit, diagnosing hosted CI, or validating repository changes."
---

# CI verification gate

Applies to all coding agents.

Two layers:

| Layer | Who | Commands |
|-------|-----|----------|
| **Agent commit/push gate** | Any coding agent before `git commit` / `git push` | format + lint + mypy (full tree) + **scoped** pytest |
| **Merge CI bar** | GitHub Actions named gates | twelve named `./tools/check` gates plus `ci-success` |

Agents must **not** run `pytest tests/ -v` by default — it is too heavy. Prefer the
smallest relevant test set for the change.

## Architecture-aware tool invocation

Use tools built for the compute node. On ARM64/GH200, run Ruff, Mypy, and pytest
directly from `.venv-arm/bin` (`.venv-arm/bin/ruff`, `.venv-arm/bin/mypy`, and
`.venv-arm/bin/pytest`). Do not invoke these checks through
`uv run` on ARM, even if a `uv` executable is available. On x86_64, use the
`.venv-x86/bin` executables. The Triton login host may expose an x86-64 `uv`
which fails with `Exec format error` on an ARM node. Verify `uname -m` and the
tool binary before starting a gate. An architecture mismatch is an invocation
failure, not a lint, type, or test result.

When a console launcher reports `bad interpreter`, inspect its shebang before
retrying. If the active environment's Python works but a relocated wrapper has
a stale absolute path, invoke the tool as a module with that same interpreter
(for example, `.venv-x86/bin/python -m pytest <paths> -q`). Record this as an
environment invocation issue, not a project test failure. Do not repair or
replace a shared virtual environment as part of an unrelated source change.

Lock/export/sync operations still require `uv`. On ARM, `tools/check` prefers
`QRL_UV` or a `uv` executable inside the selected project environment; do not
let it fall through to an x86 login-home binary. For a standalone native
binary, pass it explicitly, for example:

```bash
QRL_UV=/path/to/aarch64/uv ./tools/check deps
```

The venv setup helpers, `tools/uv-install`, and `make deps-check` honor the same
`QRL_UV` override. `tools/check build` uses the selected project Python's
`build` module when a matched environment is active.

## Hard rule — agent commit / push

**Do not** `git commit` or `git push` until this gate passes. If any step fails,
fix and re-run; do not skip with `--no-verify` unless the user explicitly requests it.

```bash
.venv-arm/bin/ruff format --check .
.venv-arm/bin/ruff check .
.venv-arm/bin/mypy .
.venv-arm/bin/pytest <relevant test paths> -q
```

**Full tree is mandatory for format / lint / types.** At commit/push you MUST run
exactly `ruff format --check .`, `ruff check .`, and `mypy .` (the trailing `.`
means the whole project). These are **not** optional and **must not** be replaced by
path-scoped commands.

| Forbidden at commit/push | Required instead |
|--------------------------|------------------|
| `mypy <touched files>` | `.venv-arm/bin/mypy .` on ARM; matching full-tree Mypy on other architectures |
| `ruff check <touched paths>` only | `.venv-arm/bin/ruff check .` on ARM; matching full-tree Ruff on other architectures |
| `ruff format --check <touched paths>` only | `.venv-arm/bin/ruff format --check .` on ARM; matching full-tree Ruff on other architectures |

Scoped ruff/mypy is allowed **only while editing** (see Local work below). A scoped
pass earlier in the chat does **not** satisfy the commit gate — re-run the full-tree
commands on the final tree, including new/edited `tests/` files (CI typechecks them).

Only **pytest** stays scoped at commit time.

### Start CI impact review before implementation

When the CI Operation Engineer is assigned to a change or asked to advise,
start the impact review before implementation begins. First inspect the base
SHA, planned/changed paths, workflow triggers and conditions, runner/toolchain,
and exact job commands. Give the owner a short path → hosted job → local command
map before they edit; include generated outputs, architecture contracts,
focused tests, and any hosted check that has no equivalent local command. The
owner acknowledges the affected contracts and tests in the task handoff. Do
not describe a check as covered merely because a nearby test or broad lint ran.

Refresh the map whenever implementation adds paths or changes interfaces,
dependencies, generated outputs, or test scope. Before commit, compare the
complete final diff with the map and run the mapped local gates on that exact
candidate, plus the mandatory full-tree quality gates. If a hosted job has
environment-specific behavior or no faithful local equivalent, identify that
gap before commit and choose the closest reproducible check; do not defer a
known, reproducible check to hosted CI. Record the final path/job/command/result
matrix in the CI Operation Engineer handoff. The goal is to catch predictable
failures before commit, not to wait for a red hosted run and then repair it.

### Change-impact preflight before push

Before pushing, inspect the complete diff and map each changed contract to its
local gate. Do not rely on hosted CI to discover predictable failures that can
be checked from the changed paths:

- Inspect the applicable workflow definitions, including triggers, path
  filters, job conditions, and exact local gate commands. Map every changed
  path to each affected hosted job; do not infer coverage from a filename or a
  neighboring targeted test alone.
- If a production import or dependency direction changed, run the applicable
  architecture contract tests, including
  `tests/architecture/test_dependency_rules.py::test_domain_fanout_is_limited_to_declared_composition_roots`.
- If production source, API signatures, or documentation links changed, run
  the generated API, usage, and documentation inventory checks:
  `python -m tools.documentation.public_api --check`,
  `python -m tools.documentation.api_usage --check`, and
  `python -m tools.documentation.inventory --check`. Regenerate stale outputs
  with the corresponding `--write` command, then rerun all three checks and
  `./tools/check docs` so the complete generated-output closure and docs gate
  are verified together.
- If a scoped test or generated-artifact check fails, fix it and rerun that
  exact check before commit/push. After a hosted failure, reproduce the failing
  test or named gate locally when possible before replacing the pushed SHA.

Record the changed-path-to-workflow mapping and each selected command/result in
the CI Operation Engineer handoff.
The full-tree format/lint/type gates and relevant scoped pytest remain required
regardless of this change-impact preflight.

### Choosing relevant tests

- Prefer tests that cover the modules you touched (same package / mirror path under
  `tests/`, plus any smoke tests you added).
- Use graph/`tests_for` when available; otherwise grep or path convention
  (for example, `<feature_module>.py` → `tests/**/test_*<feature>*`).
- Cap to a small set (typically 1–few files). Do **not** expand to the whole tree
  “to be safe.”
- Run `./tools/check full` only when the user explicitly asks, or when
  reproducing a complete CI failure. Use the
  named `./tools/check <gate>` command to reproduce one hosted gate.

### Format failures (common CI red)

If `ruff format --check .` reports files that would be reformatted:

1. Run the architecture-matched formatter, such as `.venv-arm/bin/ruff format .` on ARM (or only the listed paths).
2. Re-run the architecture-matched `ruff format --check .` until it exits 0.
3. Include the formatting diff in the commit (do not push unformatted code).

Ruff format handles Python source, not YAML. Do not pass YAML/config files in a
mixed path list to `ruff format`; it can reformat Python files and then fail on
the unsupported file type. Job `21019023` demonstrated the resulting short-job
failure. In a GPU validation script, keep formatting check-only; if correction
is required, run the formatter on `.` or Python-only paths, then rerun the full
tree check.

Never treat “lint already passed earlier in the chat” as a substitute — re-run the
gate on the **final** tree you are about to commit.

### Lint/types only

When the user asks only for format/lint/types before commit:

```bash
.venv-arm/bin/ruff format --check .
.venv-arm/bin/ruff check .
.venv-arm/bin/mypy .
```

## Local work (implementation)

While editing, prefer scoped checks only — do **not** run full-tree ruff/mypy after
every edit:

```bash
.venv-arm/bin/ruff format --check <touched paths>
.venv-arm/bin/ruff check <touched paths>
.venv-arm/bin/pytest <relevant test files> -q
```

When you are about to commit or push, stop using this section and switch to the
**Hard rule** full-tree gate (`mypy .`, not path-scoped mypy).

## Merge CI bar (not the agent default)

GitHub Actions runs twelve named gates and a required-job aggregator. The same
dispatcher can run them sequentially:

```bash
./tools/check full
```

## Out of scope unless explicitly requested

- Nightly workflow subsets (`pytest -m slow`, integration-only paths)
- Agents substituting scoped pytest for a named hosted gate when debugging CI

## Test discipline

- Mock methods with `monkeypatch.setattr`, not `instance.method = ...` (mypy
  `method-assign`).

## Relations

- Pre-commit checklist: [git-commit-rules.md](git-commit-rules.md)
- Feature workflow: [core-execution.md](core-execution.md) and [validation-routing.md](validation-routing.md)
- Agent index: [README.md](README.md)
- Full gate: `.github/workflows/ci.yml` and `tools/check`
