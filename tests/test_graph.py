import pytest

from codeslides import App, ui
from codeslides.deck import Cell, Deck
from codeslides.graph import (
    GraphCycleError,
    MultipleDefinitionError,
    build_graph,
    extract_reads_writes,
)


def test_extract_reads_writes_basic():
    reads, writes = extract_reads_writes(
        "def cell():\n    x = 1\n    y = x + 1\n    return y\n"
    )
    assert reads == frozenset()
    assert writes == frozenset({"x", "y"})


def test_extract_reads_writes_cross_cell_read():
    reads, writes = extract_reads_writes(
        "def live_demo(speed):\n    result = base * speed\n    return result\n"
    )
    assert reads == frozenset({"base"})
    assert writes == frozenset({"result"})


def test_params_excluded_from_reads():
    reads, _ = extract_reads_writes("def cell(a, b, *args, **kwargs):\n    return a + b\n")
    assert reads == frozenset()


def test_builtins_excluded_from_reads():
    reads, _ = extract_reads_writes("def cell():\n    x = len([1, 2, 3])\n    return x\n")
    assert reads == frozenset()


def test_nested_function_writes_dont_leak():
    reads, writes = extract_reads_writes(
        """
def outer():
    def inner(z):
        w = z + free_var
        return w
    return inner
"""
    )
    assert reads == frozenset({"free_var"})
    assert writes == frozenset({"inner"})


def test_lambda_reads_propagate_params_dont():
    reads, writes = extract_reads_writes(
        "def cell():\n    f = lambda a: a + captured\n    return f\n"
    )
    assert reads == frozenset({"captured"})
    assert writes == frozenset({"f"})


def test_for_loop_and_with_targets_are_writes():
    reads, writes = extract_reads_writes(
        """
def cell():
    total = 0
    for item in items:
        total += item
    with open(path) as handle:
        data = handle.read()
    return total, data
"""
    )
    assert writes >= {"total", "item", "data", "handle"}
    assert reads == frozenset({"items", "path"})


def test_rejects_non_single_function_source():
    with pytest.raises(ValueError):
        extract_reads_writes("x = 1\ny = 2\n")


def test_build_graph_linear_dependency():
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    graph = build_graph(app.deck)
    assert graph.topological_order() == ["setup", "live_demo"]
    assert graph.affected_by("setup") == ["setup", "live_demo"]
    assert graph.affected_by("live_demo") == ["live_demo"]
    # "setup" is included alongside "base": a cell's own name is always an
    # implicit write of itself (kernel.py binds the compiled function into
    # the namespace under the cell's name, so other cells can call it
    # directly -- see test_kernel.py's cross-cell-call tests).
    assert app.deck.cells["setup"].writes == frozenset({"base", "setup"})
    assert app.deck.cells["live_demo"].reads == frozenset({"base"})


def test_build_graph_preserves_a_cells_layout():
    """Regression guard: `build_graph`'s own `parse_cell` reconstructs a
    new `Cell` (to populate reads/writes) rather than mutating the
    original in place -- a real bug was caught by hand where adding
    `Cell.layout` didn't also update this constructor call, so every
    `Kernel.reload_deck` (which always calls `build_graph`) silently
    dropped a cell's saved layout back to `None`, even though the .py
    file on disk still had it and a fresh `load_deck` alone (without
    going through `build_graph`) read it back correctly -- the loss only
    showed up one layer up, after the graph was built."""
    app = App()

    @app.cell(layout={"code_fraction": 0.6, "panel_fraction": 0.4, "lower_tabs": ["canvas"]})
    def setup():
        base = 5
        return base

    graph = build_graph(app.deck)
    assert graph is not None  # graph itself isn't the point here
    assert app.deck.cells["setup"].layout == {
        "code_fraction": 0.6,
        "panel_fraction": 0.4,
        "lower_tabs": ["canvas"],
    }


def test_build_graph_diamond_dependency():
    app = App()

    @app.cell
    def root():
        x = 1
        return x

    @app.cell
    def left():
        y = x * 2  # noqa: F821
        return y

    @app.cell
    def right():
        z = x * 3  # noqa: F821
        return z

    @app.cell
    def combine():
        total = y + z  # noqa: F821
        return total

    graph = build_graph(app.deck)
    order = graph.topological_order()
    assert order.index("root") < order.index("left")
    assert order.index("root") < order.index("right")
    assert order.index("left") < order.index("combine")
    assert order.index("right") < order.index("combine")
    assert set(graph.affected_by("root")) == {"root", "left", "right", "combine"}


def test_build_graph_detects_cycle():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="def a():\n    x = y\n    return x"))
    deck.add_cell(Cell(name="b", source="def b():\n    y = x\n    return y"))

    with pytest.raises(GraphCycleError):
        build_graph(deck)


def test_build_graph_detects_multiple_definitions():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="def a():\n    z = 1\n    return z"))
    deck.add_cell(Cell(name="b", source="def b():\n    z = 2\n    return z"))

    with pytest.raises(MultipleDefinitionError):
        build_graph(deck)


def test_independent_cells_have_no_edges():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="def a():\n    x = 1\n    return x"))
    deck.add_cell(Cell(name="b", source="def b():\n    y = 2\n    return y"))

    graph = build_graph(deck)
    assert graph.affected_by("a") == ["a"]
    assert graph.affected_by("b") == ["b"]
