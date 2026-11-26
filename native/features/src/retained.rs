//! Retained unswept swing levels per side (reference: `features.technical.swings.retained_swing_levels`).
//!
//! State per side is an ordered list of confirmed levels (price, pivot location). At each bar:
//! 1. a confirmed swing enters the list only when its extreme and location are finite;
//! 2. a level is removed when the close is beyond it (above a high level, below a low level);
//! 3. the first remaining level whose wick is beyond it is recorded as swept on this bar;
//! 4. the list keeps only its newest `width` entries;
//! 5. the count and the ordered levels are written for the bar.
//!
//! Step 2 recomputes the removal flag from the close on every bar, so a swept flag never persists
//! across bars. Output is row-major `n x width`; slot 0 is the oldest kept level, as in Python.

use std::cmp::Ordering;
use std::fmt;

/// Refusal of a kernel call. The wrapper maps every variant to a Python `ValueError`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KernelError {
    /// An input slice does not have the bar count of the first input.
    LengthMismatch {
        /// Name of the mismatched input.
        field: &'static str,
        /// Bar count expected from the first input.
        expected: usize,
        /// Length actually supplied.
        found: usize,
    },
    /// The retained width must be at least one.
    ZeroWidth,
    /// The output matrix size overflows `usize`.
    SizeOverflow,
}

impl fmt::Display for KernelError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            KernelError::LengthMismatch {
                field,
                expected,
                found,
            } => write!(f, "{field} has length {found}, expected {expected}"),
            KernelError::ZeroWidth => write!(f, "retained width must be at least 1"),
            KernelError::SizeOverflow => write!(f, "retained output size overflows"),
        }
    }
}

impl std::error::Error for KernelError {}

/// Borrowed inputs, one entry per bar. Swing arrays come from the swing frame; price arrays from
/// the bar frame.
#[derive(Debug, Clone, Copy)]
pub struct RetainedInput<'a> {
    /// Confirmed high-swing events.
    pub swing_high_event: &'a [bool],
    /// Confirmed low-swing events.
    pub swing_low_event: &'a [bool],
    /// High-swing extreme price at confirmation (NaN when absent).
    pub swing_high_extreme: &'a [f64],
    /// Low-swing extreme price at confirmation (NaN when absent).
    pub swing_low_extreme: &'a [f64],
    /// High-swing pivot location (bar position, NaN when absent).
    pub swing_high_location: &'a [f64],
    /// Low-swing pivot location (bar position, NaN when absent).
    pub swing_low_location: &'a [f64],
    /// Bar highs.
    pub high: &'a [f64],
    /// Bar lows.
    pub low: &'a [f64],
    /// Bar closes.
    pub close: &'a [f64],
}

/// Owned outputs, one entry per bar except the row-major matrices (`n x width`).
#[derive(Debug, Clone, PartialEq)]
pub struct RetainedOutput {
    /// Retained width (slots per side).
    pub width: usize,
    /// Number of retained high levels after the bar's update.
    pub n_retained_highs: Vec<i64>,
    /// Number of retained low levels after the bar's update.
    pub n_retained_lows: Vec<i64>,
    /// Swept high level price on this bar, NaN when none.
    pub swept_high: Vec<f64>,
    /// Swept low level price on this bar, NaN when none.
    pub swept_low: Vec<f64>,
    /// Pivot location of the swept high level, NaN when none.
    pub swept_high_loc: Vec<f64>,
    /// Pivot location of the swept low level, NaN when none.
    pub swept_low_loc: Vec<f64>,
    /// Retained high prices, row-major `n x width`, NaN in unused slots.
    pub retained_highs: Vec<f64>,
    /// Retained high pivot locations, row-major `n x width`.
    pub retained_high_locs: Vec<f64>,
    /// Retained low prices, row-major `n x width`, NaN in unused slots.
    pub retained_lows: Vec<f64>,
    /// Retained low pivot locations, row-major `n x width`.
    pub retained_low_locs: Vec<f64>,
}

/// True when the close is strictly above a high level. NaN on either side is never an invalidation.
fn closed_above(close: f64, price: f64) -> bool {
    matches!(close.partial_cmp(&price), Some(Ordering::Greater))
}

