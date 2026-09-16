#!/usr/bin/env python3
"""Build data/company_original_approval_scorecard.csv

Counts, per listed issuer, the original non-NME FDA approvals published in
data/fda_original_non_nme_decisions.csv. Split by chemical type so a Type 5
new-manufacturer filing is never scored as if it were a Type 3 new dosage
form or a Type 4 new combination.

Nothing is modelled. Every number is a count of rows that already carry an
official Drugs@FDA link.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "company_original_approval_scorecard.csv"
TODAY = date(2026, 9, 16)
RECENT_CUTOFF = date(TODAY.year - 5, TODAY.month, TODAY.day)

GROUP_COLS = [
    ("n_type2_new_active", "Type 2 — New active ingredient"),
    ("n_type3_new_dosage", "Type 3 — New dosage form"),
    ("n_type4_new_combination", "Type 4 — New combination"),
    ("n_type5_formulation_or_manufacturer", "Type 5 — New formulation or manufacturer"),
    ("n_new_indication_original", "New indication filed as distinct original"),
    ("n_biosimilar_or_unpublished_bla", None),  # special
    ("n_medical_gas", "Medical gas"),
    ("n_other", None),
]


def main() -> int:
    with (DATA / "fda_original_non_nme_decisions.csv").open(newline="", encoding="utf-8-sig") as fh:
        orig = list(csv.DictReader(fh))

    novel = defaultdict(int)
    with (DATA / "fda_decisions_master.csv").open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            t = (r.get("ticker") or "").strip()
            if t and t not in {"NO_US_TICKER", "UNRESOLVED"} and "?" not in t:
                novel[t] += 1

    groups = defaultdict(list)
    for r in orig:
        ticker = (r.get("ticker") or "").strip()
        if ticker in {"", "UNRESOLVED", "NO_US_TICKER"}:
            continue
        groups[ticker].append(r)

    rows = []
    for ticker, rs in groups.items():
        names = defaultdict(int)
        for r in rs:
            names[r["company_name"]] += 1
        company = max(names, key=lambda n: names[n])
        dates = sorted(r["decision_date"] for r in rs if r["decision_date"])
        prio = sum(1 for r in rs if (r.get("review_priority") or "").upper() == "PRIORITY")
        recent = sum(
            1 for r in rs
            if r["decision_date"] and date.fromisoformat(r["decision_date"]) >= RECENT_CUTOFF
        )
        drugs = {r["application_number"] for r in rs}
        n = len(rs)
        nov = novel.get(ticker, 0)
        cls = max(
            {r["us_investable_class"] for r in rs},
            key=lambda c: sum(1 for r in rs if r["us_investable_class"] == c),
        )
        flagged = sum(1 for r in rs if "FLAGGED" in (r.get("verification_status") or ""))

        def count_group(prefix: str = None, exact: str = None, contains: tuple = ()):
            c = 0
            for r in rs:
                g = r.get("chemical_type_group") or ""
                if exact and g == exact:
                    c += 1
                elif prefix and g.startswith(prefix):
                    c += 1
                elif contains and any(s in g for s in contains):
                    c += 1
            return c

        n2 = count_group(prefix="Type 2")
        n3 = count_group(prefix="Type 3")
        n4 = count_group(prefix="Type 4")
        n5 = count_group(prefix="Type 5")
        nind = count_group(prefix="New indication")
        nbio = count_group(contains=("Biosimilar", "possible biosimilar", "BLA — class"))
        ngas = count_group(exact="Medical gas")
        accounted = n2 + n3 + n4 + n5 + nind + nbio + ngas
        nother = max(0, n - accounted)
        # Clinical-relevant originals: Type 2/3/4 + new-indication originals.
        # Type 5 manufacturer changes and medical gases are excluded from this
        # numerator on purpose — they are not clinical-trial conversions.
        clinical = n2 + n3 + n4 + nind

        rows.append({
            "company_name": company,
            "ticker": ticker,
            "us_investable_class": cls,
            "total_original_non_nme": n,
            "distinct_applications": len(drugs),
            "n_type2_new_active": n2,
            "n_type3_new_dosage": n3,
            "n_type4_new_combination": n4,
            "n_type5_formulation_or_manufacturer": n5,
            "n_new_indication_original": nind,
            "n_biosimilar_or_unpublished_bla": nbio,
            "n_medical_gas": ngas,
            "n_other": nother,
            "clinical_relevant_count": clinical,
            "priority_review_count": prio,
            "priority_review_share_pct": round(100.0 * prio / n, 1),
            "first_orig_date": dates[0] if dates else "",
            "last_orig_date": dates[-1] if dates else "",
            "orig_last_5y": recent,
            "orig_velocity_per_yr": round(recent / 5.0, 2),
            "novel_approvals_tracked": nov,
            "rows_flagged_for_review": flagged,
            "evidence_basis": (
                f"{n} original non-NME FDA approvals across {len(drugs)} application(s), "
                f"2000-2026; clinical-relevant (Type 2/3/4 + new-indication originals) = {clinical}. "
                f"Each row in data/fda_original_non_nme_decisions.csv (filter ticker={ticker}) "
                f"links Drugs@FDA."
            ),
            "verification_status": (
                "Verified - counted from openFDA Drugs@FDA ORIG/AP records"
                + (f" - {flagged} row(s) flagged for review" if flagged else "")
            ),
        })

    rows.sort(key=lambda r: (-r["clinical_relevant_count"], -r["total_original_non_nme"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} companies")
    print(f"  total originals attributed: {sum(r['total_original_non_nme'] for r in rows)}")
    print(f"  clinical-relevant attributed: {sum(r['clinical_relevant_count'] for r in rows)}")
    print("\n  top 12 by clinical-relevant originals (Type 2/3/4 + new-indication):")
    for r in rows[:12]:
        print(f"    {r['ticker']:<8} {r['company_name'][:32]:<32} "
              f"clin {r['clinical_relevant_count']:3d}  total {r['total_original_non_nme']:3d}  "
              f"T3 {r['n_type3_new_dosage']:3d}  T5 {r['n_type5_formulation_or_manufacturer']:3d}  "
              f"last5y {r['orig_last_5y']:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
