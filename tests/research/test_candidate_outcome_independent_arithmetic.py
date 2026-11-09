import numpy as np
import pandas as pd
import pytest
from scripts.research.analysis.evaluation.candidate_outcome_reference import (
    independently_replay_outcomes,
)
from scripts.research.analysis.evaluation.verify_candidate_proposal_outcomes import (
    _independently_recompute_resolved_values,
    _limit_fill_price_bound_audit,
)


def _outcome_id(proposal_id: str, stop: str, target: str) -> str:
    import hashlib
    import json

    identity = {
        "proposal_id": proposal_id,
        "stop_choice": stop,
        "target_choice": target,
        "schema_version": "candidate-conditional-outcome-v2",
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"co2-{digest[:24]}"


def test_reference_replay_recomputes_market_exit_and_unfilled_limit() -> None:
    times = pd.to_datetime(
        [
            "2025-01-02T10:00:00Z",
            "2025-01-02T10:00:30Z",
            "2025-01-02T10:01:00Z",
            "2025-01-02T10:02:00Z",
        ],
        utc=True,
    )
    proposals = pd.DataFrame(
        [
            {
                "proposal_id": "market",
                "direction": 1,
                "entry_type": "market",
                "proposed_entry_price": 100.0,
                "valid_from": times[0].isoformat(),
                "eligible_action_fill_time": times[0].isoformat(),
                "expires_at": times[2].isoformat(),
                "session_close_time": times[3].isoformat(),
                "permissible_stop_choices": '[["s", 99.0]]',
                "permissible_target_choices": '[["t", 101.0]]',
            },
            {
                "proposal_id": "limit",
                "direction": 1,
                "entry_type": "limit",
                "proposed_entry_price": 99.5,
                "valid_from": times[0].isoformat(),
                "eligible_action_fill_time": times[0].isoformat(),
                "expires_at": times[2].isoformat(),
                "session_close_time": times[3].isoformat(),
                "permissible_stop_choices": '[["s", 99.0]]',
                "permissible_target_choices": '[["t", 101.0]]',
            },
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "proposal_id": "market",
                "stop_choice": "s",
                "target_choice": "t",
                "status": "filled_resolved",
                "evaluated_until": times[1].isoformat(),
                "order_expires_at": times[2].isoformat(),
                "fill_time": times[0].isoformat(),
                "fill_price": 100.1,
                "exit_time": times[1].isoformat(),
                "exit_price": 101.1,
                "exit_reason": "tp",
                "net_r": 1.0 / 1.1,
                "unresolved_reason": None,
                "outcome_id": _outcome_id("market", "s", "t"),
                "schema_version": "candidate-conditional-outcome-v2",
                "estimand": "conditional_fixed_entry",
            },
            {
                "proposal_id": "limit",
                "stop_choice": "s",
                "target_choice": "t",
                "status": "unfilled_expired",
                "evaluated_until": times[2].isoformat(),
                "order_expires_at": times[2].isoformat(),
                "fill_time": None,
                "fill_price": None,
                "exit_time": None,
                "exit_price": None,
                "exit_reason": None,
                "net_r": None,
                "unresolved_reason": None,
                "outcome_id": _outcome_id("limit", "s", "t"),
                "schema_version": "candidate-conditional-outcome-v2",
                "estimand": "conditional_fixed_entry",
            },
        ]
    )

    result = independently_replay_outcomes(
        proposals,
        outcomes,
        times.view("int64"),
        np.array([99.9, 101.1, 100.0, 100.0]),
        np.array([100.1, 101.2, 100.2, 100.2]),
        coverage_cutoffs={"market": None, "limit": None},
        training_cutoff=times[3],
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        max_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        limit_require_trade_through=False,
    )

    assert result["status"] == "verified"
    assert result["rows_checked"] == 2
    assert result["expected_status_counts"] == {
        "filled_resolved": 1,
        "unfilled_expired": 1,
    }

    corrupted = outcomes.copy()
    corrupted.loc[corrupted["proposal_id"].eq("market"), "exit_price"] = 100.0
    mismatch = independently_replay_outcomes(
        proposals,
        corrupted,
        times.view("int64"),
        np.array([99.9, 101.1, 100.0, 100.0]),
        np.array([100.1, 101.2, 100.2, 100.2]),
        coverage_cutoffs={"market": None, "limit": None},
        training_cutoff=times[3],
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        max_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        limit_require_trade_through=False,
    )
    assert mismatch["status"] == "mismatch"
    assert mismatch["mismatch_rows"] == 1
    assert mismatch["mismatch_fields"] == {"exit_price": 1}


