//! Causal sequential kernels for the feature pipeline.
//!
//! Each kernel reproduces one Python reference function bit for bit: the same comparisons,
//! the same IEEE-754 operations in the same order, and no fast-math. Python wrappers own the
//! DataFrame layer; this crate only sees slices and returns vectors. It has no Python, I/O or
//! broker dependency.

pub mod retained;

pub use retained::{retained_swing_levels, KernelError, RetainedInput, RetainedOutput};
