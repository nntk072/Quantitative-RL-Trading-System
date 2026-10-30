from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.maintenance.artifacts.inventory_checkpoint_serialized_classes import (
    build_inventory,
)


def _write_checkpoint(path: Path, metadata: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("data", metadata)
        archive.writestr("policy.pth", b"tensor-payload-must-not-be-read")


def test_inventory_finds_legacy_class_path_without_loading_tensor_payload(
    tmp_path: Path,
) -> None:
    root = tmp_path / "outputs"
    checkpoint = root / "run" / "model" / "ppo_final.zip"
    _write_checkpoint(
        checkpoint,
        json.dumps(
            {
                "features_extractor_class": "models.encoders.core.MTFEncoder",
                "policy_class": "stable_baselines3.PPO",
            }
        ),
    )
    _write_checkpoint(root / "run" / "source_snapshot.zip", "not a checkpoint")

    inventory = build_inventory(root)

    assert inventory["summary"]["checkpoint_archives"] == 1
    legacy = inventory["legacy_references"]
    assert len(legacy) == 1
    assert legacy[0]["path"] == "run/model/ppo_final.zip"
    assert legacy[0]["serialized_encoder_class_paths"] == ["models.encoders.core.MTFEncoder"]
    assert legacy[0]["legacy_module_references"] == ["models.encoders.core."]