def test_reference_replay_applies_limit_trade_through_contract() -> None:
    times = pd.to_datetime(
        ["2025-01-02T10:00:00Z", "2025-01-02T10:01:00Z", "2025-01-02T10:02:00Z"],
        utc=True,
    )
    proposal = pd.DataFrame(
        [
            {
                "proposal_id": "limit",
                "direction": 1,
                "entry_type": "limit",
                "proposed_entry_price": 100.1,
                "valid_from": times[0].isoformat(),
                "eligible_action_fill_time": times[0].isoformat(),
                "expires_at": times[1].isoformat(),
                "session_close_time": times[2].isoformat(),
                "permissible_stop_choices": '[["s", 99.0]]',
                "permissible_target_choices": '[["t", 101.0]]',
            }
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "proposal_id": "limit",
                "stop_choice": "s",
                "target_choice": "t",
                "status": "unfilled_expired",
                "evaluated_until": times[1].isoformat(),
                "order_expires_at": times[1].isoformat(),
                "fill_time": None,
                "fill_price": None,
                "exit_time": None,
                "exit_price": None,
                "exit_reason": None,
                "net_r": None,
                "unresolved_reason": None,
                "outcome_id": _outcome_id("limit", "s", "t"),
                "schema_version": "candidate-conditional-outcome-v2",
                "estimand": "conditional_fixed_entry",
            }
        ]
    )

    result = independently_replay_outcomes(
        proposal,
        outcomes,
        times.view("int64"),
        np.array([99.9, 99.9, 99.9]),
        np.array([100.1, 100.1, 100.1]),
        coverage_cutoffs={"limit": None},
        training_cutoff=times[2],
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        max_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        limit_require_trade_through=True,
    )

    assert result["status"] == "verified"
    assert result["expected_status_counts"] == {"unfilled_expired": 1}


def test_reference_replay_turns_coverage_censoring_into_unresolved_data() -> None:
    times = pd.to_datetime(
        ["2025-01-02T10:00:00Z", "2025-01-02T10:01:00Z", "2025-01-02T10:02:00Z"],
        utc=True,
    )
    proposal = pd.DataFrame(
        [
            {
                "proposal_id": "limit",
                "direction": 1,
                "entry_type": "limit",
                "proposed_entry_price": 99.0,
                "valid_from": times[0].isoformat(),
                "eligible_action_fill_time": times[0].isoformat(),
                "expires_at": times[2].isoformat(),
                "session_close_time": times[2].isoformat(),
                "permissible_stop_choices": '[["s", 98.0]]',
                "permissible_target_choices": '[["t", 101.0]]',
            }
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "proposal_id": "limit",
                "stop_choice": "s",
                "target_choice": "t",
                "status": "unresolved_data",
                "evaluated_until": times[1].isoformat(),
                "order_expires_at": times[2].isoformat(),
                "fill_time": None,
                "fill_price": None,
                "exit_time": None,
                "exit_price": None,
                "exit_reason": None,
                "net_r": None,
                "unresolved_reason": "local two-sided quote coverage is incomplete before order expiry",
                "outcome_id": _outcome_id("limit", "s", "t"),
                "schema_version": "candidate-conditional-outcome-v2",
                "estimand": "conditional_fixed_entry",
            }
        ]
    )

    result = independently_replay_outcomes(
        proposal,
        outcomes,
        times.view("int64"),
        np.array([99.9, 99.9, 99.9]),
        np.array([100.1, 100.1, 100.1]),
        coverage_cutoffs={"limit": times[1]},
        training_cutoff=times[2],
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        max_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        limit_require_trade_through=False,
    )

    assert result["status"] == "verified"
    assert result["expected_status_counts"] == {"unresolved_data": 1}


