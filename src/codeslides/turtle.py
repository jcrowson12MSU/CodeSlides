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
    # Screen/window state (docs/turtle-compatibility-todo.md Phase 1) --
    # folded into the same per-cell-execution state as the turtle's own
    # motion/pen fields above, rather than a second parallel contextvar:
    # a cell has exactly one `turtle_canvas` element (ARCHITECTURE.md
    # section 7's "auto-targeting" design), so there is only ever one
    # screen worth of state to track per execution, same as there's only
    # one turtle's worth. `world_coords` is `None` until
    # `setworldcoordinates(...)` is called -- `None` means "use the
    # viewer's existing default mapping" (canvas-center-origin, 1 turtle
    # unit = 1 pixel), so a script that never calls it draws exactly as
    # it always has.
    world_coords: tuple[float, float, float, float] | None = None
    background_color: str = "white"
    # Appearance state (docs/turtle-compatibility-todo.md Phase 2) --
    # `"classic"` matches real stdlib turtle's own actual default cursor
    # shape (`_CFG["shape"]`, not the "arrow" a bare `shape()` query
    # happens to report on a never-configured turtle in some contexts)
    # and is also what this app's own `TurtleCanvasViewer.tsx` marker
    # already looked like before shapes existed at all -- so a script
    # that never calls `shape(...)` renders identically to before.
    shape_name: str = "classic"
    stretch_wid: float = 1.0  # perpendicular to heading (real turtle's own term for "width")
    stretch_len: float = 1.0  # along heading ("length")
    outline_width: float = 1.0
    # docs/turtle-compatibility-todo.md Phase 3: whether a
    # begin_fill()/end_fill() region is currently open. Purely a local
    # Python-side query flag for `filling()` -- the actual fill-path
    # (which points bound the filled region) is reconstructed by
    # `TurtleCanvasViewer.tsx` from the `goto` commands already emitted
    # between the `begin_fill`/`end_fill` markers, not tracked here, so
    # this module never needs its own polygon-accumulation logic.
    filling: bool = False
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


# -- Fill (docs/turtle-compatibility-todo.md Phase 3) ------------------------
#
# `begin_fill()`/`end_fill()` bracket a filled-shape's outline: every
# `goto` (directly, or via `forward`/`circle`/etc., all of which end up
# calling `_move_to` -> `goto`) between the two calls traces the
# region's boundary, and `end_fill()` paints the enclosed area in the
# turtle's current `fillcolor` -- matching real turtle's own semantics
# exactly (verified against the CPython source: `begin_fill` starts
# recording `_position` on every subsequent move, `end_fill` fills the
# accumulated polygon). This module only ever emits `begin_fill`/
# `end_fill` as markers in the command stream; it never accumulates the
# polygon's points itself -- `TurtleCanvasViewer.tsx` already replays
# every `goto` in order, so reconstructing "which points fell between
# these two markers" there avoids a second, parallel bookkeeping
# structure on the Python side that would need to stay in sync with the
# `goto` commands already being emitted for the pen stroke itself.


def begin_fill() -> None:
    """Idempotent, matching real turtle: calling this while already
    filling doesn't restart the region or emit a second marker (real
    turtle's own `if not self.filling(): ...` guard)."""
    state = _state()
    if state.filling:
        return
    state.filling = True
    state.emit("begin_fill", color=state.fill_color)


def end_fill() -> None:
    """Idempotent, matching real turtle: calling this while not
    currently filling is a safe no-op, not an error."""
    state = _state()
    if not state.filling:
        return
    state.filling = False
    state.emit("end_fill")


def filling() -> bool:
    return _state().filling


# -- Drawing marks ----------------------------------------------------------


def _color_to_css(value: Any) -> str:
    """Every other color-accepting function here takes a plain CSS
    color string and passes it straight through -- `dot()` is the one
    place real turtle also accepts a bare `(r, g, b)` numeric tuple
    (`dot(20, 255, 0, 0)`), which has no meaning to the browser's own
    CSS color parsing (`TurtleCanvasViewer.tsx`'s `ctx.fillStyle`)
    without conversion first. Deliberately does not implement real
    turtle's `colormode()`-dependent 0-1-vs-0-255 scaling -- `colormode`
    is already an accepted no-op (Phase 1, `Screen`), so this always
    assumes the common 0-255 scale, matching the vast majority of real
    lesson code that calls this at all."""
    if isinstance(value, str):
        return value
    r, g, b = value
    return f"rgb({r}, {g}, {b})"


