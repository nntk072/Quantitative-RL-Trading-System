# Compute Domain Map

## Ownership

Own hardware capability discovery, accelerator precision selection, resource sizing,
and scheduler adapters. Learning composes the selected precision with model-specific
encoder behavior; models do not discover hardware.

## Boundary

- Public entry points: `compute/environment/capabilities.py`, `compute/environment/device.py`, `compute/environment/precision.py`, `compute/slurm/resources.py`, and `compute/slurm/campaign_worker_resources.py`.
- Device, resource, job, and backend contracts live in `compute/contracts.py`.
- Device discovery may use Torch; compute must not import model or learner classes.
- Slurm is an adapter. Scientific result identity must not depend on job IDs.
- Worker allocation/resource sampling and persistent dispatch mechanics belong to `compute.slurm`; campaign policy and cache-failure recovery belong to `experiments`.
- `experiments.campaigns.resources` and `compute.slurm.resume` remain compatibility adapters for existing callers.

## Invariants and Tests

- Respect the live allocation and CPU/RAM/GPU inventory before a real request.
- Never fan out short Slurm steps; use an existing allocation when available.
- Focused tests: `tests/integration/test_device.py`, `tests/test_experiments/test_triton_campaign_worker_dispatch.py`.

## Change Map

| Task | Axis | Start file | Contract and test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Add a compute backend | execution adapter | `compute/slurm/resources.py` | resource request semantics; scheduler tests | one backend and contract tests | model constructors and scientific behavior |
| Change accelerator precision | device runtime policy | `compute/environment/precision.py` | capability-driven dtype; `tests/integration/test_device.py` | hardware selection and runtime setup | model-specific encoder behavior |
| Change campaign worker resource sampling | Slurm worker mechanics | `compute/slurm/campaign_worker_resources.py` | worker request contracts; `tests/test_experiments/test_campaign_resources.py` | resource sampling and dispatch only | campaign policy and recovery semantics |

## Axis of Change

- **Axis:** hardware capability discovery and workload execution backend.
- **Owner:** `compute/` owns resource facts and scheduler adapters.
- **Stable boundary:** `DeviceCapabilities`, `ResourceProfile`, `JobSpec`, and `ExecutionBackend`.
- **Expected edit radius:** one backend adapter and its contract tests.
- **Must not depend on:** model classes or scientific policy.

## Verified Source Paths

- `compute/environment/device.py`
- `compute/environment/capabilities.py`
- `compute/environment/precision.py`
- `compute/slurm/resources.py`
- `compute/slurm/campaign_worker_resources.py`
- `compute/slurm/resume.py` (compatibility adapter)
- `tests/integration/test_device.py`
- `tests/test_experiments/test_triton_campaign_worker_dispatch.py`
- `compute/contracts.py`
