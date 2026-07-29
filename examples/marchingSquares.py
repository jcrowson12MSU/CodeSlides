from codeslides import App, cs, turtle, ui
import random

app = App()

@app.cell(hide_def=True)
def setup():
    import turtle
    import random



#
# import turtle
# import random
# # https://en.wikipedia.org/wiki/Marching_squares
#
# def createMatrix(rows, cols):
#     """
#     This function creates a 2D list where each inner list
#     contains randomly generated 1s and 0s.
#     :param rows: How many inner lists are in the 2D list
#     :param cols: How many values are in each inner list
#     :return: a 2D list where the inner items are 1s or 0s
#     rows, cols = 3, 4
#     [   [1,1,0,0],
#         [0,0,0,1],
#         [0,0,0,0]
#     ]
#     """
#     l = []
#     for row in range(rows+1):
#         newRow = []
#         for col in range(cols+1):
#             value = random.randint(0,1)
#             newRow.append(value)
#         l.append(newRow)
#     return l
#
# def markCorners(cells, t):
#     """
#     This function plots each corner of a 2D grid as either
#     red or pink for each value in the 2D list cells. It can
#     be called or not. It just illustrates the grid created by
#     the 2D list cells.
#     :param cells: a 2D list containging random 1s and 0s
#     :param t: a turtle
#     :return: None
#     """
#
#     # for row in cells:
#     # for row in range(len(cells)):
#     for rowIndex, row in enumerate(cells):
#         for colIndex, colValue in enumerate(row):
#             if colValue == 0:
#                 t.color('pink')
#             else:
#                 t.color('red')
#
#             t.goto(colIndex, rowIndex)
#             t.stamp()
#
# def midpoint(p1, p2):
#     """
#     This function computes the midpoint between p1 and p2.
#     :param p1: a tuple representing a point
#     :param p2: a tuple representing a point
#     :return: a tuple representing the midpoint between p1 and p2
#     p1 = (2,6)
#     p2 = (10, 8)
#     return (6, 7)
#     """
#     x1, y1 = p1
#     x2, y2 = p2
#     return (x1 + x2) / 2, (y1 + y2) / 2
#
#
#
# def drawLineSegment(t, p1,p2,p3,p4):
#     """
#     This function draws a line starting at the midpoint of
#     p1 and p2 and ending at the midpoint of p3 and p4.
#     :param t: a turtle
#     :param p1: a tuple representing a point
#     :param p2: a tuple representing a point
#     :param p3: a tuple representing a point
#     :param p4: a tuple representing a point
#     :return: None
#     """
#     start = midpoint(p1,p2)
#     end = midpoint(p3, p4)
#     t.up()
#     t.goto(start)
#     t.down()
#     t.goto(end)
#     t.up()
#
#
# def marchingSqs(cells, t):
#     """
#     https://en.wikipedia.org/wiki/Marching_squares
#     This function implements the marching squares algorithm.
#     This algorithm has 16 different cases depending on which
#     corners of a square are 1s and which ones are 0s. After
#     determining which case a square in the grid falls into, it
#     draws a line segment corresponding to that case.
#     :param cells: a 2D list
#     :param t: a turtle
#     :return: None
#     """
#
#     for y, row in enumerate(cells[:-1]):
#         for x in range(len(row)-1):
#             lowerLeft = (x, y)
#             upperLeft = (x, y+1)
#             upperRight = (x+1, y+1)
#             lowerRight = (x+1, y)
#             llValue = cells[y][x]
#             ulValue = cells[y+1][x]
#             urValue = cells[y+1][x+1]
#             lrValue = cells[y][x+1]
#             case = f"{ulValue}{urValue}{lrValue}{llValue}"
#
#             if case == "0000": pass
#             elif case == "0001": drawLineSegment(t, lowerLeft, upperLeft, lowerLeft, lowerRight)
#             elif case == "0010": drawLineSegment(t, lowerRight, upperRight, lowerLeft, lowerRight)
#             elif case == "0011": drawLineSegment(t, lowerLeft, upperLeft, lowerRight, upperRight)
#             elif case == "0100": drawLineSegment(t, upperLeft, upperRight, lowerRight, upperRight)
#             elif case == "0101":
#                 drawLineSegment(t, lowerRight, upperRight, lowerLeft, lowerRight)
#                 drawLineSegment(t, lowerLeft, upperLeft, upperLeft, upperRight)
#             elif case == "0110": drawLineSegment(t, upperLeft, upperRight, lowerLeft, lowerRight)
#             elif case == "0111": drawLineSegment(t, upperLeft, upperRight, lowerLeft, upperLeft)
#             elif case == "1000": drawLineSegment(t, upperLeft, upperRight, lowerLeft, upperLeft)
#             elif case == "1001": drawLineSegment(t, upperLeft, upperRight, lowerLeft, lowerRight)
#             elif case == "1010":
#                 drawLineSegment(t, upperLeft, upperRight, lowerRight, upperRight)
#                 drawLineSegment(t, lowerLeft, lowerRight, lowerLeft, upperLeft)
#             elif case == "1011": drawLineSegment(t, upperLeft, upperRight, lowerRight, upperRight)
#             elif case == "1100": drawLineSegment(t, lowerLeft, upperLeft, lowerRight, upperRight)
#             elif case == "1101": drawLineSegment(t, lowerRight, upperRight, lowerLeft, lowerRight)
#             elif case == "1110": drawLineSegment(t, lowerLeft, upperLeft, lowerLeft, lowerRight)
#             elif case == "1111": pass
#
#
#
#
#
#
#
#
#
# scale = 10
# rows, cols = 3*scale, 4*scale
# wn = turtle.Screen()
# wn.setworldcoordinates(0, 0, cols, rows)
#
#
#
# t = turtle.Turtle()
# wn.tracer(0)
# t.up()
# t.hideturtle()
# t.shape("circle")
# t.shapesize(0.5)
#
#
#
# cells = createMatrix(rows, cols)
# # for i, row in enumerate(cells):
# #     print(i, row)
#
# markCorners(cells, t)
# t.color("black")
# marchingSqs(cells, t)
#
# wn.update()
# wn.mainloop()
#
# # program used to make rotary encoder act as a scroll wheel
# import time
# import digitalio
# import board
# import rotaryio
# import usb_hid
#
# from adafruit_hid.mouse import Mouse
#
# # Rotary encoder connections to board
# encoder = rotaryio.IncrementalEncoder(board.GP4, board.GP3)
# encoderSw = digitalio.DigitalInOut(board.GP2)
# encoderSw.direction = digitalio.Direction.INPUT
# encoderSw.pull = digitalio.Pull.UP
# lastPosition = 0
#
# # LED flashes when a movement is made
# led = digitalio.DigitalInOut(board.GP25)
# led.direction = digitalio.Direction.OUTPUT
#
# # USB device
# m = Mouse(usb_hid.devices)
#
# # button delay
# delay = 0.2
#
# # loop
# while True:
#     # poll encoder position
#     position = encoder.position
#     if position != lastPosition:
#         led.value = True
#         if lastPosition < position:
#             m.move(0, 0, -1)
#         else:
#             m.move(0, 0, 1)
#         lastPosition = position
#         led.value = False
#
#
#
#     time.sleep(0.1)


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("test")
    ],
)
def createMatrix(rows=2, cols=5):
    """
    This function creates a 2D list where each inner list
    contains randomly generated 1s and 0s.
    :param rows: How many inner lists are in the 2D list
    :param cols: How many values are in each inner list
    :return: a 2D list where the inner items are 1s or 0s
    rows, cols = 3, 4
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
