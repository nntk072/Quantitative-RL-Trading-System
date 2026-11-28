"""Run opt-in local analyzers and retain normalized findings and native reports."""

from __future__ import annotations

import os
import site
import tomllib
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

from tools.quality.coverage_report import PRODUCT_PACKAGES
from tools.quality.local_checks.normalization import (
    classify_pypi_scope,
    make_quality_finding,
    partition_partial_report,
    read_analyzer_report,
)
from tools.quality.local_checks.run_evidence import (
    HERE,
    ROOT,
    quality_executable,
    quality_source_paths,
    read_quality_json,
    run_quality_process,
    write_quality_json,
)

ANALYZERS = (
    "ruff",
    "mypy",
    "bandit",
    "semgrep",
    "vulture",
    "radon",
    "xenon",
    "actionlint",
    "shellcheck",
    "hadolint",
    "sqlfluff",
    "pip-audit",
    "gitleaks",
    "osv-scanner",
    "checkov",
    "trivy",
    "codeql",
    "coverity",
)


def publish_analyzer_findings(out: Path, tool: str, rows: list[dict[str, Any]]) -> None:
    """Save normalized records and a SARIF view with explicit unknown severity."""
    write_quality_json(out / f"{tool}-findings.json", rows)
    results = []
    for row in rows:
        item: dict[str, Any] = {
            "ruleId": row["checker"],
            "message": {"text": row["message"] or row["checker"]},
            "partialFingerprints": {"qrlFingerprint": row["fingerprint"]},
        }
        severity = row.get("severity")
        if severity in {"critical", "high", "error"}:
            item["level"] = "error"
        elif severity in {"medium", "warning"}:
            item["level"] = "warning"
        elif severity in {"low", "info", "note"}:
            item["level"] = "note"
        if row.get("file"):
            loc: dict[str, Any] = {"artifactLocation": {"uri": row["file"]}}
            if row.get("line"):
                loc["region"] = {"startLine": row["line"]}
            item["locations"] = [{"physicalLocation": loc}]
        results.append(item)
    write_quality_json(
        out / f"{tool}.sarif",
        {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [{"tool": {"driver": {"name": tool}}, "results": results}],
        },
    )


def quality_tool_doctor(out: Path, timeout: int, probe: bool) -> dict[str, Any]:
    """Report availability and optional version probes, never install tools."""
    names = sorted(
        set(ANALYZERS)
        | {
            "cov-analyze",
            "cov-format-errors",
            "cov-manage-emit",
            "mutmut",
            "uv",
            "cargo",
            "rustc",
            "cargo-llvm-cov",
            "cargo-nextest",
            "cargo-mutants",
            "cargo-fuzz",
            "cargo-miri",
            "cargo-deny",
            "cargo-audit",
            "clang-tidy",
            "cppcheck",
            "llvm-cov",
            "llvm-profdata",
            "gcov",
            "lcov",
            "compute-sanitizer",
            "npm",
            "sccache",
            "diff-cover",
        }
    )
    tools: dict[str, Any] = {}
    for name in names:
        exe = quality_executable(name)
        row: dict[str, Any] = {"path": exe, "status": "available" if exe else "missing_tool"}
        if exe and probe:
            row["version_probe"] = run_quality_process(
                [exe, "--version"], out / f"{name}-version.log", min(timeout, 15)
            )
        tools[name] = row
    return {
        "status": "ok",
        "tools": tools,
        "qualification": "Availability is not license or hardware verification.",
    }


