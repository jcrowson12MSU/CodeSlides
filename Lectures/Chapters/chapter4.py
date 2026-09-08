"""Branches -- lecture deck built from Lectures/ZybooksNotes/Chapter 4
(zyBooks CSE 1284, sections 4.1-4.7 and 4.9-4.11; section 4.8's source
PDF was not provided and is skipped).

Like chapter1.py/chapter2.py/chapter3.py, this deck is deliberately
straight-line code -- no `def` anywhere inside a cell body, since
functions haven't been taught yet. Every cell's own MAIN code editor is
hidden (`hide_code=True`); the runnable/editable code a student sees and
can experiment with lives in one or more `ui.tests(...)` boxes instead,
mirroring zyBooks' own "type this exact program, run it, change the
input" pattern for `input()`-driven branch examples. The cell body
itself still computes real values from a `ui.text_input`-bound stand-in
for `input()` wherever zyBooks' own example read input, so the slide's
own live output (via `cs.md(...)`) has something real to react to,
exactly like input_and_prompts/simple_program in chapter1.py.

Where zyBooks used a flowchart/animation tool (branching concept,
hotel-rate/insurance-price traces, the AND/OR/NOT truth tables, the
precedence-rules tree, the code-block indentation figure) this deck
re-creates the same teaching point as Markdown (tables, worked traces)
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
    """# Branches

Eight zyBooks sections (4.1-4.7, 4.9-4.11) on how a program can take
different paths depending on a condition -- `if`, `elif`, `else`,
comparison and logical operators, ranges, nested branches, precedence,
indentation, and conditional expressions -- rebuilt as runnable
CodeSlides cells.

Every code sample lives in its own **test editor** below the notes,
not the slide's main editor -- run it, change it, break it.

Use **Slides** to step through in order, or **Cells** to jump straight
to a topic."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def branching_concept():
    """## Branches: The General Idea

A **branch** is a sequence of statements only executed under a certain
condition.

An **if branch** is a branch taken only *if* an expression is `True`.

**Example: a restaurant host seating patrons**

- Party of 1 &rarr; seated at the counter
- Party of 2 &rarr; seated at a small table
- Party of 3 or more &rarr; seated at a large table

The host mentally runs an algorithm: *if* party of 1, seat at the
counter; *else if* party of 2, seat at a small table; *else*, seat at
a large table. That "if / else if / else" structure is exactly what
the rest of this chapter writes in Python."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('user_age_text', default='68'),
        ui.tests('Hotel rate trace', default='hotel_rate = 155\nuser_age = 68\n\nif user_age > 65:\n    hotel_rate = hotel_rate - 20\n\nprint("Your rate:", hotel_rate)'),
    ],
    hide_code=True,
)
def if_branch_trace(user_age_text):
    """## An `if` Branch: Hotel Rate Example

A decision leads to two possible paths. If the expression is `True`,
the branch's statements execute; if `False`, they're skipped and
execution continues after the branch.

```python
hotel_rate = 155
user_age = int(input("Age: "))

if user_age > 65:
    hotel_rate = hotel_rate - 20

print("Your rate:", hotel_rate)
```

If `user_age` is `68`, then `68 > 65` is `True`, so the discount
applies and the rate becomes `135`. If `user_age` were `65` or under,
the branch would be skipped and the rate would stay `155`.

Type an age below -- try something over 65, then something under."""
    user_age = int(user_age_text)
    hotel_rate = 155
    if user_age > 65:
        hotel_rate = hotel_rate - 20
    return cs.md(f"**Your rate:** `{hotel_rate}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('val_text', default='-7'),
        ui.tests('Absolute value', default='val = -7\nif val < 0:\n    val = -val\n\nprint(val)'),
    ],
    hide_code=True,
)
def if_else_absolute_value(val_text):
    """## `if`-`else`: Computing Absolute Value

An **`if`-`else` branch** has two branches: the first executes *if* an
expression is `True`; otherwise, the *else* branch executes.

```python
val = int(input("Value: "))
if val < 0:
    val = -val

print(val)
```

If `val` is negative, it's flipped to positive; otherwise it's left
alone -- either way, the result printed is the absolute value.

