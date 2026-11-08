#!/usr/bin/env python3
"""Scan Git-visible repository files for credential-like secrets."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCANNER_VERSION = "1.5.0"
DISABLED_PLUGINS = ("Base64HighEntropyString", "HexHighEntropyString")
MAX_RESEARCH_TABLE_BYTES = 8 * 1024 * 1024
CANDIDATE_ACTION_IDENTITY_PATH = (
    "evidence/research/candidate_action_linkage/unmatched_baseline_candidate_actions.csv"
)
CANDIDATE_EVENT_ID_VERSION = "trade-setup-event-identity-v3"
TELEGRAM_TOKEN_PATTERN = re.compile(r"\d{8,10}:[0-9A-Za-z_-]{35}")
EVENT_FIELD_PATTERN = re.compile(r"[A-Za-z0-9_-]+\Z")


def oversized_research_table_exclusion() -> tuple[str | None, int]:
    """Build a scanner exclusion for oversized generated CSV/Parquet evidence.

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
        if path.suffix.lower() not in {".csv", ".parquet"}:
            continue
        if path.stat().st_size > MAX_RESEARCH_TABLE_BYTES:
            excluded.append(relative)
    if not excluded:
        return None, 0
    pattern = "^(?:" + "|".join(re.escape(path) for path in sorted(excluded)) + ")$"
    return pattern, len(excluded)


def validate_candidate_action_identity_false_positives(path: Path) -> int:
    """Validate Telegram-shaped matches produced by timestamp/field-name boundaries.

    Args:
        path: Generated candidate-action CSV.

    Returns:
        Number of matches explained by the deterministic event identity format.
    """
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "trade_setup_source_event_id" not in (reader.fieldnames or []):
            raise ValueError("candidate-action identity CSV is missing its identity column")
        for line, row in enumerate(reader, start=2):
            source = row.get("trade_setup_source_event_id") or ""
            matches = list(TELEGRAM_TOKEN_PATTERN.finditer(source))
            for field, value in row.items():
                if (
                    field != "trade_setup_source_event_id"
                    and value
                    and TELEGRAM_TOKEN_PATTERN.search(value)
                ):
                    raise ValueError(f"unexpected Telegram-shaped value at {path}:{line}")
            if not matches:
                continue
            parts = source.split(":", maxsplit=4)
            if len(parts) != 5 or parts[0] != CANDIDATE_EVENT_ID_VERSION:
                raise ValueError(f"unrecognized generated event identity at {path}:{line}")
            pairs = []
            cursor = len(":".join(parts[:4])) + 1
            for pair in parts[4].split(":"):
                field, separator, value = pair.partition("=")
                if not separator or not EVENT_FIELD_PATTERN.fullmatch(field) or not value.isdigit():
                    raise ValueError(f"malformed generated timestamp identity at {path}:{line}")
                value_end = cursor + len(pair)
                pairs.append((field, value, value_end))
                cursor += len(pair) + 1
            for match in matches:
                explained = False
                for previous, following in zip(pairs, pairs[1:]):
                    _, previous_value, previous_end = previous
                    next_field = following[0]
                    if len(next_field) < 35:
                        continue
                    for digits in range(8, 11):
                        expected = f"{previous_value[-digits:]}:{next_field[:35]}"
                        if match.start() == previous_end - digits and match.group(0) == expected:
                            explained = True
                            break
                    if explained:
                        break
                if not explained:
                    raise ValueError(f"unexplained Telegram-shaped match at {path}:{line}")
                count += 1
    return count


def uv_command() -> str:
    configured = os.environ.get("UV_BIN") or os.environ.get("QRL_UV")
    command = configured or shutil.which("uv")
    if not command:
        raise RuntimeError("uv is required to run the isolated secret scanner")
    return command


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
        "scan",
    ]
    for plugin in DISABLED_PLUGINS:
        command.extend(("--disable-plugin", plugin))
    exclusion_pattern, excluded_count = oversized_research_table_exclusion()
    identity_path = ROOT / CANDIDATE_ACTION_IDENTITY_PATH
    identity_matches = validate_candidate_action_identity_false_positives(identity_path)
    if identity_matches:
        exact_path = re.escape(CANDIDATE_ACTION_IDENTITY_PATH)
        if exclusion_pattern:
            inner = exclusion_pattern.removeprefix("^(?:").removesuffix(")$")
            exclusion_pattern = f"^(?:{inner}|{exact_path})$"
        else:
            exclusion_pattern = f"^{exact_path}$"
        excluded_count += 1
    if exclusion_pattern:
        command.extend(("--exclude-files", exclusion_pattern))
        print(
            f"Excluding {excluded_count} generated research evidence files from the primary scan."
        )
        if identity_matches:
            print(
                f"Validated {identity_matches} Telegram-shaped timestamp/field-boundary matches; "
                "other detectors still scan the CSV."
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
    if identity_matches:
        identity_command = [
            uv_command(),
            "tool",
            "run",
            "--from",
            f"detect-secrets=={SCANNER_VERSION}",
            "detect-secrets",
            "scan",
        ]
        for plugin in (*DISABLED_PLUGINS, "TelegramBotTokenDetector"):
            identity_command.extend(("--disable-plugin", plugin))
        identity_command.append(CANDIDATE_ACTION_IDENTITY_PATH)
        identity_result = subprocess.run(
            identity_command, cwd=ROOT, check=False, capture_output=True, text=True
        )
        if identity_result.returncode != 0:
            print(identity_result.stderr, file=sys.stderr, end="")
            print("Secondary event-identity scan failed.", file=sys.stderr)
            return identity_result.returncode or 2
        try:
            identity_payload = json.loads(identity_result.stdout)
            findings.extend(findings_from_baseline(identity_payload))
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"Could not interpret event-identity scan output: {exc}", file=sys.stderr)
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
