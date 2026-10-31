from __future__ import annotations

from importlib import import_module


def test_legacy_module_path_forwards_to_canonical_analysis_implementation() -> None:
    canonical = import_module("scripts.research.analysis.evidence.verify_result_manifest")
    legacy = import_module("scripts.research.thesis.evidence.verify_result_manifest")

    assert legacy.validate_result_manifest is canonical.validate_result_manifest
    assert legacy.main is canonical.main
