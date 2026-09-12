#!/usr/bin/env python3
"""Shared extraction logic for openFDA Drugs@FDA application records.

Used both by the GitHub Actions fetch runner (which runs it against the live
payload before committing, so the repository never has to store 100+ MB of
JSON) and by the local build scripts.

Rules that keep the output hallucination-free:

* A "decision" is emitted only when a *single* submission object satisfies all
  of: ``submission_type == ORIG``, ``submission_status == AP`` and a
  ``submission_status_date`` inside the requested year. openFDA flattens
  nested fields, so filtering on the three clauses separately would match
  applications where *different* submissions satisfy each clause - this module
  does the precise match instead.
* Every emitted record carries the exact API request URL and the Drugs@FDA
  application URL so it can be re-verified by hand.
* Nothing is inferred: if a field is missing upstream it is left empty.
"""

from __future__ import annotations

import re

DRUGSFDA_URL = (
    "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
    "?event=overview.process&varApplNo={appl}"
)

# openFDA returns application numbers such as NDA021996 / BLA125145 / ANDA078902.
APPL_RE = re.compile(r"^(?P<kind>[A-Z]+)(?P<num>\d+)$")

CLASS_ORDER = {
    "Type 1": 1,
    "Type 1/4": 1,
    "Type 2": 2,
    "Type 3": 3,
    "Type 4": 4,
    "Type 5": 5,
}


def appl_parts(application_number: str):
    m = APPL_RE.match((application_number or "").strip())
    if not m:
        return None, None
    return m.group("kind"), m.group("num")


def iso_date(yyyymmdd: str) -> str:
    """Drugs@FDA dates are YYYYMMDD. Returns ISO or '' when unusable."""
    s = (yyyymmdd or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return ""


def class_rank(desc: str) -> int:
    for key, rank in CLASS_ORDER.items():
        if (desc or "").startswith(key):
            return rank
    return 99


def compact_products(products) -> list:
    out = []
    for p in products or []:
        ing = "; ".join(
            f"{a.get('name','').strip()} {a.get('strength','').strip()}".strip()
            for a in p.get("active_ingredients") or []
        )
        out.append({
            "product_number": p.get("product_number", ""),
            "brand_name": (p.get("brand_name") or "").strip(),
            "active_ingredients": ing,
            "dosage_form": (p.get("dosage_form") or "").strip(),
            "route": (p.get("route") or "").strip(),
            "marketing_status": (p.get("marketing_status") or "").strip(),
        })
    return out


def extract(rec: dict, year: int, query_url: str, keep_submissions: bool = False):
    """Return a decision dict, or None when the record has no ORIG/AP event in `year`."""
    appl = (rec.get("application_number") or "").strip()
    kind, num = appl_parts(appl)
    if kind not in {"NDA", "BLA"}:
        return None
    subs = rec.get("submissions") or []
    hits = [
        s for s in subs
        if (s.get("submission_type") or "").strip().upper() == "ORIG"
        and (s.get("submission_status") or "").strip().upper() == "AP"
        and iso_date(s.get("submission_status_date", "")).startswith(str(year))
    ]
    if not hits:
        return None
    # Prefer the earliest ORIG approval inside the year; record the others.
    hits.sort(key=lambda s: iso_date(s.get("submission_status_date", "")))
    primary = hits[0]
    ofda = rec.get("openfda") or {}

    def first(x):
        if isinstance(x, list):
            return x[0] if x else ""
        return x or ""

    products = compact_products(rec.get("products"))
    out = {
        "application_number": appl,
        "application_kind": kind,
        "application_num": num,
        "sponsor_name": (rec.get("sponsor_name") or "").strip(),
        "brand_name_openfda": first(ofda.get("brand_name")),
        "generic_name_openfda": first(ofda.get("generic_name")),
        "manufacturer_name": first(ofda.get("manufacturer_name")),
        "pharm_class_epc": "; ".join(ofda.get("pharm_class_epc") or []),
        "route": first(ofda.get("route")),
        "substance_name": "; ".join(ofda.get("substance_name") or []),
        "products": products,
        "decision_date": iso_date(primary.get("submission_status_date", "")),
        "submission_class_code": (primary.get("submission_class_code") or "").strip(),
        "submission_class_code_description": (primary.get("submission_class_code_description") or "").strip(),
        "review_priority": (primary.get("review_priority") or "").strip(),
        "n_orig_approvals_in_year": len(hits),
        "other_orig_dates_in_year": [iso_date(s.get("submission_status_date", "")) for s in hits[1:]],
        "source_url_drugsatfda": DRUGSFDA_URL.format(appl=num),
        "source_query_url": query_url,
    }
    if keep_submissions:
        out["orig_submissions"] = hits
    return out


def extract_year(payload: dict, year: int, query_url: str):
    """Extract every ORIG/AP NDA/BLA decision from one openFDA year payload."""
    recs = payload.get("results") or []
    out = []
    for rec in recs:
        d = extract(rec, year, query_url)
        if d:
            out.append(d)
    # de-duplicate on application number + decision date
    seen, uniq = set(), []
    for d in out:
        key = (d["application_number"], d["decision_date"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)
    uniq.sort(key=lambda d: (d["decision_date"], d["application_number"]))
    return uniq


if __name__ == "__main__":
    import json
    import sys

    year = int(sys.argv[1])
    payload = json.load(open(sys.argv[2]))
    query_url = sys.argv[3] if len(sys.argv) > 3 else ""
    rows = extract_year(payload, year, query_url)
    json.dump({"year": year, "count": len(rows), "decisions": rows}, sys.stdout, indent=1)
