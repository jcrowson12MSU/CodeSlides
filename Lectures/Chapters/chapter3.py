"""Strings -- lecture deck built from Lectures/ZybooksNotes/Chapter 3
(zyBooks CSE 1284, sections 3.1-3.3 and 3.5; section 3.4's source PDF was
not provided and is skipped).

Like chapter1.py and chapter2.py, this deck is deliberately straight-line
code -- no `def` anywhere inside a cell body, since functions haven't
been taught yet. Every cell's own MAIN code editor is hidden
(`hide_code=True`); any runnable/editable code a student is meant to see
or try lives in a `ui.tests(...)` box, never the main editor. The cell
body itself still computes real values, so notes and any text_input/
slider-bound demos have something live to react to.

Where zyBooks used a JS-driven visualization (the string-indexing boxes,
the PythonTutor concatenation trace, the slicing tool, the ASCII
comparison trace), this deck re-creates the same teaching point with a
live `ui.text_input` bound into the cell's own parameters, plus
`cs.md(...)` output describing what happened -- consistent with the
prior chapters' pattern of using a real reactive control as a stand-in
for a canned animation.
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
    """# Strings

Four zyBooks sections (3.1-3.3, 3.5) on how Python represents, slices,
formats, and searches text -- rebuilt as runnable CodeSlides cells.
Every code sample lives in its own **test editor** below the notes, not
the slide's main editor -- run it, change it, break it.

Use **Slides** to step through in order, or **Cells** to jump straight
to a topic."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('sample_word', default='Trish'),
    ],
    hide_code=True,
)
def string_basics(sample_word):
    """## Strings Are a Sequence of Characters

A **string** is a sequence of characters that represents textual data,
like a location or a message to the user. A **string literal** is a
string defined directly in source code by surrounding a value with
single or double quotes, like `'MARY'` or `"MARY"`.

A string is a **sequence type** -- a type that orders a collection of
objects (here, characters) into a sequence, each with its own numbered
**index** starting at `0`.

Type a word into the box below -- each character is shown lined up
under its index."""
    indices = "  ".join(str(i) for i in range(len(sample_word)))
    letters = "  ".join(sample_word)
    summary = f"index:  {indices}\nchar:   {letters}"
    return cs.md(f"```text\n{summary}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('len() examples', default='george_v = ("His Majesty George V, by the Grace of God, "\n            "of the United Kingdom of Great Britain and "\n            "Ireland and of the British Dominions beyond "\n            "the Seas, King, Defender of the Faith, Emperor of India")\ngandhi = "Mohandas Karamchand Gandhi"\njohn_f_kennedy = "JFK"\n\nprint(len(george_v), "characters is much too long of a name!")\nprint(len(gandhi), "characters is better...")\nprint(len(john_f_kennedy), "characters is short enough.")\n'),
    ],
    hide_code=True,
)
def string_length():
    """## Finding a String's Length

The **`len()`** built-in function returns the length of any sequence
object passed as an argument (a string, or another sequence type like a
list).

```python
gandhi = "Mohandas Karamchand Gandhi"
print(len(gandhi))   # 26
```

Manually counting characters in a long string literal is error-prone --
`len()` counts them exactly, every time. Run the test to compare the
lengths of three very differently sized names."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Positive and negative indexing', default='alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"\n\nprint(\n    alphabet[0],\n    alphabet[19],\n    alphabet[2],\n    alphabet[10],\n)\n\n# A negative index counts backward from the end of the string.\nprint(\n    alphabet[-1],   # last character\n    alphabet[-26],  # first character -- same as alphabet[0]\n    alphabet[-9],\n)\n'),
    ],
    hide_code=True,
)
def string_indexing():
    """## Indexing

A programmer can reference a single character at a specific index by
appending square brackets containing the desired index after a
string's name. `alphabet[0]` is the first character, `"A"`;
`alphabet[19]` is the 20th character, `"T"`.

A **negative index** counts backward from the end of the string, which
is useful when a string is very long or its length isn't known in
advance -- `alphabet[-1]` is the *last* character, and `alphabet[-26]`
is the first character of a 26-character string (the same as
`alphabet[0]`).

