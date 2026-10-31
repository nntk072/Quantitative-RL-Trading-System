"""Decision and structural-validity diagnostics for setup-conditioned policies."""

from __future__ import annotations

from collections import Counter
from typing import Any, cast

import numpy as np
import pandas as pd

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_IDEAS,
    TRADE_SETUP_TIMEFRAMES,
    trade_setup_candidate,
)

_STRUCTURAL_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H2", "H4", "D1", "W1")
_TIMEFRAME_RANK = {name: index for index, name in enumerate(_STRUCTURAL_TIMEFRAMES)}
_SESSION_REFERENCE_PREFIXES = ("asian_", "london_", "prev_day_", "ctx_prev_week_")


def _reference_timeframes(reference: object) -> tuple[list[str], bool]:
    """Return candle timeframes and whether a reference contains session levels.

    SL/TP source strings can combine several references with ``|``. Session
    highs/lows have no candle timeframe, but remain valid structural anchors.
    Unprefixed candle references follow the execution resolver and mean M1.
    """
    if reference is None or reference is pd.NA or reference is pd.NaT:
        return [], False
    if isinstance(reference, (float, np.floating)) and np.isnan(reference):
        return [], False
    timeframes: list[str] = []
    has_session_reference = False
    for source in str(reference or "").split("|"):
        source = source.strip()
        if not source:
            continue
        if source.startswith(_SESSION_REFERENCE_PREFIXES):
            has_session_reference = True
            continue
        matched = next(
            (tf for tf in _STRUCTURAL_TIMEFRAMES if source.startswith(f"{tf}_")),
            None,
        )
        timeframes.append(matched or "M1")
    return timeframes, has_session_reference


