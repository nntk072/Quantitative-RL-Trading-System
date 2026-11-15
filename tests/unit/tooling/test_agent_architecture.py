"""Deterministic checks for the shared agent configuration and helpers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def run_tool(tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools/agent" / tool), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_rule_and_profile_validators_accept_repository_contract() -> None:
    assert run_tool("validate-rules").returncode == 0
    assert run_tool("validate-profiles").returncode == 0


def test_context_status_marks_changed_fact_source_stale(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    source = tmp_path / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "source.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    revision = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    packet = tmp_path / "context"
    packet.mkdir()
    (packet / "ownership.json").write_text('{"owner": "ml_engineer"}\n', encoding="utf-8")
    facts = {"fact": "verified", "revision": revision, "source": "source.py::value"}
    (packet / "facts.jsonl").write_text(json.dumps(facts) + "\n", encoding="utf-8")
    source.write_text("value = 2\n", encoding="utf-8")

    result = run_tool("context-status", "--repo", str(tmp_path), "--task", str(packet))

    assert result.returncode == 1
    assert 'active ownership {"owner": "ml_engineer"}' in result.stdout
    assert "stale fact line 1: source.py::value" in result.stdout


def test_context_status_keeps_unrelated_fact_current_after_edit(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    for name in ("source.py", "other.py"):
        (tmp_path / name).write_text(f"{name} = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    revision = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    packet = tmp_path / "context"
    packet.mkdir()
    facts = {"fact": "verified", "revision": revision, "source": "source.py::symbol"}
    (packet / "facts.jsonl").write_text(json.dumps(facts) + "\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("other = 2\n", encoding="utf-8")

    result = run_tool("context-status", "--repo", str(tmp_path), "--task", str(packet))

    assert result.returncode == 0
    assert "shared facts 1; stale 0" in result.stdout


def test_extension_doctor_is_local_and_noninteractive() -> None:
    result = run_tool("extension-doctor")
    assert result.returncode == 0
    assert "Codex CLI" in result.stdout
    assert "Code Review Graph" in result.stdout
    assert "unavailable" in result.stdout or "available" in result.stdout


def test_routing_rules_cover_known_unknown_and_sequential_work() -> None:
    extensions = (ROOT / ".agents/rules/extension-routing.md").read_text(encoding="utf-8")
    delegation = (ROOT / ".agents/rules/delegation.md").read_text(encoding="utf-8")
    effort = (ROOT / ".agents/rules/reasoning-effort.md").read_text(encoding="utf-8")
    assert "Known file or local text" in extensions
    assert "Code Review Graph" in extensions
    assert "Serena" in extensions and "Graphify" in extensions
    assert "Obsidian" in extensions and "RTK" in extensions
    assert "Choose one primary tool" in extensions
    assert "blocked task" in delegation
    assert "Root-only work is the default" in delegation
    assert "waits silently" in delegation
    assert "30 minutes" in delegation and "15 minutes" in delegation
    assert "XHigh" in effort and "High" in effort and "Medium" in effort
