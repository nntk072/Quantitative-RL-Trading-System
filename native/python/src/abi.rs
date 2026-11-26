//! Python boundary of the shared data ABI.
//!
//! Each array is read through the buffer protocol and checked before it is copied: the element
//! code and size, native byte order, C-contiguity, and then the shape. The copy is owned by the
//! returned batch, so no Python object is retained after the call. Validation rules live in
//! `qrl_domain::abi`; this module only converts Python objects and maps refusals to exceptions.

use std::ffi::CStr;

use pyo3::buffer::{Element, PyUntypedBuffer};
use pyo3::exceptions::{PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyTuple};
use qrl_domain::abi::{
    self, layout, AbiError as Refusal, BarBatch, BarColumns, Column, ColumnSpec, FeatureRowBlock,
    FeatureRowColumns, ObservationWindow, ObservationWindowColumns, PayloadKind, QuoteBatch,
    QuoteColumns, SchemaId,
};

/// Python exception types of the ABI. `AbiVersionError` is a subclass of `AbiError`.
mod exceptions {
    use pyo3::exceptions::PyValueError;

    pyo3::create_exception!(
        qrl_native,
        AbiError,
        PyValueError,
        "A shared data ABI input was refused: shape, length, mask, finiteness or a record rule."
    );

    pyo3::create_exception!(
        qrl_native,
        AbiVersionError,
        AbiError,
        "The schema identity or ABI version is unknown or not accepted for this payload."
    );
}

pub(crate) use exceptions::{AbiError, AbiVersionError};

/// Maps a refusal to the Python exception class that names its category.
///
/// Dtype, byte-order and buffer-protocol refusals are `TypeError`, as NumPy raises for a
/// wrong element type. Unknown schemas or versions are `AbiVersionError`. Everything else is
/// `AbiError`, a `ValueError`.
fn to_py(err: Refusal) -> PyErr {
    let message = err.to_string();
    match err {
        Refusal::DType { .. } | Refusal::NotNative { .. } | Refusal::NotBuffer { .. } => {
            PyTypeError::new_err(message)
        }
        Refusal::UnsupportedSchema { .. } | Refusal::UnsupportedAbiVersion { .. } => {
            AbiVersionError::new_err(message)
        }
        _ => AbiError::new_err(message),
    }
}

/// Native byte order, returned as the struct-module code of the element.
///
/// Accepts the bare code (native), `@`, and the explicit order that matches this host. Any
/// other prefix, such as `>` on a little-endian host, is not native and is refused.
fn native_code(format: &CStr) -> Option<u8> {
    match format.to_bytes() {
        [code] => Some(*code),
        [b'@', code] => Some(*code),
        [b'<' | b'=', code] if cfg!(target_endian = "little") => Some(*code),
        [b'>' | b'!', code] if cfg!(target_endian = "big") => Some(*code),
        _ => None,
    }
}

/// An element type that the ABI accepts, with the struct codes it is read from.
trait AbiElement: Element {
    /// NumPy-style name used in messages.
    const NAME: &'static str;
    /// Accepted native struct-module codes.
    const CODES: &'static [u8];
}

impl AbiElement for i32 {
    const NAME: &'static str = "int32";
    const CODES: &'static [u8] = b"il";
}

impl AbiElement for i64 {
    const NAME: &'static str = "int64";
    const CODES: &'static [u8] = b"ql";
}

impl AbiElement for u8 {
    const NAME: &'static str = "uint8";
    const CODES: &'static [u8] = b"B";
}

impl AbiElement for f32 {
    const NAME: &'static str = "float32";
    const CODES: &'static [u8] = b"f";
}

impl AbiElement for f64 {
    const NAME: &'static str = "float64";
    const CODES: &'static [u8] = b"d";
}

