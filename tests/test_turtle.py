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


def test_circle_semicircle_ends_at_the_stdlib_docstrings_own_example():
    """Regression test for a real bug found by a post-Phase-5 audit
    (docs/turtle-compatibility-todo.md's "Remaining work" section): an
    earlier version of circle() had no leading/trailing half-step
    rotation (real turtle rotates by half a step-angle before the
    first chord and unwinds it after the last, verified against the
    CPython source, so the chord polygon is centered on the true arc)
    -- invisible for a *full* circle (both endpoints coincide with the
    start regardless), which is exactly why the test above alone never
    caught it. Reproduces real turtle's own documented
    `circle(120, 180)` docstring example exactly (semicircle from the
    origin facing east ends at (0, 2*radius))."""
    with turtle.execution_context():
        turtle.circle(120, 180)
        end = turtle.position()

    assert end == pytest.approx((0, 240), abs=1e-6)


def test_circle_quarter_arc_ends_at_the_expected_position():
    with turtle.execution_context():
        turtle.circle(100, 90)
        end = turtle.position()

    assert end == pytest.approx((100, 100), abs=1e-6)


def test_circle_changes_heading_by_the_full_extent():
    with turtle.execution_context():
        turtle.circle(100, 180)
        h = turtle.heading()

    assert h == pytest.approx(180)


def test_circle_with_negative_radius_curves_clockwise():
    """Real turtle: positive radius curves counterclockwise, negative
    radius curves clockwise (verified against the CPython source's own
    docstring) -- a quarter-turn clockwise from due east ends pointing
    south, at (radius, -radius)."""
    with turtle.execution_context():
        turtle.circle(-50, 90)
        end = turtle.position()
        h = turtle.heading()

    assert end == pytest.approx((50, -50), abs=1e-6)
    assert h == pytest.approx(270)


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


def test_reset_restores_stretch_and_outline_to_defaults():
    """Real turtle's own TPen._reset resets stretch/outline (verified
    against the CPython source) -- a real gap caught while touching
    reset() again for Phase 3: shapesize (Phase 2) added these fields
    but never wired them into reset()."""
    with turtle.execution_context():
        turtle.shapesize(3, 4, 5)
        turtle.reset()
        assert turtle.shapesize() == (1.0, 1.0, 1.0)


def test_reset_does_not_touch_the_shape_name():
    """Also verified against the CPython source: shape lives on a
    separate object real turtle's own _reset() never touches, unlike
    stretch/outline -- reset() must not revert an explicitly-set shape
    back to the default."""
    with turtle.execution_context():
        turtle.shape("circle")
        turtle.reset()
        assert turtle.shape() == "circle"


# -- begin_fill()/end_fill()/filling() (docs/turtle-compatibility-todo.md Phase 3) --


def test_filling_defaults_to_false():
    with turtle.execution_context():
        assert turtle.filling() is False


def test_begin_fill_sets_filling_true():
    with turtle.execution_context():
        turtle.begin_fill()
        assert turtle.filling() is True


def test_end_fill_sets_filling_false():
    with turtle.execution_context():
        turtle.begin_fill()
        turtle.end_fill()
        assert turtle.filling() is False


def test_begin_fill_emits_a_command_carrying_the_current_fill_color():
    with turtle.execution_context() as commands:
        turtle.fillcolor("gold")
        turtle.begin_fill()

    assert commands[-1] == {"op": "begin_fill", "color": "gold"}


def test_end_fill_emits_a_bare_command():
    with turtle.execution_context() as commands:
        turtle.begin_fill()
        turtle.end_fill()

    assert commands[-1] == {"op": "end_fill"}


def test_begin_fill_is_idempotent():
    """Matches real turtle: calling begin_fill() while already filling
    doesn't emit a second marker (verified against the CPython source's
    own `if not self.filling(): ...` guard)."""
    with turtle.execution_context() as commands:
        turtle.begin_fill()
        turtle.begin_fill()

    assert sum(1 for c in commands if c["op"] == "begin_fill") == 1


def test_end_fill_is_idempotent():
    """Matches real turtle: calling end_fill() while not filling is a
    safe no-op, not an error, and never emits a spurious marker."""
    with turtle.execution_context() as commands:
        turtle.end_fill()
        assert commands == []

        turtle.begin_fill()
        turtle.end_fill()
        turtle.end_fill()

    assert sum(1 for c in commands if c["op"] == "end_fill") == 1


