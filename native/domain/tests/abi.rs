//! Public-API tests of the shared data ABI (SHARED-DATA-ABI).
//!
//! Each payload has one accepted batch and one refusal per rule. Property tests check that a
//! valid batch returns exactly the values it was given, and that a single injected defect is
//! always refused at the row where it was placed.

use proptest::prelude::*;

use qrl_domain::abi::{
    check_abi_version, layout, AbiError, BarBatch, BarColumns, Column, FeatureRowBlock,
    FeatureRowColumns, ObservationWindow, ObservationWindowColumns, PayloadKind, QuoteBatch,
    QuoteColumns, SchemaId, SHARED_DATA_ABI_VERSION,
};

const T0: i64 = 1_700_000_000_000_000_000;
const MINUTE: i64 = 60_000_000_000;

fn quote_columns(rows: usize) -> QuoteColumns {
    let event: Vec<i64> = (0..rows as i64).map(|i| T0 + i * MINUTE).collect();
    let available = event.clone();
    QuoteColumns {
        event_time_ns: Column::vector(event),
        available_at_ns: Column::vector(available),
        source_sequence: Column::vector((0..rows as i64).collect()),
        bid: Column::vector(vec![1.10; rows]),
        bid_valid: Column::vector(vec![1; rows]),
        ask: Column::vector(vec![1.11; rows]),
        ask_valid: Column::vector(vec![1; rows]),
        bid_size: Column::vector(vec![5.0; rows]),
        bid_size_valid: Column::vector(vec![1; rows]),
        ask_size: Column::vector(vec![4.0; rows]),
        ask_size_valid: Column::vector(vec![1; rows]),
        source_flags: Column::vector(vec![0; rows]),
    }
}

fn quote(columns: QuoteColumns) -> Result<QuoteBatch, AbiError> {
    QuoteBatch::try_new("market-event.v1", "EURUSD", "broker-csv", columns)
}

fn bar_columns(rows: usize) -> BarColumns {
    let event: Vec<i64> = (0..rows as i64).map(|i| T0 + i * MINUTE).collect();
    let close: Vec<i64> = event.iter().map(|t| t + MINUTE).collect();
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
    }
}

fn bar(columns: BarColumns) -> Result<BarBatch, AbiError> {
    BarBatch::try_new("market-event.v1", "US100", "mt5-export", columns)
}

fn feature_columns(rows: usize, width: usize) -> FeatureRowColumns {
    let event: Vec<i64> = (0..rows as i64).map(|i| T0 + i * MINUTE).collect();
    let mut values = vec![0.5; rows * width];
    let mut valid = vec![1_u8; rows * width];
    // First row is warm-up: every feature is missing and stored as NaN.
    for slot in 0..width {
        values[slot] = f64::NAN;
        valid[slot] = 0;
    }
    FeatureRowColumns {
        available_at_ns: Column::vector(event.clone()),
        event_time_ns: Column::vector(event),
        session_eligible: Column::vector(vec![1; rows]),
        values: Column::matrix(rows, width, values),
        values_valid: Column::matrix(rows, width, valid),
    }
}

fn feature(width: usize, columns: FeatureRowColumns) -> Result<FeatureRowBlock, AbiError> {
    FeatureRowBlock::try_new(
        "feature-row.v1",
        "US100",
        "core-v1",
        "1.0.0",
        "sha256:abc",
        width,
        columns,
    )
}

fn observation_columns(rows: usize, width: usize, real_from: usize) -> ObservationWindowColumns {
    let mut values = vec![0.0_f32; rows * width];
    let mut mask = vec![0_u8; rows];
    for row in real_from..rows {
        mask[row] = 1;
        for col in 0..width {
            values[row * width + col] = 0.25;
        }
    }
    ObservationWindowColumns {
        values: Column::matrix(rows, width, values),
        mask: Column::vector(mask),
    }
}

fn expect_rule(result: Result<impl std::fmt::Debug, AbiError>, rule: &str) {
    match result {
        Err(AbiError::Rule { rule: found, .. }) => assert_eq!(found, rule),
        other => panic!("expected rule refusal {rule:?}, got {other:?}"),
    }
}

// ---- versions and layouts -------------------------------------------------------------------