/// Reads one array into an owned, row-major copy with its shape.
///
/// Checks, in order: buffer protocol, byte order, element code and size, C-contiguity. The shape
/// is checked later by the domain constructor, which knows the layout rank and length.
fn read_column<T: AbiElement>(
    py: Python<'_>,
    obj: &Bound<'_, PyAny>,
    column: &'static str,
) -> Result<Column<T>, Refusal> {
    let buffer = PyUntypedBuffer::get(obj).map_err(|_| Refusal::NotBuffer { column })?;
    let format = buffer.format();
    let code = native_code(format).ok_or_else(|| Refusal::NotNative {
        column,
        found: format.to_string_lossy().into_owned(),
    })?;
    if !T::CODES.contains(&code) || buffer.item_size() != std::mem::size_of::<T>() {
        return Err(Refusal::DType {
            column,
            expected: T::NAME,
            found: format.to_string_lossy().into_owned(),
        });
    }
    if !buffer.is_c_contiguous() {
        return Err(Refusal::NotContiguous { column });
    }
    let shape = buffer.shape().to_vec();
    let typed = buffer.into_typed::<T>().map_err(|err| Refusal::Buffer {
        column,
        reason: err.to_string(),
    })?;
    let data = typed.to_vec(py).map_err(|err| Refusal::Buffer {
        column,
        reason: err.to_string(),
    })?;
    Ok(Column { shape, data })
}

/// Reads a required key of the input mapping.
fn take<T: AbiElement>(
    py: Python<'_>,
    columns: &Bound<'_, PyDict>,
    column: &'static str,
) -> PyResult<Column<T>> {
    match columns.get_item(column)? {
        Some(obj) => read_column(py, &obj, column).map_err(to_py),
        None => Err(to_py(Refusal::MissingColumn { column })),
    }
}

/// Refuses any key that the payload layout does not name, including nullable companions.
fn check_keys(columns: &Bound<'_, PyDict>, spec: &[ColumnSpec]) -> PyResult<()> {
    let mut allowed: Vec<String> = Vec::new();
    for column in spec {
        allowed.push(column.name.to_owned());
        if column.nullable {
            allowed.push(format!("{}_valid", column.name));
        }
    }
    for key in columns.keys() {
        let name = key
            .extract::<String>()
            .unwrap_or_else(|_| format!("{key:?}"));
        if !allowed.contains(&name) {
            return Err(to_py(Refusal::UnexpectedColumn { column: name }));
        }
    }
    Ok(())
}

fn to_bytes<'py>(py: Python<'py>, data: impl Iterator<Item = [u8; 8]>) -> Bound<'py, PyBytes> {
    let bytes: Vec<u8> = data.flatten().collect();
    PyBytes::new(py, &bytes)
}

fn i64_bytes<'py>(py: Python<'py>, values: &[i64]) -> Bound<'py, PyBytes> {
    to_bytes(py, values.iter().map(|value| value.to_le_bytes()))
}

fn f64_bytes<'py>(py: Python<'py>, values: &[f64]) -> Bound<'py, PyBytes> {
    to_bytes(py, values.iter().map(|value| value.to_le_bytes()))
}

fn i32_bytes<'py>(py: Python<'py>, values: &[i32]) -> Bound<'py, PyBytes> {
    let bytes: Vec<u8> = values
        .iter()
        .flat_map(|value| value.to_le_bytes())
        .collect();
    PyBytes::new(py, &bytes)
}

fn f32_bytes<'py>(py: Python<'py>, values: &[f32]) -> Bound<'py, PyBytes> {
    let bytes: Vec<u8> = values
        .iter()
        .flat_map(|value| value.to_le_bytes())
        .collect();
    PyBytes::new(py, &bytes)
}

fn mask_bytes<'py>(py: Python<'py>, values: &[bool]) -> Bound<'py, PyBytes> {
    let bytes: Vec<u8> = values.iter().map(|&value| u8::from(value)).collect();
    PyBytes::new(py, &bytes)
}

fn unknown_column(name: &str) -> PyErr {
    PyKeyError::new_err(format!("no column named {name:?} in this batch"))
}

fn payload_kind(name: &str) -> PyResult<PayloadKind> {
    match name {
        "quote" => Ok(PayloadKind::Quote),
        "bar" => Ok(PayloadKind::Bar),
        "feature_row" => Ok(PayloadKind::FeatureRow),
        "observation" => Ok(PayloadKind::Observation),
        other => Err(PyValueError::new_err(format!(
            "unknown payload {other:?}; expected quote, bar, feature_row or observation"
        ))),
    }
}

