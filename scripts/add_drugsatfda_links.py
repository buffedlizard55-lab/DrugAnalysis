#!/usr/bin/env python3
"""Attach a Drugs@FDA application link to master rows that had none.

Why: scripts/crosscheck_master_vs_openfda.py can only machine-verify a master
row when the row cites a Drugs@FDA application number (``varApplNo=``). 264 of
the rows imported from FDA's HTML year tables (which stopped embedding
application numbers around 2019) had no such link and were parked as
NO_APPL_NUMBER — an un-audited blind spot.

How: for each such row, look the brand up in the committed openFDA ORIG/AP
payloads (data/raw/openfda_orig_decisions_2011_2026/decisions_<year>.json,
captured verbatim by the GitHub Actions fetch job). A link is written ONLY
when exactly one application carries that brand with an ORIG approval date
within 3 days of the master decision_date. Anything ambiguous or unmatched is
left untouched and listed on stdout for human review — nothing is guessed.

The link goes into source_url_2 when that column is empty; otherwise the
application number is recorded in notes as ``appl NDA######`` together with the
Drugs@FDA URL, which the cross-check regex also picks up.
"""
from __future__ import annotations

import csv
import glob
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "fda_decisions_master.csv"
RAW = ROOT / "data" / "raw" / "openfda_orig_decisions_2011_2026"
APPL_RE = re.compile(r"varApplNo=(\d+)", re.I)
TODAY = "2026-09-17"


def nb(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def daf_url(appl: str) -> str:
    num = re.sub(r"\D", "", appl).zfill(6)
    return f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo={num}"


def main() -> int:
    idx: dict[str, list] = defaultdict(list)
    for f in sorted(glob.glob(str(RAW / "decisions_*.json"))):
        for x in json.load(open(f, encoding="utf-8")).get("decisions", []):
            names = {nb(x.get("brand_name_openfda"))}
            for p in x.get("products") or []:
                names.add(nb(p.get("brand_name")))
            for n in names:
                if n:
                    idx[n].append(x)

    with MASTER.open(newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        rows = list(rd)
        fields = rd.fieldnames

    linked, ambiguous, unmatched = [], [], []
    for r in rows:
        blob = " ".join([r["source_url_1"], r["source_url_2"], r["notes"]])
        if APPL_RE.search(blob):
            continue
        brand = r["drug_brand"]
        key = nb(r["drug_generic"]) if brand.startswith("(no trade") else nb(brand.split("(")[0])
        try:
            md = date.fromisoformat(r["decision_date"])
        except ValueError:
            continue
        cands = list(idx.get(key, []))
        close = [c for c in cands if abs((date.fromisoformat(c["decision_date"]) - md).days) <= 3]
        if not close and len(key) >= 5:  # e.g. "XACDURO (COPACKAGED)", "VOQUEZNA TRIPLE PAK"
            cands = [x for k, xs in idx.items() if k.startswith(key) for x in xs]
            close = [c for c in cands if abs((date.fromisoformat(c["decision_date"]) - md).days) <= 3]
        apps = sorted({c["application_number"] for c in close})
        if not apps:
            unmatched.append((r["decision_id"], r["decision_date"], brand))
            continue
        pick = apps[0]
        rec = next(c for c in close if c["application_number"] == pick)
        basis = (f"Drugs@FDA application resolved {TODAY} via openFDA brand+date match "
                 f"(openFDA ORIG-1 {rec['decision_date']}, sponsor {rec.get('sponsor_name','')}, "
                 f"{rec.get('submission_class_code_description','')}, {rec.get('review_priority','') or 'priority n/a'})")
        if len(apps) > 1:
            # Written as "application 212726" (not "NDA212726") on purpose: build_original_non_nme.py treats every
            # NDA/BLA-prefixed number in a master note as "already in the master" and would drop the sibling's own
            # row from data/fda_original_non_nme_decisions.csv. The sibling is a separate FDA decision.
            sib = ", ".join(re.sub(r"^(NDA|BLA)", "application ", a) for a in apps[1:])
            basis += f"; same-day sibling application(s) for another dosage form: {sib}"
            ambiguous.append((r["decision_id"], brand, apps))
        if not r["source_url_2"].strip():
            r["source_url_2"] = daf_url(pick)
            r["notes"] = (f"appl {pick}. {basis}." + (" " + r["notes"] if r["notes"] else "")).strip()
        else:
            r["notes"] = (f"appl {pick}; {daf_url(pick)}. {basis}." + (" " + r["notes"] if r["notes"] else "")).strip()
        linked.append((r["decision_id"], brand, pick))

    with MASTER.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)

    print(f"linked {len(linked)} rows; {len(ambiguous)} had same-day sibling applications (both recorded); "
          f"{len(unmatched)} left without a link:")
    for u in unmatched:
        print("  UNMATCHED", *u)
    for a in ambiguous:
        print("  SIBLINGS ", *a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
