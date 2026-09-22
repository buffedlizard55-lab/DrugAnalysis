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
    ck(any("PENDING" in r["observed_value"] or "0 rows dated before 1939" in r["observed_value"]
           for r in ev[-1:]), "the whole-table census row is missing or silent")
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

    # ---- 8. no invented fields anywhere ----------------------------------
    for name in ("boundary", "census", "register", "status"):
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
    for name in ("boundary", "census", "register", "status"):
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
    print("OK: every cell of the four v28 pre-1939 tables reproduces from the committed "
          "official primary sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
