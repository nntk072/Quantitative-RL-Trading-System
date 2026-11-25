//! Order lifecycle, fills and the decision that precedes an order.
//!
//! Distinct concepts, kept as distinct types:
//! - [`OrderIntent`] is a decision (side and size). It has no identity, no state and
//!   is never sent anywhere.
//! - [`Order`] is the order created from an intent. It owns the lifecycle state machine.
//! - [`Fill`] is an execution report for one order. It is applied to an `Order` and to a
//!   [`Position`](crate::position::Position).
//!
//! Every lifecycle move is checked; invalid moves return [`DomainError::InvalidTransition`]
//! and leave the order unchanged.

use crate::units::{Price, Quantity, Side};
use crate::wire;
use crate::DomainError;

/// A decision to trade. Not an order: it has no lifecycle.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct OrderIntent {
    pub side: Side,
    pub quantity: Quantity,
}

/// Lifecycle state of an [`Order`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrderState {
    Pending,
    Accepted,
    PartiallyFilled,
    Filled,
    Cancelled,
    Rejected,
}

impl OrderState {
    /// Terminal states admit no further transition.
    pub const fn is_terminal(self) -> bool {
        matches!(
            self,
            OrderState::Filled | OrderState::Cancelled | OrderState::Rejected
        )
    }

    /// The complete transition table. Anything not listed is refused.
    const fn can_transition_to(self, to: OrderState) -> bool {
        use OrderState::*;
        matches!(
            (self, to),
            (Pending, Accepted)
                | (Pending, Rejected)
                | (Accepted, PartiallyFilled)
                | (Accepted, Filled)
                | (Accepted, Cancelled)
                | (PartiallyFilled, PartiallyFilled)
                | (PartiallyFilled, Filled)
                | (PartiallyFilled, Cancelled)
        )
    }
}

/// An execution report for one order. Price and quantity are validated at construction.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fill {
    pub order_id: u64,
    pub side: Side,
    pub price: Price,
    pub quantity: Quantity,
    /// Commission in cents; never negative.
    pub fee_cents: i64,
}

impl Fill {
    /// Builds a fill; a negative fee is rejected.
    pub fn new(
        order_id: u64,
        side: Side,
        price: Price,
        quantity: Quantity,
        fee_cents: i64,
    ) -> Result<Self, DomainError> {
        if fee_cents < 0 {
            return Err(DomainError::NegativeFee);
        }
        Ok(Self {
            order_id,
            side,
            price,
            quantity,
            fee_cents,
        })
    }
}

/// An order created from an [`OrderIntent`], with checked lifecycle transitions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Order {
    id: u64,
    side: Side,
    quantity: Quantity,
    filled_lots: i64,
    state: OrderState,
}

impl Order {
    /// Creates a pending order from a decision.
    pub fn new(id: u64, intent: OrderIntent) -> Self {
        Self {
            id,
            side: intent.side,
            quantity: intent.quantity,
            filled_lots: 0,
            state: OrderState::Pending,
        }
    }

    pub const fn id(&self) -> u64 {
        self.id
    }

    pub const fn side(&self) -> Side {
        self.side
    }

    pub const fn quantity(&self) -> Quantity {
        self.quantity
    }

    pub const fn filled_lots(&self) -> i64 {
        self.filled_lots
    }

    /// Lots still open; never negative because overfills are refused.
    pub const fn remaining_lots(&self) -> i64 {
        self.quantity.lots() - self.filled_lots
    }

    pub const fn state(&self) -> OrderState {
        self.state
    }

    /// Pending to Accepted.
    pub fn accept(&mut self) -> Result<(), DomainError> {
        self.transition(OrderState::Accepted)
    }

    /// Pending to Rejected.
    pub fn reject(&mut self) -> Result<(), DomainError> {
        self.transition(OrderState::Rejected)
    }

    /// Accepted or PartiallyFilled to Cancelled. Filled orders cannot be cancelled.
    pub fn cancel(&mut self) -> Result<(), DomainError> {
        self.transition(OrderState::Cancelled)
    }

