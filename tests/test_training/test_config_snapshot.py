from __future__ import annotations

import pytest
from omegaconf import OmegaConf

from training.artifacts import write_run_config_snapshot


def test_run_config_snapshot_resolves_values_and_is_stable(tmp_path) -> None:
    config = OmegaConf.create(
        {
            "base": {"steps": 1000},
            "training": {"steps": "${base.steps}"},
        }
    )

    snapshot = write_run_config_snapshot(tmp_path, config)
    original = snapshot.read_text(encoding="utf-8")

    assert snapshot == tmp_path / "config.yaml"
    assert "steps: 1000" in original
    assert "${base.steps}" not in original
    assert write_run_config_snapshot(tmp_path, config) == snapshot
    assert snapshot.read_text(encoding="utf-8") == original


def test_run_config_snapshot_rejects_rewriting_run_identity(tmp_path) -> None:
    first = OmegaConf.create({"training": {"steps": 1000}})
    changed = OmegaConf.create({"training": {"steps": 2000}})
    write_run_config_snapshot(tmp_path, first)

    with pytest.raises(FileExistsError, match="snapshot already differs"):
        write_run_config_snapshot(tmp_path, changed)
