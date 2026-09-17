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

# ---- original non-NME NDA/BLA approvals ------------------------------------
orig = read("fda_original_non_nme_decisions.csv")
seen_orig = set()
for i, r in enumerate(orig, 2):
    oid = r.get("orig_id", "").strip()
    if not oid:
        errors.append(f"orig:{i}: missing orig_id")
    elif oid in seen_orig:
        errors.append(f"orig:{i}: duplicate orig_id {oid}")
    else:
        seen_orig.add(oid)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("decision_date", "")):
        errors.append(f"orig:{i}: invalid ISO date {r.get('decision_date','')!r}")
    for k in ("source_url_1", "source_url_2"):
        check_url(r.get(k, ""), f"orig:{i}:{k}")
    if not any(r.get(k, "").strip() for k in ("source_url_1", "source_url_2", "source_query_url")):
        errors.append(f"orig:{i}: no official FDA source link on row")
    if not r.get("verification_status", "").strip():
        errors.append(f"orig:{i}: missing verification_status")
    # Type 1 NMEs must never leak into this file — they belong on the master list.
    desc = r.get("chemical_type_description", "")
    if "Type 1 - New Molecular Entity" in desc:
        errors.append(f"orig:{i}: Type 1 NME leaked into non-NME file ({oid})")
    tk = r.get("ticker", "").strip()
    if tk and tk not in {"UNRESOLVED", "NO_US_TICKER"} and not r.get("sponsor_resolution_basis", "").strip():
        errors.append(f"orig:{i}: ticker {tk} asserted with no sponsor_resolution_basis")
    if "FLAG" in r.get("verification_status", "").upper():
        warnings.append(f"orig:{i} flagged for manual review ({oid})")
orig_unresolved = sum(1 for r in orig if r.get("ticker", "").strip() == "UNRESOLVED")
if orig_unresolved:
    warnings.append(f"orig: {orig_unresolved} row(s) have an unresolved sponsor — left unresolved, not guessed")
# Every year 2000-2026 must be represented (coverage claim).
orig_years = {r.get("decision_date", "")[:4] for r in orig}
missing_years = [str(y) for y in range(2000, 2027) if str(y) not in orig_years]
if missing_years:
    errors.append(f"orig: missing years {', '.join(missing_years)} — coverage claim broken")

# ---- original-approval scorecard -------------------------------------------
oscores = read("company_original_approval_scorecard.csv")
orig_by_ticker = {}
for r in orig:
    t = r.get("ticker", "").strip()
    if t and t not in {"UNRESOLVED", "NO_US_TICKER"}:
        orig_by_ticker[t] = orig_by_ticker.get(t, 0) + 1
for i, r in enumerate(oscores, 2):
    t = r.get("ticker", "").strip()
    try:
        n = int(r["total_original_non_nme"])
    except (ValueError, KeyError):
        errors.append(f"orig_scorecard:{i}: non-numeric total_original_non_nme")
        continue
    if orig_by_ticker.get(t, 0) != n:
        errors.append(f"orig_scorecard:{i}: {t} claims {n} originals but "
                      f"fda_original_non_nme_decisions.csv has {orig_by_ticker.get(t, 0)}")
    try:
        share = float(r["priority_review_share_pct"])
        if not 0 <= share <= 100:
            errors.append(f"orig_scorecard:{i}: priority_review_share_pct outside 0-100")
    except (ValueError, KeyError):
        errors.append(f"orig_scorecard:{i}: non-numeric priority_review_share_pct")
    try:
        clin = int(r["clinical_relevant_count"])
        if clin > n:
            errors.append(f"orig_scorecard:{i}: clinical_relevant_count {clin} > total {n}")
    except (ValueError, KeyError):
        errors.append(f"orig_scorecard:{i}: non-numeric clinical_relevant_count")

# ---- Type 1 unmatched (flagged, not merged) --------------------------------
t1gap = read("fda_type1_not_in_nme_master.csv")
for i, r in enumerate(t1gap, 2):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("decision_date", "")):
        errors.append(f"t1gap:{i}: invalid ISO date {r.get('decision_date','')!r}")
    check_url(r.get("source_url_1", ""), f"t1gap:{i}:source_url_1")
    if "FLAGGED" not in (r.get("verification_status") or "").upper():
        errors.append(f"t1gap:{i}: Type 1 unmatched row is not flagged — must not look like a merged NME")
warnings.append(f"t1gap: {len(t1gap)} Type 1 openFDA rows not matched to the NME master — flagged, not merged")

# ---- orig year register ----------------------------------------------------
yreg = read("fda_orig_year_register.csv")
if len(yreg) != 27:
    errors.append(f"orig_year_register: {len(yreg)} rows, expected 27 (2000-2026)")
published_sum = sum(int(r.get("non_nme_published") or 0) for r in yreg)
if published_sum != len(orig):
    errors.append(f"orig_year_register: sum(non_nme_published)={published_sum} != {len(orig)} orig rows")

# ---- CRL master (expanded 2026-09-17: 58 hand-verified + 400 from openFDA CRL API)
crl = read("fda_crl_master.csv")
if len(crl) < 458:
    errors.append(f"crl: {len(crl)} rows, expected >= 458 (58 hand-verified + 400 openFDA)")
