
from codeslides import App, cs, ui
from codeslides.kernel import Kernel
from codeslides.session import Session


def _build_deck():
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    return app


def test_run_all_executes_in_dependency_order():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.namespace["base"] == 5
    assert session.namespace["result"] == 15
    assert session.instances["setup"].status == "idle"
    assert session.instances["live_demo"].status == "idle"


def test_element_value_change_triggers_minimal_rerun():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_element_changed("live_demo", "speed", 7, session)

    assert session.namespace["result"] == 35
    assert session.instances["live_demo"].elements["speed"].value == 7


def test_editing_upstream_cell_propagates_to_dependents():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_cell_edited("setup", "def setup():\n    base = 100\n    return base\n", session)

    assert session.namespace["base"] == 100
    assert session.namespace["result"] == 300  # base(100) * speed(default 3)


def test_exception_is_captured_without_crashing_kernel():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_cell_edited("setup", "def setup():\n    base = 1 / 0\n    return base\n", session)

    assert session.instances["setup"].status == "error"
    assert "ZeroDivisionError" in session.instances["setup"].error
    # the kernel itself must still be usable after a cell error
    kernel.on_cell_edited("setup", "def setup():\n    base = 9\n    return base\n", session)
    assert session.namespace["base"] == 9
    assert session.instances["setup"].status == "idle"


def test_viewer_elements_are_not_passed_as_kwargs():
    app = App()

    @app.cell(
        elements=[
            ui.turtle_canvas("canvas"),
            ui.notes("notes"),
        ]
    )
    def draw():
        picture = "a square"
        return picture

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["draw"].status == "idle", session.instances["draw"].error
    assert session.namespace["picture"] == "a square"


def test_multi_value_return_unpacks_by_name():
    app = App()

    @app.cell
    def pair():
        a = 1
        b = 2
        return a, b

    @app.cell
    def total():
        c = a + b  # noqa: F821
        return c

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.namespace["a"] == 1
    assert session.namespace["b"] == 2
    assert session.namespace["c"] == 3


def test_return_of_non_name_expression_is_rejected():
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(Cell(name="bad", source="def bad():\n    x = 1\n    return x + 1\n"))

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["bad"].status == "error"
    assert "must `return` a name or tuple of names" in session.instances["bad"].error


def test_clone_isolation_holds_under_real_execution():
    """Regression test for the marimo cloned-editor bug described in
    VISION.md: cloning a Session and editing one clone's cell source (or
    an element's value) must never affect the other clone, or the shared
    Deck/Kernel baseline."""
    app = _build_deck()
    kernel = Kernel(app.deck)

    session_a = Session(deck=app.deck)
    kernel.run_all(session_a)
    session_b = session_a.clone()

    kernel.on_element_changed("live_demo", "speed", 999, session_b)
    assert session_a.namespace["result"] == 15
    assert session_b.namespace["result"] == 4995

    kernel.on_cell_edited(
        "live_demo",
        "def live_demo(speed):\n    result = base + speed\n    return result\n",
        session_b,
    )
    assert session_b.namespace["result"] == 1004

    # session_a must still use the ORIGINAL multiply logic
    kernel.on_element_changed("live_demo", "speed", 10, session_a)
    assert session_a.namespace["result"] == 50

    # the shared Deck/Kernel baseline must be untouched by session_b's edit
    assert "live_demo" not in session_a.source_overrides
    assert "result = base * speed" in kernel.deck.cells["live_demo"].source


def _build_viewer_deck():
    app = App()

    @app.cell(elements=[ui.image("plot")])
    def make_plot():
        cs.image("plot", "/tmp/figure.png")
        x = 1
        return x

    return app


def test_cs_image_writes_element_content():
    app = _build_viewer_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    results = kernel.run_all(session)

    assert session.instances["make_plot"].status == "idle"
    assert session.instances["make_plot"].elements["plot"].content == "/tmp/figure.png"
    assert results["make_plot"].element_writes == [
        cs.ElementWrite(element_name="plot", kind="image", content="/tmp/figure.png")
    ]


def test_cs_write_to_unknown_element_is_a_cell_error():
    app = App()

    @app.cell(elements=[ui.image("plot")])
    def bad_target():
        cs.image("does_not_exist", "/tmp/figure.png")
        x = 1
        return x

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["bad_target"].status == "error"
    assert "does_not_exist" in session.instances["bad_target"].error
    # nothing partially applied on error
    assert session.instances["bad_target"].elements["plot"].content is None


def test_cs_write_is_not_applied_when_a_later_write_in_the_same_cell_fails():
    app = App()

    @app.cell(elements=[ui.image("a"), ui.image("b")])
    def two_targets():
        cs.image("a", "1.png")
        cs.image("does_not_exist", "2.png")
        x = 1
        return x

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["two_targets"].status == "error"
    # the earlier, valid write must not have been applied either --
    # all-or-nothing, matching namespace write semantics
    assert session.instances["two_targets"].elements["a"].content is None


def test_notes_element_content_seeded_from_default():
    app = App()

    @app.cell(elements=[ui.notes("n", default="# Title\nBody")])
    def cell_with_notes():
        x = 1
        return x

    session = Session(deck=app.deck)
    assert session.instances["cell_with_notes"].elements["n"].content == "# Title\nBody"


def test_element_writes_isolated_across_cloned_sessions():
    app = _build_viewer_deck()
    kernel = Kernel(app.deck)

    session_a = Session(deck=app.deck)
    kernel.run_all(session_a)
    session_b = session_a.clone()

    # mutate b's element content directly (simulating a later write) and
    # confirm a is untouched -- same isolation guarantee as namespace/value
    session_b.instances["make_plot"].elements["plot"].content = "/tmp/different.png"

    assert session_a.instances["make_plot"].elements["plot"].content == "/tmp/figure.png"
    assert session_b.instances["make_plot"].elements["plot"].content == "/tmp/different.png"


