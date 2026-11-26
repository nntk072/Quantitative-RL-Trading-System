"""Fast pre-push checks for files changed against a base branch.

Run as ``./tools/check_fast`` or ``python -m tools.check_fast [--base REF]``.
The interpreter comes from ``QRL_PYTHON``. Mypy is local-only (not in CI yet).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from tools.quality.module_size import PRODUCT_PACKAGES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = "/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv-x86/bin/python"
DEFAULT_BASE = "origin/main-native"
PROFILE_DIR = Path("config/studies/profiles")
# Same marker expression as the `tools/check unit` gate.
UNIT_MARKERS = "unit and not slow and not integration and not architecture and not gpu and not triton and not research"
FAILURE_LINE = re.compile(r"^(FAILED|ERROR)\b|: error:|Would reformat|Traceback|^E |not registered")
NO_PY = "no changed Python files"


@dataclass(frozen=True)
class Result:
    name: str
    command: str
    code: int
    passed: bool
    output: str = ""
    skipped: bool = False

    def first_line(self) -> str:
        """Return the first failing output line, or an empty string when passed."""
        lines = [line.strip() for line in self.output.splitlines() if line.strip()]
        if self.passed:
            return ""
        match = next((line for line in lines if FAILURE_LINE.search(line)), None)
        return (match or (lines[0] if lines else f"exit {self.code}, no output"))[:120]


def skip(name: str, reason: str) -> Result:
    """Build a skipped result that runs nothing."""
    return Result(name, reason, 0, True, skipped=True)


def run(name: str, args: list[str], ok_codes: tuple[int, ...] = (0,)) -> Result:
    """Run args (args[0] is the interpreter) from the repository root."""
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
    shown = " ".join(["$QRL_PYTHON", *args[1:]])
    output = proc.stdout + proc.stderr
    return Result(name, shown, proc.returncode, proc.returncode in ok_codes, output)


def git(*args: str) -> list[str]:
    """Return the non-empty stdout lines of a git command run in the repository."""
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def changed_files(base: str) -> list[str]:
    """Files differing from base (committed and uncommitted) plus untracked files."""
    tracked = git("diff", "--name-only", "--diff-filter=ACMR", base)
    return sorted(set(tracked) | set(git("ls-files", "--others", "--exclude-standard")))


def unit_tests_for(root: Path, changed: list[str]) -> list[str]:
    """Changed unit test files plus unit tests whose text imports a changed module."""
    found = (root / "tests/unit").rglob("test_*.py")
    texts = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in found}
    selected = {path for path in changed if path in texts}
    for path in changed:
        if not path.endswith(".py") or path.startswith("tests/"):
            continue
        parts = path[: -len(".py")].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        dotted = ".".join(parts)
        parent, _, leaf = dotted.rpartition(".")
        patterns = [re.compile(rf"\b{re.escape(dotted)}\b")]
        if parent:
            from_form = rf"from\s+{re.escape(parent)}\s+import\b[^\n]*\b{re.escape(leaf)}\b"
            patterns.append(re.compile(from_form))
        selected |= {t for t, text in texts.items() if any(p.search(text) for p in patterns)}
    return sorted(selected)


def registration_failures(root: Path, changed: list[str]) -> list[str]:
    """Each changed product-package module must be listed in its package profile."""
    failures: list[str] = []
    for path in changed:
        package = path.split("/", 1)[0]
        if not path.endswith(".py") or path.startswith("tests/") or package not in PRODUCT_PACKAGES:
            continue
        rel = (PROFILE_DIR / f"{package}.yaml").as_posix()
        if not (root / rel).exists():
            failures.append(f"{path} not registered: no profile; create {rel} with '- {path}'")
            continue
        profile = yaml.safe_load((root / rel).read_text(encoding="utf-8")) or {}
        scopes = [
            s.get("path", "") for s in profile.get("source_scopes") or [] if isinstance(s, dict)
        ]
        if path in (profile.get("api_paths") or []):
            continue
        if any(path == s or path.startswith(s.rstrip("/") + "/") for s in scopes):
            continue
        failures.append(f"{path} not registered: add '- {path}' under api_paths in {rel}")
    return failures


def build_results(python: str, changed: list[str]) -> list[Result]:
    """Run the ordered checks and return one result per check."""
    py_files = [p for p in changed if p.endswith(".py") and (ROOT / p).exists()]
    results: list[Result] = []
    if py_files:
        fmt = [python, "-m", "ruff", "format", "--check", *py_files]
        results += [
            run("ruff format", fmt),
            run("ruff check", [python, "-m", "ruff", "check", *py_files]),
        ]
    else:
        results += [skip("ruff format", NO_PY), skip("ruff check", NO_PY)]
    tests = unit_tests_for(ROOT, changed)
    name = "unit tests (changed + importers)"
    if tests:
        # Exit 5 means the marker filter deselected every selected test.
        pytest_args = [python, "-m", "pytest", "-q", "-m", UNIT_MARKERS, *tests]
        results.append(run(name, pytest_args, ok_codes=(0, 5)))
    else:
        results.append(skip(name, "no matching unit tests"))
    for module in ("public_api", "api_usage", "inventory"):
        results.append(
            run(f"docs {module}", [python, "-m", f"tools.documentation.{module}", "--check"])
        )
    contracts = "tests/architecture/test_documentation_contracts.py"
    results.append(run("docs contracts", [python, "-m", "pytest", "-q", contracts]))
    failures = registration_failures(ROOT, changed)
    ok = not failures
    results.append(
        Result("module registration", "profile check", int(not ok), ok, "\n".join(failures))
    )
    if py_files:
        results.append(run("mypy (local-only, not in CI)", [python, "-m", "mypy", *py_files]))
    else:
        results.append(skip("mypy (local-only, not in CI)", NO_PY))
    return results


def render(results: list[Result]) -> str:
    """Format the summary table with check, command, exit, result, and first failure."""
    rows = [("check", "command", "exit", "result", "first failing line")]
    for r in results:
        status = "SKIP" if r.skipped else ("PASS" if r.passed else "FAIL")
        command = r.command if len(r.command) <= 70 else r.command[:67] + "..."
        code = "-" if r.skipped else str(r.code)
        rows.append((r.name, command, code, status, r.first_line()))
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    return "\n".join(
        "  ".join(f"{c:<{w}}" for c, w in zip(row[:4], widths, strict=True)) + f"  {row[4]}"
        for row in rows
    )


def main(argv: list[str] | None = None) -> int:
    """Run the fast checks against the base ref and return 1 if any failed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"base ref (default {DEFAULT_BASE})")
    args = parser.parse_args(argv)
    python = os.environ.get("QRL_PYTHON", DEFAULT_PYTHON)
    if not os.access(python, os.X_OK):
        print(f"QRL_PYTHON is not executable: {python}", file=sys.stderr)
        return 2
    try:
        git("rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}")
    except subprocess.CalledProcessError:
        print(f"base ref not found: {args.base} (run git fetch origin)", file=sys.stderr)
        return 2
    changed = changed_files(args.base)
    print(f"base={args.base} changed={len(changed)} python={python}")
    results = build_results(python, changed)
    print(render(results))
    for r in results:
        if not r.passed and r.output:
            tail = r.output.strip().splitlines()[-40:]
            print(f"\n--- {r.name} output (last {len(tail)} lines)\n" + "\n".join(tail))
    failed = [r.name for r in results if not r.passed]
    print("\n" + (f"FAILED: {', '.join(failed)}" if failed else "all checks passed"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
