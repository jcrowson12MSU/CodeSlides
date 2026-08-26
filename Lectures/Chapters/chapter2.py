"""Variables, Objects, and Expressions -- lecture deck built from
Lectures/ZybooksNotes/Chapter 2 (zyBooks CSE 1284, sections 2.1-2.8 and
2.10-2.12; section 2.9's source PDF was not provided and is skipped).

Like chapter1.py, this deck is deliberately straight-line code -- no
`def` anywhere inside a cell body, since functions haven't been taught
yet. Per instructions, this deck goes one step further than chapter1:
every cell's own MAIN code editor is hidden (`hide_code=True`), and any
runnable/editable code a student is meant to see or try lives instead
in a `ui.tests(...)` box. The cell body itself still computes real
values (so notes, text_input-bound demos, and tests all have something
live to react to), but the student-facing "here is Python, try it"
experience always happens in a test editor, never the main one.

Where zyBooks used a JS-driven visualization (the bus-riddle activity,
the interpreter/memory diagram, the name-binding animation), this deck
re-creates the same teaching point with a live `ui.text_input` or
`ui.slider` bound into the cell's own parameters, plus `cs.md(...)`
output describing what happened -- consistent with chapter1's pattern
of using a real reactive control as a stand-in for a canned animation.
"""

import math

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
    """# Variables, Objects, and Expressions

Twelve zyBooks sections (2.1-2.8, 2.10-2.12) on how Python remembers,
names, types, and combines values -- rebuilt as runnable CodeSlides
cells. Every code sample lives in its own **test editor** below the
notes, not the slide's main editor -- run it, change it, break it.

Use **Slides** to step through in order, or **Cells** to jump straight
to a topic."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('num_people', default='5'),
    ],
    hide_code=True,
)
def bus_riddle(num_people):
    """## Remembering a Value

Here's a variation on a children's riddle: *You are driving a bus.*

- The bus starts with **5** people.
- At the first stop, 3 people get off and 1 gets on.
- At the second stop, 2 people get off and 4 get on.

At every stop, something has to *remember* the current number of
people so the next stop can use it. The box below stands in for that
memory -- type the running total into it as you work through the
stops by hand.

The riddle's real ending question is "What is the bus driver's
name?" -- most people are so busy tracking the passenger count that
they forget the very first sentence already told them: ***you** are
driving the bus.*"""
    return cs.md(f"**Current num_people:** `{num_people}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Run it', default='x = 5\nprint(x)\n\ny = x\nprint(y)\n\nz = x + 2\nprint(z)\n\nx = 3\nprint(x, y, z)\n'),
    ],
    hide_code=True,
)
def variables_and_assignments():
    """## Variables and Assignments

In a program, a **variable** is a named item, such as `x` or
`num_people`, that holds a value.

```python
x = 5
```

An **assignment statement** assigns a variable with a value. That
statement means `x` is assigned with `5`, and `x` holds that value
during subsequent statements, until `x` is assigned again.

An assignment statement's left side must be a variable. The right
side can be any **expression** -- `5`, `x`, and `x + 2` are each an
expression that evaluates to a value.

```python
y = x       # y is assigned x's present value
z = x + 2   # z is assigned x's present value, plus 2
x = 3       # x's old value (5) is overwritten and lost; y and z keep theirs
```

Run the test below and watch: `y` and `z` don't change when `x` is
reassigned at the end -- only `x` does."""
    x = 5
    y = x
    z = x + 2
    x = 3
    return x, y, z


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def equals_is_not_equals():
    """## `=` Is Not Equals

In algebra, an equation means "the item on the left always equals the
item on the right." So for `x + y = 5` and `x * y = 6`, algebra lets
you *solve* for `x = 2` and `y = 3`.

Assignment statements look similar but mean something completely
different. In programming, `=` is **not** equality -- `x = 5` is read
as *"x is assigned with 5,"* never as *"x equals 5."* The `=` isn't a
question about equality; it's an action that **puts** a value into a
variable, executed once, in sequence, when that line runs.

