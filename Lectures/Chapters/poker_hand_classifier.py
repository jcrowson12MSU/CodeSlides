"""Poker Hand Classifier -- a capstone deck built entirely from material in
Lectures/ZybooksNotes: Chapter 3 (3.1 string basics, 3.2 slicing, 3.3
f-strings, 3.5 string methods) and Chapter 4 (4.1-4.7, 4.9-4.11: if/elif/
else, comparison and logical operators, ranges, precedence, indentation,
conditional expressions).

Deliberately no `def`, no loops, no lists/dicts -- none of those appear in
either chapter's material, so the whole classifier is straight-line code
against five separately-named card variables, exactly like chapter3.py/
chapter4.py's own "no def anywhere inside a cell body" convention. A card
is a short string like "AS" or "10H" (rank + suit, one string -- 3.1's
"string is a sequence of characters"), so every rank/suit is pulled out
with 3.2 slicing (`card[:-1]`, `card[-1]`) rather than a function call.
Hand detection is a chain of `==`/`in`/`and`/`or` comparisons (Chapter 4)
across the five already-named cards -- no iteration.

Every cell's own MAIN code editor is hidden (`hide_code=True`); the
runnable/editable code a student sees lives in a `ui.tests(...)` box
instead, mirroring the prior chapters' pattern. A `ui.text_input`-bound
hand (five space-separated cards) drives the live classifier on its own
slide so a student can type a new hand and watch the classification
change without touching any code.
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
    """# Poker Hand Classifier

A capstone project built from just two chapters: **Strings** (3.1-3.3,
3.5) and **Branches** (4.1-4.7, 4.9-4.11). No functions, no loops, no
lists -- every card is its own named string variable, and the whole
classifier is one long chain of `if`/`elif`/`and`/`or`.

**The idea:** a playing card is a short string like `"AS"` (Ace of
Spades) or `"10H"` (Ten of Hearts) -- rank characters followed by one
suit character. Slice off the rank and the suit, then compare five
cards' worth of ranks and suits against each other with the same
comparison and logical operators from Chapter 4.

