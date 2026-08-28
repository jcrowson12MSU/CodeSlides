# Discussion Guide: Personal Budget Simulator (Lab Idea 7)

**Purpose:** A quick oral check-in for a TA to run 1-on-1 with a student after they submit
the Personal Budget Simulator lab. Goal is to confirm the student understands their own
code and can explain *why* they made the choices they did — not just that it runs.

**Target time:** ~5 minutes for a student who genuinely did the work. If a student is
stalling on the first one or two questions, that's a signal to slow down and probe rather
than rush through the list.

**How to use this:** Pull up the student's actual `.py` file on their screen and point at
their specific lines while asking — don't ask in the abstract. Questions are grouped by
section but you don't need to ask every single one; pick 1–2 per section based on what's
interesting in *their* code, and always ask at least one from "Design & Judgment Calls."

---

## Section 1 — Income

- Walk me through this line: `gross_income = hourly_wage * hours_per_week * num_weeks`.
  Why multiply all three instead of computing weekly pay first and then scaling it?
- You read `hours_per_week` and `hourly_wage` with `float(input(...))` but `num_weeks`
  with `int(input(...))`. Why the different type conversion there?

## Section 2 — Fixed Expenses

- Why use `+=` three times instead of one line like
  `total_fixed_expenses = rent + utilities_estimate + subscriptions_total`?
  (Listening for: understands compound operators are equivalent here, this is a stylistic/
  pedagogical choice, not a functional one — good answer shows they know it's a choice.)
- What would happen to your total if you initialized `total_fixed_expenses` as `0`
  instead of `0.0`? Would your program still work? Why or why not?

## Section 3 — Variable Spending Estimate

- Show me the line where you compute `discretionary_percent_of_income`. What would this
  calculation return if you hadn't converted your inputs to `float`? Have you actually
  tried it and seen what breaks?
- Why multiply by `100` here instead of just printing the raw ratio?

## Section 4 — Savings Goal Check

- This is the trickiest section — walk me through what `//` and `%` are each doing here
  in plain English, using your own variable names.
- Explain the difference between `full_periods_before_goal` and
  `goal_reached_in_period`. Why is one of them `+ 1` relative to the other?
- Why did you convert everything to cents (`int(leftover * 100)`) before doing the `//`
  and `%` math instead of just using the dollar amounts directly? What goes wrong if you
  don't?
- The starter logic assumes `leftover` is positive. What would actually happen —
  mechanically, not just "it would break" — if a student's expenses exceeded their
  income? Walk me through what `//` and `%` would return with a negative `leftover`.

## Section 5 — What-If Randomizer

- Why did you pick the specific `random.randint()` ranges you used for car repair,
  medical copay, and gift? What made those numbers "realistic" to you?
- Walk me through `difference = leftover - adjusted_leftover`. Could you have computed
  this without keeping `leftover` around from Section 4? What does that tell you about
  why you needed to preserve that variable instead of overwriting it?

## Design & Judgment Calls (ask at least one)

- Where in this file did you have to keep a variable alive across sections just because
  a later section needed it? Was there a point you almost overwrote something you still
  needed?
- Your written reflection mentions a floating-point rounding artifact
  (e.g. something like `29.999999999999996`). Where did you actually see that in your
  output, and what specifically did you change to clean up the display?
- If I told you that you could use `if` statements, what's the first thing in this
  program you'd change or add? (Listening for: real understanding of where the current
  code is fragile — e.g., the unhandled negative-leftover case — vs. a generic answer.)
- What was the single hardest bug to track down in this lab, and how did you find it?

---

### Quick pass/fail signal for the TA

A student who understands their own code should be able to:
1. Point to any line and say what it computes and why it's needed later, without
   re-reading it silently first.
2. Explain `//` vs `%` in Section 4 using their own numbers, not a textbook definition.
3. Name at least one specific design choice (compound operators, cents conversion,
   randint ranges) and give a reason for it beyond "that's what the instructions said."

If a student can't do #1 for their own variables, that's worth flagging regardless of
whether the output is correct.
