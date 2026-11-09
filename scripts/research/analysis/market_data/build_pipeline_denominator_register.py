"""Build a provenance-aware inventory of available research pipeline denominators.

The source artifacts cover different profiles and units. This report keeps them
as separate evidence groups and records unavailable historical links as null,
never as zero. It does not fabricate a joined end-to-end funnel.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
MARKET_QUALITY = Path("evidence/research/market_data_quality/local_market_data_quality.json")
CENSUS = Path("evidence/research/trade_setup_opportunity_census/census.json")
CARDINALITY = Path("evidence/research/candidate_event_cardinality/cardinality_register.json")
CARRY_FORWARD = Path("evidence/research/market_data_quality/tickbook_carry_forward_audit.json")
CAMPAIGN = Path("outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def count_csv(path: Path) -> tuple[int, Counter[str]]:
    types: Counter[str] = Counter()
    rows = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            rows += 1
            if "type" in record:
                types[record["type"] or "<empty>"] += 1
    return rows, types


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def numeric_value(value: object, *, field: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected a numeric value for {field}, got {value!r}")
    return value


def add_stage(
    rows: list[dict[str, Any]],
    *,
    group: str,
    scope: str,
    stage: str,
    metric: str,
    value: int | float | None,
    unit: str,
    state: str,
    source: str,
    note: str,
) -> None:
    rows.append(
        {
            "evidence_group": group,
            "scope": scope,
            "stage": stage,
            "metric": metric,
            "value": value,
            "unit": unit,
            "state": state,
            "source": source,
            "note": note,
        }
    )


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def collect(
    root: Path, market_quality_path: Path = MARKET_QUALITY
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    market_path = (
        market_quality_path if market_quality_path.is_absolute() else root / market_quality_path
    )
    census_path = root / CENSUS
    cardinality_path = root / CARDINALITY
    carry_path = root / CARRY_FORWARD
    market = read_json(market_path)
    census = read_json(census_path)
    cardinality = read_json(cardinality_path)
    carry = read_json(carry_path)
    if not market.get("all_inputs_present") or not market.get("all_input_hashes_match"):
        raise ValueError("local market-data input identity gate does not pass")
    if carry.get("status") != "complete_source_hash_verified_production_path_counts":
        raise ValueError("TickBook carry-forward audit is not complete and hash-verified")

    stage_rows: list[dict[str, Any]] = []
    source_paths: set[Path] = {
        market_path,
        census_path,
        cardinality_path,
        carry_path,
        Path(__file__).resolve(),
    }

    # Raw rows are reported by source kind and role. Calendar rows are metadata,
    # not market observations, and are intentionally excluded from these totals.
    raw_totals: dict[tuple[str, str], int] = defaultdict(int)
    tick_records: list[dict[str, Any]] = []
    for item in market["inputs"]:
        if item.get("kind") not in {"bar", "tick"}:
            continue
        if item.get("row_count") is None:
            raise ValueError(f"source row count missing for {item.get('path')}")
        role = str(item.get("role", item.get("source_role", "unknown")))
        kind = str(item["kind"])
        instrument = str(item.get("instrument", "unknown"))
        timeframe = str(item.get("timeframe", "unknown"))
        rows = int(item["row_count"])
        raw_totals[(role, kind)] += rows
        add_stage(
            stage_rows,
            group="local_market_data",
            scope=f"{role}:{instrument}:{timeframe}",
            stage="raw_rows",
            metric=f"{kind}_source_rows",
            value=rows,
            unit="rows",
            state="measured",
            source=display_path(market_path, root),
            note="Source-file rows; wall-clock timestamps have no external clock claim.",
        )
        if kind == "tick":
            tick_records.append(item)

    tick_rows_total = 0
    usable_quotes_total = 0
    missing_side_total = 0
    for item in tick_records:
        rows = int(item["row_count"])
        bid_missing = int(item.get("missing_or_nonfinite_bid_rows", 0))
        ask_missing = int(item.get("missing_or_nonfinite_ask_rows", 0))
        both_missing = int(item.get("missing_or_nonfinite_bid_and_ask_rows", 0))
        missing_any_side = bid_missing + ask_missing - both_missing
        nonpositive = int(item.get("nonpositive_bid_or_ask_rows", 0))
        inverted = int(item.get("inverted_quote_rows", 0))
        # Current counters do not provide intersections among these invalidity
        # classes. Exact arithmetic is safe here because the observed structural
        # violations are zero; fail closed if a future source changes that.
        if nonpositive or inverted:
            raise ValueError(
                "nonpositive/inverted quotes require joint invalidity counts before "
                "an exact usable-quote denominator can be reported"
            )
        usable = rows - missing_any_side
        if usable < 0:
            raise ValueError(f"invalid quote-side counts for {item.get('path')}")
        tick_rows_total += rows
        usable_quotes_total += usable
        missing_side_total += missing_any_side
        add_stage(
            stage_rows,
            group="local_market_data",
            scope=f"{item.get('role')}:{item.get('instrument')}:{item.get('timeframe')}",
            stage="usable_quotes",
            metric="finite_two_sided_quote_rows",
            value=usable,
            unit="rows",
            state="measured",
            source=display_path(market_path, root),
            note=(
                f"Raw rows {rows}; rows missing/nonfinite on either side {missing_any_side}; "
                "nonpositive and inverted counts are both zero in this scan."
            ),
        )

    add_stage(
        stage_rows,
        group="local_market_data",
        scope="all local campaign tick inputs",
        stage="raw_rows",
        metric="tick_source_rows_total",
        value=tick_rows_total,
        unit="rows",
        state="measured",
        source=display_path(market_path, root),
        note="Sum of four role/instrument tick streams; not a unique-market-time count.",
    )
    add_stage(
        stage_rows,
        group="local_market_data",
        scope="all local campaign tick inputs",
        stage="usable_quotes",
        metric="finite_two_sided_quote_rows_total",
        value=usable_quotes_total,
        unit="rows",
        state="measured",
        source=display_path(market_path, root),
        note=f"{missing_side_total} source rows lacked at least one finite side.",
    )

    carry_totals = carry["totals"]
    for metric, value, unit, note in (
        (
            "raw_valid_two_sided_quotes_before_carry",
            int(carry_totals["raw_valid_two_sided_quotes"]),
            "rows",
            "Raw source rows already had finite positive non-crossed bid and ask.",
        ),
        (
            "rows_restored_by_side_carry_forward",
            int(carry_totals["rows_with_any_side_carried_into_valid_quote"]),
            "rows",
            "Rows made executable by carrying at least one prior side; this can combine sides from different source rows.",
        ),
        (
            "tickbook_rows_retained_after_carry",
            int(carry_totals["rows_retained_after_carry"]),
            "rows",
            "Current TickBook transform, no session-hour filter, source rows hash-checked before and after.",
        ),
        (
            "rows_dropped_after_carry",
            int(carry_totals["rows_dropped_for_unavailable_side_after_carry"])
            + int(carry_totals["rows_dropped_for_crossed_pair_after_carry"]),
            "rows",
            "Post-carry drop reason counts are mutually exclusive and sum to this value.",
        ),
    ):
        add_stage(
            stage_rows,
            group="local_tickbook_transform",
            scope="all four hash-verified campaign tick inputs",
            stage="raw_to_tickbook_quotes",
            metric=metric,
            value=value,
            unit=unit,
            state="measured",
            source=str(CARRY_FORWARD),
            note=note,
        )

    # Feature and candidate counts describe the selected training-only census
    # profile. They are not joined to the separate saved A4A/A4B policy runs.
    census_scope = "selected training-only opportunity census profile"
    add_stage(
        stage_rows,
        group="candidate_census",
        scope=census_scope,
        stage="feature_ready_rows",
        metric="primary_symbol_m1_rows",
        value=int(census["feature_rows"]),
        unit="rows",
        state="measured",
        source=str(CENSUS),
        note="The census states this equals training_m1_rows; one selected profile, not all features/configs.",
    )
    add_stage(
        stage_rows,
        group="candidate_census",
        scope=census_scope,
        stage="eligible_candidates",
        metric="active_candidate_row_occurrences",
        value=int(cardinality["active_candidate_profile"]["active_candidate_row_occurrences"]),
        unit="candidate-row occurrences",
        state="measured",
        source=str(CARDINALITY),
        note="Across supported candidate tuples; not unique decisions, events, orders, or trades.",
    )
    add_stage(
        stage_rows,
        group="candidate_census",
        scope=census_scope,
        stage="eligible_candidates",
        metric="supported_candidate_tuples",
        value=int(census["supported_candidate_count"]),
        unit="configured tuples",
        state="measured",
        source=str(CENSUS),
        note="Of the configured setup catalog; support does not imply a valid order or trade.",
    )
    add_stage(
        stage_rows,
        group="candidate_census",
        scope=census_scope,
        stage="eligible_candidates",
        metric="unsupported_candidate_tuples",
        value=int(census["unsupported_candidate_count"]),
        unit="configured tuples",
        state="measured",
        source=str(CENSUS),
        note="Disabled/unsupported by the selected profile; not missing observations or zero activity.",
    )
    add_stage(
        stage_rows,
        group="candidate_census",
        scope=census_scope,
        stage="eligible_candidates",
        metric="active_rows_missing_required_source_time",
        value=int(cardinality["active_candidate_profile"]["missing_source_time_rows"]),
        unit="candidate-row occurrences",
        state="measured",
        source=str(CARDINALITY),
        note="Zero means no missing required timestamp among this census's active rows only.",
    )

    # Historical policy diagnostics have valid decision/fill/position marginal
    # counts but no candidate proposal/action/order identity chain.
    diagnostic_paths = sorted(
        (root / CAMPAIGN / "runs/attempts").rglob("evaluation_diagnostics.json")
    )
    if len(diagnostic_paths) != 4:
        raise ValueError(
            f"expected four selected A4A/A4B diagnostics, found {len(diagnostic_paths)}"
        )
    runs: list[dict[str, Any]] = []
    for diagnostics_path in diagnostic_paths:
        diagnostics = read_json(diagnostics_path)
        run_root = diagnostics_path.parent
        relative = diagnostics_path.relative_to(root)
        arm = next(
            (part.split("_")[1].upper() for part in relative.parts if part.startswith("ladder_a4")),
            None,
        )
        partition = run_root.name
        if arm not in {"A4A", "A4B"} or partition not in {"training", "testing"}:
            raise ValueError(f"unexpected selected run path: {relative}")
        fills_path = run_root / "fills.csv"
        positions_path = run_root / "positions.csv"
        if not fills_path.is_file() or not positions_path.is_file():
            raise ValueError(f"selected run lacks fill or position ledger: {run_root}")
        fill_rows, fill_types = count_csv(fills_path)
        positions: list[dict[str, str]] = []
        with positions_path.open(newline="", encoding="utf-8") as handle:
            positions = list(csv.DictReader(handle))
        completed = sum(bool_value(row.get("completed")) for row in positions)
        identified_positions = int(diagnostics.get("identified_position_count", -1))
        execution_events = int(diagnostics.get("execution_event_count", -1))
        if fill_rows != execution_events or len(positions) != identified_positions:
            raise ValueError(f"diagnostics/CSV row mismatch for {arm} {partition}")
        if completed != int(diagnostics["entry_state_diagnostics"].get("closed", -2)):
            raise ValueError(f"completed position/closed transition mismatch for {arm} {partition}")

        scope = f"{arm} {partition} policy-evaluation partition"
        source_label = str(relative)
        entry = diagnostics.get("entry_state_diagnostics", {})
        funnel = diagnostics.get("entry_funnel", {})
        summary = {
            "arm": arm,
            "partition": partition,
            "scope": scope,
            "environment_steps": int(diagnostics["n_steps"]),
            "sessions": int(diagnostics["n_sessions"]),
            "entry_state_candidate_created": int(entry.get("candidate_created", 0)),
            "entry_state_trigger_requested": int(entry.get("trigger_requested", 0)),
            "entry_state_trigger_refused": int(entry.get("trigger_refused", 0)),
            "entered_positions": int(entry.get("entered", 0)),
            "execution_events": execution_events,
            "fill_event_rows_by_type": dict(sorted(fill_types.items())),
            "position_rows": len(positions),
            "completed_position_rows": completed,
            "order_attempt_count": None,
            "accepted_order_count": None,
            "historical_candidate_to_action_links": None,
            "entry_funnel_counts": {str(k): int(v) for k, v in sorted(funnel.items())},
            "source_files": {
                "diagnostics": source_label,
                "fills": str(fills_path.relative_to(root)),
                "positions": str(positions_path.relative_to(root)),
            },
        }
        runs.append(summary)
        source_paths.update({diagnostics_path, fills_path, positions_path})
        add_stage(
            stage_rows,
            group="selected_policy_runs",
            scope=scope,
            stage="session_decisions",
            metric="policy_environment_steps",
            value=numeric_value(summary["environment_steps"], field="environment_steps"),
            unit="steps",
            state="measured",
            source=source_label,
            note="One vectorized environment step per saved decision row; not a per-session decision decomposition.",
        )
        add_stage(
            stage_rows,
            group="selected_policy_runs",
            scope=scope,
            stage="session_decisions",
            metric="evaluated_sessions",
            value=numeric_value(summary["sessions"], field="sessions"),
            unit="sessions",
            state="measured",
            source=source_label,
            note="Session count from diagnostics; no action-by-session table is available here.",
        )
        for metric, key in (
            ("entry_state_candidate_created", "entry_state_candidate_created"),
            ("entry_fsm_trigger_requests", "entry_state_trigger_requested"),
            ("entry_fsm_trigger_refusals", "entry_state_trigger_refused"),
            ("entered_positions", "entered_positions"),
            ("execution_event_rows", "execution_events"),
            ("position_rows", "position_rows"),
            ("completed_positions", "completed_position_rows"),
        ):
            add_stage(
                stage_rows,
                group="selected_policy_runs",
                scope=scope,
                stage=metric,
                metric=metric,
                value=numeric_value(summary[key], field=key),
                unit="events"
                if "event" in metric or "trigger" in metric
                else "positions"
                if "position" in metric
                else "rows",
                state="measured",
                source=source_label,
                note="Marginal count only; no historical proposal-to-order join.",
            )
        add_stage(
            stage_rows,
            group="selected_policy_runs",
            scope=scope,
            stage="orders",
            metric="order_attempt_count",
            value=None,
            unit="orders",
            state="not_recorded",
            source=source_label,
            note="Trigger requests are FSM events, not broker order submissions.",
        )
        add_stage(
            stage_rows,
            group="selected_policy_runs",
            scope=scope,
            stage="orders",
            metric="accepted_order_count",
            value=None,
            unit="orders",
            state="not_recorded",
            source=source_label,
            note="No order identity or accepted-order ledger in the scanned historical artifacts.",
        )
        add_stage(
            stage_rows,
            group="selected_policy_runs",
            scope=scope,
            stage="candidate_to_action_linkage",
            metric="historical_candidate_to_action_links",
            value=None,
            unit="links",
            state="not_recorded_in_scanned_artifacts",
            source=str(CARDINALITY),
            note="Scoped scan only; not a global absence claim.",
        )

    # Record data-source identities, including expected and observed hashes.
    raw_inputs = []
    for item in market["inputs"]:
        raw_inputs.append(
            {
                "path": item.get("path"),
                "kind": item.get("kind"),
                "role": item.get("role", item.get("source_role")),
                "row_count": item.get("row_count"),
                "bytes": item.get("bytes"),
                "expected_sha256": item.get("expected_sha256"),
                "observed_sha256": item.get("observed_sha256"),
                "hash_matches_manifest": item.get("hash_matches_manifest"),
            }
        )

    source_hashes = {display_path(path, root): sha256(path) for path in sorted(source_paths)}
    report = {
        "schema": "qrl.pipeline_denominator_register.v1",
        "status": "verified_marginal_denominators_with_unavailable_links_explicit",
        "repository_head": market.get("repository_head"),
        "generated_from_current_worktree": True,
        "market_data_quality_scan": {
            "path": display_path(market_path, root),
            "sha256": sha256(market_path),
            "input_count": int(market["input_count"]),
            "input_bytes_scanned": int(market["input_bytes_scanned"]),
            "all_inputs_present": bool(market["all_inputs_present"]),
            "all_input_hashes_match": bool(market["all_input_hashes_match"]),
            "bar_rows_by_role": {
                role: count for (role, kind), count in sorted(raw_totals.items()) if kind == "bar"
            },
            "tick_rows_by_role": {
                role: count for (role, kind), count in sorted(raw_totals.items()) if kind == "tick"
            },
            "tick_rows_total": tick_rows_total,
            "finite_two_sided_quote_rows_total": usable_quotes_total,
            "tick_rows_missing_at_least_one_finite_side": missing_side_total,
            "quote_denominator_rule": "raw tick row minus rows missing/nonfinite bid or ask; exact for this scan because nonpositive and inverted quote counts are zero",
        },
        "tickbook_carry_forward_audit": {
            "path": str(CARRY_FORWARD),
            "sha256": sha256(carry_path),
            "tick_builder_sha256_at_run": carry["tick_builder_sha256"],
            "totals": carry_totals,
            "rows_carried_forward_are_not_simultaneous_quote_proof": True,
        },
        "candidate_census": {
            "path": str(CENSUS),
            "sha256": sha256(census_path),
            "profile_scope": census_scope,
            "training_m1_rows": int(census["training_m1_rows"]),
            "feature_ready_rows": int(census["feature_rows"]),
            "configured_candidates": int(census["candidate_count"]),
            "supported_candidate_tuples": int(census["supported_candidate_count"]),
            "unsupported_candidate_tuples": int(census["unsupported_candidate_count"]),
            "active_candidate_row_occurrences": int(
                cardinality["active_candidate_profile"]["active_candidate_row_occurrences"]
            ),
            "active_rows_missing_required_source_time": int(
                cardinality["active_candidate_profile"]["missing_source_time_rows"]
            ),
            "runtime_inactive_candidate_rows": None,
            "runtime_inactive_candidate_rows_state": "not_emitted_as_a_distinct_denominator",
        },
        "selected_policy_evaluations": runs,
        "flow_interpretation": {
            "single_joined_funnel_available": False,
            "missing_is_distinct_from_zero": True,
            "unsupported_candidates_are_not_missing_or_inactive_rows": True,
            "entry_fsm_triggers_are_not_order_submissions": True,
            "exposed_report_period": "2026-01-01 through 2026-10-16; exploratory/report-only, not untouched OOS",
            "limitations": [
                "Local source-row and quote-quality counts, candidate-census counts, and selected policy-run counts use different profiles or units and are not joined into one funnel.",
                "No historical action-by-session decomposition, broker order-attempt ledger, accepted-order ledger, or candidate-to-action identity chain is present in the scanned artifacts.",
                "Entry-state trigger requests and refusals are recorded, but are not broker order counts.",
                "Reported fills, positions, and closures are marginal counts checked against their selected run diagnostics and CSV ledgers.",
                "All historical policy ‘testing’ partitions are in the exposed report period and are not untouched OOS.",
                "Counts make no provider, license, authoritative clock, or external session-calendar claim.",
                "The TickBook carry-forward result is a current preprocessing count; carried bid/ask sides need not have been observed simultaneously.",
            ],
        },
        "source_artifact_sha256": source_hashes,
        "raw_input_identities": raw_inputs,
    }
    return report, stage_rows


def write_packet(root: Path, out_dir: Path, market_quality_path: Path = MARKET_QUALITY) -> None:
    report, stage_rows = collect(root, market_quality_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    register_path = out_dir / "pipeline_denominator_register.json"
    csv_path = out_dir / "pipeline_stage_counts.csv"
    readme_path = out_dir / "README.md"
    register_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(stage_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(stage_rows)

    run_rows = report["selected_policy_evaluations"]
    carry_totals = report["tickbook_carry_forward_audit"]["totals"]
    table = [
        "| Run partition | Steps | Sessions | Candidate created | Trigger requested / refused | Open fills | Execution rows | Positions | Completed | Orders |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in run_rows:
        open_fills = int(run["fill_event_rows_by_type"].get("open", 0))
        table.append(
            f"| {run['arm']} {run['partition']} | {run['environment_steps']} | {run['sessions']} | "
            f"{run['entry_state_candidate_created']} | {run['entry_state_trigger_requested']} / "
            f"{run['entry_state_trigger_refused']} | {open_fills} | {run['execution_events']} | "
            f"{run['position_rows']} | {run['completed_position_rows']} | not recorded |"
        )
    readme = "\n".join(
        [
            "# Pipeline denominator register",
            "",
            "This packet inventories the denominators available at each research-pipeline stage. It keeps separately sourced counts separate: the local data audit, the selected training-only candidate census, and the archived A4A/A4B policy evaluations are different scopes and do not form one joined funnel.",
            "",
            "## Local data",
            "",
            f"The current-byte quality scan covers {report['market_data_quality_scan']['input_count']} manifested inputs ({report['market_data_quality_scan']['input_bytes_scanned']:,} bytes). It records {sum(report['market_data_quality_scan']['bar_rows_by_role'].values()):,} bar rows and {report['market_data_quality_scan']['tick_rows_total']:,} tick rows, of which {report['market_data_quality_scan']['finite_two_sided_quote_rows_total']:,} have finite and non-crossed bid/ask sides in the raw row. The {report['market_data_quality_scan']['tick_rows_missing_at_least_one_finite_side']:,} rows missing at least one side are excluded from that raw quote count. Nonpositive and inverted raw quote counts are zero.",
            "",
            f"The current production TickBook builder restores {carry_totals['rows_with_any_side_carried_into_valid_quote']:,} rows using independent side carry-forward, retains {carry_totals['rows_retained_after_carry']:,} rows total, and drops {int(carry_totals['rows_dropped_for_unavailable_side_after_carry']) + int(carry_totals['rows_dropped_for_crossed_pair_after_carry']):,}. The restored-row count does not imply simultaneous bid/ask availability.",
            "",
            "## Feature and candidate census",
            "",
            f"The selected training-only census reports {report['candidate_census']['feature_ready_rows']:,} primary-symbol M1 feature rows. Its configured catalog has {report['candidate_census']['configured_candidates']} setup tuples: {report['candidate_census']['supported_candidate_tuples']} supported and {report['candidate_census']['unsupported_candidate_tuples']} unsupported by that profile. It records {report['candidate_census']['active_candidate_row_occurrences']:,} supported candidate-row occurrences, with {report['candidate_census']['active_rows_missing_required_source_time']} active rows missing required source time. Unsupported tuples are not counted as missing observations or runtime-inactive rows.",
            "",
            "## Archived policy evaluation marginals",
            "",
            *table,
            "",
            "`trigger requested/refused` are entry-state-machine events, not submitted/accepted broker orders. The historical artifacts do not record order-attempt or accepted-order counts, action-by-session decisions, or a candidate-to-action ID chain. These are marked unavailable, not zero. All position rows in this selected packet are marked completed and reconcile to the recorded closed-position count.",
            "",
            "## Interpretation limits",
            "",
            "- The rows above are marginal counts with distinct scopes and units; do not divide one stage by another across evidence groups or describe them as conversion rates.",
            "- Candidate row occurrences are not unique decisions, logical events, orders, fills, or trades.",
            "- The evaluation `testing` partition is the exposed 2026-01-01 through 2026-10-16 report period; it is exploratory, not untouched OOS.",
            "- Local counts do not establish provider rights, authoritative time, or external session-calendar facts.",
            "- See `pipeline_denominator_register.json` for hashes, per-input identities, explicit null states, TickBook carry-forward counts, and all four run partitions; `pipeline_stage_counts.csv` is the flattened stage inventory.",
            "",
            "## Reproduction",
            "",
            "Run the generator on the same checkout and local evidence inputs:",
            "",
            "```bash",
            "PYTHONPATH=. .venv/bin/python -m scripts.research.analysis.market_data.build_pipeline_denominator_register",
            "```",
            "",
        ]
    )
    readme_path.write_text(readme, encoding="utf-8")
    checksums = []
    for path in (register_path, csv_path, readme_path):
        checksums.append(f"{sha256(path)}  {path.name}")
    (out_dir / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(out_dir),
                "input_rows": report["market_data_quality_scan"]["tick_rows_total"],
                "usable_quote_rows": report["market_data_quality_scan"][
                    "finite_two_sided_quote_rows_total"
                ],
                "feature_rows": report["candidate_census"]["feature_ready_rows"],
                "candidate_row_occurrences": report["candidate_census"][
                    "active_candidate_row_occurrences"
                ],
                "selected_policy_partitions": len(run_rows),
                "recorded_order_attempt_counts": None,
                "recorded_order_attempt_counts_state": "not recorded; null in packet",
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--market-quality", type=Path, default=MARKET_QUALITY)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("evidence/research/pipeline_denominators"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    write_packet(root, out_dir, args.market_quality)


if __name__ == "__main__":
    main()
