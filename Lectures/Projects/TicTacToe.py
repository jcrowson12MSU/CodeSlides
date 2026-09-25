
from codeslides import App, cs, ui

app = App()


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Game board set up', default='gameboard = """1|2|3\n-----\n4|5|6\n----\n7|8|9"""\n\nprint(gameboard)\n\ngameboard = "1|2|3\\n-----\\n4|5|6\\n----\\n7|8|9"\nprint(gameboard)'),
    ],
    hide_def=True,
    hide_code=True,
    layout={'column_fraction': 0.5, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'Game board set up': 'top-right'}, 'extra_code_fraction': 0.5},
)
def intro():
    """# Gameboard set up

```
1|2|3
-----
4|5|6
----
7|8|9

1|2|3\\n-----\\n4|5|6\\n----\\n7|8|9
```
"""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Edit Game board', default='gameboard = "1|2|3\\n-----\\n4|5|6\\n----\\n7|8|9"\nmove = input("Player Makes Move: ")\ncurrent_player = input("Player Mark: ")\n\ngameboard = gameboard.replace(move, current_player)\nprint(gameboard)'),
        ui.slider('Player Makes Move', min=1, max=9, default=5),
        ui.text_input('Player Mark', default=''),
    ],
    hide_def=True,
    hide_code=True,
    layout={'column_fraction': 0.5, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'__inputs__': 'top-left', 'Edit Game board': 'top-right'}, 'extra_code_fraction': 0.5},
)
def edit_game_board():
    """Edit game board"""



@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Game board set up', default='game_board = """1|2|3\\n-----\\n4|5|6\\n-----\\n7|8|9"""\nround = 0\nwinner = None\nwhile winner == None:\n    if round % 2 == 0:\n        current_player = "X"\n    else:\n        current_player = "O"\n    print(game_board)\n    current_player_move = input(f"Where do you want to make your move ({current_player} player)? ")\n    game_board = game_board.replace(current_player_move, current_player)\n\n    if game_board[0] == game_board[2] == game_board[4]:\n        winner = game_board[0]\n    elif game_board[12] == game_board[14] == game_board[16]:\n        winner = game_board[12]\n    elif game_board[24] == game_board[26] == game_board[28]:\n        winner = game_board[24]\n    elif game_board[0] == game_board[12] == game_board[24]:\n        winner = game_board[0]\n    elif game_board[2] == game_board[14] == game_board[26]:\n        winner = game_board[2]\n    elif game_board[4] == game_board[16] == game_board[28]:\n        winner = game_board[4]\n    elif game_board[0] == game_board[14] == game_board[28]:\n        winner = game_board[0]\n    elif game_board[4] == game_board[14] == game_board[24]:\n        winner = game_board[4]\n    elif round == 8:\n        winner = "CAT"\n    round += 1\n\nprint(f"The winner is {winner}!")'),
        ui.text_input('Player 1(1)', default=''),
        ui.text_input('Player 2(2)', default=''),
        ui.text_input('Player 1(3)', default=''),
        ui.text_input('Player 2(4)', default=''),
        ui.text_input('Player 1(5)', default=''),
        ui.text_input('Player 2(6)', default=''),
        ui.text_input('Player 1(7)', default=''),
        ui.text_input('Player 2(8)', default=''),
        ui.text_input('Player 1(9)', default=''),
    ],
    hide_def=True,
    hide_code=True,
    layout={'column_fraction': 0.16379655569947338, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'Game board set up': 'top-left', '__inputs__': 'bottom-left'}, 'extra_code_fraction': 0.5},
)
def looping_example():
    """Edit game board"""


@app.slide('1', cells=['intro'])
def slide_1():
    """"""


@app.slide('2', cells=['edit_game_board'])
def slide_2():
    """"""


@app.slide('3', cells=['looping_example'])
def slide_3():
    """"""
