//! Bounded property tests for the native domain invariants (QUALITY-AND-SECURITY).
//!
//! Determinism: every property runs with the fixed seed `SEED` and exactly `CASES` generated
//! cases, and failure persistence is off, so a rerun checks the same inputs and writes no files.
//!
//! Oracles: each property compares production code with an independent model that uses `i128`
//! arithmetic or with a stated invariant. Production formulas are never their own oracle.
//!
//! Covered invariants:
//! - integer units: checked arithmetic is exact or reports `Overflow`, never wraps;
//! - daily floor and capacity: exact, floored at zero, monotone in equity and in the limit;
//! - breach latch: monotone within a session, cleared only by a strictly newer session;
//! - position and account accounting: lots, fees, cash and PnL conserve, and refused fills
//!   leave the account unchanged;
//! - valuation: market value and unrealized PnL are exact or refuse with `Overflow`;
//! - wire frames: length and version are checked before decoding.

use proptest::collection::vec;
use proptest::prelude::*;
use proptest::test_runner::{Config, RngSeed, TestCaseError};

use qrl_domain::order::ORDER_WIRE_LEN;
use qrl_domain::position::{AVERAGE_ENTRY_SCALE, POSITION_WIRE_LEN};
use qrl_domain::{
    checked_add_units, limits, notional_cents, Account, DailyLossGuard, DomainError, Fill, Order,
    OrderIntent, Position, Price, Quantity, Side, DOMAIN_SCHEMA_VERSION,
};

/// Generated cases per property.
const CASES: u32 = 512;

/// Fixed RNG seed shared by every property in this file.
const SEED: u64 = 0x5152_4c44_0000_0002;

fn config() -> Config {
    Config {
        cases: CASES,
        rng_seed: RngSeed::Fixed(SEED),
        failure_persistence: None,
        ..Config::default()
    }
}

/// Widens an `i64` to the exact `i128` oracle type.
fn wide(value: i64) -> i128 {
    i128::from(value)
}

/// Exact product of three factors, or `None` when it does not fit in `i128`.
fn product3(a: i64, b: i64, c: i64) -> Option<i128> {
    wide(a).checked_mul(wide(b))?.checked_mul(wide(c))
}

/// Checks an `i64` result against an exact value: the exact value must match when it fits in
/// `i64`, and `Overflow` must be reported exactly when it does not (or when it is undefined).
fn expect_fits(result: Result<i64, DomainError>, exact: Option<i128>) -> Result<(), TestCaseError> {
    let fitting = exact.filter(|value| i64::try_from(*value).is_ok());
    match (result, fitting) {
        (Ok(got), Some(expected)) => {
            prop_assert_eq!(wide(got), expected);
        }
        (Err(err), None) => {
            prop_assert_eq!(err, DomainError::Overflow);
        }
        (got, expected) => {
            prop_assert!(
                false,
                "result {:?} disagrees with exact {:?}",
                got,
                expected
            );
        }
    }
    Ok(())
}

/// Oracle for capacity above a floor. The unclamped difference `equity - floor` must fit in `i64`
/// (the production code reports `Overflow` when it does not, even if the clamped value would be
/// zero). When it fits, the exact value is floored at zero.
fn capacity_oracle(floor: i64, equity: i64) -> Option<i128> {
    let difference = i64::try_from(wide(equity) - wide(floor)).ok()?;
    Some(wide(difference.max(0)))
}

/// Oracle for `remaining_daily_capacity`: the floor `start - limit` must itself fit in `i64`.
fn expected_capacity(start: i64, limit: i64, equity: i64) -> Option<i128> {
    let floor = i64::try_from(wide(start) - wide(limit)).ok()?;
    capacity_oracle(floor, equity)
}

/// Integers biased toward the edges of the `i64` range, plus small values.
fn any_int() -> impl Strategy<Value = i64> {
    prop_oneof![
        4 => any::<i64>(),
        1 => Just(i64::MIN),
        1 => Just(i64::MAX),
        1 => Just(0i64),
        1 => (i64::MAX - 8)..=i64::MAX,
        1 => i64::MIN..=(i64::MIN + 8),
        1 => -8i64..=8,
    ]
}

/// Strictly positive integers with the same edge bias.
fn positive_int() -> impl Strategy<Value = i64> {
    prop_oneof![
        4 => 1i64..=i64::MAX,
        1 => (i64::MAX - 8)..=i64::MAX,
        1 => 1i64..=8,
    ]
}

