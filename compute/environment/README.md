# Compute environment

`compute/environment/` discovers device capabilities and translates them into
training-device, precision, and resource-shape recommendations. It does not
submit jobs or choose a research variant.

| Module | Responsibility |
|---|---|
| `capabilities.py` | Describe available compute and device features. |
| `device.py` | Resolve a configured device and suggest environment, rollout, batch, and epoch sizes from resource limits. |
| `precision.py` | Select supported autocast settings and configure accelerator precision. |

The training setup consumes these helpers. Resource suggestions depend on
visible CPU, host memory, and accelerator capacity; they are advisory and do
not replace the scheduler's live allocation inventory. Focused coverage is in
`tests/unit/compute/`.
