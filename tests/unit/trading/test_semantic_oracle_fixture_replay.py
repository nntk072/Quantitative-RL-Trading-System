"""Replay of the hand-calculated semantic oracle fixtures (SEMANTIC-ORACLE).

The expected values live in ``planning/native_modernization/semantic_oracle/fixtures``
and were worked out by hand before any comparison ran. This module only replays them
against production code. Tolerances are read from the fixture file, not from this module.

Cases whose fixture polarity is ``defect`` are strict expected failures: each names a
source disagreement that is classified in ``semantic_contracts.md`` and is not fixed in
this package. If a source change makes one pass, the strict marker turns it into a
failure, which forces an explicit fixture version change instead of a silent update.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from market_data.loading.ticks import event_keyed_execution_rng
from market_data.transforms.sessions import ny_session_mask
from simulation.environment.rewards import EquityDeltaReward, EquityLogGrowthReward
from trading.account import AccountState
from trading.execution.broker import Broker, Position
from trading.execution.costs import CostModel
from trading.execution.quotes import (
    adverse_tick_fill_quote,
    bar_stop_fill_quote,
    exit_side_bar_range,
    protective_level_fill_quote,
    quote_from_bar_price,
    raw_spread_to_price,
    undo_adverse_tick_slippage_quote,
)
from trading.positions.multi_tp import target_close_size
from trading.risk.execution_reserve import modeled_execution_reserve_usd
from trading.risk.ftmo_clock import ftmo_trading_day
from trading.risk.guardrails import FTMOGuardrails, guardrail_breach_scope
from trading.risk.sizing import (
    compute_lots,
    compute_lots_with_execution_reserve,
    compute_sl_tp_from_structure,
    compute_sl_tp_long,
    compute_sl_tp_short,
    stop_loss_risk_usd,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "planning" / "native_modernization" / "semantic_oracle" / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "semantic_oracle_fixtures.v1.json"
MANIFEST_PATH = FIXTURE_DIR / "MANIFEST.json"


def _load_fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data


FIXTURE = _load_fixture()
TOLERANCES: dict[str, dict[str, Any]] = FIXTURE["tolerances"]


def _cost_model(args: dict[str, Any] | None) -> CostModel:
    return CostModel(**(args or {}))


def _tuple(value: Any) -> tuple[float, float]:
    left, right = value
    return float(left), float(right)


def _run_quote_case(op: str, args: dict[str, Any]) -> Any:
    """Dispatch the bid/ask, spread, fee and slippage fixture operations."""
    if op == "quote_from_bar_price":
        return _tuple(
            quote_from_bar_price(
                _cost_model(args["cost_model"]), args["price"], args["spread_points"]
            )
        )
    if op == "quote_default_spread_is_price_units":
        return _tuple(_cost_model(args["cost_model"]).bar_quote(close=args["close"]))
    if op == "fill_price":
        return _cost_model(args["cost_model"]).fill_price(
            args["bid"], args["ask"], args["direction"]
        )
    if op == "total_cost":
        return _cost_model(args["cost_model"]).total_cost(args["lots"])
    if op == "cost_model_construct":
        return CostModel(**args)
    if op == "protective_level_fill_quote":
        return _tuple(
            protective_level_fill_quote(
                args["direction"], args["hit_price"], _cost_model(args["cost_model"])
            )
        )
    if op == "bar_stop_fill_quote":
        return _tuple(
            bar_stop_fill_quote(
                args["direction"],
                args["stop_price"],
                args["bar_open"],
                args["raw_spread_points"],
                _cost_model(args["cost_model"]),
            )
        )
    if op == "adverse_tick_fill_quote":
        return _tuple(
            adverse_tick_fill_quote(
                _tuple(args["quote"]),
                args["direction"],
                args["slippage_points"],
                opening=args["opening"],
            )
        )
    if op == "undo_adverse_tick_slippage_quote":
        return _tuple(
            undo_adverse_tick_slippage_quote(
                _tuple(args["quote"]),
                args["direction"],
                args["slippage_points"],
                opening=args["opening"],
            )
        )
    if op == "exit_side_bar_range":
        return _tuple(
            exit_side_bar_range(
                args["direction"],
                args["bid_low"],
                args["bid_high"],
                args["spread_price_units"],
                _cost_model(args.get("cost_model")),
            )
        )
    if op == "raw_spread_to_price":
        return raw_spread_to_price(args["raw_spread_points"], args["point_size"])
    raise UnknownOperationError(op)


def _run_sizing_case(op: str, args: dict[str, Any]) -> Any:
    """Dispatch lot-rounding, stop, and target-price fixture operations."""
    if op == "stop_loss_risk_usd":
        return stop_loss_risk_usd(**args)
    if op == "compute_lots":
        return compute_lots(**args)
    if op == "compute_lots_with_execution_reserve":
        return compute_lots_with_execution_reserve(**args)
    if op == "modeled_execution_reserve_usd":
        return modeled_execution_reserve_usd(**args)
    if op == "compute_sl_tp_long":
        return list(compute_sl_tp_long(**args))
    if op == "compute_sl_tp_short":
        return list(compute_sl_tp_short(**args))
    if op == "compute_sl_tp_from_structure":
        return list(compute_sl_tp_from_structure(**args))
    if op == "target_close_size":
        slots = set(args["active_tp"])
        position = Position(
            direction=1,
            size=float(args["size"]),
            entry_price=100.0,
            margin_used=0.0,
            initial_size=float(args["initial_size"]),
            tp_initial_size=float(args["initial_size"]),
            tp_lot_fractions=tuple(float(v) for v in args["fractions"]),
            ema_runner_fraction=float(args["runner_fraction"]),
        )
        for slot in (1, 2, 3):
            if slot in slots:
                setattr(position, f"tp{slot}_price", 100.0 + slot)
        return target_close_size(position, int(args["slot"]), is_final=bool(args["is_final"]))
    raise UnknownOperationError(op)


def _run_misc_case(op: str, args: dict[str, Any]) -> Any:
    """Dispatch timing, session, RNG, and reward fixture operations."""
    if op == "ftmo_trading_day":
        return str(ftmo_trading_day(args["timestamp"]))
    if op == "ny_session_mask_default":
        index = pd.DatetimeIndex(args["index"])
        return [bool(v) for v in ny_session_mask(index).to_numpy()]
    if op == "ny_session_mask":
        index = pd.DatetimeIndex(args["index"])
        mask = ny_session_mask(index, start=args["start"], end=args["end"])
        return [bool(v) for v in mask.to_numpy()]
    if op == "event_keyed_draws":
        draws = event_keyed_execution_rng(int(args["seed"]), args["key"]).random(int(args["n"]))
        return [repr(float(v)) for v in draws]
    if op == "equity_delta_reward":
        reward = EquityDeltaReward(fixed_risk_usd=args["fixed_risk_usd"])
        return reward(args["step_pnl"], breach=bool(args.get("breach", False)))
    if op == "equity_delta_reward_construct":
        return EquityDeltaReward(fixed_risk_usd=args["fixed_risk_usd"])
    if op == "equity_log_growth_reward":
        log_reward = EquityLogGrowthReward(scale=args["scale"])
        return log_reward(0.0, previous_equity=args["previous_equity"], equity=args["equity"])
    raise UnknownOperationError(op)


class UnknownOperationError(LookupError):
    """Raised when a fixture names an operation this replay does not implement."""

    def __init__(self, op: str) -> None:
        super().__init__(f"unknown fixture operation {op!r}")


def _dispatch(op: str, args: dict[str, Any]) -> Any:
    for runner in (_run_quote_case, _run_sizing_case, _run_misc_case):
        try:
            return runner(op, args)
        except UnknownOperationError:
            continue
    raise UnknownOperationError(op)


def _tolerance(name: str) -> tuple[float, float, str, float]:
    spec = TOLERANCES[name]
    return (
        float(spec["abs"]),
        float(spec["rel"]),
        spec["kind"],
        float(spec.get("step_unit_lots", 0.0)),
    )


def _assert_matches(actual: Any, expected: Any, tol_name: str) -> None:
    if isinstance(expected, dict):
        raise AssertionError("dict expectations are handled by the caller")
    if isinstance(expected, list):
        assert isinstance(actual, (list, tuple)), f"expected a sequence, got {actual!r}"
        assert len(actual) == len(expected), f"length {len(actual)} != {len(expected)}"
        for got, want in zip(actual, expected, strict=True):
            _assert_matches(got, want, tol_name)
        return
    if expected is None or isinstance(expected, (bool, str)):
        assert actual == expected, f"{actual!r} != {expected!r}"
        return
    abs_tol, rel_tol, kind, step = _tolerance(tol_name)
    got = float(actual)
    assert math.isfinite(got), f"non-finite actual {got!r}"
    if kind == "lot_step_count":
        assert round(got / step) == round(float(expected) / step), (
            f"lot-step count {round(got / step)} != {round(float(expected) / step)}"
        )
        assert abs(got - float(expected)) <= 1e-9, f"lot residual {got - float(expected)!r}"
        return
    assert abs(got - float(expected)) <= max(abs_tol, rel_tol * abs(float(expected))), (
        f"{got!r} != {float(expected)!r} outside {tol_name} ({abs_tol})"
    )


def _case_params(section: str) -> list[Any]:
    params: list[Any] = []
    for case in FIXTURE["cases"][section]:
        marks: list[Any] = []
        if case["polarity"] == "defect":
            marks.append(
                pytest.mark.xfail(
                    strict=True,
                    reason=f"{case['id']}: {case['classification']}",
                )
            )
        params.append(pytest.param(case, id=case["id"], marks=marks))
    return params


def _replay_case(case: dict[str, Any]) -> None:
    expected = case["expect"]
    tol = case["tol"]
    op = case["op"]
    args = case["args"]
    if isinstance(expected, dict) and "raises" in expected:
        with pytest.raises(ValueError):
            _dispatch(op, args)
        return
    if isinstance(expected, dict) and "lt_size" in expected:
        actual = _dispatch(op, args)
        assert float(actual) < float(expected["lt_size"]), (
            f"whole-position exit: leg returned {actual!r}, position is {expected['lt_size']!r}"
        )
        return
    if expected == "same_as_repeat":
        first = event_keyed_execution_rng(int(args["seed"]), args["key"]).random(int(args["n"]))
        second = event_keyed_execution_rng(int(args["seed"]), args["key"]).random(int(args["n"]))
        assert np.array_equal(first, second)
        return
    if expected == "different":
        if "keys" in args:
            draws = [
                event_keyed_execution_rng(int(args["seed"]), key).random() for key in args["keys"]
            ]
        else:
            draws = [
                event_keyed_execution_rng(int(seed), args["key"]).random() for seed in args["seeds"]
            ]
        assert draws[0] != draws[1]
        return
    actual = _dispatch(op, args)
    _assert_matches(actual, expected, tol)


@pytest.mark.parametrize(
    "case",
    [p for section in FIXTURE["cases"] for p in _case_params(section)],
)
def test_hand_calculated_case_replays_against_production(case: dict[str, Any]) -> None:
    _replay_case(case)


def test_fixture_case_ids_are_unique() -> None:
    ids = [case["id"] for cases in FIXTURE["cases"].values() for case in cases]
    ids += [scenario["id"] for scenario in FIXTURE["account_scenarios"]]
    ids += [case["id"] for case in FIXTURE["defect_cases"]]
    assert len(ids) == len(set(ids))


def test_every_fixture_case_declares_a_known_polarity() -> None:
    allowed = {"positive", "adverse", "boundary", "characterization", "defect"}
    polarities = [case["polarity"] for cases in FIXTURE["cases"].values() for case in cases]
    polarities += [case["polarity"] for case in FIXTURE["cases"]["rewards"]]
    assert set(polarities) <= allowed


def test_defect_and_characterization_cases_carry_a_classification() -> None:
    for cases in FIXTURE["cases"].values():
        for case in cases:
            if case["polarity"] in {"defect", "characterization"}:
                assert case.get("classification"), case["id"]


# --- account and broker event traces ------------------------------------------------


def _build_account(scenario: dict[str, Any]) -> tuple[AccountState, Broker]:
    setup = scenario["setup"]
    acc = AccountState(initial_balance=float(setup["initial_balance"]))
    cost = _cost_model(setup["cost_model"])
    broker = Broker(
        contract_size=float(setup["broker"]["contract_size"]),
        margin_pct=float(setup["broker"]["margin_pct"]),
        cost_model=cost,
    )
    return acc, broker


def _check_expect(
    expect: dict[str, Any],
    observed: dict[str, Any],
    event_id: str,
) -> None:
    for name, want in expect.items():
        assert name in observed, f"{event_id}: operation did not report {name!r}"
        got = observed[name]
        if want is None or isinstance(want, (bool, str)):
            assert got == want, f"{event_id}.{name}: {got!r} != {want!r}"
        else:
            abs_tol, rel_tol, _, _ = _tolerance("money_usd_abs")
            assert abs(float(got) - float(want)) <= max(abs_tol, rel_tol * abs(float(want))), (
                f"{event_id}.{name}: {got!r} != {want!r}"
            )


def _run_event(
    event: dict[str, Any],
    acc: AccountState,
    broker: Broker,
    state: dict[str, Any],
) -> dict[str, Any]:
    op = event["op"]
    args = event["args"]
    if op == "open":
        position = broker.open_position(acc, _tuple(args["quote"]), args["lots"], args["direction"])
        state["position"] = position
        if position is None:
            return {"opened": False, "balance": acc.balance}
        return {
            "opened": True,
            "entry_price": position.entry_price,
            "margin_used": position.margin_used,
            "balance": acc.balance,
            "position_size": position.size,
        }
    if op == "mtm":
        broker.mark_to_market(acc, state["position"], _tuple(args["quote"]))
        return {"open_pnl": acc.open_pnl, "equity": acc.equity, "max_drawdown": acc.max_drawdown}
    if op == "stop_close":
        quote = bar_stop_fill_quote(
            args["direction"],
            args["stop_price"],
            args["bar_open"],
            args["raw_spread_points"],
            broker.cost_model,
        )
        pnl, fill = broker.close_position(acc, state["position"], quote)
        return {
            "fill_price": fill,
            "pnl": pnl,
            "balance": acc.balance,
            "equity": acc.equity,
            "open_pnl": acc.open_pnl,
            "daily_loss": acc.daily_loss,
            "max_drawdown": acc.max_drawdown,
            "position_size": state["position"].size,
        }
    if op == "partial_close":
        pnl, fill = broker.close_position(
            acc, state["position"], _tuple(args["quote"]), size=args["size"]
        )
        return {
            "fill_price": fill,
            "pnl": pnl,
            "balance": acc.balance,
            "equity": acc.equity,
            "open_pnl": acc.open_pnl,
            "position_size": state["position"].size,
        }
    if op == "close_trade":
        acc.close_trade(args["pnl"])
        return {
            "balance": acc.balance,
            "equity": acc.equity,
            "daily_loss": acc.daily_loss,
            "max_drawdown": acc.max_drawdown,
        }
    if op == "reset_daily":
        acc.reset_daily()
        return {"session_start_equity": acc.session_start_equity, "daily_loss": acc.daily_loss}
    if op == "daily_capacity":
        return {
            "floor": acc.daily_floor(args["daily_loss_limit"]),
            "remaining": acc.remaining_daily_capacity(args["daily_loss_limit"]),
        }
    if op == "guardrail":
        guard = FTMOGuardrails(
            daily_loss_limit_pct=args["daily_loss_limit_pct"],
            max_loss_limit_initial_pct=args["max_loss_limit_initial_pct"],
        )
        reason = guard.breach_reason(acc)
        observed: dict[str, Any] = {"breach_reason": reason}
        if reason is not None:
            observed["guardrail_scope"] = guardrail_breach_scope(reason)
        observed["remaining_daily"] = acc.remaining_daily_capacity(guard.daily_limit_for(acc))
        return observed
    if op == "set_state_guardrail":
        acc.equity = float(args["equity"])
        acc.session_start_equity = float(args["session_start_equity"])
        guard = FTMOGuardrails(
            daily_loss_limit_pct=args["daily_loss_limit_pct"],
            max_loss_limit_initial_pct=args["max_loss_limit_initial_pct"],
        )
        return {"breach_reason": guard.breach_reason(acc)}
    raise AssertionError(f"unknown account event {op!r}")


@pytest.mark.parametrize(
    "scenario",
    [pytest.param(s, id=s["id"]) for s in FIXTURE["account_scenarios"]],
)
def test_account_event_trace_matches_hand_ledger(scenario: dict[str, Any]) -> None:
    keys = [tuple(event["key"]) for event in scenario["events"]]
    assert keys == sorted(keys), "fixture ordering keys must be strictly sorted"
    assert len(keys) == len(set(keys)), "ordering keys must be unique"
    acc, broker = _build_account(scenario)
    state: dict[str, Any] = {}
    for event in scenario["events"]:
        observed = _run_event(event, acc, broker, state)
        _check_expect(event["expect"], observed, f"{scenario['id']}@{event['key']}")


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            c,
            id=c["id"],
            marks=[pytest.mark.xfail(strict=True, reason=f"{c['id']}: {c['classification']}")],
        )
        for c in FIXTURE["defect_cases"]
    ],
)
def test_open_position_keeps_equity_identity_at_once(case: dict[str, Any]) -> None:
    args = case["args"]
    acc = AccountState(initial_balance=float(args["initial_balance"]))
    broker = Broker(
        contract_size=float(args["broker"]["contract_size"]),
        margin_pct=float(args["broker"]["margin_pct"]),
        cost_model=_cost_model(args["cost_model"]),
    )
    broker.open_position(acc, _tuple(args["quote"]), args["lots"], args["direction"])
    expected = case["expect"]
    assert acc.balance == pytest.approx(expected["balance"], abs=1e-6)
    assert acc.equity == pytest.approx(acc.balance + acc.open_pnl, abs=1e-6), (
        f"equity {acc.equity} != balance {acc.balance} + open_pnl {acc.open_pnl}"
    )
    assert acc.equity == pytest.approx(expected["equity"], abs=1e-6)


# --- fixture integrity --------------------------------------------------------------


def test_fixture_manifest_matches_fixture_bytes() -> None:
    """A silent edit to the frozen fixture file must fail here."""
    import json

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    assert manifest["fixture_file"] == FIXTURE_PATH.name
    assert manifest["schema_version"] == FIXTURE["schema_version"]
    assert manifest["sha256"] == digest, "fixture changed: bump the fixture version and manifest"


def test_fixture_declares_hand_calculation_for_every_case() -> None:
    for cases in FIXTURE["cases"].values():
        for case in cases:
            assert case.get("hand_calculation"), case["id"]
    for scenario in FIXTURE["account_scenarios"]:
        for event in scenario["events"]:
            assert event.get("hand_calculation"), f"{scenario['id']}@{event['key']}"


def test_adverse_and_positive_cases_cover_each_numeric_domain() -> None:
    """Each domain with a numeric contract has a positive and an adverse or boundary case."""
    by_domain: dict[str, set[str]] = {}
    for section, cases in FIXTURE["cases"].items():
        for case in cases:
            by_domain.setdefault(section, set()).add(case["polarity"])
    for section in (
        "bid_ask_spread_fees",
        "sizing_lot_rounding",
        "partial_targets",
        "timing_and_sessions",
        "rewards",
    ):
        polarities = by_domain[section]
        assert "positive" in polarities or "boundary" in polarities, section
        assert polarities & {"adverse", "boundary", "defect"}, section
    scenario_domains = {s["domain"] for s in FIXTURE["account_scenarios"]}
    required = {
        "equity_margin_daily_reset",
        "partial_fill_conservation",
        "fees_partial_fill_conservation",
        "equity_margin",
        "daily_reset_breach_latch",
    }
    assert required <= scenario_domains


def test_timestamps_in_fixture_are_timezone_aware_iso_strings() -> None:
    for case in FIXTURE["cases"]["timing_and_sessions"]:
        if case["op"] == "ftmo_trading_day" and "raises" not in str(case["expect"]):
            parsed = datetime.fromisoformat(case["args"]["timestamp"])
            assert parsed.tzinfo is not None
