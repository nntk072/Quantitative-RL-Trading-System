#!/usr/bin/env python3
"""Generate or validate the human-facing documentation page inventory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
OUTPUT = DOCS / "documentation_inventory.json"
LINK_PATTERN = re.compile(r"!??\[[^\]]*\]\(([^)]+)\)")
TOCTREE_PATTERN = re.compile(r"```\{toctree\}([^`]*)```", re.DOTALL)
GENERATED_PARTS = {"generated", "_build"}


def source_text(path: Path) -> tuple[str, dict[str, Any]]:
    """Return searchable source text and notebook metadata for a page."""
    if path.suffix == ".ipynb":
        notebook = json.loads(path.read_text(encoding="utf-8"))
        sources = [
            "".join(cell.get("source", []))
            if isinstance(cell.get("source", ""), list)
            else str(cell.get("source", ""))
            for cell in notebook.get("cells", [])
        ]
        return "\n".join(sources), notebook.get("metadata", {})
    return path.read_text(encoding="utf-8"), {}


def document_paths() -> tuple[Path, ...]:
    """Return maintained Markdown and notebook pages, excluding generated API."""
    return tuple(
        sorted(
            path
            for path in DOCS.rglob("*")
            if path.is_file()
            and path.suffix in {".md", ".ipynb"}
            and not GENERATED_PARTS.intersection(path.parts)
        )
    )


def resolve_docname(source: Path, reference: str) -> Path | None:
    """Resolve an extensionless toctree document reference when it exists."""
    token = reference.strip().split(maxsplit=1)[0]
    if not token or token.startswith("_") or token.startswith("http"):
        return None
    candidate = (source.parent / token).resolve()
    options = [candidate]
    if not candidate.suffix:
        options.extend(candidate.with_suffix(suffix) for suffix in (".md", ".ipynb", ".rst"))
    for option in options:
        if option.is_file():
            return option
    return None


def toctree_targets(path: Path) -> set[Path]:
    """Return document targets referenced by Sphinx toctrees on one page."""
    text, _metadata = source_text(path)
    targets: set[Path] = set()
    for block in TOCTREE_PATTERN.findall(text):
        for line in block.splitlines():
            entry = line.strip()
            if not entry or entry.startswith(":") or entry.startswith("#"):
                continue
            target = resolve_docname(path, entry)
            if target is not None:
                targets.add(target)
    return targets


def toctree_blocks(path: Path) -> list[str]:
    """Return Sphinx toctree directive bodies from one page."""
    text, _metadata = source_text(path)
    return TOCTREE_PATTERN.findall(text)


def primary_navigation_owners() -> dict[Path, set[str]]:
    """Map pages in visible section trees to their primary root navigation."""
    owners: dict[Path, set[str]] = {}
    root_page = DOCS / "index.md"
    labels = {
        "learn": "Learn",
        "framework": "Framework",
        "api": "API",
        "research": "Research",
        "reproduce": "Reproduce",
        "develop": "Develop",
        "operations": "Operations",
    }
    for block in toctree_blocks(root_page):
        if any(line.strip() == ":hidden:" for line in block.splitlines()):
            continue
        entries = [
            resolve_docname(root_page, line.strip())
            for line in block.splitlines()
            if line.strip() and not line.strip().startswith((":", "#"))
        ]
        for entry in (candidate for candidate in entries if candidate is not None):
            section = entry.relative_to(DOCS).parts[0]
            owner = labels.get(section, section.title())
            pending = [entry]
            visited: set[Path] = set()
            while pending:
                page = pending.pop()
                if page in visited:
                    continue
                visited.add(page)
                owners.setdefault(page, set()).add(owner)
                for child_block in toctree_blocks(page):
                    if any(line.strip() == ":hidden:" for line in child_block.splitlines()):
                        continue
                    for line in child_block.splitlines():
                        line_entry = line.strip()
                        if not line_entry or line_entry.startswith((":", "#")):
                            continue
                        target = resolve_docname(page, line_entry)
                        if target is not None:
                            pending.append(target)
    return owners


def local_links(path: Path, text: str) -> list[str]:
    """Return local or external Markdown link targets in one page."""
    links: list[str] = []
    for match in LINK_PATTERN.finditer(text):
        raw = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
        parsed = urlsplit(raw)
        if raw and not parsed.scheme and not parsed.netloc and parsed.path:
            links.append(raw)
        elif raw:
            links.append(raw)
    return links


def title_for(path: Path, text: str, metadata: dict[str, Any]) -> str:
    """Return a page title from notebook metadata or the first Markdown heading."""
    notebook_title = metadata.get("title")
    if isinstance(notebook_title, str) and notebook_title.strip():
        return notebook_title.strip()
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ").title()


def page_type(path: Path) -> str:
    """Classify a page by its reader-facing role."""
    parts = path.relative_to(DOCS).parts
    if path.suffix == ".ipynb":
        return "reproduction" if parts[0] == "reproduce" else "tutorial"
    if parts[0] == "api":
        return "reference"
    if parts[0] == "research":
        return "research"
    if parts[0] == "reproduce":
        return "reproduction"
    if parts[0] in {"how-to", "develop", "development"}:
        return "developer" if parts[0] != "how-to" else "how-to"
    if parts[0] == "operations":
        return "operations"
    if parts[0] in {"concepts", "framework"}:
        return "explanation"
    if parts[0] == "reference":
        return "reference"
    if parts[0] == "tutorials":
        return "tutorial"
    return "developer"


def page_status(path: Path) -> str:
    """Classify operational and historical pages separately from current guides."""
    relative = path.relative_to(DOCS).as_posix()
    if "migrations/" in relative or relative.startswith("internal_page_index"):
        return "historical/internal"
    if relative.startswith("operations/research_execution_plan"):
        return "operational/current queue"
    if relative.startswith("operations/"):
        return "operational"
    if relative.startswith("research/"):
        return "research status is stated on page"
    return "current"


def build_inventory() -> dict[str, Any]:
    """Build a deterministic inventory with page role, links, and orphan status."""
    paths = document_paths()
    tree_targets = {target for source in paths for target in toctree_targets(source)}
    owners = primary_navigation_owners()
    pages: list[dict[str, Any]] = []
    for path in paths:
        text, metadata = source_text(path)
        relative = path.relative_to(ROOT).as_posix()
        section = path.relative_to(DOCS).parts[0] if path.parent != DOCS else "home"
        pages.append(
            {
                "path": relative,
                "title": title_for(path, text, metadata),
                "section": section,
                "type": page_type(path),
                "status": page_status(path),
                "links": local_links(path, text),
                "orphan_status": "orphan"
                if path not in tree_targets and path != DOCS / "index.md"
                else "in toctree",
                "primary_navigation_owner": sorted(owners.get(path, set())),
            }
        )
    return {"schema_version": 1, "page_count": len(pages), "pages": pages}


def main() -> int:
    """Write the current inventory or fail when the committed file is stale."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build_inventory(), indent=2, sort_keys=True) + "\n"
    if args.write:
        OUTPUT.write_text(expected, encoding="utf-8")
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
        return 0
    actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if actual != expected:
        print(
            f"{OUTPUT.relative_to(ROOT)} is stale; run python -m tools.documentation.inventory --write"
        )
        return 1
    report = json.loads(actual)
    orphans = [page["path"] for page in report["pages"] if page["orphan_status"] == "orphan"]
    if orphans:
        print("Documentation inventory contains orphan pages:")
        for path in orphans:
            print(f"- {path}")
        return 1
    duplicates = [
        page["path"]
        for page in report["pages"]
        if len(page.get("primary_navigation_owner", [])) > 1
    ]
    if duplicates:
        print("Documentation pages have multiple primary navigation owners:")
        for path in duplicates:
            print(f"- {path}")
        return 1
    print(f"Documentation inventory is current ({report['page_count']} pages; no orphans).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
