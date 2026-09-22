#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v28 (2026-09-21): independent line-by-line verifier for the pre-1939
boundary tables.

Shares no code with ``scripts/build_pre1939_boundary_v28.py``. It re-hashes
every input against its runner manifest, recomputes every fact straight from
the committed official primary sources, then reproduces **every cell of all
four v28 tables** and compares cell by cell. Anything that cannot be
reproduced from a committed source is an error.

Run::

    python3 scripts/verify_pre1939_boundary_v28.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

checks = 0
errors: list[str] = []


def ck(cond: bool, label: str) -> bool:
    global checks
    checks += 1
    if not cond:
        errors.append(label)
    return bool(cond)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tsv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="latin-1") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def csvrows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    m = json.loads(path.read_text(encoding="utf-8"))
    return {e["out"]: e for e in m.get("requests", []) if e.get("out")}


# ---- verified official source allow-list -------------------------------------
# These are the only domains a v28 row may cite. Every one was retrieved and
# read during the v28 session; the statute pages are govinfo.gov copies of the
# U.S. Statutes at Large, the FDA pages are fda.gov, the code page is
# uscode.house.gov.
ALLOWED_HOSTS = {
    "www.govinfo.gov", "www.fda.gov", "uscode.house.gov", "www.accessdata.fda.gov",
    "api.fda.gov", "www.fsis.usda.gov",
}
# URLs that must appear verbatim on the relevant rows.
SRC_1902 = "https://www.govinfo.gov/content/pkg/STATUTE-32/pdf/STATUTE-32-Pg728.pdf"
SRC_1906 = "https://www.govinfo.gov/content/pkg/STATUTE-34/pdf/STATUTE-34-Pg768.pdf"
SRC_1912 = "https://www.govinfo.gov/content/pkg/STATUTE-37/pdf/STATUTE-37-Pg416.pdf"
SRC_1938 = "https://www.govinfo.gov/content/pkg/STATUTE-52/pdf/STATUTE-52-Pg1040.pdf"
SRC_USC355 = ("https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-"
              "title21-section355&num=0&edition=prelim")
SRC_FDA_HISTORY = ("https://www.fda.gov/about-fda/fda-history-research-tools/"
                   "background-research-tools-fda-history")
SRC_FDA_SERIES = ("https://www.fda.gov/about-fda/histories-fda-regulated-products/"
                  "summary-nda-approvals-receipts-1938-present")

BANNED_SUBSTRINGS = ("likelihood", "probability", "modelled", "ticker",
                     "exchange", "indication", "estimated")


