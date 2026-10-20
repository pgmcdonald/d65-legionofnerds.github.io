"""Staff and classroom figures for closing-dewey-lincolnwood.html.

1. Who worked at Dewey and Lincolnwood (December 2025 staff directory),
   grouped by what closing the building would do to each role.
2. Last year's test: homeroom classes by school, 2025-26 (teachers listed in
   the December 2025 directory) vs 2026-27 (district's fall section list).
3. Receiving schools under the FY28 map: regular classes and average class
   size in next year's grades 1-5, before and after (uses the model in
   build_fy28_class_merge.py, at the contract's class-size goals).

Run: python3 dataanalysis/build_fy28_staffing.py
"""

import collections
import csv
import math
import re
from pathlib import Path

import openpyxl

import build_fy28_class_merge as cm

DATA = Path(__file__).parent / "data"
DIRECTORY = DATA / "staff_directory_20251219.csv"
SECTIONS = DATA / "sy27_fall" / "k5_sections_fy27.xlsx"

HOMEROOM = r"(Kindergarten|[1-5](st|nd|rd|th)( and [1-5](st|nd|rd|th))? Grade) Teacher$"
GROUPS = [
    ("Run the building", r"^(Principal|Assistant Principal|School Administrative Assistant|Health Clerk|Custodian|Library Media Specialist)$"),
    ("Homeroom teachers", HOMEROOM),
    ("Art, music, PE and other specials", r"(Art|Music|Physical Education|Band|Orchestra|Drama|Computer Science) Teacher"),
    ("Special education and student support", r"(IES|Paraprofessional|Speech|Occupational|Social Worker|Psychologist|ESL|Interventionist|Coach|Nurse)"),
    ("Lunch", r"(Lunchroom|Nutrition)"),
    ("Before- and after-school care", r"SACC"),
]
SCHOOL_KEYS = {
    "Dawes": "Dawes", "Dewey": "Dewey", "Foster": "Foster", "Lincoln Elementary": "Lincoln",
    "Lincolnwood": "Lincolnwood", "Oakton": "Oakton", "Orrington": "Orrington", "Walker": "Walker",
    "Washington": "Washington", "Willard": "Willard", "Kingsley": "Kingsley",
    "Bessie Rhodes": "Bessie Rhodes", "King Jr": "King Arts",
}


def school_of(location):
    location = location.replace("Dr Martin Luther King Jr", "King Jr").replace("Lincoln Elementary School", "Lincoln Elementary")
    for key, name in SCHOOL_KEYS.items():
        if key in location:
            return name


def staff_groups(rows):
    print("1. Staff at the two schools, December 2025 directory (shared staff counted at each school)")
    for full in ("Dewey Elementary School", "Lincolnwood Elementary School"):
        counts, shared = collections.Counter(), collections.Counter()
        for r in rows:
            if full not in r["location"]:
                continue
            title = r["title"].strip()
            group = next((g for g, p in GROUPS if re.search(p, title)), "Unclassified")
            counts[group] += 1
            shared[group] += r["location"].strip() != full
        print(f"  {full}: {sum(counts.values())}")
        for g, _ in GROUPS:
            print(f"    {g:42s} {counts[g]:3d}  (shared with other schools: {shared[g]})")


def classes_by_school(rows):
    print("\n2. Homeroom classes by school, 2025-26 directory vs 2026-27 section list")
    before = collections.Counter(school_of(r["location"]) for r in rows if re.search(HOMEROOM, r["title"].strip()))
    sheet = openpyxl.load_workbook(SECTIONS, read_only=True)["Sheet1"]
    after = collections.Counter(school_of(r[0]) for r in list(sheet.iter_rows(values_only=True))[1:] if r[0])
    schools = ["Kingsley", "Bessie Rhodes", "Foster", "Lincolnwood", "Orrington", "Willard", "Lincoln",
               "Dawes", "Oakton", "Washington", "Walker", "Dewey", "King Arts"]
    for s in schools:
        print(f"  {s:14s} {before[s]:3d} -> {after[s]:3d}  ({after[s] - before[s]:+d})")
    print(f"  {'Total':14s} {sum(before[s] for s in schools):3d} -> {sum(after[s] for s in schools):3d}")


def receiving_schools():
    print("\n3. Next year's grades 1-5, regular classes, at the contract's class-size goals")
    students, twi = cm.load()
    goals = cm.GOALS
    plans = [("Dewey", cm.DEWEY_FLOWS, 0.0), ("Lincolnwood", cm.LINCOLNWOOD_FLOWS, cm.LINCOLNWOOD_STEP / 6)]
    tot_students = tot_before = tot_after = 0
    for closing, flows, remove in plans:
        moving = cm.regular(students, twi, closing, remove)
        n_closing = sum(math.ceil(x / cm.PRACTICE) for x in moving)
        tot_students += sum(moving)
        tot_before += n_closing
        print(f"  {closing} closes: {sum(moving):.0f} students in {n_closing} classes (average {sum(moving) / n_closing:.1f})")
        total = sum(flows.values())
        for school, n in flows.items():
            here = cm.regular(students, twi, school)
            incoming = [moving[g] * n / total for g in range(5)]
            b = sum(math.ceil(here[g] / cm.PRACTICE) for g in range(5))
            a = sum(math.ceil((here[g] + incoming[g]) / goals[g]) for g in range(5))
            tot_students += sum(here)
            tot_before += b
            tot_after += a
            print(f"    {school:11s} +{sum(incoming):4.0f} students   classes {b:2d} -> {a:2d}   "
                  f"average {sum(here) / b:4.1f} -> {(sum(here) + sum(incoming)) / a:4.1f}")
    print(f"  All eight schools: classes {tot_before} -> {tot_after}, "
          f"average class {tot_students / tot_before:.1f} -> {tot_students / tot_after:.1f}")


def main():
    rows = list(csv.DictReader(open(DIRECTORY)))
    staff_groups(rows)
    classes_by_school(rows)
    receiving_schools()


if __name__ == "__main__":
    main()
