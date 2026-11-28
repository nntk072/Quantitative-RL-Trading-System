"""Validated normalization for structured local analyzers and diagnostic streams."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree


def _require_report_list(value: Any, label: str) -> list[Any]:
    """Validate a structured list rather than silently discarding malformed data."""
    if not isinstance(value, list):
        raise ValueError(f"Expected list: {label}")
    return value


def _normalize_finding_location(value: Any, root: Path) -> str | None:
    """Normalize repository-relative and file URI locations."""
    if value is None:
        return None
    path = str(value)
    if path.startswith("file:"):
        uri = urlparse(path)
        if uri.netloc not in ("", "localhost"):
            return path
        path = unquote(uri.path)
    resolved = Path(path)
    if resolved.is_absolute() and resolved.is_relative_to(root):
        path = resolved.relative_to(root).as_posix()
    return path


def make_quality_finding(
    tool: str,
    checker: str,
    message: str,
    root: Path,
    *,
    file: Any = None,
    line: Any = None,
    severity: Any = None,
    package: Any = None,
    confidence: Any = None,
    native_id: Any = None,
) -> dict[str, Any]:
    """Use stable report-independent identities; do not copy secret matches."""
    path = _normalize_finding_location(file, root)
    location = line if isinstance(line, int) and not isinstance(line, bool) and line > 0 else None
    fingerprint = hashlib.sha256(
        json.dumps([tool, checker, path, location, package, native_id], sort_keys=True).encode()
    ).hexdigest()
    return {
        "tool": tool,
        "checker": checker,
        "message": message,
        "file": path,
        "line": location,
        "severity": str(severity).lower() if severity else None,
        "confidence": confidence,
        "package": package or (path.split("/")[0] if path else None),
        "finding_id": fingerprint,
        "fingerprint": fingerprint,
        "native_id": native_id,
        "status": "untriaged",
    }


def _normalize_sarif(raw: dict[str, Any], tool: str, root: Path) -> list[dict[str, Any]]:
    """Parse standard SARIF and reject reported execution failure."""
    runs = _require_report_list(raw["runs"], "SARIF runs")
    if not runs or raw.get("version") != "2.1.0":
        raise ValueError("Unsupported SARIF document")
    result = []
    for run in runs:
        if any(v.get("executionSuccessful") is False for v in run.get("invocations", [])):
            raise ValueError("SARIF reports failed analysis")
        for row in _require_report_list(run.get("results", []), "SARIF results"):
            loc = (row.get("locations") or [{}])[0].get("physicalLocation", {})
            result.append(
                make_quality_finding(
                    tool,
                    str(row["ruleId"]),
                    "Potential secret (redacted)" if tool == "gitleaks" else row["message"]["text"],
                    root,
                    file=loc.get("artifactLocation", {}).get("uri"),
                    line=loc.get("region", {}).get("startLine"),
                    severity=row.get("level"),
                    native_id=row.get("partialFingerprints"),
                )
            )
    return result


def partition_partial_report(
    tool: str, raw: dict[str, Any], root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Keep usable findings while separately recording unassessed input.

    The strict normalizers still reject partial input. Callers must mark the
    resulting scan incomplete whenever this partition contains skipped entries.
    """
    result = dict(raw)
    skipped: list[dict[str, Any]] = []
    if tool in {"bandit", "semgrep"}:
        errors = _require_report_list(raw.get("errors", []), "analysis errors")
        for row in errors:
            skipped.append(
                {
                    "file": _normalize_finding_location(row.get("filename", row.get("path")), root),
                    "reason": "analyzer_reported_error",
                }
            )
        result["errors"] = []
    elif tool == "pip-audit":
        dependencies = _require_report_list(raw["dependencies"], "dependencies")
        result["dependencies"] = []
        for row in dependencies:
            if row.get("skip_reason"):
                skipped.append({"package": row["name"], "reason": "dependency_not_assessed"})
            else:
                result["dependencies"].append(row)
    else:
        raise ValueError("Unsupported partial report format")
    return result, skipped


