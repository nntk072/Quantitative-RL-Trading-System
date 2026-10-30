"""Compatibility re-exports for campaign resource helpers now owned by compute."""

from __future__ import annotations

from compute.slurm.campaign_worker_resources import (
    ROOT as ROOT,
)
from compute.slurm.campaign_worker_resources import (
    WORKER_CPU_AFFINITY_GUARD as WORKER_CPU_AFFINITY_GUARD,
)
from compute.slurm.campaign_worker_resources import (
    available_resources as available_resources,
)
from compute.slurm.campaign_worker_resources import (
    cgroup_memory_file as cgroup_memory_file,
)
from compute.slurm.campaign_worker_resources import (
    cpu_mask_for_slot as cpu_mask_for_slot,
)
from compute.slurm.campaign_worker_resources import (
    expand_slurm_hosts as expand_slurm_hosts,
)
from compute.slurm.campaign_worker_resources import (
    resolve_worker_nodes as resolve_worker_nodes,
)
from compute.slurm.campaign_worker_resources import (
    sample_resources as sample_resources,
)
from compute.slurm.campaign_worker_resources import (
    utc as utc,
)
from compute.slurm.campaign_worker_resources import (
    worker_command as worker_command,
)
from compute.slurm.campaign_worker_resources import (
    worker_node_cpu_ids as worker_node_cpu_ids,
)

__all__ = [
    "ROOT",
    "WORKER_CPU_AFFINITY_GUARD",
    "available_resources",
    "cgroup_memory_file",
    "cpu_mask_for_slot",
    "expand_slurm_hosts",
    "resolve_worker_nodes",
    "sample_resources",
    "utc",
    "worker_command",
    "worker_node_cpu_ids",
]
