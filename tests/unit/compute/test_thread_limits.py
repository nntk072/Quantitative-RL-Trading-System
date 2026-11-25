"""Bounded thread pools derived from the granted core count, never host totals."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from compute.slurm.thread_limits import (
    THREAD_ENV_KEYS,
    apply_torch_threads,
    thread_environment,
    torch_thread_counts,
)


def test_every_native_pool_is_sized_to_the_granted_cores() -> None:
    assert thread_environment(3) == {
        "OMP_NUM_THREADS": "3",
        "MKL_NUM_THREADS": "3",
        "OPENBLAS_NUM_THREADS": "3",
        "RAYON_NUM_THREADS": "3",
        "POLARS_MAX_THREADS": "3",
    }
    assert set(THREAD_ENV_KEYS) == set(thread_environment(1))


@pytest.mark.parametrize("granted", [0, -2])
def test_thread_limits_refuse_an_empty_core_grant(granted: int) -> None:
    with pytest.raises(ValueError, match="at least one"):
        thread_environment(granted)
    with pytest.raises(ValueError, match="at least one"):
        torch_thread_counts(granted)


def test_torch_intra_op_follows_the_grant_and_inter_op_stays_at_one() -> None:
    assert torch_thread_counts(3) == (3, 1)


def test_apply_torch_threads_sets_both_pools_on_the_given_module() -> None:
    calls: list[tuple[str, int]] = []
    fake_torch = SimpleNamespace(
        set_num_threads=lambda count: calls.append(("intra", count)),
        set_num_interop_threads=lambda count: calls.append(("inter", count)),
    )

    assert apply_torch_threads(2, torch_module=fake_torch) == (2, 1)
    assert calls == [("intra", 2), ("inter", 1)]
