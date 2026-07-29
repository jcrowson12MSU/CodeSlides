"""Turtle drawing exercised through the real kernel/Session, not just
turtle.py in isolation -- see test_turtle.py for the module's own API
tests, and test_cs.py/test_kernel.py for the equivalent cs.* coverage."""

from codeslides import App, turtle, ui
from codeslides.kernel import Kernel
from codeslides.session import Session


def _square_deck():
    app = App()

    @app.cell(elements=[ui.turtle_canvas("canvas")])
    def draw_square():
        for _ in range(4):
            turtle.forward(50)
            turtle.right(90)
        done = True
        return done

    return app


def test_turtle_drawing_writes_commands_to_its_canvas_element():
    app = _square_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.instances["draw_square"].status == "idle", session.instances["draw_square"].error
    commands = session.instances["draw_square"].elements["canvas"].content
    assert commands is not None
    assert len(commands) > 0
    assert all(c["op"] in {"goto", "heading"} for c in commands)


def test_turtle_canvas_content_isolated_across_cloned_sessions():
    """Regression-shaped test mirroring the cs.image() clone-isolation
    test: two Sessions running the same turtle-drawing cell must get
    independent turtle state/canvas content, per ARCHITECTURE.md section 7."""
    app = _square_deck()
    kernel = Kernel(app.deck)

    session_a = Session(deck=app.deck)
    kernel.run_all(session_a)
    session_b = session_a.clone()

    # mutate b's canvas content directly (simulating a later independent
    # draw) and confirm a is untouched
    session_b.instances["draw_square"].elements["canvas"].content = ["different"]

    assert session_a.instances["draw_square"].elements["canvas"].content != ["different"]
    assert session_b.instances["draw_square"].elements["canvas"].content == ["different"]


def test_cell_without_turtle_canvas_element_errors_on_turtle_call():
    app = App()

    @app.cell
    def draw_without_canvas():
        turtle.forward(10)
        done = True
        return done

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["draw_without_canvas"].status == "error"
    assert "outside of cell execution" in session.instances["draw_without_canvas"].error


def test_cell_with_multiple_turtle_canvases_errors_on_turtle_call():
    app = App()

    @app.cell(elements=[ui.turtle_canvas("a"), ui.turtle_canvas("b")])
    def draw_ambiguous():
        turtle.forward(10)
        done = True
        return done

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["draw_ambiguous"].status == "error"


def test_editing_turtle_cell_redraws_with_new_commands():
    app = _square_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    original_commands = session.instances["draw_square"].elements["canvas"].content

    kernel.on_cell_edited(
        "draw_square",
        "def draw_square():\n    turtle.forward(10)\n    done = True\n    return done\n",
        session,
    )

    new_commands = session.instances["draw_square"].elements["canvas"].content
    assert new_commands != original_commands
    assert len(new_commands) == 1
    assert new_commands[0]["x"] == 10


def test_turtle_object_constructed_in_one_cell_draws_on_the_calling_cells_canvas():
    """The user's own markCorners(cells, t) shape: mark_corners is
    defined in one cell with no turtle_canvas of its own, takes `t` as
    an ordinary parameter, and is called from a second cell that
    *does* have a turtle_canvas -- t = turtle.Turtle() constructed
    there and passed in. Every t.* call inside mark_corners must draw
    onto the *calling* cell's canvas (draw_with_turtle_object's), since
    a Turtle() is a proxy onto whichever cell execution is currently
    active, not onto whatever cell it was constructed in.

    mark_corners needs its own `tests` element (empty default is fine)
    so it's only ever *defined*, not auto-called with no arguments
    (TODO.md #43/`_run_cells`) -- `points`/`t` have no defaults, so an
    auto-call would fail before draw_with_turtle_object ever got a
    chance to call it itself with real arguments."""
    app = App()

    @app.cell(elements=[ui.tests("unit")])
    def mark_corners(points, t):
        for x, y in points:
            t.goto(x, y)
            t.stamp()
        marked = True
        return marked

    @app.cell(elements=[ui.turtle_canvas("canvas")])
    def draw_with_turtle_object():
        t = turtle.Turtle()
        mark_corners([(0, 0), (1, 1)], t)
        drawn = True
        return drawn

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["draw_with_turtle_object"].status == "idle", (
        session.instances["draw_with_turtle_object"].error
    )
    commands = session.instances["draw_with_turtle_object"].elements["canvas"].content
    stamps = [c for c in commands if c["op"] == "stamp"]
    assert len(stamps) == 2
    assert (stamps[0]["x"], stamps[0]["y"]) == (0, 0)
    assert (stamps[1]["x"], stamps[1]["y"]) == (1, 1)