Type a number below, positive or negative."""
    val = int(val_text)
    if val < 0:
        val = -val
    return cs.md(f"**Output:** `{val}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('num_years_text', default='50'),
        ui.tests('Hotel discount', default='num_years = 50\nhotel_rate = 150\n\nif num_years == 50:\n    print("Congratulations on 50 years of marriage!")\n    hotel_rate = hotel_rate / 2\n\nprint(f"Your hotel rate: ${hotel_rate:.2f}")'),
    ],
    hide_code=True,
)
def equality_operator(num_years_text):
    """## The Equality Operator: `==`

An **`if` statement** executes a group of statements *if* an
expression is `True`.

The **equality operator** (`==`) evaluates to `True` if the left and
right sides are equal.

```python
hotel_rate = 150
num_years = int(input("Enter years married: "))

if num_years == 50:
    print("Congratulations on 50 years of marriage!")
    hotel_rate = hotel_rate / 2

print(f"Your hotel rate: ${hotel_rate:.2f}")
```

If `num_years` is `50`, `num_years == 50` is `True`, so both indented
statements run: the congratulations message prints, and the rate is
cut in half.

Type a number of years below."""
    num_years = int(num_years_text)
    hotel_rate = 150
    message = ""
    if num_years == 50:
        message = "Congratulations on 50 years of marriage!"
        hotel_rate = hotel_rate / 2
    rate_line = f"Your hotel rate: ${hotel_rate:.2f}"
    return cs.md(f"**Output:**\n\n```text\n{message + chr(10) if message else ''}{rate_line}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Equality vs inequality', default='x = 3\nprint(x == 3)\nprint(x == 4)\nprint(x != 3)\nprint(x != 4)'),
    ],
    hide_code=True,
)
def equality_inequality_table():
    """## Equality and Inequality Operators

A **Boolean** is a type that has just two values: `True` or `False`.

| Operator | Description | Example (`x = 3`) |
| --- | --- | --- |
| `==` | `a == b` means `a` is equal to `b`. | `x == 3` is `True`; `x == 4` is `False` |
| `!=` | `a != b` means `a` is not equal to `b`. | `x != 3` is `False`; `x != 4` is `True` |

