#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v19 (2026-09-19): append one dated, additive adjudication note.

The archived CDER 2013 NME year table was re-read live in full (27 numbered
rows + the Simponi Aria correction footnote) and transcribed verbatim to
data/raw/source_captures_2026_09_19/fda_2013_nme_table_2026_09_19.json.  The
master's 27 rows for 2013 match CDER's posted 27 exactly (Brintellix/
Trintellix rename aside), so the crosswalk's 2013 PROJECT_SHORT_FLAGGED (-2)
verdict is an inter-FDA-source discrepancy (History Office series 29 vs
CDER's own posted list 27), not a project enumeration error.

This script appends that finding to the 2013 crosswalk evidence_note only.
No value changes; idempotent via the dated marker; asserts pre-existing text
before writing; records the run in data/staging/v19_annotation_report.json.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CROSS = DATA / "fda_official_series_crosswalk.csv"
REPORT = DATA / "staging" / "v19_annotation_report.json"

MARKER = "v19 (2026-09-19)"

ADDITION = (
    " v19 (2026-09-19): the archived CDER 2013 NME table was re-read live in full "
    "(capture 20140327204457; 27 numbered rows transcribed verbatim to "
    "data/raw/source_captures_2026_09_19/fda_2013_nme_table_2026_09_19.json) and the "
    "master's 27 rows for 2013 match the posted 27 exactly. The page carries the "
    "footnote '* Correction: Simponi Aria, posted on 7/18/2013 was removed from this "
    "list on 9/17/2013. The product was inadvertently posted on this site.' The -2 "
    "gap is therefore inter-FDA-source (History Office series 29 vs CDER posted list "
    "27), not a project enumeration error; Simponi Aria must NOT be added. Next "
    "source: the 2013 NDA/BLA calendar-year approvals page."
)


def main() -> int:
    with CROSS.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = list(reader)
    assert "evidence_note" in header, "crosswalk lost its evidence_note column"
    target = next(r for r in rows if r["year"] == "2013")
    assert target["verdict"] == "PROJECT_SHORT_FLAGGED", "2013 verdict drifted"
    assert target["delta_nme_comparable_vs_official"] == "-2", "2013 delta drifted"
    changed = False
    if MARKER not in (target["evidence_note"] or ""):
        target["evidence_note"] = (target["evidence_note"] or "") + ADDITION
        changed = True
    if changed:
        with CROSS.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps({"marker": MARKER, "changed_2013_note": changed,
                                  "target": "fda_official_series_crosswalk.csv year 2013"},
                                 indent=2) + "\n", encoding="utf-8")
    print(f"v19 annotation: {'appended' if changed else 'already present (no-op)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
