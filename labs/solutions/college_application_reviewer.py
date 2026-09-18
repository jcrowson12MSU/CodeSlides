# College Application Reviewer
#
# Sample solution for labs/chapter4-lab-ideas.md.
#
# Rules followed: no loops, no functions, no lists/dicts/tuples/sets.
# Every decision is made with if/elif/else on strings (or, where noted,
# on a length/int derived from a string). Home state for the in-state
# tuition check is Michigan ("MI").

applicant_name = input("Applicant name: ")
state = input("State (2-letter code): ")
intended_major = input("Intended major: ")
gpa_text = input("GPA (format X.XX, e.g. 3.85): ")
test_score_text = input("Test score: ")
essay = input("Short essay (one paragraph, one line): ")
recommendation_text = input("Line from a letter of recommendation: ")
activities = input("Extracurriculars (comma-separated): ")
email = input("Email address: ")
special_program_code = input("Special program code (or leave blank): ")

print()
print("===== Admissions Decision Letter =====")
print("Applicant:", applicant_name)
print()

# --- 1. Name formatting check ---
if "," in applicant_name:
    print("1. Please resubmit your name in 'First Last' format.")
else:
    print("1. Name on file:", applicant_name)

# --- 2. In-state vs. out-of-state ---
if state.upper() == "MI":
    print("2. In-state tuition rate applies.")
else:
    print("2. Out-of-state tuition rate applies.")

# --- 3. Major recognized or "Undeclared" fallback ---
if intended_major.strip() == "":
    print("3. No major entered -- you will start as Undeclared.")
else:
    print("3. Intended major on file:", intended_major)

# --- 4. STEM vs. non-STEM welcome message ---
print("4. Welcome to the university!")
major_lower = intended_major.lower()
if "computer" in major_lower:
    print("4. Welcome to the College of Engineering and Computing!")
if "engineer" in major_lower:
    print("4. Welcome to the College of Engineering and Computing!")
if "math" in major_lower:
    print("4. Welcome to the College of Natural Science!")
if "bio" in major_lower:
    print("4. Welcome to the College of Natural Science!")

# --- 5. GPA band (string comparison, no float conversion) ---
if gpa_text >= "3.9":
    gpa_band = "Highest Honors"
elif gpa_text >= "3.5":
    gpa_band = "Honors"
elif gpa_text >= "2.0":
    gpa_band = "Standard"
else:
    gpa_band = "Needs Review"
print("5. GPA band:", gpa_band)

# --- 6. Test score sanity check ---
if not test_score_text.isdigit():
    print("6. Test score must be numeric -- skipping test score review.")
    test_score_ok = False
else:
    test_score_ok = True
    test_score = int(test_score_text)
    print("6. Test score on file:", test_score)

# --- 7. Essay length gate ---
if len(essay) < 50:
    print("7. Your essay seems short -- consider expanding it.")
else:
    print("7. Essay length is sufficient.")

# --- 8. Recommendation sentiment keyword check ---
recommendation_lower = recommendation_text.lower()
flagged_recommendation = False
if "exceptional" in recommendation_lower:
    flagged_recommendation = True
if "outstanding" in recommendation_lower:
    flagged_recommendation = True
if "one of the best" in recommendation_lower:
    flagged_recommendation = True

if flagged_recommendation:
    print("8. Recommendation flagged for scholarship review.")
else:
    print("8. Recommendation on file, no special flag.")

# --- 9. Extracurricular count via .count() ---
activity_count = activities.count(",")
if activity_count == 0:
    print("9. Consider listing at least one activity.")
elif activity_count == 1:
    print("9. Nice start -- consider getting involved further.")
else:
    print("9. Well-rounded applicant.")

# --- 10. Email format check ---
if "@" not in email or (not email.endswith(".com") and not email.endswith(".edu") and not email.endswith(".org")):
    print("10. Email address looks malformed and won't be used for correspondence.")
else:
    print("10. Email on file:", email)

# --- 11. Optional scholarship code, nested if ---
if special_program_code.strip() != "":
    if special_program_code == "FIRSTGEN":
        print("11. Flagged for First-Generation Student scholarship review.")
    elif special_program_code == "VETERAN":
        print("11. Flagged for Veteran scholarship review.")
    elif special_program_code == "LEGACY":
        print("11. Flagged for Legacy scholarship review.")
    else:
        print("11. Unrecognized program code -- no scholarship review triggered.")
else:
    print("11. No special program code entered.")

# --- 12. Overall decision line combining multiple conditions ---
honors_or_above = False
if gpa_band == "Highest Honors":
    honors_or_above = True
if gpa_band == "Honors":
    honors_or_above = True

if honors_or_above and flagged_recommendation:
    decision = "Admit with Distinction"
elif honors_or_above or flagged_recommendation:
    decision = "Admit"
else:
    decision = "Refer to Committee"

print()
print("12. Final decision:", decision)
print("=======================================")