/// Shared data ABI version implemented by this build.
#[pyfunction]
pub(crate) fn shared_data_abi_version() -> u32 {
    abi::SHARED_DATA_ABI_VERSION
}

/// Refuses an ABI version other than this build's version.
#[pyfunction]
pub(crate) fn require_abi_version(version: u32) -> PyResult<()> {
    abi::check_abi_version(version).map_err(to_py)
}

/// Schema identities recognised by this build, as written by `market_data.arrow_schemas` and
/// `decisioning.observations`.
#[pyfunction]
pub(crate) fn schema_ids() -> Vec<&'static str> {
    SchemaId::ALL.iter().map(|schema| schema.as_str()).collect()
}

/// Column layout of a payload in wire order, as `(name, dtype, rank, nullable, unit)` tuples.
///
/// `payload` is one of `quote`, `bar`, `feature_row` or `observation`.
#[pyfunction]
pub(crate) fn abi_layout<'py>(
    py: Python<'py>,
    payload: &str,
) -> PyResult<Vec<Bound<'py, PyTuple>>> {
    layout(payload_kind(payload)?)
        .iter()
        .map(|spec| {
            PyTuple::new(
                py,
                [
                    spec.name.into_pyobject(py)?.into_any(),
                    spec.dtype.name().into_pyobject(py)?.into_any(),
                    spec.rank.into_pyobject(py)?.into_any(),
                    spec.nullable.into_pyobject(py)?.to_owned().into_any(),
                    spec.unit.into_pyobject(py)?.into_any(),
                ],
            )
        })
        .collect()
}

/// Number of coordinates of an account observation schema (`account-state-v1` or `-v2`).
#[pyfunction]
pub(crate) fn observation_width(schema_id: &str) -> PyResult<usize> {
    SchemaId::parse(schema_id)
        .and_then(abi::observation_width)
        .ok_or_else(|| {
            to_py(Refusal::UnsupportedSchema {
                found: schema_id.to_owned(),
                accepted: "account-state-v1, account-state-v2",
            })
        })
}

/// Validated quote batch for one instrument. Owns its copy of the input arrays.
#[pyclass(name = "QuoteBatch", module = "qrl_native", frozen)]
pub(crate) struct PyQuoteBatch {
    inner: QuoteBatch,
}

#[pymethods]
impl PyQuoteBatch {
    /// Builds a batch from a mapping of ABI column names to NumPy-compatible arrays.
    ///
    /// Nullable columns take a `<name>_valid` companion (`uint8`, 1 = present). Every array must be
    /// C-contiguous, native-endian and of the layout dtype. Missing values must be NaN.
    #[staticmethod]
    #[pyo3(signature = (*, schema_id, instrument_id, source_id, columns))]
    fn from_columns(
        py: Python<'_>,
        schema_id: &str,
        instrument_id: &str,
        source_id: &str,
        columns: &Bound<'_, PyDict>,
    ) -> PyResult<Self> {
        check_keys(columns, layout(PayloadKind::Quote))?;
        let input = QuoteColumns {
            event_time_ns: take(py, columns, "event_time_ns")?,
            available_at_ns: take(py, columns, "available_at_ns")?,
            source_sequence: take(py, columns, "source_sequence")?,
            bid: take(py, columns, "bid")?,
            bid_valid: take(py, columns, "bid_valid")?,
            ask: take(py, columns, "ask")?,
            ask_valid: take(py, columns, "ask_valid")?,
            bid_size: take(py, columns, "bid_size")?,
            bid_size_valid: take(py, columns, "bid_size_valid")?,
            ask_size: take(py, columns, "ask_size")?,
            ask_size_valid: take(py, columns, "ask_size_valid")?,
            source_flags: take(py, columns, "source_flags")?,
        };
        let inner =
            QuoteBatch::try_new(schema_id, instrument_id, source_id, input).map_err(to_py)?;
        Ok(Self { inner })
    }

    /// Number of quote rows.
    #[getter]
    fn rows(&self) -> usize {
        self.inner.rows()
    }

