# Lab: Personal Budget Simulator

## Overview

You'll write a single Python script that models a simple personal budget:
income, fixed expenses, discretionary spending, a savings goal, and a
randomized "what if something unexpected happens" scenario.

**Constraints:** This lab only uses skills from Chapters 1–2. Do **not** use
`def`, `if`, or any loops (`for`/`while`) — everything should run top to
bottom as one straight-line script. If a problem in this lab feels like it
wants an `if` statement, that's intentional — note it in your written
reflection instead of reaching for one.

**Skills this lab is checking:** `input()`/`print()`, string formatting
(f-strings), `int()`/`float()` conversion, arithmetic operators and
precedence, compound operators (`+=`, `-=`), integer division (`//`) and
modulo (`%`), and the `random` module.

## Required Sections

Your script must contain all five sections below, in order, on one file.

### Section 1 — Income

- Prompt for: hourly wage, hours worked per week, and the number of weeks in
  the budgeting period.
- Compute the **gross income** for the whole period from those three values.
- Print a formatted header/banner and the gross income.

### Section 2 — Fixed Expenses

- Prompt for three separate costs, each covering the *entire* budgeting
  period (not weekly or monthly unless that happens to match your period):
  rent, a utilities estimate, and a subscriptions total.
- Add them into a running total using compound operators (`+=`), not a single
  `a + b + c` expression.
- Print each expense and the total.

### Section 3 — Variable Spending Estimate

- Prompt for an estimated **daily** discretionary spending amount.
- Compute total discretionary spending for the budgeting period. Think
  carefully about how to get from "per day" to "per period" — you already
  have the information you need from Section 1, so you shouldn't need to
  ask the user for anything new here.
- Compute what percentage of gross income that spending represents. Watch
  out for integer-division surprises — make sure your math produces a real
  decimal percentage, not a truncated whole number.
- Print the total and the percentage.

### Section 4 — Savings Goal Check

- Prompt for a savings goal amount.
- Compute **leftover** money after fixed and discretionary expenses are
  subtracted from gross income.
- Using `//`, compute how many *whole* budgeting periods it would take to
  reach the savings goal at the current leftover-per-period rate.
- Using `%`, compute how much additional money (beyond those whole periods)
  is still needed in the next, partial period to finish reaching the goal.
- Print the leftover amount, the goal, the number of full periods, and the
  remaining amount needed.
- **Note:** this section's math assumes your leftover amount is positive
  (i.e., your expenses don't exceed your income). You don't need to detect
  or handle a negative leftover — that requires `if`, which is off-limits
  for this lab. Just be aware of it, and write about it in your reflection.

### Section 5 — What-If Randomizer

- Using `random.randint()`, generate three random "surprise expenses": a car
  repair, a medical copay, and a gift. Pick a realistic min/max range for
  each — they shouldn't all use the same range.
- Starting from your leftover amount (from Section 4), subtract all three
  surprise expenses using `-=` to get an **adjusted leftover**.
- Compute the dollar difference between the original leftover and the
  adjusted leftover.
- Print all three random amounts, the original leftover, the adjusted
  leftover, and the difference.

## Formatting requirements

- All dollar amounts should print with exactly two decimal places (e.g.
  `$1234.50`, not `$1234.5` or `$1234.499999999998`).
- Use f-strings for your `print()` calls.
- Include a clear banner/header so the output is easy to read top to bottom.

## Deliverables

Submit all of the following together:

1. **One `.py` file** containing all five sections, roughly 150–250 lines
   including comments and blank lines for spacing.
2. **Output from at least two full runs** with different input values,
   pasted into your submission (not just screenshots — plain text is fine).
3. **A short written reflection** (about half a page) that answers:
   - Point out at least one place in your code where a floating-point
     rounding artifact showed up in a raw calculation (something like
     `29.999999999999996` instead of `30.0`), and explain what you did to
     display it cleanly.
   - Briefly describe what would happen to your Section 4 math if a user's
     expenses exceeded their income (a negative leftover). You don't need to
     fix this — just explain what `//` and `%` would actually produce.

## Before you submit — self-check

- [ ] All five sections are present, in order, and clearly labeled.
- [ ] No `def`, `if`, `for`, or `while` anywhere in the file.
- [ ] Every dollar amount prints with two decimal places.
- [ ] You can explain, out loud, why every variable in your file exists and
      where it gets used later. (Your TA will ask you this at checkoff.)
- [ ] You ran the script at least twice with different inputs and the output
      makes sense both times.
- [ ] Your written reflection is included and answers both required
      questions above.
