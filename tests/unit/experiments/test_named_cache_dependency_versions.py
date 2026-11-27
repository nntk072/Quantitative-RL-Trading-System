from __future__ import annotations

import importlib.metadata
import platform

import pytest

from experiments.runs import named_cache_rebuild


def test_named_cache_source_metadata_records_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def version(package: str) -> str:
        if package == "pyarrow":
            raise importlib.metadata.PackageNotFoundError(package)
        return f"{package}-test-version"

    monkeypatch.setattr(importlib.metadata, "version", version)

    versions = named_cache_rebuild._dependency_versions()

    assert versions == {
        "python": platform.python_version(),
        "numpy": "numpy-test-version",
        "pandas": "pandas-test-version",
        "pyarrow": None,
        "omegaconf": "omegaconf-test-version",
    }
