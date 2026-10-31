from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from scripts.dev.security.dependency_audit import (
    findings_from_report,
    load_exceptions,
    unexpected_skips,
    uv_command,
)
from scripts.dev.security.secret_scan import findings_from_baseline
from scripts.dev.security.secret_scan import uv_command as secret_uv_command


def _exception_file(tmp_path: Path, contents: str) -> Path:
    path = tmp_path / "exceptions.toml"
    path.write_text(contents, encoding="utf-8")
    return path


def test_uv_command_prefers_explicit_architecture_override(monkeypatch, tmp_path: Path) -> None:
    native_uv = tmp_path / "uv-aarch64"
    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.delenv("QRL_UV", raising=False)
    monkeypatch.setenv("THESIS_UV", str(native_uv))
    monkeypatch.setattr(
        "scripts.dev.security.dependency_audit.shutil.which", lambda _: "/usr/bin/uv"
    )

    assert uv_command() == str(native_uv)


def test_dependency_audit_prefers_canonical_qrl_uv(monkeypatch, tmp_path: Path) -> None:
    native_uv = tmp_path / "uv-qrl"
    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.setenv("QRL_UV", str(native_uv))
    monkeypatch.setenv("THESIS_UV", "/deprecated/uv")
    monkeypatch.setattr(
        "scripts.dev.security.dependency_audit.shutil.which", lambda _: "/usr/bin/uv"
    )

    assert uv_command() == str(native_uv)


def test_secret_scanner_uv_command_prefers_architecture_override(
    monkeypatch, tmp_path: Path
) -> None:
    native_uv = tmp_path / "uv-aarch64"
    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.delenv("QRL_UV", raising=False)
    monkeypatch.setenv("THESIS_UV", str(native_uv))
    monkeypatch.setattr("scripts.dev.security.secret_scan.shutil.which", lambda _: "/usr/bin/uv")

    assert secret_uv_command() == str(native_uv)


def test_secret_scanner_prefers_canonical_qrl_uv(monkeypatch, tmp_path: Path) -> None:
    native_uv = tmp_path / "uv-qrl"
    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.setenv("QRL_UV", str(native_uv))
    monkeypatch.setenv("THESIS_UV", "/deprecated/uv")
    monkeypatch.setattr("scripts.dev.security.secret_scan.shutil.which", lambda _: "/usr/bin/uv")

    assert secret_uv_command() == str(native_uv)


def test_empty_exception_file_is_valid(tmp_path: Path) -> None:
    path = _exception_file(tmp_path, "# intentionally empty\n")

    assert load_exceptions(path, today=dt.date(2026, 10, 21)) == set()


def test_valid_exception_matches_normalized_package_name(tmp_path: Path) -> None:
    path = _exception_file(
        tmp_path,
        """
[[exception]]
advisory = "GHSA-ABCD-1234-EFGH"
package = "Example_Package"
reason = "A reviewed upstream compatibility blocker."
impact = "The affected optional path is disabled in thesis runs."
review_after = 2026-11-01
""",
    )

    assert load_exceptions(path, today=dt.date(2026, 10, 21)) == {
        ("example-package", "GHSA-ABCD-1234-EFGH")
    }


def test_expired_exception_fails_closed(tmp_path: Path) -> None:
    path = _exception_file(
        tmp_path,
        """
[[exception]]
advisory = "CVE-2026-0001"
package = "example-package"
reason = "temporary"
impact = "reviewed"
review_after = 2026-10-20
""",
    )

    with pytest.raises(ValueError, match="expired"):
        load_exceptions(path, today=dt.date(2026, 10, 21))


def test_missing_exception_field_fails_closed(tmp_path: Path) -> None:
    path = _exception_file(
        tmp_path,
        """
[[exception]]
advisory = "CVE-2026-0001"
package = "example-package"
reason = "temporary"
review_after = 2026-11-01
""",
    )

    with pytest.raises(ValueError, match="impact"):
        load_exceptions(path, today=dt.date(2026, 10, 21))


def test_findings_report_preserves_unique_advisories_and_skips() -> None:
    report = {
        "dependencies": [
            {
                "name": "Example_Package",
                "version": "1.0",
                "vulns": [{"id": "CVE-2026-0001"}, {"id": "CVE-2026-0001"}],
            },
            {
                "name": "torch",
                "version": None,
                "skip_reason": "local CUDA wheel unavailable from PyPI",
                "vulns": [],
            },
        ]
    }

    findings, skipped = findings_from_report(report)

    assert findings == [
        ("example-package", "CVE-2026-0001", "1.0"),
        ("example-package", "CVE-2026-0001", "1.0"),
    ]
    assert skipped == ["torch@unknown: local CUDA wheel unavailable from PyPI"]


def test_findings_report_rejects_unidentified_advisory() -> None:
    with pytest.raises(ValueError, match="no advisory ID"):
        findings_from_report(
            {"dependencies": [{"name": "example-package", "version": "1.0", "vulns": [{}]}]}
        )


def test_only_the_reviewed_cuda_torch_skip_is_allowed() -> None:
    assert (
        unexpected_skips(
            [
                "torch@unknown: Dependency not found on PyPI and could not be audited: "
                "torch (2.14.0+cu130)"
            ]
        )
        == []
    )
    assert unexpected_skips(["example-package@1.0: package metadata unavailable"]) == [
        "example-package@1.0: package metadata unavailable"
    ]


def test_secret_scan_metadata_omits_matched_secret_values() -> None:
    baseline = {
        "results": {
            "tests/test_fixture.py": [
                {
                    "line_number": 12,
                    "type": "Secret Keyword",
                    "hashed_secret": "not reported",  # pragma: allowlist secret
                }
            ]
        }
    }

    assert findings_from_baseline(baseline) == [("tests/test_fixture.py", 12, "Secret Keyword")]


def test_secret_scan_rejects_malformed_finding() -> None:
    with pytest.raises(ValueError, match="location metadata"):
        findings_from_baseline({"results": {"tests/test_fixture.py": [{"type": "Unknown"}]}})
