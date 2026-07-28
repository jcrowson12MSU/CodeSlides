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
import io
import textwrap
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field

from codeslides import cs, turtle
from codeslides.deck import Cell, Deck, Element
from codeslides.graph import DependencyGraph, build_graph
from codeslides.output import resolve_output, wire_safe_value
from codeslides.session import Session

_NESTED_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


class CellDefinitionError(ValueError):
    """Raised when a cell's `return` statement doesn't cleanly name its
    declared writes (ARCHITECTURE.md section 3: cells expose named
    bindings, not arbitrary expressions)."""


@dataclass
class ExecutionResult:
    """What running one cell produced, ready to populate a CellInstance."""

    status: str  # "idle" | "error"
    stdout: str = ""
    stderr: str = ""
    value: object | None = None
    error: str | None = None
    element_writes: list[cs.ElementWrite] = field(default_factory=list)


def _compile_cell_function(source: str, globals_dict: dict[str, object]):
    """Define a cell's function into `globals_dict` (so the function's own
    `__globals__` *is* that dict -- free variables it references resolve
    via ordinary Python global lookup, exactly like top-level names in a
    module) and return the callable plus the ordered list of names its
    `return` statement exposes. Dedented so cells whose source happens to
    be nested (e.g. under a test function) still parse.
    """
    dedented = textwrap.dedent(source)
    tree = ast.parse(dedented)
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        raise ValueError(f"expected exactly one function definition, found {len(func_defs)}")
    func = func_defs[0]
    func.decorator_list = []  # strip @app.cell(...) -- only the plain function is executed

    return_names = _extract_return_names(func)

    module = ast.Module(body=[func], type_ignores=[])
    ast.fix_missing_locations(module)
    code = compile(module, filename="<cell>", mode="exec")
    exec(code, globals_dict)  # noqa: S102 - trusted lesson code, defines the cell function only
    return globals_dict[func.name], return_names


def _extract_return_names(func) -> list[str]:
    """Find the function's own `return` statement (if any) and return the
    name(s) it exposes, in order. A bare `return name` yields `[name]`; a
    `return a, b` yields `[a, b]`; no return yields `[]`. Any other return
    shape (a computed expression, not a name/tuple-of-names) is rejected --
    cells expose named bindings, not arbitrary expressions, per
    ARCHITECTURE.md section 3. Returns nested inside an `if`/`for`/`with`
    block still belong to `func`; returns inside a nested function/lambda
    do not and are skipped."""
    returns = list(_own_returns(func.body))
    if not returns:
        return []
    if len(returns) > 1:
        raise CellDefinitionError(f"cell {func.name!r} has multiple return statements")
    (ret,) = returns
    if ret.value is None:
        return []
    if isinstance(ret.value, ast.Name):
        return [ret.value.id]
    if isinstance(ret.value, ast.Tuple) and all(isinstance(e, ast.Name) for e in ret.value.elts):
        return [e.id for e in ret.value.elts]
    raise CellDefinitionError(
        f"cell {func.name!r} must `return` a name or tuple of names, not a computed expression"
    )


def _own_returns(stmts):
    """Yield `Return` nodes belonging to this scope, recursing into
    control-flow blocks (if/for/while/with/try) but not into nested
    function/class/lambda definitions."""
    for stmt in stmts:
        if isinstance(stmt, ast.Return):
            yield stmt
        elif isinstance(stmt, _NESTED_SCOPE_TYPES):
            continue
        else:
            for field_name in ("body", "orelse", "finalbody", "handlers"):
                child = getattr(stmt, field_name, None)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.ExceptHandler):
                            yield from _own_returns(item.body)
                        elif isinstance(item, ast.stmt):
                            yield from _own_returns([item])


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


