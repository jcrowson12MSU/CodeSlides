"""Demonstrates the codeslides.turtle Screen support added in
docs/turtle-compatibility-todo.md's Phase 1 (TODO.md #62): setworldcoordinates,
bgcolor, and the accepted-no-op lifecycle calls (tracer/update/exitonclick/bye)
that let real, unmodified turtle scripts like examples/originalMarchingSquares.py
run here with just the import line swapped.
"""

from codeslides import App, cs, turtle, ui

app = App()


@app.cell
def intro():
    doc = cs.md(
        "## What's new: `turtle.Screen()`\n"
        "Before this upgrade, `turtle.Screen()` raised `AttributeError` "
        "immediately -- there was no `Screen` concept in `codeslides.turtle` "
        "at all. Nearly every real turtle script opens with "
        "`wn = turtle.Screen()`, so this was the single biggest blocker to "
        "running unmodified lesson code.\n\n"
        "This deck walks through what `Screen()` now supports, one slide "
        "at a time."
    )
    return doc


@app.cell(elements=[ui.turtle_canvas("default_canvas", width=400, height=400)])
def without_screen():
    """Baseline, no `Screen()` call at all -- the coordinate system
    every turtle cell has always used: origin at the canvas's center,
    one turtle unit equals one pixel, y increases upward. `right(72)`
    five times traces a five-pointed star."""
    star_turtle = turtle.Turtle()
    for _point in range(5):
        star_turtle.forward(80)
        star_turtle.right(144)


@app.cell(
    instance="editable",
    elements=[
        ui.slider("grid_size", min=4, max=24, default=12),
        ui.turtle_canvas("world_canvas", width=400, height=400),
        ui.notes("world_notes"),
    ],
)
def world_coordinates(grid_size):
    """`wn.setworldcoordinates(0, 0, grid_size, grid_size)` remaps the
    canvas so `(0, 0)` is the bottom-left corner and `(grid_size,
    grid_size)` is the top-right -- independently scaled per axis to
    fill the canvas edge to edge, matching real turtle's own
    non-aspect-preserving behavior. Move the slider and the whole grid
    rescales to still fill the canvas exactly, at any grid size.

    This is the exact pattern `examples/originalMarchingSquares.py`
    needs (`wn.setworldcoordinates(0, 0, cols, rows)` before drawing a
    grid of stamps) -- `wn.tracer(0)` is called too, right where a real
    script calls it, to show it's now a safe no-op rather than a
    missing attribute."""
    world_screen = turtle.Screen()
    world_screen.setworldcoordinates(0, 0, grid_size, grid_size)
    world_screen.tracer(0)

    grid_turtle = turtle.Turtle()
    grid_turtle.up()
    grid_turtle.hideturtle()

    for row in range(grid_size):
        for col in range(grid_size):
            grid_turtle.color("red" if (row + col) % 3 == 0 else "pink")
            grid_turtle.goto(col, row)
            grid_turtle.stamp()

    world_screen.update()


@app.cell(
    instance="editable",
    elements=[
        ui.text_input("background", default="lightyellow"),
        ui.turtle_canvas("bg_canvas", width=400, height=400),
    ],
)
def background_color(background):
    """`wn.bgcolor(...)` paints the canvas background before anything
    else is drawn -- try `"black"`, `"lightblue"`, or any CSS color
    name/hex code in the text box."""
    bg_screen = turtle.Screen()
    bg_screen.bgcolor(background)

    square_turtle = turtle.Turtle()
    square_turtle.color("white" if background == "black" else "black")
    square_turtle.up()
    square_turtle.goto(-100, 0)
    square_turtle.down()
    for _side in range(4):
        square_turtle.forward(200)
        square_turtle.right(90)


@app.cell(elements=[ui.turtle_canvas("lifecycle_canvas", width=300, height=300), ui.notes("lifecycle_notes")])
def lifecycle_calls():
    """`tracer(n)`, `update()`, `exitonclick()`, and `bye()` are all
    accepted as safe no-ops now, rather than raising `AttributeError`.

    `tracer(0)`/`update()` toggle/flush a per-step redraw mode real
    turtle uses -- this app already always redraws the complete,
    finished picture in one pass after a cell finishes running, so
    there's no separate mode to toggle (see
    docs/turtle-animation-feasibility.md for the full animation
    story). `exitonclick()`/`bye()` normally keep/close a window that
    doesn't exist here at all -- a cell's output is a static rendered
    canvas, not a blocking window, so both are simply no-ops.

    Try it: this cell's own body below calls all four, in the same
    order a real script typically would, right before drawing
    anything -- confirm it runs without error."""
    lifecycle_screen = turtle.Screen()
    lifecycle_screen.tracer(0)
    circle_turtle = turtle.Turtle()
    circle_turtle.circle(50)
    lifecycle_screen.update()
    lifecycle_screen.exitonclick()
    lifecycle_screen.bye()


@app.slide("Screen Upgrade", cells=["intro"])
def slide_intro():
    """Why Screen() support matters."""


@app.slide("Before: Default Coordinates", cells=["without_screen"])
def slide_before():
    """The coordinate system every turtle cell already had."""


@app.slide("setworldcoordinates()", cells=["world_coordinates"], reveal_code=True)
def slide_world():
    """Rescale the whole canvas to a custom coordinate system -- try the slider."""


@app.slide("bgcolor()", cells=["background_color"], reveal_code=True)
def slide_bg():
    """Paint the canvas background -- try the text box."""


@app.slide("Lifecycle No-ops", cells=["lifecycle_calls"], reveal_code=True)
def slide_lifecycle():
    """tracer/update/exitonclick/bye are all safe to call now."""