    /// Schema identity.
    #[getter]
    fn schema_id(&self) -> &'static str {
        self.inner.schema().as_str()
    }

    /// Instrument identity.
    #[getter]
    fn instrument_id(&self) -> String {
        self.inner.instrument_id().to_owned()
    }

    /// Source identity.
    #[getter]
    fn source_id(&self) -> String {
        self.inner.source_id().to_owned()
    }

    /// One column as little-endian packed bytes, for example `np.frombuffer(b, "<f8")`.
    fn column<'py>(&self, py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyBytes>> {
        Ok(match name {
            "event_time_ns" => i64_bytes(py, self.inner.event_time_ns()),
            "available_at_ns" => i64_bytes(py, self.inner.available_at_ns()),
            "source_sequence" => i64_bytes(py, self.inner.source_sequence()),
            "bid" => f64_bytes(py, self.inner.bid().values()),
            "bid_valid" => mask_bytes(py, self.inner.bid().valid()),
            "ask" => f64_bytes(py, self.inner.ask().values()),
            "ask_valid" => mask_bytes(py, self.inner.ask().valid()),
            "bid_size" => f64_bytes(py, self.inner.bid_size().values()),
            "bid_size_valid" => mask_bytes(py, self.inner.bid_size().valid()),
            "ask_size" => f64_bytes(py, self.inner.ask_size().values()),
            "ask_size_valid" => mask_bytes(py, self.inner.ask_size().valid()),
            "source_flags" => i32_bytes(py, self.inner.source_flags()),
            other => return Err(unknown_column(other)),
        })
    }
}

/// Validated OHLC bar batch for one instrument. Owns its copy of the input arrays.
#[pyclass(name = "BarBatch", module = "qrl_native", frozen)]
pub(crate) struct PyBarBatch {
    inner: BarBatch,
}

#[pymethods]
impl PyBarBatch {
    /// Builds a batch from a mapping of ABI column names. See `QuoteBatch.from_columns`.
    #[staticmethod]
    #[pyo3(signature = (*, schema_id, instrument_id, source_id, columns))]
    fn from_columns(
        py: Python<'_>,
        schema_id: &str,
        instrument_id: &str,
        source_id: &str,
        columns: &Bound<'_, PyDict>,
    ) -> PyResult<Self> {
        check_keys(columns, layout(PayloadKind::Bar))?;
        let input = BarColumns {
            event_time_ns: take(py, columns, "event_time_ns")?,
            close_time_ns: take(py, columns, "close_time_ns")?,
            available_at_ns: take(py, columns, "available_at_ns")?,
            source_sequence: take(py, columns, "source_sequence")?,
            open: take(py, columns, "open")?,
            high: take(py, columns, "high")?,
            low: take(py, columns, "low")?,
            close: take(py, columns, "close")?,
            volume: take(py, columns, "volume")?,
            volume_valid: take(py, columns, "volume_valid")?,
        };
        let inner = BarBatch::try_new(schema_id, instrument_id, source_id, input).map_err(to_py)?;
        Ok(Self { inner })
    }

    /// Number of bar rows.
    #[getter]
    fn rows(&self) -> usize {
        self.inner.rows()
    }

    /// Instrument identity.
    #[getter]
    fn instrument_id(&self) -> String {
        self.inner.instrument_id().to_owned()
    }

    /// Source identity.
    #[getter]
    fn source_id(&self) -> String {
        self.inner.source_id().to_owned()
    }

    /// One column as little-endian packed bytes.
    fn column<'py>(&self, py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyBytes>> {
        Ok(match name {
            "event_time_ns" => i64_bytes(py, self.inner.event_time_ns()),
            "close_time_ns" => i64_bytes(py, self.inner.close_time_ns()),
            "available_at_ns" => i64_bytes(py, self.inner.available_at_ns()),
            "source_sequence" => i64_bytes(py, self.inner.source_sequence()),
            "open" => f64_bytes(py, self.inner.open()),
            "high" => f64_bytes(py, self.inner.high()),
            "low" => f64_bytes(py, self.inner.low()),
            "close" => f64_bytes(py, self.inner.close()),
            "volume" => f64_bytes(py, self.inner.volume().values()),
            "volume_valid" => mask_bytes(py, self.inner.volume().valid()),
            other => return Err(unknown_column(other)),
        })
    }
}

