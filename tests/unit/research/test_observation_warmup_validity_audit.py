from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

import pandas as pd
from omegaconf import OmegaConf
from scripts.research.analysis.features import audit_observation_warmup_validity as audit

ROOT = Path(__file__).resolve().parents[3]


def test_build_audit_regeneration_command_supports_external_output_paths(
    tmp_path: Path, monkeypatch: Any
) -> None:
    config_path = ROOT / "config/research/survival_trade_setup_mtf_conditioned.yaml"
    output_dir = tmp_path / "output packet"
    cache_dir = tmp_path / "cache packet"
    captured: dict[str, Any] = {}
    config = object()

    def fake_load_config(*, config_path: str) -> object:
        return config

    def fake_build_audit_from_config(cfg: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"status": "captured"}

    monkeypatch.setattr(audit, "load_config", fake_load_config)
    monkeypatch.setattr(audit, "_sha256", lambda _: "a" * 64)
    monkeypatch.setattr(audit, "build_audit_from_config", fake_build_audit_from_config)

    result = audit.build_audit(config_path, output_dir, cache_dir)

    command = shlex.split(captured["regeneration_command"])
    assert result == {"status": "captured"}
    assert command == [
        ".venv/bin/python",
        "scripts/research/analysis/features/audit_observation_warmup_validity.py",
        "--config",
        "config/research/survival_trade_setup_mtf_conditioned.yaml",
        "--output-dir",
        str(output_dir),
        "--cache-dir",
        str(cache_dir),
    ]


def test_observation_audit_clips_later_rows_before_feature_inputs(
    monkeypatch: Any,
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {
                "primary": "US100",
                "split": {"train_start": "2024-12-30", "train_end": "2025-12-31"},
            }
        }
    )
    index = pd.DatetimeIndex(["2025-12-31 14:30", "2026-01-01 14:30"])
    bars = pd.DataFrame({"close": [100.0, 900_001.0]}, index=index)
    observed: dict[str, Any] = {}
    tickbook = object()

    def fake_run_pipeline(_cfg: Any, **kwargs: Any) -> dict[str, Any]:
        observed["bar_cutoff"] = kwargs.get("end_inclusive")
        return {
            "US100": {"M1": bars.copy()},
            "US500": {"M1": bars.copy()},
        }

    def fake_tick_books(_cfg: Any, **kwargs: Any) -> dict[str, object]:
        observed["tick_cutoff"] = kwargs.get("end_inclusive")
        return {"US100": tickbook}

    monkeypatch.setattr(audit, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(audit, "build_tick_books", fake_tick_books)

    datasets, ticks = audit._load_training_inputs(cfg)

    assert observed["bar_cutoff"] == "2025-12-31"
    assert observed["tick_cutoff"] == "2025-12-31"
    assert datasets["US100"]["M1"]["close"].tolist() == [100.0]
    assert datasets["US500"]["M1"]["close"].tolist() == [100.0]
    assert 900_001.0 not in datasets["US100"]["M1"]["close"].tolist()
    assert ticks is tickbook
