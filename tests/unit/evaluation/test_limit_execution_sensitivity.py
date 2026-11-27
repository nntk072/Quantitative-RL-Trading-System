from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from evaluation.metrics.limit_execution_sensitivity import compare_limit_execution_sensitivity


def _result(*, trade_through: bool, events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "execution_contract": {
            "schema_version": "backtest_execution_contract.v1",
            "cost_model": {"spread_points": 0.6, "slippage_points": 5.0},
            "market_fill": {"fill_latency_bars": 0},
            "limit_order": {
                "policy_selectable": True,
                "quote_source": "TickBook",
                "max_offset_atr": 1.0,
                "max_ttl_bars": 60,
                "require_trade_through": trade_through,
                "fill_rule": (
                    "strict_executable_quote_trade_through"
                    if trade_through
                    else "executable_quote_exact_touch_or_better"
                ),
            },
        },
        "action_schema": {
            "version": "trade-setup-entry-execution-action-v2",
            "has_entry_execution": True,
        },
        "observation_schema": {"version": "account-state-v1"},
        "observation_inputs": {"feature_validity_channels": False},
        "policy_decisions": pd.DataFrame(
            [
                {
                    "decision_id": "d1",
                    "action": 1,
                    "trade_setup_candidate_id": 5,
                    "trade_setup_eligible": True,
                    "execution_type": "limit",
                    "limit_offset_atr": 0.25,
                    "limit_ttl_bars": 5,
                    "selected_risk_frac": 0.01,
                    "selected_geometry_action": None,
                }
            ]
        ),
        "trades": pd.DataFrame(events),
    }


def test_limit_sensitivity_pairs_fill_and_cancellation_under_matching_inputs() -> None:
    exact = _result(
        trade_through=False,
        events=[
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "order_type": "limit",
                "limit_price": 100.0,
            },
            {
                "type": "order_fill",
                "order_id": "o1",
                "decision_id": "d1",
                "price": 100.0,
            },
            {
                "type": "open",
                "order_id": "o1",
                "decision_id": "d1",
                "position_id": "p1",
                "price": 100.0,
            },
            {
                "type": "close",
                "position_id": "p1",
                "net_pnl": 12.0,
                "position_complete": True,
            },
        ],
    )
    strict = _result(
        trade_through=True,
        events=[
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "order_type": "limit",
                "limit_price": 100.0,
            },
            {
                "type": "order_cancel",
                "order_id": "o1",
                "decision_id": "d1",
                "reason": "limit_ttl_expired",
            },
        ],
    )

    report = compare_limit_execution_sensitivity(exact, strict)

    assert report["status"] == "execution_contracts_match"
    assert report["other_run_provenance_verified"] is False
    assert report["decision_counts"]["common"] == 1
    assert report["limit_order_counts"]["paired"] == 1
    paired = report["paired_limit_outcomes"][0]
    assert paired["exact_touch"]["status"] == "filled"
    assert paired["exact_touch"]["realized_net_pnl"] == 12.0
    assert paired["exact_touch"]["position_complete"] is True
    assert paired["trade_through"]["status"] == "cancelled"
    assert report["economic_value_claim"] == "not_estimated"


def test_limit_sensitivity_reports_other_input_differences() -> None:
    exact = _result(trade_through=False, events=[])
    strict = _result(trade_through=True, events=[])
    strict["execution_contract"]["limit_order"]["max_ttl_bars"] = 30

    report = compare_limit_execution_sensitivity(exact, strict)

    assert report["status"] == "execution_contract_mismatch"
    assert report["execution_and_policy_schemas_match_except_fill_rule"] is False


def test_limit_sensitivity_requires_both_declared_assumptions() -> None:
    exact = _result(trade_through=True, events=[])
    strict = _result(trade_through=True, events=[])

    with pytest.raises(ValueError, match="exact-touch"):
        compare_limit_execution_sensitivity(exact, strict)


def test_limit_sensitivity_excludes_no_trade_decisions_from_order_counts() -> None:
    exact = _result(trade_through=False, events=[])
    strict = _result(trade_through=True, events=[])
    for result in (exact, strict):
        result["policy_decisions"].loc[0, "action"] = 0
        result["policy_decisions"].loc[0, "trade_setup_candidate_id"] = 0
        result["policy_decisions"].loc[0, "trade_setup_eligible"] = True

    report = compare_limit_execution_sensitivity(exact, strict)

    assert report["limit_order_counts"]["exact_touch"] == 0
    assert report["limit_order_counts"]["trade_through"] == 0


