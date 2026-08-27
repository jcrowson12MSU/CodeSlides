# Lab Assignment Ideas — Single-File Edition

Source material: `Lectures/Chapters/chapter1.py` (Introduction to Python)
and `Lectures/Chapters/chapter2.py` (Variables, Types, and Expressions).

These ideas replace the multi-file "toolkit" structure from
`chapter1-2-lab-ideas.md` with a **single `.py` file per lab**. Same
skills, same three-week scope, same constraint that neither chapter has
covered functions, loops, or conditionals yet — so every idea below is
still straight-line code from top to bottom. What changes is the
*shape*: instead of five small standalone programs, each lab is one
script divided into clearly labeled sections (comment banners), where
later sections are often allowed to build on variables computed in
earlier ones. That's actually a slightly closer match to what Chapter 2
already models — `division_and_modulo`, `math_module`, and
`random_numbers` all read as "one scenario worked through step by step,"
not independent programs.

## Skills inventory

(Same as before — repeated here so this file stands alone.)

**From Chapter 1:** Input → Process → Output; variables and `=`;
`print()` with `sep=`/`end=`; strings and escape sequences; `int` vs
`float` literals; `input()` always returns a string; the three error
types (syntax/runtime/logic) and why exact output formatting matters;
`=` vs `==`; a worked multi-input calculation with a formatted summary.

**From Chapter 2:** assignment statements incl. a variable on both
sides; the "only a bare variable may sit left of `=`" rule; identifiers
and naming style; mutability; `float` literals/scientific
notation/`OverflowError`; explicit conversion with `int()`/`float()`/
`str()`; arithmetic expressions and operator precedence; compound
assignment (`+=`, `-=`, `*=`, `/=`); `//` and `%` incl. digit
extraction; `import` and dot notation; the `math` module; the `random`
module.

## A note on single-file structure

Every lab below should be submitted as one `.py` file, organized with
comment banners marking each section, e.g.:

```python
# ============================================================
# SECTION 1: Trip Basics
# ============================================================
...

# ============================================================
# SECTION 2: Fuel and Cost
# ============================================================
...
```

Because the whole file is one script, a variable computed in Section 2
can be reused in Section 4 without re-prompting for it — encourage
students to *plan* which values need to flow forward (this is good
practice for the return-value/parameter thinking they'll need once
functions are introduced) but don't require it; a student who
re-collects a value with a second `input()` call instead should not be
penalized, just prompted to note the redundancy in their reflection.

---

## Lab Idea 4: Road Trip Planner

**Theme:** One continuous script that plans a road trip from start to
finish, with each section depending on realistic values computed
earlier — a natural fit for a single growing file.

**Required sections (all in one file):**

1. **Trip Basics** — prompt for starting city name, destination city
   name, and total distance in miles (`float`). Print a formatted trip
   header using `sep`/`end` and an f-string banner.
2. **Vehicle and Fuel** — prompt for the car's fuel efficiency (mpg) and
   the price of gas per gallon; compute total gallons needed (`/`) and
   total fuel cost; also compute *whole* gallons and leftover
   fractional gallons using `//` and `%` on a scaled integer (e.g.
   tenths-of-a-gallon) to force real practice with integer division on
   a value that isn't already a clean integer.
3. **Time Estimate** — prompt for average driving speed (mph); compute
   total driving time in hours as a `float`, then convert that float
   into whole hours and remaining minutes using `//`/`%` (same pattern
   as the Ch. 2 minutes-to-hours example, but derived rather than
   directly input).
4. **Pit Stops** — using `random.randint()`, generate a random number of
   rest stops between 2 and 5, and for *each* stop's *position* (not a
   loop — just three or four separate `random.randint()` calls, one
   per possible stop, clearly labeled Stop 1 / Stop 2 / etc.), compute
   how many miles into the trip that stop falls, using the randomly
   generated stop count from earlier and simple arithmetic.
5. **Trip Cost Summary** — using `math` module functions at least once
   (e.g., `math.ceil` to round the fuel cost up to the nearest dollar
   for a "budget with buffer" figure), print a final formatted summary
   table combining every value computed in the sections above:
   distance, time (hours and minutes), fuel cost (exact and rounded
   buffer), and the random pit stop positions.

**Deliverables:** one `.py` file (150–250 lines expected including
comments/banners), a short written reflection (half a page) identifying
every place a value from an earlier section was reused in a later one,
and output from at least two full runs with different inputs pasted
into the submission.