def execute_cell(
    cell_name: str, source: str, session: Session, elements: list[Element] | None = None
) -> ExecutionResult:
    """Call the cell named `cell_name`'s function (compiled fresh from
    `source`, which the caller has already resolved to this Session's
    effective source -- the Deck's, or a per-Session override for
    `instance="editable"` cells) against `session.namespace`: cross-cell
    reads are made available as the function's own globals (ordinary
    Python name resolution, matching how a plain module-level function
    reads other module-level names), bound input-element values are
    passed as keyword arguments (they're genuine parameters), and the
    function's `return`-named values are written back into the namespace.

    The function is defined into a *copy* of the namespace, not the
    namespace itself, so a failed call never partially pollutes it. Never
    touches any namespace but `session`'s, nor any Deck-level state -- this
    is what makes cloned Sessions (ARCHITECTURE.md section 1) fully
    independent at execution time, including per-Session source overrides
    (section 3), not just in the data model.

    `elements` is the cell's static element list (from the Deck, or an
    editable-instance override) -- needed to find its `turtle_canvas`
    element, if it has one, since `codeslides.turtle` calls
    (ARCHITECTURE.md section 7) have no way to name a target themselves
    without breaking stdlib `turtle` call syntax.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    turtle_element = _find_turtle_canvas(elements or [])
    try:
        # `cs`/`turtle` are framework-provided names every cell body can
        # call without its own import -- the compiled function's globals
        # are otherwise seeded only from the Session namespace, so without
        # this a bare `cs.image(...)`/`turtle.forward(...)` call would
        # NameError even though the deck's source file imports them at
        # module scope (that import context isn't carried into the
        # per-cell exec).
        call_globals = {"cs": cs, "turtle": turtle, **session.namespace}
        fn, return_names = _compile_cell_function(source, call_globals)

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


def _find_tests_element(elements: list[Element]) -> str | None:
    """Return the name of the cell's one `tests` element, if it has
    exactly one -- same "ambiguous means none" rule as
    `_find_turtle_canvas`, since a cell's test result has nowhere
    well-defined to go if more than one `tests` element is attached."""
    test_elements = [e.name for e in elements if e.kind == "tests"]
    return test_elements[0] if len(test_elements) == 1 else None


def run_tests(source: str, namespace: dict[str, object]) -> dict[str, str]:
    """Run a `tests` element's source (ARCHITECTURE.md section 3b) as
    plain Python statements -- ordinary `assert`s, not a
    `unittest.TestCase` -- against `namespace` (the cell's own effective
    namespace: its return-named values plus everything its upstream
    dependencies wrote, i.e. `session.namespace` at the moment right
    after the cell's own execution finishes). Returns a wire-ready
    `{"status": "pass" | "fail" | "error", "message": str}` dict:

    - "pass": every statement ran with no exception.
    - "fail": an `AssertionError` was raised (a failed assertion).
    - "error": anything else (a `NameError` referencing something the
      cell never defined, a `SyntaxError` from an in-progress edit, etc)
      -- distinguished from "fail" so an author can tell "the code under
      test is wrong" apart from "the test itself doesn't even run."

    Runs in a *copy* of `namespace`, never the namespace itself -- test
    code must never be able to mutate a cell's actual results out from
    under it (ARCHITECTURE.md section 1's isolation principle applies
    just as much to a test run as to any other execution)."""
    if not source.strip():
        return {"status": "pass", "message": ""}
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exec(compile(source, filename="<test>", mode="exec"), {**namespace})  # noqa: S102 - trusted lesson code
    except AssertionError as exc:
        return {"status": "fail", "message": str(exc) or "assertion failed"}
    except Exception:  # noqa: BLE001 - any other exception is a test-runner-level error, not a pass/fail
        return {"status": "error", "message": traceback.format_exc()}
    return {"status": "pass", "message": ""}


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
        showing what the user typed) and no other cell is touched."""
        session.source_overrides[cell_name] = source
        try:
            graph = self._effective_graph(session)
        except (SyntaxError, ValueError) as exc:
            session.instances[cell_name].status = "error"
            session.instances[cell_name].error = str(exc)
            return {
                cell_name: ExecutionResult(status="error", error=str(exc)),
            }
        affected = graph.affected_by(cell_name)
        return self._run_cells(affected, session)

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
        results other cells already produced. Returns the new
        `{"status", "message"}` result dict directly (there's no
        ExecutionResult here -- nothing was "executed" as a cell)."""
        instance = session.instances[cell_name].elements[element_name]
        instance.value = source
        result = run_tests(source, session.namespace)
        instance.content = result
        return result

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
        cell's raw returned value), alongside stdout/stderr."""
        results: dict[str, ExecutionResult] = {}
        for name in names:
            source = session.source_overrides.get(name, self.deck.cells[name].source)
            instance = session.instances[name]
            instance.status = "running"
            elements = self.deck.cells[name].elements
            result = execute_cell(name, source, session, elements=elements)
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
            # stands right after this cell's own run -- exactly what the
            # cell's own body would have seen. Skipped on the cell's own
            # error: there's no valid new result to test against, and
            # running tests against a stale/partial namespace would just
            # be misleading, not informative.
            tests_element = _find_tests_element(elements)
            if tests_element is not None:
                test_instance = instance.elements[tests_element]
                if result.status == "idle":
                    test_instance.content = run_tests(test_instance.value or "", session.namespace)
                else:
                    test_instance.content = {"status": "error", "message": "cell did not run successfully"}
        return results