Run the test and match each printed character back to its index."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Strings are immutable', default='alphabet = "abcdefghijklmnopqrstuvwxyz"\nprint("Lowercase:", alphabet)\n\n# alphabet[0] = "A"   # TypeError -- strings do not support item assignment\n\n# The correct way to "change" a string is to rebind the variable\n# to an entirely new string.\nalphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"\nprint("Uppercase:", alphabet)\n'),
    ],
    hide_code=True,
)
def string_immutability():
    """## Strings Are Immutable

Once created, a string's characters can never be changed in place.
`alphabet[0] = "A"` looks like it should update a single character, but
it raises a `TypeError` -- strings do not support item assignment.

The correct way to "update" a string is to assign the variable a brand
new string value, completely replacing the old one:

```python
alphabet = "abcdefghijklmnopqrstuvwxyz"
alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"   # a new string object, not an edit
```

Uncomment the marked line in the test to see the `TypeError` for
yourself."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Building a sentence with +', default='planet = "Mars"\nnum_moons = "2"\nmoon1 = "Phobos"\nmoon2 = "Deimos"\n\nstatement = planet + " has "\nstatement = statement + num_moons + " moons."\nstatement = statement + " The first moon is " + moon1\nstatement = statement + ", and the second moon is " + moon2\n\nprint(statement)\n'),
    ],
    hide_code=True,
)
def string_concatenation():
    """## String Concatenation

A program can add new characters onto the end of a string using `+`, in
a process called **string concatenation**. Each `+` produces a brand
new string -- since strings are immutable, none of the originals are
changed.

```python
planet = "Mars"
statement = planet + " has 2 moons."
```

Run the test and watch `statement` grow, one concatenation at a time,
by building up a sentence about Mars's moons."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('slice_source', default='http://en.wikipedia.org/wiki/Turing'),
        ui.text_input('slice_start', default='7'),
        ui.text_input('slice_end', default='23'),
    ],
    hide_code=True,
)
def slicing_basics(slice_source, slice_start, slice_end):
    """## Slicing

**Slice notation** has the form `my_str[start:end]`, which creates a
*new* string containing the characters of `my_str` from index `start`
up to, but not including, index `end`.

```python
url = "http://en.wikipedia.org/wiki/Turing"
domain = url[7:23]   # "en.wikipedia.org"
```

Edit the source string, `start`, or `end` below -- the slice recomputes
live."""
    start = int(slice_start)
    end = int(slice_end)
    sliced = slice_source[start:end]
    summary = f"{slice_source!r}[{start}:{end}] -> {sliced!r}"
    return cs.md(f"```text\n{summary}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('A slice is a brand-new string', default='my_str = "The cat jumped the brown cow"\nanimal = my_str[4:7]\nprint(f"The animal is a {animal}")\n\nmy_str = "The fox jumped the brown llama"\nprint(f"The animal is still a {animal}")   # animal is untouched\n'),
    ],
    hide_code=True,
)
def slicing_creates_new_object():
    """## A Slice Creates a New Object

`my_str[4:7]` copies characters out of `my_str` into a completely
separate string object. Once `animal` holds that copy, later
reassigning `my_str` to something else has **no effect** on `animal` --
they were never the same object to begin with.

Run the test: `animal` still prints `"cat"` even after `my_str` is
reassigned to a sentence about a fox."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Omitting start/end, and negative slice indices', default='my_str = "http://en.wikipedia.org/wiki/Nasa/"\n\nprint(my_str[10:19])   # "wikipedia"          -- indices 10-18\nprint(my_str[10:-5])   # "wikipedia.org/wiki/" -- indices 10 up to (len-5)\nprint(my_str[8:])      # "n.wikipedia.org/wiki/Nasa/" -- index 8 to the end\nprint(my_str[:23])     # "http://en.wikipedia.org"    -- start to index 23\nprint(my_str[:-1])     # everything but the last character\n'),
    ],
    hide_code=True,
)
def slicing_omitted_bounds():
    """## Omitting Start or End

Either side of `[start:end]` can be left out. Leaving out `start`
means "from the beginning"; leaving out `end` means "to the very end."
An `end` can also be negative, counting backward from the end of the
string, same as a negative index.

