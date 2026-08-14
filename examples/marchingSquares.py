from codeslides import App, cs, turtle, ui
import random

app = App()

@app.cell(hide_def=True)
def setup():
    import turtle
    import random


@app.cell(
    instance='editable',
    elements=[
        ui.notes('config'),
    ],
)
def config():
    """The grid size that drives the whole program: every downstream
cell -- createMatrix, markCorners, marchingSquares -- is ultimately
sized off of these two numbers. Change them here and every cell that
reads rows/cols re-runs with the new grid size."""
    rows = 30
    cols = 30
    return rows, cols


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('test', default='print(createMatrix(3,4))'),
    ],
)
def createMatrix(rows=2, cols=5):
    """This function creates a 2D list where each inner list
contains randomly generated 1s and 0s.
- rows: How many inner lists are in the 2D list
- cols: How many values are in each inner list
- **returns**: a 2D list where the inner items are 1s or 0s

----

Example:

> rows, cols = 3, 4
[   [1,1,0,0],
    [0,0,0,1],
    [0,0,0,0]
]
"""
    l = []
    for row in range(rows+1):
        newRow = []
        for col in range(cols+1):
            value = random.randint(0,1)
            newRow.append(value)
        l.append(newRow)

    return l




@app.cell(
    instance='editable',
    elements=[
        ui.notes('markCorners'),
        ui.turtle_canvas('Canvas', width=400, height=400),
        ui.tests('Run Code', default='cells1 = createMatrix(30, 30)\nt = turtle.Turtle()\n# t.shape("circle")\nmarkCorners(cells1, t)'),
    ],
)
def markCorners(cells2= None, t = None):
    """
This function plots each corner of a 2D grid as either
red or pink for each value in the 2D list cells. It can
be called or not. It just illustrates the grid created by
the 2D list cells.
- cells: a 2D list containing random 1s and 0s
- t: a turtle
- **returns**: None
"""
    count = 0
    for rowIndex, row1 in enumerate(cells2):
        for colIndex, colValue in enumerate(row1):
            count += 1
            if colValue == 0:
                t.color('pink')
            else:
                t.color('red')

            t.goto(colIndex, rowIndex)
            t.stamp()


@app.cell(
    instance='editable',
    elements=[
        ui.notes('Notes'),
        ui.iframe('Desmos', src='https://www.desmos.com/calculator/31jgkf3tgp', height=400),
        ui.tests('Run Code', default='print(midpoint((2,4), (10, -81)))'),
    ],
)
def midpoint(p1, p2):
    """This function computes the midpoint between p1 and p2.
- p1: a tuple representing a point
- p2: a tuple representing a point
- **returns**: a tuple representing the midpoint between p1 and p2

----

Example

p1 = (2,6)
p2 = (10, 8)
return (6, 7)"""
    x1, y1 = p1
    x2, y2 = p2
    return (x1 + x2) / 2, (y1 + y2) / 2


@app.cell(
    instance='editable',
    elements=[
        ui.notes('Contents'),
        ui.turtle_canvas('canvas', width=400, height=400),
    ],
    hide_def=True,
    is_main=True,
    layout={'code_fraction': 0.5, 'panel_fraction': 0.5, 'lower_tabs': ['canvas']},
)
def cell_4():
    """# Marching Squares

*Drawing 2D contour lines from a grid of 1s and 0s.*

## Contents

1. [Setup](#slide-1)
2. [Config](#slide-2)
3. [CreateMatrix](#slide-3)
4. [MarkCorners](#slide-4)
5. [MidPoint](#slide-5)
6. [DrawLineSegment](#slide-6)
7. [MarchingSquares](#slide-7)"""

    if __name__ == "__main__":
        scale = 3
        rows, cols = 4 * scale, 6 * scale
        wn = turtle.Screen()
        wn.setworldcoordinates(0, 0, cols, rows)
        wn.tracer(0)

        t = turtle.Turtle()
        t.up()
        t.hideturtle()
        t.shape("circle")

        cells = createMatrix(rows, cols)
        marchingSquares(cells, t)


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Run Code', default='p1 = (100, 100)\np2 = (100, 0)\np3 = (100, 100)\np4 = (0, 100)\n\nt = turtle.Turtle()\nt.up()\nt.hideturtle()\n\nt.goto(0, 0)\nt.stamp()\nt.goto(100, 0)\nt.stamp()\nt.goto(100, 100)\nt.stamp()\nt.goto(0, 100)\nt.stamp()\n\n# t.shape("circle")\n# t.shapesize(0.5)\n\ndrawLineSegment(t, p1, p2, p3, p4)'),
        ui.turtle_canvas('Canvas', width=400, height=400),
    ],
)
def drawLineSegment(t5, p1, p2, p3, p4):
    """This function draws a line starting at the midpoint of
p1 and p2 and ending at the midpoint of p3 and p4.
- t: a turtle
- p1: a tuple representing a point
- p2: a tuple representing a point
- p3: a tuple representing a point
- p4: a tuple representing a point
- **returns**: None"""
    start = midpoint(p1,p2)
    end = midpoint(p3, p4)
    t5.up()
    t5.goto(start)
    t5.down()
    t5.goto(end)
    t5.up()
    print(start)