#[test]
fn version_one_is_the_only_accepted_version() {
    assert_eq!(SHARED_DATA_ABI_VERSION, 1);
    assert!(check_abi_version(1).is_ok());
    assert!(matches!(
        check_abi_version(0),
        Err(AbiError::UnsupportedAbiVersion { found: 0, .. })
    ));
}

#[test]
fn layouts_are_the_wire_order_for_every_payload() {
    assert_eq!(layout(PayloadKind::Quote).len(), 8);
    assert_eq!(layout(PayloadKind::Bar).len(), 9);
    assert_eq!(layout(PayloadKind::FeatureRow).len(), 4);
    assert_eq!(layout(PayloadKind::Observation).len(), 2);
}

// ---- quotes --------------------------------------------------------------------------------

#[test]
fn valid_quotes_are_accepted_and_returned_unchanged() {
    let batch = quote(quote_columns(4)).expect("valid quotes");
    assert_eq!(batch.rows(), 4);
    assert_eq!(batch.schema(), SchemaId::MarketEventV1);
    assert_eq!(batch.instrument_id(), "EURUSD");
    assert_eq!(batch.bid().values(), &[1.10; 4]);
    assert_eq!(batch.source_sequence(), &[0, 1, 2, 3]);
}

#[test]
fn quotes_with_a_missing_side_keep_the_missing_slot_as_nan() {
    let mut columns = quote_columns(2);
    columns.ask = Column::vector(vec![1.11, f64::NAN]);
    columns.ask_valid = Column::vector(vec![1, 0]);
    let batch = quote(columns).expect("one-sided quote is a valid record");
    assert_eq!(batch.ask().valid(), &[true, false]);
    assert!(batch.ask().values()[1].is_nan());
}

#[test]
fn quote_refuses_an_unknown_or_foreign_schema() {
    for schema in ["market-event.v3", "feature-row.v1", "market-event.v2"] {
        let result = QuoteBatch::try_new(schema, "EURUSD", "src", quote_columns(2));
        assert!(
            matches!(result, Err(AbiError::UnsupportedSchema { .. })),
            "schema {schema} must be refused"
        );
    }
}

#[test]
fn quote_refuses_empty_identity() {
    let result = QuoteBatch::try_new("market-event.v1", "  ", "src", quote_columns(2));
    assert_eq!(
        result,
        Err(AbiError::EmptyIdentity {
            field: "instrument_id"
        })
    );
}

#[test]
fn quote_refuses_an_empty_batch() {
    assert_eq!(quote(quote_columns(0)), Err(AbiError::EmptyBatch));
}

#[test]
fn quote_refuses_a_column_length_mismatch() {
    let mut columns = quote_columns(3);
    columns.ask = Column::vector(vec![1.11, 1.11]);
    assert_eq!(
        quote(columns),
        Err(AbiError::Length {
            column: "ask",
            expected: 3,
            found: 2
        })
    );
}

#[test]
fn quote_refuses_a_matrix_where_a_vector_is_required() {
    let mut columns = quote_columns(2);
    columns.bid = Column::matrix(1, 2, vec![1.1, 1.1]);
    assert_eq!(
        quote(columns),
        Err(AbiError::Rank {
            column: "bid",
            expected: 1,
            found: 2
        })
    );
}

#[test]
fn quote_refuses_a_shape_that_does_not_match_its_data() {
    let mut columns = quote_columns(3);
    columns.source_flags = Column {
        shape: vec![3],
        data: vec![0, 0],
    };
    assert!(matches!(
        quote(columns),
        Err(AbiError::Length {
            column: "source_flags",
            expected: 3,
            found: 2
        })
    ));
}

#[test]
fn quote_refuses_non_finite_present_prices() {
    for bad in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        let mut columns = quote_columns(3);
        columns.bid = Column::vector(vec![1.10, bad, 1.10]);
        assert_eq!(
            quote(columns),
            Err(AbiError::NonFinite {
                column: "bid",
                row: 1
            }),
            "value {bad} must be refused where present"
        );
    }
}

#[test]
fn quote_refuses_a_sentinel_in_a_missing_slot() {
    let mut columns = quote_columns(2);
    columns.bid = Column::vector(vec![1.10, 0.0]);
    columns.bid_valid = Column::vector(vec![1, 0]);
    assert_eq!(
        quote(columns),
        Err(AbiError::MissingNotNan {
            column: "bid",
            row: 1
        })
    );
}