def test_reference_replay_recomputes_scheduled_session_close() -> None:
    times = pd.to_datetime(
        ["2025-01-02T10:00:00Z", "2025-01-02T10:01:00Z", "2025-01-02T10:02:00Z"],
        utc=True,
    )
    proposals = pd.DataFrame(
        [
            {
                "proposal_id": "market",
                "direction": 1,
                "entry_type": "market",
                "proposed_entry_price": 100.0,
                "valid_from": times[0].isoformat(),
                "eligible_action_fill_time": times[0].isoformat(),
                "expires_at": times[2].isoformat(),
                "session_close_time": times[2].isoformat(),
                "permissible_stop_choices": '[["s", 99.0]]',
                "permissible_target_choices": '[["t", 101.0]]',
            }
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "proposal_id": "market",
                "stop_choice": "s",
                "target_choice": "t",
                "status": "filled_resolved",
                "evaluated_until": times[1].isoformat(),
                "order_expires_at": times[2].isoformat(),
                "fill_time": times[0].isoformat(),
                "fill_price": 100.1,
                "exit_time": times[1].isoformat(),
                "exit_price": 100.0,
                "exit_reason": "session_close",
                "net_r": -0.1 / 1.1,
                "unresolved_reason": None,
                "outcome_id": _outcome_id("market", "s", "t"),
                "schema_version": "candidate-conditional-outcome-v2",
                "estimand": "conditional_fixed_entry",
            }
        ]
    )

    result = independently_replay_outcomes(
        proposals,
        outcomes,
        times.view("int64"),
        np.array([99.9, 100.0, 100.2]),
        np.array([100.1, 100.1, 100.3]),
        coverage_cutoffs={"market": None},
        training_cutoff=times[2],
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        max_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        limit_require_trade_through=False,
    )

    assert result["status"] == "verified"
    assert result["expected_status_counts"] == {"filled_resolved": 1}


def test_reference_replay_marks_session_close_quote_before_entry_unresolved() -> None:
    times = pd.to_datetime(
        ["2025-01-02T10:01:00Z", "2025-01-02T10:01:30Z", "2025-01-02T10:02:00Z"],
        utc=True,
    )
    proposals = pd.DataFrame(
        [
            {
                "proposal_id": "market",
                "direction": 1,
                "entry_type": "market",
                "proposed_entry_price": 100.0,
                "valid_from": times[0].isoformat(),
                "eligible_action_fill_time": times[1].isoformat(),
                "expires_at": times[2].isoformat(),
                "session_close_time": times[2].isoformat(),
                "permissible_stop_choices": '[["s", 99.0]]',
                "permissible_target_choices": '[["t", 101.0]]',
            }
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "proposal_id": "market",
                "stop_choice": "s",
                "target_choice": "t",
                "status": "unresolved_data",
                "evaluated_until": times[2].isoformat(),
                "order_expires_at": times[2].isoformat(),
                "fill_time": times[1].isoformat(),
                "fill_price": 100.1,
                "exit_time": None,
                "exit_price": None,
                "exit_reason": None,
                "net_r": None,
                "unresolved_reason": "session-close execution quote predates the entry fill",
                "outcome_id": _outcome_id("market", "s", "t"),
                "schema_version": "candidate-conditional-outcome-v2",
                "estimand": "conditional_fixed_entry",
            }
        ]
    )

    result = independently_replay_outcomes(
        proposals,
        outcomes,
        times.view("int64"),
        np.array([99.9, 99.9, 99.9]),
        np.array([100.1, 100.1, 100.1]),
        coverage_cutoffs={"market": None},
        training_cutoff=times[2],
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        max_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        limit_require_trade_through=False,
    )

    assert result["status"] == "verified"
    assert result["expected_status_counts"] == {"unresolved_data": 1}


def test_reference_replay_fails_closed_on_randomized_latency() -> None:
    with pytest.raises(ValueError, match="requires zero randomized latency"):
        independently_replay_outcomes(
            pd.DataFrame(),
            pd.DataFrame(),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.float64),
            coverage_cutoffs={},
            training_cutoff=pd.Timestamp("2025-01-02T10:00:00Z"),
            slippage_points=0.0,
            commission_per_lot=0.0,
            contract_size=1.0,
            max_quote_wait_ms=60_000,
            randomized_fill_latency_ms=1.0,
            limit_require_trade_through=False,
        )


