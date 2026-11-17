from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from research_tools.studies.handlers.simulation import run_parity_checks


def test_parity_audit_runs_declared_test_paths_as_one_argument_vector(
    tmp_path: Path, monkeypatch: Any
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="3 passed", stderr="")

    monkeypatch.setattr("research_tools.studies.handlers.simulation.subprocess.run", fake_run)
    study = {"checks": ["tests/b.py", "tests/a.py", "tests/a.py"]}

    report = run_parity_checks(tmp_path, study, tmp_path)

    command, kwargs = calls[0]
    assert command[-2:] == ["tests/a.py", "tests/b.py"]
    assert kwargs["shell"] is False
    assert kwargs["cwd"] == tmp_path
    assert report["diagnostic_status"] == "passed"
    assert report["checks"] == ["tests/a.py", "tests/b.py"]
    assert (tmp_path / "pytest.stdout.txt").read_text(encoding="utf-8") == "3 passed"