The **inequality operator** (`!=`) evaluates to `True` if the left and
right sides are *different*."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('user_num_text', default='22'),
        ui.tests('Even or odd', default='user_num = 22\ndiv_remainder = user_num % 2\n\nif div_remainder == 0:\n    print(f"{user_num} is even.")\nelse:\n    print(f"{user_num} is odd.")'),
    ],
    hide_code=True,
)
def if_else_even_odd(user_num_text):
    """## `if`-`else`: Even or Odd

An **`if`-`else` statement** executes one group of statements when an
expression is `True`, and another group when it's `False`.

```python
user_num = int(input("Enter a number: "))
div_remainder = user_num % 2

if div_remainder == 0:
    print(f"{user_num} is even.")
else:
    print(f"{user_num} is odd.")
```

`user_num % 2` is the remainder of dividing by 2 -- `0` for even
numbers, `1` for odd ones.

Type a number below."""
    user_num = int(user_num_text)
    div_remainder = user_num % 2
    if div_remainder == 0:
        result = f"{user_num} is even."
    else:
        result = f"{user_num} is odd."
    return cs.md(f"**Output:** `{result}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('num_years_text2', default='25'),
        ui.tests('Anniversaries', default='num_years = 25\n\nif num_years == 1:\n    print("Your first year -- great!")\nelif num_years == 10:\n    print("A whole decade -- impressive.")\nelif num_years == 25:\n    print("Your silver anniversary -- enjoy.")\nelif num_years == 50:\n    print("Your golden anniversary -- amazing.")\nelse:\n    print("Nothing special.")'),
    ],
    hide_code=True,
)
def elif_anniversaries(num_years_text2):
    """## `elif`: Additional Branches

Additional branches use the **`elif`** keyword, which means "else if".

```python
if expression1:
    ...  # first branch
elif expression2:
    ...  # second branch, only checked if expression1 was False
else:
    ...  # third branch, only if every expression above was False
```

Only **one** branch in the whole chain ever executes -- as soon as one
condition is `True`, Python runs that branch and skips the rest.

```python
num_years = int(input("Enter number years married: "))

if num_years == 1:
    print("Your first year -- great!")
elif num_years == 10:
    print("A whole decade -- impressive.")
elif num_years == 25:
    print("Your silver anniversary -- enjoy.")
elif num_years == 50:
    print("Your golden anniversary -- amazing.")
else:
    print("Nothing special.")
```

Type a number of years below and watch exactly one message appear."""
    num_years = int(num_years_text2)
    if num_years == 1:
        message = "Your first year -- great!"
    elif num_years == 10:
        message = "A whole decade -- impressive."
    elif num_years == 25:
        message = "Your silver anniversary -- enjoy."
    elif num_years == 50:
        message = "Your golden anniversary -- amazing."
    else:
        message = "Nothing special."
    return cs.md(f"**Output:** `{message}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def ranges_general():
    """## Detecting Ranges With Branches

An `if`-`elif`-`else` chain can also capture **ranges**, not just
exact values. Each branch's condition only runs when every earlier
branch's condition was `False` -- so a later branch's low end is
whatever the previous branch's condition ruled out.

**Example: youth soccer teams by age**

```text
If age < 6:       No team
Elif age < 8:      U8 team    (covers ages 6-7)
Elif age < 10:     U10 team   (covers ages 8-9)
Elif age < 12:     U12 team   (covers ages 10-11)
Else:              No team    (age 12+)
```

Notice the `U8` branch's condition is just `age < 8` -- it doesn't
also need to say `age >= 6`, because if that were true, the *first*
branch (`age < 6`) would already have run and skipped everything
after it."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('relational_x_text', default='3'),
        ui.tests('Relational operators', default='x = 3\nprint(x < 4)\nprint(x > 2)\nprint(x <= 3)\nprint(x >= 4)'),
    ],
    hide_code=True,
)
def relational_operators_table(relational_x_text):
    """## Relational Operators

A **relational operator** checks how one operand's value relates to
another.

| Operator | Description | Example (`x = 3`) |
| --- | --- | --- |
| `<` | `a < b` means `a` is less than `b`. | `x < 4` is `True`; `x < 3` is `False` |
| `>` | `a > b` means `a` is greater than `b`. | `x > 2` is `True`; `x > 3` is `False` |
| `<=` | `a <= b` means `a` is less than or equal to `b`. | `x <= 4` and `x <= 3` are `True`; `x <= 2` is `False` |
| `>=` | `a >= b` means `a` is greater than or equal to `b`. | `x >= 2` and `x >= 3` are `True`; `x >= 4` is `False` |

Try a value below and see how it compares to `4`."""
    x = int(relational_x_text)
    return cs.md(
        f"`x = {x}`\n\n"
        f"| Expression | Result |\n| --- | --- |\n"
        f"| `x < 4` | `{x < 4}` |\n"
        f"| `x > 4` | `{x > 4}` |\n"
        f"| `x <= 4` | `{x <= 4}` |\n"
        f"| `x >= 4` | `{x >= 4}` |"
    )


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('insurance_age_text', default='27'),
        ui.tests('Insurance price by age', default='user_age = 27\n\nif user_age < 16:      # Age 15 and under\n    print("Too young.")\n    insurance_price = 0\nelif user_age < 25:    # Age 16 - 24\n    insurance_price = 4800\nelif user_age < 40:    # Age 25 - 39\n    insurance_price = 2350\nelse:                   # Age 40 and up\n    insurance_price = 2100\n\nprint(f"Annual price: ${insurance_price}")'),
    ],
    hide_code=True,
)
def ranges_insurance(insurance_age_text):
    """## Detecting Ranges: Insurance Prices

Because each `elif` only runs when every earlier condition was
`False`, a chain of `<` comparisons can carve age into ranges without
ever writing the range's lower bound explicitly.

```python
user_age = int(input("Enter your age: "))

if user_age < 16:      # Age 15 and under
    print("Too young.")
    insurance_price = 0
elif user_age < 25:    # Age 16 - 24
    insurance_price = 4800
elif user_age < 40:    # Age 25 - 39
    insurance_price = 2350
else:                   # Age 40 and up
    insurance_price = 2100

print(f"Annual price: ${insurance_price}")
```

Trace `user_age = 27`: `27 < 16` is `False`, `27 < 25` is `False`,
`27 < 40` is `True` &rarr; `insurance_price = 2350`.

Type an age below and watch which range it lands in."""
    user_age = int(insurance_age_text)
    too_young = ""
    if user_age < 16:
        too_young = "Too young.\n"
        insurance_price = 0
    elif user_age < 25:
        insurance_price = 4800
    elif user_age < 40:
        insurance_price = 2350
    else:
        insurance_price = 2100
    return cs.md(f"**Output:**\n\n```text\n{too_young}Annual price: ${insurance_price}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('AND / OR / NOT', default='x, y = 7, 9\nprint((x > 0) and (y < 10))\nprint((x > 0) and (y < 5))\nprint((x < 0) or (y > 5))\nprint(not (x < 0))'),
    ],
    hide_code=True,
)
def logical_operators():
    """## Logical Operators: `and`, `or`, `not`

A **logical operator** treats its operands as `True`/`False` and
evaluates to `True` or `False`. Python's logical operators are the
lowercase keywords **`and`**, **`or`**, and **`not`**.

| a | b | `a and b` | `a or b` |
| --- | --- | --- | --- |
| `False` | `False` | `False` | `False` |
| `False` | `True` | `False` | `True` |
| `True` | `False` | `False` | `True` |
| `True` | `True` | `True` | `True` |

| a | `not a` |
| --- | --- |
| `False` | `True` |
| `True` | `False` |

With `x = 7, y = 9`:

- `(x > 0) and (y < 10)` &rarr; `True and True` &rarr; **`True`**
- `(x > 0) and (y < 5)` &rarr; `True and False` &rarr; **`False`**
- `(x < 0) or (y > 5)` &rarr; `False or True` &rarr; **`True`**
- `not (x < 0)` &rarr; operand is `False` &rarr; **`True`**"""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('channel_text', default='3'),
        ui.tests('Cable TV channel ranges', default='user_channel = 3\n\nif (user_channel >= 2) and (user_channel <= 499):\n    channel_type = "standard"\nelif (user_channel >= 1002) and (user_channel <= 1499):\n    channel_type = "HD"\nelse:\n    channel_type = "not a channel"\n\nprint(channel_type)'),
    ],
    hide_code=True,
)
def and_for_ranges(channel_text):
    """## Using `and` to Detect a Range

A number line makes the pattern clear: the range `10 < x < 15` (values
`11`, `12`, `13`, `14`) is the *overlap* of two half-open ranges --
`x` above `10` **and** `x` below `15`:

```python
10 < x and x < 15
```

Applied to a real range check -- cable TV channels:

```python
user_channel = int(input("Channel: "))

if (user_channel >= 2) and (user_channel <= 499):
    channel_type = "standard"
elif (user_channel >= 1002) and (user_channel <= 1499):
    channel_type = "HD"
else:
    channel_type = "not a channel"

print(channel_type)
```

Both bounds of each range are checked explicitly here, since standard
and HD channel numbers don't sit next to each other.

Type a channel number below."""
    user_channel = int(channel_text)
    if 2 <= user_channel <= 499:
        channel_type = "standard"
    elif 1002 <= user_channel <= 1499:
        channel_type = "HD"
    else:
        channel_type = "not a channel"
    return cs.md(f"**Output:** `{channel_type}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Boolean values', default='my_bool = True\nprint(my_bool)\n\nis_small = 4 < 3\nprint(is_small)'),
    ],
    hide_code=True,
)
def boolean_variables_and_logical_table():
    """## Boolean Variables and Logical Operators

A **Boolean** is a value that is either `True` or `False`, and a
variable can hold one directly:

```python
my_bool = True          # Assigns my_bool the boolean value True
is_small = 4 < 3         # Assigns is_small the result of 4 < 3 (False)
```

| Operator | Description |
| --- | --- |
| `a and b` | Boolean AND: `True` when *both* operands are `True`. |
| `a or b` | Boolean OR: `True` when *at least one* operand is `True`. |
| `not a` | Boolean NOT: `True` when the operand is `False`, and vice versa. |

With `age = 19, days = 7, user_char = "q"`:

| Expression | Result |
| --- | --- |
| `(age > 16) and (age < 25)` | `True` -- both operands `True` |
| `(age > 16) and (days > 10)` | `False` -- `days > 10` is `False` |
| `(age > 16) or (days > 10)` | `True` -- at least one is `True` |
| `not (days > 10)` | `True` -- operand is `False` |
| `not (age > 16)` | `False` -- operand is `True` |"""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Explicit vs implicit ranges', default='x = 15\n\n# Explicitly defined ranges\nif (x >= 0) and (x <= 10):\n    label = "0..10"\nelif (x >= 11) and (x <= 20):\n    label = "11..20"\nelse:\n    label = "21+"\nprint("explicit:", label)\n\n# Implicitly defined ranges (equivalent)\nif x <= 10:\n    label = "0..10"\nelif x <= 20:\n    label = "11..20"\nelse:\n    label = "21+"\nprint("implicit:", label)'),
    ],
    hide_code=True,
)
def implicit_vs_explicit_ranges():
    """## Implicit vs. Explicit Ranges

When ranges have **no gaps** between them, a multi-branch `if` can
drop the redundant lower bound -- the earlier branches already ruled
it out.

```python
# Explicitly defined ranges
if (x >= 0) and (x <= 10):
    ...
elif (x >= 11) and (x <= 20):
    ...
else:
    ...
```

```python
# Implicitly defined ranges -- equivalent, less redundant
if x <= 10:
    ...          # x >= 0 is implied
elif x <= 20:
    ...          # x > 10 is implied
else:
    ...          # x > 20 is implied
```

If the first branch didn't run, `x` must already be `> 10` -- so the
second branch only needs to check the upper bound. This is exactly the
same simplification the insurance-price example used earlier."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('movie_age_text', default='67'),
        ui.tests('Movie ticket price', default='user_age = 67\n\nif user_age <= 12:      # Age 12 and under\n    print("Child ticket discount.")\n    movie_ticket_price = 11\nelif user_age >= 65:    # Age 65 and older\n    print("Senior ticket discount.")\n    movie_ticket_price = 12\nelse:                    # All other ages\n    movie_ticket_price = 14\n\nprint(f"Movie ticket price: ${movie_ticket_price}")'),
    ],
    hide_code=True,
)
def ranges_with_gaps(movie_age_text):
    """## Detecting Ranges With Gaps

Not every range chain covers every value -- ages `13` through `64`
here fall in a **gap** between the child and senior discounts, and get
the `else` branch's default price.

```python
user_age = int(input("Enter your age: "))

if user_age <= 12:      # Age 12 and under
    print("Child ticket discount.")
    movie_ticket_price = 11
elif user_age >= 65:    # Age 65 and older
    print("Senior ticket discount.")
    movie_ticket_price = 12
else:                    # All other ages
    movie_ticket_price = 14

print(f"Movie ticket price: ${movie_ticket_price}")
```

Trace `user_age = 67`: `67 <= 12` is `False`, `67 >= 65` is `True`
&rarr; senior discount, `$12`.
Trace `user_age = 19`: both conditions `False` &rarr; the gap &rarr;
`$14`.

Type an age below."""
    user_age = int(movie_age_text)
    note = ""
    if user_age <= 12:
        note = "Child ticket discount.\n"
        movie_ticket_price = 11
    elif user_age >= 65:
        note = "Senior ticket discount.\n"
        movie_ticket_price = 12
    else:
        movie_ticket_price = 14
    return cs.md(f"**Output:**\n\n```text\n{note}Movie ticket price: ${movie_ticket_price}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('office_num_text', default='120'),
        ui.tests('Two disjoint valid ranges (elif form)', default='office_num = 120\n\nif office_num >= 100 and office_num <= 150:\n    valid = True\nelif office_num >= 200 and office_num <= 250:\n    valid = True\nelse:\n    valid = False\n\nprint("valid office number:", valid)'),
        ui.tests('Same check combined with or', default='office_num = 120\n\nif (office_num >= 100 and office_num <= 150) or (office_num >= 200 and office_num <= 250):\n    valid = True\nelse:\n    valid = False\n\nprint("valid office number:", valid)'),
    ],
    hide_code=True,
)
def gaps_and_or(office_num_text):
    """## Combining Gapped Ranges With `or`

Two *separate* valid ranges (with a gap between them) can be checked
with two `and`-joined conditions in an `elif` chain, or combined into
a **single** branch using `or`:

```python
# Two branches, one range each
if office_num >= 100 and office_num <= 150:
    valid = True
elif office_num >= 200 and office_num <= 250:
    valid = True
else:
    valid = False
```

```python
# One branch, both ranges combined with or
if (office_num >= 100 and office_num <= 150) or (office_num >= 200 and office_num <= 250):
    valid = True
else:
    valid = False
```

`and` picks out the lower/upper bound *within* one range; `or`
combines two whole ranges into one condition. Numbers outside both
ranges -- the gap -- fall through to `False` either way.

Type an office number below (try `120`, then `300`)."""
    office_num = int(office_num_text)
    valid = (100 <= office_num <= 150) or (200 <= office_num <= 250)
    return cs.md(f"**valid office number:** `{valid}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Multiple independent ifs', default='user_age = 26\n\n# Note that more than one "if" statement can execute\nif user_age < 16:\n    print("Enjoy your early years.")\n\nif user_age > 15:\n    print("You are old enough to drive.")\n\nif user_age > 17:\n    print("You are old enough to vote.")\n\nif user_age > 24:\n    print("Most car rental companies will rent to you.")\n\nif user_age > 34:\n    print("You can run for president.")'),
    ],
    hide_code=True,
)
def multiple_independent_ifs():
    """## Multiple, Independent `if` Statements

Separate `if` statements -- **not** joined by `elif` -- are each
checked on their own. Unlike an `elif` chain, more than one can
execute for the same run.

```python
user_age = 26

if user_age < 16:
    print("Enjoy your early years.")

if user_age > 15:
    print("You are old enough to drive.")

if user_age > 17:
    print("You are old enough to vote.")

if user_age > 24:
    print("Most car rental companies will rent to you.")

if user_age > 34:
    print("You can run for president.")
```

With `user_age = 26`, three separate `if`s are `True` (`> 15`, `> 17`,
`> 24`), so **three** lines print -- run it and count them."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Nested if-else', default='user_choice = 2\nnum_items = 5\n\nif user_choice == 1:\n    print("user_choice is 1")\nelif user_choice == 2:\n    if num_items < 0:\n        print("user_choice is 2 and num_items < 0")\n    else:\n        print("user_choice is 2 and num_items >= 0")\nelse:\n    print("user_choice is neither 1 or 2")'),
    ],
    hide_code=True,
)
def nested_if_else():
    """## Nested `if`-`else`

