#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v22 (2026-09-20): 1977-1979 year-by-year workbench.

Does NOT write data/pre1980_fda_decisions.csv. The 173 verified Type 1/1-4
rows stay exactly as v21 produced them. This builder only writes:

* data/pre1980_kind_unresolved_nme_adjudication.csv  (7 NME-comparable KIND_UNRESOLVED)
* data/pre1980_year_focus_1977_1979.csv              (3 year rows)
* data/pre1980_1977_gap_search_log.csv               (public-data searches; no invented names)
* data/pre1980_v22_captures_index.csv                (V22-C01..C03)

Fail-closed membership tests:
* NDA 18-103 / 018103 / SELACRYN / TICRYNAFEN is absent from every remaining
  FDA database file (Applications, Submissions, Products, 1965-1979 payloads).
* ApplNo 012043 is present as ORIG/AP 1978-10-16 TYPE 1/4 STANDARD in
  Submissions_1965_1979.txt and absent from Applications_all_types.txt.

Selacryn is named in missing_nme_candidates.csv by the v21 builder (v22 pin);
it is never added as a decision-table row.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_DB = DATA / "raw" / "drugsatfda_data_files_2026_09"
CAPTURES_DIR = DATA / "raw" / "source_captures_2026_09_20"
EVIDENCE = CAPTURES_DIR / "live_primary_captures_v22_2026_09_20.json"

BLOCKS = {
    (1965, 1969): "openfda_orig_decisions_1965_1969",
    (1970, 1974): "openfda_orig_decisions_1970_1974",
    (1975, 1979): "openfda_orig_decisions_1975_1979",
}

NME_UNRESOLVED = (
    ("1966", "014262", "1966-05-20", "TYPE 1/4",
     "Type 1 - New Molecular Entity and Type 4 - New Combination", "STANDARD",
     "FULLDB-1966-UNRES10"),
    ("1969", "016486", "1969-01-24", "TYPE 1/4",
     "Type 1 - New Molecular Entity and Type 4 - New Combination", "STANDARD",
     "FULLDB-1969-UNRES02"),
    ("1970", "016771", "1970-11-13", "TYPE 1/4",
     "Type 1 - New Molecular Entity and Type 4 - New Combination", "STANDARD",
     "FULLDB-1970-UNRES22"),
    ("1973", "017383", "1973-02-20", "TYPE 1",
     "Type 1 - New Molecular Entity", "PRIORITY",
     "FULLDB-1973-UNRES04"),
    ("1973", "017024", "1973-07-09", "TYPE 1",
     "Type 1 - New Molecular Entity", "STANDARD",
     "FULLDB-1973-UNRES15"),
    ("1973", "017267", "1973-10-02", "TYPE 1",
     "Type 1 - New Molecular Entity", "PRIORITY",
     "FULLDB-1973-UNRES28"),
    ("1978", "012043", "1978-10-16", "TYPE 1/4",
     "Type 1 - New Molecular Entity and Type 4 - New Combination", "STANDARD",
     "FULLDB-1978-UNRES22"),
)

OFFICIAL = {"1977": ("25", "63"), "1978": ("17", "86"), "1979": ("14", "94")}
ENUMERATED = {"1977": 17, "1978": 18, "1979": 13}
PAYLOAD_ORIG = {"1977": 42, "1978": 66, "1979": 62}
UNRES_TOTAL = {"1977": 32, "1978": 28, "1979": 19}
UNRES_NME = {"1977": 0, "1978": 1, "1979": 0}
UNRES_CLASS = {
    "1977": "27 unpublished class, 2 TYPE 5, 2 TYPE 3, 1 TYPE 2 (0 TYPE 1/1-4)",
    "1978": "23 unpublished class, 2 TYPE 3, 1 TYPE 5, 1 TYPE 4, 1 TYPE 1/4 (012043)",
    "1979": "17 unpublished class, 1 TYPE 5, 1 TYPE 6 (0 TYPE 1/1-4)",
}
BRANDS = {
    "1977": ("Lorelco, Tavist-1, Topicort, Bicnu, Optimine, Colestid, Tagamet, "
             "Cloderm, Prostin E2, Flexeril, Norpace, Didronel, Florone, Ativan, "
             "Lioresal, Thallous Chloride Tl 201, Nolvadex"),
    "1978": ("Elspar, Duricef, DDAVP, Depakene, Rimso-50, Glucoscan, Parlodel, "
             "Motofen, Dobutrex, Lopressor, Rocaltrol, Timoptic, Stadol, Amipaque, "
             "Clinoril, Mandol, Mefoxin, Platinol-AQ"),
    "1979": ("Hemabate, Reglan, Ceclor, Nubain, Liposyn 10%, Surmontil, Cyclapen-W, "
             "Demser, Cyclocort, Loniten, Corgard, Forane, Cerubidine"),
}

