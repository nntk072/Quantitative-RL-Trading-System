"""Owner-approved pre-cutoff window of an MT5 export, split by label before any value is parsed (DATA-SCHEMAS).

Export rows are chronological, so a row is in the window when its DATE label sorts before the
cutoff. Lines on or after the cutoff are only counted; their values are never parsed, converted or
checked. A non-chronological export is refused, because a prefix window is then not defined.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class ExportWindow:
    """Header, in-window body lines, and line accounting for one export file.

    Attributes:
        header: Header line exactly as in the file.
        body: Non-empty data lines dated before the cutoff, in file order.
        lines_on_or_after_cutoff: Data lines dated on or after the cutoff (counted, not parsed).
        body_lines_in_file: All non-empty data lines in the file.
    """

    header: str
    body: list[str]
    lines_on_or_after_cutoff: int
    body_lines_in_file: int


def split_export_window(raw: bytes, window_before: str | None) -> ExportWindow:
    """Split raw export bytes into the pre-cutoff window and the count after it.

    Args:
        raw: Exact file bytes (ASCII, tab-separated, CRLF or LF).
        window_before: ``YYYY.MM.DD`` label cutoff, exclusive. None keeps every line.

    Returns:
        The window. Raises RuntimeError when an in-window row follows an out-of-window row.
    """
    text_lines = [line for line in raw.decode("ascii").splitlines() if line.strip()]
    header, body = text_lines[0], text_lines[1:]
    if window_before is None:
        return ExportWindow(header, body, 0, len(body))
    keep: list[str] = []
    after = 0
    for line in body:
        if line.split("\t", 1)[0] < window_before:
            if after:
                raise RuntimeError("export is not chronological: in-window row after cutoff")
            keep.append(line)
        else:
            after += 1
    return ExportWindow(header, keep, after, len(body))


def window_frame(window: ExportWindow) -> pd.DataFrame:
    """Parse the in-window lines into a string-typed frame with stripped column names.

    Args:
        window: Window returned by :func:`split_export_window`.

    Returns:
        One row per in-window line, in file order, with columns named without ``<>``.

    Raises:
        RuntimeError: If the parsed row count differs from the in-window line count.
    """
    frame = pd.read_csv(
        io.StringIO("\n".join([window.header, *window.body]) + "\n"), sep="\t", dtype=str
    ).rename(columns=lambda name: name.strip("<>"))
    if len(frame) != len(window.body):
        raise RuntimeError(f"row count mismatch: parsed {len(frame)}, lines {len(window.body)}")
    return frame
