"""Source snapshot admission rejects archives that no longer match their manifest."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from experiments.runs.source_snapshot import (
    sha256_file,
    verify_experiment_run_source_snapshot,
    write_experiment_run_source_snapshot,
)


def _snapshot(tmp_path: Path) -> tuple[Path, dict[str, object], bytes]:
    repository = tmp_path / "repo"
    repository.mkdir()
    source = repository / "trainer.py"
    source.write_text("train = 1\n", encoding="utf-8")
    snapshot = tmp_path / "run" / "source_snapshot.zip"
    record = write_experiment_run_source_snapshot(
        repository,
        [source],
        snapshot,
        git_sha="c" * 40,
        expected_source_hashes={"trainer.py": sha256_file(source)},
    )
    with zipfile.ZipFile(snapshot) as archive:
        manifest = archive.read("source_manifest.json")
    return snapshot, record, manifest


def test_source_snapshot_rejects_changed_member_even_when_archive_hash_is_updated(
    tmp_path: Path,
) -> None:
    snapshot, record, manifest = _snapshot(tmp_path)
    replacement = snapshot.with_suffix(".replacement.zip")
    with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source_manifest.json", manifest)
        archive.writestr("trainer.py", b"train = 2\n")
    replacement.replace(snapshot)
    updated_record = {
        **record,
        "sha256": sha256_file(snapshot),
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
    }

    valid, reason = verify_experiment_run_source_snapshot(snapshot, updated_record)

    assert not valid
    assert reason == "source snapshot file hash mismatch: trainer.py"


def test_source_snapshot_rejects_unmanifested_archive_members(tmp_path: Path) -> None:
    snapshot, record, manifest = _snapshot(tmp_path)
    replacement = snapshot.with_suffix(".replacement.zip")
    with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source_manifest.json", manifest)
        archive.writestr("trainer.py", b"train = 1\n")
        archive.writestr("extra.py", b"untracked = True\n")
    replacement.replace(snapshot)
    updated_record = {
        **record,
        "sha256": sha256_file(snapshot),
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
    }

    valid, reason = verify_experiment_run_source_snapshot(snapshot, updated_record)

    assert not valid
    assert reason == "source snapshot contents differ from its file manifest"


def test_source_snapshot_rejects_manifest_bytes_that_no_longer_match_the_record(
    tmp_path: Path,
) -> None:
    snapshot, record, manifest = _snapshot(tmp_path)
    parsed = json.loads(manifest)
    parsed["git_sha"] = "d" * 40
    changed_manifest = (json.dumps(parsed, indent=2, sort_keys=True) + "\n").encode()
    replacement = snapshot.with_suffix(".replacement.zip")
    with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source_manifest.json", changed_manifest)
        archive.writestr("trainer.py", b"train = 1\n")
    replacement.replace(snapshot)
    updated_record = {**record, "sha256": sha256_file(snapshot)}

    valid, reason = verify_experiment_run_source_snapshot(snapshot, updated_record)

    assert not valid
    assert reason == "source snapshot manifest hash mismatch"
