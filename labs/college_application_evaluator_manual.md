# LAB ACTIVITY: College Application Evaluator

## Lab 2: College Application Evaluator

### Overview

You'll write a single Python script that models how a college might
screen an incoming application: minimum admission requirements,
automatic admission, a tiered academic scholarship, Honors College
eligibility, major-based placement, a leadership award, a
first-generation support program, and in-state/out-of-state tuition
handling.

**Skills this lab is checking:** `input()`, `print()`, output,
`if`/`elif`/`else`, and comparison/boolean expressions.

### Required Sections

Your script must contain **Milestones 1-5**, in order, on one file.

#### Milestone 1 (20 pts): Applicant Information

1) Prompt for:

   - Applicant **name** and **state of residence**.
   - **High school GPA** and **ACT score** (overall).
   - **ACT Math score** and **ACT English score**.
   - **Community service hours** and **number of extracurricular
     activities**.
   - Whether the applicant is a **first-generation college student**
     (`yes`/`no`).
   - **Intended major**.

2) Convert every numeric response to the correct type (`float` for
   GPA, `int` for everything else) at the moment you read it in.

3) Generate output to match the example below, including the
   `Application Results for <name>` header.

#### Milestone 2 (20 pts): Basic Requirements and Admission Decision

1) Check the **GPA requirement**: met if GPA is 2.5 or higher.

2) Check the **ACT requirement**: met if the ACT score is 18 or
   higher.

3) Determine the overall **admission status** — a student is
   `ADMITTED` only if *both* the GPA and ACT requirements are met.

4) Generate output to match the example below.

\newpage

#### Milestone 3 (20 pts): Automatic Admission and Academic Scholarship

1) Determine **automatic admission**: `YES` only if GPA is 3.5 or
   higher *and* ACT is 24 or higher.

2) Determine the applicant's **academic scholarship** using the
   following tiers, checked from highest to lowest so that only the
   *best* tier a student qualifies for is awarded:

   | GPA at least | ACT at least | Scholarship |
   | --- | --- | --- |
   | 3.9 | 32 | $12,000 |
   | 3.7 | 28 | $8,000 |
   | 3.5 | 25 | $5,000 |
   | 3.2 | 22 | $2,000 |
   | (none of the above) | | $0 |

   Start a `scholarship` variable at `0`, and only check a lower tier
   if `scholarship` is still `0` after checking every tier above it.

3) Generate output to match the example below.

#### Milestone 4 (20 pts): Placement and Recognition

1) Determine **Honors College** eligibility: `ELIGIBLE` only if GPA is
   3.7 or higher *and* ACT is 28 or higher.

2) Determine **Engineering placement**, but only print anything for
   this section if the intended major (compared case-insensitively) is
   `"engineering"`: `READY FOR CALCULUS TRACK` if the ACT Math score is
   24 or higher, otherwise `MATH PLACEMENT REQUIRED`.

3) Determine **English placement** for every applicant based on ACT
   English score: `ADVANCED COMPOSITION` (26+), `COMPOSITION I`
   (20-25), or `DEVELOPMENTAL SUPPORT RECOMMENDED` (below 20).

4) Determine the **community leadership award**: `ELIGIBLE` only if
   community service hours are 100 or more *and* the applicant lists 3
   or more extracurricular activities.

5) Determine **first-generation support program** eligibility based
   directly on the applicant's yes/no answer (compared
   case-insensitively).

6) Generate output to match the example below.

\newpage

#### Milestone 5 (20 pts): Tuition and Presidential Scholarship

1) Determine **tuition classification**: `IN-STATE` if the applicant's
   state (compared case-insensitively) is your home state, otherwise
   `OUT-OF-STATE`.

2) For **out-of-state** applicants only, determine **out-of-state
   tuition waiver** eligibility: `ELIGIBLE` only if GPA is 3.5 or
   higher *and* ACT is 26 or higher.

3) Determine eligibility for a **Presidential Scholarship interview**:
   only print an invitation line, and only if GPA is 3.9 or higher
   *and* ACT is 30 or higher *and* community service hours are 50 or
   more. If the applicant doesn't qualify, print nothing for this
   section.

4) Generate output to match the example below.

### Deliverables

Submit all of the following together:

1) **One `.py` file** containing all five sections, including comments
   and blank lines for spacing.
2) Your code should be commented. Not commenting your code will
   result in -10 points. Comment headers should mark each numbered
   requirement (matching Milestones 2-5 above) so a grader can find
   each one quickly.
