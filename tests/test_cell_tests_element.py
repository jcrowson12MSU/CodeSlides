"""Tests for the `ui.tests(...)` element (ARCHITECTURE.md section 3b):
a second, unittest-like code editor attached to a cell. A cell with a
`tests` element is *defined* but never auto-called with no arguments the
way a plain cell is -- only the test (which calls the function itself,
with whatever arguments it chooses) exercises it. See TODO.md's
"the main code editor should not be run at all if there is a test
block" entry."""

from codeslides import App, turtle, ui
from codeslides.kernel import Kernel, run_tests
from codeslides.session import Session


def _build_deck(test_source: str = "assert live_demo(3) == 15"):
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
    assert run_tests("assert 1 + 1 == 2", {}) == {
        "status": "pass",
        "message": "",
        "stdout": "",
        "stderr": "",
    }


def test_run_tests_fail_with_assertion_message():
    result = run_tests("assert 1 == 2, 'nope'", {})
    assert result == {"status": "fail", "message": "nope", "stdout": "", "stderr": ""}


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
    assert run_tests("", {}) == {"status": "pass", "message": "", "stdout": "", "stderr": ""}
    assert run_tests("   \n  ", {}) == {"status": "pass", "message": "", "stdout": "", "stderr": ""}


def test_run_tests_surfaces_printed_output_with_no_assertions_at_all():
    """The tests box isn't only for assert-only unittest-style checks --
    a plain `print(some_function(3, 4))` with no assertions at all is
    just as valid, to show/talk through a sample input and its output.
    Previously this printed text was captured internally and then
    silently discarded before ever reaching the caller."""
    result = run_tests("print(double(21))", {"double": lambda x: x * 2})
    assert result["status"] == "pass"
    assert result["stdout"] == "42\n"


def test_run_tests_surfaces_stdout_alongside_a_passing_assertion():
    result = run_tests("print('checking...')\nassert 1 + 1 == 2", {})
    assert result["status"] == "pass"
    assert result["stdout"] == "checking...\n"


def test_run_tests_surfaces_stdout_printed_before_a_failing_assertion():
    # output printed before the failure is still real, useful context --
    # not thrown away just because the test overall failed.
    result = run_tests("print('about to fail')\nassert False", {})
    assert result["status"] == "fail"
    assert result["stdout"] == "about to fail\n"


def test_tests_element_auto_runs_after_run_all_and_passes():
    app = _build_deck("assert live_demo(3) == 15")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["live_demo"].elements["unit"].content == {
        "status": "pass",
        "message": "",
        "stdout": "",
        "stderr": "",
    }


def test_tests_element_auto_runs_and_fails():
    app = _build_deck("assert live_demo(3) == 999, 'wrong'")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["live_demo"].elements["unit"].content == {
        "status": "fail",
        "message": "wrong",
        "stdout": "",
        "stderr": "",
    }


def test_live_demo_is_never_auto_called_with_no_arguments():
    """The core of this change: live_demo(speed) has an input element
    (a slider) bound to `speed`, but that binding is only ever consumed
    if the cell is actually *called* -- and a tested cell no longer is,
    automatically. `result` (a name only the call would produce) must
    never appear in the namespace just from run_all; only the test
    calling live_demo() itself produces a value."""
    app = _build_deck("assert live_demo(3) == 15")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["live_demo"].status == "idle"
    assert "result" not in session.namespace
    assert callable(session.namespace["live_demo"])
    assert session.instances["live_demo"].elements["unit"].content["status"] == "pass"


def test_tests_element_can_call_the_cell_with_a_different_argument_than_any_slider_value():
    """A tested cell's own input-element value (e.g. a slider) is no
    longer consumed automatically at all -- the test is free to call
    the function with whatever argument it chooses, completely
    independent of what the slider element instance currently holds."""
    app = _build_deck("assert live_demo(7) == 35")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["live_demo"].elements["unit"].content["status"] == "pass"


def test_tests_element_does_not_run_when_the_cell_itself_fails_to_define():
    app = _build_deck("assert live_demo(3) == 15")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.instances["live_demo"].elements["unit"].content["status"] == "pass"

    # break the cell's own *definition* -- a bad return shape
    # (CellDefinitionError: multiple return statements), not just a bad
    # call -- since defining (not calling) is what a tested cell can now
    # fail at. A plain SyntaxError from a mid-edit is a separate,
    # pre-existing early-return path in on_cell_edited (before
    # _run_cells is ever reached at all), so it wouldn't exercise the
    # "cell errored -> mark test error" branch this test is actually
    # checking. (A computed-expression return, e.g. `return speed + 1`,
    # no longer counts as a bad definition -- see kernel.py's
    # `_extract_return_names` -- so multiple `return`s is the remaining
    # way to trigger this.)
    kernel.on_cell_edited(
        "live_demo", "def live_demo(speed):\n    if speed > 0:\n        return speed\n    return 0\n", session
    )

    assert session.instances["live_demo"].status == "error"
    assert session.instances["live_demo"].elements["unit"].content["status"] == "error"


