"""Reactive execution kernel. See ARCHITECTURE.md sections 3, 3a, and 4.

Executes cells inside a Session's namespace (never sharing it with any
other Session -- the structural fix for the marimo cloned-editor bug, see
ARCHITECTURE.md section 1). A cell is compiled and called as an ordinary
Python function: cross-cell reads resolve through the function's own
`__globals__` (seeded from the Session's namespace, exactly like ordinary
module-level name lookup), input-element values are passed as keyword
arguments (they're genuine declared parameters), and its `return`
statement's names -- read directly off the AST, in the order written --
are unpacked back into the Session's namespace. This avoids relying on
`Cell.writes` (a set, for graph purposes only) for positional binding.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import io
import textwrap
import traceback
import types
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codeslides import cs, turtle
from codeslides.deck import Cell, Deck, Element, Slide
from codeslides.graph import (
    DependencyGraph,
    build_graph,
    extract_return_names,
)
from codeslides.output import resolve_output, wire_safe_value
from codeslides.serialization import reattach_decorator, set_notes_docstring, set_tests_default
from codeslides.session import CellInstance, ElementInstance, Session, _deck_asset_url

# Extension for each image MIME type a browser's <input type="file"
# accept="image/*"> can plausibly hand back via FileReader.readAsDataURL.
_IMAGE_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/x-icon": ".ico",
}


def _save_data_uri_as_asset(deck_path: str, data_uri: str) -> str:
    """Decode an uploaded image's `data:<mime>;base64,<data>` URI
    (EditCellPanel.tsx's file picker, via `FileReader.readAsDataURL`)
    and write it as a real file in an `assets/` folder next to the deck
    file, returning the new file's path relative to the deck's own
    directory (e.g. `"assets/1f2e3d4c5b6a7988.png"`) -- this is what
    actually gets stored as `ui.image(name, src=...)` in the `.py` file,
    so the deck stays a small, readable text file (and portable if its
    whole directory is copied elsewhere) instead of embedding
    potentially-large base64 blobs inline.

    Named by a truncated sha256 of the decoded bytes, not the browser's
    original filename (which the data URI never carries anyway, and
    which could collide across two unrelated images) -- re-uploading
    the exact same image byte-for-byte reuses the same file rather than
    accumulating duplicates, while two different images have no
    realistic chance of colliding. If a file with that name already
    exists, it's assumed identical (same hash) and left untouched
    rather than rewritten.

    Raises `ValueError` if `data_uri` isn't a well-formed
    `data:<mime>;base64,...` URI, or if `<mime>` isn't one of the image
    types `_IMAGE_MIME_EXTENSIONS` recognizes."""
    header, _, encoded = data_uri.partition(",")
    if not header.startswith("data:") or ";base64" not in header:
        raise ValueError(f"not a base64 data URI: {data_uri[:40]!r}...")
    mime = header[len("data:") : header.index(";")]
    ext = _IMAGE_MIME_EXTENSIONS.get(mime)
    if ext is None:
        raise ValueError(f"unsupported image MIME type for upload: {mime!r}")

    raw = base64.b64decode(encoded)
    digest = hashlib.sha256(raw).hexdigest()[:16]
    filename = f"{digest}{ext}"

    assets_dir = Path(deck_path).resolve().parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_path = assets_dir / filename
    if not asset_path.exists():
        asset_path.write_bytes(raw)

    return f"assets/{filename}"


def strip_noop_turtle_imports(stmts: list[ast.stmt]) -> list[ast.stmt]:
    """Drop every bare `import turtle` statement from a top-level
    statement list (a cell's own body, here, or a whole deck module's
    top level, `loader.py`'s `load_deck`) -- `turtle` is already provided
    as `codeslides.turtle` in every cell's execution globals (this
    module's own `call_globals`/`test_globals`), the same framework name
    `cs` already is with no import needed. A real `import turtle`
    executing for real would rebind the name to the actual stdlib module
    (which opens a Tk window and does nothing this app's own turtle
    canvas can see) -- or, at deck-load time, simply crash outright on
    any machine without tkinter available (real bug, reproduced by
    hand: `ModuleNotFoundError: No module named '_tkinter'`).

    Deliberately narrow: only a bare, unaliased `import turtle` (not
    `import turtle as t`, not `from turtle import forward`) is treated
    as a no-op -- the author is expected to keep writing plain
    `turtle.forward(...)` calls exactly like the framework name already
    requires, so an ordinary `import turtle` is the only spelling that
    needs to silently do nothing. The statement is dropped rather than
    rewritten so the *displayed*/on-disk source is completely
    unaffected (ARCHITECTURE.md section 2's file format is still
    `Cell.source`/`inspect.getsource` verbatim) -- this only changes
    what actually executes, mirroring the very reason the import is
    there in the first place: so a student later runs the same `.py`
    file standalone, where `import turtle` needs to do its real job.
    """
    return [
        stmt
        for stmt in stmts
        if not (
            isinstance(stmt, ast.Import)
            and len(stmt.names) == 1
            and stmt.names[0].name == "turtle"
            and stmt.names[0].asname is None
        )
    ]


@dataclass
class ExecutionResult:
    """What running one cell produced, ready to populate a CellInstance."""

    status: str  # "idle" | "error"
    stdout: str = ""
    stderr: str = ""
    value: object | None = None
    error: str | None = None
    element_writes: list[cs.ElementWrite] = field(default_factory=list)


def _compile_cell_function(source: str, namespace: dict[str, object]):
    """Compile a cell's function so its real `__globals__` *is*
    `namespace` itself -- not a copy -- and return the callable and the
    ordered list of names its `return` statement exposes. `namespace`
    is never mutated by this call; the caller decides when (and
    whether) to actually bind the returned function into it, exactly
    like the previous copy-based version let it.

    Sharing the real `namespace` object (rather than a `{**namespace}`
    copy, which was this function's previous behavior) is required, not
    just an optimization: a `global x` statement always resolves
    through the specific dict object that ends up as the function's own
    `__globals__`, fixed once at this compile step -- a copy-then-
    sync-back approach cannot make `global`-declared writes visible to
    *other* cells that call this one, because by the time any syncing
    happens, the callee already ran against the wrong dict. This is
    what makes `examples/marchingSquares.py`'s cell_2 (`global x1; x1
    += 5`, meant to be readable/writable by any other cell or test box)
    actually work like real Python: `x1` genuinely is the same name in
    the same dict everywhere, exactly like a real module's globals.

    Getting there needs two steps, not just `exec(code, namespace)`,
    because default argument values (`def f(rows=2, cols=5)`) are
    computed by the module-level bytecode `exec` runs, as a *side
    effect* of defining the function -- there's no way to ask Python to
    "compute the defaults, but don't also bind the function itself into
    this dict," and binding it directly into `namespace` under the
    AST's literal `def` name (not necessarily this cell's actual
    identity, for a renamed `instance="editable"` cell) would violate
    the "never partially pollute the namespace before the caller
    decides to" contract every caller here still relies on. So: (1)
    `exec` into a throwaway shallow copy of `namespace`, purely so
    default values evaluate against a realistic set of names, and (2)
    rebuild a fresh function object from the resulting code object,
    this time with the real `namespace` as `__globals__` -- `namespace`
    itself is never touched by either step.

    Dedented so cells whose source happens to be nested (e.g. under a
    test function) still parse.
    """
    dedented = textwrap.dedent(source)
    tree = ast.parse(dedented)
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        raise ValueError(f"expected exactly one function definition, found {len(func_defs)}")
    func = func_defs[0]
    func.decorator_list = []  # strip @app.cell(...) -- only the plain function is executed
    func.body = strip_noop_turtle_imports(func.body)

    return_names = extract_return_names(func)

    module = ast.Module(body=[func], type_ignores=[])
    ast.fix_missing_locations(module)
    code = compile(module, filename="<cell>", mode="exec")
    scratch = dict(namespace)
    exec(code, scratch)  # noqa: S102 - trusted lesson code; only evaluates defaults, `namespace` untouched
    defined = scratch[func.name]
    fn = types.FunctionType(
        defined.__code__, namespace, defined.__name__, defined.__defaults__, defined.__closure__
    )
    fn.__kwdefaults__ = defined.__kwdefaults__
    return fn, return_names


@contextmanager
def _maybe_turtle_context(turtle_element: str | None):
    """Only actually establish turtle.execution_context() when the cell
    has exactly one turtle_canvas element. Without this, a cell with zero
    or multiple canvases (an ambiguous/invalid target -- see
    _find_turtle_canvas) would still get a fresh, valid turtle context to
    draw into, silently swallowing what should be a clear error from
    `turtle._state()` about calling turtle functions with no valid target.
    """
    if turtle_element is None:
        yield None
    else:
        with turtle.execution_context() as commands:
            yield commands


def _find_turtle_canvas(elements: list[Element]) -> str | None:
    """Return the name of the cell's one `turtle_canvas` element, if it
    has exactly one. `codeslides.turtle` calls have no way to name a
    target themselves (unlike `cs.image`/`cs.iframe`) without breaking
    stdlib `turtle` call syntax, so a cell using turtle must have exactly
    one such element; zero means turtle calls will raise (from
    `turtle._state()`), and more than one has no well-defined target so is
    treated the same as having none -- turtle calls will still raise.
    """
    canvases = [e.name for e in elements if e.kind == "turtle_canvas"]
    return canvases[0] if len(canvases) == 1 else None


def _input_value_as_str(kind: str, raw: Any) -> str:
    """Render one input element's current raw value as the `str`
    `input()` must always return, regardless of the element kind that
    actually produced it. A `text_input`'s value is already a `str`
    (`raw or ""` just guards against `None` on an element that's never
    been touched). A `slider`'s value is a JS `Number` -> Python `float`
    (`SliderWidget.tsx`'s own `onChange(Number(...))`) -- `str()`ing a
    float directly would turn a whole-number slider position like `15`
    into `"15.0"`, and `int("15.0")` raises `ValueError` (unlike
    `int(15.0)`, which is fine) -- exactly the kind of thing a student
    writing `age = int(input(...))` around a slider-backed prompt would
    hit and have no way to explain. Rendering a whole-number float
    without the trailing `.0` sidesteps that: `int(input(...))` keeps
    working the same way it would for a typed whole number, while a
    genuinely fractional slider value (`15.5`) still comes through with
    its decimal part intact."""
    if kind == "slider":
        value = float(raw or 0)
        return str(int(value)) if value.is_integer() else str(value)
    return str(raw or "")


def _make_input_shim(cell_name: str, elements: list[Element], element_instances: dict[str, ElementInstance]):
    """Build a per-call replacement for the builtin `input()`, so a cell
    (or `tests` box) can write plain `input("prompt")` -- exactly the
    syntax the deck's own notes/fenced-code samples teach -- and have it
    read from this cell's own `ui.text_input`/`ui.slider` elements
    instead of stdin (which doesn't exist here; a real `input()` call
    would just hang/error -- see `Kernel`'s own module docstring, or the
    incident that led to this shim existing in the first place). Each
    successive call returns the next `text_input`/`slider` element's
    current value, in the order they're declared in `elements=[...]` --
    the two kinds share one combined sequence (a cell with
    `[slider("a"), text_input("b")]` reads `a` first, `b` second), not
    "drain all text_inputs, then all sliders," so the reading order
    always matches the order the elements themselves appear on the page.
    `ui.button` is deliberately still excluded -- a click *count* isn't
    a value a student would ever type at an `input()` prompt the way a
    slider's numeric position or a text box's typed text both are.

    Bound into `session.namespace["input"]` for the duration of one call
    (see `execute_cell`'s own `finally` restoring it afterward, same
    save/restore pattern already used there for `__name__`) -- this
    shadows the real builtin only for cells that actually reference
    `input` by name (ordinary Python global lookup order: local ->
    enclosing -> the cell's own `__globals__`, which *is*
    `session.namespace` -- see `_compile_cell_function`'s own docstring
    -- -> builtins), so it's never a global monkeypatch of
    `builtins.input` itself.

    Real `input()` echoes the prompt to stdout with no trailing newline,
    then a real terminal echoes back whatever the user types; there's no
    terminal here, so this writes the prompt AND the value together (a
    plausible transcript of what that exchange would have looked like)
    rather than just the value alone, so a cell that calls `input()`
    multiple times still produces a readable, prompt-labeled stdout
    transcript instead of a bare unlabeled sequence of values.
    """
    readable_kinds = ("text_input", "slider")
    readable_elements = [e for e in elements if e.kind in readable_kinds]
    calls = {"count": 0}

    def shim(prompt: str = "") -> str:
        index = calls["count"]
        calls["count"] += 1
        if index >= len(readable_elements):
            raise EOFError(
                f"input(): cell {cell_name!r} only has {len(readable_elements)} ui.text_input/ui.slider "
                f"element(s), but input() was called a {index + 1}{'st' if index == 0 else 'th'} time -- "
                "add another ui.text_input or ui.slider to this cell's elements=[...] for this call to read from."
            )
        element = readable_elements[index]
        raw = element_instances.get(element.name, ElementInstance()).value
        value = _input_value_as_str(element.kind, raw)
        print(f"{prompt}{value}")
        return value

    return shim


def execute_cell(
    cell_name: str,
    source: str,
    session: Session,
    elements: list[Element] | None = None,
    deck_imports: dict[str, object] | None = None,
    is_main: bool = False,
) -> ExecutionResult:
    """Call the cell named `cell_name`'s function (compiled fresh from
    `source`, which the caller has already resolved to this Session's
    effective source -- the Deck's, or a per-Session override for
    `instance="editable"` cells) directly against `session.namespace`
    itself: cross-cell reads are made available as the function's own
    globals (ordinary Python name resolution, matching how a plain
    module-level function reads other module-level names), bound
    input-element values are passed as keyword arguments (they're
    genuine parameters), and the function's `return`-named values are
    written back into the namespace.

    The function's `__globals__` *is* `session.namespace` (via
    `_compile_cell_function` -- see its docstring for why a copy cannot
    work), not a copy of it, so a `global x` write is immediately a
    real, permanent mutation of `session.namespace`, visible to any
    other cell (or a `tests` box, `run_tests`) that reads or calls into
    it afterward -- exactly like real Python. This does mean a cell that
    raises partway through a `global`-declared mutation leaves whatever
    it already wrote in place, same as a real Python script would if it
    crashed mid-function; only the cell's own name and `return`-named
    bindings still wait for a fully successful call before being bound
    (below). Never touches any namespace but `session`'s, nor any
    Deck-level state -- this is what makes cloned Sessions
    (ARCHITECTURE.md section 1) fully independent at execution time,
    including per-Session source overrides (section 3), not just in the
    data model.

    `elements` is the cell's static element list (from the Deck, or an
    editable-instance override) -- needed to find its `turtle_canvas`
    element, if it has one, since `codeslides.turtle` calls
    (ARCHITECTURE.md section 7) have no way to name a target themselves
    without breaking stdlib `turtle` call syntax.

    `deck_imports` is `Deck.imports` (`deck.py`) -- names a top-level
    `import`/`from ... import` bound in the deck's own source file
    (`loader.py`'s `load_deck`), so a cell body can use e.g. `numpy`
    without its own repeated `import numpy` in every cell that needs it.

    `is_main` (true only when `cell_name` is the Deck's one
    `Cell.is_main` cell -- callers pass `self.deck.cells[cell_name]
    .is_main`) makes `__name__` resolve to `"__main__"` for the
    duration of this one call, so a cell whose body is a real `if
    __name__ == "__main__":` block (matching how a student would run
    the whole deck as a standalone script) actually executes that
    block here too, instead of it being permanently dead code. Real
    Python resolves `__name__` from the running module's own
    `__globals__`, and since `session.namespace` *is* every cell's
    `__globals__` here (`_compile_cell_function`'s docstring), setting
    it there makes ordinary Python name resolution do the rest with no
    special-casing inside the cell body itself. Set only immediately
    before this call and restored (to whatever it was before, or
    removed entirely if it wasn't set) immediately after, in a
    `finally` -- `__name__ == "__main__"` must be true only while the
    main cell itself is actually running, never left lingering in the
    shared namespace afterward where an unrelated cell's own `if
    __name__ == "__main__":` (unlikely, but not impossible) would
    otherwise spuriously see it as still true.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    turtle_element = _find_turtle_canvas(elements or [])
    _NO_PRIOR_NAME = object()
    prior_name = session.namespace.get("__name__", _NO_PRIOR_NAME)
    _NO_PRIOR_INPUT = object()
    prior_input = session.namespace.get("input", _NO_PRIOR_INPUT)
    try:
        # `cs`/`turtle` are framework-provided names every cell body can
        # call without its own import -- the compiled function's globals
        # are otherwise seeded only from the Session namespace, so without
        # this a bare `cs.image(...)`/`turtle.forward(...)` call would
        # NameError even though the deck's source file imports them at
        # module scope (that import context isn't carried into the
        # per-cell exec). `deck_imports` follows right after for the same
        # reason, for whatever else the deck's own file imports -- both
        # are written directly into `session.namespace` (setdefault, so a
        # cell's own prior write to a same-named global always wins, never
        # gets clobbered back to the framework's own value on the next
        # run) since `_compile_cell_function` now shares that dict as the
        # function's real `__globals__` rather than layering a throwaway
        # copy on top of it.
        for name, value in {"cs": cs, "turtle": turtle, **(deck_imports or {})}.items():
            session.namespace.setdefault(name, value)
        if is_main:
            session.namespace["__name__"] = "__main__"
        # Direct assignment, not setdefault like cs/turtle above -- each
        # cell needs its OWN shim (bound to its own text_input/slider
        # elements in its own order), not whichever cell happened to run
        # first's.
        # Restored (or removed) in the `finally` below, same reasoning and
        # same pattern as `__name__` just above: a per-call value that
        # must never leak into an unrelated cell's own run through the
        # shared `session.namespace`.
        session.namespace["input"] = _make_input_shim(cell_name, elements or [], session.instances[cell_name].elements)
        fn, return_names = _compile_cell_function(source, session.namespace)

        # Only bind element values for elements that are also declared
        # parameters -- input elements (slider/button/text_input) are, but
        # viewer elements (turtle_canvas/image/iframe/notes) are populated
        # *from* the cell's execution, not consumed as inputs to it
        # (ARCHITECTURE.md section 3a), so they must never be passed as
        # kwargs.
        params = set(fn.__code__.co_varnames[: fn.__code__.co_argcount])
        kwargs: dict[str, object] = {}
        element_instances = session.instances[cell_name].elements
        for element_name, instance in element_instances.items():
            if element_name in params:
                kwargs[element_name] = instance.value

        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            cs.execution_context() as writes,
            _maybe_turtle_context(turtle_element) as turtle_commands,
        ):
            result = fn(**kwargs)
    except Exception:  # noqa: BLE001 - a cell's own error must not kill the kernel, whether
        # it's a parse/definition problem (CellDefinitionError) or a runtime exception.
        return ExecutionResult(
            status="error",
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
            error=traceback.format_exc(),
        )
    finally:
        if is_main:
            if prior_name is _NO_PRIOR_NAME:
                session.namespace.pop("__name__", None)
            else:
                session.namespace["__name__"] = prior_name
        if prior_input is _NO_PRIOR_INPUT:
            session.namespace.pop("input", None)
        else:
            session.namespace["input"] = prior_input

    if turtle_commands and turtle_element is not None:
        writes.append(cs.ElementWrite(element_name=turtle_element, kind="turtle", content=turtle_commands))

    # The cell's own function is itself bound into the namespace under its
    # own name -- graph.py's extract_reads_writes now treats a cell's name
    # as an implicit write for exactly this reason, so another cell can
    # call it directly (e.g. `drawSquares` calling `drawSquare(...)`),
    # same as any two ordinary module-level functions could. Bound only
    # after a successful call, matching the "never partially pollute the
    # namespace on failure" rule the return-names binding below follows.
    session.namespace[cell_name] = fn

    if len(return_names) == 1:
        session.namespace[return_names[0]] = result
    elif len(return_names) > 1:
        values = result if isinstance(result, tuple) else (result,)
        if len(values) != len(return_names):
            return ExecutionResult(
                status="error",
                stdout=stdout.getvalue(),
                stderr=stderr.getvalue(),
                error=f"cell {cell_name!r} returned {len(values)} values for {len(return_names)} names",
            )
        for name, value in zip(return_names, values, strict=True):
            session.namespace[name] = value

    element_instances = session.instances[cell_name].elements
    for write in writes:
        if write.element_name not in element_instances:
            return ExecutionResult(
                status="error",
                stdout=stdout.getvalue(),
                stderr=stderr.getvalue(),
                error=(
                    f"cell {cell_name!r} called cs.{write.kind}({write.element_name!r}, ...) "
                    f"but has no element named {write.element_name!r}"
                ),
            )
    # Applied only after every write validates -- a bad element name in a
    # later cs.* call must not leave earlier ones partially applied,
    # matching the same all-or-nothing semantics as namespace writes above.
    for write in writes:
        element_instances[write.element_name].content = write.content

    return ExecutionResult(
        status="idle",
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
        value=result,
        element_writes=writes,
    )


def define_cell(
    cell_name: str,
    source: str,
    session: Session,
    deck_imports: dict[str, object] | None = None,
) -> ExecutionResult:
    """Compile the cell named `cell_name`'s function and bind it into
    `session.namespace` under its own name -- exactly like `execute_cell`
    already does -- but never actually *call* it. Used instead of
    `execute_cell` (`_run_cells`) for a cell that has a `tests` element
    attached, or has an unbound required parameter (no default, not
    matched by an input element): that cell's own top-level body is
    never auto-run with no arguments the way a plain cell's is; only a
    `tests` element (calling the function itself, with whatever
    arguments it chooses) or another cell's own code exercises it.
    `drawLineSegment(t, p1, p2, p3, p4)`/`markCorners(cells, t)` having
    no input elements bound to any parameter used to mean either was
    always called as e.g. `markCorners()`, every parameter defaulting to
    `None` if given one, or a guaranteed `TypeError` if not -- this
    sidesteps that entirely, since the function is simply never invoked
    on its own.

    Never writes a `return`-named value into the namespace (nothing ran
    to produce one) -- a cell relying on another *tested* cell's return
    value for its own reads would need that other cell's test to have
    actually run and, if it chooses to, written the value back some
    other way; this function only ever provides the *callable* itself,
    same as any two ordinary module-level functions would see each
    other regardless of whether either has been called yet.

    Still reports `CellDefinitionError`/`SyntaxError` (a bad `return`
    shape, invalid syntax) as this cell's own error -- those are
    definition-time problems, not call-time ones, so skipping the call
    doesn't skip catching them."""
    try:
        for name, value in {"cs": cs, "turtle": turtle, **(deck_imports or {})}.items():
            session.namespace.setdefault(name, value)
        fn, _ = _compile_cell_function(source, session.namespace)
    except Exception:  # noqa: BLE001 - same "a cell's own error must not kill the kernel" rule as execute_cell
        return ExecutionResult(status="error", error=traceback.format_exc())

    session.namespace[cell_name] = fn
    return ExecutionResult(status="idle")


def _find_tests_element(elements: list[Element]) -> str | None:
    """Return the name of the cell's one `tests` element, if it has
    exactly one -- same "ambiguous means none" rule as
    `_find_turtle_canvas`, since a cell's test result has nowhere
    well-defined to go if more than one `tests` element is attached."""
    test_elements = [e.name for e in elements if e.kind == "tests"]
    return test_elements[0] if len(test_elements) == 1 else None


def _has_unbound_required_param(source: str, elements: list[Element]) -> bool:
    """True if the cell's function has at least one parameter with no
    default value that isn't also bound by a matching input element
    (`ui.slider`/`ui.button`/`ui.text_input`, etc. -- anything whose
    name appears as an element in `elements`, same "element name ==
    parameter name" binding `execute_cell` itself uses).

    A required parameter with nothing to supply it would otherwise
    always be auto-called with that argument simply missing the moment
    `run_all`/`_run_cells` runs the cell with no arguments at all --
    `TypeError: missing N required positional arguments` -- exactly the
    same class of problem TODO.md #43 already solved for a `tests`-
    element cell like `markCorners(cells, t)`. This generalizes that
    fix: a cell meant to be called *only* by another cell's code (e.g.
    `drawLineSegment(t, p1, p2, p3, p4)`, no defaults on any parameter,
    no `tests` element either) should be just as safe -- requiring a
    `ui.tests(...)` element purely to suppress the auto-call, or
    otherwise forcing every parameter to fake a default (`=None`), was
    never really optional, just an awkward workaround.

    Parses `source` directly via `ast` rather than compiling/calling it
    -- this only needs the function's own argument list and defaults,
    computed the same way `_run_cells` needs to decide *before* choosing
    between `execute_cell` (calls it) and `define_cell` (never calls
    it), so it must not itself execute anything. Returns `False` (safe
    to call) if `source` doesn't even parse as a single function --
    that's `execute_cell`'s own error to raise, not this check's."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return False
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        return False
    func = func_defs[0]

    element_names = {e.name for e in elements}
    args = func.args.posonlyargs + func.args.args
    positional_required = args[: len(args) - len(func.args.defaults)]
    kwonly_required = [a for a, default in zip(func.args.kwonlyargs, func.args.kw_defaults) if default is None]

    return any(a.arg not in element_names for a in (*positional_required, *kwonly_required))


def _source_has_main_guard(source: str) -> bool:
    """True if the cell's function body contains a top-level `if
    __name__ == "__main__":` (or its reflected form, `if "__main__" ==
    __name__:`) statement -- the deck author's own way of saying "this
    is an entry point," matching a real standalone script's own
    convention, without necessarily having checked the `is_main`
    checkbox (`deck.Cell.is_main`) too. `execute_cell` treats either
    signal identically (`is_main or _source_has_main_guard(source)`):
    a cell written this way is presumably meant to behave like a real
    `__main__` guard, or it would just be permanently-dead code inside
    the reactive kernel (`__name__` otherwise never resolves to
    `"__main__"` there -- see `execute_cell`'s own docstring).

    Deliberately narrow (a top-level `if` in the function body, not
    anywhere nested inside a loop/other `if`/etc.) -- same "top-level
    only" precedent `_own_returns` (graph.py) already sets for finding
    a cell's own `return` statement, so a cell that merely *mentions*
    the pattern somewhere deep inside unrelated control flow doesn't
    false-positive. Parses `source` directly via `ast`, never executes
    it; returns `False` if `source` doesn't even parse (same
    fail-safe precedent as `_has_unbound_required_param`)."""

    def is_dunder_name_compare(node: ast.expr) -> bool:
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            return False
        left, right = node.left, node.comparators[0]
        pair = (left, right)
        name_side = next((n for n in pair if isinstance(n, ast.Name) and n.id == "__name__"), None)
        main_side = next(
            (n for n in pair if isinstance(n, ast.Constant) and n.value == "__main__"), None
        )
        return name_side is not None and main_side is not None and name_side is not main_side

    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return False
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        return False

    return any(
        isinstance(stmt, ast.If) and is_dunder_name_compare(stmt.test) for stmt in func_defs[0].body
    )


def run_tests(
    source: str,
    namespace: dict[str, object],
    elements: list[Element] | None = None,
    deck_imports: dict[str, object] | None = None,
    element_instances: dict[str, ElementInstance] | None = None,
) -> dict[str, Any]:
    """Run a `tests` element's source (ARCHITECTURE.md section 3b) as
    plain Python statements -- ordinary `assert`s, not a
    `unittest.TestCase` -- against `namespace` (the cell's own effective
    namespace: its return-named values plus everything its upstream
    dependencies wrote, i.e. `session.namespace` at the moment right
    after the cell's own execution finishes). Returns a wire-ready dict:

    - `status`: "pass" (every statement ran with no exception), "fail"
      (an `AssertionError` was raised), or "error" (anything else -- a
      `NameError` referencing something the cell never defined, a
      `SyntaxError` from an in-progress edit, etc -- kept distinct from
      "fail" so an author can tell "the code under test is wrong" apart
      from "the test itself doesn't even run").
    - `message`: the assertion/traceback text, or "" on pass.
    - `stdout`/`stderr`: always populated, pass or fail -- this box isn't
      only for `assert`-only unittest-style checks; an author can just as
      well write `print(createMatrix(3, 4))` with no assertions at all,
      to show/talk through a sample input and its output, and that
      printed text needs to actually reach the browser. Previously
      captured here but silently discarded before ever reaching the
      caller -- a print-only box always reported a trivial "pass" with
      its output thrown away, indistinguishable from an empty box.
    - `turtle_commands`: present only if `elements` includes exactly one
      `turtle_canvas` (same "ambiguous means none" rule execute_cell
      already applies) -- the test's own turtle drawing, meant to be
      written into that *same* canvas element by the caller, so a
      turtle-drawing cell's test can be visually checked against the
      cell's own canvas without needing a second one. Always present
      (possibly `[]`) when the cell has a canvas, so the caller can
      always tell "this cell has a canvas to update" from the key's
      presence rather than an empty list being ambiguous with "no
      canvas at all."

    Runs directly against `namespace` itself (mutated in place), not a
    copy -- a test box's own top-level code is exactly as "real" a
    piece of top-level Python as any cell's body, so a name it assigns
    persists into `session.namespace` the same way a cell's
    `global`-declared write does (see `execute_cell`/
    `_compile_cell_function`'s docstrings for why a copy fundamentally
    cannot make this work: a called cell's `global x` always resolves
    through that specific cell's own `__globals__` dict, fixed at
    compile time, never through whatever dict happens to call it). This
    is what makes a test like `x1 = 4; cell_2()` (where `cell_2` does
    `global x1; x1 += 5`) able to see and mutate the same `x1` the
    deck's other cells do, exactly like ordinary top-level script code
    calling a function that declares `global`.

    `cs`/`turtle`/`deck_imports` are seeded directly into `namespace`
    (via `setdefault`, so a cell's own prior write to a same-named
    global is never clobbered back to the framework's value) exactly
    like `execute_cell`/`define_cell` do, for the same reason: test code
    is still ordinary Python, needing the same framework names and
    deck-level imports available without an explicit import. The turtle
    context is fresh for every test run (a clean `_TurtleState`,
    position reset to the origin) -- the test's drawing replaces
    whatever the cell's own last run drew, it never draws *on top of*
    stale turtle state left over from the cell.

    `element_instances` (the owning cell's `CellInstance.elements`, if
    given) similarly seeds a per-call `input()` shim reading from this
    cell's own `ui.text_input`/`ui.slider` elements in order -- see
    `_make_input_shim`'s own docstring for why this is a direct
    assignment, not `setdefault` like `cs`/`turtle` above, and restored
    afterward rather than left in `namespace` for whatever runs next."""
    turtle_element = _find_turtle_canvas(elements or [])
    result: dict[str, Any] = {"status": "pass", "message": "", "stdout": "", "stderr": ""}
    if turtle_element is not None:
        result["turtle_commands"] = []
    if not source.strip():
        return result

    stdout, stderr = io.StringIO(), io.StringIO()
    for name, value in {"cs": cs, "turtle": turtle, **(deck_imports or {})}.items():
        namespace.setdefault(name, value)
    _NO_PRIOR_INPUT = object()
    prior_input = namespace.get("input", _NO_PRIOR_INPUT)
    if element_instances is not None:
        namespace["input"] = _make_input_shim("<test>", elements or [], element_instances)
    test_globals = namespace
    try:
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            _maybe_turtle_context(turtle_element) as turtle_commands,
        ):
            exec(compile(source, filename="<test>", mode="exec"), test_globals)  # noqa: S102 - trusted lesson code
    except AssertionError as exc:
        result["status"] = "fail"
        result["message"] = str(exc) or "assertion failed"
    except Exception:  # noqa: BLE001 - any other exception is a test-runner-level error, not a pass/fail
        result["status"] = "error"
        result["message"] = traceback.format_exc()
    finally:
        if element_instances is not None:
            if prior_input is _NO_PRIOR_INPUT:
                namespace.pop("input", None)
            else:
                namespace["input"] = prior_input

    result["stdout"] = stdout.getvalue()
    result["stderr"] = stderr.getvalue()
    if turtle_element is not None:
        result["turtle_commands"] = turtle_commands
    return result


def _run_and_apply_test(
    instance: CellInstance,
    tests_element: str,
    namespace: dict[str, object],
    elements: list[Element],
    deck_imports: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Run `instance`'s `tests_element` and apply the result: the test's
    own `{"status", "message", "stdout", "stderr"}` onto the tests
    element's `content` (ARCHITECTURE.md section 3b), and -- if the cell
    has a turtle canvas -- the test's turtle drawing onto *that* canvas
    element's `content`, replacing whatever the cell's own last run drew
    there. This is the "test code can draw into the cell's canvas to
    visually check turtle logic in isolation" behavior: the test's
    drawing intentionally overwrites the cell's, since there's only one
    canvas and the point is seeing what the test *would* draw, not
    layering it on top of unrelated leftover state. A subsequent run of
    the cell itself (an edit, a slider change) draws fresh and overwrites
    it right back.

    `stdout`/`stderr` are included regardless of `status` -- this box
    isn't only for `assert`-only checks; `print(createMatrix(3, 4))`
    with no assertions at all is just as valid a use (showing/talking
    through a sample input and its output), and its printed text needs
    to reach the browser exactly like the cell's own output already
    does."""
    test_source = instance.elements[tests_element].value or ""
    result = run_tests(test_source, namespace, elements, deck_imports=deck_imports, element_instances=instance.elements)
    instance.elements[tests_element].content = {
        "status": result["status"],
        "message": result["message"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }

    turtle_element = _find_turtle_canvas(elements)
    if turtle_element is not None and "turtle_commands" in result:
        instance.elements[turtle_element].content = result["turtle_commands"]
    return result


class Kernel:
    """Owns a Deck's baseline dependency graph and runs edits against
    Sessions.

    One Kernel per Deck (ARCHITECTURE.md section 4); many Sessions can run
    concurrently against it, each with its own isolated namespace. The
    Kernel's own `self.deck`/`self.graph` are the *baseline* (as-saved)
    definitions and are never mutated by a Session's edits -- a
    `instance="editable"` cell's live edits are stored only in
    `session.source_overrides` (ARCHITECTURE.md section 3), so the
    effective graph for a Session with overrides is computed on demand and
    discarded, never shared with other Sessions or written back into the
    Deck. This is what keeps two clones of an edited slide fully
    independent (ARCHITECTURE.md section 1), matching the marimo bug fix
    this whole model exists for.
    """

    def __init__(self, deck: Deck, deck_path: str | None = None) -> None:
        self.deck = deck
        self.graph: DependencyGraph = build_graph(deck)
        # The Deck's source file, if this Kernel was started against a real
        # file (CLI usage) rather than an in-memory Deck (tests). Used only
        # by `save_edits` (TODO.md #11) to know what to write back to --
        # never read for execution, which always goes through `self.deck`.
        self.deck_path = deck_path

    def reload_deck(self, deck: Deck) -> None:
        """Replace the baseline Deck/graph wholesale -- used by the CLI's
        file-watcher (TODO.md #10) when the deck's source file changes on
        disk. Existing Sessions are untouched: their namespace, element
        state, and any `instance="editable"` source_overrides survive a
        reload exactly as they were, since none of that lives on the
        Kernel. A Session only sees the new baseline the next time it
        runs a cell that has no override for it (ARCHITECTURE.md section 3's
        override-takes-precedence rule already handles this correctly)."""
        self.deck = deck
        self.graph = build_graph(deck)

    def run_all(self, session: Session) -> dict[str, ExecutionResult]:
        """Run every cell once, in topological order, against `session`."""
        graph = self._effective_graph(session)
        return self._run_cells(graph.topological_order(), session)

    def on_cell_edited(
        self, cell_name: str, source: str, session: Session
    ) -> dict[str, ExecutionResult]:
        """Handle a source edit to `cell_name`, scoped to `session` only:
        record the override, recompute *this session's* effective graph,
        and re-run the minimal affected set (ARCHITECTURE.md section 3,
        steps 1-3). Never touches `self.deck` or any other Session.

        An edit that doesn't even parse (a syntax error while mid-edit --
        the ordinary, expected state of live-typed code between
        keystrokes) or that breaks graph-level invariants
        (`MultipleDefinitionError`/`GraphCycleError`) is reported as this
        cell's own error, exactly like a runtime exception inside the
        cell would be -- it must not crash the edit_cell round trip or
        leave `session.source_overrides` silently unset. The invalid
        source is still recorded as the override (so the editor keeps
        showing what the user typed) and no other cell is touched.

        `source` is decorator- and docstring-free (the browser's editor
        only ever shows/edits `display_source`'s output, which strips
        both) -- and, for a `hide_def=True` cell (`Cell.hide_def`), also
        `def`-line-free and un-indented -- `reattach_decorator` reunites
        it with whatever decorator, docstring, and (if `hide_def`) `def`
        line currently apply to this cell (this Session's own prior
        override if one exists, else the Deck's baseline) before it's
        recorded, so `session.source_overrides` stays the full shape
        `save_edits`/`_apply_overrides` expect and a later Save doesn't
        silently drop the decorator, the `def` line, or the cell's notes
        from the file.

        `reattach_decorator` falls back to reattaching just the decorator
        (no docstring) if the edited body doesn't even parse -- the
        ordinary, expected state of live-typed code between keystrokes --
        so the override still records what was typed rather than
        nothing at all; the graph-rebuild below independently fails and
        reports the same syntax error either way."""
        current = session.source_overrides.get(cell_name, self.deck.cells[cell_name].source)
        hide_def = self.deck.cells[cell_name].hide_def
        session.source_overrides[cell_name] = reattach_decorator(current, source, hide_def=hide_def)
        try:
            graph = self._effective_graph(session)
        except (SyntaxError, ValueError) as exc:
            session.instances[cell_name].status = "error"
            session.instances[cell_name].error = str(exc)
            # A bad definition (e.g. `CellDefinitionError`'s multiple-return
            # check) is now caught here, at graph-build time, rather than
            # only surfacing once `_run_cells` actually tries to run the
            # cell -- `extract_reads_writes` needs a cell's return names to
            # know its graph-level writes, so it now runs this analysis (and
            # can raise this same error) earlier than before. A tested cell
            # must still see this reflected as its own test error (matching
            # `_run_cells`'s "cell errored -> mark test error" branch), not
            # silently keep showing whatever pass/fail it last had.
            tests_element = _find_tests_element(self.deck.cells[cell_name].elements)
            if tests_element is not None:
                session.instances[cell_name].elements[tests_element].content = {
                    "status": "error",
                    "message": "cell did not run successfully",
                }
            return {
                cell_name: ExecutionResult(status="error", error=str(exc)),
            }
        affected = graph.affected_by(cell_name)
        return self._run_cells(affected, session)

    def on_notes_edited(self, cell_name: str, element_name: str, notes_text: str, session: Session) -> None:
        """Handle a `notes` element's markdown content changing, scoped to
        `session` only: fold it into `session.source_overrides` as a
        regenerated whole-cell source (docstring replaced/inserted/
        removed -- `set_notes_docstring`), the same slot a plain code edit
        already uses, so the existing Save button/`save_edits` path
        persists it with no separate save mechanism (ARCHITECTURE.md
        section 8's "pure UI state" still holds -- this never triggers a
        re-run, same as the `instance.content` update below always has).

        Unlike `on_cell_edited`, an unparseable *current* source (this
        cell's own code is mid-edit with invalid syntax elsewhere in the
        same session) means there's no reliable place to insert/replace a
        docstring -- silently skip updating `source_overrides` in that
        case rather than raising out of a call site with no error-
        reporting path for notes edits, matching this method's
        `-> None` (no `ExecutionResult`s to report, unlike a code edit).
        The in-memory `instance.content` update (what the notes viewer
        actually renders) always happens regardless, so the editor never
        appears to reject or lose what was typed -- only the disk-bound
        override is deferred until the code becomes valid again."""
        instance = session.instances[cell_name].elements.get(element_name)
        if instance is not None:
            instance.content = notes_text
        current = session.source_overrides.get(cell_name, self.deck.cells[cell_name].source)
        try:
            session.source_overrides[cell_name] = set_notes_docstring(current, notes_text)
        except (SyntaxError, ValueError):
            pass

    def on_element_changed(
        self, cell_name: str, element_name: str, value: object, session: Session
    ) -> dict[str, ExecutionResult]:
        """Handle an input element's value changing: update the element
        instance and re-run the minimal affected set, same as an edit to
        the owning cell (ARCHITECTURE.md section 3a).

        Same graceful-failure guard as `on_cell_edited`: some *other*
        cell in this Session may currently have an invalid (mid-edit)
        source override sitting in `session.source_overrides` --
        rebuilding the effective graph must not crash just because this
        unrelated element's value changed."""
        session.instances[cell_name].elements[element_name].value = value
        try:
            graph = self._effective_graph(session)
        except (SyntaxError, ValueError) as exc:
            return {cell_name: ExecutionResult(status="error", error=str(exc))}
        affected = graph.affected_by(cell_name)
        return self._run_cells(affected, session)

    def on_tests_edited(
        self, cell_name: str, element_name: str, source: str, session: Session
    ) -> dict[str, str]:
        """Handle an edit to a `tests` element's source (ARCHITECTURE.md
        section 3b): store the new source and re-run it immediately
        against the namespace as it currently stands -- i.e. against
        whatever the owning cell's *last successful run* already put
        there, not a fresh re-run of the cell itself. Unlike
        `on_cell_edited`/`on_element_changed`, this never touches the
        dependency graph or re-runs any cell: test source has no
        reads/writes of its own to the graph, it only observes the
        results other cells already produced. If the cell has a
        `turtle_canvas`, the test's own turtle drawing (if any) replaces
        that canvas's content too -- see `_run_and_apply_test`. Returns
        the new `{"status", "message", "stdout", "stderr"}` result (never
        `turtle_commands`; the canvas gets its own separate update) --
        this is what `ws_handler.py`'s `SetTestSource` sends straight
        back to the browser as this element's live output, so a
        print-only test box (no assertions at all, just e.g.
        `print(createMatrix(3, 4))` to show a sample input/output) needs
        its printed text here, not just in the auto-run-after-a-cell-edit
        path.

        Also folds the edit into `session.source_overrides` as a
        regenerated whole-cell source (`set_tests_default`, replacing
        this element's own `default=` on the decorator) -- the same slot
        a code or notes edit already uses, so the existing Save button/
        `save_edits` path persists it with no separate save mechanism.
        Previously this test source lived *only* in
        `instance.elements[element_name].value`, in-memory -- Save never
        touched it at all, so a test box's content silently reverted to
        the deck file's original `default=` on the next reload or fresh
        Session. Same graceful-failure guard as `on_notes_edited`: an
        unparseable *current* source (this cell's own code is mid-edit
        with invalid syntax elsewhere in the same session) means there's
        nowhere reliable to update the decorator -- silently skip
        updating `source_overrides` in that case; the in-memory
        `instance.value`/test-run result above still always happens
        regardless, so the editor never appears to reject or lose what
        was typed."""
        instance = session.instances[cell_name]
        elements = self.deck.cells[cell_name].elements
        instance.elements[element_name].value = source
        result = _run_and_apply_test(
            instance, element_name, session.namespace, elements, deck_imports=self.deck.imports
        )
        current = session.source_overrides.get(cell_name, self.deck.cells[cell_name].source)
        try:
            session.source_overrides[cell_name] = set_tests_default(current, element_name, source)
        except (SyntaxError, ValueError):
            pass
        return {
            "status": result["status"],
            "message": result["message"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

    def add_cell(self, session: Session) -> tuple[Cell, ExecutionResult]:
        """Add a brand-new, blank `instance="editable"` cell (TODO.md
        #21) -- appended to the deck's `.py` file on disk immediately
        (not staged behind the Save button, unlike an edit to an
        *existing* cell's source: a newly-added cell must never be
        silently lost if the author forgets to click Save), then
        reloaded into this Kernel's own baseline synchronously (same
        `load_deck` + swap-in pattern `save_deck`/the CLI file-watcher
        already use, so `/api/deck` and every *new* Session/connection
        see it immediately -- but see the module-level note on scope:
        already-open Sessions other than this one only pick it up on
        their next reconnect, matching `reload_deck`'s existing,
        deliberately narrow scope).

        Requires `self.deck_path` (raises `ValueError` without one --
        there's nowhere to append to for an in-memory-only Deck, e.g.
        most of this test suite).

        Backfills `session`'s own `instances` for the new cell via
        `Session.seed_cell_instance` -- without this, the very next
        `run_all`/`on_cell_edited` in *this* session would `KeyError`
        on `session.instances[new_name]`, since every such lookup
        assumes every cell in the graph already has an instance. Then
        runs the new cell once (its body is just `pass`, so this mostly
        exists for consistency -- every other cell is running-state by
        the time an author sees it, a blank cell shouldn't look
        conspicuously different)."""
        if self.deck_path is None:
            raise ValueError("cannot add a cell: this Kernel was not started from a deck file")

        from codeslides.serialization import append_cell, new_cell_name

        name = new_cell_name(frozenset(self.deck.cells))
        append_cell(self.deck_path, name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))

        cell = self.deck.cells[name]
        session.seed_cell_instance(name, cell)
        results = self._run_cells([name], session)
        return cell, results[name]

    def add_slide(
        self, title: str, cell_names: list[str], reveal_code: bool = False
    ) -> Slide:
        """Create a new slide grouping `cell_names` (browser-driven
        counterpart to the `@app.slide(...)` decorator) -- appended to
        the deck's `.py` file on disk immediately, then reloaded into
        this Kernel's own baseline synchronously, same "write now, no
        staged/unsaved state" precedent as `add_cell`.

        Unlike `add_cell`, there's no per-Session instance to seed and
        nothing to run: a Slide never introduces variables into the
        dependency graph or executes anything (`deck.Slide`'s own
        docstring) -- it only groups cells that already have their own
        instances/results.

        Requires `self.deck_path` (raises `ValueError` without one, same
        as `add_cell`)."""
        if self.deck_path is None:
            raise ValueError("cannot add a slide: this Kernel was not started from a deck file")

        from codeslides.serialization import append_slide

        append_slide(self.deck_path, title, cell_names, reveal_code)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))

        return self.deck.slides[-1]

    def remove_slide(self, index: int) -> None:
        """Delete slide `index` entirely -- on disk, immediately, then
        reloaded into this Kernel's own baseline synchronously, same
        write-now precedent as `add_slide`/`remove_cell`.

        Deliberately does NOT touch any Session's own state (unlike
        `remove_cell`, which pops the removed name out of every
        Session's `instances`/`source_overrides`/`namespace`) -- a
        Slide has no per-Session instance to begin with (`add_slide`'s
        own docstring: "nothing to run"), and removing one doesn't
        remove any cell, so there's nothing cell-shaped for a Session
        to forget here.

        Requires `self.deck_path` (raises `ValueError` without one,
        same as `add_slide`)."""
        if self.deck_path is None:
            raise ValueError("cannot remove a slide: this Kernel was not started from a deck file")

        from codeslides.serialization import remove_slide as _remove_slide_on_disk

        _remove_slide_on_disk(self.deck_path, index)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))

    def add_title_slide(self, session: Session) -> tuple[Cell, Slide, ExecutionResult]:
        """Create a title slide (TODO.md #61): a new `cs.md(...)` cell
        holding the deck's own title, a one-line summary placeholder, and
        a generated table of contents of the deck's other slides,
        inserted as the deck's *first* slide -- one click, no form to
        fill in first (confirmed with the user: the title/TOC are
        generated, the author edits the placeholder summary afterward
        the same way they'd edit any other cell). Same "write to disk
        immediately" precedent as `add_cell`/`add_slide` -- no staged/
        unsaved state, so a title slide is never silently lost if the
        author forgets to click Save.

        Backfills `session`'s own `instances` for the new cell (same
        reason as `add_cell`: every existing lookup assumes
        `session.instances[cell_name]` always exists) and runs it once,
        for the same "shouldn't look conspicuously unlike every other
        cell by the time the author sees it" consistency `add_cell`
        already established -- unlike a blank cell's `pass` body, this
        one actually has real content to show immediately.

        Requires `self.deck_path` (raises `ValueError` without one, same
        as `add_cell`/`add_slide`)."""
        if self.deck_path is None:
            raise ValueError("cannot add a title slide: this Kernel was not started from a deck file")

        from codeslides.serialization import append_title_slide

        deck_title = Path(self.deck_path).stem
        cell_name, slide_title = append_title_slide(self.deck_path, deck_title)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))

        cell = self.deck.cells[cell_name]
        session.seed_cell_instance(cell_name, cell)
        results = self._run_cells([cell_name], session)
        slide = next(s for s in self.deck.slides if s.title == slide_title)
        return cell, slide, results[cell_name]

    def rename_cell(self, session: Session, old_name: str, new_name: str) -> Cell:
        """Rename a cell's identity (TODO.md #22 -- the edit button's
        "edit the title of a cell"), on disk, immediately: rewrites the
        cell's own `def`/decorator line and cascades into every slide's
        `cells=[...]` reference (`serialization.rename_cell`), then
        reloads this Kernel's baseline synchronously, same pattern as
        `add_cell`/`save_deck`.

        Refuses the rename (`ValueError`) if any *other* cell's already-
        parsed `reads` names `old_name` -- i.e. some other cell's code
        directly reads this cell's return value or calls it by name
        (ARCHITECTURE.md section 3's graph edges). Rewriting an arbitrary
        Python identifier occurrence inside someone else's cell body
        isn't safe to do blindly (could be a substring match, a shadowed
        local, anything) -- confirmed with the user this should be a
        clean, actionable error telling the author to remove the
        reference first, not a silent/partial rewrite.

        Remaps `session`'s own `instances`/`source_overrides` entries
        from `old_name` to `new_name` (same key, new name) so this
        session doesn't `KeyError` on its next run -- other already-open
        Sessions are unaffected until they reconnect, same scope as
        `add_cell`.

        A `source_overrides` entry isn't just moved to the new key
        as-is: its own `def old_name(...)` line (and decorator, if
        stale) must be regenerated too, via `rebuild_cell_source` --
        otherwise the override's *value* still literally reads `def
        old_name(...)` even though it's now keyed under `new_name`, and
        a later Save (`save_edits`) would splice that stale text back
        onto the file verbatim, silently reintroducing the old name and
        undoing the rename on disk the moment the user saves. Rebuilt
        from the just-`reload_deck`-ed `Cell` (the fresh on-disk
        instance/elements/hide_def), keeping the override's own edited
        body byte-identical -- same shape `rebuild_cell_source`'s other
        callers (`_replace_elements`) already use."""
        if self.deck_path is None:
            raise ValueError("cannot rename a cell: this Kernel was not started from a deck file")
        if old_name not in self.deck.cells:
            raise ValueError(f"cannot rename cell {old_name!r}: it no longer exists")
        if new_name in self.deck.cells and new_name != old_name:
            raise ValueError(f"cannot rename cell {old_name!r} to {new_name!r}: that name already exists")

        blockers = sorted(
            name
            for name, cell in self.deck.cells.items()
            if name != old_name and old_name in cell.reads
        )
        if blockers:
            raise ValueError(
                f"cannot rename cell {old_name!r}: it's referenced by {blockers} -- "
                "remove those references first"
            )

        from codeslides.serialization import rename_cell as _rename_cell_on_disk

        _rename_cell_on_disk(self.deck_path, old_name, new_name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))

        if old_name in session.instances:
            session.instances[new_name] = session.instances.pop(old_name)
        if old_name in session.source_overrides:
            from codeslides.serialization import rebuild_cell_source

            stale = session.source_overrides.pop(old_name)
            new_cell = self.deck.cells[new_name]
            session.source_overrides[new_name] = rebuild_cell_source(
                new_name,
                new_cell.instance,
                new_cell.elements,
                stale,
                hide_def=new_cell.hide_def,
                is_main=new_cell.is_main,
                is_setup=new_cell.is_setup,
                hide_code=new_cell.hide_code,
            )
        if old_name in session.namespace:
            del session.namespace[old_name]

        cell = self.deck.cells[new_name]
        session.seed_cell_instance(new_name, cell)
        return cell

    def set_main_cell(self, session: Session, cell_name: str) -> Cell:
        """Mark `cell_name` as the deck's one designated main cell
        (TODO.md's `is_main` toggle -- "how do I denote the cell
        containing the main code"), on disk, immediately, same
        write-immediately precedent as `rename_cell`/`add_cell`: there's
        no staged/unsaved version of this. `serialization.set_main_cell`
        also strips `is_main=True` from whichever *other* cell had it
        (a deck can only have one -- `deck.Deck.add_cell` enforces this
        at the model layer too), so this single call can flip the
        designation from one cell to another in one disk write.

        Reloads this Kernel's baseline synchronously afterward (same
        pattern as `rename_cell`/`remove_cell`) so `self.deck.cells[...]
        .is_main` is correct for every Session immediately, not just
        this one -- unlike a cell's own code/elements, `is_main` isn't
        something a Session can locally override, so there's no
        `session.source_overrides` bookkeeping needed here the way
        `rename_cell` has for a renamed cell's pending edit."""
        if self.deck_path is None:
            raise ValueError("cannot set a main cell: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot set cell {cell_name!r} as main: it no longer exists")

        from codeslides.serialization import set_main_cell as _set_main_cell_on_disk

        _set_main_cell_on_disk(self.deck_path, cell_name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        return self.deck.cells[cell_name]

    def set_setup_cell(self, session: Session, cell_name: str) -> Cell:
        """Mark `cell_name` as the deck's one designated setup/imports
        cell (`deck.Cell.is_setup`), same shape as `set_main_cell` in
        every respect -- on disk immediately, one-per-deck (enforced by
        `serialization.set_setup_cell` stripping any other holder), and
        reloads this Kernel's baseline synchronously afterward."""
        if self.deck_path is None:
            raise ValueError("cannot set a setup cell: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot set cell {cell_name!r} as setup: it no longer exists")

        from codeslides.serialization import set_setup_cell as _set_setup_cell_on_disk

        _set_setup_cell_on_disk(self.deck_path, cell_name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        return self.deck.cells[cell_name]

    def set_hide_code(self, session: Session, cell_name: str, hide_code: bool) -> Cell:
        """Set/clear `cell_name`'s `hide_code` (`deck.Cell.hide_code`),
        on disk, immediately -- same write-immediately, reload-baseline-
        synchronously precedent as `set_main_cell`. Unlike `is_main`,
        there's no uniqueness constraint to enforce, so this only ever
        touches `cell_name`'s own decorator."""
        if self.deck_path is None:
            raise ValueError("cannot set hide_code: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot set hide_code for cell {cell_name!r}: it no longer exists")

        from codeslides.serialization import set_hide_code as _set_hide_code_on_disk

        _set_hide_code_on_disk(self.deck_path, cell_name, hide_code)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        return self.deck.cells[cell_name]

    def remove_cell(self, session: Session, name: str) -> None:
        """Delete a cell entirely (TODO.md #54's "cells can be deleted
        and rearranged"), on disk, immediately -- the inverse of
        `add_cell`. Cascades into any `@app.slide(..., cells=[...])`
        reference to `name` (`serialization.remove_cell` strips it out
        of the list, a plain presentation-grouping fact, not a code
        dependency, so this is always a safe cascade rather than a
        refusal).

        Refuses the delete (`ValueError`) if any *other* cell's already-
        parsed `reads` names either `name` itself (calls this cell's
        function directly, e.g. `name(...)`) or *any name this cell's
        own `return` binds* (reads a value only this cell produces,
        e.g. `def name(): ... return shared_value` and another cell's
        body uses `shared_value`) -- both are real code dependencies
        (ARCHITECTURE.md section 3's graph edges: a cell's own name is
        an implicit write alongside whatever its `return` exposes, so
        both are just different entries in the same `Cell.writes` set).
        Deleting the cell out from under either would leave that other
        cell's next run raising a plain `NameError` with no indication
        why -- refusing up front and telling the author to remove the
        reference first is the same honest tradeoff `rename_cell`
        already makes, extended here to cover a return-value reference
        too (confirmed by hand that `rename_cell` itself doesn't check
        this either -- a pre-existing gap there, out of scope to fix as
        part of this change, but one this method must not repeat, since
        deleting a cell is a strictly more destructive operation than
        renaming one).

        Drops `name`'s own entries from `session.instances`/
        `source_overrides`/`namespace` -- there's no "remap to a new
        key" step the way `rename_cell` needs, since the cell (and
        every name it ever wrote) is simply gone, not renamed."""
        if self.deck_path is None:
            raise ValueError("cannot remove a cell: this Kernel was not started from a deck file")
        if name not in self.deck.cells:
            raise ValueError(f"cannot remove cell {name!r}: it no longer exists")

        removed_names = self.deck.cells[name].writes  # the cell's own name + every name its return binds
        blockers = sorted(
            other_name
            for other_name, cell in self.deck.cells.items()
            if other_name != name and cell.reads & removed_names
        )
        if blockers:
            raise ValueError(
                f"cannot remove cell {name!r}: it's referenced by {blockers} -- "
                "remove those references first"
            )

        from codeslides.serialization import remove_cell as _remove_cell_on_disk

        _remove_cell_on_disk(self.deck_path, name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))

        session.instances.pop(name, None)
        session.source_overrides.pop(name, None)
        session.namespace.pop(name, None)

    def reorder_cells(self, session: Session, cell_order: list[str]) -> None:
        """Reorder every cell in the deck to match `cell_order` exactly
        (TODO.md #54), on disk, immediately -- each cell's own source is
        untouched, only which order the top-level definitions appear in
        the file (and therefore `Deck.cells`' own dict order, which
        `_effective_graph`/`_run_cells`/the browser's own cell list all
        already read display/execution order from) changes.

        No Session-side cleanup needed, unlike `rename_cell`/`remove_cell`
        -- `session.instances`/`source_overrides`/`namespace` are all
        keyed by cell *name*, never by position, so nothing about them
        goes stale just because the underlying deck's cells changed
        order."""
        if self.deck_path is None:
            raise ValueError("cannot reorder cells: this Kernel was not started from a deck file")
        if sorted(cell_order) != sorted(self.deck.cells):
            raise ValueError(
                f"cannot reorder cells: {cell_order!r} is not a permutation of the deck's "
                f"current cells {sorted(self.deck.cells)!r}"
            )

        from codeslides.serialization import reorder_cells as _reorder_cells_on_disk

        _reorder_cells_on_disk(self.deck_path, cell_order)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))

    def add_element(self, session: Session, cell_name: str, element: Element) -> tuple[Cell, ExecutionResult]:
        """Add `element` to `cell_name`'s `elements=[...]` list, on disk,
        immediately (TODO.md #22's element picker), then reload this
        Kernel's baseline synchronously, same pattern as `add_cell`.

        Backfills `session`'s own instance for the new element (via
        `Session.seed_cell_instance`, safe to call again for an
        already-seeded cell -- it only fills in what's missing) and
        re-runs the cell once so its status/output reflect the change
        immediately, same as a freshly-added cell does.

        Also resyncs any pending, unsaved `session.source_overrides`
        entry for this cell (`_resync_stale_override`) -- otherwise a
        later Save would splice that override's now-stale `elements=[...]`
        decorator back onto the file, silently reverting this add."""
        if self.deck_path is None:
            raise ValueError("cannot add an element: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot add an element to cell {cell_name!r}: it no longer exists")

        from codeslides.serialization import add_element as _add_element_on_disk

        _add_element_on_disk(self.deck_path, cell_name, element)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        self._resync_stale_override(session, cell_name)

        cell = self.deck.cells[cell_name]
        session.seed_cell_instance(cell_name, cell)
        results = self._run_cells([cell_name], session)
        return cell, results[cell_name]

    def remove_element(self, session: Session, cell_name: str, element_name: str) -> tuple[Cell, ExecutionResult]:
        """Remove the element named `element_name` from `cell_name`, on
        disk, immediately, then reload this Kernel's baseline
        synchronously -- the inverse of `add_element`.

        Drops the element's now-stale `ElementInstance` from `session`'s
        own instance for this cell (a removed element's leftover value/
        content would otherwise linger in memory even though it's gone
        from the Deck) and re-runs the cell once.

        Also resyncs any pending, unsaved `session.source_overrides`
        entry for this cell (`_resync_stale_override`), same reasoning
        as `add_element`."""
        if self.deck_path is None:
            raise ValueError("cannot remove an element: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot remove an element from cell {cell_name!r}: it no longer exists")

        from codeslides.serialization import remove_element as _remove_element_on_disk

        _remove_element_on_disk(self.deck_path, cell_name, element_name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        self._resync_stale_override(session, cell_name)

        cell = self.deck.cells[cell_name]
        if cell_name in session.instances:
            session.instances[cell_name].elements.pop(element_name, None)
        session.seed_cell_instance(cell_name, cell)
        results = self._run_cells([cell_name], session)
        return cell, results[cell_name]

    def remove_primary_editor(self, session: Session, cell_name: str) -> tuple[Cell, ExecutionResult]:
        """Delete `cell_name`'s body code entirely, on disk, immediately,
        then reload this Kernel's baseline synchronously --
        CELL_QUADRANT_LAYOUT_TODO.md item 2b's confirmed "zero primary
        editor means zero body code" decision. Similar overall shape to
        `remove_element` (reload, then re-run) but NOT `_resync_stale_
        override`: that helper's whole job is to keep a pending, unsaved
        source_overrides entry's *body* byte-identical while only
        regenerating its decorator -- exactly wrong here, since this
        operation's entire point is to replace the body. Calling it
        would silently keep the session showing (and a later Save
        re-writing) the pre-removal body forever, even though the
        on-disk cell is already a pass-bodied stub -- this was a real
        bug, caught via a live browser session, not just reasoning about
        the code: `session.source_overrides[cell_name]` must be dropped
        entirely instead, so the freshly-reloaded `cell.source` (the new
        stub) is what the browser is shown and what a later Save writes.
        No `ElementInstance` to drop either -- the cell's own body is
        what changed, not one of its elements -- so re-running it is
        what reflects the change (a `pass`-bodied cell returns `None`,
        same as any other cell whose body just returns nothing).

        `serialization.remove_primary_editor` itself raises
        `SaveConflictError` if `cell_name` still has a test editor (the
        add-time-only dependency rule enforced here by blocking removal,
        not by cascading a delete) -- this method doesn't duplicate that
        check, it just lets the exception propagate, same as
        `add_element`'s own duplicate-name `SaveConflictError` does."""
        if self.deck_path is None:
            raise ValueError("cannot remove the primary editor: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot remove the primary editor from cell {cell_name!r}: it no longer exists")

        from codeslides.serialization import remove_primary_editor as _remove_primary_editor_on_disk

        _remove_primary_editor_on_disk(self.deck_path, cell_name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        session.source_overrides.pop(cell_name, None)

        cell = self.deck.cells[cell_name]
        session.seed_cell_instance(cell_name, cell)
        results = self._run_cells([cell_name], session)
        return cell, results[cell_name]

    def add_primary_editor(self, session: Session, cell_name: str) -> tuple[Cell, ExecutionResult]:
        """Restore `cell_name`'s body to a blank, editable starting
        point, on disk, immediately, then reload this Kernel's baseline
        synchronously -- the inverse of `remove_primary_editor`, same
        overall shape as `add_element`. Also drops any pending
        `session.source_overrides` entry for this cell rather than
        resyncing it, same reasoning as `remove_primary_editor` above:
        the body just changed underneath whatever unsaved edit the
        override held, so there is nothing meaningful left to preserve
        from it."""
        if self.deck_path is None:
            raise ValueError("cannot add a primary editor: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot add a primary editor to cell {cell_name!r}: it no longer exists")

        from codeslides.serialization import add_primary_editor as _add_primary_editor_on_disk

        _add_primary_editor_on_disk(self.deck_path, cell_name)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        session.source_overrides.pop(cell_name, None)

        cell = self.deck.cells[cell_name]
        session.seed_cell_instance(cell_name, cell)
        results = self._run_cells([cell_name], session)
        return cell, results[cell_name]

    def reorder_elements(self, session: Session, cell_name: str, element_order: list[str]) -> Cell:
        """Reorder `cell_name`'s elements to match `element_order`, on
        disk, immediately (TODO.md #23's up/down reorder buttons), then
        reload this Kernel's baseline synchronously.

        A pure reorder never changes execution -- no element's config,
        value, or content changes, and the cell's own body is untouched
        -- so unlike `add_element`/`remove_element` this doesn't re-run
        the cell; the caller's existing `session.instances[cell_name]`
        (status/output/every element's live state) stays exactly as it
        was, keyed by name same as before.

        Also resyncs any pending, unsaved `session.source_overrides`
        entry for this cell (`_resync_stale_override`), same reasoning
        as `add_element`."""
        if self.deck_path is None:
            raise ValueError("cannot reorder elements: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot reorder elements for cell {cell_name!r}: it no longer exists")

        from codeslides.serialization import reorder_elements as _reorder_elements_on_disk

        _reorder_elements_on_disk(self.deck_path, cell_name, element_order)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        self._resync_stale_override(session, cell_name)
        return self.deck.cells[cell_name]

    def set_element_config(
        self, session: Session, cell_name: str, element_name: str, config: dict[str, object]
    ) -> Cell:
        """Replace the element named `element_name`'s config wholesale
        (TODO.md #23's iframe URL textbox, TODO.md #52's image-upload
        picker), on disk, immediately, then reload this Kernel's
        baseline synchronously.

        For an `iframe` or `image` element specifically, also pushes the
        new `src` straight into *this* session's own
        `ElementInstance.content` -- either one's rendered content
        otherwise only ever changes via the owning cell's own
        `cs.iframe(...)`/`cs.image(...)` call during a run
        (ARCHITECTURE.md section 3a), so without this, setting the URL/
        uploading an image here would correctly update the Deck's static
        default but never actually show up in the browser unless the
        cell happened to re-run afterward. Other element kinds' `content`
        is left alone -- their config isn't rendered directly, only
        interpreted the next time the owning cell runs.

        An `image` element's `src` is always a *list* (`ui.image`'s own
        constructor normalizes it, so this holds regardless of how the
        element was originally written) -- more than one image renders
        as a carousel (`ImageViewer`), the normal result of multi-
        selecting files in the upload picker (EditCellPanel.tsx's file
        input). Each item in the list is handled independently: a
        freshly-uploaded `data:image/...;base64,...` URI is written to
        a real file on disk (`_save_data_uri_as_asset`, in an `assets/`
        folder next to the deck) and replaced with that file's deck-
        relative path *before* anything is serialized, while an already-
        relative path (an existing image passing through untouched, or
        one hand-written into the source) is left alone -- so the `.py`
        file itself only ever gains small, portable, human-readable
        `src=["assets/<hash>.png", ...]` entries, never inline blobs,
        and calling this repeatedly with the same list (e.g. re-saving
        after adding one more image) never re-writes files that are
        already on disk. The browser itself still needs *absolute URLs*
        to actually fetch each file (a relative disk path means nothing
        to `<img src>`), so `instance.content` below becomes the list of
        `/deck-assets/...` URLs (`_deck_asset_url`, shared with
        `Session.seed_cell_instance`'s equivalent pre-upload seeding) --
        the matching `StaticFiles` mount `server.py`'s `create_app`
        registers at that same prefix, rooted at the deck's own
        `assets/` directory. The `.py` file's own `src=` and the
        browser's `instance.content` are deliberately different strings
        for exactly this reason: one is for a human reading the source,
        the other is for a running browser tab.

        Also resyncs any pending, unsaved `session.source_overrides`
        entry for this cell (`_resync_stale_override`), same reasoning
        as `add_element`."""
        if self.deck_path is None:
            raise ValueError("cannot set element config: this Kernel was not started from a deck file")
        if cell_name not in self.deck.cells:
            raise ValueError(f"cannot set config for an element in cell {cell_name!r}: it no longer exists")

        cell_before = self.deck.cells[cell_name]
        element_before = next((e for e in cell_before.elements if e.name == element_name), None)
        if element_before is not None and element_before.kind == "image" and isinstance(config.get("src"), list):
            # Each item is independently either a fresh data: URI (a
            # newly-picked file -- EditCellPanel.tsx's multi-select
            # upload sends the *whole* list, existing images plus
            # newly-picked ones, in one call) or an already-relative
            # asset path (an existing image passing through untouched)
            # -- only the former triggers a new write, so this is safe
            # to call repeatedly for the same list of images.
            config = {
                **config,
                "src": [
                    _save_data_uri_as_asset(self.deck_path, s) if isinstance(s, str) and s.startswith("data:") else s
                    for s in config["src"]
                ],
            }

        from codeslides.serialization import set_element_config as _set_element_config_on_disk

        _set_element_config_on_disk(self.deck_path, cell_name, element_name, config)

        from codeslides.loader import load_deck

        self.reload_deck(load_deck(self.deck_path))
        self._resync_stale_override(session, cell_name)

        cell = self.deck.cells[cell_name]
        element = next((e for e in cell.elements if e.name == element_name), None)
        if element is not None and element.kind in ("iframe", "image") and cell_name in session.instances:
            instance = session.instances[cell_name].elements.get(element_name)
            if instance is not None:
                if element.kind == "image":
                    instance.content = [_deck_asset_url(s) for s in config.get("src", [])]
                else:
                    instance.content = config.get("src", "")
        return cell

    def _resync_stale_override(self, session: Session, cell_name: str) -> None:
        """If `session` has a pending, unsaved `source_overrides` entry
        for `cell_name`, regenerate its decorator/`def` line from the
        just-`reload_deck`-ed `Cell` (this method must only be called
        right after an on-disk write + `reload_deck`), keeping the
        override's own edited body byte-identical.

        `add_element`/`remove_element`/`reorder_elements`/
        `set_element_config` all write a cell's `elements=[...]`
        decorator to disk immediately, then reload -- but none of them
        touch `session.source_overrides`, and `reload_deck` deliberately
        leaves existing Sessions' overrides untouched (they must survive
        a *file-watcher* reload unaffected). If this session also has an
        in-flight, unsaved code edit for the same cell, that override's
        own decorator now disagrees with the disk's fresh one (e.g. it
        still says `elements=[slider1]` after `slider2` was just added on
        disk) -- left alone, a later Save would splice that stale
        decorator back onto the file verbatim, silently reverting the
        very change the user just made through the element picker/
        reorder/config UI, even though everything they saw on screen
        already reflected it. Same fix shape as `rename_cell`'s own
        stale-override problem, just without a key rename."""
        if cell_name not in session.source_overrides:
            return
        from codeslides.serialization import rebuild_cell_source

        cell = self.deck.cells[cell_name]
        session.source_overrides[cell_name] = rebuild_cell_source(
            cell_name,
            cell.instance,
            cell.elements,
            session.source_overrides[cell_name],
            hide_def=cell.hide_def,
            is_main=cell.is_main,
            is_setup=cell.is_setup,
            hide_code=cell.hide_code,
        )

    def _effective_graph(self, session: Session) -> DependencyGraph:
        """The dependency graph as this Session currently sees it: the
        Deck's cells, with any of this Session's source overrides applied.
        Built fresh (never cached/shared) so per-Session divergence never
        leaks into the Kernel's baseline or another Session."""
        if not session.source_overrides:
            return self.graph
        effective = Deck()
        for name, cell in self.deck.cells.items():
            override = session.source_overrides.get(name)
            effective.add_cell(
                Cell(
                    name=cell.name,
                    source=override if override is not None else cell.source,
                    instance=cell.instance,
                    elements=cell.elements,
                )
            )
        return build_graph(effective)

    def _run_cells(self, names: list[str], session: Session) -> dict[str, ExecutionResult]:
        """Run `names` in order against `session`, updating each cell
        instance's status/output/error in place. `instance.output` carries
        the tagged output union from ARCHITECTURE.md section 6 (`kind` +
        `data`, resolved by `codeslides.output.resolve_output` from the
        cell's raw returned value), alongside stdout/stderr.

        A cell with a `tests` element is *defined* (`define_cell`) but
        never auto-run with no arguments the way a plain cell is --
        only its test (which calls the function itself, with whatever
        arguments it chooses) exercises it. A cell like `markCorners(cells,
        t)`, with no input elements bound to either parameter, would
        otherwise always be called as `markCorners()`, both defaulting to
        `None` regardless of what the test box passes -- this makes that
        entire class of "cell auto-ran with placeholder Nones" error
        impossible for a tested cell, not just harder to trigger.

        The same "define, don't call" treatment applies to any cell
        with an unbound required parameter (no default value, and no
        matching input element), `tests` element or not
        (`_has_unbound_required_param`) -- a helper cell meant only to
        be called by another cell's code, like `drawLineSegment(t, p1,
        p2, p3, p4)`, is just as safe from an auto-call as a tested
        cell already was; it should never have to fake a `=None`
        default on every parameter, or add a `tests` element it
        doesn't actually want, purely to avoid a guaranteed `TypeError`
        the moment `run_all` reaches it."""
        results: dict[str, ExecutionResult] = {}
        for name in names:
            source = session.source_overrides.get(name, self.deck.cells[name].source)
            instance = session.instances[name]
            instance.status = "running"
            elements = self.deck.cells[name].elements
            tests_element = _find_tests_element(elements)
            if tests_element is not None or _has_unbound_required_param(source, elements):
                result = define_cell(name, source, session, deck_imports=self.deck.imports)
            else:
                result = execute_cell(
                    name,
                    source,
                    session,
                    elements=elements,
                    deck_imports=self.deck.imports,
                    is_main=self.deck.cells[name].is_main or _source_has_main_guard(source),
                )
            instance.status = result.status
            resolved = resolve_output(result.value) if result.status == "idle" else None
            instance.output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "value": wire_safe_value(result.value),
                "kind": resolved.kind if resolved else None,
                "data": resolved.data if resolved else None,
            }
            instance.error = result.error
            results[name] = result

            # Auto-run this cell's attached tests element (ARCHITECTURE.md
            # section 3b), if it has one, against the namespace as it
            # stands right after the cell was defined (or, for an
            # untested cell, run) -- exactly what the test's own call
            # into the function will see. Skipped on an error defining/
            # running the cell: there's no valid function/namespace to
            # test against, and running tests against a stale/partial
            # namespace would just be misleading, not informative.
            if tests_element is not None:
                if result.status == "idle":
                    _run_and_apply_test(
                        instance, tests_element, session.namespace, elements, deck_imports=self.deck.imports
                    )
                else:
                    instance.elements[tests_element].content = {
                        "status": "error",
                        "message": "cell did not run successfully",
                    }
        return results