/// True when the close is strictly below a low level. NaN on either side is never an invalidation.
fn closed_below(close: f64, price: f64) -> bool {
    matches!(close.partial_cmp(&price), Some(Ordering::Less))
}

#[derive(Clone, Copy)]
struct Level {
    price: f64,
    location: f64,
}

/// Runs the retained-level state machine over every bar.
///
/// # Errors
///
/// Returns [`KernelError::ZeroWidth`] when `width` is zero, [`KernelError::LengthMismatch`] when
/// any input differs in length from `swing_high_event`, and [`KernelError::SizeOverflow`] when
/// `n * width` does not fit in `usize`.
pub fn retained_swing_levels(
    input: &RetainedInput<'_>,
    width: usize,
) -> Result<RetainedOutput, KernelError> {
    if width == 0 {
        return Err(KernelError::ZeroWidth);
    }
    let n = input.swing_high_event.len();
    let checks: [(&'static str, usize); 8] = [
        ("swing_low_event", input.swing_low_event.len()),
        ("swing_high_extreme", input.swing_high_extreme.len()),
        ("swing_low_extreme", input.swing_low_extreme.len()),
        ("swing_high_location", input.swing_high_location.len()),
        ("swing_low_location", input.swing_low_location.len()),
        ("high", input.high.len()),
        ("low", input.low.len()),
        ("close", input.close.len()),
    ];
    for (field, found) in checks {
        if found != n {
            return Err(KernelError::LengthMismatch {
                field,
                expected: n,
                found,
            });
        }
    }
    let matrix = n.checked_mul(width).ok_or(KernelError::SizeOverflow)?;

    let mut out = RetainedOutput {
        width,
        n_retained_highs: vec![0; n],
        n_retained_lows: vec![0; n],
        swept_high: vec![f64::NAN; n],
        swept_low: vec![f64::NAN; n],
        swept_high_loc: vec![f64::NAN; n],
        swept_low_loc: vec![f64::NAN; n],
        retained_highs: vec![f64::NAN; matrix],
        retained_high_locs: vec![f64::NAN; matrix],
        retained_lows: vec![f64::NAN; matrix],
        retained_low_locs: vec![f64::NAN; matrix],
    };

    let mut highs: Vec<Level> = Vec::new();
    let mut lows: Vec<Level> = Vec::new();

    for t in 0..n {
        if input.swing_high_event[t]
            && input.swing_high_extreme[t].is_finite()
            && input.swing_high_location[t].is_finite()
        {
            highs.push(Level {
                price: input.swing_high_extreme[t],
                location: input.swing_high_location[t],
            });
        }
        if input.swing_low_event[t]
            && input.swing_low_extreme[t].is_finite()
            && input.swing_low_location[t].is_finite()
        {
            lows.push(Level {
                price: input.swing_low_extreme[t],
                location: input.swing_low_location[t],
            });
        }

        // A body close through a level invalidates it. Comparisons with NaN are false, as in
        // Python, so a NaN close keeps every level.
        let close = input.close[t];
        highs.retain(|level| !closed_above(close, level.price));
        lows.retain(|level| !closed_below(close, level.price));

        // The first level whose wick is beyond it is swept on this bar.
        if let Some(level) = highs.iter().find(|level| input.high[t] > level.price) {
            out.swept_high[t] = level.price;
            out.swept_high_loc[t] = level.location;
        }
        if let Some(level) = lows.iter().find(|level| input.low[t] < level.price) {
            out.swept_low[t] = level.price;
            out.swept_low_loc[t] = level.location;
        }

        // Keep the newest `width` levels; the list is ordered oldest first.
        if highs.len() > width {
            let excess = highs.len() - width;
            highs.drain(..excess);
        }
        if lows.len() > width {
            let excess = lows.len() - width;
            lows.drain(..excess);
        }

        out.n_retained_highs[t] = highs.len() as i64;
        out.n_retained_lows[t] = lows.len() as i64;
        let base = t * width;
        for (slot, level) in highs.iter().enumerate() {
            out.retained_highs[base + slot] = level.price;
            out.retained_high_locs[base + slot] = level.location;
        }
        for (slot, level) in lows.iter().enumerate() {
            out.retained_lows[base + slot] = level.price;
            out.retained_low_locs[base + slot] = level.location;
        }
    }
    Ok(out)
}