Use **Slides** to build the classifier up piece by piece, or **Cells**
to jump straight to a topic."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('A hand as five strings', default='card1 = "AS"\ncard2 = "10H"\ncard3 = "10D"\ncard4 = "4C"\ncard5 = "10S"\n\nprint(card1)\nprint(card2)\nprint(len(card2))\nprint("Number of cards:", 5)'),
    ],
    hide_def=True,
    hide_code=True,
)
def cards_as_strings():
    """## A Card Is Just a String

A **string** is a sequence of characters (3.1) -- and a playing card's
short name is a perfectly good string: rank characters, then exactly
one suit character.

| Card | String |
| --- | --- |
| Ace of Spades | `"AS"` |
| Ten of Hearts | `"10H"` |
| Four of Clubs | `"4C"` |

Ranks are `2`-`9`, `10`, `J`, `Q`, `K`, `A`. Suits are `S` (Spades),
`H` (Hearts), `D` (Diamonds), `C` (Clubs) -- always the **last**
character, which is why `10H` is 3 characters but still just one card:
`len("10H")` is `3`, not `2`.

A 5-card hand is five separate string variables -- `card1` through
`card5` -- no list needed yet."""
    card1 = "AS"
    card2 = "10H"
    card3 = "10D"
    card4 = "4C"
    card5 = "10S"
    return cs.md(
        f"**Hand:** `{card1}` `{card2}` `{card3}` `{card4}` `{card5}`\n\n"
        f"`len({card2!r})` is `{len(card2)}` -- 3 characters, still one card."
    )


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('slice_card', default='10H'),
        ui.tests('Slicing off rank and suit', default='card = "10H"\nrank = card[:-1]\nsuit = card[-1]\nprint("rank:", rank)\nprint("suit:", suit)\n\n# A one-character rank works the same way\ncard2 = "AS"\nprint(card2[:-1], card2[-1])'),
    ],
    hide_code=True,
    layout={'column_fraction': 0.45, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'Slicing off rank and suit': 'top-right', '__inputs__': 'bottom-left'}, 'extra_code_fraction': 0.5},
)
def slicing_rank_suit(slice_card):
    """## Slicing Off the Rank and the Suit

**Slice notation** (3.2) has the form `my_str[start:end]`, returning a
new string with the characters from `start` up to (not including)
`end`. A **negative index** counts from the end of the string.

The suit is always the *last* character, no matter how long the rank
is -- so `card[-1]` is the suit and `card[:-1]` ("everything except
the last character," straight from Table 3.2.1) is the rank:

```python
card = "10H"
rank = card[:-1]   # "10" -- everything but the last character
suit = card[-1]    # "H"  -- just the last character
```

This works identically whether the rank is one character (`"AS"` ->
`"A"`, `"S"`) or two (`"10H"` -> `"10"`, `"H"`) -- no need to check
the length first.

Type a card below (try `AS`, `10H`, `KD`)."""
    rank = slice_card[:-1]
    suit = slice_card[-1]
    return cs.md(f"`{slice_card}` &rarr; rank `{rank}`, suit `{suit}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('f-string hand summary', default='card1 = "AS"\ncard2 = "10H"\ncard3 = "10D"\ncard4 = "4C"\ncard5 = "10S"\n\nprint(f"Hand: {card1}, {card2}, {card3}, {card4}, {card5}")\nprint(f"Card 1 rank={card1[:-1]}, suit={card1[-1]}")'),
    ],
    hide_code=True,
)
def fstring_hand_summary():
    """## Displaying the Hand With f-strings

A **formatted string literal** (f-string, 3.3) embeds a placeholder
**replacement field** -- `{expression}` -- directly inside a string
literal, evaluated when the program runs.

```python
card1 = "AS"
print(f"Card 1 rank={card1[:-1]}, suit={card1[-1]}")
```

Every classifier cell from here on prints its result the same way:
build up a plain-English f-string describing what was found, instead
of several separate `print()` calls."""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('count() and in', default='card1 = "AS"\ncard2 = "10H"\ncard3 = "10D"\ncard4 = "4C"\ncard5 = "10S"\n\nsuits = card1[-1] + card2[-1] + card3[-1] + card4[-1] + card5[-1]\nprint("suits:", suits)\nprint("How many spades?", suits.count("S"))\nprint("Any hearts at all?", "H" in suits)'),
    ],
    hide_code=True,
)
def string_methods_count_in():
    """## Counting Matches With `count()` and `in`

Two string methods and the `in` operator (3.5) do most of the actual
"how many of X are in this hand" work:

- **`count(x)`** -- returns the number of times `x` occurs in the
  string.
- **`x in string`** -- `True` if `x` occurs anywhere in `string`.

Concatenating (3.1) the five single-character suits into one string
turns "how many of card1..card5 are spades" into a single `count()`
call instead of five separate comparisons:

```python
suits = card1[-1] + card2[-1] + card3[-1] + card4[-1] + card5[-1]
suits.count("S")     # how many spades
"H" in suits          # is at least one card a heart
```"""


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Flush check', default='card1 = "AS"\ncard2 = "9S"\ncard3 = "2S"\ncard4 = "KS"\ncard5 = "7S"\n\nsuit1 = card1[-1]\nsuit2 = card2[-1]\nsuit3 = card3[-1]\nsuit4 = card4[-1]\nsuit5 = card5[-1]\n\nis_flush = (suit1 == suit2) and (suit1 == suit3) and (suit1 == suit4) and (suit1 == suit5)\nprint("Flush?", is_flush)'),
    ],
    hide_code=True,
)
def flush_check():
    """## Detecting a Flush: All Five Suits Equal

A **Flush** is five cards of the *same suit*. The **equality
operator** `==` (4.4) checks two values match; chaining four of them
with **`and`** (4.9's precedence table: `and` binds every comparison
together) is `True` only if *all five* suits equal the first one --
exactly like `x == 5 or y == 10 and z != 10` from the precedence
section, just longer:

```python
is_flush = (suit1 == suit2) and (suit1 == suit3) \\
    and (suit1 == suit4) and (suit1 == suit5)
```

Only one comparison can ever be `False` for the whole chain to fail
-- **multiple independent conditions joined by `and`** (4.9), not a
loop."""
    card1 = "AS"
    card2 = "9S"
    card3 = "2S"
    card4 = "KS"
    card5 = "7S"
    suit1, suit2, suit3, suit4, suit5 = card1[-1], card2[-1], card3[-1], card4[-1], card5[-1]
    is_flush = (suit1 == suit2) and (suit1 == suit3) and (suit1 == suit4) and (suit1 == suit5)
    return cs.md(f"**Suits:** `{suit1} {suit2} {suit3} {suit4} {suit5}`  \n**Flush?** `{is_flush}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Pair check', default='card1 = "AS"\ncard2 = "10H"\ncard3 = "10D"\ncard4 = "4C"\ncard5 = "9S"\n\nrank1 = card1[:-1]\nrank2 = card2[:-1]\nrank3 = card3[:-1]\nrank4 = card4[:-1]\nrank5 = card5[:-1]\n\nranks = rank1 + "," + rank2 + "," + rank3 + "," + rank4 + "," + rank5\nprint(ranks)\n\nhas_pair = (\n    rank1 == rank2 or rank1 == rank3 or rank1 == rank4 or rank1 == rank5 or\n    rank2 == rank3 or rank2 == rank4 or rank2 == rank5 or\n    rank3 == rank4 or rank3 == rank5 or\n    rank4 == rank5\n)\nprint("Has a pair?", has_pair)'),
    ],
    hide_code=True,
)
def pair_check():
    """## Detecting a Pair: Any Two Ranks Equal

A **Pair** is two cards sharing a rank. With only five variables (no
loop, per this chapter's material) that means checking *every*
possible pair of the five ranks -- 10 comparisons in all -- joined
with **`or`** (4.9): `True` as soon as *any single one* matches.

```python
has_pair = (
    rank1 == rank2 or rank1 == rank3 or rank1 == rank4 or rank1 == rank5 or
    rank2 == rank3 or rank2 == rank4 or rank2 == rank5 or
    rank3 == rank4 or rank3 == rank5 or
    rank4 == rank5
)
```

Contrast with the Flush check: a Flush needs **every** comparison to
hold (`and`), a Pair needs **at least one** (`or`) -- the same
and-vs-or distinction 4.9's Boolean-variable table draws out."""
    card1, card2, card3, card4, card5 = "AS", "10H", "10D", "4C", "9S"
    rank1, rank2, rank3, rank4, rank5 = card1[:-1], card2[:-1], card3[:-1], card4[:-1], card5[:-1]
    has_pair = (
        rank1 == rank2 or rank1 == rank3 or rank1 == rank4 or rank1 == rank5 or
        rank2 == rank3 or rank2 == rank4 or rank2 == rank5 or
        rank3 == rank4 or rank3 == rank5
        or rank4 == rank5
    )
    return cs.md(f"**Ranks:** `{rank1}, {rank2}, {rank3}, {rank4}, {rank5}`  \n**Has a pair?** `{has_pair}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.tests('Three/four of a kind via count()', default='card1 = "10S"\ncard2 = "10H"\ncard3 = "10D"\ncard4 = "4C"\ncard5 = "9S"\n\nranks = card1[:-1] + "," + card2[:-1] + "," + card3[:-1] + "," + card4[:-1] + "," + card5[:-1]\n\n# How many cards share card1\'s rank, including card1 itself?\nmatches_rank1 = ranks.count(card1[:-1])\nprint("Cards matching card1\'s rank:", matches_rank1)\n\nif matches_rank1 == 4:\n    print("Four of a Kind (on card1\'s rank)")\nelif matches_rank1 == 3:\n    print("Three of a Kind (on card1\'s rank)")\nelse:\n    print("card1\'s rank does not repeat 3+ times")'),
    ],
    hide_code=True,
)
def three_four_of_a_kind():
    """## Three/Four of a Kind: Counting Repeats

Joining every rank into one comma-separated string turns "how many
cards share this rank" back into a single `count()` call (3.5) --
just like the suits did for the Flush check, but on ranks instead:

```python
ranks = rank1 + "," + rank2 + "," + rank3 + "," + rank4 + "," + rank5
matches_rank1 = ranks.count(rank1)
```

The comma separators matter: without them, `count("1")` on ranks
`"10","10","10","4","9"` would also match the `"1"` inside `"10"`
where there isn't one -- a subtle bug 3.5's `count()`/`find()`
distinction (searching for a *substring*, not a whole field) makes
worth calling out.

Then it's an ordinary `if`/`elif` (4.7) on the count:

```python
if matches_rank1 == 4:
    ...  # Four of a Kind
elif matches_rank1 == 3:
    ...  # Three of a Kind
```"""
    card1, card2, card3, card4, card5 = "10S", "10H", "10D", "4C", "9S"
    rank1, rank2, rank3, rank4, rank5 = card1[:-1], card2[:-1], card3[:-1], card4[:-1], card5[:-1]
    ranks = rank1 + "," + rank2 + "," + rank3 + "," + rank4 + "," + rank5
    matches_rank1 = ranks.count(rank1)
    if matches_rank1 == 4:
        label = "Four of a Kind (on card1's rank)"
    elif matches_rank1 == 3:
        label = "Three of a Kind (on card1's rank)"
    else:
        label = "card1's rank does not repeat 3+ times"
    return cs.md(f"**Ranks:** `{ranks}`  \n**matches_rank1 =** `{matches_rank1}`  \n**{label}**")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('straight_low_text', default='4'),
        ui.tests('Straight check by numeric value', default='low = 4\n\n# Five consecutive integer ranks starting at low\nr1, r2, r3, r4, r5 = low, low + 1, low + 2, low + 3, low + 4\n\nis_straight = (r2 == r1 + 1) and (r3 == r1 + 2) and (r4 == r1 + 3) and (r5 == r1 + 4)\nprint(f"{r1} {r2} {r3} {r4} {r5}")\nprint("Straight?", is_straight)'),
    ],
    hide_code=True,
    layout={'column_fraction': 0.45, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'Straight check by numeric value': 'top-right', '__inputs__': 'bottom-left'}, 'extra_code_fraction': 0.5},
)
def straight_check(straight_low_text):
    """## Detecting a Straight: Five Consecutive Ranks

A **Straight** is five cards with consecutive ranks, regardless of
suit. `int()` converts a numeric rank string to an integer (used
throughout Chapter 4's own `input()` examples), so once face cards
are mapped to numbers (`J=11, Q=12, K=13, A=14`), a Straight is just a
**range check** (4.6/4.7): each rank is exactly one more than the
last.

```python
is_straight = (
    (r2 == r1 + 1) and (r3 == r1 + 2)
    and (r4 == r1 + 3) and (r5 == r1 + 4)
)
```

Same `and`-chain shape as the Flush check earlier -- only the
comparison itself changed, from "equal to" to "exactly one more
than."

Type the lowest rank in the straight below (as a number, `2`-`10`)."""
    low = int(straight_low_text)
    r1, r2, r3, r4, r5 = low, low + 1, low + 2, low + 3, low + 4
    is_straight = (r2 == r1 + 1) and (r3 == r1 + 2) and (r4 == r1 + 3) and (r5 == r1 + 4)
    return cs.md(f"**Ranks:** `{r1} {r2} {r3} {r4} {r5}`  \n**Straight?** `{is_straight}`")


