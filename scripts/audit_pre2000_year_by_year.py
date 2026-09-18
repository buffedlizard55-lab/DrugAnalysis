#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Year-by-year pre-2000 audit (2000 -> 1985, newest first).

For EVERY master row whose decision_date falls in 1985-2000 this script
re-verifies the row against three independent official FDA layers and writes
data/pre2000_year_audit.csv (one row per master decision, links for manual
review on every row) plus data/pre2000_year_summary.csv (per-year roll-up).

v9 (2026-09-18) audited 1996-2000; v10 (2026-09-18) extended the same
three-layer method to 1985-1995, completing the whole pre-2000 era
(492 rows = 204 v9 + 288 v10).

The three layers are:

  L1 FDA official year enumeration
     1998/1999/2000: the contemporaneous CDER "NMEs Approved in <year>"
     tables, captured verbatim from FDA/Wayback into
     data/staging/fda_nme_<year>_verbatim.json (row_count pins: 36/37/27).
     1985-1997: no year table exists (documented; verified for 2011-2016
     family pages too - none carries a review column); FDA's official CDER
     "Novel Drug Approvals Compilation" (media/177921 XLSX, runner-captured
     with SHA-256) is the official enumeration, so L1 == L2 for those years.

  L2 FDA CDER Novel Drug Approvals Compilation 1985-2025
     data/raw/probe/fda_nme_compilation_1985_2025.xlsx - approval date,
     applicant, Review Designation, Accelerated Approval per application.

  L3 openFDA Drugs@FDA (verbatim runner captures, fetch run 13)
     1985-1999: data/raw/openfda_orig_decisions_2011_2026/decisions_<y>.json
     2000:      data/raw/openfda_approvals_2000_2010/2000.json (ORIG/AP rows
                extracted from the full-year application payload)
     compared on: ORIG approval date, sponsor, brand, submission class.

Live spot-checks performed in-session through the page-fetch tool (api.fda.gov)
are staged in data/staging/pre2000_live_checks.json with the exact query URL
and verdict, and merged into the audit output. Nothing is inferred: every
comparison is between committed, hash-manifested captures, and every
disagreement becomes a flag rather than a "fix".

Exit code 1 if any assertion fails (row coverage, year pins).
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MASTER = DATA / "fda_decisions_master.csv"
OUT_AUDIT = DATA / "pre2000_year_audit.csv"
OUT_SUMMARY = DATA / "pre2000_year_summary.csv"
LIVE_CHECKS = DATA / "staging" / "pre2000_live_checks.json"
COMP_XLSX = DATA / "raw" / "probe" / "fda_nme_compilation_1985_2025.xlsx"

# audit order, newest first: the whole pre-2000 era (v9: 2000-1996; v10: +1985-1995)
YEARS = [2000, 1999, 1998, 1997, 1996, 1995, 1994, 1993, 1992, 1991,
         1990, 1989, 1988, 1987, 1986, 1985]
YEARS_WITH_TABLE = {1998, 1999, 2000}
# Official master year pins (every year 1985-2000; from the Compilation import
# pinned in build_backfill_1985_1997_and_cber.py and the v7 1998 import).
YEAR_PINS = {
    2000: 29, 1999: 37, 1998: 36, 1997: 43, 1996: 59,
    1995: 30, 1994: 23, 1993: 27, 1992: 29, 1991: 32,
    1990: 24, 1989: 27, 1988: 20, 1987: 22, 1986: 23, 1985: 31,
}
COMPILATION_URL = "https://www.fda.gov/media/177921/download?attachment"
YEAR_TABLE_CAPTURE = {
    1998: "https://web.archive.org/web/20051016001622/http://www.fda.gov/cder/rdmt/nmecy98.htm",
    1999: "https://web.archive.org/web/20090709174613/http://www.fda.gov/Drugs/DevelopmentApprovalProcess/HowDrugsareDevelopedandApproved/DrugandBiologicApprovalReports/NMEDrugandNewBiologicApprovals/ucm081686.htm",
    2000: "https://web.archive.org/web/20090709174610/http://www.fda.gov/Drugs/DevelopmentApprovalProcess/HowDrugsareDevelopedandApproved/DrugandBiologicApprovalReports/NMEDrugandNewBiologicApprovals/ucm081685.htm",
}

