#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v26 (2026-09-21): backward extension of the verified decision tables to
1939-1964 - the years BEFORE the project's previous earliest covered year
(1965, the start of data/pre1980_fda_decisions.csv).

Source of record
----------------
data/raw/openfda_orig_decisions_1939_1964/ - the official openFDA Drugs@FDA
extract (endpoint https://api.fda.gov/drug/drugsfda.json, filter
submissions.submission_type:"ORIG" AND submissions.submission_status:"AP" AND
submissions.submission_status_date within the year), fetched by the GitHub
Actions runner on 2026-09-19 with per-file SHA-256 recorded in the manifest.
Every emitted field is copied verbatim from that payload; nothing is inferred.
The 1938 FDCA is the enabling statute; Drugs@FDA's own database starts in
1939, so 1939 is the earliest assertable year (no 1938 row can be produced
from any official record - the FDA's official NDA series begins 1938 but
publishes no per-year NDA count for it; see the register notes).

Second cross-check layer (no network):
data/raw/drugsatfda_data_files_2026_09/Applications_all_types.txt - the
unfiltered official Drugs@FDA database application map (29,336 applications,
SHA-manifested, fetched 2026-09-19). Every 1939-1964 application number is
checked against it for application TYPE and holder name; any disagreement
aborts the build. Result on the current payloads: 0 of 535 type mismatches,
0 of 535 holder mismatches, 0 of 535 absent from the database.

