from codeslides import App, cs, turtle, ui
from codeslides.kernel import Kernel
from codeslides.loader import load_deck
from codeslides.protocol import (
    AddCell,
    AddElement,
    CellAdded,
    CellOutput,
    CellRenamed,
    CellStatus,
    CloneSession,
    DeckSaved,
    EditCell,
    ElementAdded,
    ElementConfigSet,
    ElementOutput,
    ElementRemoved,
    ElementsReordered,
    ErrorMessage,
    NavigateSlide,
    RemoveElement,
    RenameCell,
    ReorderElements,
    RunAll,
    SaveDeck,
    SessionCloned,
    SetElementConfig,
    SetElementValue,
    SetTestSource,
    SetUiState,
)
from codeslides.ws_handler import SessionRegistry, handle_message


def _build_deck():
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(
        instance="editable",
        elements=[
            ui.slider("speed", min=1, max=10, default=3),
            ui.turtle_canvas("canvas"),
        ],
    )
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    return app


def test_run_all_emits_status_and_output_per_cell():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()

    messages = handle_message(registry, RunAll(session_id=session.session_id))

    statuses = [m for m in messages if isinstance(m, CellStatus)]
    outputs = [m for m in messages if isinstance(m, CellOutput)]
    assert {m.cell_id for m in statuses} == {"setup", "live_demo"}
    assert {m.cell_id for m in outputs} == {"setup", "live_demo"}
    assert all(m.status == "idle" for m in statuses)


def test_run_all_emits_no_element_output_for_a_viewer_element_never_written_to():
    # `canvas` is a turtle_canvas the cell never calls cs.* for (turtle
    # support is TODO.md #15) -- targeted writes mean no broadcast happens.
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()

    messages = handle_message(registry, RunAll(session_id=session.session_id))

    assert [m for m in messages if isinstance(m, ElementOutput)] == []


def test_run_all_emits_element_output_for_cs_image_write():
    app = App()

    @app.cell(elements=[ui.image("plot")])
    def make_plot():
        cs.image("plot", "/tmp/figure.png")
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()

    messages = handle_message(registry, RunAll(session_id=session.session_id))

    element_outputs = [m for m in messages if isinstance(m, ElementOutput)]
    assert len(element_outputs) == 1
    assert element_outputs[0].cell_id == "make_plot"
    assert element_outputs[0].element_id == "plot"
    assert element_outputs[0].content == "/tmp/figure.png"


def test_run_all_surfaces_notes_docstring_without_any_write():
    app = App()

    @app.cell(elements=[ui.notes("n")])
    def cell_with_notes():
        """# Title\nBody"""
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()

    messages = handle_message(registry, RunAll(session_id=session.session_id))

    element_outputs = [m for m in messages if isinstance(m, ElementOutput)]
    assert len(element_outputs) == 1
    assert element_outputs[0].element_id == "n"
    assert element_outputs[0].content == "# Title\nBody"


def test_set_ui_state_notes_source_updates_content_without_rerun():
    app = App()

    @app.cell(elements=[ui.notes("n")])
    def cell_with_notes():
        """original"""
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))
    namespace_before = dict(session.namespace)

    messages = handle_message(
        registry,
        SetUiState(session_id=session.session_id, cell_id="cell_with_notes", element_id="n", notes_source="edited"),
    )

    assert messages == []
    assert session.instances["cell_with_notes"].elements["n"].content == "edited"
    assert session.namespace == namespace_before


def test_set_test_source_runs_the_test_and_emits_element_output():
    app = App()

    @app.cell(elements=[ui.tests("unit", default="assert x == 1")])
    def cell_with_tests():
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))
    assert session.instances["cell_with_tests"].elements["unit"].content == {
        "status": "pass",
        "message": "",
    }

    messages = handle_message(
        registry,
        SetTestSource(
            session_id=session.session_id,
            cell_id="cell_with_tests",
            element_id="unit",
            source="assert x == 999, 'nope'",
        ),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ElementOutput)
    assert messages[0].content == {"status": "fail", "message": "nope"}
    assert session.instances["cell_with_tests"].elements["unit"].content == {
        "status": "fail",
        "message": "nope",
    }
    assert session.instances["cell_with_tests"].elements["unit"].value == "assert x == 999, 'nope'"


