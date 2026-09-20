#!/usr/bin/env python3
"""
build_year_verification_crosswalk_v24.py — v24 session (2026-09-20)

Builds:
  data/year_verification_crosswalk_v24.csv
    Year-by-year comparison: our master + orig_non_nme combined vs openFDA raw decisions.
    Every entry cites its openFDA source query URL. Flags gaps for human review.

Reads:
  data/fda_decisions_master.csv
  data/fda_original_non_nme_decisions.csv
  data/raw/openfda_orig_decisions_1980_1984/*.json
  data/raw/openfda_orig_decisions_2011_2026/*.json
  data/staging/missing_openfda_entries.json

Source: openFDA Drugs@FDA API (api.fda.gov/drug/drugsfda.json) — public domain.
"""

import json, os, csv, re, sys
from collections import defaultdict

RAW_DIRS = [
    'data/raw/openfda_orig_decisions_1980_1984',
    'data/raw/openfda_orig_decisions_2011_2026',
]

def load_openfda_decisions():
    """Load all ORIG AP decisions from the committed openFDA payloads."""
    all_decisions = []
    for folder in RAW_DIRS:
        for f in sorted(os.listdir(folder)):
            if not f.endswith('.json') or f == 'manifest.json':
                continue
            fp = os.path.join(folder, f)
            with open(fp) as fh:
                d = json.load(fh)
            year = d.get('year', int(f.replace('decisions_','').replace('.json','')))
            endpoint = d.get('source_endpoint','')
            for dec in d.get('decisions', []):
                date = dec.get('decision_date','')
                appl = dec.get('application_number','')
                brand = dec.get('brand_name_openfda','')
                sponsor = dec.get('sponsor_name','')
                cls = dec.get('submission_class_code','')
                cls_desc = dec.get('submission_class_code_description','')
                priority = dec.get('review_priority','')
                generic = dec.get('generic_name_openfda','')
                source_url = dec.get('source_url_drugsatfda','')
                source_query = dec.get('source_query_url','')
                if date:
                    num = re.sub(r'^[A-Z]+0*', '', appl)
                    all_decisions.append({
                        'year': int(date[:4]),
                        'date': date,
                        'appl': appl,
                        'appl_norm': num,
                        'brand': brand,
                        'sponsor': sponsor,
                        'cls': cls,
                        'cls_desc': cls_desc,
                        'priority': priority,
                        'generic': generic,
                        'source_url': source_url,
                        'source_query': source_query,
                        'payload_year': year,
                    })
    return all_decisions

