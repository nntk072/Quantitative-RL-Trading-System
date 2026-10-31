"""Stable market-data command surface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path


def _forward(callable_main: Callable[[], object], argv: list[str]) -> None:
    original = sys.argv
    try:
        sys.argv = [original[0], *argv]
        callable_main()
    finally:
        sys.argv = original


def main() -> None:
    program = Path(sys.argv[0]).name
    parser = argparse.ArgumentParser(prog=program if program != "pytest" else "qrl-data")
    parser.add_argument("command", choices=("prepare", "discover", "prebuild-experiment-run-cache"))
    args, rest = parser.parse_known_args()
    if args.command == "prepare":
        from market_data.commands.prepare import main as command_main
    elif args.command == "discover":
        from market_data.commands.discover import main as command_main
    else:
        from market_data.commands.prebuild_experiment_run_cache import main as command_main
    _forward(command_main, rest)