def _static_commands(out: Path) -> dict[str, tuple[list[str], tuple[int, ...], Path | None]]:
    """Build explicit report-format commands from the current repository inventory."""
    owned = sorted(PRODUCT_PACKAGES)
    files = quality_source_paths()
    shell = [p for p in files if p.endswith(".sh") or p in {"tools/check", "tools/crgraph"}]
    docker = [p for p in files if Path(p).name == "Dockerfile"]
    sql = [p for p in files if p.endswith(".sql")]
    sarif = out / "gitleaks-native.sarif"
    bandit_report = out / "bandit-native.json"
    osv_update = ["--download-offline-databases"] if os.environ.get("QRL_OSV_UPDATE") == "1" else []
    # None means the tool writes to stdout; the caller retains its separate stderr.
    return {
        "ruff": (["ruff", "check", "--output-format", "json", *owned], (1,), None),
        "mypy": (["mypy", "--output", "json", *owned], (1,), None),
        "bandit": (
            ["bandit", "-q", "-r", *owned, "-f", "json", "-o", str(bandit_report)],
            (1,),
            bandit_report,
        ),
        "semgrep": (
            [
                "semgrep",
                "scan",
                "--config",
                str(HERE / "semgrep.yml"),
                "--metrics=off",
                "--disable-version-check",
                "--json",
                "--error",
                *owned,
            ],
            (1,),
            None,
        ),
        "vulture": (["vulture", *owned, "--min-confidence", "80"], (3,), None),
        "radon": (["radon", "cc", "-j", *owned], (), None),
        "xenon": (
            ["xenon", "--max-absolute", "B", "--max-modules", "B", "--max-average", "A", *owned],
            (1,),
            None,
        ),
        "actionlint": (["actionlint", "-format", "{{json .}}"], (1,), None),
        "shellcheck": (["shellcheck", "--format=json", *shell] if shell else [], (1,), None),
        "hadolint": (["hadolint", "--format", "json", *docker] if docker else [], (1,), None),
        "sqlfluff": (
            ["sqlfluff", "lint", "--format", "json", "--dialect", "ansi", *sql] if sql else [],
            (1,),
            None,
        ),
        "pip-audit": (
            [
                "pip-audit",
                "--format",
                "json",
                "--skip-editable",
                *[arg for p in site.getsitepackages() for arg in ("--path", p)],
            ],
            (1,),
            None,
        ),
        "gitleaks": (
            [
                "gitleaks",
                "dir",
                ".",
                "--redact=100",
                "--report-format",
                "sarif",
                "--report-path",
                str(sarif),
            ],
            (1,),
            sarif,
        ),
        "osv-scanner": (
            [
                "osv-scanner",
                "scan",
                "source",
                "--offline",
                *osv_update,
                "--format",
                "json",
                "-L",
                "uv.lock",
            ],
            (1,),
            None,
        ),
        "checkov": (
            ["checkov", "-d", ".", "--skip-download", "--skip-path", "outputs", "-o", "json"],
            (1,),
            None,
        ),
        "trivy": (
            [
                "trivy",
                "fs",
                "--skip-db-update",
                "--skip-java-db-update",
                "--offline-scan",
                "--skip-dirs",
                "outputs",
                "--skip-dirs",
                "data",
                "--format",
                "json",
                "--exit-code",
                "1",
                ".",
            ],
            (1,),
            None,
        ),
    }


def _read_static_findings(tool: str, report: Path, stderr: Path) -> list[dict[str, Any]]:
    """Normalize tool-specific structured results, including advisory complexity diagnostics."""
    if tool == "radon":
        raw = read_quality_json(report)
        result = []
        for path, blocks in raw.items():
            if not isinstance(blocks, list):
                raise ValueError(f"Radon reported an error for {path}")
            for block in blocks:
                if block["complexity"] > 10:
                    result.append(
                        make_quality_finding(
                            tool,
                            "cyclomatic-complexity",
                            f"{block['name']}: complexity {block['complexity']}",
                            ROOT,
                            file=path,
                            line=block["lineno"],
                        )
                    )
        return result
    if tool == "xenon":
        lines = report.read_text().splitlines() + stderr.read_text().splitlines()
        return [
            make_quality_finding(tool, "complexity-budget", line, ROOT)
            for line in lines
            if line.startswith("ERROR:")
        ]
    if tool == "actionlint" and not report.read_text().strip():
        return []
    return read_analyzer_report(tool, report, ROOT)


def run_static_analyzers(out: Path, timeout: int, selected: list[str]) -> dict[str, Any]:
    """Run selected analyzers; malformed reports and incomplete scans fail closed."""
    commands = _static_commands(out)
    if not selected or not set(selected).issubset(commands):
        raise ValueError("Unknown or empty static analyzer selection")
    results: dict[str, Any] = {}
    for tool in dict.fromkeys(selected):
        argv, codes, file_report = commands[tool]
        if not argv:
            results[tool] = {"status": "not_applicable"}
            continue
        log = out / f"{tool}.log"
        row = run_quality_process(argv, log, timeout, findings_codes=codes)
        if row["status"] in {"ok", "findings"}:
            try:
                report = file_report or log
                partial: list[dict[str, Any]] = []
                if tool in {"bandit", "semgrep", "pip-audit"}:
                    raw = read_quality_json(report)
                    usable, partial = partition_partial_report(tool, raw, ROOT)
                    if partial:
                        report = out / f"{tool}-partial-native.json"
                        write_quality_json(report, usable)
                issues = _read_static_findings(tool, report, log.with_suffix(".log.stderr"))
                if row["status"] == "findings" and not issues and not partial:
                    raise ValueError("Nonzero findings exit without normalized findings")
                publish_analyzer_findings(out, tool, issues)
                limited = False
                if tool == "pip-audit" and partial:
                    locked = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
                    installed = {
                        dist.metadata["Name"].lower().replace("_", "-").replace(".", "-"): (
                            dist.version
                        )
                        for dist in distributions(path=site.getsitepackages())
                    }
                    partial = classify_pypi_scope(partial, locked, installed)
                    limited = all(item["scope"] != "unassessed" for item in partial)
                row.update(
                    status="scope_limited"
                    if limited
                    else "incomplete"
                    if partial
                    else "findings"
                    if issues
                    else "ok",
                    findings_count=len(issues),
                    skipped_count=len(partial),
                    skipped=partial,
                )
            except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
                row.update(status="error", error=str(exc), error_type=type(exc).__name__)
        results[tool] = row
    statuses = {row["status"] for row in results.values()}
    return {
        "status": "incomplete"
        if statuses - {"ok", "findings", "not_applicable", "scope_limited"}
        else "scope_limited"
        if "scope_limited" in statuses
        else "findings"
        if "findings" in statuses
        else "ok",
        "tools": results,
    }


