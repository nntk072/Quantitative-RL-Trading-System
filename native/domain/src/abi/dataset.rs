//! `DatasetView`: validated bars, aligned feature rows, fold bounds and the fitted-state reference.
//!
//! A view is immutable. It has no mutating method, so a clone of an `Arc<DatasetView>` may be
//! shared in process without copying: the lifetime is proven by `Arc`, and no raw pointers or
//! manual memory management are involved. Other processes do not share memory with it. They read the cache container, which
//! is a copy, and the decoder re-runs every batch constructor on what it reads.
//!
//! Fold rules (all rows are indices into the aligned dataset, end-exclusive):
//! - each training range is non-empty and ends at or before its test fold starts;
//! - each test fold is non-empty and ends within the dataset;
//! - the gap between training end and test start is at least `purge_rows + embargo_rows`, which
//!   is the label horizon plus the embargo (the sum is the stricter reading);
//! - test folds do not overlap.
//!
//! Fitted-state rules: the fitted range is non-empty, lies inside every fold's training range,
//! and therefore uses training rows only. A fitted state without folds cannot prove this and is
//! refused.
//!
//! Container (cache) format, version 1, little-endian:
//! `magic "QRLDSV01" | abi_version u32 | payload_len u64 | fnv1a64(payload) u64 | payload`.
//! FNV-1a detects every single-byte change and every truncation, so it guards against corruption.
//! It is not a tamper-proof digest and must not be read as one.

use super::batches::{BarBatch, BarColumns, Column, FeatureRowBlock, FeatureRowColumns};
use super::{check_abi_version, AbiError};

/// Magic bytes that open every cache container.
pub const CONTAINER_MAGIC: &[u8; 8] = b"QRLDSV01";

const HEADER_LEN: usize = 8 + 4 + 8 + 8;
const BAR_SCHEMA: &str = "market-event.v1";
const FEATURE_SCHEMA: &str = "feature-row.v1";
const TABLE: &str = "dataset_view";

/// One purged, embargoed walk-forward fold, as end-exclusive row ranges.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fold {
    /// First training row.
    pub train_start: usize,
    /// One past the last training row.
    pub train_end: usize,
    /// First test row.
    pub test_start: usize,
    /// One past the last test row.
    pub test_end: usize,
    /// Label horizon in rows, removed before the test fold.
    pub purge_rows: usize,
    /// Embargo in rows, removed before the test fold.
    pub embargo_rows: usize,
}

/// Reference to a state fitted on training rows only (for example normalization statistics).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FittedState {
    /// Identity of the fitted state; must not be empty.
    pub state_id: String,
    /// First row the state was fitted on.
    pub fit_start: usize,
    /// One past the last row the state was fitted on.
    pub fit_end: usize,
}

/// Immutable, validated dataset: bars, aligned feature rows, folds and an optional fitted state.
#[derive(Debug, Clone, PartialEq)]
pub struct DatasetView {
    bars: BarBatch,
    features: FeatureRowBlock,
    folds: Vec<Fold>,
    fitted: Option<FittedState>,
    content_hash: u64,
}

fn rule(row: usize, rule: &'static str) -> AbiError {
    AbiError::Rule {
        table: TABLE,
        row,
        rule,
    }
}

fn check_folds(folds: &[Fold], rows: usize) -> Result<(), AbiError> {
    for (index, fold) in folds.iter().enumerate() {
        if fold.train_start >= fold.train_end {
            return Err(rule(index, "training range must be non-empty"));
        }
        if fold.train_end > fold.test_start {
            return Err(rule(
                index,
                "training range must end before its test fold starts",
            ));
        }
        if fold.test_start >= fold.test_end {
            return Err(rule(index, "test fold must be non-empty"));
        }
        if fold.test_end > rows {
            return Err(rule(index, "test fold exceeds the dataset"));
        }
        let gap = fold.test_start - fold.train_end;
        let required = fold
            .purge_rows
            .checked_add(fold.embargo_rows)
            .ok_or(AbiError::Length {
                column: "purge_rows",
                expected: usize::MAX,
                found: fold.purge_rows,
            })?;
        if gap < required {
            return Err(rule(
                index,
                "purge and embargo must fit between training end and test start",
            ));
        }
    }
    let mut order: Vec<usize> = (0..folds.len()).collect();
    order.sort_by_key(|&index| folds[index].test_start);
    for pair in order.windows(2) {
        let (earlier, later) = (folds[pair[0]], folds[pair[1]]);
        if earlier.test_end > later.test_start {
            return Err(rule(pair[1], "test folds must not overlap"));
        }
    }
    Ok(())
}