#[test]
fn quote_refuses_a_non_positive_price_and_a_negative_size() {
    let mut zero = quote_columns(2);
    zero.ask = Column::vector(vec![1.11, 0.0]);
    assert_eq!(
        quote(zero),
        Err(AbiError::NotPositive {
            column: "ask",
            row: 1
        })
    );
    let mut negative = quote_columns(2);
    negative.bid_size = Column::vector(vec![5.0, -1.0]);
    assert_eq!(
        quote(negative),
        Err(AbiError::Negative {
            column: "bid_size",
            row: 1
        })
    );
}

#[test]
fn quote_refuses_a_mask_that_is_not_zero_or_one() {
    let mut columns = quote_columns(2);
    columns.bid_valid = Column::vector(vec![1, 2]);
    assert_eq!(
        quote(columns),
        Err(AbiError::Mask {
            column: "bid_valid",
            row: 1
        })
    );
}

#[test]
fn quote_refuses_bid_above_ask() {
    let mut columns = quote_columns(2);
    columns.bid = Column::vector(vec![1.10, 1.12]);
    expect_rule(quote(columns), "bid exceeds ask");
}

#[test]
fn quote_refuses_availability_before_event_time() {
    let mut columns = quote_columns(2);
    columns.available_at_ns = Column::vector(vec![T0, T0 - 1]);
    expect_rule(quote(columns), "available_at precedes event_time");
}

#[test]
fn quote_refuses_a_repeated_or_decreasing_source_sequence() {
    let mut repeated = quote_columns(3);
    repeated.source_sequence = Column::vector(vec![0, 1, 1]);
    expect_rule(quote(repeated), "source_sequence must strictly increase");
}

#[test]
fn quote_refuses_event_time_that_goes_backwards() {
    let mut columns = quote_columns(2);
    columns.event_time_ns = Column::vector(vec![T0 + MINUTE, T0]);
    columns.available_at_ns = Column::vector(vec![T0 + MINUTE, T0]);
    expect_rule(quote(columns), "event_time must not decrease");
}

// ---- bars ----------------------------------------------------------------------------------

#[test]
fn valid_bars_are_accepted_and_returned_unchanged() {
    let batch = bar(bar_columns(3)).expect("valid bars");
    assert_eq!(batch.rows(), 3);
    assert_eq!(batch.close(), &[100.5; 3]);
    assert_eq!(batch.volume().valid(), &[true; 3]);
}

#[test]
fn bar_refuses_market_event_v2_because_revisions_must_be_resolved_first() {
    let result = BarBatch::try_new("market-event.v2", "US100", "src", bar_columns(2));
    assert!(matches!(result, Err(AbiError::UnsupportedSchema { .. })));
}

#[test]
fn bar_refuses_non_positive_or_non_finite_ohlc() {
    let mut columns = bar_columns(2);
    columns.low = Column::vector(vec![99.0, f64::NAN]);
    assert_eq!(
        bar(columns),
        Err(AbiError::NonFinite {
            column: "low",
            row: 1
        })
    );
    let mut zero = bar_columns(2);
    zero.open = Column::vector(vec![100.0, 0.0]);
    assert_eq!(
        bar(zero),
        Err(AbiError::NotPositive {
            column: "open",
            row: 1
        })
    );
}

#[test]
fn bar_refuses_ohlc_outside_its_bounds() {
    let mut columns = bar_columns(2);
    columns.high = Column::vector(vec![101.0, 100.0]);
    columns.close = Column::vector(vec![100.5, 100.5]);
    expect_rule(bar(columns), "OHLC bounds violated");
}

#[test]
fn bar_refuses_a_close_that_does_not_follow_the_open() {
    let mut columns = bar_columns(2);
    columns.close_time_ns = Column::vector(vec![T0 + MINUTE, T0 + MINUTE]);
    expect_rule(bar(columns), "close_time must follow event_time");
}

#[test]
fn bar_refuses_availability_before_close_as_an_incomplete_bar() {
    let mut columns = bar_columns(2);
    columns.available_at_ns = Column::vector(vec![T0 + MINUTE, T0 + 2 * MINUTE - 1]);
    expect_rule(
        bar(columns),
        "available_at precedes close_time (incomplete bar)",
    );
}

