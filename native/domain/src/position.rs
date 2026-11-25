//! Signed position with average entry, realized PnL and fees.
//!
//! Units and rounding:
//! - The average entry is stored in ticks scaled by [`AVERAGE_ENTRY_SCALE`] (micro-ticks),
//!   so a 2-lot long at 1000 plus 1 lot at 1010 averages 1003.333333 ticks, not a truncated
//!   1003. Reductions keep the average exact; increases round it half away from zero at the
//!   scale. [`Position::average_entry_ticks`] rounds half away from zero to whole ticks.
//! - Realized PnL is computed from the scaled average and rounded half away from zero to
//!   whole cents on each reduction. Fees are accumulated separately and are not netted into
//!   realized PnL.
//! - A fill that crosses zero closes the whole position first (realizing PnL on the old
//!   average), then opens the remainder at the fill price.
//! - Every operation computes into a local copy and commits only on success, so a refused
//!   fill leaves the position unchanged.

use crate::order::Fill;
use crate::DomainError;

/// Scale of the stored average entry: micro-ticks per tick.
pub const AVERAGE_ENTRY_SCALE: i64 = 1_000_000;

/// Round `num / den` to the nearest integer, ties away from zero. `den` must be positive.
fn round_div(num: i128, den: i128) -> i128 {
    debug_assert!(den > 0);
    let quotient = num / den;
    let remainder = num % den;
    if remainder.abs() * 2 >= den {
        quotient + num.signum()
    } else {
        quotient
    }
}

/// A signed position in lots (positive long, negative short).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Position {
    lots: i64,
    average_entry_scaled: i64,
    realized_pnl_cents: i64,
    fees_cents: i64,
}

impl Position {
    /// A flat position with no PnL and no fees.
    pub const fn flat() -> Self {
        Self {
            lots: 0,
            average_entry_scaled: 0,
            realized_pnl_cents: 0,
            fees_cents: 0,
        }
    }

    /// Signed position in lots.
    pub const fn lots(&self) -> i64 {
        self.lots
    }

    /// Average entry in micro-ticks ([`AVERAGE_ENTRY_SCALE`] per tick); `None` when flat.
    pub const fn average_entry_scaled(&self) -> Option<i64> {
        if self.lots == 0 {
            None
        } else {
            Some(self.average_entry_scaled)
        }
    }

    /// Average entry rounded half away from zero to whole ticks; `None` when flat.
    pub fn average_entry_ticks(&self) -> Option<i64> {
        self.average_entry_scaled().map(|scaled| {
            // Dividing an i64 by the positive scale always yields an i64-sized quotient.
            i64::try_from(round_div(
                i128::from(scaled),
                i128::from(AVERAGE_ENTRY_SCALE),
            ))
            .expect("an i64 divided by a positive scale fits in i64")
        })
    }

    /// Gross realized trading PnL in cents, excluding fees.
    pub const fn realized_pnl_cents(&self) -> i64 {
        self.realized_pnl_cents
    }

    /// Total commissions in cents.
    pub const fn fees_cents(&self) -> i64 {
        self.fees_cents
    }

