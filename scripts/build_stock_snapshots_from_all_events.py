#!/usr/bin/env python3
"""Ingest all pending Yahoo event captures into stock_price_snapshots.csv.

The fetch jobs remain the source of truth. This consumer only reads payloads
and manifests, applies the project's fixed trading-day bracket rule, and
preserves failed requests as explicit unavailable rows. It is idempotent on
(ticker, decision_date), so it can run after each Actions fetch batch.
"""
from __future__ import annotations
import csv, datetime as dt, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data/stock_price_snapshots.csv"
SOURCES = [
    (ROOT / "data/raw/stock_yahoo_events_remaining", ROOT / "fetch_jobs/stock_yahoo_events_remaining.json"),
    (ROOT / "data/raw/stock_yahoo_orig_remaining", ROOT / "fetch_jobs/stock_yahoo_orig_remaining.json"),
    (ROOT / "data/raw/stock_yahoo_suppl_remaining", ROOT / "fetch_jobs/stock_yahoo_suppl_remaining.json"),
]
HEADER = ["ticker", "company", "decision_date", "decision_type", "close_before", "date_before",
          "close_on_or_after", "date_on_or_after", "close_few_days_later", "date_few_days_later",
          "pct_change_on_decision", "source_url", "verification_status", "notes"]


def bars(payload):
    chart = payload.get("chart", {})
    if chart.get("error"): return [], str(chart["error"])
    result = (chart.get("result") or [None])[0]
    if not result: return [], "no result object"
    ts = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close")) or []
    return [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), c) for t, c in zip(ts, closes) if c is not None], ""


def bracket(data, decision):
    day = dt.date.fromisoformat(decision)
    before = [x for x in data if x[0] < day]
    after = [x for x in data if x[0] >= day]
    return (before[-1] if before else None, after[0] if after else None, after[1] if len(after) > 1 else None)


def main():
    existing_rows = list(csv.DictReader(SNAP.open(newline="", encoding="utf-8-sig")))
    existing = {(r["ticker"], r["decision_date"]) for r in existing_rows}
    additions = []
    for raw, job in SOURCES:
        if not (raw / "manifest.json").exists():
            continue
        manifest = json.loads((raw / "manifest.json").read_text())
        statuses = {x.get("id"): (x.get("status"), x.get("error", "")) for x in manifest.get("requests", [])}
        specs = json.loads(job.read_text())
        for spec in specs:
            for item in spec.get("items", []):
                key = (item.get("ticker", ""), item.get("decision_date", ""))
                if not key[0] or not key[1] or key in existing: continue
                path = raw / item["out"]
                status, err = statuses.get(item["id"], (None, ""))
                notes, verification = [], "Verified"
                cb = coa = later = None
                if path.exists():
                    status = 200 if status == "skipped-existing" else status
                if not path.exists() or status not in (None, 200, "200"):
                    verification = "Data unavailable - acquired/delisted or pre-Yahoo coverage"
                    notes.append(f"fetch status: {status or 'no file'} {err}".strip())
                else:
                    data, error = bars(json.loads(path.read_text()))
                    if error:
                        verification = "Data unavailable - Yahoo payload error"; notes.append(error)
                    else:
                        cb, coa, later = bracket(data, item["decision_date"])
                        if not cb: verification = "Data unavailable - no bar before decision date"; notes.append("no prior trading-day bar")
                        if coa and coa[0].isoformat() != item["decision_date"]:
                            verification = "Verified - approx window"; notes.append(f"next trading day used: {coa[0].isoformat()}")
                def val(x): return (f"{x[1]:.4f}".rstrip("0").rstrip("."), x[0].isoformat()) if x else ("", "")
                b, db = val(cb); o, do = val(coa); l, dl = val(later)
                pct = ""
                if b and o: pct = str(round((float(o) / float(b) - 1) * 100, 2))
                additions.append({"ticker": item["ticker"], "company": item.get("expected_company", ""),
                    "decision_date": item["decision_date"], "decision_type": item.get("decision_type", ""),
                    "close_before": b, "date_before": db, "close_on_or_after": o, "date_on_or_after": do,
                    "close_few_days_later": l, "date_few_days_later": dl, "pct_change_on_decision": pct,
                    "source_url": item["url"], "verification_status": verification, "notes": "; ".join(notes)})
                existing.add(key)
    if additions:
        rows = existing_rows + additions
        rows.sort(key=lambda r: (r["decision_date"], r["ticker"]), reverse=True)
        with SNAP.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=HEADER); w.writeheader(); w.writerows(rows)
    print(f"all-event stock ingestion: appended {len(additions)} rows; total {len(existing_rows) + len(additions)}")

if __name__ == "__main__": main()
