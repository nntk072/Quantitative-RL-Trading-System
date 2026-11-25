#!/usr/bin/env python3
"""Check product Python modules against the maintained source-size limit."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_PACKAGES = (
    "configuration",
    "artifacts",
    "market_data",
    "features",
    "trading",
    "simulation",
    "models",
    "decisioning",
    "learning",
    "training",
    "evaluation",
    "experiments",
    "live",
    "integrations",
    "compute",
)
_EXCEPTION_HEADER = re.compile(r"^##\s+module size exceptions\s*$", re.IGNORECASE)
_TABLE_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*$")


def _documented_exceptions(readme: Path) -> dict[str, str]:
    """Read explicit module reasons from a README's Module size exceptions section."""
    lines = readme.read_text(encoding="utf-8").splitlines()
    in_section = False
    exceptions: dict[str, str] = {}
    for line in lines:
        if line.startswith("## "):
            in_section = bool(_EXCEPTION_HEADER.fullmatch(line.strip()))
            continue
        if not in_section:
            continue
        match = _TABLE_ROW.fullmatch(line.strip())
        if match:
            module, reason = match.groups()
            reason = reason.strip()
            if len(reason) >= 20 and not reason.lower().startswith(("todo", "tbd", "reason")):
                exceptions[Path(module).as_posix()] = reason
    return exceptions


def _has_documented_reason(module: Path, package_root: Path) -> bool:
    """Return whether the nearest package README records this module's reason."""
    for directory in (module.parent, *module.parent.parents):
        if not directory.is_relative_to(package_root):
            break
        relative_module = module.relative_to(directory).as_posix()
        for name in ("README.md", "README.rst"):
            readme = directory / name
            if readme.is_file() and relative_module in _documented_exceptions(readme):
                return True
    return False


def find_oversized_modules(
    root: Path = ROOT,
    *,
    max_lines: int = 1000,
    packages: tuple[str, ...] = PRODUCT_PACKAGES,
) -> list[tuple[str, int]]:
    """Return product modules above the limit without a README reason."""
    oversized: list[tuple[str, int]] = []
    for package in packages:
        package_root = root / package
        if not package_root.is_dir():
            continue
        for module in sorted(package_root.rglob("*.py")):
            line_count = len(module.read_text(encoding="utf-8").splitlines())
            if line_count > max_lines and not _has_documented_reason(module, package_root):
                oversized.append((module.relative_to(root).as_posix(), line_count))
    return oversized


def main() -> int:
    """Print unexcepted oversized modules and return a CI-friendly status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--max-lines", type=int, default=1000, help="maximum source lines")
    arguments = parser.parse_args()
    oversized = find_oversized_modules(arguments.root, max_lines=arguments.max_lines)
    if oversized:
        print(f"Python modules exceed {arguments.max_lines} lines without a README reason:")
        for path, line_count in oversized:
            print(f"  {path}: {line_count} lines")
        return 1
    print(f"All product Python modules are at most {arguments.max_lines} lines or documented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