    /// Applies a fill to an accepted or partially filled order.
    ///
    /// Refuses fills for another order or side, fills that would exceed the order quantity,
    /// and fills while the order is pending or terminal.
    pub fn apply_fill(&mut self, fill: &Fill) -> Result<(), DomainError> {
        if fill.order_id != self.id {
            return Err(DomainError::OrderMismatch);
        }
        if fill.side != self.side {
            return Err(DomainError::SideMismatch);
        }
        if !matches!(
            self.state,
            OrderState::Accepted | OrderState::PartiallyFilled
        ) {
            return Err(DomainError::InvalidTransition {
                from: self.state,
                to: OrderState::PartiallyFilled,
            });
        }
        let filled = self
            .filled_lots
            .checked_add(fill.quantity.lots())
            .ok_or(DomainError::Overflow)?;
        if filled > self.quantity.lots() {
            return Err(DomainError::Overfill);
        }
        let next = if filled == self.quantity.lots() {
            OrderState::Filled
        } else {
            OrderState::PartiallyFilled
        };
        self.transition(next)?;
        self.filled_lots = filled;
        Ok(())
    }

    fn transition(&mut self, to: OrderState) -> Result<(), DomainError> {
        if !self.state.can_transition_to(to) {
            return Err(DomainError::InvalidTransition {
                from: self.state,
                to,
            });
        }
        self.state = to;
        Ok(())
    }

    /// Canonical fixed-width frame of the order: version, id, side tag, quantity, filled lots,
    /// state tag. Little-endian integers.
    pub fn to_wire(&self) -> [u8; ORDER_WIRE_LEN] {
        let mut out = [0u8; ORDER_WIRE_LEN];
        out[0] = wire::VERSION;
        out[1..9].copy_from_slice(&self.id.to_le_bytes());
        out[9] = match self.side {
            Side::Buy => 0,
            Side::Sell => 1,
        };
        out[10..18].copy_from_slice(&self.quantity.lots().to_le_bytes());
        out[18..26].copy_from_slice(&self.filled_lots.to_le_bytes());
        out[26] = match self.state {
            OrderState::Pending => 0,
            OrderState::Accepted => 1,
            OrderState::PartiallyFilled => 2,
            OrderState::Filled => 3,
            OrderState::Cancelled => 4,
            OrderState::Rejected => 5,
        };
        out
    }

    /// Decodes a frame written by [`Order::to_wire`].
    ///
    /// Refuses a wrong length, version or tag, a nonpositive quantity, and a state that the
    /// transition table could not reach with the recorded fill count.
    pub fn from_wire(bytes: &[u8]) -> Result<Self, DomainError> {
        wire::check_frame(bytes, ORDER_WIRE_LEN)?;
        let side = match wire::read_tag(bytes, 9)? {
            0 => Side::Buy,
            1 => Side::Sell,
            _ => return Err(DomainError::InvalidEncoding),
        };
        let state = match wire::read_tag(bytes, 26)? {
            0 => OrderState::Pending,
            1 => OrderState::Accepted,
            2 => OrderState::PartiallyFilled,
            3 => OrderState::Filled,
            4 => OrderState::Cancelled,
            5 => OrderState::Rejected,
            _ => return Err(DomainError::InvalidEncoding),
        };
        let order = Self {
            id: wire::read_u64(bytes, 1)?,
            side,
            quantity: Quantity::from_lots(wire::read_i64(bytes, 10)?)
                .map_err(|_| DomainError::InvalidEncoding)?,
            filled_lots: wire::read_i64(bytes, 18)?,
            state,
        };
        if order.is_reachable() {
            Ok(order)
        } else {
            Err(DomainError::InvalidEncoding)
        }
    }

