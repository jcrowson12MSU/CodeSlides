"""Lists -- lecture deck built from Lectures/ZybooksNotes/Chapter 6
(zyBooks CSE 1284, sections 6.1-6.4 and 6.6-6.9; section 6.5's source
PDF was not provided and is skipped).

Like chapter1.py/chapter2.py/chapter3.py/chapter4.py, this deck is
deliberately straight-line code -- no `def` anywhere inside a cell
body, since functions haven't been taught yet. Every cell's own MAIN
code editor is hidden (`hide_code=True`); the runnable/editable code a
student sees and can experiment with lives in one or more
`ui.tests(...)` boxes instead, mirroring zyBooks' own "type this exact
program, run it, change the input" pattern. Unlike `def`, `for`/`while`
loops are used freely here (both in the cell bodies and the test
boxes) -- zyBooks' own Chapter 6 examples already lean on `for` to
iterate lists (e.g. building/printing a list, nested loops over a 2D
list), and there's no earlier chapter in this deck series to introduce
loops separately, so this deck follows the source material rather than
inventing a loop-free rewrite.

Where zyBooks used an interactive walkthrough/animation tool (the
list-of-references diagram, in-place-modification traces, the 2D-list
row/column grid, the membership-operator check marks) this deck
re-creates the same teaching point as Markdown (worked traces, tables)
plus a live `ui.tests` box a student can actually run, consistent with
the prior chapters' "real reactive control instead of a canned
animation" pattern.
"""

from codeslides import App, cs, ui

app = App()


@app.cell(
    instance='static',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def intro():
    """# Lists

Eight zyBooks sections (6.1-6.4, 6.6-6.9) on Python's `list` type --
creating and indexing lists, slicing, list methods, nesting lists to
build 2D data, membership/identity operators, splitting and joining
strings, and sorting -- rebuilt as runnable CodeSlides cells.

Every code sample lives in its own **test editor** below the notes,
not the slide's main editor -- run it, change it, break it.

Use **Slides** to step through in order, or **Cells** to jump straight
to a topic."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Creating and indexing a list', default='prices = ["$20", 14.99, 5]\nprint(prices)\nprint(prices[0])\nprint(prices[2])'),
    ],
    hide_code=True,
)
def list_basics():
    """## Lists: Container, Element, Index

A **container** is a construct used to group related values together,
and can even hold other objects instead of data.

A **list** is a container created by surrounding a sequence of
variables or values with brackets, `[ ]`. A list item is called an
**element**.

Elements are ordered by position in the list, known as the element's
**index** -- indices start at `0`, not `1`.

```python
prices = ["$20", 14.99, 5]
print(prices)      # ['$20', 14.99, 5]
print(prices[0])   # '$20'  -- first element, index 0
print(prices[2])   # 5      -- third element, index 2
```

A list holds *references* to the objects it contains, not the objects
themselves -- `prices[0]` looks up whatever object currently sits at
index 0."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('update_index_text', default='0'),
        ui.tests('Updating an element in-place', default='prices = [1.50, 3.75, 6.00]\nprint("Cost:", prices[0] + prices[1])\n\n# Update the first price\nprices[0] = 2.50\n\n# Print the updated cost\nprint("Updated cost:", prices[0] + prices[1])'),
    ],
    hide_code=True,
)
def in_place_modification(update_index_text):
    """## In-Place Modification

A list is **mutable**: its size can grow or shrink, and the values
within it can change, all *in place* -- assigning `my_list[i] = x`
changes the element at index `i` without creating a new list.

```python
prices = [1.50, 3.75, 6.00]
print("Cost:", prices[0] + prices[1])   # Cost: 5.25

prices[0] = 2.50   # Update the first price

print("Updated cost:", prices[0] + prices[1])  # Updated cost: 6.25
```

Type an index below (`0`, `1`, or `2`) to see which price gets
replaced with `99.99`."""
    prices = [1.50, 3.75, 6.00]
    index = int(update_index_text)
    if 0 <= index <= 2:
        prices[index] = 99.99
        result = f"prices = {prices}"
    else:
        result = "index out of range (use 0, 1, or 2)"
    return cs.md(f"**Output:** `{result}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('append, pop, remove', default='my_list = [10, "bw"]\nprint(my_list)\n\nmy_list.append("abc")\nprint(f"After append: {my_list}")\n\nmy_list.pop(1)\nprint(f"After pop: {my_list}")\n\nmy_list.remove("abc")\nprint(f"After remove: {my_list}")'),
    ],
    hide_code=True,
)
def append_pop_remove():
    """## Adding and Removing Elements: A Method Preview

A **method** instructs an object to perform some action, and is
specified using the object's variable name followed by a `.` symbol
and then the method name.

- **`append(x)`** adds `x` to the end of the list.
- **`pop(i)`** removes and returns the element at index `i` (last
  element if `i` is omitted).
- **`remove(x)`** removes the *first* element equal to `x`.

```python
my_list = [10, "bw"]
print(my_list)                          # [10, 'bw']

my_list.append("abc")
print(f"After append: {my_list}")       # After append: [10, 'bw', 'abc']

my_list.pop(1)                          # removes "bw" (index 1)
print(f"After pop: {my_list}")          # After pop: [10, 'abc']

my_list.remove("abc")
print(f"After remove: {my_list}")       # After remove: [10]
```

`append`/`pop`/`remove` are only three of many **list methods** -- the
full set is covered a few slides ahead."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Sequence functions and methods', default='house_prices = [380000, 900000, 875000] + [225000]\nprint(f"There are {len(house_prices)} prices in the list")\n\ncost = min(house_prices)\nprint(f"Lowest cost housing: {cost}")\nprint(f"Highest cost housing: {max(house_prices)}")\nprint(f"Total value: {sum(house_prices)}")\nprint(f"Index of 900000: {house_prices.index(900000)}")\nprint(f"Count of 875000: {house_prices.count(875000)}")'),
    ],
    hide_code=True,
)
def sequence_functions_table():
    """## Sequence-Type Functions and Methods