/// Ordinary trading magnitudes, where most fills are accepted.
fn small_positive() -> impl Strategy<Value = i64> {
    1i64..=5_000
}

#[derive(Debug, Clone, Copy)]
enum SessionStep {
    Observe(i64),
    NewSession { advance: u64, anchor: i64 },
    Stale { offset: u64, anchor: i64 },
}

fn session_step() -> impl Strategy<Value = SessionStep> {
    prop_oneof![
        4 => any_int().prop_map(SessionStep::Observe),
        1 => (1u64..=3, 0i64..=1_000_000_000_000)
            .prop_map(|(advance, anchor)| SessionStep::NewSession { advance, anchor }),
        1 => (0u64..=5, 0i64..=1_000_000_000_000)
            .prop_map(|(offset, anchor)| SessionStep::Stale { offset, anchor }),
    ]
}

#[derive(Debug, Clone, Copy)]
struct FillStep {
    buy: bool,
    price: i64,
    lots: i64,
    fee: i64,
}

fn fill_step() -> impl Strategy<Value = FillStep> {
    (
        any::<bool>(),
        prop_oneof![4 => small_positive(), 1 => positive_int()],
        prop_oneof![4 => 1i64..=50, 1 => positive_int()],
        prop_oneof![3 => 0i64..=10_000, 1 => 0i64..=i64::MAX],
    )
        .prop_map(|(buy, price, lots, fee)| FillStep {
            buy,
            price,
            lots,
            fee,
        })
}

