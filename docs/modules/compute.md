# Compute module

## Purpose

Compute support describes the available execution device and resources so
training and evaluation can run on a suitable machine. It also provides
resource-aware worker dispatch and scheduler integration.

## Inputs and outputs

| Receives | Produces |
|---|---|
| Workload resource needs, compatible device capabilities, and live scheduler state | Resource choice, worker layout, allocation operations, and measured utilization/throughput |

## Resource flow

```mermaid
flowchart LR
    Request[Training or evaluation workload] --> Estimate[Estimate CPU, RAM, and GPU needs]
    Inventory[Live scheduler and device inventory] --> Select[Choose compatible allocation]
    Estimate --> Select
    Select --> Workers[Worker and vector-environment layout]
    Workers --> Measure[Measure throughput and utilization]
```

An allocated GPU is not the same as a GPU in active use. Performance reports
should distinguish allocated resources, measured utilization, CPU/RAM use,
and end-to-end learning throughput. More workers can reduce throughput when
CPU, memory bandwidth, interprocess communication, or GPU inference becomes
the bottleneck.

## Limitations

Resource availability changes over time. A throughput result belongs to its
measured hardware, software environment, model geometry, and workload; it is
not a general device guarantee.

## UML

This UML shows workload needs, hardware capability, scheduling, execution, and
measured resource outcomes as separate concepts.

```mermaid
classDiagram
    class JobSpec {
      +command
      +cpu_count
      +memory_bytes
      +accelerator_request
    }
    class ResourceProfile {
      +cpu_count
      +memory_bytes
      +device_type
    }
    class DeviceCapabilities {
      +device_name
      +memory_bytes
      +supported_precision
    }
    class ExecutionBackend {
      +submit(JobSpec)
      +status(job_id)
    }
    class SlurmBackend
    class LocalBackend
    class ResourceInventory
    class WorkerLayout {
      +environment_count
      +process_count
    }
    class ResourceMeasurement {
      +cpu_use
      +host_memory
      +gpu_use
      +throughput
    }
    JobSpec --> ResourceProfile : requests
    ResourceInventory o-- DeviceCapabilities
    ResourceInventory --> ResourceProfile : informs
    SlurmBackend ..|> ExecutionBackend
    LocalBackend ..|> ExecutionBackend
    ExecutionBackend --> JobSpec : runs
    JobSpec --> WorkerLayout : configures
    WorkerLayout --> ResourceMeasurement : measured as
```

## Implementation reference

The `compute/` module owns device discovery, resource profiles, and scheduler
adapters. Cluster operation rules are in [Triton operations](../operations/triton.md).