A branch's statements can include *any* valid statement -- including
another `if`-`else`. That's a **nested if-else statement**: a whole
second decision made only after the first one lands on a particular
branch.

```python
if user_choice == 1:
    print("user_choice is 1")
elif user_choice == 2:
    if num_items < 0:
        print("user_choice is 2 and num_items < 0")
    else:
        print("user_choice is 2 and num_items >= 0")
else:
    print("user_choice is neither 1 or 2")
```

With `user_choice = 2, num_items = 5`: the outer `elif` matches, then
the **inner** `if`-`else` runs its own check --
`num_items < 0` is `False`, so the inner `else` prints
`"user_choice is 2 and num_items >= 0"`.

Each level of nesting is its own independent decision, indented one
level deeper."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Evaluation-order trace', default='x, y, z = 7, 6, 3\nresult = y * z < x + 1 or z == 3\nprint(result)'),
    ],
    hide_code=True,
)
def precedence_rules():
    """## Order of Evaluation: Precedence Rules

The order operators are evaluated in is governed by **precedence
rules** -- highest to lowest:

| Operator | Category |
| --- | --- |
| `( )` | parentheses -- evaluated first |
| `* / % + -` | arithmetic |
| `< <= > >= == !=` | relational, (in)equality |
| `not` | logical NOT |
| `and` | logical AND |
| `or` | logical OR |

Worked example, `x = 7, y = 6, z = 3`:

```python
y * z < x + 1 or z == 3
```

Think of it as a tree, evaluated bottom-up:

1. `y * z` &rarr; `18`
2. `x + 1` &rarr; `8`
3. `18 < 8` &rarr; `False`
4. `z == 3` &rarr; `True`
5. `False or True` &rarr; **`True`**

Arithmetic first, then relational/equality, then `not`, then `and`,
then `or` last."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Indentation defines the block', default='year = 1965\nmodel = "Ford"\n\nantique = False\ndomestic = False\n\nif year < 1970:\n    # indented 4 columns -- inside the if block\n    antique = True\n\nif model in ["Ford", "Chevrolet", "Dodge"]:\n  # indented 2 columns -- any amount > 0 works\n  domestic = True\n\nif antique:\n    if domestic:\n        # nested block: 4 more columns (8 total)\n        print("My own model-T still runs like a charm...")'),
    ],
    hide_code=True,
)
def code_blocks_indentation():
    """## Code Blocks and Indentation

