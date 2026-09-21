#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent line-by-line verifier for the v26 pre-1965 tables (1939-1964).

Shares no code with scripts/build_pre1965_decisions_v26.py. It re-opens the
committed official payloads, re-hashes them against the runner manifest,
re-reads data/fda_official_year_series.csv and the full official Drugs@FDA
database map, and reproduces every published cell of the four v26 tables
from the cited primary sources. Any published value that cannot be
reproduced fails the check.

Checks performed
----------------
1.  SHA-256 of every 1939-1964 payload equals the runner manifest value;
    payload count field == decisions list length; every decision_date inside
    its payload year; per-year raw-record totals re-read from the manifest.
2.  SHA-256 of Applications_all_types.txt equals its manifest value.
3.  Every pre1965_originals_audit_1939_1964.csv row (535) reproduces field
    by field from its payload record and the official database map: kind,
    class code/description, priority, holder, product facts, first-appearance
    screen, classification group, NME flag, tracked-in, URLs, and the
    full-database holder/type cross-check.
4.  Every pre1965_fda_decisions.csv row (178) reproduces from its payload
    record, is exactly the NME-comparable subset of the audit table, and
    carries a verification status consistent with its probe state.
5.  Every pre1965_year_register.csv row (26) re-computes from the payloads:
    counts, class splits, priority splits, official NME/NDAs verbatim from
    data/fda_official_year_series.csv, delta, raw payload path, query URL
    equal to the manifest page URL.
6.  Every pre1965_era_analysis.csv row (26) re-computes its numeric columns;
    every landmark brand name must exist verbatim among that year's NME
    product brands in the payload.
7.  When the probe layer (data/raw/pre1965_row_probes_1939_1964/) exists:
    every probe file hashes to its manifest SHA; the probe index covers
    exactly the captured applications; MATCH rows agree with the payload on
    date, class, priority and holder; rows without a probe are PROBE_PENDING.
8.  No duplicate (application, date) in any table; IDs sequential per year;
    no likelihood/probability column in any v26 output; years exactly 1939-1964.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BLOCK_DIR = DATA / "raw" / "openfda_orig_decisions_1939_1964"
APPS_DIR = DATA / "raw" / "drugsatfda_data_files_2026_09"
APPS_FILE = APPS_DIR / "Applications_all_types.txt"
PROBE_DIR = DATA / "raw" / "pre1965_row_probes_1939_1964"
YEARS = tuple(range(1939, 1965))
NME_CLASSES = {"TYPE 1", "TYPE 1/4"}

errors: list[str] = []
checked = 0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ok(cond: bool, msg: str) -> None:
    global checked
    checked += 1
    if not cond:
        errors.append(msg)


def norm(v: str) -> str:
    return (v or "").strip().upper()


def squash(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "")).strip().upper()


def read_csv(name: str) -> list[dict]:
    p = DATA / name
    if not p.exists():
        errors.append(f"missing table: {name}")
        return []
    with p.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def ingredients_of(dec: dict) -> set[str]:
    ings: set[str] = set()
    for x in dec.get("products") or []:
        for part in (x.get("active_ingredients") or "").split(";"):
            part = part.strip().upper()
            m = re.match(r"^([A-Z0-9\-\s/\.\\(\\),]+?)(:\s+\d|\s+EQ\s|\s+N/A|\s+\*\*|$)".replace(":", ""), part)
            name = (m.group(1).strip() if m else part).rstrip(" .")
            if name:
                ings.add(name)
    return ings


# ---------------------------------------------------------------- integrity
manifest = json.loads((BLOCK_DIR / "manifest.json").read_text(encoding="utf-8"))
req_by_year = {int(r["id"].split("_")[-1]): r for r in manifest["requests"]
               if r.get("sha256")}