def test_recomputes_source_quote_fills_and_net_r_for_both_directions() -> None:
    times = pd.to_datetime(
        [
            "2025-01-02T10:01:00Z",
            "2025-01-02T10:02:00Z",
            "2025-01-02T10:03:00Z",
            "2025-01-02T10:03:00Z",
            "2025-01-02T10:04:00Z",
        ],
        utc=True,
    ).view("int64")
    proposals = pd.DataFrame(
        {
            "proposal_id": ["long", "short"],
            "direction": [1, -1],
            "entry_type": ["market", "limit"],
            "proposed_entry_price": [100.0, 99.8],
            "permissible_stop_choices": [
                '[["stop", 99.3]]',
                '[["stop", 100.6]]',
            ],
        }
    )
    outcomes = pd.DataFrame(
        {
            "proposal_id": ["long", "short"],
            "status": ["filled_resolved", "filled_resolved"],
            "stop_choice": ["stop", "stop"],
            "fill_time": [
                "2025-01-02T10:01:00.000Z",
                "2025-01-02T10:03:00Z",
            ],
            "exit_time": ["2025-01-02T10:02:00Z", "2025-01-02T10:04:00.000Z"],
            "fill_price": [100.3, 99.9],
            "exit_price": [101.0, 99.0],
            "net_r": [0.68, 1.2571428571428571],
            "outcome_id": ["long-outcome", "short-outcome"],
        }
    )

    result = _independently_recompute_resolved_values(
        proposals,
        outcomes,
        times,
        np.array([99.9, 101.2, 99.9, 100.2, 98.6]),
        np.array([100.1, 101.4, 100.1, 100.4, 98.8]),
        tickbook_sha256="fixture",
        slippage_points=0.2,
        commission_per_lot=0.1,
        contract_size=10.0,
    )

    assert result["status"] == "verified"
    assert result["rows_checked"] == 2
    assert result["fill_source_quote_matches"] == 2
    assert result["exit_source_quote_matches"] == 2
    assert result["net_r_recalculations_match"] == 2


def test_flags_return_mismatch_and_non_tick_execution_time() -> None:
    proposals = pd.DataFrame(
        {
            "proposal_id": ["long"],
            "direction": [1],
            "entry_type": ["market"],
            "proposed_entry_price": [100.0],
            "permissible_stop_choices": ['[["stop", 99.3]]'],
        }
    )
    outcomes = pd.DataFrame(
        {
            "proposal_id": ["long"],
            "status": ["filled_resolved"],
            "stop_choice": ["stop"],
            "fill_time": ["2025-01-02T10:01:00Z"],
            "exit_time": ["2025-01-02T10:02:00Z"],
            "fill_price": [100.3],
            "exit_price": [101.0],
            "net_r": [0.7],
            "outcome_id": ["bad-outcome"],
        }
    )

    result = _independently_recompute_resolved_values(
        proposals,
        outcomes,
        pd.to_datetime(["2025-01-02T10:01:00Z"], utc=True).view("int64"),
        np.array([99.9]),
        np.array([100.1]),
        tickbook_sha256="fixture",
        slippage_points=0.2,
        commission_per_lot=0.1,
        contract_size=10.0,
    )

    assert result["status"] == "mismatch"
    assert result["mismatch_rows"] == 1
    assert result["first_mismatch_outcome_ids"] == ["bad-outcome"]


def test_independently_checks_long_and_short_limit_price_bounds() -> None:
    proposals = pd.DataFrame(
        {
            "proposal_id": ["long", "short"],
            "entry_type": ["limit", "limit"],
            "direction": [1, -1],
            "proposed_entry_price": [100.0, 100.0],
        }
    )
    valid_outcomes = pd.DataFrame(
        {
            "proposal_id": ["long", "short"],
            "fill_price": [99.75, 100.25],
        }
    )
    invalid_outcomes = pd.DataFrame(
        {
            "proposal_id": ["long", "short"],
            "fill_price": [100.25, 99.75],
        }
    )

    valid = _limit_fill_price_bound_audit(proposals, valid_outcomes)
    invalid = _limit_fill_price_bound_audit(proposals, invalid_outcomes)

    assert valid["known_limit_fills_checked"] == 2
    assert valid["price_bound_violations"] == 0
    assert invalid["price_bound_violations"] == 2
    assert len(invalid["examples"]) == 2


