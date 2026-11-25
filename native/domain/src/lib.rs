//! Pure domain primitives for the native trading kernels.
//!
//! This crate has no Python, I/O or broker dependencies. Discrete quantities use
//! checked integer arithmetic; overflow is reported as an error rather than wrapped.

pub mod account;
pub mod order;
pub mod position;
pub mod risk;
pub mod units;
mod wire;

pub use account::Account;
pub use order::{Fill, Order, OrderIntent, OrderState};
pub use position::Position;
pub use risk::DailyLossGuard;
pub use units::{notional_cents, Price, Quantity, Side};

/// Schema version of the native domain contract. Bump when a serialized field changes meaning.
///
/// Version 2 adds the exact cost basis and tick value to [`Position`] and changes how realized
/// PnL is rounded (the cost removed on each reduction is rounded to whole cents). Version 1 had
/// no serialized form.
pub const DOMAIN_SCHEMA_VERSION: u32 = 2;

/// Failure of a checked domain operation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DomainError {
    /// The result does not fit in the target integer type.
    Overflow,
    /// A quantity must be a strictly positive number of lot steps.
    NonPositiveQuantity,
    /// A price must be a strictly positive number of ticks.
    NonPositivePrice,
    /// A tick value (cents per tick per lot) must be strictly positive.
    NonPositiveTickValue,
    /// A commission must not be negative.
    NegativeFee,
    /// The requested order lifecycle move is not in the transition table.
    InvalidTransition {
        from: order::OrderState,
        to: order::OrderState,
    },
    /// A fill would exceed the order quantity.
    Overfill,
    /// A fill's side does not match the order's side.
    SideMismatch,
    /// A fill references a different order.
    OrderMismatch,
    /// Starting cash must not be negative.
    NegativeCash,
    /// A position's tick value is fixed by its first fill; a different value is refused.
    TickValueMismatch,
    /// A daily-loss limit must be a strictly positive number of cents.
    NonPositiveLossLimit,
    /// A new daily session must have a strictly greater identifier than the current one.
    SessionNotAdvanced,
    /// The daily-loss breach latch is set for this session; new exposure is refused.
    DailyLossBreached,
    /// A serialized value is malformed, has an unknown version, or is internally inconsistent.
    InvalidEncoding,
}

impl std::fmt::Display for DomainError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DomainError::Overflow => write!(f, "integer overflow in domain arithmetic"),
            DomainError::NonPositiveQuantity => {
                write!(f, "quantity must be a positive number of lot steps")
            }
            DomainError::NonPositivePrice => write!(f, "price must be a positive number of ticks"),
            DomainError::NonPositiveTickValue => {
                write!(f, "tick value must be a positive number of cents")
            }
            DomainError::NegativeFee => write!(f, "fee must not be negative"),
            DomainError::InvalidTransition { from, to } => {
                write!(f, "invalid order transition from {from:?} to {to:?}")
            }
            DomainError::Overfill => write!(f, "fill exceeds the order quantity"),
            DomainError::SideMismatch => write!(f, "fill side does not match the order side"),
            DomainError::OrderMismatch => write!(f, "fill references a different order"),
            DomainError::NegativeCash => write!(f, "starting cash must not be negative"),
            DomainError::TickValueMismatch => {
                write!(
                    f,
                    "tick value differs from the value fixed by the first fill"
                )
            }
            DomainError::NonPositiveLossLimit => {
                write!(f, "daily loss limit must be a positive number of cents")
            }
            DomainError::SessionNotAdvanced => {
                write!(f, "session identifier must strictly increase")
            }
            DomainError::DailyLossBreached => {
                write!(f, "daily loss limit is breached for this session")
            }
            DomainError::InvalidEncoding => write!(f, "malformed or inconsistent serialized value"),
        }
    }
}

impl std::error::Error for DomainError {}