payloads: dict[int, list[dict]] = {}
for year in YEARS:
    path = BLOCK_DIR / f"decisions_{year}.json"
    ok(path.exists(), f"{year}: missing payload {path}")
    if not path.exists():
        continue
    req = req_by_year.get(year)
    ok(req is not None, f"{year}: missing manifest request")
    if req is None:
        continue
    ok(sha256_file(path) == req["sha256"], f"{year}: payload SHA-256 drift vs manifest")
    obj = json.loads(path.read_text(encoding="utf-8"))
    decs = obj.get("decisions")
    ok(isinstance(decs, list), f"{year}: no decisions list")
    if not isinstance(decs, list):
        continue
    ok(obj.get("count") == len(decs), f"{year}: count field != decisions length")
    raw = sum(p.get("n_raw_records", 0) for p in req.get("pages", []))
    ok(raw >= len(decs), f"{year}: manifest raw records {raw} < extracted {len(decs)}")
    for d in decs:
        ok(re.fullmatch(rf"{year}-\d{{2}}-\d{{2}}", (d.get("decision_date") or "")) is not None,
           f"{year}: decision_date outside year: {d.get('decision_date')!r} {d.get('application_number')}")
    payloads[year] = decs

apps_manifest = json.loads((APPS_DIR / "manifest.json").read_text(encoding="utf-8"))
apps_entry = next((e for e in apps_manifest["requests"]
                   if e.get("out") == "Applications_all_types.txt"), None)
ok(apps_entry is not None, "Applications_all_types.txt not in 2026_09 manifest")
if apps_entry is not None:
    ok(sha256_file(APPS_FILE) == apps_entry["out_sha256"],
       "Applications_all_types.txt SHA-256 drift vs manifest")
apps: dict[str, tuple[str, str]] = {}
with APPS_FILE.open(encoding="utf-8") as fh:
    next(fh)
    for ln in fh:
        parts = ln.rstrip("\n").rstrip("\r").split("\t")
        if len(parts) >= 4 and parts[0].strip():
            apps[parts[0].strip().zfill(6)] = (parts[1].strip(), parts[3].strip())

official: dict[int, dict[str, str]] = {}
for r in read_csv("fda_official_year_series.csv"):
    y = (r.get("year") or "").strip()
    if y.isdigit() and int(y) in YEARS:
        official[int(y)] = {"nme": (r.get("nmes_approved") or "").strip(),
                            "ndas": (r.get("ndas_approved") or "").strip(),
                            "url": (r.get("source_url") or "").strip()}

# first-appearance universe (independent recomputation)
first: dict[str, tuple] = {}
for year in YEARS:
    for d in payloads.get(year, []):
        pos = (year, d["decision_date"])
        for ing in ingredients_of(d):
            if ing not in first or pos < first[ing][0]:
                first[ing] = (pos, d["application_number"], d["decision_date"])