A **code block** is a series of statements grouped together. In
Python, a block is indicated purely by **indentation** -- there are no
braces `{}` like some other languages use.

```python
if year < 1970:
    # new block: indented 4 columns
    antique = True

if model in ["Ford", "Chevrolet", "Dodge"]:
  # new block: indented 2 columns -- any amount > 0 is OK
  domestic = True

if antique:
    if domestic:
        # nested block: 4 more columns (8 total)
        print("My own model-T still runs like a charm...")
```

The exact number of spaces doesn't matter, as long as **every
statement in the same block uses the same indentation** -- mixing
amounts within one block is an `IndentationError`. Long lines inside
parentheses (a multi-line string, a long function call, a list or
dict literal) can also wrap across lines; indentation there is just
for readability, not a new block."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('my_number_text', default='7'),
        ui.tests('Conditional expression', default='my_number = 7\nyour_number = 0 if my_number <= 9 else 4\nprint(your_number)'),
    ],
    hide_code=True,
)
def conditional_expressions(my_number_text):
    """## Conditional Expressions

A **conditional expression** packs a whole `if`-`else` into a single
line:

```text
expr_when_true if condition else expr_when_false
```

This:

```python
if condition:
    my_var = expr1
else:
    my_var = expr2
```

is equivalent to:

```python
my_var = expr1 if condition else expr2
```

The condition is evaluated first; if `True`, `expr1` is evaluated and
assigned; if `False`, `expr2` is used instead.

```python
my_number = int(input("Number: "))
your_number = 0 if my_number <= 9 else 4
print(your_number)
```

Type a number below -- `9` or under gives `0`, anything higher gives
`4`."""
    my_number = int(my_number_text)
    your_number = 0 if my_number <= 9 else 4
    return cs.md(f"**Output:** `{your_number}`")