Because of this, the left side of `=` must always be a single
variable -- `x + 1 = 3` and `x + y = y + x` are **not** valid
assignment statements in Python, even though both are valid algebra."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Variable on both sides', default='x = 1\nprint(x)\n\nx = x * 20\nprint(x)\n\nx = x * 20\nprint(x)\n'),
    ],
    hide_code=True,
)
def variable_both_sides():
    """## A Variable on Both Sides

Because `=` means assignment, not equality, a variable is allowed to
appear on *both* sides of one assignment statement:

```python
x = x + 1
```

The right side (`x + 1`) is evaluated first, using `x`'s **current**
value -- then the result is stored back into `x`, overwriting the old
value. Increasing a variable's value by 1 this way is called
**incrementing** the variable.

Only the *latest* value is ever held in a variable -- a variable has
no memory of what it used to be. Run the test: each `x = x * 20`
multiplies whatever `x` currently is."""
    x_grown = 1
    x_grown = x_grown * 20
    x_grown = x_grown * 20
    return x_grown


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Valid or invalid?', default='x = 1\nprint("valid: x = 1")\n\ny = 5\nx = y\nprint("valid: x = y")\n\nx = y + 2\nprint("valid: x = y + 2")\n\n# x + 1 = 3        # INVALID -- left side is an expression, not a variable\n# x + y = y + x    # INVALID -- left side is an expression, not a variable\n'),
    ],
    hide_code=True,
)
def valid_assignment_statements():
    """## Valid Assignment Statements

An assignment statement's left side **must** be a single variable.
The right side can be almost any expression.

| Statement | Valid? | Why |
| --- | --- | --- |
| `x = 1` | Valid | left side is a variable |
| `x = y` | Valid | left side is a variable |
| `x = y + 2` | Valid | left side is a variable |
| `x + 1 = 3` | **Invalid** | left side is an expression, not a variable |
| `x + y = y + x` | **Invalid** | left side is an expression, not a variable |

Uncomment the last two lines in the test below in your head -- Python
would raise a `SyntaxError` on either one, because `x + 1` can never
be the target of an assignment."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Name validator', default='name = "num_clementines"\nprint(name, "is a valid identifier")\n\n# 7isTheNumber      # INVALID -- starts with a digit\n# this is a variable # INVALID -- contains spaces\n\nthisIsAVariable = 1        # camelCase\nthis_is_a_variable = 2     # snake_case\nGRAVITY = 9.8               # ALL_CAPS, common for constants\nprint(thisIsAVariable, this_is_a_variable, GRAVITY)\n'),
    ],
    hide_def=True,
    hide_code=True,
)
def identifiers():
    """## Identifiers

An **identifier**, also called a **name**, is a sequence of letters
(`a`-`z`, `A`-`Z`), digits (`0`-`9`), and underscores, and must
**start with a letter or an underscore** -- never a digit.

Python is **case sensitive**: `name`, `Name`, and `NAME` are three
different identifiers.

**Reserved words** (keywords) are part of the Python language itself
and can't be used as a programmer-defined name: `False`, `None`,
`True`, `and`, `as`, `def`, `for`, `if`, `import`, `while`, ... and
more.