| Syntax | Meaning |
| --- | --- |
| `my_str[8:]` | index 8 through the end |
| `my_str[:23]` | the start through index 22 |
| `my_str[:-1]` | everything but the last character |

Run the test against a URL and match each slice to its printed
result."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Stride', default='numbers = "0123456789"\n\nprint(f"All numbers: {numbers[::]}")\nprint(f"Every even number: {numbers[::2]}")\nprint(f"Every third number between 1 and 8: {numbers[1:9:3]}")\n'),
    ],
    hide_code=True,
)
def slicing_stride():
    """## Stride

Slice notation also accepts a third number, `my_str[start:end:stride]`
-- the **stride** determines how much to advance the index after each
character is read. A stride of `2` reads every other character; a
stride of `3` reads every third.

Leaving `start` and `end` empty (`numbers[::2]`) means "the whole
string, but only every 2nd character." Run the test to see all three
strides applied to the digits `0123456789`."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('usr_text', default='Introduction to Python'),
    ],
    hide_code=True,
)
def slicing_halves(usr_text):
    """## Worked Example: Splitting a String in Half

Slicing composes naturally with other expressions -- the slice bounds
don't have to be literal numbers, they can be any expression, like
`len(usr_text) // 2`.

```python
first_half = usr_text[:len(usr_text) // 2]
last_half = usr_text[len(usr_text) // 2:]
```

Edit the text box below -- the cell reruns and shows both halves,
split at the midpoint."""
    midpoint = len(usr_text) // 2
    first_half = usr_text[:midpoint]
    last_half = usr_text[midpoint:]
    summary = (
        f'"{usr_text}"\n'
        f"first half:  {first_half!r}\n"
        f"second half: {last_half!r}"
    )
    return cs.md(f"```text\n{summary}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Replacement fields', default='number = 6\namount = 32\nprint(f"{number} burritos cost ${amount}")\n'),
    ],
    hide_code=True,
)
def fstrings_basics():
    """## f-strings

A **formatted string literal** (an **f-string**) lets a programmer
build a string with embedded expressions that are evaluated as the
program runs. Writing `f"..."` (an `f` right before the opening quote)
turns on this behavior.

Each `{...}` inside the string is a **replacement field** -- a
placeholder expression whose value is substituted into the final
string.

```python
number = 6
amount = 32
print(f"{number} burritos cost ${amount}")   # "6 burritos cost $32"
```

Run the test, then try changing `number` and `amount`."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Self-documenting = specifier', default='print(f"{2**2=}")\n\ntwo_power_two = 2**2\nprint(f"{two_power_two=}")\n\nprint(f"{2**2=},{2**4=}")\n\n# Doubled braces print a literal brace instead of starting a field.\nprint(f"{{2**2}}")\nprint(f"{{{2**2=}}}")\n'),
    ],
    hide_code=True,
)
def fstrings_equals_and_braces():
    """## Debugging With `=`, and Literal Braces

Adding `=` right before the closing `}` of a replacement field prints
*both* the expression's text and its value -- handy for quick
debugging without writing a separate `print(f"expr: {expr}")`.

```python
print(f"{2**2=}")   # "2**2=4"
```

Because `{` and `}` are special inside an f-string, printing a literal
brace character requires **doubling** it: `{{` becomes `{` and `}}`
becomes `}`. Run the test to see the self-documenting `=` and the
doubled-brace escapes side by side."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('replace()', default='phrase = "Someday I will have three goats, six horses, and one cow."\n\n# Replace English number words with Spanish.\nphrase = phrase.replace("one", "uno")\nphrase = phrase.replace("two", "dos")\nphrase = phrase.replace("three", "tres")\n\nprint(phrase)\n\n# A third argument limits how many occurrences get replaced.\nrepeated = "one one one one"\nprint(repeated.replace("one", "ONE", 2))\n'),
    ],
    hide_code=True,
)
def string_methods_replace():
    """## The `replace()` Method

`my_str.replace(old, new)` returns a **copy** of `my_str` with every
occurrence of `old` swapped for `new` -- the original string is
untouched, since strings are immutable.

An optional third argument, `my_str.replace(old, new, count)`, limits
the swap to just the first `count` occurrences.

