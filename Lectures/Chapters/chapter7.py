"""Loops -- lecture deck built from Lectures/ZybooksNotes/Chapter 7
(zyBooks CSE 1284, sections 7.1-7.13, 7.15) and
Lectures/ZybooksNotes/Chapter 7/chapter 7 plan.md.

Like chapter1.py/chapter2.py/chapter3.py/chapter4.py/chapter6.py, this
deck is deliberately straight-line code -- no `def` anywhere inside a
cell body, since functions haven't been taught yet. Every cell's own
MAIN code editor is hidden (`hide_code=True`); the runnable/editable
code a student sees and can experiment with lives in one or more
`ui.tests(...)` boxes instead, mirroring zyBooks' own "type this exact
program, run it, change the input" pattern.

The plan doc has two halves, separated by its own `---`. The first
half (while loops -- the general loop concept, Python's `while` syntax,
sentinel values, infinite loops, a counter variable) became the cells
up through `sentinel_vs_counter` below; several of those cells' own
notes carry hand-edits made directly in this file after the fact (typos
and all -- left exactly as written, never "cleaned up"). The second
half (`for_loop_intro` onward) is `for` loops: ranges, comparing `for`
to `while`, list comprehensions, nested loops, `break`, `enumerate()`/
`zip()`. Per that section's own instruction, its worked examples are
new code, not reused from the zyBooks sections OR from chapter6.py's
own earlier (nested, `enumerate()`-only) `for`-loop example."""

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
    """# While Loops

Four zyBooks sections (7.1-7.4) on `while` loops -- the general loop
concept, Python's `while` syntax, sentinel values, infinite loops, and
using a loop variable to count -- rebuilt as runnable CodeSlides
cells.

Every code sample lives in its own **test editor** below the notes,
not the slide's main editor -- run it, change it, break it.

Use **Slides** to step through in order, or **Cells** to jump straight
to a topic."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('if vs. while', default='attempts = 0\n\nprint("--- if version (runs once) ---")\n\nif attempts < 3:\n    print(f"attempt {attempts}")\n    attempts = attempts + 1\n\nprint(f"after if: attempts = {attempts}")\n\n\nprint("--- while version (repeats) ---")\nattempts = 0\nwhile attempts < 3:\n    print(f"attempt {attempts}")\n    attempts = attempts + 1\nprint(f"after while: attempts = {attempts}")\n'),
    ],
    hide_def=True,
    hide_code=True,
)
def while_vs_if():
    """## While Loops vs. `if` Statements

A **loop** is a program construct that repeatedly executes a block of
statements -- the **loop body** -- as long as a boolean expression
stays `True`. Each pass through the loop body is one **iteration**.

An `if` statement and a `while` loop share the exact same shape: a
boolean expression, then an indented block that runs only when that
expression is `True`.

```python
if condition:
    # body runs 0 or 1 times

while condition:
    # body runs 0 or many times
```

The difference is what happens after the body finishes. An `if`
statement's body runs *at most once* and execution moves on. A `while`
loop's body, once it finishes, jumps back up and **reevaluates the
same boolean expression** -- if it's still `True`, the body runs
again. Only once the expression evaluates to `False` does execution
finally move past the loop.

```python
while expression:      # reevaluated at the top of every iteration
    # loop body
# execution lands here once expression is False
```

