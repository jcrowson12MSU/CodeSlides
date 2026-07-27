"""CodeSlides live-demo version of examples/marchingSquares.py.

The original is a plain stdlib-turtle script (`import turtle`,
`turtle.Screen()`, an OO `Turtle()` instance, `wn.setworldcoordinates(...)`,
`wn.tracer(0)`, `wn.mainloop()`) -- none of that exists in
`codeslides.turtle`, which is a from-scratch, tkinter-free shim of bare
module-level functions targeting the cell's one `turtle_canvas` element
(see ARCHITECTURE.md section 7). Porting it to a deck means:

- Dropping `Screen`/`Turtle`/`setworldcoordinates`/`tracer`/`mainloop`
  entirely -- there's no window object or object-oriented turtle here,
  and rendering is already "instant, no animation" by construction
  (docs/turtle-animation-feasibility.md), so there's nothing for
  `tracer(0)` to toggle.
- Re-centering coordinates: the original assumed `setworldcoordinates(0,
  0, cols, rows)`, i.e. the grid's origin at the canvas's bottom-left
  corner. `codeslides.turtle`'s canvas is origin-at-center, so every
  point is shifted by half the grid's extent to keep the drawing centered
  and fully on-canvas instead of half off-screen.
- Turning the fixed `scale = 10` into a `density` slider and adding a
  `reroll` button that feeds a fresh random seed -- the whole point of
  marching squares is watching the contour lines change as the random
  0/1 grid changes, so both are natural, pedagogically useful live knobs
  rather than the original's one-shot, run-once script.
- Nesting every helper (`createMatrix`, `midpoint`, `drawLineSegment`,
  `marchingSqs`) *inside* the one cell that uses them, rather than at
  module level like the original: a cell's compiled globals are seeded
  only with `cs`/`turtle` and the Session's namespace (kernel.py's
  execute_cell docstring) -- plain module-level helper functions in the
  deck file are never bound into that namespace, so a cell can't call
  them unless they're either their own cells (overkill for small
  algorithm-internal helpers like these) or defined as nested functions
  inside the cell body, which is what real Python closures are for.
"""

from codeslides import App, cs, turtle, ui

app = App()


@app.cell
def explain():
    doc = cs.md(
        "## Marching squares\n"
        "https://en.wikipedia.org/wiki/Marching_squares\n\n"
        "A random grid of 0s and 1s is generated, then for every 2x2 block "
        "of corners, one of 16 cases decides which line segment (if any) to "
        "draw through it. The result is a set of contour lines separating "
        "the 1-regions from the 0-regions. Drag **density** to change the "
        "grid's resolution, or press **reroll** to regenerate the random "
        "grid at the current density."
    )
    return doc