def test_set_test_source_does_not_rerun_the_cell():
    app = App()

    @app.cell(elements=[ui.tests("unit", default="assert x == 1")])
    def cell_with_tests():
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))
    namespace_before = dict(session.namespace)

    handle_message(
        registry,
        SetTestSource(
            session_id=session.session_id,
            cell_id="cell_with_tests",
            element_id="unit",
            source="assert x == 1",
        ),
    )

    assert session.namespace == namespace_before


def test_set_test_source_unknown_element_produces_error_not_crash():
    app = App()

    @app.cell
    def plain():
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()

    messages = handle_message(
        registry,
        SetTestSource(
            session_id=session.session_id, cell_id="plain", element_id="does-not-exist", source="assert True"
        ),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_run_all_surfaces_a_fresh_cells_test_result_without_any_edit():
    """A tests element's result must reach the browser on the very first
    run_all too, not just after a later edit -- same fallback shape as
    notes' authored-default surfacing."""
    app = App()

    @app.cell(elements=[ui.tests("unit", default="assert x == 1")])
    def cell_with_tests():
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()

    messages = handle_message(registry, RunAll(session_id=session.session_id))

    element_outputs = [m for m in messages if isinstance(m, ElementOutput) and m.element_id == "unit"]
    assert len(element_outputs) == 1


def _build_turtle_and_tests_deck(test_source: str = "turtle.forward(1)"):
    app = App()

    @app.cell(
        elements=[
            ui.turtle_canvas("canvas", width=400, height=400),
            ui.tests("unit", default=test_source),
        ],
    )
    def draw_something():
        turtle.forward(200)
        turtle.right(90)
        turtle.forward(200)

    return app


def test_run_all_emits_exactly_one_canvas_message_reflecting_the_tests_drawing():
    """The cell's own body draws 3 turtle commands; its tests element
    draws 1. The canvas message the browser receives must reflect the
    test's 1 command (the final state), and there must be exactly one
    such message -- not the cell's stale write followed by a second,
    duplicate-looking one for the test."""
    registry = SessionRegistry(kernel=Kernel(_build_turtle_and_tests_deck("turtle.forward(1)").deck))
    session = registry.create()

    messages = handle_message(registry, RunAll(session_id=session.session_id))

    canvas_messages = [m for m in messages if isinstance(m, ElementOutput) and m.element_id == "canvas"]
    assert len(canvas_messages) == 1
    assert len(canvas_messages[0].content) == 1


def test_set_test_source_with_turtle_calls_updates_the_canvas():
    registry = SessionRegistry(kernel=Kernel(_build_turtle_and_tests_deck("turtle.forward(1)").deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))

    messages = handle_message(
        registry,
        SetTestSource(
            session_id=session.session_id,
            cell_id="draw_something",
            element_id="unit",
            source="turtle.forward(1)\nturtle.forward(1)\nturtle.forward(1)",
        ),
    )

    unit_messages = [m for m in messages if isinstance(m, ElementOutput) and m.element_id == "unit"]
    canvas_messages = [m for m in messages if isinstance(m, ElementOutput) and m.element_id == "canvas"]
    assert len(unit_messages) == 1
    assert unit_messages[0].content == {"status": "pass", "message": ""}
    assert len(canvas_messages) == 1
    assert len(canvas_messages[0].content) == 3


def test_set_test_source_without_turtle_calls_does_not_emit_a_canvas_message():
    """A test that never touches turtle shouldn't force a canvas resend --
    only relevant when the cell actually has a turtle_canvas element and
    the test could plausibly have drawn into it."""
    app = App()

    @app.cell(elements=[ui.tests("unit", default="assert True")])
    def plain_cell():
        x = 1
        return x

    registry = SessionRegistry(kernel=Kernel(app.deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))

    messages = handle_message(
        registry,
        SetTestSource(session_id=session.session_id, cell_id="plain_cell", element_id="unit", source="assert True"),
    )

    canvas_messages = [m for m in messages if isinstance(m, ElementOutput) and m.element_id != "unit"]
    assert canvas_messages == []


def test_set_element_value_triggers_minimal_rerun():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))

    messages = handle_message(
        registry,
        SetElementValue(session_id=session.session_id, cell_id="live_demo", element_id="speed", value=7),
    )

    outputs = [m for m in messages if isinstance(m, CellOutput)]
    assert {m.cell_id for m in outputs} == {"live_demo"}
    assert session.namespace["result"] == 35