Run the test box below and compare: the `if` block prints one line no
matter what, but the `while` block keeps iterating -- printing and
incrementing `attempts` -- until `attempts < 3` finally turns
`False`."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('countdown_start_text', default='5'),
        ui.tests('Rocket launch countdown', default='seconds = int(input("Countdown timer: "))\n\nwhile seconds > 0:\n    print(seconds)\n    seconds = seconds - 1\n\nprint("Liftoff!")\n'),
    ],
)
def simple_while_example(countdown_start_text):
    """## A Simple While Loop: Countdown

Here's a `while` loop that counts a rocket launch down to liftoff.

```python
seconds = 5

while seconds > 0:
    print(seconds)
    seconds = seconds - 1

print("Liftoff!")
```
```text
5
4
3
2
1
Liftoff!
```

Tracing it out: `seconds` starts at `5`. The loop condition
`seconds > 0` is checked `True` so the body runs: `5` is
printed, and `seconds` becomes `4`. That's **one iteration**. The
condition is checked again still `True` so a second iteration
prints `4` and decrements to `3`. This repeats for a total of five
iterations (printing `5, 4, 3, 2, 1`), and on the sixth check,
`seconds > 0` is `0 > 0`, which is `False`, so the loop ends and
`"Liftoff!"` prints.

Type a starting number of seconds below to see the countdown output
change."""
    try:
        start = int(countdown_start_text)
        seconds = start
        lines = []
        while seconds > 0:
            lines.append(str(seconds))
            seconds = seconds - 1
        lines.append('Liftoff!')
        output = '\n'.join(lines)
        countdown_result = cs.md(f'**Output:**\n```text\n{output}\n```')
    except ValueError:
        countdown_result = cs.md('**Output:** enter a whole number')
    return countdown_result


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Largest temperature reading', default='readings = [68, 74, 71, 80, 77]\n\nindex = 0\nlargest = readings[0]\n\nwhile index < len(readings):\n    if readings[index] > largest:\n        largest = readings[index]\n    index = index + 1\n\nprint(f"Largest reading: {largest}")\n'),
    ],
    hide_code=True,
    layout={'column_fraction': 0.32471264367816094, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'Largest temperature reading': 'top-right'}, 'extra_code_fraction': 0.5},
)
def while_over_list():
    """## Finding the Largest Item

A `while` loop can walk through a list one element at a time by
tracking the current position with an **index variable**, stopping
once the index reaches the list's length.

## Code discussion:
`largest` is initialized to the *first* element (not some placeholder like `-1`) since these temperature readings could legitimately be negative. 

Each iteration compares the current element, `readings[index]`, against the best value seen so far, replacing `largest` whenever a bigger reading turns up. `index` is incremented on every iteration regardless forgetting that line would leave `index` stuck at `0` and turn this into an infinite loop."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'Sentinel-controlled grocery list',
            default=(
                'print("Enter grocery items one at a time.")\n'
                'print("Type \'done\' when you\'re finished.\\n")\n\n'
                'item = input("Item: ")\n'
                'items = []\n\n'
                'while item != "done":\n'
                '    items.append(item)\n'
                '    item = input("Item: ")\n\n'
                'print(f"\\nGrocery list ({len(items)} items): {items}")\n'
            ),
        ),
    ],
    hide_code=True,
)
def sentinel_values():
    """## Sentinel Values

A **sentinel value** is a special value that signals a loop to stop it isn't real data, it's a stop sign. A loop controlled by a sentinel keeps running until that specific value shows up, so the *user* (or the data itself) decides when the loop ends, not a fixed count baked into the code.

Here, a shopper builds a grocery list by typing one item per prompt, and signals they're done by typing `"done"`:

If a shopper types `milk`, `eggs`, `done`, the loop runs for two
iterations (adding `"milk"` and `"eggs"`) -- the third input, `"done"`, never gets appended; it just makes the condition `False` and ends the loop. `"done"` here plays the exact same role `-1` played for the\\ `readings`/average examples back in 7.1, or `"star"` played for the
password example in 7.2 any value works as a sentinel as long as it can't be confused with real data."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'Finite loop',
            default=(
                'count = 0\n'
                'while count < 5:\n'
                '    print(count)\n'
                '    count = count + 1\n'
                'print("done -- finite, ran exactly 5 times")\n'
            ),
        ),
        ui.tests(
            'Indefinite loop (sentinel)',
            default=(
                'total = 0\n'
                'value = int(input("Enter a number (0 to stop): "))\n'
                'while value != 0:\n'
                '    total = total + value\n'
                '    value = int(input("Enter a number (0 to stop): "))\n'
                'print(f"Total: {total}")\n'
            ),
        ),
        ui.tests(
            'Infinite loop -- DO NOT RUN without a fix',
            default=(
                '# count = 0\n'
                '# while count < 5:\n'
                '#     print(count)\n'
                '#     # forgot to update count -- count < 5 is always True\n'
                '\n'
                '# Uncomment above to see the bug, or fix it by adding:\n'
                '# count = count + 1\n'
                'print("This box is commented out on purpose -- see the notes.")\n'
            ),
        ),
    ],
    hide_code=True,
)
def loop_duration_types():
    """Come back on Monday
## Finite, Indefinite, and Infinite Iteration

Loops can be grouped by whether and how the number of iterations
is known ahead of time.

**Finite iteration the number of iterations is known before the loop starts, usually because a counter runs up to a fixed limit.

**Indefinite iteration** -- the number of iterations depends on
something not known in advance, like user input or a sentinel value.
The countdown and sentinel examples above are both indefinite: nobody
knows how many groceries a shopper will type before `"done"`.

**Infinite iteration** -- the loop's condition never becomes `False`,
so it never stops on its own. This is usually a bug -- most often
forgetting to update the loop variable inside the body:


An infinite loop isn't always a mistake, though -- a video game's main
loop (`while True:`, checking for input every pass) is intentionally
infinite, and is only ever exited with a `break` or by closing the
program."""


@app.cell(
    instance='editable',
    elements=[
        ui.text_input('gcd_a_text', default='48'),
        ui.text_input('gcd_b_text', default='18'),
        ui.notes('notes'),
        ui.tests('GCD with an iteration counter', default='num_a = int(input("Enter first positive integer: "))\nnum_b = int(input("Enter second positive integer: "))\n\niteration_count = 0   # counter variable\n\nwhile num_a != num_b:\n    if num_a > num_b:\n        num_a = num_a - num_b\n    else:\n        num_b = num_b - num_a\n    iteration_count = iteration_count + 1\n\nprint(f"GCD is {num_a}")\nprint(f"Found in {iteration_count} iterations")\n'),
    ],
    hide_code=True,
    layout={'column_fraction': 0.4408783783783784, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'GCD with an iteration counter': 'top-right'}, 'extra_code_fraction': 0.5},
)
def gcd_with_counter(gcd_a_text, gcd_b_text):
    """## Greatest Common Divisor, with a Counter Variable

zyBooks' GCD program uses Euclid's subtraction algorithm to find the **greatest common divisor** of two positive integers: repeatedly
subtract the smaller value from the larger until they're equal that shared value is the GCD.


A **counter variable** is a loop variable whose only job is to *count* iterations it starts at `0` (or `1`) and is incremented by a fixed amount, usually `1`, each time through the loop body. It doesn't drive the loop's condition; it just keeps a tally on the side. Adding one to
the GCD program answers "how many subtraction steps did that take?":

This is the behavior that I want for the breakpoint debugging behavior.

|iteration_count|num_a|num_b|
|---|---|---|
|1|30|18|
|2|12|18|
|3|12|6|
|4|6|6|


"""
    try:
        a = int(gcd_a_text)
        b = int(gcd_b_text)
        if a <= 0 or b <= 0:
            gcd_result = cs.md('**Output:** both numbers must be positive')
        else:
            iteration_count = 0
            while a != b:
                if a > b:
                    a = a - b
                else:
                    b = b - a
                iteration_count = iteration_count + 1
            gcd_result = cs.md(
                f'**Output:**\n```text\nGCD is {a}\nFound in {iteration_count} iterations\n```'
            )
    except ValueError:
        gcd_result = cs.md('**Output:** enter two whole numbers')
    return gcd_result


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'Sentinel variable vs. counter variable',
            default=(
                '# Sentinel variable: its VALUE stops the loop\n'
                'answer = ""\n'
                'while answer != "quit":\n'
                '    answer = input("Type quit to exit: ")\n'
                'print("Sentinel example done.\\n")\n\n'
                '# Counter variable: it just tallies iterations\n'
                'count = 0\n'
                'while count < 3:\n'
                '    print(f"iteration {count}")\n'
                '    count = count + 1\n'
                'print(f"Counter example done, ran {count} times.")\n'
            ),
        ),
    ],
    hide_code=True,
)
def sentinel_vs_counter():
    """## Sentinel Variable vs. Counter (Loop) Variable

Both a **sentinel variable** and a **counter variable** live inside a
`while` loop's condition, which can make them easy to mix up -- but
they play opposite roles.

A **sentinel variable** holds *data the loop is watching for* -- the
loop keeps running until that variable's value matches a specific stop
signal (the sentinel). Its value comes from *outside* the loop's own
bookkeeping -- typically user input, or the next item read from a
list or file.

```python
answer = ""
while answer != "quit":       # stop as soon as the VALUE is "quit"
    answer = input("Type quit to exit: ")
```

A **counter variable** (also called a **loop variable** when it's the
one driving the condition) holds *how many iterations have happened*
-- it starts at a known value and changes by a fixed, predictable
amount each pass, so the loop is (usually) finite and the exact
iteration count is knowable ahead of time.

```python
count = 0
while count < 3:              # stop once the COUNT reaches 3
    print(f"iteration {count}")
    count = count + 1
```

The quick test: if you can predict how many times a `while` loop will
run just by reading the code (no user input required), its loop
variable is acting as a counter. If the number of iterations depends
on outside data hitting a specific stop value, that variable is acting
as a sentinel. The GCD program above actually uses *both* at once:
`num_a != num_b` is the sentinel-style condition that ends the
algorithm, while `iteration_count` is a separate counter tracking how
long it took."""