def _source_findings(tool: str, raw: Any, root: Path) -> list[dict[str, Any]]:
    """Normalize supported source diagnostic schemas."""
    result = []
    if tool in {"semgrep", "bandit"}:
        if raw.get("errors"):
            raise ValueError(f"{tool} reported analysis errors")
        raw = raw["results"]
    for row in _require_report_list(raw, tool):
        if tool == "ruff":
            checker, msg, path, line = (
                row["code"],
                row["message"],
                row["filename"],
                row["location"]["row"],
            )
            severity = None
        elif tool == "semgrep":
            checker, msg, path, line = (
                row["check_id"],
                row["extra"]["message"],
                row["path"],
                row["start"]["line"],
            )
            severity = row["extra"].get("severity")
        elif tool == "bandit":
            checker, msg, path, line = (
                row["test_id"],
                row["issue_text"],
                row["filename"],
                row["line_number"],
            )
            severity = row.get("issue_severity")
        elif tool == "mypy":
            checker, msg, path, line = (
                row.get("code") or "diagnostic",
                row["message"],
                row["file"],
                row["line"],
            )
            severity = row["severity"]
        elif tool == "actionlint":
            checker, msg, path, line = row["kind"], row["message"], row["filepath"], row["line"]
            severity = "error"
        else:
            checker, msg, path, line = row["code"], row["message"], row["file"], row["line"]
            severity = row.get("level")
        result.append(
            make_quality_finding(
                tool,
                str(checker),
                str(msg),
                root,
                file=path,
                line=line,
                severity=severity,
                confidence=row.get("issue_confidence"),
            )
        )
    return result


def _normalize_dependency_findings(
    tool: str, raw: dict[str, Any], root: Path
) -> list[dict[str, Any]]:
    """Normalize package vulnerability reports."""
    result = []
    if tool == "pip-audit":
        for dep in _require_report_list(raw["dependencies"], "dependencies"):
            if dep.get("skip_reason"):
                raise ValueError("pip-audit skipped at least one dependency")
            for issue in _require_report_list(dep["vulns"], "vulnerabilities"):
                result.append(
                    make_quality_finding(
                        tool,
                        issue["id"],
                        issue.get("description") or issue["id"],
                        root,
                        package=dep["name"],
                        native_id=dep.get("version"),
                    )
                )
    elif tool == "osv-scanner":
        for scan in _require_report_list(raw["results"], "OSV results"):
            path = scan.get("source", {}).get("path")
            for dep in _require_report_list(scan["packages"], "OSV packages"):
                for issue in _require_report_list(
                    dep.get("vulnerabilities", []), "OSV vulnerabilities"
                ):
                    package = dep["package"]
                    result.append(
                        make_quality_finding(
                            tool,
                            issue["id"],
                            issue.get("summary") or issue["id"],
                            root,
                            file=path,
                            package=package["name"],
                            native_id=package.get("version"),
                        )
                    )
    elif tool == "cargo-audit":
        for issue in _require_report_list(
            raw["vulnerabilities"]["list"], "cargo-audit vulnerabilities"
        ):
            advisory, package = issue["advisory"], issue["package"]
            result.append(
                make_quality_finding(
                    tool,
                    advisory["id"],
                    advisory.get("title") or advisory["id"],
                    root,
                    package=package["name"],
                    native_id=package.get("version"),
                )
            )
    else:
        raise ValueError(f"Unsupported dependency tool: {tool}")
    return result


