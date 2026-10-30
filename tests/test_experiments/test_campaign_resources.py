from __future__ import annotations

from compute.slurm import campaign_worker_resources as resources


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


def test_legacy_campaign_resource_module_forwards_to_compute_owner() -> None:
    from experiments.campaigns import resources as legacy_resources

    assert legacy_resources.worker_command is resources.worker_command
    assert legacy_resources.resolve_worker_nodes is resources.resolve_worker_nodes
