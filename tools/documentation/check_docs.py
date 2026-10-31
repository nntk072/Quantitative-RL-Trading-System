#!/usr/bin/env python3
"""Check maintained documentation links and package-local guide coverage."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = (
    "configuration",
    "artifacts",
    "market_data",
    "features",
    "trading",
    "decisioning",
    "simulation",
    "models",
    "learning",
    "training",
    "evaluation",
    "experiments",
    "live",
    "integrations",
    "compute",
    "orchestra",
)
SUBPACKAGE_GUIDES = (
    "scripts/research/analysis/README.md",
    "scripts/research/thesis/README.md",
    "market_data/loading/README.md",
    "market_data/cache/README.md",
    "market_data/transforms/README.md",
    "market_data/splits/README.md",
    "features/context/README.md",
    "features/pipeline/README.md",
    "features/technical/README.md",
    "features/po3/README.md",
    "compute/slurm/README.md",
    "integrations/mt5/README.md",
    "trading/orders/README.md",
    "trading/execution/README.md",
    "trading/risk/README.md",
    "simulation/environment/README.md",
    "simulation/contracts/README.md",
    "simulation/backtest/README.md",
    "models/encoders/README.md",
    "learning/rl/README.md",
    "training/runner/README.md",
    "training/setup/README.md",
    "training/callbacks/README.md",
    "evaluation/rollout/README.md",
    "evaluation/reporting/README.md",
    "evaluation/plotting/README.md",
    "evaluation/reanalysis/README.md",
    "experiments/variants/README.md",
    "experiments/runs/README.md",
)
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
INLINE_CODE = re.compile(r"`([^`]+)`")
SOURCE_ROOTS = (
    ".agents/",
    "artifacts/",
    "compute/",
    "config/",
    "configuration/",
    "decisioning/",
    "evaluation/",
    "experiments/",
    "features/",
    "integrations/",
    "learning/",
    "live/",
    "market_data/",
    "models/",
    "orchestra/",
    "scripts/",
    "simulation/",
    "tests/",
    "tools/",
    "trading/",
    "training/",
)
SOURCE_SUFFIXES = {".py", ".sh", ".toml", ".yaml", ".yml"}
MAINTAINED_DOCS = (
    "README.md",
    "AGENTS.md",
    "docs",
    ".agents",
    "configuration/README.md",
    "artifacts/README.md",
    "market_data/README.md",
    "market_data/loading/README.md",
    "market_data/cache/README.md",
    "market_data/transforms/README.md",
    "market_data/splits/README.md",
    "features/README.md",
    "features/context/README.md",
    "features/pipeline/README.md",
    "features/technical/README.md",
    "features/po3/README.md",
    "trading/orders/README.md",
    "trading/execution/README.md",
    "trading/risk/README.md",
    "trading/README.md",
    "decisioning/README.md",
    "simulation/README.md",
    "simulation/environment/README.md",
    "simulation/contracts/README.md",
    "simulation/backtest/README.md",
    "models/README.md",
    "models/encoders/README.md",
    "learning/README.md",
    "learning/rl/README.md",
    "training/README.md",
    "training/runner/README.md",
    "training/setup/README.md",
    "training/callbacks/README.md",
    "evaluation/README.md",
    "evaluation/metrics/README.md",
    "evaluation/rollout/README.md",
    "evaluation/reporting/README.md",
    "evaluation/plotting/README.md",
    "evaluation/reanalysis/README.md",
    "experiments/README.md",
    "experiments/variants/README.md",
    "experiments/runs/README.md",
    "live/README.md",
    "integrations/README.md",
    "integrations/mt5/README.md",
    "compute/README.md",
    "compute/slurm/README.md",
    "orchestra/README.md",
    "tests/README.md",
    "tests/unit/research/README.md",
    "scripts/README.md",
    "scripts/research/analysis/README.md",
    "scripts/research/thesis/README.md",
)


def maintained_markdown(root: Path) -> tuple[Path, ...]:
    """Return curated documentation, excluding machine evidence snapshots."""
    paths: set[Path] = set()
    for item in MAINTAINED_DOCS:
        candidate = root / item
        if candidate.is_file() and candidate.suffix.lower() == ".md":
            paths.add(candidate)
        elif candidate.is_dir():
            paths.update(path for path in candidate.rglob("*.md"))
    return tuple(sorted(paths))


def broken_links(document: Path) -> list[tuple[int, str]]:
    """Find missing relative targets; external and fragment-only links are skipped."""
    failures: list[tuple[int, str]] = []
    for line_number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
        for match in LINK.finditer(line):
            target = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = (document.parent / unquote(parsed.path)).resolve()
            if not path.exists():
                failures.append((line_number, target))
    return failures


def missing_source_paths(document: Path) -> list[tuple[int, str]]:
    """Find stale, explicit source/config paths in maintained prose."""
    if document.is_relative_to(ROOT / "docs/thesis"):
        # These records preserve paths as observed when historical evidence
        # was produced; do not rewrite their provenance during doc cleanup.
        return []
    failures: list[tuple[int, str]] = []
    for line_number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
        for match in INLINE_CODE.finditer(line):
            token = match.group(1).strip().split(maxsplit=1)[0].rstrip(".,;)")
            token = token.split("::", maxsplit=1)[0]
            if ":" in token:
                token = token.split(":", maxsplit=1)[0]
            if (
                token.startswith(SOURCE_ROOTS)
                and not any(marker in token for marker in ("<", ">", "*", "{"))
                and Path(token).suffix in SOURCE_SUFFIXES
                and not (ROOT / token).exists()
            ):
                failures.append((line_number, token))
    return failures


def validate(root: Path) -> list[str]:
    """Return documentation contract failures for a repository tree."""
    errors: list[str] = []
    for package in PACKAGES:
        readme = root / package / "README.md"
        if not readme.is_file():
            errors.append(f"missing package guide: {readme.relative_to(root)}")
    for guide in SUBPACKAGE_GUIDES:
        if not (root / guide).is_file():
            errors.append(f"missing subpackage guide: {guide}")
    for document in maintained_markdown(root):
        for line_number, target in broken_links(document):
            errors.append(
                f"{document.relative_to(root)}:{line_number}: missing local link {target}"
            )
        for line_number, target in missing_source_paths(document):
            errors.append(
                f"{document.relative_to(root)}:{line_number}: missing source path {target}"
            )
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        print("Documentation checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Documentation links and package guides are valid ({len(maintained_markdown(ROOT))} pages)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
