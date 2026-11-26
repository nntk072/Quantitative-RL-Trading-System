//! Python binding for the native domain kernels.
//!
//! Only conversions and error mapping live here. Business logic stays in `qrl-domain`.

use pyo3::exceptions::{PyOverflowError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyTuple};
use qrl_domain::{DomainError, Fill, Price, Quantity, Side};
use qrl_features::{KernelError, RetainedInput};

/// Maps a domain refusal to Python: overflow to `OverflowError`, invalid input to `ValueError`.
fn to_py_err(err: DomainError) -> PyErr {
    match err {
        DomainError::Overflow => PyOverflowError::new_err(err.to_string()),
        _ => PyValueError::new_err(err.to_string()),
    }
}

/// Schema version of the native domain contract.
#[pyfunction]
fn domain_schema_version() -> u32 {
    qrl_domain::DOMAIN_SCHEMA_VERSION
}

/// Adds two integer-unit quantities, raising `OverflowError` instead of wrapping.
#[pyfunction]
fn checked_add_units(lhs: i64, rhs: i64) -> PyResult<i64> {
    qrl_domain::checked_add_units(lhs, rhs).map_err(|err| PyOverflowError::new_err(err.to_string()))
}

/// Session-start equity minus equity, floored at zero, in cents.
#[pyfunction]
fn canonical_daily_loss_cents(session_start: i64, equity: i64) -> PyResult<i64> {
    qrl_domain::limits::canonical_daily_loss(session_start, equity)
        .map_err(|err| PyOverflowError::new_err(err.to_string()))
}

/// Daily-loss floor in cents: session start minus the limit.
#[pyfunction]
fn daily_floor_cents(session_start: i64, daily_loss_limit: i64) -> PyResult<i64> {
    qrl_domain::limits::daily_floor(session_start, daily_loss_limit)
        .map_err(|err| PyOverflowError::new_err(err.to_string()))
}

/// Remaining capacity above the daily floor in cents, floored at zero.
#[pyfunction]
fn remaining_daily_capacity_cents(
    session_start: i64,
    equity: i64,
    daily_loss_limit: i64,
) -> PyResult<i64> {
    qrl_domain::limits::remaining_daily_capacity(session_start, equity, daily_loss_limit)
        .map_err(|err| PyOverflowError::new_err(err.to_string()))
}

/// Notional in cents: price ticks times lots times cents per tick per lot, checked.
#[pyfunction]
fn notional_cents(price_ticks: i64, lots: i64, cents_per_tick_per_lot: i64) -> PyResult<i64> {
    let price = Price::from_ticks(price_ticks).map_err(to_py_err)?;
    let quantity = Quantity::from_lots(lots).map_err(to_py_err)?;
    qrl_domain::notional_cents(price, quantity, cents_per_tick_per_lot).map_err(to_py_err)
}

/// Signed position with average entry, realized PnL and fees, backed by `qrl_domain::Position`.
#[pyclass(name = "Position", module = "qrl_native")]
struct PyPosition {
    inner: qrl_domain::Position,
}

#[pymethods]
impl PyPosition {
    #[new]
    fn new() -> Self {
        Self {
            inner: qrl_domain::Position::flat(),
        }
    }

    /// Applies one fill. `buy` selects the side; a refused fill leaves the position unchanged.
    #[pyo3(signature = (buy, price_ticks, lots, fee_cents, cents_per_tick_per_lot))]
    fn apply_fill(
        &mut self,
        buy: bool,
        price_ticks: i64,
        lots: i64,
        fee_cents: i64,
        cents_per_tick_per_lot: i64,
    ) -> PyResult<()> {
        let side = if buy { Side::Buy } else { Side::Sell };
        let price = Price::from_ticks(price_ticks).map_err(to_py_err)?;
        let quantity = Quantity::from_lots(lots).map_err(to_py_err)?;
        // Position-level fills carry no order identity; order_id is not used by Position.
        let fill = Fill::new(0, side, price, quantity, fee_cents).map_err(to_py_err)?;
        self.inner
            .apply_fill(&fill, cents_per_tick_per_lot)
            .map_err(to_py_err)
    }

    /// Signed position in lots.
    #[getter]
    fn lots(&self) -> i64 {
        self.inner.lots()
    }

    /// Average entry rounded half away from zero to whole ticks; `None` when flat.
    #[getter]
    fn average_entry_ticks(&self) -> Option<i64> {
        self.inner.average_entry_ticks()
    }

    /// Gross realized trading PnL in cents, excluding fees.
    #[getter]
    fn realized_pnl_cents(&self) -> i64 {
        self.inner.realized_pnl_cents()
    }

    /// Total commissions in cents.
    #[getter]
    fn fees_cents(&self) -> i64 {
        self.inner.fees_cents()
    }
}

