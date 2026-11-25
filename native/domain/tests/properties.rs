//! Property tests for the domain invariants (NATIVE-DOMAIN).
//!
//! Each property is checked on random operation sequences against an independent running
//! total kept in the test, not against the production formulas.

use proptest::collection::vec;
use proptest::prelude::*;

use qrl_domain::order::ORDER_WIRE_LEN;
use qrl_domain::position::POSITION_WIRE_LEN;
use qrl_domain::{
    Account, DailyLossGuard, DomainError, Fill, Order, OrderIntent, OrderState, Position, Price,
    Quantity, Side,
};

/// Largest tick value used by the random sequences; magnitudes stay far inside i64.
const MAX_TICK_VALUE: i64 = 10_000;

#[derive(Debug, Clone, Copy)]
struct FillSpec {
    side: Side,
    price: i64,
    lots: i64,
    fee: i64,
}

fn any_side() -> impl Strategy<Value = Side> {
    prop_oneof![Just(Side::Buy), Just(Side::Sell)]
}

fn fill_spec() -> impl Strategy<Value = FillSpec> {
    (any_side(), 1i64..=2_000_000, 1i64..=50, 0i64..=1_000_000).prop_map(
        |(side, price, lots, fee)| FillSpec {
            side,
            price,
            lots,
            fee,
        },
    )
}

fn to_fill(spec: FillSpec) -> Fill {
    Fill::new(
        1,
        spec.side,
        Price::from_ticks(spec.price).unwrap(),
        Quantity::from_lots(spec.lots).unwrap(),
        spec.fee,
    )
    .unwrap()
}

#[derive(Debug, Clone, Copy)]
enum OrderStep {
    Accept,
    Reject,
    Cancel,
    Fill {
        foreign: bool,
        side: Side,
        lots: i64,
        price: i64,
    },
}

fn order_step() -> impl Strategy<Value = OrderStep> {
    prop_oneof![
        Just(OrderStep::Accept),
        Just(OrderStep::Reject),
        Just(OrderStep::Cancel),
        (any::<bool>(), any_side(), 1i64..=25, 1i64..=1_000).prop_map(
            |(foreign, side, lots, price)| {
                OrderStep::Fill {
                    foreign,
                    side,
                    lots,
                    price,
                }
            }
        ),
    ]
}

