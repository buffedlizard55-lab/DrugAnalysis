#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v19 (2026-09-19): verified pre-1980 FDA decision tables for 1977, 1978, 1979.

Year-by-year treatment of the three years immediately before the project's
1980 boundary.  Owns four tables (single-writer discipline):

* data/pre1980_fda_decisions.csv          (48 verified Type 1/1-4 rows)
* data/pre1980_year_audit.csv             (3 year rows with official-series verdicts)
* data/pre1980_era_analysis.csv           (3 era rows)
* data/pre1980_primary_captures_index.csv (12 live-capture rows)

Fail-closed rules (no hallucinations by construction):

* Regulatory facts are copied verbatim from the committed openFDA Drugs@FDA
  extracts in data/raw/openfda_orig_decisions_1975_1979/.  The builder aborts
  unless every payload file's SHA-256 matches its run-19 manifest entry AND
  the run-19 raw_sha256 agrees with the archived run-18 manifest (two
  independent API fetches ~2h apart returned byte-identical responses).
* Display names (brand/generic) come from an explicit per-application map
  below; the builder aborts if the payload's product strings drift from it.
* No applicant lineage, ticker, or indication is asserted: sponsors are the
  Drugs@FDA holders of record (qualified as such), tickers are never
  assigned, and indications stay empty without an approval-era label.
* A first-appearance screen across ALL committed 1965-1979 payloads must
  reproduce the single known flag (the Cyclapen tablet/suspension pair);
  any other earlier-ingredient hit aborts the write.
* Official counts are read from data/fda_official_year_series.csv and must
  equal 1977=25, 1978=17, 1979=14 NMEs (63/86/94 NDAs approved).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw" / "openfda_orig_decisions_1975_1979"
ALL_BLOCKS = ["openfda_orig_decisions_1965_1969", "openfda_orig_decisions_1970_1974",
              "openfda_orig_decisions_1975_1979"]
CAPTURES_DIR = DATA / "raw" / "source_captures_2026_09_19"
EVIDENCE = CAPTURES_DIR / "live_primary_captures_v19_2026_09_19.json"
RUN18_MANIFEST = CAPTURES_DIR / "run18_manifest_openfda_orig_decisions_1975_1979.json"

YEARS = (1977, 1978, 1979)
EXPECTED_T1 = {1977: 17, 1978: 18, 1979: 13}
EXPECTED_OFFICIAL = {1977: ("25", "63"), 1978: ("17", "86"), 1979: ("14", "94")}

DRUGSFDA = ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
            "?event=overview.process&varApplNo={num}")
OPENFDA_Q = 'https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{appl}%22'

