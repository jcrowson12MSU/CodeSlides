"""Cell parser & dependency graph. See ARCHITECTURE.md section 3.

Static analysis via `ast`: for each Cell, determine the names it writes
(names it declares `global` and assigns, plus whatever its `return`
statement exposes) and the names it reads (free variables referenced but
not locally bound). A directed edge `A -> B` exists when B reads a name A
writes. Function parameters are excluded from reads — per ARCHITECTURE.md
section 3a, those are bound by attached input Elements (or plain default
arguments), not by other cells.

**Cell writes match real Python function-scoping, not marimo's flat
"every top-level assignment is a define" model.** A cell here is compiled
as a genuine Python function (`kernel.py`'s `_compile_cell_function`), not
flattened module-level statements the way marimo's own cells are — so an
ordinary local assignment with no `global` declaration must behave like
an ordinary local variable: private to that one cell, never colliding
with another cell's unrelated local of the same name, exactly as real
Python already guarantees for two unrelated functions. Only a name the
cell body actually declares `global` (a real, deliberate statement of
"this is meant to be shared across cells," matching how a script author
would mark shared mutable state in plain Python) becomes a graph-tracked
write. This was a real, reported bug before this comment existed: two
cells that each happened to use an unrelated local variable named the
same thing (e.g. a loop variable `x`, or a turtle-handle parameter named
`t`) would fail to even load the deck at all, with a `MultipleDefinitionError`
that had nothing to do with either cell's actual intent — confirmed by
hand with a real deck (`examples/marchingSquares.py`) that hit exactly
this with a plain `for x in range(...)` loop colliding against an
unrelated `global x` cell purely because both happened to write a
same-named local.
"""

from __future__ import annotations

import ast
import builtins
import textwrap
from dataclasses import dataclass, field

from codeslides.deck import Cell, Deck

_BUILTIN_NAMES = frozenset(dir(builtins)) | {"__name__", "__file__"}
_NESTED_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


class MultipleDefinitionError(ValueError):
    """Raised when more than one cell writes the same name."""

    def __init__(self, name: str, cell_names: list[str]) -> None:
        self.name = name
        self.cell_names = cell_names
        super().__init__(f"name {name!r} is defined by multiple cells: {cell_names}")


class GraphCycleError(ValueError):
    """Raised when the cell dependency graph contains a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(f"dependency cycle detected: {' -> '.join(cycle)}")


class CellDefinitionError(ValueError):
    """Raised when a cell's `return` statement doesn't cleanly name its
    declared writes (ARCHITECTURE.md section 3: cells expose named
    bindings, not arbitrary expressions). Lives here, not in `kernel.py`,
    because it's raised by `extract_return_names` below -- the same AST
    analysis both this module's `extract_reads_writes` (to know a cell's
    graph-level writes) and `kernel.py` (to know which names to unpack a
    cell's return value into at execution time) need; `kernel.py` imports
    it back from here."""


class _ReadWriteVisitor(ast.NodeVisitor):
    """Collects free reads, `global`-declared writes, and all local
    names (the last one needed only to correctly exclude locals from
    `reads` -- see `extract_reads_writes` below) from a function body.

    Not flow-sensitive within the "is this name global or local"
    question -- Python itself resolves that per-name, for the whole
    function, the moment a `global` statement or any assignment to that
    name appears anywhere in the body (the exact rule behind the
    well-known `UnboundLocalError` gotcha for reading a local before its
    first assignment), so a single, non-flow-sensitive pass matches real
    Python's own resolution rule here, not just approximates it.

    Nested function/lambda bodies are mostly treated as opaque scopes:
    their own reads still count as *this* cell's reads (closures can
    capture outer names), and their own plain local assignments don't
    leak out to the outer cell at all. `global` is the one exception,
    verified by hand against real Python: a `global x` statement inside
    a *nested* function still refers to the same module/exec-globals
    dict a `global x` in the cell's own top-level body would -- nesting
    depth doesn't change which namespace `global` points at -- so a
    nested function's own `global` declarations are folded into the
    outer cell's writes too, not treated as opaque the way a nested
    function's plain locals are.
    """

    def __init__(self, params: frozenset[str]) -> None:
        self.params = params
        # `local_names`: every name this scope assigns anywhere in its
        # body (the old, sole meaning of `writes` before this class
        # distinguished global from local) -- used only to keep `reads`
        # correct (a name read after being locally assigned is not a
        # free variable), never surfaced as a graph-level write.
        self.local_names: set[str] = set()
        # `global_writes`: only names this scope actually declares
        # `global` -- these, plus whatever the cell's own `return`
        # exposes (added by `extract_reads_writes` below, outside this
        # visitor), are the only real graph-level writes.
        self.global_writes: set[str] = set()
        self.reads: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.local_names.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.reads.add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_writes.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.local_names.add(node.name)
        self._visit_nested_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.local_names.add(node.name)
        self._visit_nested_scope(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.local_names.add(node.name)
        self._visit_nested_scope(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_nested_scope(node)

    def _visit_nested_scope(self, node: ast.AST) -> None:
        """Recurse into a nested function/class/lambda for *reads* and
        *global writes* only -- its own local assignments (parameters,
        internal non-global names) stay local and must not register as
        writes/reads of the enclosing cell. A nested scope's own
        `global` declarations DO bubble up (verified against real
        Python: `global x` always refers to the same module/exec-
        globals dict regardless of nesting depth, so a nested function
        declaring `global x` is a real write this cell makes, exactly
        as if the outer body had declared it directly) -- see this
        class's own docstring."""
        nested_params: set[str] = set()
        if isinstance(node, ast.Lambda):
            args = node.args
            body_nodes = [node.body]
        else:
            args = node.args
            body_nodes = node.body

        for arg_group in (args.posonlyargs, args.args, args.kwonlyargs):
            nested_params.update(a.arg for a in arg_group)
        if args.vararg:
            nested_params.add(args.vararg.arg)
        if args.kwarg:
            nested_params.add(args.kwarg.arg)

        inner = _ReadWriteVisitor(params=frozenset(nested_params))
        for child in body_nodes:
            inner.visit(child)
        # Reads not satisfied by the nested scope's own params/locals are
        # free variables from the enclosing cell's perspective.
        self.reads.update(inner.reads - nested_params - inner.local_names)
        self.global_writes.update(inner.global_writes)