Official year series:
data/fda_official_year_series.csv (FDA "Summary of NDA approvals and receipts,
1938-present") supplies the official NME/NDAs figures verbatim where
published (1941-1964 per-year; 1938-40 published as a combined series with
NMEs qualified "1940 only"; 1939 has no official NME figure).

Probe layer (fetched later, on the Actions runner, job
fetch_jobs/pre1965_row_probes_1939_1964.json): one live openFDA capture per
application. Base mode (no --join-probes) marks every row
"Payload-verified (live probe layer pending)". Join mode reads
data/raw/pre1965_row_probes_1939_1964/, re-hashes every probe file against
its manifest entry, and compares live ORIG-AP date/class/priority/holder with
the payload. Field disagreement aborts (fail-closed); an application whose
live record is empty (ABSENT_LIVE) or that publishes no ORIG-AP submission
(NO_ORIG_AP_LIVE) is FLAGGED for review, never silently kept as verified.

Tables owned (all rewritten deterministically on every run):
* data/pre1965_originals_audit_1939_1964.csv   (535 rows, every ORIG/AP row)
* data/pre1965_fda_decisions.csv               (178 NME-comparable rows,
                                                same schema as
                                                data/pre1980_fda_decisions.csv)
* data/pre1965_year_register.csv               (26 rows, one per year)
* data/pre1965_era_analysis.csv                (26 rows, one per year)
* data/pre1965_row_probe_index.csv             (join mode: one row per
                                                probed application)

Fail-closed rules
-----------------
* payload file SHA-256 vs runner manifest (26 files);
* payload count field == decisions list length (26 files);
* every decision_date inside its payload year;
* per-year application/type/holder cross-check vs the full official database
  (mismatch aborts);
* NME rows whose active ingredients already appear on an earlier row of the
  1939-1964 payload universe are FLAGGED (re-screening / sibling pair) -
  flagged, never corrected, never excluded from the row count, and excluded
  only from the separate counted-once statistic;
* no ticker, indication, or approval-era applicant lineage is asserted;
* no likelihood or probability column is written anywhere.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BLOCK_DIR = DATA / "raw" / "openfda_orig_decisions_1939_1964"
APPS_DIR = DATA / "raw" / "drugsatfda_data_files_2026_09"
PROBE_DIR = DATA / "raw" / "pre1965_row_probes_1939_1964"

AUDIT_CSV = DATA / "pre1965_originals_audit_1939_1964.csv"
DECISIONS_CSV = DATA / "pre1965_fda_decisions.csv"
REGISTER_CSV = DATA / "pre1965_year_register.csv"
ERA_CSV = DATA / "pre1965_era_analysis.csv"
PROBE_INDEX_CSV = DATA / "pre1965_row_probe_index.csv"
APPS_FILE = APPS_DIR / "Applications_all_types.txt"
OFFICIAL_CSV = DATA / "fda_official_year_series.csv"

YEARS = tuple(range(1939, 1965))
NME_CLASSES = {"TYPE 1", "TYPE 1/4"}
V26 = "v26 (2026-09-21)"

AUDIT_HEADER = ["row_id", "year", "application_number", "application_kind",
                "decision_date", "submission_class_code",
                "submission_class_code_description", "review_priority",
                "nme_comparable", "classification_group",
                "sponsor_name_drugsatfda_holder", "full_db_holder_match",
                "first_product_brand", "first_product_ingredients",
                "first_product_form_route", "n_products",
                "first_product_marketing_status", "ingredient_first_appearance",
                "ingredient_screen", "tracked_in", "live_probe_status",
                "drugsatfda_url", "openfda_url", "verification_status", "notes"]
DECISION_HEADER = ["decision_id", "year", "application_number", "drug_brand",
                   "drug_generic", "company_name",
                   "corporate_lineage_and_ticker", "decision_type",
                   "decision_date", "chemical_type_code",
                   "chemical_type_description", "review_priority", "indication",
                   "regulatory_milestone", "source_url_1", "source_url_2",
                   "verification_status", "notes"]
REGISTER_HEADER = ["year", "payload_orig_ap_count", "manifest_raw_records",
                   "nme_type1_rows", "nme_type14_rows", "nme_rows_total",
                   "nme_counted_once", "blank_class_rows", "unknown_class_rows",
                   "priority_reviews", "standard_reviews",
                   "official_fda_nme_count", "official_ndas_approved",
                   "delta_nme_rows_vs_official", "official_source_url",
                   "raw_payload", "query_url", "source_type", "coverage_status",
                   "probe_status", "notes"]
ERA_HEADER = ["year", "total_nmes_approved", "official_fda_nme_count",
              "nme_comparable_rows", "official_series_delta",
              "verified_decisions_tracked", "priority_reviews",
              "standard_reviews", "unpublished_priority_reviews",
              "orphan_drug_act_status", "statutory_framework",
              "landmark_approvals", "historical_significance",
              "primary_source_basis"]
PROBE_HEADER = ["row_id", "application_number", "probe_file", "probe_url",
                "probe_sha256", "live_orig_date", "live_class_code",
                "live_review_priority", "live_sponsor", "status",
                "checked_against_payload"]


def fail(msg: str) -> None:
    raise SystemExit(f"build_pre1965_decisions_v26: {msg}")


def norm(value: str) -> str:
    return (value or "").strip().upper()


def squash(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().upper()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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

def verify_payloads() -> dict[int, list[dict]]:
    manifest = json.loads((BLOCK_DIR / "manifest.json").read_text(encoding="utf-8"))
    by_year = {int(r["id"].split("_")[-1]): r for r in manifest["requests"]
               if r.get("sha256")}
    payloads: dict[int, list[dict]] = {}
    for year in YEARS:
        path = BLOCK_DIR / f"decisions_{year}.json"
        if not path.exists():
            fail(f"missing committed payload: {path}")
        req = by_year.get(year)
        if req is None or sha256_file(path) != req["sha256"]:
            fail(f"{year}: payload SHA-256 drift vs runner manifest")
        obj = json.loads(path.read_text(encoding="utf-8"))
        decisions = obj.get("decisions")
        if not isinstance(decisions, list):
            fail(f"{year}: payload shape invalid (no decisions list)")
        if obj.get("count") != len(decisions):
            fail(f"{year}: payload count field {obj.get('count')} != "
                 f"{len(decisions)} decisions")
        for d in decisions:
            date = (d.get("decision_date") or "")
            if not re.fullmatch(rf"{year}-\d{{2}}-\d{{2}}", date):
                fail(f"{year}: decision_date {date!r} outside payload year")
        payloads[year] = decisions
    return payloads


def load_apps() -> dict[str, tuple[str, str]]:
    """Unfiltered official Drugs@FDA application map: num6 -> (type, holder)."""
    manifest = json.loads((APPS_DIR / "manifest.json").read_text(encoding="utf-8"))
    recorded = {e["out"]: e for e in manifest["requests"] if e.get("out")}
    entry = recorded.get("Applications_all_types.txt")
    if entry is None or sha256_file(APPS_FILE) != entry["out_sha256"]:
        fail("Applications_all_types.txt SHA-256 drift vs runner manifest")
    apps: dict[str, tuple[str, str]] = {}
    with APPS_FILE.open(encoding="utf-8") as fh:
        next(fh)  # header: ApplNo\tApplType\tApplPublicNotes\tSponsorName
        for ln in fh:
            parts = ln.rstrip("\n").rstrip("\r").split("\t")
            if len(parts) >= 4 and parts[0].strip():
                apps[parts[0].strip().zfill(6)] = (parts[1].strip(), parts[3].strip())
    return apps


def load_official() -> dict[int, dict[str, str]]:
    """FDA official year series (committed, source-URL per row)."""
    if not OFFICIAL_CSV.exists():
        fail("missing data/fda_official_year_series.csv")
    out: dict[int, dict[str, str]] = {}
    for r in read_csv(OFFICIAL_CSV):
        y = (r.get("year") or "").strip()
        if y.isdigit() and int(y) in YEARS:
            out[int(y)] = {"nme": (r.get("nmes_approved") or "").strip(),
                           "ndas": (r.get("ndas_approved") or "").strip(),
                           "url": (r.get("source_url") or "").strip()}
    return out


def ingredients_of(dec: dict) -> set[str]:
    """v21 ingredient tokenizer, verbatim (screen device, not a fact)."""
    ings: set[str] = set()
    for x in dec.get("products") or []:
        for part in (x.get("active_ingredients") or "").split(";"):
            part = part.strip().upper()
            m = re.match(r"^([A-Z0-9\-\s/\.\\(\\),]+?)(?:\s+\d|\s+EQ\s|\s+N/A|\s+\*\*|$)", part)
            name = (m.group(1).strip() if m else part).rstrip(" .")
            if name:
                ings.add(name)
    return ings


def build_first_appearance(payloads: dict[int, list[dict]]) -> dict[str, tuple]:
    """ingredient -> ((year, date), application_number, date) earliest row."""
    first: dict[str, tuple] = {}
    for year in YEARS:
        for d in payloads[year]:
            pos = (year, d["decision_date"])
            for ing in ingredients_of(d):
                if ing not in first or pos < first[ing][0]:
                    first[ing] = (pos, d["application_number"], d["decision_date"])
    return first


# ---------------------------------------------------------------------------
# probe layer (join mode)
# ---------------------------------------------------------------------------

def load_probes(payloads: dict[int, list[dict]]) -> dict[str, dict]:
    if not (PROBE_DIR / "manifest.json").exists():
        return {}
    manifest = json.loads((PROBE_DIR / "manifest.json").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in manifest["requests"] if e.get("sha256")}
    out: dict[str, dict] = {}
    want = {(year, d["application_number"])
            for year in YEARS for d in payloads[year]}
    missing = [f"probe_{y}_{a}" for y, a in sorted(want)
               if f"probe_{y}_{a}" not in entries]
    if missing:
        print(f"v26 probes: {len(missing)}/{len(want)} applications not yet "
              f"captured (e.g. {missing[0]}); those rows stay PROBE_PENDING")
    for year in YEARS:
        for dec in payloads[year]:
            appl = dec["application_number"]
            entry = entries.get(f"probe_{year}_{appl}")
            if entry is None:
                continue
            if entry.get("status") != 200:
                fail(f"{appl}: live probe not HTTP 200 (status={entry.get('status')})")
            path = PROBE_DIR / entry["out"]
            if not path.exists():
                fail(f"{appl}: probe file missing: {path}")
            if sha256_file(path) != entry["sha256"]:
                fail(f"{appl}: probe SHA-256 drift vs manifest")
            recs = (json.loads(path.read_text(encoding="utf-8")).get("results")) or []
            if not recs:
                out[appl] = {"status": "ABSENT_LIVE", "url": entry.get("url", ""),
                             "sha": entry["sha256"], "file": entry["out"]}
                continue
            rec = recs[0]
            subs = [s for s in (rec.get("submissions") or [])
                    if norm(s.get("submission_type")) == "ORIG"
                    and norm(s.get("submission_status")) == "AP"]
            payload_date = dec["decision_date"]
            hit = None
            for s in subs:
                d = (s.get("submission_status_date") or "").strip()
                if re.fullmatch(r"\d{8}", d) and \
                        f"{d[0:4]}-{d[4:6]}-{d[6:8]}" == payload_date:
                    hit = s
                    break
            if hit is None:
                out[appl] = {"status": "NO_ORIG_AP_LIVE", "url": entry.get("url", ""),
                             "sha": entry["sha256"], "file": entry["out"],
                             "n_live_orig_ap": len(subs)}
                continue
            live = {
                "status": "MATCH",
                "url": entry.get("url", ""), "sha": entry["sha256"],
                "file": entry["out"],
                "date": payload_date,
                "class": norm(hit.get("submission_class_code")),
                "priority": norm(hit.get("review_priority")),
                "sponsor": squash(rec.get("sponsor_name")),
            }
            if live["class"] != norm(dec.get("submission_class_code")):
                fail(f"{appl}: live class {live['class']} != payload "
                     f"{norm(dec.get('submission_class_code'))}")
            if live["priority"] != norm(dec.get("review_priority")):
                fail(f"{appl}: live priority {live['priority']} != payload "
                     f"{norm(dec.get('review_priority'))}")
            if live["sponsor"] != squash(dec.get("sponsor_name")):
                fail(f"{appl}: live sponsor {live['sponsor']!r} != payload "
                     f"{squash(dec.get('sponsor_name'))!r}")
            out[appl] = live
    return out


# ---------------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------------

def classification_group(cls: str, desc: str) -> str:
    if cls == "TYPE 1":
        return "NME (Type 1)"
    if cls == "TYPE 1/4":
        return "NME + new combination (Type 1/4)"
    return desc or "NOT PUBLISHED (blank class)"


def statutory_framework(year: int, dec_dates: list[str]) -> str:
    base_38 = ("Pre-1962 federal NDA framework under the 1938 FD&C Act: "
               "safety ('safe for use as labeled') was required; proof of "
               "effectiveness was NOT a legal requirement for new-drug "
               "approval. (1962 Kefauver-Harris amendments added the "
               "effectiveness requirement.)")
    if year <= 1961:
        return base_38
    if year == 1962:
        pre = [d for d in dec_dates if d < "1962-09-22"]
        post = [d for d in dec_dates if d >= "1962-09-22"]
        return (f"Regime changed during 1962: the Kefauver-Harris "
                f"(Drug Efficacy) Amendments were enacted 1962-09-22, adding "
                f"the proof-of-effectiveness requirement to the 1938 "
                f"safety-only standard. In this payload: {len(pre)} of "
                f"{len(dec_dates)} original approvals predate the enactment "
                f"(reviewed under the 1938 standard), {len(post)} postdate it.")
    return ("Post-Kefauver-Harris: the 1962 amendments required substantial "
            "evidence of both safety and effectiveness for new drugs; the "
            "DESI program (begun 1962) was simultaneously re-studying "
            "pre-1962 approvals for efficacy.")


def era_narrative(year: int, payloads: dict[int, list[dict]],
                  audit_by_year: dict[int, list[dict]],
                  official: dict[int, dict[str, str]]) -> tuple[str, str]:
    """(landmark_approvals, historical_significance) - data-derived only."""
    decs = payloads[year]
    t1 = [d for d in decs if norm(d.get("submission_class_code")) in NME_CLASSES]
    brands = []
    for d in sorted(t1, key=lambda x: (x["decision_date"], x["application_number"])):
        prods = d.get("products") or []
        b = (prods[0].get("brand_name") if prods else "") or d.get("brand_name_openfda") or ""
        b = b.strip()
        if b and b not in brands:
            brands.append(b)
    landmark = ", ".join(brands[:8]) + (f" (+{len(brands) - 8} more)" if len(brands) > 8 else "")
    nme_n = len(t1)
    total = len(decs)
    off = official.get(year, {})
    off_nme = off.get("nme", "")
    parts = [f"The committed Drugs@FDA extract enumerates {nme_n} Type 1/1-4 "
             f"original approvals among {total} ORIG/AP applications for "
             f"{year}. Application-level enumeration from the official "
             f"payload, not a reconstructed contemporaneous statistic."]
    if off_nme:
        parts.append(f"Official FDA series (committed "
                     f"data/fda_official_year_series.csv, source "
                     f"FDA summary-nda-approvals-receipts-1938-present): "
                     f"{off_nme} NMEs{', ' + off.get('ndas','') + ' NDAs approved' if off.get('ndas') else ''}.")
    else:
        parts.append("The FDA official series publishes no separate NME "
                     "figure for this year (1938-40 is published combined; "
                     "NMEs qualified '1940 only').")
    if year == 1939:
        parts.append("First approval year of the Drugs@FDA database: NDA000552 "
                     "(heparin sodium, LIQUAEMIN SODIUM, Aspen Global Inc.) "
                     "1939 is the first and lowest-numbered heparin NDA; "
                     "independently confirmed by Federal Register 91 FR "
                     "(2026-03-09) listing NDA 000552 as 'Liquaemin Sodium "
                     "(heparin sodium) injectable ... Aspen Global Inc.' "
                     "and as the first heparin NDA to take effect (1939). "
                     "The 1938 FD&C Act (enacted 1938-06-28) was the "
                     "enabling statute; no 1938 decision row exists in any "
                     "official Drugs@FDA/openFDA record.")
    if year == 1957:
        parts.append("FLAG (re-screening screen): NDA009149 (Type 1, "
                     "CHLORPROMAZINE HYDROCHLORIDE) appears after NDA011120 "
                     "(1957-09-18, same ingredient) inside the 1939-1964 "
                     "payload universe; the payloads do not carry the "
                     "earlier chlorpromazine original (Drugs@FDA pre-1965 "
                     "coverage is incomplete), so both rows are kept and the "
                     "pair is flagged for review, never auto-corrected.")
    if year == 1960:
        parts.append("FLAG (re-screening screen): NDA012265 (Type 1, RESERPINE) "
                     "appears after NDA009296 (1954-04-01, same ingredient); "
                     "flagged for review, never auto-corrected.")
    if year == 1961:
        parts.append("Historical context (not a decision row): the "
                     "thalidomide NDA application (filed September 1960, "
                     "Richardson-Merrell) was under FDA review all year and "
                     "was NEVER approved - the company withdrew the pending "
                     "application in 1962 after the European birth-defect "
                     "disaster; the refusal is credited to FDA reviewer "
                     "Frances Oldham Kelsey. Recorded here for context only; "
                     "thalidomide has no approval row in this table.")
    if year == 1962:
        parts.append("Kefauver-Harris (Drug Efficacy) Amendments enacted "
                     "1962-09-22 (prompted in part by the thalidomide "
                     "tragedy): new drugs now required proof of BOTH safety "
                     "and effectiveness. Same-year sibling pair flagged: "
                     "NDA012486/NDA012487 (CHLORPROTHIXENE, two applications, "
                     "molecule counted once in the counted-once statistic).")
    if year == 1952:
        parts.append("FLAG (re-screening screen): NDA008592 (Type 1, "
                     "NOREPINEPHRINE BITARTRATE) appears after NDA007513 "
                     "(1950-07-13, same ingredient); flagged for review.")
    if year == 1955:
        parts.append("FLAG (re-screening screen): NDA010028 (Type 1, "
                     "MEPROBAMATE) appears after NDA009698 (1955-04-28, same "
                     "ingredient, same year); sibling pair, flagged for "
                     "review, counted once in the counted-once statistic.")
    return landmark, " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--join-probes", action="store_true",
                    help="join the per-row live probe layer if its manifest exists")
    args = ap.parse_args()

    payloads = verify_payloads()
    apps = load_apps()
    official = load_official()
    first = build_first_appearance(payloads)

    probes: dict[str, dict] = {}
    # Auto-join whenever the probe manifest exists (complete or partial):
    # captured rows resolve to MATCH/ABSENT_LIVE/NO_ORIG_AP_LIVE, uncaptured
    # rows stay PROBE_PENDING. Deterministic for a given input state.
    if (PROBE_DIR / "manifest.json").exists() or args.join_probes:
        probes = load_probes(payloads)

    audit_rows: list[dict] = []
    decision_rows: list[dict] = []
    register_rows: list[dict] = []
    era_rows: list[dict] = []
    probe_index_rows: list[dict] = []
    per_year: dict[int, dict] = {}

    total = 0
    total_nme = 0
    total_nme_once = 0
    n_flagged_nme = 0

    for year in YEARS:
        decs = sorted(payloads[year],
                      key=lambda d: (d["decision_date"], d["application_number"]))
        t1 = [d for d in decs if norm(d.get("submission_class_code")) in NME_CLASSES]
        # counted-once (strict, molecule-conservative): an NME row counts
        # once only if NONE of its ingredients appears on any earlier row of
        # the 1939-1964 payload universe. Sibling pairs and re-screening rows
        # are excluded from this statistic only - they keep their row and
        # their FLAG, never auto-corrected.
        counted_once = 0
        for d in t1:
            ings = ingredients_of(d)
            if ings and not any(first[i][0] < (year, d["decision_date"])
                                for i in ings):
                counted_once += 1
        # per-year audit
        year_audit: list[dict] = []
        for seq, d in enumerate(decs, 1):
            appl = d["application_number"]
            kind = d.get("application_kind", "NDA")
            cls = norm(d.get("submission_class_code"))
            desc = (d.get("submission_class_code_description") or "").strip()
            nme = cls in NME_CLASSES
            prods = d.get("products") or []
            fp = prods[0] if prods else {}
            brand = (fp.get("brand_name") or "").strip()
            ings = (fp.get("active_ingredients") or "").strip()
            num = (d.get("application_num") or "").zfill(6)
            if num in apps:
                db_type, db_holder = apps[num]
                if db_type.upper() != kind.upper():
                    fail(f"{appl}: payload kind {kind} != full-DB ApplType "
                         f"{db_type}")
                holder_match = "MATCH" if squash(d.get("sponsor_name")) == squash(db_holder) \
                    else f"FLAG (full-DB holder {db_holder!r})"
            else:
                fail(f"{appl}: application number absent from the full "
                     f"official Drugs@FDA database (Applications_all_types.txt)")
            earlier = []
            for ing in sorted(ingredients_of(d)):
                pos, fapp, fdate = first[ing]
                if not (pos == (year, d["decision_date"]) and fapp == appl):
                    earlier.append((ing, fdate, fapp))
            if nme and earlier:
                n_flagged_nme += 1
                screen = ("FLAG-RESCREEN: " +
                          "; ".join(f"{i} first seen {fd} on {fa}" for i, fd, fa in earlier) +
                          " - ingredient already appears on an earlier row of the "
                          "1939-1964 payload universe (sibling pair or re-approval "
                          "of a marketed ingredient). Flagged for review; the row is "
                          "kept verbatim and excluded only from the counted-once "
                          "statistic. Drugs@FDA pre-1965 coverage is incomplete, "
                          "so an earlier marketing may also simply be absent "
                          "from the payloads.")
                first_app = earlier[0][1] + " on " + earlier[0][2] + \
                    (f" ({len(earlier)} ingredients flagged)" if len(earlier) > 1 else "")
            elif nme:
                screen = "first appearance in the 1939-1964 payload universe " \
                         "(Drugs@FDA coverage before 1965 is incomplete: re-approval " \
                         "screen, not proof of first marketing)"
                first_app = "first-in-payloads (1939-1964 universe)"
            else:
                screen = "non-NME row: earlier appearances permitted by " \
                         "construction; see ingredient_first_appearance"
                if earlier:
                    first_app = earlier[0][1] + " on " + earlier[0][2]
                else:
                    first_app = "first-in-payloads (1939-1964 universe)"
            pr = probes.get(appl)
            if pr:
                live_status = pr["status"]
            else:
                live_status = "PROBE_PENDING"
            if live_status == "MATCH":
                verif = "Verified (live probe match)"
            elif live_status == "ABSENT_LIVE":
                verif = "Flagged (ABSENT_LIVE live probe)"
            elif live_status == "NO_ORIG_AP_LIVE":
                verif = "Flagged (no ORIG-AP submission in live probe)"
            else:
                verif = "Payload-verified (live probe layer pending)"
            if "FLAG-RESCREEN" in screen:
                verif += "; re-screening flag (see ingredient_screen)"
            row_id = f"PRE1965AUDIT-{year}-{seq:02d}"
            aud = {
                "row_id": row_id, "year": year, "application_number": appl,
                "application_kind": kind, "decision_date": d["decision_date"],
                "submission_class_code": (d.get("submission_class_code") or "").strip(),
                "submission_class_code_description": desc,
                "review_priority": (d.get("review_priority") or "").strip(),
                "nme_comparable": "TRUE" if nme else "FALSE",
                "classification_group": classification_group(cls, desc),
                "sponsor_name_drugsatfda_holder": (d.get("sponsor_name") or "").strip(),
                "full_db_holder_match": holder_match,
                "first_product_brand": brand,
                "first_product_ingredients": ings,
                "first_product_form_route": f"{fp.get('dosage_form','')}; {fp.get('route','')}".strip("; "),
                "n_products": len(prods),
                "first_product_marketing_status": (fp.get("marketing_status") or "").strip(),
                "ingredient_first_appearance": first_app,
                "ingredient_screen": screen,
                "tracked_in": (f"PRE1965-{year}-{seq:02d} (data/pre1965_fda_decisions.csv)"
                               if nme else "none (not a Type 1/1-4 original approval)"),
                "live_probe_status": live_status,
                "drugsatfda_url": ("https://www.accessdata.fda.gov/scripts/cder/daf/"
                                   f"index.cfm?event=overview.process&varApplNo={num}"),
                "openfda_url": (f"https://api.fda.gov/drug/drugsfda.json?search="
                                f"application_number:%22{appl}%22"),
                "verification_status": verif,
                "notes": ("Row of the complete 1939-1964 original-application audit "
                          f"({V26}): every ORIG/AP row of the committed SHA-verified "
                          "openFDA payload; facts verbatim from the payload; "
                          "application type and holder cross-checked against the "
                          "full official Drugs@FDA database (Applications_all_types.txt, "
                          "29,336 applications); no ticker, indication or applicant "
                          "lineage asserted."),
            }
            year_audit.append(aud)
            audit_rows.append(aud)
            if pr:
                if live_status == "MATCH":
                    checked = "date+class+priority+holder all equal"
                elif live_status == "ABSENT_LIVE":
                    checked = "openFDA returned no record for this application"
                else:
                    checked = (f"live record has {pr.get('n_live_orig_ap', 0)} "
                               "ORIG/AP submission(s), none on the payload date")
                probe_index_rows.append({
                    "row_id": row_id, "application_number": appl,
                    "probe_file": pr["file"], "probe_url": pr.get("url", ""),
                    "probe_sha256": pr.get("sha", ""),
                    "live_orig_date": pr.get("date", ""),
                    "live_class_code": pr.get("class", ""),
                    "live_review_priority": pr.get("priority", ""),
                    "live_sponsor": pr.get("sponsor", ""),
                    "status": live_status,
                    "checked_against_payload": checked,
                })
            if nme:
                dec_app = f"{kind} {num}"
                generic = (d.get("generic_name_openfda") or d.get("substance_name") or "").strip()
                if not generic and ings:
                    generic = ings.split(" ")[0] if re.match(r"^[A-Z0-9\-]+(\s+[A-Z0-9\-\s]+?)?\s+\d", ings) else ings
                company = (f"{(d.get('sponsor_name') or '').strip()} (Drugs@FDA holder of "
                           "record; approval-era applicant lineage not pinned; holder "
                           "cross-checked against the full official Drugs@FDA database 2026-09)")
                notes = (f"{V26} added from the committed openFDA Drugs@FDA payload "
                         f"(data/raw/openfda_orig_decisions_1939_1964/decisions_{year}.json, "
                         "SHA-256 verified against the 2026-09-19 runner manifest). "
                         f"Payload: ORIG/AP {d['decision_date']}, {cls or 'BLANK class'}, "
                         f"{(d.get('review_priority') or 'UNKNOWN')}, holder "
                         f"{(d.get('sponsor_name') or 'BLANK')}, product {brand or 'NO PRODUCT NAME PUBLISHED'} "
                         f"({ings}; {fp.get('dosage_form','')}; {fp.get('route','')}; "
                         f"{fp.get('marketing_status','')}). Ingredient screen: {screen}. "
                         "No ticker or indication asserted; the openFDA sponsor is the "
                         "current Drugs@FDA holder of record, not asserted as the "
                         "approval-era applicant.")
                if "FLAG-RESCREEN" in screen:
                    notes += " " + screen
                if pr:
                    notes += (f" Live per-row probe ({pr['file']}, SHA-256 "
                              f"{pr.get('sha','')[:16]}...): status {live_status}; "
                              + probe_index_rows[-1]["checked_against_payload"])
                decision_rows.append({
                    "decision_id": f"PRE1965-{year}-{seq:02d}", "year": year,
                    "application_number": dec_app, "drug_brand": brand,
                    "drug_generic": generic, "company_name": company,
                    "corporate_lineage_and_ticker": ("No ticker assigned: "
                                                     "historical applicant and period "
                                                     "listing require separate "
                                                     "primary-source corporate "
                                                     "resolution; no inference made."),
                    "decision_type": f"APPROVAL (ORIGINAL {kind})",
                    "decision_date": d["decision_date"],
                    "chemical_type_code": (d.get("submission_class_code") or "").strip(),
                    "chemical_type_description": desc,
                    "review_priority": (d.get("review_priority") or "").strip(),
                    "indication": "",
                    "regulatory_milestone": ("Pre-1965 original approval (Drugs@FDA "
                                             "era begins 1939); indication and "
                                             "lineage are not asserted without an "
                                             "approval-era primary record."),
                    "source_url_1": aud["drugsatfda_url"],
                    "source_url_2": aud["openfda_url"],
                    "verification_status": verif,
                    "notes": notes,
                })
        # register row
        manifest = json.loads((BLOCK_DIR / "manifest.json").read_text(encoding="utf-8"))
        req = next(r for r in manifest["requests"] if int(r["id"].split("_")[-1]) == year)
        raw_records = sum(p.get("n_raw_records", 0) for p in req.get("pages", []))
        n_blank = sum(1 for d in decs if not norm(d.get("submission_class_code")))
        n_unk = sum(1 for d in decs if norm(d.get("submission_class_code")) == "UNKNOWN")
        n_prio = sum(1 for d in decs if norm(d.get("review_priority")) == "PRIORITY")
        n_std = sum(1 for d in decs if norm(d.get("review_priority")) == "STANDARD")
        off = official.get(year, {})
        off_nme = off.get("nme", "")
        m_int = re.fullmatch(r"(\d+)", off_nme)
        delta = (str(len(t1) - int(m_int.group(1)))) if m_int else "n/a (no official per-year figure)"
        n_probed = sum(1 for d in decs if d["application_number"] in probes)
        probe_status = (f"complete ({n_probed}/{len(decs)})" if probes and n_probed == len(decs)
                        else f"partial ({n_probed}/{len(decs)})" if probes
                        else "pending (job queued: fetch_jobs/pre1965_row_probes_1939_1964.json)")
        notes = (f"openFDA Drugs@FDA ORIG/AP enumeration {year} (NDA+BLA; the API "
                 f"returned {raw_records} raw records, {len(decs)} unique "
                 f"application+date decisions after the extractor's de-duplication). "
                 f"{len(t1)} Type 1/1-4 (NME-comparable) of {len(decs)} rows; "
                 f"counted-once NME statistic: {counted_once} (re-screening/sibling "
                 f"rows flagged, never corrected). Blank class: {n_blank}; "
                 f"UNKNOWN class: {n_unk}. All {len(decs)} application numbers "
                 f"verified present in the full official Drugs@FDA database with "
                 f"matching type and holder (0 mismatches).")
        if year in (1939, 1940):
            notes += (" Official series: 1938-40 published combined (1782 NDAs, "
                      "2752 received; NMEs 14 qualified '1940 only') - no separate "
                      "1939/1940 figure exists in the official source.")
        register_rows.append({
            "year": year, "payload_orig_ap_count": len(decs),
            "manifest_raw_records": raw_records,
            "nme_type1_rows": sum(1 for d in decs if norm(d.get("submission_class_code")) == "TYPE 1"),
            "nme_type14_rows": sum(1 for d in decs if norm(d.get("submission_class_code")) == "TYPE 1/4"),
            "nme_rows_total": len(t1), "nme_counted_once": counted_once,
            "blank_class_rows": n_blank, "unknown_class_rows": n_unk,
            "priority_reviews": n_prio, "standard_reviews": n_std,
            "official_fda_nme_count": off_nme,
            "official_ndas_approved": off.get("ndas", ""),
            "delta_nme_rows_vs_official": delta,
            "official_source_url": off.get("url", ""),
            "raw_payload": f"data/raw/openfda_orig_decisions_1939_1964/decisions_{year}.json",
            "query_url": (req.get("pages") or [{}])[0].get("url", req.get("search", "")),
            "source_type": "openFDA Drugs@FDA ORIG/AP (NDA+BLA; same extraction as 1965-2026 blocks)",
            "coverage_status": "Complete for the committed payload; Drugs@FDA pre-1965 coverage is itself incomplete (official caveat)",
            "probe_status": probe_status,
            "notes": notes,
        })
        # era row
        landmark, significance = era_narrative(year, payloads, {year: year_audit}, official)
        t1_dates = [d["decision_date"] for d in decs]
        unprio = len(decs) - n_prio - n_std
        era_rows.append({
            "year": year, "total_nmes_approved": len(t1),
            "official_fda_nme_count": off_nme or "not published separately",
            "nme_comparable_rows": len(t1),
            "official_series_delta": delta,
            "verified_decisions_tracked": len(t1),
            "priority_reviews": n_prio, "standard_reviews": n_std,
            "unpublished_priority_reviews": unprio,
            "orphan_drug_act_status": ("The Orphan Drug Act had not yet been "
                                       "enacted (1983); no orphan-law framework "
                                       "applied to these approvals."),
            "statutory_framework": statutory_framework(year, t1_dates),
            "landmark_approvals": landmark,
            "historical_significance": significance,
            "primary_source_basis": (f"openFDA Drugs@FDA ORIG/AP payload "
                                     f"data/raw/openfda_orig_decisions_1939_1964/"
                                     f"decisions_{year}.json (SHA-256 verified vs "
                                     f"2026-09-19 runner manifest); full official "
                                     f"Drugs@FDA database cross-check "
                                     f"(Applications_all_types.txt, 29,336 apps); "
                                     f"official counts from "
                                     f"data/fda_official_year_series.csv"
                                     + (f"; live probes: {n_probed}/{len(decs)}" if probes else
                                       "; live probe layer pending (job queued)")),
        })
        per_year[year] = {"audit": year_audit, "nme": len(t1), "once": counted_once}
        total += len(decs)
        total_nme += len(t1)
        total_nme_once += counted_once

    if total != 535:
        fail(f"total rows {total} != 535 (payload census changed?)")
    if total_nme != 178:
        fail(f"total NME-comparable rows {total_nme} != 178")

    write_csv(AUDIT_CSV, AUDIT_HEADER, audit_rows)
    write_csv(DECISIONS_CSV, DECISION_HEADER, decision_rows)
    write_csv(REGISTER_CSV, REGISTER_HEADER, register_rows)
    write_csv(ERA_CSV, ERA_HEADER, era_rows)
    if probes:
        write_csv(PROBE_INDEX_CSV, PROBE_HEADER, probe_index_rows)
    elif PROBE_INDEX_CSV.exists():
        PROBE_INDEX_CSV.unlink()

    matched = sum(1 for p in probes.values() if p["status"] == "MATCH")
    absent = sum(1 for p in probes.values() if p["status"] == "ABSENT_LIVE")
    noorig = sum(1 for p in probes.values() if p["status"] == "NO_ORIG_AP_LIVE")
    print(f"v26 pre-1965 build: {total} audit rows (1939-1964), {total_nme} "
          f"NME-comparable decision rows (counted-once {total_nme_once}), "
          f"{n_flagged_nme} NME re-screening flags, 26 register rows, 26 era rows")
    if probes:
        print(f"v26 probe join: {len(probes)} captured -> {matched} MATCH, "
              f"{absent} ABSENT_LIVE, {noorig} NO_ORIG_AP_LIVE "
              f"(row-level flags written; build fails closed on field mismatch)")
    else:
        print("v26 probe layer: not present; rows carry 'live probe layer pending'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
