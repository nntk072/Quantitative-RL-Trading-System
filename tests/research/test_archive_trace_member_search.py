from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from scripts.research.analysis.evidence.search_archive_trace_members import (
    scan_archive_roots,
)


def test_archive_trace_search_reports_matching_member_names(tmp_path: Path) -> None:
    archive_path = tmp_path / "run.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("training/trade_setup_decisions.csv", "decision_id\n")
        archive.writestr("model/ppo_final.zip", "checkpoint")

    report = scan_archive_roots([tmp_path])

    assert report["archive_count"] == 1
    assert report["readable_archive_count"] == 1
    assert report["member_count"] == 2
    assert report["matching_member_count"] == 1
    assert report["matches"] == [
        {
            "archive": str(archive_path.resolve()),
            "member": "training/trade_setup_decisions.csv",
        }
    ]
    assert report["archive_contents_hashed"] is False
    assert report["member_contents_extracted"] is False


def test_archive_trace_search_records_unreadable_zip_files(tmp_path: Path) -> None:
    (tmp_path / "empty_checkpoint.zip").touch()

    report = scan_archive_roots([tmp_path])

    assert report["archive_count"] == 1
    assert report["readable_archive_count"] == 0
    assert report["unreadable_archive_count"] == 1
    archive = report["archives"][0]
    assert archive["read_status"] == "unreadable"
    assert archive["size_bytes"] == 0


def test_archive_trace_search_does_not_follow_nested_directory_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    with ZipFile(external / "external.zip", "w") as archive:
        archive.writestr("candidate_to_action.csv", "candidate,action\n")
    link = root / "linked_archive"
    link.symlink_to(external, target_is_directory=True)

    report = scan_archive_roots([root])

    assert report["archive_count"] == 0
    assert report["directory_symlinks_followed"] is False