Run the test to translate three English number words to Spanish, one
`replace()` call at a time."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('find(), rfind(), and count()', default='word = "onomatopoeia"\n\nprint(word.find("o"))          # first "o", from the start\nprint(word.find("o", 1))       # first "o" starting the search at index 1\nprint(word.find("o", 1, 4))    # first "o" between index 1 and 4\nprint(word.rfind("o"))         # first "o" searching from the end\nprint(word.count("o"))         # how many "o" characters total\nprint(word.find("z"))          # not found -> -1\n'),
    ],
    hide_code=True,
)
def string_methods_find():
    """## Searching: `find()`, `rfind()`, `count()`

`my_str.find(x)` returns the index of the *first* occurrence of `x` in
the string, or `-1` if `x` never appears. `find(x, start)` begins the
search at `start`; `find(x, start, end)` also stops the search before
`end`.

`my_str.rfind(x)` works the same way but searches **in reverse**,
finding the last occurrence's index. `my_str.count(x)` returns how many
times `x` occurs.

Run the test against `"onomatopoeia"` and predict each result before
checking the output."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Hangman: find() + count() at work', default='word = "onomatopoeia"\nnum_guesses = 10\nhidden_word = "-" * len(word)\n\nguess = 1\nwhile guess <= num_guesses and "-" in hidden_word:\n    print(hidden_word)\n    user_input = input(f"Enter a character (guess #{guess}): ")\n\n    if len(user_input) == 1:\n        num_occurrences = word.count(user_input)\n        position = -1\n        for occurrence in range(num_occurrences):\n            position = word.find(user_input, position + 1)\n            hidden_word = hidden_word[:position] + user_input + hidden_word[position + 1:]\n\n    guess += 1\n\nprint(hidden_word)\n'),
    ],
    hide_code=True,
)
def string_methods_hangman():
    """## Worked Example: Hangman

This guessing game uses `"in"` to keep looping while `hidden_word`
still has hidden (`"-"`) characters, `count()` to see how many times a
guessed letter occurs in the secret word, and `find()` -- called
repeatedly, each time starting one past the last match -- to locate
*every* occurrence of that letter so all of them get revealed at once.

Run the test in the console and guess a few letters of
`"onomatopoeia"`."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('compare_left', default='Yankee Sierra'),
        ui.text_input('compare_right', default='Yankee Zulu'),
    ],
    hide_code=True,
)
def string_comparisons(compare_left, compare_right):
    """## Comparing Strings

`==` checks whether two strings are exactly identical. `<` and `>`
compare strings using each character's **ASCII value**, left to right
-- the first pair of characters that differs decides the result. `in`
checks whether one string is a substring of another, and is
case-sensitive: `"seph" in "Joseph"` is `True`, but `"jo" in "Joseph"`
is `False`.

Edit the two strings below to see how they compare."""
    equal = compare_left == compare_right
    greater = compare_left > compare_right
    contains = compare_right in compare_left
    summary = (
        f"{compare_left!r} == {compare_right!r}  ->  {equal}\n"
        f"{compare_left!r} >  {compare_right!r}  ->  {greater}\n"
        f"{compare_right!r} in {compare_left!r}  ->  {contains}"
    )
    return cs.md(f"```text\n{summary}\n```")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('is vs. ==', default='student_name = "Amy Adams"\n\n# "is" checks object identity, not value equality -- comparing a\n# string variable to a freshly-written literal with "is" is almost\n# always a bug, even when it happens to work here.\nif student_name is "Amy Adams":\n    print("Identity operator: True")\nelse:\n    print("Identity operator: False")\n\nif student_name == "Amy Adams":\n    print("Equality operator: True")\nelse:\n    print("Equality operator: False")\n'),
    ],
    hide_code=True,
)
def identity_vs_equality():
    """## `is` Is Not `==`

`==` compares **values** -- whether two strings contain the same
characters. `is` compares **identity** -- whether two variables refer
to the literal same object in memory. Two equal-looking strings are not
guaranteed to be the same object, so `is` can silently give a
different answer than `==` even when the values match.

**Always use `==` to compare string values.** Reserve `is` for
identity checks like `x is None`. Run the test and notice both
comparisons happen to agree here -- that's not a guarantee."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('isX() checks', default='samples = ["hello123", "12345", "hello", "HELLO", "   ", "Hello World"]\n\nfor s in samples:\n    print(f"{s!r:>15} isalnum={s.isalnum()!s:5} isdigit={s.isdigit()!s:5} "\n          f"islower={s.islower()!s:5} isupper={s.isupper()!s:5} isspace={s.isspace()}")\n'),
    ],
    hide_code=True,
)
def string_is_methods():
    """## Checking String Contents: the `isX()` Methods

