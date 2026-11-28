from __future__ import annotations

import numpy as np
from research_tools.learning.benchmarks.profile_env_step import (
    _latency_percentiles_ms,
    _profile,
)


def test_latency_percentiles_report_p50_p95_and_p99_in_milliseconds() -> None:
    actual = _latency_percentiles_ms(
        np.asarray([1_000, 2_000, 3_000, 4_000, 5_000], dtype=np.int64)
    )

    assert actual == {"p50": 0.003, "p95": 0.0048, "p99": 0.00496}


def test_latency_percentiles_handle_empty_samples() -> None:
    assert _latency_percentiles_ms(np.asarray([], dtype=np.int64)) == {
        "p50": None,
        "p95": None,
        "p99": None,
    }


def test_profile_can_collect_step_latencies_without_cprofile_overhead() -> None:
    class ActionSpace:
        def seed(self, seed: int) -> None:
            del seed

        def sample(self) -> int:
            return 0

    class Env:
        action_space = ActionSpace()

        def reset(self, *, seed: int) -> None:
            del seed

        def step(self, action: int) -> tuple[dict[str, int], float, bool, bool]:
            del action
            return {}, 0.0, False, False

    wall, profiler, latency_samples = _profile(Env(), 3, 42, capture_profile=False)

    assert wall >= 0.0
    assert profiler.getstats() == []
    assert len(latency_samples) == 3
