#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent line-by-line verifier for the v23 1977-1979 action register.

This script shares no code with the builder. It re-opens the committed official
Drugs@FDA extracts, re-reads the exact line number each published row cites and
re-parses every field from that line. If a published cell cannot be reproduced
from the cited source line, the check fails.

Checks performed
----------------
1. SHA-256 of every official input still equals the runner manifest value.
2. Every ``pre1980_1977_1979_original_actions.csv`` row reproduces from its
   cited line: ApplNo, submission type/number, class-code id, review priority,
   status, date.
3. Every ``pre1980_1977_1979_submission_actions.csv`` row reproduces the same
   way, and its ``is_original_approval`` flag agrees with the original register.
4. Every document row reproduces from ``ApplicationDocs_appl_window.txt``.
5. Brand/holder cells must exist verbatim in the official Products /
   Applications extracts - a name that is not in an official file fails.
6. The class split is exactly 170 / 479 / 79 and the tracked set equals the
   v20 audit's 170 applications (no silent addition or omission).
7. Every aggregate in ``pre1980_1977_1979_year_analysis.csv`` is recomputed.
8. ``pre1980_fda_decisions.csv`` is unchanged (173 rows, no Selacryn, no 012043).
9. No likelihood / probability column exists in any v23 output.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DBDIR = DATA / "raw" / "drugsatfda_data_files_2026_09"

