//! Python binding for the native domain kernels.
//!
//! Only conversions and error mapping live here. Business logic stays in `qrl-domain`.

use pyo3::exceptions::{PyOverflowError, PyValueError};
use pyo3::prelude::*;
use qrl_domain::{DomainError, Fill, Price, Quantity, Side};

mod abi;

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

#[pymodule]
fn qrl_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(domain_schema_version, module)?)?;
    module.add_function(wrap_pyfunction!(checked_add_units, module)?)?;
    module.add_function(wrap_pyfunction!(canonical_daily_loss_cents, module)?)?;
    module.add_function(wrap_pyfunction!(daily_floor_cents, module)?)?;
    module.add_function(wrap_pyfunction!(remaining_daily_capacity_cents, module)?)?;
    module.add_function(wrap_pyfunction!(notional_cents, module)?)?;
    module.add_class::<PyPosition>()?;
    module.add_function(wrap_pyfunction!(abi::shared_data_abi_version, module)?)?;
    module.add_function(wrap_pyfunction!(abi::require_abi_version, module)?)?;
    module.add_function(wrap_pyfunction!(abi::abi_layout, module)?)?;
    module.add_function(wrap_pyfunction!(abi::observation_width, module)?)?;
    module.add_function(wrap_pyfunction!(abi::schema_ids, module)?)?;
    module.add_class::<abi::PyQuoteBatch>()?;
    module.add_class::<abi::PyBarBatch>()?;
    module.add_class::<abi::PyFeatureRowBlock>()?;
    module.add_class::<abi::PyObservationWindow>()?;
    module.add_class::<abi::PyDatasetView>()?;
    module.add_function(wrap_pyfunction!(
        abi::dataset_view_from_cache_bytes,
        module
    )?)?;
    module.add("AbiError", module.py().get_type::<abi::AbiError>())?;
    module.add(
        "AbiVersionError",
        module.py().get_type::<abi::AbiVersionError>(),
    )?;
    module.add(
        "AbiCacheError",
        module.py().get_type::<abi::AbiCacheError>(),
    )?;
    Ok(())
}
