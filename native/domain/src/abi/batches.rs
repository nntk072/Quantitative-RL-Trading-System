//! Validated batches. A constructor either returns a batch that satisfies every rule of its
//! payload or returns the first refusal in row order. Nothing is filled or repaired.
//!
//! Shape rules are checked before value rules, and value rules before record rules, so that a
//! refusal always names the most basic defect first.

use super::{observation_width, AbiError, SchemaId};

/// An owned, row-major array as copied from the caller, with its shape.
///
/// The data length must equal the product of the shape; this is checked by the constructors.
#[derive(Debug, Clone, PartialEq)]
pub struct Column<T> {
    /// Dimensions, outermost first. A vector has one dimension; a feature matrix has two.
    pub shape: Vec<usize>,
    /// Elements in row-major order.
    pub data: Vec<T>,
}

impl<T> Column<T> {
    /// A one-dimensional column.
    pub fn vector(data: Vec<T>) -> Self {
        Self {
            shape: vec![data.len()],
            data,
        }
    }

    /// A two-dimensional row-major column of `rows` by `cols`.
    pub fn matrix(rows: usize, cols: usize, data: Vec<T>) -> Self {
        Self {
            shape: vec![rows, cols],
            data,
        }
    }
}

/// Nullable `float64` values with their presence mask. A missing slot holds NaN.
#[derive(Debug, Clone, PartialEq)]
pub struct NullableF64 {
    values: Vec<f64>,
    valid: Vec<bool>,
}

impl NullableF64 {
    /// The stored values, NaN at missing slots.
    pub fn values(&self) -> &[f64] {
        &self.values
    }

    /// Presence mask, `true` where a value is present.
    pub fn valid(&self) -> &[bool] {
        &self.valid
    }
}

#[derive(Clone, Copy)]
enum Bound {
    Any,
    Positive,
    NonNegative,
}

fn check_identity(field: &'static str, value: &str) -> Result<(), AbiError> {
    if value.trim().is_empty() {
        Err(AbiError::EmptyIdentity { field })
    } else {
        Ok(())
    }
}

fn check_schema(
    found: &str,
    accepted: &[SchemaId],
    accepted_names: &'static str,
) -> Result<SchemaId, AbiError> {
    match SchemaId::parse(found) {
        Some(schema) if accepted.contains(&schema) => Ok(schema),
        _ => Err(AbiError::UnsupportedSchema {
            found: found.to_owned(),
            accepted: accepted_names,
        }),
    }
}

fn check_layout<T>(column: &'static str, input: &Column<T>, rank: usize) -> Result<(), AbiError> {
    if input.shape.len() != rank {
        return Err(AbiError::Rank {
            column,
            expected: rank,
            found: input.shape.len(),
        });
    }
    let elements = input
        .shape
        .iter()
        .try_fold(1_usize, |acc, &dim| acc.checked_mul(dim));
    if elements != Some(input.data.len()) {
        return Err(AbiError::Length {
            column,
            expected: elements.unwrap_or(usize::MAX),
            found: input.data.len(),
        });
    }
    Ok(())
}

/// A rank-1 column, optionally required to have `rows` elements.
fn vector<'a, T>(
    column: &'static str,
    input: &'a Column<T>,
    rows: Option<usize>,
) -> Result<&'a [T], AbiError> {
    check_layout(column, input, 1)?;
    if let Some(expected) = rows {
        if input.data.len() != expected {
            return Err(AbiError::Length {
                column,
                expected,
                found: input.data.len(),
            });
        }
    }
    Ok(&input.data)
}

/// A rank-2 row-major column with `rows` rows and `width` columns.
fn matrix<'a, T>(
    column: &'static str,
    input: &'a Column<T>,
    rows: usize,
    width: usize,
) -> Result<&'a [T], AbiError> {
    check_layout(column, input, 2)?;
    if input.shape[0] != rows {
        return Err(AbiError::Length {
            column,
            expected: rows,
            found: input.shape[0],
        });
    }
    if input.shape[1] != width {
        return Err(AbiError::Width {
            column,
            expected: width,
            found: input.shape[1],
        });
    }
    Ok(&input.data)
}

