#!/usr/bin/env python3
"""Build data/fda_original_non_nme_decisions.csv

FDA original NDA/BLA approvals that are *not* Type 1 NMEs (those live in
data/fda_decisions_master.csv for 1985-2026 and in
data/pre1985_fda_decisions.csv for the pre-1985 historical era).

Coverage: 1983-2026 (v15, 2026-09-18 backward extension into 1983-1984).
The focus years 1983/1984/1985 therefore carry the complete Drugs@FDA
original-approval enumeration: every ORIG/AP record in the committed
payloads is tracked in exactly one project table (verified by
data/focus_years_1983_1985_audit.csv).

Why this file exists
--------------------
FDA approves only ~50 novel drugs a year. The 1,427-row NME master (1985–2026) already
matches FDA's official year counts, so 1,000 *new novel* approvals do not
exist and must not be invented. Original approvals of other chemical types
are the honest next body of FDA decisions:

  Type 2  new active ingredient (includes many 351(k) biosimilars)
  Type 3  new dosage form
  Type 4  new combination
  Type 5  new formulation or new manufacturer
  Type 6/9/10  new indication filed as a distinct original
  Type 7  already marketed without an approved NDA
  Type 8  partial Rx-to-OTC
  BLA class unpublished  — frequently a biosimilar; flagged, never guessed

Source
------
data/raw/openfda_orig_decisions_2011_2026/decisions_<year>.json (1985-2026)
data/raw/openfda_orig_decisions_1980_1984/decisions_<year>.json (1983-1984)
produced on GitHub Actions by fetch_jobs/openfda_orig_decisions_2011_2026.json
and fetch_jobs/openfda_orig_decisions_1980_1984.json from
api.fda.gov/drug/drugsfda.json. Every request URL and payload SHA-256
is in the matching directory's manifest.json.

Hallucination controls
----------------------
* Every field is copied verbatim from the openFDA extract. Nothing is inferred.
* Type 1 NMEs are excluded (they belong on the novel-approval master). They
  are written instead to data/fda_type1_not_in_nme_master.csv IF they cannot
  be matched to an existing master row — flagged for review, never silently
  merged (that would break the official NME year-count audit).
* PRE-1985 (1983-1984) Type 1/1-4 NMEs belong to data/pre1985_fda_decisions.csv
  (v13/v14 verified rows). A pre-1985 Type 1/1-4 application that is NOT in
  that table ABORTS the build instead of being invented or merged. The two
  non-Type-1 applications already tracked there (furosemide oral-solution
  NDA018413, Trandate NDA018716) are likewise excluded by application number.
* Indication text is NOT synthesised: openFDA's original-approval extract has
  no structured indication field. Each row links Drugs@FDA and the openFDA
  application query instead.
* Sponsor/ticker resolution reuses scripts/build_supplement_decisions.py
  (SEC company_tickers.json + verified master lineage). Unresolved sponsors
  get ticker UNRESOLVED — never guessed. PRE-1985 rows additionally state
  that the openFDA sponsor is the *current* Drugs@FDA holder and is not
  asserted as the historical applicant or a period listing.
* Medical-gas originals are kept (they are real FDA decisions) but labelled
  so they are never scored as biotech clinical-trial conversions.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw" / "openfda_orig_decisions_2011_2026"
RAW_PRE = DATA / "raw" / "openfda_orig_decisions_1980_1984"
OUT = DATA / "fda_original_non_nme_decisions.csv"
OUT_T1 = DATA / "fda_type1_not_in_nme_master.csv"
OUT_YEAR = DATA / "fda_orig_year_register.csv"

# Import the already-audited sponsor resolver rather than re-implementing it.
_spec = importlib.util.spec_from_file_location(
    "suppl_mod", ROOT / "scripts" / "build_supplement_decisions.py"
)
suppl_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(suppl_mod)

APPL_FROM_MASTER = re.compile(
    r"(?:NDA|BLA|ANDA)\s*[- ]?(\d{5,6})"
    r"|appl\s*N?(\d{5,6})"
    r"|ApplNo[=:](\d{5,6})"
    r"|varApplNo=(\d{5,6})"
    r"|N(\d{6})",
    re.I,
)
FR_NOISE = re.compile(r"\s*\*\*.*$")
BIOSIM_SUFFIX = re.compile(r"-[A-Z]{4}\b", re.I)
GAS_NAMES = {
    "oxygen", "nitrogen", "nitrous oxide", "carbon dioxide", "helium",
    "medical air", "air", "carbon dioxide usp", "oxygen usp",
}


def is_type1_nme(rec: dict) -> bool:
    """True only for Type 1 (NME) and Type 1/4. Type 10 is a different class."""
    code = (rec.get("submission_class_code") or "").strip().upper()
    desc = (rec.get("submission_class_code_description") or "").strip()
    if code in {"TYPE 1", "TYPE 1/4"}:
        return True
    if "Type 1 - New Molecular Entity" in desc:
        return True
    return False


def chemical_group(rec: dict) -> str:
    desc = (rec.get("submission_class_code_description") or "").strip()
    code = (rec.get("submission_class_code") or "").strip()
    kind = rec.get("application_kind") or ""
    d = desc.lower()
    brand = brand_of(rec).lower()
    generic = generic_of(rec).lower()
    if "medical gas" in d or any(g in brand or g in generic for g in GAS_NAMES if g in (brand, generic) or brand.startswith(g) or generic.startswith(g)):
        if any(g == brand or g == generic or brand.startswith(g + ",") or generic.startswith(g)
               for g in GAS_NAMES) or "medical air" in brand or "medical air" in generic \
               or "carbon dioxide" in brand or "carbon dioxide" in generic \
               or "nitrous oxide" in brand or brand in {"oxygen", "oxygen, usp", "nitrogen", "helium"}:
            return "Medical gas"
    if d.startswith("type 2"):
        return "Type 2 — New active ingredient"
    if d.startswith("type 3"):
        return "Type 3 — New dosage form"
    if d.startswith("type 4") or (d.startswith("new combination") and "type 1" not in d):
        return "Type 4 — New combination"
    if d.startswith("type 5"):
        return "Type 5 — New formulation or manufacturer"
    if d.startswith("type 6") or d.startswith("type 9") or d.startswith("type 10") or d.startswith("type 10"):
        return "New indication filed as distinct original"
    if d.startswith("type 7"):
        return "Type 7 — Already marketed without approved NDA"
    if d.startswith("type 8"):
        return "Type 8 — Partial Rx-to-OTC"
    if "efficacy" in d:
        return "Efficacy class on an original submission"
    # Biosimilar heuristic: 351(k) BLAs often have no class code and a 4-letter suffix.
    if kind == "BLA" and BIOSIM_SUFFIX.search(generic_of(rec) or brand_of(rec) or ""):
        return "Biosimilar (351(k)) — class unpublished or Type 2"
    if kind == "BLA" and (not d or d in {"unknown", ""}):
        return "BLA — class not published (possible biosimilar)"
    if not d or d in {"unknown", ""}:
        return "Class not published"
    return desc or code or "Unclassified"


def brand_of(rec: dict) -> str:
    for p in rec.get("products") or []:
        b = (p.get("brand_name") or "").strip()
        if b:
            return b
    return (rec.get("brand_name_openfda") or "").strip()


def generic_of(rec: dict) -> str:
    g = (rec.get("generic_name_openfda") or "").strip()
    if g:
        return g
    s = (rec.get("substance_name") or "").strip()
    if s:
        return s
    for p in rec.get("products") or []:
        ing = FR_NOISE.sub("", (p.get("active_ingredients") or "")).strip()
        if ing:
            return ing
    return ""


def dosage_form_of(rec: dict) -> str:
    forms = []
    for p in rec.get("products") or []:
        f = (p.get("dosage_form") or "").strip()
        if f and f not in forms:
            forms.append(f)
    return "; ".join(forms)


def route_of(rec: dict) -> str:
    r = (rec.get("route") or "").strip()
    if r:
        return r
    routes = []
    for p in rec.get("products") or []:
        x = (p.get("route") or "").strip()
        if x and x not in routes:
            routes.append(x)
    return "; ".join(routes)


def master_application_numbers(master_rows) -> set[str]:
    found = set()
    for r in master_rows:
        blob = " ".join([
            r.get("notes", ""), r.get("source_url_1", ""), r.get("source_url_2", ""),
            r.get("classification_basis", ""),
        ])
        for m in APPL_FROM_MASTER.finditer(blob):
            digits = next(g for g in m.groups() if g)
            found.add(digits.zfill(6))
    return found


def master_brand_date(master_rows) -> set[tuple[str, str]]:
    out = set()
    for r in master_rows:
        b = re.sub(r"[^a-z0-9]+", "", (r.get("drug_brand") or "").lower())
        d = (r.get("decision_date") or "").strip()
        if b and d:
            out.add((b, d))
    return out


def resolve_row(sponsor: str, reg: dict):
    entry, basis = suppl_mod.resolve(sponsor, reg)
    if entry:
        company = entry.get("resolved_company", "") or sponsor
        exchange = entry.get("exchange", "")
        cls = entry.get("us_investable_class", "") or "UNRESOLVED (REVIEW)"
        ticker = (entry.get("ticker", "") or "").strip()
        if not ticker:
            ticker = "NO_US_TICKER"
    else:
        company = sponsor
        ticker = "UNRESOLVED"
        exchange = ""
        cls = "UNRESOLVED (REVIEW)"
    historical = bool(re.search(
        r"acquired by|merged|delisted|\bvia\b|applicant at approval",
        company, re.I,
    ))
    if historical and cls.startswith("US-LISTED"):
        cls = "FORMERLY US-LISTED (DELISTED/ACQUIRED)"
    return company, ticker, exchange, cls, basis, historical


def openfda_app_url(appl: str) -> str:
    return f'https://api.fda.gov/drug/drugsfda.json?search=application_number:"{appl}"'


FIRST_YEAR = 1983  # v15: backward extension into the 1983/1984 focus years
LAST_YEAR = 2026

# PRE-1985 annotations: rows whose committed payload fields are copied verbatim
# but whose internal consistency needs an explicit review note so future passes
# do not re-investigate them. Values are appended to the row notes verbatim.
PRE_1985_ANNOTATIONS = {
    "NDA022046": (
        "FLAGGED IRREGULARITY (annotated 2026-09-18): openFDA records this ORIG/AP on "
        "1983-07-13 (class UNKNOWN, STANDARD) although the NDA022046 number series dates from "
        "the late 1990s; FDA's 2012 approval letter for this application cross-references the "
        "legacy bupivacaine applications NDA016964 and NDA018692 "
        "(https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2012/016964s070,018692s015,022046s004ltr.pdf). "
        "The 1983 status date is therefore a Drugs@FDA application-lineage artifact candidate. "
        "The row is published exactly as the committed FDA payload states; treat the 1983 date "
        "as FDA-recorded, not independently corroborated by a 1983 document."
    ),
}

# Annotations for Type-1-gap rows (NEXT_SESSION.md item 9): durable, so a
# regenerated gap file keeps the adjudication notes.
T1_ANNOTATIONS = {
    "NDA022023": ("Emend IV (fosaprepitant, Merck, 2008-01-25): FDA's official 2008 NME table excluded it "
                  "(the aprepitant moiety was already approved as Emend capsules in 2003, master D806). "
                  "Kept OUT of the NME master per the year-table pinning decision; the approval itself is real "
                  "(openFDA ORIG-1 AP 2008-01-25, STANDARD). Do not re-investigate."),
    "NDA020564": ("Epivir NDA 020564 (HBV strength, 2004-11-22): lamivudine moiety approved as Epivir 1995 "
                  "(master D975); this filing is the HBV indication/strength and FDA's 2004 table excluded it. "
                  "Do not re-investigate."),
    "NDA211617": ("Nexlizet (bempedoic acid + ezetimibe, 2020-02-26): Type 1/4 combination; bempedoic acid "
                  "itself is Nexletol (master D362, 2020-02-21). FDA's 2020 novel table counts Nexletol only. "
                  "Do not re-investigate."),
    "NDA212643": ("Gallium Ga 68 gozetotide NDA 212643 (UCSF, 2020-12-01): the two site-specific Ga-68 "
                  "PSMA-11 applications approved the same day; FDA's 2020 table lists UCLA's NDA 212642 "
                  "(master D350). UCSF = academic applicant, no equity. Do not re-investigate."),
    "BLA761391": ("Nemluvio BLA 761391 (Galderma, 2024-12-13): a SECOND BLA for nemolizumab; the master's "
                  "Nemluvio row (2024-08-12) follows FDA's 2024 novel-approvals table (one row per novel "
                  "active ingredient). Kept out of the master per year-table pinning. Do not re-investigate."),
    "BLA761464": ("Datroway BLA 761464 (AstraZeneca/Daiichi Sankyo, 2025-06-23): a SECOND BLA for "
                  "datopotamab deruxtecan; the master's Datroway row (2025-01-17) follows FDA's 2025 novel "
                  "table. Kept out of the master per year-table pinning. Do not re-investigate."),
    # Pre-1998 surface since the 1985-2026 payload extension: five unrelated
    # cases documented so nobody re-investigates them.
    "NDA020803": ("Alrex (loteprednol etabonate 0.2%, Bausch & Lomb): openFDA Type 1 ORIG/AP 1998-03-09 — "
                  "loteprednol is on FDA's CY1998 NME table as Lotemax (D995) with the SAME approval date; "
                  "Alrex is the concurrent second same-day product of the same moiety and is excluded from "
                  "FDA's NME count. Do not merge."),
    "BLA103786": ("Retavase: the master carries Retavase per the Compilation as BLA103632 (1996-10-30, "
                  "D1358). This openFDA record cites licence BLA103786 (1998-05-06, sponsor of record EKR "
                  "Therap). Second licence/status record for the same product — do not merge."),
    "BLA103836": ("Actimmune: the master carries Actimmune per the Compilation as BLA103348 (1990-12-20, "
                  "D1167). openFDA carries a separate ORIG/AP record on BLA103836 (1999-02-25, sponsor of "
                  "record Horizon). Competing licence numbers — do not merge; manual adjudication required."),
    "NDA016768": ("Estrovis (quinestrol): legacy 1960s application number (016768) carrying a 1996-04-26 "
                  "ORIG/AP status date in openFDA; FDA's Compilation has no 1996 Estrovis row — pre-1985-era "
                  "product with a later status record. Flagged as an openFDA legacy-status artifact; do not merge."),
    "NDA008319": ("Butazolidin (phenylbutazone): legacy 1950s application (008319) carrying a 1997-06-25 "
                  "ORIG/AP status date in openFDA; FDA's Compilation has no 1997 Butazolidin row (product "
                  "predates the NME era) — openFDA legacy-status artifact; do not merge."),
}


def load_year_files():
    files = []
    for path in sorted(RAW.glob("decisions_*.json")) + sorted(RAW_PRE.glob("decisions_*.json")):
        payload = json.load(open(path))
        year = payload.get("year")
        if year is None or int(year) < FIRST_YEAR or int(year) > LAST_YEAR:
            continue
        files.append(payload)
    return files


def load_pre1985_appl_set() -> set[str]:
    """Six-digit application numbers already tracked in data/pre1985_fda_decisions.csv.

    For the 1983/1984 payload years this table is the authoritative home of the
    Type 1/1-4 NME rows (v13/v14) plus the two separately verified non-Type-1
    applications (furosemide NDA018413, Trandate NDA018716).
    """
    path = DATA / "pre1985_fda_decisions.csv"
    out: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            m = re.search(r"(\d{5,6})", r.get("application_number", ""))
            if m:
                out.add(m.group(1).zfill(6))
    return out


def main() -> int:
    reg = suppl_mod.load_registry()
    print(f"sponsor registry keys: {len(reg)}")

    master_rows = list(csv.DictReader((DATA / "fda_decisions_master.csv").open(
        newline="", encoding="utf-8-sig")))
    master_appls = master_application_numbers(master_rows)
    master_bd = master_brand_date(master_rows)
    print(f"master application numbers extracted: {len(master_appls)}")
    pre1985_appls = load_pre1985_appl_set()
    print(f"pre1985 table application numbers extracted: {len(pre1985_appls)}")

    rows, t1_gap, tally = [], [], Counter()
    year_counts = {y: Counter() for y in range(FIRST_YEAR, LAST_YEAR + 1)}
    seen = set()

    for payload in load_year_files():
        year = int(payload["year"])
        is_pre = year < 1985
        search = payload.get("search", "")
        endpoint = payload.get("source_endpoint", "https://api.fda.gov/drug/drugsfda.json")
        for rec in payload.get("decisions") or []:
            appl = (rec.get("application_number") or "").strip()
            date = (rec.get("decision_date") or "").strip()
            key = (appl, date)
            if not appl or not date or key in seen:
                continue
            seen.add(key)
            year_counts[year]["raw_orig"] += 1

            brand = brand_of(rec)
            generic = generic_of(rec)
            num = (rec.get("application_num") or "").zfill(6)
            in_master_appl = num in master_appls
            nb = re.sub(r"[^a-z0-9]+", "", brand.lower())
            in_master_bd = (nb, date) in master_bd if nb else False

            if is_type1_nme(rec):
                year_counts[year]["type1"] += 1
                if is_pre:
                    # v15: pre-1985 Type 1/1-4 NMEs are owned by
                    # data/pre1985_fda_decisions.csv (v13/v14 verified rows).
                    if num in pre1985_appls:
                        year_counts[year]["type1_in_pre1985_table"] += 1
                        continue
                    raise SystemExit(
                        f"pre-1985 Type 1/1-4 application {appl} approved {date} is NOT in "
                        "data/pre1985_fda_decisions.csv. The pre-1985 NME table must be "
                        "extended and verified first; refusing to invent or merge rows."
                    )
                if in_master_appl or in_master_bd:
                    year_counts[year]["type1_in_master"] += 1
                    continue
                # Genuine Type 1 not matched to the NME master. Do NOT add to
                # the non-NME file and do NOT silently merge into the master
                # (that would break the official NME year-count audit).
                t1_gap.append(rec)
                year_counts[year]["type1_unmatched"] += 1
                continue

            if is_pre:
                # v15: the pre-1985 table also owns the two separately verified
                # non-Type-1 originals (furosemide NDA018413, Trandate NDA018716).
                # The 1985-2026 master is not an exclusion source for these years.
                if num in pre1985_appls:
                    year_counts[year]["non_nme_in_pre1985_table"] += 1
                    continue
            elif in_master_appl:
                year_counts[year]["non_nme_already_in_master"] += 1
                continue

            group = chemical_group(rec)
            company, ticker, exchange, cls, basis, historical = resolve_row(
                rec.get("sponsor_name") or "", reg
            )

            flags = []
            if group == "Medical gas":
                flags.append("FLAGGED: medical gas — not a biotech clinical-trial conversion")
            if group.startswith("Type 5"):
                flags.append("Type 5 may be a new manufacturer rather than a new clinical programme")
            if "possible biosimilar" in group.lower() or group.startswith("Biosimilar"):
                flags.append("biosimilar/class unpublished — 351(k) status not asserted beyond the openFDA fields")
            if group == "Class not published":
                flags.append("FLAGGED: openFDA published no submission_class_code")
            if historical:
                flags.append("FLAGGED: ticker is historical (issuer since acquired/delisted)")
            if ticker == "UNRESOLVED":
                flags.append("FLAGGED: sponsor not resolved to a listed security")
            if int(rec.get("n_orig_approvals_in_year") or 1) > 1:
                flags.append(f"openFDA recorded {rec['n_orig_approvals_in_year']} ORIG/AP dates in this year; earliest kept")

            vstatus = "Verified - openFDA Drugs@FDA ORIG/AP record"
            if flags:
                vstatus += " - " + "; ".join(flags)

            letter_url = rec.get("source_url_drugsatfda") or ""
            query_url = rec.get("source_query_url") or ""
            app_url = openfda_app_url(appl)

            tally[group] += 1
            tally["resolved" if ticker not in {"UNRESOLVED"} else "unresolved_sponsor"] += 1
            year_counts[year]["published"] += 1

            pre_note = (
                "PRE-1985 ROW (v15 backward extension into the 1983-1984 focus years): "
                "sponsor_name is the CURRENT Drugs@FDA application holder; it is NOT asserted "
                "as the historical 1983/1984 applicant and no period listing class is claimed. "
            ) if is_pre else ""
            pre_annotation = PRE_1985_ANNOTATIONS.get(appl, "") if is_pre else ""
            if pre_annotation and pre_annotation not in flags:
                flags = flags + [pre_annotation]
                vstatus = "Verified - openFDA Drugs@FDA ORIG/AP record"
                if flags:
                    vstatus += " - " + "; ".join(flags)
            rows.append({
                "orig_id": f"O-{appl}",
                "company_name": company,
                "openfda_sponsor_name": rec.get("sponsor_name") or "",
                "ticker": ticker,
                "exchange": exchange,
                "us_investable_class": cls,
                "drug_brand": brand,
                "drug_generic": generic,
                "application_number": appl,
                "application_kind": rec.get("application_kind") or "",
                "decision_type": "Original Approval (non-NME)",
                "decision_date": date,
                "chemical_type_code": rec.get("submission_class_code") or "",
                "chemical_type_description": rec.get("submission_class_code_description") or "",
                "chemical_type_group": group,
                "review_priority": rec.get("review_priority") or "",
                "dosage_form": dosage_form_of(rec),
                "route": route_of(rec),
                "pharm_class_epc": rec.get("pharm_class_epc") or "",
                "source_url_1": letter_url,
                "source_url_2": app_url,
                "source_query_url": query_url,
                "verification_status": vstatus,
                "sponsor_resolution_basis": basis,
                "notes": (
                    pre_note
                    + "Indication text is intentionally not recorded: openFDA's original-approval "
                    "extract has no structured indication field. Read the linked Drugs@FDA "
                    "application record. Chemical type is FDA's submission_class_code_description, "
                    "copied verbatim. "
                    + (" ".join(flags) if flags else "")
                ),
            })

    rows.sort(key=lambda r: (r["decision_date"], r["application_number"]))
    # orig_id uniqueness: same application can theoretically appear twice if
    # two ORIG/AP dates exist in different years. Disambiguate.
    seen_ids = {}
    for r in rows:
        oid = r["orig_id"]
        if oid in seen_ids:
            r["orig_id"] = f"{oid}-{r['decision_date']}"
        seen_ids[r["orig_id"]] = True

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} original non-NME decisions")
    for k, v in tally.most_common():
        print(f"  {k:<62} {v}")
    us = sum(1 for r in rows if r["us_investable_class"].startswith("US-LISTED"))
    print(f"  {'US-LISTED (investable universe)':<62} {us}")

    # Type 1 unmatched — flagged review file, not merged into master.
    t1_rows = []
    for rec in t1_gap:
        brand = brand_of(rec)
        generic = generic_of(rec)
        company, ticker, exchange, cls, basis, historical = resolve_row(
            rec.get("sponsor_name") or "", reg
        )
        t1_rows.append({
            "gap_id": f"T1GAP-{rec.get('application_number')}",
            "company_name": company,
            "openfda_sponsor_name": rec.get("sponsor_name") or "",
            "ticker": ticker,
            "exchange": exchange,
            "us_investable_class": cls,
            "drug_brand": brand,
            "drug_generic": generic,
            "application_number": rec.get("application_number") or "",
            "application_kind": rec.get("application_kind") or "",
            "decision_date": rec.get("decision_date") or "",
            "chemical_type_description": rec.get("submission_class_code_description") or "",
            "review_priority": rec.get("review_priority") or "",
            "source_url_1": rec.get("source_url_drugsatfda") or "",
            "source_url_2": openfda_app_url(rec.get("application_number") or ""),
            "verification_status": (
                "FLAGGED FOR REVIEW — Type 1 NME in openFDA Drugs@FDA but not matched "
                "to fda_decisions_master.csv. NOT merged into the NME master (would break "
                "the official CDER year-count audit). Early-2000s BLAs were often CBER-"
                "licensed and excluded from CDER NME year tables; later rows may be "
                "alternate presentations or copacks of an already-listed NME."
            ),
            "sponsor_resolution_basis": basis,
            "notes": (
                "Do not treat as a confirmed missing novel approval until a human "
                "compares this row to FDA's official NME year table and the master list. "
                "Blank beats guessed — left out of the 1,427-row NME count on purpose."
                + (" ADJUDICATED 2026-09-17: "
                   + T1_ANNOTATIONS.get(rec.get("application_number") or "", "")
                   if T1_ANNOTATIONS.get(rec.get("application_number") or "")
                   else "")
            ),
        })
    t1_rows.sort(key=lambda r: (r["decision_date"], r["application_number"]))
    with OUT_T1.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(t1_rows[0].keys()) if t1_rows else [
            "gap_id", "company_name", "verification_status"])
        w.writeheader()
        w.writerows(t1_rows)
    print(f"wrote {OUT_T1.relative_to(ROOT)}: {len(t1_rows)} Type 1 unmatched (FLAGGED, not merged)")

    year_rows = []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        c = year_counts[y]
        query = (
            f"https://api.fda.gov/drug/drugsfda.json?search="
            f'submissions.submission_type:"ORIG" AND submissions.submission_status:"AP" '
            f"AND submissions.submission_status_date:[{y}0101 TO {y}1231]"
        )
        raw_payload = (
            f"data/raw/openfda_orig_decisions_1980_1984/decisions_{y}.json" if y < 1985
            else f"data/raw/openfda_orig_decisions_2011_2026/decisions_{y}.json"
        )
        if y < 1985:
            notes = (
                f"1983-1984 focus year (v15): Type 1/1-4 NMEs are tracked in "
                f"pre1985_fda_decisions.csv ({c['type1_in_pre1985_table']} applications); "
                f"{c['non_nme_in_pre1985_table']} separately verified non-Type-1 original(s) also "
                f"tracked there (furosemide NDA018413 1983, Trandate NDA018716 1984); "
                f"{c['published']} non-NME originals published in fda_original_non_nme_decisions.csv. "
                f"See data/focus_years_1983_1985_audit.csv for the complete enumeration audit."
            )
        else:
            notes = (
                f"Type 1 NMEs belong on fda_decisions_master.csv "
                f"({c['type1_in_master']} matched, {c['type1_unmatched']} flagged unmatched). "
                f"{c['published']} non-NME originals published in fda_original_non_nme_decisions.csv."
            )
        year_rows.append({
            "year": y,
            "openfda_orig_nda_bla_count": c["raw_orig"],
            "type1_nme_in_openfda": c["type1"],
            "type1_matched_to_nme_master": c["type1_in_master"],
            "type1_unmatched_flagged": c["type1_unmatched"],
            "non_nme_already_in_master": c["non_nme_already_in_master"],
            "non_nme_published": c["published"],
            "official_source_url": query,
            "source_type": "openFDA Drugs@FDA ORIG/AP (NDA+BLA only; ANDA excluded at extract)",
            "coverage_status": "Complete" if c["raw_orig"] else "No ORIG/AP NDA/BLA in openFDA for this year",
            "raw_payload": raw_payload,
            "notes": notes,
        })
    with OUT_YEAR.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(year_rows[0].keys()))
        w.writeheader()
        w.writerows(year_rows)
    print(f"wrote {OUT_YEAR.relative_to(ROOT)}: {len(year_rows)} years")

    # ---- v15 hallucination gates -------------------------------------------
    # (1) No pre-1985 Type 1 may have leaked into the flagged gap file: the
    # pre-1985 NME table owns those rows and the builder aborts on a miss.
    pre_t1_gap = [r for r in t1_gap if int((r.get("decision_date") or "9999")[:4]) < 1985]
    if pre_t1_gap:
        raise SystemExit(
            "v15 gate violated: pre-1985 Type 1 rows reached the gap file: "
            + ", ".join(r.get("application_number", "?") for r in pre_t1_gap)
        )
    # (2) The two backward years must reproduce the committed-payload
    # enumeration exactly. If a re-fetch changes these numbers, re-verify the
    # payloads and update these gates and the focus-year audit TOGETHER.
    for _y, _expected_raw, _expected_pub in ((1983, 70, 56), (1984, 109, 89)):
        c = year_counts[_y]
        if c["raw_orig"] != _expected_raw or c["published"] != _expected_pub:
            raise SystemExit(
                f"v15 gate: {_y} enumeration changed (raw={c['raw_orig']} expected {_expected_raw}; "
                f"published={c['published']} expected {_expected_pub}). Re-verify the committed "
                "payload and data/pre1985_fda_decisions.csv before touching these gates."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
