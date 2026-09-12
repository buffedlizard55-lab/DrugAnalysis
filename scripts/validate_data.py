#!/usr/bin/env python3
"""Deterministic QA gate for the published CSVs.

This does not infer missing facts. It only rejects malformed rows and reports
records that require human review, so new entries cannot silently enter the
published tables with guessed values.
"""
import csv, re, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
errors, warnings = [], []

def read(name):
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows: errors.append(f"{name}: no data rows")
    return rows

def check_url(value, label):
    if not value: return
    p = urlparse(value)
    if p.scheme not in {"http", "https"} or not p.netloc:
        errors.append(f"{label}: invalid URL {value!r}")

master = read("fda_decisions_master.csv")
required = {"company_name", "drug_brand", "decision_date", "source_url_1", "verification_status", "decision_id", "exchange"}
for i, r in enumerate(master, 2):
    missing = sorted(k for k in required if not r.get(k, "").strip())
    if missing:
        warnings.append(f"master:{i} missing required review field(s): {', '.join(missing)}")
    if r.get("decision_date", "") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["decision_date"]):
        errors.append(f"fda_decisions_master.csv:{i}: invalid ISO date {r['decision_date']!r}")
    for k in ("source_url_1", "source_url_2"): check_url(r.get(k, ""), f"master:{i}:{k}")
    if "FLAG" in r.get("verification_status", "").upper() or "FLAG" in r.get("notes", "").upper():
        warnings.append(f"master:{i} flagged for manual review ({r.get('decision_id','')})")
ids = [r.get("decision_id") for r in master]
for x in {x for x in ids if x}:
    if ids.count(x) > 1: warnings.append(f"master: duplicate decision_id {x} — deduplicate before refresh")

scores = read("company_scores.csv")
for i, r in enumerate(scores, 2):
    for k in ("total_score_0_100", "success_rate_pct"):
        try:
            n = float(r[k])
            if not 0 <= n <= 100: errors.append(f"company_scores.csv:{i}: {k} outside 0–100")
        except (ValueError, KeyError): errors.append(f"company_scores.csv:{i}: non-numeric {k}")

prices = read("stock_price_snapshots.csv")
for i, r in enumerate(prices, 2):
    check_url(r.get("source_url", ""), f"prices:{i}:source_url")
    if not r.get("verification_status", "").strip(): errors.append(f"prices:{i}: missing verification_status")

print(f"Validated {len(master)} FDA rows, {len(scores)} company scorecards, and {len(prices)} price snapshots.")
print(f"Warnings requiring manual review: {len(warnings)}")
for w in warnings[:12]: print("WARNING", w)
if len(warnings) > 12: print(f"WARNING ... {len(warnings)-12} more")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors: print("ERROR", e)
    sys.exit(1)
print("PASS: schema, IDs, dates, ranges, and source URL checks succeeded.")
