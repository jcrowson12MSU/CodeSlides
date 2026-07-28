"""Example deck demonstrating ui.tests(...) -- a second, unittest-like
code editor attached to a cell (ARCHITECTURE.md section 3b). See
TODO.md #15 for the full feature writeup.
"""

from codeslides import App, cs, ui

app = App()


@app.cell
def explain():
    doc = cs.md(
        "## `ui.tests(...)`: check a cell's code as you edit it\n\n"
        "Attach a second code editor to any cell with "
        "`ui.tests(\"name\", default=\"...\")` in its `elements=[...]` list. "
        "That editor holds plain Python `assert` statements -- not a "
        "`unittest.TestCase`, just the lightest possible check -- and it "
        "runs automatically every time the cell itself re-runs: editing "
        "the code, moving a bound slider, clicking `run_all`.\n\n"
        "**What the test can see.** It runs with access to the cell's own "
        "return-named values, plus anything upstream cells wrote -- exactly "
        "the same names the cell's own body could read. No imports needed "
        "for those; `cs` and `turtle` are also available automatically, "
        "same as in a regular cell.\n\n"
        "**Pass, fail, or error.** A green **PASS** badge means every "
        "statement ran with no exception. A failed `assert` shows a red "
        "**FAIL** badge with the assertion message. Anything else -- a "
        "typo, a `NameError` -- shows an amber **ERROR** badge instead, so "
        "you can tell \"my code is wrong\" apart from \"my test doesn't "
        "even run.\"\n\n"
        "**Editing the test never re-runs the cell.** You can fix up the "
        "test code on its own and see the badge update instantly, without "
        "the cell itself executing again -- it's checked against whatever "
        "the cell's last run already produced.\n\n"
        "**Turtle drawings too.** If the cell has a `turtle_canvas`, test "
        "code can call `turtle.forward(...)` etc. and see the result drawn "
        "onto that same canvas -- a scratch space to try out turtle logic "
        "without touching the cell's own code. See the `draw_square` cell "
        "below."
    )
    return doc


@app.cell
def setup():
    base = 5
    return base


@app.cell(
    instance="editable",
    elements=[
        ui.slider("speed", min=1, max=10, default=3),
        ui.tests("unit", default="assert result == 15"),
    ],
)
def live_demo(speed):
    # `base` comes from the `setup` cell via the reactive dependency graph;
    # ruff can't see that wiring, hence noqa below. Try dragging `speed` --
    # the `unit` test re-checks `result == 15` automatically and flips to a
    # red FAIL badge once speed != 3, since 5 * 3 == 15 only holds there.
    # Edit the test itself (e.g. `assert result == base * speed`) to make
    # it pass at every speed instead.
    result = base * speed  # noqa: F821
    return result


@app.cell(
    elements=[
        ui.turtle_canvas("canvas", width=400, height=400),
        ui.tests(
            "unit",
            default="turtle.forward(100)\nturtle.right(90)\nturtle.forward(100)",
        ),
    ],
)
def draw_square():
    # This cell's own body draws nothing -- the `unit` test's turtle calls
    # are what you see on the canvas. Edit the test code (e.g. add two
    # more forward/right pairs to close the square) and watch the canvas
    # redraw immediately, with no effect on the cell's own (empty) body.
    pass


@app.slide("Using ui.tests", cells=["explain"])
def slide_1():
    """What ui.tests(...) does and how to use it."""


@app.slide("Live Demo: a passing/failing assertion", cells=["live_demo"], reveal_code=True)
def slide_2():
    """Drag speed; watch the unit test's badge flip between pass and fail."""


@app.slide("Live Demo: turtle calls from a test", cells=["draw_square"], reveal_code=True)
def slide_3():
    """Edit the test code; the canvas redraws from the test, not the cell."""
