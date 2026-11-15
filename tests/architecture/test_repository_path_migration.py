from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_configuration_migration_records_resolve_to_current_profiles() -> None:
    migration_path = ROOT / "docs/architecture/migrations/config_identity_migration_20261031.json"
    migration = json.loads(migration_path.read_text(encoding="utf-8"))
    entries = migration["entries"]

    assert entries
    assert len({entry["historical_path"] for entry in entries}) == len(entries)
    assert len({entry["current_path"] for entry in entries}) == len(entries)
    for entry in entries:
        current_path = (ROOT / entry["current_path"]).resolve()
        assert current_path.is_relative_to(ROOT.resolve())
        assert current_path.is_file()
        assert len(entry["archive_sha256"]) == 64
        assert len(entry["current_sha256"]) == 64
