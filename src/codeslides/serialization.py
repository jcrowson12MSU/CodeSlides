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
import textwrap
from collections.abc import Callable
from pathlib import Path

from codeslides.deck import Cell, Element


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


def _is_app_cell_decorator(dec: ast.expr) -> bool:
    """True for `@app.cell` (a bare `ast.Attribute`) or `@app.cell(...)`
    (an `ast.Call` wrapping one) -- specifically excludes `@app.slide(...)`,
    which is also a top-level-function decorator in the exact same file
    but names an entirely different kind of thing (`Deck.slides`, not
    `Deck.cells`). Matches on the decorator's own `.attr` being `"cell"`,
    not on the function being decorated at all -- a function decorated
    with `@app.slide(...)` is never a cell, no matter how much it looks
    like one syntactically (same `def name():` shape, same file)."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    return isinstance(target, ast.Attribute) and target.attr == "cell"


def _cell_line_spans(source: str) -> dict[str, tuple[int, int]]:
    """Map each top-level `@app.cell`-decorated function's name to its
    (start_line, end_line) span, 1-indexed and inclusive, covering its
    decorator(s) through its final line. `ast.FunctionDef.lineno` points
    at the `def` line, not any decorator above it (true even as of Python
    3.13) -- the decorator's own `lineno` is what `inspect.getsource`
    actually uses to include it, so we do the same here.

    Deliberately excludes a top-level function decorated with
    `@app.slide(...)` instead of `@app.cell(...)` -- both are ordinary
    `FunctionDef` nodes at the same syntactic level, so a naive "every
    top-level function" scan would misidentify a slide as a cell (a
    real bug caught by hand: `remove_cell`/`reorder_cells`, which use
    every key in this dict's return value rather than looking up one
    already-known cell name the way `rename_cell`/`append_cell` do,
    would otherwise try to delete/reorder a slide function as if it
    were a cell).
    """
    tree = ast.parse(source)
    spans: dict[str, tuple[int, int]] = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any(_is_app_cell_decorator(dec) for dec in node.decorator_list):
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


def new_cell_name(existing_names: frozenset[str] | set[str]) -> str:
    """Pick an unused `cell_N` identifier for a brand-new blank cell
    (TODO.md #21) -- `N` is the smallest positive integer not already
    taken, so repeatedly adding and removing cells doesn't accumulate
    ever-larger suffixes."""
    n = 1
    while f"cell_{n}" in existing_names:
        n += 1
    return f"cell_{n}"


def blank_cell_source(name: str) -> str:
    """The literal source text for a brand-new blank cell: a decorator
    line plus a `pass`-bodied function, matching exactly what
    `inspect.getsource` would produce for a hand-authored cell (the same
    shape `Cell.source` always holds elsewhere) -- `instance="editable"`
    so it's immediately live-editable in the browser without a second
    step, per TODO.md #21's "author picks elements/edits afterward"
    scope."""
    return f'@app.cell(instance="editable")\ndef {name}():\n    pass\n'


def _element_call_source(element: Element) -> str:
    """Serialize an Element back to the literal `ui.<kind>(...)` call that
    would construct it -- `Element.config` always holds exactly the
    constructor's own keyword arguments (every `ui.py` constructor takes
    keyword-only params matching its config keys 1:1, verified by
    construction: `ui.slider("s", **ui.slider("s", min=1, max=10).config)`
    round-trips), so this never needs per-kind formatting logic."""
    kwargs = ", ".join(f"{key}={value!r}" for key, value in element.config.items())
    return f'ui.{element.kind}({element.name!r}, {kwargs})' if kwargs else f"ui.{element.kind}({element.name!r})"


def _split_cell_source(source: str) -> tuple[str, list[str]]:
    """Split a cell's full source (decorator(s) through the end of the
    function body, the shape `Cell.source` always holds) into the
    function's `def name(...):` line and its body lines, discarding the
    decorator entirely -- used by `rename_cell`/`add_element`/
    `remove_element` to keep the body byte-identical while only
    regenerating the decorator and/or the `def` line."""
    tree = ast.parse(textwrap.dedent(source))
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        raise ValueError(f"expected exactly one function definition, found {len(func_defs)}")
    func = func_defs[0]
    lines = textwrap.dedent(source).splitlines()
    def_start = func.lineno - 1  # 0-indexed; the `def`/`async def` line itself
    return lines[def_start], lines[def_start + 1 :]


def display_source(source: str, hide_def: bool = False) -> str:
    """The `@app.cell(...)` decorator (however many lines it spans) is
    Deck-authoring boilerplate the user never asked to see or edit --
    strip it before source reaches a browser's code editor (server.py's
    `/api/deck` and `CellAdded`), while `Cell.source` itself keeps the
    decorator, since execution (kernel.py), the dependency graph
    (graph.py), and `.py` file round-tripping (`_apply_overrides` above)
    all still need it. Reuses `_split_cell_source`'s decorator-stripping
    logic rather than duplicating the AST walk.

    Also strips the docstring (if any): it's the cell's `notes` element
    content (`Cell.docstring`/`set_notes_docstring`), rendered in its own
    markdown viewer, not code -- showing it a second time verbatim at the
    top of the code editor would be redundant and, since the editor's
    text is exactly what a later save writes back via
    `reattach_decorator`, editing it there would fight with the notes
    viewer over the same line. Uses the *dedented* body from
    `_split_cell_source` (matching `_docstring_node`'s own dedented
    parse) so the line-span arithmetic lines up.

    `hide_def=True` (`@app.cell(hide_def=True)`, `Cell.hide_def`) also
    strips the `def name(...):` line itself, dedenting the body one level
    so it reads as ordinary top-level-looking statements instead of an
    indented function body -- for a cell whose `def` line is pure
    boilerplate (a typical no-parameter `setup()`), not something the
    author needs to see or edit. `reattach_decorator` is the inverse:
    it reinserts the real `def` line (re-indenting the body back under
    it) the same way it already reinserts the decorator."""
    def_line, body_lines = _split_cell_source(source)
    docstring_source = "\n".join([def_line, *body_lines]) + "\n"
    node = _docstring_node(docstring_source)
    if node is None:
        lines = docstring_source.splitlines()
    else:
        start, end = node.lineno - 1, node.end_lineno  # 0-indexed, exclusive end
        lines = docstring_source.splitlines()
        del lines[start:end]
    if hide_def:
        lines = textwrap.dedent("\n".join(lines[1:])).splitlines()
    return "\n".join(lines) + "\n"


def _decorator_prefix(source: str) -> str:
    """The literal decorator text (however many lines it spans) above a
    cell's `def` line, or `""` if it has none -- the inverse of
    `_split_cell_source`, which discards this same text."""
    tree = ast.parse(textwrap.dedent(source))
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    func = func_defs[0]
    def_start = func.lineno - 1  # 0-indexed; the `def`/`async def` line itself
    lines = textwrap.dedent(source).splitlines()[:def_start]
    return "\n".join(lines) + "\n" if lines else ""


def reattach_decorator(
    current_full_source: str, edited_display_source: str, hide_def: bool = False
) -> str:
    """The browser only ever shows/edits `display_source`'s decorator-free
    output (a live `edit_cell` sends back exactly that shape) -- before an
    edit is recorded as a `session.source_overrides` entry, it must be
    reunited with a decorator so it's still the full shape `Cell.source`,
    `save_edits`, and `_apply_overrides` all assume, and so a save doesn't
    silently delete the decorator line from the deck's `.py` file.
    `current_full_source` supplies the decorator to keep -- the caller's
    own `Deck.cells[name].source` (or a still-pending prior override for
    the same cell in the same Session, if the decorator itself was just
    regenerated by an add_element/rename_cell in this Session before this
    edit) -- since a plain code edit never changes the decorator itself,
    only what's already keeping this cell's `elements=[...]` and
    `instance=...` in sync with the Deck's own state.

    `hide_def=True` (`Cell.hide_def`) means `edited_display_source` is
    also `def`-line-free and un-indented (`display_source`'s inverse
    transform) -- `current_full_source` supplies the real `def` line too,
    same rationale as the decorator: the browser never showed or let the
    author edit it (a `hide_def` cell's parameter list, if it somehow has
    one, isn't editable from the code editor at all), so it must be
    reinserted, with the body re-indented one level to sit back under it,
    before this is recorded as the override.

    `edited_display_source` is also docstring-free (`display_source`
    strips it too, since it's the cell's notes content, rendered in its
    own markdown viewer -- not code) -- `set_notes_docstring` reinserts
    `current_full_source`'s existing docstring the same way, so a plain
    code edit can't silently delete a cell's notes just because the
    editor never showed the docstring line to begin with.

    `edited_display_source` is routinely invalid Python mid-keystroke (an
    unclosed paren, a dangling colon) -- `set_notes_docstring` needs to
    parse the reattached body to place the docstring, so on a
    `SyntaxError`/`ValueError` this falls back to reattaching just the
    decorator (and `def` line, if `hide_def`), no docstring reinsertion.
    The caller (`on_cell_edited`) still records this as the override so
    the editor keeps showing what was typed, and its own graph-rebuild
    step independently reports the same syntax error -- this fallback
    exists only so recording the override itself can't raise first."""
    if hide_def:
        def_line, _ = _split_cell_source(current_full_source)
        indented_body = textwrap.indent(edited_display_source, "    ")
        edited_display_source = def_line + "\n" + indented_body
    reattached = _decorator_prefix(current_full_source) + edited_display_source
    try:
        return set_notes_docstring(reattached, display_docstring(current_full_source))
    except (SyntaxError, ValueError):
        return reattached


def _docstring_node(source: str) -> ast.Expr | None:
    """The function's docstring statement node (a bare string-expression
    as the first line of the body), or `None` if it doesn't have one --
    used by both `display_docstring` (read) and `set_notes_docstring`
    (write) so the two agree on exactly what counts as "the docstring"."""
    tree = ast.parse(textwrap.dedent(source))
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    func = func_defs[0]
    if not func.body:
        return None
    first = func.body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first
    return None


def _triple_quote_literal(text: str) -> str:
    """Format `text` as a triple-quoted Python string literal (real line
    breaks for an embedded newline, not an escaped `\\n`), the same
    quote-style-picking precedent `repr()` itself uses for single/double
    quotes: prefer `\"\"\"`, fall back to `'''` if `text` contains a run
    of 3+ double quotes or ends in one (either would otherwise close the
    literal early or merge into an ambiguous 4+-quote run). Every
    literal backslash is escaped first (`\\` -> `\\\\`), before the
    quote character is examined at all -- otherwise a text already
    ending in an odd number of backslashes would itself swallow the
    backslash this function inserts to escape a trailing quote, instead
    of that backslash actually escaping the quote as intended.

    If `text` contains 3+-in-a-row (or a trailing single) of *both*
    quote characters -- pasted code containing another docstring, most
    likely -- `'''` is picked anyway and every remaining dangerous `'`
    run/trailing `'` is individually escaped, since some valid choice
    of delimiter always exists (escaping can't fail the way "avoid the
    delimiter entirely" can when both characters are present).

    Deliberately does *not* re-indent continuation lines to match the
    surrounding code -- `display_docstring`/`Cell.docstring` both read
    the literal's exact parsed value back out as the note's content, so
    injecting extra leading whitespace on line 2+ would silently splice
    that whitespace into the semantic text of the note itself, not just
    its on-disk formatting."""
    text = text.replace("\\", "\\\\")

    def is_dangerous(s: str, ch: str) -> bool:
        return ch * 3 in s or s.endswith(ch)

    if not is_dangerous(text, '"'):
        quote = '"""'
    elif not is_dangerous(text, "'"):
        quote = "'''"
    else:
        quote = "'''"
        text = "".join(f"\\{ch}" if ch == "'" else ch for ch in text)

    return f"{quote}{text}{quote}"


def set_notes_docstring(current_full_source: str, notes_text: str) -> str:
    """Regenerate a cell's full source with its docstring replaced by
    `notes_text` (a `notes` element's markdown content, edited in the
    browser and saved via the ordinary Save button/`save_edits` path --
    it's folded into `session.source_overrides` as a whole-cell source
    edit, the same slot a code edit already uses, rather than a separate
    save mechanism). Same precedent as `@app.slide`'s docstring-as-notes
    (`app.py`), just for a cell's own function instead of a slide's.

    Inserts a new docstring as the function's first statement if it
    doesn't have one yet; replaces it in place (preserving indentation)
    if it does; removes it entirely if `notes_text` is empty (an absent
    docstring and an empty one both read back as `""`, so writing one
    out for empty text would just be inert boilerplate). Writes a real
    triple-quoted block via `_triple_quote_literal` -- a multi-line note
    shows up in the `.py` file with actual line breaks, not a single
    repr()'d line with escaped `\\n`s, per the user's own explicit ask."""
    tree = ast.parse(textwrap.dedent(current_full_source))
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    func = func_defs[0]
    lines = textwrap.dedent(current_full_source).splitlines()
    existing = _docstring_node(current_full_source)

    if existing is not None:
        start, end = existing.lineno - 1, existing.end_lineno  # 0-indexed, exclusive end
        indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
        del lines[start:end]
        if notes_text:
            literal = _triple_quote_literal(notes_text)
            lines.insert(start, f"{indent}{literal}")
    elif notes_text:
        # No existing docstring -- insert one immediately after the `def`
        # line, i.e. the true first line of the body, *not* necessarily
        # before func.body[0]: comments aren't AST nodes, so a body that
        # opens with a comment block (common on an instructor's own
        # hand-written cell) would otherwise put func.body[0].lineno past
        # those comments, landing the "docstring" below them instead of
        # at the top where a real docstring belongs syntactically.
        # Indent matches the body's first statement (or, for a body
        # that's only ever had `pass`/nothing yet, the same indent
        # `blank_cell_source` already uses).
        body_start = func.lineno  # 0-indexed line right after the `def` line
        first_body_line = lines[func.body[0].lineno - 1]
        indent = first_body_line[: len(first_body_line) - len(first_body_line.lstrip())]
        literal = _triple_quote_literal(notes_text)
        lines.insert(body_start, f"{indent}{literal}")

    return "\n".join(lines) + "\n"


def display_docstring(source: str) -> str:
    """The cell's current notes text, read the same way `set_notes_docstring`
    writes it -- used by callers that need to recompute it from a live,
    possibly-just-edited `source` (e.g. `kernel.py`'s `on_cell_edited`,
    which must keep an in-session notes override in sync if the user is
    simultaneously editing the code and the docstring in the same save).
    `Cell.docstring` (`deck.py`) is the *load-time* equivalent of this,
    populated once via `fn.__doc__` when the deck file's `@app.cell`
    actually executes -- this is for the in-between: source text that
    hasn't been executed yet, only parsed."""
    node = _docstring_node(source)
    if node is None:
        return ""
    assert isinstance(node.value, ast.Constant)
    return node.value.value


def rebuild_cell_source(
    name: str, instance: str, elements: list[Element], source: str, hide_def: bool = False
) -> str:
    """Regenerate a cell's full source text with a new `name` and/or
    `elements` list, keeping its function body (everything after the
    `def` line) byte-identical -- used by `rename_cell` (new `name`, same
    elements) and `add_element`/`remove_element`/`reorder_elements`/
    `set_element_config` (same name, new elements) via `_replace_elements`.
    The `def` line's own parameter list is preserved as-is (renaming only
    changes the function's *name*, never its signature).

    `hide_def` must be threaded through from the cell's *current*
    `hide_def` (`_replace_elements` detects it from the decorator's own
    AST, same as it already does for `instance="editable"`) and included
    in the regenerated decorator -- otherwise any of these operations
    would silently drop `hide_def=True` from the file the moment they
    touch this cell, even though nothing about hiding the `def` line was
    ever meant to change."""
    def_line, body_lines = _split_cell_source(source)
    # def_line looks like "def old_name(params):" -- replace only the name.
    paren = def_line.index("(")
    new_def_line = f"def {name}{def_line[paren:]}"

    if elements:
        element_lines = "\n".join(f"        {_element_call_source(e)}," for e in elements)
        hide_def_line = "\n    hide_def=True," if hide_def else ""
        decorator = (
            f"@app.cell(\n    instance={instance!r},\n    elements=[\n{element_lines}\n    ],{hide_def_line}\n)"
        )
    else:
        kwargs = [kw for kw in (f"instance={instance!r}" if instance != "static" else "", "hide_def=True" if hide_def else "") if kw]
        decorator = f"@app.cell({', '.join(kwargs)})" if kwargs else "@app.cell"

    return decorator + "\n" + new_def_line + "\n" + "\n".join(body_lines) + "\n"


def append_cell(deck_path: str, name: str) -> str:
    """Append a new blank cell (see `blank_cell_source`) to the end of
    `deck_path`'s cell definitions, immediately, on disk -- TODO.md #21
    chose "write to disk right away" over "staged until Save is
    clicked" specifically so a newly-added cell can never be silently
    lost if the author forgets to click Save afterward, unlike an
    edited *existing* cell's `source_override` (which the Save button
    already governs). Returns the appended source text (identical to
    `blank_cell_source(name)`) so the caller can hand it straight to
    `Cell`/`ElementInstance` construction without re-deriving it.

    Raises `SaveConflictError` if `name` already names a cell in the
    file (can happen if the file changed on disk since the caller last
    loaded it, e.g. two instructors editing the same deck) -- the
    caller is expected to have picked `name` via `new_cell_name` against
    its own last-known cell set, but that set can be stale by the time
    this actually writes.
    """
    path = Path(deck_path)
    original = path.read_text()
    spans = _cell_line_spans(original)
    if name in spans:
        raise SaveConflictError(f"cannot add cell {name!r}: a cell with that name already exists")

    new_source = blank_cell_source(name)
    # PEP 8 / this codebase's own convention: two blank lines between
    # top-level defs (every existing deck in examples/ follows this) --
    # match it so the appended cell doesn't look visually out of place
    # next to cells the author wrote by hand.
    stripped = original.rstrip("\n")
    updated = stripped + "\n\n\n" + new_source

    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise InvalidSourceError(
            f"appending cell {name!r} would leave {deck_path!r} with invalid Python syntax: {exc}"
        ) from exc

    path.write_text(updated)
    return new_source


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


def _slide_cells_spans(source: str) -> list[tuple[int, int, int, int, list[str]]]:
    """Find every `@app.slide(..., cells=[...])` call's `cells` argument in
    `source`: (start_line, end_line, start_col, end_col, cell_names),
    1-indexed lines / 0-indexed columns matching `ast`'s own convention.
    Used by `rename_cell` to cascade a rename into slide references
    without touching anything else about the slide's decorator call."""
    tree = ast.parse(source)
    spans = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "slide"):
            continue
        for kw in node.keywords:
            if kw.arg == "cells":
                names = ast.literal_eval(kw.value)
                spans.append((kw.value.lineno, kw.value.end_lineno, kw.value.col_offset, kw.value.end_col_offset, names))
    return spans