fn check_fitted(fitted: &FittedState, folds: &[Fold], rows: usize) -> Result<(), AbiError> {
    if fitted.state_id.trim().is_empty() {
        return Err(AbiError::EmptyIdentity {
            field: "fitted_state_id",
        });
    }
    if folds.is_empty() {
        return Err(rule(
            0,
            "a fitted state requires folds to prove it uses training rows only",
        ));
    }
    if fitted.fit_start >= fitted.fit_end {
        return Err(rule(0, "fitted range must be non-empty"));
    }
    if fitted.fit_end > rows {
        return Err(rule(0, "fitted range exceeds the dataset"));
    }
    for (index, fold) in folds.iter().enumerate() {
        if fitted.fit_start < fold.train_start || fitted.fit_end > fold.train_end {
            return Err(rule(
                index,
                "fitted state uses rows outside this fold's training range",
            ));
        }
    }
    Ok(())
}

fn fnv1a64(bytes: &[u8]) -> u64 {
    const OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
    const PRIME: u64 = 0x0000_0100_0000_01b3;
    bytes.iter().fold(OFFSET, |hash, &byte| {
        (hash ^ u64::from(byte)).wrapping_mul(PRIME)
    })
}

impl DatasetView {
    /// Validates the parts and returns an immutable view.
    ///
    /// Bars and features must share an instrument, a row count and identical decision times.
    /// Folds and the fitted-state reference must satisfy the rules in the module documentation.
    pub fn try_new(
        bars: BarBatch,
        features: FeatureRowBlock,
        folds: Vec<Fold>,
        fitted: Option<FittedState>,
    ) -> Result<Self, AbiError> {
        if bars.instrument_id() != features.instrument_id() {
            return Err(rule(0, "bar and feature instruments differ"));
        }
        if bars.rows() != features.rows() {
            return Err(AbiError::Length {
                column: "features",
                expected: bars.rows(),
                found: features.rows(),
            });
        }
        for (row, (bar_time, feature_time)) in bars
            .event_time_ns()
            .iter()
            .zip(features.event_time_ns())
            .enumerate()
        {
            if bar_time != feature_time {
                return Err(rule(row, "feature and bar decision clocks differ"));
            }
        }
        let rows = bars.rows();
        check_folds(&folds, rows)?;
        if let Some(state) = &fitted {
            check_fitted(state, &folds, rows)?;
        }
        let mut view = Self {
            bars,
            features,
            folds,
            fitted,
            content_hash: 0,
        };
        view.content_hash = fnv1a64(&view.payload());
        Ok(view)
    }

    /// Number of aligned rows.
    pub fn rows(&self) -> usize {
        self.bars.rows()
    }

    /// Validated bar batch.
    pub fn bars(&self) -> &BarBatch {
        &self.bars
    }

    /// Validated feature-row block aligned with the bars.
    pub fn features(&self) -> &FeatureRowBlock {
        &self.features
    }

    /// Walk-forward folds, in the order given.
    pub fn folds(&self) -> &[Fold] {
        &self.folds
    }

    /// Fitted-state reference, if any.
    pub fn fitted(&self) -> Option<&FittedState> {
        self.fitted.as_ref()
    }

    /// FNV-1a digest of the canonical payload. Equal views have equal digests in every process.
    pub fn content_hash(&self) -> u64 {
        self.content_hash
    }

    /// Serializes the view into a checksummed cache container.
    pub fn to_bytes(&self) -> Vec<u8> {
        let payload = self.payload();
        let mut out = Vec::with_capacity(HEADER_LEN + payload.len());
        out.extend_from_slice(CONTAINER_MAGIC);
        out.extend_from_slice(&super::SHARED_DATA_ABI_VERSION.to_le_bytes());
        out.extend_from_slice(&(payload.len() as u64).to_le_bytes());
        out.extend_from_slice(&fnv1a64(&payload).to_le_bytes());
        out.extend_from_slice(&payload);
        out
    }

