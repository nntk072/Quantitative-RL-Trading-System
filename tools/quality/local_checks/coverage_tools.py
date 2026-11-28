"""Local coverage collection, changed-code analysis and trusted baseline comparison."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

from tools.quality.coverage_report import PRODUCT_PACKAGES, aggregate_coverage, compare_baseline

from tools.quality.local_checks.run_evidence import HERE, ROOT, quality_file_sha256, write_quality_json, run_quality_process, quality_git, read_quality_json, quality_source_paths
from tools.quality.local_checks.receipts import read_collected_inventory, validate_test_receipts

PLUGIN = "tools.quality.local_checks.pytest_receipts"


def changed_source_lines(diff: str) -> dict[str, set[int]]:
    """Extract postimage lines from zero-context Git hunks."""
    result: dict[str, set[int]] = {}
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith(("+++ ", "diff --git ")):
            current = None
        elif current and (match := re.match(r"^@@ .* \+(\d+)(?:,(\d+))? @@", line)):
            start, count = int(match[1]), int(match[2] or "1")
            result.setdefault(current, set()).update(range(start, start + count))
    return result


def changed_coverage_metrics(
    report: dict[str, Any], changed: dict[str, set[int]], critical: list[str]
) -> dict[str, Any]:
    """Count statements and branch arcs associated with changed source lines."""
    result = {}
    absent = []
    for name, lines in sorted(changed.items()):
        if not lines:
            continue
        if name.split("/")[0] not in PRODUCT_PACKAGES or not name.endswith(".py"):
            continue
        row = report["files"].get(name)
        if row is None:
            absent.append(name)
            continue
        hit = set(row["executed_lines"]) & lines
        miss = set(row["missing_lines"]) & lines
        arcs = [a for a in row.get("executed_branches", []) if lines.intersection(a)]
        missing = [a for a in row.get("missing_branches", []) if lines.intersection(a)]
        result[name] = {
            "statement_covered": len(hit),
            "statement_total": len(hit | miss),
            "branch_covered": len(arcs),
            "branch_total": len(arcs) + len(missing),
            "missing_lines": sorted(miss),
            "missing_branches": missing,
            "excluded_changed_lines": sorted(set(row.get("excluded_lines", [])) & lines),
            "critical": any(name.startswith(p) for p in critical),
        }
    return {
        "files": result,
        "unmeasured_changed_files": absent,
        "branch_data_present": report.get("meta", {}).get("branch_coverage", False),
    }


def validate_coverage_report(report: dict[str, Any], full: bool) -> None:
    """Validate statement and arc partitions; full reports must inventory every package."""
    packages = set()
    for name, row in report["files"].items():
        packages.add(name.split("/")[0])
        executed, missing = set(row["executed_lines"]), set(row["missing_lines"])
        hit = {tuple(a) for a in row.get("executed_branches", [])}
        miss = {tuple(a) for a in row.get("missing_branches", [])}
        s = row["summary"]
        if executed & missing or hit & miss:
            raise ValueError(f"Overlapping coverage partitions: {name}")
        if (
            len(executed) != s["covered_lines"]
            or len(executed | missing) != s["num_statements"]
            or len(hit) != s["covered_branches"]
            or len(hit | miss) != s["num_branches"]
        ):
            raise ValueError(f"Coverage counts do not reconcile: {name}")
    if full and (not packages.issuperset(PRODUCT_PACKAGES) or not report["meta"]["branch_coverage"]):
        raise ValueError("Incomplete product package or branch coverage")


def _local_coverage_config(out: Path) -> Path:
    """Derive a local configuration without changing the canonical project settings."""
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["coverage"]["run"]
    text = "[run]\nbranch = True\nrelative_files = True\n"
    installed = tuple(int(n) for n in version("coverage").split(".")[:2])
    if installed >= (7, 10):
        text += "patch = subprocess\n"
    text += "source =\n"
    text += "".join(f"    {name}\n" for name in cfg["source"])
    path = out / "coverage.ini"
    path.write_text(text)
    return path


def _run_coverage_shard(
    out: Path, name: str, args: list[str], config: Path, timeout: int, workers: int
) -> dict[str, Any]:
    """Execute an isolated shard with coverage and exact collection receipts."""
    raw = out / "raw"
    raw.mkdir(exist_ok=True)
    env = {
        "COVERAGE_FILE": str(raw / f".coverage.{name}"),
        "COVERAGE_RCFILE": str(config),
        "QRL_LOCAL_INVENTORY": str(out / f"{name}-inventory.json"),
        "QRL_LOCAL_RECEIPTS": str(out / f"{name}-receipts.jsonl"),
    }
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        PLUGIN,
        "--cov",
        "--cov-context=test",
        f"--cov-config={config}",
        "--cov-report=",
        f"--junitxml={out / (name + '.xml')}",
    ]
    if workers > 1:
        command.extend(["-n", str(workers)])
    result = run_quality_process(command + args, out / f"{name}.log", timeout, env=env)
    if result["status"] != "ok":
        return result
    rows = read_collected_inventory(sorted(out.glob(f"{name}-inventory.json*")))
    receipts = validate_test_receipts(out / f"{name}-receipts.jsonl", {r["nodeid"] for r in rows})
    if any(r["status"] in {"failed", "incomplete"} for r in receipts.values()):
        raise ValueError("Invalid execution receipts")
    write_quality_json(out / f"{name}-outcomes.json", receipts)
    if not list(raw.glob(f".coverage.{name}*")):
        raise ValueError("Coverage data missing")
    return {**result, "inventory": rows, "tests": len(rows)}


def collect_local_coverage(
    out: Path, selection: list[str], full: bool, timeout: int, workers: int
) -> dict[str, Any]:
    """Collect selected tests or the explicit full unit/integration coverage profile."""
    if full == bool(selection) or workers < 1 or any(p.startswith("-") for p in selection):
        raise ValueError("Specify either --full or explicit test paths")
    policy = read_quality_json(HERE / "policy.json")
    config = _local_coverage_config(out)
    jobs = (
        {name: ["-m", marker, "tests"] for name, marker in policy["markers"].items()}
        if full
        else {"selected": selection}
    )
    reports = {name: _run_coverage_shard(out, name, args, config, timeout, workers) for name, args in jobs.items()}
    if any(r["status"] != "ok" for r in reports.values()):
        return {"status": "incomplete", "jobs": reports}
    env = {"COVERAGE_FILE": str(out / ".coverage"), "COVERAGE_RCFILE": str(config)}
    for command in (
        ["combine", "--keep", str(out / "raw")],
        ["json", "--show-contexts", "-o", str(out / "coverage.json")],
        ["xml", "-o", str(out / "coverage.xml")],
        ["html", "-d", str(out / "htmlcov")],
    ):
        result = run_quality_process(
            [sys.executable, "-m", "coverage", *command],
            out / f"{command[0]}.log",
            timeout,
            env=env,
        )
        if result["status"] != "ok":
            return {"status": "incomplete", "stage": command[0], "result": result}
    raw = read_quality_json(out / "coverage.json")
    validate_coverage_report(raw, full)
    if full:
        _validate_product_file_inventory(raw, config, out / ".coverage")
    write_quality_json(out / "coverage-summary.json", aggregate_coverage(raw))
    nodes = [row for r in reports.values() for row in r["inventory"]]
    if len({row["nodeid"] for row in nodes}) != len(nodes):
        raise ValueError("Unit and integration inventories overlap")
    write_quality_json(out / "test-inventory.json", nodes)
    return {
        "status": "ok",
        "scope": "full" if full else "selected",
        "jobs": reports,
        "coverage_sha256": quality_file_sha256(out / ".coverage"),
        "inventory_sha256": quality_file_sha256(out / "test-inventory.json"),
        "coverage_config_sha256": quality_file_sha256(config),
    }


def _validate_product_file_inventory(report: dict[str, Any], config: Path, data: Path) -> None:
    """Require executable product modules to agree with coverage.py source analysis."""
    from coverage import Coverage

    cov = Coverage(config_file=str(config), data_file=str(data))
    cov.load()
    for path in quality_source_paths():
        if path.split("/")[0] not in PRODUCT_PACKAGES or not path.endswith(".py"):
            continue
        if (ROOT / path).is_symlink():
            raise ValueError(f"Unexpected product symlink: {path}")
        _, statements, _, _, _ = cov.analysis2(str(ROOT / path))
        row = report["files"].get(path)
        if statements and row is None:
            raise ValueError(f"Missing executable source: {path}")
        if row and set(statements) != set(row["executed_lines"]) | set(row["missing_lines"]):
            raise ValueError(f"Source statement mismatch: {path}")


def analyze_local_coverage(report: Path, base: str, full: bool, baseline_manifest: Path | None = None) -> dict[str, Any]:
    """Compare against a target Git ref without modifying the established baseline."""
    if base.startswith("-"):
        raise ValueError("Invalid base")
    raw = read_quality_json(report)
    validate_coverage_report(raw, full)
    merged = quality_git("merge-base", base, "HEAD").decode().strip()
    diff = quality_git("diff", "--no-renames", "--unified=0", merged, "--").decode()
    changed = changed_source_lines(diff)
    for name in quality_git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"):
        if name.endswith(".py") and (ROOT / name).is_file():
            changed[name] = set(range(1, len((ROOT / name).read_text().splitlines()) + 1))
    policy = read_quality_json(HERE / "policy.json")
    summary = aggregate_coverage(raw)
    delta = changed_coverage_metrics(raw, changed, policy["critical_prefixes"])
    findings = []
    if delta["unmeasured_changed_files"]:
        findings.append("Changed product files absent from coverage evidence")
    if not delta["branch_data_present"]:
        findings.append("Branch coverage data unavailable")
    if full:
        baseline = json.loads(quality_git("show", f"{base}:tools/quality/coverage_baseline.json"))
        if baseline.get("source_branch") != "main":
            raise ValueError("Expected the committed main baseline")
        findings.extend(compare_baseline(summary, baseline))
        for name, row in {"overall": baseline["overall"], **baseline["packages"]}.items():
            prior = row["branch_ratio"]
            current = (
                summary["overall"] if name == "overall" else summary["packages"].get(name, {})
            ).get("branch_ratio")
            if prior is not None and (current is None or current < prior):
                findings.append(f"{name}: branch coverage regression")
    if baseline_manifest is not None:
        if not full:
            raise ValueError("A selected report cannot be compared with a full baseline")
        from tools.quality.local_checks.coverage_governance import verified_baseline_candidate

        candidate = verified_baseline_candidate(baseline_manifest, base)
        findings.extend(compare_baseline(summary, candidate["summary"]))
        for name, row in {"overall": candidate["summary"]["overall"], **candidate["summary"]["packages"]}.items():
            prior = row["branch_ratio"]
            current = (summary["overall"] if name == "overall" else summary["packages"].get(name, {})).get("branch_ratio")
            if prior is not None and (current is None or current < prior):
                findings.append(f"{name}: branch coverage below verified baseline")
    for name, row in delta["files"].items():
        for kind in ("statement", "branch"):
            total = row[f"{kind}_total"]
            threshold = policy["targets"][f"{'critical_' if row['critical'] else ''}changed_{kind}"]
            if total and 100 * row[f"{kind}_covered"] / total < threshold:
                findings.append(f"{name}: changed {kind} coverage below advisory target")
        if row["excluded_changed_lines"]:
            findings.append(f"{name}: new or changed excluded lines")
    return {
        "status": "findings" if findings else "ok",
        "summary": summary,
        "diff": delta,
        "merge_base": merged,
        "findings": findings,
        "scope": "full" if full else "selected",
    }
