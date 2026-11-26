//! DatasetView: fold bounds, fitted-state references and cache-container corruption (SHARED-DATA-ABI).

use qrl_domain::abi::{
    AbiError, BarBatch, BarColumns, Column, DatasetView, FeatureRowBlock, FeatureRowColumns,
    FittedState, Fold,
};

const T0: i64 = 1_700_000_000_000_000_000;
const MINUTE: i64 = 60_000_000_000;

fn bars(rows: usize) -> BarBatch {
    let event: Vec<i64> = (0..rows as i64).map(|i| T0 + i * MINUTE).collect();
    let close: Vec<i64> = event.iter().map(|t| t + MINUTE).collect();
    BarBatch::try_new(
        "market-event.v1",
        "US100",
        "mt5-export",
        BarColumns {
            event_time_ns: Column::vector(event),
            close_time_ns: Column::vector(close.clone()),
            available_at_ns: Column::vector(close),
            source_sequence: Column::vector((0..rows as i64).collect()),
            open: Column::vector(vec![100.0; rows]),
            high: Column::vector(vec![101.0; rows]),
            low: Column::vector(vec![99.0; rows]),
            close: Column::vector(vec![100.5; rows]),
            volume: Column::vector(vec![10.0; rows]),
            volume_valid: Column::vector(vec![1; rows]),
        },
    )
    .expect("valid bars")
}

fn features(rows: usize, width: usize) -> FeatureRowBlock {
    let event: Vec<i64> = (0..rows as i64).map(|i| T0 + i * MINUTE).collect();
    let mut values = vec![0.25; rows * width];
    let mut valid = vec![1_u8; rows * width];
    for slot in 0..width {
        values[slot] = f64::NAN;
        valid[slot] = 0;
    }
    FeatureRowBlock::try_new(
        "feature-row.v1",
        "US100",
        "core-v1",
        "1.0.0",
        "sha256:abc",
        width,
        FeatureRowColumns {
            available_at_ns: Column::vector(event.clone()),
            event_time_ns: Column::vector(event),
            session_eligible: Column::vector(vec![1; rows]),
            values: Column::matrix(rows, width, values),
            values_valid: Column::matrix(rows, width, valid),
        },
    )
    .expect("valid features")
}

fn fold(
    train_end: usize,
    test_start: usize,
    test_end: usize,
    purge: usize,
    embargo: usize,
) -> Fold {
    Fold {
        train_start: 0,
        train_end,
        test_start,
        test_end,
        purge_rows: purge,
        embargo_rows: embargo,
    }
}

fn view(folds: Vec<Fold>, fitted: Option<FittedState>) -> Result<DatasetView, AbiError> {
    DatasetView::try_new(bars(20), features(20, 3), folds, fitted)
}

fn rule_of(result: Result<DatasetView, AbiError>) -> &'static str {
    match result {
        Err(AbiError::Rule { rule, .. }) => rule,
        other => panic!("expected a rule refusal, got {other:?}"),
    }
}

// ---- construction and sharing ----------------------------------------------------------------

#[test]
fn valid_view_exposes_its_parts_and_a_stable_content_hash() {
    let first = view(vec![fold(10, 12, 20, 1, 1)], None).expect("valid view");
    let second = view(vec![fold(10, 12, 20, 1, 1)], None).expect("valid view");
    assert_eq!(first.rows(), 20);
    assert_eq!(first.folds().len(), 1);
    assert_eq!(first.content_hash(), second.content_hash());
    assert_ne!(
        first.content_hash(),
        view(vec![fold(10, 13, 20, 1, 1)], None)
            .unwrap()
            .content_hash()
    );
}

#[test]
fn views_are_shared_in_process_through_arc_without_copying_the_arrays() {
    let shared = std::sync::Arc::new(view(vec![fold(10, 12, 20, 1, 1)], None).unwrap());
    let other = std::sync::Arc::clone(&shared);
    assert!(std::ptr::eq(shared.bars(), other.bars()));
    assert_eq!(std::sync::Arc::strong_count(&shared), 2);
}

#[test]
fn bars_and_features_must_share_decision_times_and_rows() {
    let mismatched_rows = DatasetView::try_new(bars(20), features(19, 3), vec![], None);
    assert!(matches!(mismatched_rows, Err(AbiError::Length { .. })));

    let shifted = {
        let event: Vec<i64> = (0..20_i64).map(|i| T0 + i * MINUTE + 1).collect();
        FeatureRowBlock::try_new(
            "feature-row.v1",
            "US100",
            "core-v1",
            "1.0.0",
            "sha256:abc",
            1,
            FeatureRowColumns {
                available_at_ns: Column::vector(event.clone()),
                event_time_ns: Column::vector(event),
                session_eligible: Column::vector(vec![1; 20]),
                values: Column::matrix(20, 1, vec![0.0; 20]),
                values_valid: Column::matrix(20, 1, vec![1; 20]),
            },
        )
        .unwrap()
    };
    assert_eq!(
        rule_of(DatasetView::try_new(bars(20), shifted, vec![], None)),
        "feature and bar decision clocks differ"
    );
}

// ---- fold bounds -----------------------------------------------------------------------------

#[test]
fn folds_with_purge_and_embargo_that_fit_are_accepted() {
    assert!(view(vec![fold(10, 13, 20, 2, 1)], None).is_ok());
}

#[test]
fn empty_training_range_is_refused() {
    let mut bad = fold(10, 12, 20, 0, 0);
    bad.train_start = 10;
    assert_eq!(
        rule_of(view(vec![bad], None)),
        "training range must be non-empty"
    );
}

