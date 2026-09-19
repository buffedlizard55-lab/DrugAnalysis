#!/usr/bin/env python3
"""Append pre-1980 Type 1/Type 1-4 approvals from committed FDA payloads.

This is intentionally a narrow, fail-closed builder.  It does not name an
applicant, ticker, indication, or historical sponsor when the payload does not
provide one.  The only populated regulatory facts are copied from the
committed openFDA extraction.  It refuses to write unless every requested
1965-1979 payload and its manifest exists and every year contains at least one
Type 1-class record; a missing Type 1 payload is an error, never a reason to
invent a row.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "pre1985_fda_decisions.csv"
RAW_DIRS = [DATA / "raw" / f"openfda_orig_decisions_{a}_{b}" for a, b in ((1965, 1969), (1970, 1974), (1975, 1979))]
YEARS = range(1965, 1980)
HEADER = ["decision_id", "year", "application_number", "drug_brand", "drug_generic", "company_name",
          "corporate_lineage_and_ticker", "decision_type", "decision_date", "chemical_type_code",
          "chemical_type_description", "review_priority", "indication", "regulatory_milestone",
          "source_url_1", "source_url_2", "verification_status", "notes"]


def norm_num(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-6:].zfill(6)


def payloads():
    rows = []
    for raw in RAW_DIRS:
        manifest = raw / "manifest.json"
        if not manifest.exists():
            raise SystemExit(f"missing manifest: {manifest}")
        # Read by the explicit year range encoded in the directory name.
        m = re.search(r"_(\d{4})_(\d{4})$", raw.name)
        if not m:
            raise SystemExit(f"cannot determine year range from {raw}")
        lo, hi = map(int, m.groups())
        for year in range(lo, hi + 1):
            path = raw / f"decisions_{year}.json"
            if not path.exists():
                raise SystemExit(f"missing committed payload: {path}")
            obj = json.loads(path.read_text(encoding="utf-8"))
            decisions = obj.get("decisions")
            if not isinstance(decisions, list):
                raise SystemExit(f"invalid decisions list: {path}")
            typed = [r for r in decisions if (r.get("submission_class_code") or "").upper() in {"TYPE 1", "TYPE 1/4"}]
            if not typed:
                raise SystemExit(f"{year}: no Type 1/Type 1-4 records in {path}; aborting without writing")
            rows.extend(typed)
    return rows


def main() -> int:
    records = payloads()
    existing = list(csv.DictReader(OUT.open(newline="", encoding="utf-8-sig"))) if OUT.exists() else []
    existing_apps = {norm_num(r.get("application_number", "")) for r in existing}
    additions = []
    for r in records:
        app = norm_num(r.get("application_number", ""))
        year = int((r.get("decision_date") or "")[:4])
        if year not in YEARS or app in existing_apps:
            continue
        brand = (r.get("brand_name_openfda") or "").strip()
        if not brand and r.get("products"):
            brand = (r["products"][0].get("brand_name") or "").strip()
        generic = (r.get("generic_name_openfda") or r.get("substance_name") or "").strip()
        app_label = f"{r.get('application_kind', 'NDA')}{app}"
        query = r.get("source_query_url", "")
        additions.append({
            "decision_id": f"PRE1985-{year}-{app}", "year": year,
            "application_number": app_label, "drug_brand": brand, "drug_generic": generic,
            "company_name": f"{r.get('sponsor_name','').strip()} (current Drugs@FDA holder; approval-era applicant not pinned)",
            "corporate_lineage_and_ticker": "Not assigned: historical applicant and period ticker require separate primary-source evidence; no inference made.",
            "decision_type": "APPROVAL (ORIGINAL NDA)", "decision_date": r.get("decision_date", ""),
            "chemical_type_code": r.get("submission_class_code", ""),
            "chemical_type_description": r.get("submission_class_code_description", ""),
            "review_priority": r.get("review_priority", ""), "indication": "",
            "regulatory_milestone": "Pre-1980 approval; indication and lineage are not asserted without an approval-era primary record.",
            "source_url_1": r.get("source_url_drugsatfda", ""), "source_url_2": query,
            "verification_status": "Verified from committed openFDA payload",
            "notes": f"Pre-1980 Type 1 expansion. Fields are copied from the committed FDA extraction; openFDA sponsor is the current Drugs@FDA holder, not asserted as the historical applicant. Payload product/class/date/priority are verbatim. No ticker or indication guessed. Payload application={r.get('application_number','')}; brand={brand}; generic={generic}.",
        })
        existing_apps.add(app)
    if additions:
        all_rows = existing + additions
        all_rows.sort(key=lambda r: (r["decision_date"], r["application_number"]))
        with OUT.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=HEADER)
            writer.writeheader(); writer.writerows(all_rows)
    print(f"pre-1980 payloads verified: {len(records)} Type 1 rows; appended {len(additions)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
