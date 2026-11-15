#!/usr/bin/env python3
"""Audit the current clean-restart evidence state without reviving old results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/reproduce/evidence_audit.md"
RAW_MANIFEST = ROOT / "evidence/research/data_identity/raw_data_manifest.json"


def render_audit(root: Path = ROOT) -> str:
    """Report retained source identity and make absent empirical results explicit."""
    manifest_path = root / RAW_MANIFEST.relative_to(ROOT)
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        file_count = manifest.get("inventory_file_count", 0)
        byte_count = manifest.get("inventory_total_bytes", 0)
        identity_status = "present"
        identity_detail = f"{file_count} CSV files, {byte_count} bytes"
    else:
        identity_status = "missing"
        identity_detail = "raw CSV identity manifest is absent"
    return "\n".join(
        [
            "# Research evidence audit status",
            "",
            "Historical run outputs and data-derived evidence packets were removed during the 2026-11-15 clean restart. This audit does not carry forward prior numerical results.",
            "",
            "## Retained source identity",
            "",
            f"- Raw-data SHA-256 manifest: **{identity_status}** ({identity_detail})",
            "- Feature-cache compatibility: **not revalidated**",
            "- Refreshed data-quality, simulator, policy-training, and baseline results: **not generated**",
            "",
            "The raw-data manifest establishes file identity only. It does not validate the retained cache, execution semantics, or a scientific claim. Regenerate evidence under the active [research validation protocol](../research/validation_protocol.md).",
            "",
        ]
    )


def main() -> int:
    """Write the audit report or verify its committed copy is current."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render_audit()
    if args.write:
        OUTPUT.write_text(expected, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != expected:
        print(
            f"{OUTPUT.relative_to(ROOT)} is stale; run python -m tools.documentation.evidence_audit --write"
        )
        return 1
    print("Research evidence sufficiency audit is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