@app.cell(
    instance='static',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def for_loop_intro():
    """# For Loops

Every `while` loop example so far has needed the same three pieces of
bookkeeping written out by hand: a starting value, a boolean condition
to check, and a line that updates a variable so the loop eventually
stops iterating.

A **`for` loop** is a different kind of loop built specifically for
**iterating** -- visiting each item in something, one at a time --
without writing that bookkeeping yourself. Python manages the starting
value, the stopping check, and the update automatically; the programmer
just says *what* to iterate over.

The rest of this chapter builds up `for` loops from the ground up: how
they iterate over ranges of numbers and over lists, when to reach for
one instead of a `while` loop, and several more things `for` loops make
easy -- comprehensions, nested loops, `enumerate()`, and `zip()`."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('range_stop_text', default='6'),
        ui.tests(
            'range() examples',
            default=(
                'print("range(6):", list(range(6)))\n'
                'print("range(2, 6):", list(range(2, 6)))\n'
                'print("range(2, 12, 3):", list(range(2, 12, 3)))\n'
                'print("range(10, 0, -2):", list(range(10, 0, -2)))\n'
            ),
        ),
    ],
)
def for_loops_and_ranges(range_stop_text):
    """## For Loops and `range()`

A `for` loop's basic shape is:

```python
for loop_variable in something_iterable:
    # body runs once per item, loop_variable holds the current one
```

`range()` generates a sequence of whole numbers without ever storing
them all in memory -- it's built specifically to pair with `for` loops
when what's needed is "do this N times" or "count from A to B."

```python
for count in range(5):
    print(count)
```
```text
0
1
2
3
4
```

`range()` takes the same **start / end / stride** shape as the slice
notation from Chapter 3 (`my_list[start:end:stride]`): `range(end)`
starts at `0`, `range(start, end)` starts wherever you say, and
`range(start, end, stride)` adds a step size -- negative to count
down. Just like slicing, `end` is never included in the result.

| Call | Produces |
| --- | --- |
| `range(6)` | `0, 1, 2, 3, 4, 5` |
| `range(2, 6)` | `2, 3, 4, 5` |
| `range(2, 12, 3)` | `2, 5, 8, 11` |
| `range(10, 0, -2)` | `10, 8, 6, 4, 2` |

`list(range(...))` is used above only to *print* every value at once
for comparison -- a real `for` loop never needs `list()`, it consumes
`range()`'s values directly, one at a time.

Type a stopping value below to see `range(0, that value)`'s own
values."""
    try:
        stop = int(range_stop_text)
        values = list(range(stop))
        range_demo_result = cs.md(f'**Output:** `range(0, {stop})` produces `{values}`')
    except ValueError:
        range_demo_result = cs.md('**Output:** enter a whole number')
    return range_demo_result


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'for vs. while, same job',
            default=(
                'print("--- for loop ---")\n'
                'for step in range(4):\n'
                '    print(f"step {step}")\n\n'
                'print("--- identical while loop ---")\n'
                'step = 0\n'
                'while step < 4:\n'
                '    print(f"step {step}")\n'
                '    step = step + 1\n'
            ),
        ),
    ],
    hide_code=True,
)
def for_vs_while():
    """## `for` Loops vs. `while` Loops

These two loops do exactly the same thing:

```python
for step in range(4):
    print(f"step {step}")

step = 0
while step < 4:
    print(f"step {step}")
    step = step + 1
```

The `for` version is shorter because Python is handling three things
automatically that the `while` version has to spell out by hand:

- **Creating the loop variable** -- `step` starts at `0` with no
  separate `step = 0` line needed.
- **Working toward the boolean condition becoming false** -- each pass
  through `range(4)` moves to the next value on its own; there's no
  `step = step + 1` to remember (or forget).
- **Managing the boolean condition itself** -- there's no `step < 4` to
  write at all; the loop simply ends once `range(4)` runs out of
  values.

That's also exactly where the risk of an infinite loop disappears: a
`while` loop only stops if its own body updates the right variable in
the right direction, but a `for` loop iterating over a range or a list
always has a known, finite number of items, so it's *guaranteed* to
finish.

**Rule of thumb:** when the number of iterations is knowable up front
(a fixed count, or "once per item in this list"), reach for a `for`
loop. Save `while` for when the stopping point depends on something
that can only be known while the program is running -- user input, a
sentinel value, or a condition that isn't a simple count."""


@app.cell(
    instance='editable',
    elements=[
        ui.text_input('lcm_a_text', default='4'),
        ui.text_input('lcm_b_text', default='6'),
        ui.notes('notes'),
        ui.tests(
            'LCM with a for loop',
            default=(
                'num_a = int(input("Enter first positive integer: "))\n'
                'num_b = int(input("Enter second positive integer: "))\n'
                'bigger = max(num_a, num_b)\n\n'
                'lcm = None\n'
                'for candidate in range(bigger, num_a * num_b + 1, bigger):\n'
                '    if candidate % num_a == 0 and candidate % num_b == 0:\n'
                '        lcm = candidate\n'
                '        break\n\n'
                'print(f"LCM is {lcm}")\n'
            ),
        ),
    ],
    hide_code=True,
)
def lcm_with_for_loop(lcm_a_text, lcm_b_text):
    """## Least Common Multiple, with a `for` Loop

Where the earlier GCD example used a `while` loop (its stopping point,
"until the two numbers are equal," isn't a fixed count), finding the
**least common multiple** of two numbers fits a `for` loop perfectly:
the only numbers worth checking are the multiples of the larger value,
and there's a known point to stop looking -- `num_a * num_b` is always
a common multiple, even if not the smallest one.

```python
bigger = max(num_a, num_b)
lcm = None
for candidate in range(bigger, num_a * num_b + 1, bigger):
    if candidate % num_a == 0 and candidate % num_b == 0:
        lcm = candidate
        break
```

`range()` here only ever produces multiples of `bigger` (its own
stride), so every `candidate` is already a multiple of one of the two
numbers -- the loop just checks each one against the *other* number
until it finds a match, then `break`s out immediately (more on `break`
later in this chapter).

Type two positive integers below to see their LCM."""
    try:
        a = int(lcm_a_text)
        b = int(lcm_b_text)
        if a <= 0 or b <= 0:
            lcm_result = cs.md('**Output:** both numbers must be positive')
        else:
            bigger = max(a, b)
            lcm = None
            for candidate in range(bigger, a * b + 1, bigger):
                if candidate % a == 0 and candidate % b == 0:
                    lcm = candidate
                    break
            lcm_result = cs.md(f'**Output:**\n```text\nLCM is {lcm}\n```')
    except ValueError:
        lcm_result = cs.md('**Output:** enter two whole numbers')
    return lcm_result


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'Doubling every price',
            default=(
                'prices = [4.50, 12.00, 7.25, 20.00]\n\n'
                'for index in range(len(prices)):\n'
                '    prices[index] = prices[index] * 2\n\n'
                'print(prices)\n'
            ),
        ),
    ],
    hide_code=True,
)
def modifying_list_with_for():
    """## Modifying a List with a `for` Loop

`for item in my_list:` is great for *reading* every element, but
`item` is just a copy of each value -- reassigning it doesn't change
the list:

```python
prices = [4.50, 12.00, 7.25, 20.00]
for item in prices:
    item = item * 2   # does NOT change prices
print(prices)          # unchanged
```

To actually modify the list, loop over its **indices** instead (via
`range(len(my_list))`) and assign back through `my_list[index]`:

```python
prices = [4.50, 12.00, 7.25, 20.00]
for index in range(len(prices)):
    prices[index] = prices[index] * 2
print(prices)
```
```text
[9.0, 24.0, 14.5, 40.0]
```

A `for` loop is the natural choice here -- and for iterating a list in
general -- because a list's length is already known the moment the
loop starts (`len(prices)` doesn't change while the loop runs), so
there's no need to track a separate counter or watch for a sentinel;
`range(len(prices))` visits each valid index exactly once."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'List comprehension',
            default=(
                'prices = [4.50, 12.00, 7.25, 20.00]\n\n'
                'doubled = [price * 2 for price in prices]\n\n'
                'print(doubled)\n'
            ),
        ),
    ],
    hide_code=True,
)
def list_comprehensions():
    """## List Comprehensions