fn to_mask(column: &'static str, values: &[u8]) -> Result<Vec<bool>, AbiError> {
    values
        .iter()
        .enumerate()
        .map(|(row, &value)| match value {
            0 => Ok(false),
            1 => Ok(true),
            _ => Err(AbiError::Mask { column, row }),
        })
        .collect()
}

fn check_present(
    column: &'static str,
    row: usize,
    value: f64,
    bound: Bound,
) -> Result<(), AbiError> {
    if !value.is_finite() {
        return Err(AbiError::NonFinite { column, row });
    }
    match bound {
        Bound::Any => Ok(()),
        Bound::Positive if value <= 0.0 => Err(AbiError::NotPositive { column, row }),
        Bound::NonNegative if value < 0.0 => Err(AbiError::Negative { column, row }),
        Bound::Positive | Bound::NonNegative => Ok(()),
    }
}

fn check_required(column: &'static str, values: &[f64], bound: Bound) -> Result<(), AbiError> {
    values
        .iter()
        .enumerate()
        .try_for_each(|(row, &value)| check_present(column, row, value, bound))
}

/// Checks a nullable column stored row-major with `width` values per row (1 for a vector).
/// The row reported in a refusal is the row of the element, not its flat index.
fn check_nullable(
    column: &'static str,
    values: &[f64],
    valid: &[bool],
    bound: Bound,
    width: usize,
) -> Result<(), AbiError> {
    values
        .iter()
        .zip(valid)
        .enumerate()
        .try_for_each(|(index, (&value, &present))| {
            let row = index / width;
            if present {
                check_present(column, row, value, bound)
            } else if value.is_nan() {
                Ok(())
            } else {
                Err(AbiError::MissingNotNan { column, row })
            }
        })
}

fn nullable(values: Vec<f64>, valid: Vec<bool>) -> NullableF64 {
    NullableF64 { values, valid }
}

fn rule(table: &'static str, row: usize, rule: &'static str) -> AbiError {
    AbiError::Rule { table, row, rule }
}

/// Requires `values[row]` to be strictly greater than `values[row - 1]` for every row.
fn strictly_increasing(
    table: &'static str,
    values: &[i64],
    message: &'static str,
) -> Result<(), AbiError> {
    values.windows(2).enumerate().try_for_each(|(index, pair)| {
        if pair[1] > pair[0] {
            Ok(())
        } else {
            Err(rule(table, index + 1, message))
        }
    })
}

fn non_decreasing(
    table: &'static str,
    values: &[i64],
    message: &'static str,
) -> Result<(), AbiError> {
    values.windows(2).enumerate().try_for_each(|(index, pair)| {
        if pair[1] >= pair[0] {
            Ok(())
        } else {
            Err(rule(table, index + 1, message))
        }
    })
}

fn non_empty(rows: usize) -> Result<usize, AbiError> {
    if rows == 0 {
        Err(AbiError::EmptyBatch)
    } else {
        Ok(rows)
    }
}

/// Input columns of a quote batch, named as in [`super::layout`].
#[derive(Debug, Clone, PartialEq)]
pub struct QuoteColumns {
    /// Event time, UTC nanoseconds.
    pub event_time_ns: Column<i64>,
    /// Availability time, UTC nanoseconds.
    pub available_at_ns: Column<i64>,
    /// Source sequence, strictly increasing.
    pub source_sequence: Column<i64>,
    /// Bid price (nullable).
    pub bid: Column<f64>,
    /// Bid validity mask, `bid_valid`.
    pub bid_valid: Column<u8>,
    /// Ask price (nullable).
    pub ask: Column<f64>,
    /// Ask validity mask, `ask_valid`.
    pub ask_valid: Column<u8>,
    /// Bid size (nullable).
    pub bid_size: Column<f64>,
    /// Bid size validity mask, `bid_size_valid`.
    pub bid_size_valid: Column<u8>,
    /// Ask size (nullable).
    pub ask_size: Column<f64>,
    /// Ask size validity mask, `ask_size_valid`.
    pub ask_size_valid: Column<u8>,
    /// Source flag bits, opaque to the kernels.
    pub source_flags: Column<i32>,
}

