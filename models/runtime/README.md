# Model runtime helpers

`models/runtime/` contains execution-time wrappers for model modules. Its
precision helper applies the configured autocast behavior to an extractor
without changing the model's architecture or checkpoint schema.

Device and dtype support is architecture-dependent. Keep accelerator
capability discovery in `compute/`; test wrapper parity and CPU behavior in
`tests/unit/models/` and `tests/unit/compute/`.
