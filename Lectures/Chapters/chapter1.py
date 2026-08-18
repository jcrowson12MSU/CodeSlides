"""Introduction to Python -- lecture deck built from
Lectures/Chapters/chapter1noates.md (24 source slides), expanded into
runnable CodeSlides cells wherever the source had a code example, plus
richer live demonstrations for the two purely-conceptual slides (IDE,
error taxonomy) that had no code of their own.

Deliberately straight-line code throughout -- no `def` anywhere inside
a cell body, and no `ui.tests` snippet calls a function either. This
is the first chapter; functions haven't been introduced to the
student yet, so nothing here should read as if they had been. Where
an earlier draft used a small helper function purely to make a
`ui.tests` variant runnable (e.g. "run this again with a different
name"), the test variant instead just re-states the same few lines of
straight-line code with different literal values, exactly like a
student re-typing the lines themselves would.

Slides that showed `input()` keep `input()` in the cell's own source
sample for realism (that's genuinely how a student would type it),
but the runnable version underneath uses `ui.text_input(...)` boxes as
a real stand-in instead -- this UI has no interactive stdin, so a cell
can't actually call `input()` itself (there's nothing to shim it with;
calling it here would just fail). A `ui.text_input` element's value
binds into the cell's own same-named parameter and reruns the cell
automatically on every edit (ARCHITECTURE.md section 3a), which is
close enough to typing at an `input()` prompt to teach the same
concept with a real, live textbox rather than a canned re-run of a
`ui.tests` snippet -- `runtime_errors` in particular relies on this:
typing `twelve` into its box raises a genuine `ValueError` live, not a
pre-written test case demonstrating one.

Every one of these `text_input`-driven cells returns `cs.md(...)`
instead of calling `print()` -- this app only ever surfaces a cell's
own stdout inside a `ui.tests` element's own output box (see
`TestsElementWidget.tsx`), never for a plain cell body just running on
its own, so a `text_input`-driven cell that only `print()`ed its
result would rerun silently on every keystroke with nothing visible
changing. `cs.md()` renders a cell's *returned* value as formatted
output right where a viewer element would normally show one
(ARCHITECTURE.md section 6), which does update live. `ui.tests` is
still used elsewhere in this deck (`variables`, `print_function`,
etc.) for topics that aren't about `input()` at all, where a
re-runnable code sample -- and its own dedicated output box -- is the
more natural fit.

The one slide whose *broken* code is a real, permanent Python
`SyntaxError` (Slide 18) can't be a cell's own body -- the whole deck
file is `ast.parse`d at load time, so unbalanced-paren source would
fail to load at all. That one broken snippet lives in the notes'
markdown code fence instead (mirroring the source .md's own before/
after code-block pattern); the fixed version is the real runnable
cell. Runtime and logic errors (Slides 19-20), by contrast, are
syntactically valid Python that only fails when *run* -- those are
genuinely live: click Run and watch a real traceback/wrong-answer
appear, then compare against the corrected version alongside it.
"""

from codeslides import App, cs, ui

app = App()


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def intro():
    """# Introduction to Python

Twenty-four topics from *how programs work* through a full worked
example, rebuilt from `chapter1noates.md` as runnable CodeSlides
cells -- almost every slide here has real code you can run, edit,
and re-run, not just a description of what the code would do.

Use **Slides** to step through the lecture in order, or switch to
**Cells** to jump straight to any topic and experiment."""


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.text_input("name", default="Ada"),
    ],
)
def how_programs_work(name):
    """## How Programs Work: Input → Process → Output

A program is a list of instructions that run one at a time.

- **Input:** get information
- **Process:** do something with that information
- **Output:** show or store the result

Type your own name in the box below -- the cell reruns automatically
and greets whoever you typed."""
    message = "Hello, " + name
    return cs.md(f"**Output:** `{message}`")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default="age = 15\nname = 'Ava'\nprint(age, name)"),
    ],
)
def variables():
    """## Variables: Buckets for Information

A variable is a named "bucket" that stores a value.

```python
age = 15
name = "Ava"
```

Read assignment right-to-left:

> **Evaluate the right side, then store the result in the variable
> on the left.**"""
    age = 15
    name = "Ava"
    return age, name


