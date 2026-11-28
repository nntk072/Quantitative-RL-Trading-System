"""Conditional native, GPU, SQL and frontend quality adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.quality.local_checks.analyzer_execution import publish_analyzer_findings
from tools.quality.local_checks.normalization import read_analyzer_report
from tools.quality.local_checks.run_evidence import ROOT, quality_source_paths, run_quality_process

NATIVE_PROFILES = {
    "rust": ["fmt", "clippy", "coverage", "mutation", "fuzz", "miri", "audit", "deny", "nextest"],
    "cpp": ["clang-tidy", "cppcheck", "llvm-coverage", "lcov", "asan", "ubsan", "tsan", "fuzz"],
    "cuda": ["memcheck", "racecheck", "initcheck", "synccheck"],
    "sql": ["lint", "migration-test"],
    "web": ["lint", "types", "coverage", "playwright"],
}


def _native_target_path(target: str) -> Path:
    """Resolve a repository-local existing target without permitting option injection."""
    if target.startswith("-"):
        raise ValueError("Invalid target")
    path = (ROOT / target).resolve()
    if not path.is_relative_to(ROOT) or not path.exists():
        raise ValueError("Target must be an existing repository-local path")
    return path


def discover_native_components() -> dict[str, list[str]]:
    """Inventory actual native source and manifest files without installing toolchains."""
    paths = quality_source_paths()
    return {
        "rust": [p for p in paths if Path(p).name == "Cargo.toml"],
        "cpp": [p for p in paths if Path(p).suffix in {".c", ".cpp", ".cc", ".cxx"}],
        "cuda": [p for p in paths if Path(p).suffix in {".cu", ".cuh"}],
        "sql": [p for p in paths if p.endswith(".sql")],
        "web": [p for p in paths if Path(p).name == "package.json"],
    }


def run_native_profile(out: Path, timeout: int, profile: str, check: str,
                       target: str | None, arguments: list[str]) -> dict[str, Any]:
    """Execute only an applicable, explicitly selected native check with bounded time."""
    if profile not in NATIVE_PROFILES or check not in NATIVE_PROFILES[profile]:
        raise ValueError("Unknown native check")
    components = discover_native_components()[profile]
    if not components and not (profile == "cuda" and target):
        return {"status": "not_applicable", "profile": profile, "check": check, "components": []}
    if profile == "rust":
        manifest = _native_target_path(target or components[0])
        if manifest.name != "Cargo.toml":
            raise ValueError("Expected Cargo.toml")
        commands = {
            "fmt": ["cargo", "fmt", "--manifest-path", str(manifest), "--", "--check"],
            "clippy": ["cargo", "clippy", "--manifest-path", str(manifest), "--locked", "--all-targets", "--message-format=json", "--", "-D", "warnings"],
            "coverage": ["cargo", "llvm-cov", "--manifest-path", str(manifest), "--locked", "--json", "--output-path", str(out/"rust-coverage.json")],
            "mutation": ["cargo", "mutants", "--manifest-path", str(manifest), "--output", str(out/"rust-mutation")],
            "fuzz": ["cargo", "+nightly", "fuzz", "run", *arguments],
            "miri": ["cargo", "+nightly", "miri", "test", "--manifest-path", str(manifest), "--locked"],
            "audit": ["cargo", "audit", "--json", "--file", str(manifest.parent/"Cargo.lock")],
            "deny": ["cargo", "deny", "--manifest-path", str(manifest), "check"],
            "nextest": ["cargo", "nextest", "run", "--manifest-path", str(manifest), "--locked"],
        }
        if check == "fuzz" and not arguments:
            raise ValueError("Supply an existing cargo-fuzz target and explicit budget")
        result = run_quality_process(commands[check], out/f"{check}.log", timeout, cwd=manifest.parent,
                                     findings_codes=(1, 2) if check == "mutation" else ())
    elif profile == "cuda":
        if not target:
            raise ValueError("Supply a reviewed executable or script for actual CUDA validation")
        executable = _native_target_path(target)
        result = run_quality_process(["compute-sanitizer", "--tool", check, "--error-exitcode", "99",
                                     str(executable), *arguments], out/f"{check}.log", timeout,
                                     findings_codes=(99,))
    elif profile == "cpp":
        if check == "cppcheck":
            result = run_quality_process(["cppcheck", "--enable=all", "--xml", "--xml-version=2",
                                         "--error-exitcode=1", *components], out/"cppcheck.log", timeout,
                                         findings_codes=(1,))
            if result["status"] in {"ok", "findings"}:
                rows = read_analyzer_report("cppcheck", out/"cppcheck.log.stderr", ROOT)
                publish_analyzer_findings(out, "cppcheck", rows)
                result.update(status="findings" if rows else "ok", findings_count=len(rows))
        elif check == "clang-tidy":
            if not target:
                raise ValueError("Supply the existing compilation database directory")
            build = _native_target_path(target)
            result = run_quality_process(["clang-tidy", "-p", str(build), *components,
                                         "--export-fixes="+str(out/"clang-tidy.yaml")],
                                         out/"clang-tidy.log", timeout)
        elif check == "llvm-coverage":
            if not target or not arguments:
                raise ValueError("Supply an instrumented executable and merged profdata path")
            binary, data = _native_target_path(target), _native_target_path(arguments[0])
            result = run_quality_process(["llvm-cov", "export", str(binary), "-instr-profile="+str(data)],
                                         out/"llvm-coverage.json", timeout)
        elif check == "lcov":
            if not target:
                raise ValueError("Supply an instrumented build directory")
            build = _native_target_path(target)
            result = run_quality_process(["lcov", "--capture", "--directory", str(build),
                                         "--output-file", str(out/"coverage.info")], out/"lcov.log", timeout)
        else:
            if not target:
                raise ValueError("Supply an already-instrumented test or fuzz executable")
            executable = _native_target_path(target)
            result = run_quality_process([str(executable), *arguments], out/f"{check}.log", timeout,
                env={"ASAN_OPTIONS": "halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1",
                     "TSAN_OPTIONS": "halt_on_error=1"}, findings_codes=(1, 66))
            result["qualification"] = "Caller must verify the binary was built with the selected instrumentation."
    elif profile == "sql":
        if check == "lint":
            result = run_quality_process(["sqlfluff", "lint", "--format", "json", "--dialect", "ansi", *components],
                                         out/"sqlfluff.json", timeout, findings_codes=(1,))
            if result["status"] in {"ok", "findings"}:
                rows = read_analyzer_report("sqlfluff", out/"sqlfluff.json", ROOT)
                publish_analyzer_findings(out, "sqlfluff", rows)
                result.update(status="findings" if rows else "ok", findings_count=len(rows))
        else:
            if not target:
                raise ValueError("Supply the repository-owned migration test executable")
            result = run_quality_process([str(_native_target_path(target)), *arguments],
                                         out/"migration-test.log", timeout)
    else:
        manifest = _native_target_path(target or components[0])
        if manifest.name != "package.json":
            raise ValueError("Expected package.json")
        cmd = {"lint": ["eslint", "."], "types": ["tsc", "--noEmit"],
               "coverage": ["vitest", "run", "--coverage"], "playwright": ["playwright", "test"]}[check]
        result = run_quality_process(["npm", "exec", "--offline", "--", *cmd], out/f"{check}.log",
                                     timeout, cwd=manifest.parent, findings_codes=(1,))
    return {"profile": profile, "check": check, "components": components, **result}
