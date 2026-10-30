## Local verification (implementation)

Run from `{{workspace}}`. Cover **only** what you changed:

- `.venv/bin/ruff format --check <touched paths>` on ARM/GH200
- `.venv/bin/ruff check <touched paths>` on ARM/GH200
- `.venv/bin/pytest <relevant test files> -q` on ARM/GH200 (use the matching
  environment on other architectures)

On ARM/GH200 use `.venv/bin/ruff`, `.venv/bin/mypy`, and
`.venv/bin/pytest` directly. Do not run quality checks through an x86 `uv`
binary from the login home.

Do not run the full CI gate during implementation. Do not use `pytest -m "not slow"`
as a substitute when a targeted test file already exists.

## Full CI gate (Orchestra phase 9)

Orchestra delegates to the same full dispatcher as the named GitHub gates:

{{ci_commands}}

Agent commit/push checks are different: full-tree Ruff format, Ruff lint, and
Mypy plus scoped relevant pytest. Implementer and fixer agents must not run the
full dispatcher during implementation. If a hosted gate already failed, rerun
only that named gate.
