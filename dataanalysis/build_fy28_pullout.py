"""Pull-out service rooms after closing Dewey and Lincolnwood (2027-28).

Reproduces the room-by-room pull-out section of closing-dewey-lincolnwood.html
in Python, so its figures can be checked without a browser, and adds two checks:

1. Sensitivity: how the shortage changes as rooms are shared through the day
   instead of each service having a room all day.
2. Source check: rebuilds each school's IEP and English learner counts from
   data/sy27_fall/school_summary.csv (dashboard snapshot, Sep 25, 2026) and
   reruns the model with them.

Room data (the district/StudioGC "Building Classrooms" sheet, Oct 6, 2026),
enrollment and counts are read from the page itself (the `var D = [...]`
block), so this script and the page always use the same inputs.

Model, per school that stays open
---------------------------------
classes  = for each grade K-5: max(this year's sections,
           ceil((students + arrivals / 6) / class size)), class size 23 in
           K-2 and 25 in grades 3-5 (contract goals, DEC Article 9(A))
spare    = classrooms + kindergarten rooms - classes
has      = small-group rooms + special ed/sensory rooms + spare classrooms
           (if spare < 0, a class takes a small-group room first)
need     = fixed service rooms + ceil(IEP students / IEPs per resource room)
           + ceil(English learners / EL group cap)
EL cap   = 90% of the school's average class, rounded down (Illinois
           23 IAC 228.30(b)(1)); 50 when that rule is switched off, i.e.
           groups scheduled through the day
short    = classrooms short + max(0, need - has) + missing art/music rooms

Run: python3 dataanalysis/build_fy28_pullout.py
"""

import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
PAGE = HERE / "closing-dewey-lincolnwood.html"
SUMMARY = HERE / "data" / "sy27_fall" / "school_summary.csv"

DEFAULT = dict(fixed=3, iep=20, k2=23, g35=25, il=True, use_spare=True, spec=True)

# Each step shares more of the day than the one before.
SENSITIVITY = [
    ("Default: rooms in use all day, art and music expected", {}),
    ("Art and music not counted as a need", dict(spec=False)),
    ("EL groups scheduled through the day", dict(spec=False, il=False)),
    ("Plus lighter rule: 2 fixed rooms, 1 per 30 IEPs", dict(spec=False, il=False, fixed=2, iep=30)),
    ("Plus one shared room for all fixed services", dict(spec=False, il=False, fixed=1, iep=30)),
]


def load_schools(page=PAGE):
    html = page.read_text()
    start = html.index("var D = [") + len("var D = ")
    end = html.index("];", start) + 1
    return json.loads(html[start:end])


def calc(b, o):
    c = {"cls": 0, "kin": 0, "svc": 0, "sg": 0, "spc": 0}
    for r in b["rooms"]:
        c[r[0]] += 1
    classes = sum(
        max(b["sec"][i], math.ceil((b["k5"][i] + b["inc"] / 6) / (o["k2"] if i < 3 else o["g35"])))
        for i in range(6)
    )
    spare = c["cls"] + c["kin"] - classes
    x = c["sg"] + c["svc"] + (spare if spare < 0 else (spare if o["use_spare"] else 0))
    class_short = -x if x < 0 else 0
    have = max(0, x)
    kids = sum(b["k5"]) + b["inc"]
    el_per = math.floor(0.9 * kids / classes + 1e-9) if o["il"] else 50
    need = o["fixed"] + math.ceil(b["iep"] / o["iep"]) + math.ceil(b["el"] / el_per)
    pull_short = max(0, need - have)
    art = sum(1 for r in b["rooms"] if r[0] == "spc" and r[4] == "art")
    music = sum(1 for r in b["rooms"] if r[0] == "spc" and r[4] == "music")
    other = sum(1 for r in b["rooms"] if r[0] == "spc" and r[4] not in ("art", "music"))
    spec_miss = []
    if o["spec"]:
        for name, n in (("art", art), ("music", music)):
            if not n:
                if other:
                    other -= 1
                else:
                    spec_miss.append(name)
    return dict(school=b["s"], spare=spare, sg=c["sg"], svc=c["svc"], have=have, need=need,
                el_per=el_per, spec_miss=spec_miss,
                short=class_short + pull_short + len(spec_miss))


def run(schools, **changes):
    o = dict(DEFAULT, **changes)
    return [calc(b, o) for b in schools if not b["closing"]]


def totals(rows):
    return (sum(r["have"] for r in rows), sum(r["need"] for r in rows),
            sum(r["short"] for r in rows), [r["school"] for r in rows if r["short"]])


def with_summary_counts(schools):
    """Rebuild IEP/EL counts from school_summary.csv: each school's own rate on
    its remaining students, Dewey + Lincolnwood's combined rate on arrivals."""
    s = {r["school"].split(" ")[0]: r for r in csv.DictReader(open(SUMMARY))}
    rate = lambda name, col: float(s[name][col]) / float(s[name]["enrollment"])
    closing = ["Dewey", "Lincolnwood"]
    moving = sum(float(s[n]["enrollment"]) for n in closing)
    in_iep = sum(float(s[n]["iep_students"]) for n in closing) / moving
    in_el = sum(float(s[n]["el_students"]) for n in closing) / moving
    out = []
    for b in schools:
        b = dict(b)
        if not b["closing"]:
            k5 = sum(b["k5"])
            b["iep"] = rate(b["s"], "iep_students") * k5 + in_iep * b["inc"]
            b["el"] = rate(b["s"], "el_students") * k5 + in_el * b["inc"]
        out.append(b)
    return out, in_iep, in_el


def main():
    schools = load_schools()

    rows = run(schools)
    print("1. Default view (as the page opens)")
    print(f"  {'School':11s} {'Spare':>5s} {'SmGrp':>5s} {'SpEd':>4s} {'Has':>4s} {'Need':>4s} {'Art/music missing':>18s} {'Short':>5s}")
    for r in rows:
        print(f"  {r['school']:11s} {r['spare']:5d} {r['sg']:5d} {r['svc']:4d} {r['have']:4d} {r['need']:4d} "
              f"{', '.join(r['spec_miss']):>18s} {r['short']:5d}")
    have, need, short, where = totals(rows)
    print(f"  {'Total':11s} {'':17s} {have:4d} {need:4d} {'':18s} {short:5d}")

    print("\n2. Sensitivity: sharing rooms through the day")
    for label, changes in SENSITIVITY:
        have, need, short, where = totals(run(schools, **changes))
        print(f"  {label:55s} has {have:3d}  need {need:3d}  short {short:3d}  at {len(where)} of 8: {', '.join(where)}")

    print("\n3. Counts rebuilt from data/sy27_fall/school_summary.csv")
    alt, in_iep, in_el = with_summary_counts(schools)
    print(f"  Arriving students: {in_iep:.1%} with IEPs, {in_el:.1%} English learners "
          f"(page uses 17.4% and 8.4%)")
    for a, b in zip(alt, schools):
        if not b["closing"]:
            print(f"  {b['s']:11s} IEP {b['iep']:6.1f} -> {a['iep']:6.1f}   EL {b['el']:6.1f} -> {a['el']:6.1f}")
    for label, changes in SENSITIVITY:
        page_short = totals(run(schools, **changes))[2]
        csv_short = totals(run(alt, **changes))[2]
        print(f"  {label:55s} short {page_short:3d} (page counts)  {csv_short:3d} (csv counts)")


if __name__ == "__main__":
    main()