**Sequence-type functions/methods** are built into Python and work on
any sequence -- lists *and* strings.

| Operation | Description |
| --- | --- |
| `len(list)` | Find the length of the list. |
| `list1 + list2` | Concatenate `list2` onto the end of `list1` (a *new* list). |
| `min(list)` | The element with the smallest value. |
| `max(list)` | The element with the largest value. |
| `sum(list)` | The sum of all elements (numbers only). |
| `list.index(val)` | Index of the first element equal to `val`. |
| `list.count(val)` | How many elements equal `val`. |

```python
house_prices = [380000, 900000, 875000] + [225000]
print(f"There are {len(house_prices)} prices in the list")

cost = min(house_prices)
```"""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('slice_start_text', default='0'),
        ui.text_input('slice_end_text', default='2'),
        ui.tests('List slicing', default='boston_bruins = ["Tyler", "Zdeno", "Patrice"]\nprint(f"Elements 0 and 1: {boston_bruins[0:2]}")\nprint(f"Elements 1 and 2: {boston_bruins[1:3]}")\n\nelection_years = [1992, 1996, 2000, 2004, 2008]\nprint(election_years[0:-1])   # Every year except the last\nprint(election_years[0:-3])   # Every year except the last three\nprint(election_years[-3:-1])  # The third and second to last years'),
    ],
    hide_code=True,
    layout={'tab_quadrant': {'List slicing': 'top-right', '__inputs__': 'bottom-left'}},
)
def list_slicing(slice_start_text, slice_end_text):
    """## List Slicing

**Slice notation** reads multiple elements from a list into a *new*
list containing only the desired elements: `my_list[start:end]` --
`start` is included, `end` is not.

```python
boston_bruins = ["Tyler", "Zdeno", "Patrice"]
print(boston_bruins[0:2])   # ['Tyler', 'Zdeno']
print(boston_bruins[1:3])   # ['Zdeno', 'Patrice']
```

Negative indices count from the end:

```python
election_years = [1992, 1996, 2000, 2004, 2008]
print(election_years[0:-1])   # [1992, 1996, 2000, 2004] -- all but the last
print(election_years[0:-3])   # [1992, 1996]             -- all but the last 3
print(election_years[-3:-1])  # [2000, 2004]              -- 3rd/2nd-to-last
```

An optional third component, the **stride**, skips elements between
those extracted: `my_list[start:end:stride]`.

