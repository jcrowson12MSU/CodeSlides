"""Smoke-test deck exercising elements (sliders, turtle canvas, notes).

See TODO.md #13 for real teaching examples with full reactivity wired up.
"""

from codeslides import App, ui

app = App()


@app.cell
def setup():
    base = 5
    return base


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
    # (TODO.md #3) -- not yet resolvable by static tools until the kernel
    # (TODO.md #4) actually wires cross-cell namespaces together.
    result = base * speed  # noqa: F821
    return result


@app.slide("Live Coding", cells=["live_demo"], reveal_code=True)
def slide_1():
    """Instructor edits `live_demo` live; slide reactively updates."""
