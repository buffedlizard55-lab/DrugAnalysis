#!/usr/bin/env python3
"""Deterministic QA gate for the published CSVs.

This does not infer missing facts. It only rejects malformed rows and reports
records that require human review, so new entries cannot silently enter the
published tables with guessed values.
"""
import csv, json, re, sys
from collections import Counter
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
# ---- NME master year coverage (1985-2026; pre-1998 = Compilation, added 2026-09-17 v8) ------------
# Rows flagged NOT_ON_FDA_NME_TABLE (i.e. D634 Contrave, a Type 4 combination
# kept only for transparency) do not count toward the official year totals.
# Detector: decision_type is the authoritative carrier; strip attribution text
# ('D634 re-labelled NOT_ON_FDA_NME_TABLE' in Ofev's note) so the WRONG row is
# never the one excluded (prior version excluded Ofev instead of Contrave and
# the 2014 count passed by coincidence).
def _not_on_nme_table(r):
    t = (r.get("decision_type", "") + " " + r.get("verification_status", "") + " " + r.get("notes", ""))
    t = re.sub(r"D\d+\s+re-?labelled\s+NOT_ON_FDA_NME_TABLE", "", t, flags=re.I)
    return "NOT_ON_FDA_NME_TABLE" in t
master_years = {}
_flagged_not_on = [r.get("decision_id") for r in master if _not_on_nme_table(r)]
if _flagged_not_on != ["D634"]:
    errs.append(f"NOT_ON_FDA_NME_TABLE detector must isolate exactly [D634], got {_flagged_not_on}")
for r in master:
    if _not_on_nme_table(r):
        continue
    y = r.get("decision_date", "")[:4]
    master_years[y] = master_years.get(y, 0) + 1
missing_master_years = [str(y) for y in range(1985, 2027) if str(y) not in master_years]
if missing_master_years:
    errors.append(f"master: no rows for year(s) {', '.join(missing_master_years)} — 1985-2026 coverage claim broken")
year_reg = read("fda_year_source_register.csv")
if len(year_reg) != 42 or {r.get("year") for r in year_reg} != {str(y) for y in range(1985, 2027)}:
    errors.append(f"fda_year_source_register: {len(year_reg)} rows, expected exactly one row per year 1985-2026")
for r in year_reg:
    check_url(r.get("official_source_url", ""), f"year_register:{r.get('year')}")
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
# Every year 1985-2026 must be represented (coverage claim).
orig_years = {r.get("decision_date", "")[:4] for r in orig}
missing_years = [str(y) for y in range(1985, 2027) if str(y) not in orig_years]
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
if len(yreg) != 42:
    errors.append(f"orig_year_register: {len(yreg)} rows, expected 42 (1985-2026)")
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

# ---- 2026-09-18 session: pre-2000 audit, pathway consistency, dead-URL ban,
# ---- snapshot integrity, sponsor index -------------------------------------------------
# 1. Pre-2000 year-by-year audit file: 492 rows (v9 204 + v10 288), 1:1 with
#    the master window, every verdict backed by >=2 official layers, every row
#    carrying links.
p2k = read("pre2000_year_audit.csv")
_PRE2000_YEARS = {str(y) for y in range(1985, 2001)}
_expected_ids = {r["decision_id"] for r in master if r["decision_date"][:4] in _PRE2000_YEARS}
_got_ids = {r["decision_id"] for r in p2k}
if _expected_ids != _got_ids:
    errors.append(f"pre2000_year_audit: decision_id set != master 1985-2000 window "
                  f"(missing {len(_expected_ids - _got_ids)}, extra {len(_got_ids - _expected_ids)})")
if len(p2k) != 492:
    errors.append(f"pre2000_year_audit: expected 492 rows, got {len(p2k)}")
_bad_verdicts = [r["decision_id"] for r in p2k if not r["verdict"].startswith("VERIFIED")]
if _bad_verdicts:
    errors.append(f"pre2000_year_audit: {len(_bad_verdicts)} rows not VERIFIED*: {_bad_verdicts[:5]}")
