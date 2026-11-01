#!/usr/bin/env python3
"""Check maintained documentation links and package-local guide coverage."""

from __future__ import annotations

import json
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
    "compute/environment/README.md",
    "decisioning/adapters/README.md",
    "experiments/orchestration/README.md",
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
    "integrations/mt5/adapters/README.md",
    "integrations/mt5/cli/README.md",
    "integrations/mt5/domain/README.md",
    "integrations/mt5/robot/README.md",
    "learning/supervised/README.md",
    "live/runtime/README.md",
    "market_data/commands/README.md",
    "models/auxiliary/README.md",
    "models/factory/README.md",
    "models/runtime/README.md",
    "orchestra/commands/README.md",
    "trading/orders/README.md",
    "trading/execution/README.md",
    "trading/risk/README.md",
    "simulation/environment/README.md",
    "simulation/contracts/README.md",
    "simulation/backtest/README.md",
    "simulation/backtest/cross_validation/README.md",
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
    "trading/account/README.md",
    "trading/baselines/README.md",
    "trading/policy/README.md",
    "trading/positions/README.md",
    "trading/strategies/README.md",
    "training/artifacts/README.md",
    "training/configuration/README.md",
    "training/reporting/README.md",
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
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "SUPPORT.md",
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
    "compute/environment/README.md",
    "decisioning/adapters/README.md",
    "experiments/orchestration/README.md",
    "integrations/mt5/adapters/README.md",
    "integrations/mt5/cli/README.md",
    "integrations/mt5/domain/README.md",
    "integrations/mt5/robot/README.md",
    "learning/supervised/README.md",
    "live/runtime/README.md",
    "market_data/commands/README.md",
    "models/auxiliary/README.md",
    "models/factory/README.md",
    "models/runtime/README.md",
    "orchestra/README.md",
    "orchestra/commands/README.md",
    "simulation/backtest/cross_validation/README.md",
    "trading/account/README.md",
    "trading/baselines/README.md",
    "trading/policy/README.md",
    "trading/positions/README.md",
    "trading/strategies/README.md",
    "training/artifacts/README.md",
    "training/configuration/README.md",
    "training/reporting/README.md",
    "tests/README.md",
    "tests/unit/research/README.md",
    "scripts/README.md",
    "scripts/research/analysis/README.md",
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
    if document.suffix == ".ipynb":
        notebook = json.loads(document.read_text(encoding="utf-8"))
        source_lines = [
            source_line
            for cell in notebook.get("cells", [])
            for source_line in (
                "".join(cell.get("source", []))
                if isinstance(cell.get("source", ""), list)
                else str(cell.get("source", ""))
            ).splitlines()
        ]
    else:
        source_lines = document.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(source_lines, 1):
        for match in LINK.finditer(line):
            target = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = (document.parent / unquote(parsed.path)).resolve()
            candidates = (
                path,
                path.with_suffix(".md"),
                path.with_suffix(".ipynb"),
                path.with_suffix(".rst"),
                path / "index.md",
                path / "index.rst",
            )
            if not any(candidate.exists() for candidate in candidates):
                failures.append((line_number, target))
    return failures


def missing_source_paths(document: Path) -> list[tuple[int, str]]:
    """Find stale, explicit source/config paths in maintained prose."""
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
    index = root / "docs/index.md"
    if index.is_file():
        index_text = index.read_text(encoding="utf-8")
        required_sections = (
            "learn/index",
            "framework/index",
            "api/index",
            "research/README",
            "reproduce/index",
            "develop/index",
        )
        if ":glob:" in index_text:
            errors.append("docs/index.md: root navigation must use explicit page references")
        for section in required_sections:
            if section not in index_text:
                errors.append(f"docs/index.md: missing primary destination {section}")
        if "../operations/README" not in (root / "docs/develop/index.md").read_text(
            encoding="utf-8"
        ):
            errors.append("docs/develop/index.md: operations portal is not reachable from Develop")
    for notebook in sorted(
        path for path in (root / "docs").rglob("*.ipynb") if "_build" not in path.parts
    ):
        for line_number, target in broken_links(notebook):
            errors.append(
                f"{notebook.relative_to(root)}:{line_number}: missing local link {target}"
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