A **list comprehension** builds a new list from an existing iterable
in a single line, instead of writing out a `for` loop that appends to
an empty list:

```python
prices = [4.50, 12.00, 7.25, 20.00]

doubled = []
for price in prices:
    doubled.append(price * 2)
```

is the same as:

```python
doubled = [price * 2 for price in prices]
```

The general shape is `[expression for loop_variable in iterable]` --
`expression` (usually built from `loop_variable`) is evaluated for
every item, and the results become the new list's elements.

A comprehension can also filter which items are included at all, by
adding `if condition` at the end:

```python
on_sale = [price for price in prices if price < 10]
```

This only keeps prices under `10`, skipping the rest entirely --
equivalent to a `for` loop with an `if` check before each `append()`.
Comprehensions read best for short, simple transformations; a regular
`for` loop is usually clearer once the logic needs more than one
line."""


@app.cell(
    instance='static',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def conditional_expression_review():
    """## Reminder: Conditional Expressions

Chapter 4 introduced the **conditional expression** -- an `if`-`else`
packed into a single expression:

```python
expr_when_true if condition else expr_when_false
```

It's worth keeping in mind heading into comprehensions: a
comprehension's own `expression` slot can *be* a conditional
expression, which is a different thing from the `if condition` filter
on the previous slide. `[x for x in nums if x > 0]` *removes* items;
`[x if x > 0 else 0 for x in nums]` *keeps every item*, just replacing
the negative ones with `0`. It's easy to reach for the wrong one --
when in doubt, ask whether the goal is "skip some items" (filter) or
"transform every item, differently depending on a condition"
(conditional expression)."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'Multiplication grid',
            default=(
                'for row in range(1, 4):\n'
                '    line = ""\n'
                '    for col in range(1, 4):\n'
                '        line = line + str(row * col) + "\\t"\n'
                '    print(line)\n'
            ),
        ),
    ],
    hide_code=True,
)
def nested_for_loop_example():
    """## Nested `for` Loops

A loop written inside another loop's body is a **nested loop** -- the
**outer loop** runs once per iteration of some larger task, and the
**inner loop** runs completely, start to finish, on *every single*
iteration of the outer one.

Printing a small multiplication grid needs one loop per dimension: the
outer loop picks a row number, the inner loop picks a column number for
that row, and each cell is their product:

```python
for row in range(1, 4):
    line = ""
    for col in range(1, 4):
        line = line + str(row * col) + "\\t"
    print(line)
```
```text
1	2	3
2	4	6
3	6	9
```

For every one of the outer loop's 3 iterations, the inner loop runs all
3 of its own iterations -- 9 total cell calculations for a 3x3 grid.
Nested loops like this are exactly how `chapter6.py`'s multi-dimensional
list examples visit every row and column."""