_no_links = [r["decision_id"] for r in p2k
             if not r["source_drugsatfda"].strip() or not r["source_year_table_or_compilation"].strip()]
if _no_links:
    errors.append(f"pre2000_year_audit: rows missing official links: {_no_links[:5]}")
_year_pins = Counter(r["audit_year"] for r in p2k)
for y, n in (("2000", 29), ("1999", 37), ("1998", 36), ("1997", 43), ("1996", 59),
             ("1995", 30), ("1994", 23), ("1993", 27), ("1992", 29), ("1991", 32),
             ("1990", 24), ("1989", 27), ("1988", 20), ("1987", 22), ("1986", 23),
             ("1985", 31)):
    if _year_pins.get(y) != n:
        errors.append(f"pre2000_year_audit: year {y} pin {n} broken (got {_year_pins.get(y)})")
# v10 live-check refinement: every 1985-1995 absence flag must cite a live check
# (no generic 'not yet re-checked live' flags may remain).
_unchecked = [r["decision_id"] for r in p2k
              if "not yet re-checked live" in r["review_flag"]]
if _unchecked:
    errors.append(f"pre2000_year_audit: {len(_unchecked)} rows still lack a live re-check: "
                  f"{_unchecked[:5]}")

# 2. The dead 2019 Wayback wrapper must never come back.
_back = [r["decision_id"] for r in master if "20190207172014" in r["source_url_1"]]
if _back:
    errors.append(f"master: {len(_back)} rows cite the dead 20190207172014 Wayback capture again: {_back[:5]}")

# 3. Pathway column consistency (post labelling pass): no legacy spellings,
#    every row older than 2026 carries a pathway (Compilation coverage).
_legacy_pw = [r["decision_id"] for r in master
              if r["review_pathway"] and ("Priority Review" in r["review_pathway"]
                                          or "/" in r["review_pathway"])]
if _legacy_pw:
    errors.append(f"master: legacy pathway spellings returned: {_legacy_pw[:5]}")
_blanks_pre2026 = [r["decision_id"] for r in master
                   if not r["review_pathway"].strip() and r["decision_date"][:4] != "2026"]
if _blanks_pre2026:
    errors.append(f"master: blank pathway on non-2026 rows (no Compilation row): {_blanks_pre2026[:5]}")

# 3b. v10 pathway reconciliation: the 35 PATHWAY_CONFLICT flags are closed;
#     every touched row carries a dated note; the changelog matches the master.
_pwconf = [r["decision_id"] for r in master if "PATHWAY_CONFLICT" in r["notes"]]
if _pwconf:
    errors.append(f"master: {len(_pwconf)} PATHWAY_CONFLICT notes remain (reconciliation regressed): {_pwconf[:5]}")
_pwnotes = Counter()
for r in master:
    for tag in ("PATHWAY_RECONCILED", "PATHWAY_CORRECTED", "PATHWAY_ENRICHED", "PATHWAY_NOTE"):
        if f"{tag} 2026-09-18" in r["notes"]:
            _pwnotes[tag] += 1
if sum(_pwnotes.values()) != 64:
    errors.append(f"master: expected 64 dated pathway notes (v10 reconciliation), "
                  f"found {sum(_pwnotes.values())}: {dict(_pwnotes)}")
_pwc_log = ROOT / "data" / "staging" / "pathway_reconciliation_changelog.json"
if not _pwc_log.exists():
    errors.append("pathway_reconciliation_changelog.json missing")
else:
    import json as _json
    _log = _json.load(open(_pwc_log))
    if _log.get("n_changes") != 64:
        errors.append(f"changelog n_changes {_log.get('n_changes')} != 64")

