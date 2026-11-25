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
}

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