def rename_cell(deck_path: str, old_name: str, new_name: str) -> None:
    """Rename a cell (its Deck-key identity, not just cosmetic text) from
    `old_name` to `new_name`, on disk, immediately -- TODO.md #22.

    Rewrites two things: the cell's own decorator+`def` line (via
    `rebuild_cell_source`, body untouched) and every `@app.slide(...,
    cells=[...])` call anywhere in the file that names `old_name`, so
    slide grouping keeps pointing at the same cell under its new name.

    Does *not* attempt to rewrite any *other* cell's body that happens to
    reference `old_name` as a Python identifier (e.g. `result =
    old_name() * 2`, or reading its return value) -- `Kernel.rename_cell`
    checks for that and refuses the rename first, since blindly rewriting
    arbitrary identifier occurrences inside someone else's code is not
    safe (could be a substring match, a shadowed local, anything);
    telling the author to remove the reference first is the honest
    option, not a silent, possibly-wrong rewrite.

    Raises `SaveConflictError` if `old_name` no longer exists or
    `new_name` already names a different cell (can happen if the file
    changed on disk since the caller's last-known cell set), or
    `InvalidSourceError` if the result doesn't parse.
    """
    path = Path(deck_path)
    original = path.read_text()
    spans = _cell_line_spans(original)
    if old_name not in spans:
        raise SaveConflictError(f"cannot rename cell {old_name!r}: it no longer exists")
    if new_name in spans and new_name != old_name:
        raise SaveConflictError(f"cannot rename cell {old_name!r} to {new_name!r}: that name already exists")

    tree = ast.parse(original)
    func = next(
        n
        for n in ast.iter_child_nodes(tree)
        if isinstance(n, ast.FunctionDef) and n.name == old_name
    )
    is_editable = any(
        isinstance(dec, ast.Call)
        and any(kw.arg == "instance" and ast.literal_eval(kw.value) == "editable" for kw in dec.keywords)
        for dec in func.decorator_list
    )
    instance = "editable" if is_editable else "static"
    # Same detection, for hide_def=True -- without this, renaming a cell
    # would silently drop hide_def from the file, even though a rename
    # has no reason to change it.
    hide_def = any(
        isinstance(dec, ast.Call)
        and any(kw.arg == "hide_def" and ast.literal_eval(kw.value) is True for kw in dec.keywords)
        for dec in func.decorator_list
    )

    start, end = spans[old_name]
    lines = original.splitlines(keepends=True)
    old_cell_source = "".join(lines[start - 1 : end])
    # Reuse the cell's own currently-declared elements verbatim (parsed
    # fresh from its own source, not from any caller-supplied Deck model)
    # -- a rename must never silently drop/reorder elements.
    elements = _existing_elements(func)

    new_cell_source = rebuild_cell_source(new_name, instance, elements, old_cell_source, hide_def=hide_def)
    updated_lines = list(lines)
    updated_lines[start - 1 : end] = [new_cell_source]
    updated = "".join(updated_lines)

    # Cascade into slide references, working on the just-updated text so
    # line numbers from the (possibly now-different-length) cell edit
    # above don't apply here -- slide spans are recomputed fresh.
    slide_spans = _slide_cells_spans(updated)
    if slide_spans:
        slide_lines = updated.splitlines(keepends=True)
        for s_start, s_end, s_col, e_col, names in sorted(slide_spans, key=lambda s: s[0], reverse=True):
            if old_name not in names:
                continue
            new_names = [new_name if n == old_name else n for n in names]
            literal = "[" + ", ".join(repr(n) for n in new_names) + "]"
            if s_start == s_end:
                line = slide_lines[s_start - 1]
                slide_lines[s_start - 1] = line[:s_col] + literal + line[e_col:]
            else:
                first_line = slide_lines[s_start - 1][:s_col]
                last_line = slide_lines[s_end - 1][e_col:]
                slide_lines[s_start - 1 : s_end] = [first_line + literal + last_line]
        updated = "".join(slide_lines)

    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise InvalidSourceError(
            f"renaming cell {old_name!r} to {new_name!r} would leave {deck_path!r} with invalid "
            f"Python syntax, not saved: {exc}"
        ) from exc

    path.write_text(updated)


