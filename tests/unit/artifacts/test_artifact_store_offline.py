from __future__ import annotations

import errno
import io
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from artifacts import ArtifactManifest, BaselineValidation, RetentionClass, promote_to_baseline
from artifacts.atomic import write_bytes_atomic
from artifacts.identity import file_sha256
from artifacts.integrity import (
    INDEX_NAME,
    ArtifactChecksumError,
    ArtifactFileMissingError,
    ArtifactIntegrityError,
    verify_file_index,
    write_file_index,
)

PAYLOAD = b'{"net_return": 0.12}\n'


def _manifest() -> ArtifactManifest:
    return ArtifactManifest(
        kind="evaluation",
        artifact_id="evaluation:offline-store",
        retention=RetentionClass.BASELINE_PROMOTABLE,
        parents=("run:seed42",),
        provenance={"source_revision": "abc123"},
    )


def _accept(_: Path) -> BaselineValidation:
    return BaselineValidation("offline-store-check", ("metrics",))


def _source(root: Path, payload: bytes = PAYLOAD) -> Path:
    source = root / "candidate"
    source.mkdir(parents=True)
    (source / "metrics.json").write_bytes(payload)
    return source


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _published(tmp_path: Path) -> Path:
    destination = tmp_path / "baseline" / "candidate-v1"
    promote_to_baseline(_source(tmp_path), destination, _manifest(), validate=_accept)
    write_file_index(destination)
    return destination


class _FullDisk(io.BytesIO):
    def write(self, data: bytes) -> int:  # type: ignore[override]
        raise OSError(errno.ENOSPC, "No space left on device")


def test_interrupted_atomic_write_keeps_previous_destination_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "manifest.json"
    destination.write_bytes(b"previous\n")

    def interrupt(_fd: int) -> None:
        raise KeyboardInterrupt("simulated kill during fsync")

    monkeypatch.setattr("artifacts.atomic.os.fsync", interrupt)

    with pytest.raises(KeyboardInterrupt):
        write_bytes_atomic(destination, b"replacement\n")

    assert destination.read_bytes() == b"previous\n"
    assert list(tmp_path.iterdir()) == [destination]


def test_interrupted_first_write_publishes_no_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "manifest.json"

    def interrupt(_fd: int) -> None:
        raise KeyboardInterrupt("simulated kill during fsync")

    monkeypatch.setattr("artifacts.atomic.os.fsync", interrupt)

    with pytest.raises(KeyboardInterrupt):
        write_bytes_atomic(destination, b"complete\n")

    assert list(tmp_path.iterdir()) == []


def test_interrupted_promotion_copy_publishes_nothing_and_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "metrics.json"
    source.write_bytes(PAYLOAD)
    baseline = tmp_path / "baseline"
    destination = baseline / "metrics-v1"

    def partial_copy(_src: object, dst: object, *args: object, **kwargs: object) -> None:
        Path(str(dst)).write_bytes(PAYLOAD[:5])
        raise KeyboardInterrupt("simulated kill during copy")

    monkeypatch.setattr("artifacts.promotion.shutil.copy2", partial_copy)
    with pytest.raises(KeyboardInterrupt):
        promote_to_baseline(source, destination, _manifest(), validate=_accept)

    assert not destination.exists()
    assert list(baseline.iterdir()) == []
    assert source.read_bytes() == PAYLOAD

    monkeypatch.undo()
    promote_to_baseline(source, destination, _manifest(), validate=_accept)
    assert (destination / "payload").read_bytes() == PAYLOAD


def test_disk_full_during_atomic_write_keeps_previous_and_removes_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "metrics.json"
    destination.write_bytes(b"previous\n")

    def full_disk_fdopen(fd: int, mode: str = "rb") -> _FullDisk:
        os.close(fd)
        return _FullDisk()

    monkeypatch.setattr("artifacts.atomic.os.fdopen", full_disk_fdopen)

    with pytest.raises(OSError) as info:
        write_bytes_atomic(destination, b"replacement\n")

    assert info.value.errno == errno.ENOSPC
    assert destination.read_bytes() == b"previous\n"
    assert list(tmp_path.iterdir()) == [destination]


