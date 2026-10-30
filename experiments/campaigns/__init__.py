"""Stable campaign workflow entry points."""

from __future__ import annotations


def run_campaign() -> int:
    """Run the campaign controller through its canonical composition root."""
    from experiments.campaigns.campaign_execution import main

    return main()


__all__ = ["run_campaign"]