def test_server_side_reference_uses_exact_triggering_source_row_on_timestamp_tie() -> None:
    times = pd.to_datetime(
        [
            "2025-01-02T10:00:00Z",
            "2025-01-02T10:01:00Z",
            "2025-01-02T10:01:00Z",
            "2025-01-02T10:02:00Z",
        ],
        utc=True,
    )
    proposal = pd.DataFrame(
        [
            {
                "proposal_id": "long",
                "direction": 1,
                "entry_type": "market",
                "proposed_entry_price": 100.0,
                "valid_from": times[0].isoformat(),
                "eligible_action_fill_time": times[0].isoformat(),
                "expires_at": times[2].isoformat(),
                "session_close_time": times[3].isoformat(),
                "permissible_stop_choices": '[["s", 99.0]]',
                "permissible_target_choices": '[["t", 101.0]]',
            }
        ]
    )
    outcomes = pd.DataFrame(
        [
            {
                "proposal_id": "long",
                "stop_choice": "s",
                "target_choice": "t",
                "status": "filled_resolved",
                "evaluated_until": times[2].isoformat(),
                "order_expires_at": times[2].isoformat(),
                "fill_time": times[0].isoformat(),
                "fill_price": 100.1,
                "exit_time": times[2].isoformat(),
                "exit_price": 101.2,
                "exit_reason": "tp",
                "net_r": 1.0,
                "unresolved_reason": None,
                "outcome_id": _outcome_id("long", "s", "t"),
                "schema_version": "candidate-conditional-outcome-v2",
                "estimand": "conditional_fixed_entry",
            }
        ]
    )
    bids = np.array([99.9, 100.5, 101.2, 100.0])
    asks = bids + 0.2

    result = independently_replay_outcomes(
        proposal,
        outcomes,
        times.view("int64"),
        bids,
        asks,
        coverage_cutoffs={"long": None},
        training_cutoff=times[3],
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        max_quote_wait_ms=60_000,
        randomized_fill_latency_ms=0.0,
        limit_require_trade_through=False,
        server_side_protective_orders=True,
    )

    assert result["status"] == "verified"
    assert result["rows_checked"] == 1


def test_server_side_arithmetic_uses_first_trigger_row_in_timestamp_tie() -> None:
    times = pd.to_datetime(
        [
            "2025-01-02T10:00:00Z",
            "2025-01-02T10:01:00Z",
            "2025-01-02T10:01:00Z",
        ],
        utc=True,
    ).view("int64")
    proposals = pd.DataFrame(
        {
            "proposal_id": ["long"],
            "direction": [1],
            "entry_type": ["market"],
            "proposed_entry_price": [100.0],
            "permissible_stop_choices": ['[["s", 99.2]]'],
            "permissible_target_choices": ['[["t", 101.0]]'],
        }
    )
    outcomes = pd.DataFrame(
        {
            "proposal_id": ["long"],
            "status": ["filled_resolved"],
            "stop_choice": ["s"],
            "target_choice": ["t"],
            "fill_time": ["2025-01-02T10:00:00Z"],
            "exit_time": ["2025-01-02T10:01:00Z"],
            "exit_reason": ["tp"],
            "fill_price": [100.2],
            "exit_price": [101.2],
            "net_r": [1.0],
            "outcome_id": ["server-side-tie"],
        }
    )

    result = _independently_recompute_resolved_values(
        proposals,
        outcomes,
        times,
        np.array([100.0, 100.5, 101.2]),
        np.array([100.2, 100.7, 101.4]),
        tickbook_sha256="fixture",
        slippage_points=0.0,
        commission_per_lot=0.0,
        contract_size=1.0,
        server_side_protective_orders=True,
    )

    assert result["status"] == "verified"
    assert result["exit_source_quote_matches"] == 1