def remove_cell(deck_path: str, name: str) -> None:
    """Delete a cell (its whole decorator+`def` block) from `deck_path`,
    on disk, immediately -- the inverse of `append_cell`.

    Also strips `name` out of every `@app.slide(..., cells=[...])` call
    that references it, so a deleted cell never leaves a slide pointing
    at a name that no longer exists (`Deck.add_slide`'s own `unknown =
    [...]` check would otherwise reject the very next `load_deck`).
    This is a plain cascade, not a refusal, unlike `Kernel.remove_cell`'s
    own check for another *cell's code* referencing this one by name
    (`reads`) -- a slide's `cells=[...]` is presentation grouping, not a
    code dependency, so there's no "unsafe blind rewrite" risk the way
    there is for rewriting an arbitrary identifier occurrence inside
    someone else's function body (see `rename_cell`'s own docstring for
    why *that* case is refused instead of cascaded).

    Raises `SaveConflictError` if `name` doesn't exist, or
    `InvalidSourceError` if the result doesn't parse.
    """
    path = Path(deck_path)
    original = path.read_text()
    spans = _cell_line_spans(original)
    if name not in spans:
        raise SaveConflictError(f"cannot remove cell {name!r}: it no longer exists")

    start, end = spans[name]
    lines = original.splitlines(keepends=True)
    # Delete the cell's own block, then collapse whatever blank-line gap
    # is left at the cut point down to exactly two blank lines (one
    # blank line, i.e. "\n\n" between the two now-adjacent lines) --
    # the same two-blank-lines-between-top-level-defs convention
    # `append_cell` already establishes when it appends a new cell.
    del lines[start - 1 : end]
    # Trim any blank lines immediately surrounding the cut, then
    # reinsert exactly two.
    cut = start - 1
    end_of_prev = cut
    while end_of_prev > 0 and lines[end_of_prev - 1].strip() == "":
        end_of_prev -= 1
    end_of_next = cut
    while end_of_next < len(lines) and lines[end_of_next].strip() == "":
        end_of_next += 1
    if end_of_prev > 0 and end_of_next < len(lines):
        lines[end_of_prev:end_of_next] = ["\n", "\n"]
    else:
        # Deleted the first or last block in the file -- no "gap" to
        # restore between two neighbors, just drop the extra blank
        # lines left dangling at whichever edge this was.
        lines[end_of_prev:end_of_next] = []
    updated = "".join(lines)

    slide_spans = _slide_cells_spans(updated)
    if slide_spans:
        slide_lines = updated.splitlines(keepends=True)
        for s_start, s_end, s_col, e_col, names in sorted(slide_spans, key=lambda s: s[0], reverse=True):
            if name not in names:
                continue
            new_names = [n for n in names if n != name]
            literal = "[" + ", ".join(repr(n) for n in new_names) + "]"
            if s_start == s_end:
                line = slide_lines[s_start - 1]
                slide_lines[s_start - 1] = line[:s_col] + literal + line[e_col:]
            else:
                first_line = slide_lines[s_start - 1][:s_col]
                last_line = slide_lines[s_end - 1][e_col:]
                slide_lines[s_start - 1 : s_end] = [first_line + literal + last_line]
        updated = "".join(slide_lines)

    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise InvalidSourceError(
            f"removing cell {name!r} would leave {deck_path!r} with invalid Python syntax, not saved: {exc}"
        ) from exc

    path.write_text(updated)