def summarize_trade_setup_decisions(
    decisions: pd.DataFrame, trades: pd.DataFrame
) -> dict[str, Any]:
    """Return benchmark metrics for policy choices, entropy, and structural safety."""
    canonical_wire_schema = "trade_setup_candidate_id" in decisions.columns or (
        "trade_setup_candidate_id" in trades.columns
    )
    decisions = decisions.rename(
        columns={
            "trade_setup_candidate_id": "thesis_candidate_id",
            "trade_setup_entropy_nats": "thesis_entropy_nats",
            "eligible_trade_setup_ids": "eligible_candidate_ids",
        }
    )
    trades = trades.rename(
        columns={
            "trade_setup_candidate_id": "thesis_candidate_id",
            "trade_setup_schema_version": "thesis_schema_version",
        }
    )
    if decisions.empty:
        decision_metrics: dict[str, Any] = {
            "decision_steps": 0,
            "no_trade_count": 0,
            "no_trade_rate": None,
            "invalid_selection_count": 0,
            "invalid_selection_rate": None,
            "selected_idea_count": 0,
            "selected_timeframe_count": 0,
            "thesis_entropy_mean_nats": None,
            "thesis_entropy_by_month": [],
            "selection_counts": [],
            "execution_action_by_thesis": [],
            "no_trade_only_eligible_steps": 0,
            "trade_thesis_eligible_steps": 0,
            "eligible_trade_thesis_count_mean": None,
            "eligible_trade_thesis_count_median": None,
            "eligible_trade_thesis_count_max": 0,
            "no_trade_rate_when_trade_thesis_eligible": None,
            "selection_by_idea": [],
            "selection_by_timeframe": [],
            "selection_matrix": [],
            "execution_by_opened_thesis": [],
            "performance_by_idea_timeframe": [],
        }
    else:
        selected = pd.to_numeric(decisions["thesis_candidate_id"], errors="raise").astype(int)
        no_trade = selected.eq(NO_TRADE_ID)
        ideas = decisions.loc[~no_trade, "idea"].fillna("").astype(str)
        timeframes = decisions.loc[~no_trade, "setup_timeframe"].fillna("").astype(str)
        entropy = pd.to_numeric(decisions["thesis_entropy_nats"], errors="coerce")
        timestamps = pd.to_datetime(decisions["time"], errors="coerce", utc=True)
        entropy_rows = pd.DataFrame(
            {
                "month": timestamps.dt.strftime("%Y-%m"),
                "entropy": entropy,
                "no_trade": no_trade.astype(float),
            }
        )
        entropy_by_month = (
            entropy_rows.dropna(subset=["month", "entropy"])
            .groupby("month", sort=True)
            .agg(
                count=("entropy", "count"),
                mean=("entropy", "mean"),
                median=("entropy", "median"),
                no_trade_rate=("no_trade", "mean"),
            )
            .reset_index()
            .to_dict(orient="records")
        )
        selected_counts = selected.value_counts().sort_index()
        selection_counts = [
            {
                "candidate_id": int(cast(int, candidate_id)),
                "idea": TRADE_SETUP_CANDIDATES[cast(int, candidate_id)].idea,
                "setup_timeframe": TRADE_SETUP_CANDIDATES[cast(int, candidate_id)].setup_timeframe,
                "direction": TRADE_SETUP_CANDIDATES[cast(int, candidate_id)].direction,
                "count": int(count),
            }
            for candidate_id, count in selected_counts.items()
        ]
        invalid = ~decisions["selection_valid"].astype(bool)
        decision_metrics = {
            "decision_steps": int(len(decisions)),
            "no_trade_count": int(no_trade.sum()),
            "no_trade_rate": float(no_trade.mean()),
            "invalid_selection_count": int(invalid.sum()),
            "invalid_selection_rate": float(invalid.mean()),
            "selected_idea_count": int(ideas[ideas.ne("")].nunique()),
            "selected_timeframe_count": int(timeframes[timeframes.ne("")].nunique()),
            "thesis_entropy_mean_nats": float(entropy.mean()),
            "thesis_entropy_by_month": entropy_by_month,
            "selection_counts": selection_counts,
        }
        action_columns = [name for name in decisions if str(name).startswith("action_")]
        execution_by_thesis: list[dict[str, Any]] = []
        if action_columns:
            executions = decisions.loc[~no_trade].groupby(
                ["idea", "setup_timeframe"], dropna=False, sort=True
            )
            for (idea, timeframe), group in executions:
                row: dict[str, Any] = {
                    "idea": str(idea),
                    "setup_timeframe": str(timeframe),
                    "decision_count": int(len(group)),
                }
                for column in action_columns:
                    values = pd.to_numeric(group[column], errors="coerce").dropna()
                    if not values.empty:
                        row[f"{column}_mean"] = float(values.mean())
                        row[f"{column}_std"] = float(values.std(ddof=0))
                execution_by_thesis.append(row)
        decision_metrics["execution_action_by_thesis"] = execution_by_thesis
        eligible_ids = [
            {int(value) for value in values if int(value) != NO_TRADE_ID}
            for values in decisions["eligible_candidate_ids"]
        ]
        eligible_sizes = np.asarray([len(values) for values in eligible_ids], dtype=np.int64)
        trade_eligible_steps = eligible_sizes > 0
        selected_trade = selected[~no_trade]
        idea_rows: list[dict[str, Any]] = []
        timeframe_rows: list[dict[str, Any]] = []
        matrix_rows: list[dict[str, Any]] = []
        for idea in TRADE_SETUP_IDEAS:
            idea_ids = {item.candidate_id for item in TRADE_SETUP_CANDIDATES if item.idea == idea}
            eligible_occurrences = sum(len(values & idea_ids) for values in eligible_ids)
            eligible_steps = sum(bool(values & idea_ids) for values in eligible_ids)
            selected_count = int(
                sum(TRADE_SETUP_CANDIDATES[int(value)].idea == idea for value in selected_trade)
            )
            idea_rows.append(
                {
                    "idea": idea,
                    "eligible_candidate_occurrences": eligible_occurrences,
                    "eligible_steps": eligible_steps,
                    "selected_count": selected_count,
                    "selection_share": float(selected_count / max(1, len(selected_trade))),
                    "selection_rate_given_eligible_step": float(
                        selected_count / max(1, eligible_steps)
                    ),
                }
            )
            for timeframe in TRADE_SETUP_TIMEFRAMES:
                cell_ids = {
                    item.candidate_id
                    for item in TRADE_SETUP_CANDIDATES
                    if item.idea == idea and item.setup_timeframe == timeframe
                }
                cell_eligible_occurrences = sum(len(values & cell_ids) for values in eligible_ids)
                cell_eligible_steps = sum(bool(values & cell_ids) for values in eligible_ids)
                cell_selected = int(
                    sum(
                        TRADE_SETUP_CANDIDATES[int(value)].idea == idea
                        and TRADE_SETUP_CANDIDATES[int(value)].setup_timeframe == timeframe
                        for value in selected_trade
                    )
                )
                matrix_rows.append(
                    {
                        "idea": idea,
                        "timeframe": timeframe,
                        "eligible_candidate_occurrences": cell_eligible_occurrences,
                        "eligible_steps": cell_eligible_steps,
                        "selected_count": cell_selected,
                        "selection_share": float(cell_selected / max(1, len(selected_trade))),
                        "selection_rate_given_eligible_step": float(
                            cell_selected / max(1, cell_eligible_steps)
                        ),
                    }
                )
        for timeframe in TRADE_SETUP_TIMEFRAMES:
            tf_ids = {
                item.candidate_id
                for item in TRADE_SETUP_CANDIDATES
                if item.setup_timeframe == timeframe
            }
            eligible_occurrences = sum(len(values & tf_ids) for values in eligible_ids)
            eligible_steps = sum(bool(values & tf_ids) for values in eligible_ids)
            selected_count = int(
                sum(
                    TRADE_SETUP_CANDIDATES[int(value)].setup_timeframe == timeframe
                    for value in selected_trade
                )
            )
            timeframe_rows.append(
                {
                    "timeframe": timeframe,
                    "eligible_candidate_occurrences": eligible_occurrences,
                    "eligible_steps": eligible_steps,
                    "selected_count": selected_count,
                    "selection_share": float(selected_count / max(1, len(selected_trade))),
                    "selection_rate_given_eligible_step": float(
                        selected_count / max(1, eligible_steps)
                    ),
                }
            )
        decision_metrics.update(
            {
                "no_trade_only_eligible_steps": int((eligible_sizes == 0).sum()),
                "trade_thesis_eligible_steps": int(trade_eligible_steps.sum()),
                "eligible_trade_thesis_count_mean": float(eligible_sizes.mean()),
                "eligible_trade_thesis_count_median": float(np.median(eligible_sizes)),
                "eligible_trade_thesis_count_max": int(eligible_sizes.max(initial=0)),
                "no_trade_rate_when_trade_thesis_eligible": float(
                    (no_trade & trade_eligible_steps).sum()
                    / max(1, int(trade_eligible_steps.sum()))
                ),
                "selection_by_idea": idea_rows,
                "selection_by_timeframe": timeframe_rows,
                "selection_matrix": matrix_rows,
            }
        )

    opens = trades.loc[
        trades.get("type", pd.Series(index=trades.index, dtype=object)).eq("open")
    ].copy()
    sl_side_violations = 0
    sl_timeframe_floor_violations = 0
    sd_timeframe_violations = 0
    allowed_lower_timeframe_tp_references = 0
    tp_side_violations = 0
    trades_with_any_violation = 0
    semantic_violations: Counter[str] = Counter()
    for trade_row in opens.to_dict(orient="records"):
        direction_value = _finite(trade_row.get("primary_direction", trade_row.get("direction", 0)))
        direction = int(direction_value or 0)
        entry = _finite(trade_row.get("price"))
        sl = _finite(trade_row.get("sl_price"))
        tp = _finite(trade_row.get("tp_price"))
        row_sl_side = int(
            entry is not None
            and sl is not None
            and ((direction == 1 and sl >= entry) or (direction == -1 and sl <= entry))
        )
        row_tp_side = int(
            entry is not None
            and tp is not None
            and ((direction == 1 and tp <= entry) or (direction == -1 and tp >= entry))
        )
        sl_side_violations += row_sl_side
        tp_side_violations += row_tp_side
        setup_tf = str(trade_row.get("primary_setup_timeframe", "")).upper()
        sl_tf = str(trade_row.get("sl_timeframe", "")).upper()
        sl_reference_tfs, has_session_sl_reference = _reference_timeframes(
            trade_row.get("sl_ref", "")
        )
        if sl_tf in _TIMEFRAME_RANK and sl_tf not in sl_reference_tfs:
            sl_reference_tfs.append(sl_tf)
        row_sl_floor = 0
        if setup_tf in _TIMEFRAME_RANK and sl_reference_tfs:
            row_sl_floor = int(
                any(_TIMEFRAME_RANK[tf] < _TIMEFRAME_RANK[setup_tf] for tf in sl_reference_tfs)
            )
            sl_timeframe_floor_violations += row_sl_floor
        elif setup_tf in _TIMEFRAME_RANK and has_session_sl_reference:
            # Session anchors (Asian/London/day/week) are valid structure refs
            # without a candle-timeframe label.
            pass
        else:
            semantic_violations["missing_primary_or_sl_timeframe"] += 1
        selected_refs = [
            reference
            for reference in trade_row.get("tp_references", [])
            if isinstance(reference, dict) and reference.get("reason") == "selected"
        ]
        selected_tfs: list[str] = []
        has_session_tp_reference = False
        for reference in selected_refs:
            reference_tf = str(reference.get("timeframe", "")).upper()
            if reference_tf in _TIMEFRAME_RANK:
                selected_tfs.append(reference_tf)
                continue
            source_names = reference.get("sources") or [reference.get("name", "")]
            if isinstance(source_names, str):
                source_names = [source_names]
            parsed_tfs, has_session = _reference_timeframes("|".join(map(str, source_names)))
            selected_tfs.extend(parsed_tfs)
            has_session_tp_reference = has_session_tp_reference or has_session
        if not selected_tfs:
            fallback_tf = str(trade_row.get("tp_timeframe", "")).upper()
            if fallback_tf:
                selected_tfs = [fallback_tf]
        if not selected_tfs and not has_session_tp_reference:
            tp_reference_tfs, has_session_tp_reference = _reference_timeframes(
                trade_row.get("tp_ref", "")
            )
            selected_tfs.extend(tp_reference_tfs)
        row_tp_floor = int(
            setup_tf in _TIMEFRAME_RANK
            and any(
                tf in _TIMEFRAME_RANK and _TIMEFRAME_RANK[tf] < _TIMEFRAME_RANK[setup_tf]
                for tf in selected_tfs
            )
        )
        allowed_lower_timeframe_tp_references += row_tp_floor
        if (
            not selected_tfs
            and not has_session_tp_reference
            and str(trade_row.get("tp_ref", "")).lower() not in {"", "ema_21"}
        ):
            semantic_violations["missing_primary_or_tp_timeframe"] += 1
        row_sd = 0
        if str(trade_row.get("primary_idea", "")) == "standard_deviation":
            sl_ref = str(trade_row.get("sl_ref", "")).upper()
            expected_sd_ref = (
                "STANDARD_DEVIATION_LEVEL_1_PRICE"
                if setup_tf == "M1"
                else f"{setup_tf}_STANDARD_DEVIATION_LEVEL_1_PRICE"
            )
            row_sd = int(
                setup_tf not in TRADE_SETUP_TIMEFRAMES or not sl_ref.startswith(expected_sd_ref)
            )
            sd_timeframe_violations += row_sd
        try:
            candidate = trade_setup_candidate(int(trade_row.get("thesis_candidate_id", -1)))
        except (TypeError, ValueError):
            candidate = None
        if candidate is None or candidate.is_no_trade:
            semantic_violations["unresolvable_or_no_trade_candidate_opened"] += 1
        elif (
            candidate.idea != trade_row.get("primary_idea")
            or candidate.setup_timeframe != setup_tf
            or candidate.direction != direction
        ):
            semantic_violations["candidate_fields_disagree"] += 1
        if not trade_row.get("thesis_schema_version"):
            semantic_violations["missing_thesis_schema_version"] += 1
        trades_with_any_violation += int(any((row_sl_side, row_sl_floor, row_sd, row_tp_side)))

    open_counts = Counter(
        (str(row.get("primary_idea", "")), str(row.get("primary_setup_timeframe", "")))
        for row in opens.to_dict(orient="records")
        if row.get("primary_idea") and row.get("primary_setup_timeframe")
    )
    decision_metrics["opened_trade_count"] = int(len(opens))
    decision_metrics["opened_trade_idea_count"] = len({idea for idea, _ in open_counts})
    decision_metrics["opened_trade_timeframe_count"] = len(
        {timeframe for _, timeframe in open_counts}
    )
    decision_metrics["opened_trade_counts"] = [
        {"idea": idea, "setup_timeframe": timeframe, "count": count}
        for (idea, timeframe), count in sorted(open_counts.items())
    ]
    execution_by_opened_thesis: list[dict[str, Any]] = []
    if not opens.empty and {"primary_idea", "primary_setup_timeframe"}.issubset(opens.columns):
        for (idea, timeframe), group in opens.groupby(
            ["primary_idea", "primary_setup_timeframe"], dropna=False, sort=True
        ):
            summary: dict[str, Any] = {
                "idea": str(idea),
                "setup_timeframe": str(timeframe),
                "trade_count": int(len(group)),
            }
            for column in ("risk_cash", "risk_frac", "stop_distance", "planned_rr"):
                if column in group.columns:
                    values = pd.to_numeric(group[column], errors="coerce").dropna()
                    if not values.empty:
                        summary[f"{column}_median"] = float(values.median())
                        summary[f"{column}_mean"] = float(values.mean())
            for column in ("sl_ref", "tp_ref", "sl_timeframe", "tp_timeframe", "exit_mode"):
                if column in group.columns:
                    summary[f"{column}_counts"] = {
                        str(key): int(value)
                        for key, value in group[column]
                        .fillna("")
                        .astype(str)
                        .value_counts()
                        .items()
                    }
            execution_by_opened_thesis.append(summary)
    decision_metrics["execution_by_opened_thesis"] = execution_by_opened_thesis
    performance_by_thesis: list[dict[str, Any]] = []
    if not opens.empty and {"primary_idea", "primary_setup_timeframe"}.issubset(opens.columns):
        for (idea, timeframe), group in opens.groupby(
            ["primary_idea", "primary_setup_timeframe"], dropna=False, sort=True
        ):
            performance_row: dict[str, Any] = {
                "idea": str(idea),
                "setup_timeframe": str(timeframe),
                "trade_count": int(len(group)),
            }
            pnl = pd.to_numeric(
                group.get("position_net_pnl", pd.Series(index=group.index, dtype=float)),
                errors="coerce",
            ).dropna()
            if not pnl.empty:
                winners = pnl[pnl > 0.0]
                losers = pnl[pnl < 0.0]
                performance_row.update(
                    {
                        "completed_trade_count": int(len(pnl)),
                        "net_pnl": float(pnl.sum()),
                        "mean_pnl": float(pnl.mean()),
                        "median_pnl": float(pnl.median()),
                        "win_rate": float((pnl > 0.0).mean()),
                        "profit_factor": (
                            float(winners.sum() / abs(losers.sum())) if not losers.empty else None
                        ),
                    }
                )
            realized_r = pd.to_numeric(
                group.get("position_realized_r", pd.Series(index=group.index, dtype=float)),
                errors="coerce",
            ).dropna()
            if not realized_r.empty:
                performance_row["mean_realized_r"] = float(realized_r.mean())
                performance_row["median_realized_r"] = float(realized_r.median())
                performance_row["realized_r_trade_count"] = int(len(realized_r))
            performance_by_thesis.append(performance_row)
    decision_metrics["performance_by_idea_timeframe"] = performance_by_thesis
    decision_metrics["structural_violations"] = {
        "sl_wrong_side": sl_side_violations,
        "sl_below_primary_timeframe": sl_timeframe_floor_violations,
        # Informational only: lower-timeframe TPs are explicitly allowed.
        "tp_below_primary_timeframe": allowed_lower_timeframe_tp_references,
        "standard_deviation_sl_not_level_1_on_setup_timeframe": sd_timeframe_violations,
        "tp_wrong_side": tp_side_violations,
        "total": trades_with_any_violation,
    }
    decision_metrics["semantic_violations"] = dict(sorted(semantic_violations.items()))
    decision_metrics["semantic_violation_count"] = int(sum(semantic_violations.values()))
    if canonical_wire_schema:
        key_names = {
            "thesis_entropy_mean_nats": "trade_setup_entropy_mean_nats",
            "thesis_entropy_by_month": "trade_setup_entropy_by_month",
            "execution_action_by_thesis": "execution_action_by_trade_setup",
            "trade_thesis_eligible_steps": "trade_setup_eligible_steps",
            "eligible_trade_thesis_count_mean": "eligible_trade_setup_count_mean",
            "eligible_trade_thesis_count_median": "eligible_trade_setup_count_median",
            "eligible_trade_thesis_count_max": "eligible_trade_setup_count_max",
            "no_trade_rate_when_trade_thesis_eligible": "no_trade_rate_when_trade_setup_eligible",
            "execution_by_opened_thesis": "execution_by_opened_trade_setup",
        }
        decision_metrics = {
            key_names.get(key, key): value for key, value in decision_metrics.items()
        }
        violations = decision_metrics.get("semantic_violations")
        if isinstance(violations, dict) and "missing_thesis_schema_version" in violations:
            violations["missing_trade_setup_schema_version"] = violations.pop(
                "missing_thesis_schema_version"
            )
    decision_metrics["wire_schema"] = "trade_setup" if canonical_wire_schema else "thesis_legacy"
    return decision_metrics


def _finite(value: object) -> float | None:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


# The old function name is an explicit compatibility alias for report callers.
summarize_thesis_decisions = summarize_trade_setup_decisions

__all__ = ["summarize_trade_setup_decisions", "summarize_thesis_decisions"]