def dot(size: float | str | None = None, *color: Any) -> None:
    """Matches real turtle's own `dot(size=None, *color)` signature
    (verified against the CPython source), not just the common
    `dot(size, "colorname")` shape: a lone string/tuple positional with
    no `size` at all is also valid (`dot("red")`), and `color` can be
    three separate RGB numbers (`dot(20, 255, 0, 0)`) as well as one
    color string/tuple (`dot(20, "red")`) -- `*color` is a real varargs
    tuple in both call shapes, not a single positional.

    Default size when none is given matches real turtle's own formula
    exactly (`pensize + max(pensize, 4)`, verified against the CPython
    source) -- the shim's previous `max(pen_width + 4, 8)` computed a
    different value for the common pensize=1 case (8 instead of 5)."""
    state = _state()
    default_size = state.pen_width + max(state.pen_width, 4)
    if not color:
        if isinstance(size, (str, tuple)):
            dot_color = size
            dot_size = default_size
        else:
            dot_color = state.pen_color
            dot_size = size if size else default_size
    else:
        dot_size = size if size is not None else default_size
        dot_color = color[0] if len(color) == 1 else color
    state.emit("dot", x=state.x, y=state.y, size=dot_size, color=_color_to_css(dot_color))


def stamp() -> None:
    state = _state()
    state.emit(
        "stamp",
        x=state.x,
        y=state.y,
        heading=state.heading,
        color=state.pen_color,
        shape=state.shape_name,
        stretch_wid=state.stretch_wid,
        stretch_len=state.stretch_len,
        outline=state.outline_width,
    )


_APPROX_PIXELS_PER_CHAR = 7  # calibrated to TurtleCanvasViewer.tsx's fixed "12px sans-serif"


def write(text: str, *, move: bool = False, align: str = "left", font: tuple | None = None) -> None:
    """`move=True` moves the turtle to the drawn text's right edge (real
    turtle's own semantics -- verified against the CPython source),
    approximated here rather than measured exactly: real turtle asks
    Tk's actual font-rendering engine for the text's real pixel
    bounding box, which this app has no equivalent of -- rendering
    happens entirely client-side (`TurtleCanvasViewer.tsx`) and there's
    no round trip back into an already-finished, synchronous cell
    execution to ask the browser how wide the text actually came out.
    `_APPROX_PIXELS_PER_CHAR` is a simple average-character-width
    estimate calibrated to the viewer's fixed `"12px sans-serif"` font
    -- close enough for `move=True`'s common real use (chaining
    `write()` calls to build up a line of text) without needing true
    font metrics.

    Only estimated when there's no active `setworldcoordinates(...)`
    (Phase 1): the pixel-to-turtle-unit scale factor in that case
    depends on the `turtle_canvas` element's actual on-screen
    width/height, which only the frontend knows -- this module can't
    convert a pixel-width estimate into the right number of turtle
    units without it. Silently leaving the turtle in place in that one
    case (same as this function's behavior everywhere before this fix)
    was judged less misleading than moving it to a confidently wrong
    position; `move=True` under `setworldcoordinates` is the one
    remaining honest gap here, not a further approximation."""
    state = _state()
    state.emit("write", x=state.x, y=state.y, text=str(text), align=align)
    if move and state.world_coords is None:
        # Matches real turtle's own anchor-point semantics (its own
        # canvas anchor mapping -- "left"->sw, "center"->s, "right"->se
        # -- confirms "right" already anchors text at its own right
        # edge, so there's nothing further to move for that case).
        approx_width = len(str(text)) * _APPROX_PIXELS_PER_CHAR
        if align == "center":
            approx_width /= 2
        elif align == "right":
            approx_width = 0
        _move_to(state, state.x + approx_width, state.y)
    _ = font  # accepted for stdlib-signature compatibility, not yet used


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
    # Stretch/outline reset matches real turtle's own `TPen._reset`
    # (verified against the CPython source) -- a real, pre-existing gap
    # caught while touching this function again for Phase 3: shapesize
    # (Phase 2) added these fields but never wired them into reset().
    # `shape_name` itself is deliberately NOT reset here, matching real
    # turtle: shape lives on a separate object (`self.turtle`) `_reset`
    # never touches.
    state.stretch_wid = fresh.stretch_wid
    state.stretch_len = fresh.stretch_len
    state.outline_width = fresh.outline_width
    # An in-progress fill is aborted by a reset, matching real turtle's
    # own `_clear()` (`self._fillitem = self._fillpath = None`) --
    # verified against the CPython source.
    state.filling = fresh.filling
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