@app.slide("Title", cells=[])
def slide_title():
    """"""


@app.slide("Branches: The General Idea", cells=["branching_concept"])
def slide_1():
    """"""


@app.slide("An if Branch: Hotel Rate", cells=["if_branch_trace"])
def slide_2():
    """"""


@app.slide("if-else: Absolute Value", cells=["if_else_absolute_value"])
def slide_3():
    """"""


@app.slide("The Equality Operator: ==", cells=["equality_operator"])
def slide_4():
    """"""


@app.slide("Equality and Inequality", cells=["equality_inequality_table"])
def slide_5():
    """"""


@app.slide("if-else: Even or Odd", cells=["if_else_even_odd"])
def slide_6():
    """"""


@app.slide("elif: Additional Branches", cells=["elif_anniversaries"])
def slide_7():
    """"""


@app.slide("Detecting Ranges With Branches", cells=["ranges_general"])
def slide_8():
    """"""


@app.slide("Relational Operators", cells=["relational_operators_table"])
def slide_9():
    """"""


@app.slide("Ranges: Insurance Prices", cells=["ranges_insurance"])
def slide_10():
    """"""


@app.slide("Logical Operators: and, or, not", cells=["logical_operators"])
def slide_11():
    """"""


@app.slide("Using and to Detect a Range", cells=["and_for_ranges"])
def slide_12():
    """"""


@app.slide("Boolean Variables", cells=["boolean_variables_and_logical_table"])
def slide_13():
    """"""


@app.slide("Implicit vs Explicit Ranges", cells=["implicit_vs_explicit_ranges"])
def slide_14():
    """"""


@app.slide("Ranges With Gaps", cells=["ranges_with_gaps"])
def slide_15():
    """"""


@app.slide("Combining Gapped Ranges With or", cells=["gaps_and_or"])
def slide_16():
    """"""


@app.slide("Multiple Independent ifs", cells=["multiple_independent_ifs"])
def slide_17():
    """"""


@app.slide("Nested if-else", cells=["nested_if_else"])
def slide_18():
    """"""


@app.slide("Order of Evaluation: Precedence", cells=["precedence_rules"])
def slide_19():
    """"""


@app.slide("Code Blocks and Indentation", cells=["code_blocks_indentation"])
def slide_20():
    """"""


@app.slide("Conditional Expressions", cells=["conditional_expressions"])
def slide_21():
    """"""