# 4. Snapshot table integrity: unique (ticker, decision_date); the 1998-2000
#    event ingestion landed (1998>=13, 1999>=14, 2000>=9 rows incl. recorded
#    failures); every row has a source_url.
_seen = set()
for i, r in enumerate(prices, 2):
    k = (r["ticker"], r["decision_date"])
    if k in _seen:
        errors.append(f"snapshots:{i}: duplicate (ticker, decision_date) {k}")
    _seen.add(k)
    if not r.get("source_url", "").strip():
        errors.append(f"snapshots:{i}: blank source_url")
_sn_by_year = Counter(r["decision_date"][:4] for r in prices)
for y, lo in (("1998", 13), ("1999", 14), ("2000", 9)):
    if _sn_by_year.get(y, 0) < lo:
        errors.append(f"snapshots: year {y} has {_sn_by_year.get(y)} rows, minimum {lo} "
                      "(the 1998-2000 event ingestion must stay in the table)")

# 5. Pre-2000 sponsor-resolution index: 67 rows, defined statuses, links present.
#    v10: the 25 REVIEW (recoverable) rows were processed - 18 VENUE-VERIFIED,
#    1 RESOLVED (Agouron AGPH), 3 CITATION-LOCATED, 3 ATTRIBUTION-CASE.
#    v11: the symbol pass moved 8 of those to RESOLVED (Advanced Magnetics
#    AMEX:AVM, Neurex NASDAQ NMS:NXCO delisted 1998, Cytogen NASDAQ NMS:CYTO x2,
#    Immunomedics NASDAQ NMS:IMMU, Gensia Sicor NASDAQ NMS:GNSA, IVAX/Baker
#    Norton AMEX:IVX) and demoted Carter-Wallace to VENUE-VERIFIED (NYSE per the
#    12(b) cover; its Item 5 is incorporated by reference) - so the standing
#    split is 9 RESOLVED, 12 VENUE-VERIFIED, 1 CITATION-LOCATED.
_sp = read("pre2000_sponsor_resolution_index.csv")
if len(_sp) != 67:
    errors.append(f"pre2000_sponsor_resolution_index: expected 67 rows, got {len(_sp)}")
_statuses = {"REVIEW (recoverable)", "REVIEW (unresolved)", "REVIEW (foreign listing)",
             "NO-EQUITY (documented)", "REVIEW",
             "VENUE-VERIFIED (ticker pending)", "RESOLVED (venue+ticker per period 10-K)",
             "CITATION-LOCATED (fetch the period 10-K and extract venue+ticker)",
             "ATTRIBUTION-CASE (parent/subsidiary)"}
for i, r in enumerate(_sp, 2):
    if r["status"] not in _statuses:
        errors.append(f"pre2000_sponsor_resolution_index:{i}: unknown status {r['status']!r}")
    if not r["sec_edgar_company_search"].strip() or not r["drugsatfda_link"].strip():
        errors.append(f"pre2000_sponsor_resolution_index:{i}: blank research link")
_recoverable = [r["decision_id"] for r in _sp if r["status"] == "REVIEW (recoverable)"]
if _recoverable:
    errors.append(f"pre2000_sponsor_resolution_index: {len(_recoverable)} rows still "
                  f"'REVIEW (recoverable)' after the v10 pass: {_recoverable[:5]}")
# v10 EDGAR evidence file must exist and cover 19 master rows
if not (ROOT / "data" / "staging" / "pre2000_sponsor_edgar_evidence.json").exists():
    errors.append("pre2000_sponsor_edgar_evidence.json missing")
