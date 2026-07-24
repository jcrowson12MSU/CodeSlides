
from codeslides import App, ui
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
