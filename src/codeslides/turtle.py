"""Turtle-compatible drawing API for the browser. See ARCHITECTURE.md
section 7, strategy (b): a from-scratch reimplementation of the common
subset of the standard library's `turtle` module, since strategy (a)
(intercepting real `turtle`'s Tk backend) requires a Tk-enabled Python
build -- `import turtle` fails outright wherever `_tkinter` isn't
installed, which is common in server/CI/sandboxed environments, this
project's own dev environment included. No `tkinter` dependency at all.

Usage inside a cell body -- note there is no element name in any call,
matching the stdlib turtle API exactly so existing lesson code needs only
an import swap::

    from codeslides import turtle

    @app.cell(elements=[ui.turtle_canvas("canvas")])
    def draw():
        turtle.forward(100)
        turtle.right(90)
        turtle.forward(100)

This module's functions operate on a per-execution contextvar the kernel
establishes around each cell call (`execution_context()`), auto-targeting
the *one* `turtle_canvas` element on the currently-executing cell -- a
cell with zero or more than one such element is a configuration error,
since (unlike `cs.image`/`cs.iframe`) these calls have no way to name a
target themselves without breaking stdlib-compatible call syntax.
"""

from __future__ import annotations

import contextvars
import math
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _TurtleState:
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0  # degrees, 0 = pointing right (east), counterclockwise
    pen_down: bool = True
    pen_color: str = "black"
    fill_color: str = "black"
    pen_width: float = 1.0
    visible: bool = True
    speed: int = 6
    commands: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, op: str, **kwargs: Any) -> None:
        self.commands.append({"op": op, **kwargs})


_current: contextvars.ContextVar[_TurtleState | None] = contextvars.ContextVar(
    "codeslides_current_turtle", default=None
)


@contextmanager
def execution_context():
    """Kernel-internal: establishes fresh turtle state for the current
    cell's execution. Yields the recorded command list, for the kernel to
    package as `turtle_frame` content on the cell's `turtle_canvas`
    element -- same "collect during the call, apply only on success"
    shape as `cs.execution_context()`, so a failing cell never leaves a
    half-drawn frame behind."""
    state = _TurtleState()
    token = _current.set(state)
    try:
        yield state.commands
    finally:
        _current.reset(token)


def _state() -> _TurtleState:
    state = _current.get()
    if state is None:
        raise RuntimeError(
            "turtle functions called outside of cell execution -- codeslides.turtle "
            "only works inside a cell body while the kernel is running it, and the "
            "cell must have exactly one turtle_canvas element attached"
        )
    return state


# -- Motion -------------------------------------------------------------


def forward(distance: float) -> None:
    state = _state()
    radians = math.radians(state.heading)
    new_x = state.x + distance * math.cos(radians)
    new_y = state.y + distance * math.sin(radians)
    _move_to(state, new_x, new_y)


fd = forward


def backward(distance: float) -> None:
    forward(-distance)


bk = back = backward


def right(angle: float) -> None:
    state = _state()
    state.heading = (state.heading - angle) % 360
    state.emit("heading", heading=state.heading)


rt = right


def left(angle: float) -> None:
    right(-angle)


lt = left


def goto(x: float, y: float | None = None) -> None:
    state = _state()
    if y is None and isinstance(x, tuple):
        x, y = x
    _move_to(state, float(x), float(y))


setpos = setposition = goto


def setx(x: float) -> None:
    state = _state()
    _move_to(state, float(x), state.y)


def sety(y: float) -> None:
    state = _state()
    _move_to(state, state.x, float(y))


def setheading(angle: float) -> None:
    state = _state()
    state.heading = angle % 360
    state.emit("heading", heading=state.heading)


seth = setheading


def home() -> None:
    state = _state()
    _move_to(state, 0.0, 0.0)
    state.heading = 0.0
    state.emit("heading", heading=state.heading)


def circle(radius: float, extent: float = 360, steps: int | None = None) -> None:
    """Approximate a circle/arc as a series of short line segments, same
    strategy the real turtle module uses internally."""
    state = _state()
    steps = steps or max(int(abs(extent) / 6), 6)
    step_angle = extent / steps
    step_length = 2 * radius * math.sin(math.radians(step_angle) / 2) * (1 if radius >= 0 else -1)
    for _ in range(steps):
        forward(step_length)
        left(step_angle)
    _ = state  # state mutated via forward/left above


def _move_to(state: _TurtleState, x: float, y: float) -> None:
    state.emit(
        "goto",
        x=x,
        y=y,
        pen_down=state.pen_down,
        color=state.pen_color,
        width=state.pen_width,
    )
    state.x = x
    state.y = y


# -- Pen state ------------------------------------------------------------


def penup() -> None:
    state = _state()
    state.pen_down = False
    state.emit("pen", down=False)


pu = up = penup


def pendown() -> None:
    state = _state()
    state.pen_down = True
    state.emit("pen", down=True)


pd = down = pendown


def isdown() -> bool:
    return _state().pen_down


def pencolor(color: str | None = None) -> str | None:
    state = _state()
    if color is None:
        return state.pen_color
    state.pen_color = color
    state.emit("pencolor", color=color)
    return None


def fillcolor(color: str | None = None) -> str | None:
    state = _state()
    if color is None:
        return state.fill_color
    state.fill_color = color
    state.emit("fillcolor", color=color)
    return None