Type a start/end index below to slice `boston_bruins` yourself."""
    boston_bruins = ["Tyler", "Zdeno", "Patrice"]
    try:
        start = int(slice_start_text)
        end = int(slice_end_text)
        sliced = boston_bruins[start:end]
        result = f"boston_bruins[{start}:{end}] = {sliced}"
    except ValueError:
        result = "enter whole numbers for start/end"
    return cs.md(f"**Output:** `{result}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Full method trace', default='vals = [1, 4, 16]\n\nvals.append(9)\nprint(f"append(9): {vals}")\n\nvals.insert(2, 18)\nprint(f"insert(2, 18): {vals}")\n\nvalue = vals.pop()\nprint(f"pop() -> {value}, list now {vals}")\n\nvals.remove(4)\nprint(f"remove(4): {vals}")\n\n# vals.remove(55) would raise ValueError -- 55 is not in vals'),
        ui.tests('sort / reverse', default='my_list = [14, 5, 8]\nmy_list.sort()\nprint(f"sort(): {my_list}")\n\nmy_list.reverse()\nprint(f"reverse(): {my_list}")'),
    ],
    hide_code=True,
)
def list_methods_table():
    """## List Methods

A **list method** performs a useful operation on a list, such as
adding elements, removing elements, sorting, or reversing.

**Adding elements**

| Method | Description |
| --- | --- |
| `list.append(x)` | Add `x` to the end of the list. |
| `list.extend([x])` | Add all items of another list to the end. |
| `list.insert(i, x)` | Insert `x` *before* position `i`. |

**Removing elements**

| Method | Description |
| --- | --- |
| `list.remove(x)` | Remove the first item equal to `x`. |
| `list.pop()` | Remove and return the last item. |
| `list.pop(i)` | Remove and return the item at position `i`. |

**Modifying / miscellaneous**

| Method | Description |
| --- | --- |
| `list.sort()` | Sort the list in-place. |
| `list.reverse()` | Reverse the list in-place. |
| `list.index(x)` | Index of the first item equal to `x`. |
| `list.count(x)` | Count occurrences of `x`. |