def _normalize_trivy_findings(raw: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    """Normalize vulnerability, configuration, secret and license findings."""
    result = []
    if "Results" not in raw or raw.get("Results") is None:
        raise ValueError("Trivy did not report a result inventory")
    for target in _require_report_list(raw["Results"], "Trivy results"):
        for issue in target.get("Vulnerabilities") or []:
            result.append(
                make_quality_finding(
                    "trivy",
                    issue["VulnerabilityID"],
                    issue.get("Title") or issue["VulnerabilityID"],
                    root,
                    file=target["Target"],
                    package=issue["PkgName"],
                    severity=issue.get("Severity"),
                    native_id=issue.get("InstalledVersion"),
                )
            )
        for issue in target.get("Misconfigurations") or []:
            result.append(
                make_quality_finding(
                    "trivy",
                    issue["ID"],
                    issue.get("Title") or issue["ID"],
                    root,
                    file=target["Target"],
                    severity=issue.get("Severity"),
                )
            )
        for issue in target.get("Secrets") or []:
            result.append(
                make_quality_finding(
                    "trivy",
                    issue["RuleID"],
                    "Potential secret (redacted)",
                    root,
                    file=target["Target"],
                    severity=issue.get("Severity"),
                    line=issue.get("StartLine"),
                )
            )
        for issue in target.get("Licenses") or []:
            result.append(
                make_quality_finding(
                    "trivy",
                    issue["Name"],
                    "License finding",
                    root,
                    file=target["Target"],
                    package=issue.get("PkgName"),
                    severity=issue.get("Severity"),
                )
            )
    return result


def _normalize_other_findings(tool: str, raw: Any, root: Path) -> list[dict[str, Any]]:
    """Normalize other explicitly supported analyzer formats."""
    result = []
    if tool == "coverity":
        if raw.get("error"):
            raise ValueError("Coverity reported an error")
        for issue in _require_report_list(raw["issues"], "Coverity issues"):
            result.append(
                make_quality_finding(
                    tool,
                    issue["checkerName"],
                    issue.get("checkerProperties", {}).get("subcategoryLocalEffect", ""),
                    root,
                    file=issue.get("mainEventFilePathname"),
                    line=issue.get("mainEventLineNumber"),
                    severity=issue.get("impact"),
                    native_id=issue.get("mergeKey"),
                )
            )
    elif tool == "checkov":
        for scan in raw if isinstance(raw, list) else [raw]:
            if scan.get("results", {}).get("parsing_errors"):
                raise ValueError("Checkov reported parsing errors")
            for issue in _require_report_list(scan["results"]["failed_checks"], "Checkov findings"):
                result.append(
                    make_quality_finding(
                        tool,
                        issue["check_id"],
                        issue["check_name"],
                        root,
                        file=issue["file_path"],
                        line=(issue.get("file_line_range") or [None])[0],
                        severity=issue.get("severity"),
                        native_id=issue.get("resource"),
                    )
                )
    elif tool == "sqlfluff":
        for source in _require_report_list(raw, tool):
            for issue in _require_report_list(source["violations"], "SQLFluff violations"):
                result.append(
                    make_quality_finding(
                        tool,
                        issue["code"],
                        issue["description"],
                        root,
                        file=source["filepath"],
                        line=issue.get("start_line_no", issue.get("line_no")),
                    )
                )
    else:
        raise ValueError(f"No structured normalizer for {tool}")
    return result


def normalize_analyzer_findings(tool: str, raw: Any, root: Path) -> list[dict[str, Any]]:
    """Dispatch supported structured reports; malformed input is never a clean scan."""
    if isinstance(raw, dict) and raw.get("version") == "2.1.0":
        return _normalize_sarif(raw, tool, root)
    if tool in {"ruff", "semgrep", "bandit", "mypy", "shellcheck", "hadolint", "actionlint"}:
        return _source_findings(tool, raw, root)
    if tool in {"pip-audit", "osv-scanner", "cargo-audit"}:
        return _normalize_dependency_findings(tool, raw, root)
    if tool == "trivy":
        return _normalize_trivy_findings(raw, root)
    return _normalize_other_findings(tool, raw, root)


def read_analyzer_report(tool: str, path: Path, root: Path) -> list[dict[str, Any]]:
    """Read JSON, mypy JSON lines, or Cppcheck XML; fail closed on format errors."""
    text = path.read_text()
    if tool == "mypy":
        raw: Any = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif tool == "cppcheck":
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("Unsupported XML declaration")
        doc = ElementTree.fromstring(text)
        errors = doc.find("errors")
        if doc.tag != "results" or errors is None:
            raise ValueError("Invalid Cppcheck XML")
        return [
            make_quality_finding(
                tool,
                row.attrib["id"],
                row.attrib["msg"],
                root,
                file=loc.get("file"),
                line=int(loc.get("line", "0")),
                severity=row.get("severity"),
            )
            for row in errors.findall("error")
            for loc in [next(iter(row.findall("location")), ElementTree.Element("location"))]
        ]
    elif tool == "vulture":
        rows = []
        for line in text.splitlines():
            match = re.fullmatch(r"(.+):(\d+): (.+) \((\d+)% confidence\)", line)
            if not match:
                raise ValueError("Unrecognized Vulture diagnostic")
            rows.append(
                make_quality_finding(
                    tool,
                    "dead-code",
                    match[3],
                    root,
                    file=match[1],
                    line=int(match[2]),
                    confidence=int(match[4]),
                )
            )
        return rows
    else:
        raw = json.loads(text)
    return normalize_analyzer_findings(tool, raw, root)
