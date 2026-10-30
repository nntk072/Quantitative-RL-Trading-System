"""Stable experiment run workflow entry points."""

from __future__ import annotations


def run_experiment() -> int:
    """Run the experiment run controller through its canonical composition root."""
    from experiments.runs.execution import main

    return main()


__all__ = ["run_experiment"]
