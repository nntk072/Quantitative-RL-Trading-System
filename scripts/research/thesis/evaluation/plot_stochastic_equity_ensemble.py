"""Deprecated import adapter; implementation lives in the research analysis package."""

import sys
from importlib import import_module as _import_module
from pathlib import Path
from typing import Any

for _candidate in Path(__file__).resolve().parents:
    if (_candidate / "pyproject.toml").is_file():
        sys.path.insert(0, str(_candidate))
        break

_implementation = _import_module(
    "scripts.research.analysis.evaluation.plot_stochastic_equity_ensemble"
)


def __getattr__(name: str) -> Any:
    return getattr(_implementation, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_implementation)))


if __name__ == "__main__":
    entry = getattr(_implementation, "main", None)
    if not callable(entry):
        raise SystemExit("This compatibility module has no command-line entry point.")
    raise SystemExit(entry())
