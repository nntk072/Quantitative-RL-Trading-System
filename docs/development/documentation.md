# Source documentation and comment policy

Write documentation at the layer that owns the information. Public Python
callables explain their contract in Google-style docstrings; comments explain
non-obvious constraints in the implementation; package guides orient readers;
reference pages record exact schemas and settings. Changelogs describe
meaningful project changes instead of accumulating in source files.

## Google-style docstrings

Document stable public functions, classes, protocols, and exported data types
with a short summary and the details needed to call or implement them. Use
Google section names such as `Args`, `Returns`, `Raises`, `Yields`, and
`Attributes` when those details need explanation. Keep types in annotations
and explain units, ordering, defaults, side effects, validation, and error
conditions in prose. Do not repeat an obvious type annotation as prose.

Private helpers do not need a docstring when their purpose and behavior are
clear from the implementation. Experimental APIs should identify their scope
and stability. Avoid maintaining NumPy-style section headings alongside the
Google convention.

## Comments

Keep a comment when it explains why code preserves a causal boundary,
compatibility condition, numerical assumption, external-system quirk, or
non-obvious invariant. Remove comments that only restate the next statement,
generic section labels, stale TODOs, commented-out code, and source-file change
logs. Put project history in `CHANGELOG.md` or Git history.

## Diagrams

Add a diagram when it makes a real relationship or sequence easier to
understand. Use flowcharts for dependencies and data movement, sequence
diagrams for runtime chronology, and state diagrams for lifecycle rules. Use
class diagrams only for stable object relationships. A guide does not need a
diagram when prose or a short table communicates the subsystem more clearly.

The documentation gate builds the Sphinx site with warnings as errors and
checks maintained links and source references. See the
[documentation maintenance map](../MAINTAINING.md) for page ownership.