| Method | Returns `True` when... |
| --- | --- |
| `isalnum()` | every character is a letter or digit (0-9) |
| `isdigit()` | every character is a digit (0-9) |
| `islower()` | every cased character is lowercase |
| `isupper()` | every cased character is uppercase |
| `isspace()` | every character is whitespace |

These are commonly used to validate input before converting it, e.g.
checking `user_input.isdigit()` before calling `int(user_input)`. Run
the test across several sample strings and compare the results."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('case_text', default='  Hello, World!  '),
    ],
    hide_code=True,
)
def string_case_methods(case_text):
    """## Reshaping a String: `startswith()`, `endswith()`, Case, and `strip()`

More string methods, all returning a **new** string (or a `bool`)
rather than modifying the original:

| Method | Effect |
| --- | --- |
| `startswith(x)` / `endswith(x)` | `True` if the string starts/ends with `x` |
| `capitalize()` | first character uppercase, the rest lowercase |
| `lower()` / `upper()` | every character lowercased / uppercased |
| `strip()` | leading and trailing whitespace removed |
| `title()` | first letter of each word capitalized |

Edit the text box below -- every transformation is applied live to
whatever you type."""
    summary = (
        f"original:    {case_text!r}\n"
        f"startswith('  He'): {case_text.startswith('  He')}\n"
        f"endswith('!  '):    {case_text.endswith('!  ')}\n"
        f"capitalize(): {case_text.capitalize()!r}\n"
        f"lower():      {case_text.lower()!r}\n"
        f"upper():      {case_text.upper()!r}\n"
        f"strip():      {case_text.strip()!r}\n"
        f"title():      {case_text.title()!r}"
    )
    return cs.md(f"```text\n{summary}\n```")


@app.slide("Title", cells=[])
def slide_1():
    """"""


@app.slide("Strings Are a Sequence of Characters", cells=["string_basics"])
def slide_2():
    """"""


@app.slide("Finding a String's Length", cells=["string_length"])
def slide_3():
    """"""


@app.slide("Indexing", cells=["string_indexing"])
def slide_4():
    """"""


@app.slide("Strings Are Immutable", cells=["string_immutability"])
def slide_5():
    """"""


@app.slide("String Concatenation", cells=["string_concatenation"])
def slide_6():
    """"""


@app.slide("Slicing", cells=["slicing_basics"])
def slide_7():
    """"""


@app.slide("A Slice Creates a New Object", cells=["slicing_creates_new_object"])
def slide_8():
    """"""


@app.slide("Omitting Start or End", cells=["slicing_omitted_bounds"])
def slide_9():
    """"""


@app.slide("Stride", cells=["slicing_stride"])
def slide_10():
    """"""


@app.slide("Worked Example: Splitting a String in Half", cells=["slicing_halves"])
def slide_11():
    """"""


@app.slide("f-strings", cells=["fstrings_basics"])
def slide_12():
    """"""


@app.slide("Debugging With = and Literal Braces", cells=["fstrings_equals_and_braces"])
def slide_13():
    """"""


@app.slide("The replace() Method", cells=["string_methods_replace"])
def slide_14():
    """"""


@app.slide("Searching: find(), rfind(), count()", cells=["string_methods_find"])
def slide_15():
    """"""


@app.slide("Worked Example: Hangman", cells=["string_methods_hangman"])
def slide_16():
    """"""


@app.slide("Comparing Strings", cells=["string_comparisons"])
def slide_17():
    """"""


@app.slide("is Is Not ==", cells=["identity_vs_equality"])
def slide_18():
    """"""


@app.slide("Checking String Contents: the isX() Methods", cells=["string_is_methods"])
def slide_19():
    """"""


@app.slide("Reshaping a String", cells=["string_case_methods"])
def slide_20():
    """"""
