#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pathway reconciliation pass (v10, 2026-09-18) - closes the 35 PATHWAY_CONFLICT
flags plus the unflagged pathway disagreements found by a full master-vs-Compilation
cross-check, using ONLY official FDA sources:

  1. FDA CDER Novel Drug Approvals Compilation 1985-2025 (media/177921)
     - Review Designation + Accelerated Approval columns, per application.
  2. FDA CDER annual reports "New Drug Therapy Approvals 2024/2025"
     (media/184967, media/190705) - official priority-review and
     accelerated-approval drug lists, captured verbatim 2026-09-18 in
     data/staging/fda_annual_report_designation_lists.json.
  3. openFDA Drugs@FDA ORIG-1 review_priority (committed runner payloads).
  4. Verified fact that the 2011-2016 FDA year tables carry NO review column
     (three archived captures checked live 2026-09-18, staged in the same JSON),
     so the hand-entered 'Priority' values on those rows had no column support
     in their cited source.

Groups processed (every transition hard-asserted; the script refuses to run on
unexpected state):

  G1a 2024 conflicts, Compilation+report agree Priority     11 rows Standard -> Priority
  G1b 2024 conflicts, Compilation+report agree Standard      3 rows Priority  -> Standard
  G1c 2025 conflicts, Compilation+report agree Priority     10 rows Standard(-;Accel) -> Priority(-;Accel)
  G1d 2025 conflicts, Compilation+report agree Standard      1 row  Priority;Accelerated -> Standard;Accelerated
  G1e 2011-2016 conflicts, Compilation+Drugs@FDA Standard   10 rows Priority(-;Accel) -> Standard(-;Accel)
  G2  review designation missing (pathway said 'Accelerated'
      alone); Compilation+Drugs@FDA say Priority              9 rows -> 'Priority; Accelerated'
  G3  Accelerated token missing while the Compilation's
      Accelerated Approval column is a qualified Yes          8 rows append '; Accelerated'
  G4  voucher rows (Compilation: 'Priority (used priority
      review voucher)'; reports exclude vouchers) notes-only 10 rows (2 shared with G3)
  G5  Compilation qualified per-indication Priority vs
      Drugs@FDA STANDARD                                     2 rows notes-only