else:
    _ev = json.load(open(ROOT / "data" / "staging" / "pre2000_sponsor_edgar_evidence.json"))
    _ev_rows = {d for c in _ev["companies"].values() for d in c.get("rows", [])}
    _tagged = {r["decision_id"] for r in master if "SPONSOR-RESOLVED 2026-09-18" in r["notes"]}
    if _ev_rows != _tagged:
        errors.append(f"EDGAR evidence rows {_ev_rows} != master SPONSOR-RESOLVED rows {_tagged}")
    _agouron = [r for r in master if r["decision_id"] == "D1380"]
    if _agouron and "AGPH" not in _agouron[0]["exchange"]:
        errors.append("D1380 Agouron exchange must carry the 10-K-verified AGPH ticker")

    # v11 (2026-09-18): the symbol pass. Each of these exchange strings carries a
    # ticker read verbatim out of the registrant's own period filing on EDGAR
    # (Item 5 / cover 12(b)); the master note on the row quotes the sentence and
    # gives the replayable URL. Pin them so a later pass cannot silently revert
    # to a remembered symbol (v9's 'ANM' for Advanced Magnetics and 'NXRX' for
    # Neurex were exactly that kind of guess, and both were wrong).
    _m_by_id = {r["decision_id"]: r for r in master}
    _V11_SYMBOLS = {
        "D1345": ("AMEX:AVM", "AVM"),   # Advanced Magnetics FY1996 10-K405 Item 5
        "D1363": ("AMEX:AVM", "AVM"),
        "D1396": ("NASDAQ NMS:NXCO", "NXCO"),   # + delisting year pinned below
        "D1357": ("NASDAQ NMS:CYTO", ""),       # ticker column deliberately blank
        "D1381": ("NASDAQ NMS:CYTO", ""),
        "D1338": ("NASDAQ NMS:IMMU", ""),
        "D1394": ("NASDAQ NMS:GNSA", "GNSA"),
        "D1353": ("AMEX:IVX", "IVX"),           # venue was AMEX, not Nasdaq
        "D1359": ("NYSE", ""),                  # venue only; Item 5 is incorporated by reference
    }
    for _did, (_needle, _tk) in _V11_SYMBOLS.items():
        _r = _m_by_id.get(_did)
        if not _r:
            errors.append(f"v11 symbol pass: {_did} missing from the master")
            continue
        if _needle not in _r["exchange"]:
            errors.append(f"v11 symbol pass: {_did} exchange must carry '{_needle}', got {_r['exchange']!r}")
        if _r["ticker"] != _tk:
            errors.append(f"v11 symbol pass: {_did} ticker must be {_tk!r} (blank means a documented "
                          f"downstream hazard, not missing data), got {_r['ticker']!r}")
        if "SPONSOR-RESOLVED 2026-09-18 (v11 symbol pass)" not in _r["notes"]:
            errors.append(f"v11 symbol pass: {_did} must carry the dated v11 note with the verbatim Item 5 quote")
    # Neurex is the first worklist row with a pinned delisting year (Elan merger).
    if _m_by_id.get("D1396") and "delisted 1998" not in _m_by_id["D1396"]["exchange"]:
        errors.append("D1396 Neurex exchange must carry the EDGAR-pinned 'delisted 1998'")
    # index progress guard: these 9 rows are resolved and must stay resolved
    _v11_resolved = {"D1338", "D1345", "D1353", "D1357", "D1363", "D1380", "D1381", "D1394", "D1396"}
    _sp_by_id = {r["decision_id"]: r for r in _sp}
    for _did in sorted(_v11_resolved):
        if _sp_by_id.get(_did, {}).get("status") != "RESOLVED (venue+ticker per period 10-K)":
            errors.append(f"pre2000_sponsor_resolution_index: {_did} must stay "
                          f"'RESOLVED (venue+ticker per period 10-K)'")

# 6. Era analysis: 16 rows (1985-2000); approvals match the master counts.
_era = read("pre2000_era_analysis.csv")
if len(_era) != 16:
    errors.append(f"pre2000_era_analysis: expected 16 year rows, got {len(_era)}")
_m_by_year = Counter(r["decision_date"][:4] for r in master)
for r in _era:
    if int(r["master_approvals"]) != _m_by_year.get(r["year"], 0):
        errors.append(f"pre2000_era_analysis:{r['year']}: approvals {r['master_approvals']} "
                      f"!= master {_m_by_year.get(r['year'], 0)}")

