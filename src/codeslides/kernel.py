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
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass

from codeslides.deck import Cell, Deck
from codeslides.graph import DependencyGraph, build_graph
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


def execute_cell(cell_name: str, source: str, session: Session) -> ExecutionResult:
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
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        call_globals = dict(session.namespace)
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

        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = fn(**kwargs)
    except Exception:  # noqa: BLE001 - a cell's own error must not kill the kernel, whether
        # it's a parse/definition problem (CellDefinitionError) or a runtime exception.
        return ExecutionResult(
            status="error",
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
            error=traceback.format_exc(),
        )

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

    return ExecutionResult(status="idle", stdout=stdout.getvalue(), stderr=stderr.getvalue(), value=result)


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

    def __init__(self, deck: Deck) -> None:
        self.deck = deck
        self.graph: DependencyGraph = build_graph(deck)

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
        steps 1-3). Never touches `self.deck` or any other Session."""
        session.source_overrides[cell_name] = source
        graph = self._effective_graph(session)
        affected = graph.affected_by(cell_name)
        return self._run_cells(affected, session)

    def on_element_changed(
        self, cell_name: str, element_name: str, value: object, session: Session
    ) -> dict[str, ExecutionResult]:
        """Handle an input element's value changing: update the element
        instance and re-run the minimal affected set, same as an edit to
        the owning cell (ARCHITECTURE.md section 3a)."""
        session.instances[cell_name].elements[element_name].value = value
        graph = self._effective_graph(session)
        affected = graph.affected_by(cell_name)
        return self._run_cells(affected, session)

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
        instance's status/output/error in place. `instance.output` holds
        the raw stdout/stderr/value for now; resolving it into the tagged
        output union from ARCHITECTURE.md section 6 is TODO.md #12."""
        results: dict[str, ExecutionResult] = {}
        for name in names:
            source = session.source_overrides.get(name, self.deck.cells[name].source)
            instance = session.instances[name]
            instance.status = "running"
            result = execute_cell(name, source, session)
            instance.status = result.status
            instance.output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "value": result.value,
            }
            instance.error = result.error
            results[name] = result
        return results
