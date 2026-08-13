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


# -- shape()/shapesize() (docs/turtle-compatibility-todo.md Phase 2) --------


def test_shape_default_is_classic():
    with turtle.execution_context():
        assert turtle.shape() == "classic"


def test_shape_sets_and_queries():
    with turtle.execution_context() as commands:
        turtle.shape("circle")
        current = turtle.shape()

    assert current == "circle"
    assert commands[0] == {
        "op": "shape",
        "name": "circle",
        "stretch_wid": 1.0,
        "stretch_len": 1.0,
        "outline": 1.0,
    }


def test_shape_rejects_an_unknown_name():
    """Real turtle raises for a shape name that's never been registered
    -- validated here against the same fixed built-in set every stdlib
    turtle installation ships with (register_shape/getshapes are
    unsupported, see Gap 4), rather than silently accepting anything."""
    with turtle.execution_context(), pytest.raises(ValueError, match="not-a-real-shape"):
        turtle.shape("not-a-real-shape")


def test_shapesize_default_is_1_1_1():
    with turtle.execution_context():
        assert turtle.shapesize() == (1.0, 1.0, 1.0)


def test_shapesize_with_only_stretch_wid_stretches_both_axes_uniformly():
    """Matches real turtle's own defaulting: stretch_len defaults to
    match stretch_wid when only stretch_wid is given."""
    with turtle.execution_context():
        turtle.shapesize(3)
        assert turtle.shapesize() == (3, 3, 1.0)


def test_shapesize_with_only_stretch_len_leaves_stretch_wid_alone():
    with turtle.execution_context():
        turtle.shapesize(stretch_len=5)
        assert turtle.shapesize() == (1.0, 5, 1.0)


def test_shapesize_sets_all_three_independently():
    with turtle.execution_context() as commands:
        turtle.shapesize(2, 3, outline=4)

    assert commands[-1] == {
        "op": "shape",
        "name": "classic",
        "stretch_wid": 2,
        "stretch_len": 3,
        "outline": 4,
    }


def test_shapesize_rejects_a_zero_stretch_factor():
    with turtle.execution_context(), pytest.raises(ValueError, match="must not be zero"):
        turtle.shapesize(0)


def test_shape_and_shapesize_share_state_so_shapesize_preserves_the_current_shape_name():
    with turtle.execution_context() as commands:
        turtle.shape("square")
        turtle.shapesize(2)

    assert commands[-1]["name"] == "square"
    assert commands[-1]["stretch_wid"] == 2


def test_stamp_snapshots_the_shape_at_the_moment_its_called():
    """A stamp must reflect whatever shape/stretch was active when
    stamp() ran, not whatever the shape happens to be by the time the
    frontend replays the whole command list -- verified here the same
    way the existing heading-snapshot behavior already is, by changing
    the shape again *after* the stamp and confirming the stamp's own
    command still shows the earlier value."""
    with turtle.execution_context() as commands:
        turtle.shape("triangle")
        turtle.shapesize(2, 2)
        turtle.stamp()
        turtle.shape("circle")  # changed again after the stamp

    stamp_cmd = next(c for c in commands if c["op"] == "stamp")
    assert stamp_cmd["shape"] == "triangle"
    assert stamp_cmd["stretch_wid"] == 2
    assert stamp_cmd["stretch_len"] == 2


def test_turtle_object_shape_and_shapesize_work_the_same_as_module_functions():
    t = turtle.Turtle()
    with turtle.execution_context():
        t.shape("square")
        t.shapesize(2, 2, 3)
        assert t.shape() == "square"
        assert t.shapesize() == (2, 2, 3)


# -- Screen() object handle (docs/turtle-compatibility-todo.md Phase 1) -----


def test_screen_calls_outside_execution_context_raise():
    with pytest.raises(RuntimeError, match="outside of cell execution"):
        turtle.Screen()


