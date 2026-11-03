"""Integrity checks for the subject-named paired-attribution evidence packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def test_entry_exit_attribution_manifest_matches_semantic_packet_assets() -> None:
    """The semantic packet assets must remain byte-identical to their origins."""
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / "evidence/research/entry_and_exit_attribution/evidence_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["evidence_id"] == "entry_and_exit_attribution"
    assert len(manifest["assets"]) == 5
    for asset in manifest["assets"]:
        if not asset["copied_into_packet"]:
            assert asset["path"] is None
            assert asset["external_archive_path"]
            assert asset["external_archive_sha256"] == asset["sha256"]
            continue
        path = root / asset["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == asset["sha256"], asset["path"]
        historical_path = root / asset["historical_source_path"]
        if historical_path.is_file():
            historical_digest = hashlib.sha256(historical_path.read_bytes()).hexdigest()
            assert historical_digest == asset["sha256"], asset["historical_source_path"]

    generated_outputs = manifest["generated_outputs"]
    assert len(generated_outputs) == 1
    for output in generated_outputs:
        output_path = root / output["path"]
        generator_path = root / output["generator_path"]
        output_digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        generator_digest = hashlib.sha256(generator_path.read_bytes()).hexdigest()
        assert output_digest == output["sha256"], output["path"]
        assert generator_digest == output["generator_sha256"], output["generator_path"]