def test_set_ui_state_is_a_pure_noop():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))
    namespace_before = dict(session.namespace)

    messages = handle_message(
        registry, SetUiState(session_id=session.session_id, cell_id="live_demo", collapsed=True)
    )

    assert messages == []
    assert session.instances["live_demo"].collapsed is True
    assert session.namespace == namespace_before


def test_set_ui_state_minimizes_an_element():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))

    messages = handle_message(
        registry,
        SetUiState(session_id=session.session_id, cell_id="live_demo", element_id="speed", minimized=True),
    )

    assert messages == []
    assert session.instances["live_demo"].elements["speed"].minimized is True


def test_clone_session_creates_isolated_copy():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()
    handle_message(registry, RunAll(session_id=session.session_id))

    messages = handle_message(registry, CloneSession(source_session_id=session.session_id))
    assert len(messages) == 1
    assert isinstance(messages[0], SessionCloned)
    new_id = messages[0].new_session_id

    handle_message(
        registry,
        SetElementValue(session_id=new_id, cell_id="live_demo", element_id="speed", value=999),
    )

    original = registry.get(session.session_id)
    clone = registry.get(new_id)
    assert original.namespace["result"] == 15
    assert clone.namespace["result"] == 4995


def test_unknown_session_produces_error_not_crash():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))

    messages = handle_message(registry, RunAll(session_id="does-not-exist"))

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)
    assert messages[0].session_id == "does-not-exist"


def test_unknown_cell_produces_error_not_crash():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()

    messages = handle_message(
        registry, EditCell(session_id=session.session_id, cell_id="does-not-exist", source="x = 1")
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_unknown_element_produces_error_not_crash():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()

    messages = handle_message(
        registry,
        SetElementValue(
            session_id=session.session_id, cell_id="live_demo", element_id="does-not-exist", value=1
        ),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_navigate_slide_is_a_noop_for_known_session():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))
    session = registry.create()

    messages = handle_message(
        registry, NavigateSlide(session_id=session.session_id, slide_id="slide_1")
    )

    assert messages == []


_DECK_FILE_SOURCE = (
    "from codeslides import App, ui\n\n"
    "app = App()\n\n"
    "@app.cell\n"
    "def setup():\n"
    "    base = 5\n"
    "    return base\n\n"
    '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
    "def live_demo(speed):\n"
    "    result = base * speed  # noqa: F821\n"
    "    return result\n"
)


def _build_file_backed_registry(tmp_path):
    """A SaveDeck test needs a real deck_path on disk (unlike the rest of
    this file's in-memory `_build_deck()`), since saving writes to it."""
    path = tmp_path / "deck.py"
    path.write_text(_DECK_FILE_SOURCE)
    deck = load_deck(str(path))
    registry = SessionRegistry(kernel=Kernel(deck, deck_path=str(path)))
    return registry, path


