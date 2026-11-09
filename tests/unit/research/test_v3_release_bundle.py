from pathlib import Path

from scripts.research.audits.build_v3_release_bundle_manifest import (
    REQUIRED_FILES,
    build_release_bundle,
)


def test_release_bundle_requires_every_canonical_package_file(tmp_path: Path) -> None:
    for name in REQUIRED_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    payload = build_release_bundle(tmp_path, verdict="READY WITH SCIENTIFIC LIMITATIONS")
    assert payload["status"] == "pass"
    assert payload["artifact_count"] == len(REQUIRED_FILES)
