//! Cash and position for one instrument in one account currency.
//!
//! Cash moves by the whole notional of each fill and by its fee: a buy pays the notional, a
//! sell receives it, and every fill pays its commission. Equity at a mark is cash plus the
//! market value of the open lots. Realized PnL, fees and cost basis come from [`Position`],
//! so for every reachable state, with `S` the starting cash and `F` the fees paid:
//!
//! - `cash = S + cash_flow - F`, where `cash_flow` is the signed notional of all fills;
//! - `equity(mark) = S + realized_pnl - F + unrealized_pnl(mark)`.
//!
//! The account does not enforce buying power or margin; cash may go negative. Loss limits are
//! applied by [`crate::risk::DailyLossGuard`].

use crate::order::Fill;
use crate::position::Position;
use crate::units::{notional_cents, Price, Side};
use crate::DomainError;

/// Cash and position for one instrument.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Account {
    starting_cash_cents: i64,
    cash_cents: i64,
    position: Position,
}

impl Account {
    /// An account holding `starting_cash_cents` and no position. Negative starting cash is
    /// refused.
    pub fn new(starting_cash_cents: i64) -> Result<Self, DomainError> {
        if starting_cash_cents < 0 {
            return Err(DomainError::NegativeCash);
        }
        Ok(Self {
            starting_cash_cents,
            cash_cents: starting_cash_cents,
            position: Position::flat(),
        })
    }

    /// Cash at the start of the account's history, in cents.
    pub const fn starting_cash_cents(&self) -> i64 {
        self.starting_cash_cents
    }

    /// Current cash in cents, after fees.
    pub const fn cash_cents(&self) -> i64 {
        self.cash_cents
    }

    /// The position in this account.
    pub const fn position(&self) -> &Position {
        &self.position
    }

    /// Applies a fill to cash and position together. A refused fill leaves the account
    /// unchanged.
    pub fn apply_fill(
        &mut self,
        fill: &Fill,
        cents_per_tick_per_lot: i64,
    ) -> Result<(), DomainError> {
        let mut next = *self;
        next.position.apply_fill(fill, cents_per_tick_per_lot)?;
        let notional = notional_cents(fill.price, fill.quantity, cents_per_tick_per_lot)?;
        let after_trade = match fill.side {
            Side::Buy => self.cash_cents.checked_sub(notional),
            Side::Sell => self.cash_cents.checked_add(notional),
        }
        .ok_or(DomainError::Overflow)?;
        next.cash_cents = after_trade
            .checked_sub(fill.fee_cents)
            .ok_or(DomainError::Overflow)?;
        *self = next;
        Ok(())
    }

    /// Cash plus the market value of the open lots at `mark`, in cents.
    pub fn equity_cents(&self, mark: Price) -> Result<i64, DomainError> {
        self.cash_cents
            .checked_add(self.position.market_value_cents(mark)?)
            .ok_or(DomainError::Overflow)
    }

    /// Unrealized PnL of the open lots at `mark`, in cents.
    pub fn unrealized_pnl_cents(&self, mark: Price) -> Result<i64, DomainError> {
        self.position.unrealized_pnl_cents(mark)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::units::Quantity;

    const TICK_VALUE_CENTS: i64 = 100;

    fn fill(side: Side, price: i64, lots: i64, fee: i64) -> Fill {
        Fill::new(
            1,
            side,
            Price::from_ticks(price).unwrap(),
            Quantity::from_lots(lots).unwrap(),
            fee,
        )
        .unwrap()
    }

    #[test]
    fn new_account_holds_only_starting_cash() {
        let account = Account::new(1_000_000).unwrap();
        assert_eq!(account.cash_cents(), 1_000_000);
        assert_eq!(account.starting_cash_cents(), 1_000_000);
        assert_eq!(account.position().lots(), 0);
        assert_eq!(Account::new(-1), Err(DomainError::NegativeCash));
    }

    #[test]
    fn buy_pays_notional_and_fee_then_mark_reconciles_by_hand() {
        // Start 10000.00. Buy 2 at 1000 ticks (2000.00) with a 2.50 fee.
        // Cash: 1_000_000 - 200_000 - 250 = 799_750.
        // Mark 1010: market value 2 * 1010 * 100 = 202_000; equity 1_001_750.
        // Identity: start 1_000_000 + realized 0 - fees 250 + unrealized (202_000 - 200_000).
        let mut account = Account::new(1_000_000).unwrap();
        account
            .apply_fill(&fill(Side::Buy, 1000, 2, 250), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(account.cash_cents(), 799_750);
        let mark = Price::from_ticks(1010).unwrap();
        assert_eq!(account.equity_cents(mark), Ok(1_001_750));
        assert_eq!(account.unrealized_pnl_cents(mark), Ok(2_000));
    }

    #[test]
    fn partial_sell_realizes_by_hand_and_equity_is_unchanged_at_same_mark() {
        // Continue from the buy above. Sell 1 at 1010, no fee.
        // Proceeds 101_000; basis removed 100_000; realized 1_000.
        // Cash: 799_750 + 101_000 = 900_750. Remaining long 1 lot, basis 100_000.
        // Mark 1010: equity 900_750 + 101_000 = 1_001_750, unchanged by the trade itself.
        let mut account = Account::new(1_000_000).unwrap();
        account
            .apply_fill(&fill(Side::Buy, 1000, 2, 250), TICK_VALUE_CENTS)
            .unwrap();
        let mark = Price::from_ticks(1010).unwrap();
        let before = account.equity_cents(mark).unwrap();
        account
            .apply_fill(&fill(Side::Sell, 1010, 1, 0), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(account.cash_cents(), 900_750);
        assert_eq!(account.position().realized_pnl_cents(), 1_000);
        assert_eq!(account.position().open_cost_cents(), 100_000);
        assert_eq!(account.equity_cents(mark), Ok(before));
    }

    #[test]
    fn refused_fill_leaves_cash_and_position_unchanged() {
        let mut account = Account::new(1_000_000).unwrap();
        account
            .apply_fill(&fill(Side::Buy, 1000, 1, 0), TICK_VALUE_CENTS)
            .unwrap();
        let before = account;
        assert_eq!(
            account.apply_fill(&fill(Side::Sell, 1000, 1, 0), 50),
            Err(DomainError::TickValueMismatch)
        );
        assert_eq!(account, before);
    }

    #[test]
    fn notional_overflow_is_refused_without_touching_cash() {
        let mut account = Account::new(i64::MAX).unwrap();
        let before = account;
        // 2 ticks with tick value i64::MAX: notional overflows before cash is touched.
        assert_eq!(
            account.apply_fill(&fill(Side::Buy, 2, 1, 0), i64::MAX),
            Err(DomainError::Overflow)
        );
        assert_eq!(account, before);
    }
}