def test_save_deck_writes_the_override_and_clears_it(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    # The browser's editor only ever shows/edits the decorator-free shape
    # (display_source) -- on_cell_edited reattaches live_demo's existing
    # decorator before recording the override.
    edited_body = (
        "def live_demo(speed):\n"
        "    result = base * speed * 10  # noqa: F821\n"
        "    return result\n"
    )
    handle_message(registry, EditCell(session_id=session.session_id, cell_id="live_demo", source=edited_body))
    new_source = (
        '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
        + edited_body
    )
    assert session.source_overrides["live_demo"] == new_source

    messages = handle_message(registry, SaveDeck(session_id=session.session_id))

    assert messages == [DeckSaved(session_id=session.session_id, cells=["live_demo"])]
    assert "base * speed * 10" in path.read_text()
    # the override is now redundant with the on-disk baseline -- cleared
    assert session.source_overrides == {}
    # and the Kernel's own baseline picked up the change synchronously,
    # not waiting on the CLI file-watcher's async debounce
    assert "base * speed * 10" in registry.kernel.deck.cells["live_demo"].source


def test_save_deck_with_no_overrides_is_a_noop(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    before = path.read_text()

    messages = handle_message(registry, SaveDeck(session_id=session.session_id))

    assert messages == [DeckSaved(session_id=session.session_id, cells=[])]
    assert path.read_text() == before


def test_save_deck_without_a_deck_path_errors_cleanly():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))  # no deck_path
    session = registry.create()
    handle_message(
        registry,
        EditCell(
            session_id=session.session_id,
            cell_id="live_demo",
            source="def live_demo(speed):\n    result = speed\n    return result\n",
        ),
    )

    messages = handle_message(registry, SaveDeck(session_id=session.session_id))

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_save_deck_with_an_unparseable_override_errors_without_writing(tmp_path):
    """A syntax error left over from live-typing must never reach disk --
    save_deck must report it as an ErrorMessage, not crash the connection
    (this reproduces a real bug found via manual browser testing: an
    in-flight edit_cell with invalid syntax was correctly handled as a
    per-cell error, but a subsequent save_deck still tried to write --
    and then reload -- that same broken text)."""
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    before = path.read_text()

    handle_message(
        registry,
        EditCell(
            session_id=session.session_id,
            cell_id="live_demo",
            source="def live_demo(speed):\n    result = (\n",
        ),
    )
    # decorator-free `source` in (matches the browser's display shape) --
    # on_cell_edited reattaches live_demo's existing decorator before
    # recording the override.
    expected_override = (
        '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
        "def live_demo(speed):\n    result = (\n"
    )
    assert session.source_overrides["live_demo"] == expected_override

    messages = handle_message(registry, SaveDeck(session_id=session.session_id))

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)
    # nothing was written, and the override is still there for the
    # instructor to keep fixing
    assert path.read_text() == before
    assert session.source_overrides["live_demo"] == expected_override


def test_save_deck_unknown_session_produces_error_not_crash(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)

    messages = handle_message(registry, SaveDeck(session_id="does-not-exist"))

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_save_deck_only_affects_the_saving_sessions_overrides(tmp_path):
    """Another Session's independent edit to the same cell must survive a
    different Session's save untouched (ARCHITECTURE.md section 1
    isolation guarantee -- saving must not leak across Sessions)."""
    registry, path = _build_file_backed_registry(tmp_path)
    session_a = registry.create()
    session_b = registry.create()

    # decorator-free `source` (matches the browser's display shape) --
    # on_cell_edited reattaches live_demo's existing decorator.
    decorator = '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
    body_a = "def live_demo(speed):\n    result = base * speed * 100  # noqa: F821\n    return result\n"
    body_b = "def live_demo(speed):\n    result = base * speed * 200  # noqa: F821\n    return result\n"
    handle_message(registry, EditCell(session_id=session_a.session_id, cell_id="live_demo", source=body_a))
    handle_message(registry, EditCell(session_id=session_b.session_id, cell_id="live_demo", source=body_b))

    handle_message(registry, SaveDeck(session_id=session_a.session_id))

    assert "base * speed * 100" in path.read_text()
    assert session_a.source_overrides == {}
    # session_b's own override is untouched by session_a's save
    assert session_b.source_overrides["live_demo"] == decorator + body_b