def test_goto_calls_between_begin_and_end_fill_still_emit_normal_goto_commands():
    """begin_fill/end_fill are pure markers -- the actual boundary
    points are reconstructed by the frontend from the ordinary `goto`
    commands already emitted for the pen stroke itself, so this module
    must not suppress or alter them while filling is active."""
    with turtle.execution_context() as commands:
        turtle.begin_fill()
        turtle.goto(10, 0)
        turtle.goto(10, 10)
        turtle.end_fill()

    goto_commands = [c for c in commands if c["op"] == "goto"]
    assert len(goto_commands) == 2
    assert goto_commands[0]["x"] == pytest.approx(10)
    assert goto_commands[1]["y"] == pytest.approx(10)


def test_reset_aborts_an_in_progress_fill():
    """Matches real turtle's own _clear() (`self._fillitem =
    self._fillpath = None`, verified against the CPython source) --
    reset() must abort filling, not leave it dangling true."""
    with turtle.execution_context():
        turtle.begin_fill()
        turtle.reset()
        assert turtle.filling() is False


def test_turtle_object_fill_methods_work_the_same_as_module_functions():
    t = turtle.Turtle()
    with turtle.execution_context():
        t.begin_fill()
        assert t.filling() is True
        t.end_fill()
        assert t.filling() is False


# -- dot()/write() behavioral-parity fixes (docs/turtle-compatibility-todo.md Phase 4) --


def test_dot_with_no_args_uses_pencolor_and_default_size():
    """Default size matches real turtle's own formula exactly
    (`pensize + max(pensize, 4)`, verified against the CPython source)
    -- the pre-Phase-4 shim computed a different value (8, not 5) for
    the common pensize=1 case."""
    with turtle.execution_context() as commands:
        turtle.pencolor("green")
        turtle.dot()

    assert commands[-1] == {"op": "dot", "x": 0.0, "y": 0.0, "size": 5.0, "color": "green"}


def test_dot_with_size_and_color_string():
    with turtle.execution_context() as commands:
        turtle.dot(20, "red")

    assert commands[-1] == {"op": "dot", "x": 0.0, "y": 0.0, "size": 20, "color": "red"}


def test_dot_with_only_a_color_string_no_size():
    """Real turtle allows a bare color positional with no size at all
    (verified against the CPython source's own `isinstance(size, (str,
    tuple))` branch) -- this shape was never supported by the pre-
    Phase-4 shim's `dot(size=None, color_=None)` two-positional-only
    signature."""
    with turtle.execution_context() as commands:
        turtle.dot("blue")

    assert commands[-1]["color"] == "blue"
    assert commands[-1]["size"] == pytest.approx(5.0)


def test_dot_with_rgb_varargs_converts_to_a_css_rgb_string():
    """Real turtle's `dot(size, r, g, b)` varargs shape (verified
    against the CPython source) -- the pre-Phase-4 shim's
    `dot(size=None, color_=None)` signature couldn't accept this at
    all (TypeError: too many positional arguments)."""
    with turtle.execution_context() as commands:
        turtle.dot(20, 255, 0, 0)

    assert commands[-1] == {"op": "dot", "x": 0.0, "y": 0.0, "size": 20, "color": "rgb(255, 0, 0)"}


def test_dot_with_an_rgb_tuple_converts_to_a_css_rgb_string():
    with turtle.execution_context() as commands:
        turtle.dot(20, (10, 20, 30))

    assert commands[-1]["color"] == "rgb(10, 20, 30)"


def test_turtle_object_dot_works_the_same_as_the_module_function():
    t = turtle.Turtle()
    with turtle.execution_context() as commands:
        t.dot(20, "purple")

    assert commands[-1] == {"op": "dot", "x": 0.0, "y": 0.0, "size": 20, "color": "purple"}


def test_write_without_move_leaves_the_turtle_in_place():
    with turtle.execution_context():
        turtle.write("Hello")
        assert turtle.position() == pytest.approx((0, 0))


def test_write_with_move_true_advances_the_turtle_rightward():
    """move=True moves the turtle to the drawn text's estimated right
    edge (real turtle's own semantics, verified against the CPython
    source) -- approximated via a fixed per-character width rather than
    real font metrics, since this app has no equivalent of Tk's actual
    text-rendering engine to measure exactly (see the function's own
    docstring for the full reasoning)."""
    with turtle.execution_context():
        turtle.penup()
        turtle.write("Hello", move=True)
        x, y = turtle.position()

    assert x > 0
    assert y == pytest.approx(0)


def test_write_with_move_true_and_center_align_advances_half_as_far():
    with turtle.execution_context():
        turtle.penup()
        turtle.write("Hello", move=True)
        left_aligned_x, _ = turtle.position()

    with turtle.execution_context():
        turtle.penup()
        turtle.write("Hello", move=True, align="center")
        center_aligned_x, _ = turtle.position()

    assert center_aligned_x == pytest.approx(left_aligned_x / 2)