    /// Applies a fill. `cents_per_tick_per_lot` is the instrument tick value and must be
    /// strictly positive.
    pub fn apply_fill(
        &mut self,
        fill: &Fill,
        cents_per_tick_per_lot: i64,
    ) -> Result<(), DomainError> {
        if cents_per_tick_per_lot <= 0 {
            return Err(DomainError::NonPositiveTickValue);
        }
        let price_scaled = fill
            .price
            .ticks()
            .checked_mul(AVERAGE_ENTRY_SCALE)
            .ok_or(DomainError::Overflow)?;
        let fill_lots = fill
            .side
            .sign()
            .checked_mul(fill.quantity.lots())
            .ok_or(DomainError::Overflow)?;
        let fees_cents = self
            .fees_cents
            .checked_add(fill.fee_cents)
            .ok_or(DomainError::Overflow)?;

        let mut next = *self;
        next.fees_cents = fees_cents;

        if self.lots == 0 || self.lots.signum() == fill_lots.signum() {
            // Open or increase: weighted average of the existing and new lots.
            let old_abs = i128::from(self.lots.unsigned_abs());
            let add_abs = i128::from(fill_lots.unsigned_abs());
            let weighted = i128::from(self.average_entry_scaled)
                .checked_mul(old_abs)
                .and_then(|old| {
                    i128::from(price_scaled)
                        .checked_mul(add_abs)
                        .and_then(|new| old.checked_add(new))
                })
                .ok_or(DomainError::Overflow)?;
            let average = round_div(weighted, old_abs + add_abs);
            next.average_entry_scaled =
                i64::try_from(average).map_err(|_| DomainError::Overflow)?;
            next.lots = self
                .lots
                .checked_add(fill_lots)
                .ok_or(DomainError::Overflow)?;
        } else {
            // Reduce, and possibly flip through zero.
            let sign = i128::from(self.lots.signum());
            let position_abs = i128::from(self.lots.unsigned_abs());
            let fill_abs = i128::from(fill_lots.unsigned_abs());
            let closed = position_abs.min(fill_abs);
            // closed * sign * (exit - entry), in cents * AVERAGE_ENTRY_SCALE, then rounded.
            let gain_scaled = i128::from(price_scaled)
                .checked_sub(i128::from(self.average_entry_scaled))
                .and_then(|diff| diff.checked_mul(sign))
                .and_then(|diff| diff.checked_mul(closed))
                .and_then(|diff| diff.checked_mul(i128::from(cents_per_tick_per_lot)))
                .ok_or(DomainError::Overflow)?;
            let gain_cents = i64::try_from(round_div(gain_scaled, i128::from(AVERAGE_ENTRY_SCALE)))
                .map_err(|_| DomainError::Overflow)?;
            next.realized_pnl_cents = self
                .realized_pnl_cents
                .checked_add(gain_cents)
                .ok_or(DomainError::Overflow)?;

            let remaining_position = position_abs - closed;
            let remaining_fill = fill_abs - closed;
            if remaining_position > 0 {
                // Partial reduction: the average of the open lots is unchanged.
                let lots = i64::try_from(remaining_position).map_err(|_| DomainError::Overflow)?;
                next.lots = self.lots.signum() * lots;
            } else if remaining_fill > 0 {
                // Flip: the remainder opens a new position at the fill price.
                let lots = i64::try_from(remaining_fill).map_err(|_| DomainError::Overflow)?;
                next.lots = fill_lots.signum() * lots;
                next.average_entry_scaled = price_scaled;
            } else {
                next.lots = 0;
                next.average_entry_scaled = 0;
            }
        }

        *self = next;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::order::Fill;
    use crate::units::{Price, Quantity, Side};

    const TICK_VALUE_CENTS: i64 = 100; // 1 tick per lot is worth 1.00

    fn fill(side: Side, price: i64, lots: i64) -> Fill {
        Fill::new(
            1,
            side,
            Price::from_ticks(price).unwrap(),
            Quantity::from_lots(lots).unwrap(),
            0,
        )
        .unwrap()
    }

    #[test]
    fn flat_position_has_no_average_entry() {
        let position = Position::flat();
        assert_eq!(position.lots(), 0);
        assert_eq!(position.average_entry_ticks(), None);
        assert_eq!(position.realized_pnl_cents(), 0);
    }

    #[test]
    fn increase_averages_by_hand_and_realizes_nothing() {
        // Long 2 lots at 1000, then buy 1 lot at 1010.
        // Average = (2 * 1000 + 1 * 1010) / 3 = 1003.333... ticks.
        // Scaled: (2 * 1_000_000_000 + 1 * 1_010_000_000) / 3 = 1_003_333_333.33 -> 1_003_333_333.
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.average_entry_ticks(), Some(1000));
        position
            .apply_fill(&fill(Side::Buy, 1010, 1), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), 3);
        assert_eq!(position.average_entry_scaled(), Some(1_003_333_333));
        assert_eq!(position.average_entry_ticks(), Some(1003));
        assert_eq!(position.realized_pnl_cents(), 0);
    }

    #[test]
    fn reduce_realizes_pnl_by_hand_and_round_trip_nets_zero() {
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        position
            .apply_fill(&fill(Side::Buy, 1010, 1), TICK_VALUE_CENTS)
            .unwrap();

        // Sell 1 at 1010 against average 1003.333333: gain 6.666667 ticks = 666.6667 cents -> 667.
        position
            .apply_fill(&fill(Side::Sell, 1010, 1), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), 2);
        assert_eq!(position.average_entry_scaled(), Some(1_003_333_333));
        assert_eq!(position.realized_pnl_cents(), 667);

        // Sell 2 at 1000: loss 2 * 3.333333 ticks = 666.6666 cents -> -667. Net 0, flat.
        position
            .apply_fill(&fill(Side::Sell, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), 0);
        assert_eq!(position.average_entry_ticks(), None);
        assert_eq!(position.realized_pnl_cents(), 0);
    }

    #[test]
    fn short_reduce_profits_when_price_falls() {
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Sell, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), -2);
        // Buy 1 at 990: short gains 10 ticks = 1000 cents.
        position
            .apply_fill(&fill(Side::Buy, 990, 1), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), -1);
        assert_eq!(position.average_entry_ticks(), Some(1000));
        assert_eq!(position.realized_pnl_cents(), 1000);
    }

    #[test]
    fn crossing_zero_closes_then_opens_remainder_at_fill_price() {
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, 1000, 1), TICK_VALUE_CENTS)
            .unwrap();
        // Sell 3 at 1010: close 1 lot (+10 ticks = 1000 cents), open short 2 at 1010.
        position
            .apply_fill(&fill(Side::Sell, 1010, 3), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), -2);
        assert_eq!(position.average_entry_ticks(), Some(1010));
        assert_eq!(position.realized_pnl_cents(), 1000);
    }

    #[test]
    fn fees_accumulate_separately_from_realized_pnl() {
        let mut position = Position::flat();
        let paid = Fill::new(
            1,
            Side::Buy,
            Price::from_ticks(1000).unwrap(),
            Quantity::from_lots(1).unwrap(),
            250,
        )
        .unwrap();
        position.apply_fill(&paid, TICK_VALUE_CENTS).unwrap();
        position.apply_fill(&paid, TICK_VALUE_CENTS).unwrap();
        assert_eq!(position.fees_cents(), 500);
        assert_eq!(position.realized_pnl_cents(), 0);
    }

    #[test]
    fn nonpositive_tick_value_is_refused() {
        let mut position = Position::flat();
        assert_eq!(
            position.apply_fill(&fill(Side::Buy, 1000, 1), 0),
            Err(DomainError::NonPositiveTickValue)
        );
        assert_eq!(position, Position::flat());
    }

    #[test]
    fn overflowing_price_is_refused_and_position_unchanged() {
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, 1000, 1), TICK_VALUE_CENTS)
            .unwrap();
        let before = position;
        // i64::MAX ticks cannot be scaled into the average without overflow.
        assert_eq!(
            position.apply_fill(&fill(Side::Buy, i64::MAX, 1), TICK_VALUE_CENTS),
            Err(DomainError::Overflow)
        );
        assert_eq!(position, before);
    }

    #[test]
    fn overflowing_fees_are_refused_and_position_unchanged() {
        let mut position = Position::flat();
        let max_fee = Fill::new(
            1,
            Side::Buy,
            Price::from_ticks(1000).unwrap(),
            Quantity::from_lots(1).unwrap(),
            i64::MAX,
        )
        .unwrap();
        position.apply_fill(&max_fee, TICK_VALUE_CENTS).unwrap();
        let before = position;
        let one_cent_fee = Fill::new(
            1,
            Side::Buy,
            Price::from_ticks(1000).unwrap(),
            Quantity::from_lots(1).unwrap(),
            1,
        )
        .unwrap();
        assert_eq!(
            position.apply_fill(&one_cent_fee, TICK_VALUE_CENTS),
            Err(DomainError::Overflow)
        );
        assert_eq!(position, before);
    }

    #[test]
    fn overflowing_realized_pnl_is_refused() {
        // Long 1 at the largest scalable price, then sell at a much lower price with a huge
        // tick value: the gain exceeds i64 cents and must be refused, not wrapped.
        let high = i64::MAX / AVERAGE_ENTRY_SCALE;
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, high, 1), i64::MAX)
            .unwrap();
        let before = position;
        assert_eq!(
            position.apply_fill(&fill(Side::Sell, 1, 1), i64::MAX),
            Err(DomainError::Overflow)
        );
        assert_eq!(position, before);
    }
}
