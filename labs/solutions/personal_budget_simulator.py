import random

# SECTION 1: Income
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

# SECTION 2: Fixed Expenses
rent = float(input(f"Rent (the {num_weeks} week period): $"))
utilities_estimate = float(input(f"Utilities estimate (the {num_weeks} week period): $"))
subscriptions_total = float(input(f"Subscriptions total (the {num_weeks} week period): $"))

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

# SECTION 3: Variable Spending Estimate
daily_discretionary = float(input("Estimated daily discretionary spending: $"))

total_discretionary = daily_discretionary * num_weeks * 7
discretionary_percent_of_income = (total_discretionary / gross_income) * 100

print("--- Discretionary Spending ---")
print(f"Total discretionary spending: ${total_discretionary:.2f}")
print(f"That's {discretionary_percent_of_income:.1f}% of gross income")
print()


# SECTION 4: Unexpected Expenses
leftover = gross_income - total_fixed_expenses - total_discretionary
event1_name, event1_cost = input("Unexpected expense name: "), float(input("Unexpected expense cost: $"))
event2_name, event2_cost = input("Unexpected expense name: "), float(input("Unexpected expense cost: $"))
event3_name, event3_cost = input("Unexpected expense name: "), float(input("Unexpected expense cost: $"))

adjusted_leftover = leftover
adjusted_leftover -= event1_cost
adjusted_leftover -= event2_cost
adjusted_leftover -= event3_cost

difference = leftover - adjusted_leftover

print("--- What-If: Surprise Expenses ---")
print(f"{event1_name}:   ${event1_cost:.2f}")
print(f"{event2_name}:   ${event2_cost:.2f}")
print(f"{event3_name}:   ${event3_cost:.2f}")
print(f"Original leftover: ${leftover:.2f}")
print(f"Adjusted leftover: ${adjusted_leftover:.2f}")
print(f"Difference:        ${difference:.2f}")
print("=" * 50)