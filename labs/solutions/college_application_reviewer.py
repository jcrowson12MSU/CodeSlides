# College Application Evaluator

print("========================================")
print("College Application Evaluator")
print("========================================")
print()

# ---------------------------------------------------------
# Get applicant information
# ---------------------------------------------------------

name = input("Applicant name: ")
state = input("State of residence: ")
gpa = float(input("High school GPA: "))
act = int(input("ACT score: "))
math_act = int(input("ACT Math score: "))
english_act = int(input("ACT English score: "))
service_hours = int(input("Community service hours: "))
activities = int(input("Number of extracurricular activities: "))
first_generation = input("First-generation college student? (yes/no): ")
major = input("Intended major: ")

print()
print("Application Results for", name)
print("----------------------------------------")


# ---------------------------------------------------------
# 1. Basic GPA requirement
# ---------------------------------------------------------

if gpa >= 2.5:
    print("GPA requirement: MET")
else:
    print("GPA requirement: NOT MET")


# ---------------------------------------------------------
# 2. Basic ACT requirement
# ---------------------------------------------------------

if act >= 18:
    print("ACT requirement: MET")
else:
    print("ACT requirement: NOT MET")


# ---------------------------------------------------------
# 3. Admission decision
#
# Students need both the minimum GPA and ACT.
# Nested if statements are used instead of "and".
# ---------------------------------------------------------

if gpa >= 2.5:
    if act >= 18:
        print("Admission status: ADMITTED")
    else:
        print("Admission status: NOT ADMITTED")
else:
    print("Admission status: NOT ADMITTED")


# ---------------------------------------------------------
# 4. Automatic admission
#
# Strong applicants can qualify automatically.
# ---------------------------------------------------------

if gpa >= 3.5:
    if act >= 24:
        print("Automatic admission: YES")
    else:
        print("Automatic admission: NO")
else:
    print("Automatic admission: NO")


# ---------------------------------------------------------
# 5. Academic scholarship
#
# Cascade from the highest scholarship downward.
# ---------------------------------------------------------

scholarship = 0

if gpa >= 3.9:
    if act >= 32:
        scholarship = 12000

if scholarship == 0:
    if gpa >= 3.7:
        if act >= 28:
            scholarship = 8000

if scholarship == 0:
    if gpa >= 3.5:
        if act >= 25:
            scholarship = 5000

if scholarship == 0:
    if gpa >= 3.2:
        if act >= 22:
            scholarship = 2000

print("Academic scholarship: $", scholarship, sep="")


# ---------------------------------------------------------
# 6. Honors College eligibility
# ---------------------------------------------------------

if gpa >= 3.7:
    if act >= 28:
        print("Honors College: ELIGIBLE")
    else:
        print("Honors College: NOT ELIGIBLE")
else:
    print("Honors College: NOT ELIGIBLE")


# ---------------------------------------------------------
# 7. Engineering placement
#
# Engineering students need a minimum math ACT.
# ---------------------------------------------------------

if major.lower() == "engineering":
    if math_act >= 24:
        print("Engineering placement: READY FOR CALCULUS TRACK")
    else:
        print("Engineering placement: MATH PLACEMENT REQUIRED")


# ---------------------------------------------------------
# 8. English placement
# ---------------------------------------------------------

if english_act >= 26:
    print("English placement: ADVANCED COMPOSITION")
elif english_act >= 20:
    print("English placement: COMPOSITION I")
else:
    print("English placement: DEVELOPMENTAL SUPPORT RECOMMENDED")


# ---------------------------------------------------------
# 9. Community leadership award
# ---------------------------------------------------------

if service_hours >= 100:
    if activities >= 3:
        print("Leadership award: ELIGIBLE")
    else:
        print("Leadership award: NOT ELIGIBLE")
else:
    print("Leadership award: NOT ELIGIBLE")


# ---------------------------------------------------------
# 10. First-generation student program
# ---------------------------------------------------------

if first_generation.lower() == "yes":
    print("First-generation support program: ELIGIBLE")
else:
    print("First-generation support program: NOT ELIGIBLE")


# ---------------------------------------------------------
# 11. Out-of-state tuition status
# ---------------------------------------------------------

if state.lower() == "mississippi":
    print("Tuition classification: IN-STATE")
else:
    print("Tuition classification: OUT-OF-STATE")


# ---------------------------------------------------------
# 12. Out-of-state tuition scholarship
# ---------------------------------------------------------

if state.lower() != "mississippi":
    if gpa >= 3.5:
        if act >= 26:
            print("Out-of-state tuition waiver: ELIGIBLE")
        else:
            print("Out-of-state tuition waiver: NOT ELIGIBLE")
    else:
        print("Out-of-state tuition waiver: NOT ELIGIBLE")


# ---------------------------------------------------------
# 13. Presidential scholarship interview
# ---------------------------------------------------------

if gpa >= 3.9:
    if act >= 30:
        if service_hours >= 50:
            print("Presidential Scholarship interview: INVITED")


# ---------------------------------------------------------
# Final message
# ---------------------------------------------------------

print()
print("Application evaluation complete.")