    /// Whether the lifecycle could have produced this state and fill count.
    fn is_reachable(&self) -> bool {
        let quantity = self.quantity.lots();
        let filled = self.filled_lots;
        match self.state {
            OrderState::Pending | OrderState::Accepted | OrderState::Rejected => filled == 0,
            OrderState::PartiallyFilled => filled > 0 && filled < quantity,
            OrderState::Filled => filled == quantity,
            OrderState::Cancelled => (0..quantity).contains(&filled),
        }
    }
}

/// Serialized length of an [`Order`] frame in bytes.
pub const ORDER_WIRE_LEN: usize = 27;

#[cfg(test)]
mod tests {
    use super::*;

    fn intent(side: Side, lots: i64) -> OrderIntent {
        OrderIntent {
            side,
            quantity: Quantity::from_lots(lots).unwrap(),
        }
    }

    fn fill(order_id: u64, side: Side, price: i64, lots: i64, fee: i64) -> Fill {
        Fill::new(
            order_id,
            side,
            Price::from_ticks(price).unwrap(),
            Quantity::from_lots(lots).unwrap(),
            fee,
        )
        .unwrap()
    }

    #[test]
    fn new_order_is_pending_with_nothing_filled() {
        let order = Order::new(7, intent(Side::Buy, 3));
        assert_eq!(order.state(), OrderState::Pending);
        assert_eq!(order.filled_lots(), 0);
        assert_eq!(order.remaining_lots(), 3);
        assert!(!order.state().is_terminal());
    }

    #[test]
    fn full_lifecycle_through_partial_fill_to_filled() {
        let mut order = Order::new(1, intent(Side::Buy, 3));
        order.accept().unwrap();
        order.apply_fill(&fill(1, Side::Buy, 1000, 1, 0)).unwrap();
        assert_eq!(order.state(), OrderState::PartiallyFilled);
        assert_eq!(order.remaining_lots(), 2);
        order.apply_fill(&fill(1, Side::Buy, 1001, 2, 0)).unwrap();
        assert_eq!(order.state(), OrderState::Filled);
        assert_eq!(order.remaining_lots(), 0);
        assert!(order.state().is_terminal());
    }

    #[test]
    fn filled_order_cannot_be_cancelled() {
        let mut order = Order::new(1, intent(Side::Sell, 1));
        order.accept().unwrap();
        order.apply_fill(&fill(1, Side::Sell, 1000, 1, 0)).unwrap();
        assert_eq!(
            order.cancel(),
            Err(DomainError::InvalidTransition {
                from: OrderState::Filled,
                to: OrderState::Cancelled,
            })
        );
        assert_eq!(order.state(), OrderState::Filled);
    }

    #[test]
    fn partially_filled_order_can_be_cancelled_for_the_remainder() {
        let mut order = Order::new(1, intent(Side::Buy, 2));
        order.accept().unwrap();
        order.apply_fill(&fill(1, Side::Buy, 1000, 1, 0)).unwrap();
        order.cancel().unwrap();
        assert_eq!(order.state(), OrderState::Cancelled);
        assert_eq!(order.filled_lots(), 1);
    }

    #[test]
    fn pending_order_cannot_be_filled_or_cancelled() {
        let mut order = Order::new(1, intent(Side::Buy, 1));
        assert_eq!(
            order.apply_fill(&fill(1, Side::Buy, 1000, 1, 0)),
            Err(DomainError::InvalidTransition {
                from: OrderState::Pending,
                to: OrderState::PartiallyFilled,
            })
        );
        assert_eq!(
            order.cancel(),
            Err(DomainError::InvalidTransition {
                from: OrderState::Pending,
                to: OrderState::Cancelled,
            })
        );
        assert_eq!(order.state(), OrderState::Pending);
        assert_eq!(order.filled_lots(), 0);
    }

