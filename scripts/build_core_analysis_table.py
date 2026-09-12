# -*- coding: utf-8 -*-
"""
Builds data/core_analysis_table.csv - the primary user-facing analysis table
joining: company, drug/trial, FDA decision, stock price reaction, and the
company's tracked success-rate summary pulled from company_scorecards.csv.

Columns answer the brief directly:
  company / ticker / drug / recent clinical indication
  decision_type + decision_date   -> the FDA decision
  stock_price_before / after / pct_change -> price reaction on the decision day
  price_t1 / pct_change_t1        -> price reaction by the next trading day,
                                     which is often where the real move lands
                                     (e.g. Celcuity +7.0% on the day then
                                     -17.6% the next session)
  company_success_rate_summary    -> the company's tracked hit rate
  flags                           -> rows that need manual review

Fix applied 2026-09-12: the CRL loop previously looked the price snapshot up
with `d["decision_date"]` (the last APPROVAL row's date) instead of
`c["crl_date"]`, so every CRL row matched the wrong snapshot or none at all.
"""
import csv

decisions = list(csv.DictReader(open("data/fda_decisions_master.csv")))
crls = list(csv.DictReader(open("data/fda_crl_master.csv")))
snapshots = {(r["ticker"], r["decision_date"]): r
             for r in csv.DictReader(open("data/stock_price_snapshots.csv"))}
scorecards = {r["ticker"]: r for r in csv.DictReader(open("data/company_scorecards.csv"))}

HEADER = ["company_name", "ticker", "drug_name", "decision_type", "decision_date",
          "indication", "review_pathway",
          "stock_price_before", "stock_price_after", "pct_change",
          "price_t1", "pct_change_t1",
          "price_data_status", "company_success_rate_summary",
          "fda_source_url", "secondary_source_url", "flags", "verification_status"]


def flag_of(verification_status, notes):
    flags = []
    vs = (verification_status or "").lower()
    n = (notes or "").lower()
    if "flagged" in vs:
        flags.append("IRREGULARITY")
    if "ownership change" in n or "current holder" in n:
        flags.append("OWNERSHIP-CHANGE")
    if "withdraw" in n:
        flags.append("WITHDRAWN")
    if "incomplete" in vs or "unavailable" in vs:
        flags.append("PRICE-GAP")
    return "; ".join(dict.fromkeys(flags))


def summary_for(ticker):
    sc = scorecards.get(ticker)
    if not sc:
        return "Not yet built - scorecard pending"
    return ("{}/{} tracked programs approved; {} advancing; {} paused/on hold; {} CRL(s)".format(
        sc["approved_count"], sc["total_pipeline_programs_tracked"],
        sc["advanced_to_next_phase_count"], sc["paused_or_clinical_hold_count"],
        sc["crl_rejected_count"]))


def price_cells(snap, ticker):
    """Returns before, after, pct, t1, t1_pct, status for a matched snapshot."""
    if not snap:
        if ticker in ("NO_TICKER", ""):
            return "", "", "", "", "", "No public ticker"
        return "", "", "", "", "", "Not yet matched to price snapshot"
    before = snap.get("close_before", "")
    after = snap.get("close_on_or_after", "")
    pct = snap.get("pct_change_on_decision", "")
    t1 = snap.get("close_few_days_later", "")
    try:
        t1_pct = "{:.2f}".format(100.0 * (float(t1) / float(before) - 1.0)) if (t1 and before) else ""
    except (TypeError, ValueError, ZeroDivisionError):
        t1_pct = ""
    return before, after, pct, t1, t1_pct, snap.get("verification_status", "")


rows = []

for d in decisions:
    t = d["ticker"]
    snap = snapshots.get((t, d["decision_date"]))
    before, after, pct, t1, t1_pct, status = price_cells(snap, t)
    rows.append([
        d["company_name"], t, f"{d['drug_brand']} ({d['drug_generic']})",
        d["decision_type"], d["decision_date"], d["indication"], d.get("review_pathway", ""),
        before, after, pct, t1, t1_pct, status, summary_for(t),
        d["source_url_1"], d.get("source_url_2", ""),
        flag_of(d["verification_status"], d.get("notes", "")), d["verification_status"],
    ])

for c in crls:
    t = c["ticker"]
    snap = snapshots.get((t, c["crl_date"]))          # <- was d["decision_date"] (bug)
    before, after, pct, t1, t1_pct, status = price_cells(snap, t)
    rows.append([
        c["company_name"], t, c["drug_name"],
        "Complete Response Letter (Rejection)", c["crl_date"], c["indication"], "",
        before, after, pct, t1, t1_pct, status, summary_for(t),
        c["source_url_1"], c.get("source_url_2", ""),
        flag_of(c["verification_status"], c.get("notes", "")), c["verification_status"],
    ])

# newest decisions first - the table is used as a forward-looking decision engine
rows.sort(key=lambda r: r[4], reverse=True)

with open("data/core_analysis_table.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(HEADER)
    w.writerows(rows)

matched = sum(1 for r in rows if r[12] in ("Verified",))
print(f"Wrote {len(rows)} core analysis rows ({matched} with verified price data)")
