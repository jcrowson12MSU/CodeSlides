"""Demonstrates the codeslides.turtle distance()/towards() support added
in docs/turtle-compatibility-todo.md's Phase 5 (TODO.md #62): the remaining
lower-priority Turtle methods this phase specifically scoped.
"""

from codeslides import App, cs, turtle, ui

app = App()


@app.cell
def intro():
    doc = cs.md(
        "## What's new: `distance()` and `towards()`\n"
        "Before this upgrade, neither existed -- calling either raised "
        "`AttributeError`. Real turtle lessons use them for chasing/"
        "following behavior: `towards(x, y)` returns the angle to aim "
        "at a point, `distance(x, y)` returns how far away it is.\n\n"
        "This deck walks through both, one slide at a time."
    )
    return doc


@app.cell(
    instance="editable",
    elements=[
        ui.slider("target_x", min=-100, max=100, default=80),
        ui.slider("target_y", min=-100, max=100, default=60),
        ui.turtle_canvas("distance_canvas", width=300, height=300),
        ui.notes("distance_notes"),
    ],
)
def measure_distance(target_x, target_y):
    """`distance(x, y)` returns how far the turtle is from a point, in
    turtle step units -- move the sliders and watch the printed number
    change."""
    measure_turtle = turtle.Turtle()
    measure_turtle.up()
    measure_turtle.goto(0, 0)
    measure_turtle.dot(8, "black")
    measure_turtle.goto(target_x, target_y)
    measure_turtle.dot(10, "crimson")
    measured_distance = measure_turtle.distance(0, 0)
    measure_turtle.write(f"  distance = {measured_distance:.1f}")
    measure_turtle.goto(1000, 1000)


@app.cell(
    instance="editable",
    elements=[
        ui.slider("aim_x", min=-100, max=100, default=-70),
        ui.slider("aim_y", min=-100, max=100, default=50),
        ui.turtle_canvas("towards_canvas", width=300, height=300),
        ui.notes("towards_notes"),
    ],
)
def aim_and_travel(aim_x, aim_y):
    """`towards(x, y)` returns the angle to point at a target -- combined
    with `distance()`, a turtle can aim itself and travel exactly far
    enough to arrive. Move the sliders and the line always ends exactly
    on the target dot."""
    chaser = turtle.Turtle()
    chaser.up()
    chaser.goto(0, 0)
    chaser.color("darkblue")
    chaser.setheading(chaser.towards(aim_x, aim_y))
    travel_distance = chaser.distance(aim_x, aim_y)
    chaser.down()
    chaser.forward(travel_distance)
    chaser.dot(10, "gold")
    chaser.up()
    chaser.goto(1000, 1000)


@app.cell(elements=[ui.turtle_canvas("shared_state_canvas", width=350, height=150), ui.notes("shared_state_notes")])
def two_turtles_share_one_position():
    """An honest limitation, not a bug: this app tracks exactly one
    turtle's worth of state per cell execution, so a second `Turtle()`
    handle passed to `distance()`/`towards()` as the target always
    resolves to the *same* position -- `t1.distance(t2)` is always 0
    here, unlike real turtle, where two turtles genuinely track
    separate positions."""
    t1 = turtle.Turtle()
    t2 = turtle.Turtle()
    t1.up()
    t1.goto(-100, 0)
    t2.up()
    t2.goto(80, 40)
    shared_state_distance = t1.distance(t2)
    t1.write(f"  t1.distance(t2) = {shared_state_distance:.1f} (always 0 here)")
    t1.goto(1000, 1000)
    t2.goto(1000, 1000)


@app.slide("distance()/towards() Upgrade", cells=["intro"])
def slide_intro():
    """Why these two functions matter."""


@app.slide("distance()", cells=["measure_distance"], reveal_code=True)
def slide_distance():
    """How far away is the target? -- try the sliders."""


@app.slide("towards()", cells=["aim_and_travel"], reveal_code=True)
def slide_towards():
    """Aim and travel exactly to the target -- try the sliders."""


@app.slide("The Shared-State Gap", cells=["two_turtles_share_one_position"], reveal_code=True)
def slide_gap():
    """Two Turtle() handles always share one position in this app."""
