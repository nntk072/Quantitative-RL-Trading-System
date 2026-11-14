"""Tests for handoff bundles."""

from __future__ import annotations

import hashlib
import subprocess

from orchestra import handoff
from orchestra.handoff import HandoffBundle, _cap, build_context_manifest, render_handoff_prompt


def test_handoff_caps() -> None:
    assert len(_cap("x" * 100, 50)) < 100
    assert "[truncated]" in _cap("x" * 100, 50)


def test_render_handoff_prompt_minimal() -> None:
    bundle = HandoffBundle(
        task_id="task-1",
        phase="implementation",
        tier="T2",
        goal="fix bug",
        plan_digest="plan here",
        resume_hint="continue step 3",
        source_model="opencode/default",
    )
    text = render_handoff_prompt(bundle)
    assert "continue step 3" in text
    assert "Do not re-plan" in text.lower() or "do not re-plan" in text.lower()
    assert "fix bug" in text


def test_git_diff_helpers_are_empty_when_git_is_unavailable(tmp_path, monkeypatch) -> None:
    def missing_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", missing_git)

    assert handoff.git_diff_stat(tmp_path) == ""
    assert handoff.git_diff_excerpt(tmp_path) == ""


def test_context_manifest_tracks_revision_and_dirty_content(tmp_path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path)
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    subprocess.run(["git", "add", "source.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    source.write_text("value = 2\n")

    manifest = build_context_manifest(tmp_path)

    assert manifest["revision"]
    assert manifest["dirty"] is True
    assert manifest["files"] == [
        {
            "path": "source.py",
            "state": "modified",
            "sha256": hashlib.sha256(b"value = 2\n").hexdigest(),
        }
    ]


def test_old_handoff_without_context_manifest_remains_compatible() -> None:
    bundle = HandoffBundle.from_dict(
        {"task_id": "old", "phase": "implementation", "tier": "T2", "goal": "fix"}
    )
    assert bundle.context_manifest == {}


def test_render_handoff_references_revision_and_changed_file_hash() -> None:
    bundle = HandoffBundle(
        task_id="task-2",
        phase="implementation",
        tier="T2",
        goal="continue",
        context_manifest={
            "revision": "abc123",
            "dirty": True,
            "files": [{"path": "src/module.py", "state": "modified", "sha256": "def456"}],
        },
    )

    prompt = render_handoff_prompt(bundle)

    assert "revision=abc123; dirty=True" in prompt
    assert "src/module.py [modified] sha256=def456" in prompt