AUDIT_HEADER = [
    "audit_year", "decision_id", "drug_brand", "drug_generic", "company_name",
    "master_decision_date", "application_number",
    "l1_year_table", "l1_table_date", "l1_table_class",
    "l2_compilation_match", "l2_compilation_date", "l2_review_designation",
    "l2_accelerated_approval",
    "l3_openfda_match", "l3_orig_date", "l3_sponsor", "l3_brand",
    "l3_submission_class", "l3_review_priority",
    "date_agreement", "verdict", "live_check", "review_flag",
    "source_year_table_or_compilation", "source_drugsatfda",
    "source_openfda",
]


def read_master_rows():
    with MASTER.open(newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["decision_date"][:4] in
                {str(y) for y in YEARS}]


APPL_RE = re.compile(r"appl (?:N|BL)[ #]?(\d{5,6})", re.I)


def appl_number_of(row):
    """Application number exactly as recorded on the master row (no guessing).
    Order: the row's Drugs@FDA/openFDA URL number first (the link the row is
    published with), then the notes - a notes-first order could pick up a
    superseded number kept inside a correction note (see D911 Perjeta)."""
    m = (re.search(r"varApplNo=(\d{5,6})", row["source_url_1"])
         or re.search(r"applno(?:%3D|=)(\d{5,6})",
                      row["source_url_1"] + row["source_url_2"], re.I)
         or re.search(r"ApplNo=(\d{5,6})", row["source_url_2"])
         or APPL_RE.search(row["notes"])
         or re.search(r"(?:NDA|BLA)[ -]?(\d{5,6})", row["notes"][:160]))
    return m.group(1).zfill(6) if m else ""


