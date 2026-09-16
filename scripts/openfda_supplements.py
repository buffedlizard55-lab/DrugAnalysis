#!/usr/bin/env python3
"""Extraction logic for FDA **efficacy supplement** approvals (Drugs@FDA).

An *efficacy supplement* (submission_class_code == "EFFICACY") is the
regulatory vehicle FDA uses for a new indication, a new population, or a
labelled efficacy claim change on an already-approved NDA/BLA.  These are
real, dated FDA decisions on publicly traded companies' drugs, and they are
by far the largest body of *officially documented* FDA efficacy decisions:
roughly 130-600 per calendar year versus ~50 novel (NME) approvals.

Why this module exists
----------------------
The repository's master list already covers novel drug approvals 2000-2026
completely.  Growing the decision universe further without inventing data
requires a source where every field can be copied verbatim from an official
FDA record.  Drugs@FDA efficacy supplements satisfy that: sponsor, brand
name, application number, submission number, decision date, review priority
and the FDA approval-letter PDF all come straight from openFDA.

Rules that keep the output hallucination-free
---------------------------------------------
* A record is emitted only when a **single** submission object satisfies all
  of: ``submission_type == SUPPL``, ``submission_class_code == EFFICACY``,
  ``submission_status == AP`` and ``submission_status_date`` inside the
  requested year.  openFDA flattens nested fields, so querying the three
  clauses separately would match applications where *different* submissions
  satisfy each clause; this module does the precise per-submission match.
* Every emitted record carries (a) the FDA approval-letter PDF URL when
  openFDA publishes one for that exact submission, (b) the Drugs@FDA
  application overview URL, and (c) the exact API request URL, so any row can
  be re-verified by hand.
* Nothing is inferred.  Missing upstream fields are emitted as empty strings.
  The *indication* text is deliberately NOT synthesised: FDA does not publish
  it as a structured field for supplements, so the row points at the approval
  letter instead of guessing.
"""

from __future__ import annotations

import re

DRUGSFDA_URL = (
    "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
    "?event=overview.process&varApplNo={appl}"
)

APPL_RE = re.compile(r"^(?P<kind>[A-Z]+)(?P<num>\d+)$")


def appl_parts(application_number: str):
    m = APPL_RE.match((application_number or "").strip())
    if not m:
        return None, None
    return m.group("kind"), m.group("num")


def iso_date(yyyymmdd: str) -> str:
    s = (yyyymmdd or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return ""


def _first(x):
    if isinstance(x, list):
        return x[0] if x else ""
    return x or ""


def _docs(sub: dict):
    """Return (letter_url, label_url) exactly as published by openFDA."""
    letter = label = ""
    for d in sub.get("application_docs") or []:
        kind = (d.get("type") or "").strip().lower()
        url = (d.get("url") or "").strip()
        if not url:
            continue
        if kind == "letter" and not letter:
            letter = url
        elif kind == "label" and not label:
            label = url
    return letter, label


def extract(rec: dict, year: int, query_url: str):
    """Yield one dict per EFFICACY/AP supplement of `rec` decided in `year`."""
    appl = (rec.get("application_number") or "").strip()
    kind, num = appl_parts(appl)
    if kind not in {"NDA", "BLA"}:
        return []
    ofda = rec.get("openfda") or {}
    products = rec.get("products") or []
    brand = _first(ofda.get("brand_name")) or (
        (products[0].get("brand_name") or "").strip() if products else ""
    )
    generic = _first(ofda.get("generic_name"))
    if not generic and products:
        ing = products[0].get("active_ingredients") or []
        generic = "; ".join((a.get("name") or "").strip() for a in ing)

    out = []
    for sub in rec.get("submissions") or []:
        if (sub.get("submission_type") or "").strip().upper() != "SUPPL":
            continue
        if (sub.get("submission_class_code") or "").strip().upper() != "EFFICACY":
            continue
        if (sub.get("submission_status") or "").strip().upper() != "AP":
            continue
        date = iso_date(sub.get("submission_status_date", ""))
        if not date.startswith(str(year)):
            continue
        letter, label = _docs(sub)
        props = [
            (p.get("code") or "").strip()
            for p in sub.get("submission_property_type") or []
            if (p.get("code") or "").strip()
        ]
        out.append({
            "application_number": appl,
            "application_kind": kind,
            "application_num": num,
            "submission_number": (sub.get("submission_number") or "").strip(),
            "sponsor_name": (rec.get("sponsor_name") or "").strip(),
            "brand_name": brand,
            "generic_name": generic,
            "substance_name": "; ".join(ofda.get("substance_name") or []),
            "pharm_class_epc": "; ".join(ofda.get("pharm_class_epc") or []),
            "route": _first(ofda.get("route")),
            "manufacturer_name": _first(ofda.get("manufacturer_name")),
            "decision_date": date,
            "review_priority": (sub.get("review_priority") or "").strip(),
            "submission_property_type": "; ".join(props),
            "approval_letter_url": letter,
            "label_url": label,
            "source_url_drugsatfda": DRUGSFDA_URL.format(appl=num),
            "source_query_url": query_url,
        })
    return out


def extract_year(payload: dict, year: int, query_url: str):
    rows = []
    for rec in payload.get("results") or []:
        rows.extend(extract(rec, year, query_url))
    seen, uniq = set(), []
    for r in rows:
        key = (r["application_number"], r["submission_number"], r["decision_date"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    uniq.sort(key=lambda r: (r["decision_date"], r["application_number"], r["submission_number"]))
    return uniq


if __name__ == "__main__":
    import json
    import sys

    year = int(sys.argv[1])
    payload = json.load(open(sys.argv[2]))
    rows = extract_year(payload, year, sys.argv[3] if len(sys.argv) > 3 else "")
    json.dump({"year": year, "count": len(rows), "supplements": rows}, sys.stdout, indent=1)
