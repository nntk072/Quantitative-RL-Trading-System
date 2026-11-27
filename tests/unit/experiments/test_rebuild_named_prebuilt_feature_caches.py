"""Transactional publication behavior for the named feature-cache builder."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from omegaconf import DictConfig, OmegaConf

from experiments.runs import named_cache_rebuild as cache_builder


@pytest.mark.unit
def test_trade_setup_experiment_run_maps_all_18_variants_to_four_feature_caches() -> None:
    rows = cache_builder.plan()
    assert len(rows) == 4
    bindings = rows[0]["experiment_run_variant_cache_bindings"]
    assert len(bindings) == 18

    counts: dict[str, int] = {}
    for cache_path in bindings.values():
        counts[cache_path] = counts.get(cache_path, 0) + 1
    assert counts == {
        "data/prebuilt_feature_cache/baseline.parquet": 1,
        "data/prebuilt_feature_cache/baseline_strategy_actions.parquet": 5,
        "data/prebuilt_feature_cache/idea1_po3_ifvg.parquet": 6,
        "data/prebuilt_feature_cache/idea2_distribution.parquet": 6,
    }


@pytest.mark.unit
def test_htf_confirmed_cache_requires_sweep_audit_parquet(tmp_path: Path) -> None:
    cache_path = tmp_path / "idea1.parquet"
    htf_cfg = OmegaConf.create({"features": {"po3_reference_mode": "htf_confirmed"}})

    with pytest.raises(RuntimeError, match="required sweep-audit parquet"):
        cache_builder._validate_staged_sweep_audit(cache_path, htf_cfg)

    audit_path = Path(f"{cache_path}.htf_sweeps.parquet")
    audit_path.write_bytes(b"audited sweep references")
    assert cache_builder._validate_staged_sweep_audit(cache_path, htf_cfg) == audit_path


@pytest.mark.unit
def test_legacy_cache_does_not_require_sweep_audit_parquet(tmp_path: Path) -> None:
    cache_path = tmp_path / "baseline.parquet"
    legacy_cfg = OmegaConf.create({"features": {}})

    assert cache_builder._validate_staged_sweep_audit(cache_path, legacy_cfg) is None


@pytest.mark.unit
def test_resolved_config_record_hashes_effective_merged_configuration() -> None:
    cfg = OmegaConf.create(
        {
            "features": {"sessions": {"ny": {"start": "08:30", "end": "15:00"}}},
            "data": {"primary": "US100.cash"},
        }
    )
    record = cache_builder._resolved_config_record(cfg)
    assert record["value"] == OmegaConf.to_container(cfg, resolve=True)
    assert len(record["sha256"]) == 64

    cfg.features.sessions.ny.end = "14:00"
    changed = cache_builder._resolved_config_record(cfg)
    assert changed["sha256"] != record["sha256"]


@pytest.mark.unit
def test_loaded_source_hashes_include_migrated_project_packages_only() -> None:
    import configuration.paths as configuration_paths
    import features.pipeline.feature_matrix_builder as feature_builder
    import training.configuration.variant_resolution as variant_resolution

    sources = cache_builder._loaded_project_source_hashes()
    expected_modules = (
        cache_builder,
        configuration_paths,
        feature_builder,
        variant_resolution,
    )
    for module in expected_modules:
        module_file = module.__file__
        assert module_file is not None
        module_path = Path(module_file).resolve()
        relative_path = module_path.relative_to(cache_builder.ROOT.resolve()).as_posix()
        assert relative_path in sources
        assert sources[relative_path] == cache_builder.sha256_file(module_path)

    assert all(not path.startswith("quant_rl/") for path in sources)
    assert all("site-packages/" not in path for path in sources)


@pytest.mark.unit
def test_fresh_market_forces_raw_rebuild_in_temporary_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = OmegaConf.create({"data": {"raw_dir": "data", "cache_dir": "shared-cache"}})
    captured: dict[str, object] = {}

    def fake_run_pipeline(
        config: DictConfig, *, force: bool = False
    ) -> dict[str, dict[str, pd.DataFrame]]:
        captured["raw_dir"] = config.data.raw_dir
        captured["cache_dir"] = config.data.cache_dir
        captured["force"] = force
        assert Path(str(config.data.cache_dir)).is_dir()
        return {"US100.cash": {"M1": pd.DataFrame()}}

    monkeypatch.setattr(cache_builder, "run_pipeline", fake_run_pipeline)
    market = cache_builder._load_fresh_market(cfg)

    assert captured["raw_dir"] == str((cache_builder.ROOT / "data").resolve())
    assert captured["force"] is True
    assert captured["cache_dir"] != "shared-cache"
    assert not Path(str(captured["cache_dir"])).exists()
    assert cfg.data.cache_dir == "shared-cache"
    assert "US100.cash" in market


def _transaction_files(tmp_path: Path) -> tuple[dict[Path, Path], Path, Path, Path]:
    backup = tmp_path / "backup"
    backup.mkdir()
    stage = tmp_path / "stage"
    stage.mkdir()
    staged: dict[Path, Path] = {}
    for name in ("baseline.parquet", "idea1.parquet"):
        target = tmp_path / name
        target.write_text(f"old:{name}", encoding="utf-8")
        (backup / name).write_text(f"old:{name}", encoding="utf-8")
        staged_path = stage / name
        staged_path.write_text(f"new:{name}", encoding="utf-8")
        staged[target] = staged_path

    report_tmp = stage / "report.json.tmp"
    report_tmp.write_text('{"status":"passed"}\n', encoding="utf-8")
    report = tmp_path / "report.json"
    return staged, backup, report_tmp, report


@pytest.mark.unit
def test_publish_staged_files_replaces_caches_and_report(tmp_path: Path) -> None:
    staged, backup, report_tmp, report = _transaction_files(tmp_path)

    def validate() -> None:
        assert all(target.read_text(encoding="utf-8").startswith("new:") for target in staged)

    cache_builder._publish_staged_files(staged, backup, report_tmp, report, validate)

    assert all(target.read_text(encoding="utf-8").startswith("new:") for target in staged)
    assert report.read_text(encoding="utf-8") == '{"status":"passed"}\n'
    assert not report_tmp.exists()


@pytest.mark.unit
def test_publish_staged_files_rolls_back_on_validation_failure(tmp_path: Path) -> None:
    staged, backup, report_tmp, report = _transaction_files(tmp_path)

    def fail_validation() -> None:
        raise RuntimeError("simulated post-publish verification failure")

    with pytest.raises(RuntimeError, match="simulated post-publish"):
        cache_builder._publish_staged_files(staged, backup, report_tmp, report, fail_validation)

    assert all(target.read_text(encoding="utf-8").startswith("old:") for target in staged)
    assert not report.exists()


@pytest.mark.unit
def test_publish_staged_files_rolls_back_partial_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged, backup, report_tmp, report = _transaction_files(tmp_path)
    target_a, target_b = tuple(staged)
    original_replace = os.replace

    def fail_on_second_target(
        source: str | os.PathLike[str], target: str | os.PathLike[str]
    ) -> None:
        if Path(target) == target_b:
            raise OSError("simulated replacement failure")
        original_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_on_second_target)
    with pytest.raises(OSError, match="simulated replacement failure"):
        cache_builder._publish_staged_files(staged, backup, report_tmp, report, lambda: None)

    assert target_a.read_text(encoding="utf-8") == "old:baseline.parquet"
    assert target_b.read_text(encoding="utf-8") == "old:idea1.parquet"
    assert not report.exists()


def _install_minimal_rebuild_plan(
    monkeypatch: pytest.MonkeyPatch, root: Path, cache_dir: Path
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cache_builder, "ROOT", root)
    monkeypatch.setattr(
        cache_builder,
        "plan",
        lambda: [{"variant": "representative", "cache_path": str(cache_dir / "cache.parquet")}],
    )


@pytest.mark.unit
def test_rebuild_rejects_report_outside_repository_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    cache_dir = root / "cache"
    _install_minimal_rebuild_plan(monkeypatch, root, cache_dir)

    with pytest.raises(ValueError, match="report path must stay inside the repository"):
        cache_builder.rebuild(root / "backup", tmp_path / "external-report.json")

    assert not (root / "backup").exists()
    assert not (tmp_path / "external-report.json").exists()


@pytest.mark.unit
def test_rebuild_refuses_to_overwrite_an_existing_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    cache_dir = root / "cache"
    _install_minimal_rebuild_plan(monkeypatch, root, cache_dir)
    report = root / "reports" / "rebuild.json"
    report.parent.mkdir()
    report.write_text("prior evidence\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite existing report"):
        cache_builder.rebuild(root / "backup", report)

    assert report.read_text(encoding="utf-8") == "prior evidence\n"
    assert not (root / "backup").exists()


@pytest.mark.unit
def test_rebuild_refuses_to_reuse_existing_backup_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    cache_dir = root / "cache"
    _install_minimal_rebuild_plan(monkeypatch, root, cache_dir)
    backup = root / "backup"
    backup.mkdir()
    report = root / "rebuild.json"

    with pytest.raises(FileExistsError, match="refusing to reuse existing backup directory"):
        cache_builder.rebuild(backup, report)

    assert backup.is_dir()
    assert not report.exists()


@pytest.mark.unit
def test_rebuild_rejects_cache_directory_symlink_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    actual_cache_dir = root / "actual-cache"
    actual_cache_dir.mkdir()
    linked_cache_dir = root / "cache-link"
    linked_cache_dir.symlink_to(actual_cache_dir, target_is_directory=True)
    _install_minimal_rebuild_plan(monkeypatch, root, linked_cache_dir)

    with pytest.raises(RuntimeError, match="cache directory must be a real directory"):
        cache_builder.rebuild(root / "backup", root / "rebuild.json")

    assert linked_cache_dir.is_symlink()
    assert not (root / "backup").exists()
    assert not (root / "rebuild.json").exists()


@pytest.mark.unit
def test_rebuild_refuses_missing_raw_source_before_staging_or_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    cache_dir = root / "data" / "prebuilt_feature_cache"
    _install_minimal_rebuild_plan(monkeypatch, root, cache_dir)

    def load_variant(_name: str) -> tuple[dict[str, str], DictConfig]:
        return {"variant": "fixture"}, OmegaConf.create(
            {
                "data": {
                    "raw_dir": "data/raw",
                    "primary": "ES",
                    "secondary": "NQ",
                    "m1_files": {"ES": "ES.csv", "NQ": "NQ.csv"},
                    "prebuilt_feature_cache": str(cache_dir / "cache.parquet"),
                    "split": {"train_end": "2025-12-31", "test_start": "2026-01-01"},
                }
            }
        )

    monkeypatch.setattr(cache_builder, "load_variant", load_variant)
    monkeypatch.setattr(
        cache_builder,
        "_load_fresh_market",
        lambda *_args, **_kwargs: pytest.fail("raw source absence must be detected first"),
    )
    report = root / "reports" / "rebuild.json"
    backup = root / "backup"

    with pytest.raises(FileNotFoundError, match="raw M1 input missing for ES"):
        cache_builder.rebuild(backup, report)

    assert not backup.exists()
    assert not report.exists()
    assert list(cache_dir.iterdir()) == []


@pytest.mark.unit
def test_rebuild_rejects_raw_source_changed_during_staging_without_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    cache_dir = root / "data" / "prebuilt_feature_cache"
    raw_dir = root / "data" / "raw"
    cache_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    raw_primary = raw_dir / "ES.csv"
    raw_secondary = raw_dir / "NQ.csv"
    raw_primary.write_bytes(b"original primary bars")
    raw_secondary.write_bytes(b"original secondary bars")
    cache_names = (
        "baseline.parquet",
        "baseline_strategy_actions.parquet",
        "idea1_po3_ifvg.parquet",
        "idea2_distribution.parquet",
    )
    for name in cache_names:
        (cache_dir / name).write_bytes(f"old:{name}".encode())
        Path(f"{cache_dir / name}.hash").write_text("old-cache-hash\n", encoding="utf-8")
    monkeypatch.setattr(cache_builder, "ROOT", root)
    rows = [
        {
            "variant": name,
            "cache_path": str(cache_dir / cache_name),
            "experiment_run_variant_cache_bindings": {"fixture": str(cache_name)},
        }
        for name, cache_name in zip(cache_builder.VARIANTS, cache_names, strict=True)
    ]
    monkeypatch.setattr(cache_builder, "plan", lambda: rows)
    cfgs = [
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
        for cache_name in cache_names
    ]
    cfg_by_name = dict(zip(cache_builder.VARIANTS, cfgs, strict=True))
    monkeypatch.setattr(
        cache_builder,
        "load_variant",
        lambda name: ({"variant": name}, cfg_by_name[name]),
    )
    index = pd.date_range("2025-12-29", periods=2, freq="D")
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    monkeypatch.setattr(
        cache_builder,
        "_load_fresh_market",
        lambda _cfg: {"ES": {"M1": bars}, "NQ": {"M1": bars.copy()}},
    )
    monkeypatch.setattr(
        cache_builder,
        "feature_cache_content_hash",
        lambda *_args, **_kwargs: "verified-feature-hash",
    )
    features = pd.DataFrame({"feature": [0.25, 0.5]}, index=index)
    changed_source = False

    def build_features(_bars: pd.DataFrame, *, cache_path: Path, **_kwargs: Any) -> pd.DataFrame:
        nonlocal changed_source
        cache_path.write_bytes(b"new staged parquet")
        Path(f"{cache_path}.hash").write_text("verified-feature-hash\n", encoding="utf-8")
        if not changed_source:
            raw_primary.write_bytes(b"primary source changed during rebuild")
            changed_source = True
        return features.copy()

    monkeypatch.setattr(cache_builder, "build_features", build_features)
    monkeypatch.setattr(pd, "read_parquet", lambda _path: features.copy())
    report = root / "reports" / "rebuild.json"
    backup = root / "backups" / "rebuild"

    with pytest.raises(RuntimeError, match="raw market inputs changed during cache rebuild"):
        cache_builder.rebuild(backup, report)

    assert not backup.exists()
    assert not report.exists()
    for name in cache_names:
        assert (cache_dir / name).read_bytes() == f"old:{name}".encode()
        assert Path(f"{cache_dir / name}.hash").read_text(encoding="utf-8") == "old-cache-hash\n"
    assert not list(cache_dir.glob("named-feature-cache-stage-*"))