def reorder_cells(deck_path: str, cell_order: list[str]) -> None:
    """Reorder every top-level cell in `deck_path` to match `cell_order`
    exactly, on disk, immediately -- each cell's own block (decorator
    through end of body) is kept byte-identical, only which order the
    blocks appear in the file changes. `cell_order` must be a
    permutation of every cell currently in the file, matching
    `reorder_elements`'s own "the frontend only ever hands back a full
    permutation, built from swapping two adjacent entries" precedent.

    Any top-level content that isn't part of a cell's own span (the
    `app = App()` line, top-level imports, standalone comments, blank
    lines) keeps its exact original position *outside* the region the
    cell blocks occupy -- text before the first cell block and after
    the last one is left completely untouched. Content that used to sit
    *between* two specific cell blocks (e.g. a comment written directly
    above one particular cell) is not preserved relative to that cell
    once cells are reordered -- there's no principled way to know which
    neighbor a mid-file comment "belongs to" after their relative order
    changes, so it is dropped rather than guessed at, and every
    adjacent pair in the reassembled sequence gets the same uniform
    two-blank-line separator `append_cell`/`remove_cell` already use.
    This is a deliberate, documented limitation, not an oversight: a
    comment sitting directly above a cell does not travel with it.

    Raises `SaveConflictError` if `cell_order` isn't exactly a
    permutation of the file's current cells, or `InvalidSourceError` if
    the result doesn't parse.
    """
    path = Path(deck_path)
    original = path.read_text()
    spans = _cell_line_spans(original)
    if sorted(cell_order) != sorted(spans):
        raise SaveConflictError(
            f"cannot reorder cells: {cell_order!r} is not a permutation of the deck's "
            f"current cells {sorted(spans)!r}"
        )

    lines = original.splitlines(keepends=True)
    block_texts = {name: "".join(lines[start - 1 : end]) for name, (start, end) in spans.items()}

    first_block_start = min(start for start, _ in spans.values())
    last_block_end = max(end for _, end in spans.values())

    before = "".join(lines[: first_block_start - 1])
    after = "".join(lines[last_block_end:])

    reassembled = "\n\n\n".join(block_texts[name].rstrip("\n") for name in cell_order) + "\n"
    updated = before + reassembled + after

    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise InvalidSourceError(
            f"reordering cells would leave {deck_path!r} with invalid Python syntax, not saved: {exc}"
        ) from exc

    path.write_text(updated)