/// A validated, owned quote batch for one instrument.
#[derive(Debug, Clone, PartialEq)]
pub struct QuoteBatch {
    schema: SchemaId,
    instrument_id: String,
    source_id: String,
    event_time_ns: Vec<i64>,
    available_at_ns: Vec<i64>,
    source_sequence: Vec<i64>,
    bid: NullableF64,
    ask: NullableF64,
    bid_size: NullableF64,
    ask_size: NullableF64,
    source_flags: Vec<i32>,
}

impl QuoteBatch {
    /// Validates and takes ownership of quote columns.
    ///
    /// Rules: `market-event.v1`; non-empty identities; present prices strictly positive and
    /// sizes non-negative; `bid <= ask` when both are present; `available_at >= event_time`;
    /// `source_sequence` strictly increasing; `event_time` non-decreasing.
    pub fn try_new(
        schema_id: &str,
        instrument_id: &str,
        source_id: &str,
        columns: QuoteColumns,
    ) -> Result<Self, AbiError> {
        let schema = check_schema(schema_id, &[SchemaId::MarketEventV1], "market-event.v1")?;
        check_identity("instrument_id", instrument_id)?;
        check_identity("source_id", source_id)?;

        let event = vector("event_time_ns", &columns.event_time_ns, None)?;
        let rows = non_empty(event.len())?;
        let available = vector("available_at_ns", &columns.available_at_ns, Some(rows))?;
        let sequence = vector("source_sequence", &columns.source_sequence, Some(rows))?;
        let bid = vector("bid", &columns.bid, Some(rows))?;
        let bid_valid = to_mask(
            "bid_valid",
            vector("bid_valid", &columns.bid_valid, Some(rows))?,
        )?;
        let ask = vector("ask", &columns.ask, Some(rows))?;
        let ask_valid = to_mask(
            "ask_valid",
            vector("ask_valid", &columns.ask_valid, Some(rows))?,
        )?;
        let bid_size = vector("bid_size", &columns.bid_size, Some(rows))?;
        let bid_size_valid = to_mask(
            "bid_size_valid",
            vector("bid_size_valid", &columns.bid_size_valid, Some(rows))?,
        )?;
        let ask_size = vector("ask_size", &columns.ask_size, Some(rows))?;
        let ask_size_valid = to_mask(
            "ask_size_valid",
            vector("ask_size_valid", &columns.ask_size_valid, Some(rows))?,
        )?;
        let source_flags = vector("source_flags", &columns.source_flags, Some(rows))?;

        check_nullable("bid", bid, &bid_valid, Bound::Positive, 1)?;
        check_nullable("ask", ask, &ask_valid, Bound::Positive, 1)?;
        check_nullable("bid_size", bid_size, &bid_size_valid, Bound::NonNegative, 1)?;
        check_nullable("ask_size", ask_size, &ask_size_valid, Bound::NonNegative, 1)?;

        for row in 0..rows {
            if bid_valid[row] && ask_valid[row] && bid[row] > ask[row] {
                return Err(rule("quote", row, "bid exceeds ask"));
            }
            if available[row] < event[row] {
                return Err(rule("quote", row, "available_at precedes event_time"));
            }
        }
        strictly_increasing("quote", sequence, "source_sequence must strictly increase")?;
        non_decreasing("quote", event, "event_time must not decrease")?;

        Ok(Self {
            schema,
            instrument_id: instrument_id.to_owned(),
            source_id: source_id.to_owned(),
            event_time_ns: event.to_vec(),
            available_at_ns: available.to_vec(),
            source_sequence: sequence.to_vec(),
            bid: nullable(bid.to_vec(), bid_valid),
            ask: nullable(ask.to_vec(), ask_valid),
            bid_size: nullable(bid_size.to_vec(), bid_size_valid),
            ask_size: nullable(ask_size.to_vec(), ask_size_valid),
            source_flags: source_flags.to_vec(),
        })
    }