# -- Appearance (docs/turtle-compatibility-todo.md Phase 2) -----------------
#
# `shape`/`shapesize` change how the turtle's own cursor (drawn at its
# current position/heading, and by `stamp()`) looks -- pure appearance
# state, same category as `pencolor`/`pensize` above, with no effect on
# motion. Emitted as a `shape` command (mirroring how `heading`/
# `pencolor`/`visible` already track state changes into the command
# stream) so `TurtleCanvasViewer.tsx`'s replay can pick up the latest
# shape/stretch for both `stamp` and the final "here's where the turtle
# ended up" marker drawn after replay.

_SHAPE_NAMES = frozenset({"arrow", "turtle", "circle", "square", "triangle", "classic"})


def shape(name: str | None = None) -> str | None:
    """Set/query the turtle's cursor shape. Matches real turtle's own
    validation: an unknown name raises rather than silently doing
    nothing -- real turtle validates against `screen.getshapes()`
    (unsupported here, see `Screen`'s docstring on its event/registry
    methods), so this validates against the same fixed built-in set
    every stdlib turtle installation ships with instead."""
    state = _state()
    if name is None:
        return state.shape_name
    if name not in _SHAPE_NAMES:
        raise ValueError(f"there is no shape named {name!r} -- expected one of {sorted(_SHAPE_NAMES)}")
    state.shape_name = name
    _emit_shape(state)
    return None


def shapesize(
    stretch_wid: float | None = None, stretch_len: float | None = None, outline: float | None = None
) -> tuple[float, float, float] | None:
    """Set/query the turtle's cursor stretch factors and outline width.
    Mirrors real turtle's own defaulting exactly (verified against the
    stdlib source): querying with all three args `None` returns the
    current `(stretch_wid, stretch_len, outline)`; giving only
    `stretch_wid` stretches both axes uniformly (`stretch_len` defaults
    to match it); giving only `stretch_len` leaves the existing
    `stretch_wid` alone; `outline`, if given, is independent of
    stretching, applied on top of whichever combination of the above."""
    state = _state()
    if stretch_wid is None and stretch_len is None and outline is None:
        return (state.stretch_wid, state.stretch_len, state.outline_width)
    if stretch_wid == 0 or stretch_len == 0:
        raise ValueError("stretch_wid/stretch_len must not be zero")
    if stretch_wid is not None:
        state.stretch_wid = stretch_wid
        state.stretch_len = stretch_len if stretch_len is not None else stretch_wid
    elif stretch_len is not None:
        state.stretch_len = stretch_len
    if outline is not None:
        state.outline_width = outline
    _emit_shape(state)
    return None


def _emit_shape(state: _TurtleState) -> None:
    """Shared by `shape`/`shapesize`: always emits the *complete*
    current appearance state (name + both stretch factors + outline),
    never just whichever field one particular call changed -- so the
    frontend replay can take the latest `shape` command's fields
    wholesale for both `stamp` and the final position marker, instead
    of needing to merge partial updates across multiple commands the
    way it already has to avoid for `heading`/`pencolor`."""
    state.emit(
        "shape",
        name=state.shape_name,
        stretch_wid=state.stretch_wid,
        stretch_len=state.stretch_len,
        outline=state.outline_width,
    )


# -- Screen (docs/turtle-compatibility-todo.md Phase 1) ---------------------
#
# Real stdlib turtle splits `Turtle` (one cursor's motion/pen/appearance)
# from `Screen`/`TurtleScreen` (the drawing window: coordinate system,
# redraw timing, background, window lifecycle). This module previously
# had no `Screen` concept at all -- `turtle.Screen()` raised
# `AttributeError` immediately, which is the single most common way a
# real, unmodified turtle script failed to run here at all (nearly
# every real-world script opens with `wn = turtle.Screen()`).
#
# These are module-level functions, same shape as every motion/pen
# function above -- `Screen()` at the bottom returns a thin object whose
# methods just call these, the same relationship `Turtle` already has to
# the motion functions, so `turtle.Screen()` and `wn.tracer(0)` work
# exactly like `turtle.Turtle()` and `t.forward(100)` do.