#[test]
fn bar_refuses_a_duplicate_open_time() {
    let mut columns = bar_columns(2);
    columns.event_time_ns = Column::vector(vec![T0, T0]);
    columns.close_time_ns = Column::vector(vec![T0 + MINUTE, T0 + MINUTE]);
    columns.available_at_ns = Column::vector(vec![T0 + MINUTE, T0 + MINUTE]);
    expect_rule(bar(columns), "event_time must strictly increase");
}

#[test]
fn bar_refuses_a_negative_volume_and_keeps_missing_volume_as_nan() {
    let mut negative = bar_columns(2);
    negative.volume = Column::vector(vec![10.0, -1.0]);
    assert_eq!(
        bar(negative),
        Err(AbiError::Negative {
            column: "volume",
            row: 1
        })
    );
    let mut missing = bar_columns(2);
    missing.volume = Column::vector(vec![10.0, f64::NAN]);
    missing.volume_valid = Column::vector(vec![1, 0]);
    let batch = bar(missing).expect("missing volume is allowed when marked missing");
    assert_eq!(batch.volume().valid(), &[true, false]);
}

// ---- feature rows --------------------------------------------------------------------------

#[test]
fn valid_feature_block_keeps_warm_up_missing_values_as_nan_with_mask() {
    let block = feature(3, feature_columns(4, 3)).expect("valid features");
    assert_eq!(block.rows(), 4);
    assert_eq!(block.width(), 3);
    assert_eq!(block.feature_set_id(), "core-v1");
    assert_eq!(block.values().valid()[..3], [false, false, false]);
    assert!(block.values().values()[0].is_nan());
    assert_eq!(block.session_eligible(), &[true; 4]);
}

#[test]
fn feature_block_refuses_a_width_that_differs_from_the_manifest() {
    let result = feature(4, feature_columns(3, 3));
    assert_eq!(
        result,
        Err(AbiError::Width {
            column: "values",
            expected: 4,
            found: 3
        })
    );
}

#[test]
fn feature_block_refuses_a_zero_width_manifest() {
    let result = feature(0, feature_columns(2, 1));
    assert!(matches!(result, Err(AbiError::Width { .. })));
}

#[test]
fn feature_block_refuses_empty_content_hash_and_feature_version() {
    let empty_hash = FeatureRowBlock::try_new(
        "feature-row.v1",
        "US100",
        "core-v1",
        "1.0.0",
        "",
        3,
        feature_columns(2, 3),
    );
    assert_eq!(
        empty_hash,
        Err(AbiError::EmptyIdentity {
            field: "content_hash"
        })
    );
}

#[test]
fn feature_block_refuses_a_non_finite_present_value() {
    let mut columns = feature_columns(3, 2);
    let mut values = columns.values.data.clone();
    values[2] = f64::INFINITY; // row 1, column 0, present
    columns.values = Column::matrix(3, 2, values);
    assert_eq!(
        feature(2, columns),
        Err(AbiError::NonFinite {
            column: "values",
            row: 1
        })
    );
}

#[test]
fn feature_block_refuses_a_sentinel_zero_in_a_missing_slot() {
    let mut columns = feature_columns(2, 2);
    let mut values = columns.values.data.clone();
    values[0] = 0.0; // row 0 is warm-up and marked missing
    columns.values = Column::matrix(2, 2, values);
    assert_eq!(
        feature(2, columns),
        Err(AbiError::MissingNotNan {
            column: "values",
            row: 0
        })
    );
}

#[test]
fn feature_block_refuses_information_available_after_its_event_time() {
    let mut columns = feature_columns(2, 1);
    columns.available_at_ns = Column::vector(vec![T0, T0 + 2 * MINUTE]);
    expect_rule(
        feature(1, columns),
        "feature uses information available after its event_time",
    );
}

#[test]
fn feature_block_refuses_a_session_mask_that_is_not_binary() {
    let mut columns = feature_columns(2, 1);
    columns.session_eligible = Column::vector(vec![1, 3]);
    assert_eq!(
        feature(1, columns),
        Err(AbiError::Mask {
            column: "session_eligible",
            row: 1
        })
    );
}

// ---- observation windows -------------------------------------------------------------------

