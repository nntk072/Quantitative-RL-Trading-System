# Artifacts and evidence lineage

**Status:** draft
**Use this when:** You need to locate what produced a number, verify its inputs, or preserve a result for reproduction.

## Summary and use this when

Start with a claim and follow its manifest references to the exact run and
retained bytes. A semantic identifier expresses how an artifact was derived.
A file digest identifies the bytes that were saved.

- Look up run, data, checkpoint and report identities before reanalysis.
- Verify report artifact hashes against the on-disk bytes.
- Record the resolved configuration and observed source state.
- Preserve the parent chain when promoting a reviewed reference artifact.

## Key terms

- [Artifact and evidence levels](../../glossary.md)
- [Artifact storage and provenance](../../reference/artifacts.md)
- [Research result identity](../../research/result_identity_and_evidence.md)

## Explanation

### The rule

`artifact_id` serializes semantic inputs as sorted, compact JSON and hashes
the encoding with SHA-256. The kind prefixes the digest in the displayed
identifier. Relevant semantic input identity must be supplied by the calling
domain. `file_sha256` reads bytes from disk and hashes them separately.

`ArtifactManifest` carries the kind, ID, schema version, creation metadata,
retention class, parent IDs and provenance. Consumers need the producer's
metadata to interpret the payload. A parent ID names a dependency, so a
review must also locate and verify the corresponding record.

The generated evaluation manifest records existing training, validation
and testing partitions. It lists known numerical artifacts found in those
partitions and their hashes. It can record the configuration digest and
parent training or reanalysis manifests when present. An absent artifact
needs an explicit availability decision at the research result boundary.

### Why promotion has its own contract

`promote_to_baseline` requires the promotable retention class, parent IDs
and a source revision. It stages a copy in the destination parent directory,
validates the staged payload, and checks that validation did not alter its
digest before publishing the directory.

That promotion records validation of the staged artifact by a particular
validator. Research claim verification also needs the period role, run
identity and the artifacts that support the measured outcome.

### Failure modes

- Treating a filename or a timestamp as immutable identity can link to
  replaced bytes.
- Reusing a semantic ID with incomplete derivation inputs hides a setting change.
- Quoting HEAD alone can hide execution from a dirty checkout.
- Treating an evaluation manifest as a completeness check can hide absent
  ledgers or metrics.
- A promoted reference can outlive the availability of its raw inputs.

## Worked example

The Tier A notebook computes two semantic IDs from reordered input mappings,
then hashes a synthetic payload and detects a changed byte sequence. Its
temporary directory contains all the data it uses.

```{toctree}
:hidden:

examples/artifacts-evidence-lineage
```

## Tasks

- Verify report lineage with the [artifact reference](../../reference/artifacts.md).
- Review output formats using the [manifest schemas](../../reference/manifest_schemas.md).
- Follow [research result identity](../../research/result_identity_and_evidence.md) for v2 record requirements.
- Use the [artifact lineage contract](../../reference/subjects/artifacts-evidence-lineage.md) to evaluate availability and promotion.

## Contract

| Item | Meaning | Source |
|---|---|---|
| Artifact ID | Kind plus SHA-256 of canonical semantic input encoding | `artifacts/identity.py::artifact_id` |
| Bytes | SHA-256 of the actual file contents | `artifacts/identity.py::file_sha256` |
| Manifest metadata | Positive schema version, retention, parent IDs and provenance | `artifacts/manifest.py::ArtifactManifest` |
| Evaluation envelope | Known available artifacts and parent manifest checksums | `evaluation/reporting/evaluation_manifest.py::build_evaluation_manifest` |
| Baseline promotion | Validation of staged copy with parent and source revision | `artifacts/promotion.py::promote_to_baseline` |

## Verify

- `tests/unit/artifacts/test_artifact_lifecycle.py` covers identity and
  manifest handling.
- `tests/unit/artifacts/test_artifact_promotion.py` covers validation and
  publication at the baseline destination.
- `tests/unit/evaluation/test_evaluation_manifest.py` covers the evaluation
  envelope.
- `tests/unit/research/test_result_manifest_v2.py` covers the research
  result verifier and schema.

## Limits and common mistakes

- A content digest verifies identity given access to the bytes. It cannot
  recover bytes that are absent.
- Change visibility in a dirty-source record depends on the source files and
  hashes captured by the producer.
- An optional parent or optional config hash in an evaluation envelope can
  still be required for the claim being reviewed.
- Treat retention class, schema version, lineage and reproduction level as
  separate fields with separate verification requirements.
- Preserve the identity of a report-only period on every edge from data to claim.

## Change checklist

- List every semantic input that can change the artifact and its ID.
- Record source state, config, data and cache inputs from the executed run.
- Hash the ledgers and outputs referenced by each reported claim.
- Identify how the analysis resolves relative paths before relocating files.
- Read the retained hash record before generating any replacement report.
- Verify referenced files and parent manifests are reachable and unchanged.
- Record recovery, transformation and promotion with their source identities.
- Recheck what reproduction is possible with the artifacts actually retained.

## Review procedure

1. Locate the manifest associated with the reported value. Resolve the claim,
   comparison and run identifiers before using any filenames in prose.
2. Confirm the producer's schema version and the role of each artifact.
   Check whether the listed digest represents semantic inputs or stored bytes.
3. Recover the precise checkout, dirty-source record and resolved settings.
   Compare the data identity and feature compatibility metadata separately.
4. Open the saved ledgers, hash the exact files and verify any retained
   evaluation parent manifests. Record missing files and unexplained changes.
5. Trace reanalysis through the frozen checkpoint, evaluation interval and
   settings where those identities exist. Preserve the original producer record.
6. For baseline promotion, inspect parent IDs, source revision, the staged
   payload digest, validator identity and recorded validation.
7. Recompute using the retained format and exact scope before declaring a
   recomputation level. Keep narrower inspection claims within their scope.
8. Record the remaining dependency for any replay or retraining claim that
   needs artifacts beyond the available evaluation bundle.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `evidence_reporting_engineer`
