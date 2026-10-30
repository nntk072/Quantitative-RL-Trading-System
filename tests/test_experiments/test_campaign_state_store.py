from __future__ import annotations

import json
from pathlib import Path

from experiments.campaigns.state_store import atomic_json, read_manifest


def test_campaign_manifest_uses_shared_strict_atomic_json_writer(tmp_path: Path) -> None:
    path = tmp_path / "campaign" / "campaign.json"
    manifest = {"state": "running", "completed": 2}

    atomic_json(path, manifest)

    assert path.read_text(encoding="utf-8") == '{\n  "completed": 2,\n  "state": "running"\n}\n'
    assert json.loads(path.read_text(encoding="utf-8")) == manifest
    assert read_manifest(path) == manifest