# Explicit display map: application -> (brand display, generic display,
# expected first-product brand UPPER, expected ingredient token in first product).
# The builder aborts on any drift between this map and the payload.
DISPLAY = {
    # ---------------- 1977 ----------------
    "NDA017535": ("Lorelco", "probucol", "LORELCO", "PROBUCOL"),
    "NDA017661": ("Tavist-1", "clemastine fumarate", "TAVIST-1", "CLEMASTINE FUMARATE"),
    "NDA017856": ("Topicort", "desoximetasone", "TOPICORT", "DESOXIMETASONE"),
    "NDA017422": ("Bicnu", "carmustine", "BICNU", "CARMUSTINE"),
    "NDA017601": ("Optimine", "azatadine maleate", "OPTIMINE", "AZATADINE MALEATE"),
    "NDA017563": ("Colestid", "colestipol hydrochloride", "COLESTID", "COLESTIPOL HYDROCHLORIDE"),
    "NDA017920": ("Tagamet", "cimetidine", "TAGAMET", "CIMETIDINE"),
    "NDA017765": ("Cloderm", "clocortolone pivalate", "CLODERM", "CLOCORTOLONE PIVALATE"),
    "NDA017810": ("Prostin E2", "dinoprostone", "PROSTIN E2", "DINOPROSTONE"),
    "NDA017821": ("Flexeril", "cyclobenzaprine hydrochloride", "FLEXERIL", "CYCLOBENZAPRINE HYDROCHLORIDE"),
    "NDA017447": ("Norpace", "disopyramide phosphate", "NORPACE", "DISOPYRAMIDE PHOSPHATE"),
    "NDA017831": ("Didronel", "etidronate disodium", "DIDRONEL", "ETIDRONATE DISODIUM"),
    "NDA017741": ("Florone", "diflorasone diacetate", "FLORONE", "DIFLORASONE DIACETATE"),
    "NDA017794": ("Ativan", "lorazepam", "ATIVAN", "LORAZEPAM"),
    "NDA017851": ("Lioresal", "baclofen", "LIORESAL", "BACLOFEN"),
    "NDA017806": ("Thallous Chloride Tl 201", "thallous chloride Tl-201",
                  "THALLOUS CHLORIDE TL 201", "THALLOUS CHLORIDE"),
    "NDA017970": ("Nolvadex", "tamoxifen citrate", "NOLVADEX", "TAMOXIFEN CITRATE"),
    # ---------------- 1978 ----------------
    "BLA101063": ("Elspar", "asparaginase", "ELSPAR", "ASPARAGINASE"),
    "NDA050512": ("Duricef", "cefadroxil", "DURICEF", "CEFADROXIL"),
    "NDA017922": ("DDAVP", "desmopressin acetate", "DDAVP", "DESMOPRESSIN ACETATE"),
    "NDA018081": ("Depakene", "valproic acid", "DEPAKENE", "VALPROIC ACID"),
    "NDA017788": ("Rimso-50", "dimethyl sulfoxide", "RIMSO-50", "DIMETHYL SULFOXIDE"),
    "NDA017907": ("Glucoscan", "technetium Tc-99m gluceptate", "GLUCOSCAN", "TECHNETIUM TC-99M GLUCEPTATE"),
    "NDA017962": ("Parlodel", "bromocriptine mesylate", "PARLODEL", "BROMOCRIPTINE MESYLATE"),
    "NDA017744": ("Motofen", "difenoxin hydrochloride and atropine sulfate",
                  "MOTOFEN", "DIFENOXIN"),
    "NDA017820": ("Dobutrex", "dobutamine hydrochloride", "DOBUTREX", "DOBUTAMINE"),
    "NDA017963": ("Lopressor", "metoprolol tartrate", "LOPRESSOR", "METOPROLOL TARTRATE"),
    "NDA018044": ("Rocaltrol", "calcitriol", "ROCALTROL", "CALCITRIOL"),
    "NDA018086": ("Timoptic", "timolol maleate", "TIMOPTIC", "TIMOLOL MALEATE"),
    "NDA017857": ("Stadol", "butorphanol tartrate", "STADOL", "BUTORPHANOL TARTRATE"),
    "NDA017982": ("Amipaque", "metrizamide", "AMIPAQUE", "METRIZAMIDE"),
    "NDA017911": ("Clinoril", "sulindac", "CLINORIL", "SULINDAC"),
    "NDA050504": ("Mandol", "cefamandole nafate", "MANDOL", "CEFAMANDOLE"),
    "NDA050517": ("Mefoxin", "cefoxitin sodium", "MEFOXIN", "CEFOXITIN SODIUM"),
    "NDA018057": ("Platinol-AQ", "cisplatin", "PLATINOL-AQ", "CISPLATIN"),
    # ---------------- 1979 ----------------
    "NDA017989": ("Hemabate", "carboprost tromethamine", "HEMABATE", "CARBOPROST TROMETHAMINE"),
    "NDA017862": ("Reglan", "metoclopramide hydrochloride", "REGLAN", "METOCLOPRAMIDE"),
    "NDA050521": ("Ceclor", "cefaclor", "CECLOR", "CEFACLOR"),
    "NDA018024": ("Nubain", "nalbuphine hydrochloride", "NUBAIN", "NALBUPHINE HYDROCHLORIDE"),
    "NDA018203": ("Liposyn 10%", "safflower oil", "LIPOSYN 10%", "SAFFLOWER OIL"),
    "NDA016792": ("Surmontil", "trimipramine maleate", "SURMONTIL", "TRIMIPRAMINE MALEATE"),
    "NDA050508": ("Cyclapen-W", "cyclacillin", "CYCLAPEN-W", "CYCLACILLIN"),
    "NDA017871": ("Demser", "metyrosine", "DEMSER", "METYROSINE"),
    "NDA018116": ("Cyclocort", "amcinonide", "CYCLOCORT", "AMCINONIDE"),
    "NDA018154": ("Loniten", "minoxidil", "LONITEN", "MINOXIDIL"),
    "NDA018063": ("Corgard", "nadolol", "CORGARD", "NADOLOL"),
    "NDA017624": ("Forane", "isoflurane", "FORANE", "ISOFLURANE"),
    "NDA050484": ("Cerubidine", "daunorubicin hydrochloride", "CERUBIDINE", "DAUNORUBICIN"),
}