proptest! {
    #![proptest_config(config())]

    /// Integer units: checked addition is exact or reports `Overflow`.
    #[test]
    fn checked_add_is_exact_or_overflows(a in any_int(), b in any_int()) {
        expect_fits(checked_add_units(a, b), Some(wide(a) + wide(b)))?;
    }

    /// Notional is `price * lots * tick value` exactly, or `Overflow` when it leaves `i64`.
    #[test]
    fn notional_is_exact_or_overflows(
        ticks in positive_int(),
        lots in positive_int(),
        tick_value in positive_int(),
    ) {
        let price = Price::from_ticks(ticks).unwrap();
        let quantity = Quantity::from_lots(lots).unwrap();
        expect_fits(
            notional_cents(price, quantity, tick_value),
            product3(ticks, lots, tick_value),
        )?;
    }

    /// Non-positive units are refused across the full `i64` range, and nothing else is.
    #[test]
    fn non_positive_units_are_refused_over_the_full_range(value in any_int()) {
        prop_assert_eq!(Price::from_ticks(value).is_ok(), value > 0);
        prop_assert_eq!(Quantity::from_lots(value).is_ok(), value > 0);
        let unit_price = Price::from_ticks(1).unwrap();
        let unit_quantity = Quantity::from_lots(1).unwrap();
        prop_assert_eq!(
            notional_cents(unit_price, unit_quantity, value).is_ok(),
            value > 0
        );
    }

    /// The daily floor is `start - limit` exactly, or `Overflow`.
    #[test]
    fn daily_floor_is_exact_or_overflows(start in any_int(), limit in any_int()) {
        expect_fits(
            limits::daily_floor(start, limit),
            Some(wide(start) - wide(limit)),
        )?;
    }

    /// Capacity is the exact distance above the floor, floored at zero. It never decreases as
    /// equity rises or as the loss limit widens, and it is zero at or below the floor.
    #[test]
    fn capacity_is_exact_and_monotone(
        start in any_int(),
        limit in positive_int(),
        other_limit in positive_int(),
        equity_a in any_int(),
        equity_b in any_int(),
    ) {
        let (low, high) = if equity_a <= equity_b {
            (equity_a, equity_b)
        } else {
            (equity_b, equity_a)
        };
        let capacity_low = limits::remaining_daily_capacity(start, low, limit);
        let capacity_high = limits::remaining_daily_capacity(start, high, limit);
        expect_fits(capacity_low, expected_capacity(start, limit, low))?;
        expect_fits(capacity_high, expected_capacity(start, limit, high))?;

        if let (Ok(below), Ok(above)) = (capacity_low, capacity_high) {
            prop_assert!(below <= above, "capacity fell from {} to {} as equity rose", below, above);
            prop_assert!(below >= 0 && above >= 0);
            if high <= limits::daily_floor(start, limit).unwrap() {
                prop_assert_eq!(above, 0);
            }
        }

        // Widening the loss limit lowers the floor and never reduces capacity.
        let (narrow, wide_limit) = if limit <= other_limit {
            (limit, other_limit)
        } else {
            (other_limit, limit)
        };
        if let (Ok(narrow_capacity), Ok(wide_capacity)) = (
            limits::remaining_daily_capacity(start, high, narrow),
            limits::remaining_daily_capacity(start, high, wide_limit),
        ) {
            prop_assert!(narrow_capacity <= wide_capacity);
        }
        if let (Ok(narrow_floor), Ok(wide_floor)) = (
            limits::daily_floor(start, narrow),
            limits::daily_floor(start, wide_limit),
        ) {
            prop_assert!(wide_floor <= narrow_floor);
        }
    }

    /// Breach latch and floor follow an independent session model. The floor is constant within
    /// a session, the latch is set by any observation at or below the floor, it survives recovery
    /// and refused session restarts, and only a strictly newer session clears it.
    #[test]
    fn breach_latch_and_floor_follow_the_session_model(
        start in 0i64..=1_000_000_000_000,
        limit in 1i64..=1_000_000_000_000,
        steps in vec(session_step(), 1..80),
    ) {
        let mut guard = DailyLossGuard::new(1, start, limit).unwrap();
        let mut session_id: u64 = 1;
        let mut floor = start - limit;
        let mut latched = false;
        for step in steps {
            let before = guard;
            match step {
                SessionStep::Observe(equity) => {
                    // The latch is set before the capacity arithmetic, so it holds even when the
                    // returned capacity is an overflow. This is the fail-closed behavior.
                    let result = guard.observe_equity(equity);
                    latched |= equity <= floor;
                    expect_fits(result, capacity_oracle(floor, equity))?;
                }
                SessionStep::NewSession { advance, anchor } => {
                    session_id += advance;
                    let restarted = guard.start_session(session_id, anchor);
                    prop_assert_eq!(restarted, Ok(()));
                    floor = anchor - limit;
                    latched = false;
                }
                SessionStep::Stale { offset, anchor } => {
                    let attempt = session_id.saturating_sub(offset);
                    prop_assert_eq!(
                        guard.start_session(attempt, anchor),
                        Err(DomainError::SessionNotAdvanced)
                    );
                    prop_assert_eq!(guard, before);
                }
            }
            prop_assert_eq!(guard.session_id(), session_id);
            prop_assert_eq!(guard.floor_cents(), floor);
            prop_assert_eq!(guard.is_breached(), latched);
            prop_assert_eq!(guard.admit_entry().is_err(), latched);
        }
    }

    /// Accounting conservation over random fills. Each accepted fill keeps lots, fees, cash and
    /// PnL equal to independent wide-integer totals, and the average entry stays inside the
    /// price range of the open lots. A refused fill (`Overflow`) leaves the whole account
    /// unchanged, including cash, position and fees.
    #[test]
    fn account_conserves_lots_fees_cash_and_pnl(
        start in 0i64..=i64::MAX,
        tick_value in prop_oneof![4 => 1i64..=1_000, 1 => positive_int()],
        steps in vec(fill_step(), 0..120),
    ) {
        let mut account = Account::new(start).unwrap();
        let mut lots_total: i128 = 0;
        let mut fees_total: i128 = 0;
        let mut cash_flow: i128 = 0;
        // Inclusive price range (ticks) of the lots open since the position was last flat.
        let mut range: Option<(i128, i128)> = None;
        for step in steps {
            let before = account;
            let side = if step.buy { Side::Buy } else { Side::Sell };
            let sign = side.sign();
            let fill = Fill::new(
                1,
                side,
                Price::from_ticks(step.price).unwrap(),
                Quantity::from_lots(step.lots).unwrap(),
                step.fee,
            )
            .unwrap();
            match account.apply_fill(&fill, tick_value) {
                Err(err) => {
                    prop_assert_eq!(err, DomainError::Overflow);
                    prop_assert_eq!(account, before);
                }
                Ok(()) => {
                    // Accepted, so the notional fits in i64 and the wide product is exact.
                    let notional = product3(step.price, step.lots, tick_value).unwrap();
                    cash_flow -= i128::from(sign) * notional;
                    fees_total += wide(step.fee);
                    let lots_before = lots_total;
                    lots_total += i128::from(sign) * wide(step.lots);
                    let price = wide(step.price);
                    range = if lots_total == 0 {
                        None
                    } else if lots_before == 0 || lots_before.signum() != lots_total.signum() {
                        Some((price, price))
                    } else if i128::from(sign) == lots_before.signum() {
                        range.map(|(lo, hi)| (lo.min(price), hi.max(price)))
                    } else {
                        range
                    };

                    let position = account.position();
                    prop_assert_eq!(wide(position.lots()), lots_total);
                    prop_assert_eq!(wide(position.fees_cents()), fees_total);
                    prop_assert_eq!(
                        wide(account.cash_cents()),
                        wide(start) + cash_flow - fees_total
                    );
                    // Cash flow equals realized PnL minus the signed open cost basis.
                    prop_assert_eq!(
                        wide(position.realized_pnl_cents()) - wide(position.open_cost_cents()),
                        cash_flow
                    );
                    match range {
                        None => {
                            prop_assert_eq!(position.average_entry_scaled(), None);
                            prop_assert_eq!(position.open_cost_cents(), 0);
                        }
                        Some((lo, hi)) => {
                            let average = wide(
                                position
                                    .average_entry_scaled()
                                    .expect("an open position has an average entry"),
                            );
                            let scale = wide(AVERAGE_ENTRY_SCALE);
                            prop_assert!(
                                lo * scale <= average && average <= hi * scale,
                                "average {} micro-ticks outside [{}, {}] ticks",
                                average,
                                lo,
                                hi
                            );
                        }
                    }
                }
            }
        }
    }

    /// Market value and unrealized PnL are exact or refuse with `Overflow`. Both are computed
    /// from a position opened by one accepted fill.
    #[test]
    fn valuation_is_exact_or_overflows(
        buy in any::<bool>(),
        entry in small_positive(),
        lots in 1i64..=50,
        tick_value in 1i64..=1_000_000_000_000,
        mark in positive_int(),
    ) {
        let side = if buy { Side::Buy } else { Side::Sell };
        let sign = i128::from(side.sign());
        let fill = Fill::new(
            1,
            side,
            Price::from_ticks(entry).unwrap(),
            Quantity::from_lots(lots).unwrap(),
            0,
        )
        .unwrap();
        let mut position = Position::flat();
        position.apply_fill(&fill, tick_value).unwrap();
        let mark_price = Price::from_ticks(mark).unwrap();

        let exact_market = product3(mark, lots, tick_value).map(|value| sign * value);
        expect_fits(position.market_value_cents(mark_price), exact_market)?;

        let exact_basis = product3(entry, lots, tick_value).map(|value| sign * value);
        match (position.unrealized_pnl_cents(mark_price), exact_market, exact_basis) {
            (Ok(unrealized), Some(market), Some(basis)) => {
                prop_assert_eq!(wide(unrealized), market - basis);
            }
            (Err(err), _, _) => prop_assert_eq!(err, DomainError::Overflow),
            (got, market, basis) => {
                prop_assert!(false, "unrealized {:?} with market {:?} basis {:?}", got, market, basis);
            }
        }
    }

    /// Wire frames: a frame of the wrong length or version is refused with `InvalidEncoding`
    /// before any field is read, for both position and order frames.
    #[test]
    fn frame_length_and_version_are_checked_before_decoding(
        len in 0usize..=2 * POSITION_WIRE_LEN,
        version in any::<u8>(),
        bytes in vec(any::<u8>(), 2 * POSITION_WIRE_LEN),
    ) {
        let current = u8::try_from(DOMAIN_SCHEMA_VERSION).unwrap();
        let mut frame = bytes[..len].to_vec();
        if let Some(first) = frame.first_mut() {
            *first = version;
        }
        if len != POSITION_WIRE_LEN || version != current {
            prop_assert_eq!(Position::from_wire(&frame), Err(DomainError::InvalidEncoding));
        }
        if len != ORDER_WIRE_LEN || version != current {
            prop_assert_eq!(Order::from_wire(&frame), Err(DomainError::InvalidEncoding));
        }
    }

    /// A fresh order's frame decodes to the same order for any valid quantity and side.
    #[test]
    fn fresh_order_frame_round_trips(
        id in any::<u64>(),
        lots in positive_int(),
        buy in any::<bool>(),
    ) {
        let side = if buy { Side::Buy } else { Side::Sell };
        let order = Order::new(
            id,
            OrderIntent {
                side,
                quantity: Quantity::from_lots(lots).unwrap(),
            },
        );
        prop_assert_eq!(Order::from_wire(&order.to_wire()), Ok(order));
    }
}
