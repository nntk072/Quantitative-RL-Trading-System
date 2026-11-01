# Model factory

`models/factory/` resolves registered encoder architecture identifiers to
their implementations. The registry is the code-side mapping used by model
construction; configured architecture names are checked against it by the
model catalog validation.

Add a model through its owning encoder module and registry entry, then update
configuration catalog and checkpoint compatibility tests. Do not duplicate the
architecture-name list in prose. Focused checks are in `tests/unit/models/`.