Removing a value that isn't there (`list.remove(55)` on a list without
`55`) raises a `ValueError` -- the trace below stops right before
that line."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('nest_row_text', default='0'),
        ui.text_input('nest_col_text', default='0'),
        ui.tests('Tic-tac-toe board', default='tic_tac_toe = [\n    ["X", "O", "X"],\n    [" ", "X", " "],\n    ["O", "O", "X"]\n]\nprint(tic_tac_toe[0][0], tic_tac_toe[0][1], tic_tac_toe[0][2])\nprint(tic_tac_toe[1][0], tic_tac_toe[1][1], tic_tac_toe[1][2])\nprint(tic_tac_toe[2][0], tic_tac_toe[2][1], tic_tac_toe[2][2])'),
    ],
    hide_code=True,
)
def list_nesting(nest_row_text, nest_col_text):
    """## List Nesting: 2D Lists

Embedding a list inside another list is **list nesting** -- it lets a
programmer build a **multi-dimensional data structure**, the simplest
being a two-dimensional table like a spreadsheet or a tic-tac-toe
board.

```python
my_list = [[10, 20], [30, 40]]
print(my_list[0])       # [10, 20]  -- one indexing op reaches a nested list
print(my_list[0][0])    # 10        -- two indexing ops reach an element
```

```python
tic_tac_toe = [
    ["X", "O", "X"],
    [" ", "X", " "],
    ["O", "O", "X"]
]
print(tic_tac_toe[0][0], tic_tac_toe[0][1], tic_tac_toe[0][2])  # X O X
```

Elements are accessed by `[row][column]`. Nesting depth is arbitrary --
a list of lists of lists works exactly the same way, just with one
more `[index]`.

Type a row/column below to read a cell from `tic_tac_toe`."""
    tic_tac_toe = [
        ["X", "O", "X"],
        [" ", "X", " "],
        ["O", "O", "X"],
    ]
    try:
        row = int(nest_row_text)
        col = int(nest_col_text)
        cell = tic_tac_toe[row][col]
        result = f"tic_tac_toe[{row}][{col}] = {cell!r}"
    except (ValueError, IndexError):
        result = "row/column must be whole numbers 0-2"
    return cs.md(f"**Output:** `{result}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Nested for loop', default='currency = [\n    [1.00, 5.00, 10.0],  # US Dollars\n    [0.75, 3.77, 7.53],  # Euros\n    [0.65, 3.25, 6.50],  # British pounds\n]\n\nfor row in currency:\n    for cell in row:\n        print(cell, end=" ")\n    print()'),
        ui.tests('enumerate() for indices', default='currency = [\n    [1, 5, 10],\n    [0.75, 3.77, 7.53],\n    [0.65, 3.25, 6.50],\n]\n\nfor row_index, row in enumerate(currency):\n    for column_index, item in enumerate(row):\n        print(f"currency[{row_index}][{column_index}] is {item:.2f}")'),
    ],
    hide_code=True,
)
def nested_for_loops():
    """## Iterating Multi-Dimensional Lists

A programmer can visit every element of a nested list with **nested
`for` loops** -- one loop per dimension.

```python
currency = [
    [1.00, 5.00, 10.0],  # US Dollars
    [0.75, 3.77, 7.53],  # Euros
    [0.65, 3.25, 6.50],  # British pounds
]

for row in currency:
    for cell in row:
        print(cell, end=" ")
    print()
```
```text
1.00 5.00 10.0
0.75 3.77 7.53
0.65 3.25 6.50
```

`enumerate()` on both loops recovers the row/column indices along with
each value:

```python
for row_index, row in enumerate(currency):
    for column_index, item in enumerate(row):
        print(f"currency[{row_index}][{column_index}] is {item:.2f}")
```"""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('membership_name_text', default='Messi'),
        ui.tests('in / not in on a list', default='prices = ["$20", 15, 5]\nprint(15 in prices)\nprint(44 in prices)\n\nrequest_str = "GET index.html HTTP/1.1"\nif "/1.1" in request_str:\n    print("HTTP protocol 1.1")\nif "HTTPS" not in request_str:\n    print("Unsecured connection")'),
    ],
    hide_code=True,
)
def membership_operators(membership_name_text):
    """## Membership Operators: `in` / `not in`

The **membership operators** `in` and `not in` yield `True` if the
left operand's value matches an element of the right operand -- a
list, or (as a **substring** check) a string.

```python
prices = ["$20", 15, 5]
print(15 in prices)   # True
print(44 in prices)   # False
```

```python
barcelona_fc_roster = ["Alves", "Messi", "Fabregas"]
name = input("Enter name to check: ")
if name in barcelona_fc_roster:
    print(f"Found {name} on the roster.")
else:
    print(f"Could not find {name} on the roster.")
```

`in` also checks substrings of a string, and checks *keys* (not
values) of a dict:

```python
request_str = "GET index.html HTTP/1.1"
if "/1.1" in request_str:
    print("HTTP protocol 1.1")
```

Type a name below to check it against the Barcelona roster."""
    barcelona_fc_roster = ["Alves", "Messi", "Fabregas"]
    name = membership_name_text
    if name in barcelona_fc_roster:
        result = f"Found {name} on the roster."
    else:
        result = f"Could not find {name} on the roster."
    return cs.md(f"**Output:** `{result}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('is / is not', default='w = 500\nx = 500 + 500  # Create a new object with value 1000\ny = w + w      # Create a second object with value 1000\nz = x          # Bind z to the same object as x\n\nif z is x:\n    print("z and x are bound to the same object")\nif z is not y:\n    print("z and y are NOT bound to the same object")'),
    ],
    hide_code=True,
)
def identity_operators():
    """## Identity Operators: `is` / `is not`

The **identity operator**, `is`, checks whether two variables are
bound to a *single* object -- not merely equal values. **`is not`**
gives the negated result.

```python
w = 500
x = 500 + 500  # Create a new object with value 1000
y = w + w      # Create a second object with value 1000
z = x          # Bind z to the same object as x

if z is x:
    print("z and x are bound to the same object")
if z is not y:
    print("z and y are NOT bound to the same object")
```
```text
z and x are bound to the same object
z and y are NOT bound to the same object
```

`x` and `y` both hold the value `1000`, so `x == y` is `True` -- but
they're two *different* objects, so `x is y` is `False`. `==` compares
values; `is` compares identity."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('separator_text', default='/'),
        ui.tests('split()', default='url = "en.wikipedia.org/wiki/ethanol"\ntokens = url.split("/")  # Uses "/" separator\nprint(tokens)\n\nsentence = "I love python"\nprint(sentence.split())  # No argument: splits on whitespace'),
        ui.tests('join()', default='web_path = ["www.website.com", "profile", "settings"]\nseparator = "/"\nurl = separator.join(web_path)\nprint(url)\n\n# split() and join() together: swap a path\'s separator\npath = "C:/Users/Wolfman/Documents/report.pdf"\ntokens = path.split("/")\nprint("\\\\".join(tokens))'),
    ],
    hide_code=True,
)
def split_and_join(separator_text):
    """## Splitting and Joining Strings

