#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit the us_investable_class disagreements between the master and the core table.

Writes data/staging/core_class_disagreements.csv. It CHANGES NOTHING - it only
measures, so the 145-row baseline that validate_data.py section 7 pins can be
adjudicated ticker by ticker instead of guessed at.

Two different problems are separated, because they have different fixes:

  A. TICKER-INTERNALLY-INCONSISTENT (master vs master). The master itself
     assigns different us_investable_class values to different rows that share
     one ticker - e.g. some NVS rows say "US-LISTED (ADR)" and others
     "US-LISTED". build_core_analysis_table.py builds class_by_ticker with
     setdefault() in master order, so whichever row comes first wins for ALL of
     them and the rest are published contradicting their own committed class.
     Fix belongs in the master (one class per ticker, or a decision-date-aware
     model), and needs evidence per company.

  B. ROW-LEVEL vs TICKER-LEVEL (core vs master). The core row's class differs
     from its own master row's class. Every A-row is also a B-row; B additionally
     contains rows whose own class is the minority for their ticker.

Repo law respected: this script only reads and reports. It never writes to the
master, the core table or company_scores.
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "staging" / "core_class_disagreements.csv"


def rd(name):
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


master = rd("fda_decisions_master.csv")
core = rd("core_analysis_table.csv")

core_by_key = {}
for r in core:
    core_by_key.setdefault((r["company_name"], r["decision_date"], r["drug_name"]), r)

mkey = lambda r: (r["company_name"], r["decision_date"], f"{r['drug_brand']} ({r['drug_generic']})")

# A sentinel is not a security, so rows sharing one must NOT be grouped as if
# they were one ticker (that was the NO_US_TICKER bug fixed in the core builder
# on 2026-09-18). Mirrors TICKER_SENTINELS in both builders.
TICKER_SENTINELS = {"", "NO_TICKER", "NO_US_TICKER", "N/A", "NONE", "PRIVATE"}


def real_ticker(t):
    t = (t or "").strip()
    return "" if t in TICKER_SENTINELS else t

# class_by_ticker exactly as build_core_analysis_table.py builds it
class_by_ticker = {}
for r in master:
    t = real_ticker(r["ticker"])
    if t:
        class_by_ticker.setdefault(t, (r.get("us_investable_class") or "").strip())

# A: real tickers whose master rows disagree among themselves
per_ticker = defaultdict(Counter)
sentinel_rows = []
for r in master:
    t = real_ticker(r["ticker"])
    if t:
        per_ticker[t][(r.get("us_investable_class") or "").strip()] += 1
    elif (r["ticker"] or "").strip():
        sentinel_rows.append(r)
inconsistent = {t: c for t, c in per_ticker.items() if len(c) > 1}

rows_out = []
for r in master:
    k = mkey(r)
    c = core_by_key.get(k)
    if c is None:
        continue
    own = (r.get("us_investable_class") or "").strip()
    pub = (c.get("us_investable_class") or "").strip()
    if own == pub:
        continue
    t = real_ticker(r["ticker"])
    kinds = []
    if t in inconsistent:
        kinds.append("TICKER-INTERNALLY-INCONSISTENT")
    kinds.append("ROW-LEVEL-vs-TICKER-LEVEL")
    tick_counts = per_ticker.get(t) or Counter()
    tick_classes = " | ".join("%s:%d" % (k2, v2) for k2, v2 in sorted(tick_counts.items()))
    rows_out.append({
        "decision_id": r["decision_id"],
        "decision_date": r["decision_date"],
        "company_name": r["company_name"],
        "ticker": t,
        "drug": r["drug_brand"],
        "master_class": own,
        "core_published_class": pub,
        "ticker_level_class": class_by_ticker.get(t, ""),
        "rows_for_this_ticker": sum(tick_counts.values()),
        "classes_for_this_ticker": tick_classes,
        "problem": "+".join(kinds),
        "exchange": r["exchange"],
    })

rows_out.sort(key=lambda x: (x["problem"], x["ticker"], x["decision_date"]))
cols = list(rows_out[0].keys())
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows_out)

print(f"Wrote {len(rows_out)} disagreement rows to {OUT.relative_to(ROOT)}")
print(f"  tickers involved: {len({r['ticker'] for r in rows_out})}")
print(f"  A. tickers whose own master rows disagree among themselves: {len(inconsistent)}")
for t, c in sorted(inconsistent.items(), key=lambda kv: -sum(kv[1].values())):
    print(f"       {t:<14} {sum(c.values()):>3} rows  " + " | ".join(f"{k}:{v}" for k, v in sorted(c.items())))
print(f"  rows carrying a ticker sentinel (not grouped as tickers): {len(sentinel_rows)}")
print("  B. by problem kind:")
for k, v in Counter(r["problem"] for r in rows_out).most_common():
    print(f"       {v:>4}  {k}")