def test_screen_object_calls_outside_execution_context_raise():
    with turtle.execution_context():
        wn = turtle.Screen()
    with pytest.raises(RuntimeError, match="outside of cell execution"):
        wn.tracer(0)


def test_setworldcoordinates_emits_a_command_with_the_four_bounds():
    with turtle.execution_context() as commands:
        wn = turtle.Screen()
        wn.setworldcoordinates(0, 0, 10, 20)

    assert commands[0] == {"op": "setworldcoordinates", "llx": 0, "lly": 0, "urx": 10, "ury": 20}


def test_tracer_and_update_are_accepted_as_no_ops():
    """Real turtle's tracer(0)/update() toggle/flush a per-step redraw
    mode this app never had in the first place -- it already always
    redraws the complete, finished picture in one pass (docs/turtle-
    animation-feasibility.md). Both must be callable without raising or
    emitting a spurious command, not error out on an otherwise
    load-bearing-only-in-real-turtle line."""
    with turtle.execution_context() as commands:
        wn = turtle.Screen()
        wn.tracer(0)
        wn.update()

    assert commands == []


def test_exitonclick_and_bye_are_accepted_as_no_ops():
    """A CodeSlides cell has no window to keep open or close -- these
    must be safely callable, typically as the very last lines of a
    real turtle script, without raising or doing anything."""
    with turtle.execution_context() as commands:
        wn = turtle.Screen()
        wn.exitonclick()
        wn.bye()

    assert commands == []


def test_bgcolor_emits_a_command_and_is_queryable():
    with turtle.execution_context() as commands:
        wn = turtle.Screen()
        wn.bgcolor("lightyellow")
        current = wn.bgcolor()

    assert current == "lightyellow"
    assert commands[0] == {"op": "bgcolor", "color": "lightyellow"}


def test_screensize_with_bg_also_sets_the_background_color():
    """Real turtle documents screensize(..., bg=...) as equivalent to a
    separate bgcolor() call -- verified this holds here too, since
    screensize itself has no scrolling-region concept to actually
    resize in this app's fixed-size turtle_canvas."""
    with turtle.execution_context() as commands:
        wn = turtle.Screen()
        wn.screensize(400, 400, bg="white")

    assert commands == [{"op": "bgcolor", "color": "white"}]


def test_colormode_is_accepted_as_a_no_op():
    with turtle.execution_context() as commands:
        wn = turtle.Screen()
        wn.colormode(255)

    assert commands == []


def test_unsupported_screen_event_methods_raise_a_clear_not_implemented_error():
    """onclick/onkey/onkeypress/ontimer/listen/register_shape/getshapes
    are architecturally out of scope (docs/turtle-compatibility-todo.md
    Gap 4): this app's cells run once, synchronously, to completion --
    there is no persistent event loop for a callback to fire against
    later. A clear, documented error is much better than silently
    registering a callback that can never actually run."""
    with turtle.execution_context():
        wn = turtle.Screen()
        for name, args in [
            ("onclick", (lambda x, y: None,)),
            ("onkey", (lambda: None, "space")),
            ("onkeypress", (lambda: None, "space")),
            ("ontimer", (lambda: None, 100)),
            ("listen", ()),
            ("register_shape", ("name",)),
            ("getshapes", ()),
        ]:
            with pytest.raises(NotImplementedError, match=name):
                getattr(wn, name)(*args)


def test_reference_deck_screen_setup_sequence_runs_without_error():
    """The exact setup sequence from examples/originalMarchingSquares.py
    that motivated this whole phase -- confirms it no longer fails
    outright the way it did before Screen existed at all (the original
    bug report: `wn = turtle.Screen()` raised AttributeError
    immediately). t.shape(...) is deliberately excluded here -- that's
    Phase 2, still unimplemented at this point."""
    with turtle.execution_context():
        wn = turtle.Screen()
        wn.setworldcoordinates(0, 0, 18, 12)
        wn.tracer(0)

        t = turtle.Turtle()
        t.up()
        t.hideturtle()

        wn.update()
        wn.exitonclick()
