from codeslides import App, cs, ui
from codeslides.kernel import Kernel
from codeslides.protocol import (
    CellOutput,
    CellStatus,
    CloneSession,
    EditCell,
    ElementOutput,
    ErrorMessage,
    NavigateSlide,
    RunAll,
    SessionCloned,
    SetElementValue,
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


def test_run_all_surfaces_notes_default_without_any_write():
    app = App()

    @app.cell(elements=[ui.notes("n", default="# Title\nBody")])
    def cell_with_notes():
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

    @app.cell(elements=[ui.notes("n", default="original")])
    def cell_with_notes():
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