**PEP 8** (the Python Enhancement Proposal for style) recommends
`snake_case` for ordinary variable names, and `ALL_CAPS` for
constants like `GRAVITY`. Use **meaningful** names -- `num_students`
beats `ns` or `num`."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('id() and type()', default='x = 2 + 2\nprint(x)\nprint(type(x))\nprint(id(x))\n\nprint(type("ABC"))\nprint(id("ABC"))\n'),
    ],
    hide_code=True,
)
def objects():
    """## Objects

An **object** represents a value and is automatically created by the
Python interpreter whenever needed, such as when executing a line of
code like `x = 4`.

Every object has three things:

- **Value** -- a value such as `20`, `"abcdef"`, or `55`.
- **Type** -- the object's type, such as `int` or `str`. The built-in
  `type()` function returns it.
- **Identity** -- a unique identifier describing the object, given by
  the built-in `id()` function (its memory address).

**Garbage collection** is the automatic process of deleting an object
once nothing refers to it anymore, freeing up memory space -- a
programmer never has to do this by hand."""
    obj_value = 2 + 2
    return obj_value


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Name binding', default='bob_salary = 25000\ntom_salary = 30000\nprint("bob:", bob_salary, " tom:", tom_salary)\n\nbob_salary = tom_salary\nprint("after bob_salary = tom_salary  -->  bob:", bob_salary, " tom:", tom_salary)\n\ntom_salary = tom_salary * 1.2\nprint("after tom_salary = tom_salary * 1.2  -->  bob:", bob_salary, " tom:", tom_salary)\n\ntotal_salaries = bob_salary + tom_salary\nprint("total_salaries:", total_salaries)\n'),
    ],
    hide_code=True,
)
def name_binding():
    """## Name Binding

**Name binding** is the process of associating a name (a variable)
with an object in memory. The same object can have more than one name
bound to it, but every name is always bound to exactly one object at
a time. Name binding happens every time an assignment statement runs.

```python
bob_salary = 25000
tom_salary = 30000
bob_salary = tom_salary   # bob_salary now names the SAME object tom_salary does
tom_salary = tom_salary * 1.2   # tom_salary is rebound to a brand-new object
```

After `bob_salary = tom_salary`, both names are bound to the same
`30000` object -- the old `25000` object bob_salary used to name is
no longer referenced by anything, so it gets garbage collected.
Rebinding `tom_salary` to a new object afterward does **not** change
what `bob_salary` refers to."""
    bob_salary = 25000
    tom_salary = 30000
    bob_salary = tom_salary
    tom_salary = tom_salary * 1.2
    total_salaries = bob_salary + tom_salary
    return bob_salary, tom_salary, total_salaries


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Mutability check', default='age = 15\nprint("before:", age, id(age))\n\nage = age + 1   # this does NOT change the old object -- it rebinds age to a NEW object\nprint("after:", age, id(age))\n'),
    ],
    hide_code=True,
)
def mutability():
    """## Mutability

**Mutability** indicates whether an object's *value* is allowed to
change after it's created. **Integers and strings are immutable** --
an `int` or `str` object's value can never change once created.

This can be surprising: `age = age + 1` looks like it "changes"
`age`, but it doesn't mutate the old `15` object at all. Instead, a
**new** object (`16`) is created, and `age` is *rebound* to it -- the
old `15` object is left alone (and, if nothing else names it, garbage
collected).

Run the test and compare `id(age)` before and after -- it changes,
proving a new object was created rather than the old one being
edited in place."""
    age = 15
    age = age + 1
    return age


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('miles_text', default='450'),
    ],
    hide_code=True,
)
def floats(miles_text):
    """## Floating-Point Numbers

A **floating-point number** (a `float`) is a real number, like `98.6`
or `-666.667`. A **floating-point literal** always includes the
fractional part, even if it's `.0` -- `99.0`, not `99`.

```python
miles = float(input("Enter a distance in miles: "))
hours_to_fly = miles / 500.0
hours_to_drive = miles / 60.0
print(hours_to_fly, "hours to fly")
print(hours_to_drive, "hours to drive")
```

**Scientific notation** writes a float using an `e` for "times 10 to
the power of" -- `6.02e23` means $6.02 \\times 10^{23}$.

Type a distance into the box below -- it stands in for the
`input()` call above, and updates the flight/drive times live."""
    miles = float(miles_text)
    hours_to_fly = miles / 500.0
    hours_to_drive = miles / 60.0
    summary = (
        f"{miles} miles would take:\n"
        f"{hours_to_fly} hours to fly\n"
        f"{hours_to_drive} hours to drive"
    )
    return cs.md(f"```text\n{summary}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Overflow', default='print(2.0**256)\nprint(2.0**512)\nprint(2.0**1024)   # OverflowError -- result too large to store\n'),
    ],
    hide_code=True,
)
def float_overflow():
    """## OverflowError

**Overflow** occurs when a value is too large to be stored in the
memory the interpreter allocated for it. Assigning a floating-point
value outside Python's representable range raises an
**`OverflowError`**.

```python
print(2.0**256)    # 1.157920892373162e+77   -- fine
print(2.0**512)    # 1.3407807929942597e+154 -- fine
print(2.0**1024)   # OverflowError: (34, 'Result too large')
```

Run the test below and watch the traceback appear on the third
line -- a real, live `OverflowError`, not a description of one."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Rounding Pi', default='import math\n\nprint("Default output of Pi:", math.pi)\nprint("Pi reduced to 4 digits:", f"{math.pi:.4f}")\nprint("Pi reduced to 2 digits:", f"{math.pi:.2f}")\n'),
    ],
    hide_code=True,
)
def formatting_floats():
    """## Formatting Floats