@app.cell(
    instance='static',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def fixme_comments():
    """## `FIXME` Comments

Real programs are rarely written all at once, correct on the first
try -- they're built up incrementally, one small piece at a time, with
each piece tested before moving to the next. A **`FIXME` comment**
marks a spot that's intentionally incomplete or known to be wrong, so
it isn't forgotten once the surrounding code starts to work:

```python
def grade_for(score):
    if score >= 90:
        return "A"
    # FIXME: only handles A grades so far -- add B/C/D/F (jc, 3/1)
    return "unknown"
```

`FIXME` (often tagged with an author's initials and a date, as above)
is a plain-text convention, not a Python keyword -- it works purely
because it's a distinctive word a programmer (or an editor's search
function) can scan for later. The same convention shows up as `TODO`
in a lot of real codebases; both mean the same thing. Leaving one is
almost always better than leaving a guess or a silent gap: it turns "I
hope I remember this later" into something searchable."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'break out of a while loop',
            default=(
                'target = "banana"\n'
                'fruit = ""\n\n'
                'while True:\n'
                '    fruit = input("Enter a fruit (or the secret word to stop): ")\n'
                '    if fruit == target:\n'
                '        print("Found it -- stopping early.")\n'
                '        break\n'
                '    print(f"{fruit} is not it, keep going.")\n'
            ),
        ),
    ],
    hide_code=True,
)
def break_with_while():
    """## `break`ing Out of a `while` Loop

A **`break` statement** immediately exits the loop it's inside --
execution jumps straight past the loop entirely, skipping any remaining
iterations, no matter what the loop's own boolean condition says.

`break` is especially handy with `while True:`, a loop that would
otherwise never stop on its own -- the exit condition is checked
*inside* the body instead of in the loop's own header:

```python
target = "banana"
while True:
    fruit = input("Enter a fruit (or the secret word to stop): ")
    if fruit == target:
        print("Found it -- stopping early.")
        break
    print(f"{fruit} is not it, keep going.")
```

Without the `break`, this loop would need its stopping condition
written into `while <condition>:` itself -- but the condition here
("the user just typed the secret word") can only be checked *after*
reading their input, which is why `while True:` plus an inner `if` and
`break` reads more naturally than trying to force the check into the
loop's own header."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests(
            'enumerate()',
            default=(
                'runners = ["Ava", "Noah", "Mia"]\n\n'
                'for place, runner in enumerate(runners, start=1):\n'
                '    print(f"{place}. {runner}")\n'
            ),
        ),
        ui.tests(
            'zip()',
            default=(
                'runners = ["Ava", "Noah", "Mia"]\n'
                'finish_times = [14.2, 14.8, 15.1]\n\n'
                'for runner, finish_time in zip(runners, finish_times):\n'
                '    print(f"{runner} finished in {finish_time} seconds")\n'
            ),
        ),
    ],
    hide_code=True,
)
def enumerate_and_zip():
    """## `enumerate()` and `zip()`

Two `for`-loop helpers that come up constantly once loops are iterating
over more than one thing at a time.

**`enumerate()`** pairs each item with its own index, so there's no
need for a separate counter variable or `range(len(...))`:

```python
runners = ["Ava", "Noah", "Mia"]
for place, runner in enumerate(runners, start=1):
    print(f"{place}. {runner}")
```
```text
1. Ava
2. Noah
3. Mia
```

`start=1` shifts where the numbering begins (`enumerate()` starts at
`0` by default) -- handy any time the count should read naturally to a
person, like places in a race rather than array indices.

**`zip()`** walks *multiple* lists together, pairing up their items by
position:

```python
runners = ["Ava", "Noah", "Mia"]
finish_times = [14.2, 14.8, 15.1]
for runner, finish_time in zip(runners, finish_times):
    print(f"{runner} finished in {finish_time} seconds")
```
```text
Ava finished in 14.2 seconds
Noah finished in 14.8 seconds
Mia finished in 15.1 seconds
```

Without `zip()`, pairing two lists up this way would mean looping over
indices instead (`for i in range(len(runners)):` then indexing into
both lists) -- `zip()` skips that entirely and hands over both values
directly, already matched up."""


