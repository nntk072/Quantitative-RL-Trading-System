"""Stable evaluation command surface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path


def _forward(callable_main: Callable[[], object], argv: list[str]) -> None:
    """Process the requested value.

    Args:
        callable_main: Callable main used by the operation described above.
        argv: Items supplied for the argv, in input order.
    """
    original = sys.argv
    try:
        sys.argv = [original[0], *argv]
        callable_main()
    finally:
        sys.argv = original


def main() -> None:
    """Dispatch the evaluation command-line workflow."""
    program = Path(sys.argv[0]).name
    parser = argparse.ArgumentParser(prog=program if program != "pytest" else "qrl-evaluate")
    parser.add_argument("command", choices=("reanalyze",))
    args, rest = parser.parse_known_args()
    from evaluation.reanalysis.checkpoint_reanalysis import main as command_main

    _forward(command_main, rest)
