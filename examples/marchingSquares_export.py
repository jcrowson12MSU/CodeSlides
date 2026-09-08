import turtle
import random


def config():
    """# ttt


The grid size that drives the whole program: every downstream
cell -- createMatrix, markCorners, marchingSquares -- is ultimately
sized off of these two numbers. Change them here and every cell that
reads rows/cols re-runs with the new grid size."""
    rows = 30
    cols = 30
    return rows, cols


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
        print(3)
    return l


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
