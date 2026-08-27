"""Lab Idea 7: Personal Budget Simulator -- reference solution.

Uses only skills taught in Chapter 1 (input/output, variables, print
formatting, strings, int/float) and Chapter 2 (assignment, type
conversion, arithmetic + precedence, compound operators, // and %,
import, the math module, the random module). No def, no if, no loops.
"""

import random

# ============================================================
# SECTION 1: Income
# ============================================================
hourly_wage = float(input("Hourly wage: $"))
hours_per_week = float(input("Hours worked per week: "))
num_weeks = int(input("Number of weeks in this budgeting period: "))

gross_income = hourly_wage * hours_per_week * num_weeks

print()
print("=" * 50)
print("PERSONAL BUDGET SIMULATOR")
print("=" * 50)
print(f"Gross income for {num_weeks} week(s): ${gross_income:.2f}")
print()

# ============================================================
# SECTION 2: Fixed Expenses
# ============================================================
rent = float(input("Rent (for the period): $"))
utilities_estimate = float(input("Utilities estimate (for the period): $"))
subscriptions_total = float(input("Subscriptions total (for the period): $"))

total_fixed_expenses = 0.0
total_fixed_expenses += rent
total_fixed_expenses += utilities_estimate
total_fixed_expenses += subscriptions_total

print("--- Fixed Expenses ---")
print(f"Rent:          ${rent:.2f}")
print(f"Utilities:     ${utilities_estimate:.2f}")
print(f"Subscriptions: ${subscriptions_total:.2f}")
print(f"Total fixed:   ${total_fixed_expenses:.2f}")
print()

# ============================================================
# SECTION 3: Variable Spending Estimate
# ============================================================
daily_discretionary = float(input("Estimated daily discretionary spending: $"))
num_days = int(input("Number of days in this budgeting period: "))

total_discretionary = daily_discretionary * num_days
discretionary_percent_of_income = (total_discretionary / gross_income) * 100

print("--- Discretionary Spending ---")
print(f"Total discretionary spending: ${total_discretionary:.2f}")
print(f"That's {discretionary_percent_of_income:.1f}% of gross income")
print()

# ============================================================
# SECTION 4: Savings Goal Check
# ============================================================
savings_goal = float(input("Savings goal: $"))

leftover = gross_income - total_fixed_expenses - total_discretionary

# How many FULL periods of saving $leftover happen before the goal
# is crossed, and how much of the *next* period is needed to finish
# crossing it. Example: leftover=$690/period, goal=$500 -> 0 full
# periods, then $500 of the next $690 period reaches the goal, so
# the goal is crossed partway through period 1.
#
# NOTE: this model assumes leftover is positive (income covers
# expenses each period, same as every period). Try running the
# program with expenses that exceed income -- without `if`, this
# section can't detect and warn about that case; it's a good example
# for a written reflection on WHY conditionals will matter next.
leftover_cents = int(leftover * 100)
goal_cents = int(savings_goal * 100)

full_periods_before_goal = goal_cents // leftover_cents
amount_needed_in_next_period_cents = goal_cents % leftover_cents
amount_needed_in_next_period = amount_needed_in_next_period_cents / 100
goal_reached_in_period = full_periods_before_goal + 1

print("--- Savings Goal ---")
print(f"Leftover this period: ${leftover:.2f}")
print(f"Savings goal:          ${savings_goal:.2f}")
print(f"Full periods of saving before the goal is crossed: {full_periods_before_goal}")
print(f"Amount needed from the next period to finish reaching the goal: ${amount_needed_in_next_period:.2f}")
print(f"Goal is crossed during period #{goal_reached_in_period}")
print()

# ============================================================
# SECTION 5: What-If Randomizer
# ============================================================
car_repair = random.randint(50, 800)
medical_copay = random.randint(20, 200)
gift = random.randint(10, 100)

adjusted_leftover = leftover
adjusted_leftover -= car_repair
adjusted_leftover -= medical_copay
adjusted_leftover -= gift

difference = leftover - adjusted_leftover

print("--- What-If: Surprise Expenses ---")
print(f"Car repair:   ${car_repair}")
print(f"Medical copay: ${medical_copay}")
print(f"Gift:         ${gift}")
print(f"Original leftover: ${leftover:.2f}")
print(f"Adjusted leftover: ${adjusted_leftover:.2f}")
print(f"Difference:        ${difference:.2f}")
print("=" * 50)
