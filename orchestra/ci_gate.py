"""Orchestra's adapter to the repository's canonical CI dispatcher."""

from __future__ import annotations

from dataclasses import dataclass

# The full dispatcher includes build, integration, assurance, and training-smoke
# gates. Allow a generous bound while keeping a lost child process recoverable.
CI_GATE_TIMEOUT_S = 6 * 60 * 60.0


@dataclass(frozen=True)
class CiCheck:
    """One named verification operation executed by Orchestra."""

    name: str
    argv: list[str]
    timeout: float | None = None


# GitHub invokes the named gates in parallel and aggregates them. Orchestra
# delegates to the same dispatcher in its local serial mode; it does not carry
# a second, divergent list of Ruff/Mypy/pytest commands.
CI_CHECKS: tuple[CiCheck, ...] = (
    CiCheck("full", ["./tools/check", "full"], timeout=CI_GATE_TIMEOUT_S),
)


def ci_command_lines() -> str:
    """Render the canonical verification command for prompts and reports."""
    return "\n".join(f"- `{' '.join(check.argv)}`" for check in CI_CHECKS)


def gate_passed(results: dict[str, dict[str, object]]) -> bool:
    """Return true only when every required verification operation succeeded."""
    for check in CI_CHECKS:
        entry = results.get(check.name)
        if not entry or not entry.get("success") or entry.get("skipped"):
            return False
    return True


def first_failure(results: dict[str, dict[str, object]]) -> str | None:
    for check in CI_CHECKS:
        entry = results.get(check.name, {})
        if not entry.get("success") or entry.get("skipped"):
            return check.name
    return None