def _replace_elements(
    deck_path: str,
    cell_name: str,
    build_new_elements: Callable[[list[Element]], list[Element]],
    error_context: str,
) -> Cell:
    """Shared plumbing for every `elements=[...]`-rewriting operation
    (`add_element`/`remove_element`/`reorder_elements`/
    `set_element_config`): locate `cell_name`'s current source, parse its
    existing elements, hand them to `build_new_elements` to produce the
    new ordered list, regenerate the cell's decorator via
    `rebuild_cell_source` (body untouched), validate, and write --
    identical shape across all four operations, so this is the one place
    that shape needs to be right. `error_context` is a short phrase (e.g.
    "add an element to") used only in the not-found error message.
    """
    path = Path(deck_path)
    original = path.read_text()
    spans = _cell_line_spans(original)
    if cell_name not in spans:
        raise SaveConflictError(f"cannot {error_context} {cell_name!r}: it no longer exists")

    start, end = spans[cell_name]
    lines = original.splitlines(keepends=True)
    cell_source = "".join(lines[start - 1 : end])

    tree = ast.parse(cell_source)
    func = next(n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.FunctionDef))
    existing = _existing_elements(func)
    is_editable = any(
        isinstance(dec, ast.Call)
        and any(kw.arg == "instance" and ast.literal_eval(kw.value) == "editable" for kw in dec.keywords)
        for dec in func.decorator_list
    )
    # Same detection as is_editable, for hide_def=True -- without this,
    # rebuild_cell_source would silently drop hide_def from the file the
    # moment any of add_element/remove_element/reorder_elements/
    # set_element_config/rename_cell touches this cell, even though none
    # of them have any reason to change it.
    hide_def = any(
        isinstance(dec, ast.Call)
        and any(kw.arg == "hide_def" and ast.literal_eval(kw.value) is True for kw in dec.keywords)
        for dec in func.decorator_list
    )

    new_elements = build_new_elements(existing)

    new_cell_source = rebuild_cell_source(
        cell_name, "editable" if is_editable else "static", new_elements, cell_source, hide_def=hide_def
    )
    updated_lines = list(lines)
    updated_lines[start - 1 : end] = [new_cell_source]
    updated = "".join(updated_lines)
    updated = _ensure_ui_imported(updated)

    try:
        ast.parse(updated)
    except SyntaxError as exc:
        raise InvalidSourceError(
            f"editing cell {cell_name!r}'s elements would leave {deck_path!r} with invalid "
            f"Python syntax, not saved: {exc}"
        ) from exc

    path.write_text(updated)
    return Cell(
        name=cell_name,
        source=new_cell_source,
        instance="editable" if is_editable else "static",
        elements=new_elements,
        hide_def=hide_def,
    )


