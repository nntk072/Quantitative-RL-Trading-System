//! Fixed-width binary frame shared by the serialized domain values.
//!
//! Layout rules, applied by every value type:
//! - byte 0 is the schema version ([`DOMAIN_SCHEMA_VERSION`]); any other value is refused;
//! - integers are little-endian; enums are single tag bytes;
//! - the frame length is fixed per type, so decoding never allocates;
//! - decoding validates the value's invariants and refuses anything it could not have
//!   produced, so a successful decode re-encodes to the same bytes.

use crate::{DomainError, DOMAIN_SCHEMA_VERSION};

/// Version byte written at offset 0 of every frame.
pub(crate) const VERSION: u8 = DOMAIN_SCHEMA_VERSION as u8;

/// Checks the frame length and version byte.
pub(crate) fn check_frame(bytes: &[u8], len: usize) -> Result<(), DomainError> {
    if bytes.len() == len && bytes.first() == Some(&VERSION) {
        Ok(())
    } else {
        Err(DomainError::InvalidEncoding)
    }
}

/// Reads an `N`-byte field starting at `at`; the caller has already checked the frame length.
pub(crate) fn field<const N: usize>(bytes: &[u8], at: usize) -> Result<[u8; N], DomainError> {
    bytes
        .get(at..at + N)
        .and_then(|slice| slice.try_into().ok())
        .ok_or(DomainError::InvalidEncoding)
}

pub(crate) fn read_u64(bytes: &[u8], at: usize) -> Result<u64, DomainError> {
    field::<8>(bytes, at).map(u64::from_le_bytes)
}

pub(crate) fn read_i64(bytes: &[u8], at: usize) -> Result<i64, DomainError> {
    field::<8>(bytes, at).map(i64::from_le_bytes)
}

pub(crate) fn read_tag(bytes: &[u8], at: usize) -> Result<u8, DomainError> {
    bytes.get(at).copied().ok_or(DomainError::InvalidEncoding)
}