@app.cell(instance="editable", elements=[ui.notes("notes")])
def assignment_vs_equality():
    """## `=` Is Not Math Equality

In math:

```text
x + 2 = 7
```

means both sides have the same value.

In Python:

```python
x = 7
```

means store `7` in `x`.

Simple assignment pattern:

```python
variable_name = value
```"""
    x = 7
    return x


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.text_input("first_text", default="4"),
        ui.text_input("second_text", default="9"),
    ],
)
def simple_program(first_text, second_text):
    """## A Simple Python Program

```python
first = int(input("First number: "))
second = int(input("Second number: "))

total = first + second

print("Total:", total)
```

- **Input:** two numbers
- **Process:** add them
- **Output:** print the total

The two boxes below stand in for `input()` -- type numbers into them
and the cell reruns automatically, converting each with `int(...)`
exactly the way `int(input(...))` would."""
    first = int(first_text)
    second = int(second_text)

    total = first + second

    return cs.md(f"**Total:** `{total}`")


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def computational_thinking():
    """## Computational Thinking

Computational thinking means breaking a problem into clear steps
that a computer can follow.

Ask:

- What information do I need?
- What steps should happen?
- What answer should be produced?"""


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.text_input("first_n_text", default="4"),
        ui.text_input("second_n_text", default="9"),
    ],
)
def algorithm(first_n_text, second_n_text):
    """## Algorithm

An **algorithm** is a step-by-step plan for solving a problem.

Example algorithm:

```text
1. Ask for two numbers
2. Convert them to integers
3. Add them
4. Print the answer
```

Then translate the algorithm into Python, one step at a time -- the
code below *is* that translation, the same shape as `simple_program`
from a few slides back. Type numbers into the two boxes below to try
it."""
    first_n = int(first_n_text)
    second_n = int(second_n_text)
    total = first_n + second_n
    return cs.md(f"**Answer:** `{total}`")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default='print("Hello")\nprint("Welcome to Python")'),
    ],
)
def print_function():
    """## `print()`

`print()` sends output to the screen.

```python
print("Hello")
print("Welcome to Python")
```

Each `print()` normally starts a new line."""
    print("Hello")
    print("Welcome to Python")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default='print("Room 203")\nprint("Email sent!")'),
    ],
)
def strings():
    """## Strings

A **string** is text inside quotes.

```python
print("Hello")
print('Python is fun')
```

Strings can contain letters, numbers, spaces, and symbols."""
    print("Hello")
    print("Python is fun")


@app.cell(instance="editable", elements=[ui.notes("notes")])
def int_and_float():
    """## `int` and `float`

Python has different types of numbers.

```python
students = 24      # int
price = 3.99       # float
```

- `int`: whole number
- `float`: number with a decimal"""
    students = 24  # int
    price = 3.99  # float
    return students, price


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default='print("Name\\tGrade")'),
    ],
)
def escape_sequences():
    """## Newline and Tab

Escape sequences control formatting.

```python
print("Line 1\\nLine 2")
print("Name\\tGrade")
```

- `\\n` moves to a new line
- `\\t` inserts a tab"""
    print("Line 1\nLine 2")
    print("Name\tGrade")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default='print("\\\\")'),
    ],
)
def quotes_and_backslashes():
    """## Printing Quotes and Backslashes

```python
print('"Hello"')
print("\\"Hello\\"")
print("\\\\")
```

- Use single quotes to easily print double quotes.
- Use `\\"` to print a double quote inside double quotes.
- Use `\\\\` to print one backslash."""
    print('"Hello"')
    print("\"Hello\"")
    print("\\")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default='print("Sam", "is", 16, "years old.")'),
    ],
)
def printing_multiple_things():
    """## Printing Multiple Things

Separate items with commas.

```python
name = "Ava"
age = 15

print(name, "is", age, "years old.")
```

Python automatically adds spaces between comma-separated items."""
    name = "Ava"
    age = 15
    print(name, "is", age, "years old.")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default='print("Hello", end=" ")\nprint("there")'),
    ],
)
def sep_and_end():
    """## `sep` and `end`

Control spacing with `sep`.

```python
print("2026", "08", "18", sep="-")
```

Control what happens at the end with `end`.

```python
print("Hello", end=" ")
print("there")
```"""
    print("2026", "08", "18", sep="-")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it", default='print(1 + 1)\nprint("1" + "1")'),
    ],
)
def data_types_matter():
    """## Data Types Matter: `1` vs `"1"`

```python
print(1 + 1)
print("1" + "1")
```

Output:

```text
2
11
```

`1` is a number. `"1"` is text."""
    print(1 + 1)
    print("1" + "1")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.text_input("name", default="Sam"),
    ],
)
def input_and_prompts(name):
    """## Input and Prompts

`input()` reads what the user types.

```python
name = input("What is your name? ")
print("Hello,", name)
```

Important: `input()` always gives back a string.

```python
age = int(input("Age: "))
```

Type your own name into the box below -- it stands in for `input()`,
and the cell reruns automatically as you type."""
    return cs.md(f"**Output:** `Hello, {name}`")


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def ide():
    """## IDE

An IDE (**I**ntegrated **D**evelopment **E**nvironment) helps you
write, run, test, and debug programs -- CodeSlides itself is one:
this very code editor, the **Run** button on each cell, the output
panel below it, and this live notes editor are the same four pieces
every IDE has.

| IDE tool | What it's for | Here, it's... |
| -------- | -------------- | ----------------- |
| Code editor | Write the source | the panel on the right |
| Run button | Execute the code | `Shift+Enter` |
| Console | See results and errors | the output panel |
| Highlighting | Spot typos at a glance | automatic, as you type |
| Debugger | Find what went wrong | the error slides next |"""


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def errors_are_normal():
    """## Errors Are Normal

Programming requires precision. Small details matter.

Three major error types:

- [x] **Syntax error** -- Python cannot understand the code.
- [ ] **Runtime error** -- code starts, then crashes.
- [ ] **Logic error** -- code runs but gives the wrong answer.

The next three slides show each one *actually happening*, live --
not just described."""