crl_ids = [r.get("crl_id") for r in crl]
for x in {x for x in crl_ids if x}:
    if crl_ids.count(x) > 1:
        errors.append(f"crl: duplicate crl_id {x}")
for i, r in enumerate(crl, 2):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("crl_date", "")):
        errors.append(f"crl:{i}: invalid ISO crl_date {r.get('crl_date','')!r}")
    if not (2000 <= int(r["crl_date"][:4] or 0) <= 2026):
        errors.append(f"crl:{i}: crl_date outside 2000-2026")
    for k in ("source_url_1", "source_url_2"):
        if not r.get(k, "").strip():
            errors.append(f"crl:{i}: missing {k}")
        check_url(r.get(k, ""), f"crl:{i}:{k}")
    if not r.get("company_name", "").strip():
        errors.append(f"crl:{i}: blank company_name")
new_crl = [r for r in crl if r.get("crl_id", "").startswith("CR-")]
if any(not r.get("stock_reaction") for r in new_crl):
    pass  # blank price reaction is allowed and expected (blank beats guessed)
if any(r.get("ticker") and r.get("verification_status", "") == "Verified - FLAGGED (sponsor/equity not yet resolved)"
       for r in new_crl):
    errors.append("crl: CR- row has both a ticker and an unresolved-sponsor flag")
warnings.append(f"crl: {sum(1 for r in new_crl if not r.get('ticker'))} of {len(new_crl)} new CRL rows have "
                f"unresolved sponsors (flagged, blank ticker — never guessed)")

# ---- ClinicalTrials.gov Phase 3 registry (2026-09-17 capture)
ctgov = read("clinical_trials_phase3_registry.csv")
if len(ctgov) < 2000:
    errors.append(f"ctgov: {len(ctgov)} rows, expected >= 2000 from the 2026-09-17 capture")
ncts = [r.get("nct_id") for r in ctgov]
if len(ncts) != len(set(ncts)):
    errors.append("ctgov: duplicate nct_id")
for i, r in enumerate(ctgov, 2):
    if not re.fullmatch(r"NCT\d{8}", r.get("nct_id", "")):
        errors.append(f"ctgov:{i}: bad nct_id {r.get('nct_id','')!r}")
        continue
    if r.get("source_url") != f"https://clinicaltrials.gov/study/{r['nct_id']}":
        errors.append(f"ctgov:{i}: source_url does not match the official study page")
    d = r.get("primary_completion_date", "")
    # ClinicalTrials.gov publishes day- or month-precision dates; both kept verbatim
    if d and not (re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or re.fullmatch(r"\d{4}-\d{2}", d)):
        errors.append(f"ctgov:{i}: primary_completion_date {d!r} not ISO YYYY-MM-DD / YYYY-MM")
    if d and d[:4] not in {"2026", "2027"}:
        errors.append(f"ctgov:{i}: primary_completion_date {d!r} outside capture window")
    if not r.get("lead_sponsor", "").strip():
        errors.append(f"ctgov:{i}: blank lead_sponsor")
    if r.get("ticker") and r.get("investability_class") != "US-LISTED":
        errors.append(f"ctgov:{i}: ticker present but investability_class is {r.get('investability_class')!r}")


# ---- Company Clinical Trial Scorecard (dedicated phase progression & FDA record)
clin_scores = read("company_clinical_trial_scorecard.csv")
if len(clin_scores) < 300:
    errors.append(f"clin_scores: {len(clin_scores)} rows, expected >= 300")
for i, r in enumerate(clin_scores, 2):
    if not r.get("company_name", "").strip():
        errors.append(f"clin_scores:{i}: blank company_name")
    if not r.get("verification_status", "").strip():
        errors.append(f"clin_scores:{i}: blank verification_status")
    for k in ("source_url_1", "source_url_2"):
        check_url(r.get(k, ""), f"clin_scores:{i}:{k}")
    g = r.get("success_grade", "").strip()
    if g and g not in {"A", "B", "C", "D", "E"}:
        errors.append(f"clin_scores:{i}: unknown success_grade {g!r}")
    rate = r.get("clinical_progression_rate_pct", "").strip()
    if rate:
        try:
            n = float(rate)
            if not 0 <= n <= 100:
                errors.append(f"clin_scores:{i}: clinical_progression_rate_pct outside 0-100")
        except ValueError:
            errors.append(f"clin_scores:{i}: non-numeric clinical_progression_rate_pct")

print(f"Validated {len(master)} FDA novel-approval rows, {len(suppl)} efficacy-supplement rows, "
      f"{len(orig)} original non-NME rows, {len(oscores)} orig scorecards, {len(t1gap)} Type-1-gap flags, "
      f"{len(exp)} label-expansion scorecards, {len(audit)} cross-check rows, "
      f"{len(scores)} company scorecards, {len(prices)} price snapshots, "
      f"{len(crl)} CRL rows (+{len(new_crl)} new from the openFDA CRL database), and "
      f"{len(ctgov)} ClinicalTrials.gov Phase 3 rows, and {len(clin_scores)} clinical trial scorecards.")
print(f"Warnings requiring manual review: {len(warnings)}")
for w in warnings[:12]: print("WARNING", w)
if len(warnings) > 12: print(f"WARNING ... {len(warnings)-12} more")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors: print("ERROR", e)
    sys.exit(1)
print("PASS: schema, IDs, dates, ranges, and source URL checks succeeded.")
