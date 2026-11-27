"""Safe, synthetic contracts for the guarded legacy baseline cache repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

from experiments.runs import baseline_cache_rebuild


def _prepare_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    old_cache: bytes = b"old cache bytes",
    old_hash: str = "old-feature-hash",
    create_cache: bool = True,
    create_sidecar: bool = True,
) -> tuple[Path, Path, Path, dict[str, Any], pd.DataFrame]:
    root = tmp_path / "repo"
    cache_path = root / baseline_cache_rebuild.LEGACY_BASELINE_CACHE
    cache_path.parent.mkdir(parents=True)
    if create_cache:
        cache_path.write_bytes(old_cache)
    sidecar = Path(f"{cache_path}.hash")
    if create_sidecar:
        sidecar.write_text(f"{old_hash}\n", encoding="utf-8")

    cfg = OmegaConf.create({"data": {"primary": "ES", "secondary": "NQ"}})
    resolved = {
        "base_config": "config/base/default.yaml",
        "strategy": "baseline",
        "overrides": [],
        "feature_profile": "core",
        "reward_mode": "dsr",
    }
    index = pd.date_range("2025-12-30", periods=2, freq="D")
    primary = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    secondary = pd.DataFrame({"close": [200.0, 201.0]}, index=index)
    features = pd.DataFrame({"feature": [0.25, 0.5]}, index=index)
    observations: dict[str, Any] = {}

    monkeypatch.setattr(baseline_cache_rebuild, "ROOT", root)
    monkeypatch.setattr(
        baseline_cache_rebuild, "resolve_variant", lambda *_args, **_kwargs: resolved
    )
    monkeypatch.setattr(baseline_cache_rebuild, "load_merged_config", lambda _args: cfg)

    def run_pipeline(pipeline_cfg: Any) -> dict[str, dict[str, pd.DataFrame]]:
        observations["pipeline_cfg"] = pipeline_cfg
        return {"ES": {"M1": primary}, "NQ": {"M1": secondary}}

    monkeypatch.setattr(baseline_cache_rebuild, "run_pipeline", run_pipeline)
    monkeypatch.setattr(
        baseline_cache_rebuild, "get_split_config", lambda _cfg: ("2025-12-31", "2026-01-01")
    )
    monkeypatch.setattr(baseline_cache_rebuild, "get_train_start_config", lambda _cfg: "2025-12-30")
    monkeypatch.setattr(
        baseline_cache_rebuild,
        "make_train_mask",
        lambda index_values, *_args: pd.Series(True, index=index_values),
    )
    monkeypatch.setattr(
        baseline_cache_rebuild,
        "feature_cache_content_hash",
        lambda *_args, **_kwargs: "expected-feature-hash",
    )
    monkeypatch.setattr(pd, "read_parquet", lambda _path: features.copy())
    monkeypatch.setattr(
        baseline_cache_rebuild.__dict__["subprocess"],
        "check_output",
        lambda *_args, **_kwargs: "abc123\n",
    )
    report_path = root / "reports" / "baseline-cache.json"
    return cache_path, sidecar, report_path, observations, features


def test_rebuild_reuses_matching_cache_and_records_verified_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path, sidecar, report_path, observations, features = _prepare_rebuild(
        monkeypatch,
        tmp_path,
        old_hash="expected-feature-hash",
    )
    monkeypatch.setattr(
        baseline_cache_rebuild,
        "build_features",
        lambda *_args, **_kwargs: pytest.fail("matching cache identity must avoid rebuilding"),
    )

    report = baseline_cache_rebuild.rebuild(report_path.parent.parent / "backup", report_path)

    assert observations["pipeline_cfg"].data.primary == "ES"
    assert report["repository_head"] == "abc123"
    assert report["cache"]["matches_effective_config"] is True
    assert report["cache"]["previous_hash"] == report["cache"]["actual_hash"]
    assert report["cache"]["feature_rows"] == len(features)
    assert (
        report["cache"]["previous_cache_sha256"]
        == hashlib.sha256(cache_path.read_bytes()).hexdigest()
    )
    backup_dir = report_path.parent.parent / "backup"
    assert (backup_dir / cache_path.name).read_bytes() == b"old cache bytes"
    assert (backup_dir / sidecar.name).read_text(encoding="utf-8") == "expected-feature-hash\n"
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def test_rebuild_replaces_stale_cache_from_verified_temporary_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path, sidecar, report_path, _observations, _features = _prepare_rebuild(
        monkeypatch,
        tmp_path,
        old_hash="stale-feature-hash",
    )
    build_calls: list[Path] = []

    def build_features(_primary: pd.DataFrame, *, cache_path: Path, **_kwargs: Any) -> pd.DataFrame:
        build_calls.append(cache_path)
        cache_path.write_bytes(b"rebuilt cache bytes")
        Path(f"{cache_path}.hash").write_text("expected-feature-hash\n", encoding="utf-8")
        return pd.DataFrame({"feature": [0.25, 0.5]}, index=_primary.index)

    monkeypatch.setattr(baseline_cache_rebuild, "build_features", build_features)

    report = baseline_cache_rebuild.rebuild(report_path.parent.parent / "backup", report_path)

    assert len(build_calls) == 1
    assert build_calls[0].parent != cache_path.parent
    assert not build_calls[0].exists()
    assert cache_path.read_bytes() == b"rebuilt cache bytes"
    assert sidecar.read_text(encoding="utf-8").strip() == "expected-feature-hash"
    assert report["cache"]["previous_hash"] == "stale-feature-hash"
    assert report["cache"]["actual_hash"] == "expected-feature-hash"
    assert (
        report_path.parent.parent / "backup" / cache_path.name
    ).read_bytes() == b"old cache bytes"


def test_rebuild_keeps_published_cache_when_staged_identity_is_wrong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path, sidecar, report_path, _observations, features = _prepare_rebuild(
        monkeypatch,
        tmp_path,
        old_hash="stale-feature-hash",
    )

    def build_features(_primary: pd.DataFrame, *, cache_path: Path, **_kwargs: Any) -> pd.DataFrame:
        cache_path.write_bytes(b"unverified staged bytes")
        Path(f"{cache_path}.hash").write_text("wrong-feature-hash\n", encoding="utf-8")
        return features.copy()

    monkeypatch.setattr(baseline_cache_rebuild, "build_features", build_features)

    with pytest.raises(RuntimeError, match="rebuilt cache hash mismatch"):
        baseline_cache_rebuild.rebuild(report_path.parent.parent / "backup", report_path)

    assert cache_path.read_bytes() == b"old cache bytes"
    assert sidecar.read_text(encoding="utf-8") == "stale-feature-hash\n"
    assert (
        report_path.parent.parent / "backup" / cache_path.name
    ).read_bytes() == b"old cache bytes"
    assert not report_path.exists()


@pytest.mark.parametrize(
    ("create_cache", "create_sidecar", "missing_name"),
    [(False, True, "baseline.parquet"), (True, False, "baseline.parquet.hash")],
)
def test_rebuild_requires_both_legacy_cache_and_identity_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    create_cache: bool,
    create_sidecar: bool,
    missing_name: str,
) -> None:
    cache_path, _sidecar, _report_path, _observations, _features = _prepare_rebuild(
        monkeypatch,
        tmp_path,
        create_cache=create_cache,
        create_sidecar=create_sidecar,
    )
    backup_dir = cache_path.parent.parent / "backup"
    report_path = cache_path.parent.parent / "report.json"

    with pytest.raises(FileNotFoundError, match=missing_name):
        baseline_cache_rebuild.rebuild(backup_dir, report_path)

    assert not backup_dir.exists()
    assert not report_path.exists()
