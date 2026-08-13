"""Demonstrates the codeslides.turtle dot()/write(move=True) behavioral-parity
fixes added in docs/turtle-compatibility-todo.md's Phase 4 (TODO.md #62):
dot()'s real stdlib *color varargs signature, and write(move=True) actually
advancing the turtle instead of silently no-oping.
"""

from codeslides import App, cs, turtle, ui

app = App()


@app.cell
def intro():
    doc = cs.md(
        "## What's new: `dot()` and `write(move=True)`\n"
        "Before this upgrade, `dot()` only accepted a single positional "
        "color -- `dot(20, 255, 0, 0)` (real turtle's RGB-varargs form) "
        "raised a `TypeError`. And `write(..., move=True)` silently did "
        "nothing, so chaining `write()` calls to build up a line of text "
        "just overlapped everything at the same spot.\n\n"
        "This deck walks through both fixes, one slide at a time."
    )
    return doc


@app.cell(elements=[ui.turtle_canvas("dot_canvas", width=400, height=150), ui.notes("dot_notes")])
def dot_varargs():
    """Four different `dot()` call shapes, all now supported:
    `dot()` (default size/color), `dot(20, "red")` (explicit size and
    a color string), `dot("blue")` (a bare color, no size at all --
    also valid in real turtle), and `dot(20, 0, 200, 0)` (three
    separate RGB numbers as varargs, converted to a real CSS color)."""
    dot_turtle = turtle.Turtle()
    dot_turtle.up()
    dot_turtle.hideturtle()
    dot_turtle.goto(-135, 0)
    dot_turtle.dot()
    dot_turtle.goto(-45, 0)
    dot_turtle.dot(20, "red")
    dot_turtle.goto(45, 0)
    dot_turtle.dot("blue")
    dot_turtle.goto(135, 0)
    dot_turtle.dot(20, 0, 200, 0)
    dot_turtle.goto(1000, 1000)


@app.cell(
    instance="editable",
    elements=[
        ui.text_input("first_word", default="Score:"),
        ui.text_input("second_word", default="42"),
        ui.turtle_canvas("write_canvas", width=350, height=150),
        ui.notes("write_notes"),
    ],
)
def chained_write(first_word, second_word):
    """`write(text, move=True)` now moves the turtle to the drawn
    text's right edge, so a second `write()` call lands right after it
    instead of on top of it. Edit either text box -- the two words
    always stay side by side, never overlapping."""
    write_turtle = turtle.Turtle()
    write_turtle.up()
    write_turtle.hideturtle()
    write_turtle.goto(-150, 0)
    write_turtle.write(first_word + " ", move=True)
    write_turtle.write(second_word)
    write_turtle.goto(1000, 1000)


@app.cell(elements=[ui.turtle_canvas("gap_canvas", width=400, height=200), ui.notes("gap_notes")])
def the_one_remaining_gap():
    """An honest limitation, not a bug: `write(move=True)` estimates
    text width from character count, since this app has no way to
    measure real font metrics or ask the browser how wide text
    actually rendered. Under `setworldcoordinates(...)`, the
    pixel-to-turtle-unit scale depends on the canvas's actual on-screen
    size, which this Python code can't know -- so `move=True` is a
    deliberate no-op there instead of guessing wrong. The two words
    below overlap on purpose, to show this honestly rather than hide
    it."""
    gap_screen = turtle.Screen()
    gap_screen.setworldcoordinates(0, 0, 10, 10)
    gap_turtle = turtle.Turtle()
    gap_turtle.up()
    gap_turtle.hideturtle()
    gap_turtle.goto(2, 5)
    gap_turtle.write("Under", move=True)
    gap_turtle.write("Overlap!")
    gap_turtle.goto(1000, 1000)


@app.slide("dot()/write() Upgrade", cells=["intro"])
def slide_intro():
    """Why these two fixes matter."""


@app.slide("dot() Varargs", cells=["dot_varargs"], reveal_code=True)
def slide_dot():
    """Four dot() call shapes, all supported now."""


@app.slide("write(move=True)", cells=["chained_write"], reveal_code=True)
def slide_write():
    """Chained write() calls no longer overlap -- try the text boxes."""


@app.slide("The One Remaining Gap", cells=["the_one_remaining_gap"], reveal_code=True)
def slide_gap():
    """write(move=True) under setworldcoordinates is a deliberate no-op."""