@app.cell(instance="editable", elements=[ui.notes("notes")])
def syntax_errors():
    """## Syntax Errors

A syntax error breaks Python's grammar rules -- Python won't even
start running the program.

```python
print("Hello"
```

Problem: missing closing parenthesis. A broken snippet like that
can't be this cell's own runnable body (CodeSlides checks that the
*whole file* is valid Python before it will even load), so it's
shown here as a code sample instead. The fix -- and this cell's real,
runnable code -- puts the missing `)` back:

```python
print("Hello")
```"""
    print("Hello")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.text_input("age_text", default="15"),
    ],
)
def runtime_errors(age_text):
    """## Runtime Errors

A runtime error happens *while the program is running* -- Python
understood the code fine, but something goes wrong once it executes.

```python
age = int(input("Age: "))
```

If the user types `twelve`, the program crashes because `"twelve"`
cannot become an integer.

Type into the box below -- `15` works fine, but try typing `twelve`
instead and watch a real `ValueError` appear as soon as you do."""
    age = int(age_text)
    return cs.md(f"**Age:** `{age}`")


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests(
            "Buggy version (adds instead of multiplies)",
            default="length = 10\nwidth = 5\narea = length + width\nprint(area)",
        ),
        ui.tests(
            "Fixed version",
            default="length = 10\nwidth = 5\narea = length * width\nprint(area)",
        ),
    ],
)
def logic_errors():
    """## Logic Errors

A logic error means the program *runs*, but the answer is wrong --
no crash, no red error, just a bad result that's easy to miss.

```python
length = 10
width = 5

area = length + width
print(area)
```

The program should multiply, not add:

```python
area = length * width
```

Run both tests: the buggy version prints `15` (10 + 5, silently
wrong); the fixed version prints `50` (10 × 5, correct) -- same
inputs, same lack of any error, very different answers."""
    length = 10
    width = 5

    area = length + width  # bug: should multiply
    print(area)


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it, matching output", default='print("Hello")\nprint("World")'),
        ui.tests("Run it, end=\" \" instead of a newline", default='print("Hello", end=" ")\nprint("World")'),
    ],
)
def whitespace_matters():
    """## Whitespace Matters

Whitespace includes spaces, tabs, and newlines.

```python
print("Hello")
print("World")
```

is different from:

```python
print("Hello", end=" ")
print("World")
```

Output formatting must often match exactly -- run both tests and
compare: one puts `Hello` and `World` on separate lines, the other
joins them on one line with a single space."""


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Run it and watch the TypeError", default='age = "15"  # forgot int(...)\nnext_age = age + 1'),
    ],
)
def common_beginner_mistakes():
    """## Common Beginner Mistakes

```python
print("Hello)
```

Missing quote.

```python
print("Age:" age)
```

Missing comma.

```python
age = input("Age: ")
next_age = age + 1
```

Forgot to convert input to `int` -- this one is a **runtime** error
(`str` + `int` raises `TypeError`), not a syntax error, since the
code itself is grammatically valid Python. Run the test below to see
that error happen for real."""