def extract_return_names(func) -> list[str]:
    """Find the function's own `return` statement (if any) and return the
    name(s) it exposes to the dependency graph, in order. A bare `return
    name` yields `[name]`; a `return a, b` yields `[a, b]`; no return, or
    any other return shape (a computed expression, e.g. `return (x1 +
    x2) / 2, (y1 + y2) / 2`, not a bare name/tuple-of-names), yields
    `[]` -- there's simply no existing name to publish a computed
    expression's value under, so it's treated the same as no return at
    all: nothing extra gets bound into `session.namespace` for other
    cells to read by name.

    This does *not* make a computed-expression return unusable -- the
    cell's own displayed output still shows the returned value regardless
    of `return_names` (`kernel.py`'s `ExecutionResult.value`/
    `resolve_output`, set from the function's actual return value
    unconditionally), and the function itself is still bound into
    `session.namespace` under its own name after a successful call
    (ARCHITECTURE.md section 3's "a cell's own name is itself an
    implicit write"), so another cell can still get the real computed
    value by calling it directly, e.g. `mx, my = midpoint(p1, p2)` --
    exactly like calling any other cell's function. Only an *implicit*,
    graph-level name for the computed value is unavailable, which was
    never possible for an unnamed expression anyway.

    Returns nested inside an `if`/`for`/`with` block still belong to
    `func`; returns inside a nested function/lambda do not and are
    skipped."""
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
    return []


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


def extract_reads_writes(source: str) -> tuple[frozenset[str], frozenset[str]]:
    """Parse a single function definition's source and return (reads, writes).

    `source` is expected to be the source of exactly one function, as
    produced by `inspect.getsource` on an `@app.cell`-decorated function
    (decorator lines are ignored). Dedented before parsing so cells whose
    source function happens to be nested (e.g. defined inside a test
    function) still parse correctly.

    `writes` is the union of names the cell's body declares `global`
    (anywhere, including nested functions -- see `_ReadWriteVisitor`)
    and whatever its own `return` statement exposes (`extract_return_names`)
    -- these are the only two ways a cell can make a name available to
    other cells. An ordinary local assignment with no `global` is never
    a write, matching real Python function scoping.
    """
    tree = ast.parse(textwrap.dedent(source))
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        raise ValueError(f"expected exactly one function definition, found {len(func_defs)}")
    func = func_defs[0]

    params = frozenset(
        a.arg
        for a in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs)
    )

    visitor = _ReadWriteVisitor(params=params)
    for stmt in func.body:
        visitor.visit(stmt)

    writes = frozenset(visitor.global_writes) | frozenset(extract_return_names(func))
    reads = frozenset(visitor.reads) - visitor.local_names - writes - params - _BUILTIN_NAMES
    return reads, writes