3) To receive credit for the assignment, you need to complete a check
   off with one of the lab TAs.
   - The TA will ask you questions about your code. If you cannot
     answer the TA's questions, you will not receive credit for the
     assignment. Checkoffs can be attempted multiple times.

### Example Output 1

```text
Applicant name: Taylor Morgan
State of residence: Alabama
High school GPA: 3.95
ACT score: 32
ACT Math score: 30
ACT English score: 27
Community service hours: 120
Number of extracurricular activities: 4
First-generation college student? (yes/no): no
Intended major: Engineering

========================================
College Application Evaluator
========================================

Application Results for Taylor Morgan
----------------------------------------
GPA requirement: MET
ACT requirement: MET
Admission status: ADMITTED
Automatic admission: YES
Academic scholarship: $12000
Honors College: ELIGIBLE
Engineering placement: READY FOR CALCULUS TRACK
English placement: ADVANCED COMPOSITION
Leadership award: ELIGIBLE
First-generation support program: NOT ELIGIBLE
Tuition classification: OUT-OF-STATE
Out-of-state tuition waiver: ELIGIBLE
Presidential Scholarship interview: INVITED

Application evaluation complete.
```

*(The prompts above are shown before the banner only to illustrate
what the program asks for — in your actual program, `print()` the
banner first, then prompt for input, matching the order in Milestone
2.)*

Example 1 is a strong out-of-state applicant, so it shows what
happens when almost every branch's best-case line prints, including
the Presidential Scholarship invitation and a full $12,000 scholarship
award.

### Example Output 2

```text
Applicant name: Priya Nair
State of residence: Mississippi
High school GPA: 3.6
ACT score: 25
ACT Math score: 21
ACT English score: 24
Community service hours: 80
Number of extracurricular activities: 2
First-generation college student? (yes/no): yes
Intended major: Biology

========================================
College Application Evaluator
========================================

Application Results for Priya Nair
----------------------------------------
GPA requirement: MET
ACT requirement: MET
Admission status: ADMITTED
Automatic admission: YES
Academic scholarship: $5000
Honors College: NOT ELIGIBLE
English placement: COMPOSITION I
Leadership award: NOT ELIGIBLE
First-generation support program: ELIGIBLE
Tuition classification: IN-STATE

Application evaluation complete.
```

Example 2 is an in-state, non-Engineering applicant whose GPA and ACT
land in the middle of the scholarship table. Notice two things this
example demonstrates that Example 1 doesn't: the **Engineering
placement** line is completely absent (the major isn't Engineering, so
that section prints nothing), and there's no out-of-state tuition
waiver or Presidential Scholarship line at all, because both of those
sections only ever print for an out-of-state applicant.

### Example Output 3

```text
Applicant name: Devon Marsh
State of residence: Tennessee
High school GPA: 2.0
ACT score: 16
ACT Math score: 18
ACT English score: 17
Community service hours: 20
Number of extracurricular activities: 1
First-generation college student? (yes/no): no
Intended major: Undecided

========================================
College Application Evaluator
========================================

Application Results for Devon Marsh
----------------------------------------
GPA requirement: NOT MET
ACT requirement: NOT MET
Admission status: NOT ADMITTED
Automatic admission: NO
Academic scholarship: $0
Honors College: NOT ELIGIBLE
English placement: DEVELOPMENTAL SUPPORT RECOMMENDED
Leadership award: NOT ELIGIBLE
First-generation support program: NOT ELIGIBLE
Tuition classification: OUT-OF-STATE
Out-of-state tuition waiver: NOT ELIGIBLE

Application evaluation complete.
```

Example 3 is the required "fails the basic requirements" case from the
self-check below. It's also out-of-state, so unlike Example 2, the
out-of-state tuition waiver line *does* print here — just as `NOT
ELIGIBLE`, since the GPA/ACT minimums for the waiver aren't met either.
This is the example to compare your own output against if a section
you expect to see is missing or a section you expect to be silent is
printing anyway.

### self-check

- All 5 Milestones are present, in order, and clearly labeled.
- Every scholarship tier is checked from highest to lowest, and only
  one tier is ever awarded.
- The Engineering placement section prints nothing for a non-Engineering
  major, and the Presidential Scholarship line prints nothing when the
  applicant doesn't qualify.
- You ran the script at least three times with different inputs —
  including once with an applicant who fails the basic GPA/ACT
  requirements — and verified the outputs against Examples 1-3 above.
