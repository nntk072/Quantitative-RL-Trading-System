"""Read-only command line for validating and planning registered studies."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from configuration.paths import repository_root
from research_tools.studies.study_audits import StudyAuditError, run_study_audit
from research_tools.studies.study_catalog import (
    StudyCatalogError,
    build_study_plan,
    validate_study_catalog,
)
from research_tools.studies.study_inventory import StudyInventoryError
from research_tools.studies.study_runner import StudyRunnerError, run_study_checks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qrl-study")
    parser.add_argument("--root", type=Path, help="repository root; defaults to this checkout")
    parser.add_argument(
        "--master", type=Path, help="study master YAML path relative to repository root"
    )
    parser.add_argument("--module", help="limit check selection to one module ID")
    parser.add_argument("--study", help="limit check selection to one study ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="render checks without executing them"
    )
    parser.add_argument("--output-dir", type=Path, help="write a check report without overwriting")
    parser.add_argument(
        "command", choices=("list", "validate", "plan", "inventory", "check", "audit")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """List, validate, plan, or run focused registered study checks."""
    args = _parser().parse_args(argv)
    root = args.root.resolve() if args.root else repository_root(__file__)
    try:
        if args.command == "validate":
            study_ids = validate_study_catalog(root, args.master)
            print(f"validated {len(study_ids)} registered studies")
        elif args.command == "list":
            study_ids = validate_study_catalog(root, args.master)
            print("\n".join(study_ids))
        elif args.command == "plan":
            plan: dict[str, Any] = build_study_plan(root, args.master)
            print(json.dumps(plan, indent=2, sort_keys=True))
        elif args.command == "inventory":
            if args.module is not None and args.study is not None:
                raise StudyCatalogError("select either a module or a study for inventory")
            plan = build_study_plan(root, args.master, include_inventory=True)
            inventory = plan["inventory"]
            if args.module is not None:
                modules = {module["id"]: module for module in inventory["source"]["modules"]}
                if args.module not in modules:
                    raise StudyCatalogError(f"unknown module: {args.module}")
                inventory["source"]["modules"] = [modules[args.module]]
                inventory["source"]["file_count"] = len(modules[args.module]["files"])
                inventory["source"]["symbol_count"] = sum(
                    len(item["symbols"]) for item in modules[args.module]["files"]
                )
                for section in ("config", "tests"):
                    inventory[section]["files"] = [
                        item
                        for item in inventory[section]["files"]
                        if args.module in item["module_ids"]
                    ]
                    inventory[section]["file_count"] = len(inventory[section]["files"])
                    if section == "config":
                        inventory[section]["key_count"] = sum(
                            len(item["keys"]) for item in inventory[section]["files"]
                        )
                inventory["evidence"]["files"] = [
                    {
                        **item,
                        "study_ids": [
                            study
                            for study in item["study_ids"]
                            if study.startswith(f"{args.module}.")
                        ],
                    }
                    for item in inventory["evidence"]["files"]
                    if any(study.startswith(f"{args.module}.") for study in item["study_ids"])
                ]
                inventory["evidence"]["file_count"] = len(inventory["evidence"]["files"])
            elif args.study is not None:
                known = set(plan["catalog_study_ids"])
                if args.study not in known:
                    raise StudyCatalogError(f"unknown study: {args.study}")
                inventory["source"]["modules"] = [
                    {
                        **module,
                        "files": [
                            item for item in module["files"] if args.study in item["study_ids"]
                        ],
                    }
                    for module in inventory["source"]["modules"]
                    if any(args.study in item["study_ids"] for item in module["files"])
                ]
                inventory["source"]["file_count"] = sum(
                    len(module["files"]) for module in inventory["source"]["modules"]
                )
                inventory["source"]["symbol_count"] = sum(
                    len(item["symbols"])
                    for module in inventory["source"]["modules"]
                    for item in module["files"]
                )
                for section in ("config", "tests", "evidence"):
                    inventory[section]["files"] = [
                        {**item, "study_ids": [args.study]}
                        for item in inventory[section]["files"]
                        if args.study in item["study_ids"]
                    ]
                    inventory[section]["file_count"] = len(inventory[section]["files"])
                    if section == "config":
                        inventory[section]["key_count"] = sum(
                            len(item["keys"]) for item in inventory[section]["files"]
                        )
            print(json.dumps(inventory, indent=2, sort_keys=True))
        elif args.command == "check":
            result = run_study_checks(
                root,
                master_path=args.master,
                module_id=args.module,
                study_id=args.study,
                dry_run=args.dry_run,
                output_dir=args.output_dir,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            if result["status"] in {"failed", "blocked"}:
                return 1
        elif args.command == "audit":
            if args.module is not None:
                raise StudyAuditError("audit accepts one explicit --study ID, not --module")
            if args.study is None:
                raise StudyAuditError("audit requires one explicit --study ID")
            if args.dry_run:
                raise StudyAuditError(
                    "audit has no dry-run mode; use check --dry-run to preview tests"
                )
            result = run_study_audit(
                root,
                study_id=args.study,
                master_path=args.master,
                output_dir=args.output_dir,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            if (
                result["status"] != "completed"
                or result["diagnostic_status"] == "failed"
                or (
                    isinstance(result["diagnostic_status"], str)
                    and result["diagnostic_status"].startswith("blocked")
                )
            ):
                return 1
    except (StudyAuditError, StudyCatalogError, StudyInventoryError, StudyRunnerError) as exc:
        print(f"qrl-study: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
