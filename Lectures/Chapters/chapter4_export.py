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


    """## Branches: The General Idea

A **branch** is a sequence of statements only executed under a certain
condition.

An **if branch** is a branch taken only *if* an expression is `True`.

**Example: a restaurant host seating patrons**

- Party of 1 -> seated at the counter
- Party of 2 -> seated at a small table
- Party of 3 or more -> seated at a large table

The host mentally runs an algorithm: *if* party of 1, seat at the
counter; *else if* party of 2, seat at a small table; *else*, seat at
a large table. That "if / else if / else" structure is exactly what
the rest of this chapter writes in Python."""


def if_branch_trace(user_age_text):
    """## An `if` Branch: Hotel Rate Example

A decision leads to two possible paths. If the expression is `True`,
the branch's statements execute; if `False`, they're skipped and
execution continues after the branch."""
    user_age = int(user_age_text)
    hotel_rate = 155
    if user_age > 65:
        hotel_rate = hotel_rate - 20
    return cs.md(f"**Your rate:** `{hotel_rate}`")


def if_else_absolute_value(val_text):
    """## `if`-`else`: Computing Absolute Value

An **`if`-`else` branch** has two branches: the first executes *if* an
expression is `True`; otherwise, the *else* branch executes."""
    val = int(val_text)
    if val < 0:
        val = -val
    return cs.md(f"**Output:** `{val}`")


def equality_operator(num_years_text):
    """## The Equality Operator: `==`

An **`if` statement** executes a group of statements *if* an
expression is `True`.

The **equality operator** (`==`) evaluates to `True` if the left and
right sides are equal."""
    num_years = int(num_years_text)
    hotel_rate = 150
    message = ""
    if num_years == 50:
        message = "Congratulations on 50 years of marriage!"
        hotel_rate = hotel_rate / 2
    rate_line = f"Your hotel rate: ${hotel_rate:.2f}"
    return cs.md(f"**Output:**\n\n```text\n{message + chr(10) if message else ''}{rate_line}\n```")


def equality_inequality_table():
    """## Equality and Inequality Operators

A **Boolean** is a type that has just two values: `True` or `False`.

| Operator | Description | Example (x = 3) |
| --- | --- | --- |
| == | a == b means a is equal to b. | x == 3 is True; x == 4 is False |
| != | a != b means a is not equal to b. | x != 3 is False; x != 4 is True |

The **inequality operator** (`!=`) evaluates to `True` if the left and
right sides are *different*."""


def if_else_even_odd(user_num_text):
    """## `if`-`else`: Even or Odd

An **`if`-`else` statement** executes one group of statements when an
expression is `True`, and another group when it's `False`."""
    user_num = int(user_num_text)
    div_remainder = user_num % 2
    if div_remainder == 0:
        result = f"{user_num} is even."
    else:
        result = f"{user_num} is odd."
    return cs.md(f"**Output:** `{result}`")


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
condition is `True`, Python runs that branch and skips the rest."""
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


def relational_operators_table(relational_x_text):
    """## Relational Operators

A **relational operator** checks how one operand's value relates to
another."""
    x = int(relational_x_text)
    return cs.md(
        f"`x = {x}`\n\n"
        f"| Expression | Result |\n| --- | --- |\n"
        f"| `x < 4` | `{x < 4}` |\n"
        f"| `x > 4` | `{x > 4}` |\n"
        f"| `x <= 4` | `{x <= 4}` |\n"
        f"| `x >= 4` | `{x >= 4}` |"
    )


def ranges_insurance(insurance_age_text):
    """## Detecting Ranges: Insurance Prices

Because each `elif` only runs when every earlier condition was
`False`, a chain of `<` comparisons can carve age into ranges without
ever writing the range's lower bound explicitly."""
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


def logical_operators():
    """TR 8am start with 3 prop truth table
## Logical Operators: `and`, `or`, `not`

A **logical operator** treats its operands as `True`/`False` and
evaluates to `True` or `False`. Python's logical operators are the
lowercase keywords **`and`**, **`or`**, and **`not`**.

| a | b | a and b | a or b |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 |
| 1 | 0 | 0 | 1 |
| 1 | 1 | 1 | 1 |

| a | not a |
| --- | --- |
| 0 | 1 |
| 1 | 0 |
"""


def and_for_ranges(channel_text):
    """## Using `and` to Detect a Range

A number line makes the pattern clear: the range `10 < x < 15` (values
`11`, `12`, `13`, `14`) is the *overlap* of two half-open ranges --
`x` above `10` **and** `x` below `15`:

```python
10 < x and x < 15
```

Applied to a real range check -- cable TV channels:
"""
    user_channel = int(channel_text)
    if 2 <= user_channel <= 499:
        channel_type = "standard"
    elif 1002 <= user_channel <= 1499:
        channel_type = "HD"
    else:
        channel_type = "not a channel"
    return cs.md(f"**Output:** `{channel_type}`")


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
