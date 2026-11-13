"""Historical evidence catalog with normalized customer-facing taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_HISTORY = ROOT / "config/research/history.yaml"


@dataclass(frozen=True, slots=True)
class HistoricalEvidence:
    """One normalized historical evidence collection."""

    evidence_id: str
    domain: str
    path: Path
    disposition: str
    summary: str


def load_history(path: str | Path = DEFAULT_HISTORY) -> tuple[HistoricalEvidence, ...]:
    """Load historical evidence without modifying source artifacts.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by load_history.
    """
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported historical evidence catalog")
    entries = raw.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("historical evidence catalog requires entries")
    result: list[HistoricalEvidence] = []
    for evidence_id, value in entries.items():
        if not isinstance(evidence_id, str) or not isinstance(value, dict):
            raise ValueError("historical evidence entries must be string-keyed mappings")
        domain = value.get("domain")
        raw_path = value.get("path")
        disposition = value.get("disposition")
        summary = value.get("summary")
        if (
            not isinstance(domain, str)
            or not domain.strip()
            or not isinstance(raw_path, str)
            or not raw_path.strip()
            or not isinstance(disposition, str)
            or not disposition.strip()
            or not isinstance(summary, str)
            or not summary.strip()
        ):
            raise ValueError(f"historical evidence entry {evidence_id!r} is incomplete")
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"historical evidence path escapes repository: {raw_path}")
        source = (ROOT / relative).resolve()
        if not source.is_dir():
            raise FileNotFoundError(source)
        result.append(
            HistoricalEvidence(
                evidence_id=evidence_id,
                domain=domain,
                path=source,
                disposition=disposition,
                summary=summary,
            )
        )
    return tuple(result)


def render_markdown(entries: tuple[HistoricalEvidence, ...]) -> str:
    """Render a concise domain-oriented index while retaining source paths.

    Args:
        entries: Historical evidence records to render.

    Returns:
        Result produced by render_markdown.
    """
    domains = sorted({entry.domain for entry in entries})
    lines = [
        "# Historical research evidence",
        "",
        "This index rewrites historical evidence into the current research taxonomy. "
        "It does not rewrite or replace the underlying evidence files.",
        "",
    ]
    for domain in domains:
        lines.extend((f"## {domain.replace('_', ' ').title()}", ""))
        for entry in entries:
            if entry.domain != domain:
                continue
            relative = entry.path.relative_to(ROOT).as_posix()
            lines.append(
                f"- **{entry.evidence_id.replace('_', ' ').title()}** — "
                f"{entry.summary} Disposition: `{entry.disposition}`. "
                f"Source: `{relative}`."
            )
        lines.append("")
    return "\n".join(lines)


__all__ = ["DEFAULT_HISTORY", "HistoricalEvidence", "load_history", "render_markdown"]
