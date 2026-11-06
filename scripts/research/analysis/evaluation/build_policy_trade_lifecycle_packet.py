"""Verify and aggregate the selected policy's partition-level lifecycle reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PARTITIONS = ("a4a_training", "a4b_training", "a4a_testing", "a4b_testing")
SCHEMA = "qrl.selected_policy_trade_lifecycle_packet.v1"
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_packet(packet_dir: Path, partitions: tuple[str, ...] = PARTITIONS) -> dict[str, Any]:
    """Verify child reports and build a machine-readable packet summary."""
    partition_reports: dict[str, Any] = {}
    source_evidence: dict[str, Any] = {}
    failures: list[dict[str, str]] = []

    for partition in partitions:
        partition_dir = packet_dir / partition
        manifest_path = partition_dir / "evidence_manifest.json"
        report_path = partition_dir / "selected_policy_trade_lifecycle.json"
        if not manifest_path.is_file() or not report_path.is_file():
            failures.append({"partition": partition, "reason": "manifest_or_report_missing"})
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected_script = manifest.get("analysis_script", {}).get("sha256")
        actual_script = _sha256(
            REPO_ROOT / "scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py"
        )
        if expected_script != actual_script:
            failures.append({"partition": partition, "reason": "analysis_script_hash_mismatch"})

        for name, expected_hash in manifest.get("report_files", {}).items():
            path = partition_dir / name
            if not path.is_file() or _sha256(path) != expected_hash:
                failures.append({"partition": partition, "reason": f"report_hash_mismatch:{name}"})

        partition_inputs: dict[str, Any] = {}
        for name, identity in manifest.get("input_files", {}).items():
            path = Path(identity["path"])
            exists = path.is_file()
            actual_hash = _sha256(path) if exists else None
            matched = exists and actual_hash == identity.get("sha256")
            if not matched:
                failures.append({"partition": partition, "reason": f"input_hash_mismatch:{name}"})
            partition_inputs[name] = {
                "path": path.as_posix(),
                "sha256": actual_hash,
                "expected_sha256": identity.get("sha256"),
                "matched": matched,
            }

        source_evidence[partition] = {
            "manifest_sha256": _sha256(manifest_path),
            "report_sha256": _sha256(report_path),
            "inputs": partition_inputs,
        }
        counts = report.get("counts", {})
        account = report.get("cashflow_equity_reconciliation", {})
        partition_reports[partition] = {
            "integrity_status": report.get("integrity_status", "incomplete"),
            "decision_rows": counts.get("decision_rows"),
            "fill_event_rows": counts.get("fill_event_rows"),
            "positions": counts.get("positions"),
            "linked_positions": counts.get("positions_with_linked_fill_events"),
            "unlinked_fill_position_ids": counts.get("unlinked_fill_position_ids"),
            "cashflow_equity_status": account.get("status", "incomplete"),
            "close_fill_charge_checks": account.get("close_charge_checks"),
            "allocated_entry_commission_total": account.get("allocated_entry_commission_total"),
            "completed_close_equity_checks": account.get("completed_close_equity_checks"),
            "ending_reconstructed_balance": account.get("ending_reconstructed_balance"),
            "payout_count": account.get("payout_count"),
            "scope": report.get("scope", {}),
        }
        if report.get("integrity_status") != "matched":
            failures.append({"partition": partition, "reason": "child_integrity_not_matched"})
        if account.get("status") != "matched":
            failures.append({"partition": partition, "reason": "cashflow_equity_not_matched"})

    totals: dict[str, int] = {}
    for field in ("decision_rows", "fill_event_rows", "positions", "linked_positions"):
        values = [item.get(field) for item in partition_reports.values()]
        totals[field] = sum(value for value in values if isinstance(value, int))
    has_mismatch = any(
        failure["reason"].startswith(
            (
                "analysis_script_hash_mismatch",
                "report_hash_mismatch:",
                "input_hash_mismatch:",
                "child_integrity_not_matched",
                "cashflow_equity_not_matched",
            )
        )
        for failure in failures
    )
    status = (
        "mismatch"
        if has_mismatch
        else "matched"
        if len(partition_reports) == len(partitions) and not failures
        else "incomplete"
    )
    return {
        "schema": SCHEMA,
        "status": status,
        "partition_count": len(partition_reports),
        "partitions": partition_reports,
        "totals": totals,
        "failure_count": len(failures),
        "failures": failures,
        "claim_boundary": (
            "Recorded source ledgers reconcile. This does not replay the policy, reconstruct open-position mark-to-market, "
            "validate historical candidate eligibility, or establish causal or economic superiority."
        ),
        "source_evidence": source_evidence,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Selected policy trade lifecycle packet",
        "",
        f"Packet verification: **{report['status']}** across {report['partition_count']} partitions.",
        "",
        "| Partition | Integrity | Decisions | Fills | Positions linked | Charge checks | Flat-close equity checks | Ending reconstructed balance |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in report["partitions"].items():
        lines.append(
            f"| `{name}` | {item['integrity_status']} | {item['decision_rows']} | "
            f"{item['fill_event_rows']} | {item['linked_positions']}/{item['positions']} | "
            f"{item['close_fill_charge_checks']} | {item['completed_close_equity_checks']} | "
            f"{item['ending_reconstructed_balance']} |"
        )
    lines.extend(
        [
            "",
            f"Across the verified partitions, {report['totals']['positions']:,} positions link to "
            f"fill events. The cashflow audit checks {sum(item.get('completed_close_equity_checks') or 0 for item in report['partitions'].values()):,} "
            "completed closes while flat, validates net-PnL/allocated-entry-fee arithmetic for "
            f"{sum(item.get('close_fill_charge_checks') or 0 for item in report['partitions'].values()):,} "
            "close fills, and applies recorded payouts in event-time order.",
            "",
            report["claim_boundary"],
            "",
            "Input and report hashes are recorded in `evidence_manifest.json`; each partition retains its own source manifest.",
            "",
        ]
    )
    return "\n".join(lines)


def write_packet(packet_dir: Path) -> dict[str, Any]:
    """Write the verified aggregate JSON, Markdown, and packet manifest."""
    report = build_packet(packet_dir)
    json_path = packet_dir / "selected_policy_trade_lifecycle.json"
    markdown_path = packet_dir / "selected_policy_trade_lifecycle.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    manifest = {
        "schema": SCHEMA,
        "analysis_script": {
            "path": SCRIPT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": _sha256(SCRIPT_PATH),
        },
        "partition_manifests": {
            name: item["manifest_sha256"] for name, item in report["source_evidence"].items()
        },
        "source_evidence": report["source_evidence"],
        "report_files": {
            json_path.name: _sha256(json_path),
            markdown_path.name: _sha256(markdown_path),
            **(
                {"README.md": _sha256(packet_dir / "README.md")}
                if (packet_dir / "README.md").is_file()
                else {}
            ),
        },
    }
    (packet_dir / "evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet-dir",
        type=Path,
        default=Path("evidence/research/selected_policy_trade_lifecycle"),
        help="Directory containing the four partition reports",
    )
    args = parser.parse_args()
    report = write_packet(args.packet_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "partitions": report["partition_count"],
                "failures": report["failure_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
