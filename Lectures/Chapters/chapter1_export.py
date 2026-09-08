    """# Introduction to Python

Twenty-four topics from *how programs work* through a full worked
example, rebuilt from `chapter1noates.md` as runnable CodeSlides
cells -- almost every slide here has real code you can run, edit,
and re-run, not just a description of what the code would do.

Use **Slides** to step through the lecture in order, or switch to
**Cells** to jump straight to any topic and experiment."""


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


def variables():
    """## Variables: Buckets for Information

A variable is a named "bucket" that stores a value.

```python
age = 15
name = "Ava"
```

The = is the **assignment operator**. The assignment operator is used to store a value in a variable.

> **Evaluate the right side, then store the result in the variable on the left.**"""
    age = 15
    name = "Ava"
    return age, name


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


    """## Computational Thinking

Computational thinking means breaking a problem into clear steps
that a computer can follow.

Ask:

- What information do I need?
- What steps should happen?
- What answer should be produced?


Grab cake mix
mix with water(????)
Bake 365f for 20 min

"""


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


def strings():
    """## Strings

A **string** is text inside quotes.

```python
print("Hello")
print('Python is fun')
```

Strings can contain letters, numbers, spaces, and symbols.
Strings are just text. You cannot do math with strings even if the content of a string is a number.
"""
    print("Hello")
    print("Python is fun")


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


    """#### Start Here for TR8/TR2
## Errors Are Normal

Programming requires precision. Small details matter.

Three major error types:

- [ ] **Syntax error** -- Python cannot understand the code.
- [ ] **Runtime error** -- code starts, then crashes.
- [ ] **Logic error** -- code runs but gives the wrong answer.

The next three slides show each one *actually happening*, live --
not just described."""


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
    print(f"Age: {age}")


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
    name = input("name: ")
    hours = float(input("hours_text: "))
    rate = float(input("rate_text: "))

    pay = hours * rate

    summary = (
        "Pay Summary\n"
        "-----------\n"
        f"Employee: {name}\n"
        f"Hours: {hours}\n"
        f"Rate: ${rate}\n"
        f"Pay: ${pay}"
    )
    print(summary)


    """Math cannot be performed with strings.
print("4" - "5") #does not work
but print("4" + "5") # does work

 """

    print("4" + "5")


    """# Invalid Variable Names
- 7isTheNumber
- this is a variable


# Valid
- FALSE, false
- _
- thisIsAVariable #CamelCase
- this_is_a_variable #underscore case / snake case
- GRAVITY #This convention is commonly used for constants
- sErIaLkIlLeRcAsE



"""
    print(3)
