//! Pure domain primitives for the native trading kernels.
//!
//! This crate has no Python, I/O or broker dependencies. Discrete quantities use
//! checked integer arithmetic; overflow is reported as an error rather than wrapped.

/// Schema version of the native domain contract. Bump when a serialized field changes meaning.
pub const DOMAIN_SCHEMA_VERSION: u32 = 1;

/// Failure of a checked domain operation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DomainError {
    /// The result does not fit in the target integer type.
    Overflow,
}

impl std::fmt::Display for DomainError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DomainError::Overflow => write!(f, "integer overflow in domain arithmetic"),
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
    fn schema_version_is_one() {
        assert_eq!(DOMAIN_SCHEMA_VERSION, 1);
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
