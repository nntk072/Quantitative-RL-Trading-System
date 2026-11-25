//! Signed position with average entry, cost basis, realized PnL and fees.
//!
//! Units and rounding:
//! - The average entry is stored in ticks scaled by [`AVERAGE_ENTRY_SCALE`] (micro-ticks),
//!   so a 2-lot long at 1000 plus 1 lot at 1010 averages 1003.333333 ticks, not a truncated
//!   1003. Reductions keep the average exact; increases round it half away from zero at the
//!   scale. [`Position::average_entry_ticks`] rounds half away from zero to whole ticks.
//! - The open cost basis is kept exactly in whole cents (`price * lots * tick value`, signed
//!   by side). A reduction removes its share of that basis, rounded half away from zero to
//!   whole cents, and realizes `exit value - removed basis`. The basis is therefore the single
//!   source for realized PnL, which keeps cash, PnL and open exposure reconciled exactly.
//! - Fees are accumulated separately and are not netted into realized PnL.
//! - A fill that crosses zero closes the whole position first (realizing PnL on the old
//!   basis), then opens the remainder at the fill price.
//! - The tick value is fixed by the first fill; a later fill with a different value is refused.
//! - Every operation computes into a local copy and commits only on success, so a refused
//!   fill leaves the position unchanged.

use crate::order::Fill;
use crate::units::{notional_cents, Price, Quantity};
use crate::wire;
use crate::DomainError;

/// Scale of the stored average entry: micro-ticks per tick.
pub const AVERAGE_ENTRY_SCALE: i64 = 1_000_000;

/// Serialized length of a [`Position`] frame in bytes.
pub const POSITION_WIRE_LEN: usize = 49;

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
    open_cost_cents: i64,
    realized_pnl_cents: i64,
    fees_cents: i64,
    tick_value_cents: i64,
}

