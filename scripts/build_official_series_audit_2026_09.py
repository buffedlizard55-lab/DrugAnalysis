#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v17 (2026-09-19): reconcile the project's year-by-year FDA decision enumeration
against FDA's own published historical tabulation, and size the pre-1985 gap.

New primary evidence consumed (all committed under
``data/raw/source_captures_2026_09_19/``):

* FDA History Office, "Summary of NDA Approvals & Receipts, 1938 to the present"
  - the official NME-approvals-by-year series back to 1940, including the
  pre-1985 years the project previously recorded as "no official pre-1985
  annual NME table was located".
* The CDER NME Compilation landing page - the dataset's own inclusion rule
  (Type 1/1-4 NDAs plus new biologics under BLA; CBER products excluded).
* Live per-application captures for the 1983-1985 flagged rows.

Outputs (single writer; read-only over every other table):

* ``data/fda_official_year_series.csv``          - verbatim official counts.
* ``data/fda_official_series_crosswalk.csv``     - official vs project, per year,
  with an explicit verdict for every year 1980-2026.
* ``data/pre1985_nme_gap_analysis.csv``          - the 1980-1985 gap, sized and
  sourced, with the payload-invisible applications named.
* ``data/pre1985_primary_captures_index.csv``    - the live captures, indexed to
  the project rows they touch.

Nothing here changes an existing project value: the script only adds derived
audit tables.  It is idempotent and aborts on any inconsistency with the
committed evidence.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CAPTURES = DATA / "raw" / "source_captures_2026_09_19"
COMPILATION = DATA / "raw" / "probe" / "fda_nme_compilation_1985_2025.xlsx"
PAYLOAD_1980_1984 = DATA / "raw" / "openfda_orig_decisions_1980_1984"
PAYLOAD_1985 = DATA / "raw" / "openfda_orig_decisions_2011_2026" / "decisions_1985.json"

HISTORY_CAPTURE = CAPTURES / "fda_history_nda_nme_approvals_1938_2022.json"
COMPILATION_LANDING = CAPTURES / "fda_nme_compilation_landing_2026_09_19.json"
LIVE_CAPTURES = CAPTURES / "live_primary_captures_2026_09_19.json"

