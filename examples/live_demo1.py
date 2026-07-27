"""Smoke-test deck exercising elements (sliders, turtle canvas, notes,
image/iframe viewers).

See TODO.md #13 for real teaching examples with full reactivity wired up.
"""

from codeslides import App, cs, turtle, ui

app = App()


@app.cell
def setup():
    base = 5
    return base


@app.cell
def explain():
    # cs.md() marks a cell's return value as markdown (ARCHITECTURE.md
    # section 6) -- rendered as formatted text instead of a plain repr.
    doc = cs.md(f"## Reactive dependency graph\n`base` is currently **{base}**.")  # noqa: F821
    return doc


@app.cell(instance="editable", elements=[ui.image("preview")])
def make_preview():
    # a small inline checkerboard PNG so this renders without depending on
    # an external file -- a real lesson would point cs.image() at a
    # matplotlib figure or a saved file path instead. Edit the code below
    # (e.g. swap the color) and press Shift+Enter to see the image update.
    swatch = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKAAAABkCAIAAACO1KzYAAABCUlEQVR42u3c"
        "sQkAMQwEQfWljt2k3YMMF4h5Pj/YSYXr9B3/P5/dzG4JDVhowEIDBgzYLmC7gO0CBiw0YKEBCw3YLmC7"
        "gO0CBiw0YKEBCw0YcBRYrN27gAELDVhowIAB2wVsF7BdwICFBiw0YKEB2wVsF7BdwICFBiw0YKEBA84C"
        "i+WqUmjAQgMGDNguYLuA7QIGLDRgoQELDdguYLuA7QIGLDRgoQELDRgwYLveybLrqtIuYMBCAxYasNCA"
        "7QK2C9guYMBCAxYasNCA7QK2C9guYMBCAxYasNDeyYLkqtIuYLuA7QIGLDRgoQELDdguYLuA7QIGLDRg"
        "oQELDRgwYLuA7QIGLPTq3Qfu4oAp8ZZdwwAAAABJRU5ErkJggg=="
    )
    cs.image("preview", swatch)
    return swatch


@app.cell(
    instance="editable",
    elements=[
        ui.slider("speed", min=1, max=10, default=3),
        ui.turtle_canvas("canvas", width=400, height=400),
        ui.notes("notes", default="# Live Coding\nWatch `speed` change the turtle's step size."),
    ],
)
def drawSquare(speed, location=(0, 0)):
    # `base` comes from the `setup` cell via the reactive dependency graph
    # (codeslides.graph.build_graph); ruff can't see that wiring, hence noqa.
    # `speed` scales the step size of a five-pointed star -- moving the
    # slider redraws it larger or smaller. The x5 keeps it comfortably
    # visible on the 400x400 canvas across the whole speed range (1-10):
    # a step size under ~20px is nearly invisible next to the turtle
    # marker itself.
    #
    # `location` has a default so this cell can still run standalone on
    # its own slide (driven only by the `speed` slider) -- but
    # `drawSquares` below also calls `drawSquare` directly with an
    # explicit `location` for each square, exactly like any two ordinary
    # Python functions in one module: a cell's own name is always bound
    # into the shared namespace as a callable (codeslides.graph treats a
    # cell's name as an implicit write of itself for exactly this reason).
    # When called this way, `drawSquare`'s turtle.forward/right calls draw
    # into whichever canvas is currently active -- `drawSquares`'s own, in
    # this case, since turtle drawing targets the *currently executing*
    # cell's canvas, not the canvas declared on whichever cell's code
    # happens to be running at the moment.
    step = base * speed * 5  # noqa: F821
    turtle.goto(location)
    for _ in range(4):
        turtle.forward(step)
        turtle.right(90)
    result = step
    return result

@app.cell(
    instance="editable",
    elements=[
        ui.turtle_canvas("canvas", width=400, height=400),
        ui.notes("notes", default="# Draw multiple squares\nCalls `drawSquare` once per location."),
    ],
)
def drawSquares(locations=((0, 0), (100, 0), (0, 100), (100, 100))):
    # `locations` has a default (a plain tuple of (x, y) pairs) since no
    # input element kind supports "a list of points" -- this cell is meant
    # to be run as a whole, not tuned one field at a time via the UI.
    # Fixed speed=3 here; drawSquare's own `speed` slider only applies
    # when drawSquare is run standalone on its own slide.
    for location in locations:
        drawSquare(3, location)


@app.slide("Setup", cells=["setup", "explain"])
def slide_1():
    """Base value computed once, shared by later slides. `explain` shows
    it back via cs.md() rich output."""


@app.slide("Image Preview", cells=["make_preview"])
def slide_2():
    """A cs.image() viewer, code hidden until revealed."""


@app.slide("Draw a square", cells=["drawSquare"], reveal_code=True)
def slide_3():
    """Instructor edits `drawSquare` live; slide reactively updates."""


@app.slide("Draw multiple squares", cells=["drawSquares"], reveal_code=True)
def slide_4():
    """`drawSquares` calls `drawSquare` directly, once per location --
    demonstrates a cell calling another cell's function."""
