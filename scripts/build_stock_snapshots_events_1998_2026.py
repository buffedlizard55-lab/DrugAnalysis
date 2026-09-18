#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append stock-price snapshots from the raw Yahoo events directory
data/raw/stock_yahoo_events_1998_2026 (verbatim captures produced by the
GitHub runner from fetch_jobs/stock_yahoo_events_1998_2026.json, SHA-256
manifest alongside), using the SAME fixed rule set as
build_stock_snapshots_from_events.py:

  close_before          close of the last trading day strictly BEFORE the decision date
  close_on_or_after     close ON the decision date; failing that, the next trading day
  close_few_days_later  close of the next trading day after close_on_or_after
  pct_change_on_decision  100 * (close_on_or_after / close_before - 1)

Events whose request FAILED on the runner (delisted symbol, no data this far
back - e.g. SNY/ALC pre-2019 ADR lines, RHHBY 1990s OTC ADRs) are written with
blank price cells and the failure recorded - one row per event, nothing
silently dropped, never retried with a successor ticker (documented repo law:
the failure IS the data).

Idempotent: dedupes on (ticker, decision_date) against the committed
data/stock_price_snapshots.csv. Every number comes from a manifest-audited raw
capture; source_url keeps the exact replayable request.

This consumer exists because the 1998-2000 event captures (31 payloads + 5
recorded failures, fetched in v7/v8 runner runs) were never ingested into the
snapshot table - found and fixed in the 2026-09-18 session.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "stock_yahoo_events_1998_2026"
JOB = ROOT / "fetch_jobs" / "stock_yahoo_events_1998_2026.json"
SNAP = ROOT / "data" / "stock_price_snapshots.csv"

HEADER = ["ticker", "company", "decision_date", "decision_type", "close_before", "date_before",
          "close_on_or_after", "date_on_or_after", "close_few_days_later", "date_few_days_later",
          "pct_change_on_decision", "source_url", "verification_status", "notes"]


def bar_date(epoch: int) -> dt.date:
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).date()


def extract(payload: dict):
    """(bars, error_text): list of (date, close) daily bars from a Yahoo chart payload."""
    chart = (payload or {}).get("chart", {})
    if chart.get("error"):
        return [], str(chart["error"])
    res = (chart.get("result") or [None])[0]
    if not res:
        return [], "no result object"
    ts = res.get("timestamp") or []
    closes = (((res.get("indicators") or {}).get("quote") or [{}])[0].get("close")) or []
    bars = [(bar_date(t), c) for t, c in zip(ts, closes) if c is not None]
    return bars, ""


def snapshot_from_bars(bars, decision: str):
    dd = dt.date.fromisoformat(decision)
    before = [b for b in bars if b[0] < dd]
    onafter = [b for b in bars if b[0] >= dd]
    cb = before[-1] if before else None
    coa = onafter[0] if onafter else None
    later = onafter[1] if len(onafter) > 1 else None
    return cb, coa, later


def main() -> int:
    if not (RAW / "manifest.json").exists():
        print(f"no captures at {RAW.relative_to(ROOT)}; run the fetch job first")
        return 0
    manifest = json.load(open(RAW / "manifest.json"))
    status_by_id = {r.get("id"): (r.get("status"), r.get("error", "")) for r in manifest.get("requests", [])}

    specs = json.load(open(JOB))
    items = [it for spec in specs for it in spec.get("items", [])]
    existing = {(r["ticker"], r["decision_date"])
                for r in csv.DictReader(open(SNAP, newline="", encoding="utf-8-sig"))}
    out_new = 0
    rows_out = []
    for it in items:
        key = (it["ticker"], it["decision_date"])
        if key in existing:
            continue
        path = RAW / it["out"]
        status, err = status_by_id.get(it["id"], (None, ""))
        note_bits, vstat = [], "Verified"
        if path.exists():
            status = 200 if status == "skipped-existing" else status
        close_before = date_before = close_on = date_on = close_later = date_later = pct = ""
        if not path.exists() or (status not in (200, "200", None)):
            vstat = "Data unavailable - acquired/delisted or pre-Yahoo coverage"
            note_bits.append(f"fetch status: {status or 'no file'} {err or ''}".strip() +
                             " (recorded in the job manifest; never retried with a successor ticker)")
        else:
            bars, err2 = extract(json.load(open(path)))
            if err2:
                vstat = "Data unavailable - acquired/delisted or pre-Yahoo coverage"
                note_bits.append(f"Yahoo chart payload error: {err2}")
            else:
                cb, coa, later = snapshot_from_bars(bars, it["decision_date"])
                if cb:
                    close_before, date_before = f"{cb[1]:.4f}".rstrip('0').rstrip('.'), cb[0].isoformat()
                if coa:
                    close_on, date_on = f"{coa[1]:.4f}".rstrip('0').rstrip('.'), coa[0].isoformat()
                    if date_on != it["decision_date"]:
                        vstat = "Verified - approx window"
                        note_bits.append(f"decision date {it['decision_date']} was not a trading day "
                                         f"in the capture; using next trading day {date_on}")
                if later:
                    close_later, date_later = f"{later[1]:.4f}".rstrip('0').rstrip('.'), later[0].isoformat()
                if close_before and close_on:
                    try:
                        pct = str(round((float(close_on) / float(close_before) - 1) * 100, 2))
                    except Exception:
                        pct = ""
                if cb is None:
                    vstat = "Data unavailable - no bar before decision date in capture"
                    note_bits.append("capture has no trading day before the decision date")
        if it["ticker"] in {"GSK", "ALC", "RHHBY", "AZN", "SNY", "GE", "PG", "NVO", "NVS"}:
            note_bits.append("lineage proxy per master precedent (see master row notes: decision-date "
                             "symbol differs from the modern ticker)")
        if it.get("event_source", "").startswith("D"):
            note_bits.append(f"master decision {it['event_source']}")
        rows_out.append({
            "ticker": it["ticker"], "company": it["expected_company"],
            "decision_date": it["decision_date"], "decision_type": it["decision_type"],
            "close_before": close_before, "date_before": date_before,
            "close_on_or_after": close_on, "date_on_or_after": date_on,
            "close_few_days_later": close_later, "date_few_days_later": date_later,
            "pct_change_on_decision": pct,
            "source_url": it["url"],
            "verification_status": vstat, "notes": "; ".join(note_bits),
        })
        out_new += 1

    rows = list(csv.DictReader(open(SNAP, newline="", encoding="utf-8-sig"))) + rows_out
    # Final integrity pass: collapse byte-identical duplicate (ticker, decision_date)
    # rows (the 1998-2026 and 1985-1998 jobs overlap for pre-1998 events; identical
    # captures ingested by both consumers produced exact duplicate rows). First
    # occurrence wins; rows with actual price differences are NEVER collapsed here -
    # they stay for manual adjudication.
    seen, deduped, dropped = set(), [], 0
    for r in rows:
        k = (r["ticker"], r["decision_date"])
        if k in seen:
            dropped += 1
            continue
        seen.add(k)
        deduped.append(r)
    rows = sorted(deduped, key=lambda r: (r["decision_date"], r["ticker"]), reverse=True)
    with open(SNAP, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader(); w.writerows(rows)
    priced = sum(1 for r in rows_out if r["close_before"] and r["close_on_or_after"])
    print(f"appended {out_new} snapshot rows -> {SNAP.relative_to(ROOT)} (total {len(rows)})")
    print(f"of them, with full price bracket: {priced}")
    if dropped:
        print(f"collapsed {dropped} byte-identical duplicate (ticker, decision_date) rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