FR_URL = "https://www.govinfo.gov/content/pkg/FR-1996-05-20/html/96-12570.htm"
DAF = ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
       "?event=overview.process&varApplNo={num}")
NEEDLES_018103 = ("018103", "18103", "18-103", "SELACRYN", "TICRYNAFEN", "TIENILIC")


def fail(msg: str) -> None:
    raise SystemExit(f"build_pre1980_focus_1977_1979_v22: {msg}")


def load_tsv_applnos(path: Path) -> set[str]:
    if not path.exists():
        fail(f"missing {path}")
    appls: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as fh:
        header = fh.readline()
        if not header.upper().startswith("APPLNO"):
            fail(f"{path.name}: expected ApplNo header, got {header[:80]!r}")
        for line in fh:
            appls.add(line.split("\t", 1)[0].strip())
    return appls


def count_needle_hits(path: Path, needles: tuple[str, ...]) -> int:
    hits = 0
    upper = tuple(n.upper() for n in needles)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            u = line.upper()
            if any(n in u for n in upper):
                hits += 1
    return hits


def submissions_row(appl: str) -> str:
    path = RAW_DB / "Submissions_1965_1979.txt"
    with path.open(encoding="utf-8", errors="replace") as fh:
        fh.readline()
        matches = [line.rstrip("\n") for line in fh if line.split("\t", 1)[0] == appl]
    if len(matches) != 1:
        fail(f"expected exactly 1 Submissions row for {appl}, got {len(matches)}")
    return matches[0]


def payload_has_appl(appl: str) -> bool:
    for (lo, hi), block in BLOCKS.items():
        d = DATA / "raw" / block
        for year in range(lo, hi + 1):
            obj = json.loads((d / f"decisions_{year}.json").read_text(encoding="utf-8"))
            for rec in obj.get("decisions") or []:
                if rec.get("application_number") == appl:
                    return True
    return False