@app.slide("Title", cells=[])
def slide_title():
    """"""


@app.slide("While Loops vs. if Statements", cells=["while_vs_if"])
def slide_1():
    """"""


@app.slide("A Simple While Loop: Countdown", cells=["simple_while_example"])
def slide_2():
    """"""


@app.slide("Iterating a List with While", cells=["while_over_list"])
def slide_3():
    """"""


@app.slide("Sentinel Values", cells=["sentinel_values"])
def slide_4():
    """"""


@app.slide("Finite, Indefinite, and Infinite Iteration", cells=["loop_duration_types"])
def slide_5():
    """"""


@app.slide("Greatest Common Divisor, with a Counter Variable", cells=["gcd_with_counter"])
def slide_6():
    """"""


@app.slide("Sentinel Variable vs. Counter Variable", cells=["sentinel_vs_counter"])
def slide_7():
    """"""


@app.slide("For Loops", cells=["for_loop_intro"])
def slide_8():
    """"""


@app.slide("For Loops and range()", cells=["for_loops_and_ranges"])
def slide_9():
    """"""


@app.slide("For Loops vs. While Loops", cells=["for_vs_while"])
def slide_10():
    """"""


@app.slide("Least Common Multiple, with a For Loop", cells=["lcm_with_for_loop"])
def slide_11():
    """"""


@app.slide("Modifying a List with a For Loop", cells=["modifying_list_with_for"])
def slide_12():
    """"""


@app.slide("List Comprehensions", cells=["list_comprehensions"])
def slide_13():
    """"""


@app.slide("Reminder: Conditional Expressions", cells=["conditional_expression_review"])
def slide_14():
    """"""


@app.slide("Nested For Loops", cells=["nested_for_loop_example"])
def slide_15():
    """"""


@app.slide("FIXME Comments", cells=["fixme_comments"])
def slide_16():
    """"""


@app.slide("Break with a While Loop", cells=["break_with_while"])
def slide_17():
    """"""


@app.slide("enumerate() and zip()", cells=["enumerate_and_zip"])
def slide_18():
    """"""