def test_reload_deck_affects_new_sessions():
    """CLI file-watcher reload (TODO.md #10): a new Session created after
    reload_deck() must run against the new deck's code, not the original."""
    app = _build_deck()
    kernel = Kernel(app.deck)

    new_app = App()

    @new_app.cell
    def setup():
        base = 100
        return base

    @new_app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    kernel.reload_deck(new_app.deck)

    session = Session(deck=new_app.deck)
    kernel.run_all(session)

    assert session.namespace["base"] == 100
    assert session.namespace["result"] == 300


def test_reload_deck_does_not_disturb_an_existing_sessions_namespace():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.namespace["result"] == 15

    new_app = App()

    @new_app.cell
    def setup():
        base = 999
        return base

    @new_app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    kernel.reload_deck(new_app.deck)

    # the existing session's namespace is untouched until it next runs
    assert session.namespace["result"] == 15

    # but running it again now picks up the reloaded baseline
    kernel.run_all(session)
    assert session.namespace["base"] == 999
    assert session.namespace["result"] == 2997


def test_on_cell_edited_with_a_syntax_error_reports_a_cell_error_not_a_crash():
    """An instructor live-typing code passes through invalid intermediate
    syntax constantly (e.g. an unclosed paren mid-edit) -- this must
    surface as this cell's own error, not raise out of on_cell_edited and
    take down the caller (the websocket handler has no try/except around
    this call; previously an uncaught SyntaxError here crashed the whole
    connection)."""
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    results = kernel.on_cell_edited("live_demo", "def live_demo(speed):\n    result = (\n", session)

    assert results["live_demo"].status == "error"
    assert session.source_overrides["live_demo"] == "def live_demo(speed):\n    result = (\n"
    # other cells/namespace are untouched
    assert session.namespace["base"] == 5


def test_on_element_changed_tolerates_an_unrelated_cells_broken_override():
    """A different cell in the same Session may currently have an invalid
    (mid-edit) source override sitting around -- changing some other
    element's value rebuilds the *whole* effective graph and must not
    crash just because of that unrelated broken cell."""
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_cell_edited("live_demo", "def live_demo(speed):\n    result = (\n", session)
    assert session.source_overrides["live_demo"] == "def live_demo(speed):\n    result = (\n"

    results = kernel.on_element_changed("live_demo", "speed", 7, session)

    assert results["live_demo"].status == "error"


def _build_cross_cell_call_deck():
    """`drawSquares` calls `drawSquare` directly, same as any two plain
    Python functions in one module -- the use case examples/live_demo1.py
    hit when a user wanted one cell to call another's function.

    `step` has a default so `drawSquare` can also still run standalone as
    its own cell (e.g. bound to a slider via `run_all`), same as the real
    example: a cell meant to be both directly runnable *and* callable from
    another cell needs its parameters to work either way -- called with an
    explicit argument, or falling back to its default when run alone.
    """
    app = App()

    @app.cell
    def drawSquare(step=1):
        result = step * 2
        return result

    @app.cell
    def drawSquares():
        results = [drawSquare(step) for step in (1, 2, 3)]
        return results

    return app


def test_a_cell_can_call_another_cells_function_directly():
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.namespace["results"] == [2, 4, 6]
    # the callee's own function object is bound into the namespace under
    # its cell name, exactly like any other cell's return-named values
    assert callable(session.namespace["drawSquare"])
    assert session.instances["drawSquare"].status == "idle"
    assert session.instances["drawSquares"].status == "idle"


def test_a_cells_own_name_is_a_graph_write_creating_a_real_dependency_edge():
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)

    assert kernel.graph.topological_order() == ["drawSquare", "drawSquares"]
    assert kernel.graph.affected_by("drawSquare") == ["drawSquare", "drawSquares"]
    assert app.deck.cells["drawSquare"].writes == frozenset({"drawSquare", "result"})
    assert "drawSquare" in app.deck.cells["drawSquares"].reads


def test_editing_the_called_cell_reruns_the_caller_too():
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.namespace["results"] == [2, 4, 6]

    results = kernel.on_cell_edited(
        "drawSquare",
        "def drawSquare(step=1):\n    result = step * 10\n    return result\n",
        session,
    )

    assert set(results) == {"drawSquare", "drawSquares"}
    assert session.namespace["results"] == [10, 20, 30]


def test_a_callee_cells_failed_run_does_not_update_its_bound_callable():
    """Same all-or-nothing guarantee that already applies to return-named
    values (a failed cell never partially updates the namespace) must also
    hold for the cell's own callable binding: if `drawSquare` fails to run
    standalone (e.g. an edit removes the default its own slider/run_all
    path needs), `session.namespace["drawSquare"]` must keep the last
    *successful* version rather than being cleared or left half-updated --
    otherwise a caller like `drawSquares` would see a stale-but-consistent
    function, or worse, no function at all."""
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    original_fn = session.namespace["drawSquare"]

    # remove the default -- drawSquare can no longer run standalone with
    # no bound `step`, so its own cell run fails
    results = kernel.on_cell_edited(
        "drawSquare", "def drawSquare(step):\n    result = step * 10\n    return result\n", session
    )

    assert results["drawSquare"].status == "error"
    # the stale-but-working callable is still there, untouched
    assert session.namespace["drawSquare"] is original_fn
    assert session.namespace["results"] == [2, 4, 6]
