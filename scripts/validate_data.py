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

# ---- efficacy supplements (label expansions) -------------------------------
suppl = read("fda_supplement_decisions.csv")
seen_suppl = set()
for i, r in enumerate(suppl, 2):
    sid = r.get("supplement_id", "").strip()
    if not sid:
        errors.append(f"supplements:{i}: missing supplement_id")
    elif sid in seen_suppl:
        errors.append(f"supplements:{i}: duplicate supplement_id {sid}")
    else:
        seen_suppl.add(sid)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("decision_date", "")):
        errors.append(f"supplements:{i}: invalid ISO date {r.get('decision_date','')!r}")
    for k in ("approval_letter_url", "label_url", "source_url_drugsatfda"):
        check_url(r.get(k, ""), f"supplements:{i}:{k}")
    # Every row must cite at least one official FDA document or record.
    if not any(r.get(k, "").strip() for k in ("approval_letter_url", "label_url", "source_url_drugsatfda")):
        errors.append(f"supplements:{i}: no official FDA source link on row")
    if not r.get("verification_status", "").strip():
        errors.append(f"supplements:{i}: missing verification_status")
    if "FLAG" in r.get("verification_status", "").upper():
        warnings.append(f"supplements:{i} flagged for manual review ({r.get('supplement_id','')})")
    # A ticker must never be asserted without a resolution basis.
    tk = r.get("ticker", "").strip()
    if tk and tk not in {"UNRESOLVED", "NO_US_TICKER"} and not r.get("sponsor_resolution_basis", "").strip():
        errors.append(f"supplements:{i}: ticker {tk} asserted with no sponsor_resolution_basis")
unresolved = sum(1 for r in suppl if r.get("ticker", "").strip() == "UNRESOLVED")
if unresolved:
    warnings.append(f"supplements: {unresolved} row(s) have an unresolved sponsor — left unresolved, not guessed")

# ---- label-expansion scorecard ---------------------------------------------
exp = read("company_label_expansion_scorecard.csv")
suppl_by_ticker = {}
for r in suppl:
    t = r.get("ticker", "").strip()
    if t and t not in {"UNRESOLVED", "NO_US_TICKER"}:
        suppl_by_ticker[t] = suppl_by_ticker.get(t, 0) + 1
for i, r in enumerate(exp, 2):
    t = r.get("ticker", "").strip()
    try:
        n = int(r["total_efficacy_supplements"])
    except (ValueError, KeyError):
        errors.append(f"expansion_scorecard:{i}: non-numeric total_efficacy_supplements")
        continue
    # The scorecard must be a faithful count of the underlying rows — this
    # catches any drift between the two files.
    if suppl_by_ticker.get(t, 0) != n:
        errors.append(f"expansion_scorecard:{i}: {t} claims {n} supplements but "
                      f"fda_supplement_decisions.csv has {suppl_by_ticker.get(t, 0)}")
    try:
        share = float(r["priority_review_share_pct"])
        if not 0 <= share <= 100:
            errors.append(f"expansion_scorecard:{i}: priority_review_share_pct outside 0-100")
    except (ValueError, KeyError):
        errors.append(f"expansion_scorecard:{i}: non-numeric priority_review_share_pct")

# ---- verification cross-check ----------------------------------------------
audit = read("verification_crosscheck.csv")
VALID_STATUS = {"MATCH", "MATCH_DATE_ONLY", "MATCH_VIA_GENERIC", "DATE_DIFFERS_FROM_DRUGSFDA_1_3D",
                "NO_APPL_NUMBER", "NOT_IN_OPENFDA", "MISMATCH_DATE", "MISMATCH_BRAND"}
master_ids = {r.get("decision_id", "") for r in master}
for i, r in enumerate(audit, 2):
    st = r.get("crosscheck_status", "").strip()
    if st not in VALID_STATUS:
        errors.append(f"crosscheck:{i}: unknown status {st!r}")
    if r.get("decision_id", "") not in master_ids:
        errors.append(f"crosscheck:{i}: decision_id {r.get('decision_id','')!r} not in master list")
    if st.startswith("MISMATCH"):
        warnings.append(f"crosscheck:{i} {st} for {r.get('decision_id','')} "
                        f"({r.get('drug_brand','')}) — official sources disagree, needs human adjudication")
if len(audit) != len(master):
    errors.append(f"crosscheck: {len(audit)} audit rows for {len(master)} master rows — rerun "
                  f"scripts/crosscheck_master_vs_openfda.py")

print(f"Validated {len(master)} FDA novel-approval rows, {len(suppl)} efficacy-supplement rows, "
      f"{len(exp)} label-expansion scorecards, {len(audit)} cross-check rows, "
      f"{len(scores)} company scorecards, and {len(prices)} price snapshots.")
print(f"Warnings requiring manual review: {len(warnings)}")
for w in warnings[:12]: print("WARNING", w)
if len(warnings) > 12: print(f"WARNING ... {len(warnings)-12} more")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors: print("ERROR", e)
    sys.exit(1)
print("PASS: schema, IDs, dates, ranges, and source URL checks succeeded.")
