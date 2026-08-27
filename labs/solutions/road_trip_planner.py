"""Lab Idea 4: Road Trip Planner -- reference solution.

Uses only skills taught in Chapter 1 (input/output, variables, print
formatting, strings, int/float) and Chapter 2 (assignment, type
conversion, arithmetic + precedence, compound operators, // and %,
import, the math module, the random module). No def, no if, no loops.
"""

import math
import random

# ============================================================
# SECTION 1: Trip Basics
# ============================================================
start_city = input("Starting city: ")
destination_city = input("Destination city: ")
distance_miles = float(input("Total distance (miles): "))

print()
print("=" * 50)
print(f"ROAD TRIP: {start_city} -> {destination_city}")
print("=" * 50)
print(f"Distance: {distance_miles} miles")
print()

# ============================================================
# SECTION 2: Vehicle and Fuel
# ============================================================
mpg = float(input("Car's fuel efficiency (mpg): "))
price_per_gallon = float(input("Gas price per gallon: $"))

gallons_needed = distance_miles / mpg
fuel_cost = gallons_needed * price_per_gallon

# Practice with // and % on a scaled integer, since gallons_needed
# is rarely a clean whole number on its own.
tenths_of_gallon = int(gallons_needed * 10)
whole_gallons = tenths_of_gallon // 10
leftover_tenths = tenths_of_gallon % 10

print("--- Fuel ---")
print(f"Gallons needed: {gallons_needed:.2f}")
print(f"That's {whole_gallons} whole gallon(s) and {leftover_tenths} tenth(s) of a gallon left over")
print(f"Estimated fuel cost: ${fuel_cost:.2f}")
print()

# ============================================================
# SECTION 3: Time Estimate
# ============================================================
average_speed_mph = float(input("Average driving speed (mph): "))

total_hours = distance_miles / average_speed_mph

# Convert the float hours into whole hours + remaining minutes,
# same pattern as the Ch. 2 minutes-to-hours example.
total_minutes = int(total_hours * 60)
whole_hours = total_minutes // 60
remaining_minutes = total_minutes % 60

print("--- Time ---")
print(f"Estimated driving time: {whole_hours} hour(s), {remaining_minutes} minute(s)")
print()

# ============================================================
# SECTION 4: Pit Stops
# ============================================================
num_stops = random.randint(2, 5)

# Not a loop -- four separately labeled possible stops, each its
# own random.randint() call, matching the lab's straight-line
# constraint.
stop_1_mile = random.randint(1, int(distance_miles))
stop_2_mile = random.randint(1, int(distance_miles))
stop_3_mile = random.randint(1, int(distance_miles))
stop_4_mile = random.randint(1, int(distance_miles))

print("--- Pit Stops ---")
print(f"Planning for {num_stops} rest stop(s) on this trip.")
print(f"Possible stop 1 at mile marker: {stop_1_mile}")
print(f"Possible stop 2 at mile marker: {stop_2_mile}")
print(f"Possible stop 3 at mile marker: {stop_3_mile}")
print(f"Possible stop 4 at mile marker: {stop_4_mile}")
print()

# ============================================================
# SECTION 5: Trip Cost Summary
# ============================================================
# math.ceil rounds the fuel cost up to the nearest dollar, giving
# a "budget with buffer" figure.
fuel_cost_buffer = math.ceil(fuel_cost)

print("=" * 50)
print("TRIP SUMMARY")
print("=" * 50)
print(f"Route:            {start_city} -> {destination_city}")
print(f"Distance:         {distance_miles} miles")
print(f"Driving time:     {whole_hours} hour(s), {remaining_minutes} minute(s)")
print(f"Fuel needed:      {gallons_needed:.2f} gallons")
print(f"Fuel cost:        ${fuel_cost:.2f} (exact)")
print(f"Budget w/ buffer: ${fuel_cost_buffer} (rounded up)")
print(f"Planned stops:    {num_stops}")
print(f"  Stop 1 near mile {stop_1_mile}")
print(f"  Stop 2 near mile {stop_2_mile}")
print(f"  Stop 3 near mile {stop_3_mile}")
print(f"  Stop 4 near mile {stop_4_mile}")
print("=" * 50)
