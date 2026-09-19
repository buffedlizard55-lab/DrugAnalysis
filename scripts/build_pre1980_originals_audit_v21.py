#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v21 (2026-09-19): complete original-application audit for pre-1980 years
1965-1976 - the backward extension of the v20 audit (1977-1979).

Every ORIG/AP payload row of the twelve new years is enumerated (477 rows =
32+16+32+22+25+38+48+29+43+73+39+80), not just the 125 Type 1/1-4 decisions,
with the same two cross-verification layers used for 1977-1979:

  Layer 1 (row probes):  data/raw/pre1980_row_probes_1965_1976/probe_*.json -
                         one complete live openFDA record per NME-comparable
                         application (125) + the amikacin gap-candidate probe,
                         SHA-manifested; date/class/priority/holder are
                         compared with the payload and any disagreement aborts.
                         Non-NME rows are not individually probed (documented
                         per row); they are covered by layer 2.
  Layer 2 (full DB):     data/raw/drugsatfda_data_files_2026_09/* - the
                         official Drugs@FDA database files narrowed to the
                         1965-1979 window. Every 1965-1976 ORIG/AP approval in
                         the FULL database is enumerated and diffed against the
                         payload extraction, so applications absent from the
                         openFDA payloads (the Seldane-class gap) are NAMED
                         instead of lost.

Owns three new tables (v20's 1977-1979 tables are untouched):

* data/pre1980_originals_audit_1965_1976.csv        (477 rows)
* data/pre1980_row_probe_index_1965_1976.csv        (125 live-capture rows)
* data/pre1980_full_db_crosscheck_1965_1976.csv     (per-year diff + invisibles)

Fail-closed rules: payload SHA-256 vs the runner manifest; per-year row counts
pinned; display names only from the v21 display map (drift aborts); every
earlier-ingredient hit on an NME row must be adjudicated in the v21
ALLOWED_EARLIER table; probe SHA vs manifest; full-DB member SHAs and recorded
filters re-verified. No ticker, indication or applicant lineage is asserted.
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
BLOCKS = {(1965, 1969): "openfda_orig_decisions_1965_1969",
          (1970, 1974): "openfda_orig_decisions_1970_1974",
          (1975, 1979): "openfda_orig_decisions_1975_1979"}
PRE1965_BLOCK = "openfda_orig_decisions_1939_1964"
PROBES_DIR = DATA / "raw" / "pre1980_row_probes_1965_1976"
ZIP_DIR = DATA / "raw" / "drugsatfda_data_files_2026_09"
REPORT = DATA / "staging" / "pre1980_originals_audit_v21_report.json"

YEARS = tuple(range(1965, 1977))
EXPECTED_ROWS = {1965: 32, 1966: 16, 1967: 32, 1968: 22, 1969: 25, 1970: 38,
                 1971: 48, 1972: 29, 1973: 43, 1974: 73, 1975: 39, 1976: 80}
EXPECTED_T1 = {1965: 11, 1966: 7, 1967: 13, 1968: 4, 1969: 8, 1970: 11,
               1971: 7, 1972: 7, 1973: 11, 1974: 16, 1975: 9, 1976: 21}
NME_CLASSES = {"TYPE 1", "TYPE 1/4"}

sys.path.insert(0, str(ROOT / "scripts"))
from build_pre1980_decisions_v21 import DISPLAY, ALLOWED_EARLIER  # noqa: E402

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


def fail(msg: str) -> None:
    raise SystemExit(f"build_pre1980_originals_audit_v21: {msg}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iso_api_date(value: str) -> str:
    s = (value or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def norm(value: str) -> str:
    return (value or "").strip().upper()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------

def verify_payloads() -> dict[int, list]:
    payloads: dict[int, list] = {}
    for (lo, hi), block in BLOCKS.items():
        d = DATA / "raw" / block
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        by_year = {int(r["id"].split("_")[-1]): r for r in manifest["requests"] if r.get("sha256")}
        for year in range(lo, hi + 1):
            if year not in YEARS:
                continue
            path = d / f"decisions_{year}.json"
            if not path.exists():
                fail(f"missing committed payload: {path}")
            req = by_year.get(year)
            if req is None or sha256_file(path) != req["sha256"]:
                fail(f"{year}: payload SHA drift vs runner manifest")
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("count") != len(obj.get("decisions") or []):
                fail(f"{year}: payload shape invalid")
            if len(obj["decisions"]) != EXPECTED_ROWS[year]:
                fail(f"{year}: payload row count {len(obj['decisions'])} != {EXPECTED_ROWS[year]}")
            payloads[year] = obj["decisions"]
    missing = [y for y in YEARS if y not in payloads]
    if missing:
        fail(f"payloads missing for {missing}")
    return payloads


def load_universe() -> dict[int, list]:
    """1939-1979 payload universe for the ingredient first-appearance screen."""
    out: dict[int, list] = {}
    pre = DATA / "raw" / PRE1965_BLOCK
    manifest = json.loads((pre / "manifest.json").read_text(encoding="utf-8"))
    by_year = {int(r["id"].split("_")[-1]): r for r in manifest["requests"] if r.get("sha256")}
    for year in range(1939, 1965):
        path = pre / f"decisions_{year}.json"
        req = by_year.get(year)
        if req is None or not path.exists() or sha256_file(path) != req["sha256"]:
            fail(f"{year}: pre-1965 payload missing or SHA drift")
        out[year] = json.loads(path.read_text(encoding="utf-8"))["decisions"]
    for (lo, hi), block in BLOCKS.items():
        for year in range(lo, hi + 1):
            out[year] = json.loads((DATA / "raw" / block / f"decisions_{year}.json")
                                   .read_text(encoding="utf-8"))["decisions"]
    return out


def ingredients_of(dec: dict) -> set[str]:
    ings = set()
    for x in dec.get("products") or []:
        for part in (x.get("active_ingredients") or "").split(";"):
            part = part.strip().upper()
            m = re.match(r"^([A-Z0-9\-\s/\.\(\),]+?)(?:\s+\d|\s+EQ\s|\s+N/A|\s+\*\*|$)", part)
            name = (m.group(1).strip() if m else part).rstrip(" .")
            if name:
                ings.add(name)
    return ings


# ---------------------------------------------------------------------------
# Layer 1: probes (NME-comparable rows + the gap candidate)
# ---------------------------------------------------------------------------

def verify_probes(payloads: dict[int, list]) -> dict[str, dict]:
    if not (PROBES_DIR / "manifest.json").exists():
        print("v21 audit: probe layer not present yet; NME rows marked probe-pending")
        return {}
    manifest = json.loads((PROBES_DIR / "manifest.json").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in manifest["requests"] if e.get("sha256")}
    out: dict[str, dict] = {}
    mismatch: list[str] = []
    want = [(year, d) for year in YEARS for d in payloads[year]
            if norm(d.get("submission_class_code")) in NME_CLASSES]
    for year, dec in want:
        appl = dec["application_number"]
        entry = entries.get(f"probe_{year}_{appl}")
        if entry is None or entry.get("status") != 200:
            fail(f"{appl}: live probe missing or not HTTP 200")
        path = PROBES_DIR / entry["out"]
        if not path.exists() or sha256_file(path) != entry["sha256"]:
            fail(f"{appl}: probe file missing or SHA drift vs manifest")
        obj = json.loads(path.read_text(encoding="utf-8"))
        rec = next((r for r in obj.get("results") or []
                    if r.get("application_number") == appl), None)
        if rec is None:
            out[appl] = {"status": "ABSENT_LIVE", "sha": entry["sha256"], "url": entry["url"]}
            mismatch.append(f"{appl}: ABSENT from live openFDA although the payload carries it")
            continue
        exp = (dec["decision_date"] or "").replace("-", "")
        orig = [s for s in rec.get("submissions") or []
                if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"
                and s.get("submission_status_date") == exp]
        if len(orig) != 1:
            out[appl] = {"status": "MISMATCH", "sha": entry["sha256"], "url": entry["url"]}
            mismatch.append(f"{appl}: expected exactly one live ORIG/AP on {exp}")
            continue
        s = orig[0]
        out[appl] = {"status": "MATCH", "sha": entry["sha256"], "url": entry["url"],
                     "date": s.get("submission_status_date", ""),
                     "class": s.get("submission_class_code", ""),
                     "priority": s.get("review_priority", ""),
                     "sponsor": rec.get("sponsor_name", "")}
        if norm(s.get("submission_class_code")) != norm(dec.get("submission_class_code")):
            mismatch.append(f"{appl}: live class != payload class")
        if norm(s.get("review_priority")) != norm(dec.get("review_priority")):
            mismatch.append(f"{appl}: live priority != payload priority")
        if (rec.get("sponsor_name") or "") != (dec.get("sponsor_name") or ""):
            mismatch.append(f"{appl}: live holder != payload holder")
    if mismatch:
        fail("live probe disagreement (fail-closed):\n  " + "\n  ".join(mismatch[:25]))
    return out


# ---------------------------------------------------------------------------
# Layer 2: full Drugs@FDA database window extract
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


def verify_full_db() -> dict | None:
    if not ZIP_DIR.exists():
        print("v21 audit: full-DB layer not present yet; skipping the window cross-check")
        return None
    manifest = json.loads((ZIP_DIR / "manifest.json").read_text(encoding="utf-8"))
    if not [e for e in manifest["requests"] if e.get("id", "").endswith(":zip")]:
        fail("full-DB manifest carries no zip entry")
    files = {}
    for out_name in ("Submissions_1965_1979.txt", "Applications_appl_window.txt",
                     "Products_appl_window.txt", "SubmissionClass_Lookup.txt"):
        path = ZIP_DIR / out_name
        if not path.exists():
            fail(f"full-DB extract missing: {out_name}")
        entry = next((e for e in manifest["requests"] if e.get("out") == out_name), {})
        if not entry.get("out_sha256") or sha256_file(path) != entry["out_sha256"]:
            fail(f"{out_name}: SHA drift vs runner manifest")
        filt = entry.get("filter", {})
        fkind = filt if isinstance(filt, str) else filt.get("type", "FULL")
        if fkind not in ("date_year_in", "applno_in_collected", "FULL"):
            fail(f"{out_name}: unexpected recorded filter {fkind!r}")
        files[out_name] = path
    return files


def full_db_orig_ap(files: dict) -> dict[int, list[dict]]:
    subs = read_tab(files["Submissions_1965_1979.txt"])
    lookup = {r["SubmissionClassCodeID"]: r for r in read_tab(files["SubmissionClass_Lookup.txt"])}
    appl_type = {r["ApplNo"]: r.get("ApplType", "").strip().upper()
                 for r in read_tab(files["Applications_appl_window.txt"])}
    products: dict[str, list[dict]] = {}
    for r in read_tab(files["Products_appl_window.txt"]):
        products.setdefault(r["ApplNo"], []).append(r)
    date_mdY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})")
    date_iso = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
    out: dict[int, list[dict]] = {y: [] for y in YEARS}
    for s in subs:
        if norm(s.get("SubmissionType")) != "ORIG" or norm(s.get("SubmissionStatus")) != "AP":
            continue
        raw = (s.get("SubmissionStatusDate") or "").strip()
        m = date_mdY.match(raw) or date_iso.match(raw)
        if not m:
            continue
        g = m.groups()
        if len(g[0]) == 4:
            year, mo, dy = int(g[0]), int(g[1]), int(g[2])
        else:
            mo, dy, year = int(g[0]), int(g[1]), int(g[2])
        if year not in YEARS:
            continue
        appl_no = s["ApplNo"].strip()
        kind = appl_type.get(appl_no, "")
        if kind not in ("NDA", "BLA"):
            continue
        lk = lookup.get((s.get("SubmissionClassCodeID") or "").strip(), {})
        prods = products.get(appl_no, [])
        out[year].append({
            "appl_no": appl_no, "kind": kind, "application_number": f"{kind}{appl_no}",
            "decision_date": f"{year}-{mo:02d}-{dy:02d}",
            "submission_class_code": norm(lk.get("SubmissionClassCode")),
            "submission_class_code_description": (lk.get("SubmissionClassCodeDescription") or "").strip(),
            "review_priority": norm(s.get("ReviewPriority")),
            "products": [{"brand_name": p.get("DrugName", ""),
                          "active_ingredients": p.get("ActiveIngredient", ""),
                          "dosage_form": p.get("Form", "")} for p in prods],
        })
    for year in YEARS:
        out[year].sort(key=lambda r: (r["decision_date"], r["application_number"]))
    return out


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def main() -> int:
    payloads = verify_payloads()
    universe = load_universe()
    probes = verify_probes(payloads)
    files = verify_full_db()

    first: dict[str, tuple] = {}
    for y in sorted(universe):
        for d in sorted(universe[y], key=lambda r: (r["decision_date"], r["application_number"])):
            for ing in ingredients_of(d):
                first.setdefault(ing, (y, d["application_number"], d["decision_date"]))

    decisions_path = DATA / "pre1980_fda_decisions.csv"
    if not decisions_path.exists():
        fail("data/pre1980_fda_decisions.csv missing; run build_pre1980_decisions_v21.py first")
    dec_rows = read_csv(decisions_path)
    tracked = {r["application_number"].replace(" ", ""): r["decision_id"] for r in dec_rows
               if r["year"] in {str(y) for y in YEARS}}
    if len(tracked) != sum(EXPECTED_T1.values()):
        fail(f"decision table carries {len(tracked)} tracked 1965-1976 applications, "
             f"expected {sum(EXPECTED_T1.values())}")

    audit_rows, probe_rows = [], []
    for year in YEARS:
        decs = sorted(payloads[year], key=lambda d: (d["decision_date"], d["application_number"]))
        t1 = [d for d in decs if norm(d.get("submission_class_code")) in NME_CLASSES]
        if len(t1) != EXPECTED_T1[year]:
            fail(f"{year}: NME-comparable enumeration {len(t1)} != {EXPECTED_T1[year]}")
        for seq, d in enumerate(decs, 1):
            appl = d["application_number"]
            kind = "BLA" if appl.startswith("BLA") else "NDA"
            cls = norm(d.get("submission_class_code"))
            nme = cls in NME_CLASSES
            prods = d.get("products") or []
            fp = prods[0] if prods else {}
            brand = fp.get("brand_name", "")
            ings = fp.get("active_ingredients", "")
            if appl in DISPLAY:
                brand_disp, _g, exp_brand, exp_ing = DISPLAY[appl]
                if not any((p.get("brand_name") or "") == exp_brand and
                           exp_ing in (p.get("active_ingredients") or "").upper()
                           for p in prods):
                    fail(f"{appl}: display-map drift vs payload products")
                brand = brand_disp
            earlier = []
            for ing in sorted(ingredients_of(d)):
                fy, fapp, fdate = first[ing]
                if not (fy == year and fapp == appl):
                    earlier.append((ing, fy, fapp, fdate))
            if nme:
                for ing, _fy, _fapp, _f in earlier:
                    if (year, appl, ing) not in ALLOWED_EARLIER:
                        fail(f"{appl}: NME row ingredient {ing} earlier appearance not adjudicated")
                screen = ("first appearance in the 1939-1979 payload universe" if not earlier
                          else "adjudicated earlier appearance (combination component or "
                               "same-ingredient sibling application); see the decision row notes")
            else:
                screen = ("non-NME row: earlier appearances permitted by construction; "
                          "see ingredient_first_appearance")
            if earlier:
                ing, fy, fapp, fdate = earlier[0]
                first_app = (f"{ing} first {fdate} on {fapp}" if len(earlier) == 1 else
                             f"{len(earlier)} ingredients first seen earlier "
                             f"(earliest {fdate} on {fapp})")
            else:
                first_app = "first-in-payloads (1939-1979 universe)"
            pr = probes.get(appl, {})
            if pr:
                live_status = pr.get("status", "PROBE_PENDING")
            else:
                # A non-NME row legitimately has no probe; an NME row without one
                # means the probe layer did not load, and that must stay visible
                # (the validator errors on PROBE_PENDING).
                live_status = "NOT_PROBED_NON_NME_ROW" if not nme else "PROBE_PENDING"
            if live_status == "MATCH":
                verif = "Verified (live probe match)"
            elif live_status == "ABSENT_LIVE":
                verif = "Flagged (ABSENT_LIVE)"
            elif live_status == "PROBE_PENDING":
                verif = "Payload-verified (live probe layer pending)"
            elif live_status == "NOT_PROBED_NON_NME_ROW":
                verif = ("Payload-verified; no per-row live probe issued for non-NME rows "
                         "(cross-checked against the full Drugs@FDA database instead)")
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
                "first_product_form_route": f"{fp.get('dosage_form', '')}; {fp.get('route', '')}".strip("; "),
                "n_products": len(prods),
                "first_product_marketing_status": fp.get("marketing_status", ""),
                "ingredient_first_appearance": first_app,
                "ingredient_screen": screen,
                "tracked_in": tracked.get(appl, "none (not a Type 1/1-4 original approval)"),
                "live_probe_status": live_status,
                "drugsatfda_url": ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                                   f"?event=overview.process&varApplNo={appl[3:]}"),
                "openfda_url": f"https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{appl}%22",
                "verification_status": verif,
                "notes": ("Row of the complete 1965-1976 original-application audit (v21): every "
                          "ORIG/AP row of the committed SHA-verified payloads; facts verbatim from "
                          "the payload; no ticker, indication or applicant lineage asserted."),
            }
            audit_rows.append(aud)
            if pr:
                probe_rows.append({
                    "row_id": aud["row_id"], "application_number": appl,
                    "probe_file": f"probe_{appl}.json",
                    "probe_url": pr.get("url", ""), "probe_sha256": pr.get("sha", ""),
                    "live_orig_date": pr.get("date", ""), "live_class_code": pr.get("class", ""),
                    "live_review_priority": pr.get("priority", ""),
                    "live_sponsor": pr.get("sponsor", ""), "status": live_status,
                    "checked_against_payload": ("date+class+priority+holder all equal"
                                                if live_status == "MATCH" else
                                                "openFDA returned no record for this application"),
                })

    if len(audit_rows) != sum(EXPECTED_ROWS.values()):
        fail(f"audit rows {len(audit_rows)} != {sum(EXPECTED_ROWS.values())}")
    if len(probe_rows) != sum(EXPECTED_T1.values()):
        fail(f"probe rows {len(probe_rows)} != {sum(EXPECTED_T1.values())}")
    if probes and sum(1 for p in probe_rows if p["status"] == "MATCH") != len(probe_rows):
        fail("probe layer present but not every NME row is a MATCH")

    write_csv(DATA / "pre1980_originals_audit_1965_1976.csv", AUDIT_HEADER, audit_rows)
    write_csv(DATA / "pre1980_row_probe_index_1965_1976.csv", PROBE_HEADER, probe_rows)

    # ---- Layer 2: full-DB cross-check + payload-invisible enumeration ----
    cross_rows = []
    invisible_total = 0
    if files:
        db = full_db_orig_ap(files)
        for year in YEARS:
            payload_keys = {(d["application_number"], d["decision_date"]) for d in payloads[year]}
            db_keys = {(r["application_number"], r["decision_date"]) for r in db[year]}
            missing_in_db = payload_keys - db_keys
            if missing_in_db:
                fail(f"{year}: {len(missing_in_db)} payload rows absent from the full Drugs@FDA "
                     f"database: {sorted(missing_in_db)[:5]}")
            invisible = sorted(db_keys - payload_keys)
            invisible_total += len(invisible)
            for i, (appl, date) in enumerate(invisible, 1):
                rec = next(r for r in db[year]
                           if (r["application_number"], r["decision_date"]) == (appl, date))
                prods = "; ".join(f"{p['brand_name']} ({p['active_ingredients']}; {p['dosage_form']})"
                                  for p in rec["products"])
                nme = rec["submission_class_code"] in NME_CLASSES
                cross_rows.append({
                    "record_id": f"FULLDB-{year}-INV{i:02d}", "year": year,
                    "application_number": appl, "kind": rec["kind"], "appl_no": rec["appl_no"],
                    "decision_date": date,
                    "submission_class_code": rec["submission_class_code"],
                    "submission_class_code_description": rec["submission_class_code_description"],
                    "review_priority": rec["review_priority"], "products_verbatim": prods,
                    "in_openfda_payload": "FALSE",
                    "classification": ("PAYLOAD-INVISIBLE NME CANDIDATE" if nme
                                       else "PAYLOAD-INVISIBLE non-NME original"),
                    "drugsatfda_url": ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                                       f"?event=overview.process&varApplNo={rec['appl_no']}"),
                    "openfda_url": ("https://api.fda.gov/drug/drugsfda.json?search="
                                    f"application_number:%22{appl}%22"),
                    "verification_status": "Named from the full Drugs@FDA database files",
                    "notes": ("Present in the official Drugs@FDA database files (fda.gov media "
                              "89850) but absent from the committed openFDA ORIG/AP payload - the "
                              "Seldane-class invisibility. Recorded verbatim from the database "
                              "files; NOT merged into the decision tables."),
                })
            cross_rows.append({
                "record_id": f"FULLDB-{year}-SUMMARY", "year": year, "application_number": "",
                "kind": "", "appl_no": "", "decision_date": "", "submission_class_code": "",
                "submission_class_code_description": "", "review_priority": "",
                "products_verbatim": "", "in_openfda_payload": "", "classification": "SUMMARY",
                "drugsatfda_url": "", "openfda_url": "", "verification_status": "CROSS-CHECKED",
                "notes": (f"full-DB ORIG/AP approvals {year}: {len(db[year])}; openFDA payload "
                          f"rows: {len(payloads[year])}; payload-invisible (named from the full "
                          f"Drugs@FDA database): {len(invisible)}"),
            })
        write_csv(DATA / "pre1980_full_db_crosscheck_1965_1976.csv", CROSS_HEADER, cross_rows)

    REPORT.write_text(json.dumps({
        "generated_utc": "2026-09-19",
        "years": list(YEARS),
        "audit_rows": len(audit_rows),
        "per_year_rows": {str(y): EXPECTED_ROWS[y] for y in YEARS},
        "nme_comparable_rows": {str(y): EXPECTED_T1[y] for y in YEARS},
        "probe_layer": {"present": bool(probes), "rows": len(probe_rows),
                        "match": sum(1 for p in probe_rows if p["status"] == "MATCH")},
        "full_db_layer": {"present": bool(files),
                          "payload_invisible_total": invisible_total,
                          "cross_rows": len(cross_rows)},
        "gates": ["payload SHA-256 vs manifest", "per-year row counts pinned",
                  "display-map drift aborts", "NME earlier-appearance adjudication required",
                  "probe SHA + date/class/priority/holder equality",
                  "full-DB member SHAs + recorded filters",
                  "payload rows absent from the full DB abort the build"],
    }, indent=2) + "\n", encoding="utf-8")

    print(f"v21 audit: {len(audit_rows)} rows across {len(YEARS)} years "
          f"({sum(EXPECTED_T1.values())} NME-comparable), probes "
          f"{'complete' if probes else 'PENDING'}, full-DB cross-check "
          f"{'done (' + str(invisible_total) + ' payload-invisible)' if files else 'PENDING'}")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
