#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pathway-consistency labelling pass (NEXT_SESSION v8 item 3).

For every master row whose application number matches a row of FDA's official
CDER Novel Drug Approvals Compilation (media/177921 XLSX, runner-captured with
SHA-256), this script makes data/fda_decisions_master.csv's review_pathway
column consistent with the Compilation's own "Review Designation" (col 18) and
"Accelerated Approval" (col 20) fields:

  1. FILL   - blank review_pathway -> Compilation tokens
              (e.g. "Priority", "Standard", "Priority; Accelerated",
              "Priority; Breakthrough; Accelerated").
  2. APPEND - Compilation "Accelerated Approval = Yes" and pathway lacking the
             Accelerated token -> append "; Accelerated".
  3. NORMALISE - separator/spelling variants are canonicalised without
             changing meaning: "Priority/Accelerated" -> "Priority; Accelerated",
             "Priority Review" -> "Priority", "Accelerated Approval" ->
             "Accelerated", "Priority Review + Accelerated Approval" ->
             "Priority; Accelerated", "Standard/Accelerated" ->
             "Standard; Accelerated".
  4. CONFLICT - where the master pathway (sourced from FDA annual reports)
             contradicts the Compilation Review Designation (Priority vs
             Standard), BOTH official sources are kept and the row is flagged
             notes-only: "PATHWAY_CONFLICT (Compilation Review Designation=...)"
             - never silently overwritten (repo law on source-vs-source
             conflicts).

Decision dates, decision types, year counts and verification statuses do not
change. A full change log with before/after values is written to
data/staging/pathway_labelling_changelog.json; every change is one of the four
documented operations above. Assertions re-check the year pins after the write.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "fda_decisions_master.csv"
COMP_XLSX = ROOT / "data" / "raw" / "probe" / "fda_nme_compilation_1985_2025.xlsx"
CHANGELOG = ROOT / "data" / "staging" / "pathway_labelling_changelog.json"
PROVENANCE = ("pathway labelled 2026-09-18 from FDA CDER Novel Drug Approvals Compilation "
              "(media/177921) Review Designation/Accelerated Approval columns")

PREFIX_RE = re.compile(r"^(NDA|BLA|ANDA|BL|N)")


def digits_of(appl_field):
    m = PREFIX_RE.match(appl_field or "")
    return (appl_field[m.end():] if m else appl_field).lstrip("0").zfill(6)


def appl_number_of(row):
    """Application number exactly as recorded on the master row (no guessing).
    Order: the row's Drugs@FDA/openFDA URL number first (the link the row is
    published with), then the notes. A notes-first order could pick up a
    superseded number kept inside a correction note (found on D911 Perjeta,
    whose notes keep the wrong BL 125405 text before the corrected BLA 125409)."""
    m = (re.search(r"varApplNo=(\d{5,6})", row["source_url_1"])
         or re.search(r"applno(?:%3D|=)(\d{5,6})",
                      row["source_url_1"] + row["source_url_2"], re.I)
         or re.search(r"ApplNo=(\d{5,6})", row["source_url_2"])
         or re.search(r"appl (?:N|BL)[ #]?(\d{5,6})", row["notes"], re.I)
         or re.search(r"(?:NDA|BLA)[ -]?(\d{5,6})", row["notes"][:160]))
    return m.group(1).zfill(6) if m else ""


def load_compilation():
    wb = openpyxl.load_workbook(COMP_XLSX)
    ws = wb.active
    comp = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        for i in (4, 5, 6):
            a = row[i]
            if a not in (None, ""):
                key = str(a).strip().lstrip("0").zfill(6)
                rec = {
                    "review_designation": (row[18] or "").strip(),
                    "accelerated": (row[20] or "").strip(),
                    "breakthrough": (row[21] or "").strip(),
                    "year": str(row[15] or ""),
                }
                if key in comp and comp[key] != rec:
                    print(f"WARN: compilation appl {key} has conflicting rows; keeping first")
                comp.setdefault(key, rec)
    return comp