def test_on_tests_edited_reruns_the_test_without_rerunning_the_cell():
    app = _build_deck("assert live_demo(3) == 999")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.instances["live_demo"].elements["unit"].content["status"] == "fail"
    namespace_before = dict(session.namespace)

    result = kernel.on_tests_edited("live_demo", "unit", "assert live_demo(3) == 15", session)

    assert result == {"status": "pass", "message": "", "stdout": "", "stderr": ""}
    assert session.instances["live_demo"].elements["unit"].content == {
        "status": "pass",
        "message": "",
        "stdout": "",
        "stderr": "",
    }
    assert session.instances["live_demo"].elements["unit"].value == "assert live_demo(3) == 15"
    # the cell itself never re-ran (re-defined) -- namespace is untouched
    assert session.namespace == namespace_before


def test_on_tests_edited_folds_the_edit_into_source_overrides_and_it_saves(tmp_path):
    """The actual persistence gap this fixes: a tests element's edited
    source previously lived only in instance.elements[...].value --
    in-memory, never touched by Save at all. Confirms the edit now
    round-trips through session.source_overrides/save_edits, the same
    slot a code or notes edit already uses, and survives an actual
    reload from disk."""
    path = tmp_path / "deck.py"
    path.write_text(
        "from codeslides import App, ui\n\napp = App()\n\n"
        '@app.cell(elements=[ui.tests("unit", default="assert 1 == 1")])\n'
        "def cell_with_test():\n    return 1\n"
    )
    from codeslides.loader import load_deck
    from codeslides.serialization import save_edits

    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    kernel.on_tests_edited("cell_with_test", "unit", "assert cell_with_test() == 1", session)

    assert "cell_with_test" in session.source_overrides
    assert "assert cell_with_test() == 1" in session.source_overrides["cell_with_test"]

    save_edits(str(path), session.source_overrides)
    reloaded = load_deck(str(path))
    unit = next(e for e in reloaded.cells["cell_with_test"].elements if e.name == "unit")
    assert unit.config["default"] == "assert cell_with_test() == 1"


def test_on_tests_edited_skips_source_overrides_if_the_cells_code_is_unparseable(tmp_path):
    path = tmp_path / "deck.py"
    path.write_text(
        "from codeslides import App, ui\n\napp = App()\n\n"
        '@app.cell(elements=[ui.tests("unit", default="assert 1 == 1")])\n'
        "def cell_with_test():\n    return 1\n"
    )
    from codeslides.loader import load_deck

    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    # simulate mid-keystroke invalid code sitting in this cell's own
    # override, from a concurrent code edit in the same session
    session.source_overrides["cell_with_test"] = "def cell_with_test(:\n    return 1\n"

    kernel.on_tests_edited("cell_with_test", "unit", "assert cell_with_test() == 1", session)

    # the in-memory value/result still update (the test box keeps
    # showing what was typed and its own run result)...
    assert session.instances["cell_with_test"].elements["unit"].value == "assert cell_with_test() == 1"
    # ...but the unparseable override is left alone rather than crashing
    # or silently discarding the pending (invalid) code edit
    assert session.source_overrides["cell_with_test"] == "def cell_with_test(:\n    return 1\n"


def test_tests_element_value_is_seeded_from_default():
    app = _build_deck("assert live_demo(3) == 15")
    session = Session(deck=app.deck)
    assert session.instances["live_demo"].elements["unit"].value == "assert live_demo(3) == 15"
    # no run has happened yet -- no result to show
    assert session.instances["live_demo"].elements["unit"].content is None


def test_a_print_only_test_with_no_assertions_still_shows_its_output_end_to_end():
    """The real motivating use case: a tests box holding just
    `print(double(21))`, no assert anywhere, to show/talk through a
    sample call and its output -- not a pass/fail check at all.
    Confirms this survives the full auto-run-after-run_all path (not
    just a direct run_tests call), and that the test calling the
    (never-auto-called) function itself is what actually exercises it."""
    app = App()

    @app.cell(elements=[ui.tests("unit", default="print(double(21))")])
    def double(x):
        result = x * 2
        return result

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    content = session.instances["double"].elements["unit"].content
    assert content["status"] == "pass"
    assert content["stdout"] == "42\n"


def test_tests_element_isolated_across_cloned_sessions():
    app = _build_deck("assert live_demo(3) == 15")
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    clone = session.clone()
    kernel.on_tests_edited("live_demo", "unit", "assert live_demo(3) == 999", clone)

    # the clone's edit never touches the source session's test state
    assert session.instances["live_demo"].elements["unit"].value == "assert live_demo(3) == 15"
    assert session.instances["live_demo"].elements["unit"].content == {
        "status": "pass",
        "message": "",
        "stdout": "",
        "stderr": "",
    }
    assert clone.instances["live_demo"].elements["unit"].value == "assert live_demo(3) == 999"
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
    assert session.instances["draw_something"].elements["unit"].content == {
        "status": "pass",
        "message": "",
        "stdout": "",
        "stderr": "",
    }
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