@app.cell(
    instance='editable',
    elements=[
        ui.notes('notes'),
        ui.text_input('hand_text', default='10S 10H 10D 4C 9S'),
        ui.tests(
            'The full classifier',
            default=(
                'hand_text = "10S 10H 10D 4C 9S"\n'
                '\n'
                '# Cards vary in length ("AS" is 2 chars, "10H" is 3), so\n'
                '# fixed-width slicing would misalign -- find() locates each\n'
                '# space instead, same as the cell body above.\n'
                'space1 = hand_text.find(" ")\n'
                'space2 = hand_text.find(" ", space1 + 1)\n'
                'space3 = hand_text.find(" ", space2 + 1)\n'
                'space4 = hand_text.find(" ", space3 + 1)\n'
                '\n'
                'card1 = hand_text[:space1]\n'
                'card2 = hand_text[space1 + 1:space2]\n'
                'card3 = hand_text[space2 + 1:space3]\n'
                'card4 = hand_text[space3 + 1:space4]\n'
                'card5 = hand_text[space4 + 1:]\n'
                'print(card1, card2, card3, card4, card5)\n'
            ),
        ),
    ],
    hide_code=True,
    layout={'column_fraction': 0.4, 'left_panel_fraction': 0.5, 'right_panel_fraction': 0.5, 'tab_quadrant': {'The full classifier': 'top-right', '__inputs__': 'bottom-left'}, 'extra_code_fraction': 0.5},
)
def full_classifier(hand_text):
    """## Putting It Together: One `if`-`elif` Chain

Every rule from this deck, combined into a single **nested/elif
decision** (4.7, 4.8): compute every boolean flag first (Flush, Pair,
Three/Four of a Kind, Straight -- one `and`/`or` expression each,
exactly as built above), then rank them from best to worst with one
`elif` chain, same as the anniversaries/insurance-price examples --
only the **first** `True` branch wins.

Five cards are typed as one space-separated string (`"10S 10H 10D 4C
9S"`) and split apart with `find()`/slicing (3.5/3.2) rather than a
`.split()` call, since only `find`, slicing, and indexing are in this
chapter's material.

Try: `AS 9S 2S KS 7S` (Flush), `4C 5D 6S 7H 8C` (Straight),
`10S 10H 10D 4C 9S` (Three of a Kind), `AS AH 10D 4C 9S` (Pair)."""
    space1 = hand_text.find(" ")
    space2 = hand_text.find(" ", space1 + 1)
    space3 = hand_text.find(" ", space2 + 1)
    space4 = hand_text.find(" ", space3 + 1)

    card1 = hand_text[:space1]
    card2 = hand_text[space1 + 1:space2]
    card3 = hand_text[space2 + 1:space3]
    card4 = hand_text[space3 + 1:space4]
    card5 = hand_text[space4 + 1:]

    rank1, suit1 = card1[:-1], card1[-1]
    rank2, suit2 = card2[:-1], card2[-1]
    rank3, suit3 = card3[:-1], card3[-1]
    rank4, suit4 = card4[:-1], card4[-1]
    rank5, suit5 = card5[:-1], card5[-1]

    ranks = rank1 + "," + rank2 + "," + rank3 + "," + rank4 + "," + rank5

    is_flush = (suit1 == suit2) and (suit1 == suit3) and (suit1 == suit4) and (suit1 == suit5)

    # How many cards share each card's own rank (including itself).
    count1 = ranks.count(rank1)
    count2 = ranks.count(rank2)
    count3 = ranks.count(rank3)
    count4 = ranks.count(rank4)
    count5 = ranks.count(rank5)

    best_count = count1
    best_count = max(count2, best_count)
    best_count = max(count3, best_count)
    best_count = max(count4, best_count)
    best_count = max(count5, best_count)

    has_pair = (
        rank1 == rank2 or rank1 == rank3 or rank1 == rank4 or rank1 == rank5 or
        rank2 == rank3 or rank2 == rank4 or rank2 == rank5 or
        rank3 == rank4 or rank3 == rank5
        or rank4 == rank5
    )

    # Full House needs a pair on a *different* rank than the triple --
    # otherwise "10,10,10,4,9" would wrongly look like it has a pair too,
    # since rank1 == rank2 (both "10") is part of the triple itself.
    is_full_house = (
        (count1 == 3 and (rank2 != rank1 and count2 == 2 or rank4 != rank1 and count4 == 2 or rank5 != rank1 and count5 == 2)) or
        (count2 == 3 and (rank1 != rank2 and count1 == 2 or rank4 != rank2 and count4 == 2 or rank5 != rank2 and count5 == 2)) or
        (count4 == 3 and (rank1 != rank4 and count1 == 2 or rank2 != rank4 and count2 == 2 or rank5 != rank4 and count5 == 2)) or
        (count5 == 3 and (rank1 != rank5 and count1 == 2 or rank2 != rank5 and count2 == 2 or rank4 != rank5 and count4 == 2))
    )

    if rank1 == "J":
        v1 = 11
    elif rank1 == "Q":
        v1 = 12
    elif rank1 == "K":
        v1 = 13
    elif rank1 == "A":
        v1 = 14
    else:
        v1 = int(rank1)

    if rank2 == "J":
        v2 = 11
    elif rank2 == "Q":
        v2 = 12
    elif rank2 == "K":
        v2 = 13
    elif rank2 == "A":
        v2 = 14
    else:
        v2 = int(rank2)

    if rank3 == "J":
        v3 = 11
    elif rank3 == "Q":
        v3 = 12
    elif rank3 == "K":
        v3 = 13
    elif rank3 == "A":
        v3 = 14
    else:
        v3 = int(rank3)

    if rank4 == "J":
        v4 = 11
    elif rank4 == "Q":
        v4 = 12
    elif rank4 == "K":
        v4 = 13
    elif rank4 == "A":
        v4 = 14
    else:
        v4 = int(rank4)

    if rank5 == "J":
        v5 = 11
    elif rank5 == "Q":
        v5 = 12
    elif rank5 == "K":
        v5 = 13
    elif rank5 == "A":
        v5 = 14
    else:
        v5 = int(rank5)

    lo = v1
    lo = min(v2, lo)
    lo = min(v3, lo)
    lo = min(v4, lo)
    lo = min(v5, lo)
    is_straight = (
        (v1 == lo or v2 == lo or v3 == lo or v4 == lo or v5 == lo)
        and (v1 == lo + 1 or v2 == lo + 1 or v3 == lo + 1 or v4 == lo + 1 or v5 == lo + 1)
        and (v1 == lo + 2 or v2 == lo + 2 or v3 == lo + 2 or v4 == lo + 2 or v5 == lo + 2)
        and (v1 == lo + 3 or v2 == lo + 3 or v3 == lo + 3 or v4 == lo + 3 or v5 == lo + 3)
        and (v1 == lo + 4 or v2 == lo + 4 or v3 == lo + 4 or v4 == lo + 4 or v5 == lo + 4)
        and not has_pair
    )

    if is_straight and is_flush:
        classification = "Straight Flush"
    elif best_count == 4:
        classification = "Four of a Kind"
    elif is_full_house:
        classification = "Full House"
    elif is_flush:
        classification = "Flush"
    elif is_straight:
        classification = "Straight"
    elif best_count == 3:
        classification = "Three of a Kind"
    elif has_pair:
        classification = "Pair or Two Pair"
    else:
        classification = "High Card"

    return cs.md(
        f"**Hand:** `{card1}` `{card2}` `{card3}` `{card4}` `{card5}`\n\n"
        f"**Classification:** ## {classification}"
    )


@app.slide('Title', cells=[])
def slide_title():
    """"""


@app.slide('A Card Is Just a String', cells=['cards_as_strings'])
def slide_1():
    """"""


@app.slide('Slicing Off Rank and Suit', cells=['slicing_rank_suit'])
def slide_2():
    """"""


@app.slide('Displaying the Hand With f-strings', cells=['fstring_hand_summary'])
def slide_3():
    """"""


@app.slide('Counting Matches: count() and in', cells=['string_methods_count_in'])
def slide_4():
    """"""


@app.slide('Detecting a Flush', cells=['flush_check'])
def slide_5():
    """"""


@app.slide('Detecting a Pair', cells=['pair_check'])
def slide_6():
    """"""


@app.slide('Three/Four of a Kind', cells=['three_four_of_a_kind'])
def slide_7():
    """"""


@app.slide('Detecting a Straight', cells=['straight_check'])
def slide_8():
    """"""


@app.slide('The Full Classifier', cells=['full_classifier'])
def slide_9():
    """"""