def setworldcoordinates(llx: float, lly: float, urx: float, ury: float) -> None:
    """Establish a user coordinate system: `(llx, lly)` maps to the
    canvas's bottom-left corner, `(urx, ury)` to its top-right --
    independently scaled per axis to fit the canvas's actual pixel
    dimensions (matching real turtle: this does NOT preserve aspect
    ratio, verified against the stdlib source). Recorded as a command
    (not just local Python-side state) because the actual pixel-space
    scale factors depend on the `turtle_canvas` element's own
    width/height, which only the frontend (`TurtleCanvasViewer.tsx`)
    knows -- the emitted command carries just the four world-space
    bounds, and every position the frontend replays afterward
    (`goto`/`dot`/`stamp`/...) gets mapped through them there. Real
    turtle also resets the whole screen and switches to "world" mode as
    a side effect (`self.mode("world")`, `self.update()`) -- not
    replicated here, since this app has no other coordinate "mode" to
    switch away from and no separate reset-vs-redraw step (a cell
    re-run already redraws everything from scratch)."""
    state = _state()
    state.world_coords = (llx, lly, urx, ury)
    state.emit("setworldcoordinates", llx=llx, lly=lly, urx=urx, ury=ury)


def tracer(n: int | None = None, delay: int | None = None) -> int | None:
    """Real turtle's `tracer(0)` disables per-step screen updates
    (redraw only on `update()`) for faster batch drawing; `tracer(1)`
    (the default) redraws after every command. This app's rendering is
    already unconditionally the `tracer(0)` behavior -- a cell runs to
    completion, then the *entire* finished command list is sent and
    replayed in one pass (see `docs/turtle-animation-feasibility.md`) --
    so there is no per-step redraw mode to actually toggle. Accepted
    as a no-op (not raising) purely so scripts that call it don't break
    on an otherwise load-bearing-only-in-real-turtle line; `delay` is
    accepted for the same signature-compatibility reason and also
    unused. Returns `None` regardless of `n`, since there's no
    meaningful "current tracer state" to report back (real turtle
    returns the last-set value; nothing here depends on that return
    value being accurate, only on the call not raising)."""
    _state()  # still requires an active cell execution, same as every other call
    _ = n, delay


def update() -> None:
    """Real turtle's `update()` forces a screen redraw when `tracer(0)`
    has suppressed automatic ones. A no-op here for the same reason
    `tracer` is: this app already redraws the complete, finished
    picture in one pass after the cell returns, so there's no pending
    partial frame for `update()` to flush."""
    _state()


def bgcolor(color: str | None = None) -> str | None:
    state = _state()
    if color is None:
        return state.background_color
    state.background_color = color
    state.emit("bgcolor", color=color)
    return None


def screensize(canvwidth: int | None = None, canvheight: int | None = None, bg: str | None = None) -> tuple[int, int] | None:
    """Real turtle's `screensize` resizes the *scrollable drawing
    region* (which can be larger than the visible window, with
    scrollbars) -- there is no scrolling concept in this app's fixed-
    size `turtle_canvas` element, so this is accepted for signature
    compatibility but doesn't resize anything. `bg`, if given, still
    sets the background color (real turtle documents this as
    equivalent to a `bgcolor()` call), since that part has real
    meaning here."""
    _state()
    if bg is not None:
        bgcolor(bg)
    _ = canvwidth, canvheight
    return None


def colormode(cmode: float | None = None) -> float | None:
    """Real turtle's `colormode` toggles between `1.0`-scaled and
    `255`-scaled RGB tuple color values. This shim's colors are always
    passed straight through to the browser's own CSS color parsing
    (`TurtleCanvasViewer.tsx`'s `ctx.fillStyle`/`strokeStyle`), which
    already accepts `"red"`, `"#ff0000"`, `"rgb(255,0,0)"`, etc.
    directly -- there's no intermediate numeric-tuple color
    representation here for a color *mode* to apply to, so this is
    accepted for signature compatibility only."""
    _state()
    _ = cmode
    return None


