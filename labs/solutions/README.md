# Reference Solutions — Single-File Labs

Reference solutions for the four single-file labs in
`../chapter1-2-lab-ideas-single-file.md`. Each solution uses **only**
skills taught in `Lectures/Chapters/chapter1.py` and
`Lectures/Chapters/chapter2.py` as of this writing: `input()`/`print()`,
variables and assignment (including compound operators), `int()`/
`float()`/`str()` conversion, arithmetic expressions and operator
precedence, `//` and `%`, f-string formatting with `:.Nf` precision,
`import`, and the `math`/`random` module functions the decks actually
demonstrate (`math.sqrt`, `math.pow`, `math.floor`, `math.ceil`,
`math.fabs`, `math.factorial`, `math.pi`; `random.random`,
`random.randint`, `random.randrange`, `random.seed`).

None of these use `def`, `if`, `for`/`while`, string methods, or
format-spec alignment (`:<`, `:>`) — none of that is taught yet, so
none of it appears here, matching the "single-file, straight-line code"
constraint from the lab spec.

| Solution file | Lab idea |
| --- | --- |
| `road_trip_planner.py` | Lab Idea 4: Road Trip Planner |
| `character_sheet_generator.py` | Lab Idea 5: Game Character Sheet Generator |
| `astronomy_session_planner.py` | Lab Idea 6: Backyard Astronomy Session Planner |
| `personal_budget_simulator.py` | Lab Idea 7: Personal Budget Simulator |

## Notes for instructors

- **`character_sheet_generator.py`** originally used string methods
  (`.isalpha()`, `.replace()`), string slicing, `.center()`, and
  format-spec alignment (`:+d`, `:<`, `:>`) to build the identifier
  check and an aligned character sheet table. All of that was removed
  in favor of plain `print()` calls with comma-separated arguments,
  since none of those tools are taught in Chapters 1–2 — a good example
  to point out to students of *why* a feature that "would make this
  easier" sometimes isn't available yet.
- **`astronomy_session_planner.py`** uses `random.randint(1, 5)` for the
  "seeing quality" roll instead of `random.uniform()`, since `uniform`
  isn't covered by either deck (only `random`, `randint`, `randrange`,
  and `seed` are).
- **`personal_budget_simulator.py`**'s savings-goal math (Section 4)
  only produces a sensible answer when `leftover` (income minus
  expenses) is positive. Feeding it expenses that exceed income
  produces a nonsensical negative "periods needed" value, with no way
  to detect or guard against it without `if` — this is intentional and
  called out in a code comment; it's a natural discussion point for why
  conditionals matter, without requiring the lab itself to use them.
- Every file was executed with sample input to confirm it runs without
  error and produces internally-consistent output before being added
  here.
