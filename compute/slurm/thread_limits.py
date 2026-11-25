"""Thread-pool limits for one worker, derived from the cores that worker was granted.

The worker dispatcher exports these variables to each child so a native pool
cannot exceed the granted cores. PyTorch's inter-op pool has no environment
variable, so an in-process caller applies it with ``apply_torch_threads`` at
startup. torch is imported lazily so the dispatcher does not load it.
"""

from __future__ import annotations

import importlib
from typing import Any

THREAD_ENV_KEYS: tuple[str, ...] = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "RAYON_NUM_THREADS",
    "POLARS_MAX_THREADS",
)


def _require_granted_cores(granted_cpus: int) -> None:
    """Refuse a worker with no granted cores; a zero-thread pool is never a valid limit."""
    if granted_cpus < 1:
        raise ValueError("a worker needs at least one granted CPU for its thread limits")


def thread_environment(granted_cpus: int) -> dict[str, str]:
    """Return the native thread-pool variables for a worker with ``granted_cpus`` cores.

    Args:
        granted_cpus: Cores granted to the worker (its CPU mask size).

    Returns:
        One entry per key in ``THREAD_ENV_KEYS``, each set to the granted count.
    """
    _require_granted_cores(granted_cpus)
    return dict.fromkeys(THREAD_ENV_KEYS, str(granted_cpus))


def torch_thread_counts(granted_cpus: int) -> tuple[int, int]:
    """Return ``(intra_op, inter_op)`` PyTorch thread counts for a granted core count.

    Intra-op uses every granted core. Inter-op stays at one so concurrent operator
    pools cannot oversubscribe the same cores.

    Args:
        granted_cpus: Cores granted to the worker.

    Returns:
        The intra-op and inter-op thread counts.
    """
    _require_granted_cores(granted_cpus)
    return granted_cpus, 1


def apply_torch_threads(granted_cpus: int, torch_module: Any | None = None) -> tuple[int, int]:
    """Set PyTorch's intra-op and inter-op pools from the granted cores.

    Call this at process start, before parallel work: PyTorch refuses to change the
    inter-op count after parallel work has begun.

    Args:
        granted_cpus: Cores granted to this process.
        torch_module: Module exposing ``set_num_threads`` and ``set_num_interop_threads``;
            defaults to ``torch``. Tests pass a fake.

    Returns:
        The ``(intra_op, inter_op)`` counts that were applied.
    """
    intra, inter = torch_thread_counts(granted_cpus)
    module = torch_module if torch_module is not None else importlib.import_module("torch")
    module.set_num_threads(intra)
    module.set_num_interop_threads(inter)
    return intra, inter


__all__ = ["THREAD_ENV_KEYS", "apply_torch_threads", "thread_environment", "torch_thread_counts"]
