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
