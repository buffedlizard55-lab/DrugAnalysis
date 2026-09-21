#!/usr/bin/env python3
"""
Build core decision engine table: company, recent clinical trial result, FDA decision, stock pricing after official release, and each company's score success rate.

This is the primary analysis table requested in the brief.
"""

import csv, os
from collections import defaultdict

# Load data
core_rows = []
with open('data/core_analysis_table.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        core_rows.append(row)

# Load clinical trial endpoints
trial_endpoints = {}
if os.path.exists('data/clinical_trial_endpoints.csv'):
    with open('data/clinical_trial_endpoints.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get('ticker','')
            if ticker:
                trial_endpoints[ticker] = row

# Load company detailed scorecard
detailed_scores = {}
if os.path.exists('data/company_success_rate_detailed_scorecard.csv'):
    with open('data/company_success_rate_detailed_scorecard.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get('ticker','')
            if ticker:
                detailed_scores[ticker] = row

# Load stock snapshots
snapshots = {}
if os.path.exists('data/stock_price_snapshots.csv'):
    with open('data/stock_price_snapshots.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get('ticker','')
            date = row.get('decision_date','')
            key = (ticker, date)
            snapshots[key] = row

# Build decision engine analysis table
analysis_rows = []
for row in core_rows:
    ticker = row.get('ticker','')
    company = row.get('company_name','')
    drug = row.get('drug_name','')
    decision_type = row.get('decision_type','')
    decision_date = row.get('decision_date','')
    indication = row.get('indication','')
    review_pathway = row.get('review_pathway','')
    
    # Recent clinical trial result - from trial_endpoints or from core
    trial_result = ''
    if ticker in trial_endpoints:
        te = trial_endpoints[ticker]
        trial_result = f"{te.get('drug','')} {te.get('indication','')} Phase {te.get('phase','')} endpoint {te.get('endpoint_type','')} expected {te.get('expected_date','')} status {te.get('status','')}"
    else:
        # Use indication as proxy for trial result
        trial_result = indication or f"{drug} - {decision_type}"
    
    # FDA decision
    fda_decision = f"{decision_type} on {decision_date} for {drug} ({indication[:80] if indication else 'No indication text - blank beats guessed'}) - Pathway: {review_pathway or 'Not stated'}"
    
    # Stock pricing after official release
    snap_key = (ticker, decision_date)
    snap = snapshots.get(snap_key, {})
    stock_before = snap.get('close_before','') or row.get('stock_price_before','') or ''
    stock_after = snap.get('close_on_or_after','') or row.get('stock_price_after','') or ''
    pct_change = snap.get('pct_change_on_decision','') or row.get('pct_change','') or ''
    price_t1 = snap.get('close_few_days_later','') or row.get('price_t1','') or ''
    pct_t1 = snap.get('pct_change_t1','') or row.get('pct_change_t1','') or ''
    
    stock_pricing = f"Before: {stock_before or 'N/A'} on {snap.get('date_before','') or 'N/A'} -> After: {stock_after or 'N/A'} on {snap.get('date_on_or_after','') or decision_date} ({pct_change or 'N/A'}%); T+1: {price_t1 or 'N/A'} ({pct_t1 or 'N/A'}%)"
    
    # Company score success rate
    detailed = detailed_scores.get(ticker, {})
    score = detailed.get('composite_score_0_100','') or row.get('company_score','') or ''
    grade = detailed.get('success_grade','') or row.get('company_score_grade','') or ''
    success_rate = detailed.get('success_rate_pct','') or detailed.get('fda_approval_rate_pct','') or ''
    total_drugs = detailed.get('total_drugs_in_profile','') or detailed.get('total_fda_decisions_tracked','') or ''
    approved = detailed.get('approved_drugs','') or ''
    phase3 = detailed.get('phase3_programs','') or ''
    paused = detailed.get('paused_or_hold','') or ''
    advanced = detailed.get('advanced_to_next_phase','') or ''
    
    score_summary = f"Score: {score or 'N/A'} Grade: {grade or 'N/A'} Success Rate: {success_rate or 'N/A'}% - Profile: {total_drugs or 'N/A'} total, {approved or 'N/A'} approved, {phase3 or '0'} Phase3, {paused or '0'} paused, {advanced or '0'} advanced"
    
    # Source links
    fda_url = row.get('fda_source_url','')
    secondary_url = row.get('secondary_source_url','')
    
    analysis_rows.append({
        'company_name': company,
        'ticker': ticker,
        'drug_name': drug,
        'recent_clinical_trial_result': trial_result,
        'fda_decision': fda_decision,
        'fda_decision_date': decision_date,
        'fda_decision_type': decision_type,
        'stock_pricing_before': stock_before,
        'stock_pricing_after': stock_after,
        'pct_change_on_decision': pct_change,
        'stock_price_t1': price_t1,
        'pct_change_t1': pct_t1,
        'stock_pricing_summary': stock_pricing,
        'company_success_rate_summary': score_summary,
        'company_score': score,
        'company_score_grade': grade,
        'company_success_rate_pct': success_rate,
        'total_drugs_in_profile': total_drugs,
        'approved_drugs': approved,
        'phase3_programs': phase3,
        'paused_or_hold': paused,
        'advanced_to_next_phase': advanced,
        'review_pathway': review_pathway,
        'indication': indication,
        'fda_source_url': fda_url,
        'secondary_source_url': secondary_url,
        'verification_status': row.get('verification_status',''),
        'us_investable_class': row.get('us_investable_class',''),
        'notes': f"Decision engine analysis row: {company} {drug} {decision_type} {decision_date}. Trial result: {trial_result[:100]}. Stock: {stock_pricing[:100]}. Score: {score_summary[:100]}. Sources: {fda_url} + {secondary_url}",
    })

# Sort by decision_date desc
analysis_rows.sort(key=lambda r: r['fda_decision_date'] or '', reverse=True)

# Write
fieldnames = ['company_name','ticker','drug_name','recent_clinical_trial_result','fda_decision','fda_decision_date','fda_decision_type','stock_pricing_before','stock_pricing_after','pct_change_on_decision','stock_price_t1','pct_change_t1','stock_pricing_summary','company_success_rate_summary','company_score','company_score_grade','company_success_rate_pct','total_drugs_in_profile','approved_drugs','phase3_programs','paused_or_hold','advanced_to_next_phase','review_pathway','indication','fda_source_url','secondary_source_url','verification_status','us_investable_class','notes']
with open('data/decision_engine_analysis_table.csv','w',newline='') as f:
    w=csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in analysis_rows:
        w.writerow(r)

print(f"Wrote {len(analysis_rows)} rows to decision_engine_analysis_table.csv")

# Also build a clean summary for the site
# Count by company
by_company = defaultdict(list)
for r in analysis_rows:
    by_company[r['company_name']].append(r)

print(f"Companies in analysis: {len(by_company)}")