Python doesn't try to print the *full, infinite* value of an
irrational number like $\\pi$ -- it outputs 15 digits after the
decimal point by default.

```python
import math
print(math.pi)                 # 3.141592653589793
print(f"{math.pi:.4f}")        # 3.1416  -- rounded to 4 digits
```

`f"{my_float:.Xf}"` formats `my_float` to exactly `X` digits after
the decimal point, rounding the last digit as needed. This is the
standard way to control how many decimal places a float displays."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('input_text', default='7.9'),
    ],
    hide_code=True,
)
def type_conversion(input_text):
    """## Type Conversions

A **type conversion** converts a value from one type to another, such
as converting a string to an integer. An **implicit conversion**
happens automatically, done by the Python interpreter itself (e.g.
between `int` and `float` in a mixed expression) -- everything else
is an **explicit** conversion, written by the programmer.

| Function | Creates | Can convert from |
| --- | --- | --- |
| `int()` | integer | int, float, strings containing only an integer |
| `float()` | float | int, float, strings with an integer or decimal |
| `str()` | string | anything |

```python
input_text = input("Enter a number: ")   # always a string
float_variable = float(input_text)       # string -> float
int_variable = int(float_variable)       # float -> int (drops the fraction)
```

Type a number into the box below -- the cell reruns and shows it
converted through `float()` and then `int()`."""
    float_variable = float(input_text)
    int_variable = int(float_variable)
    summary = (
        f"original input text: {input_text!r}\n"
        f"converted to a float: {float_variable}\n"
        f"float converted to an int: {int_variable}"
    )
    return cs.md(f"```text\n{summary}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('str() for concatenation', default='num_meters = 5.2\nstr_meters = str(num_meters)\n\nprint("Number of meters: " + str_meters)\n\n# print("Number of meters: " + num_meters)   # TypeError -- cant concatenate str + float\n'),
    ],
    hide_code=True,
)
def str_conversion():
    """## Converting to a String

`str()` converts (almost) any value into its string form -- useful
because `+` between a string and a non-string raises a `TypeError`
(strings can only concatenate with other strings):

```python
num_meters = 5.2
str_meters = str(num_meters)
print("Number of meters: " + str_meters)   # works: str + str
```

Without the `str(...)` conversion, `"Number of meters: " + num_meters`
would fail, because `num_meters` is a `float`, not a `str`. Run the
test to see the working version -- and read the commented-out line to
see which line would have raised the error."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.slider('x', min=0, max=10, default=4),
        ui.slider('w', min=1, max=10, default=2),
    ],
    hide_code=True,
)
def arithmetic_expressions(x, w):
    """## Arithmetic Expressions

An **expression** is a combination of variables, **literals** (a
specific value written in code, like `2`), and **operators** that
evaluates to a single value, like `2 * (x + 1)`.

| Operator | Meaning |
| --- | --- |
| `+` | addition |
| `-` | subtraction (also unary negation, e.g. `-x`) |
| `*` | multiplication |
| `/` | division |
| `**` | exponent (`x ** y` means x to the power of y) |

