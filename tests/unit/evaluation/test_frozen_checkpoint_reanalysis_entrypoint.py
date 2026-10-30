"""Frozen research launchers keep their historical reanalysis entrypoint."""

from __future__ import annotations

import importlib


def test_frozen_reanalysis_module_forwards_to_package_command() -> None:
    legacy = importlib.import_module("evaluation.reanalysis.runner")
    canonical = importlib.import_module("evaluation.reanalysis.checkpoint_reanalysis")
    assert legacy is canonical
