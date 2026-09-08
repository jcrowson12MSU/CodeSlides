import turtle
import random



# https://en.wikipedia.org/wiki/Marching_squares

def createMatrix(rows, cols):
    """
    This function creates a 2D list where each inner list
    contains randomly generated 1s and 0s.
    :param rows: How many inner lists are in the 2D list
    :param cols: How many values are in each inner list
    :return: a 2D list
    ex:
        rows = 3
        cols = 4
    Then this might look like:
    matrix = [
                [1,0,0,0],
                [0,0,1,1],
                [1,1,1,1]
            ]

    """
    matrix = []
    for row in range(rows):
        newRow = []
        for col in range(cols):
            num = random.choice([0, 1])
            newRow.append(num)
        matrix.append(newRow)

    return matrix

def markCorners(t, cells):
    """
    This function plots each corner of a 2D grid as either
    red or pink for each value in the 2D list cells. It can
    be called or not. It just illustrates the grid created by
    the 2D list cells.
    :param cells: a 2D list containging random 1s and 0s
    :param t: a turtle
    :return: None
    ex:
    rows, cols = 2, 6
    cells = [
                [1,0,0,0, 1,0],
                [0,0,1,1,0,0]
            ]

    rows, cols = 3, 5
    cells = [
                [1,0,0,0, 1],
                [0,0,1,1,0],
                [0,0,1,1,0]
            ]
    """


    for row in range(rows):
        for col in range(cols):
            if cells[row][col] == 1:
                t.color("red")
            else:
                t.color("pink")
            t.goto(col,row)
            t.stamp()



def midpoint(p1, p2):
    """
    This function computes the midpoint between p1 and p2.
    :param p1: a tuple representing a point
    :param p2: a tuple representing a point
    :return: a tuple representing a point
    p1 = (10, 2)
    """
    x1, y1 = p1
    x2, y2 = p2

    return ((x1 + x2)/2, (y1 + y2)/2)





def drawLineSegment(t, p1, p2, p3, p4):
    """
    This function draws a line starting at the midpoint of
    p1 and p2 and ending at the midpoint of p3 and p4.
    :param t: a turtle
    :param p1: a tuple representing a point
    :param p2: a tuple representing a point
    :param p3: a tuple representing a point
    :param p4: a tuple representing a point
    :return: None

    ex:
        p1 = (0,0)
        p2 = (1,0)
        p3 = (1,1)
        p4 = (1,0)
    """

    start = midpoint(p1, p2)
    end = midpoint(p3, p4)
    print(p1,p2,p3,p4)
    print("wgehrntm", start, end)
    t.up()
    t.goto(start)
    t.down()
    t.goto(end)
    t.up()

def marchingSqs(t, cells):
    """
    https://en.wikipedia.org/wiki/Marching_squares
    This function implements the marching squares algorithm.
    This algorithm has 16 different cases depending on which
    corners of a square are 1s and which ones are 0s. After
    determining which case a square in the grid falls into, it
    draws a line segment corresponding to that case.
    :param cells: a 2D list
    :param t: a turtle
    :return: None
    """
    t.color("black")
    for y in range(rows-1):
        for x in range(cols-1):
            llCorner = (x, y) #(x: 2, y: 2)
            ulCorner = (x, y+1)  # (x: 2, y: 2)
            urCorner = (x + 1, y+1)
            lrCorner = (x + 1, y)
            llState = cells[y][x]
            lrState = cells[y][x+1]
            ulState = cells[y+1][x]
            urState = cells[y+1][x+1]
            case = f"{ulState}{urState}{lrState}{llState}"
            if case == "0000": pass
            elif case == "0001": drawLineSegment(t, llCorner, lrCorner, llCorner, ulCorner)
            elif case == "0010": drawLineSegment(t, llCorner, lrCorner, lrCorner, urCorner)
            elif case == "0011": drawLineSegment(t, llCorner, ulCorner, urCorner, lrCorner)
            elif case == "0100": drawLineSegment(t, urCorner, ulCorner, urCorner, lrCorner)
            elif case == "0101":
                drawLineSegment(t, llCorner, ulCorner, ulCorner, urCorner)
                drawLineSegment(t, llCorner, lrCorner, lrCorner, urCorner)
            elif case == "0110": drawLineSegment(t, llCorner, lrCorner, ulCorner, urCorner)


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
print(cells)
print(midpoint((10, 12), (14, 20)))

# t.shapesize(0.5)
#




for i, row in enumerate(cells):
    print(i, row)
# print(cells)
#
markCorners(t, cells)
# t.color("black")
marchingSqs(t, cells)
#
wn.update()
wn.exitonclick()
