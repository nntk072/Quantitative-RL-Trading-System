//! Fixed-seed property checks for the SEMANTIC-ORACLE daily-loss and price/lot domain rules.
//!
//! The expected values are computed here in `i128` arithmetic, not with the production
//! functions, so the check is independent of the implementation. The seed is fixed, so a
//! failure reproduces on every run. The same rules are pinned on the Python side by
//! `native/python/tests/test_semantic_oracle_parity.py` and by the fixture file
//! `planning/native_modernization/semantic_oracle/fixtures/semantic_oracle_fixtures.v2.json`.

use proptest::prelude::*;
use proptest::test_runner::{Config, RngAlgorithm, TestRng, TestRunner};

use qrl_domain::limits::{canonical_daily_loss, daily_floor, remaining_daily_capacity};
use qrl_domain::{DomainError, Price, Quantity};

/// Fixed seed (32 bytes). Changing it changes the generated cases, so it is part of the evidence.
const SEED: [u8; 32] = *b"semantic-oracle-domain-seed-0001";
const CASES: u32 = 512;

fn fixed_runner() -> TestRunner {
    let rng = TestRng::from_seed(RngAlgorithm::ChaCha, &SEED);
    TestRunner::new_with_rng(
        Config {
            cases: CASES,
            failure_persistence: None,
            ..Config::default()
        },
        rng,
    )
}

/// The i64 result of an exact i128 expression, or `None` when it does not fit.
fn exact_i64(value: i128) -> Option<i64> {
    i64::try_from(value).ok()
}

#[test]
fn daily_loss_is_the_clamped_difference_or_overflows() {
    fixed_runner()
        .run(&(any::<i64>(), any::<i64>()), |(start, equity)| {
            let diff = i128::from(start) - i128::from(equity);
            match (canonical_daily_loss(start, equity), exact_i64(diff)) {
                (Ok(value), Some(_)) => {
                    prop_assert_eq!(i128::from(value), diff.max(0));
                }
                (Err(error), None) => {
                    prop_assert_eq!(error, DomainError::Overflow);
                }
                (result, fits) => {
                    prop_assert!(
                        false,
                        "loss {result:?} disagrees with exact diff {diff} (fits={fits:?})"
                    );
                }
            }
            Ok(())
        })
        .unwrap();
}

#[test]
fn daily_floor_is_start_minus_limit_or_overflows() {
    fixed_runner()
        .run(&(any::<i64>(), any::<i64>()), |(start, limit)| {
            let exact = i128::from(start) - i128::from(limit);
            match (daily_floor(start, limit), exact_i64(exact)) {
                (Ok(floor), Some(_)) => prop_assert_eq!(i128::from(floor), exact),
                (Err(error), None) => prop_assert_eq!(error, DomainError::Overflow),
                (result, fits) => {
                    prop_assert!(false, "floor {result:?} vs exact {exact} (fits={fits:?})")
                }
            }
            Ok(())
        })
        .unwrap();
}

#[test]
fn remaining_capacity_is_zero_at_and_below_the_floor() {
    // Bounded magnitudes keep every intermediate value inside i64, so the boundary is exact.
    fixed_runner()
        .run(
            &(
                -1_000_000_000i64..=1_000_000_000,
                0i64..=500_000_000,
                -2_000_000_000i64..=2_000_000_000,
            ),
            |(start, limit, equity)| {
                let floor = i128::from(start) - i128::from(limit);
                let remaining = remaining_daily_capacity(start, equity, limit)
                    .map_err(|e| TestCaseError::fail(format!("unexpected error {e:?}")))?;
                let expected = (i128::from(equity) - floor).max(0);
                prop_assert_eq!(i128::from(remaining), expected);
                if i128::from(equity) <= floor {
                    prop_assert_eq!(remaining, 0);
                }
                Ok(())
            },
        )
        .unwrap();
}

#[test]
fn price_is_accepted_exactly_when_strictly_positive() {
    fixed_runner()
        .run(&any::<i64>(), |ticks| {
            prop_assert_eq!(Price::from_ticks(ticks).is_ok(), ticks > 0);
            Ok(())
        })
        .unwrap();
}

#[test]
fn quantity_is_accepted_exactly_when_strictly_positive() {
    fixed_runner()
        .run(&any::<i64>(), |lots| {
            prop_assert_eq!(Quantity::from_lots(lots).is_ok(), lots > 0);
            Ok(())
        })
        .unwrap();
}

#[test]
fn equity_exactly_at_the_floor_is_not_a_breach() {
    // Strict-below rule: equity == floor gives zero capacity, and the floor is the boundary.
    fixed_runner()
        .run(
            &(-1_000_000_000i64..=1_000_000_000, 0i64..=500_000_000),
            |(start, limit)| {
                let floor =
                    daily_floor(start, limit).map_err(|e| TestCaseError::fail(format!("{e:?}")))?;
                prop_assert_eq!(remaining_daily_capacity(start, floor, limit).unwrap(), 0);
                prop_assert_eq!(
                    remaining_daily_capacity(start, floor + 1, limit).unwrap(),
                    1
                );
                Ok(())
            },
        )
        .unwrap();
}
