# Lab Assignment Idea — Chapter 4 (Branches)

Source material: `Lectures/Chapters/chapter3.py` (Strings) and
`Lectures/Chapters/chapter4.py` (Branches). This lab is scoped so that
`if`/`elif`/`else` is the star: nearly every requirement below exists
specifically to create one more decision point, and every decision is
made by comparing or inspecting **strings** — no `math` module, no
`random`, no lists, no loops, and no `def`.

## Skills inventory this lab draws on

**From Chapter 3 — Strings**
- String comparisons (`==`, `!=`, `<`, `>`) and why they're
  case-sensitive
- Case-normalizing input with `.lower()` / `.upper()` before comparing
- `.strip()` to clean up stray whitespace from `input()`
- `.startswith()` / `.endswith()`
- `in` / `not in` for substring checks
- `.find()` / `.count()`
- `.isX()` methods (`.isdigit()`, `.isalpha()`, `.isupper()`, ...)
- f-strings for formatted output

**From Chapter 4 — Branches**
- `if`, `if`/`else`, and `if`/`elif`/`else`
- Comparison operators: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Boolean logic: `and`, `or`, `not`, and combining multiple conditions
  in one `if`
- Nested `if` statements (an `if` inside another `if`'s branch)
- The rule that only the *first* matching branch in an `elif` chain
  runs

## The assignment: College Application Reviewer

**Theme:** the student writes a program that plays admissions officer.
It reads a fixed set of `input()` values describing one applicant —
all as strings, some later checked with `.isdigit()` rather than
converted with `int()`, since this lab is about *inspecting* strings,
not doing arithmetic on numbers — and prints a decision letter section
by section. Every section is its own reason to reach for `if`.

This framing is deliberately close to a real workflow (a batch of
independent eligibility rules feeding one decision) so the branching
doesn't feel like busywork — each `if` corresponds to one real
admissions rule.

### Required inputs (all via `input()`, all strings)

1. `applicant_name` — e.g. `"Jordan Lee"`
2. `state` — two-letter postal code, e.g. `"MI"`
3. `intended_major` — free text, e.g. `"Computer Science"`
4. `gpa_text` — typed as a string, e.g. `"3.85"`
5. `test_score_text` — typed as a string, e.g. `"1240"`
6. `essay` — a short paragraph the applicant wrote (at least one
   sentence, entered as one line)
7. `recommendation_text` — a short line from a recommender, e.g.
   `"Jordan is one of the most curious students I have taught."`
8. `activities` — a comma-separated line of extracurriculars, e.g.
   `"Robotics Club, Varsity Soccer, Tutoring"`
9. `email` — the applicant's email address, e.g.
   `"jordan.lee@example.com"`
10. `special_program_code` — a short code the applicant typed for an
    optional scholarship/program, which may be left blank, e.g.
    `"FIRSTGEN"` or `""`

### Required decision points (each one is its own `if`)

Number the sections in the printed output so a grader can match each
one to the list below. Every item **must** be implemented as a branch
that inspects a string — not a number — even where a numeric-looking
value like GPA is involved.

1. **Name formatting check** — if `applicant_name` contains a comma
   (e.g. someone mistakenly typed `"Lee, Jordan"`), print a note asking
   them to resubmit as "First Last"; otherwise print the name as
   entered. *(uses `in`)*
2. **In-state vs. out-of-state** — if `state.upper()` equals your
   school's home state's two-letter code, print an in-state tuition
   note; otherwise print an out-of-state note. *(uses `.upper()`,
   `==`)*
3. **Major recognized or "Undeclared" fallback** — if
   `intended_major.strip() == ""`, print that the applicant will start
   as "Undeclared"; otherwise print the major as entered, with the
   first letter capitalized however it was typed (don't reformat it —
   this is intentionally simple). *(uses `.strip()`)*
4. **STEM vs. non-STEM welcome message** — if `intended_major.lower()`
   contains any of a short hard-coded list of STEM keywords you check
   one at a time (e.g. `"computer"`, `"engineer"`, `"math"`, `"bio"` —
   each its own `if`, not a loop), print a STEM-specific welcome line
   in addition to the general one. *(uses `.lower()`, `in`, multiple
   `if`s — this single requirement is worth 3-4 of your 10 branches by
   itself)*
5. **GPA band, read as a string** — compare `gpa_text` directly against
   boundary strings like `"3.5"`, using `>=`/`<`, *without* converting
   to `float`. Require every test GPA to be typed in the same `"X.XX"`
   shape (one digit, a decimal point, two digits — e.g. `"3.85"`, not
   `"4"` or `"3.5"`). Print one of: "Highest Honors," "Honors,"
   "Standard," or "Needs Review," using `if`/`elif`/`elif`/`else`.
   Part of the assignment is discovering *why* that one-digit,
   fixed-width shape matters: string comparison works character by
   character, so it only agrees with numeric comparison when every
   value being compared has the same number of digits before the
   decimal point. Students prove this to themselves in the README by
   trying a "broken" input outside that shape (see the reflection
   prompt below).
6. **Test score sanity check** — if `test_score_text.isdigit()` is
   `False`, print a rejection-of-input message ("test score must be
   numeric") and skip the remaining test-score-dependent logic instead
   of crashing; otherwise proceed. *(uses `.isdigit()`, and this is the
   one place where converting to `int()` afterward for a real
   numeric comparison is expected and fine)*
7. **Essay length gate** — if `len(essay) < 50`, print a note that the
   essay seems short and recommend the applicant expand it; otherwise
   acknowledge it as sufficient. *(`len()` returns an int, but the
   thing being measured is a string — this is meant to bridge the two
   ideas)*
8. **Recommendation sentiment keyword check** — if `recommendation_text
   .lower()` contains a strong-praise word from a short fixed list
   (e.g. `"exceptional"`, `"outstanding"`, `"one of the best"`), print
   a "flagged for scholarship review" note. *(uses `.lower()`, `in`)*
9. **Extracurricular count via `.count()`** — use `activities.count(",")`
   to figure out roughly how many activities were listed (commas + 1),
   and if that count is `0` (a blank entry) print a note recommending
   the applicant list at least one activity, else if it's `1` print
   encouragement to get involved further, else print a "well-rounded
   applicant" note. *(uses `.count()`, `if`/`elif`/`else`)*
10. **Email format check** — if `"@" not in email` **or**
    (`not email.endswith(".com")` **and** `not email.endswith(".edu")`
    **and** `not email.endswith(".org")`) — combine all of these in one
    `if` using `and`/`or` — print a note that the email looks malformed
    and won't be used for correspondence. *(uses `not in`,
    `.endswith()`, boolean `and`/`or`; written as three separate
    `.endswith()` calls, not a tuple, to keep with the "no collections"
    constraint)*
11. **Optional scholarship code, nested `if`** — if
    `special_program_code.strip() != ""`: inside that `if`'s body,
    nest a second `if`/`elif`/`else` that checks the code against 2-3
    known values (e.g. `"FIRSTGEN"`, `"VETERAN"`, `"LEGACY"`) using
    `==`, printing a specific note for each and an "unrecognized
    program code" message for anything else; if the outer check is
    `False`, skip scholarship review entirely. *(this is the required
    nested-`if` demonstration)*
12. **Overall decision line combining multiple conditions** — the
    final line of the letter should be produced by one `if`/`elif`/
    `else` chain that combines at least two of the boolean results
    computed above with `and`/`or` (for example: honors-or-above GPA
    **and** a flagged recommendation → "Admit with Distinction";
    honors-or-above GPA **or** a flagged recommendation, but not both →
    "Admit"; neither → "Refer to Committee"). This is the requirement
    that forces students to *save* boolean results from earlier
    sections in variables so they can be reused here, instead of
    re-deriving them.

That's 12 required branch points as scaffolding — comfortably over
the "about 10" target — with item 4 alone naturally producing several
more `if`s in a typical solution, and item 11's nested check adding at
least one more beyond its own bullet. Instructors can trim items 4 or
11 to hit exactly 10 if a section is running short on time.

### Constraints (enforced, not just suggested)

- **No loops** (`for`, `while`) and **no functions** (`def`) — every
  check is a standalone `if` at the top level of the script, in order,
  matching the numbered list above via comments.
- **No lists, dicts, tuples, or sets** — the "check against a short
  list of keywords" items must be written as separate `if`/`elif`
  comparisons or chained `or` conditions, not by looping over a
  collection. (This is what makes item 4 produce multiple visible
  `if`s instead of one loop.)
- Only `input()`/`print()` for I/O, string methods for inspecting
  input, comparison operators, and boolean operators for combining
  conditions. `int()` conversion is allowed *only* after an
  `.isdigit()` check (item 6) and for `len()` results — not for GPA.
- Every `if`/`elif`/`else` chain must have a **comment above it**
  naming which numbered requirement it satisfies, so grading is a
  matter of checking off a list.

### Deliverables

- One `.py` file, organized top-to-bottom in the order of the 12
  requirements, each preceded by a comment header (e.g.
  `# --- 5. GPA band (string comparison) ---`).
- Three full sample runs pasted into a `results.md`: one applicant who
  should land in "Admit with Distinction," one "Admit," and one "Refer
  to Committee" — chosen deliberately by the student to prove each
  branch of the final decision (item 12) actually gets reached.
- A half-page **README reflection** answering: (a) try feeding
  `gpa_text = "4"` (instead of `"4.00"`) or `test_score_text = "85"`
  compared against a boundary like `"100"` through your item-5-style
  logic, and explain in your own words why `"85" < "100"` evaluates to
  `False` even though `85 < 100` is `True` numerically — string
  comparison walks character by character, so a 2-digit string can
  compare as "greater than" a 3-digit one; state exactly what
  fixed-width assumption your program relies on to avoid this, and
  (b) one place where you were tempted to use a list/loop for item 4
  or item 11 and how you avoided it.

### Why this hits the "~10 `if` opportunities" target without padding

Every requirement above maps to a real, distinct admissions rule, so
the branch count grows from the *scenario* rather than from
artificially splitting one check into pieces. The "no lists/loops"
constraint is what pushes item 4's keyword search and item 11's code
lookup from one loop each into several `if`/`elif` branches each,
which is exactly the kind of repetition that makes students *feel*
why loops will matter next chapter — mirroring how Lab Idea 2's BMI
category exercise in `chapter1-2-lab-ideas.md` previews `if` by
withholding it.

### Suggested grading rubric

| Category | Weight |
| --- | --- |
| Each of the 12 required branch points present, correctly ordered, and correctly commented | 45% |
| Correct behavior across the 3 required sample runs (all three final-decision outcomes reached) | 20% |
| Proper use of string methods (`.lower()`, `.strip()`, `.isdigit()`, `.count()`, `.endswith()`, `in`) rather than workarounds | 15% |
| No loops, functions, or collections used anywhere in the file | 10% |
| README reflection (GPA string-comparison pitfall + list/loop temptation) | 10% |
