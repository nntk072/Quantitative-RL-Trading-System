from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

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
