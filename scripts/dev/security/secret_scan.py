#!/usr/bin/env python3
"""Scan Git-visible repository text, excluding generated research tables."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCANNER_VERSION = "1.5.0"
DISABLED_PLUGINS = ("Base64HighEntropyString", "HexHighEntropyString")
RESEARCH_TABLE_SUFFIXES = frozenset({".csv", ".parquet"})


def _generated_research_table_exclusion() -> tuple[str | None, int]:
    """Build a scanner exclusion for generated CSV/Parquet research tables.

    Args:
        None.

    Returns:
        A path regex and the number of matching files, or ``(None, 0)``.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "evidence/research"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = [entry.decode("utf-8") for entry in result.stdout.split(b"\0") if entry]
    excluded = []
    for relative in paths:
        path = ROOT / relative
        if path.suffix.lower() in RESEARCH_TABLE_SUFFIXES:
            excluded.append(relative)
    if not excluded:
        return None, 0
    return r"^evidence/research/.*\.(?:csv|parquet)$", len(excluded)


def uv_command() -> str:
    configured = os.environ.get("UV_BIN") or os.environ.get("QRL_UV")
    command = configured or shutil.which("uv")
    if not command:
        raise RuntimeError("uv is required to run the isolated secret scanner")
    return command


def _scanner_core_count() -> int:
    """Limit scanner workers to CPUs available to this process."""
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:
        return max(1, os.cpu_count() or 1)


def findings_from_baseline(payload: Any) -> list[tuple[str, int, str]]:
    """Return safe finding metadata without exposing matched secret values."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), dict):
        raise ValueError("detect-secrets returned JSON without a results mapping")
    findings: list[tuple[str, int, str]] = []
    for filename, entries in payload["results"].items():
        if not isinstance(filename, str) or not isinstance(entries, list):
            raise ValueError("detect-secrets result entries have an invalid shape")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("detect-secrets finding must be an object")
            line = entry.get("line_number")
            detector = entry.get("type")
            if not isinstance(line, int) or not isinstance(detector, str):
                raise ValueError(
                    f"detect-secrets finding in {filename} lacks safe location metadata"
                )
            findings.append((filename, line, detector))
    return findings


def main() -> int:
    command = [
        uv_command(),
        "tool",
        "run",
        "--from",
        f"detect-secrets=={SCANNER_VERSION}",
        "detect-secrets",
        "-c",
        str(_scanner_core_count()),
        "scan",
    ]
    for plugin in DISABLED_PLUGINS:
        command.extend(("--disable-plugin", plugin))
    exclusion_pattern, excluded_count = _generated_research_table_exclusion()
    if exclusion_pattern:
        command.extend(("--exclude-files", exclusion_pattern))
        print(
            f"Excluding {excluded_count} generated research CSV/Parquet tables; source, configs, "
            "docs, tests, and evidence metadata remain scanned."
        )
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        print(f"detect-secrets failed with exit code {result.returncode}.", file=sys.stderr)
        return result.returncode or 2
    try:
        payload = json.loads(result.stdout)
        findings = findings_from_baseline(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Could not interpret detect-secrets output: {exc}", file=sys.stderr)
        return 2
    if findings:
        print(f"Credential secret scan found {len(findings)} finding(s):", file=sys.stderr)
        for filename, line, detector in findings:
            print(f"  {filename}:{line} [{detector}]", file=sys.stderr)
        print(
            "Review findings and use an inline allowlist only for confirmed fixtures.",
            file=sys.stderr,
        )
        return 1
    print("Credential secret scan passed; entropy-only Base64 and Hex detectors are disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
