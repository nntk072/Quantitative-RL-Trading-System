"""Stacked box tables for the terminal dashboard.

Each box has a ``---`` border, a ``| TITLE |`` header, and content lines.
Content lines are plain single-line strings so column tables and key/value
rows can share one renderer. Newlines inside a line are folded to spaces so
a multi-line blob can never blow up the computed width.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def render_box_table(boxes: Sequence[tuple[str, Sequence[str]]]) -> str:
    """Render ``[(TITLE, [line, ...]), ...]`` as stacked boxes.

    Every line of every box shares one width computed from the longest
    content line, so borders always match the rows exactly.

    Args:
        boxes: Items supplied for the boxes, in input order.

    Returns:
        Text returned by ``render_box_table``.
    """
    clean: list[tuple[str, list[str]]] = []
    width = 1
    for title, lines in boxes:
        flat = [str(line).replace("\n", " ").replace("\r", " ") for line in lines]
        clean.append((str(title), flat))
        for line in flat:
            width = max(width, len(line))
        width = max(width, len(str(title)))
    if not clean:
        return ""

    out: list[str] = []
    for index, (title, lines) in enumerate(clean):
        if index:
            out.append("")
        border = "-" * (width + 4)
        out.append(border)
        out.append(f"| {title.upper():<{width}} |")
        out.append(border)
        for line in lines:
            out.append(f"| {line:<{width}} |")
        out.append(border)
    return "\n".join(out)


def kv_widths(pairs: Iterable[tuple[str, str]]) -> tuple[int, int]:
    """Shared key/value column widths for a flat metric box.

    Args:
        pairs: Items supplied for the pairs, in input order.

    Returns:
        Values returned by ``kv_widths``, in the declared order.
    """
    items = list(pairs)
    key_width = max((len(str(key)) for key, _ in items), default=1) + 2
    value_width = max((len(str(value)) for _, value in items), default=1) + 2
    return key_width, value_width


def kv_lines(
    pairs: Iterable[tuple[str, str]],
    key_width: int,
    value_width: int,
) -> list[str]:
    """Align key/value pairs with shared widths (keys left, values right).

    Args:
        pairs: Items supplied for the pairs, in input order.
        key_width: Number specifying the key width for this operation.
        value_width: Number specifying the value width for this operation.

    Returns:
        Values returned by ``kv_lines``, in the declared order.
    """
    return [f"{str(key).ljust(key_width)}{str(value).rjust(value_width)}" for key, value in pairs]