errors: list[str] = []
checked = 0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(name: str) -> list[dict]:
    with (DATA / name).open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def load_lines(path: Path) -> list[str]:
    """1-indexed: index 0 is the header, so lines[n-1] is source line n."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        return [ln.rstrip("\n").rstrip("\r") for ln in fh]


def col_index(header: list[str], name: str) -> int:
    for i, h in enumerate(header):
        if h.strip().lower() == name.lower():
            return i
    raise KeyError(name)


# ---------------------------------------------------------------- integrity
manifest = json.loads((DBDIR / "manifest.json").read_text(encoding="utf-8"))
recorded = {e["out"]: e for e in manifest.get("requests", []) if e.get("out")}
for fname in ("Submissions_1965_1979.txt", "Applications_all_types.txt",
              "Products_appl_window.txt", "ApplicationDocs_appl_window.txt",
              "SubmissionClass_Lookup.txt"):
    got = sha256_file(DBDIR / fname)
    want = recorded[fname]["out_sha256"]
    if got != want:
        errors.append(f"{fname}: SHA-256 mismatch vs manifest")

subs_lines = load_lines(DBDIR / "Submissions_1965_1979.txt")
subs_header = subs_lines[0].split("\t")
SIDX = {c: i for i, c in enumerate(subs_header)}
prod_lines = load_lines(DBDIR / "Products_appl_window.txt")
PH = {c: i for i, c in enumerate(prod_lines[0].split("\t"))}
app_lines = load_lines(DBDIR / "Applications_all_types.txt")
AH = {c: i for i, c in enumerate(app_lines[0].split("\t"))}
doc_lines = load_lines(DBDIR / "ApplicationDocs_appl_window.txt")
DH = {c: i for i, c in enumerate(doc_lines[0].split("\t"))}

brand_pool = set()
ingredient_pool = set()
strength_pool = set()
for ln in prod_lines[1:]:
    c = ln.split("\t")
    brand_pool.add(c[PH["DrugName"]].strip())
    ingredient_pool.add(c[PH["ActiveIngredient"]].strip())
    strength_pool.add(c[PH["Strength"]].strip())
holder_pool = {ln.split("\t")[AH["SponsorName"]].strip() for ln in app_lines[1:]}


def iso(v: str) -> str:
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", (v or "").strip())
    return m.group(0) if m else ""


# ------------------------------------------------- originals reproduce by line
originals = read_csv("pre1980_1977_1979_original_actions.csv")
if len(originals) != 728:
    errors.append(f"original_actions: {len(originals)} rows, expected 728")
seen_lines: set[int] = set()
class_counts: dict[str, int] = {}
for r in originals:
    checked += 1
    n = int(r["evidence_source_line"])
    if n in seen_lines:
        errors.append(f"original_actions:{r['action_id']}: source line {n} reused")
    seen_lines.add(n)
    if n < 2 or n > len(subs_lines):
        errors.append(f"original_actions:{r['action_id']}: line {n} outside the file")
        continue
    c = subs_lines[n - 1].split("\t")
    for field, idx in (("appl_no", SIDX["ApplNo"]), ("submission_type", SIDX["SubmissionType"]),
                       ("submission_no", SIDX["SubmissionNo"]),
                       ("submission_class_code_id", SIDX["SubmissionClassCodeID"]),
                       ("submission_status", SIDX["SubmissionStatus"]),
                       ("review_priority", SIDX["ReviewPriority"])):
        if c[idx].strip() != r[field].strip():
            errors.append(f"original_actions:{r['action_id']}: {field} {r[field]!r} != "
                          f"source line {n} {c[idx].strip()!r}")
    if iso(c[SIDX["SubmissionStatusDate"]]) != r["action_date"]:
        errors.append(f"original_actions:{r['action_id']}: date {r['action_date']} != source line {n}")
    class_counts[r["action_class"]] = class_counts.get(r["action_class"], 0) + 1
    if r["first_product_brand"] and r["first_product_brand"] not in brand_pool:
        errors.append(f"original_actions:{r['action_id']}: brand {r['first_product_brand']!r} "
                      f"is in no official Products row")
    if r["holder_drugsatfda_verbatim"] and r["holder_drugsatfda_verbatim"] not in holder_pool:
        errors.append(f"original_actions:{r['action_id']}: holder "
                      f"{r['holder_drugsatfda_verbatim']!r} is in no official Applications row")
    if r["first_product_strength"] and r["first_product_strength"] not in strength_pool:
        errors.append(f"original_actions:{r['action_id']}: strength cell not in the official "
                      f"Products extract")
    if r["first_product_ingredients"] and r["submission_class_code"] in ("TYPE 1", "TYPE 1/4"):
        if r["first_product_ingredients"] not in ingredient_pool:
            errors.append(f"original_actions:{r['action_id']}: ingredient string not in the "
                          f"official Products extract")

want_classes = {"TRACKED_NDA_ORIGINAL": 170, "ANDA_ORIGINAL_EXCLUDED": 479, "KIND_UNRESOLVED": 79}
if class_counts != want_classes:
    errors.append(f"original_actions: class split {class_counts} != {want_classes}")

audit = read_csv("pre1980_originals_audit_1977_1979.csv")
audit_appls = {r["application_number"].replace("NDA", "").replace("BLA", "").lstrip("0").zfill(6)
               for r in audit}
tracked_appls = {r["appl_no"] for r in originals if r["action_class"] == "TRACKED_NDA_ORIGINAL"}
if audit_appls != tracked_appls:
    errors.append(f"original_actions: tracked set differs from the v20 audit by "
                  f"{sorted(audit_appls ^ tracked_appls)[:6]}")
cross = [r for r in read_csv("pre1980_full_db_crosscheck_1977_1979.csv") if r.get("appl_no")]
cross_appls = {r["appl_no"] for r in cross}
unres_appls = {r["appl_no"] for r in originals if r["action_class"] == "KIND_UNRESOLVED"}
if cross_appls != unres_appls:
    errors.append(f"original_actions: KIND_UNRESOLVED set differs from the v20.1 cross-check by "
                  f"{sorted(cross_appls ^ unres_appls)[:6]}")

# ------------------------------------------------- submissions reproduce by line
subs_rows = read_csv("pre1980_1977_1979_submission_actions.csv")
if len(subs_rows) != 5483:
    errors.append(f"submission_actions: {len(subs_rows)} rows, expected 5483")
orig_keys = {(r["appl_no"], r["action_date"], r["submission_no"]) for r in originals}
sub_lines_seen: set[int] = set()
per_year: dict[str, int] = {}
for r in subs_rows:
    checked += 1
    n = int(r["evidence_source_line"])
    if n in sub_lines_seen:
        errors.append(f"submission_actions:{r['submission_action_id']}: line {n} reused")
    sub_lines_seen.add(n)
    c = subs_lines[n - 1].split("\t")
    for field, idx in (("appl_no", SIDX["ApplNo"]), ("submission_type", SIDX["SubmissionType"]),
                       ("submission_no", SIDX["SubmissionNo"]),
                       ("submission_class_code_id", SIDX["SubmissionClassCodeID"]),
                       ("submission_status", SIDX["SubmissionStatus"]),
                       ("review_priority", SIDX["ReviewPriority"])):
        if c[idx].strip() != r[field].strip():
            errors.append(f"submission_actions:{r['submission_action_id']}: {field} "
                          f"{r[field]!r} != source line {n} {c[idx].strip()!r}")
    if iso(c[SIDX["SubmissionStatusDate"]]) != r["action_date"]:
        errors.append(f"submission_actions:{r['submission_action_id']}: date mismatch at line {n}")
    if c[SIDX["SubmissionStatusDate"]].strip() != r["action_date_verbatim"]:
        errors.append(f"submission_actions:{r['submission_action_id']}: verbatim date mismatch")
    key = (r["appl_no"], r["action_date"], r["submission_no"])
    if (key in orig_keys) != (r["is_original_approval"] == "TRUE"):
        errors.append(f"submission_actions:{r['submission_action_id']}: is_original_approval flag "
                      f"disagrees with the original register")
    per_year[r["year"]] = per_year.get(r["year"], 0) + 1
if per_year != {"1977": 1489, "1978": 2061, "1979": 1933}:
    errors.append(f"submission_actions: per-year counts {per_year} drifted")
if len(sub_lines_seen) != 5483:
    errors.append("submission_actions: every 1977-1979 source line must appear exactly once")

# --------------------------------------------------- documents reproduce by line
doc_rows = read_csv("pre1980_1977_1979_application_docs.csv")
doc_lines_seen: set[int] = set()
register_appls = {r["appl_no"] for r in originals}
for r in doc_rows:
    checked += 1
    n = int(r["evidence_source_line"])
    if n in doc_lines_seen:
        errors.append(f"docs:{r['doc_row_id']}: line {n} reused")
    doc_lines_seen.add(n)
    c = doc_lines[n - 1].split("\t")
    if c[DH["ApplNo"]].strip() != r["appl_no"]:
        errors.append(f"docs:{r['doc_row_id']}: appl mismatch at line {n}")
    if c[DH["ApplicationDocsURL"]].strip() != r["doc_url"]:
        errors.append(f"docs:{r['doc_row_id']}: url mismatch at line {n}")
    if iso(c[DH["ApplicationDocsDate"]]) != r["doc_date"]:
        errors.append(f"docs:{r['doc_row_id']}: date mismatch at line {n}")
    if r["appl_no"] not in register_appls:
        errors.append(f"docs:{r['doc_row_id']}: application is not in the register")
    if r["doc_type_label_basis"] != "INFERRED_FROM_OFFICIAL_URL_PATH":
        errors.append(f"docs:{r['doc_row_id']}: inferred label must be flagged as inferred")

# ------------------------------------------------ aggregates recomputed exactly
analysis = read_csv("pre1980_1977_1979_year_analysis.csv")
if len(analysis) != 3:
    errors.append(f"year_analysis: {len(analysis)} rows, expected 3")
for a in analysis:
    y = a["year"]
    orig = [r for r in originals if r["year"] == y]
    subs = [r for r in subs_rows if r["year"] == y]
    tracked = [r for r in orig if r["action_class"] == "TRACKED_NDA_ORIGINAL"]
    nme = [r for r in tracked if r["nme_comparable"] == "TRUE"]
    suppl = [r for r in subs if r["submission_type"] == "SUPPL"]
    recomputed = {
        "all_original_approval_actions": len(orig),
        "tracked_nda_bla_originals": len(tracked),
        "anda_originals_excluded_from_nme_basis": len([r for r in orig if r["action_class"] == "ANDA_ORIGINAL_EXCLUDED"]),
        "kind_unresolved_originals": len([r for r in orig if r["action_class"] == "KIND_UNRESOLVED"]),
        "total_ap_actions_in_year": len(subs),
        "supplement_actions_in_year": len(suppl),
        "efficacy_supplement_actions": len([r for r in suppl if r["submission_class_code"] == "EFFICACY"]),
        "labeling_supplement_actions": len([r for r in suppl if r["submission_class_code"] == "LABELING"]),
        "cmc_supplement_actions": len([r for r in suppl if r["submission_class_code"] == "MANUF (CMC)"]),
        "nme_comparable_tracked_rows": len(nme),
        "tracked_priority_review_originals": len([r for r in tracked if r["review_priority"] == "PRIORITY"]),
        "tracked_standard_review_originals": len([r for r in tracked if r["review_priority"] == "STANDARD"]),
        "tracked_blank_priority_originals": len([r for r in tracked if not r["review_priority"]]),
        "originals_with_blank_class_code_id": len([r for r in orig if not r["submission_class_code_id"]]),
        "fr_safety_determination_marker_rows": len([r for r in orig if r["fr_safety_determination_marker"] == "TRUE"]),
        "fr_safety_determination_marker_applications": len({r["appl_no"] for r in orig
                                                             if r["fr_safety_determination_marker"] == "TRUE"}),
        "fr_safety_determination_marker_products": sum(int(r["products_with_fr_marker"]) for r in orig),
        "official_doc_rows_for_this_years_applications": len([d for d in doc_rows
                                                              if d["appl_no"] in {r["appl_no"] for r in orig}]),
    }
    for k, v in recomputed.items():
        if str(a[k]) != str(v):
            errors.append(f"year_analysis:{y}: {k} published {a[k]!r} != recomputed {v}")
    checked += len(recomputed)
    if int(a["nme_comparable_tracked_rows"]) - int(a["nme_comparable_delta_vs_official"]) != int(a["official_nmes_approved"]):
        errors.append(f"year_analysis:{y}: NME delta arithmetic does not close "
                      f"({a['nme_comparable_tracked_rows']} - {a['nme_comparable_delta_vs_official']} "
                      f"!= {a['official_nmes_approved']})")
    want_unres = len([r for r in originals if r["year"] == y
                      and r["action_class"] == "KIND_UNRESOLVED"
                      and r["nme_comparable"].startswith("TRUE")])
    if str(a["nme_comparable_unresolved_rows"]) != str(want_unres):
        errors.append(f"year_analysis:{y}: unresolved NME-comparable count "
                      f"{a['nme_comparable_unresolved_rows']} != recomputed {want_unres}")

# --------------------------------------------------- decision table untouched
decisions = read_csv("pre1980_fda_decisions.csv")
if len(decisions) != 173:
    errors.append(f"pre1980_fda_decisions.csv: {len(decisions)} rows, expected 173 (v23 must not write it)")
blob = " ".join(json.dumps(r) for r in decisions).upper()
for needle in ("SELACRYN", "TICRYNAFEN", "018103", "012043"):
    if needle in blob:
        errors.append(f"pre1980_fda_decisions.csv: {needle} present - a candidate was promoted to a row")

# ------------------------------------------------------- no likelihood anywhere
for name in ("pre1980_1977_1979_original_actions.csv", "pre1980_1977_1979_submission_actions.csv",
             "pre1980_1977_1979_application_docs.csv", "pre1980_1977_1979_year_analysis.csv"):
    cols = " ".join(read_csv(name)[0].keys()).lower()
    for bad in ("likelihood", "probability", "p_approval", "odds"):
        if bad in cols:
            errors.append(f"{name}: contains a {bad!r} column")

print(f"v23 line-by-line verification: {checked} checks, "
      f"{len(errors)} error(s); classes {class_counts}")
for e in errors[:25]:
    print("ERROR", e)
sys.exit(1 if errors else 0)