#[test]
fn training_that_overlaps_its_test_fold_is_refused() {
    assert_eq!(
        rule_of(view(vec![fold(13, 12, 20, 0, 0)], None)),
        "training range must end before its test fold starts"
    );
}

#[test]
fn empty_or_out_of_range_test_fold_is_refused() {
    assert_eq!(
        rule_of(view(vec![fold(10, 12, 12, 0, 0)], None)),
        "test fold must be non-empty"
    );
    assert_eq!(
        rule_of(view(vec![fold(10, 12, 21, 0, 0)], None)),
        "test fold exceeds the dataset"
    );
}

#[test]
fn purge_plus_embargo_must_fit_before_the_test_fold() {
    // gap = 12 - 10 = 2, purge 2 + embargo 1 = 3
    assert_eq!(
        rule_of(view(vec![fold(10, 12, 20, 2, 1)], None)),
        "purge and embargo must fit between training end and test start"
    );
}

#[test]
fn overlapping_test_folds_are_refused_in_any_order() {
    let folds = vec![fold(10, 12, 16, 0, 0), fold(14, 15, 20, 0, 0)];
    assert_eq!(rule_of(view(folds, None)), "test folds must not overlap");
    let reversed = vec![fold(14, 15, 20, 0, 0), fold(10, 12, 16, 0, 0)];
    assert_eq!(rule_of(view(reversed, None)), "test folds must not overlap");
}

// ---- fitted-state reference ------------------------------------------------------------------

#[test]
fn fitted_state_inside_every_training_range_is_accepted() {
    let state = FittedState {
        state_id: "norm-v1".to_owned(),
        fit_start: 0,
        fit_end: 10,
    };
    assert!(view(vec![fold(10, 12, 20, 0, 0)], Some(state)).is_ok());
}

#[test]
fn fitted_state_that_reaches_a_test_row_is_refused() {
    let state = FittedState {
        state_id: "norm-v1".to_owned(),
        fit_start: 0,
        fit_end: 12,
    };
    assert_eq!(
        rule_of(view(vec![fold(10, 12, 20, 0, 0)], Some(state))),
        "fitted state uses rows outside this fold's training range"
    );
}

#[test]
fn fitted_state_without_folds_cannot_prove_train_only_use() {
    let state = FittedState {
        state_id: "norm-v1".to_owned(),
        fit_start: 0,
        fit_end: 5,
    };
    assert_eq!(
        rule_of(view(vec![], Some(state))),
        "a fitted state requires folds to prove it uses training rows only"
    );
}

#[test]
fn fitted_state_needs_an_identity_and_a_non_empty_range() {
    let unnamed = FittedState {
        state_id: " ".to_owned(),
        fit_start: 0,
        fit_end: 5,
    };
    assert_eq!(
        view(vec![fold(10, 12, 20, 0, 0)], Some(unnamed)).err(),
        Some(AbiError::EmptyIdentity {
            field: "fitted_state_id"
        })
    );
    let empty = FittedState {
        state_id: "norm-v1".to_owned(),
        fit_start: 5,
        fit_end: 5,
    };
    assert_eq!(
        rule_of(view(vec![fold(10, 12, 20, 0, 0)], Some(empty))),
        "fitted range must be non-empty"
    );
}

// ---- cache container -------------------------------------------------------------------------

fn small_view() -> DatasetView {
    DatasetView::try_new(
        bars(4),
        features(4, 2),
        vec![fold(2, 3, 4, 0, 0)],
        Some(FittedState {
            state_id: "norm-v1".to_owned(),
            fit_start: 0,
            fit_end: 2,
        }),
    )
    .expect("valid small view")
}

#[test]
fn container_round_trip_reproduces_the_view_and_its_hash() {
    let original = small_view();
    let bytes = original.to_bytes();
    let decoded = DatasetView::from_bytes(&bytes).expect("round trip");
    // Missing feature slots are NaN, so compare canonical bytes instead of derived PartialEq.
    assert_eq!(decoded.to_bytes(), bytes);
    assert_eq!(decoded.content_hash(), original.content_hash());
    assert_eq!(decoded.folds(), original.folds());
    assert_eq!(decoded.fitted(), original.fitted());
}

#[test]
fn every_single_byte_corruption_of_the_container_is_refused() {
    let bytes = small_view().to_bytes();
    for index in 0..bytes.len() {
        for mask in [0x01_u8, 0x80, 0xff] {
            let mut corrupt = bytes.clone();
            corrupt[index] ^= mask;
            assert!(
                DatasetView::from_bytes(&corrupt).is_err(),
                "byte {index} xor {mask:#x} was accepted"
            );
        }
    }
}

#[test]
fn every_truncation_of_the_container_is_refused() {
    let bytes = small_view().to_bytes();
    for length in 0..bytes.len() {
        assert!(
            DatasetView::from_bytes(&bytes[..length]).is_err(),
            "truncation to {length} bytes was accepted"
        );
    }
}

#[test]
fn trailing_bytes_after_the_container_are_refused() {
    let mut bytes = small_view().to_bytes();
    bytes.push(0);
    assert!(matches!(
        DatasetView::from_bytes(&bytes),
        Err(AbiError::Cache { .. })
    ));
}

#[test]
fn wrong_magic_and_unsupported_version_are_refused_with_reasons() {
    let mut magic = small_view().to_bytes();
    magic[0] = b'X';
    assert_eq!(
        DatasetView::from_bytes(&magic).err(),
        Some(AbiError::Cache {
            reason: "bad magic bytes"
        })
    );
    let mut version = small_view().to_bytes();
    version[8] = 9;
    assert!(matches!(
        DatasetView::from_bytes(&version),
        Err(AbiError::UnsupportedAbiVersion { found: 9, .. })
    ));
}
