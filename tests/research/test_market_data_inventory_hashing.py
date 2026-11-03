"""Unit tests for the reusable local market-data inventory writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.research.analysis.market_data import hash_local_data_inventory
from scripts.research.analysis.market_data.hash_local_data_inventory import (
    _manifest_diff,
    _sha256,
    _write_exclusive,
)


def test_sha256_returns_digest_and_byte_count(tmp_path: Path) -> None:
    """Hash helper reports exact bytes without transforming the input."""
    source = tmp_path / "market_data.csv"
    source.write_bytes(b"timestamp,bid,ask\n1,100,101\n")

    digest, size = _sha256(source)

    assert digest == "ab82f6e085be19647ed16a1ba7d3979e886de601ce322a3eb5621ca37b0ead46"
    assert size == source.stat().st_size


def test_manifest_write_is_atomic_and_never_overwrites(tmp_path: Path) -> None:
    """An existing evidence manifest is preserved when a second write is tried."""
    output = tmp_path / "manifest.json"
    payload = {"schema": "test.v1", "rows": 3}

    _write_exclusive(output, payload)
    original = output.read_bytes()
    assert json.loads(original) == payload

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _write_exclusive(output, {"schema": "test.v2"})

    assert output.read_bytes() == original


def test_manifest_diff_identifies_changed_source_bytes() -> None:
    """A failed inventory check reports which exact file identity changed."""
    expected = {
        "created_at_utc": "old",
        "files": [
            {
                "path": "data/prices.csv",
                "resolved_path": "data/prices.csv",
                "sha256": "old-hash",
                "size_bytes": 10,
                "mtime_utc": "old-time",
            }
        ],
    }
    observed = {
        "created_at_utc": "new",
        "files": [
            {
                "path": "data/prices.csv",
                "resolved_path": "data/prices.csv",
                "sha256": "new-hash",
                "size_bytes": 12,
                "mtime_utc": "new-time",
            }
        ],
    }

    diff = _manifest_diff(expected, observed)

    assert diff["changed_file_count"] == 1
    assert diff["changed_files_sample"] == [
        {
            "path": "data/prices.csv",
            "changed_fields": ["mtime_utc", "sha256", "size_bytes"],
            "expected_sha256": "old-hash",
            "observed_sha256": "new-hash",
            "expected_size_bytes": 10,
            "observed_size_bytes": 12,
            "expected_mtime_utc": "old-time",
            "observed_mtime_utc": "new-time",
        }
    ]


def test_manifest_uses_semantic_selected_campaign_match_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generated manifest links the selected campaign without stage labels."""
    source_root = tmp_path / "repo"
    data_path = source_root / "data" / "prices.csv"
    data_path.parent.mkdir(parents=True)
    data_path.write_bytes(b"bid,ask\n100,101\n")
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {"raw_data_files": [{"path": str(data_path), "size_bytes": data_path.stat().st_size}]}
        ),
        encoding="utf-8",
    )
    campaign_audit_path = source_root / "evidence" / "campaign_audit.json"
    campaign_audit_path.parent.mkdir(parents=True)
    campaign_audit_path.write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "path": "data/prices.csv",
                        "observed_sha256": _sha256(data_path)[0],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "manifest.json"
    monkeypatch.setattr(hash_local_data_inventory, "ROOT", source_root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hash_local_data_inventory.py",
            "--inventory",
            str(inventory_path),
            "--campaign-audit",
            str(campaign_audit_path),
            "--output",
            str(output_path),
            "--write",
        ],
    )

    assert hash_local_data_inventory.main() == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["campaign_input_audit_path"] == "evidence/campaign_audit.json"
    assert report["selected_campaign_unique_data_file_matches"] == 1
    assert report["files"][0]["selected_campaign_hash_match"] is True
    assert "p6_campaign_hash_match" not in report["files"][0]
