# Lab Assignment Ideas — Chapters 1 & 2

Source material: `Lectures/Chapters/chapter1.py` (Introduction to Python)
and `Lectures/Chapters/chapter2.py` (Variables, Types, and Expressions).

## Skills inventory

Everything below is scoped to what these two decks actually teach.
Neither chapter has covered **functions, loops, or conditionals** yet, so
every lab idea is deliberately straight-line code: no `def`, no `for`/
`while`, no `if`. A lab justifies three weeks of work by asking for more
*straight-line computation, careful formatting, and multiple worked
scenarios* — not by reaching for control flow the class hasn't seen.

**From Chapter 1 — Introduction to Python**
- Input → Process → Output as the shape of every program
- Variables as named buckets; `=` as assignment, not math equality
- `print()`, including `sep=`, `end=`, and printing multiple values
- Strings: quoting, escape sequences (`\n`, `\t`), embedded quotes/backslashes
- `int` vs `float` literals
- Why `1 + 1` and `"1" + "1"` are not the same thing
- `input()` and prompts (always returns a string)
- The IDE loop: write, run, read output, fix
- The three error types: syntax, runtime, logic — and that they look different
- Whitespace/output-formatting precision (exact match matters)
- `=` vs `==`
- A worked multi-input calculation with formatted summary output (pay calculator)

**From Chapter 2 — Variables, Types, and Expressions**
- Assignment statements, including a variable on both sides (`x = x + 1`)
- The rule that only a bare variable may sit left of `=`
- Identifiers: valid names, case sensitivity, reserved words, naming style
- Mutability/immutability of values
- `float` literals, scientific notation, `OverflowError`, decimal formatting
- Explicit type conversion: `int()`, `float()`, `str()`
- Arithmetic expressions and operator precedence (`()`, `**`, unary `-`, `* / %`, `+ -`)
- Compound assignment operators (`+=`, `-=`, `*=`, `/=`)
- Integer division `//` and modulo `%`, including digit extraction
- `import` and using functions from a module by dot notation
- The `math` module (`sqrt`, `pow`, `floor`, `ceil`, `fabs`, `pi`, ...)
- The `random` module (`random()`, `randint()`, `randrange()`, `seed()`)

## How to use this list

Each lab idea below names the specific slide-deck skills it draws on, so
you can swap requirements in/out to match how far through the two decks
your section has actually gotten. A three-week lab should read as **one
lab report with several required programs**, not one script — that's
what makes the scope match the timeline without needing loops or
functions to pad it out.

---

## Lab Idea 1: Personal Finance Toolkit

**Theme:** A small collection of standalone calculator programs a student
could plausibly use in real life — building a portfolio of "useful little
programs" rather than one big one.

**Required programs (each a separate `.py` file or clearly separated
section of one file):**

1. **Paycheck Calculator** — prompts for hourly rate, hours worked, and a
   tax rate percentage; computes gross pay, tax withheld, and net pay;
   prints a formatted, aligned pay stub using `sep`/`end`/f-strings.
   (Ch. 1 pay calculator pattern, Ch. 2 arithmetic + compound operators)
2. **Tip and Split Calculator** — prompts for a bill total, tip
   percentage, and number of people; computes tip amount, total, and
   per-person share; must handle the share not dividing evenly by
   showing dollars and cents separately using `//` and `%`.
   (Ch. 2 division/modulo, type conversion)
3. **Savings Growth Estimator** — prompts for a starting balance, an
   annual interest rate, and a number of years; uses `math.pow` to
   project the ending balance; also reports the *change* in dollars and
   as a percentage. (Ch. 2 math module, arithmetic expressions)
4. **Loan Payment Snapshot** — prompts for loan amount, annual interest
   rate, and loan term in months; computes a simplified monthly payment
   estimate (no need for the compounding-interest formula — a linear
   estimate using compound operators is fine) and total interest paid
   over the life of the loan.
