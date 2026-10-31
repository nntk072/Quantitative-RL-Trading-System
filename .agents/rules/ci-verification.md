# CI verification gate

Applies to **all agents** (Cursor, Orchestra, Cline, Windsurf, Kilo, Vibe, etc.).

Two layers:

| Layer | Who | Commands |
|-------|-----|----------|
| **Agent commit/push gate** | Any coding agent before `git commit` / `git push` | format + lint + mypy (full tree) + **scoped** pytest |
| **Merge CI bar** | GitHub Actions named gates; Orchestra phase 9 | twelve named `./tools/check` gates plus `ci-success`; Orchestra runs `./tools/check full` |

Agents must **not** run `pytest tests/ -v` by default — it is too heavy. Prefer the
smallest relevant test set for the change.

## Architecture-aware tool invocation

Use tools built for the compute node. On ARM64/GH200, run Ruff, Mypy, and pytest
directly from the active `.venv/bin` executables (`.venv/bin/ruff`,
`.venv/bin/mypy`, and `.venv/bin/pytest`). Do not invoke these checks through
`uv run` on ARM, even if a `uv` executable is available. On x86_64, use the
`.venv-x86/bin` executables. The Triton login host may expose an x86-64 `uv`
which fails with `Exec format error` on an ARM node. Verify `uname -m` and the
tool binary before starting a gate. An architecture mismatch is an invocation
failure, not a lint, type, or test result.

Lock/export/sync operations still require `uv`. On ARM, `tools/check` prefers
`QRL_UV` or a `uv` executable inside the selected project environment; do not
let it fall through to an x86 login-home binary. For a standalone native
binary, pass it explicitly, for example:

```bash
QRL_UV=/path/to/aarch64/uv ./tools/check deps
```

The venv setup helpers, `tools/uv-install`, and `make deps-check` honor the same
`QRL_UV` override. `THESIS_UV` remains a deprecated fallback for existing
setups. `tools/check build` uses the selected project Python's
`build` module when a matched environment is active.

## Hard rule — agent commit / push

**Do not** `git commit` or `git push` until this gate passes. If any step fails,
fix and re-run; do not skip with `--no-verify` unless the user explicitly requests it.

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy .
.venv/bin/pytest <relevant test paths> -q
```

**Full tree is mandatory for format / lint / types.** At commit/push you MUST run
exactly `ruff format --check .`, `ruff check .`, and `mypy .` (the trailing `.`
means the whole project). These are **not** optional and **must not** be replaced by
path-scoped commands.

| Forbidden at commit/push | Required instead |
|--------------------------|------------------|
| `mypy <touched files>` | `.venv/bin/mypy .` on ARM; matching full-tree Mypy on other architectures |
| `ruff check <touched paths>` only | `.venv/bin/ruff check .` on ARM; matching full-tree Ruff on other architectures |
| `ruff format --check <touched paths>` only | `.venv/bin/ruff format --check .` on ARM; matching full-tree Ruff on other architectures |

Scoped ruff/mypy is allowed **only while editing** (see Local work below). A scoped
pass earlier in the chat does **not** satisfy the commit gate — re-run the full-tree
commands on the final tree, including new/edited `tests/` files (CI typechecks them).

Only **pytest** stays scoped at commit time.

### Choosing relevant tests

- Prefer tests that cover the modules you touched (same package / mirror path under
  `tests/`, plus any smoke tests you added).
- Use graph/`tests_for` when available; otherwise grep or path convention
  (for example, `<feature_module>.py` → `tests/**/test_*<feature>*`).
- Cap to a small set (typically 1–few files). Do **not** expand to the whole tree
  “to be safe.”
- Run `./tools/check full` only when the user explicitly asks, or when you are
  the Orchestra verification phase / reproducing a complete CI failure. Use the
  named `./tools/check <gate>` command to reproduce one hosted gate.

### Format failures (common CI red)

If `ruff format --check .` reports files that would be reformatted:

1. Run the architecture-matched formatter, such as `.venv/bin/ruff format .` on ARM (or only the listed paths).
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
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy .
```

## Local work (implementation)

While editing, prefer scoped checks only — do **not** run full-tree ruff/mypy after
every edit:

```bash
.venv/bin/ruff format --check <touched paths>
.venv/bin/ruff check <touched paths>
.venv/bin/pytest <relevant test files> -q
```

When you are about to commit or push, stop using this section and switch to the
**Hard rule** full-tree gate (`mypy .`, not path-scoped mypy).

## Merge CI bar (not the agent default)

GitHub Actions runs twelve named gates and a required-job aggregator. Orchestra
uses the same dispatcher sequentially:

```bash
./tools/check full
```

## Out of scope unless explicitly requested

- Nightly workflow subsets (`pytest -m slow`, integration-only paths)
- Agents substituting scoped pytest for a named hosted gate when debugging CI

## Test discipline

- Mock methods with `monkeypatch.setattr`, not `instance.method = ...` (mypy
  `method-assign`).
- Orchestra router/health tests on CI: use `stub_clis` fixture
  (`tests/unit/orchestra/conftest.py`).

## Relations

- Pre-commit checklist: [git-commit-rules.md](git-commit-rules.md)
- Feature workflow: [development-workflow.md](development-workflow.md)
- Agent index: [README.md](README.md)
- Full gate: `.github/workflows/ci.yml`, `tools/check`, and Orchestra's adapter
