#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append a dated note to the 4 master rows whose published class was wrong.

Builds nothing and changes no value: it only records, on the rows themselves,
that the core analysis table used to publish a class they do not have.

Cause (found 2026-09-18, v11): `build_core_analysis_table.py` treated the
ticker-column sentinel `NO_US_TICKER` as a real symbol. Fourteen rows carry that
sentinel and belong to eleven unrelated companies, so
  * `class_by_ticker["NO_US_TICKER"]` was seeded from the first such row (D345,
    Fresenius Kabi, NON-US LISTING ONLY) and applied to all 14, contradicting the
    master's own committed class on 4 of them - the rows noted here;
  * all 14 displayed Fresenius Kabi's pipeline card ("14/14 tracked programs
    approved") as their `company_success_rate_summary`;
  * 6 of them were denied their own name-keyed row in `company_scores.csv`.
The builder now excludes every TICKER_SENTINELS value, mirroring the convention
`build_company_scores.py` already had. Only the builder changed; no master value
was edited, so the master remains the source of truth.

Notes avoid the substrings that `flag_of()` and the validator's FLAG scan key on
("ownership change", "current holder", "withdraw", "FLAG") so this documentation
pass does not silently alter the published flags column or the warning count.
"""
import csv
from pathlib import Path

MASTER = Path(__file__).resolve().parents[1] / "data" / "fda_decisions_master.csv"
DATE = "2026-09-18"

ROWS = {
    "D425": ("Actelion Pharmaceuticals Ltd", "PRIVATE / NO EQUITY", ""),
    "D442": ("Allergan plc", "US-LISTED",
             " This closes the class half of the v10 irregularity note on this row; the deliberate "
             "decision NOT to assert a decision-date ticker for AGN stands unchanged."),
    "D452": ("Allergan plc", "US-LISTED",
             " This closes the class half of the v10 irregularity note on this row; the deliberate "
             "decision NOT to assert a decision-date ticker for AGN stands unchanged."),
    "D627": ("Forest Laboratories", "PRIVATE / NO EQUITY", ""),
}

TEMPLATE = (
    "core-table join correction {date} (v11): data/core_analysis_table.csv used to publish this row's "
    "us_investable_class as 'NON-US LISTING ONLY', a value this row does not have in the master. Cause: "
    "build_core_analysis_table.py treated the ticker-column sentinel 'NO_US_TICKER' as a real symbol, so "
    "class_by_ticker was seeded from the first row carrying it (D345 Fresenius Kabi, NON-US LISTING ONLY) "
    "and applied to all 14 rows sharing the sentinel - 11 unrelated companies. The builder now excludes "
    "every TICKER_SENTINELS value, mirroring the convention scripts/build_company_scores.py already had, "
    "so the core table publishes this row's own committed class '{cls}'. The same join was also displaying "
    "Fresenius Kabi's pipeline card ('14/14 tracked programs approved') as this row's "
    "company_success_rate_summary; that is corrected too. No master value was edited by this correction - "
    "the master stays the source of truth and its {co} class of '{cls}' is unchanged."
)


def main() -> None:
    rows = list(csv.DictReader(open(MASTER, newline="", encoding="utf-8-sig")))
    header = list(rows[0].keys())
    n = 0
    for r in rows:
        hit = ROWS.get(r["decision_id"])
        if not hit:
            continue
        co, cls, extra = hit
        assert r["us_investable_class"] == cls, (r["decision_id"], r["us_investable_class"], cls)
        note = TEMPLATE.format(date=DATE, cls=cls, co=co) + extra
        if "core-table join correction" in r["notes"]:
            print(f"  {r['decision_id']}: note already present, skipped")
            continue
        for bad in ("ownership change", "current holder", "withdraw", "FLAG"):
            assert bad not in note, f"note would trip flag_of()/the FLAG scan on {bad!r}"
        r["notes"] = r["notes"].rstrip(" |") + " | " + note
        n += 1
    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    print(f"master: dated correction notes appended to {n} rows (no values changed)")


if __name__ == "__main__":
    main()
