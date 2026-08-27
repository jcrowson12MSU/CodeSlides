"""Lab Idea 5: Game Character Sheet Generator -- reference solution.

Uses only skills taught in Chapter 1 (input/output, variables, print
formatting, strings, int/float) and Chapter 2 (assignment, identifiers,
type conversion, arithmetic + precedence, compound operators, // and %,
import, the math module, the random module). No def, no if, no loops,
no string methods, no format-spec alignment -- only what the two decks
actually demonstrate.
"""

import random

# ============================================================
# SECTION 1: Identity
# ============================================================
character_name = input("Character name: ")
character_class = input("Class (e.g. Wizard): ")
starting_gold = int(input("Starting gold: "))

print()
print("=" * 50)
print(f"CHARACTER SHEET: {character_name} the {character_class}")
print("=" * 50)
print()

# ============================================================
# SECTION 2: Random Attributes
# ============================================================
strength_score = random.randint(1, 20)
dexterity_score = random.randint(1, 20)
constitution_score = random.randint(1, 20)
intelligence_score = random.randint(1, 20)
wisdom_score = random.randint(1, 20)
charisma_score = random.randint(1, 20)

strength_mod = (strength_score - 10) // 2
dexterity_mod = (dexterity_score - 10) // 2
constitution_mod = (constitution_score - 10) // 2
intelligence_mod = (intelligence_score - 10) // 2
wisdom_mod = (wisdom_score - 10) // 2
charisma_mod = (charisma_score - 10) // 2

print("--- Attributes ---")
print("Strength:    ", strength_score, " (modifier", strength_mod, ")")
print("Dexterity:   ", dexterity_score, " (modifier", dexterity_mod, ")")
print("Constitution:", constitution_score, " (modifier", constitution_mod, ")")
print("Intelligence:", intelligence_score, " (modifier", intelligence_mod, ")")
print("Wisdom:      ", wisdom_score, " (modifier", wisdom_mod, ")")
print("Charisma:    ", charisma_score, " (modifier", charisma_mod, ")")
print()

# ============================================================
# SECTION 3: Derived Stats
# ============================================================
base_hp = 10  # fixed base HP for the one class being generated
hp_per_con_mod = 3
hit_points = base_hp + (constitution_mod * hp_per_con_mod)

carry_capacity_lbs = strength_score * 15

base_armor_class = 10
armor_class = base_armor_class + dexterity_mod

print("--- Derived Stats ---")
print("Hit Points:    ", hit_points)
print("Carry Capacity:", carry_capacity_lbs, "lbs")
print("Armor Class:   ", armor_class)
print()

# ============================================================
# SECTION 4: Starting Loot Roll
# ============================================================
gold_found = random.randint(5, 100)
rarity_roll = random.random()  # 0.0 <= x < 1.0
rarity_percent = rarity_roll * 100

starting_gold += gold_found  # compound operator, per the lab spec

print("--- Loot ---")
print(f"You found {gold_found} gold in the chest!")
print(f"Item rarity roll: {rarity_roll:.4f} ({rarity_percent:.1f}%)")
print("New gold total:", starting_gold)
print()

# ============================================================
# SECTION 5: Final Character Sheet
# ============================================================
print("=" * 50)
print(character_name, "the", character_class)
print("=" * 50)
print("STR", strength_score, " mod", strength_mod)
print("DEX", dexterity_score, " mod", dexterity_mod)
print("CON", constitution_score, " mod", constitution_mod)
print("INT", intelligence_score, " mod", intelligence_mod)
print("WIS", wisdom_score, " mod", wisdom_mod)
print("CHA", charisma_score, " mod", charisma_mod)
print("-" * 50)
print("HP:", hit_points, "   AC:", armor_class, "   Carry:", carry_capacity_lbs, "lbs")
print("Gold:", starting_gold)
print("=" * 50)
