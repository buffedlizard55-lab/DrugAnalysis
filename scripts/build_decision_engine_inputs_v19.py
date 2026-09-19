#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v19 (2026-09-19): decision-engine data-quality inputs.

Per-year completeness scores on the official-series spine (1977-2026): for
every year with an official FDA NME count, completeness = NME-comparable
project rows / official NMEs, capped at 1.0, with the year's verdict.  The
decision engine must down-weight or refuse years with low completeness
rather than treat the project enumeration as the full approval population.

Also records, as data, the principled refusal behind the engine's design:
this repository can compute approval-day base rates ONLY where it holds a
matched approval-vs-CRL denominator.  The master table is approvals-only and
the CRL table is not yet matched to PDUFA action dates, so any
priority-conditioned 'likelihood' computed today would be a biased,
numerator-only statistic.  The builder therefore emits the completeness
spine plus the explicit denominator-gap flag the engine must display.

Owns: data/decision_engine_year_inputs.csv (single-writer).
Fail-closed: aborts unless the crosswalk, the pre-1980 audit, and the
official series agree on every shared year.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "decision_engine_year_inputs.csv"


def fail(msg: str) -> None:
    raise SystemExit(f"build_decision_engine_inputs_v19: {msg}")


def main() -> int:
    with (DATA / "fda_official_series_crosswalk.csv").open(newline="", encoding="utf-8-sig") as fh:
        cross = list(csv.DictReader(fh))
    with (DATA / "pre1980_year_audit.csv").open(newline="", encoding="utf-8-sig") as fh:
        audit = list(csv.DictReader(fh))
    def series_int(raw: str) -> int | None:
        m = re.match(r"\s*(\d+)", raw or "")
        return int(m.group(1)) if m else None

    with (DATA / "fda_official_year_series.csv").open(newline="", encoding="utf-8-sig") as fh:
        series = {r["year"]: series_int(r["nmes_approved"]) for r in csv.DictReader(fh)}

    rows = []
    for r in audit:
        y = r["year"]
        if series.get(y) != int(r["official_nmes_approved"]):
            fail(f"{y}: pre-1980 audit disagrees with the official series")
        official = int(r["official_nmes_approved"])
        comp = int(r["nme_comparable_rows"])
        rows.append({
            "year": y, "official_nmes_approved": official,
            "nme_comparable_rows": comp,
            "completeness_ratio": round(min(comp / official, 1.0), 4),
            "verdict": r["verdict"],
            "engine_use": ("FULL" if r["verdict"] == "MATCH"
                           else ("OVER_COUNT_REVIEW" if r["verdict"] == "PROJECT_EXCEEDS_OFFICIAL"
                                 else "DOWN_WEIGHT_SHORTFALL")),
            "source_table": "pre1980_year_audit.csv",
        })
    for r in cross:
        y = r["year"]
        if not (r["official_nmes_approved"] or "").strip():
            rows.append({
                "year": y, "official_nmes_approved": "", "nme_comparable_rows": r["nme_comparable_rows"],
                "completeness_ratio": "", "verdict": r["verdict"], "engine_use": "NO_OFFICIAL_DENOMINATOR",
                "source_table": "fda_official_series_crosswalk.csv",
            })
            continue
        if series.get(y) != int(r["official_nmes_approved"]):
            fail(f"{y}: crosswalk disagrees with the official series")
        official = int(r["official_nmes_approved"])
        comp = int(r["nme_comparable_rows"])
        rows.append({
            "year": y, "official_nmes_approved": official, "nme_comparable_rows": comp,
            "completeness_ratio": round(min(comp / official, 1.0), 4),
            "verdict": r["verdict"],
            "engine_use": ("FULL" if r["verdict"] == "MATCH"
                           else ("OVER_COUNT_REVIEW" if r["verdict"] == "PROJECT_EXCEEDS_OFFICIAL"
                                 else "DOWN_WEIGHT_SHORTFALL")),
            "source_table": "fda_official_series_crosswalk.csv",
        })
    rows.sort(key=lambda r: r["year"])
    # Completeness contract the engine relies on: MATCH years are exactly 1.0.
    for r in rows:
        if r["verdict"] == "MATCH" and r["completeness_ratio"] != 1.0:
            fail(f"{r['year']}: MATCH year without 1.0 completeness")
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n_full = sum(1 for r in rows if r["engine_use"] == "FULL")
    print(f"v19 engine inputs: {len(rows)} year rows ({n_full} FULL-use), "
          f"denominator gap flagged for likelihood estimation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