/// Validated feature-row block for one feature set. Owns its copy of the input arrays.
#[pyclass(name = "FeatureRowBlock", module = "qrl_native", frozen)]
pub(crate) struct PyFeatureRowBlock {
    inner: FeatureRowBlock,
}

#[pymethods]
impl PyFeatureRowBlock {
    /// Builds a block from ABI columns. `width` is the manifest feature count; the `values`
    /// matrix must be `(rows, width)` and C-contiguous.
    #[staticmethod]
    #[pyo3(signature = (*, schema_id, instrument_id, feature_set_id, feature_version, content_hash, width, columns))]
    #[allow(clippy::too_many_arguments)]
    fn from_columns(
        py: Python<'_>,
        schema_id: &str,
        instrument_id: &str,
        feature_set_id: &str,
        feature_version: &str,
        content_hash: &str,
        width: usize,
        columns: &Bound<'_, PyDict>,
    ) -> PyResult<Self> {
        check_keys(columns, layout(PayloadKind::FeatureRow))?;
        let input = FeatureRowColumns {
            event_time_ns: take(py, columns, "event_time_ns")?,
            available_at_ns: take(py, columns, "available_at_ns")?,
            session_eligible: take(py, columns, "session_eligible")?,
            values: take(py, columns, "values")?,
            values_valid: take(py, columns, "values_valid")?,
        };
        let inner = FeatureRowBlock::try_new(
            schema_id,
            instrument_id,
            feature_set_id,
            feature_version,
            content_hash,
            width,
            input,
        )
        .map_err(to_py)?;
        Ok(Self { inner })
    }

    /// Number of decision rows.
    #[getter]
    fn rows(&self) -> usize {
        self.inner.rows()
    }

    /// Feature count per row.
    #[getter]
    fn width(&self) -> usize {
        self.inner.width()
    }

    /// Feature-set identity.
    #[getter]
    fn feature_set_id(&self) -> String {
        self.inner.feature_set_id().to_owned()
    }

    /// One column as little-endian packed bytes. `values` is row-major `(rows, width)`.
    fn column<'py>(&self, py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyBytes>> {
        Ok(match name {
            "event_time_ns" => i64_bytes(py, self.inner.event_time_ns()),
            "available_at_ns" => i64_bytes(py, self.inner.available_at_ns()),
            "session_eligible" => mask_bytes(py, self.inner.session_eligible()),
            "values" => f64_bytes(py, self.inner.values().values()),
            "values_valid" => mask_bytes(py, self.inner.values().valid()),
            other => return Err(unknown_column(other)),
        })
    }
}

/// Validated account observation window. Owns its copy of the input arrays.
#[pyclass(name = "ObservationWindow", module = "qrl_native", frozen)]
pub(crate) struct PyObservationWindow {
    inner: ObservationWindow,
}

#[pymethods]
impl PyObservationWindow {
    /// Builds a window from `values` `(rows, width)` float32 and `mask` `(rows,)` uint8.
    #[staticmethod]
    #[pyo3(signature = (*, schema_id, columns))]
    fn from_columns(
        py: Python<'_>,
        schema_id: &str,
        columns: &Bound<'_, PyDict>,
    ) -> PyResult<Self> {
        check_keys(columns, layout(PayloadKind::Observation))?;
        let input = ObservationWindowColumns {
            values: take(py, columns, "values")?,
            mask: take(py, columns, "mask")?,
        };
        let inner = ObservationWindow::try_new(schema_id, input).map_err(to_py)?;
        Ok(Self { inner })
    }

    /// Number of rows, including left padding.
    #[getter]
    fn rows(&self) -> usize {
        self.inner.rows()
    }

    /// Coordinates per row, fixed by the schema.
    #[getter]
    fn width(&self) -> usize {
        self.inner.width()
    }

    /// Schema identity.
    #[getter]
    fn schema_id(&self) -> &'static str {
        self.inner.schema().as_str()
    }

    /// One column as little-endian packed bytes.
    fn column<'py>(&self, py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyBytes>> {
        Ok(match name {
            "values" => f32_bytes(py, self.inner.values()),
            "mask" => mask_bytes(py, self.inner.real()),
            other => return Err(unknown_column(other)),
        })
    }
}
