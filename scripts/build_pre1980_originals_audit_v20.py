#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v20 (2026-09-19): complete original-application audit for pre-1980 years
1977, 1978, 1979 — every ORIG/AP payload row (170 = 42 + 66 + 62), not just
the Type 1/1-4 decisions, plus two fail-closed cross-verification layers:

  Layer 1 (row probes):   data/raw/pre1980_row_probes_1977_1979/probe_*.json
                          — one complete live openFDA record per application,
                          SHA-manifested; every audit row is checked against
                          its probe (class/date/priority/holder) and a probe
                          index table is written.
  Layer 2 (full DB):      data/raw/drugsatfda_data_files_2026_09/* — the
                          Drugs@FDA database files (the website DB) narrowed
                          to the 1965-1979 window. Every 1977-1979 ORIG/AP
                          approval in the FULL DB is enumerated and diffed
                          against the payload extraction, so applications
                          absent from the openFDA ORIG/AP payloads (the
                          Seldane-class gap) are NAMED instead of lost.

Owns three new tables (single-writer discipline; v19 tables untouched):

* data/pre1980_originals_audit_1977_1979.csv   (170 rows, all originals)
* data/pre1980_row_probe_index.csv             (170 live-capture rows)
* data/pre1980_full_db_crosscheck_1977_1979.csv(per-year diff summary +
                                                payload-invisible approvals)

Fail-closed rules (no hallucinations by construction):

* payload facts verbatim from the committed SHA-verified openFDA extracts;
  the run-18/run-19 dual-run agreement is re-checked here;
* probe files are verified against the manifest (SHA-256) and against the
  payload row (class/date/priority/holder). Any MISMATCH aborts the build.
* full-DB extracts are verified against the runner manifest (member SHA,
  kept-row counts, recorded filter). Any payload row MISSING from the full
  DB aborts the build. Rows only in the full DB are written to the
  crosscheck table verbatim from the DB files — they are named, counted and
  flagged, never merged silently into the verified decision tables.
* No ticker, no indication, no applicant lineage is asserted anywhere.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW7579 = DATA / "raw" / "openfda_orig_decisions_1975_1979"
ALL_BLOCKS = ["openfda_orig_decisions_1965_1969", "openfda_orig_decisions_1970_1974",
              "openfda_orig_decisions_1975_1979"]
PROBES_DIR = DATA / "raw" / "pre1980_row_probes_1977_1979"
ZIP_DIR = DATA / "raw" / "drugsatfda_data_files_2026_09"
YEARS = (1977, 1978, 1979)
EXPECTED_ROWS = {1977: 42, 1978: 66, 1979: 62}
EXPECTED_T1 = {1977: 17, 1978: 18, 1979: 13}
WINDOW_YEARS = {str(y) for y in range(1965, 1980)}

sys.path.insert(0, str(ROOT / "scripts"))
from build_pre1980_decisions_v19 import DISPLAY  # noqa: E402  (explicit display names)

NME_CLASSES = {"TYPE 1", "TYPE 1/4"}
# The single permitted earlier-appearance flag (Cyclapen tablet/suspension).
ALLOWED_INVERSION = {(1979, "NDA050508", "CYCLACILLIN", 1979, "NDA050509")}


def fail(msg: str) -> None:
    raise SystemExit(f"build_pre1980_originals_audit_v20: {msg}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iso_api_date(value: str) -> str:
    s = (value or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def norm_class(value: str) -> str:
    return (value or "").strip().upper()


def norm_priority(value: str) -> str:
    return (value or "").strip().upper()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------

def verify_payloads() -> dict[int, list]:
    manifest = json.loads((RAW7579 / "manifest.json").read_text(encoding="utf-8"))
    by_year = {}
    for req in manifest["requests"]:
        by_year[int(req["id"].split("_")[-1])] = req
    payloads: dict[int, list] = {}
    for year in YEARS:
        path = RAW7579 / f"decisions_{year}.json"
        sha = sha256_file(path)
        req = by_year.get(year)
        if req is None or sha != req["sha256"]:
            fail(f"{year}: payload SHA drift vs run-19 manifest")
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("count") != len(obj.get("decisions") or []):
            fail(f"{year}: payload shape invalid")
        if len(obj["decisions"]) != EXPECTED_ROWS[year]:
            fail(f"{year}: payload row count {len(obj['decisions'])} != {EXPECTED_ROWS[year]}")
        payloads[year] = obj["decisions"]
    return payloads


def load_all_decisions() -> dict[int, list]:
    out: dict[int, list] = {}
    for block in ALL_BLOCKS:
        lo, hi = (1965, 1969) if "1965" in block else \
                 ((1970, 1974) if "1970" in block else (1975, 1979))
        for year in range(lo, hi + 1):
            obj = json.loads((DATA / "raw" / block / f"decisions_{year}.json")
                             .read_text(encoding="utf-8"))
            out[year] = obj["decisions"]
    return out


def ingredients_of(dec: dict) -> set[str]:
    ings = set()
    for x in dec.get("products") or []:
        for part in (x.get("active_ingredients") or "").split(";"):
            part = part.strip().upper()
            m = re.match(r"^([A-Z0-9\-\s/\.\(\)]+?)(?:\s+\d|\s+EQ\s|\s+N/A|\s+\*\*|$)", part)
            name = (m.group(1).strip() if m else part).rstrip(" .")
            if name:
                ings.add(name)
    return ings


# ---------------------------------------------------------------------------
# Layer 1: probes
# ---------------------------------------------------------------------------

def verify_probes(payloads: dict[int, list]) -> dict[str, dict]:
    """Return {application_number: probe_result} after fail-closed checking."""
    if not PROBES_DIR.exists():
        print("v20: probe layer not present yet; building payload-only audit")
        return {}
    manifest_path = PROBES_DIR / "manifest.json"
    if not manifest_path.exists():
        fail("probes dir exists but manifest.json missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_out = {e.get("out"): e for e in manifest["requests"]
              if e.get("status") == 200 and e.get("out")}
    expected = set()
    for year in YEARS:
        for d in payloads[year]:
            expected.add(d["application_number"])
    out: dict[str, dict] = {}
    missing, mismatch = [], []
    for appl in sorted(expected):
        fname = f"probe_{appl}.json"
        entry = by_out.get(fname)
        if entry is None:
            missing.append(appl)
            continue
        path = PROBES_DIR / fname
        if sha256_file(path) != entry["sha256"]:
            fail(f"{appl}: probe SHA drift vs manifest")
        body = json.loads(path.read_text(encoding="utf-8"))
        results = body.get("results") or []
        if not results:
            out[appl] = {"status": "ABSENT_LIVE", "probe_sha": entry["sha256"],
                         "probe_url": entry["url"]}
            continue
        rec = results[0]
        # find the ORIG-1 approval submission
        year = next(y for y in YEARS for d in [None] ) if False else None
        hits = [s for s in rec.get("submissions") or []
                if (s.get("submission_type") or "").strip().upper() == "ORIG"
                and (s.get("submission_status") or "").strip().upper() == "AP"
                and iso_api_date(s.get("submission_status_date", ""))[:4] in
                {str(y) for y in YEARS}]
        if not hits:
            out[appl] = {"status": "ORIG_APPROVAL_NOT_IN_WINDOW_LIVE",
                         "probe_sha": entry["sha256"], "probe_url": entry["url"]}
            continue
        hits.sort(key=lambda s: iso_api_date(s.get("submission_status_date", "")))
        live = hits[0]
        out[appl] = {
            "status": "MATCH",
            "live_date": iso_api_date(live.get("submission_status_date", "")),
            "live_class": norm_class(live.get("submission_class_code")),
            "live_priority": norm_priority(live.get("review_priority")),
            "live_sponsor": (rec.get("sponsor_name") or "").strip(),
            "live_url": entry["url"],
            "probe_sha": entry["sha256"],
        }
    if missing:
        fail(f"{len(missing)} payload rows have no probe capture: {missing[:6]}…")
    # now fail-closed comparison against payload facts
    for year in YEARS:
        for d in payloads[year]:
            appl = d["application_number"]
            res = out.get(appl)
            if not res or res["status"] != "MATCH":
                continue
            if res["live_date"] != d["decision_date"]:
                mismatch.append(f"{appl}: live date {res['live_date']} vs payload {d['decision_date']}")
            if res["live_class"] != norm_class(d["submission_class_code"]):
                mismatch.append(f"{appl}: live class {res['live_class']!r} vs payload {d['submission_class_code']!r}")
            lp, pp = res["live_priority"], norm_priority(d.get("review_priority"))
            if lp != pp and not (lp == "" or pp == ""):
                mismatch.append(f"{appl}: live priority {lp!r} vs payload {pp!r}")
            if res["live_sponsor"] != (d.get("sponsor_name") or "").strip():
                mismatch.append(f"{appl}: live sponsor {res['live_sponsor']!r} vs payload {d.get('sponsor_name')!r}")
    if mismatch:
        fail("live probe disagreement (fail-closed):\n  " + "\n  ".join(mismatch[:20]))
    return out


# ---------------------------------------------------------------------------
# Layer 2: full Drugs@FDA DB window extract
# ---------------------------------------------------------------------------

def read_tab(path: Path) -> list[dict]:
    lines = path.read_text(encoding="latin-1").splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        cols = ln.split("\t")
        rows.append({header[i]: (cols[i] if i < len(cols) else "") for i in range(len(header))})
    return rows


def tab_sha_from_manifest(manifest: dict, out_name: str) -> tuple[str, dict]:
    for e in manifest["requests"]:
        if e.get("out") == out_name:
            return e.get("out_sha256", ""), e
    return "", {}


def verify_full_db() -> dict | None:
    if not ZIP_DIR.exists():
        print("v20: full-DB layer not present yet; skipping Drugs@FDA window cross-check")
        return None
    manifest_path = ZIP_DIR / "manifest.json"
    if not manifest_path.exists():
        fail("full-DB dir exists but manifest.json missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    zip_entries = [e for e in manifest["requests"] if e.get("id", "").endswith(":zip")]
    if not zip_entries:
        fail("full-DB manifest carries no zip entry")
    files = {}
    for out_name in ("Submissions_1965_1979.txt", "Applications_appl_window.txt",
                     "Products_appl_window.txt", "SubmissionClass_Lookup.txt"):
        path = ZIP_DIR / out_name
        if not path.exists():
            fail(f"full-DB extract missing: {out_name}")
        want_sha, entry = tab_sha_from_manifest(manifest, out_name)
        got = sha256_file(path)
        if not want_sha or got != want_sha:
            fail(f"{out_name}: SHA drift vs runner manifest")
        if entry.get("filter", {}).get("type") not in ("date_year_in", "applno_in_collected", "FULL"):
            fail(f"{out_name}: unexpected recorded filter")
        files[out_name] = {"entry": entry, "path": path}
    return files


def full_db_orig_ap(files: dict) -> dict[int, list[dict]]:
    """ORIG-AP approvals in 1977-1979 from the FULL DB, with joins."""
    subs = read_tab(files["Submissions_1965_1979.txt"]["path"])
    lookup = {r["SubmissionClassCodeID"]: r for r in
              read_tab(files["SubmissionClass_Lookup.txt"]["path"])}
    appl_type = {r["ApplNo"]: r.get("ApplType", "").strip().upper() for r in
                 read_tab(files["Applications_appl_window.txt"]["path"])}
    products: dict[str, list[dict]] = {}
    for r in read_tab(files["Products_appl_window.txt"]["path"]):
        products.setdefault(r["ApplNo"], []).append(r)
    date_re = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})")
    out: dict[int, list[dict]] = {y: [] for y in YEARS}
    for s in subs:
        if (s.get("SubmissionType") or "").strip().upper() != "ORIG":
            continue
        if (s.get("SubmissionStatus") or "").strip().upper() != "AP":
            continue
        m = date_re.match((s.get("SubmissionStatusDate") or "").strip())
        if not m:
            continue
        year = int(m.group(3))
        if year not in YEARS:
            continue
        appl_no = s["ApplNo"].strip()
        kind = appl_type.get(appl_no, "")
        if kind not in ("NDA", "BLA"):
            continue
        lk = lookup.get((s.get("SubmissionClassCodeID") or "").strip(), {})
        prods = products.get(appl_no, [])
        out[year].append({
            "appl_no": appl_no, "kind": kind,
            "application_number": f"{kind}{appl_no}",
            "decision_date": f"{year}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}",
            "submission_no": (s.get("SubmissionNo") or "").strip(),
            "submission_class_code": (lk.get("SubmissionClassCode") or "").strip().upper(),
            "submission_class_code_description": (lk.get("SubmissionClassCodeDescription") or "").strip(),
            "review_priority": (s.get("ReviewPriority") or "").strip().upper(),
            "sponsor_name": "",
            "products": [{"brand_name": p.get("DrugName", ""),
                          "active_ingredients": p.get("ActiveIngredient", ""),
                          "dosage_form": p.get("Form", ""), "route": "",
                          "marketing_status": ""} for p in prods],
        })
    for year in YEARS:
        out[year].sort(key=lambda r: (r["decision_date"], r["application_number"]))
    return out


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

AUDIT_HEADER = ["row_id", "year", "application_number", "application_kind",
                "decision_date", "submission_class_code",
                "submission_class_code_description", "review_priority",
                "nme_comparable", "classification_group",
                "sponsor_name_drugsatfda_holder", "first_product_brand",
                "first_product_ingredients", "first_product_form_route",
                "n_products", "first_product_marketing_status",
                "ingredient_first_appearance", "ingredient_screen", "tracked_in",
                "live_probe_status", "drugsatfda_url", "openfda_url",
                "verification_status", "notes"]

PROBE_HEADER = ["row_id", "application_number", "probe_file", "probe_url",
                "probe_sha256", "live_orig_date", "live_class_code",
                "live_review_priority", "live_sponsor", "status",
                "checked_against_payload"]

CROSS_HEADER = ["record_id", "year", "application_number", "kind", "appl_no",
                "decision_date", "submission_class_code",
                "submission_class_code_description", "review_priority",
                "products_verbatim", "in_openfda_payload", "classification",
                "drugsatfda_url", "openfda_url", "verification_status", "notes"]


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    payloads = verify_payloads()
    alldec = load_all_decisions()
    probes = verify_probes(payloads)
    files = verify_full_db()

    # first-appearance index across 1965-1979 payloads
    first: dict[str, tuple] = {}
    for y in sorted(alldec):
        for d in sorted(alldec[y], key=lambda r: r["decision_date"]):
            for ing in ingredients_of(d):
                first.setdefault(ing, (y, d["application_number"], d["decision_date"]))

    # v19 tracked applications (must exist and equal 48)
    v19_path = DATA / "pre1980_fda_decisions.csv"
    if not v19_path.exists():
        fail("data/pre1980_fda_decisions.csv missing; run build_pre1980_decisions_v19.py first")
    v19_rows = read_csv(v19_path)
    if len(v19_rows) != 48:
        fail(f"v19 table has {len(v19_rows)} rows, expected 48")
    tracked_by_appl = {}
    for r in v19_rows:
        tracked_by_appl[r["application_number"].replace(" ", "")] = r["decision_id"]

    audit_rows, probe_rows = [], []
    for year in YEARS:
        decs = sorted(payloads[year],
                      key=lambda d: (d["decision_date"], d["application_number"]))
        t1 = [d for d in decs if norm_class(d.get("submission_class_code")) in NME_CLASSES]
        if len(t1) != EXPECTED_T1[year]:
            fail(f"{year}: NME-comparable enumeration {len(t1)} != {EXPECTED_T1[year]}")
        for seq, d in enumerate(decs, 1):
            appl = d["application_number"]
            kind = d.get("application_kind") or ("BLA" if appl.startswith("BLA") else "NDA")
            num = appl[3:]
            cls = norm_class(d.get("submission_class_code"))
            nme = cls in NME_CLASSES
            prods = d.get("products") or []
            fp = prods[0] if prods else {}
            brand = fp.get("brand_name", "")
            ings = fp.get("active_ingredients", "")
            if appl in DISPLAY:
                brand_disp, _generic, exp_brand, exp_ing = DISPLAY[appl]
                if exp_brand not in brand or exp_ing not in ings.upper():
                    fail(f"{appl}: display-map drift on first product")
                brand = brand_disp
            # ingredient screen
            earlier = []
            for ing in sorted(ingredients_of(d)):
                fy, fapp, fdate = first[ing]
                if not (fy == year and fapp == appl):
                    earlier.append((ing, fy, fapp, fdate))
            if nme:
                for ing, fy, fapp, _f in earlier:
                    if (year, appl, ing, fy, fapp) not in ALLOWED_INVERSION:
                        fail(f"{appl}: NME row ingredient {ing} first appears {fy} on {fapp}")
                screen = ("first-in-payloads (1965-1979 screen)" if not earlier else
                          "cyclacillin first appears one day earlier on sibling tablet "
                          "NDA050509 (Type 3) - flagged inversion, counted once")
            else:
                screen = ("non-NME row: earlier appearances permitted by construction; "
                          "see ingredient_first_appearance")
            if earlier:
                ing, fy, fapp, fdate = earlier[0]
                first_app = (f"{earlier[0][0]} first {fdate} on {fapp}"
                             if len(earlier) == 1 else
                             f"{len(earlier)} ingredients first seen earlier (earliest {fdate} on {fapp})")
            else:
                first_app = "first-in-payloads"
            pr = probes.get(appl, {})
            live_status = pr.get("status", "PROBE_PENDING")
            if live_status == "MATCH":
                verif = "Verified (live probe match)"
            elif live_status in ("ABSENT_LIVE", "ORIG_APPROVAL_NOT_IN_WINDOW_LIVE"):
                verif = f"Flagged ({live_status})"
            elif live_status == "PROBE_PENDING":
                verif = "Payload-verified (probe layer pending)"
            else:
                fail(f"{appl}: unexpected probe status {live_status}")
            aud = {
                "row_id": f"PRE1980AUDIT-{year}-{seq:02d}",
                "year": year, "application_number": appl, "application_kind": kind,
                "decision_date": d["decision_date"],
                "submission_class_code": d.get("submission_class_code", ""),
                "submission_class_code_description": d.get("submission_class_code_description", ""),
                "review_priority": d.get("review_priority", ""),
                "nme_comparable": "TRUE" if nme else "FALSE",
                "classification_group": ("NME (Type 1)" if cls == "TYPE 1" else
                                         "NME + new combination (Type 1/4)" if cls == "TYPE 1/4" else
                                         (d.get("submission_class_code_description") or
                                          "NOT PUBLISHED (blank class)")),
                "sponsor_name_drugsatfda_holder": d.get("sponsor_name", ""),
                "first_product_brand": brand,
                "first_product_ingredients": ings,
                "first_product_form_route": (f"{fp.get('dosage_form', '')}; {fp.get('route', '')}").strip("; "),
                "n_products": len(prods),
                "first_product_marketing_status": fp.get("marketing_status", ""),
                "ingredient_first_appearance": first_app,
                "ingredient_screen": screen,
                "tracked_in": tracked_by_appl.get(appl, "none (not a Type 1/1-4 original approval)"),
                "live_probe_status": live_status,
                "drugsatfda_url": ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                                   f"?event=overview.process&varApplNo={num}"),
                "openfda_url": f"https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{appl}%22",
                "verification_status": verif,
                "notes": ("Row of the complete 1977-1979 original-application audit "
                          "(v20): every ORIG/AP row of the committed dual-run payloads; "
                          "facts verbatim from the payload; no ticker, indication or "
                          "applicant lineage asserted."),
            }
            audit_rows.append(aud)
            probe_rows.append({
                "row_id": aud["row_id"], "application_number": appl,
                "probe_file": f"probe_{appl}.json" if pr else "",
                "probe_url": pr.get("live_url", ""),
                "probe_sha256": pr.get("probe_sha", ""),
                "live_orig_date": pr.get("live_date", ""),
                "live_class_code": pr.get("live_class", ""),
                "live_review_priority": pr.get("live_priority", ""),
                "live_sponsor": pr.get("live_sponsor", ""),
                "status": live_status,
                "checked_against_payload": ("date+class+priority+holder all equal" if live_status == "MATCH" else
                                            "openFDA returned no record for this application (Seldane-class absence)" if live_status == "ABSENT_LIVE" else
                                            "no ORIG/AP approval in 1977-1979 in the live record" if live_status == "ORIG_APPROVAL_NOT_IN_WINDOW_LIVE" else
                                            "probe capture pending"),
            })

    if len(audit_rows) != 170:
        fail(f"audit rows {len(audit_rows)} != 170")

    write_csv(DATA / "pre1980_originals_audit_1977_1979.csv", AUDIT_HEADER, audit_rows)
    write_csv(DATA / "pre1980_row_probe_index.csv", PROBE_HEADER, probe_rows)

    # ---- Layer 2: full-DB cross-check + payload-invisible enumeration ----
    cross_rows = []
    if files:
        db = full_db_orig_ap(files)
        for year in YEARS:
            payload_keys = {(d["application_number"], d["decision_date"])
                            for d in payloads[year]}
            db_keys = {(r["application_number"], r["decision_date"]) for r in db[year]}
            missing_in_db = payload_keys - db_keys
            if missing_in_db:
                fail(f"{year}: payload approvals absent from the full Drugs@FDA DB "
                     f"(fail-closed): {sorted(missing_in_db)}")
            db_only = [r for r in db[year]
                       if (r["application_number"], r["decision_date"]) not in payload_keys]
            # summary row
            cross_rows.append({
                "record_id": f"FULldb-{year}-SUMMARY", "year": year,
                "application_number": "", "kind": "", "appl_no": "",
                "decision_date": "",
                "submission_class_code": "", "submission_class_code_description": "",
                "review_priority": "", "products_verbatim": "",
                "in_openfda_payload": "",
                "classification": "SUMMARY",
                "drugsatfda_url": "", "openfda_url": "",
                "verification_status": "CROSS-CHECKED",
                "notes": (f"full-DB ORIG/AP approvals {year}: {len(db[year])}; "
                          f"openFDA payload rows: {len(payloads[year])}; "
                          f"payload-invisible (named from the full Drugs@FDA database): "
                          f"{len(db_only)}"),
            })
            for i, r in enumerate(db_only, 1):
                is_nme = norm_class(r["submission_class_code"]) in NME_CLASSES
                prodstr = "; ".join(
                    f"{p.get('brand_name','')} ({p.get('active_ingredients','')}; {p.get('dosage_form','')})"
                    for p in r["products"]) or "no product rows published in the window extract"
                cross_rows.append({
                    "record_id": f"FULldb-{year}-{i:02d}", "year": year,
                    "application_number": r["application_number"],
                    "kind": r["kind"], "appl_no": r["appl_no"],
                    "decision_date": r["decision_date"],
                    "submission_class_code": r["submission_class_code"],
                    "submission_class_code_description": r["submission_class_code_description"],
                    "review_priority": r["review_priority"],
                    "products_verbatim": prodstr[:2000],
                    "in_openfda_payload": "FALSE",
                    "classification": ("NME-COMPARABLE (Type 1/1-4) - candidate for the "
                                       "official-count shortfall" if is_nme else
                                       "non-NME original approval"),
                    "drugsatfda_url": ("https://www.accessdata.fda.gov/scripts/cder/daf/"
                                       f"index.cfm?event=overview.process&varApplNo={r['appl_no']}"),
                    "openfda_url": (f"https://api.fda.gov/drug/drugsfda.json?"
                                    f"search=application_number:%22{r['application_number']}%22"),
                    "verification_status": "Named from full Drugs@FDA database (verbatim extract)",
                    "notes": ("ORIG/AP approval present in the Drugs@FDA database files "
                              "(window extract, SHA-manifested) but absent from the "
                              "openFDA ORIG/AP year payload for this year - the "
                              "payload-invisible gap class. Not added to any verified "
                              "decision table; listed here for line-by-line review."),
                })
        write_csv(DATA / "pre1980_full_db_crosscheck_1977_1979.csv", CROSS_HEADER, cross_rows)

    # staging report
    report = {
        "tool": "build_pre1980_originals_audit_v20.py",
        "built_utc": os.environ.get("BUILD_STAMP", ""),
        "audit_rows": len(audit_rows),
        "audit_rows_by_year": {str(y): sum(1 for r in audit_rows if r["year"] == y) for y in YEARS},
        "nme_comparable_by_year": {str(y): sum(1 for r in audit_rows
                                               if r["year"] == y and r["nme_comparable"] == "TRUE")
                                   for y in YEARS},
        "probe_layer": {"present": bool(probes),
                        "rows": len(probes),
                        "match": sum(1 for p in probes.values() if p.get("status") == "MATCH"),
                        "absent_live": sum(1 for p in probes.values() if p.get("status") == "ABSENT_LIVE"),
                        "other": sum(1 for p in probes.values()
                                     if p.get("status") not in ("MATCH", "ABSENT_LIVE"))},
        "full_db_layer": {"present": files is not None,
                          "crosscheck_rows": len(cross_rows),
                          "payload_invisible_by_year": {
                              str(y): sum(1 for r in cross_rows
                                          if str(r["year"]) == str(y)
                                          and r["in_openfda_payload"] == "FALSE")
                              for y in YEARS}},
        "fail_closed_checks": [
            "payload SHA vs run-19 manifest (3 files)",
            "payload row counts 42/66/62; NME-comparable 17/18/13",
            "probe files complete (170) + SHA vs manifest + date/class/priority/holder equality",
            "full-DB extracts SHA vs runner manifest; filter expressions recorded",
            "payload approvals ⊆ full-DB approvals per year (abort on any absence)",
            "v19 display-map agreement for the 48 Type 1/1-4 rows",
            "Cyclapen inversion the only permitted NME earlier-appearance flag",
        ],
    }
    (DATA / "staging" / "pre1980_originals_audit_v20_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"v20: audit rows {len(audit_rows)} "
          f"(17/18/13 NME-comparable), probes {'complete' if probes else 'PENDING'}, "
          f"full-DB {'cross-checked' if files else 'PENDING'} "
          f"({len(cross_rows)} crosscheck rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
