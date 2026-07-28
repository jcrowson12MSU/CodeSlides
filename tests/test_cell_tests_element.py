"""Tests for the `ui.tests(...)` element (ARCHITECTURE.md section 3b):
a second, unittest-like code editor attached to a cell, auto-run against
the cell's own effective namespace every time the cell re-runs."""

from codeslides import App, turtle, ui
from codeslides.kernel import Kernel, run_tests
from codeslides.session import Session


def _build_deck(test_source: str = "assert result == 15"):
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(
        instance="editable",
        elements=[
            ui.slider("speed", min=1, max=10, default=3),
            ui.tests("unit", default=test_source),
        ],
    )
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    return app


def test_run_tests_pass():
    assert run_tests("assert 1 + 1 == 2", {}) == {"status": "pass", "message": ""}


def test_run_tests_fail_with_assertion_message():
    result = run_tests("assert 1 == 2, 'nope'", {})
    assert result == {"status": "fail", "message": "nope"}


def test_run_tests_fail_with_no_assertion_message():
    result = run_tests("assert 1 == 2", {})
    assert result["status"] == "fail"
    assert result["message"]  # falls back to a non-empty placeholder


def test_run_tests_error_for_anything_other_than_assertionerror():
    result = run_tests("undefined_name", {})
    assert result["status"] == "error"
    assert "NameError" in result["message"]


def test_run_tests_sees_the_passed_namespace():
    result = run_tests("assert base == 5", {"base": 5})
    assert result["status"] == "pass"


def test_run_tests_cannot_mutate_the_caller_s_namespace():
    namespace = {"base": 5}
    run_tests("base = 999", namespace)
    assert namespace["base"] == 5


def test_run_tests_empty_source_passes_trivially():
    assert run_tests("", {}) == {"status": "pass", "message": ""}
    assert run_tests("   \n  ", {}) == {"status": "pass", "message": ""}


def test_tests_element_auto_runs_after_run_all_and_passes():
    app = _build_deck("assert result == 15")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["live_demo"].elements["unit"].content == {"status": "pass", "message": ""}


def test_tests_element_auto_runs_and_fails():
    app = _build_deck("assert result == 999, 'wrong'")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["live_demo"].elements["unit"].content == {
        "status": "fail",
        "message": "wrong",
    }


def test_tests_element_reruns_automatically_when_an_upstream_slider_changes():
    app = _build_deck("assert result == 35")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.instances["live_demo"].elements["unit"].content["status"] == "fail"

    kernel.on_element_changed("live_demo", "speed", 7, session)

    assert session.namespace["result"] == 35
    assert session.instances["live_demo"].elements["unit"].content == {"status": "pass", "message": ""}


def test_tests_element_does_not_run_when_the_cell_itself_errors():
    app = _build_deck("assert result == 15")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.instances["live_demo"].elements["unit"].content["status"] == "pass"

    # break the cell itself -- speed is no longer a valid parameter name
    kernel.on_cell_edited(
        "live_demo",
        "def live_demo(nope):\n    result = base * nope\n    return result\n",
        session,
    )

    # the cell errors (no `nope` element is bound), and the test result
    # reflects that no valid run happened -- not a stale "pass" left over
    # from before the edit
    assert session.instances["live_demo"].status == "error"
    assert session.instances["live_demo"].elements["unit"].content["status"] == "error"


def test_on_tests_edited_reruns_the_test_without_rerunning_the_cell():
    app = _build_deck("assert result == 999")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.instances["live_demo"].elements["unit"].content["status"] == "fail"
    namespace_before = dict(session.namespace)

    result = kernel.on_tests_edited("live_demo", "unit", "assert result == 15", session)

    assert result == {"status": "pass", "message": ""}
    assert session.instances["live_demo"].elements["unit"].content == {"status": "pass", "message": ""}
    assert session.instances["live_demo"].elements["unit"].value == "assert result == 15"
    # the cell itself never re-ran -- namespace is untouched
    assert session.namespace == namespace_before


def test_tests_element_value_is_seeded_from_default():
    app = _build_deck("assert result == 15")
    session = Session(deck=app.deck)
    assert session.instances["live_demo"].elements["unit"].value == "assert result == 15"
    # no run has happened yet -- no result to show
    assert session.instances["live_demo"].elements["unit"].content is None


