"""Integrity checks for the semantic exit-action evidence packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKET_ROOT = REPOSITORY_ROOT / "evidence/research/exit_action_semantics"


def test_semantic_packet_assets_match_manifest_hashes() -> None:
    manifest = cast(
        dict[str, object],
        json.loads((PACKET_ROOT / "evidence_manifest.json").read_text(encoding="utf-8")),
    )
    assets = manifest["assets"]
    assert isinstance(assets, list)
    assert len(assets) == 25

    for asset in assets:
        assert isinstance(asset, dict)
        path = PACKET_ROOT / str(asset["path"])
        assert path.is_file()
        actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual_sha256 == asset["sha256"]
        historical_sha256 = str(asset["historical_source_sha256"])
        assert len(historical_sha256) == 64
        assert all(character in "0123456789abcdef" for character in historical_sha256)
        assert str(asset["historical_source_path"]).strip()
        if asset["content_transformed"]:
            assert asset["transformation"]
        else:
            assert actual_sha256 == historical_sha256


def test_cohort_notebook_reads_semantic_packet_and_verifies_cohort_hash() -> None:
    notebook = json.loads(
        (REPOSITORY_ROOT / "docs/reproduce/exit_action_semantics.ipynb").read_text(encoding="utf-8")
    )
    code = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert "evidence/research/exit_action_semantics" in code
    assert "evidence_manifest.json" in code
    assert 'assert cohort_sha256 == cohort_record["sha256"]' in code
    assert "evidence/research/exit_action_semantics" in code


def test_research_page_uses_semantic_packet_links() -> None:
    page = (REPOSITORY_ROOT / "docs/research/exit_action_semantics.md").read_text(encoding="utf-8")
    assert "evidence/research/exit_action_semantics/README.md" in page
    assert "evidence/research/exit_action_semantics/README.md" in page