    /// Decodes and re-validates a cache container. Any corruption is refused, never repaired.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, AbiError> {
        if bytes.len() < HEADER_LEN {
            return Err(AbiError::Cache {
                reason: "container is shorter than its header",
            });
        }
        if &bytes[..8] != CONTAINER_MAGIC {
            return Err(AbiError::Cache {
                reason: "bad magic bytes",
            });
        }
        let version = u32::from_le_bytes(bytes[8..12].try_into().unwrap_or([0; 4]));
        check_abi_version(version)?;
        let payload_len = u64::from_le_bytes(bytes[12..20].try_into().unwrap_or([0; 8]));
        let stored = u64::from_le_bytes(bytes[20..28].try_into().unwrap_or([0; 8]));
        let payload = &bytes[HEADER_LEN..];
        if u64::try_from(payload.len()).ok() != Some(payload_len) {
            return Err(AbiError::Cache {
                reason: "payload length does not match the container (truncated or extended)",
            });
        }
        if fnv1a64(payload) != stored {
            return Err(AbiError::Cache {
                reason: "checksum mismatch",
            });
        }
        let mut reader = Reader { data: payload };
        let view = reader.view()?;
        if !reader.data.is_empty() {
            return Err(AbiError::Cache {
                reason: "trailing bytes after the payload",
            });
        }
        Ok(view)
    }

    fn payload(&self) -> Vec<u8> {
        let mut out = Vec::new();
        let bars = &self.bars;
        put_str(&mut out, bars.instrument_id());
        put_str(&mut out, bars.source_id());
        put_i64s(&mut out, bars.event_time_ns());
        put_i64s(&mut out, bars.close_time_ns());
        put_i64s(&mut out, bars.available_at_ns());
        put_i64s(&mut out, bars.source_sequence());
        put_f64s(&mut out, bars.open());
        put_f64s(&mut out, bars.high());
        put_f64s(&mut out, bars.low());
        put_f64s(&mut out, bars.close());
        put_f64s(&mut out, bars.volume().values());
        put_bools(&mut out, bars.volume().valid());

        let features = &self.features;
        put_str(&mut out, features.instrument_id());
        put_str(&mut out, features.feature_set_id());
        put_str(&mut out, features.feature_version());
        put_str(&mut out, features.content_hash());
        put_u64(&mut out, features.width() as u64);
        put_i64s(&mut out, features.event_time_ns());
        put_i64s(&mut out, features.available_at_ns());
        put_bools(&mut out, features.session_eligible());
        put_f64s(&mut out, features.values().values());
        put_bools(&mut out, features.values().valid());

        put_u64(&mut out, self.folds.len() as u64);
        for fold in &self.folds {
            for value in [
                fold.train_start,
                fold.train_end,
                fold.test_start,
                fold.test_end,
                fold.purge_rows,
                fold.embargo_rows,
            ] {
                put_u64(&mut out, value as u64);
            }
        }
        match &self.fitted {
            None => out.push(0),
            Some(state) => {
                out.push(1);
                put_str(&mut out, &state.state_id);
                put_u64(&mut out, state.fit_start as u64);
                put_u64(&mut out, state.fit_end as u64);
            }
        }
        out
    }
}

fn put_u64(out: &mut Vec<u8>, value: u64) {
    out.extend_from_slice(&value.to_le_bytes());
}

fn put_str(out: &mut Vec<u8>, text: &str) {
    put_u64(out, text.len() as u64);
    out.extend_from_slice(text.as_bytes());
}

fn put_i64s(out: &mut Vec<u8>, values: &[i64]) {
    put_u64(out, values.len() as u64);
    for value in values {
        out.extend_from_slice(&value.to_le_bytes());
    }
}

fn put_f64s(out: &mut Vec<u8>, values: &[f64]) {
    put_u64(out, values.len() as u64);
    for value in values {
        out.extend_from_slice(&value.to_le_bytes());
    }
}

fn put_bools(out: &mut Vec<u8>, values: &[bool]) {
    put_u64(out, values.len() as u64);
    out.extend(values.iter().map(|&value| u8::from(value)));
}

/// Bounds-checked reader over a payload. Every read is checked against the remaining bytes.
struct Reader<'a> {
    data: &'a [u8],
}

fn corrupt(reason: &'static str) -> AbiError {
    AbiError::Cache { reason }
}

