"""Bounded randomized boundary test for the Python-facing native parsers (QUALITY-AND-SECURITY).

Determinism: each test seeds its own ``random.Random(SEED)`` and runs a fixed number of
iterations (``ITERATIONS``), so a rerun exercises the same inputs in the same order.

Boundary contract checked against exact Python integers (no native code is used as its own
oracle):

- a non-integer argument raises ``TypeError`` at conversion and never reaches the domain logic;
- an integer outside the signed 64-bit range raises ``OverflowError`` at conversion;
- an in-range result equals the exact value or raises ``OverflowError``; it never wraps;
- non-positive units, negative fees and a tick-value mismatch raise ``ValueError``;
- a refused ``Position.apply_fill`` leaves every getter unchanged.

A Rust panic would surface as ``pyo3_runtime.PanicException``, which no case expects, so it
fails the test.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

qrl_native = pytest.importorskip("qrl_native")

SEED = 20261126
ITERATIONS = 2000
I64_MIN = -(2**63)
I64_MAX = 2**63 - 1
EDGES = (I64_MIN, I64_MIN + 1, -1, 0, 1, 2, 3, 1_000, I64_MAX - 1, I64_MAX)
OUT_OF_RANGE = (I64_MIN - 1, I64_MAX + 1, -(2**80), 2**80)
NON_INTEGERS: tuple[Any, ...] = (1.5, 2.0, "3", None, b"4", [5])

Outcome = tuple[str, Any]


def _fits(value: int) -> bool:
    return I64_MIN <= value <= I64_MAX


def _integer(rng: random.Random) -> int:
    roll = rng.random()
    if roll < 0.3:
        return rng.choice(EDGES)
    if roll < 0.6:
        return rng.randint(-1_000, 1_000)
    return rng.randint(I64_MIN, I64_MAX)


def _corrupt(rng: random.Random, args: list[Any]) -> tuple[list[Any], str]:
    """Corrupts at most one argument and returns the boundary class the call must hit."""
    roll = rng.random()
    if roll < 0.2:
        args[rng.randrange(len(args))] = rng.choice(NON_INTEGERS)
        return args, "TypeError"
    if roll < 0.4:
        args[rng.randrange(len(args))] = rng.choice(OUT_OF_RANGE)
        return args, "OverflowError"
    return args, "clean"


def _run(fn: Callable[..., Any], args: list[Any]) -> Outcome:
    """Returns ``("value", result)`` or ``(exception class name, None)`` for boundary errors."""
    try:
        return "value", fn(*args)
    except (TypeError, OverflowError, ValueError) as exc:
        return type(exc).__name__, None


def _oracle_checked_add(a: int, b: int) -> Outcome:
    exact = a + b
    return ("value", exact) if _fits(exact) else ("OverflowError", None)


def _oracle_daily_floor(start: int, limit: int) -> Outcome:
    exact = start - limit
    return ("value", exact) if _fits(exact) else ("OverflowError", None)


def _oracle_canonical_loss(start: int, equity: int) -> Outcome:
    difference = start - equity
    if not _fits(difference):
        return "OverflowError", None
    return "value", max(difference, 0)


def _oracle_capacity(start: int, equity: int, limit: int) -> Outcome:
    floor = start - limit
    if not _fits(floor):
        return "OverflowError", None
    difference = equity - floor
    if not _fits(difference):
        return "OverflowError", None
    return "value", max(difference, 0)


def _oracle_notional(price: int, lots: int, tick_value: int) -> Outcome:
    if price <= 0 or lots <= 0 or tick_value <= 0:
        return "ValueError", None
    exact = price * lots * tick_value
    return ("value", exact) if _fits(exact) else ("OverflowError", None)


def _check_function(
    fn: Callable[..., Any],
    arity: int,
    oracle: Callable[..., Outcome],
    rng: random.Random,
) -> Counter[str]:
    seen: Counter[str] = Counter()
    for _ in range(ITERATIONS):
        args, boundary = _corrupt(rng, [_integer(rng) for _ in range(arity)])
        expected = oracle(*args) if boundary == "clean" else (boundary, None)
        got = _run(fn, args)
        assert got == expected, (fn.__name__, args, got, expected)
        seen[got[0]] += 1
    return seen


def test_checked_add_units_is_exact_or_overflows() -> None:
    seen = _check_function(
        qrl_native.checked_add_units, 2, _oracle_checked_add, random.Random(SEED)
    )
    assert seen["value"] > 0 and seen["TypeError"] > 0 and seen["OverflowError"] > 0


def test_daily_floor_is_exact_or_overflows() -> None:
    seen = _check_function(
        qrl_native.daily_floor_cents, 2, _oracle_daily_floor, random.Random(SEED + 1)
    )
    assert seen["value"] > 0 and seen["TypeError"] > 0 and seen["OverflowError"] > 0


def test_canonical_daily_loss_is_floored_exact_or_overflows() -> None:
    seen = _check_function(
        qrl_native.canonical_daily_loss_cents, 2, _oracle_canonical_loss, random.Random(SEED + 2)
    )
    assert seen["value"] > 0 and seen["TypeError"] > 0 and seen["OverflowError"] > 0


def test_remaining_capacity_is_floored_exact_or_overflows() -> None:
    seen = _check_function(
        qrl_native.remaining_daily_capacity_cents, 3, _oracle_capacity, random.Random(SEED + 3)
    )
    assert seen["value"] > 0 and seen["TypeError"] > 0 and seen["OverflowError"] > 0


def test_notional_is_exact_rejects_nonpositive_and_overflows() -> None:
    seen = _check_function(qrl_native.notional_cents, 3, _oracle_notional, random.Random(SEED + 4))
    assert seen["value"] > 0 and seen["ValueError"] > 0
    assert seen["TypeError"] > 0 and seen["OverflowError"] > 0


def _position_state(position: Any) -> tuple[Any, ...]:
    return (
        position.lots,
        position.average_entry_ticks,
        position.realized_pnl_cents,
        position.fees_cents,
    )


def test_position_refusals_leave_state_unchanged_and_lots_and_fees_conserve() -> None:
    rng = random.Random(SEED + 5)
    seen: Counter[str] = Counter()
    sequences = ITERATIONS // 10
    for _ in range(sequences):
        position = qrl_native.Position()
        fixed_tick_value: int | None = None
        lots_total = 0
        fees_total = 0
        for _ in range(10):
            buy = rng.random() < 0.5
            sign = 1 if buy else -1
            price = rng.randint(1, 5_000) if rng.random() < 0.7 else _integer(rng)
            lots = rng.randint(1, 50) if rng.random() < 0.7 else _integer(rng)
            fee = rng.randint(0, 1_000) if rng.random() < 0.7 else _integer(rng)
            tick_value = 100 if rng.random() < 0.8 else _integer(rng)
            args, boundary = _corrupt(rng, [price, lots, fee, tick_value])
            price, lots, fee, tick_value = args

            before = _position_state(position)
            got = _run(partial(position.apply_fill, buy), args)
            seen[got[0]] += 1

            if boundary == "TypeError":
                assert got == ("TypeError", None), args
            elif boundary == "OverflowError":
                assert got == ("OverflowError", None), args
            else:
                validation_failure = (
                    price <= 0
                    or lots <= 0
                    or fee < 0
                    or tick_value <= 0
                    or (fixed_tick_value is not None and tick_value != fixed_tick_value)
                )
                if validation_failure:
                    assert got == ("ValueError", None), (buy, args, got)
                else:
                    # The notional or a running total may leave i64; then the call must refuse.
                    assert got[0] in ("value", "OverflowError"), (buy, args, got)

            if got[0] != "value":
                assert _position_state(position) == before, (buy, args, got)
                continue
            lots_total += sign * lots
            fees_total += fee
            fixed_tick_value = tick_value
            assert position.lots == lots_total, (buy, args)
            assert position.fees_cents == fees_total, (buy, args)

    assert seen["value"] > 0 and seen["ValueError"] > 0
    assert seen["TypeError"] > 0 and seen["OverflowError"] > 0
