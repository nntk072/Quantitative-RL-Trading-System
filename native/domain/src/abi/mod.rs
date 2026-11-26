//! Shared data ABI: versioned array layouts that cross the Python/native boundary.
//!
//! The ABI is an in-memory contract, not a file format. Every payload is a set of named columns
//! with a fixed dtype, rank, nullability and unit (see [`layout`]). The Python binding copies
//! each array into an owned [`Column`], and the constructors in [`batches`] validate it before a
//! batch exists. A batch that was constructed successfully satisfies every rule of its payload;
//! there is no partial success.
//!
//! Conventions shared by all payloads:
//! - timestamps are `int64` nanoseconds since the Unix epoch in UTC (Arrow `timestamp[ns, UTC]`);
//! - a nullable column has a companion `uint8` validity array named `<column>_valid`, where `1`
//!   means present and `0` means missing (the polarity of Arrow validity bitmaps);
//! - a missing value is stored as NaN, and a present value must be finite. A missing slot that
//!   holds any other number, or a present slot that holds NaN or infinity, is refused;
//! - no value is ever filled, interpolated or defaulted by this layer;
//! - only C-contiguous, native-endian arrays are accepted. Non-contiguous views are refused
//!   instead of being copied silently.
//!
//! The compatibility rule is documented in `planning/native_modernization/shared_data_abi/`.

mod batches;
mod dataset;
mod error;
mod layout;

pub use batches::{
    BarBatch, BarColumns, Column, FeatureRowBlock, FeatureRowColumns, NullableF64,
    ObservationWindow, ObservationWindowColumns, QuoteBatch, QuoteColumns,
};
pub use dataset::{DatasetView, FittedState, Fold, CONTAINER_MAGIC};
pub use error::AbiError;
pub use layout::{layout, ColumnSpec, Dtype, PayloadKind};

/// Version of the shared data ABI. Bump when a layout, unit, dtype, mask polarity, null/NaN
/// policy or accepted schema identity changes meaning. See the README for the compatibility rule.
pub const SHARED_DATA_ABI_VERSION: u32 = 1;

/// Schema identities this ABI can carry, as written by `market_data.arrow_schemas`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SchemaId {
    /// `market-event.v1`: quote and bar physical layout (`SCHEMA_VERSION` in Python).
    MarketEventV1,
    /// `market-event.v2`: bars with an integer `revision`. Recognised, but not accepted by this
    /// ABI; the Python side must resolve the latest revision into a v1 view first.
    MarketEventV2,
    /// `normalized-event.v1`: recognised, not an ABI payload in version 1.
    NormalizedEventV1,
    /// `feature-row.v1`: feature rows (`FEATURE_ROW_SCHEMA_ID` in Python).
    FeatureRowV1,
    /// `account-state-v1`: legacy account observation coordinates (six values).
    AccountStateV1,
    /// `account-state-v2`: account observation coordinates (28 values).
    AccountStateV2,
}

impl SchemaId {
    /// Every schema identity this ABI recognises, accepted or not by a given payload.
    pub const ALL: [SchemaId; 6] = [
        SchemaId::MarketEventV1,
        SchemaId::MarketEventV2,
        SchemaId::NormalizedEventV1,
        SchemaId::FeatureRowV1,
        SchemaId::AccountStateV1,
        SchemaId::AccountStateV2,
    ];

    /// Parses a schema identity string. Unknown strings return `None`.
    pub fn parse(text: &str) -> Option<Self> {
        match text {
            "market-event.v1" => Some(Self::MarketEventV1),
            "market-event.v2" => Some(Self::MarketEventV2),
            "normalized-event.v1" => Some(Self::NormalizedEventV1),
            "feature-row.v1" => Some(Self::FeatureRowV1),
            "account-state-v1" => Some(Self::AccountStateV1),
            "account-state-v2" => Some(Self::AccountStateV2),
            _ => None,
        }
    }

    /// The canonical identity string of this schema.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::MarketEventV1 => "market-event.v1",
            Self::MarketEventV2 => "market-event.v2",
            Self::NormalizedEventV1 => "normalized-event.v1",
            Self::FeatureRowV1 => "feature-row.v1",
            Self::AccountStateV1 => "account-state-v1",
            Self::AccountStateV2 => "account-state-v2",
        }
    }
}

/// Number of coordinates in an account observation schema.
///
/// These counts mirror `decisioning.observations.V1_COORDINATES` (6) and `V2_COORDINATES` (28).
/// A cross-language test in `native/python/tests` fails if they diverge.
pub const fn observation_width(schema: SchemaId) -> Option<usize> {
    match schema {
        SchemaId::AccountStateV1 => Some(6),
        SchemaId::AccountStateV2 => Some(28),
        _ => None,
    }
}

/// Refuses an ABI version other than [`SHARED_DATA_ABI_VERSION`].
pub fn check_abi_version(found: u32) -> Result<(), AbiError> {
    if found == SHARED_DATA_ABI_VERSION {
        Ok(())
    } else {
        Err(AbiError::UnsupportedAbiVersion {
            found,
            supported: SHARED_DATA_ABI_VERSION,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn abi_version_is_one() {
        assert_eq!(SHARED_DATA_ABI_VERSION, 1);
    }

    #[test]
    fn schema_ids_round_trip_through_their_strings() {
        for schema in SchemaId::ALL {
            assert_eq!(SchemaId::parse(schema.as_str()), Some(schema));
        }
    }

    #[test]
    fn unknown_schema_strings_are_not_parsed() {
        assert_eq!(SchemaId::parse("market-event.v3"), None);
        assert_eq!(SchemaId::parse(""), None);
        assert_eq!(SchemaId::parse("Market-Event.v1"), None);
    }

    #[test]
    fn observation_widths_match_the_documented_counts() {
        assert_eq!(observation_width(SchemaId::AccountStateV1), Some(6));
        assert_eq!(observation_width(SchemaId::AccountStateV2), Some(28));
        assert_eq!(observation_width(SchemaId::FeatureRowV1), None);
    }

    #[test]
    fn check_abi_version_refuses_other_versions() {
        assert_eq!(check_abi_version(1), Ok(()));
        assert_eq!(
            check_abi_version(2),
            Err(AbiError::UnsupportedAbiVersion {
                found: 2,
                supported: 1
            })
        );
    }
}
