import sys
from pathlib import Path

import pytest
from scripts.research.audits.execute_v3_frozen_commands import execute_bundle


def test_frozen_executor_requires_explicit_experiment_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "scripts.research.audits.execute_v3_frozen_commands._git_state",
        lambda: ("a" * 40, True),
    )
    bundle = {
        "schema_version": "v3-frozen-command-bundle-v1",
        "source_commit": "a" * 40,
        "phase": "survival",
        "commands": [
            {
                "id": "experiment",
                "argv": [sys.executable, "-c", "print('ok')"],
                "depends_on": [],
                "artifact_roots": [],
                "experiment": True,
            }
        ],
    }
    with pytest.raises(ValueError, match="allow-experiments"):
        execute_bundle(bundle, run_root=tmp_path / "run", max_workers=1, allow_experiments=False)


def test_frozen_executor_runs_direct_nonexperiment_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "scripts.research.audits.execute_v3_frozen_commands._git_state",
        lambda: ("a" * 40, True),
    )
    bundle = {
        "schema_version": "v3-frozen-command-bundle-v1",
        "source_commit": "a" * 40,
        "phase": "verification",
        "commands": [
            {
                "id": "check",
                "argv": [sys.executable, "-c", "print('ok')"],
                "depends_on": [],
                "artifact_roots": [],
                "experiment": False,
            }
        ],
    }
    result = execute_bundle(
        bundle, run_root=tmp_path / "run", max_workers=1, allow_experiments=False
    )
    assert result["status"] == "pass"
