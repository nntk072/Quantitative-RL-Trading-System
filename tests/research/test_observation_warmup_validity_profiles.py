from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from scripts.research.analysis.features import audit_observation_warmup_validity_profiles as runner
from scripts.research.analysis.features.audit_observation_warmup_validity_profiles import (
    _observation_group_key,
    group_profiles,
)


def _cfg(
    *,
    arch: str = "mtf_reasoning",
    raw_columns: list[str] | None = None,
    validity_mask: bool = False,
    use_tick_execution: bool = True,
) -> Any:
    return OmegaConf.create(
        {
            "agent": {"arch": arch},
            "strategy": {"raw_columns": raw_columns or ["open", "high", "low", "close"]},
            "env": {"reachable_r_validity_mask": validity_mask},
            "data": {"raw_dir": "data/training", "tick_files": {"US100": "ticks.csv"}},
            "costs": {"use_tick_execution": use_tick_execution},
        }
    )


def test_observation_group_key_tracks_arch_raw_columns_and_validity_mask(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "scripts.research.analysis.features.audit_observation_warmup_validity_profiles.feature_config_key",
        lambda _cfg: "same-feature-builder",
    )
    baseline = _observation_group_key(_cfg())

    assert _observation_group_key(_cfg(arch="mlp")) != baseline
    assert _observation_group_key(_cfg(raw_columns=["open", "close"])) != baseline
    assert _observation_group_key(_cfg(validity_mask=True)) != baseline
    assert _observation_group_key(_cfg(use_tick_execution=False)) != baseline


def test_group_profiles_collapses_only_equivalent_observation_contracts(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "scripts.research.analysis.features.audit_observation_warmup_validity_profiles.feature_config_key",
        lambda _cfg: "same-feature-builder",
    )
    groups = group_profiles(
        [
            ("features/first", _cfg()),
            ("legacy_variant/equivalent", _cfg()),
            ("research/other_arch", _cfg(arch="mlp")),
        ]
    )

    assert len(groups) == 2
    equivalent = next(group for group in groups if len(group["profile_ids"]) == 2)
    distinct = next(group for group in groups if len(group["profile_ids"]) == 1)
    assert equivalent["profile_ids"] == ["features/first", "legacy_variant/equivalent"]
    assert distinct["profile_ids"] == ["research/other_arch"]
    assert all(
        group["directory"].startswith(group["representative_profile"].split("/")[0])
        for group in groups
    )


def test_run_group_uses_resolved_config_without_yaml_round_trip(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = OmegaConf.create({"agent": {"arch": "mlp"}, "data": {"split": {}}})
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_tick_cache_key", lambda _cfg: "shared-tick-cache")
    monkeypatch.setattr(runner, "load_profile_config", lambda _profile_id: cfg)
    regeneration_command = runner._build_regeneration_command(
        tmp_path / "inventory.json",
        tmp_path / "out",
        tmp_path / "cache",
        4,
    )

    def fake_build_audit_from_config(
        resolved_cfg: Any,
        *,
        config_label: str,
        config_sha256: str,
        output_dir: Path,
        cache_dir: Path,
        regeneration_command: str,
    ) -> dict[str, Any]:
        assert resolved_cfg is cfg
        assert config_label == "base/default"
        assert len(config_sha256) == 64
        assert cache_dir.is_dir()
        assert shlex.split(regeneration_command) == [
            ".venv/bin/python",
            "scripts/research/analysis/features/audit_observation_warmup_validity_profiles.py",
            "--inventory",
            "inventory.json",
            "--output-dir",
            "out",
            "--cache-dir",
            "cache",
            "--workers",
            "4",
        ]
        summary = {"status": "measured_training_split"}
        (output_dir / "warmup_validity_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        (output_dir / "column_warmup.csv").write_text(
            "timeframe,feature\nM1,signal\n", encoding="utf-8"
        )
        return summary

    monkeypatch.setattr(
        "scripts.research.analysis.features.audit_observation_warmup_validity.build_audit_from_config",
        fake_build_audit_from_config,
        raising=False,
    )
    group = {
        "directory": "base_default-0123456789ab",
        "group_key": "0" * 64,
        "representative_profile": "base/default",
        "profile_ids": ["base/default"],
    }

    result = runner._run_group(
        group,
        tmp_path / "out",
        tmp_path / "cache",
        regeneration_command,
    )

    assert result["return_code"] == 0
    assert result["summary"] == {"status": "measured_training_split"}
    assert result["column_warmup_sha256"]


def test_regeneration_command_quotes_external_cache_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    command = runner._build_regeneration_command(
        tmp_path / "inventory.json",
        tmp_path / "packet",
        Path("/scratch/work/agent cache"),
        2,
    )

    args = shlex.split(command)
    assert args[args.index("--output-dir") + 1] == "packet"
    assert args[args.index("--cache-dir") + 1] == "/scratch/work/agent cache"
    assert args[args.index("--workers") + 1] == "2"


def test_source_hash_snapshot_uses_relative_paths_and_content_hashes(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "audit.py"
    source.write_text("source-v1\n", encoding="utf-8")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "SOURCE_PATHS", (source,))

    assert runner._source_hashes() == {
        "audit.py": runner._sha256(source),
    }