def exitonclick() -> None:
    """Real turtle's `exitonclick()` blocks until the user clicks the
    window, then closes it -- typically the very last line of a script,
    keeping the window open until dismissed. A CodeSlides cell has no
    window to keep open or close (its output is a static, already-
    rendered canvas in the browser, not a blocking Tk event loop) --
    so this is an explicit, intentional no-op, not a missing feature:
    the closest real-world equivalent behavior (leave the finished
    drawing on screen) is already exactly what happens without this
    call doing anything at all."""
    _state()


def bye() -> None:
    """Real turtle's `bye()` closes the turtle window immediately. Same
    reasoning as `exitonclick()`: no window exists here to close, so
    this is an intentional no-op."""
    _state()


_UNSUPPORTED_SCREEN_EVENT_METHODS = (
    "onclick",
    "onkey",
    "onkeypress",
    "ontimer",
    "listen",
    "register_shape",
    "getshapes",
)


def _unsupported_screen_event_method(name: str):
    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError(
            f"turtle.Screen().{name}(...) is not supported -- codeslides.turtle's cells run "
            "once, synchronously, to completion and then render a finished picture; there is "
            "no persistent event loop for a keyboard/mouse/timer callback to run against "
            "later (see docs/turtle-compatibility-todo.md's Gap 4). This is a deliberate "
            "scope boundary, not an oversight: registering a callback that silently never "
            "fires would be worse than this clear error."
        )

    _raise.__name__ = name
    return _raise


for _name in _UNSUPPORTED_SCREEN_EVENT_METHODS:
    globals()[_name] = _unsupported_screen_event_method(_name)
del _name


class _Screen:
    """A `turtle.Screen()`/`wn = turtle.Screen()` handle -- mirrors
    `Turtle`'s own shape (see that class's docstring): every method is
    the same module-level function above, bound as a `staticmethod`,
    operating on the one screen's worth of state folded into the
    currently-executing cell's `_TurtleState` (there is exactly one
    `turtle_canvas` element per cell, so exactly one screen, the same
    "auto-targeting" design `Turtle` already relies on). Constructing
    `_Screen()` does nothing by itself, same as `Turtle()` -- the first
    method actually called raises the existing `RuntimeError` from
    `_state()` if there's no active cell execution.

    Named `_Screen`, not `Screen`, for the exact same reason real
    stdlib turtle does this too: `Screen()` below is the actual public
    factory function callers use (`turtle.Screen()`), so the class
    itself needs a different name to avoid the function shadowing its
    own return type."""

    setworldcoordinates = staticmethod(setworldcoordinates)
    tracer = staticmethod(tracer)
    update = staticmethod(update)
    bgcolor = staticmethod(bgcolor)
    screensize = staticmethod(screensize)
    colormode = staticmethod(colormode)
    exitonclick = staticmethod(exitonclick)
    bye = staticmethod(bye)
    onclick = staticmethod(globals()["onclick"])
    onkey = staticmethod(globals()["onkey"])
    onkeypress = staticmethod(globals()["onkeypress"])
    ontimer = staticmethod(globals()["ontimer"])
    listen = staticmethod(globals()["listen"])
    register_shape = staticmethod(globals()["register_shape"])
    getshapes = staticmethod(globals()["getshapes"])


def Screen() -> _Screen:  # matches stdlib turtle's own Screen() factory name exactly
    """`turtle.Screen()` -- returns a handle onto the current cell
    execution's one screen's worth of state, same relationship
    `turtle.Turtle()` already has to `Turtle`. Real stdlib `Screen()` is
    a singleton factory (repeated calls return the same window object);
    there is no equivalent "the same object" concept to preserve here
    since every `Screen()` call within one cell execution already
    operates on the same single `_TurtleState`, singleton or not."""
    _state()  # requires an active cell execution, same as every other call
    return _Screen()


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
    begin_fill = staticmethod(begin_fill)
    end_fill = staticmethod(end_fill)
    filling = staticmethod(filling)
    dot = staticmethod(dot)
    stamp = staticmethod(stamp)
    write = staticmethod(write)
    clear = staticmethod(clear)
    reset = staticmethod(reset)
    hideturtle = ht = staticmethod(hideturtle)
    showturtle = st = staticmethod(showturtle)
    isvisible = staticmethod(isvisible)
    speed = staticmethod(speed)
    shape = staticmethod(shape)
    shapesize = staticmethod(shapesize)
    position = pos = staticmethod(position)
    xcor = staticmethod(xcor)
    ycor = staticmethod(ycor)
    heading = staticmethod(heading)