```python
y = 3 * (x + 10 / w)
```

Drag the sliders below for `x` and `w` -- watch `y` update live as
the expression is re-evaluated with the new values."""
    y = 3 * (x + 10 / w)
    return cs.md(f"**y = 3 \\* (x + 10 / w) = ** `{y}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Order of evaluation', default='c = 4\nd = 5\n\nprint(c * d + 10)     # * before +  -->  30\nprint(c + d * 10)     # * before +  -->  54\nprint((c + d) * 10)   # parens first -->  90\nprint(2 ** 3 * 3)     # ** before * -->  24\nprint(2 * -c)         # unary - before * --> -8\n'),
    ],
    hide_code=True,
)
def precedence_rules():
    """## Precedence Rules

An expression is evaluated using the same order as standard
mathematics -- in programming this is called **precedence rules**:

1. **`( )`** -- parentheses first.
2. **`**`** -- exponent next (evaluated **right-to-left**, unlike
   everything else).
3. **unary `-`** -- negation next, as in `2 * -x`.
4. **`* / %`** -- multiplication, division, modulo (equal precedence).
5. **`+ -`** -- addition, subtraction (equal precedence, evaluated
   last).

If more than one operator of *equal* precedence could be evaluated,
Python evaluates **left to right**. Many programmers add extra
parentheses even when not required, just to make the intended order
obvious to a reader."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('down_payment_text', default='2000'),
        ui.text_input('payment_per_month_text', default='350'),
        ui.text_input('num_months_text', default='36'),
    ],
    hide_code=True,
)
def python_expressions(down_payment_text, payment_per_month_text, num_months_text):
    """## A Full Expression Example: Leasing Cost

```python
down_payment = int(input("Enter down payment: "))
payment_per_month = int(input("Enter monthly payment: "))
num_months = int(input("Enter number of months: "))

total_cost = down_payment + (payment_per_month * num_months)

print(f"Total cost: ${total_cost:.2f}")
```

`payment_per_month * num_months` is computed first (higher
precedence than `+`), then added to `down_payment` -- exactly the
precedence rules from the last slide, now doing real work.

Type your own down payment, monthly payment, and number of months
into the boxes below -- the total cost updates live."""
    down_payment = int(down_payment_text)
    payment_per_month = int(payment_per_month_text)
    num_months = int(num_months_text)
    total_cost = down_payment + (payment_per_month * num_months)
    return cs.md(f"**Total cost:** `${total_cost:.2f}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Compound operators', default='age = 10\nprint(age)\n\nage += 1   # shorthand for age = age + 1\nprint(age)\n\nage *= 2   # shorthand for age = age * 2\nprint(age)\n\nage -= 5   # shorthand for age = age - 5\nprint(age)\n\nage /= 2   # shorthand for age = age / 2\nprint(age)\n'),
    ],
    hide_def=True,
    hide_code=True,
)
def compound_operators():
    """## Compound Operators

**Compound operators** are shorthand for "take a variable, combine it
with a value, and assign the result back to that same variable":

| Compound operator | Shorthand for |
| --- | --- |
| `age += 1` | `age = age + 1` |
| `age -= 1` | `age = age - 1` |
| `age *= 1` | `age = age * 1` |
| `age /= 1` | `age = age / 1` |
| `age %= 1` | `age = age % 1` |

These are just a shorter way to write the "variable on both sides"
pattern from earlier in the chapter -- `age += 1` still evaluates the
right side using `age`'s *current* value, then rebinds `age` to the
result, exactly like `age = age + 1` would."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('minutes_text', default='150'),
    ],
    hide_code=True,
)
def division_and_modulo(minutes_text):
    """## Division and Modulo

The **modulo operator** (`%`) evaluates the *remainder* of dividing
two numbers -- `23 % 10` is `3`. **Integer division** (`//`) does the
opposite: it keeps only the whole-number part and drops the
remainder -- `23 // 10` is `2`.

