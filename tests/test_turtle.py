import math

import pytest

from codeslides import turtle


def test_calls_outside_execution_context_raise():
    with pytest.raises(RuntimeError, match="outside of cell execution"):
        turtle.forward(10)


def test_forward_emits_goto_and_updates_position():
    with turtle.execution_context() as commands:
        turtle.forward(100)
        pos = turtle.position()

    assert pos == pytest.approx((100, 0))
    assert commands[0]["op"] == "goto"
    assert commands[0]["x"] == pytest.approx(100)
    assert commands[0]["y"] == pytest.approx(0)
    assert commands[0]["pen_down"] is True


def test_right_and_forward_trace_a_square_back_to_origin():
    with turtle.execution_context():
        for _ in range(4):
            turtle.forward(50)
            turtle.right(90)
        final = turtle.position()

    assert final == pytest.approx((0, 0), abs=1e-9)


def test_left_is_inverse_of_right():
    with turtle.execution_context():
        turtle.right(37)
        turtle.left(37)
        h = turtle.heading()

    assert h == pytest.approx(0)


def test_penup_pendown_control_whether_goto_draws():
    with turtle.execution_context() as commands:
        turtle.penup()
        turtle.forward(10)
        turtle.pendown()
        turtle.forward(10)

    goto_commands = [c for c in commands if c["op"] == "goto"]
    assert goto_commands[0]["pen_down"] is False
    assert goto_commands[1]["pen_down"] is True


def test_goto_sets_absolute_position():
    with turtle.execution_context():
        turtle.forward(50)
        turtle.goto(10, 20)
        pos = turtle.position()

    assert pos == pytest.approx((10, 20))


def test_pencolor_and_fillcolor_affect_subsequent_commands():
    with turtle.execution_context() as commands:
        turtle.pencolor("red")
        turtle.forward(10)

    goto_after_color = next(c for c in commands if c["op"] == "goto")
    assert goto_after_color["color"] == "red"


def test_color_sets_both_pen_and_fill():
    with turtle.execution_context():
        turtle.color("blue")
        pen, fill = turtle.color()

    assert pen == "blue"
    assert fill == "blue"


def test_execution_context_is_isolated_per_call():
    with turtle.execution_context():
        turtle.forward(100)
        pos_a = turtle.position()

    with turtle.execution_context():
        pos_b = turtle.position()

    assert pos_a == pytest.approx((100, 0))
    assert pos_b == pytest.approx((0, 0))


def test_circle_returns_to_a_point_close_to_start_after_full_circle():
    with turtle.execution_context():
        start = turtle.position()
        turtle.circle(50)
        end = turtle.position()

    assert end == pytest.approx(start, abs=1.0)


def test_clear_emits_clear_command():
    with turtle.execution_context() as commands:
        turtle.forward(10)
        turtle.clear()

    assert commands[-1]["op"] == "clear"


def test_reset_returns_to_origin_and_default_heading():
    with turtle.execution_context():
        turtle.forward(50)
        turtle.right(45)
        turtle.reset()
        pos = turtle.position()
        h = turtle.heading()

    assert pos == pytest.approx((0, 0))
    assert h == pytest.approx(0)


def test_hideturtle_showturtle_toggle_visibility():
    with turtle.execution_context():
        turtle.hideturtle()
        assert turtle.isvisible() is False
        turtle.showturtle()
        assert turtle.isvisible() is True


def test_aliases_match_full_names():
    with turtle.execution_context():
        turtle.fd(10)
        pos_fd = turtle.position()
        turtle.bk(10)
        pos_bk = turtle.position()

    assert pos_fd == pytest.approx((10, 0))
    assert pos_bk == pytest.approx((0, 0))


def test_forward_respects_heading_direction():
    with turtle.execution_context():
        turtle.left(90)
        turtle.forward(10)
        pos = turtle.position()
        h = turtle.heading()

    assert pos == pytest.approx((0, 10), abs=1e-9)
    assert math.isclose(h, 90)


# -- Turtle() object handle -----------------------------------------------


def test_turtle_object_calls_outside_execution_context_raise():
    t = turtle.Turtle()
    with pytest.raises(RuntimeError, match="outside of cell execution"):
        t.forward(10)


def test_turtle_object_methods_emit_the_same_commands_as_module_functions():
    t = turtle.Turtle()
    with turtle.execution_context() as commands:
        t.forward(100)
        t.right(90)
        pos = t.position()
        h = t.heading()

    assert pos == pytest.approx((100, 0))
    assert math.isclose(h, 270)
    assert commands[0]["op"] == "goto"
    assert commands[0]["x"] == pytest.approx(100)
    assert commands[1]["op"] == "heading"


def test_turtle_object_created_in_one_call_targets_whichever_context_is_active_when_called():
    """A Turtle() is a proxy onto the contextvar, not an object with its
    own state -- constructing it outside any context, then calling its
    methods once a context becomes active (e.g. passed into another
    cell's function), must still work and target that active context."""
    t = turtle.Turtle()  # constructed with no context active at all
    with turtle.execution_context() as commands:
        t.goto(3, 4)

    assert commands[0]["op"] == "goto"
    assert commands[0]["x"] == pytest.approx(3)
    assert commands[0]["y"] == pytest.approx(4)


def test_turtle_object_can_be_passed_as_a_function_parameter():
    """The exact shape the user's own markCorners(cells, t) cell needs:
    t constructed in one place, passed as an ordinary parameter into a
    function defined elsewhere, and its calls still draw into the
    currently-active context (whichever cell is executing when the
    function actually runs)."""

    def draw_corners(points, t):
        for x, y in points:
            t.goto(x, y)
            t.stamp()

    t = turtle.Turtle()
    with turtle.execution_context() as commands:
        draw_corners([(0, 0), (1, 0), (1, 1), (0, 1)], t)

    stamps = [c for c in commands if c["op"] == "stamp"]
    assert len(stamps) == 4
    assert (stamps[0]["x"], stamps[0]["y"]) == pytest.approx((0, 0))
    assert (stamps[3]["x"], stamps[3]["y"]) == pytest.approx((0, 1))


def test_two_turtle_objects_share_the_same_underlying_state():
    """Documents a deliberate limitation: unlike real stdlib turtle,
    this app has exactly one turtle worth of state per cell execution
    (one contextvar, scoped to the cell's single turtle_canvas element)
    -- two Turtle() instances used in the same execution are two
    handles onto the *same* position/heading/pen state, not two
    independently-tracked turtles."""
    t1 = turtle.Turtle()
    t2 = turtle.Turtle()
    with turtle.execution_context():
        t1.goto(5, 5)
        pos_from_t2 = t2.position()

    assert pos_from_t2 == pytest.approx((5, 5))
