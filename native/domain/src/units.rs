//! Discrete exchange units: prices in integer ticks, quantities in integer lot steps.
//!
//! Constructors reject values that cannot be a tradable price or quantity. Notional
//! values are computed with checked multiplication and reported in integer cents.

use crate::DomainError;

/// A strictly positive price expressed in integer ticks.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Price {
    ticks: i64,
}

impl Price {
    /// Builds a price from ticks; zero and negative prices are rejected.
    pub fn from_ticks(ticks: i64) -> Result<Self, DomainError> {
        if ticks <= 0 {
            return Err(DomainError::NonPositivePrice);
        }
        Ok(Self { ticks })
    }

    /// The price in ticks.
    pub const fn ticks(self) -> i64 {
        self.ticks
    }
}

/// A strictly positive quantity expressed in integer lot steps.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Quantity {
    lots: i64,
}

impl Quantity {
    /// Builds a quantity from lot steps; zero and negative quantities are rejected.
    pub fn from_lots(lots: i64) -> Result<Self, DomainError> {
        if lots <= 0 {
            return Err(DomainError::NonPositiveQuantity);
        }
        Ok(Self { lots })
    }

    /// The quantity in lot steps (always positive).
    pub const fn lots(self) -> i64 {
        self.lots
    }
}

/// Direction of an order, fill or position change.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Buy,
    Sell,
}

impl Side {
    /// `+1` for buy, `-1` for sell.
    pub const fn sign(self) -> i64 {
        match self {
            Side::Buy => 1,
            Side::Sell => -1,
        }
    }
}

/// Notional value in cents: `price_ticks * lots * cents_per_tick_per_lot`, all checked.
///
/// `cents_per_tick_per_lot` is the instrument's tick value and must be strictly positive.
pub fn notional_cents(
    price: Price,
    quantity: Quantity,
    cents_per_tick_per_lot: i64,
) -> Result<i64, DomainError> {
    if cents_per_tick_per_lot <= 0 {
        return Err(DomainError::NonPositiveTickValue);
    }
    price
        .ticks
        .checked_mul(quantity.lots)
        .and_then(|ticks_lots| ticks_lots.checked_mul(cents_per_tick_per_lot))
        .ok_or(DomainError::Overflow)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn price_must_be_positive() {
        assert_eq!(Price::from_ticks(1000).map(Price::ticks), Ok(1000));
        assert_eq!(Price::from_ticks(0), Err(DomainError::NonPositivePrice));
        assert_eq!(Price::from_ticks(-5), Err(DomainError::NonPositivePrice));
    }

    #[test]
    fn quantity_must_be_positive() {
        assert_eq!(Quantity::from_lots(2).map(Quantity::lots), Ok(2));
        assert_eq!(
            Quantity::from_lots(0),
            Err(DomainError::NonPositiveQuantity)
        );
        assert_eq!(
            Quantity::from_lots(-1),
            Err(DomainError::NonPositiveQuantity)
        );
    }

    #[test]
    fn side_sign() {
        assert_eq!(Side::Buy.sign(), 1);
        assert_eq!(Side::Sell.sign(), -1);
    }

    #[test]
    fn notional_hand_calculation() {
        // 1000 ticks * 2 lots * 100 cents per tick-lot = 200_000 cents (2000.00)
        let price = Price::from_ticks(1000).unwrap();
        let qty = Quantity::from_lots(2).unwrap();
        assert_eq!(notional_cents(price, qty, 100), Ok(200_000));
    }

    #[test]
    fn notional_refuses_overflow() {
        let price = Price::from_ticks(i64::MAX).unwrap();
        let qty = Quantity::from_lots(2).unwrap();
        assert_eq!(notional_cents(price, qty, 1), Err(DomainError::Overflow));
        let small = Price::from_ticks(2).unwrap();
        // 2 * (i64::MAX / 2) = i64::MAX - 1 fits; one more cent per tick-lot does not.
        assert_eq!(
            notional_cents(small, Quantity::from_lots(1).unwrap(), i64::MAX / 2),
            Ok(i64::MAX - 1)
        );
        assert_eq!(
            notional_cents(small, Quantity::from_lots(1).unwrap(), i64::MAX / 2 + 1),
            Err(DomainError::Overflow)
        );
    }

    #[test]
    fn notional_requires_positive_tick_value() {
        let price = Price::from_ticks(1000).unwrap();
        let qty = Quantity::from_lots(1).unwrap();
        assert_eq!(
            notional_cents(price, qty, 0),
            Err(DomainError::NonPositiveTickValue)
        );
    }
}
