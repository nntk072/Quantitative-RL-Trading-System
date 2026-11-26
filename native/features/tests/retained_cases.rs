//! Hand-computed cases for the retained-level kernel (reference: swings.retained_swing_levels).

use qrl_features::{retained_swing_levels, KernelError, RetainedInput};

struct Bars {
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

impl Bars {
    fn input(&self) -> RetainedInput<'_> {
        RetainedInput {
            swing_high_event: &self.ev_h,
            swing_low_event: &self.ev_l,
            swing_high_extreme: &self.px_h,
            swing_low_extreme: &self.px_l,
            swing_high_location: &self.loc_h,
            swing_low_location: &self.loc_l,
            high: &self.high,
            low: &self.low,
            close: &self.close,
        }
    }
}

fn none(n: usize) -> Bars {
    Bars {
        ev_h: vec![false; n],
        ev_l: vec![false; n],
        px_h: vec![f64::NAN; n],
        px_l: vec![f64::NAN; n],
        loc_h: vec![f64::NAN; n],
        loc_l: vec![f64::NAN; n],
        high: vec![0.0; n],
        low: vec![0.0; n],
        close: vec![0.0; n],
    }
}

#[test]
fn empty_input_gives_empty_outputs() {
    let bars = none(0);
    let out = retained_swing_levels(&bars.input(), 3).expect("empty input is valid");
    assert!(out.n_retained_highs.is_empty());
    assert!(out.retained_highs.is_empty());
    assert_eq!(out.width, 3);
}

#[test]
fn confirmed_high_is_retained_and_swept_by_a_wick() {
    let mut bars = none(4);
    bars.ev_h[1] = true;
    bars.px_h[1] = 10.0;
    bars.loc_h[1] = 0.0;
    bars.high[2] = 9.0;
    bars.close[2] = 9.0;
    bars.high[3] = 10.5; // wick beyond the level, close back below it
    bars.close[3] = 9.9;
    let out = retained_swing_levels(&bars.input(), 2).expect("valid");
    // The level is admitted on its confirmation bar (t = 1), so it counts from t = 1 onward.
    assert_eq!(out.n_retained_highs, vec![0, 1, 1, 1]);
    assert!(out.swept_high[3] == 10.0 && out.swept_high_loc[3] == 0.0);
    assert!(out.swept_high[2].is_nan());
    // Row 3, slot 0 holds the retained high and its pivot location.
    assert_eq!(out.retained_highs[3 * 2], 10.0);
    assert_eq!(out.retained_high_locs[3 * 2], 0.0);
    assert!(out.retained_highs[3 * 2 + 1].is_nan());
}

#[test]
fn close_through_a_level_invalidates_it_before_any_sweep() {
    let mut bars = none(4);
    bars.ev_h[1] = true;
    bars.px_h[1] = 10.0;
    bars.loc_h[1] = 0.0;
    bars.high[3] = 10.5;
    bars.close[3] = 10.2; // body close above the level removes it
    let out = retained_swing_levels(&bars.input(), 2).expect("valid");
    assert_eq!(out.n_retained_highs, vec![0, 1, 1, 0]);
    assert!(out.swept_high[3].is_nan());
    assert!(out.swept_high_loc[3].is_nan());
}

#[test]
fn nan_close_keeps_every_level() {
    let mut bars = none(3);
    bars.ev_l[0] = true;
    bars.px_l[0] = 5.0;
    bars.loc_l[0] = 0.0;
    bars.close[0] = 6.0; // a close above a low level does not invalidate it
    bars.close[1] = f64::NAN;
    bars.close[2] = f64::NAN;
    let out = retained_swing_levels(&bars.input(), 1).expect("valid");
    assert_eq!(out.n_retained_lows, vec![1, 1, 1]);
}

#[test]
fn width_cap_keeps_the_newest_levels_oldest_first() {
    let mut bars = none(3);
    for (t, price) in [(0_usize, 5.0), (1, 6.0), (2, 7.0)] {
        bars.ev_h[t] = true;
        bars.px_h[t] = price;
        bars.loc_h[t] = t as f64;
    }
    let out = retained_swing_levels(&bars.input(), 2).expect("valid");
    assert_eq!(out.n_retained_highs, vec![1, 2, 2]);
    assert_eq!(out.retained_highs[2 * 2], 6.0);
    assert_eq!(out.retained_highs[2 * 2 + 1], 7.0);
    assert_eq!(out.retained_high_locs[2 * 2], 1.0);
}

#[test]
fn non_finite_swing_is_not_admitted() {
    let mut bars = none(2);
    bars.ev_h[0] = true;
    bars.px_h[0] = f64::NAN;
    bars.loc_h[0] = 0.0;
    bars.ev_h[1] = true;
    bars.px_h[1] = 4.0;
    bars.loc_h[1] = f64::INFINITY;
    let out = retained_swing_levels(&bars.input(), 1).expect("valid");
    assert_eq!(out.n_retained_highs, vec![0, 0]);
}

#[test]
fn zero_width_is_refused() {
    let bars = none(1);
    assert_eq!(
        retained_swing_levels(&bars.input(), 0).unwrap_err(),
        KernelError::ZeroWidth
    );
}

#[test]
fn mismatched_input_length_is_refused() {
    let mut bars = none(3);
    bars.close.pop();
    let err = retained_swing_levels(&bars.input(), 1).unwrap_err();
    assert_eq!(
        err,
        KernelError::LengthMismatch {
            field: "close",
            expected: 3,
            found: 2
        }
    );
}