    /// Number of quote rows.
    pub fn rows(&self) -> usize {
        self.event_time_ns.len()
    }

    /// Schema identity the batch was accepted under.
    pub fn schema(&self) -> SchemaId {
        self.schema
    }

    /// Instrument identity.
    pub fn instrument_id(&self) -> &str {
        &self.instrument_id
    }

    /// Source identity.
    pub fn source_id(&self) -> &str {
        &self.source_id
    }

    /// Event times, UTC nanoseconds.
    pub fn event_time_ns(&self) -> &[i64] {
        &self.event_time_ns
    }

    /// Availability times, UTC nanoseconds.
    pub fn available_at_ns(&self) -> &[i64] {
        &self.available_at_ns
    }

    /// Source sequences.
    pub fn source_sequence(&self) -> &[i64] {
        &self.source_sequence
    }

    /// Bid column.
    pub fn bid(&self) -> &NullableF64 {
        &self.bid
    }

    /// Ask column.
    pub fn ask(&self) -> &NullableF64 {
        &self.ask
    }

    /// Bid size column.
    pub fn bid_size(&self) -> &NullableF64 {
        &self.bid_size
    }

    /// Ask size column.
    pub fn ask_size(&self) -> &NullableF64 {
        &self.ask_size
    }

    /// Source flag bits.
    pub fn source_flags(&self) -> &[i32] {
        &self.source_flags
    }
}

/// Input columns of a bar batch, named as in [`super::layout`].
#[derive(Debug, Clone, PartialEq)]
pub struct BarColumns {
    /// Bar open time, UTC nanoseconds.
    pub event_time_ns: Column<i64>,
    /// Bar close time, UTC nanoseconds.
    pub close_time_ns: Column<i64>,
    /// Availability time, UTC nanoseconds; not before close.
    pub available_at_ns: Column<i64>,
    /// Source sequence, strictly increasing.
    pub source_sequence: Column<i64>,
    /// Open price.
    pub open: Column<f64>,
    /// High price.
    pub high: Column<f64>,
    /// Low price.
    pub low: Column<f64>,
    /// Close price.
    pub close: Column<f64>,
    /// Tick volume (nullable).
    pub volume: Column<f64>,
    /// Volume validity mask, `volume_valid`.
    pub volume_valid: Column<u8>,
}

/// A validated, owned OHLC bar batch for one instrument.
#[derive(Debug, Clone, PartialEq)]
pub struct BarBatch {
    instrument_id: String,
    source_id: String,
    event_time_ns: Vec<i64>,
    close_time_ns: Vec<i64>,
    available_at_ns: Vec<i64>,
    source_sequence: Vec<i64>,
    open: Vec<f64>,
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    volume: NullableF64,
}

