"""Tests for Orchestra's adapter to the shared CI dispatcher."""

from __future__ import annotations

from pathlib import Path

from orchestra.ci_gate import CI_CHECKS, first_failure, gate_passed

ROOT = Path(__file__).resolve().parents[3]
HOSTED_GATES = {
    "deps",
    "security-deps",
    "security-secrets",
    "quality",
    "architecture",
    "graph-quality",
    "contracts",
    "unit",
    "build",
    "integration",
    "parity",
    "training-smoke",
}


def test_orchestra_delegates_to_shared_full_dispatcher() -> None:
    assert [(check.name, check.argv) for check in CI_CHECKS] == [
        ("full", ["./tools/check", "full"])
    ]
    check_script = (ROOT / "tools/check").read_text()
    full_case = check_script.split("  full)", maxsplit=1)[1].split(";;", maxsplit=1)[0]
    assert all(f"run_{gate.replace('-', '_')}" in full_case for gate in HOSTED_GATES)


def test_hosted_workflow_uses_named_shared_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    invocations = {
        line.strip().removeprefix("- run: ./tools/check ")
        for line in workflow.splitlines()
        if "run: ./tools/check " in line
    }
    assert invocations == HOSTED_GATES
    assert "ci-success:" in workflow


def test_render_ci_verification_uses_one_canonical_command() -> None:
    from orchestra.prompts import render_ci_verification

    block = render_ci_verification("/tmp/ws")
    assert "/tmp/ws" in block
    assert "./tools/check full" in block
    assert "uv run mypy ." not in block
    assert "uv run pytest tests/ -v" not in block
    assert "Do not run the full CI gate during implementation" in block
    assert "commit" in block.lower()


def test_gate_passed_requires_success_and_rejects_skipped_checks() -> None:
    ok = {check.name: {"success": True, "output": ""} for check in CI_CHECKS}
    assert gate_passed(ok) is True
    ok["full"] = {"success": False, "output": "error"}
    assert gate_passed(ok) is False
    assert first_failure(ok) == "full"
    assert gate_passed({"full": {"success": True, "skipped": True}}) is False
    assert first_failure({"full": {"success": True, "skipped": True}}) == "full"