5. **Summary Report** — a fifth program that hard-codes example output
   from the four programs above (copy in a specific run's numbers) and
   prints a single combined "financial snapshot" using only `print()`
   formatting — no recomputation, just formatting practice with `f""`
   strings, `sep`, and `end`.

**Deliverables:** five `.py` files, a short `README.md` explaining each
program's inputs/outputs, and a **written reflection** (half a page) on
which type conversions were necessary and why (`input()` always returns
a string).

**Why it fills three weeks:** five distinct programs, each needing its
own careful I/O design, formatted output, and testing with multiple
input values (including edge cases like $0 tips or 0% interest) — plenty
of surface area without any control flow.

---

## Lab Idea 2: Unit Conversion and Measurement Suite

**Theme:** A multi-tool measurement converter, emphasizing precision,
formatting, and the difference between `int` and `float`.

**Required programs:**

1. **Temperature Converter** — converts a Fahrenheit input to Celsius
   *and* Kelvin in the same run, printed to 2 decimal places.
2. **Distance/Time Converter** — given a distance in miles and a speed in
   mph, compute travel time in hours, then convert that to whole hours
   and remaining minutes using `//` and `%` (mirrors the Ch. 2
   minutes-to-hours example, run in reverse).
3. **Recipe Scaler** — given a recipe's original serving size and
   ingredient amounts (at least 3 ingredients, each its own `float`
   input), and a desired new serving size, scale each ingredient amount
   and print a formatted new recipe card.
4. **Body Mass Index (BMI) Calculator** — given height in inches and
   weight in pounds, compute BMI using the standard formula (requires
   `**` for squaring), and print the number *and* which of 4 fixed
   category boundaries it's nearest to, using only string labels chosen
   by hard-coded comparison values shown as printed diagnostic messages
   (no `if` — just print all four boundary distances and let the
   student/reader see the results; this deliberately previews *why*
   `if` will matter next chapter, without requiring it).
5. **Randomized Practice Problems** — using `random.randint()`, generate
   two random measurements (e.g., a random Fahrenheit temperature and a
   random distance/speed pair) each time the program runs, and feed
   them into the temperature and distance conversions above so the
   output changes on every run. Use `random.seed()` once, with a comment
   explaining what reproducibility means and why a grader might want it.

**Deliverables:** five `.py` files, sample output captured from at least
three different runs per program (pasted into a `results.md`), and a
short explanation of one `OverflowError` or precision surprise
encountered while testing (even a deliberately provoked one, e.g. `2.0
** 1024`).

**Why it fills three weeks:** each converter needs its own careful
input validation strategy (even without `if`, students must think about
what a "reasonable" input range is), multiple unit systems, and the
random-number integration ties two chapters together into a nontrivial
final piece.

---

## Lab Idea 3: "Choose Your Own Adventure" Number Story *(lightweight, most approachable)*

**Theme:** A single narrative program, structured like the Ch. 1
computational-thinking "recipe" example, that walks a user through a
sequence of choices — but since there's no `if`, every "choice" is
actually a *math trick*: the user's input is fed through arithmetic to
produce a different message via string formatting, not branching logic.

**Requirements:**

- At least 8 `input()` prompts total across the story, mixing string and
  numeric input, all correctly converted with `int()`/`float()`.
- At least one moment where the story uses `random.randint()` to
  introduce an unpredictable event (a dice roll, a random encounter
  strength, a random amount of gold found) and weaves the result into
  later output.
- At least one moment using `%`/`//` meaningfully in the story (e.g.,
  splitting loot "evenly" among party members with a leftover amount
  called out by name).
- At least one moment using `math` module functions non-trivially (e.g.
  computing a "distance traveled" with `math.sqrt`, or a "damage roll"
  using `math.pow`).
- Careful, illustrated formatting throughout: multi-line `print()`
  output that reads like a story, not a debug dump — proper use of
  `\n`, `sep`, `end`, and f-strings.
- A short **design document** (1 page) written *before* coding, listing
  each planned prompt, what it captures, and what calculation or module
  call it feeds into.

**Deliverables:** one `.py` file (200+ lines is expected, mostly print
statements and prompts), the design document, and a transcript of one
full playthrough's output pasted into the submission.

**Why it fills three weeks:** the constraint of "no `if`, no `def`, no
loops" makes writing an interesting, non-repetitive 8+ step narrative
surprisingly time-consuming — the design document forces up-front
planning, and getting the formatting/pacing to read naturally is real,
iterative work.

---

## Suggested lab structure (any of the three)

| Week | Milestone |
| --- | --- |
| 1 | Design/planning document due: list every required calculation, every input, and which chapter skill it demonstrates. Instructor sign-off before coding begins. |
| 2 | Working draft of at least half the required programs/story beats, runnable and producing correct output for at least one test case each. |
| 3 | All programs complete, tested against multiple input sets, formatting polished, written reflection/README submitted alongside the code. |

## Grading rubric sketch

| Category | Weight |
| --- | --- |
| Correctness (each program/section produces correct output for given inputs) | 40% |
| Appropriate use of required skills (type conversion, precedence, modules, etc. — not avoided or worked around) | 20% |
| Output formatting and readability (`print` formatting, f-strings, alignment) | 15% |
| Code style (identifier naming, PEP 8, comments where the *why* isn't obvious) | 10% |
| Design document / README / reflection | 15% |