impl BarBatch {
    /// Validates and takes ownership of bar columns.
    ///
    /// Rules: `market-event.v1` only (`market-event.v2` carries a revision and must be resolved
    /// to a v1 view first); OHLC finite and positive; volume non-negative when present; OHLC
    /// bounds; `close_time > event_time`; `available_at >= close_time`; `event_time` and
    /// `source_sequence` strictly increasing.
    pub fn try_new(
        schema_id: &str,
        instrument_id: &str,
        source_id: &str,
        columns: BarColumns,
    ) -> Result<Self, AbiError> {
        check_schema(schema_id, &[SchemaId::MarketEventV1], "market-event.v1")?;
        check_identity("instrument_id", instrument_id)?;
        check_identity("source_id", source_id)?;

        let event = vector("event_time_ns", &columns.event_time_ns, None)?;
        let rows = non_empty(event.len())?;
        let close_time = vector("close_time_ns", &columns.close_time_ns, Some(rows))?;
        let available = vector("available_at_ns", &columns.available_at_ns, Some(rows))?;
        let sequence = vector("source_sequence", &columns.source_sequence, Some(rows))?;
        let open = vector("open", &columns.open, Some(rows))?;
        let high = vector("high", &columns.high, Some(rows))?;
        let low = vector("low", &columns.low, Some(rows))?;
        let close = vector("close", &columns.close, Some(rows))?;
        let volume = vector("volume", &columns.volume, Some(rows))?;
        let volume_valid = to_mask(
            "volume_valid",
            vector("volume_valid", &columns.volume_valid, Some(rows))?,
        )?;

        check_required("open", open, Bound::Positive)?;
        check_required("high", high, Bound::Positive)?;
        check_required("low", low, Bound::Positive)?;
        check_required("close", close, Bound::Positive)?;
        check_nullable("volume", volume, &volume_valid, Bound::NonNegative, 1)?;

        for row in 0..rows {
            if close_time[row] <= event[row] {
                return Err(rule("bar", row, "close_time must follow event_time"));
            }
            if available[row] < close_time[row] {
                return Err(rule(
                    "bar",
                    row,
                    "available_at precedes close_time (incomplete bar)",
                ));
            }
            let (o, h, l, c) = (open[row], high[row], low[row], close[row]);
            if h < o.max(c).max(l) || l > o.min(c).min(h) {
                return Err(rule("bar", row, "OHLC bounds violated"));
            }
        }
        strictly_increasing("bar", event, "event_time must strictly increase")?;
        strictly_increasing("bar", sequence, "source_sequence must strictly increase")?;

        Ok(Self {
            instrument_id: instrument_id.to_owned(),
            source_id: source_id.to_owned(),
            event_time_ns: event.to_vec(),
            close_time_ns: close_time.to_vec(),
            available_at_ns: available.to_vec(),
            source_sequence: sequence.to_vec(),
            open: open.to_vec(),
            high: high.to_vec(),
            low: low.to_vec(),
            close: close.to_vec(),
            volume: nullable(volume.to_vec(), volume_valid),
        })
    }

    /// Number of bar rows.
    pub fn rows(&self) -> usize {
        self.event_time_ns.len()
    }

    /// Instrument identity.
    pub fn instrument_id(&self) -> &str {
        &self.instrument_id
    }

    /// Source identity.
    pub fn source_id(&self) -> &str {
        &self.source_id
    }

    /// Bar open times, UTC nanoseconds.
    pub fn event_time_ns(&self) -> &[i64] {
        &self.event_time_ns
    }

    /// Bar close times, UTC nanoseconds.
    pub fn close_time_ns(&self) -> &[i64] {
        &self.close_time_ns
    }

    /// Availability times, UTC nanoseconds.
    pub fn available_at_ns(&self) -> &[i64] {
        &self.available_at_ns
    }

    /// Source sequences.
    pub fn source_sequence(&self) -> &[i64] {
        &self.source_sequence
    }

    /// Open prices.
    pub fn open(&self) -> &[f64] {
        &self.open
    }

    /// High prices.
    pub fn high(&self) -> &[f64] {
        &self.high
    }

    /// Low prices.
    pub fn low(&self) -> &[f64] {
        &self.low
    }

    /// Close prices.
    pub fn close(&self) -> &[f64] {
        &self.close
    }

    /// Tick volume column.
    pub fn volume(&self) -> &NullableF64 {
        &self.volume
    }
}

/// Input columns of a feature-row block, named as in [`super::layout`].
#[derive(Debug, Clone, PartialEq)]
pub struct FeatureRowColumns {
    /// Decision-clock time, UTC nanoseconds.
    pub event_time_ns: Column<i64>,
    /// Feature availability time, UTC nanoseconds.
    pub available_at_ns: Column<i64>,
    /// Session eligibility mask, 1 = eligible.
    pub session_eligible: Column<u8>,
    /// Feature values, shape (rows, width). Missing values are NaN.
    pub values: Column<f64>,
    /// Feature presence mask, shape (rows, width), `values_valid`.
    pub values_valid: Column<u8>,
}