proptest! {
    /// Cash, realized PnL, fees and open cost reconcile after every fill, accepted or refused.
    #[test]
    fn account_reconciles_after_every_fill(
        start in 0i64..=1_000_000_000_000,
        tick_value in 1i64..=MAX_TICK_VALUE,
        mark in 1i64..=2_000_000,
        specs in vec(fill_spec(), 0..80),
    ) {
        let mut account = Account::new(start).unwrap();
        let mark = Price::from_ticks(mark).unwrap();
        // Independent running totals, in i128 so the test cannot overflow.
        let mut cash_flow: i128 = 0;
        let mut fees: i128 = 0;
        for spec in specs {
            account.apply_fill(&to_fill(spec), tick_value).unwrap();
            let notional = i128::from(spec.price) * i128::from(spec.lots) * i128::from(tick_value);
            cash_flow += -i128::from(spec.side.sign()) * notional;
            fees += i128::from(spec.fee);

            let position = account.position();
            // cash = start + cash flow - fees
            prop_assert_eq!(
                i128::from(account.cash_cents()),
                i128::from(start) + cash_flow - fees
            );
            // realized = cash flow + open cost basis
            prop_assert_eq!(
                i128::from(position.realized_pnl_cents()),
                cash_flow + i128::from(position.open_cost_cents())
            );
            prop_assert_eq!(i128::from(position.fees_cents()), fees);
            // equity = start + realized - fees + unrealized
            let equity = account.equity_cents(mark).unwrap();
            let unrealized = account.unrealized_pnl_cents(mark).unwrap();
            prop_assert_eq!(
                i128::from(equity),
                i128::from(start) + i128::from(position.realized_pnl_cents()) - fees
                    + i128::from(unrealized)
            );
            // Closed-position consistency: flat means no basis and no average.
            if position.lots() == 0 {
                prop_assert_eq!(position.open_cost_cents(), 0);
                prop_assert_eq!(position.average_entry_ticks(), None);
            } else {
                prop_assert!(position.open_cost_cents() != 0);
                prop_assert_eq!(position.open_cost_cents().signum(), position.lots().signum());
                prop_assert!(position.average_entry_ticks().is_some());
            }
        }
    }

    /// Fills are refused atomically: a refused fill changes neither cash nor position.
    #[test]
    fn refused_fills_leave_account_unchanged(
        tick_value in 1i64..=MAX_TICK_VALUE,
        other_tick in 1i64..=MAX_TICK_VALUE,
        spec in fill_spec(),
    ) {
        let mut account = Account::new(1_000_000).unwrap();
        account.apply_fill(&to_fill(spec), tick_value).unwrap();
        let before = account;
        let result = account.apply_fill(&to_fill(spec), other_tick);
        if other_tick == tick_value {
            prop_assert!(result.is_ok());
        } else {
            prop_assert_eq!(result, Err(DomainError::TickValueMismatch));
            prop_assert_eq!(account, before);
        }
    }

    /// Quantities never go negative, fills never exceed the order, and every state the
    /// lifecycle reaches round-trips through the wire frame.
    #[test]
    fn order_quantities_stay_nonnegative_and_bounded(
        lots in 1i64..=20,
        order_side in any_side(),
        steps in vec(order_step(), 0..40),
    ) {
        let mut order = Order::new(
            7,
            OrderIntent {
                side: order_side,
                quantity: Quantity::from_lots(lots).unwrap(),
            },
        );
        for step in steps {
            let before = order;
            let result = match step {
                OrderStep::Accept => order.accept(),
                OrderStep::Reject => order.reject(),
                OrderStep::Cancel => order.cancel(),
                OrderStep::Fill { foreign, side, lots, price } => {
                    let id = if foreign { 8 } else { 7 };
                    let fill = Fill::new(
                        id,
                        side,
                        Price::from_ticks(price).unwrap(),
                        Quantity::from_lots(lots).unwrap(),
                        0,
                    )
                    .unwrap();
                    order.apply_fill(&fill)
                }
            };
            if result.is_err() {
                prop_assert_eq!(order, before);
            }
            prop_assert!(order.filled_lots() >= 0);
            prop_assert!(order.remaining_lots() >= 0);
            prop_assert_eq!(order.filled_lots() + order.remaining_lots(), lots);
            match order.state() {
                OrderState::Filled => prop_assert_eq!(order.remaining_lots(), 0),
                OrderState::PartiallyFilled => {
                    prop_assert!(order.filled_lots() > 0 && order.remaining_lots() > 0);
                }
                _ => {}
            }
            prop_assert_eq!(Order::from_wire(&order.to_wire()), Ok(order));
        }
    }

    /// Position states reached by random fills round-trip through the wire frame.
    #[test]
    fn position_round_trips_after_every_fill(
        tick_value in 1i64..=MAX_TICK_VALUE,
        specs in vec(fill_spec(), 0..60),
    ) {
        let mut position = Position::flat();
        for spec in specs {
            position.apply_fill(&to_fill(spec), tick_value).unwrap();
            prop_assert_eq!(Position::from_wire(&position.to_wire()), Ok(position));
        }
    }

    /// Any byte string is either refused or decodes to a value that re-encodes to the same
    /// bytes. Decoding never produces a state that fill logic could not reach.
    #[test]
    fn position_decoding_is_refused_or_canonical(
        mut bytes in vec(any::<u8>(), POSITION_WIRE_LEN),
        version_is_current in any::<bool>(),
    ) {
        if version_is_current {
            bytes[0] = 2;
        }
        match Position::from_wire(&bytes) {
            Ok(position) => {
                let encoded = position.to_wire();
                prop_assert_eq!(encoded.as_slice(), bytes.as_slice());
            }
            Err(err) => prop_assert_eq!(err, DomainError::InvalidEncoding),
        }
    }

    /// Single-byte corruptions of a valid frame are refused or stay canonical.
    #[test]
    fn corrupted_position_frames_are_refused_or_canonical(
        tick_value in 1i64..=MAX_TICK_VALUE,
        specs in vec(fill_spec(), 1..20),
        index in 0usize..POSITION_WIRE_LEN,
        value in any::<u8>(),
    ) {
        let mut position = Position::flat();
        for spec in specs {
            position.apply_fill(&to_fill(spec), tick_value).unwrap();
        }
        let mut frame = position.to_wire();
        frame[index] = value;
        match Position::from_wire(&frame) {
            Ok(decoded) => prop_assert_eq!(decoded.to_wire(), frame),
            Err(err) => prop_assert_eq!(err, DomainError::InvalidEncoding),
        }
    }

    /// Order frames: arbitrary bytes are refused or canonical.
    #[test]
    fn order_decoding_is_refused_or_canonical(
        mut bytes in vec(any::<u8>(), ORDER_WIRE_LEN),
        version_is_current in any::<bool>(),
    ) {
        if version_is_current {
            bytes[0] = 2;
        }
        match Order::from_wire(&bytes) {
            Ok(order) => {
                let encoded = order.to_wire();
                prop_assert_eq!(encoded.as_slice(), bytes.as_slice());
            }
            Err(err) => prop_assert_eq!(err, DomainError::InvalidEncoding),
        }
    }

    /// Invalid scalar inputs are refused at construction and never produce a value.
    #[test]
    fn invalid_scalar_inputs_are_refused(
        ticks in -5i64..=5,
        lots in -5i64..=5,
        fee in -5i64..=5,
        start in -5i64..=5,
        limit in -5i64..=5,
        side in any_side(),
    ) {
        prop_assert_eq!(Price::from_ticks(ticks).is_ok(), ticks > 0);
        prop_assert_eq!(Quantity::from_lots(lots).is_ok(), lots > 0);
        prop_assert_eq!(Account::new(start).is_ok(), start >= 0);
        prop_assert_eq!(DailyLossGuard::new(1, 0, limit).is_ok(), limit > 0);
        if let (Ok(price), Ok(quantity)) = (Price::from_ticks(ticks), Quantity::from_lots(lots)) {
            prop_assert_eq!(Fill::new(1, side, price, quantity, fee).is_ok(), fee >= 0);
        }
    }

    /// The breach latch is monotone within a session, and only a strictly newer session
    /// clears it.
    #[test]
    fn daily_loss_latch_cannot_be_bypassed(
        start in 1_000i64..=2_000_000,
        limit in 1i64..=100_000,
        equities in vec(0i64..=3_000_000, 1..60),
    ) {
        let mut guard = DailyLossGuard::new(1, start, limit).unwrap();
        let mut latched = false;
        for equity in equities {
            let capacity = guard.observe_equity(equity).unwrap();
            prop_assert!(capacity >= 0);
            if equity <= guard.floor_cents() {
                latched = true;
            }
            prop_assert_eq!(guard.is_breached(), latched);
            prop_assert_eq!(guard.admit_entry().is_err(), latched);
        }
        // A restart with the same or an older session identifier is refused and keeps the latch.
        let before = guard;
        prop_assert_eq!(guard.start_session(1, start), Err(DomainError::SessionNotAdvanced));
        prop_assert_eq!(guard, before);
        // A strictly newer session clears the latch and re-anchors.
        guard.start_session(2, start).unwrap();
        prop_assert!(!guard.is_breached());
        prop_assert_eq!(guard.session_id(), 2);
    }
}

/// Worked examples the properties above generalize.
#[test]
fn worked_example_reconciles_by_hand() {
    // Buy 2 at 1000, buy 1 at 1010, sell 3 at 1010; tick value 100; no fees.
    // Cash flow: -200_000 - 101_000 + 303_000 = 2_000.
    // Closing: basis 301_000 removed in full (the sale closes all 3 lots), so realized 2_000.
    let mut account = Account::new(1_000_000).unwrap();
    let fills = [
        (Side::Buy, 1000, 2),
        (Side::Buy, 1010, 1),
        (Side::Sell, 1010, 3),
    ];
    for (side, price, lots) in fills {
        let fill = Fill::new(
            1,
            side,
            Price::from_ticks(price).unwrap(),
            Quantity::from_lots(lots).unwrap(),
            0,
        )
        .unwrap();
        account.apply_fill(&fill, 100).unwrap();
    }
    assert_eq!(account.position().lots(), 0);
    assert_eq!(account.position().realized_pnl_cents(), 2_000);
    assert_eq!(account.cash_cents(), 1_002_000);
}