def canonicalise(pw, rd="", aa="", btd=""):
    """Canonical token list for a pathway, given the master text and (optionally)
    the Compilation fields. Meaning-preserving."""
    if not pw.strip():
        toks = []
        if rd:
            toks.append(rd)
        if aa.lower() == "yes":
            toks.append("Accelerated")
        if btd.lower() == "yes":
            toks.append("Breakthrough")
        return "; ".join(toks)
    t = pw.strip()
    t = t.replace("Priority Review + Accelerated Approval", "Priority; Accelerated")
    t = t.replace("Priority/Accelerated", "Priority; Accelerated")
    t = t.replace("Standard/Accelerated", "Standard; Accelerated")
    t = t.replace("Priority Review", "Priority")
    t = t.replace("Accelerated Approval", "Accelerated")
    t = t.replace("Accelerated approval", "Accelerated")
    t = re.sub(r"\s*;\s*", "; ", t)
    return t


def main():
    comp = load_compilation()
    with MASTER.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    before_years = Counter(r["decision_date"][:4] for r in rows)
    changelog = []
    n_fill = n_append = n_norm = n_conflict = n_unmatched_blank = 0
    for r in rows:
        a = appl_number_of(r)
        c = comp.get(a)
        if not c:
            # No Compilation row: still normalise formatting (meaning-preserving),
            # never fill or append (no official basis).
            old = r["review_pathway"]
            new = canonicalise(old)
            if new != old and old.strip():
                r["review_pathway"] = new
                r["notes"] = (r["notes"] + " | " if r["notes"].strip() else "") + PROVENANCE
                n_norm += 1
                changelog.append({"decision_id": r["decision_id"], "year": r["decision_date"][:4],
                                  "op": "NORMALISE", "old_pathway": old, "new_pathway": new})
            elif not old.strip():
                n_unmatched_blank += 1
            continue
        old = r["review_pathway"]
        ops = []
        if not old.strip():
            new = canonicalise("", c["review_designation"], c["accelerated"], c["breakthrough"])
            if new:
                ops.append("FILL")
        else:
            new = canonicalise(old)
            if (c["accelerated"].lower() == "yes"
                    and "accelerated" not in new.lower()):
                new = f"{new}; Accelerated" if new else "Accelerated"
                ops.append("APPEND")
            if canonicalise(old) != old:
                ops.append("NORMALISE")
        if ops:
            r["review_pathway"] = new
            r["notes"] = (r["notes"] + " | " if r["notes"].strip() else "") + PROVENANCE
            if "FILL" in ops:
                n_fill += 1
            if "APPEND" in ops:
                n_append += 1
            if "NORMALISE" in ops:
                n_norm += 1
            changelog.append({"decision_id": r["decision_id"], "year": r["decision_date"][:4],
                              "op": "+".join(ops), "old_pathway": old, "new_pathway": new})
        # conflict check on the review-speed axis only (AA/BT/FT tokens ignored)
        if old.strip() and c["review_designation"] in ("Priority", "Standard"):
            old_speed = "priority" if "priority" in old.lower() else \
                        "standard" if "standard" in old.lower() else ""
            if old_speed and old_speed != c["review_designation"].lower():
                tag = (f"PATHWAY_CONFLICT (FDA Compilation Review Designation="
                       f"{c['review_designation']}; master pathway said {old_speed.capitalize()} - "
                       f"both FDA sources kept, flagged for review)")
                if tag.split(" (")[0] not in r["notes"]:
                    r["notes"] = (r["notes"] + " | " if r["notes"].strip() else "") + tag
                    n_conflict += 1
                    changelog.append({"decision_id": r["decision_id"], "year": r["decision_date"][:4],
                                      "op": "CONFLICT_FLAG", "old_pathway": old, "new_pathway": new})

    after_years = Counter(r["decision_date"][:4] for r in rows)
    if before_years != after_years:
        print("FATAL: year counts changed", file=sys.stderr)
        return 1
    for dt_, n in before_years.items():
        if sum(1 for r in rows if r["decision_date"][:4] == dt_) != n:
            print("FATAL: row drift", file=sys.stderr)
            return 1

    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    CHANGELOG.write_text(json.dumps({
        "generated": "2026-09-18", "provenance": PROVENANCE,
        "filled": n_fill, "appended_accelerated": n_append,
        "normalised": n_norm, "conflicts_flagged": n_conflict,
        "changes": changelog}, indent=1))

    print(f"pathway pass: {n_fill} filled, {n_append} Accelerated appended, "
          f"{n_norm} normalised, {n_conflict} conflict-flagged (notes-only), "
          f"{n_unmatched_blank} unmatched-blank left blank (no Compilation row)")
    pw = Counter(r["review_pathway"] for r in rows)
    print("top pathway values now:", pw.most_common(10))
    blanks = sum(1 for r in rows if not r["review_pathway"].strip())
    print("blank pathways remaining:", blanks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