/// A validated, owned feature-row block for one feature set.
#[derive(Debug, Clone, PartialEq)]
pub struct FeatureRowBlock {
    instrument_id: String,
    feature_set_id: String,
    feature_version: String,
    content_hash: String,
    width: usize,
    event_time_ns: Vec<i64>,
    available_at_ns: Vec<i64>,
    session_eligible: Vec<bool>,
    values: NullableF64,
}

impl FeatureRowBlock {
    /// Validates and takes ownership of feature-row columns.
    ///
    /// `width` is the number of names in the feature-set manifest; a different matrix width is
    /// refused. Rules: `feature-row.v1`; non-empty identities including `content_hash`;
    /// present feature values finite; `available_at <= event_time`; `event_time` strictly
    /// increasing.
    pub fn try_new(
        schema_id: &str,
        instrument_id: &str,
        feature_set_id: &str,
        feature_version: &str,
        content_hash: &str,
        width: usize,
        columns: FeatureRowColumns,
    ) -> Result<Self, AbiError> {
        check_schema(schema_id, &[SchemaId::FeatureRowV1], "feature-row.v1")?;
        check_identity("instrument_id", instrument_id)?;
        check_identity("feature_set_id", feature_set_id)?;
        check_identity("feature_version", feature_version)?;
        check_identity("content_hash", content_hash)?;
        if width == 0 {
            return Err(AbiError::Width {
                column: "values",
                expected: 1,
                found: 0,
            });
        }

        let event = vector("event_time_ns", &columns.event_time_ns, None)?;
        let rows = non_empty(event.len())?;
        let available = vector("available_at_ns", &columns.available_at_ns, Some(rows))?;
        let session = to_mask(
            "session_eligible",
            vector("session_eligible", &columns.session_eligible, Some(rows))?,
        )?;
        let values = matrix("values", &columns.values, rows, width)?;
        let valid = to_mask(
            "values_valid",
            matrix("values_valid", &columns.values_valid, rows, width)?,
        )?;

        check_nullable("values", values, &valid, Bound::Any, width)?;

        for row in 0..rows {
            if available[row] > event[row] {
                return Err(rule(
                    "feature_row",
                    row,
                    "feature uses information available after its event_time",
                ));
            }
        }
        strictly_increasing("feature_row", event, "event_time must strictly increase")?;

        Ok(Self {
            instrument_id: instrument_id.to_owned(),
            feature_set_id: feature_set_id.to_owned(),
            feature_version: feature_version.to_owned(),
            content_hash: content_hash.to_owned(),
            width,
            event_time_ns: event.to_vec(),
            available_at_ns: available.to_vec(),
            session_eligible: session,
            values: nullable(values.to_vec(), valid),
        })
    }

    /// Number of decision rows.
    pub fn rows(&self) -> usize {
        self.event_time_ns.len()
    }

    /// Feature count per row, as declared by the manifest.
    pub fn width(&self) -> usize {
        self.width
    }

    /// Instrument identity.
    pub fn instrument_id(&self) -> &str {
        &self.instrument_id
    }

    /// Feature-set identity.
    pub fn feature_set_id(&self) -> &str {
        &self.feature_set_id
    }

    /// Feature-set version.
    pub fn feature_version(&self) -> &str {
        &self.feature_version
    }

    /// Content hash of the feature rows.
    pub fn content_hash(&self) -> &str {
        &self.content_hash
    }

    /// Decision times, UTC nanoseconds.
    pub fn event_time_ns(&self) -> &[i64] {
        &self.event_time_ns
    }

    /// Feature availability times, UTC nanoseconds.
    pub fn available_at_ns(&self) -> &[i64] {
        &self.available_at_ns
    }

    /// Session eligibility mask.
    pub fn session_eligible(&self) -> &[bool] {
        &self.session_eligible
    }

    /// Feature values, row-major (rows, width), with presence mask.
    pub fn values(&self) -> &NullableF64 {
        &self.values
    }
}

/// Input columns of an account observation window, named as in [`super::layout`].
#[derive(Debug, Clone, PartialEq)]
pub struct ObservationWindowColumns {
    /// Coordinates, shape (rows, width), float32.
    pub values: Column<f32>,
    /// Real-row mask, shape (rows,); 1 = real, 0 = left padding.
    pub mask: Column<u8>,
}