def color(pen_color: str | None = None, fill: str | None = None) -> tuple[str, str] | None:
    state = _state()
    if pen_color is None:
        return (state.pen_color, state.fill_color)
    pencolor(pen_color)
    fillcolor(fill if fill is not None else pen_color)
    return None


def pensize(width: float | None = None) -> float | None:
    state = _state()
    if width is None:
        return state.pen_width
    state.pen_width = width
    state.emit("pensize", width=width)
    return None


width = pensize


# -- Drawing marks ----------------------------------------------------------


def dot(size: float | None = None, color_: str | None = None) -> None:
    state = _state()
    state.emit(
        "dot",
        x=state.x,
        y=state.y,
        size=size or max(state.pen_width + 4, 8),
        color=color_ or state.pen_color,
    )


def stamp() -> None:
    state = _state()
    state.emit("stamp", x=state.x, y=state.y, heading=state.heading, color=state.pen_color)


def write(text: str, *, move: bool = False, align: str = "left", font: tuple | None = None) -> None:
    state = _state()
    state.emit("write", x=state.x, y=state.y, text=str(text), align=align)
    _ = move, font  # accepted for stdlib-signature compatibility, not yet used


def clear() -> None:
    state = _state()
    state.emit("clear")


def reset() -> None:
    state = _state()
    commands = state.commands
    commands.clear()
    fresh = _TurtleState(commands=commands)
    state.x, state.y = fresh.x, fresh.y
    state.heading = fresh.heading
    state.pen_down = fresh.pen_down
    state.pen_color = fresh.pen_color
    state.fill_color = fresh.fill_color
    state.pen_width = fresh.pen_width
    state.visible = fresh.visible
    state.speed = fresh.speed
    state.emit("clear")


# -- Visibility & speed -----------------------------------------------------


def hideturtle() -> None:
    state = _state()
    state.visible = False
    state.emit("visible", visible=False)


ht = hideturtle


def showturtle() -> None:
    state = _state()
    state.visible = True
    state.emit("visible", visible=True)


st = showturtle


def isvisible() -> bool:
    return _state().visible


def speed(value: int | str | None = None) -> int | None:
    state = _state()
    if value is None:
        return state.speed
    speeds = {"fastest": 0, "fast": 10, "normal": 6, "slow": 3, "slowest": 1}
    state.speed = speeds.get(value, value) if isinstance(value, str) else value
    return None


# -- Queries ------------------------------------------------------------


def position() -> tuple[float, float]:
    state = _state()
    return (state.x, state.y)


pos = position


def xcor() -> float:
    return _state().x


def ycor() -> float:
    return _state().y


def heading() -> float:
    return _state().heading


# -- Object-oriented handle ----------------------------------------------


class Turtle:
    """A `turtle.Turtle()` handle, for passing to another function as a
    parameter (`markCorners(cells, t)`) the way stdlib lesson code
    expects -- e.g. `t = turtle.Turtle()` in one cell/test box, then
    `t.goto(...)`/`t.stamp()` inside a function that receives `t`.

    Every method is the *same* module-level function above, bound as a
    `staticmethod` -- there is deliberately no independent per-instance
    x/y/heading/commands. All turtle state in this app lives on the one
    contextvar-based `_TurtleState` the kernel establishes per cell
    execution (`execution_context()`, scoped to that cell's single
    `turtle_canvas` element), never on a Python object, so a `Turtle()`
    instance is just a *view* onto whichever cell is currently
    executing when a method is actually called -- created in one cell,
    passed into another cell's function, its calls still draw onto the
    *calling* cell's own canvas. This also means two `Turtle()`
    instances used within the same cell execution share one position/
    heading/pen state, unlike independently-tracked turtles in real
    stdlib `turtle` -- there is exactly one turtle worth of state per
    cell execution here, not one per instance.

    Constructing `Turtle()` does nothing by itself (no validation, no
    implicit `reset()`/`clear()`) -- same as the module-level functions,
    the first method actually called raises the existing clear
    `RuntimeError` from `_state()` if there's no cell execution
    currently active.
    """

    forward = fd = staticmethod(forward)
    backward = bk = back = staticmethod(backward)
    right = rt = staticmethod(right)
    left = lt = staticmethod(left)
    goto = setpos = setposition = staticmethod(goto)
    setx = staticmethod(setx)
    sety = staticmethod(sety)
    setheading = seth = staticmethod(setheading)
    home = staticmethod(home)
    circle = staticmethod(circle)
    penup = pu = up = staticmethod(penup)
    pendown = pd = down = staticmethod(pendown)
    isdown = staticmethod(isdown)
    pencolor = staticmethod(pencolor)
    fillcolor = staticmethod(fillcolor)
    color = staticmethod(color)
    pensize = width = staticmethod(pensize)
    dot = staticmethod(dot)
    stamp = staticmethod(stamp)
    write = staticmethod(write)
    clear = staticmethod(clear)
    reset = staticmethod(reset)
    hideturtle = ht = staticmethod(hideturtle)
    showturtle = st = staticmethod(showturtle)
    isvisible = staticmethod(isvisible)
    speed = staticmethod(speed)
    position = pos = staticmethod(position)
    xcor = staticmethod(xcor)
    ycor = staticmethod(ycor)
    heading = staticmethod(heading)
