"""Build-path source identity: every module the feature build can execute changes the cache key.

Uses synthetic temporary project trees for the edit checks, so no repository file is modified.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import features
from features import registry, source_identity
from features.pipeline.feature_cache_identity import feature_cache_content_hash

REPO = Path(features.__file__).resolve().parents[1]


def test_closure_covers_undeclared_blocks_and_their_repository_imports() -> None:
    files = set(source_identity.source_files())
    for rel in (
        "features/context/order_blocks.py",
        "features/po3/fvg.py",
        "features/pipeline/feature_matrix_builder.py",
        "features/technical/__init__.py",
        "market_data/transforms/align.py",
        "market_data/loading/ticks.py",
        "decisioning/trade_setup.py",
        "artifacts/atomic.py",
        "configuration/paths.py",
    ):
        assert REPO / rel in files, rel


def test_registry_source_files_are_the_closure() -> None:
    assert set(registry.source_files()) == set(source_identity.source_files())


def test_closure_is_sorted_unique_and_inside_the_repository() -> None:
    files = source_identity.source_files()
    keys = [p.relative_to(REPO).as_posix() for p in files]
    assert keys == sorted(keys)
    assert len(set(files)) == len(files)
    assert all(REPO in p.parents for p in files)
    assert not any("__pycache__" in p.parts for p in files)


def test_digest_is_stable_across_calls() -> None:
    assert source_identity.code_digest() == source_identity.code_digest()


def _project(root: Path) -> Path:
    """Create a small project: a seed package that imports a helper package three ways."""
    (root / "seed").mkdir(parents=True)
    (root / "helper_pkg").mkdir()
    (root / "other").mkdir()
    (root / "seed" / "__init__.py").write_text("from . import leaf\n", encoding="utf-8")
    (root / "seed" / "leaf.py").write_text(
        "from helper_pkg.inner import VALUE\n\n\ndef run():\n"
        "    from helper_pkg import late\n    return VALUE, late\n",
        encoding="utf-8",
    )
    (root / "helper_pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "helper_pkg" / "inner.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "helper_pkg" / "late.py").write_text("LATE = 1\n", encoding="utf-8")
    (root / "other" / "__init__.py").write_text("", encoding="utf-8")
    (root / "other" / "unrelated.py").write_text("UNUSED = 1\n", encoding="utf-8")
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _project(tmp_path / "project")


def _seeds(root: Path) -> tuple[Path, ...]:
    return (root / "seed",)


def test_closure_follows_relative_absolute_and_function_level_imports(project: Path) -> None:
    files = source_identity.source_files(_seeds(project), project)
    relative = {p.relative_to(project).as_posix() for p in files}
    assert relative == {
        "seed/__init__.py",
        "seed/leaf.py",
        "helper_pkg/__init__.py",
        "helper_pkg/inner.py",
        "helper_pkg/late.py",
    }


def test_editing_a_transitive_module_changes_the_digest(project: Path) -> None:
    before = source_identity.code_digest(_seeds(project), project)
    (project / "helper_pkg" / "inner.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert source_identity.code_digest(_seeds(project), project) != before


def test_editing_a_module_outside_the_closure_keeps_the_digest(project: Path) -> None:
    before = source_identity.code_digest(_seeds(project), project)
    (project / "other" / "unrelated.py").write_text("UNUSED = 2\n", encoding="utf-8")
    assert source_identity.code_digest(_seeds(project), project) == before


def test_digest_is_keyed_by_project_relative_path_not_checkout_location(tmp_path: Path) -> None:
    first = _project(tmp_path / "a")
    second = _project(tmp_path / "b")
    assert source_identity.code_digest(_seeds(first), first) == source_identity.code_digest(
        _seeds(second), second
    )


def test_feature_cache_key_changes_when_an_undeclared_build_source_changes(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry, "SOURCE_ROOTS", _seeds(project))
    monkeypatch.setattr(registry, "_REPO_ROOT", project)
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
        index=pd.DatetimeIndex(["2025-01-06 00:00"], tz="UTC"),
    )
    before = feature_cache_content_hash(None, frame)
    assert feature_cache_content_hash(None, frame) == before
    (project / "helper_pkg" / "inner.py").write_text("VALUE = 3\n", encoding="utf-8")
    assert feature_cache_content_hash(None, frame) != before


def test_registry_code_identity_tracks_the_build_path_digest(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry, "SOURCE_ROOTS", _seeds(project))
    monkeypatch.setattr(registry, "_REPO_ROOT", project)
    before = registry.code_identity()
    (project / "helper_pkg" / "late.py").write_text("LATE = 2\n", encoding="utf-8")
    assert registry.code_identity() != before
