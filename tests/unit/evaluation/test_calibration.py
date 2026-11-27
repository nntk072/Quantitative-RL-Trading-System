"""Calibration summaries retain empty-bin and endpoint behavior."""

from __future__ import annotations

from typing import Any, cast

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from evaluation.metrics.calibration import calibration_report, plot_reliability_diagram


def test_calibration_report_clips_probabilities_and_omits_empty_bins() -> None:
    report = calibration_report(np.asarray([-0.2, 1.2]), np.asarray([0.0, 1.0]), n_bins=4)

    np.testing.assert_allclose(report.bin_centers, [0.0, 1.0])
    np.testing.assert_allclose(report.bin_win_rates, [0.0, 1.0])
    np.testing.assert_array_equal(report.bin_counts, [1, 1])
    assert report.ece == 0.0
    assert report.brier == 0.0
    assert "bins=2  n=2" in report.summary()


def test_empty_calibration_report_and_reliability_plot_are_supported() -> None:
    empty = calibration_report(np.asarray([]), np.asarray([]))
    assert empty.bin_counts.size == 0
    assert np.isnan(empty.ece)
    assert np.isnan(empty.brier)

    fig, ax = plt.subplots()
    returned = plot_reliability_diagram(empty, ax)
    assert returned is ax
    assert len(ax.patches) == 0
    plt.close(fig)

    created = plot_reliability_diagram(empty)
    assert created.get_xlim() == (0.0, 1.0)
    plt.close(cast(Any, created.figure))


def test_calibration_report_rejects_unaligned_prediction_and_outcome_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        calibration_report(np.asarray([0.5]), np.asarray([0.0, 1.0]))