/// Adds two quantities expressed in integer units (for example, price ticks or lots),
/// failing instead of wrapping on overflow.
pub fn checked_add_units(lhs: i64, rhs: i64) -> Result<i64, DomainError> {
    lhs.checked_add(rhs).ok_or(DomainError::Overflow)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schema_version_is_two() {
        assert_eq!(DOMAIN_SCHEMA_VERSION, 2);
    }

    #[test]
    fn adds_units_within_range() {
        assert_eq!(checked_add_units(2, 3), Ok(5));
        assert_eq!(checked_add_units(-4, 4), Ok(0));
    }

    #[test]
    fn overflow_is_an_error_not_a_wrap() {
        assert_eq!(checked_add_units(i64::MAX, 1), Err(DomainError::Overflow));
        assert_eq!(checked_add_units(i64::MIN, -1), Err(DomainError::Overflow));
    }

    #[test]
    fn error_message_names_the_failure() {
        assert!(DomainError::Overflow.to_string().contains("overflow"));
    }
}

/// Account loss limits in integer minor units (cents), with checked arithmetic.
///
/// These mirror `trading/account/limits.py` and share its hand-calculated expectations
/// (see `tests/unit/trading/test_semantic_oracle_limits_sizing.py`). Any change must update both.
pub mod limits {
    use super::DomainError;

    /// Session-start equity minus current equity, floored at zero.
    pub fn canonical_daily_loss(session_start: i64, equity: i64) -> Result<i64, DomainError> {
        Ok(session_start
            .checked_sub(equity)
            .ok_or(DomainError::Overflow)?
            .max(0))
    }

    /// Lowest permitted equity for the daily-loss rule: session start minus the limit.
    pub fn daily_floor(session_start: i64, daily_loss_limit: i64) -> Result<i64, DomainError> {
        session_start
            .checked_sub(daily_loss_limit)
            .ok_or(DomainError::Overflow)
    }

    /// Equity above the daily floor, floored at zero (zero once breached).
    pub fn remaining_daily_capacity(
        session_start: i64,
        equity: i64,
        daily_loss_limit: i64,
    ) -> Result<i64, DomainError> {
        let floor = daily_floor(session_start, daily_loss_limit)?;
        Ok(equity
            .checked_sub(floor)
            .ok_or(DomainError::Overflow)?
            .max(0))
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        // Hand calculations in cents: 10000.00 = 1_000_000 cents, 500.00 = 50_000 cents.
        #[test]
        fn daily_loss_when_losing() {
            // 1_000_000 - 970_000 = 30_000 (300.00)
            assert_eq!(canonical_daily_loss(1_000_000, 970_000), Ok(30_000));
        }

        #[test]
        fn daily_loss_zero_when_equity_rose() {
            // 1_000_000 - 1_020_000 = -20_000, floored at 0
            assert_eq!(canonical_daily_loss(1_000_000, 1_020_000), Ok(0));
        }

        #[test]
        fn floor_is_start_minus_limit() {
            // 1_000_000 - 50_000 = 950_000 (9500.00)
            assert_eq!(daily_floor(1_000_000, 50_000), Ok(950_000));
        }

        #[test]
        fn capacity_above_floor() {
            // floor 950_000; 970_000 - 950_000 = 20_000 (200.00)
            assert_eq!(
                remaining_daily_capacity(1_000_000, 970_000, 50_000),
                Ok(20_000)
            );
        }

        #[test]
        fn capacity_zero_once_breached() {
            // floor 950_000; 940_000 - 950_000 = -10_000, floored at 0
            assert_eq!(remaining_daily_capacity(1_000_000, 940_000, 50_000), Ok(0));
        }

        #[test]
        fn overflow_is_an_error() {
            assert_eq!(
                canonical_daily_loss(i64::MIN, i64::MAX),
                Err(DomainError::Overflow)
            );
            assert_eq!(daily_floor(i64::MIN, 1), Err(DomainError::Overflow));
        }
    }
}
