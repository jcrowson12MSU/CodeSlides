"""Demonstrates the codeslides.turtle shape()/shapesize() support added in
docs/turtle-compatibility-todo.md's Phase 2 (TODO.md #62): six built-in cursor
shapes and heading-relative stretch/outline, the last calls
examples/originalMarchingSquares.py's setup needed to run here unmodified.
"""

from codeslides import App, cs, turtle, ui

app = App()


@app.cell
def intro():
    doc = cs.md(
        "## What's new: `shape()` and `shapesize()`\n"
        "Before this upgrade, every turtle cursor looked the same -- a "
        "fixed triangular marker, with no way to change it. Real turtle "
        "scripts routinely call `t.shape(\"circle\")` (exactly what "
        "`examples/originalMarchingSquares.py` does) to swap the cursor, "
        "and `t.shapesize(...)` to stretch it.\n\n"
        "This deck walks through both, one slide at a time."
    )
    return doc


@app.cell(elements=[ui.turtle_canvas("shapes_canvas", width=400, height=150)])
def all_shapes():
    """`shape(name)` accepts six built-in names -- the same set every
    stdlib turtle installation ships with: `"arrow"`, `"turtle"`,
    `"circle"`, `"square"`, `"triangle"`, `"classic"` (the default,
    and what this app's cursor always looked like before this
    upgrade). Each stamp below uses a different one."""
    shape_names = ["arrow", "turtle", "circle", "square", "triangle", "classic"]
    row_turtle = turtle.Turtle()
    row_turtle.up()
    row_turtle.color("darkblue")
    for index, name in enumerate(shape_names):
        row_turtle.goto(-125 + index * 50, 0)
        row_turtle.shape(name)
        row_turtle.stamp()
    row_turtle.hideturtle()


@app.cell(
    instance="editable",
    elements=[
        ui.slider("stretch_wid", min=1, max=5, default=1),
        ui.slider("stretch_len", min=1, max=5, default=1),
        ui.turtle_canvas("stretch_canvas", width=300, height=300),
        ui.notes("stretch_notes"),
    ],
)
def stretch_shape(stretch_wid, stretch_len):
    """`shapesize(stretch_wid, stretch_len)` scales the cursor --
    `stretch_wid` perpendicular to the turtle's heading, `stretch_len`
    along it. Move the sliders independently: `stretch_len` stretches
    the square lengthwise (in the direction it's facing), `stretch_wid`
    stretches it sideways."""
    stretch_turtle = turtle.Turtle()
    stretch_turtle.up()
    stretch_turtle.shape("square")
    stretch_turtle.color("crimson")
    stretch_turtle.shapesize(stretch_wid, stretch_len)
    stretch_turtle.stamp()
    # Moved off-canvas after stamping (rather than hideturtle()) so the
    # turtle's own current-position marker doesn't draw right on top of
    # the stamp -- both would otherwise land at the exact same spot.
    stretch_turtle.goto(1000, 1000)


@app.cell(
    instance="editable",
    elements=[
        ui.slider("angle", min=0, max=345, default=0),
        ui.turtle_canvas("heading_canvas", width=300, height=300),
        ui.notes("heading_notes"),
    ],
)
def stretch_follows_heading(angle):
    """The stretch is relative to the turtle's own heading, not the
    screen -- turn the turtle with the slider and the stretched arrow
    rotates with it, always elongated in the direction it's pointing."""
    heading_turtle = turtle.Turtle()
    heading_turtle.up()
    heading_turtle.shape("arrow")
    heading_turtle.color("seagreen")
    heading_turtle.shapesize(1, 3)
    heading_turtle.setheading(angle)
    heading_turtle.stamp()
    # Moved off-canvas after stamping, same reason as stretch_shape
    # above -- the current-position marker would otherwise draw right
    # on top of the stamp in the wrong (fixed, non-seagreen) color.
    heading_turtle.goto(1000, 1000)


@app.slide("Shape Upgrade", cells=["intro"])
def slide_intro():
    """Why shape()/shapesize() support matters."""


@app.slide("shape()", cells=["all_shapes"], reveal_code=True)
def slide_shapes():
    """Six built-in cursor shapes, side by side."""


@app.slide("shapesize()", cells=["stretch_shape"], reveal_code=True)
def slide_stretch():
    """Stretch the cursor independently along each axis -- try the sliders."""


@app.slide("Stretch Follows Heading", cells=["stretch_follows_heading"], reveal_code=True)
def slide_heading():
    """The stretch rotates with the turtle -- try the angle slider."""