def _run_analyzer_stages(
    out: Path, timeout: int, steps: list[tuple[str, list[str]]]
) -> dict[str, Any]:
    """Stop a dependent analyzer pipeline on any failed or unavailable stage."""
    results = {}
    for name, argv in steps:
        results[name] = run_quality_process(argv, out / f"{name}.log", timeout)
        if results[name]["status"] != "ok":
            return {"status": results[name]["status"], "stages": results}
    return {"status": "ok", "stages": results}


def run_local_coverity(
    out: Path, timeout: int, config: Path | None, build: list[str]
) -> dict[str, Any]:
    """Use local capture and analysis only; never submit a captured build or report."""
    idir = out / "coverity-idir"
    report = out / "coverity-native.json"
    if config is None:
        config = out / "coverity-local.yaml"
        config.write_text("{}\n")
    command = ["coverity", "capture", "--dir", str(idir), "--config", str(config.resolve())]
    if build:
        command.extend(["--", *build])
    else:
        command.extend(
            [
                "--language",
                "python",
                "--disable-build-command-inference",
                "--file-include-regex",
                r"^(?:" + "|".join(sorted(PRODUCT_PACKAGES)) + r")/.*\.py$",
            ]
        )
    result = _run_analyzer_stages(
        out,
        timeout,
        [
            ("capture", command),
            ("capture-inventory", ["cov-manage-emit", "--dir", str(idir), "list"]),
            ("analyze", ["cov-analyze", "--dir", str(idir)]),
            ("format", ["cov-format-errors", "--dir", str(idir), "--json-output-v10", str(report)]),
        ],
    )
    if result["status"] != "ok":
        return result
    rows = read_analyzer_report("coverity", report, ROOT)
    publish_analyzer_findings(out, "coverity", rows)
    listed = (out / "capture-inventory.log").read_text(errors="replace").replace("\\", "/")
    expected = [
        p
        for p in quality_source_paths()
        if p.endswith(".py") and p.split("/")[0] in PRODUCT_PACKAGES
    ]
    matched = [p for p in expected if p in listed]
    write_quality_json(
        out / "capture-scope.json", {"expected_python": expected, "listed_python": matched}
    )
    result.update(
        status="incomplete"
        if len(matched) != len(expected) and not build
        else "findings"
        if rows
        else "ok",
        findings_count=len(rows),
        qualification="Capture listing is version-dependent; verify installed analyzer language support.",
    )
    return result


def run_local_codeql(
    out: Path, timeout: int, language: str, query: str, build: str | None, threads: int
) -> dict[str, Any]:
    """Create a local database and run a locally available query suite without uploading."""
    if threads < 1:
        raise ValueError("CodeQL threads must be positive")
    db = out / "codeql-db"
    report = out / "codeql-native.sarif"
    create = [
        "codeql",
        "database",
        "create",
        str(db),
        "--source-root",
        str(ROOT),
        "--language",
        language,
        "--threads",
        str(threads),
    ]
    create += ["--command", build] if build else ["--build-mode=none"]
    result = _run_analyzer_stages(
        out,
        timeout,
        [
            ("create", create),
            (
                "analyze",
                [
                    "codeql",
                    "database",
                    "analyze",
                    str(db),
                    query,
                    "--format=sarifv2.1.0",
                    "--output",
                    str(report),
                    "--threads",
                    str(threads),
                ],
            ),
        ],
    )
    if result["status"] == "ok":
        rows = read_analyzer_report("codeql", report, ROOT)
        publish_analyzer_findings(out, "codeql", rows)
        result.update(status="findings" if rows else "ok", findings_count=len(rows))
    return result
