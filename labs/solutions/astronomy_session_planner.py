"""Lab Idea 6: Backyard Astronomy Session Planner -- reference solution.

Uses only skills taught in Chapter 1 (input/output, variables, print
formatting, strings, int/float) and Chapter 2 (assignment, type
conversion, arithmetic + precedence, compound operators, // and %,
import, the math module, the random module). No def, no if, no loops.
random.uniform() is not taught in either deck, so the "seeing" quality
roll uses random.randint() instead, exactly as the lab spec allows.
"""

import math
import random

# ============================================================
# SECTION 1: Location and Time
# ============================================================
latitude = float(input("Approximate latitude (e.g. 33.4): "))
session_month = int(input("Month (1-12): "))
session_day = int(input("Day of month: "))

print()
print("=" * 50)
print(f"OBSERVING SESSION PLAN -- {session_month}/{session_day}")
print("=" * 50)
print(f"Latitude: {latitude} degrees")
print()

# ============================================================
# SECTION 2: Telescope Math
# ============================================================
aperture_mm = float(input("Telescope aperture (mm): "))
telescope_focal_length_mm = float(input("Telescope focal length (mm): "))
eyepiece_focal_length_mm = 25.0  # fixed, given by the lab instructions

focal_ratio = telescope_focal_length_mm / aperture_mm
magnification = telescope_focal_length_mm / eyepiece_focal_length_mm

# Dawes limit (arcseconds) = 116 / aperture_in_mm
resolving_power_arcsec = 116 / aperture_mm

print("--- Telescope ---")
print(f"Focal ratio (f/{focal_ratio:.1f})")
print(f"Magnification: {magnification:.1f}x (with a {eyepiece_focal_length_mm:.0f}mm eyepiece)")
print(f"Resolving power (Dawes limit): {resolving_power_arcsec:.2f} arcseconds")
print()

# ============================================================
# SECTION 3: Weather Roll
# ============================================================
cloud_cover_percent = random.randint(0, 100)
seeing_quality = random.randint(1, 5)  # 1 = poor, 5 = excellent
temperature_f = random.randint(30, 90)
temperature_c = (temperature_f - 32) * 5 / 9

print("--- Tonight's Simulated Weather ---")
print(f"Cloud cover: {cloud_cover_percent}%")
print(f"Seeing quality (1-5): {seeing_quality}")
print(f"Temperature: {temperature_f} F  ({temperature_c:.1f} C)")
print()

# ============================================================
# SECTION 4: Object Visibility
# ============================================================
# Fixed per-object difficulty rating: higher means harder to see,
# so it's subtracted from the running visibility score.
jupiter_difficulty = 10
orion_nebula_difficulty = 30
saturn_rings_difficulty = 40

jupiter_score = 100
jupiter_score -= cloud_cover_percent
jupiter_score += seeing_quality * 5
jupiter_score -= jupiter_difficulty

orion_nebula_score = 100
orion_nebula_score -= cloud_cover_percent
orion_nebula_score += seeing_quality * 5
orion_nebula_score -= orion_nebula_difficulty

saturn_rings_score = 100
saturn_rings_score -= cloud_cover_percent
saturn_rings_score += seeing_quality * 5
saturn_rings_score -= saturn_rings_difficulty

print("--- Object Visibility Scores ---")
print("Jupiter:          ", jupiter_score)
print("Orion Nebula:      ", orion_nebula_score)
print("Saturn's Rings:    ", saturn_rings_score)
print()

# ============================================================
# SECTION 5: Session Summary
# ============================================================
print("=" * 50)
print("TONIGHT'S OBSERVING PLAN")
print("=" * 50)
print(f"Date: {session_month}/{session_day}    Latitude: {latitude}")
print(f"Focal ratio: f/{focal_ratio:.1f}   Magnification: {magnification:.1f}x")
print(f"Resolving power: {resolving_power_arcsec:.2f} arcseconds")
print(f"Weather: {cloud_cover_percent}% clouds, seeing {seeing_quality}/5, {temperature_f}F / {temperature_c:.1f}C")
print("-" * 50)
print("Jupiter score:       ", jupiter_score)
print("Orion Nebula score:  ", orion_nebula_score)
print("Saturn's Rings score:", saturn_rings_score)
print("=" * 50)
