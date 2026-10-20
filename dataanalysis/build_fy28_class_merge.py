"""How many classroom teachers closing Dewey and Lincolnwood would save.

Reproduces the class-merge figures on closing-dewey-lincolnwood.html.

Method
------
Next year's grades 1-5 are this fall's K-4. For each grade, the closing
school's regular (non dual-language) students are split across receiving
schools the way the district's FY28 map sends them, added to each receiving
school's regular students, and classes are counted before and after.

* Before: every school at the district's current practice, one class per 24
  students (it matches the FY27 section list in 28 of 30 grades at the five
  schools without dual-language programs).
* After: merged grades at a chosen class size. The teachers' contract
  (DEC 2024-2028, Article 9(A)) sets class-size GOALS of 23 in K-2 and 25 in
  grades 3-5, not hard caps, so the script also tests sizes above the goal.

Dual-language students are assumed evenly spread across K-5 (the dashboard
reports each strand's total, not by grade). Dewey's 102 dual-language
students move to Lincoln as one strand, so those classes carry over and
save nothing. Lincolnwood's 23 STEP students go to Orrington separately.

Flows
-----
Lincolnwood: the district's figures (269 to Willard, 39 to Walker).
Dewey: the district hasn't published its split. These are the LoDN boundary
tool's estimates of where Dewey's students live on the FY28 map (Lincoln
101, range 77-125; Foster 94 = Foster's district projection 447 minus its
Oct 1 enrollment 353; Washington 78; Orrington 41, a Census estimate).
Dewey's regular students are split in the same proportions.

Run: python3 dataanalysis/build_fy28_class_merge.py
"""

import csv
import math
from pathlib import Path

DATA = Path(__file__).parent / "data" / "sy27_fall"

DEWEY_FLOWS = {"Lincoln": 101, "Foster": 94, "Washington": 78, "Orrington": 41}
LINCOLNWOOD_FLOWS = {"Willard": 269, "Walker": 39}
LINCOLNWOOD_STEP = 23
PRACTICE = 24

# Merged-class sizes to test, for next year's grades 1-5.
SCENARIOS = {
    "Contract goals (23 in K-2, 25 in 3-5)": [23, 23, 25, 25, 25],
    "1 over goal (24 / 26)": [24, 24, 26, 26, 26],
    "2 over goal (25 / 27)": [25, 25, 27, 27, 27],
    "26 everywhere": [26] * 5,
    "28 everywhere": [28] * 5,
}
GOALS = [23, 23, 25, 25, 25]


def load():
    students = {}
    with open(DATA / "class_size_detail_by_school.csv") as f:
        for r in csv.DictReader(f):
            students.setdefault(r["school"], {})[int(r["grade"])] = float(r["students"])
    twi = {}
    with open(DATA / "twi_strands.csv") as f:
        for r in csv.DictReader(f):
            twi[r["school"]] = float(r["twi_now"])
    return students, twi


def regular(students, twi, school, remove_per_grade=0.0):
    """This fall's K-4 regular students = next year's grades 1-5."""
    per_grade_twi = twi.get(school, 0.0) / 6
    return [students[school][g] - per_grade_twi - remove_per_grade for g in range(5)]


def classes_saved(students, twi, closing, flows, size, remove_per_grade=0.0):
    moving = regular(students, twi, closing, remove_per_grade)
    total = sum(flows.values())
    saved = over_goal = 0
    for g in range(5):
        closed = math.ceil(moving[g] / PRACTICE)
        added = 0
        for school, n in flows.items():
            here = regular(students, twi, school)[g]
            incoming = moving[g] * n / total
            before = math.ceil(here / PRACTICE)
            after = math.ceil((here + incoming) / size[g])
            added += after - before
            if (here + incoming) / after > GOALS[g]:
                over_goal += after
        saved += closed - added
    return saved, over_goal


def main():
    students, twi = load()
    print(f"{'Merged classes run at':40s} {'Dewey':>6s} {'Lincolnwood':>12s} {'Total':>6s} {'Classes over goal':>18s}")
    for name, size in SCENARIOS.items():
        d, d_over = classes_saved(students, twi, "Dewey", DEWEY_FLOWS, size)
        l, l_over = classes_saved(students, twi, "Lincolnwood", LINCOLNWOOD_FLOWS, size,
                                  remove_per_grade=LINCOLNWOOD_STEP / 6)
        print(f"{name:40s} {d:6d} {l:12d} {d + l:6d} {d_over + l_over:18d}")

    print("\nDewey's count across the uncertain Lincoln/Washington split (contract goals):")
    for lincoln in (77, 89, 101, 113, 125):
        flows = dict(DEWEY_FLOWS, Lincoln=lincoln, Washington=78 + 101 - lincoln)
        d, _ = classes_saved(students, twi, "Dewey", flows, SCENARIOS["Contract goals (23 in K-2, 25 in 3-5)"])
        print(f"  Lincoln {lincoln:3d}, Washington {flows['Washington']:3d}: {d} classes saved")


if __name__ == "__main__":
    main()
