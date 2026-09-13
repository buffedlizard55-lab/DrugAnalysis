#!/usr/bin/env python3
"""Build the 2000-2010 candidate rows for data/fda_decisions_master.csv.

Inputs (all committed under data/raw or data/staging, all official):

* ``data/raw/probe/fda_nme_compilation_1985_2025.xlsx``
  FDA, *Compilation of CDER New Molecular Entity (NME) Drug and New Biologic
  Approvals, 1985-2025* (https://www.fda.gov/media/177921/download).
  Supplies: applicant at approval, approval date, indication text, review
  designation, accelerated approval / orphan / breakthrough / fast track flags.
* ``data/staging/openfda_decisions_2000_2010.json``
  openFDA Drugs@FDA API (https://api.fda.gov/drug/drugsfda.json) - supplies the
  application number, the FDA applicant of record, the product/brand names and
  the FDA submission classification code.

This script only *joins and normalises* what those two official sources say.
It never invents a value: when one of the sources has no data for a field the
field is left empty and the reason is written to the row's notes.

It writes:

* ``data/staging/candidates_2000_2010.json`` - the joined candidate rows
  (nothing has been appended to the published tables yet)
* ``data/staging/candidate_gaps_2011_2025.json`` - CDER NME compilation rows in
  2011-2025 that the master list does not already contain
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STAGING = DATA / "staging"
RAW = DATA / "raw"

NME_XLSX = RAW / "probe" / "fda_nme_compilation_1985_2025.xlsx"
NME_SOURCE_PAGE = ("https://www.fda.gov/drugs/drug-approvals-and-databases/"
                   "compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals")
NME_SOURCE_FILE = "https://www.fda.gov/media/177921/download?attachment"
OPENFDA_JSON = STAGING / "openfda_decisions_2000_2010.json"

MASTER = DATA / "fda_decisions_master.csv"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def clean_date(value) -> str:
    """Accept datetime, 'YYYY-MM-DD ...' or 'M/D/YYYY' and return ISO date or ''."""
    if value is None:
        return ""
    s = str(value).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def title_case_sponsor(name: str) -> str:
    """openFDA returns uppercase short sponsor names (e.g. 'ABBVIE').

    They are rendered in title case purely for readability - the value itself is
    never changed, and the original uppercase string is kept in
    ``sponsor_name_raw`` so the row can be matched back to the API response.
    """
    s = (name or "").strip()
    small = {"and", "of", "the", "us", "usa", "de", "for"}
    parts = []
    for word in s.split():
        w = word.lower()
        if w.isupper() and len(w) <= 3 and w not in ("us", "usa"):
            parts.append(w.upper())          # keep FDA-style acronyms (e.g. JANSSEN PHARMS)
        elif w in small and parts:
            parts.append(w)
        else:
            parts.append(w[:1].upper() + w[1:])
    out = " ".join(parts)
    return out


def first_sentence(text: str, limit: int = 240) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if not t:
        return ""
    m = re.split(r"(?<=[.!?])\s+", t)
    head = m[0]
    if len(head) > limit:
        head = head[: limit - 1].rstrip() + "…"
    return head


def scope_for(desc: str) -> str:
    d = (desc or "").lower()
    if d.startswith("type 1"):
        return "Novel (new molecular entity / new biologic)"
    if d.startswith("type 2"):
        return "New active ingredient"
    if d.startswith("type 3") or d.startswith("type 4") or "/4" in d:
        return "New dosage form or combination"
    if d.startswith("type 8"):
        return "Prescription-to-OTC switch"
    if d.startswith("type 6") or d.startswith("type 9"):
        return "New indication"
    if d.startswith("type 5") or d.startswith("type 7"):
        return "New formulation, manufacturer or marketing status"
    return "Other new application"


def pathway_from_openfda(priority: str) -> str:
    p = (priority or "").strip().upper()
    if p == "PRIORITY":
        return "Priority"
    if p == "STANDARD":
        return "Standard"
    return ""


# --------------------------------------------------------------------------
# load sources
# --------------------------------------------------------------------------

def load_compilation():
    import openpyxl

    wb = openpyxl.load_workbook(NME_XLSX, data_only=True)
    ws = wb["2025 Compilation"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h).strip() if h else h for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = dict(zip(hdr, r))
        year = d.get("Approval Year")
        d["_year"] = int(year) if isinstance(year, (int, float)) else None
        if not d["_year"]:
            continue
        apps = []
        for i in (1, 2, 3):
            v = d.get(f"Application Number({i})")
            if v is None or str(v).strip() == "":
                continue
            num = str(int(v)) if isinstance(v, float) else str(v).strip()
            kind = (d.get("NDA/BLA") or "").strip().upper()
            apps.append(f"{kind}{num.zfill(6)}")
        d["_apps"] = apps
        out.append(d)
    return out


def load_master_keys():
    """Identity keys already present in the published master list.

    Four independent keys are collected (application number, brand+date,
    brand+year, generic+year) because FDA publishes slightly different dates in
    different systems - e.g. Tzield is dated 2022-11-17 in the CDER NME
    compilation and 2022-11-18 on the label PDF the master list was built from.
    A candidate is skipped only when it is already covered on one of them, and
    every skipped candidate is written to ``data/staging/dedupe_report.json``
    so the suppression can be reviewed rather than trusted blindly.
    """
    apps, brand_date, brand_year, generic_year = set(), set(), set(), set()
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            blob = " ".join((r.get("source_url_1") or "", r.get("source_url_2") or "",
                             r.get("notes") or ""))
            for m in re.findall(r"varApplNo=(\d+)", blob):
                apps.add(m.lstrip("0").zfill(6))
            for m in re.findall(r"(?:NDA|BLA)\s*(\d{5,7})", blob):
                apps.add(m.lstrip("0").zfill(6))
            brand, generic, date = (r.get("drug_brand") or ""), (r.get("drug_generic") or ""), \
                (r.get("decision_date") or "").strip()
            brand_date.add((norm(brand), date))
            if date:
                brand_year.add((norm(brand), date[:4]))
                if norm(generic):
                    generic_year.add((norm(generic), date[:4]))
    return apps, brand_date, brand_year, generic_year


def main() -> None:
    comp = load_compilation()
    master_apps, master_brand_date, master_brand_year, master_generic_year = load_master_keys()
    dedupe_report = []
    openfda = json.load(open(OPENFDA_JSON))["decisions"]

    comp_by_app = {}
    for d in comp:
        for a in d["_apps"]:
            comp_by_app.setdefault(a, []).append(d)

    # ---------------- 2000-2010: openFDA decisions, enriched by compilation ---
    candidates = []
    for d in openfda:
        appl = d["application_number"]
        crows = comp_by_app.get(appl, [])
        c = crows[0] if crows else None
        products = d.get("products") or []
        brand = (products[0]["brand_name"] if products else "") or d.get("brand_name_openfda", "")
        generic = (products[0]["active_ingredients"] if products else "") or d.get("generic_name_openfda", "")
        if c:
            brand = (c.get("Proprietary  Name") or "").strip() or brand
            generic = (c.get("Active Ingredient/Moiety") or "").strip() or generic

        notes = []
        comp_dates = [clean_date(cr.get("FDA Approval Date")) for cr in crows]
        if c and clean_date(c.get("FDA Approval Date")) and clean_date(c.get("FDA Approval Date")) != d["decision_date"]:
            notes.append(
                f"date conflict: Drugs@FDA ORIG approval action {d['decision_date']} vs CDER NME compilation "
                f"{clean_date(c.get('FDA Approval Date'))} - Drugs@FDA date used, both recorded"
            )
        if len(crows) > 1:
            notes.append("application number is shared by more than one CDER NME compilation entry: "
                         + "; ".join(sorted({(cr.get("Proprietary  Name") or '').strip() for cr in crows})))
        if not d.get("review_priority"):
            notes.append("no review priority published by openFDA for this submission")

        indication = ""
        approved_use = ""
        review_pathway = pathway_from_openfda(d.get("review_priority"))
        flags = {}
        if c:
            approved_use = re.sub(r"\s+", " ", (c.get("Approved Use(s)") or "")).strip()
            indication = (c.get("Abbreviated Indication(s)") or "").strip() or first_sentence(approved_use)
            desig = (c.get("Review Designation") or "").strip()
            aa = (c.get("Accelerated Approval") or "").strip()
            if desig in ("Priority", "Standard"):
                review_pathway = desig + ("; Accelerated Approval" if aa == "Yes" else "")
            elif aa == "Yes":
                review_pathway = (review_pathway + "; Accelerated Approval").strip("; ")
            flags = {
                "orphan_drug_designation": (c.get("Orphan Drug Designation") or "").strip(),
                "accelerated_approval": aa,
                "breakthrough_therapy": (c.get("Breakthrough Therapy Designation") or "").strip(),
                "fast_track": (c.get("Fast Track Designation") or "").strip(),
                "qualified_infectious_disease_product": (c.get("Qualified Infectious Disease Product") or "").strip(),
                "priority_review_voucher_issued": (c.get("Issued a Priority Review Voucher") or "").strip(),
                "priority_review_voucher_redeemed": (c.get("Redeemed a Priority Review Voucher") or "").strip(),
                "fda_receipt_date": clean_date(c.get("FDA Receipt Date")),
            }
            if (c.get("Notes") or "").strip():
                notes.append("CDER NME compilation note: " + re.sub(r"\s+", " ", str(c.get("Notes"))).strip())

        candidates.append({
            "application_number": appl,
            "application_kind": d["application_kind"],
            "decision_date": d["decision_date"],
            "decision_type": "Approval",
            "drug_brand": brand.strip(),
            "drug_generic": re.sub(r"\s+", " ", generic).strip(),
            "sponsor_name_raw": d["sponsor_name"],
            "company_name_current": title_case_sponsor(d["sponsor_name"]),
            "applicant_at_approval": (c.get("Applicant") or "").strip() if c else "",
            "submission_class": d["submission_class_code_description"],
            "submission_class_code": d["submission_class_code"],
            "decision_scope": scope_for(d["submission_class_code_description"]),
            "review_pathway": review_pathway,
            "review_priority_openfda": d["review_priority"],
            "indication": indication,
            "approved_use_full": approved_use,
            "dosage_form": (products[0]["dosage_form"] if products else ""),
            "route": (products[0]["route"] if products else ""),
            "pharm_class_epc": d.get("pharm_class_epc", ""),
            "nme_compilation_match": bool(c),
            "flags": flags,
            "source_url_drugsatfda": d["source_url_drugsatfda"],
            "source_url_openfda_query": d["source_query_url"],
            "source_url_nme_compilation": NME_SOURCE_FILE if c else "",
            "source_page_nme_compilation": NME_SOURCE_PAGE if c else "",
            "notes": "; ".join(notes),
        })

    # ---------------- compilation rows 2000-2010 with no openFDA ORIG record --
    covered = {c["application_number"] for c in candidates}
    comp_only = []
    for d in comp:
        if not (2000 <= d["_year"] <= 2010):
            continue
        if any(a in covered for a in d["_apps"]):
            continue
        app = d["_apps"][0] if d["_apps"] else ""
        approved_use = re.sub(r"\s+", " ", (d.get("Approved Use(s)") or "")).strip()
        desig = (d.get("Review Designation") or "").strip()
        aa = (d.get("Accelerated Approval") or "").strip()
        pathway = desig + ("; Accelerated Approval" if aa == "Yes" else "") if desig in ("Priority", "Standard") else ""
        comp_only.append({
            "application_number": app,
            "application_kind": (d.get("NDA/BLA") or "").strip().upper(),
            "decision_date": clean_date(d.get("FDA Approval Date")),
            "decision_type": "Approval",
            "drug_brand": (d.get("Proprietary  Name") or "").strip(),
            "drug_generic": (d.get("Active Ingredient/Moiety") or "").strip(),
            "sponsor_name_raw": "",
            "company_name_current": "",
            "applicant_at_approval": (d.get("Applicant") or "").strip(),
            "submission_class": "Type 1 - New Molecular Entity (CDER NME compilation)",
            "submission_class_code": "",
            "decision_scope": "Novel (new molecular entity / new biologic)",
            "review_pathway": pathway,
            "review_priority_openfda": "",
            "indication": (d.get("Abbreviated Indication(s)") or "").strip() or first_sentence(approved_use),
            "approved_use_full": approved_use,
            "dosage_form": (d.get("Dosage Form(1)") or "").strip(),
            "route": (d.get("Route of Administration(1)") or "").strip(),
            "pharm_class_epc": "",
            "nme_compilation_match": True,
            "flags": {
                "orphan_drug_designation": (d.get("Orphan Drug Designation") or "").strip(),
                "accelerated_approval": aa,
                "breakthrough_therapy": (d.get("Breakthrough Therapy Designation") or "").strip(),
                "fast_track": (d.get("Fast Track Designation") or "").strip(),
                "qualified_infectious_disease_product": (d.get("Qualified Infectious Disease Product") or "").strip(),
                "priority_review_voucher_issued": (d.get("Issued a Priority Review Voucher") or "").strip(),
                "priority_review_voucher_redeemed": (d.get("Redeemed a Priority Review Voucher") or "").strip(),
                "fda_receipt_date": clean_date(d.get("FDA Receipt Date")),
            },
            "source_url_drugsatfda": ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                                      f"?event=overview.process&varApplNo={app[3:]}" if app else ""),
            "source_url_openfda_query": "",
            "source_url_nme_compilation": NME_SOURCE_FILE,
            "source_page_nme_compilation": NME_SOURCE_PAGE,
            "notes": ("no ORIG approval record returned by openFDA Drugs@FDA for this application number; "
                      "row sourced solely from the CDER NME compilation"),
        })

    # ---------------- 2011-2025 compilation gaps -----------------------------
    gaps = []
    for d in comp:
        if d["_year"] < 2011:
            continue
        brand = (d.get("Proprietary  Name") or "").strip()
        generic = (d.get("Active Ingredient/Moiety") or "").strip()
        date = clean_date(d.get("FDA Approval Date"))
        reasons = []
        if any(a[3:].lstrip("0").zfill(6) in master_apps for a in d["_apps"]):
            reasons.append("application number already in master")
        if (norm(brand), date) in master_brand_date:
            reasons.append("brand+date already in master")
        if (norm(brand), date[:4]) in master_brand_year:
            reasons.append("brand+year already in master")
        if norm(generic) and (norm(generic), date[:4]) in master_generic_year:
            reasons.append("generic+year already in master")
        if reasons:
            dedupe_report.append({"brand": brand, "generic": generic, "date": date,
                                  "application_numbers": d["_apps"], "skipped_because": reasons})
            continue
        approved_use = re.sub(r"\s+", " ", (d.get("Approved Use(s)") or "")).strip()
        desig = (d.get("Review Designation") or "").strip()
        aa = (d.get("Accelerated Approval") or "").strip()
        pathway = desig + ("; Accelerated Approval" if aa == "Yes" else "") if desig in ("Priority", "Standard") else ""
        app = d["_apps"][0] if d["_apps"] else ""
        gaps.append({
            "application_number": app,
            "application_kind": (d.get("NDA/BLA") or "").strip().upper(),
            "decision_date": clean_date(d.get("FDA Approval Date")),
            "decision_type": "Approval",
            "drug_brand": (d.get("Proprietary  Name") or "").strip(),
            "drug_generic": (d.get("Active Ingredient/Moiety") or "").strip(),
            "sponsor_name_raw": "",
            "company_name_current": "",
            "applicant_at_approval": (d.get("Applicant") or "").strip(),
            "submission_class": "Type 1 - New Molecular Entity (CDER NME compilation)",
            "submission_class_code": "",
            "decision_scope": "Novel (new molecular entity / new biologic)",
            "review_pathway": pathway,
            "review_priority_openfda": "",
            "indication": (d.get("Abbreviated Indication(s)") or "").strip() or first_sentence(approved_use),
            "approved_use_full": approved_use,
            "dosage_form": (d.get("Dosage Form(1)") or "").strip(),
            "route": (d.get("Route of Administration(1)") or "").strip(),
            "pharm_class_epc": "",
            "nme_compilation_match": True,
            "flags": {
                "orphan_drug_designation": (d.get("Orphan Drug Designation") or "").strip(),
                "accelerated_approval": aa,
                "breakthrough_therapy": (d.get("Breakthrough Therapy Designation") or "").strip(),
                "fast_track": (d.get("Fast Track Designation") or "").strip(),
                "qualified_infectious_disease_product": (d.get("Qualified Infectious Disease Product") or "").strip(),
                "priority_review_voucher_issued": (d.get("Issued a Priority Review Voucher") or "").strip(),
                "priority_review_voucher_redeemed": (d.get("Redeemed a Priority Review Voucher") or "").strip(),
                "fda_receipt_date": clean_date(d.get("FDA Receipt Date")),
            },
            "source_url_drugsatfda": ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                                      f"?event=overview.process&varApplNo={app[3:]}" if app else ""),
            "source_url_openfda_query": "",
            "source_url_nme_compilation": NME_SOURCE_FILE,
            "source_page_nme_compilation": NME_SOURCE_PAGE,
            "notes": "CDER NME compilation row not present in fda_decisions_master.csv before this backfill",
        })

    STAGING.mkdir(parents=True, exist_ok=True)
    allrows = sorted(candidates + comp_only, key=lambda r: (r["decision_date"], r["drug_brand"]))
    json.dump({"generated_by": "scripts/build_backfill_2000_2010.py",
               "sources": [str(NME_SOURCE_FILE), "https://api.fda.gov/drug/drugsfda.json"],
               "count": len(allrows), "rows": allrows},
              open(STAGING / "candidates_2000_2010.json", "w"), indent=1)
    json.dump({"generated_by": "scripts/build_backfill_2000_2010.py",
               "sources": [str(NME_SOURCE_FILE)],
               "count": len(gaps), "rows": gaps},
              open(STAGING / "candidate_gaps_2011_2025.json", "w"), indent=1)
    json.dump({"generated_by": "scripts/build_backfill_2000_2010.py",
               "count": len(dedupe_report),
               "note": "CDER NME compilation rows 2011-2025 suppressed because the master list "
                       "already appears to cover them - review before trusting",
               "rows": dedupe_report},
              open(STAGING / "dedupe_report.json", "w"), indent=1)

    print(f"2000-2010 candidates : {len(candidates)} (openFDA) + {len(comp_only)} (compilation-only) = {len(allrows)}")
    print(f"2011-2025 gaps       : {len(gaps)}")
    by_scope = {}
    for r in allrows:
        by_scope[r["decision_scope"]] = by_scope.get(r["decision_scope"], 0) + 1
    for k, v in sorted(by_scope.items(), key=lambda kv: -kv[1]):
        print(f"   {v:5d}  {k}")
    print(f"suppressed as duplicates: {len(dedupe_report)}")
    print("\ngap years:", sorted({g['decision_date'][:4] for g in gaps}))
    from collections import Counter
    print("gap year counts:", Counter(g['decision_date'][:4] for g in gaps))


if __name__ == "__main__":
    main()
