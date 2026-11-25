//! Daily-loss guard: a session-start anchor, a floor and a breach latch.
//!
//! The floor and remaining capacity are computed by [`crate::limits`], which this module
//! reuses unchanged. The guard adds the session lifecycle:
//! - the anchor is the equity at the start of the session identified by `session_id`;
//! - a breach means equity is at or below the floor, i.e. remaining capacity is zero;
//! - the breach latch, once set, stays set for the rest of the session, even if equity
//!   recovers above the floor;
//! - only [`DailyLossGuard::start_session`] clears the latch. It requires a strictly greater
//!   session identifier and re-anchors to the new session's starting equity.
//!
//! Every method that can fail leaves the guard unchanged on failure.

use crate::limits;
use crate::DomainError;

/// Daily-loss floor with a session-start anchor and a breach latch.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DailyLossGuard {
    session_id: u64,
    session_start_equity_cents: i64,
    daily_loss_limit_cents: i64,
    floor_cents: i64,
    breached: bool,
}

impl DailyLossGuard {
    /// Starts a session anchored at `session_start_equity_cents`. The limit must be strictly
    /// positive, and the floor must be representable.
    pub fn new(
        session_id: u64,
        session_start_equity_cents: i64,
        daily_loss_limit_cents: i64,
    ) -> Result<Self, DomainError> {
        if daily_loss_limit_cents <= 0 {
            return Err(DomainError::NonPositiveLossLimit);
        }
        let floor_cents = limits::daily_floor(session_start_equity_cents, daily_loss_limit_cents)?;
        Ok(Self {
            session_id,
            session_start_equity_cents,
            daily_loss_limit_cents,
            floor_cents,
            breached: false,
        })
    }

    /// Identifier of the current session.
    pub const fn session_id(&self) -> u64 {
        self.session_id
    }

    /// Lowest permitted equity for the current session, in cents.
    pub const fn floor_cents(&self) -> i64 {
        self.floor_cents
    }

    /// Whether the breach latch is set for the current session.
    pub const fn is_breached(&self) -> bool {
        self.breached
    }

    /// Records an equity observation and returns the remaining capacity above the floor.
    ///
    /// Equity at or below the floor sets the latch before any arithmetic can fail, so an
    /// observation that cannot be represented as capacity still cannot clear a breach.
    pub fn observe_equity(&mut self, equity_cents: i64) -> Result<i64, DomainError> {
        if equity_cents <= self.floor_cents {
            self.breached = true;
        }
        limits::remaining_daily_capacity(
            self.session_start_equity_cents,
            equity_cents,
            self.daily_loss_limit_cents,
        )
    }

    /// Refuses new exposure while the breach latch is set.
    pub fn admit_entry(&self) -> Result<(), DomainError> {
        if self.breached {
            Err(DomainError::DailyLossBreached)
        } else {
            Ok(())
        }
    }

    /// Starts a new session with a strictly greater identifier, clearing the latch and
    /// re-anchoring to `session_start_equity_cents`.
    pub fn start_session(
        &mut self,
        session_id: u64,
        session_start_equity_cents: i64,
    ) -> Result<(), DomainError> {
        if session_id <= self.session_id {
            return Err(DomainError::SessionNotAdvanced);
        }
        *self = Self::new(
            session_id,
            session_start_equity_cents,
            self.daily_loss_limit_cents,
        )?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Hand calculations in cents: start 10000.00 = 1_000_000, limit 500.00 = 50_000,
    // so the floor is 9500.00 = 950_000.

    #[test]
    fn floor_is_start_minus_limit() {
        let guard = DailyLossGuard::new(1, 1_000_000, 50_000).unwrap();
        assert_eq!(guard.floor_cents(), 950_000);
        assert!(!guard.is_breached());
        assert_eq!(guard.admit_entry(), Ok(()));
    }

    #[test]
    fn capacity_is_reported_above_the_floor() {
        let mut guard = DailyLossGuard::new(1, 1_000_000, 50_000).unwrap();
        // 9700.00 - 9500.00 = 200.00
        assert_eq!(guard.observe_equity(970_000), Ok(20_000));
        assert!(!guard.is_breached());
    }

    #[test]
    fn breach_latches_and_survives_recovery_within_the_session() {
        let mut guard = DailyLossGuard::new(1, 1_000_000, 50_000).unwrap();
        // 9499.99 is below the floor: capacity 0, latch set.
        assert_eq!(guard.observe_equity(949_999), Ok(0));
        assert!(guard.is_breached());
        assert_eq!(guard.admit_entry(), Err(DomainError::DailyLossBreached));
        // Equity recovers to 10000.00: the latch is not cleared inside the session.
        assert_eq!(guard.observe_equity(1_000_000), Ok(50_000));
        assert!(guard.is_breached());
        assert_eq!(guard.admit_entry(), Err(DomainError::DailyLossBreached));
    }

    #[test]
    fn equity_exactly_on_the_floor_is_a_breach() {
        let mut guard = DailyLossGuard::new(1, 1_000_000, 50_000).unwrap();
        assert_eq!(guard.observe_equity(950_000), Ok(0));
        assert!(guard.is_breached());
    }

    #[test]
    fn unrepresentable_equity_below_the_floor_still_latches() {
        // Floor i64::MAX - 1; equity - floor = i64::MIN - (i64::MAX - 1) overflows. The
        // observation is refused, but equity is below the floor, so the latch is set first.
        let mut guard = DailyLossGuard::new(1, i64::MAX, 1).unwrap();
        assert_eq!(guard.observe_equity(i64::MIN), Err(DomainError::Overflow));
        assert!(guard.is_breached());
    }

    #[test]
    fn new_session_clears_the_latch_and_reanchors() {
        let mut guard = DailyLossGuard::new(1, 1_000_000, 50_000).unwrap();
        guard.observe_equity(900_000).unwrap();
        assert!(guard.is_breached());
        guard.start_session(2, 900_000).unwrap();
        // New floor: 900_000 - 50_000 = 850_000; 900_000 is 50_000 above it.
        assert_eq!(guard.session_id(), 2);
        assert_eq!(guard.floor_cents(), 850_000);
        assert!(!guard.is_breached());
        assert_eq!(guard.admit_entry(), Ok(()));
    }

    #[test]
    fn session_identifier_must_strictly_increase() {
        let mut guard = DailyLossGuard::new(5, 1_000_000, 50_000).unwrap();
        guard.observe_equity(900_000).unwrap();
        let before = guard;
        assert_eq!(
            guard.start_session(5, 1_000_000),
            Err(DomainError::SessionNotAdvanced)
        );
        assert_eq!(
            guard.start_session(4, 1_000_000),
            Err(DomainError::SessionNotAdvanced)
        );
        // A same-session reset cannot be used to clear a breach.
        assert!(guard.is_breached());
        assert_eq!(guard, before);
    }

    #[test]
    fn failed_session_start_leaves_the_guard_unchanged() {
        let mut guard = DailyLossGuard::new(1, 1_000_000, 50_000).unwrap();
        guard.observe_equity(900_000).unwrap();
        let before = guard;
        // The new floor i64::MIN - 50_000 overflows.
        assert_eq!(guard.start_session(2, i64::MIN), Err(DomainError::Overflow));
        assert_eq!(guard, before);
    }

    #[test]
    fn nonpositive_limit_is_refused() {
        assert_eq!(
            DailyLossGuard::new(1, 1_000_000, 0),
            Err(DomainError::NonPositiveLossLimit)
        );
        assert_eq!(
            DailyLossGuard::new(1, 1_000_000, -1),
            Err(DomainError::NonPositiveLossLimit)
        );
    }
}