@app.cell(
    instance="editable",
    elements=[
        ui.slider("density", min=2, max=20, default=8),
        ui.button("reroll", label="Reroll grid"),
        ui.turtle_canvas("canvas", width=440, height=440),
        ui.notes(
            "notes",
            default="# Marching squares\nDrag density or press reroll to redraw.",
        ),
    ],
)
def marching_squares_demo(density, reroll):
    # A cell's compiled globals are seeded only with `cs`/`turtle` and the
    # Session's namespace -- any stdlib module a cell body needs must be
    # imported right here, same as a fresh module would.
    import random

    def createMatrix(rows, cols, rng):
        """Build a (rows+1) x (cols+1) grid of random 0/1 corner values.

        `rng` is an explicit `random.Random` instance (not the `random`
        module's shared global state) so a `reroll` click produces a
        genuinely new grid without depending on hidden global mutation --
        the same per-Session isolation principle (ARCHITECTURE.md section
        1) that keeps two cloned Sessions from ever sharing state applies
        just as much to a cell's own use of randomness.
        """
        grid = []
        for _ in range(rows + 1):
            grid.append([rng.randint(0, 1) for _ in range(cols + 1)])
        return grid

    def midpoint(p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        return (x1 + x2) / 2, (y1 + y2) / 2

    def drawLineSegment(to_canvas, p1, p2, p3, p4):
        """Draw a line from the midpoint of p1/p2 to the midpoint of p3/p4."""
        start = to_canvas(midpoint(p1, p2))
        end = to_canvas(midpoint(p3, p4))
        turtle.penup()
        turtle.goto(*start)
        turtle.pendown()
        turtle.goto(*end)
        turtle.penup()

    def marchingSqs(cells, to_canvas):
        """Walk every 2x2 block of corners, draw the case's line segment(s)."""
        for y, row in enumerate(cells[:-1]):
            for x in range(len(row) - 1):
                lowerLeft = (x, y)
                upperLeft = (x, y + 1)
                upperRight = (x + 1, y + 1)
                lowerRight = (x + 1, y)
                llValue = cells[y][x]
                ulValue = cells[y + 1][x]
                urValue = cells[y + 1][x + 1]
                lrValue = cells[y][x + 1]
                case = f"{ulValue}{urValue}{lrValue}{llValue}"

                if case == "0000":
                    pass
                elif case == "0001":
                    drawLineSegment(to_canvas, lowerLeft, upperLeft, lowerLeft, lowerRight)
                elif case == "0010":
                    drawLineSegment(to_canvas, lowerRight, upperRight, lowerLeft, lowerRight)
                elif case == "0011":
                    drawLineSegment(to_canvas, lowerLeft, upperLeft, lowerRight, upperRight)
                elif case == "0100":
                    drawLineSegment(to_canvas, upperLeft, upperRight, lowerRight, upperRight)
                elif case == "0101":
                    drawLineSegment(to_canvas, lowerRight, upperRight, lowerLeft, lowerRight)
                    drawLineSegment(to_canvas, lowerLeft, upperLeft, upperLeft, upperRight)
                elif case == "0110":
                    drawLineSegment(to_canvas, upperLeft, upperRight, lowerLeft, lowerRight)
                elif case == "0111":  # noqa: SIM114 -- keep each of the 16 cases separate and explicit
                    drawLineSegment(to_canvas, upperLeft, upperRight, lowerLeft, upperLeft)
                elif case == "1000":
                    drawLineSegment(to_canvas, upperLeft, upperRight, lowerLeft, upperLeft)
                elif case == "1001":
                    drawLineSegment(to_canvas, upperLeft, upperRight, lowerLeft, lowerRight)
                elif case == "1010":
                    drawLineSegment(to_canvas, upperLeft, upperRight, lowerRight, upperRight)
                    drawLineSegment(to_canvas, lowerLeft, lowerRight, lowerLeft, upperLeft)
                elif case == "1011":
                    drawLineSegment(to_canvas, upperLeft, upperRight, lowerRight, upperRight)
                elif case == "1100":
                    drawLineSegment(to_canvas, lowerLeft, upperLeft, lowerRight, upperRight)
                elif case == "1101":
                    drawLineSegment(to_canvas, lowerRight, upperRight, lowerLeft, lowerRight)
                elif case == "1110":
                    drawLineSegment(to_canvas, lowerLeft, upperLeft, lowerLeft, lowerRight)
                elif case == "1111":
                    pass

    # 3:4 aspect ratio like the original script's `rows, cols = 3*scale,
    # 4*scale`; `density` replaces the original's fixed `scale = 10`, and
    # each grid cell is drawn `cell_px` canvas pixels wide/tall so the
    # whole drawing fits the 440x440 canvas regardless of density.
    rows, cols = 3 * density, 4 * density
    cell_px = 400 / max(rows, cols)

    # `reroll` is a button's click count (0 on first run, then 1, 2, ...
    # -- ARCHITECTURE.md section 3a): using it directly as the random
    # seed means each click reliably produces a *different* grid, while
    # moving the density slider without clicking reroll keeps today's
    # grid but re-samples it at the new resolution (both are meaningful,
    # distinguishable actions for a student to observe).
    rng = random.Random(reroll)
    cells = createMatrix(rows, cols, rng)

    # Re-center: the original assumed the grid's origin sat at the
    # canvas's bottom-left corner (`setworldcoordinates(0, 0, cols,
    # rows)`); codeslides.turtle's canvas is origin-at-center, so every
    # point is shifted by half the grid's pixel extent to keep the
    # drawing centered instead of half off-canvas.
    offset_x = -(cols * cell_px) / 2
    offset_y = -(rows * cell_px) / 2
    scaled_cells_note = f"{rows + 1}x{cols + 1} corners, {cell_px:.1f}px per cell"

    def to_canvas(point):
        x, y = point
        return (x * cell_px + offset_x, y * cell_px + offset_y)

    turtle.pencolor("black")
    marchingSqs(cells, to_canvas)

    result = scaled_cells_note
    return result


@app.slide("Marching Squares", cells=["explain"])
def slide_1():
    """What the algorithm does and how to use the live demo."""


@app.slide("Live Demo", cells=["marching_squares_demo"], reveal_code=True)
def slide_2():
    """Drag density or click reroll; the contour redraws reactively."""
