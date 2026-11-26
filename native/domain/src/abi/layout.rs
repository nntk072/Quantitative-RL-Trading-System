//! Column layouts of each ABI payload: field order, dtype, rank, nullability and unit.
//!
//! The order below is the wire order. Python passes the same names as dictionary keys, and the
//! order is also what `qrl_native.abi_layout` reports. Identity fields (instrument, source,
//! schema, feature set) are scalars carried by each batch header, not columns.

/// Element type of a column.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Dtype {
    /// Signed 32-bit integer.
    Int32,
    /// Signed 64-bit integer.
    Int64,
    /// Unsigned byte. Used for validity and mask arrays with values 0 or 1 only.
    UInt8,
    /// IEEE-754 single precision.
    Float32,
    /// IEEE-754 double precision.
    Float64,
}

impl Dtype {
    /// NumPy-style dtype name.
    pub const fn name(self) -> &'static str {
        match self {
            Self::Int32 => "int32",
            Self::Int64 => "int64",
            Self::UInt8 => "uint8",
            Self::Float32 => "float32",
            Self::Float64 => "float64",
        }
    }
}

/// One column of a payload layout.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ColumnSpec {
    /// Column name. Nullable columns also take a `<name>_valid` companion array.
    pub name: &'static str,
    /// Element type.
    pub dtype: Dtype,
    /// Number of dimensions: 1 for a vector per row, 2 for a row-major matrix.
    pub rank: u8,
    /// Whether the column may hold missing values (carried by the `<name>_valid` companion).
    pub nullable: bool,
    /// Physical unit or meaning, stated once so both sides agree.
    pub unit: &'static str,
}

/// Payload kinds that cross the boundary.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PayloadKind {
    /// Quote batch, schema `market-event.v1`.
    Quote,
    /// OHLC bar batch, schema `market-event.v1`.
    Bar,
    /// Feature-row block, schema `feature-row.v1`.
    FeatureRow,
    /// Account observation window, schema `account-state-v1` or `account-state-v2`.
    Observation,
}

const NS: &str = "UTC nanoseconds since epoch";

const QUOTE_V1: &[ColumnSpec] = &[
    ColumnSpec {
        name: "event_time_ns",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: NS,
    },
    ColumnSpec {
        name: "available_at_ns",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: NS,
    },
    ColumnSpec {
        name: "source_sequence",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: "source sequence, strictly increasing",
    },
    ColumnSpec {
        name: "bid",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: true,
        unit: "quote currency per instrument unit",
    },
    ColumnSpec {
        name: "ask",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: true,
        unit: "quote currency per instrument unit",
    },
    ColumnSpec {
        name: "bid_size",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: true,
        unit: "source-reported size, non-negative",
    },
    ColumnSpec {
        name: "ask_size",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: true,
        unit: "source-reported size, non-negative",
    },
    ColumnSpec {
        name: "source_flags",
        dtype: Dtype::Int32,
        rank: 1,
        nullable: false,
        unit: "source flag bits, opaque to the kernels",
    },
];

const BAR_V1: &[ColumnSpec] = &[
    ColumnSpec {
        name: "event_time_ns",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: "bar open, UTC nanoseconds since epoch",
    },
    ColumnSpec {
        name: "close_time_ns",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: "bar close, UTC nanoseconds since epoch",
    },
    ColumnSpec {
        name: "available_at_ns",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: "availability, UTC nanoseconds since epoch",
    },
    ColumnSpec {
        name: "source_sequence",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: "source sequence, strictly increasing",
    },
    ColumnSpec {
        name: "open",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: false,
        unit: "quote currency per instrument unit",
    },
    ColumnSpec {
        name: "high",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: false,
        unit: "quote currency per instrument unit",
    },
    ColumnSpec {
        name: "low",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: false,
        unit: "quote currency per instrument unit",
    },
    ColumnSpec {
        name: "close",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: false,
        unit: "quote currency per instrument unit",
    },
    ColumnSpec {
        name: "volume",
        dtype: Dtype::Float64,
        rank: 1,
        nullable: true,
        unit: "source tick volume, non-negative",
    },
];

const FEATURE_ROW_V1: &[ColumnSpec] = &[
    ColumnSpec {
        name: "event_time_ns",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: "decision clock, UTC nanoseconds since epoch",
    },
    ColumnSpec {
        name: "available_at_ns",
        dtype: Dtype::Int64,
        rank: 1,
        nullable: false,
        unit: "feature availability, UTC nanoseconds since epoch",
    },
    ColumnSpec {
        name: "session_eligible",
        dtype: Dtype::UInt8,
        rank: 1,
        nullable: false,
        unit: "eligibility mask, 1 = eligible",
    },
    ColumnSpec {
        name: "values",
        dtype: Dtype::Float64,
        rank: 2,
        nullable: true,
        unit: "feature units per the feature-set manifest, row-major (rows, width)",
    },
];

const OBSERVATION_V1: &[ColumnSpec] = &[
    ColumnSpec {
        name: "values",
        dtype: Dtype::Float32,
        rank: 2,
        nullable: false,
        unit: "normalized account-state coordinates, row-major (rows, width)",
    },
    ColumnSpec {
        name: "mask",
        dtype: Dtype::UInt8,
        rank: 1,
        nullable: false,
        unit: "real-row mask, 1 = real, 0 = left padding (zero-valued)",
    },
];

/// Layout of a payload kind in wire order.
pub const fn layout(kind: PayloadKind) -> &'static [ColumnSpec] {
    match kind {
        PayloadKind::Quote => QUOTE_V1,
        PayloadKind::Bar => BAR_V1,
        PayloadKind::FeatureRow => FEATURE_ROW_V1,
        PayloadKind::Observation => OBSERVATION_V1,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(kind: PayloadKind) -> Vec<&'static str> {
        layout(kind).iter().map(|spec| spec.name).collect()
    }

    #[test]
    fn quote_layout_matches_the_python_quote_schema_order() {
        assert_eq!(
            names(PayloadKind::Quote),
            [
                "event_time_ns",
                "available_at_ns",
                "source_sequence",
                "bid",
                "ask",
                "bid_size",
                "ask_size",
                "source_flags",
            ]
        );
    }

    #[test]
    fn bar_layout_matches_the_python_bar_schema_order() {
        assert_eq!(
            names(PayloadKind::Bar),
            [
                "event_time_ns",
                "close_time_ns",
                "available_at_ns",
                "source_sequence",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        );
    }

    #[test]
    fn feature_layout_puts_the_matrix_last() {
        assert_eq!(
            names(PayloadKind::FeatureRow),
            [
                "event_time_ns",
                "available_at_ns",
                "session_eligible",
                "values"
            ]
        );
        assert_eq!(layout(PayloadKind::FeatureRow)[3].rank, 2);
    }

    #[test]
    fn observation_values_are_float32_and_the_mask_is_uint8() {
        let spec = layout(PayloadKind::Observation);
        assert_eq!(spec[0].dtype, Dtype::Float32);
        assert_eq!(spec[1].dtype, Dtype::UInt8);
        assert!(spec.iter().all(|column| !column.nullable));
    }

    #[test]
    fn dtype_names_are_numpy_names() {
        assert_eq!(Dtype::Int64.name(), "int64");
        assert_eq!(Dtype::UInt8.name(), "uint8");
        assert_eq!(Dtype::Float32.name(), "float32");
    }
}
