#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-2000 era analysis (1985-2000), built only from committed verified data.

One row per year, 1985-2000 (the audited 1996-2000 window carries the audit
verdict columns). Everything is counted or median-ed from committed files:

  data/fda_decisions_master.csv    - approvals, pathways, US-listed classes
  data/stock_price_snapshots.csv   - price reactions (decision-day close vs
                                     last close before; unadjusted Yahoo
                                     daily closes, manifest-audited captures)
  data/pre2000_year_audit.csv      - per-row audit verdicts (1996-2000)

No external data is fetched and nothing is inferred: years without priced
events report blanks, never guesses.
"""
import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

HEADER = ["year", "master_approvals", "priority", "standard", "with_accelerated_token",
          "distinct_companies", "us_listed_class", "formerly_us_class", "non_us_class",
          "private_class", "priced_events", "full_brackets",
          "median_pct_on_decision", "mean_pct_on_decision", "biggest_gainer", "biggest_gainer_pct",
          "biggest_loser", "biggest_loser_pct", "winners_gt_10pct", "losers_lt_10pct",
          "audit_rows", "audit_all_layers", "audit_flagged"]


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    master = list(csv.DictReader(open(DATA / "fda_decisions_master.csv", encoding="utf-8-sig")))
    snaps = list(csv.DictReader(open(DATA / "stock_price_snapshots.csv", encoding="utf-8-sig")))
    try:
        audit = list(csv.DictReader(open(DATA / "pre2000_year_audit.csv", encoding="utf-8-sig")))
    except FileNotFoundError:
        audit = []
    audit_by_year = Counter(r["audit_year"] for r in audit)
    audit_all = Counter(r["audit_year"] for r in audit if r["verdict"].startswith("VERIFIED"))
    audit_flag = Counter(r["audit_year"] for r in audit if r["review_flag"].strip())

    snaps_by_year = {}
    for s in snaps:
        snaps_by_year.setdefault(s["decision_date"][:4], []).append(s)

    out = []
    for year in [str(y) for y in range(1985, 2001)]:
        rows = [r for r in master if r["decision_date"][:4] == year]
        pw = Counter(r["review_pathway"] for r in rows)
        cls = Counter(r["us_investable_class"] for r in rows)
        ss = snaps_by_year.get(year, [])
        pcts = [(s, f(s["pct_change_on_decision"])) for s in ss]
        pcts = [(s, p) for s, p in pcts if p is not None]
        vals = [p for _, p in pcts]
        row = {
            "year": year,
            "master_approvals": len(rows),
            "priority": sum(v for k, v in pw.items() if k.startswith("Priority")),
            "standard": sum(v for k, v in pw.items() if k.startswith("Standard")),
            "with_accelerated_token": sum(1 for r in rows if "accelerated" in r["review_pathway"].lower()),
            "distinct_companies": len({r["company_name"] for r in rows}),
            "us_listed_class": sum(v for k, v in cls.items() if k in ("US-LISTED", "US-LISTED (ADR)")),
            "formerly_us_class": cls.get("FORMERLY US-LISTED (DELISTED/ACQUIRED)", 0),
            "non_us_class": cls.get("NON-US LISTING ONLY", 0),
            "private_class": cls.get("PRIVATE / NO EQUITY", 0) + cls.get("NOT US-INVESTABLE (UNVERIFIED)", 0),
            "priced_events": len(vals),
            "full_brackets": sum(1 for s in ss if s["close_before"] and s["close_on_or_after"]),
            "median_pct_on_decision": f"{statistics.median(vals):.2f}" if vals else "",
            "mean_pct_on_decision": f"{statistics.fmean(vals):.2f}" if vals else "",
            "biggest_gainer": max(pcts, key=lambda t: t[1])[0]["ticker"] if pcts else "",
            "biggest_gainer_pct": f"{max(pcts, key=lambda t: t[1])[1]:.2f}" if pcts else "",
            "biggest_loser": min(pcts, key=lambda t: t[1])[0]["ticker"] if pcts else "",
            "biggest_loser_pct": f"{min(pcts, key=lambda t: t[1])[1]:.2f}" if pcts else "",
            "winners_gt_10pct": sum(1 for p in vals if p > 10),
            "losers_lt_10pct": sum(1 for p in vals if p < -10),
            "audit_rows": audit_by_year.get(year, ""),
            "audit_all_layers": audit_all.get(year, ""),
            "audit_flagged": audit_flag.get(year, ""),
        }
        out.append(row)
        print(f"{year}: n={row['master_approvals']:>3} priority={row['priority']:>3} standard={row['standard']:>3} "
              f"priced={row['priced_events']:>3} median={row['median_pct_on_decision'] or '-':>7} "
              f"gainer={row['biggest_gainer']}{row['biggest_gainer_pct']}% loser={row['biggest_loser']}{row['biggest_loser_pct']}%")

    with (DATA / "pre2000_era_analysis.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(out)
    print("wrote data/pre2000_era_analysis.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