**Why it fills three weeks:** five interdependent sections force
students to actually track which variables need to survive to later
sections — a real design problem even without functions — plus careful
tuning of the random pit-stop math and formatting a genuinely large
final summary correctly.

---

## Lab Idea 5: Game Character Sheet Generator

**Theme:** A single script that builds a tabletop-RPG-style character
sheet, mixing player-provided identity info with randomly generated
stats — appealing to students who like games, and a good showcase for
`random` alongside `math`.

**Required sections (all in one file):**

1. **Identity** — prompt for character name, a one-word class (e.g.
   "Wizard"), and a starting gold amount (`int`). Validate the name is
   a reasonable identifier-safe string by *printing* whether it could
   also be used as a Python variable name (reusing the identifier rules
   from Ch. 2, without needing `if` — just print the components of the
   check: does it start with a letter/underscore? does it contain only
   letters/digits/underscores? print `True`/`False` for each check).
2. **Random Attributes** — use `random.randint(1, 20)` six separate
   times (Strength, Dexterity, Constitution, Intelligence, Wisdom,
   Charisma — six *distinct*, separately labeled calls, not a loop),
   then compute each attribute's "modifier" using integer division and
   subtraction (`(score - 10) // 2`), printing both the raw score and
   the modifier for each of the six.
3. **Derived Stats** — compute hit points as a function of the
   Constitution modifier and class (hard-code a fixed base HP for the
   one class the student is prompted for, then add `Constitution
   modifier * some multiplier`); compute a "carry capacity" in pounds
   using `Strength score * 15` (or similar); compute an "armor class"
   combining a base value and the Dexterity modifier.
4. **Starting Loot Roll** — simulate opening a treasure chest: use
   `random.randint()` for a gold amount found and `random.random()` to
   determine a "rarity roll" for one random item (print the raw
   0–1 float, then also print it multiplied by 100 and rounded via
   `round()` or formatted to 1 decimal place as a "rarity percentage").
   Add the found gold to the starting gold from Section 1 using `+=`.
5. **Final Character Sheet** — print a fully formatted character sheet
   combining everything above: name, class, all six attributes and
   modifiers, HP, AC, carry capacity, and final gold total — formatted
   like an actual game character sheet (aligned columns using `sep`,
   multiple `print()` calls with consistent spacing, a bordered header
   using repeated characters like `"=" * 40`).

**Deliverables:** one `.py` file, two full sample runs (showing the
randomness genuinely changes each run) pasted into the submission, and
a short reflection on which derived stat calculation was trickiest to
get the types right on (e.g. avoiding an `int`/`float` mismatch in a
printed modifier).

**Why it fills three weeks:** six distinct random attribute rolls, each
feeding a distinct derived-stat formula, forces careful, repetitive-but-
not-identical arithmetic across many lines — plus the formatting
challenge of a genuinely good-looking character sheet is real, iterative
polish work that rewards the extra time.

---

## Lab Idea 6: Backyard Astronomy Session Planner

**Theme:** A single script that plans an evening of stargazing,
combining unit conversions, the `math` module for real trigonometry-
adjacent calculations, and `random` for simulating "which objects are
visible tonight."

**Required sections (all in one file):**

1. **Location and Time** — prompt for the user's approximate latitude
   (a `float`, e.g. `33.4`) and today's date components (month, day, as
   separate `int` inputs — no `datetime` module, since that's out of
   scope; just plain integers used for display).
2. **Telescope Math** — prompt for the telescope's aperture (in mm) and
   focal length (in mm); compute the focal ratio (`focal length /
   aperture`) and, using a fixed eyepiece focal length given in the
   instructions (e.g. 25mm), compute magnification
   (`telescope focal length / eyepiece focal length`). Use `math.pow`
   or `**` to also compute the telescope's theoretical resolving power
   using the Dawes limit formula (`116 / aperture_in_mm`), converting
   the result into arcseconds and printing it to 2 decimal places.
3. **Weather Roll** — since real weather data is out of scope, simulate
   tonight's conditions with `random`: a cloud cover percentage
   (`random.randint(0, 100)`), a "seeing" quality score
   (`random.uniform(1.0, 5.0)` if available, otherwise
   `random.randint(1, 5)`), and a temperature in Fahrenheit
   (`random.randint(30, 90)`). Convert the temperature to Celsius using
   the Ch. 2 conversion pattern.