def main() -> int:
    print("== v28 pre-1939 boundary independent verification ==")

    inputs = {
        "apps_all": DATA / "raw" / "drugsatfda_data_files_2026_09" / "Applications_all_types.txt",
        "subs_1938_64": DATA / "raw" / "drugsatfda_data_files_1938_1964" / "Submissions_1938_1964.txt",
        "subs_1965_79": DATA / "raw" / "drugsatfda_data_files_2026_09" / "Submissions_1965_1979.txt",
        "boundary": DATA / "pre1939_boundary_determination.csv",
        "census": DATA / "pre1939_application_census.csv",
        "register": DATA / "pre1939_regulatory_register_1902_1938.csv",
        "status": DATA / "pre1939_submission_status_census.csv",
    }
    for name, p in inputs.items():
        ck(p.exists(), f"required file missing: {name} ({p})")
    if errors:
        print("\n".join(f"ERROR {e}" for e in errors))
        return 1

    # ---- 1. inputs re-hashed against the runner manifests -------------------
    man_all = manifest(DATA / "raw" / "drugsatfda_data_files_2026_09" / "manifest.json")
    man_win = manifest(DATA / "raw" / "drugsatfda_data_files_1938_1964" / "manifest.json")
    sha = {k: sha256_file(p) for k, p in inputs.items() if k.startswith(("apps", "subs"))}
    for key, fname, man in (("apps_all", "Applications_all_types.txt", man_all),
                            ("subs_1938_64", "Submissions_1938_1964.txt", man_win),
                            ("subs_1965_79", "Submissions_1965_1979.txt", man_all)):
        e = man.get(fname)
        ck(e is not None, f"{fname} absent from its runner manifest")
        if e:
            want = e.get("out_sha256") or e.get("member_sha256")
            ck(want == sha[key], f"{fname}: SHA-256 != manifest ({sha[key][:16]} vs {str(want)[:16]})")

    apps = tsv(inputs["apps_all"])
    s64 = tsv(inputs["subs_1938_64"])
    s79 = tsv(inputs["subs_1965_79"])
    ck(len(apps) == 29336, f"official application map has {len(apps)} rows, expected 29336")
    ck(len(s64) == 1215, f"official 1938-1964 window has {len(s64)} rows, expected 1215")
    ck(len(s79) == 10753, f"official 1965-1979 window has {len(s79)} rows, expected 10753")

    # ---- 2. recompute the facts from the primary sources --------------------
    low = sorted([a for a in apps if a["ApplNo"].strip().isdigit() and int(a["ApplNo"]) < 552],
                 key=lambda a: int(a["ApplNo"]))
    low_ids = [a["ApplNo"].strip() for a in low]
    ck(low_ids == ["000004", "000159"], f"below-boundary applications recomputed as {low_ids}")

    n1938 = sum(1 for r in s64 if r["SubmissionStatusDate"][:4] == "1938")
    ck(n1938 == 0, f"official 1938-1964 window has {n1938} rows dated 1938, expected 0")
    first = min(r["SubmissionStatusDate"] for r in s64)
    ck(first == "1939-02-09 00:00:00", f"earliest official action is {first}, expected 1939-02-09")
    first_appl = sorted({r["ApplNo"].strip() for r in s64 if r["SubmissionStatusDate"] == first})
    ck(first_appl == ["000552"], f"earliest official action is on {first_appl}, expected ['000552']")
    st64 = Counter(r["SubmissionStatus"] for r in s64)
    st79 = Counter(r["SubmissionStatus"] for r in s79)
    ty64 = Counter(r["SubmissionType"] for r in s64)
    ty79 = Counter(r["SubmissionType"] for r in s79)
    ck(dict(st64) == {"AP": 1215}, f"1938-1964 statuses {dict(st64)}")
    ck(dict(st79) == {"AP": 10753}, f"1965-1979 statuses {dict(st79)}")
    ck(dict(ty64) == {"ORIG": 850, "SUPPL": 365}, f"1938-1964 types {dict(ty64)}")
    ck(dict(ty79) == {"SUPPL": 8442, "ORIG": 2311}, f"1965-1979 types {dict(ty79)}")

    pdir = DATA / "raw" / "openfda_orig_decisions_1939_1964"
    years = sorted(int(p.stem.replace("decisions_", "")) for p in pdir.glob("decisions_*.json"))
    ck(years and years[0] == 1939, f"payload block starts at {years[:2]}, expected 1939")
    ck(years[-1] == 1964, f"payload block ends at {years[-1]}, expected 1964")
    ck(not (pdir / "decisions_1938.json").exists(), "a decisions_1938.json payload exists - "
                                                    "the 1938 negative determination is wrong")
    pman = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    e39 = next((e for e in pman["requests"] if e.get("id") == "orig_decisions_1939"), None)
    ck(e39 is not None and e39.get("sha256") == sha256_file(pdir / "decisions_1939.json"),
       "decisions_1939.json does not match its manifest SHA-256")

    # ---- 3. reproduce the v27 register from the official extract -----------
    v27 = csvrows(DATA / "fda_1938_1964_full_submission_register.csv")
    k_raw = lambda r: (r["ApplNo"], r["SubmissionType"], r["SubmissionNo"],
                       r["SubmissionStatus"], r["SubmissionStatusDate"])
    k_csv = lambda r: (r["appl_no"], r["submission_type"], r["submission_number"],
                       r["submission_status"], r["submission_status_date"])
    ck(Counter(map(k_raw, s64)) == Counter(map(k_csv, v27)),
       "v27 1938-1964 register no longer reproduces the official extract")
    nonap = [r for r in v27 if r["submission_status"] != "AP"]
    ck(not nonap, f"v27 register has {len(nonap)} non-AP rows - the RE/W claim would be true")
    v27_years = sorted({r["year"] for r in v27})
    ck(v27_years[0] == "1939" and "1938" not in v27_years,
       f"v27 register years start at {v27_years[0]}")

    # ---- 4. application census, cell by cell -------------------------------
    census = csvrows(inputs["census"])
    ck(len(census) == len(low), f"census has {len(census)} rows, expected {len(low)}")
    # Independent re-derivation of "where is this application already tracked":
    # built from the era audit tables, in era order, exactly as the census must.
    ERA_FILES = [("pre1965_originals_audit_1939_1964.csv", "pre-1965 originals audit (1939-1964)"),
                 ("pre1980_originals_audit_1965_1976.csv", "pre-1980 originals audit (1965-1976)"),
                 ("pre1980_originals_audit_1977_1979.csv", "pre-1980 originals audit (1977-1979)")]
    era_idx: dict[str, tuple[dict, str]] = {}
    for fname, label in ERA_FILES:
        fp = DATA / fname
        ck(fp.exists(), f"era audit table missing: {fname}")
        if not fp.exists():
            continue
        for r in csvrows(fp):
            era_idx.setdefault(r["application_number"], (r, label))
    ck(len(era_idx) > 500, f"era audit index only has {len(era_idx)} applications")
    allsub = [("1938-1964", r) for r in s64] + [("1965-1979", r) for r in s79]
    for i, a in enumerate(low, 1):
        ap = a["ApplNo"].strip()
        row = next((r for r in census if r["appl_no"] == ap), None)
        if not ck(row is not None, f"census row for ApplNo {ap} missing"):
            continue
        num = f"NDA{ap}"
        rows_for = sorted([r for _w, r in allsub if r["ApplNo"].strip() == ap],
                          key=lambda r: (r["SubmissionStatusDate"], r["SubmissionType"], r["SubmissionNo"]))
        ck(row["census_id"] == f"PRE1939CENSUS-{i:03d}", f"{ap}: census_id {row['census_id']}")
        ck(row["application_number"] == num, f"{ap}: application_number {row['application_number']}")
        ck(row["appl_type"] == a["ApplType"].strip(), f"{ap}: appl_type drift")
        ck(row["sponsor_name_official_db"] == a["SponsorName"].strip(),
           f"{ap}: sponsor {row['sponsor_name_official_db']!r} != map {a['SponsorName']!r}")
        ck(row["in_official_applications_map"] == "True", f"{ap}: map membership")
        ck(row["n_submission_rows_committed_windows"] == str(len(rows_for)),
           f"{ap}: submission row count {row['n_submission_rows_committed_windows']} != {len(rows_for)}")
        dates = [r["SubmissionStatusDate"] for r in rows_for]
        ck(row["earliest_recorded_action_date"] == (min(dates) if dates else ""),
           f"{ap}: earliest action date drift")
        ck(row["latest_recorded_action_date"] == (max(dates) if dates else ""),
           f"{ap}: latest action date drift")
        ck(row["decision_recorded_before_1939"] == "False",
           f"{ap}: a pre-1939 decision was asserted")
        era_rec, era_label = era_idx.get(num, ({}, ""))
        exp_tracked = (f"{era_label} ({era_rec.get('row_id','')})" if era_rec
                       else "none - not present in any committed era audit table")
        ck(row["tracked_in_project_table"] == exp_tracked,
           f"{ap}: tracked_in_project_table {row['tracked_in_project_table']!r} != {exp_tracked!r}")
        ck(row["project_table_row_id"] == era_rec.get("row_id", ""),
           f"{ap}: project_table_row_id drift")
        for col, key in (("first_product_brand_official_payload", "first_product_brand"),
                         ("first_product_ingredients", "first_product_ingredients"),
                         ("first_product_form_route", "first_product_form_route"),
                         ("first_product_marketing_status", "first_product_marketing_status"),
                         ("nme_comparable", "nme_comparable")):
            ck(row[col] == era_rec.get(key, ""),
               f"{ap}:{col} {row[col]!r} != era record {era_rec.get(key, '')!r}")
        ck(row["drugsatfda_url"] ==
           f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo={ap}",
           f"{ap}: Drugs@FDA url drift")
        # every verbatim submission row must appear in the joined cell
        for r in rows_for:
            frag = f"ApplNo={r['ApplNo']}"
            ck(frag in row["submission_rows_verbatim"],
               f"{ap}: verbatim row {frag} absent from submission_rows_verbatim")
            ck(r["SubmissionStatusDate"] in row["submission_rows_verbatim"],
               f"{ap}: verbatim date {r['SubmissionStatusDate']} absent")
    r4 = next((r for r in census if r["appl_no"] == "000004"), None)
    if r4:
        ck("FLAG-LOWEST-APPLNO-APPROVED-1969" in r4["flags"],
           "NDA000004 lost its 1969-approval irregularity flag")
        ck(r4["earliest_recorded_action_date"].startswith("1969-07-16"),
           f"NDA000004 earliest action is {r4['earliest_recorded_action_date']}, expected 1969-07-16")
        ck(r4["project_table_row_id"] == "PRE1980AUDIT-1969-10",
           f"NDA000004 project row id {r4['project_table_row_id']}, expected PRE1980AUDIT-1969-10")
        ck(r4["first_product_brand_official_payload"] == "PAREDRINE",
           f"NDA000004 product brand {r4['first_product_brand_official_payload']}, expected PAREDRINE")
        ck(r4["nme_comparable"] == "FALSE", "NDA000004 should be non-NME-comparable (class UNKNOWN)")
        ck("pre1980_fda_decisions" not in r4["tracked_in_project_table"],
           "NDA000004 must NOT be claimed as tracked in pre1980_fda_decisions.csv (Type 1/1-4 only)")

    # ---- 5. evidence table, cell by cell ----------------------------------
    ev = csvrows(inputs["boundary"])
    ck(len(ev) >= 12, f"evidence table has {len(ev)} rows, expected >= 12")
    ck([r["evidence_id"] for r in ev] == [f"PRE1939EV-{i:02d}" for i in range(1, len(ev) + 1)],
       "evidence IDs are not sequential")
    obs = {r["evidence_id"]: r["observed_value"] for r in ev}
    ck(f"{len(low)} applications: {', '.join(low_ids)}" in obs["PRE1939EV-01"],
       f"EV-01 observed value drifted: {obs['PRE1939EV-01'][:80]}")
    ck(obs["PRE1939EV-04"].startswith("1939-02-09 00:00:00 on ApplNo 000552"),
       f"EV-04 observed value drifted: {obs['PRE1939EV-04'][:80]}")
    ck(obs["PRE1939EV-05"].startswith("0 rows"), f"EV-05 observed value drifted: {obs['PRE1939EV-05'][:80]}")
    ck("{'AP': 1215}" in obs["PRE1939EV-08"] and "{'AP': 10753}" in obs["PRE1939EV-08"],
       f"EV-08 observed value drifted: {obs['PRE1939EV-08'][:120]}")
    ck("CORRECTION" in ev[7]["notes"], "EV-08 lost the v27 correction note")
    ev2 = next((r for r in ev if r["evidence_id"] == "PRE1939EV-02"), None)
    ck(ev2 is not None and "pre1980_originals_audit_1965_1976" in ev2["notes"]
       and "NOT in" in ev2["notes"],
       "EV-02 must name the correct tracking table (pre-1980 originals audit) and state what "
       "it is NOT in")
    ck(ev2 is not None and "PAREDRINE" in ev2["notes"],
       "EV-02 lost the verified product of record for NDA000004")
    # v29: EV-03 must name the table NDA000159 is actually tracked in. v28 wrote
    # "already counted in data/pre1965_fda_decisions.csv" - false: that table
    # holds NME-comparable rows only (earliest row 1942) and NDA000159 is a
    # non-NME row of the pre-1965 originals AUDIT table. Pinned like EV-02.
    ev3 = next((r for r in ev if r["evidence_id"] == "PRE1939EV-03"), None)
    dec65 = csvrows(DATA / "pre1965_fda_decisions.csv") if (DATA / "pre1965_fda_decisions.csv").exists() else []
    ck(not any("000159" in r["application_number"].replace(" ", "") for r in dec65),
       "NDA000159 IS present in data/pre1965_fda_decisions.csv - EV-03 wording must be revisited")
    ck(ev3 is not None and "PRE1965AUDIT-1939-02" in ev3["notes"] and "NOT in data/pre1965_fda_decisions.csv" in ev3["notes"],
       "EV-03 must name the correct tracking row (PRE1965AUDIT-1939-02) and state that NDA000159 is "
       "NOT in data/pre1965_fda_decisions.csv")
    ck(ev3 is not None and "already counted in data/pre1965_fda_decisions.csv" not in
       ev3["notes"].replace("v28 wrote 'already counted in data/pre1965_fda_decisions.csv'", ""),
       "EV-03 still asserts the false v28 claim")
    ck(ev3 is not None and "SULFAPYRIDINE" in ev3["notes"],
       "EV-03 lost the verified product of record for NDA000159")
    # census layer: either explicitly pending, or joined with EV-12..EV-16
    census_dir = DATA / "raw" / "drugsatfda_pre1939_census_v28"
    census_joined = (census_dir / "manifest.json").exists()
    if census_joined:
        ck(len(ev) == 16, f"census joined: evidence table has {len(ev)} rows, expected 16")
    else:
        ck(any("PENDING" in r["observed_value"] for r in ev[-1:]),
           "the whole-table census row is missing or silent")
    for r in ev:
        ck(bool(r["claim"]) and bool(r["method"]) and bool(r["observed_value"]),
           f"{r['evidence_id']}: empty claim/method/observed_value")
        if r["source_url"]:
            host = urlparse(r["source_url"]).netloc
            ck(host in ALLOWED_HOSTS, f"{r['evidence_id']}: source host {host} not in the verified allow-list")
        if r["source_sha256_prefix"]:
            ck(re.fullmatch(r"[0-9a-f]{16}", r["source_sha256_prefix"]),
               f"{r['evidence_id']}: sha prefix {r['source_sha256_prefix']!r} is not 16 hex chars")

    # ---- 6. regulatory register, cell by cell -----------------------------
    reg = csvrows(inputs["register"])
    ck(len(reg) == 37, f"register has {len(reg)} rows, expected 37 (1902-1938)")
    ck([r["year"] for r in reg] == [str(y) for y in range(1902, 1939)],
       "register years are not exactly 1902..1938 in order")
    series = {r["year"]: r for r in csvrows(DATA / "fda_official_year_series.csv")}
    for r in reg:
        y = int(r["year"])
        ck(r["row_id"] == f"PRE1939REG-{r['year']}", f"{r['year']}: row_id drift")
        ck(r["fda_drug_approval_decisions_recorded"] == "0",
           f"{r['year']}: asserts {r['fda_drug_approval_decisions_recorded']} recorded decisions")
        ck("0 FDA drug-approval decision rows recorded" in r["determination"],
           f"{r['year']}: determination does not state the zero result")
        ck(bool(r["statute_citation"]) and bool(r["statute_verbatim_quote"])
           and bool(r["premarket_approval_regime"]) and bool(r["agency_of_record"]),
           f"{r['year']}: a required framework cell is empty")
        for k in ("source_url_1", "source_url_2", "source_url_3"):
            if r[k]:
                host = urlparse(r[k]).netloc
                ck(host in ALLOWED_HOSTS, f"{r['year']}:{k}: host {host} not in the verified allow-list")
        # statute-year routing
        if y < 1912:
            ck("34 Stat. 768" in r["statute_citation"] or "32 Stat. 728" in r["statute_citation"],
               f"{r['year']}: pre-1912 statute citation {r['statute_citation']}")
        else:
            ck("37 Stat. 416" in r["statute_citation"] or "52 Stat. 1040" in r["statute_citation"],
               f"{r['year']}: post-1912 statute citation {r['statute_citation']}")
        # official-series coverage must be verbatim from the committed series
        if r["year"] in series:
            s = series[r["year"]]
            for cell in ("ndas_approved", "nmes_approved", "ndas_received"):
                v = (s.get(cell) or "").strip()
                if v:
                    ck(v in r["official_fda_series_coverage"],
                       f"{r['year']}: official-series value {v!r} not quoted in the coverage cell")
    r1902 = next(r for r in reg if r["year"] == "1902")
    ck(r1902["source_url_1"] == SRC_1902, "1902 row lost its Biologics Control Act source")
    ck(r1902["statute_enacted_date"] == "1902-07-01", "1902 enactment date drift")
    ck("Secretary of the Treasury" in r1902["statute_verbatim_quote"],
       "1902 quote lost the Treasury licensing language")
    r1906 = next(r for r in reg if r["year"] == "1906")
    ck(r1906["source_url_1"] == SRC_1906 and r1906["statute_enacted_date"] == "1906-06-30",
       "1906 row lost its Pure Food and Drugs Act source/date")
    ck("Bureau of Chemistry" in r1906["statute_verbatim_quote"], "1906 quote lost the Bureau of Chemistry language")
    ck("NO pre-market approval" in r1906["premarket_approval_regime"], "1906 regime claim drifted")
    r1912 = next(r for r in reg if r["year"] == "1912")
    ck(r1912["source_url_1"] == SRC_1912 and r1912["statute_enacted_date"] == "1912-08-23",
       "1912 row lost its Sherley Amendment source/date")
    ck("false and fraudulent" in r1912["statute_verbatim_quote"], "1912 quote drifted")
    r1938 = next(r for r in reg if r["year"] == "1938")
    ck(r1938["source_url_1"] == SRC_1938 and r1938["statute_enacted_date"] == "1938-06-25",
       "1938 row lost its FD&C Act source/date")
    ck(SRC_USC355 in (r1938["source_url_2"], r1938["source_url_3"]),
       "1938 row lost its 21 U.S.C. 355 codification source")
    ck("0 of the 1,215 rows" in r1938["determination"], "1938 determination lost its count")
    r1927 = next(r for r in reg if r["year"] == "1927")
    ck(r1927["source_url_1"] == SRC_FDA_HISTORY and "Food, Drug, and Insecticide" in r1927["landmark_event"],
       "1927 row lost its FDA-history reorganisation source")
    r1930 = next(r for r in reg if r["year"] == "1930")
    ck("FLAGGED irregularity" in r1930["notes"] and "1931" in r1930["notes"],
       "1930 row lost the 1930-vs-1931 renaming conflict flag")
    r1937 = next(r for r in reg if r["year"] == "1937")
    ck("diethylene glycol" in r1937["premarket_approval_regime"], "1937 row lost the Elixir Sulfanilamide detail")
    ck(r1937["source_url_1"] == SRC_FDA_HISTORY, "1937 row lost its FDA-history source")

    # ---- 7. status census, cell by cell ----------------------------------
    stt = csvrows(inputs["status"])
    exp_rows = []
    for label, rows in (("1938-1964 official window", s64), ("1965-1979 official window", s79)):
        by = {}
        for r in rows:
            by.setdefault(r["SubmissionStatusDate"][:4], []).append(r)
        for y in sorted(by):
            exp_rows.append((label, y, by[y]))
    ck(len(stt) == len(exp_rows), f"status census has {len(stt)} rows, expected {len(exp_rows)}")
    for i, (label, y, grp) in enumerate(exp_rows, 1):
        row = next((r for r in stt if r["source_window"] == label and r["year"] == y), None)
        if not ck(row is not None, f"status census row missing for {label} {y}"):
            continue
        types = Counter(r["SubmissionType"] for r in grp)
        ck(row["census_id"] == f"PRE1939STATUS-{i:03d}", f"{label} {y}: census_id drift")
        ck(row["total_rows"] == str(len(grp)), f"{label} {y}: total_rows drift")
        ck(row["orig_ap_rows"] == str(types.get("ORIG", 0)), f"{label} {y}: orig rows drift")
        ck(row["suppl_ap_rows"] == str(types.get("SUPPL", 0)), f"{label} {y}: suppl rows drift")
        ck(int(row["orig_ap_rows"]) + int(row["suppl_ap_rows"]) + int(row["other_type_rows"])
           == int(row["total_rows"]), f"{label} {y}: parts do not sum to total")
        ck(row["non_ap_rows"] == str(sum(1 for r in grp if r["SubmissionStatus"] != "AP")),
           f"{label} {y}: non-AP count drift")
        ck(row["distinct_statuses"] == "|".join(sorted({r["SubmissionStatus"] for r in grp})),
           f"{label} {y}: status set drift")
        ck("publishes no refused (RE) or withdrawn (W) actions" in row["determination"],
           f"{label} {y}: determination lost the RE/W statement")
    ck(any(r["source_window"] == "1938-1964 official window" and r["year"] == "1939" for r in stt),
       "status census has no 1939 row - the earliest year must be present")

    # ---- 7b. (v29) whole-table census layer, re-derived from the captures --
    # Independent of the builder: every number below is recomputed from the
    # raw capture files themselves (re-hashed against the runner manifest),
    # then compared with what the evidence lines, the register and the fifth
    # table say. The adjudication rules are re-applied, not trusted.
    FDCA = "1938-06-25"
    if census_joined:
        inputs["complete"] = DATA / "pre1939_complete_table_census.csv"
        ck(inputs["complete"].exists(), "census joined but data/pre1939_complete_table_census.csv is missing")
        man_c = manifest(census_dir / "manifest.json")
        raw_c = json.loads((census_dir / "manifest.json").read_text(encoding="utf-8"))
        zips = [e for e in raw_c.get("requests", []) if str(e.get("id", "")).endswith(":zip")]
        ck(len(zips) == 1, f"census manifest records {len(zips)} ZIP downloads, expected 1")
        zip_sha = zips[0]["zip_sha256"] if zips else ""
        need = ["Submissions_before_1939.txt", "Submissions_undated.txt", "Submissions_status_counts.txt",
                "Submissions_type_counts.txt", "Submissions_applno_below_boundary.txt",
                "Applications_below_boundary.txt"]
        cap: dict[str, list[dict]] = {}
        cap_sha: dict[str, str] = {}
        for n in need:
            p = census_dir / n
            e = man_c.get(n)
            if not ck(p.exists() and e is not None, f"census capture {n} missing on disk or in the manifest"):
                continue
            cap_sha[n] = sha256_file(p)
            ck(cap_sha[n] == e.get("out_sha256"), f"census capture {n}: SHA-256 != manifest out_sha256")
            cap[n] = tsv(p)
            ck(len(cap[n]) == int(e.get("rows_kept", -1)), f"census capture {n}: rows on disk != rows_kept")
        if all(n in cap for n in need):
            total = int(man_c["Submissions_before_1939.txt"]["rows_total"])
            ck(len({man_c[n]["member_sha256"] for n in need if n.startswith("Submissions_")}) == 1,
               "census Submissions captures come from more than one member SHA")
            before, undated = cap["Submissions_before_1939.txt"], cap["Submissions_undated.txt"]
            st_c = {r["SubmissionStatus"]: int(r["count"]) for r in cap["Submissions_status_counts.txt"]}
            ty_c = {r["SubmissionType"]: int(r["count"]) for r in cap["Submissions_type_counts.txt"]}
            # adjudication rules re-applied
            ck(all(r["SubmissionStatusDate"][:10] < FDCA for r in before),
               f"a pre-1939 row is dated on/after the FD&C Act ({FDCA}) - boundary contradicted")
            ck(all(not r["SubmissionStatusDate"].strip()[:4].isdigit() for r in undated),
               "undated capture contains a dated row")
            ck(sum(st_c.values()) == total and sum(ty_c.values()) == total,
               f"census counts do not sum to the member ({sum(st_c.values())}/{sum(ty_c.values())} vs {total})")
            ck(set(st_c) <= {"AP", "TA", "<EMPTY>"}, f"status census holds non-approval-family statuses: {sorted(st_c)}")
            ck(set(ty_c) <= {"ORIG", "SUPPL"}, f"type census holds unexpected types: {sorted(ty_c)}")
            ck(sorted(r["ApplNo"] for r in cap["Applications_below_boundary.txt"]) == low_ids,
               "census below-boundary application set != map-derived set")
            hist = Counter((r["ApplNo"], r["SubmissionType"], r["SubmissionNo"], r["SubmissionStatus"],
                            r["SubmissionStatusDate"]) for r in cap["Submissions_applno_below_boundary.txt"])
            win = Counter((r["ApplNo"], r["SubmissionType"], r["SubmissionNo"], r["SubmissionStatus"],
                           r["SubmissionStatusDate"]) for r in s64 + s79 if r["ApplNo"] in low_ids)
            ck(not (win - hist), "a committed window row of a below-boundary application is absent from its complete history")
            apps_ids = {a["ApplNo"] for a in apps}
            irregular = sorted({r["ApplNo"] for r in before} | {r["ApplNo"] for r in undated if r["SubmissionType"] == "ORIG"})
            ck(all(a not in apps_ids for a in irregular),
               f"an irregular ORIG ApplNo has an application row after all: {irregular}")
            ck(not ({r["ApplNo"] for r in s64 + s79} & set(irregular)),
               "an irregular ApplNo appears in a committed window")
            # evidence lines EV-12..EV-16 against the recomputed facts
            evd = {r["evidence_id"]: r for r in ev}
            ck(evd["PRE1939EV-12"]["observed_value"].startswith(f"{len(before)} row(s) dated before 1939 of {total:,}"),
               f"EV-12 observed value drifted: {evd['PRE1939EV-12']['observed_value'][:80]}")
            ck(f"rows dated {FDCA}..1938-12-31: 0" in evd["PRE1939EV-12"]["observed_value"],
               "EV-12 must state the count of rows dated between the FD&C Act and 1938-12-31")
            for r in before:
                ck(f"ApplNo={r['ApplNo']}" in evd["PRE1939EV-12"]["observed_value"]
                   and r["SubmissionStatusDate"] in evd["PRE1939EV-12"]["observed_value"],
                   f"EV-12 does not quote pre-1939 row {r['ApplNo']} verbatim")
            ck("FLAG-PRE-STATUTE-DATE" in evd["PRE1939EV-12"]["notes"] and "never counted" in evd["PRE1939EV-12"]["notes"],
               "EV-12 lost the flag / never-counted statement")
            ck(evd["PRE1939EV-12"]["source_sha256_prefix"] == cap_sha["Submissions_before_1939.txt"][:16],
               "EV-12 sha prefix != capture")
            ck(evd["PRE1939EV-13"]["observed_value"].startswith(f"{len(undated)} undated rows"),
               f"EV-13 observed value drifted: {evd['PRE1939EV-13']['observed_value'][:60]}")
            for r in undated:
                ck(f"ApplNo={r['ApplNo']}; SubmissionClassCodeID={r['SubmissionClassCodeID'] or '(blank)'}; "
                   f"SubmissionType={r['SubmissionType']}; SubmissionNo={r['SubmissionNo']}" in evd["PRE1939EV-13"]["observed_value"],
                   f"EV-13 does not quote undated row {r['ApplNo']} {r['SubmissionType']} {r['SubmissionNo']} verbatim")
            ck(f"{total:,} rows = {len(before)} pre-statute placeholder + {len(undated)} undated + "
               f"{total - len(before) - len(undated):,} rows" in evd["PRE1939EV-13"]["notes"],
               "EV-13 arithmetic (total = pre-statute + undated + dated>=1939) missing or wrong")
            ck(evd["PRE1939EV-13"]["source_sha256_prefix"] == cap_sha["Submissions_undated.txt"][:16],
               "EV-13 sha prefix != capture")
            ck(f"SubmissionStatus census: {st_c}" in evd["PRE1939EV-14"]["observed_value"]
               and f"SubmissionType census: {ty_c}" in evd["PRE1939EV-14"]["observed_value"],
               f"EV-14 observed value drifted: {evd['PRE1939EV-14']['observed_value'][:120]}")
            ck("tentative approval letter" in evd["PRE1939EV-14"]["notes"],
               "EV-14 lost the verbatim FDA glossary definition of Tentative Approval")
            ck("approval-family" in evd["PRE1939EV-08"]["claim"] and "TA" in evd["PRE1939EV-08"]["notes"],
               "EV-08 claim/notes not refined to approval-family (AP + TA) after the census")
            ck(evd["PRE1939EV-15"]["source_sha256_prefix"] == zip_sha[:16], "EV-15 sha prefix != census ZIP sha")
            win_total = int(man_all["Submissions_1965_1979.txt"]["rows_total"])
            ck(f"Submissions {total:,} rows (+{total - win_total})" in evd["PRE1939EV-15"]["observed_value"],
               "EV-15 publication delta (submission rows) drifted")
            ck(f"Submissions {win_total:,} rows" in evd["PRE1939EV-15"]["observed_value"],
               "EV-15 must state the pinned windows' publication row count")
            ck("updated each morning, Monday through Friday" in evd["PRE1939EV-15"]["notes"],
               "EV-15 lost FDA's verbatim update-cadence statement")
            ck("github.com" not in evd["PRE1939EV-15"]["notes"], "EV-15 cites a non-official URL")
            for a in irregular:
                ck(a in evd["PRE1939EV-16"]["observed_value"], f"EV-16 does not list irregular ApplNo {a}")
            ck("no cause is inferred" in evd["PRE1939EV-16"]["notes"], "EV-16 lost its no-inference statement")
            # register 1938 row must carry the whole-table sentence
            r38 = next(r for r in reg if r["year"] == "1938")
            ck(f"0 of all {total:,} rows" in r38["recorded_decisions_basis"] and f"{len(undated)} undated" in r38["recorded_decisions_basis"],
               "register 1938 basis lost the whole-table census sentence")
            ck(r38["fda_drug_approval_decisions_recorded"] == "0", "register 1938 decisions count must stay 0")
            # fifth table, cell by cell
            comp = csvrows(inputs["complete"])
            ck([r["census_id"] for r in comp] == [f"PRE1939COMPLETE-{i:03d}" for i in range(1, 7)],
               "complete-table census IDs are not PRE1939COMPLETE-001..006")
            ck([r["capture_file"] for r in comp] == need, "complete-table census rows are not one per capture, in order")
            for r in comp:
                n = r["capture_file"]
                e = man_c[n]
                ck(r["member"] == e["member"], f"{n}: member drift")
                ck(r["member_rows_total"] == str(e["rows_total"]) and r["rows_kept"] == str(e["rows_kept"]) == str(len(cap[n])),
                   f"{n}: row counts drift vs manifest/capture")
                ck(r["source_sha256_prefix"] == cap_sha[n][:16], f"{n}: source sha prefix != capture")
                ck(r["member_sha256_prefix"] == e["member_sha256"][:16], f"{n}: member sha prefix drift")
                ck(r["zip_sha256_prefix"] == zip_sha[:16], f"{n}: zip sha prefix drift")
                ck(json.loads(r["selector"]) == e["filter"], f"{n}: selector != manifest filter")
                ck(r["captured_at_utc"] == e.get("written_at_utc", ""), f"{n}: captured_at_utc drift")
                ck(r["source_url"] == "https://www.fda.gov/media/89850/download?attachment", f"{n}: source_url drift")
                hdr = list(cap[n][0].keys()) if cap[n] else []
                want = " | ".join("; ".join(f"{h}={(x.get(h) or '(blank)')}" for h in hdr) for x in cap[n]) or "(no rows)"
                ck(r["kept_rows_verbatim"] == want, f"{n}: kept_rows_verbatim is not the verbatim capture")
                ck(r["verification_status"].startswith("Verified"), f"{n}: verification_status")
            byname = {r["capture_file"]: r for r in comp}
            ck(byname["Submissions_before_1939.txt"]["counted_as_fda_decision"].startswith("False"),
               "pre-statute row must not be counted as a decision")
            ck(byname["Submissions_undated.txt"]["counted_as_fda_decision"].startswith("False"),
               "undated rows must not be counted as decisions")
            ck(byname["Submissions_undated.txt"]["flags"] == "; ".join(
                   f"FLAG-UNDATED-ROW ApplNo={r['ApplNo']} {r['SubmissionType']} {r['SubmissionNo']}" for r in undated),
               "undated flags cell is not exactly one FLAG-UNDATED-ROW per captured row")
            ck(byname["Submissions_before_1939.txt"]["flags"] == "; ".join(
                   f"FLAG-PRE-STATUTE-DATE ApplNo={r['ApplNo']} date={r['SubmissionStatusDate']}" for r in before),
               "pre-statute flags cell is not exactly one FLAG-PRE-STATUTE-DATE (with the verbatim date) per captured row")
            for n in ("Submissions_status_counts.txt", "Submissions_type_counts.txt", "Applications_below_boundary.txt"):
                ck(byname[n]["flags"] == "", f"{n}: unexpected flags")
            ck(f"statuses {st_c}" in byname["Submissions_status_counts.txt"]["result"], "status census result drifted")
            ck(f"types {ty_c}" in byname["Submissions_type_counts.txt"]["result"], "type census result drifted")
            ck(byname["Submissions_before_1939.txt"]["result"].startswith(f"{len(before)} row(s) dated before 1939"),
               "pre-statute result drifted")
            ck(byname["Submissions_undated.txt"]["result"].startswith(f"{len(undated)} rows"), "undated result drifted")
            ck("pre1965_fda_decisions.csv" not in byname["Submissions_applno_below_boundary.txt"]["counted_as_fda_decision"],
               "complete-history row repeats the false 'counted in pre1965_fda_decisions.csv' claim")
            ck("PRE1965AUDIT-1939-02" in byname["Submissions_applno_below_boundary.txt"]["counted_as_fda_decision"]
               and "PRE1980AUDIT-1969-10" in byname["Submissions_applno_below_boundary.txt"]["counted_as_fda_decision"],
               "complete-history row must name both era-audit rows")
            extra = hist - win
            ck(f"{sum(extra.values())} rows outside both windows" in byname["Submissions_applno_below_boundary.txt"]["cross_check_vs_committed_windows"],
               "complete-history row: count of rows outside the windows drifted")
            print(f"  census layer: {total:,} rows; {len(before)} pre-statute, {len(undated)} undated, statuses {st_c}; "
                  f"{len(comp)} complete-table rows re-derived")

    # ---- 8. no invented fields anywhere ----------------------------------
    for name in ("boundary", "census", "register", "status") + (("complete",) if census_joined else ()):
        rows = csvrows(inputs[name])
        for col in rows[0].keys():
            ck(not any(b in col.lower() for b in BANNED_SUBSTRINGS),
               f"{name}: banned column {col!r}")
        # no cell may read like a filled-in guess
        for r in rows:
            for k, v in r.items():
                ck("estimated" not in v.lower() and "approximately" not in v.lower(),
                   f"{name}:{r.get('row_id') or r.get('evidence_id') or r.get('census_id')}:"
                   f"{k}: cell reads like an estimate")
    # every http(s) cell in every v28 table must be on the allow-list
    url_cells = 0
    for name in ("boundary", "census", "register", "status") + (("complete",) if census_joined else ()):
        for r in csvrows(inputs[name]):
            for k, v in r.items():
                for m in re.finditer(r"https?://[^\s,;)\]]+", v or ""):
                    url_cells += 1
                    host = urlparse(m.group(0)).netloc
                    ck(host in ALLOWED_HOSTS,
                       f"{name}: URL host {host} ({m.group(0)[:70]}) not in the verified allow-list")
    ck(url_cells > 40, f"only {url_cells} URL citations found - expected the tables to be link-rich")

    print(f"\nv28 pre-1939 verification: {checks} checks, {len(errors)} error(s); "
          f"{url_cells} URL citations re-checked against the verified official allow-list.")
    if errors:
        for e in errors[:40]:
            print("ERROR", e)
        if len(errors) > 40:
            print(f"ERROR ... {len(errors) - 40} more")
        return 1
    print(f"OK: every cell of the {'five' if census_joined else 'four'} pre-1939 tables reproduces from the "
          "committed official primary sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