`split()` breaks a string into a list of **tokens** -- substrings that
formed part of the original -- wherever a **separator** occurs.

```python
url = "en.wikipedia.org/wiki/ethanol"
tokens = url.split("/")   # Uses "/" separator
print(tokens)              # ['en.wikipedia.org', 'wiki', 'ethanol']
```

Called with no argument, `split()` defaults to splitting on
whitespace: `"I love python".split()` -> `['I', 'love', 'python']`.

`join()` is the inverse -- a string's `join()` method glues a list of
strings back together, using the string it's called on as the
separator:

```python
web_path = ["www.website.com", "profile", "settings"]
separator = "/"
url = separator.join(web_path)   # 'www.website.com/profile/settings'
```

Combining both lets a program swap a path's separator entirely:
`new_separator.join(path.split("/"))`.

Type a separator below to re-join `web_path` with it."""
    web_path = ["www.website.com", "profile", "settings"]
    sep = separator_text
    joined = sep.join(web_path)
    return cs.md(f"**Output:** `{joined}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('sort() vs sorted()', default='my_list = [150, 47, 500, -37, 0]\nmy_list.sort()\nprint(my_list)\n\nnumbers = [-5, 3, 10, 0]\nsorted_numbers = sorted(numbers)\nprint(f"Original numbers: {numbers}")\nprint(f"Sorted numbers: {sorted_numbers}")'),
        ui.tests('key and reverse', default='names = ["Serena Williams", "Venus Williams", "rafael Nadal", "john McEnroe"]\nno_key_sort = sorted(names)\nkey_sort = sorted(names, key=str.lower)\nprint(f"Sorting without key: {no_key_sort}")\nprint(f"Sorting with key: {key_sort}")\n\nnums = [3, 1, 4, 1, 5, 9]\nprint(sorted(nums, reverse=True))'),
    ],
    hide_code=True,
)
def sorting_lists():
    """## Sorting Lists

`list.sort()` sorts a list **in-place**, lowest to highest:

```python
my_list = [150, 47, 500, -37, 0]
my_list.sort()
print(my_list)   # [-37, 0, 47, 150, 500]
```

The built-in `sorted()` does the same sorting, but *returns a new
list* instead of modifying the original:

```python
numbers = [-5, 3, 10, 0]
sorted_numbers = sorted(numbers)
print(f"Original numbers: {numbers}")       # unchanged
print(f"Sorted numbers: {sorted_numbers}")  # [-5, 0, 3, 10]
```

Both `sort()` and `sorted()` accept a **`key`** -- a function applied
to each element before comparing -- and a **`reverse`** flag:

```python
names = ["Serena Williams", "Venus Williams", "rafael Nadal", "john McEnroe"]
print(sorted(names, key=str.lower))   # case-insensitive order

nums = [3, 1, 4, 1, 5, 9]
print(sorted(nums, reverse=True))     # [9, 5, 4, 3, 1, 1] -- highest to lowest
```

Without `key=str.lower`, uppercase letters sort before *all* lowercase
letters, so `"john McEnroe"` would land after every capitalized
name."""


@app.slide("Title", cells=[])
def slide_title():
    """"""


@app.slide("Lists: Container, Element, Index", cells=["list_basics"])
def slide_1():
    """"""


@app.slide("In-Place Modification", cells=["in_place_modification"])
def slide_2():
    """"""


@app.slide("Adding and Removing Elements", cells=["append_pop_remove"])
def slide_3():
    """"""


@app.slide("Sequence-Type Functions and Methods", cells=["sequence_functions_table"])
def slide_4():
    """"""


@app.slide("List Slicing", cells=["list_slicing"])
def slide_5():
    """"""


@app.slide("List Methods", cells=["list_methods_table"])
def slide_6():
    """"""


@app.slide("List Nesting: 2D Lists", cells=["list_nesting"])
def slide_7():
    """"""


@app.slide("Iterating Multi-Dimensional Lists", cells=["nested_for_loops"])
def slide_8():
    """"""


@app.slide("Membership Operators: in / not in", cells=["membership_operators"])
def slide_9():
    """"""


@app.slide("Identity Operators: is / is not", cells=["identity_operators"])
def slide_10():
    """"""


@app.slide("Splitting and Joining Strings", cells=["split_and_join"])
def slide_11():
    """"""


@app.slide("Sorting Lists", cells=["sorting_lists"])
def slide_12():
    """"""
