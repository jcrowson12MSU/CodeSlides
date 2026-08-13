"""Demonstrates the codeslides.turtle begin_fill()/end_fill()/filling() support
added in docs/turtle-compatibility-todo.md's Phase 3 (TODO.md #62):
standard-curriculum filled-shape drawing (stars, flowers, filled polygons).
"""

from codeslides import App, cs, turtle, ui

app = App()


@app.cell
def intro():
    doc = cs.md(
        "## What's new: `begin_fill()` and `end_fill()`\n"
        "Before this upgrade, `fillcolor(...)` did nothing on its own -- "
        "there was no way to actually fill a shape. Real turtle scripts "
        "bracket a shape's outline with `begin_fill()`/`end_fill()` to "
        "fill it (stars, flowers, filled polygons are standard-curriculum "
        "turtle content).\n\n"
        "This deck walks through both, one slide at a time."
    )
    return doc


@app.cell(elements=[ui.turtle_canvas("star_canvas", width=300, height=300)])
def filled_star():
    """`begin_fill()` starts recording every point the turtle visits;
    `end_fill()` closes the shape and paints the enclosed region in the
    current `fillcolor` -- here, gold, with a black outline."""
    star_turtle = turtle.Turtle()
    star_turtle.up()
    star_turtle.color("black", "gold")
    star_turtle.begin_fill()
    for _point in range(5):
        star_turtle.forward(150)
        star_turtle.right(144)
    star_turtle.end_fill()
    # Moved off-canvas afterward so the turtle's own current-position
    # marker doesn't draw on top of the finished shape.
    star_turtle.goto(1000, 1000)


@app.cell(
    instance="editable",
    elements=[
        ui.text_input("fill_color", default="lightblue"),
        ui.turtle_canvas("circle_canvas", width=300, height=300),
        ui.notes("circle_notes"),
    ],
)
def filled_circle(fill_color):
    """`circle()` moves the turtle in short internal steps -- fill isn't
    special-cased to only work with direct `goto` calls, it works with
    anything that moves the turtle while filling is active. Try any CSS
    color name in the text box."""
    circle_turtle = turtle.Turtle()
    circle_turtle.up()
    circle_turtle.color("darkblue", fill_color)
    circle_turtle.goto(0, -80)
    circle_turtle.begin_fill()
    circle_turtle.circle(80)
    circle_turtle.end_fill()
    circle_turtle.goto(1000, 1000)


@app.cell(elements=[ui.turtle_canvas("compare_canvas", width=400, height=250), ui.notes("compare_notes")])
def fillcolor_alone_does_nothing():
    """The square on the left only calls `fillcolor("crimson")` -- no
    `begin_fill()`/`end_fill()` -- and stays unfilled, exactly as
    before this upgrade. The square on the right is identical except
    for the fill calls. `fillcolor(...)` alone was never enough."""
    left_turtle = turtle.Turtle()
    left_turtle.up()
    left_turtle.color("black", "crimson")
    left_turtle.goto(-150, -50)
    left_turtle.down()
    for _side in range(4):
        left_turtle.forward(100)
        left_turtle.right(90)
    left_turtle.up()

    right_turtle = turtle.Turtle()
    right_turtle.up()
    right_turtle.color("black", "crimson")
    right_turtle.goto(50, -50)
    right_turtle.down()
    right_turtle.begin_fill()
    for _side in range(4):
        right_turtle.forward(100)
        right_turtle.right(90)
    right_turtle.end_fill()
    right_turtle.up()

    left_turtle.goto(1000, 1000)
    right_turtle.goto(1000, 1000)


@app.slide("Fill Upgrade", cells=["intro"])
def slide_intro():
    """Why begin_fill()/end_fill() support matters."""


@app.slide("Filled Star", cells=["filled_star"], reveal_code=True)
def slide_star():
    """The classic begin_fill()/end_fill() example."""


@app.slide("Filled Circle", cells=["filled_circle"], reveal_code=True)
def slide_circle():
    """Fill works through circle()'s internal steps too -- try the color box."""


@app.slide("fillcolor() Alone Does Nothing", cells=["fillcolor_alone_does_nothing"], reveal_code=True)
def slide_compare():
    """Side by side: unfilled vs. filled, same fillcolor() call."""