def test_disk_full_during_directory_promotion_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    baseline = tmp_path / "baseline"
    destination = baseline / "candidate-v1"

    def full_disk_copytree(src: object, dst: object, *args: object, **kwargs: object) -> None:
        Path(str(dst)).mkdir()
        (Path(str(dst)) / "metrics.json").write_bytes(PAYLOAD[:4])
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr("artifacts.promotion.shutil.copytree", full_disk_copytree)

    with pytest.raises(OSError) as info:
        promote_to_baseline(source, destination, _manifest(), validate=_accept)

    assert info.value.errno == errno.ENOSPC
    assert not destination.exists()
    assert list(baseline.iterdir()) == []
    assert (source / "metrics.json").read_bytes() == PAYLOAD


def test_duplicate_publish_keeps_first_copy_and_identical_payload_identity(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    first = tmp_path / "baseline" / "candidate-v1"
    promote_to_baseline(source, first, _manifest(), validate=_accept)
    before = _tree_snapshot(first)

    with pytest.raises(FileExistsError):
        promote_to_baseline(source, first, _manifest(), validate=_accept)

    assert _tree_snapshot(first) == before
    second = tmp_path / "baseline" / "candidate-copy"
    promote_to_baseline(source, second, _manifest(), validate=_accept)
    first_promotion = ArtifactManifest.read(first / "manifest.json").provenance["promotion"]
    second_promotion = ArtifactManifest.read(second / "manifest.json").provenance["promotion"]
    assert first_promotion["payload_sha256"] == second_promotion["payload_sha256"]
    assert _tree_snapshot(second)["payload/metrics.json"] == PAYLOAD


def test_concurrent_publish_to_same_identity_path_has_exactly_one_winner(tmp_path: Path) -> None:
    destination = tmp_path / "baseline" / "candidate-v1"
    sources = [
        _source(tmp_path / "attempt_a", b'{"net_return": 0.12}\n'),
        _source(tmp_path / "attempt_b", b'{"net_return": -0.40}\n'),
    ]
    barrier = threading.Barrier(2, timeout=10)

    def validate(staged: Path) -> BaselineValidation:
        # Both attempts pass the destination check and finish staging before either renames.
        barrier.wait()
        return _accept(staged)

    def publish(source: Path) -> Path:
        return promote_to_baseline(source, destination, _manifest(), validate=validate)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish, source) for source in sources]
    errors = [future.exception() for future in futures]

    winners = [source for source, error in zip(sources, errors, strict=True) if error is None]
    losers = [error for error in errors if error is not None]
    assert len(winners) == 1
    assert len(losers) == 1
    assert isinstance(losers[0], FileExistsError)
    assert (destination / "payload" / "metrics.json").read_bytes() == (
        winners[0] / "metrics.json"
    ).read_bytes()
    assert sorted(path.name for path in (tmp_path / "baseline").iterdir()) == ["candidate-v1"]


