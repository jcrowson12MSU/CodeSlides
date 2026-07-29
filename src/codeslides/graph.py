"""Cell parser & dependency graph. See ARCHITECTURE.md section 3.

Static analysis via `ast`: for each Cell, determine the names it writes
(top-level bindings in its function body) and the names it reads (free
variables referenced but not locally bound). A directed edge `A -> B`
exists when B reads a name A writes. Function parameters are excluded from
reads — per ARCHITECTURE.md section 3a, those are bound by attached input
Elements (or plain default arguments), not by other cells.
"""

from __future__ import annotations

import ast
import builtins
import textwrap
from dataclasses import dataclass, field

from codeslides.deck import Cell, Deck

_BUILTIN_NAMES = frozenset(dir(builtins)) | {"__name__", "__file__"}


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


class _ReadWriteVisitor(ast.NodeVisitor):
    """Collects free reads and top-level writes from a function body.

    Not flow-sensitive: a name assigned anywhere in the body counts as a
    write for the whole function, matching marimo's static (not runtime)
    dependency model. Nested function/lambda bodies are treated as opaque
    scopes: their own reads still count as *this* cell's reads (closures
    can capture outer names), but their internal writes don't leak out as
    writes of the outer cell.
    """

    def __init__(self, params: frozenset[str]) -> None:
        self.params = params
        self.writes: set[str] = set()
        self.reads: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.writes.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.reads.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.writes.add(node.name)
        self._visit_nested_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.writes.add(node.name)
        self._visit_nested_scope(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.writes.add(node.name)
        self._visit_nested_scope(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_nested_scope(node)

    def _visit_nested_scope(self, node: ast.AST) -> None:
        """Recurse into a nested function/class/lambda for *reads* only —
        its own local writes (parameters, internal assignments) stay local
        and must not register as writes/reads of the enclosing cell."""
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
        # Reads not satisfied by the nested scope's own params/writes are
        # free variables from the enclosing cell's perspective.
        self.reads.update(inner.reads - nested_params - inner.writes)


def extract_reads_writes(source: str) -> tuple[frozenset[str], frozenset[str]]:
    """Parse a single function definition's source and return (reads, writes).

    `source` is expected to be the source of exactly one function, as
    produced by `inspect.getsource` on an `@app.cell`-decorated function
    (decorator lines are ignored). Dedented before parsing so cells whose
    source function happens to be nested (e.g. defined inside a test
    function) still parse correctly.
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

    reads = frozenset(visitor.reads) - visitor.writes - params - _BUILTIN_NAMES
    writes = frozenset(visitor.writes)
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
