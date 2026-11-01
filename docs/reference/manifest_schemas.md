# Manifest and provenance schemas

Manifests connect artifact identity and lineage. A schema version describes a
serialization contract; it does not establish that the recorded experiment is
methodologically valid or that its metrics passed acceptance gates.

## Artifact manifest

`artifacts/manifest.py::ArtifactManifest` serializes these fields:

| Field | Type | Contract |
|---|---|---|
| `kind` | string | Non-empty artifact category. |
| `artifact_id` | string | Non-empty stable identity. |
| `schema_version` | positive integer | Manifest schema version; defaults to `1`. |
| `created_at` | ISO timestamp string | Creation time; generated in UTC by default. |
| `retention` | retention enum value | Lifecycle class such as run-retained or rebuildable. |
| `parents` | array of strings | Parent artifact IDs; empty by default. |
| `provenance` | object | JSON-compatible source/config/data details. |

`artifacts/identity.py::artifact_id` hashes canonical JSON semantic inputs with
SHA-256. The content identity is independent of the filesystem path. Parent
IDs express lineage; writers and validators remain responsible for checking
that references exist and correspond to the produced content.

## Research evidence schemas

The checked-in JSON Schemas under `schemas/` define machine-validated
research records:

| Schema | Identifier | Purpose |
|---|---|---|
| `schemas/research_result_manifest.schema.json` | `qrl.research_result_manifest.v1` | Artifact paths, roles, media types, notes, and SHA-256 content hashes for a research result. |
| `schemas/research_trial_ledger.schema.json` | `qrl.research_trial_ledger.v1` | Append-only run and attempt inventory, including failed, interrupted, inactive, and excluded work. |

Use the schema as the validation source rather than hand-maintaining a second
field list in prose. Updates to a schema identifier or required fields must
retain readers for archived records or include an explicit migration map.

## Training and experiment provenance

Training records include resolved algorithm/encoder/reward and run settings,
seed, requested/effective steps and environment count, action and observation
schemas, ordered sequence-feature schema, and evaluation outputs. Experiment
run manifests add the experiment ID, variant/seed job keys, attempts, status,
source snapshot, and artifact references. These files do not all share one
top-level schema version; consumers must validate the specific producer's
contract and preserve legacy readers where archived artifacts depend on them.

The artifact lifecycle and atomic writers are described in the
[artifact reference](artifacts.md). The run state machine is described in the
[experiment-run reference](experiment_runs.md), and model-facing schemas are
listed in [action](action_schemas.md), [observation](observation_schemas.md),
and [cache/version](cache_and_schema_versions.md) references.