    #[test]
    fn rejected_and_cancelled_are_terminal() {
        let mut rejected = Order::new(1, intent(Side::Buy, 1));
        rejected.reject().unwrap();
        assert_eq!(
            rejected.accept(),
            Err(DomainError::InvalidTransition {
                from: OrderState::Rejected,
                to: OrderState::Accepted,
            })
        );

        let mut cancelled = Order::new(2, intent(Side::Buy, 1));
        cancelled.accept().unwrap();
        cancelled.cancel().unwrap();
        assert_eq!(
            cancelled.apply_fill(&fill(2, Side::Buy, 1000, 1, 0)),
            Err(DomainError::InvalidTransition {
                from: OrderState::Cancelled,
                to: OrderState::PartiallyFilled,
            })
        );
    }

    #[test]
    fn overfill_is_refused_and_order_unchanged() {
        let mut order = Order::new(1, intent(Side::Buy, 2));
        order.accept().unwrap();
        assert_eq!(
            order.apply_fill(&fill(1, Side::Buy, 1000, 3, 0)),
            Err(DomainError::Overfill)
        );
        assert_eq!(order.state(), OrderState::Accepted);
        assert_eq!(order.filled_lots(), 0);
    }

    #[test]
    fn fill_for_other_order_or_side_is_refused() {
        let mut order = Order::new(1, intent(Side::Buy, 2));
        order.accept().unwrap();
        assert_eq!(
            order.apply_fill(&fill(9, Side::Buy, 1000, 1, 0)),
            Err(DomainError::OrderMismatch)
        );
        assert_eq!(
            order.apply_fill(&fill(1, Side::Sell, 1000, 1, 0)),
            Err(DomainError::SideMismatch)
        );
        assert_eq!(order.filled_lots(), 0);
    }

    #[test]
    fn wire_round_trip_keeps_state_and_fill_count() {
        let mut order = Order::new(42, intent(Side::Sell, 3));
        order.accept().unwrap();
        order.apply_fill(&fill(42, Side::Sell, 1000, 1, 0)).unwrap();
        let frame = order.to_wire();
        assert_eq!(frame.len(), ORDER_WIRE_LEN);
        assert_eq!(Order::from_wire(&frame), Ok(order));
    }

    #[test]
    fn wire_refuses_unreachable_or_malformed_frames() {
        let order = Order::new(1, intent(Side::Buy, 2));
        let frame = order.to_wire();
        assert_eq!(
            Order::from_wire(&frame[..ORDER_WIRE_LEN - 1]),
            Err(DomainError::InvalidEncoding)
        );
        let mut bad_version = frame;
        bad_version[0] = 9;
        assert_eq!(
            Order::from_wire(&bad_version),
            Err(DomainError::InvalidEncoding)
        );
        let mut bad_side = frame;
        bad_side[9] = 7;
        assert_eq!(
            Order::from_wire(&bad_side),
            Err(DomainError::InvalidEncoding)
        );
        let mut bad_state = frame;
        bad_state[26] = 6;
        assert_eq!(
            Order::from_wire(&bad_state),
            Err(DomainError::InvalidEncoding)
        );
        // A filled order must have filled every lot.
        let mut filled_without_lots = frame;
        filled_without_lots[26] = 3;
        assert_eq!(
            Order::from_wire(&filled_without_lots),
            Err(DomainError::InvalidEncoding)
        );
        // A pending order cannot carry fills.
        let mut pending_with_fill = frame;
        pending_with_fill[18] = 1;
        assert_eq!(
            Order::from_wire(&pending_with_fill),
            Err(DomainError::InvalidEncoding)
        );
        // Quantity zero is not a tradable order.
        let mut zero_quantity = frame;
        zero_quantity[10..18].copy_from_slice(&0i64.to_le_bytes());
        assert_eq!(
            Order::from_wire(&zero_quantity),
            Err(DomainError::InvalidEncoding)
        );
    }

    #[test]
    fn negative_fee_is_refused() {
        let price = Price::from_ticks(1000).unwrap();
        let qty = Quantity::from_lots(1).unwrap();
        assert_eq!(
            Fill::new(1, Side::Buy, price, qty, -1),
            Err(DomainError::NegativeFee)
        );
        assert!(Fill::new(1, Side::Buy, price, qty, 0).is_ok());
    }
}