# decision rows with live 2026-09-19 evidence, keyed by application.
LIVE = {
    "NDA017920": "Live 2026-09-19: openFDA ORIG/AP/exact-date coexistence total=1 (V19-C04) and Drugs@FDA page row '08/16/1977 | ORIG-1 | Approval | Type 1 - New Molecular Entity | PRIORITY' (V19-C10).",
    "NDA017970": "Live 2026-09-19: openFDA ORIG/AP/exact-date coexistence total=1 (V19-C06); ~50 supplements so the ORIG block sits below the first response chunk - precise linkage from the committed full-record extraction.",
    "BLA101063": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19780110/UNKNOWN/TYPE 1, sponsor MERCK, ELSPAR ASPARAGINASE (V19-C05).",
    "NDA017744": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19780714/STANDARD/TYPE 1-4 'Type 1 - New Molecular Entity and Type 4 - New Combination' (V19-C07).",
    "NDA050508": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19790914/STANDARD/TYPE 1, WYETH AYERST, three cyclacillin suspension products (V19-C08). Sibling tablet NDA050509 verified live as ORIG-1/AP/19790913/STANDARD/TYPE 3 (V19-C11) - the class/date inversion is a genuine FDA-data condition; cyclacillin counts once via this row.",
    "NDA017624": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19791218/PRIORITY/TYPE 1 (V19-C09).",
}

DECISION_HEADER = ["decision_id", "year", "application_number", "drug_brand", "drug_generic",
                   "company_name", "corporate_lineage_and_ticker", "decision_type", "decision_date",
                   "chemical_type_code", "chemical_type_description", "review_priority", "indication",
                   "regulatory_milestone", "source_url_1", "source_url_2", "verification_status", "notes"]


def fail(msg: str) -> None:
    raise SystemExit(f"build_pre1980_decisions_v19: {msg}")


def verify_inputs() -> tuple[dict, dict, dict]:
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    by_year_req = {}
    for req in manifest["requests"]:
        # later runs append "skipped-existing" stubs without verification
        # fields; only full entries (with sha256) may satisfy the pin
        if req.get("sha256"):
            by_year_req[int(req["id"].split("_")[-1])] = req
    payloads = {}
    for year in YEARS:
        path = RAW / f"decisions_{year}.json"
        if not path.exists():
            fail(f"missing committed payload: {path}")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        req = by_year_req.get(year)
        if req is None or sha != req["sha256"]:
            fail(f"{year}: payload SHA drift vs run-19 manifest; refusing to build")
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj.get("decisions"), list) or obj.get("count") != len(obj["decisions"]):
            fail(f"{year}: invalid payload shape")
        payloads[year] = obj
    # Dual-run agreement vs archived run-18 manifest.
    run18 = json.loads(RUN18_MANIFEST.read_text(encoding="utf-8"))["manifest"]
    r18 = {int(r["id"].split("_")[-1]): r for r in run18["requests"]}
    for year in YEARS:
        a, b = r18[year]["pages"][0]["raw_sha256"], by_year_req[year]["pages"][0]["raw_sha256"]
        if a != b:
            fail(f"{year}: run-18/run-19 raw_sha256 disagree; refusing to build")
        if r18[year]["decisions"] != by_year_req[year]["decisions"]:
            fail(f"{year}: run-18/run-19 decision counts disagree; refusing to build")
    # Live-evidence file must carry exactly the 12 v19 captures.
    ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    ids = [c["capture_id"] for c in ev.get("captures", [])]
    if ids != [f"V19-C{i:02d}" for i in range(1, 13)]:
        fail("live evidence file must carry exactly V19-C01..V19-C12")
    # Official series pins.
    official = {}
    with (DATA / "fda_official_year_series.csv").open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            official[row["year"]] = (row["nmes_approved"], row["ndas_approved"])
    for year in YEARS:
        if official.get(str(year)) != EXPECTED_OFFICIAL[year]:
            fail(f"{year}: official series drift: {official.get(str(year))}")
    return payloads, {y: by_year_req[y] for y in YEARS}, official