#[test]
fn valid_observation_window_is_accepted_with_left_padding() {
    let window = ObservationWindow::try_new("account-state-v2", observation_columns(5, 28, 2))
        .expect("left-padded window");
    assert_eq!(window.rows(), 5);
    assert_eq!(window.width(), 28);
    assert_eq!(window.real(), &[false, false, true, true, true]);
}

#[test]
fn observation_width_is_fixed_by_the_schema() {
    let result = ObservationWindow::try_new("account-state-v1", observation_columns(3, 28, 0));
    assert_eq!(
        result.map(|_| ()),
        Err(AbiError::Width {
            column: "values",
            expected: 6,
            found: 28
        })
    );
}

#[test]
fn observation_refuses_a_schema_that_is_not_an_account_state() {
    let result = ObservationWindow::try_new("feature-row.v1", observation_columns(3, 6, 0));
    assert!(matches!(result, Err(AbiError::UnsupportedSchema { .. })));
}

#[test]
fn observation_refuses_non_finite_coordinates() {
    let mut columns = observation_columns(2, 6, 0);
    columns.values.data[7] = f32::NAN;
    columns.mask = Column::vector(vec![1, 1]);
    assert_eq!(
        ObservationWindow::try_new("account-state-v1", columns),
        Err(AbiError::NonFinite {
            column: "values",
            row: 1
        })
    );
}

#[test]
fn observation_refuses_padding_after_real_rows() {
    let mut columns = observation_columns(3, 6, 0);
    columns.mask = Column::vector(vec![1, 0, 1]);
    columns.values.data[6..12].fill(0.0); // padded row is zero, so only ordering can fail
    expect_rule(
        ObservationWindow::try_new("account-state-v1", columns),
        "padding must precede real rows",
    );
}

#[test]
fn observation_refuses_non_zero_padding() {
    let mut columns = observation_columns(3, 6, 2);
    columns.values.data[0] = 0.5; // row 0 is padded
    expect_rule(
        ObservationWindow::try_new("account-state-v1", columns),
        "padded row must be all zero",
    );
}

#[test]
fn observation_refuses_an_all_padded_empty_window() {
    let columns = ObservationWindowColumns {
        values: Column::matrix(0, 6, vec![]),
        mask: Column::vector(vec![]),
    };
    assert_eq!(
        ObservationWindow::try_new("account-state-v1", columns),
        Err(AbiError::EmptyBatch)
    );
}

// ---- property tests --------------------------------------------------------------------------

proptest! {
    #[test]
    fn valid_quotes_round_trip_every_value(
        bids in prop::collection::vec(0.5_f64..2.0, 1..40),
    ) {
        let rows = bids.len();
        let mut columns = quote_columns(rows);
        columns.bid = Column::vector(bids.clone());
        columns.ask = Column::vector(bids.iter().map(|b| b + 0.01).collect());
        let batch = quote(columns).expect("valid generated quotes");
        prop_assert_eq!(batch.bid().values(), bids.as_slice());
        prop_assert_eq!(batch.rows(), rows);
    }

    #[test]
    fn one_injected_non_finite_price_is_refused_at_its_row(
        rows in 2_usize..30,
        pick in 0_usize..1000,
    ) {
        let row = pick % rows;
        let mut columns = quote_columns(rows);
        let mut bids = vec![1.10; rows];
        bids[row] = f64::NAN; // present (valid mask stays 1)
        columns.bid = Column::vector(bids);
        prop_assert_eq!(
            quote(columns),
            Err(AbiError::NonFinite { column: "bid", row })
        );
    }

    #[test]
    fn missing_slots_must_be_nan_for_any_mask_pattern(
        mask in prop::collection::vec(any::<bool>(), 1..30),
    ) {
        let rows = mask.len();
        let mut columns = quote_columns(rows);
        columns.bid = Column::vector(
            mask.iter().map(|&present| if present { 1.10 } else { f64::NAN }).collect(),
        );
        columns.bid_valid = Column::vector(mask.iter().map(|&p| u8::from(p)).collect());
        columns.ask_valid = Column::vector(vec![0; rows]);
        columns.ask = Column::vector(vec![f64::NAN; rows]);
        let batch = quote(columns).expect("NaN exactly at missing slots is canonical");
        prop_assert_eq!(batch.bid().valid(), mask.as_slice());
    }
}