@app.cell(
    instance='editable',
    elements=[
        ui.notes('Notes'),
        ui.turtle_canvas('Canvas', width=400, height=400),
        ui.tests('Test', default='\nscale = 3\nrows, cols = 4 * scale, 6 * scale\nwn = turtle.Screen()\nwn.setworldcoordinates(0, 0, cols, rows)\nwn.tracer(0)\n\nt = turtle.Turtle()\n# t.up()\nt.hideturtle()\nt.shape("circle")\n\ncells = createMatrix(rows, cols)\nmarchingSquares(cells, t)'),
        ui.image('Images', src=[]),
    ],
)
def marchingSquares(cells, t):
    """https://en.wikipedia.org/wiki/Marching_squares
This function implements the marching squares algorithm.
This algorithm has 16 different cases depending on which
corners of a square are 1s and which ones are 0s. After
determining which case a square in the grid falls into, it
draws a line segment corresponding to that case.
- cells: a 2D list
- t: a turtle
- **return**: None"""
    for y, row in enumerate(cells[:-1]):
        for x in range(len(row)-1):

            lowerLeft = (x, y)
            upperLeft = (x, y+1)
            upperRight = (x+1, y+1)
            print(4)
            lowerRight = (x+1, y)
            llValue = cells[y][x]
            ulValue = cells[y+1][x]
            urValue = cells[y+1][x+1]
            lrValue = cells[y][x+1]

            case = f"{ulValue}{urValue}{lrValue}{llValue}"
            # print(case)
            if case == "0000": pass
            elif case == "0001": drawLineSegment(t, lowerLeft, upperLeft, lowerLeft, lowerRight)
            elif case == "0010": drawLineSegment(t, lowerRight, upperRight, lowerLeft, lowerRight)
            elif case == "0011": drawLineSegment(t, lowerLeft, upperLeft, lowerRight, upperRight)
            elif case == "0100": drawLineSegment(t, upperLeft, upperRight, lowerRight, upperRight)
            elif case == "0101":
                drawLineSegment(t, lowerRight, upperRight, lowerLeft, lowerRight)
                drawLineSegment(t, lowerLeft, upperLeft, upperLeft, upperRight)
            elif case == "0110": drawLineSegment(t, upperLeft, upperRight, lowerLeft, lowerRight)
            elif case == "0111": drawLineSegment(t, upperLeft, upperRight, lowerLeft, upperLeft)
            elif case == "1000": drawLineSegment(t, upperLeft, upperRight, lowerLeft, upperLeft)
            elif case == "1001": drawLineSegment(t, upperLeft, upperRight, lowerLeft, lowerRight)
            elif case == "1010":
                drawLineSegment(t, upperLeft, upperRight, lowerRight, upperRight)
                drawLineSegment(t, lowerLeft, lowerRight, lowerLeft, upperLeft)
            elif case == "1011": drawLineSegment(t, upperLeft, upperRight, lowerRight, upperRight)
            elif case == "1100": drawLineSegment(t, lowerLeft, upperLeft, lowerRight, upperRight)
            elif case == "1101": drawLineSegment(t, lowerRight, upperRight, lowerLeft, lowerRight)
            elif case == "1110": drawLineSegment(t, lowerLeft, upperLeft, lowerLeft, lowerRight)
            elif case == "1111": pass



@app.cell(
    instance='editable',
    elements=[
        ui.notes('demo'),
        ui.turtle_canvas('Canvas', width=400, height=400),
        ui.tests('Run the whole program', default='cells = createMatrix(rows, cols)\nt = turtle.Turtle()\nt.hideturtle()\nmarkCorners(cells, t)\nmarchingSquares(cells, t)\n'),
    ],
)
def demo():
    """This is the whole program, start to finish: build a random
rows x cols grid (config), mark each corner (markCorners), then trace
the contour lines through it (marchingSquares) -- the same three steps
a student would run themselves outside of any single slide."""
    # Never actually called -- this cell has a `tests` element, so it's
    # only *defined* (see kernel.py's "define, don't call" rule). These
    # references exist purely so the dependency graph runs createMatrix/
    # markCorners/marchingSquares before this cell's own test does.
    createMatrix, markCorners, marchingSquares


@app.slide('Title', cells=['cell_4'])
def slide_title():
    """"""


@app.slide('Setup', cells=['setup'])
def slide_setup():
    """"""


@app.slide('Config', cells=['config'])
def slide_config():
    """"""


@app.slide('CreateMatrix', cells=['createMatrix'])
def slide_creatematrix():
    """"""


@app.slide('MarkCorners', cells=['markCorners'])
def slide_markcorners():
    """"""


@app.slide('MidPoint', cells=['midpoint'])
def slide_midpoint():
    """"""


@app.slide('DrawLineSegment', cells=['drawLineSegment'])
def slide_drawlinesegment():
    """"""


@app.slide('MarchingSquares', cells=['marchingSquares'])
def slide_marchingsquares():
    """"""