def test_recovery_after_interrupted_publish_succeeds_past_stale_staging(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    baseline = tmp_path / "baseline"
    destination = baseline / "candidate-v1"

    def crash(_: Path) -> BaselineValidation:
        raise KeyboardInterrupt("simulated crash during validation")

    with pytest.raises(KeyboardInterrupt):
        promote_to_baseline(source, destination, _manifest(), validate=crash)
    assert not destination.exists()

    # A hard kill skips cleanup, so leave staging debris from the crashed attempt.
    stale = baseline / ".candidate-v1.stale" / "promotion"
    stale.mkdir(parents=True)
    (stale / "payload").write_bytes(b"partial")

    promote_to_baseline(source, destination, _manifest(), validate=_accept)

    assert (destination / "payload" / "metrics.json").read_bytes() == PAYLOAD
    assert sorted(path.name for path in destination.iterdir()) == ["manifest.json", "payload"]


def test_staging_is_created_on_the_destination_filesystem(tmp_path: Path) -> None:
    observed: dict[str, bool] = {}
    destination = tmp_path / "baseline" / "candidate-v1"

    def validate(path: Path) -> BaselineValidation:
        observed["under_destination_parent"] = path.resolve().is_relative_to(
            destination.parent.resolve()
        )
        observed["same_device"] = path.stat().st_dev == destination.parent.stat().st_dev
        return _accept(path)

    promote_to_baseline(_source(tmp_path), destination, _manifest(), validate=validate)

    assert observed == {"under_destination_parent": True, "same_device": True}


def test_cross_device_rename_fails_closed_without_partial_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    baseline = tmp_path / "baseline"
    destination = baseline / "candidate-v1"

    def cross_device(_src: object, _dst: object, *args: object, **kwargs: object) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr("artifacts.promotion.os.rename", cross_device)

    with pytest.raises(OSError) as info:
        promote_to_baseline(source, destination, _manifest(), validate=_accept)

    assert info.value.errno == errno.EXDEV
    assert not destination.exists()
    assert list(baseline.iterdir()) == []
    assert (source / "metrics.json").read_bytes() == PAYLOAD


def test_file_index_lists_exact_files_with_sha256_and_resolves_manifest(tmp_path: Path) -> None:
    destination = _published(tmp_path)

    index = json.loads((destination / INDEX_NAME).read_text(encoding="utf-8"))
    assert set(index["files"]) == {"manifest.json", "payload/metrics.json"}
    for relative, entry in index["files"].items():
        assert entry["sha256"] == file_sha256(destination / relative)
        assert entry["size"] == (destination / relative).stat().st_size

    resolved = verify_file_index(destination)
    assert resolved == {relative: destination / relative for relative in index["files"]}
    manifest = ArtifactManifest.read(resolved["manifest.json"])
    assert manifest.artifact_id == "evaluation:offline-store"


def test_rewriting_file_index_is_idempotent(tmp_path: Path) -> None:
    destination = _published(tmp_path)
    first = (destination / INDEX_NAME).read_bytes()

    write_file_index(destination)

    assert (destination / INDEX_NAME).read_bytes() == first
    verify_file_index(destination)


def test_single_flipped_byte_fails_verification_with_typed_error(tmp_path: Path) -> None:
    destination = _published(tmp_path)
    target = destination / "payload" / "metrics.json"
    corrupted = bytearray(target.read_bytes())
    corrupted[0] ^= 0x01
    target.write_bytes(bytes(corrupted))

    with pytest.raises(ArtifactChecksumError, match="payload/metrics.json"):
        verify_file_index(destination)


def test_missing_listed_file_is_refused(tmp_path: Path) -> None:
    destination = _published(tmp_path)
    (destination / "payload" / "metrics.json").unlink()

    with pytest.raises(ArtifactFileMissingError, match="payload/metrics.json"):
        verify_file_index(destination)


def test_unlisted_file_is_refused(tmp_path: Path) -> None:
    destination = _published(tmp_path)
    (destination / "payload" / "extra.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError, match="unlisted"):
        verify_file_index(destination)


def test_missing_file_index_is_refused(tmp_path: Path) -> None:
    destination = _published(tmp_path)
    (destination / INDEX_NAME).unlink()

    with pytest.raises(ArtifactFileMissingError, match=INDEX_NAME):
        verify_file_index(destination)


@pytest.mark.parametrize("listed", ["../outside.json", "/etc/passwd", INDEX_NAME])
def test_index_entries_must_stay_inside_the_artifact(tmp_path: Path, listed: str) -> None:
    destination = _published(tmp_path)
    index = {"schema_version": 1, "files": {listed: {"sha256": "0" * 64, "size": 0}}}
    (destination / INDEX_NAME).write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError):
        verify_file_index(destination)


def test_symbolic_links_are_refused_when_indexing(tmp_path: Path) -> None:
    destination = _published(tmp_path)
    os.symlink(destination / "manifest.json", destination / "payload" / "alias.json")

    with pytest.raises(ArtifactIntegrityError, match="symbolic link"):
        write_file_index(destination)