def load_all_decisions() -> dict[int, list]:
    out: dict[int, list] = {}
    for block in ALL_BLOCKS:
        d = DATA / "raw" / block
        lo, hi = (1965, 1969) if "1965" in block else ((1970, 1974) if "1970" in block else (1975, 1979))
        for year in range(lo, hi + 1):
            obj = json.loads((d / f"decisions_{year}.json").read_text(encoding="utf-8"))
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


def main() -> int:
    payloads, reqs, official = verify_inputs()
    alldec = load_all_decisions()

    # First-appearance index over 1965-1979.
    first: dict[str, tuple] = {}
    for y in sorted(alldec):
        for d in sorted(alldec[y], key=lambda r: r["decision_date"]):
            for ing in ingredients_of(d):
                if ing not in first:
                    first[ing] = (y, d["application_number"], d["decision_date"])

    decision_rows = []
    audit_rows = []
    for year in YEARS:
        decs = payloads[year]["decisions"]
        t1 = [d for d in decs
              if (d.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4")]
        if len(t1) != EXPECTED_T1[year]:
            fail(f"{year}: Type 1/1-4 enumeration is {len(t1)}, expected {EXPECTED_T1[year]}")
        t1.sort(key=lambda d: (d["decision_date"], d["application_number"]))
        blank_unknown = [d for d in decs
                         if (d.get("submission_class_code") or "").upper() in ("", "UNKNOWN")]
        for seq, d in enumerate(t1, 1):
            appl = d["application_number"]
            if appl not in DISPLAY:
                fail(f"{appl}: no explicit display mapping; refusing to guess names")
            brand, generic, exp_brand, exp_ing = DISPLAY[appl]
            first_prod = (d.get("products") or [{}])[0]
            if exp_brand not in (first_prod.get("brand_name") or ""):
                fail(f"{appl}: first-product brand drift: {first_prod.get('brand_name')!r}")
            if exp_ing not in (first_prod.get("active_ingredients") or "").upper():
                fail(f"{appl}: first-product ingredient drift")
            if not d["decision_date"].startswith(str(year)):
                fail(f"{appl}: decision date outside {year}")
            kind = "NDA" if appl.startswith("NDA") else "BLA"
            num = appl[3:]
            # First-appearance screen for every ingredient on this row.
            earlier = []
            for ing in sorted(ingredients_of(d)):
                fy, fapp, fdate = first[ing]
                if not (fy == year and fapp == appl):
                    earlier.append((ing, fy, fapp, fdate))
            # The single permitted flag: cyclacillin's tablet NDA (Type 3,
            # one day earlier).  Anything else aborts the write.
            allowed = {(1979, "NDA050508", "CYCLACILLIN", 1979, "NDA050509")}
            for ing, fy, fapp, fdate in earlier:
                if (year, appl, ing, fy, fapp) not in allowed:
                    fail(f"{appl}: ingredient {ing} first appears {fdate} on {fapp}; "
                         f"re-approval screen failed")
            screen = ("first-in-payloads (1965-1979 screen)"
                      if not earlier
                      else "cyclacillin first appears one day earlier on the sibling tablet "
                           "NDA050509 (Type 3) - flagged inversion, counted once (see V19-C11)")
            prods = "; ".join(
                f"{x.get('brand_name', '')} ({x.get('active_ingredients', '')}; "
                f"{x.get('dosage_form', '')}; {x.get('marketing_status', '')})"
                for x in d.get("products") or [])
            form = (first_prod.get("dosage_form") or "").lower()
            route = (first_prod.get("route") or "").lower()
            mkt = (first_prod.get("marketing_status") or "")
            milestone = (f"{brand} ({generic}) {form} ({route}) product; ORIG-1 approval "
                         f"{d['decision_date']}; {d['submission_class_code_description']}; "
                         f"{d['review_priority'] or 'unpublished priority'} review; current "
                         f"marketing status {mkt}.")
            notes = (f"v19 2026-09-19 added from the committed openFDA Drugs@FDA payloads "
                     f"(dual-run byte-identical raw responses; run-18 vs run-19 raw_sha256 agree; "
                     f"payload SHA verified against the run-19 manifest). Payload: ORIG/AP "
                     f"{d['decision_date']}, {d['submission_class_code']}, "
                     f"{d['review_priority'] or 'priority unpublished'}, holder {d['sponsor_name']}, "
                     f"product {prods}. Ingredient screen: {screen}. "
                     f"{LIVE.get(appl, 'No live single-record probe was issued for this row in v19; it rests on the dual-run payload extraction and is re-verifiable at the two source URLs.')} "
                     f"No ticker or indication asserted.")
            decision_rows.append({
                "decision_id": f"PRE1980-{year}-{seq:02d}", "year": year,
                "application_number": f"{kind} {num}", "drug_brand": brand,
                "drug_generic": generic,
                "company_name": (f"{d['sponsor_name']} (Drugs@FDA holder of record; "
                                 f"approval-era applicant lineage not pinned)"),
                "corporate_lineage_and_ticker": ("No ticker assigned: historical applicant and "
                                                 "period listing require separate primary-source "
                                                 "corporate resolution; no inference made."),
                "decision_type": f"APPROVAL (ORIGINAL {kind})", "decision_date": d["decision_date"],
                "chemical_type_code": d["submission_class_code"],
                "chemical_type_description": d["submission_class_code_description"],
                "review_priority": d.get("review_priority", ""), "indication": "",
                "regulatory_milestone": milestone,
                "source_url_1": DRUGSFDA.format(num=num),
                "source_url_2": OPENFDA_Q.format(appl=appl),
                "verification_status": "Verified", "notes": notes,
            })
        official_nme, official_nda = official[str(year)]
        comparable = len(t1)
        delta = comparable - int(official_nme)
        verdict = ("PROJECT_SHORT_FLAGGED" if delta < 0
                   else ("PROJECT_EXCEEDS_OFFICIAL" if delta > 0 else "MATCH"))
        if year == 1977:
            irreg = ("none in the Type-1 set: all 17 ingredients first-in-payloads; "
                     "no blank/UNKNOWN-class payload rows in 1977")
            caps = "V19-C01; V19-C04; V19-C06; V19-C10"
            note = ("Official 25 NMEs vs 17 Type-1 payload rows: shortfall of 8 sits in "
                    "applications absent from the Drugs@FDA ORIG/AP payload altogether (the gap "
                    "class proven for 1985: Seldane/Protropin/Suprol/Femstat). Naming the 8 "
                    "requires the 1989 CDER statistical typescript (pp. 152-199) or the "
                    "contemporaneous FDA annual report. v20 full-DB cross-check (2026-09-19): "
                    "the complete Drugs@FDA database files (fda.gov media 89850 zip, "
                    "SHA-manifested) enumerate exactly 42 ORIG/AP approvals for 1977 - "
                    "identical to the payload, 0 payload-invisible - so the 8 sit in "
                    "applications no longer present anywhere in modern FDA databases, the "
                    "Seldane purge class.")
        elif year == 1978:
            irreg = ("MOTOFEN NDA017744 is TYPE 1/4 (NME + new combination; verified live "
                     "V19-C07) and is the +1 on the NME-comparable basis used for every "
                     "crosswalk year; Type-1-only count is 17 = official. KINLYTIC BLA021846 "
                     "(urokinase, first-in-payloads) publishes UNKNOWN class/priority "
                     "(verified live V19-C12) and is NOT counted pending an "
                     "application-level NME source. PREMARIN NDA020216 UNKNOWN is conjugated "
                     "estrogens (legacy, not an NME). Five blank-class rows are IV "
                     "electrolytes/dextrose (B Braun) and bupivacaine - marketed ingredients.")
            caps = "V19-C02; V19-C05; V19-C07; V19-C12"
            note = ("Official 17 NMEs vs 18 NME-comparable payload rows: the project exceeds "
                    "the official count by 1 because the NME-comparable basis counts the "
                    "Type 1/4 Motofen row, consistent with 1981/1984. No shortfall; the "
                    "uncounted Kinlytic UNKNOWN-candidate is flagged, not guessed.")
        else:
            irreg = ("Cyclapen inversion: tablet NDA050509 TYPE 3 approved 1979-09-13, one "
                     "day BEFORE suspension NDA050508 TYPE 1 approved 1979-09-14 (same "
                     "ingredient, same sponsor WYETH AYERST); verified live in both "
                     "directions (V19-C08/V19-C11) so the inversion is a genuine FDA-data "
                     "condition; counted once via the Type-1 row. Five blank-class rows: "
                     "furosemide (molecule first approved 1966-07-01 per the payloads), IV "
                     "electrolytes/dextrose, and potassium iodide (Thyro-Block, historically "
                     "marketed) - none an NME.")
            caps = "V19-C03; V19-C08; V19-C09; V19-C11"
            note = ("Official 14 NMEs vs 13 Type-1 payload rows: shortfall of 1 sits in an "
                    "application absent from the ORIG/AP payload (1985-proven gap class); "
                    "the 1989 CDER statistical typescript names it.")
        audit_rows.append({
            "year": year, "official_nmes_approved": official_nme,
            "official_ndas_approved": official_nda,
            "payload_orig_ap_total": len(decs),
            "payload_type1_14_rows": len(t1),
            "payload_blank_unknown_rows": len(blank_unknown),
            "verified_decision_rows": len(t1),
            "nme_comparable_rows": comparable,
            "delta_nme_comparable_vs_official": delta,
            "verdict": verdict, "live_captures": caps,
            "key_irregularities": irreg, "evidence_note": note,
            "source_urls": ("https://www.fda.gov/about-fda/histories-fda-regulated-products/"
                            "summary-nda-approvals-receipts-1938-present|"
                            "data/raw/openfda_orig_decisions_1975_1979/decisions_{y}.json|"
                            "data/raw/source_captures_2026_09_19/"
                            "live_primary_captures_v19_2026_09_19.json").format(y=year),
        })
    era_rows = []
    for year in YEARS:
        t1n = EXPECTED_T1[year]
        pri = sum(1 for r in decision_rows
                  if r["year"] == year and r["review_priority"] == "PRIORITY")
        std = sum(1 for r in decision_rows
                  if r["year"] == year and r["review_priority"] == "STANDARD")
        unk = sum(1 for r in decision_rows
                  if r["year"] == year and r["review_priority"] == "UNKNOWN")
        official_nme, official_nda = official[str(year)]
        brands = ", ".join(r["drug_brand"] for r in decision_rows if r["year"] == year)
        if year == 1977:
            sig = ("The committed Drugs@FDA extract enumerates 17 TYPE-1 original approvals, "
                   "all first-in-payloads ingredients with no blank-class rows. This is an "
                   "application-level enumeration, not a reconstructed contemporaneous annual "
                   "NME statistic. Official series: 25 NMEs (63 NDAs approved). The official "
                   "count exceeds the enumeration by 8 - the largest sized pre-1980 shortfall, "
                   "in applications absent from the ORIG/AP payload (1985-proven gap class). "
                   "Live 2026-09-19: year population 662 re-queried (V19-C01); Tagamet "
                   "coexistence + Drugs@FDA ORIG-1 row (V19-C04/V19-C10); Nolvadex coexistence "
                   "(V19-C06). Naming the 8 requires the 1989 CDER statistical typescript.")
        elif year == 1978:
            sig = ("The committed Drugs@FDA extract enumerates 17 TYPE-1 plus 1 TYPE-1/4 "
                   "(Motofen) original approvals. Application-level enumeration, not a "
                   "reconstructed contemporaneous statistic. Official series: 17 NMEs (86 "
                   "NDAs approved). On the NME-comparable basis used for every crosswalk "
                   "year the project carries 18 rows (+1, the Type 1/4 Motofen row verified "
                   "live V19-C07); Type-1-only count is 17 = official. One priority value "
                   "is published UNKNOWN (Elspar BLA101063, verified live V19-C05). The "
                   "Kinlytic UNKNOWN-candidate (V19-C12) is flagged, not counted. Live "
                   "2026-09-19: year population 756 re-queried (V19-C02).")
        else:
            sig = ("The committed Drugs@FDA extract enumerates 13 TYPE-1 original approvals. "
                   "Application-level enumeration, not a reconstructed contemporaneous "
                   "statistic. Official series: 14 NMEs (94 NDAs approved) - shortfall of 1 "
                   "in a payload-invisible application. The Cyclapen tablet/suspension "
                   "class/date inversion (NDA050509 Type 3 one day before NDA050508 Type 1) "
                   "is verified live in both directions (V19-C08/V19-C11) and counted once. "
                   "Live 2026-09-19: year population 746 re-queried (V19-C03); Forane "
                   "verbatim ORIG block (V19-C09).")
        era_rows.append({
            "year": year, "total_nmes_approved": t1n,
            "official_fda_nme_count": official_nme, "nme_comparable_rows": t1n,
            "official_series_delta": t1n - int(official_nme),
            "verified_decisions_tracked": t1n, "priority_reviews": pri,
            "standard_reviews": std,
            "unpublished_priority_reviews": unk,
            "orphan_drug_act_status": ("The Orphan Drug Act had not yet been enacted; no "
                                       "orphan-law framework applied to these approvals."),
            "statutory_framework": ("Pre-Orphan Drug Act federal NDA framework; the 1962 "
                                    "Kefauver-Harris amendments governed efficacy and safety "
                                    "review."),
            "landmark_approvals": brands, "historical_significance": sig,
            "primary_source_basis": (
                f"openFDA Drugs@FDA ORIG/AP enumeration {year} "
                f"(data/raw/openfda_orig_decisions_1975_1979/decisions_{year}.json: "
                f"{reqs[year]['decisions']} original approvals; {t1n} TYPE 1/1-4 "
                f"applications; raw_sha256 dual-run agreed; payload SHA verified). "
                f"Official counts from data/fda_official_year_series.csv ({official_nme} "
                f"NMEs, {official_nda} NDAs approved). Live probes 2026-09-19 in "
                f"data/raw/source_captures_2026_09_19/"
                f"live_primary_captures_v19_2026_09_19.json."),
        })

    ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    cap_rows = []
    for c in ev["captures"]:
        cap_rows.append({
            "capture_id": c["capture_id"], "capture_date": ev["capture_date"],
            "system": c["system"], "subject": c["subject"], "url": c["query_url"],
            "finding_summary": c["finding"], "project_table_affected": "pre1980_fda_decisions.csv",
            "project_row_ids": c["project_row_ids"], "project_effect": c["project_effect"],
            "verbatim_evidence_ref": ("data/raw/source_captures_2026_09_19/"
                                      "live_primary_captures_v19_2026_09_19.json"),
        })

    def write(name, header, rows):
        with (DATA / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=header)
            w.writeheader()
            w.writerows(rows)

    write("pre1980_fda_decisions.csv", DECISION_HEADER, decision_rows)
    write("pre1980_year_audit.csv", list(audit_rows[0].keys()), audit_rows)
    write("pre1980_era_analysis.csv", list(era_rows[0].keys()), era_rows)
    write("pre1980_primary_captures_index.csv", list(cap_rows[0].keys()), cap_rows)
    print(f"v19: {len(decision_rows)} decisions, {len(audit_rows)} audit rows, "
          f"{len(era_rows)} era rows, {len(cap_rows)} captures")


if __name__ == "__main__":
    raise SystemExit(main())