```python
minutes = int(input("Enter minutes: "))
hours = minutes // 60           # whole hours
minutes_remaining = minutes % 60   # leftover minutes
```

`//` and `%` work together like this constantly: `//` gets you "how
many whole groups," `%` gets you "what's left over."

Type a number of minutes into the box below -- watch it split into
hours and leftover minutes live."""
    minutes = int(minutes_text)
    hours = minutes // 60
    minutes_remaining = minutes % 60
    return cs.md(f"**{minutes} minute(s) is** `{hours}` **hour(s) and** `{minutes_remaining}` **minute(s)**")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Getting digits', default='user_val = 927\n\nones_digit = user_val % 10          # 927 % 10 is 7\nprint("ones:", ones_digit)\n\ntmp_val = user_val // 10            # 927 // 10 is 92\ntens_digit = tmp_val % 10           # 92 % 10 is 2\nprint("tens:", tens_digit)\n\ntmp_val = tmp_val // 10             # 92 // 10 is 9\nhundreds_digit = tmp_val % 10       # 9 % 10 is 9\nprint("hundreds:", hundreds_digit)\n'),
    ],
    hide_code=True,
)
def digit_extraction():
    """## Using `%` and `//` to Get Digits

Given a number, `%` and `//` can be used together to pull out
individual digits, one at a time from the right:

```python
user_val = 927
ones_digit = user_val % 10        # 927 % 10 is 7
tmp_val = user_val // 10          # 927 // 10 is 92
tens_digit = tmp_val % 10         # 92 % 10 is 2
tmp_val = tmp_val // 10           # 92 // 10 is 9
hundreds_digit = tmp_val % 10     # 9 % 10 is 9
```

The pattern: **dividing** by a power of 10 removes rightmost digits
(`321 // 10` is `32`); **`%`** by a power of 10 *keeps* rightmost
digits (`321 % 10` is `1`). Run the test and trace through each step
by hand to confirm `927` becomes `7`, `2`, `9`."""


@app.cell(
    instance='static',
    elements=[
        ui.notes('notes'),
    ],
    hide_def=True,
    hide_code=True,
)
def modules_intro():
    """## Modules

A programmer typically writes Python code in a file and runs that
whole file at once -- such a file is called a **script**.

A **module** is a file containing Python code -- variables, and
(once you've learned them) function definitions -- that's meant to be
*imported* and reused by other scripts, other modules, or the
interactive interpreter, instead of copy-pasted everywhere it's
needed.

To **import** a module means to run the code contained in that
module file, making everything it defines available for use by the
importing program, accessed with dot notation: `module_name.thing`.

```python
import math

num_sqrt = math.sqrt(49)   # math is the module, sqrt is defined inside it
```

A module that another file needs in order to run is called a
**dependency** of that file. Python keeps track of every module
that's already been imported in `sys.modules`, so importing the same
module twice doesn't re-run its code a second time."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('base_text', default='1000'),
        ui.text_input('rate_text', default='5'),
        ui.text_input('years_text', default='10'),
    ],
    hide_code=True,
)
def math_module(base_text, rate_text, years_text):
    """## The `math` Module

Python comes with a standard **`math` module** for advanced numeric
work. A **function** is a named list of statements that can be run
just by referring to its name; calling one is a **function call**,
and an item passed into it is an **argument**.

```python
import math

base = float(input("Enter initial savings: "))
rate = float(input("Enter annual interest % rate: "))
years = int(input("Enter years that pass: "))

total = base * math.pow(1 + (rate / 100), years)
print(f"Savings after {years} years is ${total:.2f}")
```

| Function | Does | Function | Does |
| --- | --- | --- | --- |
| `math.sqrt(x)` | square root | `math.pow(x, y)` | x to the power y |
| `math.ceil(x)` | round up | `math.floor(x)` | round down |
| `math.fabs(x)` | absolute value | `math.factorial(x)` | x! |
| `math.pi` | 3.14159... (constant) | `math.e` | 2.71828... (constant) |

Type your own starting balance, interest rate, and number of years
into the boxes below -- the savings total updates live."""
    base = float(base_text)
    rate = float(rate_text)
    years = int(years_text)
    total = base * math.pow(1 + (rate / 100), years)
    return cs.md(f"**Savings after {years} years is** `${total:.2f}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Random numbers', default='import random\n\nprint(random.random())            # float, 0.0 <= x < 1.0\nprint(random.randint(1, 10))      # int, 1 <= x <= 10  (inclusive both ends)\nprint(random.randrange(1, 10))    # int, 1 <= x < 10   (10 excluded)\n\nrandom.seed(15)   # same seed -> same "random" sequence every run\nprint(random.randint(1, 10))\nprint(random.randint(1, 10))\nprint(random.randint(1, 10))\n'),
    ],
    hide_def=True,
    hide_code=True,
)
def random_numbers():
    """## Random Numbers

The **`random`** module (in the Python Standard Library) generates
random values.

- **`random.random()`** returns a random float, `0.0` (inclusive) up
  to `1.0` (exclusive).
- **`random.randint(min, max)`** returns a random integer, `min` to
  `max` **inclusive** on both ends.
- **`random.randrange(min, max)`** returns a random integer, `min`
  inclusive up to `max` **exclusive** -- so `randrange(2, 10)` can
  never produce `10`, but `randint(2, 10)` can.

```python
import random
print(random.randint(1, 10))
```

A **seed** normally comes from the current time, so results differ
every run. Calling **`random.seed(n)`** with a fixed number makes
every subsequent "random" call produce the *same* sequence every
time the program runs -- useful for reproducible testing.

Run the test below more than once: the first three lines change
every run, but the three lines *after* `random.seed(15)` print the
same three numbers every time."""


