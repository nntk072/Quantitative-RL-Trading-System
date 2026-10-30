# Artifacts Domain Map

## Ownership

Own logical artifact identity, manifests, atomic persistence mechanics, validation,
retention, and promotion. Producing domains own the meaning and schemas of their
artifacts.

## Boundary

- Public contracts: `artifacts/contracts.py` (`ArtifactRef`, manifest contracts).
- Identity and lookup: `artifacts/identity.py` and `artifacts/layout.py`.
- Lifecycle promotion: `artifacts/promotion.py`.
- Atomic byte/text/JSON writes: `artifacts/atomic.py`.
- Depends only on the standard library. Producers may depend on `artifacts/`.
- Must not infer scientific meaning from directory names or import workflow packages.

## Invariants and Tests

- Logical keys and content digests are independent of physical layout.
- Manifest validation binds the recorded identity to the source revision and run.
- Writes are atomic; promotion requires explicit parent and revision identity.
- Focused tests: `tests/unit/artifacts/test_artifact_lifecycle.py`, `tests/unit/artifacts/test_artifact_promotion.py`.

## Change Map

| Task | Axis | Start file | Contract and test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Change artifact identity or layout | identity contract | `artifacts/identity.py` | manifest identity; `tests/unit/artifacts/test_artifact_lifecycle.py` | identity/layout plus artifact tests | producer-owned schemas and artifact meaning |
| Change artifact promotion | lifecycle | `artifacts/promotion.py` | parent/source revision checks; `tests/unit/artifacts/test_artifact_promotion.py` | promotion lifecycle plus tests | artifact bytes and producer semantics |

## Axis of Change

- **Axis:** artifact identity, storage layout, and retention mechanics.
- **Owner:** `artifacts/` owns opaque references and persistence mechanics; producer domains own schemas and meaning.
- **Stable boundary:** artifact references, manifests, and atomic persistence functions.
- **Expected edit radius:** one identity or lifecycle module plus its contract test.
- **Must not depend on:** training, evaluation, model, trading, or experiment run semantics.

## Verified Source Paths

- `artifacts/contracts.py`
- `artifacts/identity.py`
- `artifacts/layout.py`
- `artifacts/promotion.py`
- `artifacts/atomic.py`
- `tests/unit/artifacts/test_artifact_lifecycle.py`
- `tests/unit/artifacts/test_artifact_promotion.py`