def load_compilation():
    """Index the official Compilation XLSX by application number (cols 5-7)
    and by (proprietary name lower, approval-date) as a fallback match."""
    wb = openpyxl.load_workbook(COMP_XLSX)
    ws = wb.active
    by_appl, by_name_date = {}, {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = (row[0] or "").strip()
        applicant = (row[2] or "").strip()
        year = str(row[15] or "")
        d = row[14]
        d_iso = d.date().isoformat() if hasattr(d, "date") else str(d or "")[:10]
        rec = {
            "name": name, "applicant": applicant, "year": year, "date": d_iso,
            "review_designation": (row[18] or "").strip(),
            "accelerated_approval": (row[20] or "").strip(),
            "breakthrough": (row[21] or "").strip(),
            "fast_track": (row[22] or "").strip(),
            "notes": (row[26] or "").strip(),
        }
        for i in (4, 5, 6):
            a = row[i]
            if a not in (None, ""):
                key = str(a).strip().lstrip("0").zfill(6)
                by_appl.setdefault(key, []).append(rec)
        if name:
            by_name_date.setdefault((name.lower(), d_iso), []).append(rec)
    return by_appl, by_name_date


def load_year_tables():
    """Archived FDA year-table rows only: staging rows marked 'Compilation-only'
    were imports (Ontak/Wellferon 1999), not rows of the contemporaneous table,
    so they must not satisfy the L1 layer."""
    tables = {}
    for y in sorted(YEARS_WITH_TABLE):
        p = DATA / "staging" / f"fda_nme_{y}_verbatim.json"
        d = json.load(open(p))
        rows, imported = {}, {}
        for r in d["rows"]:
            a = digits_of(r.get("appl_no") or "")
            if "compilation-only" in (r.get("flag") or "").lower():
                imported[a] = r
            else:
                rows[a] = r
        tables[y] = {"meta": d, "by_appl": rows, "imported": imported}
    return tables


PREFIX_RE = re.compile(r"^(NDA|BLA|ANDA|BL|N)")


def digits_of(appl_field):
    """'NDA020353'/'BL021081'/'020353' -> zero-padded 6-digit numeric key.
    (Regex prefix strip; a naive lstrip('NBDA') mangles BL-prefixed numbers.)"""
    m = PREFIX_RE.match(appl_field or "")
    return (appl_field[m.end():] if m else appl_field).lstrip("0").zfill(6)


def load_openfda():
    """ORIG/AP decision records per year from the committed runner captures."""
    of = {}
    for y in YEARS:
        recs = []
        if y <= 1999:
            p = DATA / "raw" / "openfda_orig_decisions_2011_2026" / f"decisions_{y}.json"
            d = json.load(open(p))
            for r in d["decisions"]:
                recs.append({
                    "appl": digits_of(r["application_number"]),
                    "date": r.get("decision_date", ""),
                    "sponsor": r.get("sponsor_name", ""),
                    "brand": r.get("brand_name_openfda", "") or
                             ((r.get("products") or [{}])[0].get("brand_name") or ""),
                    "class": r.get("submission_class_code", ""),
                    "priority": r.get("review_priority", ""),
                    "url": r.get("source_url_drugsatfda", ""),
                })
        else:  # 2000 payload holds whole applications; extract the ORIG AP in-year
            p = DATA / "raw" / "openfda_approvals_2000_2010" / "2000.json"
            d = json.load(open(p))
            for r in d["results"]:
                for s in r.get("submissions", []):
                    sd = str(s.get("submission_status_date", ""))
                    if (s.get("submission_type") == "ORIG"
                            and s.get("submission_status") == "AP"
                            and sd[:4] == "2000"):
                        brand = ""
                        for pr in r.get("products", []):
                            if pr.get("brand_name"):
                                brand = pr["brand_name"]
                                break
                        recs.append({
                            "appl": digits_of(r["application_number"]),
                            "date": f"{sd[:4]}-{sd[4:6]}-{sd[6:8]}",
                            "sponsor": r.get("sponsor_name", ""),
                            "brand": brand,
                            "class": s.get("submission_class_code", ""),
                            "priority": s.get("review_priority", ""),
                            "url": "https://api.fda.gov/drug/drugsfda.json?search=application_number:"
                                   + r["application_number"],
                        })
                        break
        idx = defaultdict(list)
        for r in recs:
            idx[r["appl"]].append(r)
        of[y] = idx
    return of


def load_live_checks():
    if LIVE_CHECKS.exists():
        d = json.load(open(LIVE_CHECKS))
        checks = {}
        for c in d.get("checks", []):
            c = dict(c)
            c.setdefault("checked_utc", d.get("checked_utc", ""))
            checks[c["application_number"]] = c
        return checks
    return {}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main():
    master = read_master_rows()
    comp_by_appl, comp_by_name_date = load_compilation()
    tables = load_year_tables()
    openfda = load_openfda()
    live = load_live_checks()

    out, errors = [], []
    summary = []
    for y in YEARS:
        ys = str(y)
        rows = [r for r in master if r["decision_date"][:4] == ys]
        stats = Counter()
        for r in sorted(rows, key=lambda x: x["decision_date"]):
            a = appl_number_of(r)
            if not a:
                errors.append(f"{r['decision_id']}: no application number found")
                continue
            rec = {
                "audit_year": ys, "decision_id": r["decision_id"],
                "drug_brand": r["drug_brand"], "drug_generic": r["drug_generic"],
                "company_name": r["company_name"],
                "master_decision_date": r["decision_date"],
                "application_number": ("N" + a if not a.startswith("B") else "BL" + a),
                "l1_year_table": "", "l1_table_date": "", "l1_table_class": "",
                "l2_compilation_match": "", "l2_compilation_date": "",
                "l2_review_designation": "", "l2_accelerated_approval": "",
                "l3_openfda_match": "", "l3_orig_date": "", "l3_sponsor": "",
                "l3_brand": "", "l3_submission_class": "", "l3_review_priority": "",
                "date_agreement": "", "verdict": "", "live_check": "",
                "review_flag": "",
                "source_year_table_or_compilation": "",
                "source_drugsatfda": ("https://www.accessdata.fda.gov/scripts/cder/daf/"
                                      "index.cfm?event=overview.process&varApplNo=" + a),
                "source_openfda": ("https://api.fda.gov/drug/drugsfda.json?search=application_number:"
                                   + ("N" + a if not a.startswith("B") else "BL" + a)),
            }
            flags = []
            dates = {"master": r["decision_date"]}

            # ---- L2 Compilation (all years) --------------------------------
            crecs = comp_by_appl.get(a, [])
            c = None
            if len(crecs) == 1:
                c = crecs[0]; rec["l2_compilation_match"] = "application_number"
            elif len(crecs) > 1:
                same_year = [x for x in crecs if x["year"] == ys]
                if len(same_year) == 1:
                    c = same_year[0]; rec["l2_compilation_match"] = "application_number (year-disambiguated)"
            if c is None:
                alt = comp_by_name_date.get((norm(r["drug_brand"]), r["decision_date"]), [])
                if len(alt) == 1:
                    c = alt[0]; rec["l2_compilation_match"] = "brand+date (appl not in Compilation rows)"
            if c:
                rec["l2_compilation_date"] = c["date"]
                rec["l2_review_designation"] = c["review_designation"]
                rec["l2_accelerated_approval"] = c["accelerated_approval"]
                dates["compilation"] = c["date"]
                if c["date"] != r["decision_date"]:
                    flags.append(f"COMPILATION_DATE_DIFFERS ({c['date']} vs master {r['decision_date']})")
                rec["source_year_table_or_compilation"] = COMPILATION_URL
            else:
                rec["l2_compilation_match"] = "NO_MATCH"
                flags.append("NOT_IN_COMPILATION_BY_APPL_OR_NAME_DATE")
                rec["source_year_table_or_compilation"] = COMPILATION_URL

            # ---- L1 year table (1998-2000) ---------------------------------
            if y in YEARS_WITH_TABLE:
                t = tables[y]["by_appl"].get(a)
                rec["source_year_table_or_compilation"] = YEAR_TABLE_CAPTURE[y]
                if t:
                    rec["l1_year_table"] = "MATCH"
                    rec["l1_table_date"] = t["date"]
                    rec["l1_table_class"] = t["class"]
                    dates["year_table"] = t["date"]
                    if t["date"] != r["decision_date"]:
                        flags.append(f"YEAR_TABLE_DATE_DIFFERS ({t['date']})")
                elif a in tables[y]["imported"]:
                    imp = tables[y]["imported"][a]
                    rec["l1_year_table"] = "NO_MATCH (documented Compilation-only import; not on the archived year table)"
                    flags.append("COMPILATION_ONLY_IMPORT (year-table omission, documented at import)")
                    if imp.get("date") and imp["date"] != r["decision_date"]:
                        flags.append(f"IMPORT_ROW_DATE_DIFFERS ({imp['date']})")
                else:
                    rec["l1_year_table"] = "NO_MATCH_BY_APPL"
                    # a Compilation-matched row absent from the year table is a
                    # documented case (e.g. CBER biologics; flagged on import)
                    if "COMPILATION_ONLY_CBER" in r["notes"] or "COMPILATION_ONLY" in r["notes"]:
                        rec["l1_year_table"] = "NO_MATCH_BY_APPL (Compilation-only row, documented)"
                    else:
                        flags.append("NOT_IN_FDA_YEAR_TABLE")
            else:
                rec["l1_year_table"] = "NO_YEAR_TABLE_EXISTS (documented)"
                if not rec["source_year_table_or_compilation"]:
                    rec["source_year_table_or_compilation"] = COMPILATION_URL

            # ---- L3 openFDA -------------------------------------------------
            o = openfda[y].get(a, [])
            if len(o) == 1:
                o = o[0]
                rec["l3_openfda_match"] = "MATCH"
                rec["l3_orig_date"] = o["date"]
                rec["l3_sponsor"] = o["sponsor"]
                rec["l3_brand"] = o["brand"]
                rec["l3_submission_class"] = o["class"]
                rec["l3_review_priority"] = o["priority"]
                dates["openfda"] = o["date"]
                if o["date"] != r["decision_date"]:
                    flags.append(f"OPENFDA_DATE_DIFFERS ({o['date']})")
            elif len(o) > 1:
                rec["l3_openfda_match"] = "MULTIPLE"
                flags.append("OPENFDA_MULTIPLE_ORIG_IN_YEAR (needs review)")
            else:
                # live check (staged verbatim, 2026-09-18) refines the absence:
                # the application may exist in openFDA without a submissions
                # array (Normiflo NDA020227) or be absent entirely under every
                # plausible stored prefix (all other rows below).
                lc = (live.get("NDA" + a) or live.get("BLA" + a) or live.get("BL" + a)
                       or live.get("N" + a))  # N-prefixed CBER-era PLA numbers
                if lc and lc["result"] == "APPLICATION_PRESENT_NO_SUBMISSIONS":
                    rec["l3_openfda_match"] = "APPLICATION_PRESENT_NO_SUBMISSIONS (live check)"
                    flags.append("NOT_IN_OPENFDA_PAYLOAD - application record exists but carries no "
                                 "submissions array, so the ORIG approval date is not machine-verifiable there")
                elif lc and lc["result"] == "ORIG_DATE_DIFFERS":
                    rec["l3_openfda_match"] = (f"PRESENT_ORIG_DATE_DIFFERS (openFDA ORIG-1 "
                                               f"{lc.get('orig_date', '')}".strip() + ")")
                    flags.append("OPENFDA_ORIG_DATE_DIFFERS - application is indexed but its ORIG-1 "
                                 "approval date differs from the Compilation/master date (documented at "
                                 "import; carried as MISMATCH_DATE in verification_crosscheck.csv; the "
                                 "Compilation date is kept as official)")
                elif lc and lc["result"] == "BRAND_ONLY_UNDER_LATER_LICENCE":
                    rec["l3_openfda_match"] = "NUMBER_NOT_FOUND_BRAND_UNDER_LATER_LICENCE (live check)"
                    flags.append("NOT_IN_OPENFDA_PAYLOAD - application number returns no record and the "
                                 "brand exists only under a later, different licence (CBER-era PLA not "
                                 "transferred to Drugs@FDA); see live-check URL for the exact records")
                elif lc and lc["result"] == "NOT_FOUND":
                    rec["l3_openfda_match"] = "NOT_IN_OPENFDA"
                    flags.append("NOT_IN_OPENFDA_PAYLOAD (live check by application number "
                                 "and brand both return no record; FDA year table + Compilation remain the sources)")
                elif lc:
                    rec["l3_openfda_match"] = f"NOT_IN_YEAR_PAYLOAD ({lc['result']})"
                    flags.append("NOT_IN_YEAR_PAYLOAD - live check verdict "
                                 f"{lc['result']} (see {lc['query_url']}); see note")
                else:
                    rec["l3_openfda_match"] = "NOT_IN_OPENFDA"
                    flags.append("NOT_IN_OPENFDA_YEAR_PAYLOAD (absent from the committed ORIG/AP "
                                 "runner capture for the year; not yet re-checked live - see "
                                 "data/staging/pre2000_live_checks.json)")

            # ---- date agreement + verdict -----------------------------------
            vals = set(dates.values())
            rec["date_agreement"] = "ALL_AGREE" if len(vals) == 1 else \
                "AGREE_EXCEPT_OPENFDA" if len(vals) > 1 and len(
                    {v for k, v in dates.items() if k != "openfda"}) == 1 else "CONFLICT"

            has_table_layer = (rec["l1_year_table"].startswith("MATCH")
                               or rec["l1_year_table"].startswith("NO_YEAR_TABLE"))
            l2_ok = c is not None and rec["l2_compilation_date"] == r["decision_date"]
            l3_ok = rec["l3_openfda_match"] == "MATCH" and rec["l3_orig_date"] == r["decision_date"]

            if has_table_layer and l2_ok and l3_ok:
                rec["verdict"] = "VERIFIED_ALL_LAYERS"
            elif has_table_layer and l2_ok:
                rec["verdict"] = "VERIFIED_TABLE_AND_COMPILATION"
            elif l2_ok and l3_ok:
                rec["verdict"] = "VERIFIED_COMPILATION_AND_OPENFDA"
            elif l2_ok:
                rec["verdict"] = "VERIFIED_COMPILATION_ONLY"
            else:
                rec["verdict"] = "UNRESOLVED_NEEDS_REVIEW"

            # ---- live spot-checks (staged verbatim captures) ----------------
            lc = (live.get("NDA" + a) or live.get("BLA" + a) or live.get("BL" + a)
                       or live.get("N" + a))  # N-prefixed CBER-era PLA numbers
            if lc:
                rec["live_check"] = f"{lc['result']} ({lc['checked_utc']}; {lc['query_url']})"

            if flags:
                rec["review_flag"] = "; ".join(flags)
                stats["flagged"] += 1
            stats[rec["verdict"]] += 1
            out.append(rec)

        n = len(rows)
        summary.append({
            "audit_year": ys,
            "master_rows": n,
            "official_enumeration": (f"CDER NME year table ({tables[y]['meta']['row_count']} rows)"
                                     if y in YEARS_WITH_TABLE else
                                     "CDER Novel Drug Approvals Compilation (no year table exists)"),
            "verdict_VERIFIED_ALL_LAYERS": stats.get("VERIFIED_ALL_LAYERS", 0),
            "verdict_VERIFIED_TABLE_AND_COMPILATION": stats.get("VERIFIED_TABLE_AND_COMPILATION", 0),
            "verdict_VERIFIED_COMPILATION_AND_OPENFDA": stats.get("VERIFIED_COMPILATION_AND_OPENFDA", 0),
            "verdict_VERIFIED_COMPILATION_ONLY": stats.get("VERIFIED_COMPILATION_ONLY", 0),
            "verdict_UNRESOLVED_NEEDS_REVIEW": stats.get("UNRESOLVED_NEEDS_REVIEW", 0),
            "rows_flagged": stats.get("flagged", 0),
            "openfda_matched": sum(1 for r in out if r["audit_year"] == ys
                                   and r["l3_openfda_match"] == "MATCH"),
            "not_in_openfda": sum(1 for r in out if r["audit_year"] == ys
                                  and r["l3_openfda_match"] == "NOT_IN_OPENFDA"),
        })

    with OUT_AUDIT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_HEADER)
        w.writeheader()
        w.writerows(out)
    with OUT_SUMMARY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    # ---- assertions -------------------------------------------------------
    if len(out) != len(master):
        errors.append(f"audit rows {len(out)} != master rows {len(master)}")
    by_id = {r["decision_id"] for r in out}
    if len(by_id) != len(out):
        errors.append("duplicate decision_id in audit output")
    s = {r["audit_year"]: r for r in summary}
    for y, pin in sorted(YEAR_PINS.items(), reverse=True):
        if s[str(y)]["master_rows"] != pin:
            errors.append(f"{y} pin {pin} broken")
    if sum(YEAR_PINS.values()) != len(out):
        errors.append(f"sum of year pins {sum(YEAR_PINS.values())} != audit rows {len(out)}")

    print(f"audit rows written: {len(out)} -> {OUT_AUDIT.name}")
    for r in summary:
        print(f"  {r['audit_year']}: {r['master_rows']:>3} rows | "
              f"ALL={r['verdict_VERIFIED_ALL_LAYERS']} T+C={r['verdict_VERIFIED_TABLE_AND_COMPILATION']} "
              f"C+O={r['verdict_VERIFIED_COMPILATION_AND_OPENFDA']} C-only={r['verdict_VERIFIED_COMPILATION_ONLY']} "
              f"UNRESOLVED={r['verdict_UNRESOLVED_NEEDS_REVIEW']} flagged={r['rows_flagged']} "
              f"openFDA matched={r['openfda_matched']} not-in-openFDA={r['not_in_openfda']}")
    if errors:
        print("ASSERTION FAILURES:")
        for e in errors:
            print("  ", e)
        return 1
    print(f"ASSERTIONS PASS (year pins 2000:29 1999:37 1998:36 1997:43 1996:59 "
          f"1995:30 1994:23 1993:27 1992:29 1991:32 1990:24 1989:27 1988:20 "
          f"1987:22 1986:23 1985:31; coverage {len(out)}/{len(out)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