@app.slide("Title", cells=[])
def slide_title():
    """"""


@app.slide("Remembering a Value", cells=["bus_riddle"])
def slide_1():
    """"""


@app.slide("Variables and Assignments", cells=["variables_and_assignments"])
def slide_2():
    """"""


@app.slide("= Is Not Equals", cells=["equals_is_not_equals"])
def slide_3():
    """"""


@app.slide("A Variable on Both Sides", cells=["variable_both_sides"])
def slide_4():
    """"""


@app.slide("Valid Assignment Statements", cells=["valid_assignment_statements"])
def slide_5():
    """"""


@app.slide("Identifiers", cells=["identifiers"])
def slide_6():
    """"""


@app.slide("Objects", cells=["objects"])
def slide_7():
    """"""


@app.slide("Name Binding", cells=["name_binding"])
def slide_8():
    """"""


@app.slide("Mutability", cells=["mutability"])
def slide_9():
    """"""


@app.slide("Floating-Point Numbers", cells=["floats"])
def slide_10():
    """"""


@app.slide("OverflowError", cells=["float_overflow"])
def slide_11():
    """"""


@app.slide("Formatting Floats", cells=["formatting_floats"])
def slide_12():
    """"""


@app.slide("Type Conversions", cells=["type_conversion"])
def slide_13():
    """"""


@app.slide("Converting to a String", cells=["str_conversion"])
def slide_14():
    """"""


@app.slide("Arithmetic Expressions", cells=["arithmetic_expressions"])
def slide_15():
    """"""


@app.slide("Precedence Rules", cells=["precedence_rules"])
def slide_16():
    """"""


@app.slide("A Full Expression Example", cells=["python_expressions"])
def slide_17():
    """"""


@app.slide("Compound Operators", cells=["compound_operators"])
def slide_18():
    """"""


@app.slide("Division and Modulo", cells=["division_and_modulo"])
def slide_19():
    """"""


@app.slide("Getting Digits", cells=["digit_extraction"])
def slide_20():
    """"""


@app.slide("Modules", cells=["modules_intro"])
def slide_21():
    """"""


@app.slide("The math Module", cells=["math_module"])
def slide_22():
    """"""


@app.slide("Random Numbers", cells=["random_numbers"])
def slide_23():
    """"""