def parse_cell(cell: Cell) -> Cell:
    """Return a copy of `cell` with `reads`/`writes` populated from its source."""
    reads, writes = extract_reads_writes(cell.source)
    # A cell's own name is an implicit write of itself -- kernel.py binds
    # the cell's compiled function into the namespace under `cell.name`
    # (its Deck key, not whatever literal `def` name happens to appear in
    # the source), so another cell can call it directly (e.g.
    # `drawSquares` calling `drawSquare(...)`), same as any two top-level
    # functions in one module. Deliberately `cell.name`, not the AST's
    # function name: an `instance="editable"` cell's live source can
    # rename its own `def` line while staying the same cell (same Deck
    # key, same session.instances/source_overrides entry) -- the graph
    # and namespace both need to track cell *identity*, not whatever text
    # currently follows `def` in the editor.
    writes = writes | {cell.name}
    reads = reads - writes
    return Cell(
        name=cell.name,
        source=cell.source,
        instance=cell.instance,
        reads=reads,
        writes=writes,
        elements=cell.elements,
        docstring=cell.docstring,
        hide_def=cell.hide_def,
        layout=cell.layout,
        is_main=cell.is_main,
    )


@dataclass
class DependencyGraph:
    """A directed graph over cell names: edge A -> B means B reads a name
    A writes. Supports topological execution order and minimal re-run set
    computation (ARCHITECTURE.md section 3)."""

    edges: dict[str, set[str]] = field(default_factory=dict)  # cell -> its dependents
    _order: list[str] = field(default_factory=list)

    def dependents(self, cell_name: str) -> set[str]:
        return self.edges.get(cell_name, set())

    def topological_order(self) -> list[str]:
        return list(self._order)

    def affected_by(self, cell_name: str) -> list[str]:
        """The minimal re-run set for an edit to `cell_name`: itself plus
        all transitive descendants, in topological order."""
        affected: set[str] = set()
        stack = [cell_name]
        while stack:
            current = stack.pop()
            if current in affected:
                continue
            affected.add(current)
            stack.extend(self.dependents(current) - affected)
        return [name for name in self._order if name in affected]


def build_graph(deck: Deck) -> DependencyGraph:
    """Parse every cell in `deck` (populating reads/writes) and build the
    dependency graph. Raises MultipleDefinitionError or GraphCycleError."""
    parsed = {name: parse_cell(cell) for name, cell in deck.cells.items()}
    deck.cells.update(parsed)

    writer_of: dict[str, str] = {}
    for name, cell in parsed.items():
        for written in cell.writes:
            if written in writer_of:
                raise MultipleDefinitionError(written, sorted([writer_of[written], name]))
            writer_of[written] = name

    edges: dict[str, set[str]] = {name: set() for name in parsed}
    for name, cell in parsed.items():
        for read in cell.reads:
            producer = writer_of.get(read)
            if producer is not None:
                edges[producer].add(name)

    order = _topological_sort(edges)
    return DependencyGraph(edges=edges, _order=order)


def _topological_sort(edges: dict[str, set[str]]) -> list[str]:
    in_degree = dict.fromkeys(edges, 0)
    for dependents in edges.values():
        for dep in dependents:
            in_degree[dep] += 1

    ready = sorted(name for name, deg in in_degree.items() if deg == 0)
    order: list[str] = []
    while ready:
        ready.sort()
        current = ready.pop(0)
        order.append(current)
        for dependent in sorted(edges[current]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)

    if len(order) != len(edges):
        remaining = [name for name in edges if name not in order]
        raise GraphCycleError(_find_cycle(edges, remaining))
    return order


def _find_cycle(edges: dict[str, set[str]], remaining: list[str]) -> list[str]:
    """Best-effort extraction of one concrete cycle among `remaining` nodes,
    for a readable error message."""
    remaining_set = set(remaining)
    start = remaining[0]
    path: list[str] = [start]
    visited: set[str] = set()
    current = start
    while True:
        visited.add(current)
        next_nodes = [n for n in edges[current] if n in remaining_set]
        if not next_nodes:
            break
        current = next_nodes[0]
        if current in path:
            return path[path.index(current) :] + [current]
        path.append(current)
    return path