impl Reader<'_> {
    fn take(&mut self, count: usize) -> Result<&[u8], AbiError> {
        if count > self.data.len() {
            return Err(corrupt("payload ends inside a field"));
        }
        let (head, tail) = self.data.split_at(count);
        self.data = tail;
        Ok(head)
    }

    fn u64(&mut self) -> Result<u64, AbiError> {
        let bytes = self.take(8)?;
        Ok(u64::from_le_bytes(bytes.try_into().unwrap_or([0; 8])))
    }

    fn usize(&mut self) -> Result<usize, AbiError> {
        usize::try_from(self.u64()?).map_err(|_| corrupt("count does not fit in memory"))
    }

    /// Reads an element count and checks that `count * width` bytes remain.
    fn count(&mut self, width: usize) -> Result<usize, AbiError> {
        let count = self.usize()?;
        match count.checked_mul(width) {
            Some(bytes) if bytes <= self.data.len() => Ok(count),
            _ => Err(corrupt("section is longer than the payload")),
        }
    }

    fn string(&mut self) -> Result<String, AbiError> {
        let len = self.count(1)?;
        let bytes = self.take(len)?;
        String::from_utf8(bytes.to_vec()).map_err(|_| corrupt("identity is not valid UTF-8"))
    }

    fn i64s(&mut self) -> Result<Vec<i64>, AbiError> {
        let count = self.count(8)?;
        let (chunks, _) = self.take(count * 8)?.as_chunks::<8>();
        Ok(chunks
            .iter()
            .map(|chunk| i64::from_le_bytes(*chunk))
            .collect())
    }

    fn f64s(&mut self) -> Result<Vec<f64>, AbiError> {
        let count = self.count(8)?;
        let (chunks, _) = self.take(count * 8)?.as_chunks::<8>();
        Ok(chunks
            .iter()
            .map(|chunk| f64::from_le_bytes(*chunk))
            .collect())
    }

    fn bools(&mut self) -> Result<Vec<u8>, AbiError> {
        let count = self.count(1)?;
        Ok(self.take(count)?.to_vec())
    }

    fn view(&mut self) -> Result<DatasetView, AbiError> {
        let instrument = self.string()?;
        let source = self.string()?;
        let bar_event = self.i64s()?;
        let bar_close = self.i64s()?;
        let bar_available = self.i64s()?;
        let bar_sequence = self.i64s()?;
        let open = self.f64s()?;
        let high = self.f64s()?;
        let low = self.f64s()?;
        let close = self.f64s()?;
        let volume = self.f64s()?;
        let volume_valid = self.bools()?;
        let bars = BarBatch::try_new(
            BAR_SCHEMA,
            &instrument,
            &source,
            BarColumns {
                event_time_ns: Column::vector(bar_event),
                close_time_ns: Column::vector(bar_close),
                available_at_ns: Column::vector(bar_available),
                source_sequence: Column::vector(bar_sequence),
                open: Column::vector(open),
                high: Column::vector(high),
                low: Column::vector(low),
                close: Column::vector(close),
                volume: Column::vector(volume),
                volume_valid: Column::vector(volume_valid),
            },
        )?;

        let feature_instrument = self.string()?;
        let feature_set = self.string()?;
        let feature_version = self.string()?;
        let feature_hash = self.string()?;
        let width = self.usize()?;
        let feature_event = self.i64s()?;
        let feature_available = self.i64s()?;
        let session = self.bools()?;
        let values = self.f64s()?;
        let values_valid = self.bools()?;
        let rows = feature_event.len();
        let features = FeatureRowBlock::try_new(
            FEATURE_SCHEMA,
            &feature_instrument,
            &feature_set,
            &feature_version,
            &feature_hash,
            width,
            FeatureRowColumns {
                event_time_ns: Column::vector(feature_event),
                available_at_ns: Column::vector(feature_available),
                session_eligible: Column::vector(session),
                values: Column::matrix(rows, width, values),
                values_valid: Column::matrix(rows, width, values_valid),
            },
        )?;

        let fold_count = self.count(48)?;
        let mut folds = Vec::with_capacity(fold_count);
        for _ in 0..fold_count {
            folds.push(Fold {
                train_start: self.usize()?,
                train_end: self.usize()?,
                test_start: self.usize()?,
                test_end: self.usize()?,
                purge_rows: self.usize()?,
                embargo_rows: self.usize()?,
            });
        }
        let fitted = match self.take(1)?[0] {
            0 => None,
            1 => Some(FittedState {
                state_id: self.string()?,
                fit_start: self.usize()?,
                fit_end: self.usize()?,
            }),
            _ => return Err(corrupt("fitted-state flag is neither 0 nor 1")),
        };
        DatasetView::try_new(bars, features, folds, fitted)
    }
}