def add_element(deck_path: str, cell_name: str, element: Element) -> None:
    """Add `element` to `cell_name`'s `elements=[...]` list, on disk,
    immediately (TODO.md #22 -- same "write immediately, don't stage
    behind Save" precedent as `append_cell`/`rename_cell`: a newly added
    element must never be silently lost). The cell's body is untouched;
    only its decorator is regenerated (via `rebuild_cell_source`) with
    the new element appended to whatever elements it already had.

    Raises `SaveConflictError` if `cell_name` doesn't exist or already
    has an element named `element.name`, or `InvalidSourceError` if the
    result doesn't parse.
    """

    def build(existing: list[Element]) -> list[Element]:
        if any(e.name == element.name for e in existing):
            raise SaveConflictError(f"cell {cell_name!r} already has an element named {element.name!r}")
        return [*existing, element]

    _replace_elements(deck_path, cell_name, build, "add an element to")


def _ensure_ui_imported(source: str) -> str:
    """A cell's `elements=[...]` list always calls `ui.<kind>(...)`
    (`_element_call_source`) -- if this is the deck's *first* element
    ever (e.g. `examples/hello.py` never imports `ui` since it never
    needed it), `add_element` would otherwise silently write a file that
    `NameError`s the moment it's loaded. Adds `ui` to the existing
    `from codeslides import ...` line if it's missing one; a deck with no
    such import at all (nonstandard, but not disallowed) is left alone --
    that's a pre-existing authoring choice this function shouldn't second-
    guess by inventing an import statement out of nowhere."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "codeslides":
            names = {alias.name for alias in node.names}
            if "ui" in names:
                return source
            lines = source.splitlines(keepends=True)
            imported = sorted(names | {"ui"})
            new_line = f"from codeslides import {', '.join(imported)}\n"
            lines[node.lineno - 1 : node.end_lineno] = [new_line]
            return "".join(lines)
    return source


def remove_element(deck_path: str, cell_name: str, element_name: str) -> None:
    """Remove the element named `element_name` from `cell_name`'s
    `elements=[...]` list, on disk, immediately (TODO.md #22, same
    write-immediately precedent as `add_element`). The cell's body is
    untouched.

    Raises `SaveConflictError` if `cell_name` or `element_name` doesn't
    exist, or `InvalidSourceError` if the result doesn't parse.
    """

    def build(existing: list[Element]) -> list[Element]:
        if not any(e.name == element_name for e in existing):
            raise SaveConflictError(f"cell {cell_name!r} has no element named {element_name!r}")
        return [e for e in existing if e.name != element_name]

    _replace_elements(deck_path, cell_name, build, "remove an element from")


def reorder_elements(deck_path: str, cell_name: str, element_order: list[str]) -> None:
    """Reorder `cell_name`'s `elements=[...]` list to match
    `element_order` exactly, on disk, immediately (TODO.md #23's
    reorder-elements picker). `element_order` must be a permutation of
    the cell's current element names -- every element must appear
    exactly once, matching the frontend's up/down-arrow reorder, which
    only ever swaps two adjacent entries of the list it was already
    given.

    Raises `SaveConflictError` if `cell_name` doesn't exist or
    `element_order` isn't exactly a permutation of its current elements
    (a stale reorder request racing a since-changed element set), or
    `InvalidSourceError` if the result doesn't parse.
    """

    def build(existing: list[Element]) -> list[Element]:
        existing_by_name = {e.name: e for e in existing}
        if sorted(element_order) != sorted(existing_by_name):
            raise SaveConflictError(
                f"cannot reorder cell {cell_name!r}'s elements: {element_order!r} is not a "
                f"permutation of its current elements {sorted(existing_by_name)!r}"
            )
        return [existing_by_name[name] for name in element_order]

    _replace_elements(deck_path, cell_name, build, "reorder elements for")


def set_element_config(deck_path: str, cell_name: str, element_name: str, config: dict[str, object]) -> None:
    """Replace the element named `element_name`'s `config` dict wholesale
    (TODO.md #23's iframe URL textbox), on disk, immediately -- same
    write-immediately precedent as `add_element`. The element's position
    in the list, and every other element, is untouched.

    Raises `SaveConflictError` if `cell_name` or `element_name` doesn't
    exist, or `InvalidSourceError` if the result doesn't parse.
    """

    def build(existing: list[Element]) -> list[Element]:
        if not any(e.name == element_name for e in existing):
            raise SaveConflictError(f"cell {cell_name!r} has no element named {element_name!r}")
        return [
            Element(name=e.name, kind=e.kind, config=config) if e.name == element_name else e
            for e in existing
        ]

    _replace_elements(deck_path, cell_name, build, "set element config for")


def _existing_elements(func: ast.FunctionDef) -> list[Element]:
    """Parse the `elements=[...]` keyword argument (if any) off a cell
    function's own decorator list into `Element` objects -- reads from the
    cell's own source, not any caller-supplied Deck model, so it always
    reflects exactly what's on disk right now."""
    for dec in func.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        for kw in dec.keywords:
            if kw.arg != "elements":
                continue
            return [
                Element(
                    name=call.args[0].value,
                    kind=call.func.attr,
                    config={k.arg: ast.literal_eval(k.value) for k in call.keywords},
                )
                for call in kw.value.elts
            ]
    return []


def set_tests_default(current_full_source: str, element_name: str, default_text: str) -> str:
    """Regenerate a cell's full source with a `tests` element's own
    `default=` updated to `default_text` -- a test box's edited source,
    saved via the ordinary Save button/`save_edits` path, the same
    `session.source_overrides` slot a code or notes edit already uses
    (`kernel.py`'s `on_notes_edited` is the direct precedent for this
    shape: full source in, full source out, no separate save mechanism
    or immediate on-disk write like `set_element_config`'s own
    `_replace_elements`-based version of this same idea).

    Reuses `_existing_elements`/`rebuild_cell_source` -- the exact same
    parse-elements-then-regenerate-the-decorator machinery
    `add_element`/`remove_element`/`set_element_config` already share,
    just operating on an in-memory source string instead of a file on
    disk, and only ever changing one element's `default`, never its
    other config keys, name, or position.

    Raises `SaveConflictError` if `element_name` doesn't name an
    existing `tests` element on this cell -- mirrors the exact-shape
    precedent every other named-element lookup in this module already
    follows (`set_element_config`, `remove_element`)."""
    tree = ast.parse(textwrap.dedent(current_full_source))
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    func = func_defs[0]
    existing = _existing_elements(func)
    if not any(e.name == element_name and e.kind == "tests" for e in existing):
        raise SaveConflictError(f"no tests element named {element_name!r} on this cell")

    new_elements = [
        Element(name=e.name, kind=e.kind, config={**e.config, "default": default_text})
        if e.name == element_name
        else e
        for e in existing
    ]

    is_editable = any(
        isinstance(dec, ast.Call)
        and any(kw.arg == "instance" and ast.literal_eval(kw.value) == "editable" for kw in dec.keywords)
        for dec in func.decorator_list
    )
    hide_def = any(
        isinstance(dec, ast.Call)
        and any(kw.arg == "hide_def" and ast.literal_eval(kw.value) is True for kw in dec.keywords)
        for dec in func.decorator_list
    )

    return rebuild_cell_source(
        func.name,
        "editable" if is_editable else "static",
        new_elements,
        current_full_source,
        hide_def=hide_def,
    )
