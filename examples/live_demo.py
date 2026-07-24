"""Smoke-test deck exercising elements (sliders, turtle canvas, notes,
image/iframe viewers).

See TODO.md #13 for real teaching examples with full reactivity wired up.
"""

from codeslides import App, cs, ui

app = App()


@app.cell
def setup():
    base = 5
    return base


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
        ui.notes("notes", default="# Live Coding\nWatch `speed` change the turtle."),
    ],
)
def live_demo(speed):
    # `base` comes from the `setup` cell via the reactive dependency graph
    # (codeslides.graph.build_graph); ruff can't see that wiring, hence noqa.
    result = base * speed  # noqa: F821
    return result


@app.slide("Live Coding", cells=["live_demo"], reveal_code=True)
def slide_1():
    """Instructor edits `live_demo` live; slide reactively updates."""
