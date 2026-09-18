#!/usr/bin/env python3
"""Record the 2026-09-18 v16 Tambocor NDA018830 designation-conflict check.

The open human adjudication (NEXT_SESSION item 3a): master D1040 carries the
Compilation's review designation *Priority* while Drugs@FDA's submission
field says *STANDARD*. This script does NOT change either official value.
It appends a dated note recording today's verbatim re-check of both FDA
systems plus the exact URL of FDA's digitized 1985 ORIG-1 medical review,
so the remaining human task is narrowed to reading one identified primary
document. Idempotent: refuses to append twice.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "fda_decisions_master.csv"

NOTE = (
    " TAMBOCOR DESIGNATION CHECK (2026-09-18, v16): both FDA systems re-read verbatim. "
    "Drugs@FDA application-history page for NDA018830 (holder of record now ALVOGEN) records "
    "ORIG-1 Approval 10/31/1985, Submission Classification 'Type 1 - New Molecular Entity', "
    "Review Priority 'STANDARD', and links FDA's digitized 1985 medical review "
    "https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf "
    "(server returned HTTP 500 to the automated fetch on 2026-09-18; human should read that "
    "PDF for the contemporaneous rating - the 1985 scheme used DAE priority ratings, so a "
    "'1A'/'1B' style code there would corroborate the Compilation's Priority). FDA's "
    "Compilation (media/177921, 1985 section) still prints 'Priority'. Contemporaneous press "
    "check: NYT 1985-11-08 (https://www.nytimes.com/1985/11/08/us/drug-for-heart-rhythm-approved-for-us-sale.html) "
    "announces the approval (Oct 29 action date announced Nov 8) with NO review-designation "
    "statement. Both official FDA values are kept: review_pathway stays Priority (Compilation "
    "spine per COMPILATION_ONLY policy); the Drugs@FDA STANDARD stays recorded here for review. "
    "NOT harmonised by this project."
)


def main() -> int:
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames

    target = next(r for r in rows if r["decision_id"] == "D1040")
    if "TAMBOCOR DESIGNATION CHECK (2026-09-18" in (target.get("notes") or ""):
        print("already applied — idempotent no-op")
        return 0
    # Assert current state before touching anything.
    assert target["drug_brand"] == "Tambocor", target["drug_brand"]
    assert target["decision_date"] == "1985-10-31", target["decision_date"]
    assert target["review_pathway"] == "Priority", target["review_pathway"]
    assert "priority: STANDARD" in (target.get("notes") or "")

    target["notes"] = (target.get("notes") or "").rstrip() + NOTE

    with MASTER.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("appended dated designation-check note to D1040 (values unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