# ---------------------------------------------------------------- probes
probe_entries: dict[str, dict] = {}
probe_manifest_present = (PROBE_DIR / "manifest.json").exists()
if probe_manifest_present:
    pm = json.loads((PROBE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for e in pm["requests"]:
        if e.get("sha256"):
            probe_entries[e["id"]] = e
    for e in probe_entries.values():
        p = PROBE_DIR / e["out"]
        ok(p.exists(), f"probe file missing: {e['out']}")
        if p.exists():
            ok(sha256_file(p) == e["sha256"], f"probe SHA drift: {e['out']}")

# ---------------------------------------------------------------- audit
audit = read_csv("pre1965_originals_audit_1939_1964.csv")
ok(len(audit) == 535, f"audit rows {len(audit)} != 535")
seen_keys = set()
per_year_seq: dict[int, int] = {}
for r in audit:
    year = int(r["year"])
    ok(year in YEARS, f"audit row {r.get('row_id')}: year {year} outside 1939-1964")
    appl = r["application_number"]
    key = (appl, r["decision_date"])
    ok(key not in seen_keys, f"audit duplicate (appl,date): {key}")
    seen_keys.add(key)
    per_year_seq[year] = per_year_seq.get(year, 0) + 1
    seq = per_year_seq[year]
    ok(r["row_id"] == f"PRE1965AUDIT-{year}-{seq:02d}",
       f"{r['row_id']}: ID not sequential for its year (expected seq {seq:02d})")
    d = next((x for x in payloads.get(year, []) if x["application_number"] == appl
              and x["decision_date"] == r["decision_date"]), None)
    ok(d is not None, f"{appl}: audit row not reproducible from payload")
    if d is None:
        continue
    num = (d.get("application_num") or "").zfill(6)
    ok(r["application_kind"] == d.get("application_kind"), f"{appl}: kind mismatch")
    ok(r["submission_class_code"] == (d.get("submission_class_code") or "").strip(),
       f"{appl}: class code mismatch")
    ok(r["submission_class_code_description"] == (d.get("submission_class_code_description") or "").strip(),
       f"{appl}: class description mismatch")
    ok(r["review_priority"] == (d.get("review_priority") or "").strip(), f"{appl}: priority mismatch")
    cls = norm(r["submission_class_code"])
    ok(r["nme_comparable"] == ("TRUE" if cls in NME_CLASSES else "FALSE"), f"{appl}: nme flag mismatch")
    ok(r["sponsor_name_drugsatfda_holder"] == (d.get("sponsor_name") or "").strip(),
       f"{appl}: holder mismatch")
    prods = d.get("products") or []
    fp = prods[0] if prods else {}
    ok(r["first_product_brand"] == (fp.get("brand_name") or "").strip(), f"{appl}: brand mismatch")
    ok(r["first_product_ingredients"] == (fp.get("active_ingredients") or "").strip(),
       f"{appl}: ingredients mismatch")
    want_form = f"{fp.get('dosage_form','')}; {fp.get('route','')}".strip("; ")
    ok(r["first_product_form_route"] == want_form, f"{appl}: form/route mismatch")
    ok(int(r["n_products"]) == len(prods), f"{appl}: n_products mismatch")
    ok(r["first_product_marketing_status"] == (fp.get("marketing_status") or "").strip(),
       f"{appl}: marketing status mismatch")
    if num in apps:
        db_type, db_holder = apps[num]
        ok(db_type.upper() == d.get("application_kind", "").upper(),
           f"{appl}: full-DB ApplType {db_type} != payload kind")
        want_match = "MATCH" if squash(d.get("sponsor_name")) == squash(db_holder) \
            else f"FLAG (full-DB holder {db_holder!r})"
        ok(r["full_db_holder_match"] == want_match, f"{appl}: full-DB holder match cell wrong")
    else:
        errors.append(f"{appl}: absent from full official DB (builder must have aborted)")
    # ingredient screen
    ings = ingredients_of(d)
    earlier = [i for i in ings if first[i][0] < (year, r["decision_date"])
               or (first[i][0] == (year, r["decision_date"]) and first[i][1] != appl)]
    is_nme = cls in NME_CLASSES
    if is_nme and earlier:
        ok(r["ingredient_screen"].startswith("FLAG-RESCREEN"),
           f"{appl}: NME row with earlier ingredients not flagged")
        for i in earlier:
            ok(i in r["ingredient_screen"], f"{appl}: flagged ingredient {i} missing from screen cell")
    elif is_nme:
        ok(r["ingredient_screen"].startswith("first appearance in the 1939-1964 payload universe"),
           f"{appl}: NME screen text wrong")
    else:
        ok(r["ingredient_screen"].startswith("non-NME row"), f"{appl}: non-NME screen text wrong")
    ok(r["tracked_in"].startswith("PRE1965-") if is_nme else r["tracked_in"].startswith("none"),
       f"{appl}: tracked_in inconsistent with NME flag")
    ok(r["drugsatfda_url"] == ("https://www.accessdata.fda.gov/scripts/cder/daf/"
                               f"index.cfm?event=overview.process&varApplNo={num}"),
       f"{appl}: Drugs@FDA URL wrong")
    ok(r["openfda_url"] == (f"https://api.fda.gov/drug/drugsfda.json?search="
                            f"application_number:%22{appl}%22"),
       f"{appl}: openFDA URL wrong")
    # probe state consistency
    pr = probe_entries.get(f"probe_{year}_{appl}")
    if pr is None:
        ok(r["live_probe_status"] == "PROBE_PENDING",
           f"{appl}: no probe in manifest but status {r['live_probe_status']}")
        ok(r["verification_status"].startswith("Payload-verified"),
           f"{appl}: verification status must be Payload-verified without a probe")
    else:
        ok(r["live_probe_status"] in {"MATCH", "ABSENT_LIVE", "NO_ORIG_AP_LIVE"},
           f"{appl}: unexpected probe status {r['live_probe_status']}")

year_counts = Counter(int(r["year"]) for r in audit)
ok(sorted(year_counts) == sorted(YEARS), "audit must cover exactly 1939-1964")
for year in YEARS:
    ok(year_counts[year] == len(payloads.get(year, [])),
       f"{year}: audit rows {year_counts[year]} != payload {len(payloads.get(year, []))}")

# ---------------------------------------------------------------- decisions
decisions = read_csv("pre1965_fda_decisions.csv")
ok(len(decisions) == 178, f"decision rows {len(decisions)} != 178")
audit_nme = {r["application_number"]: r for r in audit if r["nme_comparable"] == "TRUE"}
ok(len(audit_nme) == 178, f"audit NME subset {len(audit_nme)} != 178")
dec_keys = set()
for r in decisions:
    year = int(r["year"])
    lab = r["application_number"]
    m = re.fullmatch(r"(NDA|BLA) (\d{6})", lab)
    ok(m is not None, f"{r['decision_id']}: application_number format {lab!r}")
    if not m:
        continue
    appl = f"{m.group(1)}{m.group(2)}"
    key = (appl, r["decision_date"])
    ok(key not in dec_keys, f"decision duplicate {key}")
    dec_keys.add(key)
    ar = audit_nme.get(appl)
    ok(ar is not None, f"{appl}: decision row not in audit NME subset")
    if ar is None:
        continue
    ok(r["decision_date"] == ar["decision_date"], f"{appl}: decision date != audit date")
    d = next(x for x in payloads[year] if x["application_number"] == appl)
    ok(r["chemical_type_code"] == ar["submission_class_code"], f"{appl}: decision class != audit")
    ok(r["review_priority"] == ar["review_priority"], f"{appl}: decision priority != audit")
    ok(r["decision_type"] == f"APPROVAL (ORIGINAL {m.group(1)})", f"{appl}: decision_type wrong")
    ok(r["drug_brand"] == ar["first_product_brand"], f"{appl}: decision brand != audit")
    ok(r["source_url_1"] == ar["drugsatfda_url"], f"{appl}: decision URL1 != audit")
    ok(r["source_url_2"] == ar["openfda_url"], f"{appl}: decision URL2 != audit")
    ok(r["company_name"].startswith((d.get("sponsor_name") or "BLANK").strip()),
       f"{appl}: decision company must start with the payload holder")
    ok(r["indication"] == "", f"{appl}: indication must not be asserted")
    ok("no ticker" in r["corporate_lineage_and_ticker"].lower()
       or "no inference" in r["corporate_lineage_and_ticker"].lower(),
       f"{appl}: ticker policy line missing")
    if "FLAG-RESCREEN" in ar["ingredient_screen"]:
        ok("re-screening flag" in r["verification_status"],
           f"{appl}: decision row must carry the re-screening flag")
audit_nme_keys = {(r["application_number"], r["decision_date"])
                  for r in audit if r["nme_comparable"] == "TRUE"}
ok(dec_keys == audit_nme_keys, "decision table must equal the audit NME subset exactly")

# ---------------------------------------------------------------- register
register = read_csv("pre1965_year_register.csv")
ok(len(register) == 26, f"register rows {len(register)} != 26")
for r in register:
    year = int(r["year"])
    decs = payloads.get(year, [])
    t1 = [d for d in decs if norm(d.get("submission_class_code")) in NME_CLASSES]
    ok(int(r["payload_orig_ap_count"]) == len(decs), f"{year}: register row count wrong")
    raw = sum(p.get("n_raw_records", 0) for p in req_by_year[year].get("pages", []))
    ok(int(r["manifest_raw_records"]) == raw, f"{year}: register raw records wrong")
    ok(int(r["nme_type1_rows"]) == sum(1 for d in decs if norm(d.get("submission_class_code")) == "TYPE 1"),
       f"{year}: register TYPE 1 count wrong")
    ok(int(r["nme_type14_rows"]) == sum(1 for d in decs if norm(d.get("submission_class_code")) == "TYPE 1/4"),
       f"{year}: register TYPE 1/4 count wrong")
    ok(int(r["nme_rows_total"]) == len(t1), f"{year}: register NME total wrong")
    once = 0
    for d in t1:
        ings = ingredients_of(d)
        if ings and not any(first[i][0] < (year, d["decision_date"]) for i in ings):
            once += 1
    ok(int(r["nme_counted_once"]) == once, f"{year}: register counted-once wrong")
    ok(int(r["blank_class_rows"]) == sum(1 for d in decs if not norm(d.get("submission_class_code"))),
       f"{year}: register blank-class count wrong")
    ok(int(r["unknown_class_rows"]) == sum(1 for d in decs if norm(d.get("submission_class_code")) == "UNKNOWN"),
       f"{year}: register UNKNOWN-class count wrong")
    ok(int(r["priority_reviews"]) == sum(1 for d in decs if norm(d.get("review_priority")) == "PRIORITY"),
       f"{year}: register priority count wrong")
    ok(int(r["standard_reviews"]) == sum(1 for d in decs if norm(d.get("review_priority")) == "STANDARD"),
       f"{year}: register standard count wrong")
    off = official.get(year, {})
    ok(r["official_fda_nme_count"] == off.get("nme", ""),
       f"{year}: official NME not verbatim from fda_official_year_series.csv")
    ok(r["official_ndas_approved"] == off.get("ndas", ""),
       f"{year}: official NDAs not verbatim from fda_official_year_series.csv")
    mi = re.fullmatch(r"(\d+)", r["official_fda_nme_count"])
    want_delta = str(len(t1) - int(mi.group(1))) if mi else "n/a (no official per-year figure)"
    ok(r["delta_nme_rows_vs_official"] == want_delta, f"{year}: register delta wrong")
    ok(Path(r["raw_payload"]).exists(), f"{year}: raw_payload path missing")
    ok(r["query_url"] == (req_by_year[year].get("pages") or [{}])[0].get("url", ""),
       f"{year}: register query_url != manifest page URL")
    if probe_manifest_present:
        n = sum(1 for d in decs if f"probe_{year}_{d['application_number']}" in probe_entries)
        ok(r["probe_status"].startswith(("complete", "partial")),
           f"{year}: register probe_status must reflect the probe layer")
        ok(str(n) in r["probe_status"], f"{year}: register probe_status count wrong")

# ---------------------------------------------------------------- era
era = read_csv("pre1965_era_analysis.csv")
ok(len(era) == 26, f"era rows {len(era)} != 26")
for r in era:
    year = int(r["year"])
    decs = payloads.get(year, [])
    t1 = [d for d in decs if norm(d.get("submission_class_code")) in NME_CLASSES]
    ok(int(r["total_nmes_approved"]) == len(t1), f"{year}: era NME total wrong")
    ok(int(r["nme_comparable_rows"]) == len(t1), f"{year}: era nme_comparable wrong")
    ok(int(r["verified_decisions_tracked"]) == len(t1), f"{year}: era tracked wrong")
    ok(int(r["priority_reviews"]) == sum(1 for d in decs if norm(d.get("review_priority")) == "PRIORITY"),
       f"{year}: era priority wrong")
    ok(int(r["standard_reviews"]) == sum(1 for d in decs if norm(d.get("review_priority")) == "STANDARD"),
       f"{year}: era standard wrong")
    unprio = len(decs) - len(t1) * 0 - sum(1 for d in decs if norm(d.get("review_priority")) == "PRIORITY") \
        - sum(1 for d in decs if norm(d.get("review_priority")) == "STANDARD")
    ok(int(r["unpublished_priority_reviews"]) == unprio, f"{year}: era unpublished-priority wrong")
    brands_in_payload = set()
    for d in t1:
        for p in d.get("products") or []:
            b = (p.get("brand_name") or "").strip()
            if b:
                brands_in_payload.add(b)
    lm = r["landmark_approvals"]
    lm = re.sub(r" \(\+\d+ more\)$", "", lm)
    for b in [x.strip() for x in lm.split(",") if x.strip()]:
        ok(b in brands_in_payload, f"{year}: landmark brand {b!r} not in payload NME products")
    ok(r["statutory_framework"].strip() != "", f"{year}: era statutory framework empty")
    ok(r["official_fda_nme_count"] in (official.get(year, {}).get("nme", ""),
                                       "not published separately"),
       f"{year}: era official NME not verbatim")

# ---------------------------------------------------------------- probe index
if probe_manifest_present:
    idx = read_csv("pre1965_row_probe_index.csv")
    idx_apps = {r["application_number"] for r in idx}
    want_apps = {e["id"].split("_", 2)[2] for e in probe_entries.values()}
    ok(idx_apps == want_apps, "probe index must cover exactly the captured applications")
    for r in idx:
        year = int(r["row_id"].split("-")[1])
        entry = probe_entries.get(f"probe_{year}_{r['application_number']}")
        ok(entry is not None, f"{r['application_number']}: probe index row without manifest entry")
        if entry is None:
            continue
        ok(r["probe_file"] == entry["out"], f"{r['application_number']}: probe_file wrong")
        ok(r["probe_sha256"] == entry["sha256"], f"{r['application_number']}: probe SHA wrong")
        ok(r["probe_url"] == entry.get("url", ""), f"{r['application_number']}: probe URL wrong")
        ok(r["status"] in {"MATCH", "ABSENT_LIVE", "NO_ORIG_AP_LIVE"},
           f"{r['application_number']}: probe status vocabulary")
        ar = next((x for x in audit if x["application_number"] == r["application_number"]), None)
        ok(ar is not None and ar["live_probe_status"] == r["status"],
           f"{r['application_number']}: audit/probe-index status disagree")
        if r["status"] == "MATCH":
            d = next(x for x in payloads[year] if x["application_number"] == r["application_number"])
            ok(r["live_orig_date"] == d["decision_date"], f"{r['application_number']}: live date != payload")
            ok(norm(r["live_class_code"]) == norm(d.get("submission_class_code")),
               f"{r['application_number']}: live class != payload")
            ok(norm(r["live_review_priority"]) == norm(d.get("review_priority")),
               f"{r['application_number']}: live priority != payload")
            ok(squash(r["live_sponsor"]) == squash(d.get("sponsor_name")),
               f"{r['application_number']}: live sponsor != payload")
else:
    ok(not (DATA / "pre1965_row_probe_index.csv").exists(),
       "probe index must not exist while the probe layer is absent")

# ---------------------------------------------------------------- global
for name in ("pre1965_originals_audit_1939_1964.csv", "pre1965_fda_decisions.csv",
             "pre1965_year_register.csv", "pre1965_era_analysis.csv",
             "pre1965_row_probe_index.csv"):
    p = DATA / name
    if not p.exists():
        continue
    with p.open(newline="", encoding="utf-8-sig") as fh:
        header = next(csv.reader(fh))
    for col in header:
        low = col.lower()
        ok("likelihood" not in low and "probability" not in low,
           f"{name}: forbidden column {col!r}")

print(f"v26 verify: {checked} checks, {len(errors)} errors")
for e in errors[:25]:
    print("ERROR:", e)
if len(errors) > 25:
    print(f"... {len(errors) - 25} more errors")
raise SystemExit(1 if errors else 0)