@app.cell(
    instance="editable",
    elements=[
        ui.notes("notes"),
        ui.tests("Assignment", default="score = 100\nprint(score)"),
        ui.tests("Comparison", default="score = 100\nprint(score == 100)"),
    ],
)
def assignment_vs_comparison():
    """## `=` vs `==`

Use `=` to store a value.

```python
score = 100
```

Use `==` to ask whether two values are equal.

```python
score == 100
```

Do not confuse assignment with comparison -- run the two tests below
to see the difference: one *sets* `score`, the other *asks a
question* about it and prints `True`/`False`."""
    score = 100
    return score


@app.cell(
    instance="editable",
    hide_def=True,
    is_main=True,
    elements=[
        ui.notes("notes"),
        ui.text_input("name", default="Ava"),
        ui.text_input("hours_text", default="32"),
        ui.text_input("rate_text", default="18.5"),
    ],
)
def pay_calculator(name, hours_text, rate_text):
    """# Medium Example: Pay Calculator

```python
name = input("Employee name: ")
hours = float(input("Hours worked: "))
rate = float(input("Hourly rate: "))

pay = hours * rate

print()
print("Pay Summary")
print("-----------")
print("Employee:", name)
print("Hours:", hours)
print("Rate: $", rate, sep="")
print("Pay: $", pay, sep="")
```

This program uses:

- input
- variables
- strings
- floats
- processing
- formatted output

Type your own name, hours, and rate into the boxes below -- the
summary updates automatically."""
    hours = float(hours_text)
    rate = float(rate_text)

    pay = hours * rate

    summary = (
        "Pay Summary\n"
        "-----------\n"
        f"Employee: {name}\n"
        f"Hours: {hours}\n"
        f"Rate: ${rate}\n"
        f"Pay: ${pay}"
    )
    return cs.md(f"```text\n{summary}\n```")


@app.slide("Title", cells=[])
def slide_title():
    """"""


@app.slide("Input → Process → Output", cells=["how_programs_work"])
def slide_1():
    """"""


@app.slide("Variables", cells=["variables"])
def slide_2():
    """"""


@app.slide("= Is Not Math Equality", cells=["assignment_vs_equality"])
def slide_3():
    """"""


@app.slide("A Simple Program", cells=["simple_program"])
def slide_4():
    """"""


@app.slide("Computational Thinking", cells=["computational_thinking"])
def slide_5():
    """"""


@app.slide("Algorithm", cells=["algorithm"])
def slide_6():
    """"""


@app.slide("print()", cells=["print_function"])
def slide_7():
    """"""


@app.slide("Strings", cells=["strings"])
def slide_8():
    """"""


@app.slide("int and float", cells=["int_and_float"])
def slide_9():
    """"""


@app.slide("Newline and Tab", cells=["escape_sequences"])
def slide_10():
    """"""


@app.slide("Quotes and Backslashes", cells=["quotes_and_backslashes"])
def slide_11():
    """"""


@app.slide("Printing Multiple Things", cells=["printing_multiple_things"])
def slide_12():
    """"""


@app.slide("sep and end", cells=["sep_and_end"])
def slide_13():
    """"""


@app.slide('1 vs "1"', cells=["data_types_matter"])
def slide_14():
    """"""


@app.slide("Input and Prompts", cells=["input_and_prompts"])
def slide_15():
    """"""


@app.slide("IDE", cells=["ide"])
def slide_16():
    """"""


@app.slide("Errors Are Normal", cells=["errors_are_normal"])
def slide_17():
    """"""


@app.slide("Syntax Errors", cells=["syntax_errors"])
def slide_18():
    """"""


@app.slide("Runtime Errors", cells=["runtime_errors"])
def slide_19():
    """"""


@app.slide("Logic Errors", cells=["logic_errors"])
def slide_20():
    """"""


@app.slide("Whitespace Matters", cells=["whitespace_matters"])
def slide_21():
    """"""


@app.slide("Common Beginner Mistakes", cells=["common_beginner_mistakes"])
def slide_22():
    """"""


@app.slide("= vs ==", cells=["assignment_vs_comparison"])
def slide_23():
    """"""


@app.slide("Pay Calculator", cells=["pay_calculator"])
def slide_24():
    """"""