4. **Object Visibility** — pick three fixed celestial objects (e.g.
   Jupiter, the Orion Nebula, Saturn's rings) and for *each one
   individually* (three separate, clearly labeled blocks — not a loop),
   compute a "visibility score" combining the random cloud cover and
   seeing values from Section 3 with a fixed per-object difficulty
   rating the student hard-codes (e.g. Saturn's rings are harder to see
   than Jupiter), using compound operators to accumulate a running
   score. Print each object's final score.
5. **Session Summary** — print a final "tonight's observing plan"
   report combining every earlier section: location, telescope specs
   (focal ratio, magnification, resolving power), simulated weather
   (with both F° and C°), and all three objects' visibility scores
   ranked by printing them in a fixed, hard-coded order with their
   scores next to them (no sorting needed — sorting logic is out of
   scope; just print all three, and let the reflection question ask the
   student which one *they* would pick).

**Deliverables:** one `.py` file, two full runs' output pasted into the
submission (to show the weather/visibility randomness working), and a
half-page reflection identifying every `math` module function used and
what real-world telescope concept each one modeled.

**Why it fills three weeks:** this is the most "research-flavored" of
the four ideas — students have to look up (or be given) real formulas
for focal ratio, magnification, and the Dawes limit, translate them
correctly into Python expressions respecting precedence rules, and then
build a genuinely satisfying, information-dense final report. Getting
the physics-flavored math right, on top of the formatting, is enough
work to justify the full three weeks.

---

## Lab Idea 7: Personal Budget Simulator *(closest to Lab Idea 1's finance theme, but single-file)*

**Theme:** A direct single-file rework of the finance-toolkit idea —
good if you liked Lab Idea 1's theme but want the one-file constraint.

**Required sections (all in one file):**

1. **Income** — prompt for hourly wage, hours worked per week, and
   number of weeks in the budgeting period (`int`); compute total gross
   income for the period.
2. **Fixed Expenses** — prompt for rent, a utilities estimate, and a
   subscriptions total (three separate `float` inputs); sum them into a
   total fixed-expenses figure using compound operators (`+=` chained
   across the three).
3. **Variable Spending Estimate** — prompt for an estimated daily
   discretionary spending amount and the number of days in the
   budgeting period; compute total discretionary spending, then compute
   what percentage of gross income that represents (careful `int`/
   `float` handling required to avoid an integer-division surprise).
4. **Savings Goal Check** — prompt for a savings goal amount; compute
   leftover money after fixed and discretionary expenses; compute how
   many *whole* budgeting periods (using `//`) it would take to reach
   the goal at the current leftover-per-period rate, and how much
   "extra" would still be needed in the final partial period (`%`).
5. **What-If Randomizer** — simulate three random "surprise expenses"
   using `random.randint()` (e.g., a car repair, a medical copay, a
   gift) with different min/max ranges reflecting realistic amounts for
   each; subtract each from the leftover total in turn using `-=`;
   print a final "adjusted leftover" and compare it to the original
   leftover from Section 4, printing the dollar difference.

**Deliverables:** one `.py` file, output from at least two runs with
different income/expense inputs, and a written reflection describing
one spot where floating-point rounding produced an output that looked
slightly "off" (e.g. `29.999999999999996` instead of `30.0`) and how
they handled displaying it cleanly with formatted output.

**Why it fills three weeks:** five sections that must correctly track a
running "leftover" balance through several compound-operator updates,
careful percentage math, and a randomized what-if scenario is
substantial, realistic scope for a single file — and the floating-point
formatting reflection targets a subtlety worth dwelling on.

---

## Suggested lab structure (unchanged)

| Week | Milestone |
| --- | --- |
| 1 | Design/planning document due: list every required section, every input, and which chapter skill each section demonstrates. Instructor sign-off before coding begins. |
| 2 | Working draft with at least the first half of the sections complete and producing correct output for one test case. |
| 3 | All sections complete, tested against multiple input sets, formatting polished, written reflection submitted alongside the single `.py` file. |

## Grading rubric sketch (unchanged)

| Category | Weight |
| --- | --- |
| Correctness (every section produces correct output for given inputs) | 40% |
| Appropriate use of required skills (type conversion, precedence, modules, etc. — not avoided or worked around) | 20% |
| Output formatting and readability (`print` formatting, f-strings, alignment, section banners) | 15% |
| Code style (identifier naming, PEP 8, comments where the *why* isn't obvious) | 10% |
| Design document / reflection | 15% |
