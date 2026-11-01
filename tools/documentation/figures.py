#!/usr/bin/env python3
"""Validate figure provenance, source pages, and image alt text."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/figure_registry.json"
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
IMAGE_SUFFIXES = {".png", ".svg", ".jpg", ".jpeg", ".webp", ".gif"}


def validate() -> list[str]:
    """Return registry, source-page, local-asset, and alt-text failures."""
    data: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    errors: list[str] = []
    ids = [str(entry.get("id", "")) for entry in entries]
    if not ids or len(ids) != len(set(ids)) or "" in ids:
        errors.append("figure registry IDs must be present and unique")
    registered_assets: set[str] = set()
    for entry in entries:
        identity = entry.get("id", "<unknown>")
        for required in ("kind", "source_page", "description", "provenance", "rights"):
            if not str(entry.get(required, "")).strip():
                errors.append(f"{identity}: missing {required}")
        source = ROOT / str(entry.get("source_page", ""))
        if not source.is_file():
            errors.append(f"{identity}: missing source page {entry.get('source_page')}")
        asset = entry.get("asset")
        if asset:
            relative = str(asset)
            registered_assets.add(relative)
            if not (ROOT / relative).is_file():
                errors.append(f"{identity}: missing asset {relative}")
            elif os.path.relpath(ROOT / relative, start=source.parent) not in source.read_text(
                encoding="utf-8"
            ):
                errors.append(f"{identity}: source page does not reference {relative}")
        elif entry.get("kind") != "mermaid":
            errors.append(f"{identity}: non-Mermaid entry must name its asset")

    found_assets: set[str] = set()
    for page in (ROOT / "docs").rglob("*.md"):
        if "_build" in page.parts:
            continue
        for alt_text, target in IMAGE.findall(page.read_text(encoding="utf-8")):
            if not alt_text.strip():
                errors.append(f"{page.relative_to(ROOT)}: image has empty alt text: {target}")
            if Path(target.split("#", maxsplit=1)[0]).suffix.lower() in IMAGE_SUFFIXES:
                image_path = (page.parent / target.split("#", maxsplit=1)[0]).resolve()
                try:
                    relative = image_path.relative_to(ROOT).as_posix()
                except ValueError:
                    errors.append(f"{page.relative_to(ROOT)}: image escapes repository: {target}")
                    continue
                found_assets.add(relative)
                if not image_path.is_file():
                    errors.append(f"{page.relative_to(ROOT)}: missing image asset: {target}")
    for asset in sorted(found_assets - registered_assets):
        errors.append(f"image asset is missing from docs/figure_registry.json: {asset}")
    for asset in sorted(registered_assets - found_assets):
        errors.append(f"registered image is not referenced by maintained Markdown: {asset}")
    return errors


def main() -> int:
    """Print the figure audit result and return a CI-friendly status."""
    errors = validate()
    if errors:
        print("Figure checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    print(f"Figure registry is valid ({len(data['entries'])} figures, no orphan image assets).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
