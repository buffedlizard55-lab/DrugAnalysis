# -*- coding: utf-8 -*-
"""
Builds data/core_analysis_table.csv - the primary user-facing analysis table
joining: company, drug/trial, FDA decision, stock price reaction, and a
qualitative success-rate note pulled from company_scorecards.csv where
available. This is the "core analysis table" requested: company, recent
clinical trial result, FDA decision, stock price after FDA decision,
company's success-rate score for that outcome.
"""
import csv

decisions = list(csv.DictReader(open("data/fda_decisions_master.csv")))
crls = list(csv.DictReader(open("data/fda_crl_master.csv")))
snapshots = {r["ticker"]: r for r in csv.DictReader(open("data/stock_price_snapshots.csv"))}
scorecards = {r["ticker"]: r for r in csv.DictReader(open("data/company_scorecards.csv"))}

HEADER = ["company_name","ticker","drug_name","decision_type","decision_date",
          "indication","stock_price_before","stock_price_after","pct_change",
          "price_data_status","company_success_rate_summary","fda_source_url",
          "verification_status"]

rows = []

for d in decisions:
    t = d["ticker"]
    snap = snapshots.get(t)
    sc = scorecards.get(t)
    if snap and snap.get("decision_date") == d["decision_date"]:
        before = snap.get("close_before","")
        after = snap.get("close_on_or_after","")
        pct = snap.get("pct_change_on_decision","")
        status = snap.get("verification_status","")
    else:
        before = after = pct = ""
        status = "Not yet matched to price snapshot" if t not in ("NO_TICKER",) else "No public ticker"
    if sc:
        succ = f"{sc['approved_count']}/{sc['total_pipeline_programs_tracked']} tracked programs approved; {sc['advanced_to_next_phase_count']} advancing; {sc['paused_or_clinical_hold_count']} paused/on hold; {sc['crl_rejected_count']} CRL(s)"
    else:
        succ = "Not yet built - scorecard pending"
    rows.append([
        d["company_name"], t, f"{d['drug_brand']} ({d['drug_generic']})", d["decision_type"],
        d["decision_date"], d["indication"], before, after, pct, status, succ,
        d["source_url_1"], d["verification_status"]
    ])

for c in crls:
    t = c["ticker"]
    snap = snapshots.get(t)
    sc = scorecards.get(t)
    if snap and snap.get("decision_date") == c["crl_date"]:
        before = snap.get("close_before","")
        after = snap.get("close_on_or_after","")
        pct = snap.get("pct_change_on_decision","")
        status = snap.get("verification_status","")
    else:
        before = after = pct = ""
        status = "Not yet matched to price snapshot"
    if sc:
        succ = f"{sc['approved_count']}/{sc['total_pipeline_programs_tracked']} tracked programs approved; {sc['advanced_to_next_phase_count']} advancing; {sc['paused_or_clinical_hold_count']} paused/on hold; {sc['crl_rejected_count']} CRL(s)"
    else:
        succ = "Not yet built - scorecard pending"
    rows.append([
        c["company_name"], t, c["drug_name"], "Complete Response Letter (Rejection)",
        c["crl_date"], c["indication"], before, after, pct, status, succ,
        c["source_url_1"], c["verification_status"]
    ])

rows.sort(key=lambda r: r[4])

with open("data/core_analysis_table.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(HEADER)
    w.writerows(rows)

print(f"Wrote {len(rows)} core analysis rows")
