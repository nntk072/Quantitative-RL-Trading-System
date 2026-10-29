from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import numpy as np
from scripts.research.benchmarks.measure_grouped_market_inference import _market_row_groups

from models.encoders.mtf_shared_tcn_reasoning import SharedTCNMTFReasoningEncoder


def test_market_row_groups_require_exact_sequences_and_masks() -> None:
    observations = {
        "account": np.arange(8, dtype=np.float32).reshape(4, 2),
        "seq": np.array(
            [
                [[1.0], [2.0]],
                [[3.0], [4.0]],
                [[1.0], [2.0]],
                [[1.0], [2.0]],
            ],
            dtype=np.float32,
        ),
        "mask": np.array(
            [[True, True], [True, False], [True, True], [False, True]],
            dtype=np.bool_,
        ),
    }
    encoder = cast(
        SharedTCNMTFReasoningEncoder,
        SimpleNamespace(streams=(("seq", "mask", 2, 1),)),
    )

    representatives, inverse, fingerprint = _market_row_groups(observations, encoder)

    assert representatives.tolist() == [0, 1, 3]
    assert inverse.tolist() == [0, 1, 0, 2]
    assert len(fingerprint) == 64
    assert np.unique(observations["account"], axis=0).shape[0] == 4