PRE1985_YEARS = ("1980", "1981", "1982", "1983", "1984")
XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def fail(msg: str) -> None:
    raise SystemExit(f"build_official_series_audit_2026_09: {msg}")


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing committed capture {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Source 1: FDA historical tabulation
# --------------------------------------------------------------------------- #
HISTORY = load_json(HISTORY_CAPTURE)
OFFICIAL_NME: dict[int, int] = {}
OFFICIAL_NDA: dict[int, int] = {}
for row in HISTORY["rows"]:
    y = int(row["year"])
    nme = re.sub(r"\D.*$", "", row["nmes_approved"] or "").strip()
    nda = re.sub(r"\D.*$", "", row["ndas_approved"] or "").strip()
    if nme:
        OFFICIAL_NME[y] = int(nme)
    if nda:
        OFFICIAL_NDA[y] = int(nda)

# Pinned spot-checks straight from the captured page (abort if the capture
# were ever edited into something else).
PINS_OFFICIAL = {1980: 12, 1981: 27, 1982: 28, 1983: 14, 1984: 22, 1985: 30, 1988: 21,
                 1996: 53, 2004: 36, 2013: 29, 2022: 37}
for year, value in PINS_OFFICIAL.items():
    if OFFICIAL_NME.get(year) != value:
        fail(f"official NME series: {year} = {OFFICIAL_NME.get(year)!r}, expected {value}")
if max(OFFICIAL_NME) != 2022:
    fail(f"official NME series ends at {max(OFFICIAL_NME)}, expected 2022")

# --------------------------------------------------------------------------- #
# Source 2: CDER NME Compilation workbook (committed capture)
# --------------------------------------------------------------------------- #
def read_xlsx_rows(path: Path) -> list[dict]:
    if not path.exists():
        fail(f"missing committed Compilation capture {path}")
    with zipfile.ZipFile(path) as z:
        shared = [''.join(t.text or '' for t in si.iter(XLSX_NS + 't'))
                  for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(XLSX_NS + 'si')]
        sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    out = []
    for r in sheet.iter(XLSX_NS + 'row'):
        cells = {}
        for c in r.findall(XLSX_NS + 'c'):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            kind, v, inline = c.get("t"), c.find(XLSX_NS + 'v'), c.find(XLSX_NS + 'is')
            if kind == 's' and v is not None:
                val = shared[int(v.text)]
            elif kind == 'inlineStr' and inline is not None:
                val = ''.join(x.text or '' for x in inline.iter(XLSX_NS + 't'))
            elif v is not None:
                val = v.text
            else:
                val = ''
            cells[col] = val
        out.append(cells)
    return [r for r in out[1:] if r.get('A') or r.get('E')]


COMPILATION_ROWS = read_xlsx_rows(COMPILATION)
COMPILATION_BY_YEAR = Counter(r.get('P', '') for r in COMPILATION_ROWS)
COMPILATION_KINDS = Counter(r.get('D', '') for r in COMPILATION_ROWS)
if len(COMPILATION_ROWS) != 1387:
    fail(f"Compilation data rows = {len(COMPILATION_ROWS)}, expected 1387")
if COMPILATION_BY_YEAR.get('1985') != 31:
    fail(f"Compilation 1985 section = {COMPILATION_BY_YEAR.get('1985')}, expected 31")
_tambocor = [r for r in COMPILATION_ROWS if r.get('A') == 'Tambocor' and r.get('E') == '18830']
if len(_tambocor) != 1 or _tambocor[0].get('S') != 'Priority':
    fail("Compilation Tambocor/NDA18830 row missing or no longer 'Priority'")
COMPILATION_YEARS = sorted(int(y) for y in COMPILATION_BY_YEAR if y.isdigit())

# The Compilation's own inclusion rule, quoted from the live landing-page capture.
# (Loaded so a missing/edited capture aborts the build rather than going unnoticed.)
LANDING = load_json(COMPILATION_LANDING)
if "only products with a Type 1 or Type 1/4 are considered NMEs" not in " ".join(
        LANDING["inclusion_criteria_verbatim"]):
    fail("Compilation landing capture lost its inclusion-rule sentence")

# --------------------------------------------------------------------------- #
# Source 3: project tables
# --------------------------------------------------------------------------- #
def read_csv(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        fail(f"missing project table {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


MASTER = read_csv("fda_decisions_master.csv")
PRE1985 = read_csv("pre1985_fda_decisions.csv")
AUDIT = read_csv("focus_years_1980_1985_audit.csv")
NON_NME = read_csv("fda_original_non_nme_decisions.csv")

MASTER_BY_YEAR = Counter(r["decision_date"][:4] for r in MASTER if r["decision_date"])
PRE1985_BY_YEAR = Counter(r["year"] for r in PRE1985)
PRE1985_TYPE1_BY_YEAR = Counter(r["year"] for r in PRE1985
                               if r["chemical_type_code"] in ("TYPE 1", "TYPE 1/4"))
PRE1985_BOUNDARY = defaultdict(list)
for r in PRE1985:
    if r["chemical_type_code"] not in ("TYPE 1", "TYPE 1/4"):
        PRE1985_BOUNDARY[r["year"]].append(f"{r['application_number'].replace(' ', '')} {r['drug_brand']} ({r['chemical_type_code']})")

AUDIT_TYPE1_BY_YEAR = Counter(r["year"] for r in AUDIT
                              if r["payload_class_code"] in ("TYPE 1", "TYPE 1/4"))
AUDIT_BLANK_BY_YEAR = Counter(r["year"] for r in AUDIT if not (r["payload_class_code"] or "").strip())
AUDIT_ROWS_BY_YEAR = Counter(r["year"] for r in AUDIT)

# The pre-1985 table must agree with the payload enumeration it was built from.
for y in PRE1985_YEARS:
    if PRE1985_TYPE1_BY_YEAR[y] != AUDIT_TYPE1_BY_YEAR[y]:
        fail(f"{y}: pre-1985 Type 1 rows ({PRE1985_TYPE1_BY_YEAR[y]}) != payload Type 1 audit rows ({AUDIT_TYPE1_BY_YEAR[y]})")
if MASTER_BY_YEAR.get("1985") != 31:
    fail(f"master 1985 rows = {MASTER_BY_YEAR.get('1985')}, expected 31")

# --------------------------------------------------------------------------- #
# Payload detail: blank-class inventory and payload-invisible applications
# --------------------------------------------------------------------------- #
def payload_rows(year: int) -> list[dict]:
    if year == 1985:
        path = PAYLOAD_1985
    else:
        path = PAYLOAD_1980_1984 / f"decisions_{year}.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)["decisions"]


def ingredient_names(rows: list[dict]) -> list[str]:
    """Active-ingredient names for a set of committed payload rows.

    The committed extracts flatten products; ``active_ingredients`` is a
    strength-suffixed string ("MAGNESIUM CHLORIDE 30MG/100ML") or a
    semicolon-separated list of such strings.  Strength and footnote markers
    are stripped so only the ingredient name is kept.
    """
    names: set[str] = set()
    for r in rows:
        for p in (r.get("products") or []):
            raw = p.get("active_ingredients") if isinstance(p, dict) else None
            if isinstance(raw, list):
                for ing in raw:
                    nm = ing.get("name") if isinstance(ing, dict) else str(ing)
                    if nm:
                        names.add(nm.strip())
                continue
            for part in str(raw or "").split(";"):
                nm = re.split(r"\s+\d|\s+EQ\b|\*\*", part.strip())[0].strip().rstrip(",").strip()
                if nm:
                    names.add(nm)
        if not names and (r.get("substance_name") or r.get("generic_name_openfda")):
            names.add((r.get("substance_name") or r.get("generic_name_openfda")).strip())
    return sorted(names)


GAP_EVIDENCE: dict[str, dict] = {}
for year in (1980, 1981, 1982, 1983, 1984, 1985):
    rows = payload_rows(year)
    blanks = [r for r in rows
              if not (r.get("submission_class_code") or "").strip()
              or r["submission_class_code"] == "UNKNOWN"]
    GAP_EVIDENCE[str(year)] = {
        "payload_rows": len(rows),
        "payload_type1": sum(1 for r in rows
                             if (r.get("submission_class_code") or "") in ("TYPE 1", "TYPE 1/4")),
        "payload_blank": len(blanks),
        "blank_ingredients": ingredient_names(blanks),
    }

# 1985: 27 Type 1/1-4 rows and exactly one row whose class FDA publishes as
# "UNKNOWN" (NITRO-DUR, NDA020145).
if GAP_EVIDENCE["1985"]["payload_type1"] != 27 or GAP_EVIDENCE["1985"]["payload_blank"] != 1:
    fail("1985 payload enumeration changed shape (expected 27 Type 1/1-4, 1 unpublished-class row)")

# Applications the master carries for 1985 that the payload cannot enumerate.
_master_1985_apps = {}
for r in MASTER:
    if not r["decision_date"].startswith("1985"):
        continue
    m = re.search(r"appl\s+(NDA\d+|BLA\d+)", r["notes"] or "")
    if m:
        _master_1985_apps[r["decision_id"]] = m.group(1)
_payload_1985_apps = {r["application_number"].replace(" ", "") for r in payload_rows(1985)}
_audited_1985_apps = {r["application_number"].replace(" ", "") for r in AUDIT if r["year"] == "1985"}
INVISIBLE_1985 = [(did, app) for did, app in sorted(_master_1985_apps.items())
                  if app not in _payload_1985_apps and app not in _audited_1985_apps]
INVISIBLE_LABEL = {
    "D1030": "Seldane (terfenadine)",
    "D1038": "Protropin (somatrem)",
    "D1042": "Femstat (butoconazole nitrate)",
    "D1047": "Suprol (suprofen)",
}
if sorted(did for did, _ in INVISIBLE_1985) != ["D1030", "D1038", "D1042", "D1047"]:
    fail(f"payload-invisible 1985 set changed: {INVISIBLE_1985}")

LIVE_APPS = {
    "NDA018949": "openFDA NOT_FOUND; Drugs@FDA page renders an empty application shell (V17-C03/C04)",
    "NDA019107": "openFDA NOT_FOUND (application and brand both); Drugs@FDA page renders an empty application shell (V17-C05/C06)",
    "NDA019215": "openFDA carries the product record (sponsor ROCHE PALO, FEMSTAT discontinued) with NO submissions array - the reason the ORIG/AP query cannot see it (V17-C07)",
    "NDA018217": "openFDA NOT_FOUND; absent from the published dataset entirely (V17-C07)",
}

# --------------------------------------------------------------------------- #
# Output 1: data/fda_official_year_series.csv
# --------------------------------------------------------------------------- #
series_rows = []
for row in HISTORY["rows"]:
    series_rows.append({
        "year": row["year"],
        "ndas_approved": row["ndas_approved"],
        "nmes_approved": row["nmes_approved"],
        "ndas_received": row["ndas_received"],
        "commercial_inds_received": row["commercial_inds"],
        "noncommercial_research_inds_received": row["noncommercial_inds"],
        "total_inds_received": row["total_inds"],
        "source_url": HISTORY["source_url"],
    })

# --------------------------------------------------------------------------- #
# Output 2: data/fda_official_series_crosswalk.csv  (1980-2026, one row/year)
# --------------------------------------------------------------------------- #
CROSSWALK_NOTE_BIOLOGIC = ("official NME column excludes biologics before the 2004 CDER transfer; "
                           "the Compilation (the project's 1985-1997 spine) counts Type 1/1-4 NMEs plus new biologics by design")

crosswalk = []
for year in range(1980, 2027):
    ys = str(year)
    official = OFFICIAL_NME.get(year)
    pre_rows = PRE1985_BY_YEAR.get(ys, 0)
    master_rows = MASTER_BY_YEAR.get(ys, 0)
    project_rows = pre_rows + master_rows
    type1 = PRE1985_TYPE1_BY_YEAR.get(ys, 0) if year <= 1984 else (
        sum(1 for r in AUDIT if r["year"] == ys and r["tracked_in"] == "fda_decisions_master.csv"
            and r["payload_class_code"] in ("TYPE 1", "TYPE 1/4")) if year == 1985 else "")
    boundary = len(PRE1985_BOUNDARY.get(ys, [])) if year <= 1984 else ""
    comp_rows = COMPILATION_BY_YEAR.get(ys, "") if ys in COMPILATION_BY_YEAR else ""
    delta_project = (project_rows - official) if official is not None else ""
    delta_comp = (int(comp_rows) - official) if (official is not None and comp_rows != "") else ""
    # NME-comparable rows: for 1980-1984 that is the TYPE 1/1-4 subset (the
    # pre-1985 table also carries documented non-NME boundary rows, e.g. the
    # 1983 furosemide original); from 1985 on every master row is an NME or a
    # new biologic, so the whole row count is comparable.
    if year <= 1984:
        comparable = PRE1985_TYPE1_BY_YEAR.get(ys, 0)
    else:
        comparable = project_rows
    delta_comparable = (comparable - official) if official is not None else ""

    if official is None:
        verdict = "AWAITING_OFFICIAL_SERIES"
        note = ("FDA's history tabulation is captured through 2022; no official NME count is published for "
                f"{year} on that page, so this year is not reconciled here.")
    elif delta_comparable == 0:
        verdict = "MATCH"
        note = "NME-comparable project rows equal FDA's official NME count for this year."
    elif delta_comparable > 0:
        verdict = "PROJECT_EXCEEDS_OFFICIAL"
        note = (f"NME-comparable project rows exceed the official NME count by {delta_comparable}. "
                + CROSSWALK_NOTE_BIOLOGIC
                if year >= 1985 else
                f"NME-comparable project rows exceed the official NME count by {delta_comparable}.")
    else:
        verdict = "PROJECT_SHORT_FLAGGED"
        note = (f"FDA's official NME count exceeds the project's NME-comparable rows by "
                f"{abs(delta_comparable)} - a sized, flagged coverage gap. See pre1985_nme_gap_analysis.csv "
                "for the pre-1985 years and the 1988/2013 notes below.")

    if year == 1983:
        note += (" The 1983 group reaches 14 rows only because it includes the furosemide non-NME boundary row "
                 "(NDA018413, a molecule first approved in 1968); on a like-for-like NME basis the year is short by 1.")
    if year in (1988, 2013):
        note += (f" SPECIFIC FINDING: the CDER Compilation itself carries {comp_rows} rows for {year} against "
                 f"FDA's official NME count of {official} - the only two years in 1985-2022 where the Compilation "
                 "is SHORT of the official series. The missing application(s) are not identified in either public "
                 "dataset; the 1989 CDER statistical typescript (pp. 152-199) or the relevant annual report is "
                 "required to name them.")
    if year == 1985:
        note += (" The single +1 row is the record-level difference between the Compilation (31 rows, Type 1/1-4 "
                 "plus new biologics by design) and the NME statistical series (30); Protropin (recombinant "
                 "somatrem, the only 1985 Compilation row that is a biological product) is the leading candidate, "
                 "recorded as a candidate and not asserted (see pre1985_nme_gap_analysis.csv).")

    crosswalk.append({
        "year": year,
        "official_nmes_approved": official if official is not None else "",
        "official_ndas_approved": OFFICIAL_NDA.get(year, ""),
        "project_pre1985_rows": pre_rows,
        "project_master_rows": master_rows,
        "project_novel_rows": project_rows,
        "project_type1_rows": type1,
        "nme_comparable_rows": comparable,
        "pre1985_non_nme_boundary_rows": boundary,
        "compilation_rows": comp_rows,
        "delta_project_vs_official": delta_project,
        "delta_nme_comparable_vs_official": delta_comparable,
        "delta_compilation_vs_official": delta_comp,
        "verdict": verdict,
        "evidence_note": note,
        "project_source_tables": ("fda_decisions_master.csv" if year >= 1985 else
                                  "pre1985_fda_decisions.csv; fda_decisions_master.csv" if master_rows else
                                  "pre1985_fda_decisions.csv"),
        "source_urls": f"{HISTORY['source_url']}|https://www.fda.gov/drugs/drug-approvals-and-databases/compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals",
    })

# --------------------------------------------------------------------------- #
# Output 3: data/pre1985_nme_gap_analysis.csv
# --------------------------------------------------------------------------- #
GAP_ROWS = []
NEXT_SOURCE = ("CDER 'Offices of Drug Evaluation: Statistical Report', typescript, 1989, pp. 152-199 "
               "(FDA History Office Files, Rockville MD) - the source FDA's own history page cites for the "
               "1951-1989 NME series; request via the FDA Historian (john.swann@fda.hhs.gov) or read the "
               "contemporaneous FDA annual report for the year.")
for ys in ("1980", "1981", "1982", "1983", "1984", "1985"):
    official = OFFICIAL_NME[int(ys)]
    ev = GAP_EVIDENCE[ys]
    if ys == "1985":
        project_rows = MASTER_BY_YEAR.get(ys, 0)
        type1_rows = ev["payload_type1"]
        boundary = 0
        effective = project_rows - official  # +1
        invisible = "; ".join(f"{app} {INVISIBLE_LABEL[did]}" for did, app in INVISIBLE_1985)
        invisible_verified = "; ".join(f"{app}: {LIVE_APPS[app]}" for _did, app in INVISIBLE_1985)
        candidates = ("New biologic counted by the Compilation and not by the NME statistical series: "
                      "Protropin (somatrem, a recombinant human growth hormone) is the leading candidate "
                      "because its product is a biological rather than a small molecule; this identification "
                      "rests on the product's nature, NOT on a workbook field - the Compilation's own NDA/BLA "
                      "column types all 31 of the 1985 rows 'NDA' and has no comment field populated for them, "
                      "so the workbook cannot separate the biologic. Baros Effervescent was re-verified live as "
                      "a Type 1 NDA (NDA018509, 1985-08-07) and is not the difference. Status: candidate, not a "
                      "determination; the 1989 CDER statistical typescript would settle it.")
        status = "RECONCILED_WITH_CANDIDATE — 31 (Compilation) vs 30 (official NME series); +1 row is a biological product in the Compilation"
        next_source = ("FDA CDER NME Compilation data dictionary (media/177920) plus the 1989 CDER statistical "
                       "typescript; CDER error-report address CDER.NMENewBiologicApprovals@fda.hhs.gov for the "
                       "Tambocor designation conflict (see pre1985_primary_captures_index.csv).")
    else:
        project_rows = PRE1985_BY_YEAR.get(ys, 0)
        type1_rows = PRE1985_TYPE1_BY_YEAR.get(ys, 0)
        boundary = len(PRE1985_BOUNDARY.get(ys, []))
        effective = type1_rows - official  # negative = shortfall of Type-1 NME applications
        invisible = "not enumerable — no official application-level NME list exists for this year, so payload-invisible applications cannot be named from public data"
        invisible_verified = "n/a"
        candidates = (f"The {ev['payload_blank']} payload rows with no published subclass code are all legacy "
                      f"duplicative applications of already-marketed ingredients ({len(ev['blank_ingredients'])} "
                      "distinct ingredients: " + ", ".join(ev["blank_ingredients"][:8]) +
                      ("…" if len(ev["blank_ingredients"]) > 8 else "") +
                      "). Spot check verified live 2026-09-19: openFDA serves a furosemide ORIG-1 approval dated "
                      "1968-03-20 (TYPE 3), so the 1983/1984 furosemide 'originals' are re-approvals of a molecule "
                      "first approved fifteen years earlier - the blank-class rows cannot account for the official "
                      "NME count. "
                      "The shortfall therefore sits in applications absent from the Drugs@FDA ORIG/AP payload "
                      "altogether (the class of gap proven for 1985).")
        status = f"OPEN_GAP_SIZED — official count exceeds the Type 1/1-4 enumeration by {abs(effective)}"
        next_source = NEXT_SOURCE
    GAP_ROWS.append({
        "year": ys,
        "official_nmes_approved": official,
        "project_rows": project_rows,
        "project_type1_rows": type1_rows,
        "non_nme_boundary_rows": boundary,
        "effective_type1_shortfall_negative_is_short": effective,
        "payload_original_rows": ev["payload_rows"],
        "payload_type1_rows": ev["payload_type1"],
        "payload_blank_class_rows": ev["payload_blank"],
        "payload_blank_class_ingredients": "; ".join(ev["blank_ingredients"]),
        "payload_invisible_apps_known": invisible,
        "payload_invisible_apps_verified_live_2026_09_19": invisible_verified,
        "candidate_explanations": candidates,
        "status": status,
        "next_source_required": next_source,
    })

# --------------------------------------------------------------------------- #
# Output 4: data/pre1985_primary_captures_index.csv
# --------------------------------------------------------------------------- #
LIVE = load_json(LIVE_CAPTURES)
CAPTURE_INDEX = {
    "V17-C01": ("NDA 018830 Tambocor - live Drugs@FDA original-approval row",
                "fda_decisions_master.csv", "D1040",
                "ORIG-1 10/31/1985, Type 1 - New Molecular Entity, STANDARD (third FDA-family STANDARD corroboration)",
                "conflict recorded, both values retained (Compilation Priority / Drugs@FDA STANDARD)"),
    "V17-C02": ("NDA 018615 Sulfatrim - live Drugs@FDA original-approval row",
                "fda_original_non_nme_decisions.csv", "O-NDA018615",
                "ORIG-1 01/07/1983 Approval with blank Submission Classification and blank Review Priority",
                "confirms the TRACKED_REVIEW condition is a genuine FDA source gap"),
    "V17-C03": ("NDA 018949 Seldane - openFDA API record",
                "fda_decisions_master.csv", "D1030",
                "NOT_FOUND (application absent from openFDA's Drugs@FDA dataset)",
                "precision added to the completeness-gap note"),
    "V17-C04": ("NDA 018949 Seldane - live Drugs@FDA page",
                "fda_decisions_master.csv", "D1030",
                "empty application shell: number resolves, no products and no approval history published",
                "precision added to the completeness-gap note"),
    "V17-C05": ("NDA 019107 Protropin - openFDA API record",
                "fda_decisions_master.csv", "D1038",
                "NOT_FOUND for the application number and for brand PROTROPIN",
                "row remains Compilation-only; feeds the 1985 +1 reconciliation"),
    "V17-C06": ("NDA 019107 Protropin - live Drugs@FDA page",
                "fda_decisions_master.csv", "D1038",
                "empty application shell",
                "row remains Compilation-only; feeds the 1985 +1 reconciliation"),
    "V17-C07": ("NDA 018217 Suprol / NDA 019215 Femstat - openFDA API records",
                "fda_decisions_master.csv", "D1047; D1042",
                "Femstat present as a product record with NO submissions array; Suprol absent entirely",
                "two distinct conditions now documented separately"),
    "V17-C08": ("NDA 018509 Baros Effervescent - openFDA API record",
                "fda_decisions_master.csv", "D1035",
                "ORIG-1 1985-08-07, TYPE 1, STANDARD, Mallinckrodt - Compilation row independently corroborated",
                "rules Baros out as the 1985 +1 row"),
    "V17-C09": ("NDA 018830 1985 review PDF - Wayback Machine",
                "fda_decisions_master.csv", "D1040",
                "5 captures exist (30 Mar 2021 - 30 Mar 2025); raw replay endpoints and the live PDF both returned HTTP 500 to automation",
                "human browser read is the single remaining step to settle the designation"),
    "V17-C11": ("Furosemide - pre-1980 original approvals (openFDA)",
                "pre1985_fda_decisions.csv", "PRE1985-1983-07",
                "a 1968-03-20 ORIG-1 approval of furosemide (TYPE 3) is served by the API: the 1983/1984 furosemide originals are re-approvals of a molecule first approved in 1968",
                "supplies the substantive evidence that the blank-class inventory is duplicative; proves pre-1980 payloads are fetchable"),
    "V17-C12": ("Furosemide 1980-1984 originals incl. NDA018413 (openFDA)",
                "pre1985_fda_decisions.csv", "PRE1985-1983-07",
                "an ORIG-1 dated 1983-11-30 with no class code and no priority reproduces the NDA018413 condition live",
                "corroborates the pre-1985 table's NOT STATED values from a second FDA route"),
    "V17-C10": ("1985 Compilation section - local workbook parse",
                "fda_decisions_master.csv", "D1040 + all 1985 rows",
                "31 rows (18 Priority / 13 Standard); Tambocor row read verbatim as 'Priority'; dataset-wide 1,108 NDA / 279 BLA",
                "proves the master's Priority value traces to the FDA cell, not a transcription error"),
}
capture_rows = []
for cap in LIVE["captures"]:
    cid = cap["capture_id"]
    if cid not in CAPTURE_INDEX:
        fail(f"live capture {cid} has no index entry")
    subject, table, rows, finding, effect = CAPTURE_INDEX[cid]
    capture_rows.append({
        "capture_id": cid,
        "capture_date": LIVE["captured_utc"],
        "system": cap["system"],
        "subject": subject,
        "url": cap["url"],
        "finding_summary": finding,
        "project_table_affected": table,
        "project_row_ids": rows,
        "project_effect": effect,
        "verbatim_evidence_ref": "data/raw/source_captures_2026_09_19/live_primary_captures_2026_09_19.json",
    })


PROBE_ROWS = [{
    "probe_id": "PRE1980-API-1",
    "probe_date": LIVE["captured_utc"],
    "system": "openFDA Drugs@FDA API (api.fda.gov)",
    "query_url": ("https://api.fda.gov/drug/drugsfda.json?search=products.active_ingredients.name:%22FUROSEMIDE%22"
                  "+AND+submissions.submission_type:%22ORIG%22+AND+submissions.submission_status:%22AP%22"
                  "+AND+submissions.submission_status_date:%5B19000101+TO+19791231%5D&limit=2"),
    "query_semantics": "ORIG submissions with status AP whose status date falls before 1980, for one long-marketed ingredient",
    "total_hits": "4",
    "earliest_verifiable_original": "ORIG-1 approved 1968-03-20, submission_class_code TYPE 3 - New Dosage Form, review_priority PRIORITY",
    "project_implication": ("openFDA serves pre-1980 ORIG/AP submission records, so a pre-1980 payload fetch job is feasible and "
                            "the project's 1980 boundary is a coverage choice, not an API limit. A pre-1980 block still needs a "
                            "committed fetch_jobs payload (the sandbox has no bulk network) before any pre-1980 table work."),
    "evidence_ref": "data/raw/source_captures_2026_09_19/live_primary_captures_2026_09_19.json#V17-C11",
}]


def write_csv(name: str, rows: list[dict]) -> None:
    path = DATA / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


write_csv("fda_official_year_series.csv", series_rows)
write_csv("fda_official_series_crosswalk.csv", crosswalk)
write_csv("pre1985_nme_gap_analysis.csv", GAP_ROWS)
write_csv("pre1985_primary_captures_index.csv", capture_rows)
write_csv("pre1980_openfda_probe_2026_09_19.csv", PROBE_ROWS)

# --------------------------------------------------------------------------- #
# Summary + invariants
# --------------------------------------------------------------------------- #
short = [r["year"] for r in crosswalk if r["verdict"] == "PROJECT_SHORT_FLAGGED"]
match = [r["year"] for r in crosswalk if r["verdict"] == "MATCH"]
comp_short = [r["year"] for r in crosswalk if isinstance(r["delta_compilation_vs_official"], int)
              and r["delta_compilation_vs_official"] < 0]
print(f"official NME series: {min(OFFICIAL_NME)}-{max(OFFICIAL_NME)}; "
      f"crosswalk 1980-2026: {len(crosswalk)} years")
print(f"MATCH years: {len(match)}; PROJECT_SHORT years: {short}")
print(f"Compilation short of the official NME count in: {comp_short}")
print(f"Compilation types: {dict(COMPILATION_KINDS)}")
print("LIVE CAPTURE COUNT:", len(capture_rows), "| captured:", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
