# QA for artifacts and evidence lineage

**Status:** Five source claims verified against the 2026-11-15 working tree at
HEAD `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. `artifacts/identity.py::artifact_id` hashes sorted, compact JSON of the
   supplied semantic inputs and displays the digest under the supplied kind.
2. `artifacts/identity.py::file_sha256` hashes the file's bytes in chunks.
3. `artifacts/manifest.py::ArtifactManifest.__post_init__` checks nonempty
   kind, ID and creation strings, positive integer version, retention enum,
   the parent ID tuple and a provenance dictionary.
4. `evaluation/reporting/evaluation_manifest.py::build_evaluation_manifest`
   indexes existing recognized files by partition with SHA-256 digests and
   records available config and parent digests.
5. `artifacts/promotion.py::promote_to_baseline` requires promotable retention,
   parents and a source revision. It validates the staged payload, compares
   its digest before and after validation and publishes it with the manifest.

## Document and notebook checks

The hub has 150 lines and all 11 required sections. Its seven local links,
both reference links and the hidden notebook target resolve. Source and
test paths exist, and the claims also hold for the current modified
evaluation-envelope file.

The notebook has matching title and first heading, Python 3 kernel, Tier A,
bundled synthetic data, CPU, subject, owner and under-60-seconds metadata,
and forced MyST execution. Schema and metadata checks accepted it. Its
assert-bearing code cell has count 1, one saved stdout output and no saved
errors. Saved cell timing is 0.229 seconds. The output shows a stable
semantic ID and detection of altered synthetic payload bytes.

## Evidence limit

The saved demonstration uses a temporary synthetic ledger. QA inspected
the source and saved output. End-to-end artifact promotion and research
reproduction were outside this read-only review.
