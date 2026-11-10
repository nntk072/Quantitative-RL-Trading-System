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


def test_frozen_executor_resumes_incomplete_bundle_without_repeating_passed_work(
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
                "estimated_seconds": 10,
            }
        ],
    }
    run_root = tmp_path / "resumable"
    partial = execute_bundle(
        bundle,
        run_root=run_root,
        max_workers=1,
        allow_experiments=False,
        max_runtime_seconds=0,
    )
    assert partial["status"] == "incomplete"

    resumed = execute_bundle(
        bundle,
        run_root=run_root,
        max_workers=1,
        allow_experiments=False,
        resume=True,
    )
    assert resumed["status"] == "pass"
    assert resumed["commands"][0]["status"] == "pass"


def test_frozen_executor_resumes_with_immutable_fold_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "scripts.research.audits.execute_v3_frozen_commands._git_state",
        lambda: ("a" * 40, True),
    )
    seed_artifact = tmp_path / "seed" / "run_manifest.json"
    aggregate = tmp_path / "seed" / "walk_forward.json"
    fold0 = tmp_path / "seed" / "walk_forward_folds" / "fold_0.json"
    fold1 = tmp_path / "seed" / "walk_forward_folds" / "fold_1.json"
    seed_script = (
        "from pathlib import Path; p=Path("
        + repr(str(seed_artifact))
        + "); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('seed')"
    )
    fold0_script = (
        "from pathlib import Path; r=Path("
        + repr(str(fold0))
        + "); a=Path("
        + repr(str(aggregate))
        + "); r.parent.mkdir(parents=True, exist_ok=True); r.write_text('fold0'); a.write_text('fold0')"
    )
    fold1_script = (
        "from pathlib import Path; r=Path("
        + repr(str(fold1))
        + "); a=Path("
        + repr(str(aggregate))
        + "); r.parent.mkdir(parents=True, exist_ok=True); r.write_text('fold1'); a.write_text('fold0,fold1')"
    )
    bundle = {
        "schema_version": "v3-frozen-command-bundle-v1",
        "source_commit": "a" * 40,
        "phase": "verification",
        "commands": [
            {
                "id": "seed",
                "argv": [sys.executable, "-c", seed_script],
                "depends_on": [],
                "artifact_roots": [str(seed_artifact)],
                "experiment": False,
            },
            {
                "id": "fold0",
                "argv": [sys.executable, "-c", fold0_script],
                "depends_on": ["seed"],
                "artifact_roots": [str(fold0)],
                "experiment": False,
            },
            {
                "id": "fold1",
                "argv": [sys.executable, "-c", fold1_script],
                "depends_on": ["fold0"],
                "artifact_roots": [str(fold1)],
                "experiment": False,
            },
        ],
    }

    initial = execute_bundle(
        bundle, run_root=tmp_path / "run", max_workers=1, allow_experiments=False
    )
    resumed = execute_bundle(
        bundle, run_root=tmp_path / "run", max_workers=1, allow_experiments=False, resume=True
    )

    assert initial["status"] == "pass"
    assert resumed["status"] == "pass"
    assert aggregate.read_text(encoding="utf-8") == "fold0,fold1"
