"""Import and behavior smoke test for the native CPU wheel."""

import pytest

qrl_native = pytest.importorskip("qrl_native")


def test_schema_version_matches_the_rust_contract() -> None:
    assert qrl_native.domain_schema_version() == 1


def test_checked_add_returns_the_sum() -> None:
    assert qrl_native.checked_add_units(2, 3) == 5


def test_overflow_raises_instead_of_wrapping() -> None:
    with pytest.raises(OverflowError):
        qrl_native.checked_add_units(2**63 - 1, 1)


def test_non_integer_input_is_rejected() -> None:
    with pytest.raises(TypeError):
        qrl_native.checked_add_units(1.5, 2)