/// A validated, owned observation window.
#[derive(Debug, Clone, PartialEq)]
pub struct ObservationWindow {
    schema: SchemaId,
    width: usize,
    values: Vec<f32>,
    real: Vec<bool>,
}

impl ObservationWindow {
    /// Validates and takes ownership of an observation window.
    ///
    /// Rules: `account-state-v1` (width 6) or `account-state-v2` (width 28); every value finite;
    /// the mask is 0 or 1; padding is a left prefix (`0...0 1...1`); padded rows are all zero,
    /// which is the declared pad value of `pad_observation_window`. Nothing is padded or
    /// repaired by this constructor.
    pub fn try_new(schema_id: &str, columns: ObservationWindowColumns) -> Result<Self, AbiError> {
        let schema = check_schema(
            schema_id,
            &[SchemaId::AccountStateV1, SchemaId::AccountStateV2],
            "account-state-v1, account-state-v2",
        )?;
        let Some(width) = observation_width(schema) else {
            return Err(AbiError::UnsupportedSchema {
                found: schema_id.to_owned(),
                accepted: "account-state-v1, account-state-v2",
            });
        };
        let mask = vector("mask", &columns.mask, None)?;
        let rows = non_empty(mask.len())?;
        let values = matrix("values", &columns.values, rows, width)?;
        let real = to_mask("mask", mask)?;

        for (index, &value) in values.iter().enumerate() {
            let row = index / width;
            check_present("values", row, f64::from(value), Bound::Any)?;
        }
        for row in 0..rows {
            let padded = &values[row * width..(row + 1) * width];
            if !real[row] && padded.iter().any(|&value| value != 0.0) {
                return Err(rule("observation", row, "padded row must be all zero"));
            }
            if row > 0 && real[row - 1] && !real[row] {
                return Err(rule("observation", row, "padding must precede real rows"));
            }
        }

        Ok(Self {
            schema,
            width,
            values: values.to_vec(),
            real,
        })
    }

    /// Number of rows in the window.
    pub fn rows(&self) -> usize {
        self.real.len()
    }

    /// Coordinates per row, fixed by the schema.
    pub fn width(&self) -> usize {
        self.width
    }

    /// Schema identity.
    pub fn schema(&self) -> SchemaId {
        self.schema
    }

    /// Coordinates, row-major (rows, width).
    pub fn values(&self) -> &[f32] {
        &self.values
    }

    /// Real-row mask, `true` for real rows.
    pub fn real(&self) -> &[bool] {
        &self.real
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vector_helper_refuses_a_matrix() {
        let column = Column::matrix(1, 2, vec![1_i64, 2]);
        assert_eq!(
            vector("x", &column, None),
            Err(AbiError::Rank {
                column: "x",
                expected: 1,
                found: 2
            })
        );
    }

    #[test]
    fn shape_and_data_length_must_agree() {
        let column = Column {
            shape: vec![3],
            data: vec![1.0_f64, 2.0],
        };
        assert_eq!(
            check_layout("x", &column, 1),
            Err(AbiError::Length {
                column: "x",
                expected: 3,
                found: 2
            })
        );
    }

    #[test]
    fn mask_accepts_only_zero_and_one() {
        assert_eq!(to_mask("m", &[0, 1, 1]), Ok(vec![false, true, true]));
        assert_eq!(
            to_mask("m", &[0, 2]),
            Err(AbiError::Mask {
                column: "m",
                row: 1
            })
        );
    }

    #[test]
    fn missing_slot_must_hold_nan() {
        assert_eq!(
            check_nullable("bid", &[1.0, 0.0], &[true, false], Bound::Positive, 1),
            Err(AbiError::MissingNotNan {
                column: "bid",
                row: 1
            })
        );
        assert_eq!(
            check_nullable("bid", &[1.0, f64::NAN], &[true, false], Bound::Positive, 1),
            Ok(())
        );
    }
}
