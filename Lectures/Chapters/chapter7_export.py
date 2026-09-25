    """# While Loops

Four zyBooks sections (7.1-7.4) on `while` loops -- the general loop
concept, Python's `while` syntax, sentinel values, infinite loops, and
using a loop variable to count -- rebuilt as runnable CodeSlides
cells.

Every code sample lives in its own **test editor** below the notes,
not the slide's main editor -- run it, change it, break it.

Use **Slides** to step through in order, or **Cells** to jump straight
to a topic."""


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


def while_over_list():
    """## Finding the Largest Item

A `while` loop can walk through a list one element at a time by
tracking the current position with an **index variable**, stopping
once the index reaches the list's length.

## Code discussion:
`largest` is initialized to the *first* element (not some placeholder like `-1`) since these temperature readings could legitimately be negative. 

Each iteration compares the current element, `readings[index]`, against the best value seen so far, replacing `largest` whenever a bigger reading turns up. `index` is incremented on every iteration regardless forgetting that line would leave `index` stuck at `0` and turn this into an infinite loop."""


def sentinel_values():
    """## Sentinel Values

A **sentinel value** is a special value that signals a loop to stop it isn't real data, it's a stop sign. A loop controlled by a sentinel keeps running until that specific value shows up, so the *user* (or the data itself) decides when the loop ends, not a fixed count baked into the code.

Here, a shopper builds a grocery list by typing one item per prompt, and signals they're done by typing `"done"`:

If a shopper types `milk`, `eggs`, `done`, the loop runs for two
iterations (adding `"milk"` and `"eggs"`) -- the third input, `"done"`, never gets appended; it just makes the condition `False` and ends the loop. `"done"` here plays the exact same role `-1` played for the\\ `readings`/average examples back in 7.1, or `"star"` played for the
password example in 7.2 any value works as a sentinel as long as it can't be confused with real data."""


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
