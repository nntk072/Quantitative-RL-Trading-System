"""Named-cache publication refuses incomplete prior provenance before rebuilding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

from experiments.runs import named_cache_rebuild


def test_named_cache_signature_ignores_output_path_but_binds_raw_data_and_split() -> None:
    first = OmegaConf.create(
        {
            "data": {
                "raw_dir": "data/raw",
                "prebuilt_feature_cache": "cache/first.parquet",
                "split": {"train_end": "2025-12-31", "test_start": "2026-01-01"},
            }
        }
    )
    other_cache = OmegaConf.create(
        {
            "data": {
                "raw_dir": "data/raw",
                "prebuilt_feature_cache": "cache/second.parquet",
                "split": {"train_end": "2025-12-31", "test_start": "2026-01-01"},
            }
        }
    )
    changed_split = OmegaConf.create(
        {
            "data": {
                "raw_dir": "data/raw",
                "prebuilt_feature_cache": "cache/second.parquet",
                "split": {"train_end": "2025-11-30", "test_start": "2025-12-01"},
            }
        }
    )

    assert named_cache_rebuild._cache_config_signature(
        first
    ) == named_cache_rebuild._cache_config_signature(other_cache)
    assert named_cache_rebuild._cache_config_signature(
        first
    ) != named_cache_rebuild._cache_config_signature(changed_split)


def test_rebuild_requires_backupable_cache_and_hash_sidecar_before_raw_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    cache_dir = repository / "data" / "prebuilt_feature_cache"
    raw_dir = repository / "data" / "raw"
    cache_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    (raw_dir / "ES.csv").write_bytes(b"primary raw bars")
    (raw_dir / "NQ.csv").write_bytes(b"secondary raw bars")

    cache_names = (
        "baseline.parquet",
        "baseline_strategy_actions.parquet",
        "idea1_po3_ifvg.parquet",
        "idea2_distribution.parquet",
    )
    for name in cache_names:
        (cache_dir / name).write_bytes(f"old cache {name}".encode())
        if name != "baseline.parquet":
            Path(f"{cache_dir / name}.hash").write_text("old-hash\n", encoding="utf-8")

    monkeypatch.setattr(named_cache_rebuild, "ROOT", repository)
    monkeypatch.setattr(
        named_cache_rebuild,
        "plan",
        lambda: [
            {"variant": name, "cache_path": str(cache_dir / cache_name)}
            for name, cache_name in zip(named_cache_rebuild.VARIANTS, cache_names, strict=True)
        ],
    )

    def load_variant(name: str) -> tuple[dict[str, Any], Any]:
        index = named_cache_rebuild.VARIANTS.index(name)
        cfg = OmegaConf.create(
            {
                "data": {
                    "raw_dir": "data/raw",
                    "primary": "ES",
                    "secondary": "NQ",
                    "m1_files": {"ES": "ES.csv", "NQ": "NQ.csv"},
                    "prebuilt_feature_cache": str(cache_dir / cache_names[index]),
                    "split": {"train_end": "2025-12-31", "test_start": "2026-01-01"},
                }
            }
        )
        return {"variant": name}, cfg

    monkeypatch.setattr(named_cache_rebuild, "load_variant", load_variant)
    monkeypatch.setattr(
        named_cache_rebuild,
        "_load_fresh_market",
        lambda *_args, **_kwargs: pytest.fail("incomplete existing cache must block rebuild"),
    )

    backup_dir = repository / "backup"
    report_path = repository / "reports" / "rebuild.json"
    with pytest.raises(FileNotFoundError, match="existing caches must be complete"):
        named_cache_rebuild.rebuild(backup_dir, report_path)

    assert not backup_dir.exists()
    assert not report_path.exists()
    assert (cache_dir / "baseline.parquet").read_bytes() == b"old cache baseline.parquet"


def test_staged_cache_publication_restores_old_files_after_validation_failure(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    backup.mkdir()
    target = tmp_path / "baseline.parquet"
    target.write_bytes(b"new cache")
    (backup / target.name).write_bytes(b"old cache")
    new_target = tmp_path / "new.parquet"
    staged = tmp_path / "staged.parquet"
    staged_new = tmp_path / "staged-new.parquet"
    staged.write_bytes(b"new-only cache")
    staged_new.write_bytes(b"new-only cache")
    report_tmp = tmp_path / "report.tmp"
    report_tmp.write_text("new report", encoding="utf-8")
    report_path = tmp_path / "report.json"

    def reject_published_content() -> None:
        raise RuntimeError("published hash verification failed")

    with pytest.raises(RuntimeError, match="published hash verification failed"):
        named_cache_rebuild._publish_staged_files(
            {target: staged, new_target: staged_new},
            backup,
            report_tmp,
            report_path,
            reject_published_content,
        )

    assert target.read_bytes() == b"old cache"
    assert not new_target.exists()
    assert not report_path.exists()


def test_staged_cache_publication_commits_validated_cache_and_report(tmp_path: Path) -> None:
    target = tmp_path / "baseline.parquet"
    staged = tmp_path / "staged.parquet"
    staged.write_bytes(b"verified cache")
    backup = tmp_path / "backup"
    backup.mkdir()
    report_tmp = tmp_path / "report.tmp"
    report_tmp.write_text("verified report", encoding="utf-8")
    report_path = tmp_path / "report.json"
    validations: list[bytes] = []

    def validate_published() -> None:
        validations.append(target.read_bytes())

    named_cache_rebuild._publish_staged_files(
        {target: staged}, backup, report_tmp, report_path, validate_published
    )

    assert validations == [b"verified cache"]
    assert report_path.read_text(encoding="utf-8") == "verified report"


def test_named_cache_rebuild_publishes_all_verified_artifacts_transactionally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    cache_dir = repository / "data" / "prebuilt_feature_cache"
    raw_dir = repository / "data" / "raw"
    cache_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    (raw_dir / "ES.csv").write_bytes(b"primary raw bars")
    (raw_dir / "NQ.csv").write_bytes(b"secondary raw bars")
    cache_names = (
        "baseline.parquet",
        "baseline_strategy_actions.parquet",
        "idea1_po3_ifvg.parquet",
        "idea2_distribution.parquet",
    )
    for name in cache_names:
        (cache_dir / name).write_bytes(f"old cache {name}".encode())
        Path(f"{cache_dir / name}.hash").write_text("old-hash\n", encoding="utf-8")

    monkeypatch.setattr(named_cache_rebuild, "ROOT", repository)
    plan_rows = [
        {
            "variant": name,
            "cache_path": str(cache_dir / cache_name),
            "experiment_run_variant_cache_bindings": {"example": "data/cache.parquet"},
        }
        for name, cache_name in zip(named_cache_rebuild.VARIANTS, cache_names, strict=True)
    ]
    monkeypatch.setattr(named_cache_rebuild, "plan", lambda: plan_rows)
    cfgs = []
    for cache_name in cache_names:
        cfgs.append(
            OmegaConf.create(
                {
                    "data": {
                        "raw_dir": "data/raw",
                        "primary": "ES",
                        "secondary": "NQ",
                        "m1_files": {"ES": "ES.csv", "NQ": "NQ.csv"},
                        "prebuilt_feature_cache": str(cache_dir / cache_name),
                        "split": {"train_end": "2025-12-31", "test_start": "2026-01-01"},
                    }
                }
            )
        )
    cfg_by_name = dict(zip(named_cache_rebuild.VARIANTS, cfgs, strict=True))
    monkeypatch.setattr(
        named_cache_rebuild,
        "load_variant",
        lambda name: ({"variant": name}, cfg_by_name[name]),
    )
    index = pd.date_range("2025-12-29", periods=2, freq="D")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    market = {"ES": {"M1": bars}, "NQ": {"M1": bars.copy()}}
    monkeypatch.setattr(named_cache_rebuild, "_load_fresh_market", lambda _cfg: market)
    monkeypatch.setattr(
        named_cache_rebuild,
        "feature_cache_content_hash",
        lambda *_args, **_kwargs: "verified-feature-hash",
    )
    expected_features = pd.DataFrame({"feature": [0.25, 0.5]}, index=index)

    def build_features(_bars: pd.DataFrame, *, cache_path: Path, **_kwargs: Any) -> pd.DataFrame:
        cache_path.write_bytes(b"new parquet payload")
        Path(f"{cache_path}.hash").write_text("verified-feature-hash\n", encoding="utf-8")
        return expected_features.copy()

    monkeypatch.setattr(named_cache_rebuild, "build_features", build_features)
    monkeypatch.setattr(pd, "read_parquet", lambda _path: expected_features.copy())
    monkeypatch.setattr(
        named_cache_rebuild, "_loaded_project_source_hashes", lambda: {"x.py": "abc"}
    )
    monkeypatch.setattr(
        named_cache_rebuild,
        "_dependency_versions",
        lambda: {"python": "3.test", "pandas": "test"},
    )

    def git_output(command: list[str], *, text: bool = False) -> str | bytes:
        if "status" in command:
            return "" if text else b""
        if "diff" in command:
            return b""
        if command[-2:] == ["rev-parse", "HEAD"]:
            return "abc123\n" if text else b"abc123\n"
        raise AssertionError(f"unexpected git command: {command}")

    monkeypatch.setattr(named_cache_rebuild.__dict__["subprocess"], "check_output", git_output)
    report_path = repository / "reports" / "cache_rebuild.json"
    backup_dir = repository / "backups" / "cache_rebuild"

    report = named_cache_rebuild.rebuild(backup_dir, report_path)

    assert report["status"] == "passed"
    assert report["repository_head"] == "abc123"
    assert len(report["caches"]) == len(named_cache_rebuild.VARIANTS)
    assert report_path.is_file()
    assert len(list(backup_dir.iterdir())) == 8
    for cache_name in cache_names:
        assert (cache_dir / cache_name).read_bytes() == b"new parquet payload"
        assert Path(f"{cache_dir / cache_name}.hash").read_text(encoding="utf-8").strip() == (
            "verified-feature-hash"
        )