def test_limit_sensitivity_rejects_string_setup_eligibility() -> None:
    exact = _result(trade_through=False, events=[])
    strict = _result(trade_through=True, events=[])
    for result in (exact, strict):
        result["policy_decisions"].loc[0, "trade_setup_eligible"] = "false"

    with pytest.raises(ValueError, match="non-boolean trade_setup_eligible"):
        compare_limit_execution_sensitivity(exact, strict)


def test_limit_sensitivity_does_not_treat_string_position_completion_as_true() -> None:
    exact = _result(
        trade_through=False,
        events=[
            {
                "type": "order_submit",
                "order_id": "o1",
                "decision_id": "d1",
                "order_type": "limit",
            },
            {"type": "order_fill", "order_id": "o1", "decision_id": "d1", "price": 100.0},
            {
                "type": "open",
                "order_id": "o1",
                "decision_id": "d1",
                "position_id": "p1",
                "price": 100.0,
            },
            {"type": "close", "position_id": "p1", "position_complete": "false"},
        ],
    )
    strict = _result(trade_through=True, events=[])

    report = compare_limit_execution_sensitivity(exact, strict)

    assert report["paired_limit_outcomes"][0]["exact_touch"]["position_complete"] is None

    exact["trades"] = exact["trades"].drop(columns=["position_complete"])
    report_without_flag = compare_limit_execution_sensitivity(exact, strict)
    assert (
        report_without_flag["paired_limit_outcomes"][0]["exact_touch"]["position_complete"] is None
    )


def test_limit_sensitivity_counts_unsubmitted_and_unresolved_limit_orders() -> None:
    exact = _result(trade_through=False, events=[])
    strict = _result(
        trade_through=True,
        events=[
            {
                "type": "order_submit",
                "order_id": "pending",
                "decision_id": "d1",
                "order_type": "limit",
            }
        ],
    )

    report = compare_limit_execution_sensitivity(exact, strict)

    assert report["limit_order_counts"]["outcomes"]["exact_touch"]["no_order_submitted"] == 1
    assert report["limit_order_counts"]["outcomes"]["trade_through"]["unresolved"] == 1
    assert report["paired_limit_outcomes"][0]["exact_touch"]["status"] == "no_order_submitted"


def test_limit_sensitivity_reports_common_divergences_and_arm_only_decisions() -> None:
    exact = _result(trade_through=False, events=[])
    strict = _result(trade_through=True, events=[])
    exact["policy_decisions"].loc[0, "selected_risk_frac"] = 0.01
    exact["policy_decisions"]["selected_geometry_action"] = exact["policy_decisions"][
        "selected_geometry_action"
    ].astype(object)
    exact["policy_decisions"].at[0, "selected_geometry_action"] = {"stop": float("nan")}
    strict["policy_decisions"].loc[0, "selected_risk_frac"] = 0.02
    strict["policy_decisions"]["selected_geometry_action"] = strict["policy_decisions"][
        "selected_geometry_action"
    ].astype(object)
    strict["policy_decisions"].at[0, "selected_geometry_action"] = {"stop": float("nan")}
    exact_only = exact["policy_decisions"].iloc[0].copy()
    exact_only["decision_id"] = "exact-only"
    strict_only = strict["policy_decisions"].iloc[0].copy()
    strict_only["decision_id"] = "strict-only"
    exact["policy_decisions"] = pd.concat(
        [exact["policy_decisions"], exact_only.to_frame().T], ignore_index=True
    )
    strict["policy_decisions"] = pd.concat(
        [strict["policy_decisions"], strict_only.to_frame().T], ignore_index=True
    )

    report = compare_limit_execution_sensitivity(exact, strict)

    assert report["decision_counts"]["exact_only"] == 1
    assert report["decision_counts"]["trade_through_only"] == 1
    assert report["decision_counts"]["policy_divergent_common"] == 1
    assert report["decision_divergences"][0]["fields"] == ["selected_risk_frac"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda result: result.pop("execution_contract"), "missing its execution_contract"),
        (
            lambda result: result["execution_contract"].pop("limit_order"),
            "missing limit_order settings",
        ),
        (
            lambda result: result["execution_contract"]["limit_order"].update(
                require_trade_through="false"
            ),
            "explicitly recorded as a boolean",
        ),
    ],
)
def test_limit_sensitivity_rejects_incomplete_fill_contract(mutate, message: str) -> None:
    exact = _result(trade_through=False, events=[])
    strict = _result(trade_through=True, events=[])
    mutate(exact)

    with pytest.raises(ValueError, match=message):
        compare_limit_execution_sensitivity(exact, strict)
