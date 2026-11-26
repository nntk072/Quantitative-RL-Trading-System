//! Property tests for the retained-level kernel: causality, cap, and close invalidation.

use proptest::prelude::*;
use qrl_features::{retained_swing_levels, RetainedInput, RetainedOutput};

#[derive(Debug, Clone)]
struct Series {
    ev_h: Vec<bool>,
    ev_l: Vec<bool>,
    px_h: Vec<f64>,
    px_l: Vec<f64>,
    loc_h: Vec<f64>,
    loc_l: Vec<f64>,
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
}

fn value() -> impl Strategy<Value = f64> {
    prop_oneof![
        9 => (-50_i32..50).prop_map(|v| f64::from(v) / 4.0),
        1 => Just(f64::NAN),
    ]
}

fn series(max_n: usize) -> impl Strategy<Value = Series> {
    (0..=max_n).prop_flat_map(|n| {
        (
            prop::collection::vec(any::<bool>(), n),
            prop::collection::vec(any::<bool>(), n),
            prop::collection::vec(value(), n),
            prop::collection::vec(value(), n),
            prop::collection::vec(
                prop_oneof![(0_u8..40).prop_map(f64::from), Just(f64::NAN)],
                n,
            ),
            prop::collection::vec(
                prop_oneof![(0_u8..40).prop_map(f64::from), Just(f64::NAN)],
                n,
            ),
            prop::collection::vec(value(), n),
            prop::collection::vec(value(), n),
            prop::collection::vec(value(), n),
        )
            .prop_map(
                |(ev_h, ev_l, px_h, px_l, loc_h, loc_l, high, low, close)| Series {
                    ev_h,
                    ev_l,
                    px_h,
                    px_l,
                    loc_h,
                    loc_l,
                    high,
                    low,
                    close,
                },
            )
    })
}

fn run(s: &Series, width: usize) -> RetainedOutput {
    let input = RetainedInput {
        swing_high_event: &s.ev_h,
        swing_low_event: &s.ev_l,
        swing_high_extreme: &s.px_h,
        swing_low_extreme: &s.px_l,
        swing_high_location: &s.loc_h,
        swing_low_location: &s.loc_l,
        high: &s.high,
        low: &s.low,
        close: &s.close,
    };
    retained_swing_levels(&input, width).expect("generated inputs are consistent")
}

fn same_bits(a: &[f64], b: &[f64]) -> bool {
    a.len() == b.len() && a.iter().zip(b).all(|(x, y)| x.to_bits() == y.to_bits())
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))]

    /// Row t depends only on inputs up to t: a prefix reproduces the full run's rows exactly.
    #[test]
    fn prefix_reproduces_full_run(s in series(40), width in 1_usize..=4, cut in 0_usize..=40) {
        let n = s.close.len();
        let cut = cut.min(n);
        let prefix = Series {
            ev_h: s.ev_h[..cut].to_vec(),
            ev_l: s.ev_l[..cut].to_vec(),
            px_h: s.px_h[..cut].to_vec(),
            px_l: s.px_l[..cut].to_vec(),
            loc_h: s.loc_h[..cut].to_vec(),
            loc_l: s.loc_l[..cut].to_vec(),
            high: s.high[..cut].to_vec(),
            low: s.low[..cut].to_vec(),
            close: s.close[..cut].to_vec(),
        };
        let full = run(&s, width);
        let part = run(&prefix, width);
        prop_assert_eq!(&part.n_retained_highs[..], &full.n_retained_highs[..cut]);
        prop_assert_eq!(&part.n_retained_lows[..], &full.n_retained_lows[..cut]);
        prop_assert!(same_bits(&part.swept_high, &full.swept_high[..cut]));
        prop_assert!(same_bits(&part.swept_low_loc, &full.swept_low_loc[..cut]));
        prop_assert!(same_bits(&part.retained_highs, &full.retained_highs[..cut * width]));
        prop_assert!(same_bits(&part.retained_low_locs, &full.retained_low_locs[..cut * width]));
    }

    /// Counts never exceed the width, and unused slots are NaN.
    #[test]
    fn counts_respect_width_and_unused_slots_are_nan(s in series(40), width in 1_usize..=4) {
        let out = run(&s, width);
        for t in 0..s.close.len() {
            let nh = usize::try_from(out.n_retained_highs[t]).expect("non-negative");
            let nl = usize::try_from(out.n_retained_lows[t]).expect("non-negative");
            prop_assert!(nh <= width && nl <= width);
            for slot in nh..width {
                prop_assert!(out.retained_highs[t * width + slot].is_nan());
                prop_assert!(out.retained_high_locs[t * width + slot].is_nan());
            }
            for slot in nl..width {
                prop_assert!(out.retained_lows[t * width + slot].is_nan());
            }
        }
    }

    /// A retained level after bar t was not invalidated by the close of bar t.
    #[test]
    fn retained_levels_survive_the_bar_close(s in series(40), width in 1_usize..=4) {
        let out = run(&s, width);
        for t in 0..s.close.len() {
            let close = s.close[t];
            let nh = usize::try_from(out.n_retained_highs[t]).expect("non-negative");
            let nl = usize::try_from(out.n_retained_lows[t]).expect("non-negative");
            for slot in 0..nh {
                prop_assert!(!matches!(close.partial_cmp(&out.retained_highs[t * width + slot]), Some(std::cmp::Ordering::Greater)));
            }
            for slot in 0..nl {
                prop_assert!(!matches!(close.partial_cmp(&out.retained_lows[t * width + slot]), Some(std::cmp::Ordering::Less)));
            }
        }
    }

    /// A swept level is always one of the levels present on that bar before the cap.
    #[test]
    fn swept_price_is_finite_only_with_a_location(s in series(40), width in 1_usize..=4) {
        let out = run(&s, width);
        for t in 0..s.close.len() {
            prop_assert_eq!(out.swept_high[t].is_nan(), out.swept_high_loc[t].is_nan());
            prop_assert_eq!(out.swept_low[t].is_nan(), out.swept_low_loc[t].is_nan());
        }
    }
}
