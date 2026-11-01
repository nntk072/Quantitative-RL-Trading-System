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

## Reader paths and API reference

Organize the public site by reader questions and framework subjects, then link
to source paths and generated AutoAPI for exact details. Keep the global
navigation shallow and assign maintained pages to a section toctree. The
generated `docs/documentation_inventory.json` records page type, status, local
links, and toctree/orphan status; refresh it with
`python -m tools.documentation.inventory --write` after documentation changes.

## Notebooks

Each notebook declares a title, tier, expected runtime, hardware, and data
source in metadata. Tier A notebooks use small deterministic CPU examples and
execute in both the notebook check and Sphinx build. Tier B notebooks render
tracked frozen evidence without training; Tier C may describe a full workflow
but must not execute in docs CI. Never silently skip a broken Tier A cell.
Keep outputs small and avoid machine-specific paths or secrets. Figures need a
title, units, legend when useful, and nearby text explaining what the reader
should see.

## Research claims and reproducibility

Give each prominent result a status, method, evidence source, limitations, and
reproduction level. R1 means evidence can be inspected; R2 means tracked
machine-readable inputs can recompute the stated tables or figures; R3 adds
frozen checkpoint replay; R4 adds sufficient inputs to retrain. Do not infer a
higher level from a configuration file alone. Distinguish software trace,
reproduce, replay, and retrain.

The documentation gate validates notebooks, evidence assets, page inventory,
maintained links and source references, then builds the Sphinx site with
warnings as errors. See the [visual index](../architecture/visual_index), the
[documentation inventory](../documentation_inventory.json), and the
[documentation maintenance map](../MAINTAINING.md) for page ownership.