def load_our_entries():
    """Load our existing (date, appl_norm) pairs."""
    our_set = set()
    our_rows = []

    # Master
    with open('data/fda_decisions_master.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get('decision_date','')
            appl = ''
            for url_field in ['source_url_1', 'source_url_2']:
                url = row.get(url_field,'')
                if 'varApplNo=' in url:
                    appl = url.split('varApplNo=')[1].split('&')[0]
                    break
            if date and appl:
                norm = appl.lstrip('0')
                our_set.add((date, norm))
                our_rows.append({'date': date, 'appl_norm': norm, 'source': 'master'})

    # Original non-NME
    with open('data/fda_original_non_nme_decisions.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get('decision_date','')
            appl = row.get('application_number','')
            if date and appl:
                num = re.sub(r'^[A-Z]+0*', '', appl)
                if num:
                    our_set.add((date, num))
                    our_rows.append({'date': date, 'appl_norm': num, 'source': 'orig_non_nme'})

    return our_set, our_rows

def build_crosswalk(openfda_decisions, our_set, missing_entries):
    """Build year-by-year crosswalk."""
    # Group openFDA by year
    openfda_by_year = defaultdict(list)
    for d in openfda_decisions:
        openfda_by_year[d['year']].append(d)

    # Missing by year
    missing_by_year = defaultdict(list)
    for m in missing_entries:
        missing_by_year[m['year']].append(m)

    rows = []
    years = sorted(set(list(openfda_by_year.keys()) + [int(d[:4]) for d, a in our_set]))
    for yr in years:
        if yr < 1980 or yr > 2026:
            continue
        of_count = len(openfda_by_year.get(yr, []))
        # Recount our unique pairs for this year
        our_count = sum(1 for d, a in our_set if d[:4] == str(yr))
        miss_count = len(missing_by_year.get(yr, []))
        # After v24 expansion: gap = openfda - our_count (negative means we exceed openFDA)
        # Our files now INCLUDE the previously-missing entries
        gap = of_count - our_count

        # Type breakdown from openFDA
        type_counts = defaultdict(int)
        for d in openfda_by_year.get(yr, []):
            type_counts[d['cls']] += 1

        rows.append({
            'year': yr,
            'openfda_orig_ap_count': of_count,
            'our_coverage_count': our_count,
            'new_entries_added': miss_count,
            'remaining_gap': gap,
            'type_1_nme': type_counts.get('TYPE 1', 0),
            'type_1_4': type_counts.get('TYPE 1/4', 0),
            'type_2': type_counts.get('TYPE 2', 0),
            'type_3': type_counts.get('TYPE 3', 0),
            'type_4': type_counts.get('TYPE 4', 0),
            'type_5': type_counts.get('TYPE 5', 0),
            'type_6': type_counts.get('TYPE 6', 0),
            'type_7': type_counts.get('TYPE 7', 0),
            'type_8': type_counts.get('TYPE 8', 0),
            'type_9': type_counts.get('TYPE 9', 0),
            'type_10': type_counts.get('TYPE 10', 0),
            'efficacy': type_counts.get('EFFICACY', 0),
            'unknown': type_counts.get('UNKNOWN', type_counts.get('', 0)),
            'verification_status': 'VERIFIED' if gap == 0 else f'GAP {gap:+d} — flagged for review',
            'source': f'openFDA Drugs@FDA API (api.fda.gov/drug/drugsfda.json) payloads committed in data/raw/openfda_orig_decisions_*',
            'source_url': 'https://api.fda.gov/drug/drugsfda.json?search=submissions.submission_type:"ORIG"+AND+submissions.submission_status:"AP"&limit=1000',
        })

    return rows

def main():
    print('Loading openFDA decisions...')
    openfda = load_openfda_decisions()
    print(f'  {len(openfda)} total decisions from openFDA payloads')

    print('Loading our existing entries...')
    our_set, our_rows = load_our_entries()
    print(f'  {len(our_set)} unique (date, appl) pairs')

    print('Loading missing entries...')
    with open('data/staging/missing_openfda_entries.json') as f:
        missing = json.load(f)
    print(f'  {len(missing)} entries to add')

    print('Building crosswalk...')
    rows = build_crosswalk(openfda, our_set, missing)

    outpath = 'data/year_verification_crosswalk_v24.csv'
    fieldnames = [
        'year', 'openfda_orig_ap_count', 'our_coverage_count', 'new_entries_added',
        'remaining_gap', 'type_1_nme', 'type_1_4', 'type_2', 'type_3', 'type_4',
        'type_5', 'type_6', 'type_7', 'type_8', 'type_9', 'type_10', 'efficacy',
        'unknown', 'verification_status', 'source', 'source_url'
    ]
    with open(outpath, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f'Wrote {len(rows)} rows to {outpath}')

    # Summary
    total_of = sum(r['openfda_orig_ap_count'] for r in rows)
    total_our = sum(r['our_coverage_count'] for r in rows)
    total_new = sum(r['new_entries_added'] for r in rows)
    verified = sum(1 for r in rows if r['remaining_gap'] == 0)
    print(f'\nSummary 1980-2026:')
    print(f'  openFDA total: {total_of}')
    print(f'  Our coverage: {total_our}')
    print(f'  New entries: {total_new}')
    print(f'  Years fully verified: {verified}/{len(rows)}')
    gaps = [r for r in rows if r['remaining_gap'] != 0]
    if gaps:
        print(f'  Years with gaps:')
        for r in gaps:
            print(f'    {r["year"]}: gap={r["remaining_gap"]:+d}')

if __name__ == '__main__':
    main()
