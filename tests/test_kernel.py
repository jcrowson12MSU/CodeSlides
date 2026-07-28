import pytest

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


def _write_deck_file(tmp_path, source):
    path = tmp_path / "deck.py"
    path.write_text(source)
    return path


_ADD_CELL_DECK_SOURCE = (
    "from codeslides import App\n\napp = App()\n\n@app.cell\ndef setup():\n    base = 5\n    return base\n"
)


def test_add_cell_appends_a_blank_editable_cell_to_disk(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, result = kernel.add_cell(session)

    assert cell.name == "cell_1"
    assert cell.instance == "editable"
    assert result.status == "idle"
    assert "def cell_1():" in path.read_text()
    # the Kernel's own baseline picked up the new cell too, not just the file
    assert "cell_1" in kernel.deck.cells


def test_add_cell_backfills_the_requesting_sessions_instances(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, _ = kernel.add_cell(session)

    # without backfilling, the very next run_all would KeyError on
    # session.instances["cell_1"] -- confirm it doesn't
    assert cell.name in session.instances
    kernel.run_all(session)  # must not raise


def test_add_cell_twice_picks_different_names(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell1, _ = kernel.add_cell(session)
    cell2, _ = kernel.add_cell(session)

    assert cell1.name != cell2.name
    assert {cell1.name, cell2.name} == {"cell_1", "cell_2"}


def test_add_cell_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.add_cell(session)


def test_add_cell_does_not_affect_a_different_sessions_instances(tmp_path):
    """Confirms the agreed scope: adding a cell only guarantees correctness
    for the requesting Session (and any new connection after this) -- an
    unrelated, already-open Session is untouched, matching reload_deck's
    existing, deliberately narrow scope."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session_a = Session(deck=deck)
    session_b = Session(deck=deck)
    kernel.run_all(session_a)
    kernel.run_all(session_b)

    cell, _ = kernel.add_cell(session_a)

    assert cell.name in session_a.instances
    assert cell.name not in session_b.instances


_RENAME_DECK_SOURCE = (
    "from codeslides import App, ui\n\n"
    "app = App()\n\n"
    '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
    "def live_demo(speed):\n"
    "    result = speed * 2\n"
    "    return result\n\n"
    '@app.slide("Live Coding", cells=["live_demo"])\n'
    "def slide_1():\n"
    '    """Notes."""\n'
)


def test_rename_cell_updates_the_kernel_baseline_and_disk(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell = kernel.rename_cell(session, "live_demo", "coding_demo")

    assert cell.name == "coding_demo"
    assert "coding_demo" in kernel.deck.cells
    assert "live_demo" not in kernel.deck.cells
    assert "def coding_demo(speed):" in path.read_text()
    assert kernel.deck.slides[0].cell_names == ["coding_demo"]


def test_rename_cell_remaps_the_requesting_sessions_state(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.rename_cell(session, "live_demo", "coding_demo")

    assert "coding_demo" in session.instances
    assert "live_demo" not in session.instances
    # the next run_all must not KeyError on the renamed cell
    kernel.run_all(session)


def test_rename_cell_does_not_affect_a_different_sessions_instances(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session_a = Session(deck=deck)
    session_b = Session(deck=deck)
    kernel.run_all(session_a)
    kernel.run_all(session_b)

    kernel.rename_cell(session_a, "live_demo", "coding_demo")

    assert "coding_demo" in session_a.instances
    assert "live_demo" in session_b.instances
    assert "coding_demo" not in session_b.instances


def test_rename_cell_blocked_when_another_cell_calls_it_directly(tmp_path):
    from codeslides.loader import load_deck

    source = (
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell\ndef drawSquare():\n    x = 1\n    return x\n\n"
        "@app.cell\ndef drawSquares():\n    result = drawSquare() + 1\n    return result\n"
    )
    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="drawSquares"):
        kernel.rename_cell(session, "drawSquare", "draw_one_square")

    # nothing was written -- the on-disk name is untouched
    assert "def drawSquare()" in path.read_text()


def test_rename_cell_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.rename_cell(session, "live_demo", "coding_demo")


def test_add_element_updates_disk_kernel_and_session(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, result = kernel.add_element(session, "setup", ui.slider("multiplier", min=1, max=5, default=2))

    assert [e.name for e in cell.elements] == ["multiplier"]
    assert result.status == "idle"
    assert "multiplier" in kernel.deck.cells["setup"].elements[0].name
    assert "multiplier" in session.instances["setup"].elements
    assert "ui.slider('multiplier'" in path.read_text()


def test_add_element_raises_on_a_duplicate_element_name(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="speed"):
        kernel.add_element(session, "live_demo", ui.button("speed"))


def test_remove_element_updates_disk_kernel_and_session(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, result = kernel.remove_element(session, "live_demo", "speed")

    assert cell.elements == []
    assert result.status == "error"  # live_demo's body still reads `speed`, now unbound
    assert "speed" not in session.instances["live_demo"].elements
    assert "ui.slider" not in path.read_text()


def test_remove_element_raises_if_the_element_does_not_exist(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="does_not_exist"):
        kernel.remove_element(session, "live_demo", "does_not_exist")


def test_reorder_elements_updates_disk_and_kernel_baseline(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.button("go"))

    cell = kernel.reorder_elements(session, "live_demo", ["go", "speed"])

    assert [e.name for e in cell.elements] == ["go", "speed"]
    assert [e.name for e in kernel.deck.cells["live_demo"].elements] == ["go", "speed"]


def test_reorder_elements_does_not_rerun_the_cell(tmp_path):
    """A pure reorder never changes execution -- confirm the cell's own
    status/output are left exactly as they were, since nothing was
    re-run."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.button("go"))
    status_before = session.instances["live_demo"].status
    output_before = session.instances["live_demo"].output

    kernel.reorder_elements(session, "live_demo", ["go", "speed"])

    assert session.instances["live_demo"].status == status_before
    assert session.instances["live_demo"].output == output_before


def test_reorder_elements_raises_on_a_non_permutation(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="permutation"):
        kernel.reorder_elements(session, "live_demo", ["speed", "does_not_exist"])


def test_reorder_elements_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.reorder_elements(session, "live_demo", ["speed"])


def test_set_element_config_updates_disk_and_kernel_baseline(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.iframe("preview", src="https://old.example.com"))

    cell = kernel.set_element_config(session, "live_demo", "preview", {"src": "https://new.example.com"})

    preview = next(e for e in cell.elements if e.name == "preview")
    assert preview.config == {"src": "https://new.example.com"}
    assert kernel.deck.cells["live_demo"].elements[-1].config == {"src": "https://new.example.com"}


def test_set_element_config_pushes_an_iframes_new_src_into_the_sessions_content(tmp_path):
    """An iframe's rendered content otherwise only ever changes via the
    owning cell's own cs.iframe() call during a run -- confirm editing
    the config here also updates the *live* content directly, since
    otherwise the browser would never see the new URL until the cell
    happened to re-run."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.iframe("preview", src="https://old.example.com"))
    assert session.instances["live_demo"].elements["preview"].content is None

    kernel.set_element_config(session, "live_demo", "preview", {"src": "https://new.example.com"})

    assert session.instances["live_demo"].elements["preview"].content == "https://new.example.com"


def test_set_element_config_does_not_touch_a_non_iframe_elements_content(tmp_path):
    """The content-push is deliberately iframe-only -- a slider's config
    change (e.g. min/max) has no analogous "content" to push, and must
    not clobber whatever `value` it's currently holding."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    session.instances["live_demo"].elements["speed"].value = 7

    kernel.set_element_config(session, "live_demo", "speed", {"min": 1, "max": 20, "default": 3})

    assert session.instances["live_demo"].elements["speed"].value == 7


def test_set_element_config_raises_if_the_element_does_not_exist(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="does_not_exist"):
        kernel.set_element_config(session, "live_demo", "does_not_exist", {})
