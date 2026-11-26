//! Typed refusals of the shared data ABI.
//!
//! Every refusal names the column (and row, when one applies) so that the Python exception can
//! point at the offending input. Refusals are never converted into a default value.

use std::fmt;

/// A refused ABI input.
#[derive(Debug, Clone, PartialEq)]
pub enum AbiError {
    /// The ABI version is not the one this build implements.
    UnsupportedAbiVersion {
        /// Version presented by the caller.
        found: u32,
        /// Version implemented by this build.
        supported: u32,
    },
    /// The schema identity is unknown or is not an accepted schema for this payload.
    UnsupportedSchema {
        /// Schema identity presented by the caller.
        found: String,
        /// Schema identities accepted by the payload, for the message.
        accepted: &'static str,
    },
    /// A required identity field (instrument, source, feature set, version or hash) is empty.
    EmptyIdentity {
        /// Field name.
        field: &'static str,
    },
    /// A batch has no rows. An empty batch is refused rather than reported as an empty success.
    EmptyBatch,
    /// A required column is absent from the input mapping.
    MissingColumn {
        /// Column name.
        column: &'static str,
    },
    /// The input mapping carries a key that is not part of the payload layout.
    UnexpectedColumn {
        /// Key name.
        column: String,
    },
    /// An array's number of dimensions does not match the layout.
    Rank {
        /// Column name.
        column: &'static str,
        /// Rank required by the layout.
        expected: usize,
        /// Rank presented.
        found: usize,
    },
    /// An array's length or shape does not match the batch.
    Length {
        /// Column name.
        column: &'static str,
        /// Length or width required.
        expected: usize,
        /// Length or width presented.
        found: usize,
    },
    /// A feature or observation width differs from the declared width.
    Width {
        /// Column name.
        column: &'static str,
        /// Declared width.
        expected: usize,
        /// Width presented.
        found: usize,
    },
    /// The array's element type differs from the layout. Raised by the Python boundary.
    DType {
        /// Column name.
        column: &'static str,
        /// Dtype required by the layout.
        expected: &'static str,
        /// Buffer format string presented.
        found: String,
    },
    /// The array is not in native byte order. Raised by the Python boundary.
    NotNative {
        /// Column name.
        column: &'static str,
        /// Buffer format string presented.
        found: String,
    },
    /// The object does not expose the buffer protocol. Raised by the Python boundary.
    NotBuffer {
        /// Column name.
        column: &'static str,
    },
    /// The array is not C-contiguous (strided view or Fortran order). Refused, not copied.
    NotContiguous {
        /// Column name.
        column: &'static str,
    },
    /// The buffer could not be read as the declared element type. Raised by the Python boundary.
    Buffer {
        /// Column name.
        column: &'static str,
        /// Reason reported by the buffer protocol.
        reason: String,
    },
    /// A validity or mask value is not 0 or 1.
    Mask {
        /// Column name.
        column: &'static str,
        /// Row of the first invalid value.
        row: usize,
    },
    /// A present value is NaN or infinite.
    NonFinite {
        /// Column name.
        column: &'static str,
        /// Row index.
        row: usize,
    },
    /// A missing slot does not hold NaN, so it would be read as a sentinel value.
    MissingNotNan {
        /// Column name.
        column: &'static str,
        /// Row index.
        row: usize,
    },
    /// A present value must be strictly positive.
    NotPositive {
        /// Column name.
        column: &'static str,
        /// Row index.
        row: usize,
    },
    /// A present value must not be negative.
    Negative {
        /// Column name.
        column: &'static str,
        /// Row index.
        row: usize,
    },
    /// A cache container is truncated, corrupt, or malformed.
    Cache {
        /// Reason the container was refused.
        reason: &'static str,
    },
    /// A record-level rule failed (ordering, causality, OHLC bounds, padding and similar).
    Rule {
        /// Payload name.
        table: &'static str,
        /// Row index.
        row: usize,
        /// Rule that failed.
        rule: &'static str,
    },
}

impl fmt::Display for AbiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnsupportedAbiVersion { found, supported } => write!(
                f,
                "shared data ABI version {found} is not supported (this build implements {supported})"
            ),
            Self::UnsupportedSchema { found, accepted } => {
                write!(f, "unsupported schema_id {found:?}; accepted: {accepted}")
            }
            Self::EmptyIdentity { field } => write!(f, "{field} must be a non-empty string"),
            Self::EmptyBatch => write!(f, "batch must contain at least one row"),
            Self::MissingColumn { column } => write!(f, "missing column {column:?}"),
            Self::UnexpectedColumn { column } => {
                write!(f, "unexpected column {column:?} is not in the ABI layout")
            }
            Self::Rank {
                column,
                expected,
                found,
            } => write!(f, "{column}: expected {expected} dimension(s), found {found}"),
            Self::Length {
                column,
                expected,
                found,
            } => write!(f, "{column}: expected length {expected}, found {found}"),
            Self::Width {
                column,
                expected,
                found,
            } => write!(f, "{column}: expected width {expected}, found {found}"),
            Self::DType {
                column,
                expected,
                found,
            } => write!(f, "{column}: expected dtype {expected}, found buffer format {found:?}"),
            Self::NotNative { column, found } => write!(
                f,
                "{column}: only native byte order is accepted, found buffer format {found:?}"
            ),
            Self::NotBuffer { column } => {
                write!(f, "{column}: value must be a C-contiguous numpy-compatible array")
            }
            Self::NotContiguous { column } => write!(
                f,
                "{column}: array must be C-contiguous; copy it explicitly before the call"
            ),
            Self::Buffer { column, reason } => write!(f, "{column}: {reason}"),
            Self::Mask { column, row } => write!(f, "{column}[{row}]: mask values must be 0 or 1"),
            Self::NonFinite { column, row } => {
                write!(f, "{column}[{row}]: present values must be finite")
            }
            Self::MissingNotNan { column, row } => write!(
                f,
                "{column}[{row}]: a missing value must be NaN, not a sentinel number"
            ),
            Self::NotPositive { column, row } => {
                write!(f, "{column}[{row}]: value must be strictly positive")
            }
            Self::Negative { column, row } => write!(f, "{column}[{row}]: value must not be negative"),
            Self::Rule { table, row, rule } => write!(f, "{table}[{row}]: {rule}"),
            Self::Cache { reason } => write!(f, "cache container refused: {reason}"),
        }
    }
}

impl std::error::Error for AbiError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn messages_name_the_column_and_row() {
        let err = AbiError::NonFinite {
            column: "bid",
            row: 3,
        };
        assert_eq!(err.to_string(), "bid[3]: present values must be finite");
    }

    #[test]
    fn version_message_names_both_versions() {
        let err = AbiError::UnsupportedAbiVersion {
            found: 9,
            supported: 1,
        };
        assert!(err.to_string().contains("version 9"));
        assert!(err.to_string().contains("implements 1"));
    }
}