def test_write_with_move_true_and_right_align_does_not_move():
    """Real turtle's own canvas anchor mapping ("right" -> "se", the
    southeast/bottom-right corner) already anchors right-aligned text
    at its own right edge -- verified against the CPython source --
    so there's nothing further to move for this alignment."""
    with turtle.execution_context():
        turtle.penup()
        turtle.write("Hello", move=True, align="right")
        x, y = turtle.position()

    assert (x, y) == pytest.approx((0, 0))


def test_write_with_move_true_under_active_setworldcoordinates_does_not_move():
    """The pixel-to-turtle-unit scale factor under an active
    setworldcoordinates(...) depends on the turtle_canvas element's
    actual on-screen size, which only the frontend knows -- this
    module can't convert a pixel-width estimate into the right number
    of turtle units without it, so it deliberately leaves the turtle
    in place rather than moving it to a confidently wrong position."""
    with turtle.execution_context():
        turtle.penup()
        turtle.setworldcoordinates(0, 0, 10, 10)
        turtle.write("Hello", move=True)
        x, y = turtle.position()

    assert (x, y) == pytest.approx((0, 0))


def test_write_still_emits_the_write_command_regardless_of_move():
    with turtle.execution_context() as commands:
        turtle.write("Hello", move=True)

    write_commands = [c for c in commands if c["op"] == "write"]
    assert len(write_commands) == 1
    assert write_commands[0]["text"] == "Hello"


def test_turtle_object_write_works_the_same_as_the_module_function():
    t = turtle.Turtle()
    with turtle.execution_context():
        t.up()
        t.write("Hi", move=True)
        x, _ = t.position()

    assert x > 0


# -- distance()/towards() (docs/turtle-compatibility-todo.md Phase 5) -------


def test_distance_matches_the_stdlib_docstrings_own_example():
    """turtle.pos() == (0, 0); turtle.distance(30, 40) == 50.0 --
    verified directly against real turtle's own documented example."""
    with turtle.execution_context():
        assert turtle.distance(30, 40) == pytest.approx(50.0)


def test_distance_accepts_a_tuple_the_same_as_two_positional_args():
    with turtle.execution_context():
        assert turtle.distance((30, 40)) == pytest.approx(turtle.distance(30, 40))


def test_distance_to_the_current_position_is_zero():
    with turtle.execution_context():
        turtle.goto(12, -7)
        assert turtle.distance(12, -7) == pytest.approx(0)


def test_towards_matches_the_stdlib_docstrings_own_example():
    """turtle.pos() == (10, 10); turtle.towards(0, 0) == 225.0 --
    verified directly against real turtle's own documented example."""
    with turtle.execution_context():
        turtle.goto(10, 10)
        assert turtle.towards(0, 0) == pytest.approx(225.0)


def test_towards_matches_heading_convention_pointing_east():
    """0 degrees means pointing east (this shim's own documented
    convention, matching forward()'s cos/sin usage) -- towards() must
    agree with it, not some other angle-mode offset."""
    with turtle.execution_context():
        assert turtle.towards(10, 0) == pytest.approx(0)
        assert turtle.towards(0, 10) == pytest.approx(90)


def test_distance_and_towards_reject_an_unrecognized_argument_shape():
    with turtle.execution_context():
        with pytest.raises(TypeError):
            turtle.distance("not a point")
        with pytest.raises(TypeError):
            turtle.towards(object())


def test_distance_and_towards_accept_another_turtle_as_the_target():
    """Real turtle accepts another Turtle instance as the target
    (verified against the CPython source) -- this shim has exactly one
    turtle's worth of state per cell execution (the Turtle class's own
    docstring), so a second Turtle() handle always resolves to the
    *same* position, making this a documented degenerate case (always
    0 here) rather than a genuinely independent second turtle's
    position the way real turtle would have."""
    with turtle.execution_context():
        t1 = turtle.Turtle()
        t2 = turtle.Turtle()
        t1.goto(5, 5)
        assert t1.distance(t2) == pytest.approx(0)


def test_distance_and_towards_accept_a_screen_as_the_target():
    """Same shared-state reasoning as the Turtle-target case above --
    a Screen() handle resolves to the same position too."""
    with turtle.execution_context():
        t = turtle.Turtle()
        t.goto(3, 4)
        wn = turtle.Screen()
        assert t.distance(wn) == pytest.approx(0)


def test_turtle_object_distance_and_towards_work_the_same_as_module_functions():
    t = turtle.Turtle()
    with turtle.execution_context():
        t.goto(10, 10)
        assert t.distance(0, 0) == pytest.approx(math.sqrt(200))
        assert t.towards(0, 0) == pytest.approx(225.0)


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
