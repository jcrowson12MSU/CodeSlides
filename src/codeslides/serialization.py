"""Save per-Session cell edits back into a deck's .py file. See
ARCHITECTURE.md section 2 (File format) and TODO.md #11.

The file format is plain, `ast`-parseable Python (no custom syntax), and
`Cell.source` (via `inspect.getsource`) is already exactly the on-disk
text of a cell's decorator + function definition. That means "saving" an
edit doesn't require regenerating the file from the in-memory Deck model
(which would risk losing comments, import order, blank lines, anything
not represented in Deck/Cell/Element) -- it only requires locating each
edited cell's original line span in the *current* file text and
substituting the new source text in place, leaving everything else
byte-identical.
"""

from __future__ import annotations

import ast
from pathlib import Path


class SaveConflictError(ValueError):
    """Raised when the on-disk file no longer contains a cell a caller is
    trying to save an edit for (e.g. it was renamed/deleted by a separate
    edit to the file since the Session started)."""


class InvalidSourceError(ValueError):
    """Raised when applying `source_overrides` would leave the file not
    parsing as valid Python. An `instance="editable"` cell's live source is
    routinely invalid mid-keystroke (an unclosed paren, a dangling colon)
    -- that's fine to run against (it just errors that one cell, see
    kernel.py's `on_cell_edited`), but it must never be written to disk:
    a save that corrupts the deck's own file would break every future
    load of it, not just this one Session's view."""


def _cell_line_spans(source: str) -> dict[str, tuple[int, int]]:
    """Map each top-level `@app.cell`-decorated function's name to its
    (start_line, end_line) span, 1-indexed and inclusive, covering its
    decorator(s) through its final line. `ast.FunctionDef.lineno` points
    at the `def` line, not any decorator above it (true even as of Python
    3.13) -- the decorator's own `lineno` is what `inspect.getsource`
    actually uses to include it, so we do the same here.
    """
    tree = ast.parse(source)
    spans: dict[str, tuple[int, int]] = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        spans[node.name] = (start, node.end_lineno)
    return spans


def _apply_overrides(original: str, spans: dict[str, tuple[int, int]], source_overrides: dict[str, str]) -> str:
    lines = original.splitlines(keepends=True)
    # Apply replacements bottom-to-top so earlier line numbers stay valid
    # as later spans are substituted.
    for name, (start, end) in sorted(spans.items(), key=lambda kv: kv[1][0], reverse=True):
        if name not in source_overrides:
            continue
        replacement = source_overrides[name]
        if not replacement.endswith("\n"):
            replacement += "\n"
        lines[start - 1 : end] = [replacement]
    return "".join(lines)


def save_edits(deck_path: str, source_overrides: dict[str, str]) -> None:
    """Rewrite `deck_path` on disk, replacing each named cell's source
    text with its override. `source_overrides` maps cell name -> full
    replacement source (decorator line(s) through the end of the function
    body, exactly the shape of `Cell.source`/`session.source_overrides`).

    Cells not present in `source_overrides` are left untouched, including
    their exact original text. Raises `SaveConflictError` if the file no
    longer defines a cell being saved (it changed on disk since the
    Session's baseline was loaded), or `InvalidSourceError` if applying
    the overrides would leave the file not parsing as valid Python --
    checked against the *whole resulting file*, not just each override in
    isolation, before anything is written.
    """
    if not source_overrides:
        return

    path = Path(deck_path)
    original = path.read_text()
    spans = _cell_line_spans(original)

    missing = [name for name in source_overrides if name not in spans]
    if missing:
        raise SaveConflictError(
            f"cannot save edits for cells no longer defined in {deck_path!r}: {missing}"
        )

    updated = _apply_overrides(original, spans, source_overrides)
    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise InvalidSourceError(
            f"edit to cell {sorted(source_overrides)!r} would leave {deck_path!r} with invalid "
            f"Python syntax, not saved: {exc}"
        ) from exc

    path.write_text(updated)
