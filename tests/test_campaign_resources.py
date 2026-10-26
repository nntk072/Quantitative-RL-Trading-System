from __future__ import annotations

from experiments.campaigns import resources


def test_worker_nodes_use_parent_allocation_from_nested_step(monkeypatch) -> None:
    monkeypatch.setenv("SLURM_NODELIST", "gpuarm[1-2]")
    monkeypatch.setenv("SLURM_JOB_NODELIST", "gpuarm1")
    expanded = {
        "gpuarm[1-2]": ["gpuarm1", "gpuarm2"],
        "gpuarm1,gpuarm2": ["gpuarm1", "gpuarm2"],
    }
    monkeypatch.setattr(resources, "expand_slurm_hosts", lambda value: expanded[value])

    assert resources.resolve_worker_nodes("gpuarm1,gpuarm2", dry_run=False) == [
        "gpuarm1",
        "gpuarm2",
    ]
