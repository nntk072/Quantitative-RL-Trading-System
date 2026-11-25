//! Python binding for the native domain kernels.
//!
//! Only conversions and error mapping live here. Business logic stays in `qrl-domain`.

use pyo3::exceptions::PyOverflowError;
use pyo3::prelude::*;

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
fn remaining_daily_capacity_cents(session_start: i64, equity: i64, daily_loss_limit: i64) -> PyResult<i64> {
    qrl_domain::limits::remaining_daily_capacity(session_start, equity, daily_loss_limit)
        .map_err(|err| PyOverflowError::new_err(err.to_string()))
}

#[pymodule]
fn qrl_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(domain_schema_version, module)?)?;
    module.add_function(wrap_pyfunction!(checked_add_units, module)?)?;
    module.add_function(wrap_pyfunction!(canonical_daily_loss_cents, module)?)?;
    module.add_function(wrap_pyfunction!(daily_floor_cents, module)?)?;
    module.add_function(wrap_pyfunction!(remaining_daily_capacity_cents, module)?)?;
    Ok(())
}
