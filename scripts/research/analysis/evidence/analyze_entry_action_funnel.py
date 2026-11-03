#!/usr/bin/env python3
"""Summarize train-split entry-action funnel evidence for the selected pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from artifacts.atomic import write_json_atomic, write_text_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
CAMPAIGN = Path("outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1")
CAMPAIGN_FINGERPRINT = "b37580606ca374326bce7207fb7eef118cede36cf0eaad25d37be9465bb4e1e4"
REANALYSIS = CAMPAIGN / "reanalysis_daily_stop_semantics_20261024"
ARMS = {
    "treatment": "ladder_a4a_entry_fsm_hidden_qgrid025",
    "control": "ladder_a4b_entry_fsm_qgrid025",
}
DEFAULT_OUTPUT = (
    ROOT / "evidence/research/releases/negative-evidence-readiness/entry_action_funnel_diagnosis"
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_train_funnel(root: Path, role: str, arm: str) -> dict[str, Any]:
    """Read one frozen train-only funnel and verify its campaign identity."""
    campaign_path = root / CAMPAIGN / "campaign.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    if campaign.get("fingerprint") != CAMPAIGN_FINGERPRINT:
        raise ValueError("selected campaign fingerprint differs from the registered identity")

    log_path = root / REANALYSIS / arm / "training_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    if int(log.get("seed", -1)) != 50 or int(log.get("train_bars", -1)) != 351_432:
        raise ValueError(f"unexpected run identity in {log_path}")
    funnel = log.get("entry_funnel_by_split", {}).get("train")
    if not isinstance(funnel, dict):
        raise ValueError(f"train entry funnel missing in {log_path}")
    attempts = int(funnel.get("entry_attempts", 0))
    opened = int(funnel.get("entry_opened", 0))
    rejected = {key: int(value) for key, value in funnel.items() if key.startswith("rejected_")}
    if attempts != opened + sum(rejected.values()):
        raise ValueError(f"entry funnel does not reconcile for {arm}")
    if int(funnel.get("entered", -1)) != opened or int(funnel.get("closed", -1)) != opened:
        raise ValueError(f"entry-state lifecycle totals do not reconcile for {arm}")
    return {
        "role": role,
        "arm": arm,
        "source_log": (REANALYSIS / arm / "training_log.json").as_posix(),
        "source_log_sha256": sha256_file(log_path),
        "seed": int(log["seed"]),
        "training_bars": int(log["train_bars"]),
        "entry_attempts": attempts,
        "entry_opened": opened,
        "entry_open_rate": opened / attempts if attempts else 0.0,
        "rejected_entry_state": rejected.get("rejected_entry_state", 0),
        "unarmed_request_share": (
            rejected.get("rejected_entry_state", 0) / attempts if attempts else 0.0
        ),
        "rejection_counts": rejected,
        "candidate_created": int(funnel.get("candidate_created", 0)),
        "candidate_expired": int(funnel.get("candidate_expired", 0)),
        "candidate_invalidated": int(funnel.get("candidate_invalidated", 0)),
        "trigger_requested": int(funnel.get("trigger_requested", 0)),
        "trigger_refused": int(funnel.get("trigger_refused", 0)),
        "trigger_refusal_share": float(funnel.get("trigger_refusal_rate", 0.0)),
    }


def build_diagnosis(root: Path = ROOT) -> dict[str, Any]:
    """Build a train-only, identity-checked comparison from the two run logs."""
    source = root / CAMPAIGN / "campaign.json"
    return {
        "schema_version": 1,
        "evidence_id": "entry_action_funnel_diagnosis",
        "campaign_fingerprint": CAMPAIGN_FINGERPRINT,
        "campaign_manifest_sha256": sha256_file(source),
        "period_role": "2025 training development only; exposed 2026 records not read",
        "arms": [load_train_funnel(root, role, arm) for role, arm in ARMS.items()],
        "interpretation_limit": (
            "Request and rejection counters localize action-funnel attrition. "
            "They do not establish why the policy requested entries while unarmed, "
            "prove candidate signal quality, or explain economic losses."
        ),
    }


def render_report(diagnosis: dict[str, Any]) -> str:
    """Render a compact interpretation without replacing the source logs."""
    treatment_share, control_share = (
        float(arm["unarmed_request_share"]) for arm in diagnosis["arms"]
    )
    lines = [
        "# Entry action funnel diagnosis",
        "",
        "## Scope",
        "",
        "This report compares the frozen treatment/control training logs for the",
        "selected single-seed policy pair. It reads only the 2025 training split.",
        "The 2026 report split is not read. Campaign and per-arm log hashes are",
        "recorded in the adjacent machine-readable report.",
        "",
        "## Results",
        "",
        "| Arm | Entry requests | Not armed | Not-armed share | Opened | Open rate | Candidates | Invalidated | Trigger requests refused |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in diagnosis["arms"]:
        lines.append(
            "| {role} | {entry_attempts:,} | {rejected_entry_state:,} | {unarmed_request_share:.1%} | "
            "{entry_opened:,} | {entry_open_rate:.2%} | {candidate_created:,} | "
            "{candidate_invalidated:,} | {trigger_refused:,}/{trigger_requested:,} ({trigger_refusal_share:.1%}) |".format(
                **arm
            )
        )
    lines += [
        "",
        "| Arm | Cooldown | Invalid stop | Invalid reward/risk | Overnight boundary |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in diagnosis["arms"]:
        rejected = arm["rejection_counts"]
        lines.append(
            f"| {arm['role']} | {rejected.get('rejected_cooldown', 0):,} | "
            f"{rejected.get('rejected_sl', 0):,} | {rejected.get('rejected_rr', 0):,} | "
            f"{rejected.get('rejected_overnight', 0):,} |"
        )
    lines += [
        "",
        "The largest recorded funnel loss is action requests made while the",
        "entry-state machine was `FLAT` or `CANDIDATE`: "
        f"{treatment_share:.1%} of treatment requests and "
        f"{control_share:.1%} of control requests were rejected as "
        "`entry_state_not_armed`.",
        "This is evidence of a policy/action-interface mismatch or frequent",
        "unarmed requests, not evidence that the market supplied too few entry",
        "candidates. Candidate invalidation and downstream SL/RR/cooldown",
        "rejections are separate mechanisms and should remain separate in any",
        "successor analysis.",
        "",
        "## Claim boundary",
        "",
        diagnosis["interpretation_limit"],
        "The counts do not support a performance claim or a causal explanation",
        "for the losing equity path. Any action-mask or policy-interface change",
        "would be a new experimental factor; do not apply it to the historical",
        "checkpoint or treat this diagnosis as authorization to train.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Write the machine report and human interpretation atomically."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = args.output_dir
    if not output.is_absolute():
        output = root / output
    diagnosis = build_diagnosis(root)
    output.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output / "entry_action_funnel_diagnosis.json", diagnosis)
    write_text_atomic(output / "entry_action_funnel_diagnosis.md", render_report(diagnosis))
    print(f"Wrote entry-action funnel diagnosis to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
