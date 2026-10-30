from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_path_migration_preserves_originals_and_resolves_current_paths() -> None:
    migration_path = (
        ROOT / "docs/architecture/migrations/experiment_run_name_migration_20261030.json"
    )
    migration = json.loads(migration_path.read_text(encoding="utf-8"))
    archive_path = ROOT / migration["originals_archive"]
    path_migrations = migration["path_migrations"]

    assert path_migrations
    assert len({row["old_path"] for row in path_migrations}) == len(path_migrations)

    with zipfile.ZipFile(archive_path) as archive:
        archived_paths = set(archive.namelist())
        assert len(archived_paths) == migration["original_file_count"]
        for row in path_migrations:
            original_path = row["old_path"]
            current_path = row["new_path"]

            assert original_path in archived_paths
            assert hashlib.sha256(archive.read(original_path)).hexdigest() == row["old_sha256"]
            assert (ROOT / current_path).is_file()


def test_fingerprint_migration_is_deterministic_and_collision_free() -> None:
    migration_path = (
        ROOT / "docs/architecture/migrations/experiment_run_name_migration_20261030.json"
    )
    migration = json.loads(migration_path.read_text(encoding="utf-8"))
    rows = migration["fingerprint_migrations"]

    assert len(rows) == 14
    assert len({row["previous_fingerprint"] for row in rows}) == len(rows)
    assert len({row["experiment_run_fingerprint"] for row in rows}) == len(rows)
    for row in rows:
        expected = hashlib.sha256(
            f"experiment-run-identity-v1:{row['previous_fingerprint']}".encode("ascii")
        ).hexdigest()
        assert row["experiment_run_fingerprint"] == expected