def test_tests_element_isolated_across_cloned_sessions():
    app = _build_deck("assert result == 15")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    clone = session.clone()
    kernel.on_tests_edited("live_demo", "unit", "assert result == 999", clone)

    # the clone's edit never touches the source session's test state
    assert session.instances["live_demo"].elements["unit"].value == "assert result == 15"
    assert session.instances["live_demo"].elements["unit"].content == {"status": "pass", "message": ""}
    assert clone.instances["live_demo"].elements["unit"].value == "assert result == 999"
    assert clone.instances["live_demo"].elements["unit"].content["status"] == "fail"


def _build_turtle_deck(cell_source_draws: bool, test_source: str):
    """A cell with a turtle_canvas + tests element. `cell_source_draws`
    controls whether the cell's own body has turtle calls (to
    distinguish "the test's drawing" from "the cell's own drawing" in
    the resulting canvas commands)."""
    app = App()

    if cell_source_draws:

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

    else:

        @app.cell(
            elements=[
                ui.turtle_canvas("canvas", width=400, height=400),
                ui.tests("unit", default=test_source),
            ],
        )
        def draw_something():
            pass

    return app


def test_run_tests_can_call_turtle_when_given_a_turtle_canvas_element():
    from codeslides.deck import Element

    canvas = Element(name="canvas", kind="turtle_canvas", config={"width": 400, "height": 400})
    result = run_tests("turtle.forward(50)\nturtle.right(90)\nturtle.forward(50)", {}, [canvas])

    assert result["status"] == "pass"
    assert "turtle_commands" in result
    assert len(result["turtle_commands"]) == 3


def test_run_tests_has_no_turtle_commands_key_without_a_turtle_canvas_element():
    result = run_tests("assert 1 == 1", {})
    assert "turtle_commands" not in result


def test_run_tests_turtle_call_errors_cleanly_with_no_canvas_element():
    result = run_tests("turtle.forward(50)", {})
    assert result["status"] == "error"
    assert "turtle" in result["message"].lower()


def test_tests_elements_turtle_drawing_appears_on_the_cells_own_canvas():
    """The whole point: a cell with no turtle calls of its own can still
    have its canvas populated by a test's turtle calls, so a student can
    visually check turtle logic in isolation."""
    app = _build_turtle_deck(cell_source_draws=False, test_source="turtle.forward(50)\nturtle.right(90)")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["draw_something"].status == "idle"
    assert session.instances["draw_something"].elements["unit"].content == {"status": "pass", "message": ""}
    canvas_content = session.instances["draw_something"].elements["canvas"].content
    assert len(canvas_content) == 2


def test_tests_elements_turtle_drawing_replaces_the_cells_own_drawing():
    """A cell that *does* draw its own turtle picture still gets its
    canvas overwritten by the test's drawing -- there's only one canvas,
    and the point of running the test is seeing what the test itself
    draws, not layering it on top of the cell's own leftover picture."""
    app = _build_turtle_deck(cell_source_draws=True, test_source="turtle.forward(1)")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    canvas_content = session.instances["draw_something"].elements["canvas"].content
    # the cell's own body issues 3 turtle commands (forward, right, forward);
    # the test issues exactly 1 -- the canvas reflects the test's 1, not the cell's 3
    assert len(canvas_content) == 1


def test_editing_the_test_source_updates_the_canvas_without_rerunning_the_cell():
    app = _build_turtle_deck(cell_source_draws=True, test_source="turtle.forward(1)")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    namespace_before = dict(session.namespace)

    kernel.on_tests_edited(
        "draw_something", "unit", "turtle.forward(1)\nturtle.forward(1)\nturtle.forward(1)", session
    )

    canvas_content = session.instances["draw_something"].elements["canvas"].content
    assert len(canvas_content) == 3
    # the cell itself never re-ran
    assert session.namespace == namespace_before


def test_a_failing_test_still_updates_the_canvas_with_whatever_it_drew_before_failing():
    app = _build_turtle_deck(
        cell_source_draws=False,
        test_source="turtle.forward(50)\nassert False, 'deliberate failure'",
    )
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["draw_something"].elements["unit"].content["status"] == "fail"
    # the turtle.forward(50) call before the failing assert still recorded
    # a command -- a test's turtle drawing isn't all-or-nothing the way
    # namespace writes are, since there's no "partial namespace" risk here
    canvas_content = session.instances["draw_something"].elements["canvas"].content
    assert len(canvas_content) == 1
