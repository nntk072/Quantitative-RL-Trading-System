# Baseline defect catalog (BASELINE-AUDIT)

Baseline: `6755417e` (remote `main`). Severity: high = wrong result or unsafe; medium = blocks a check or a workflow; low = hygiene.

| ID | Severity | Finding | Reproducer | Status |
|---|---|---|---|---|
| D1 | medium | The documentation inventory test fails when any Markdown file appears under `docs/` that is not in the checked-in inventory. The inventory scans every file under `docs/` (`tools/documentation/inventory.py:40`). | Add any `.md` file under `docs/`, run `pytest tests/unit/tooling/test_documentation_inventory.py`. | Caused by this workstream's `docs/plan/` files. Fixed by moving the plan to `planning/native_modernization/`. The 7 tests pass. |
| D2 | low | The local `main` ref is stale (`0dc90703`) while the remote `main` is `6755417e`. | `git rev-parse main` vs `git ls-remote origin refs/heads/main`. | Repository hygiene. Not a code defect. Target is the remote SHA. |
| D3 | medium | Local coverage runs segfault when torch is imported under coverage tracers on this node. Torch-using modules cannot be measured locally. | Recorded in earlier sessions; not re-run in this pass. | Open. Coverage must come from CI or a compute node. |
| D4 | low | The `mypy` launcher on PATH points to a stale path. | Run `mypy` directly. | Workaround: `.venv-x86/bin/python -m mypy`. |
| D5 | low | 18 product modules exceed 1000 lines (`baseline_inventory.json`, `python_files_over_1000_lines`). | Count lines. | Refactor scope (plan section 0.2 and 3). |
| D6 | low | `orchestra/` is still in the baseline tree, with a per-file ruff ignore for B and SIM. | `pyproject.toml` per-file ignores. | Out of scope for this plan. Recorded. |

No semantic defect (causality, fit scope, session mask, risk floor, fill ordering) was found by the checks run in this pass. This pass does not prove the absence of such defects. Those checks belong to SEMANTIC-ORACLE and the mutation tests, which are still open.