def read_csv(name: str) -> list[dict]:
    with (DATA / name).open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(name: str, header: list[str], rows: list[dict]) -> None:
    with (DATA / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def membership_tests() -> dict:
    apps_all = RAW_DB / "Applications_all_types.txt"
    apps_win = RAW_DB / "Applications_appl_window.txt"
    subs = RAW_DB / "Submissions_1965_1979.txt"
    prods = RAW_DB / "Products_appl_window.txt"
    for p in (apps_all, apps_win, subs, prods):
        if not p.exists():
            fail(f"missing {p}")

    n_apps = sum(1 for _ in apps_all.open(encoding="utf-8", errors="replace")) - 1
    if n_apps != 29336:
        fail(f"Applications_all_types.txt data-row count drifted: {n_apps} != 29336")

    hits = {}
    for label, path in (("Applications_all_types", apps_all),
                        ("Applications_appl_window", apps_win),
                        ("Submissions_1965_1979", subs),
                        ("Products_appl_window", prods)):
        hits[label] = count_needle_hits(path, NEEDLES_018103)
        if hits[label] != 0:
            fail(f"{label}: expected 0 hits for 018103/SELACRYN/TICRYNAFEN, got {hits[label]}")
    if payload_has_appl("NDA018103"):
        fail("NDA018103 appeared in a 1965-1979 payload; refusing to treat it as purged")

    appl_set = load_tsv_applnos(apps_all)
    if "018103" in appl_set or "012043" in appl_set:
        fail("Applications_all_types unexpectedly contains 018103 or 012043")
    if "012043" in load_tsv_applnos(apps_win):
        fail("Applications_appl_window unexpectedly contains 012043")
    if "012043" in load_tsv_applnos(prods):
        fail("Products_appl_window unexpectedly contains 012043")
    if payload_has_appl("NDA012043"):
        fail("NDA012043 appeared in a 1965-1979 payload")

    sub_line = submissions_row("012043")
    parts = sub_line.split("\t")
    # ApplNo, ClassID, Type, No, Status, Date, Notes, Priority
    if parts[0] != "012043" or parts[1] != "8" or parts[2] != "ORIG" or parts[4] != "AP":
        fail(f"012043 Submissions fields drifted: {sub_line!r}")
    if not parts[5].startswith("1978-10-16"):
        fail(f"012043 date drifted: {parts[5]!r}")
    if parts[7] != "STANDARD":
        fail(f"012043 priority drifted: {parts[7]!r}")
    return {"n_apps": n_apps, "hits": hits, "sub_012043": sub_line}


def pin_crosscheck() -> None:
    """The 7 NME-comparable KIND_UNRESOLVED rows must still be in the v20/v21 tables."""
    a = read_csv("pre1980_full_db_crosscheck_1965_1976.csv")
    b = read_csv("pre1980_full_db_crosscheck_1977_1979.csv")
    by_appl = {r["appl_no"]: r for r in a + b}
    for year, appl, date, cls, desc, prio, rec_id in NME_UNRESOLVED:
        r = by_appl.get(appl)
        if r is None:
            fail(f"{appl}: missing from full-DB cross-check CSVs")
        if r["year"] != year or r["kind"] != "UNRESOLVED":
            fail(f"{appl}: year/kind drifted ({r['year']!r}/{r['kind']!r})")
        if r["decision_date"] != date:
            fail(f"{appl}: date drifted {r['decision_date']!r} != {date!r}")
        if (r["submission_class_code"] or "").upper() != cls:
            fail(f"{appl}: class drifted {r['submission_class_code']!r} != {cls!r}")
        if (r["review_priority"] or "") != prio:
            fail(f"{appl}: priority drifted {r['review_priority']!r} != {prio!r}")
        if r["in_openfda_payload"] != "FALSE":
            fail(f"{appl}: expected in_openfda_payload=FALSE")
        if rec_id.upper() not in (r["record_id"] or "").upper() and r["record_id"] != rec_id:
            # 1978 id in the committed file is FULldb-1978-UNRES22 (mixed case)
            if r["record_id"].upper() != rec_id.upper():
                fail(f"{appl}: record_id drifted {r['record_id']!r} != {rec_id!r}")
        if desc not in (r.get("submission_class_code_description") or ""):
            fail(f"{appl}: class description drifted")

    nme_a = [r for r in a if r.get("kind") == "UNRESOLVED"
             and (r.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4")]
    nme_b = [r for r in b if r.get("kind") == "UNRESOLVED"
             and (r.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4")]
    if len(nme_a) != 6 or len(nme_b) != 1:
        fail(f"NME-comparable KIND_UNRESOLVED count drifted: 1965-76={len(nme_a)} 1977-79={len(nme_b)}")

    unres_77 = [r for r in b if r["year"] == "1977" and r["kind"] == "UNRESOLVED"]
    if len(unres_77) != 32:
        fail(f"1977 KIND_UNRESOLVED count drifted: {len(unres_77)}")
    if any((r.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4") for r in unres_77):
        fail("1977 KIND_UNRESOLVED unexpectedly includes a TYPE 1/1-4 row")


def pin_decisions_untouched() -> list[dict]:
    rows = read_csv("pre1980_fda_decisions.csv")
    if len(rows) != 173:
        fail(f"pre1980_fda_decisions.csv drifted to {len(rows)} rows (expected 173)")
    brands = {(r.get("drug_brand") or "").upper() for r in rows}
    appls = {r.get("application_number") or "" for r in rows}
    if "SELACRYN" in brands or any("018103" in a for a in appls):
        fail("Selacryn / NDA 018103 was written into the decision table; refusing")
    if any("012043" in a for a in appls):
        fail("012043 was written into the decision table; refusing")
    for year, want in ENUMERATED.items():
        got = sum(1 for r in rows if r["year"] == year)
        if got != want:
            fail(f"{year} decision rows drifted: {got} != {want}")
    return rows


def build_adjudication() -> list[dict]:
    rows = []
    official_delta = {
        "1966": ("10", 7, 3, "PROJECT_SHORT_FLAGGED"),
        "1969": ("5", 8, -3, "PROJECT_EXCEEDS_OFFICIAL"),
        "1970": ("15", 11, 4, "PROJECT_SHORT_FLAGGED"),
        "1973": ("14", 11, 3, "PROJECT_SHORT_FLAGGED"),
        "1978": ("17", 18, -1, "PROJECT_EXCEEDS_OFFICIAL"),
    }
    for year, appl, date, cls, desc, prio, rec_id in NME_UNRESOLVED:
        off, enum, shortfall, verdict = official_delta[year]
        if year == "1978":
            role = "INVENTORY_NOT_GAP_FILLER"
            adjudication = (
                "ORIG/AP row in Submissions_1965_1979.txt whose ApplNo is absent from "
                "Applications_all_types.txt, so no NDA/ANDA/BLA type can be asserted; "
                "absent from Products and from the openFDA ORIG/AP payload. 1978 has no "
                "official NME shortfall (17 official vs 18 enumerated; Motofen TYPE 1/4 is "
                "the +1), so 012043 cannot fill 1977x8 or 1979x1 and is inventory only."
            )
        elif year == "1969":
            role = "INVENTORY_NOT_GAP_FILLER"
            adjudication = (
                "ORIG/AP row in Submissions whose ApplNo is absent from Applications_all_types. "
                "1969 PROJECT_EXCEEDS_OFFICIAL (8 enumerated vs 5 official), so this TYPE 1/4 "
                "row is not a named fill for a shortfall. Recorded as a review candidate, "
                "never added as an approval."
            )
        else:
            role = "REVIEW_CANDIDATE_NOT_ADDED"
            adjudication = (
                "ORIG/AP row in Submissions_1965_1979.txt whose ApplNo is absent from "
                "Applications_all_types.txt, so no NDA/ANDA/BLA type can be asserted; the "
                "openFDA payloads do not carry it and Products publishes no brand. The year "
                f"has an official shortfall of {shortfall}, but without an Applications type "
                "and without a published product name this row is not asserted as the missing "
                "NME. Recorded as a review candidate, never added as an approval."
            )
        rows.append({
            "adjudication_id": f"KINDUNRES-{year}-{appl}",
            "crosscheck_record_id": rec_id,
            "year": year,
            "appl_no": appl,
            "decision_date": date,
            "submission_class_code": cls,
            "submission_class_code_description": desc,
            "review_priority": prio,
            "nme_comparable": "TRUE",
            "in_submissions_1965_1979": "TRUE",
            "in_applications_all_types": "FALSE",
            "in_products_appl_window": "FALSE",
            "in_openfda_payload": "FALSE",
            "official_nmes": off,
            "enumerated_nme_comparable": str(enum),
            "official_shortfall": str(shortfall),
            "year_verdict": verdict,
            "role_vs_gap": role,
            "adjudication": adjudication,
            "status": "KIND_UNRESOLVED_NOT_ADDED",
            "drugsatfda_url": DAF.format(num=appl),
            "source_urls": (f"{DAF.format(num=appl)}|"
                            "data/raw/drugsatfda_data_files_2026_09/Submissions_1965_1979.txt|"
                            "data/raw/drugsatfda_data_files_2026_09/Applications_all_types.txt"),
            "notes": (
                f"v22 2026-09-20: pinned against the committed full-DB cross-check "
                f"({rec_id}) and re-checked in Submissions_1965_1979.txt / "
                f"Applications_all_types.txt. No brand, holder, ORIG class on an Applications "
                f"row, or payload date beyond the Submissions fields above. Not added to "
                f"data/pre1980_fda_decisions.csv."
            ),
        })
    if len(rows) != 7:
        fail(f"expected 7 NME-comparable KIND_UNRESOLVED rows, got {len(rows)}")
    return rows


def build_year_focus(decisions: list[dict]) -> list[dict]:
    rows = []
    for year in ("1977", "1978", "1979"):
        off_nme, off_nda = OFFICIAL[year]
        enum = ENUMERATED[year]
        delta = enum - int(off_nme)
        verdict = ("PROJECT_SHORT_FLAGGED" if delta < 0
                   else ("PROJECT_EXCEEDS_OFFICIAL" if delta > 0 else "MATCH"))
        remaining = max(0, int(off_nme) - enum)
        named_cand = named_nda = named_status = ""
        if year == "1979":
            named_cand = "Selacryn (ticrynafen) tablets"
            named_nda = "NDA018103"
            named_status = "NAMED_CANDIDATE_NOT_ADDED"
            remaining = 0  # the 1 slot has a named (unconfirmed) candidate
            unnamed_slots = 0
            named_note = (
                "The 1 official shortfall now has a named candidate from FR 61 FR 25228; "
                "identity is not confirmed without the 1989 CDER typescript, so the slot is "
                "named-not-added rather than closed."
            )
        elif year == "1977":
            unnamed_slots = 8
            named_note = (
                "Public Drugs@FDA / openFDA / Federal Register searches this session named "
                "no 1977 NME. KIND_UNRESOLVED 1977 includes 0 TYPE 1/1-4. The 8 remain unnamed."
            )
        else:
            unnamed_slots = 0
            named_note = (
                "No official shortfall. Motofen NDA017744 TYPE 1/4 is the +1. KIND_UNRESOLVED "
                "012043 (1978-10-16 TYPE 1/4 STANDARD) is inventory, not a gap-filler."
            )
        rows.append({
            "year": year,
            "official_nmes": off_nme,
            "official_ndas": off_nda,
            "payload_orig_ap": str(PAYLOAD_ORIG[year]),
            "enumerated_type1_14": str(enum),
            "nme_comparable": str(enum),
            "delta_nme_comparable_vs_official": str(delta),
            "verdict": verdict,
            "kind_unresolved_total": str(UNRES_TOTAL[year]),
            "kind_unresolved_nme_comparable": str(UNRES_NME[year]),
            "kind_unresolved_class_census": UNRES_CLASS[year],
            "named_purge_candidate": named_cand,
            "named_purge_application": named_nda,
            "named_purge_status": named_status,
            "remaining_unnamed_nme_slots": str(unnamed_slots),
            "enumerated_brands": BRANDS[year],
            "workbench_note": named_note,
            "primary_source_urls": (
                "https://www.fda.gov/about-fda/histories-fda-regulated-products/"
                "summary-nda-approvals-receipts-1938-present|"
                f"data/raw/openfda_orig_decisions_1975_1979/decisions_{year}.json|"
                + (FR_URL if year == "1979" else
                   "data/raw/drugsatfda_data_files_2026_09/Submissions_1965_1979.txt")
            ),
        })
        # sanity vs decision table brands
        got = [r["drug_brand"] for r in decisions if r["year"] == year]
        if ", ".join(got) != BRANDS[year]:
            fail(f"{year} brand list drifted vs decision table")
        _ = remaining  # named 1979 remaining-as-sized is documented in unnamed_slots
    return rows


def build_search_log() -> list[dict]:
    """Document every 1977/1978/1979 naming search. Names are never invented."""
    return [
        {
            "search_id": "SEARCH-1977-01",
            "year": "1977",
            "query": "KIND_UNRESOLVED ORIG/AP 1977 class census in pre1980_full_db_crosscheck_1977_1979.csv",
            "source": "Committed full Drugs@FDA database cross-check (v20)",
            "result": "32 KIND_UNRESOLVED rows: 27 unpublished class, 2 TYPE 5, 2 TYPE 3, 1 TYPE 2, 0 TYPE 1, 0 TYPE 1/4.",
            "names_asserted": "",
            "status": "NO_1977_NME_NAMED",
            "url": "data/pre1980_full_db_crosscheck_1977_1979.csv",
            "notes": "KIND_UNRESOLVED cannot name the official 8-NME shortfall because none of the 32 rows is TYPE 1/1-4.",
        },
        {
            "search_id": "SEARCH-1977-02",
            "year": "1977",
            "query": "Hussar 1978 'New Drugs of 1977' American Journal of Nursing",
            "source": "AJN / Lippincott (paywalled)",
            "result": "The 1978 Hussar review is paywalled from this sandbox; no NME names were copied from it.",
            "names_asserted": "",
            "status": "PAYWALLED_NOT_USED_AS_NAMES",
            "url": "https://journals.lww.com/ajnonline/abstract/1978/07000/new_drugs_of_1977.36.aspx",
            "notes": "Standing rule: do not invent missing NME names and do not promote a paywalled secondary list into the candidate ledger.",
        },
        {
            "search_id": "SEARCH-1977-03",
            "year": "1977",
            "query": "NCATS Inxight Drugs / Orange Book NME Appendix 1950-1993 first-approved-in-1977",
            "source": "NCATS Inxight Drugs (NIH)",
            "result": "Colestipol (Colestid) first-approved 1977 matches the already-enumerated TYPE 1 row NDA017563. No additional 1977 NME name recovered from public Inxight pages this session.",
            "names_asserted": "",
            "status": "MATCHES_ALREADY_ENUMERATED",
            "url": "https://drugs.ncats.io/",
            "notes": "A hit that already sits in pre1980_fda_decisions.csv is not a gap fill.",
        },
        {
            "search_id": "SEARCH-1977-04",
            "year": "1977",
            "query": "Drugs@FDA monthly original-approval listing August 1977",
            "source": "FDA Drugs@FDA (accessdata.fda.gov)",
            "result": "Public monthly ORIG listings recovered in prior sessions list only already-enumerated TYPE 1s (Tagamet NDA017920 1977-08-16 among them).",
            "names_asserted": "",
            "status": "NO_NEW_1977_NME_NAMED",
            "url": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm",
            "notes": "Monthly ORIG pages are not a source of the missing 8.",
        },
        {
            "search_id": "SEARCH-1977-05",
            "year": "1977",
            "query": "vidarabine / Vira-A as a possible 1977 NME fill",
            "source": "Committed 1965-1979 payloads + literature",
            "result": "Vira-A (vidarabine) NDA050486 is already enumerated as a 1976 TYPE 1 original. Mixed 1976 ophthalmic vs 1977 IV reports in literature are not a verified 1977 NME fill.",
            "names_asserted": "",
            "status": "ALREADY_ENUMERATED_OTHER_YEAR",
            "url": "data/pre1980_fda_decisions.csv",
            "notes": "Do not double-count a 1976 TYPE 1 as a 1977 gap fill.",
        },
        {
            "search_id": "SEARCH-1977-06",
            "year": "1977",
            "query": "Federal Register withdrawal / DESI notices naming a 1977 NME absent from Drugs@FDA",
            "source": "GPO govinfo Federal Register HTML",
            "result": "This session's FR search named NDA 18-103 Selacryn (a 1979 candidate), not a 1977 NME. No 1977 NME name was recovered from FR HTML.",
            "names_asserted": "",
            "status": "NO_1977_NME_NAMED",
            "url": "https://www.govinfo.gov/app/search",
            "notes": "The 1977x8 still require the 1989 CDER 'Offices of Drug Evaluation: Statistical Report' (FDA History Office Files) or the contemporaneous annual report.",
        },
        {
            "search_id": "SEARCH-1978-01",
            "year": "1978",
            "query": "ApplNo 012043 in Submissions_1965_1979.txt / Applications_all_types.txt / payloads",
            "source": "Committed Drugs@FDA database files",
            "result": "One Submissions ORIG/AP row 1978-10-16 TYPE 1/4 STANDARD; 0 Applications rows; 0 Products rows; 0 payload rows.",
            "names_asserted": "",
            "status": "INVENTORY_NOT_GAP_FILLER",
            "url": "data/raw/drugsatfda_data_files_2026_09/Submissions_1965_1979.txt",
            "notes": "1978 has no official shortfall. 012043 cannot fill 1977x8 or 1979x1. Capture V22-C03.",
        },
        {
            "search_id": "SEARCH-1979-01",
            "year": "1979",
            "query": "Federal Register NDA 18-103 Selacryn (ticrynafen) Tablets",
            "source": "Federal Register 61 FR 25228 (1996-05-20) Docket 96N-0151 FR Doc 96-12570",
            "result": "FDA withdrew NDA 18-103 Selacryn (ticrynafen) Tablets held by SmithKline Beecham. Company discontinued marketing in 1980 because of liver toxicity observed after approval of the NDA. Notice does not state the original approval date, class, or priority.",
            "names_asserted": "Selacryn (ticrynafen) NDA 18-103 / NDA018103",
            "status": "NAMED_CANDIDATE_NOT_ADDED",
            "url": FR_URL,
            "notes": "Capture V22-C01. Recorded on missing_nme_candidates.csv GAP-1979-01. Not added to the decision table.",
        },
        {
            "search_id": "SEARCH-1979-02",
            "year": "1979",
            "query": "018103 / SELACRYN / TICRYNAFEN in Applications_all_types, Submissions, Products, 1965-1979 payloads",
            "source": "Committed Drugs@FDA database files + ORIG/AP payloads",
            "result": "0 hits in Applications_all_types.txt (29,336 rows), Applications_appl_window.txt, Submissions_1965_1979.txt, Products_appl_window.txt, and every 1965-1979 payload.",
            "names_asserted": "Selacryn (ticrynafen) NDA018103",
            "status": "NAMED_NDA_ABSENT_FROM_ALL_REMAINING_FDA_FILES",
            "url": "data/raw/drugsatfda_data_files_2026_09/Applications_all_types.txt",
            "notes": "Capture V22-C02. Seldane-class purge proven by a named NDA. Distinct from amikacin NDA050495 (openFDA shell, no submissions array).",
        },
        {
            "search_id": "SEARCH-1979-03",
            "year": "1979",
            "query": "Literature FDA approval date 1979-05-02 for ticrynafen / tienilic acid",
            "source": "NCATS Inxight (OB NME Appendix 1950-1993); Pink Sheet/Citeline; ScienceDirect; Wikipedia Tienilic acid",
            "result": "NCATS Inxight cites first approved 1979 from the Orange Book NME Appendix 1950-1993. Secondary literature reports FDA 1979-05-02 and US market withdrawal January 1980. That calendar date is NOT in remaining FDA databases. The 1979 TYPE 1 list has no May 2 (gap Apr 4 Ceclor NDA050521 -> May 15 Nubain NDA018024).",
            "names_asserted": "Selacryn (ticrynafen) NDA018103",
            "status": "LITERATURE_DATE_NOT_FDA_DATABASE",
            "url": "https://en.wikipedia.org/wiki/Tienilic_acid",
            "notes": "The 1979-05-02 date is recorded as literature-reported, never written as an FDA-database decision_date.",
        },
    ]


def build_captures_index() -> list[dict]:
    ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if [c["capture_id"] for c in ev["captures"]] != ["V22-C01", "V22-C02", "V22-C03"]:
        fail("v22 evidence file must carry exactly V22-C01..V22-C03")
    sha = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    rows = []
    for c in ev["captures"]:
        rows.append({
            "capture_id": c["capture_id"],
            "capture_date": ev["capture_date"],
            "system": c["system"],
            "subject": c["subject"],
            "url": c["query_url"],
            "finding_summary": c["finding"],
            "project_table_affected": (
                "missing_nme_candidates.csv" if c["capture_id"] != "V22-C03"
                else "pre1980_kind_unresolved_nme_adjudication.csv"
            ),
            "project_row_ids": c["project_row_ids"],
            "project_effect": c["project_effect"],
            "verbatim_evidence_ref": (
                "data/raw/source_captures_2026_09_20/live_primary_captures_v22_2026_09_20.json"
            ),
            "evidence_sha256": sha,
        })
    return rows


def main() -> int:
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    if not EVIDENCE.exists():
        fail(f"missing {EVIDENCE}")
    membership_tests()
    pin_crosscheck()
    decisions = pin_decisions_untouched()

    adj = build_adjudication()
    focus = build_year_focus(decisions)
    log = build_search_log()
    caps = build_captures_index()

    write_csv("pre1980_kind_unresolved_nme_adjudication.csv", list(adj[0].keys()), adj)
    write_csv("pre1980_year_focus_1977_1979.csv", list(focus[0].keys()), focus)
    write_csv("pre1980_1977_gap_search_log.csv", list(log[0].keys()), log)
    write_csv("pre1980_v22_captures_index.csv", list(caps[0].keys()), caps)

    print(f"v22: {len(adj)} KIND_UNRESOLVED NME adjudications, "
          f"{len(focus)} year-focus rows, {len(log)} search-log rows, "
          f"{len(caps)} captures; decision table left at {len(decisions)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
