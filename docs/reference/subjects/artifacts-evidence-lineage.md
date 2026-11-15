# Artifacts and evidence lineage contract

**Status:** draft
**Scope:** Distinct identity, lineage and integrity fields used to verify a research result.

| Boundary | Record or type | Review contract |
|---|---|---|
| Semantic artifact identity | `ArtifactId` | Displayed as `kind:digest`, with the digest from sorted compact JSON of semantic inputs. |
| Payload identity | `file_sha256` | Verify the digest against the retained bytes of the exact file. |
| Generic manifest | `ArtifactManifest` | Nonempty kind and ID, positive integer schema version, creation string, retention enum, parent ID tuple and provenance. |
| Evaluation envelope | `evaluation-artifacts-v1` | Records existing recognized partitions and files, with config and parent hashes when available. Review completeness for the specific claim separately. |
| Baseline promotion | `promote_to_baseline` | Requires promotable retention, parent IDs and source revision. The destination receives the validated staged payload and manifest. |
| Research result v2 | `qrl.research_result_manifest.v2` | Record run IDs, comparisons, claims, artifacts and reasons for unavailable draft identities. A frozen manifest requires resolved identity and a freeze timestamp. |

When reconstructing a metric, follow claim to comparison to run to ledger.
Pair every path reference with the expected hash and record any missing
dependency. A directory name alone cannot identify an evaluated policy or
period. Check retained source-state and configuration records when an
artifact was produced from a modified checkout.

Sources are `artifacts/identity.py`, `artifacts/manifest.py`,
`artifacts/promotion.py`, `evaluation/reporting/evaluation_manifest.py`
and `schemas/research_result_manifest_v2.schema.json`.
See [result identity](../../research/result_identity_and_evidence.md)
and the [subject guide](../../subjects/E_evaluation_research/artifacts-evidence-lineage.md).
