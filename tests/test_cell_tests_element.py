"""Tests for the `ui.tests(...)` element (ARCHITECTURE.md section 3b):
a second, unittest-like code editor attached to a cell, auto-run against
the cell's own effective namespace every time the cell re-runs."""

from codeslides import App, ui
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
