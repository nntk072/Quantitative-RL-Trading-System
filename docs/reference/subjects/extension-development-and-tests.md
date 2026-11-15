# Development and tests contract

**Status:** draft
**Source of truth:** `config/base/default.yaml`; `tests/conftest.py`; `pyproject.toml`; `tools/check`; `tools/documentation/check_notebooks.py`

## Collection and named gates

`execution_markers_for_test` resolves the suite from the path, in this
precedence: `architecture`, `integration`, `research`, `unit`. An
unclassified path raises `ValueError`. A recognized existing marker
suppresses the addition of a suite marker. The recognized set is `unit`,
`integration`, `architecture`, `slow`, `gpu`, `triton`, and `research`.

| Named gate | Scope |
|---|---|
| `./tools/check architecture` | `tests/architecture` |
| `./tools/check unit` | `unit and not slow and not integration and not architecture and not gpu and not triton and not research` |
| `./tools/check integration` | `integration and not slow` |
| `./tools/check contracts` | Config typo safety, action schema, experiment run artifacts, cache hash, and fit scope tests selected explicitly |
| `./tools/check docs` | Documentation contract tests, notebooks, generated assets/index validation and a Sphinx build |

## Public changes

- Declare runtime settings under the canonical config before use. Update
  the owner's schema reference and compatibility tests when wire meaning changes.
- Validate inputs at their owning package boundary and keep cross-package
  imports on the public interface.
- Tier A notebooks declare title, kernel, expected runtime, hardware, data,
  subject and owner. The notebook checker requires force execution mode,
  a first Markdown title cell, and executable code.
- See the [testing strategy](../../development/testing.md) and
  [documentation policy](../../development/documentation.md).