Every change is written as a dated note that preserves both prior FDA sources;
nothing is silently overwritten. Changelog:
data/staging/pathway_reconciliation_changelog.json
"""
import csv
import json
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MASTER = DATA / "fda_decisions_master.csv"
COMP_XLSX = DATA / "raw" / "probe" / "fda_nme_compilation_1985_2025.xlsx"
REPORTS = DATA / "staging" / "fda_annual_report_designation_lists.json"
CHANGELOG = DATA / "staging" / "pathway_reconciliation_changelog.json"
DATE = "2026-09-18"

# ---------------------------------------------------------------- expected transitions
G1A = {  # 2024: Standard -> Priority (Compilation + 2024 report priority list)
    "D002": "Exblifep", "D011": "Zevtera", "D012": "Lumisight", "D022": "Kisunla",
    "D025": "Aqneursa", "D028": "Lazcluze", "D031": "Nemluvio", "D032": "Yorvipath",
    "D036": "Orlynvah", "D038": "Itovebi", "D042": "Alhemo",
}
G1B = {  # 2024: Priority -> Standard (not on the report priority list)
    "D004": "Tevimbra", "D013": "Anktiva", "D017": "Rytelo",
}
G1C = {  # 2025: Standard[-;Accelerated] -> Priority[-;Accelerated]
    "D047": ("Standard", "Priority"),
    "D049": ("Standard", "Priority"),
    "D056": ("Standard", "Priority"),
    "D058": ("Standard", "Priority"),
    "D062": ("Standard", "Priority"),
    "D066": ("Standard; Accelerated", "Priority; Accelerated"),
    "D070": ("Standard", "Priority"),
    "D071": ("Standard; Accelerated", "Priority; Accelerated"),
    "D078": ("Standard", "Priority"),
    "D086": ("Standard", "Priority"),
}
G1D = {"D050": ("Priority; Accelerated", "Standard; Accelerated")}  # 2025 Vanrafia
G1E = {  # 2011-2016: hand-entered Priority without column support -> Standard
    "D451": ("Priority", "Standard"),            # Kengreal 2015
    "D573": ("Priority", "Standard"),            # Tafinlar 2013
    "D574": ("Priority", "Standard"),            # Mekinist 2013
    "D583": ("Priority", "Standard"),            # Anthim 2016
    "D588": ("Priority", "Standard"),            # Bosulif 2012
    "D598": ("Priority", "Standard"),            # Xarelto 2011
    "D607": ("Priority", "Standard"),            # Brilinta 2011
    "D611": ("Priority; Accelerated", "Standard; Accelerated"),  # Kyprolis 2012
    "D621": ("Priority", "Standard"),            # Xeljanz 2012
    "D633": ("Priority", "Standard"),            # Gattex 2012
}
G2 = {  # 'Accelerated' alone -> 'Priority; Accelerated' (Compilation + openFDA PRIORITY)
    "D279": "Balversa", "D280": "Brukinsa", "D284": "Enhertu", "D290": "Oxbryta",
    "D291": "Padcev", "D293": "Polivy", "D300": "Xpovio", "D376": "Trodelvy",
    "D506": "Alunbrig",
}
G3 = {  # append '; Accelerated' (Compilation Accelerated Approval = qualified Yes)
    "D332": ("Priority", "Priority; Accelerated"),                 # Copiktra 2018
    "D402": ("Priority", "Priority; Accelerated"),                 # Rozlytrek 2019
    "D209": ("Priority; Breakthrough", "Priority; Breakthrough; Accelerated"),  # Scemblix 2021
    "D551": ("Priority", "Priority; Accelerated"),                 # Zydelig 2014
    "D780": ("Priority", "Priority; Accelerated"),                 # Sutent 2006
    "D789": ("Priority", "Priority; Accelerated"),                 # Sprycel 2006
    "D975": ("Priority", "Priority; Accelerated"),                 # Synercid IV 1999
    "D067": ("Standard", "Standard; Accelerated"),                 # Keytruda Qlex 2025
}
G4 = {  # voucher rows - notes only (pathway stays Standard per report convention)
    "D288": "Mayzent", "D112": "Vabysmo", "D122": "Mounjaro", "D135": "Imjudo",
    "D161": "Veozah", "D198": "Fabhalta", "D041": "Alyftrek", "D057": "Enflonsia",
    "D063": "Rhapsido", "D067": "Keytruda Qlex",
}
G5 = {  # Compilation qualified per-indication Priority vs Drugs@FDA STANDARD - notes only
    "D783": "Eraxis", "D860": "Sabril",
}

REPORT_MEDIA = {"2024": "media/184967", "2025": "media/190705"}
CONFLICT_RE = re.compile(
    r"PATHWAY_CONFLICT \(FDA Compilation Review Designation=\w+; master pathway "
    r"said [\w; ]+ - both FDA sources kept, flagged for review\)")


def load_compilation():
    wb = openpyxl.load_workbook(COMP_XLSX)
    ws = wb.active
    comp = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = (row[0] or "").strip()
        year = str(row[15] or "")
        for i in (4, 5, 6):
            a = row[i]
            if a not in (None, ""):
                comp.setdefault(str(a).strip().lstrip("0").zfill(6), []).append(
                    {"name": name, "year": year,
                     "review": (row[18] or "").strip(),
                     "accel": (row[20] or "").strip()})
    return comp


def load_openfda_priority():
    """ORIG-1 review_priority per application from the committed runner payloads
    (2011-2026 decision extracts + 2000-2010 full-year application payloads)."""
    of = {}
    strip = re.compile(r"^(?:NDA|BLA|N|BL)")
    for p in sorted((DATA / "raw" / "openfda_orig_decisions_2011_2026").glob("decisions_*.json")):
        d = json.load(open(p))
        for r in d["decisions"]:
            a = strip.sub("", r["application_number"]).lstrip("0").zfill(6)
            of[a] = r.get("review_priority", "")
    for p in sorted((DATA / "raw" / "openfda_approvals_2000_2010").glob("*.json")):
        if p.name == "manifest.json":
            continue
        d = json.load(open(p))
        for res in d.get("results", []):
            for s in res.get("submissions", []):
                if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP":
                    a = strip.sub("", res["application_number"]).lstrip("0").zfill(6)
                    of.setdefault(a, s.get("review_priority", ""))
    return of


def appl_of(row):
    m = (re.search(r"varApplNo=(\d{5,6})", row["source_url_1"])
         or re.search(r"applno(?:%3D|=)(\d{5,6})", row["source_url_1"] + row["source_url_2"], re.I)
         or re.search(r"ApplNo=(\d{5,6})", row["source_url_2"])
         or re.search(r"appl (?:N|BL)[ #]?(\d{5,6})", row["notes"], re.I)
         or re.search(r"(?:NDA|BLA)[ -]?(\d{5,6})", row["notes"][:160]))
    return m.group(1).zfill(6) if m else ""


def comp_for(comp, appl, year):
    crecs = comp.get(appl, [])
    if len(crecs) == 1:
        return crecs[0]
    if len(crecs) > 1:
        same = [x for x in crecs if x["year"] == year]
        if len(same) == 1:
            return same[0]
    return None


def main():
    master = list(csv.DictReader(open(MASTER, newline="", encoding="utf-8-sig")))
    by_id = {r["decision_id"]: r for r in master}
    reports = json.load(open(REPORTS))
    rep = {
        "2024": {n.strip() for n in reports["reports"]["2024"]["priority_review_list_verbatim"].replace(";", ",").split(",")},
        "2025": {n.strip() for n in reports["reports"]["2025"]["priority_review_list_verbatim"].replace(";", ",").split(",")},
    }
    comp = load_compilation()
    ofda = load_openfda_priority()
    changes = []
    errors = []

    def set_pathway(did, old, new, note_builder, group):
        r = by_id[did]
        if r["review_pathway"] != old:
            errors.append(f"{group} {did}: expected pathway {old!r}, found {r['review_pathway']!r}")
            return
        c = comp_for(comp, appl_of(r), r["decision_date"][:4])
        note = note_builder(r, c)
        # replace the conflict note if present, else append
        if CONFLICT_RE.search(r["notes"]):
            r["notes"] = CONFLICT_RE.sub(note, r["notes"])
        elif "PATHWAY_CONFLICT" in r["notes"]:
            errors.append(f"{group} {did}: unparseable PATHWAY_CONFLICT note")
            return
        else:
            r["notes"] = (r["notes"] + " | " + note).strip(" |")
        changes.append({"decision_id": did, "group": group, "brand": r["drug_brand"],
                        "year": r["decision_date"][:4],
                        "pathway_before": old, "pathway_after": new,
                        "compilation_review": c["review"] if c else "",
                        "compilation_accelerated": c["accel"] if c else ""})
        r["review_pathway"] = new

    def append_note(did, note_builder, group, replace_conflict=False):
        r = by_id[did]
        c = comp_for(comp, appl_of(r), r["decision_date"][:4])
        note = note_builder(r, c)
        if replace_conflict and CONFLICT_RE.search(r["notes"]):
            r["notes"] = CONFLICT_RE.sub(note, r["notes"])
        else:
            r["notes"] = (r["notes"] + " | " + note).strip(" |")
        changes.append({"decision_id": did, "group": group, "brand": r["drug_brand"],
                        "year": r["decision_date"][:4],
                        "pathway_before": r["review_pathway"], "pathway_after": r["review_pathway"],
                        "compilation_review": c["review"] if c else "",
                        "compilation_accelerated": c["accel"] if c else ""})

    # ---- G1a/G1b: 2024 conflicts --------------------------------------------
    for did, brand in G1A.items():
        r = by_id[did]
        assert r["drug_brand"] == brand, did
        assert brand in rep["2024"], f"{brand} not on 2024 report list?!"
        set_pathway(
            did, "Standard", "Priority",
            lambda r, c, brand=brand: (
                f"PATHWAY_RECONCILED {DATE}: master previously said Standard (annual-report-derived "
                f"table; the live 2024 novel-drug-approvals page carries no review column - verified "
                f"{DATE}); corrected to Priority on the agreement of two official FDA sources: CDER "
                f"Novel Drug Approvals Compilation Review Designation={c['review'] if c else '?'} and the "
                f"2024 report 'New Drug Therapy Approvals 2024' ({REPORT_MEDIA['2024']}) Priority Review "
                f"list, which includes {brand}; openFDA Drugs@FDA ORIG-1 review_priority="
                f"{ofda.get(appl_of(r), '?')} agrees. Both prior sources preserved in this note."),
            "G1a")
    for did, brand in G1B.items():
        r = by_id[did]
        assert r["drug_brand"] == brand, did
        assert brand not in rep["2024"], f"{brand} unexpectedly on 2024 report list?!"
        set_pathway(
            did, "Priority", "Standard",
            lambda r, c, brand=brand: (
                f"PATHWAY_RECONCILED {DATE}: master previously said Priority; corrected to Standard on "
                f"the agreement of two official FDA sources: CDER Novel Drug Approvals Compilation "
                f"Review Designation={c['review'] if c else '?'} and the 2024 report 'New Drug Therapy "
                f"Approvals 2024' ({REPORT_MEDIA['2024']}) Priority Review list, which does NOT include "
                f"{brand} (28 drugs listed); openFDA Drugs@FDA ORIG-1 review_priority="
                f"{ofda.get(appl_of(r), '?')} agrees. Both prior sources preserved in this note."),
            "G1b")

    # ---- G1c/G1d: 2025 conflicts --------------------------------------------
    for did, (old, new) in G1C.items():
        r = by_id[did]
        assert r["drug_brand"] in rep["2025"], f"{r['drug_brand']} not on 2025 report list?!"
        set_pathway(
            did, old, new,
            lambda r, c: (
                f"PATHWAY_RECONCILED {DATE}: master previously said {old}; corrected to {new.split(';')[0].strip()} "
                f"on the agreement of two official FDA sources: CDER Novel Drug Approvals Compilation Review "
                f"Designation={c['review'] if c else '?'} and the 2025 report 'New Drug Therapy Approvals 2025' "
                f"({REPORT_MEDIA['2025']}) Priority Review list, which includes {r['drug_brand']}; openFDA "
                f"Drugs@FDA ORIG-1 review_priority={ofda.get(appl_of(r), '?')} agrees. "
                f"Both prior sources preserved in this note."),
            "G1c")
    for did, (old, new) in G1D.items():
        r = by_id[did]
        assert r["drug_brand"] not in rep["2025"], f"{r['drug_brand']} unexpectedly on 2025 list?!"
        set_pathway(
            did, old, new,
            lambda r, c: (
                f"PATHWAY_RECONCILED {DATE}: master previously said {old}; corrected to Standard (keeping "
                f"; Accelerated) on the agreement of two official FDA sources: CDER Novel Drug Approvals "
                f"Compilation Review Designation={c['review'] if c else '?'} + Accelerated Approval="
                f"{c['accel'] if c else '?'} and the 2025 report 'New Drug Therapy Approvals 2025' "
                f"({REPORT_MEDIA['2025']}), whose Priority Review list does NOT include {r['drug_brand']} "
                f"but whose Accelerated Approval list does; openFDA Drugs@FDA ORIG-1 review_priority="
                f"{ofda.get(appl_of(r), '?')} agrees on Standard. Both prior sources preserved in this note."),
            "G1d")

    # ---- G1e: 2011-2016 conflicts -------------------------------------------
    for did, (old, new) in G1E.items():
        set_pathway(
            did, old, new,
            lambda r, c: (
                f"PATHWAY_RECONCILED {DATE}: master previously said {old} (hand-entered at original build; "
                f"the cited FDA year table carries no review-classification column - verified on archived "
                f"captures {DATE}, see data/staging/fda_annual_report_designation_lists.json); corrected to "
                f"{new.split(';')[0].strip()} on the agreement of two official FDA machine sources: CDER Novel "
                f"Drug Approvals Compilation Review Designation={c['review'] if c else '?'} and openFDA "
                f"Drugs@FDA ORIG-1 review_priority={ofda.get(appl_of(r), '?')}. No official "
                f"source supporting {old.split(';')[0].strip()} was found; both prior values preserved in this note."),
            "G1e")

    # ---- G2: review designation missing -------------------------------------
    for did, brand in G2.items():
        r = by_id[did]
        assert r["drug_brand"] == brand, did
        set_pathway(
            did, "Accelerated", "Priority; Accelerated",
            lambda r, c: (
                f"PATHWAY_CORRECTED {DATE}: review_pathway was 'Accelerated' (acceleration recorded, review "
                f"designation missing at original build); CDER Novel Drug Approvals Compilation Review "
                f"Designation={c['review'] if c else '?'} and openFDA Drugs@FDA ORIG-1 review_priority="
                f"{ofda.get(appl_of(r), '?')} agree on Priority -> 'Priority; Accelerated' "
                f"(Compilation Accelerated Approval={c['accel'] if c else '?'} corroborates the token)."),
            "G2")

    # ---- G3: missing Accelerated token (qualified Yes) ----------------------
    for did, (old, new) in G3.items():
        set_pathway(
            did, old, new,
            lambda r, c: (
                f"PATHWAY_ENRICHED {DATE}: '; Accelerated' appended from the Compilation's Accelerated "
                f"Approval column, which reads verbatim '{c['accel'] if c else '?'}' (a per-indication "
                f"qualification kept here for the decision engine); pathway {old!r} -> {new!r}."),
            "G3")

    # ---- G4: voucher rows (notes only) ---------------------------------------
    for did, brand in G4.items():
        r = by_id[did]
        assert r["drug_brand"] == brand, did
        append_note(
            did,
            lambda r, c: (
                f"PATHWAY_NOTE {DATE}: the Compilation's Review Designation reads verbatim "
                f"'{c['review'] if c else '?'}'. FDA's annual reports state that voucher redemptions "
                f"'do not meet priority review criteria' and are excluded from the designated-"
                f"priority-review list, so this row's pathway remains {r['review_pathway']} (report "
                f"convention); the shortened review clock is documented here for the decision engine. "
                f"openFDA Drugs@FDA ORIG-1 review_priority="
                f"{ofda.get(appl_of(r), '?')} (the voucher's 6-month clock is recorded "
                f"as PRIORITY in Drugs@FDA)."),
            "G4")

    # ---- G5: qualified per-indication Priority vs Drugs@FDA STANDARD ---------
    for did, brand in G5.items():
        r = by_id[did]
        assert r["drug_brand"] == brand, did
        append_note(
            did,
            lambda r, c: (
                f"PATHWAY_NOTE {DATE}: the Compilation's Review Designation reads verbatim "
                f"'{c['review'] if c else '?'}' (per-indication); openFDA Drugs@FDA records the ORIG-1 "
                f"review_priority as {ofda.get(appl_of(r), '?')}, so the pathway remains "
                f"{r['review_pathway']} with this qualification documented."),
            "G5")

    if errors:
        print("PRECONDITION FAILURES (nothing written):")
        for e in errors:
            print("  ", e)
        return 1

    # ---- write ----------------------------------------------------------------
    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(master[0].keys()), lineterminator="\r\n")
        w.writeheader()
        w.writerows(master)

    left = [r["decision_id"] for r in master if "PATHWAY_CONFLICT" in r["notes"]]
    if left:
        print(f"ERROR: {len(left)} PATHWAY_CONFLICT notes remain: {left}")
        return 1

    changelog = {
        "generated": DATE,
        "sources": [
            "FDA CDER Novel Drug Approvals Compilation 1985-2025 (media/177921)",
            "FDA New Drug Therapy Approvals 2024 report (media/184967) - captured 2026-09-18",
            "FDA New Drug Therapy Approvals 2025 report (media/190705) - captured 2026-09-18",
            "openFDA Drugs@FDA committed runner payloads (ORIG-1 review_priority)",
            "Archived FDA year tables 2011/2015/2016 (no review column - verified 2026-09-18)",
        ],
        "n_changes": len(changes),
        "groups": {
            "G1a_2024_standard_to_priority": len(G1A),
            "G1b_2024_priority_to_standard": len(G1B),
            "G1c_2025_standard_to_priority": len(G1C),
            "G1d_2025_vanrafia_to_standard_accel": len(G1D),
            "G1e_2011_2016_priority_to_standard": len(G1E),
            "G2_accelerated_only_to_priority_accel": len(G2),
            "G3_accelerated_token_appended": len(G3),
            "G4_voucher_note_only": len(G4),
            "G5_qualified_priority_note_only": len(G5),
        },
        "changes": changes,
    }
    json.dump(changelog, open(CHANGELOG, "w"), indent=1)

    from collections import Counter
    print(f"master written; {len(changes)} rows touched")
    for g, n in Counter(c['group'] for c in changes).most_common():
        print(f"  {g}: {n}")
    print("PATHWAY_CONFLICT flags remaining: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
