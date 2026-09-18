#!/usr/bin/env python3
"""Generate fetch_jobs/stock_yahoo_events_1985_1998.json

Enumerates the pre-1998 (and 2000-2003 CBER) master rows whose issuer is
US-investable (US-LISTED or US-LISTED (ADR)) with a bare A-Z ticker, and
writes one Yahoo chart-API request per event in exactly the format of
fetch_jobs/stock_yahoo_events_1998_2026.json, so the GitHub runner captures
the raw payloads verbatim into data/raw/stock_yahoo_events_1985_1998/ with a
SHA-256 manifest.

Notes on what this job deliberately includes:
  * Rows are decision-dated 1985-2003, i.e. BEFORE the 1998-2026 job. A
    bar-window of +/-12 days around the decision date is used (same as the
    1998-2026 job).
  * Tickers that no longer serve history (delisted) will fail on the runner;
    the failure is recorded in the manifest and never retried with a
    successor ticker (repo law).
  * Tickers that are modern proxies for a legacy lineage (GSK per the master
    precedent, ALC for Alcon, RHHBY for Roche) are included because the
    master precedent used them for the same-era 2000+ rows; their snapshot
    notes must repeat the lineage caveat.

Deterministic: re-running rewrites the same file.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "fda_decisions_master.csv"
OUT = ROOT / "fetch_jobs" / "stock_yahoo_events_1985_1998.json"

CLEAN_TICKER = re.compile(r"^[A-Z]{1,5}$")


def epoch(d: str) -> int:
    return int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())


def main() -> int:
    rows = csv.DictReader(open(MASTER, newline="", encoding="utf-8-sig"))
    items = []
    for r in rows:
        did = int(r["decision_id"][1:])
        if did < 1029 or did > 1437:  # the 1985-1997 + CBER 2000-2003 block
            continue
        cls = (r.get("us_investable_class") or "").strip()
        tk = (r.get("ticker") or "").strip()
        if not cls.startswith("US-LISTED") or not CLEAN_TICKER.match(tk):
            continue
        d = r["decision_date"]
        if not d or int(d[:4]) > 2003:
            continue
        p1 = epoch(dt.datetime.fromisoformat(d).date().__sub__(dt.timedelta(days=12)).isoformat())
        p2 = epoch((dt.datetime.fromisoformat(d).date() + dt.timedelta(days=13)).isoformat()) - 1
        items.append({
            "id": f"{tk}_{d}",
            "url": (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
                    f"?period1={p1}&period2={p2}&interval=1d&includePrePost=false"),
            "out": f"{tk}_{d}.json",
            "ticker": tk,
            "decision_date": d,
            "decision_type": r["decision_type"],
            "expected_company": r["company_name"],
            "source": "Yahoo Finance chart API",
            "event_source": r["decision_id"],
        })
    items.sort(key=lambda x: (x["decision_date"], x["ticker"]))
    spec = [{
        "type": "generic",
        "id": "yahoo_chart_events_1985_1998",
        "sleep": 0.6,
        "timeout": 60,
        "retries": 3,
        "skip_existing": True,
        "items": items,
    }]
    OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    from collections import Counter
    print(f"wrote {OUT.relative_to(ROOT)} with {len(items)} events")
    print("by ticker:", dict(Counter(i["ticker"] for i in items).most_common()))
    print("decision years:", min(i['decision_date'] for i in items), "..", max(i['decision_date'] for i in items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
