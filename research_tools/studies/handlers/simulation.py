"""Run the exact integration checks registered for simulator parity."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def run_parity_checks(root: Path, study: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    """Execute declared simulator parity pytest paths as one bounded process."""
    checks = study.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(not isinstance(path, str) for path in checks)
    ):
        raise ValueError("simulator parity study requires registered pytest paths")
    command = [sys.executable, "-m", "pytest", "-q", *sorted(set(checks))]
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    (output_dir / "pytest.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "pytest.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    return {
        "diagnostic_status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "checks": sorted(set(checks)),
        "stdout_path": "pytest.stdout.txt",
        "stderr_path": "pytest.stderr.txt",
    }
