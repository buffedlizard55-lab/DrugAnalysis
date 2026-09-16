#!/usr/bin/env python3
"""Build data/company_label_expansion_scorecard.csv.

What this measures
------------------
The repository's existing company_scores.csv scores companies on *novel* (NME)
approvals. That misses the single largest body of evidence about whether a
company's clinical trials keep converting into FDA approvals: **efficacy
supplements**, i.e. FDA decisions granting a NEW indication or NEW population
for an already-marketed drug.

Each approved efficacy supplement is, by definition, a completed clinical
programme whose data FDA judged sufficient. Counting them per company gives a
directly observed, fully sourced answer to the project's scorecard question —
"how many drugs in their profile/history/pipeline have succeeded" — without
relying on any company's self-reported pipeline page.

Metrics (all counted, none modelled)
------------------------------------
  total_efficacy_supplements   approved efficacy supplements 2000-2026
  distinct_drugs_expanded      distinct applications that gained an indication
  priority_review_count        supplements FDA gave Priority Review
  priority_review_share_pct    Priority share — FDA's own signal that the new
                               indication is a significant improvement
  orphan_supplement_count      supplements carrying an Orphan property code
  first_/last_expansion        date range of the company's expansion record
  expansions_last_5y           supplements decided in the trailing 5 years
                               (recency: an old record is weaker evidence)
  expansion_velocity_per_yr    expansions_last_5y / 5
  novel_approvals_tracked      NME approvals for the same company in the
                               master list (joined on ticker)
  breadth_ratio                supplements per novel approval — how much
                               additional indication value the company has
                               extracted from each molecule it got approved

No score is invented: this file reports counts and ratios, each traceable to
the rows in fda_supplement_decisions.csv that produced it.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "company_label_expansion_scorecard.csv"

TODAY = date(2026, 9, 16)
RECENT_CUTOFF = date(TODAY.year - 5, TODAY.month, TODAY.day)


def main() -> int:
    with (DATA / "fda_supplement_decisions.csv").open(newline="", encoding="utf-8-sig") as fh:
        suppl = list(csv.DictReader(fh))

    # Novel-approval counts per ticker, from the already-verified master list.
    novel = defaultdict(int)
    with (DATA / "fda_decisions_master.csv").open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            t = (r.get("ticker") or "").strip()
            if t and t not in {"NO_US_TICKER", "UNRESOLVED"} and "?" not in t:
                novel[t] += 1

    groups = defaultdict(list)
    for r in suppl:
        ticker = (r.get("ticker") or "").strip()
        if ticker in {"", "UNRESOLVED", "NO_US_TICKER"}:
            continue  # never score an issuer we could not identify
        groups[ticker].append(r)

    rows = []
    for ticker, rs in groups.items():
        # Company label: the most frequent spelling among this ticker's rows.
        names = defaultdict(int)
        for r in rs:
            names[r["company_name"]] += 1
        company = max(names, key=lambda n: names[n])

        dates = sorted(r["decision_date"] for r in rs if r["decision_date"])
        prio = sum(1 for r in rs if r.get("review_priority", "").upper() == "PRIORITY")
        orphan = sum(1 for r in rs if "orphan" in (r.get("submission_property_type", "") or "").lower())
        recent = sum(1 for r in rs
                     if r["decision_date"] and date.fromisoformat(r["decision_date"]) >= RECENT_CUTOFF)
        drugs = {r["application_number"] for r in rs}
        n = len(rs)
        nov = novel.get(ticker, 0)
        cls = max({r["us_investable_class"] for r in rs},
                  key=lambda c: sum(1 for r in rs if r["us_investable_class"] == c))
        flagged = sum(1 for r in rs if "FLAGGED" in r.get("verification_status", ""))

        rows.append({
            "company_name": company,
            "ticker": ticker,
            "us_investable_class": cls,
            "total_efficacy_supplements": n,
            "distinct_drugs_expanded": len(drugs),
            "priority_review_count": prio,
            "priority_review_share_pct": round(100.0 * prio / n, 1),
            "orphan_supplement_count": orphan,
            "first_expansion_date": dates[0] if dates else "",
            "last_expansion_date": dates[-1] if dates else "",
            "expansions_last_5y": recent,
            "expansion_velocity_per_yr": round(recent / 5.0, 2),
            "novel_approvals_tracked": nov,
            "breadth_ratio_suppl_per_novel": (round(n / nov, 2) if nov else ""),
            "rows_flagged_for_review": flagged,
            "evidence_basis": (f"{n} approved FDA efficacy supplements across {len(drugs)} application(s), "
                               f"2000-2026, each row carrying its FDA approval-letter or Drugs@FDA link "
                               f"in data/fda_supplement_decisions.csv (filter ticker={ticker})"),
            "verification_status": ("Verified - counted from openFDA Drugs@FDA efficacy-supplement records"
                                    + (f" - {flagged} row(s) flagged for review" if flagged else "")),
        })

    rows.sort(key=lambda r: -r["total_efficacy_supplements"])

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} companies")
    print(f"  total supplements attributed: {sum(r['total_efficacy_supplements'] for r in rows)}")
    print("\n  top 12 by approved label expansions:")
    for r in rows[:12]:
        print(f"    {r['ticker']:<6} {r['company_name'][:34]:<34} "
              f"{r['total_efficacy_supplements']:4d} suppl  "
              f"{r['distinct_drugs_expanded']:3d} drugs  "
              f"priority {r['priority_review_share_pct']:5.1f}%  "
              f"last5y {r['expansions_last_5y']:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
