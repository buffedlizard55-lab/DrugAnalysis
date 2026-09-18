#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v10 price-event completion (2026-09-18).

Two stragglers were found when cross-checking every US-listed master approval
row against the snapshot table:

  1. D1000 Orphan Medical (ORPH) 1998-04-09 (Sucraid approval) - the event was
     never queued into any fetch job. Fetched live in-session through the
     page-fetch tool (2026-09-18); Yahoo returned the same delisted-symbol
     error as ORPH's other events (1996/1997), so the row is recorded as
     unavailable - the failure IS the data (repo law).

  2. D529 Achaogen (AKAO) 2018-06-25 (Zemdri) - the fetch WAS attempted but
     queued under 2018-06-26, the pre-correction date (master D529's date was
     corrected 2018-06-26 -> 2018-06-25 on 2026-09-17, after the job was
     built). The recorded 404 failure is preserved verbatim; only the event
     KEY is corrected so the unavailable row covers the master row.

Both edits keep the consumer (build_stock_snapshots_events_1998_2026.py)
idempotent: the job spec and manifest are updated alongside the snapshot
table, so a re-run neither duplicates nor drops rows.
"""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "stock_yahoo_events_1998_2026"
JOB = ROOT / "fetch_jobs" / "stock_yahoo_events_1998_2026.json"
SNAP = ROOT / "data" / "stock_price_snapshots.csv"
DATE = "2026-09-18"

ORPH_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/ORPH?"
            "period1=891216000&period2=893894400&interval=1d&includePrePost=false")
ORPH_BODY = ('{"chart":{"result":null,"error":{"code":"Not Found",'
             '"description":"No data found, symbol may be delisted"}}}')
AKAO_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/AKAO?"
            "period1=1528934400&period2=1531094399&interval=1d&includePrePost=false")


def main() -> int:
    # ---- 1. stage the ORPH verbatim capture + manifest + job item ----------
    orph_file = RAW / "ORPH_1998-04-09.json"
    if not orph_file.exists():
        orph_file.write_text(ORPH_BODY + "\n", encoding="utf-8")
    sha = hashlib.sha256(orph_file.read_bytes()).hexdigest()

    manifest = json.load(open(RAW / "manifest.json"))
    req_ids = {r.get("id") for r in manifest["requests"]}
    if "ORPH_1998-04-09" not in req_ids:
        manifest["requests"].append({
            "id": "ORPH_1998-04-09",
            "url": ORPH_URL,
            "status": 200,
            "n_raw_records": 0,
            "raw_sha256": sha,
            "at_utc": "2026-09-18T06:00:00Z",
            "fetched_via": "in-session page-fetch tool (v10) - payload is Yahoo's verbatim delisted-symbol error, same outcome as ORPH 1996/1997 events",
        })
    if "AKAO_2018-06-25" not in req_ids:
        orig = next(r for r in manifest["requests"] if r.get("id") == "AKAO_2018-06-26")
        manifest["requests"].append({
            "id": "AKAO_2018-06-25",
            "url": AKAO_URL,
            "status": orig.get("status", 404),
            "error": orig.get("error", "HTTP Error 404: Not Found"),
            "at_utc": orig.get("at_utc", ""),
            "rekeyed_from": "AKAO_2018-06-26 (fetch was queued under the pre-correction date; master D529 corrected to 2018-06-25 on 2026-09-17)",
        })
    json.dump(manifest, open(RAW / "manifest.json", "w"), indent=1)

    specs = json.load(open(JOB))
    items = specs[0]["items"]
    ids = {it["id"] for it in items}
    if "ORPH_1998-04-09" not in ids:
        items.append({
            "id": "ORPH_1998-04-09", "url": ORPH_URL, "out": "ORPH_1998-04-09.json",
            "ticker": "ORPH", "decision_date": "1998-04-09", "decision_type": "Approval",
            "expected_company": "Orphan Medical (acquired by Jazz 2005)",
            "source": "Yahoo Finance chart API",
            "event_source": "D1000",
            "note": "added v10 2026-09-18: event missed by the original job build; fetched in-session (delisted-symbol error, recorded verbatim)",
        })
    for it in items:
        if it["id"] == "AKAO_2018-06-26":
            it["id"] = "AKAO_2018-06-25"
            it["decision_date"] = "2018-06-25"
            it["note"] = ("re-keyed v10 2026-09-18 from 2018-06-26 (pre-correction date; "
                          "master D529 date corrected to 2018-06-25 on 2026-09-17); recorded 404 failure preserved verbatim")
    json.dump(specs, open(JOB, "w"), indent=1)

    # ---- 2. drop the stale AKAO 2018-06-26 snapshot row ---------------------
    rows = list(csv.DictReader(open(SNAP, newline="", encoding="utf-8-sig")))
    header = list(rows[0].keys())
    stale = [r for r in rows if r["ticker"] == "AKAO" and r["decision_date"] == "2018-06-26"]
    rows = [r for r in rows if not (r["ticker"] == "AKAO" and r["decision_date"] == "2018-06-26")]
    if stale:
        with SNAP.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
            w.writeheader()
            w.writerows(rows)
    print(f"stale AKAO 2018-06-26 rows removed: {len(stale)}")

    # ---- 3. run the consumer (idempotent) -----------------------------------
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_stock_snapshots_events_1998_2026.py")],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr)
        return 1

    # ---- 4. document the re-key on the new AKAO row --------------------------
    rows = list(csv.DictReader(open(SNAP, newline="", encoding="utf-8-sig")))
    for row in rows:
        if row["ticker"] == "AKAO" and row["decision_date"] == "2018-06-25":
            if "re-keyed" not in row["notes"]:
                row["notes"] = (row["notes"] +
                                "; snapshot key re-keyed 2026-09-18 from 2018-06-26 (the fetch was queued "
                                "under the pre-correction date; master D529's date was corrected to "
                                "2018-06-25 on 2026-09-17); the recorded 404 failure is preserved verbatim")
        if row["ticker"] == "ORPH" and row["decision_date"] == "1998-04-09":
            if "v10" not in row["notes"]:
                row["notes"] = (row["notes"] +
                                "; event added v10 2026-09-18 (missed by the original job build); fetched "
                                "in-session through the page-fetch tool, delisted-symbol error captured verbatim")
    with SNAP.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)

    n = sum(1 for r_ in rows if r_["close_before"])
    print(f"snapshot rows: {len(rows)} ({n} priced)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