impl Position {
    /// A flat position with no PnL, no fees and no tick value yet.
    pub const fn flat() -> Self {
        Self {
            lots: 0,
            average_entry_scaled: 0,
            open_cost_cents: 0,
            realized_pnl_cents: 0,
            fees_cents: 0,
            tick_value_cents: 0,
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

    /// Signed cost basis of the open lots in cents: positive when long, negative when short,
    /// zero when flat.
    pub const fn open_cost_cents(&self) -> i64 {
        self.open_cost_cents
    }

    /// Cents per tick per lot fixed by the first fill; zero before any fill.
    pub const fn tick_value_cents(&self) -> i64 {
        self.tick_value_cents
    }

    /// Gross realized trading PnL in cents, excluding fees.
    pub const fn realized_pnl_cents(&self) -> i64 {
        self.realized_pnl_cents
    }

    /// Total commissions in cents.
    pub const fn fees_cents(&self) -> i64 {
        self.fees_cents
    }

    /// Signed market value of the open lots at `mark`, in cents; zero when flat.
    pub fn market_value_cents(&self, mark: Price) -> Result<i64, DomainError> {
        if self.lots == 0 {
            return Ok(0);
        }
        let magnitude =
            i64::try_from(self.lots.unsigned_abs()).map_err(|_| DomainError::Overflow)?;
        let value = notional_cents(mark, Quantity::from_lots(magnitude)?, self.tick_value_cents)?;
        if self.lots > 0 {
            Ok(value)
        } else {
            Ok(-value)
        }
    }

    /// Market value of the open lots at `mark` minus their cost basis, in cents.
    pub fn unrealized_pnl_cents(&self, mark: Price) -> Result<i64, DomainError> {
        self.market_value_cents(mark)?
            .checked_sub(self.open_cost_cents)
            .ok_or(DomainError::Overflow)
    }

    /// Applies a fill. `cents_per_tick_per_lot` is the instrument tick value and must be
    /// strictly positive and equal to the value used by earlier fills.
    pub fn apply_fill(
        &mut self,
        fill: &Fill,
        cents_per_tick_per_lot: i64,
    ) -> Result<(), DomainError> {
        let tick_value = cents_per_tick_per_lot;
        if tick_value <= 0 {
            return Err(DomainError::NonPositiveTickValue);
        }
        if self.tick_value_cents != 0 && self.tick_value_cents != tick_value {
            return Err(DomainError::TickValueMismatch);
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
        // Whole-fill value in cents, signed by side: the cost basis change if the fill opens.
        let traded = notional_cents(fill.price, fill.quantity, tick_value)?;
        let signed_traded = fill
            .side
            .sign()
            .checked_mul(traded)
            .ok_or(DomainError::Overflow)?;

        let mut next = *self;
        next.fees_cents = fees_cents;
        next.tick_value_cents = tick_value;

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
            next.open_cost_cents = self
                .open_cost_cents
                .checked_add(signed_traded)
                .ok_or(DomainError::Overflow)?;
        } else {
            // Reduce, and possibly flip through zero.
            let position_abs = i128::from(self.lots.unsigned_abs());
            let fill_abs = i128::from(fill_lots.unsigned_abs());
            let closed = position_abs.min(fill_abs);
            let remaining_position = position_abs - closed;
            let remaining_fill = fill_abs - closed;

            // Basis removed with the closed lots, rounded to whole cents; the open lots keep
            // the rest, so open_cost + realized always equals cumulative cash flow.
            let removed = i64::try_from(round_div(
                i128::from(self.open_cost_cents) * closed,
                position_abs,
            ))
            .map_err(|_| DomainError::Overflow)?;
            let closed_lots = i64::try_from(closed).map_err(|_| DomainError::Overflow)?;
            let exit = notional_cents(fill.price, Quantity::from_lots(closed_lots)?, tick_value)?;
            // A closing sell gains exit - basis; a closing buy (short) gains basis - exit.
            let gain = i128::from(-fill.side.sign()) * i128::from(exit) - i128::from(removed);
            let gain_cents = i64::try_from(gain).map_err(|_| DomainError::Overflow)?;
            next.realized_pnl_cents = self
                .realized_pnl_cents
                .checked_add(gain_cents)
                .ok_or(DomainError::Overflow)?;
            let open_after = self
                .open_cost_cents
                .checked_sub(removed)
                .ok_or(DomainError::Overflow)?;

            if remaining_position > 0 {
                // Partial reduction: the average of the open lots is unchanged.
                let lots = i64::try_from(remaining_position).map_err(|_| DomainError::Overflow)?;
                next.lots = self.lots.signum() * lots;
                next.open_cost_cents = open_after;
            } else if remaining_fill > 0 {
                // Flip: the remainder opens a new position at the fill price.
                let lots = i64::try_from(remaining_fill).map_err(|_| DomainError::Overflow)?;
                let open_value =
                    notional_cents(fill.price, Quantity::from_lots(lots)?, tick_value)?;
                next.lots = fill_lots.signum() * lots;
                next.average_entry_scaled = price_scaled;
                next.open_cost_cents = fill
                    .side
                    .sign()
                    .checked_mul(open_value)
                    .ok_or(DomainError::Overflow)?;
            } else {
                next.lots = 0;
                next.average_entry_scaled = 0;
                next.open_cost_cents = 0;
            }
        }

        *self = next;
        Ok(())
    }

    /// Canonical fixed-width frame: version, then little-endian fields in declaration order.
    pub fn to_wire(&self) -> [u8; POSITION_WIRE_LEN] {
        let mut out = [0u8; POSITION_WIRE_LEN];
        out[0] = wire::VERSION;
        out[1..9].copy_from_slice(&self.lots.to_le_bytes());
        out[9..17].copy_from_slice(&self.average_entry_scaled.to_le_bytes());
        out[17..25].copy_from_slice(&self.open_cost_cents.to_le_bytes());
        out[25..33].copy_from_slice(&self.realized_pnl_cents.to_le_bytes());
        out[33..41].copy_from_slice(&self.fees_cents.to_le_bytes());
        out[41..49].copy_from_slice(&self.tick_value_cents.to_le_bytes());
        out
    }

    /// Decodes a frame written by [`Position::to_wire`].
    ///
    /// Refuses a wrong length or version, and any state [`Position::apply_fill`] could not
    /// have produced (for example a flat position with a nonzero cost basis).
    pub fn from_wire(bytes: &[u8]) -> Result<Self, DomainError> {
        wire::check_frame(bytes, POSITION_WIRE_LEN)?;
        let position = Self {
            lots: wire::read_i64(bytes, 1)?,
            average_entry_scaled: wire::read_i64(bytes, 9)?,
            open_cost_cents: wire::read_i64(bytes, 17)?,
            realized_pnl_cents: wire::read_i64(bytes, 25)?,
            fees_cents: wire::read_i64(bytes, 33)?,
            tick_value_cents: wire::read_i64(bytes, 41)?,
        };
        if position.is_reachable() {
            Ok(position)
        } else {
            Err(DomainError::InvalidEncoding)
        }
    }

    /// Whether `apply_fill` could have produced this state.
    fn is_reachable(&self) -> bool {
        if self.tick_value_cents < 0 {
            return false;
        }
        if self.tick_value_cents == 0 {
            // Never filled: nothing else may be set.
            return *self == Self::flat();
        }
        if self.fees_cents < 0 {
            return false;
        }
        if self.lots == 0 {
            return self.average_entry_scaled == 0 && self.open_cost_cents == 0;
        }
        self.average_entry_scaled > 0
            && self.open_cost_cents != 0
            && self.open_cost_cents.signum() == self.lots.signum()
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
        assert_eq!(position.open_cost_cents(), 0);
    }

    #[test]
    fn increase_averages_by_hand_and_realizes_nothing() {
        // Long 2 lots at 1000, then buy 1 lot at 1010.
        // Average = (2 * 1000 + 1 * 1010) / 3 = 1003.333... ticks.
        // Scaled: (2 * 1_000_000_000 + 1 * 1_010_000_000) / 3 = 1_003_333_333.33 -> 1_003_333_333.
        // Cost basis: 2 * 1000 * 100 + 1 * 1010 * 100 = 301_000 cents.
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
        assert_eq!(position.open_cost_cents(), 301_000);
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
        // Basis removed: 301_000 / 3 = 100_333.33 -> 100_333; exit 101_000; gain 667.
        position
            .apply_fill(&fill(Side::Sell, 1010, 1), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), 2);
        assert_eq!(position.average_entry_scaled(), Some(1_003_333_333));
        assert_eq!(position.realized_pnl_cents(), 667);
        assert_eq!(position.open_cost_cents(), 200_667);

        // Sell 2 at 1000: loss 2 * 3.333333 ticks = 666.6666 cents -> -667. Net 0, flat.
        position
            .apply_fill(&fill(Side::Sell, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), 0);
        assert_eq!(position.average_entry_ticks(), None);
        assert_eq!(position.realized_pnl_cents(), 0);
        assert_eq!(position.open_cost_cents(), 0);
    }

    #[test]
    fn short_reduce_profits_when_price_falls() {
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Sell, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), -2);
        assert_eq!(position.open_cost_cents(), -200_000);
        // Buy 1 at 990: short gains 10 ticks = 1000 cents.
        position
            .apply_fill(&fill(Side::Buy, 990, 1), TICK_VALUE_CENTS)
            .unwrap();
        assert_eq!(position.lots(), -1);
        assert_eq!(position.average_entry_ticks(), Some(1000));
        assert_eq!(position.open_cost_cents(), -100_000);
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
        assert_eq!(position.open_cost_cents(), -202_000);
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
    fn changed_tick_value_is_refused_and_position_unchanged() {
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, 1000, 1), TICK_VALUE_CENTS)
            .unwrap();
        let before = position;
        assert_eq!(
            position.apply_fill(&fill(Side::Buy, 1000, 1), 50),
            Err(DomainError::TickValueMismatch)
        );
        assert_eq!(position, before);
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
    fn overflowing_notional_is_refused_and_position_unchanged() {
        // 1 lot at 2 ticks with a tick value of i64::MAX: the cents value exceeds i64.
        let mut position = Position::flat();
        let before = position;
        assert_eq!(
            position.apply_fill(&fill(Side::Buy, 2, 1), i64::MAX),
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
        // Tick value V = i64::MAX / 2. A short sold at 2 and covered at 1 realizes exactly V.
        // Two such trips realize 2V = i64::MAX - 1; a third would exceed i64 and must be refused.
        let v = i64::MAX / 2;
        let mut position = Position::flat();
        for _ in 0..2 {
            position.apply_fill(&fill(Side::Sell, 2, 1), v).unwrap();
            position.apply_fill(&fill(Side::Buy, 1, 1), v).unwrap();
        }
        assert_eq!(position.realized_pnl_cents(), 2 * v);
        assert_eq!(position.lots(), 0);

        position.apply_fill(&fill(Side::Sell, 2, 1), v).unwrap();
        let before = position;
        assert_eq!(
            position.apply_fill(&fill(Side::Buy, 1, 1), v),
            Err(DomainError::Overflow)
        );
        assert_eq!(position, before);
    }

    #[test]
    fn unrealized_pnl_is_market_value_minus_basis() {
        // Long 3 with basis 301_000 cents; mark 1010 gives 303_000 cents: unrealized 2_000.
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        position
            .apply_fill(&fill(Side::Buy, 1010, 1), TICK_VALUE_CENTS)
            .unwrap();
        let mark = Price::from_ticks(1010).unwrap();
        assert_eq!(position.market_value_cents(mark), Ok(303_000));
        assert_eq!(position.unrealized_pnl_cents(mark), Ok(2_000));
        assert_eq!(Position::flat().market_value_cents(mark), Ok(0));
    }

    #[test]
    fn wire_round_trip_and_refusal_of_inconsistent_frames() {
        let mut position = Position::flat();
        position
            .apply_fill(&fill(Side::Buy, 1000, 2), TICK_VALUE_CENTS)
            .unwrap();
        position
            .apply_fill(&fill(Side::Sell, 1010, 1), TICK_VALUE_CENTS)
            .unwrap();
        let frame = position.to_wire();
        assert_eq!(Position::from_wire(&frame), Ok(position));

        // Wrong length and wrong version.
        assert_eq!(
            Position::from_wire(&frame[..POSITION_WIRE_LEN - 1]),
            Err(DomainError::InvalidEncoding)
        );
        let mut bad_version = frame;
        bad_version[0] = 0;
        assert_eq!(
            Position::from_wire(&bad_version),
            Err(DomainError::InvalidEncoding)
        );

        // A flat position may not carry a cost basis.
        let mut flat_with_basis = Position::flat().to_wire();
        flat_with_basis[17] = 1;
        flat_with_basis[41] = 100;
        assert_eq!(
            Position::from_wire(&flat_with_basis),
            Err(DomainError::InvalidEncoding)
        );

        // A long position with a short-signed basis is refused.
        let mut sign_flip = frame;
        sign_flip[17..25].copy_from_slice(&(-1i64).to_le_bytes());
        assert_eq!(
            Position::from_wire(&sign_flip),
            Err(DomainError::InvalidEncoding)
        );
    }
}