def test_add_cell_emits_cell_added_and_writes_to_disk(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()

    messages = handle_message(registry, AddCell(session_id=session.session_id))

    assert isinstance(messages[0], CellAdded)
    added = messages[0]
    assert added.session_id == session.session_id
    assert added.instance == "editable"
    assert "def cell_1():" in added.source
    # the @app.cell decorator is stripped before it reaches the browser
    # (display_source), same as /api/deck -- the on-disk file still has it.
    assert "@app.cell" not in added.source
    assert added.elements == []
    # written to disk immediately -- no separate save_deck needed
    assert "def cell_1():" in path.read_text()
    assert "@app.cell" in path.read_text()
    # and the Kernel's own baseline picked it up synchronously
    assert added.cell_id in registry.kernel.deck.cells
    # the requesting session's own instances were backfilled so a
    # subsequent run_all/edit_cell for this cell won't KeyError
    assert added.cell_id in session.instances


def test_add_cell_without_a_deck_path_errors_cleanly():
    registry = SessionRegistry(kernel=Kernel(_build_deck().deck))  # no deck_path
    session = registry.create()

    messages = handle_message(registry, AddCell(session_id=session.session_id))

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_add_cell_unknown_session_produces_error_not_crash(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)

    messages = handle_message(registry, AddCell(session_id="does-not-exist"))

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_add_cell_twice_picks_different_names(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)
    session = registry.create()

    first = handle_message(registry, AddCell(session_id=session.session_id))[0]
    second = handle_message(registry, AddCell(session_id=session.session_id))[0]

    assert first.cell_id != second.cell_id


def test_add_cell_does_not_affect_a_different_sessions_instances(tmp_path):
    """A new cell must be scoped like the CLI file-watcher's reload
    (ARCHITECTURE.md, TODO.md #13): guaranteed correct for the requesting
    session and any new connection after this, but not broadcast live into
    other already-open sessions."""
    registry, _ = _build_file_backed_registry(tmp_path)
    session_a = registry.create()
    session_b = registry.create()

    added = handle_message(registry, AddCell(session_id=session_a.session_id))[0]

    assert added.cell_id in session_a.instances
    assert added.cell_id not in session_b.instances


def test_rename_cell_emits_cell_renamed_and_writes_to_disk(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()

    messages = handle_message(
        registry, RenameCell(session_id=session.session_id, cell_id="live_demo", new_name="coding_demo")
    )

    assert isinstance(messages[0], CellRenamed)
    renamed = messages[0]
    assert renamed.old_cell_id == "live_demo"
    assert renamed.cell_id == "coding_demo"
    assert "def coding_demo(speed):" in path.read_text()
    assert "coding_demo" in registry.kernel.deck.cells
    assert "coding_demo" in session.instances
    assert "live_demo" not in session.instances


def test_rename_cell_unknown_session_produces_error_not_crash(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)

    messages = handle_message(
        registry, RenameCell(session_id="does-not-exist", cell_id="live_demo", new_name="coding_demo")
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_rename_cell_blocked_when_referenced_produces_error_not_crash(tmp_path):
    path = tmp_path / "deck.py"
    path.write_text(
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell\ndef drawSquare():\n    x = 1\n    return x\n\n"
        "@app.cell\ndef drawSquares():\n    result = drawSquare() + 1\n    return result\n"
    )
    deck = load_deck(str(path))
    registry = SessionRegistry(kernel=Kernel(deck, deck_path=str(path)))
    session = registry.create()

    messages = handle_message(
        registry, RenameCell(session_id=session.session_id, cell_id="drawSquare", new_name="draw_one_square")
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)
    assert "def drawSquare()" in path.read_text()


def test_add_element_emits_element_added_and_writes_to_disk(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()

    messages = handle_message(
        registry,
        AddElement(
            session_id=session.session_id,
            cell_id="setup",
            element_name="multiplier",
            kind="slider",
            config={"min": 1, "max": 5, "default": 2},
        ),
    )

    assert isinstance(messages[0], ElementAdded)
    added = messages[0]
    assert added.cell_id == "setup"
    assert [e["name"] for e in added.elements] == ["multiplier"]
    assert "ui.slider('multiplier'" in path.read_text()
    assert "multiplier" in session.instances["setup"].elements


def test_add_element_unknown_session_produces_error_not_crash(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)

    messages = handle_message(
        registry,
        AddElement(
            session_id="does-not-exist", cell_id="setup", element_name="multiplier", kind="slider", config={"min": 1, "max": 5}
        ),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_add_element_duplicate_name_produces_error_not_crash(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    before = path.read_text()

    messages = handle_message(
        registry,
        AddElement(
            session_id=session.session_id, cell_id="live_demo", element_name="speed", kind="button", config={}
        ),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)
    assert path.read_text() == before


def test_remove_element_emits_element_removed_and_writes_to_disk(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()

    messages = handle_message(
        registry, RemoveElement(session_id=session.session_id, cell_id="live_demo", element_name="speed")
    )

    assert isinstance(messages[0], ElementRemoved)
    removed = messages[0]
    assert removed.cell_id == "live_demo"
    assert removed.elements == []
    assert "ui.slider" not in path.read_text()
    assert "speed" not in session.instances["live_demo"].elements


def test_remove_element_unknown_session_produces_error_not_crash(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)

    messages = handle_message(
        registry, RemoveElement(session_id="does-not-exist", cell_id="live_demo", element_name="speed")
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_remove_element_unknown_element_produces_error_not_crash(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    before = path.read_text()

    messages = handle_message(
        registry, RemoveElement(session_id=session.session_id, cell_id="live_demo", element_name="does_not_exist")
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)
    assert path.read_text() == before


def test_reorder_elements_emits_elements_reordered_and_writes_to_disk(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    handle_message(
        registry,
        AddElement(session_id=session.session_id, cell_id="live_demo", element_name="go", kind="button", config={}),
    )

    messages = handle_message(
        registry,
        ReorderElements(session_id=session.session_id, cell_id="live_demo", element_order=["go", "speed"]),
    )

    assert isinstance(messages[0], ElementsReordered)
    reordered = messages[0]
    assert [e["name"] for e in reordered.elements] == ["go", "speed"]
    text = path.read_text()
    assert text.index("ui.button('go'") < text.index("ui.slider('speed'")


def test_reorder_elements_unknown_session_produces_error_not_crash(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)

    messages = handle_message(
        registry, ReorderElements(session_id="does-not-exist", cell_id="live_demo", element_order=["speed"])
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_reorder_elements_non_permutation_produces_error_not_crash(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    before = path.read_text()

    messages = handle_message(
        registry,
        ReorderElements(session_id=session.session_id, cell_id="live_demo", element_order=["does_not_exist"]),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)
    assert path.read_text() == before


def test_set_element_config_emits_element_config_set_and_writes_to_disk(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    handle_message(
        registry,
        AddElement(
            session_id=session.session_id,
            cell_id="live_demo",
            element_name="preview",
            kind="iframe",
            config={"src": "https://old.example.com"},
        ),
    )

    messages = handle_message(
        registry,
        SetElementConfig(
            session_id=session.session_id,
            cell_id="live_demo",
            element_id="preview",
            config={"src": "https://new.example.com"},
        ),
    )

    kinds = [type(m) for m in messages]
    assert ElementConfigSet in kinds
    assert ElementOutput in kinds
    config_set = next(m for m in messages if isinstance(m, ElementConfigSet))
    preview = next(e for e in config_set.elements if e["name"] == "preview")
    # Reloading re-executes the on-disk `ui.iframe(...)` call through the
    # real constructor, which re-applies its own `height=240` default for
    # the kwarg this SetElementConfig payload omitted -- see
    # test_serialization.py's own version of this assertion.
    assert preview["config"] == {"src": "https://new.example.com", "height": 240}
    output = next(m for m in messages if isinstance(m, ElementOutput))
    assert output.element_id == "preview"
    assert output.content == "https://new.example.com"
    assert "https://new.example.com" in path.read_text()


def test_set_element_config_on_a_non_iframe_emits_no_element_output(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)
    session = registry.create()

    messages = handle_message(
        registry,
        SetElementConfig(
            session_id=session.session_id,
            cell_id="live_demo",
            element_id="speed",
            config={"min": 1, "max": 20, "default": 3},
        ),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ElementConfigSet)


def test_set_element_config_unknown_session_produces_error_not_crash(tmp_path):
    registry, _ = _build_file_backed_registry(tmp_path)

    messages = handle_message(
        registry,
        SetElementConfig(session_id="does-not-exist", cell_id="live_demo", element_id="speed", config={}),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)


def test_set_element_config_unknown_element_produces_error_not_crash(tmp_path):
    registry, path = _build_file_backed_registry(tmp_path)
    session = registry.create()
    before = path.read_text()

    messages = handle_message(
        registry,
        SetElementConfig(
            session_id=session.session_id, cell_id="live_demo", element_id="does_not_exist", config={}
        ),
    )

    assert len(messages) == 1
    assert isinstance(messages[0], ErrorMessage)
    assert path.read_text() == before