# 7. Core analysis table <-> master integrity (v11 2026-09-18).
#    build_core_analysis_table.py writes one row per master row plus one per CRL
#    (then sorts by date desc), and it derives a TICKER-KEYED class map with
#    setdefault() in master order which it applies to EVERY row sharing that
#    ticker. So filling a master `ticker` can silently re-class a DIFFERENT row:
#    that is exactly why D1338's verified IMMU and D1357/D1381's verified CYTO
#    are kept out of the ticker column (NO_TICKER_FILL in
#    scripts/resolve_pre2000_sponsors_v11.py). This section makes that hazard
#    measurable instead of invisible:
#      (a) shape: one core row per master row + one per CRL row;
#      (b) coverage: every master row is present in the core table;
#      (c) ratchet: the number of rows whose core class disagrees with the
#          master row's OWN committed class must stay at the audited baseline.
#    Baseline history: 145 when this gate was added. The same pass then found and
#    fixed a real join bug - build_core_analysis_table.py treated the
#    NO_US_TICKER sentinel as a symbol, so 11 unrelated companies shared Fresenius
#    Kabi's class and pipeline card - which removed 4 contradictions and re-pinned
#    the baseline at 141. All 141 remaining rows are TICKER-INTERNALLY-INCONSISTENT:
#    the master itself assigns different committed classes to rows sharing one
#    ticker, across 22 tickers in two families (ADR-vs-direct: GSK, NVS, RHHBY,
#    AZN, SNY, BAYRY, TAK, NVO, TEVA; delisted-vs-current: SHPG, MDCO, CELG, ALXN,
#    ORPH, SGEN, CBST, SLXP, BPMC, SPPI, BLCO, SWTX, AAAP). Adjudicating them needs
#    per-company primary evidence, so it is NEXT_SESSION.md next-step 2, itemised in
#    data/staging/core_class_disagreements.csv. This ratchet does NOT bless them -
#    it stops a 142nd appearing unnoticed when someone fills a ticker.
CORE_CLASS_BASELINE = 141
_core = read("core_analysis_table.csv")
_crl_master = read("fda_crl_master.csv")
if len(_core) != len(master) + len(_crl_master):
    errors.append(f"core_analysis_table: expected {len(master)} master + {len(_crl_master)} CRL = "
                  f"{len(master) + len(_crl_master)} rows, got {len(_core)}")
_core_key = lambda r: (r["company_name"], r["decision_date"], r["drug_name"])
_master_key = lambda r: (r["company_name"], r["decision_date"],
                         f"{r['drug_brand']} ({r['drug_generic']})")
_core_by_key = {}
for _r in _core:
    _core_by_key.setdefault(_core_key(_r), _r)
_missing_core = [r["decision_id"] for r in master if _master_key(r) not in _core_by_key]
if _missing_core:
    errors.append(f"core_analysis_table: {len(_missing_core)} master rows are missing from the "
                  f"joined table: {_missing_core[:5]}")
_class_dis = [(r["decision_id"], r["ticker"], r["us_investable_class"],
               _core_by_key[_master_key(r)]["us_investable_class"])
              for r in master
              if _master_key(r) in _core_by_key
              and r["us_investable_class"] != _core_by_key[_master_key(r)]["us_investable_class"]]
if len(_class_dis) != CORE_CLASS_BASELINE:
    errors.append(
        f"core_analysis_table: {len(_class_dis)} rows carry a us_investable_class that disagrees "
        f"with the master row's own committed class (audited baseline {CORE_CLASS_BASELINE}). "
        f"Examples: {_class_dis[:5]}. A NEW disagreement usually means a master `ticker` was just "
        f"filled for a symbol another row already carries - build_core_analysis_table.py propagates "
        f"one class per ticker to every row sharing it. Fix the fill (see NO_TICKER_FILL in "
        f"scripts/resolve_pre2000_sponsors_v11.py and NEXT_SESSION.md next-step 2), or adjudicate "
        f"the legacy 145 and re-pin CORE_CLASS_BASELINE deliberately - never silently.")
else:
    warnings.append(f"core table: {len(_class_dis)} legacy class disagreements with the master "
                    f"(audited baseline, pending adjudication - NEXT_SESSION.md next-step 2)")

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