/// Decodes little-endian `f64` values from a bytes buffer, refusing a partial element.
fn decode_f64(name: &str, bytes: &[u8]) -> PyResult<Vec<f64>> {
    if !bytes.len().is_multiple_of(8) {
        return Err(PyValueError::new_err(format!(
            "{name} must be a whole number of float64 values, got {} bytes",
            bytes.len()
        )));
    }
    let (words, _) = bytes.as_chunks::<8>();
    Ok(words.iter().map(|word| f64::from_le_bytes(*word)).collect())
}

/// Decodes a boolean array sent as one byte per bar; any byte other than 0 or 1 is refused.
fn decode_bool(name: &str, bytes: &[u8]) -> PyResult<Vec<bool>> {
    bytes
        .iter()
        .map(|byte| match byte {
            0 => Ok(false),
            1 => Ok(true),
            other => Err(PyValueError::new_err(format!(
                "{name} must contain only 0 or 1 bytes, found {other}"
            ))),
        })
        .collect()
}

/// Encodes values as little-endian bytes so Python reads them as `<f8` / `<i8` arrays.
fn encode_f64(values: &[f64]) -> Vec<u8> {
    values
        .iter()
        .flat_map(|value| value.to_le_bytes())
        .collect()
}

fn encode_i64(values: &[i64]) -> Vec<u8> {
    values
        .iter()
        .flat_map(|value| value.to_le_bytes())
        .collect()
}

/// Retained unswept swing levels per side. Arrays cross the boundary as little-endian bytes:
/// `float64` for prices, locations and bar series; one byte per bar for the boolean events.
/// Returns the ten output arrays in the order of `retained_swing_levels_outputs` on the Python side.
#[pyfunction]
#[pyo3(signature = (
    swing_high_event,
    swing_low_event,
    swing_high_extreme,
    swing_low_extreme,
    swing_high_location,
    swing_low_location,
    high,
    low,
    close,
    width
))]
#[allow(clippy::too_many_arguments)]
fn retained_swing_levels<'py>(
    py: Python<'py>,
    swing_high_event: &[u8],
    swing_low_event: &[u8],
    swing_high_extreme: &[u8],
    swing_low_extreme: &[u8],
    swing_high_location: &[u8],
    swing_low_location: &[u8],
    high: &[u8],
    low: &[u8],
    close: &[u8],
    width: usize,
) -> PyResult<Bound<'py, PyTuple>> {
    let swing_high_event = decode_bool("swing_high_event", swing_high_event)?;
    let swing_low_event = decode_bool("swing_low_event", swing_low_event)?;
    let swing_high_extreme = decode_f64("swing_high_extreme", swing_high_extreme)?;
    let swing_low_extreme = decode_f64("swing_low_extreme", swing_low_extreme)?;
    let swing_high_location = decode_f64("swing_high_location", swing_high_location)?;
    let swing_low_location = decode_f64("swing_low_location", swing_low_location)?;
    let high = decode_f64("high", high)?;
    let low = decode_f64("low", low)?;
    let close = decode_f64("close", close)?;
    let input = RetainedInput {
        swing_high_event: &swing_high_event,
        swing_low_event: &swing_low_event,
        swing_high_extreme: &swing_high_extreme,
        swing_low_extreme: &swing_low_extreme,
        swing_high_location: &swing_high_location,
        swing_low_location: &swing_low_location,
        high: &high,
        low: &low,
        close: &close,
    };
    let out = qrl_features::retained_swing_levels(&input, width).map_err(|err| match err {
        KernelError::SizeOverflow => PyOverflowError::new_err(err.to_string()),
        _ => PyValueError::new_err(err.to_string()),
    })?;
    let parts = [
        PyBytes::new(py, &encode_i64(&out.n_retained_highs)),
        PyBytes::new(py, &encode_i64(&out.n_retained_lows)),
        PyBytes::new(py, &encode_f64(&out.swept_high)),
        PyBytes::new(py, &encode_f64(&out.swept_low)),
        PyBytes::new(py, &encode_f64(&out.swept_high_loc)),
        PyBytes::new(py, &encode_f64(&out.swept_low_loc)),
        PyBytes::new(py, &encode_f64(&out.retained_highs)),
        PyBytes::new(py, &encode_f64(&out.retained_high_locs)),
        PyBytes::new(py, &encode_f64(&out.retained_lows)),
        PyBytes::new(py, &encode_f64(&out.retained_low_locs)),
    ];
    PyTuple::new(py, parts)
}

#[pymodule]
fn qrl_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(retained_swing_levels, module)?)?;
    module.add_function(wrap_pyfunction!(domain_schema_version, module)?)?;
    module.add_function(wrap_pyfunction!(checked_add_units, module)?)?;
    module.add_function(wrap_pyfunction!(canonical_daily_loss_cents, module)?)?;
    module.add_function(wrap_pyfunction!(daily_floor_cents, module)?)?;
    module.add_function(wrap_pyfunction!(remaining_daily_capacity_cents, module)?)?;
    module.add_function(wrap_pyfunction!(notional_cents, module)?)?;
    module.add_class::<PyPosition>()?;
    Ok(())
}
