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
# Every year 1980-2026 must be represented (coverage claim; v16 extended 1980-1982).
orig_years = {r.get("decision_date", "")[:4] for r in orig}
missing_years = [str(y) for y in range(1980, 2027) if str(y) not in orig_years]
if missing_years:
    errors.append(f"orig: missing years {', '.join(missing_years)} — coverage claim broken")

# ---- v15/v16 pre-1985 backward extension (1980-1984 focus years) ------------
_pre_orig_years = {"1980": 73, "1981": 48, "1982": 78, "1983": 56, "1984": 89}
_pre_payload_dir = ROOT / "data" / "raw" / "openfda_orig_decisions_1980_1984"
_pre_by_year = {y: [r for r in orig if r.get("decision_date", "").startswith(y)]
                for y in _pre_orig_years}
for _y, _n in _pre_orig_years.items():
    if len(_pre_by_year[_y]) != _n:
        errors.append(f"orig:{_y}: expected {_n} v15 backward-extension rows, got {len(_pre_by_year[_y])}")
_pre_appls: dict[str, str] = {}
for _y, _rows in _pre_by_year.items():
    for r in _rows:
        a = (r.get("application_number") or "").strip()
        if a in _pre_appls:
            errors.append(f"orig: duplicate pre-1985 application {a}")
        _pre_appls[a] = r.get("orig_id", "")
        code = (r.get("chemical_type_code") or "").strip().upper()
        if code in {"TYPE 1", "TYPE 1/4"}:
            errors.append(f"orig:{r['orig_id']}: Type 1/1-4 code {code} must not appear in the "
                          f"pre-1985 backward extension (pre1985_fda_decisions.csv owns those)")
        if "PRE-1985 ROW" not in (r.get("notes") or ""):
            errors.append(f"orig:{r['orig_id']}: pre-1985 row missing the PRE-1985 holder disclaimer")
        # Verbatim cross-check against the committed payload.
        try:
            pl = json.load(open(_pre_payload_dir / f"decisions_{_y}.json"))
            rec = next((x for x in pl["decisions"]
                        if (x.get("application_number") or "").strip() == a), None)
        except Exception as _exc:  # payload missing/corrupt
            rec = None
            errors.append(f"orig: pre-1985 payload unreadable for {_y}: {_exc}")
        if rec is None:
            errors.append(f"orig:{r['orig_id']}: application {a} not in committed {_y} payload")
        else:
            if (rec.get("decision_date") or "").strip() != r.get("decision_date", "").strip():
                errors.append(f"orig:{r['orig_id']}: date {r['decision_date']} != payload {rec.get('decision_date')}")
            if (rec.get("submission_class_code") or "").strip() != (r.get("chemical_type_code") or "").strip():
                errors.append(f"orig:{r['orig_id']}: class {r.get('chemical_type_code')!r} != payload {rec.get('submission_class_code')!r}")
            if (rec.get("review_priority") or "").strip() != (r.get("review_priority") or "").strip():
                errors.append(f"orig:{r['orig_id']}: priority {r.get('review_priority')!r} != payload {rec.get('review_priority')!r}")
            if (rec.get("sponsor_name") or "").strip() != (r.get("openfda_sponsor_name") or "").strip():
                errors.append(f"orig:{r['orig_id']}: holder {r.get('openfda_sponsor_name')!r} != payload {rec.get('sponsor_name')!r}")
# The two non-Type-1 applications already tracked in pre1985_fda_decisions.csv
# (furosemide NDA018413, Trandate NDA018716) must never appear here.
_pre_table_appls = set()
for r in read("pre1985_fda_decisions.csv"):
    m = re.search(r"(\d{6})", re.sub(r"[^0-9]", "", r.get("application_number", "")))
    if m:
        _pre_table_appls.add("NDA" + m.group(1))
for _a in ("NDA018413", "NDA018716"):
    if _a in _pre_appls:
        errors.append(f"orig: {_a} is tracked in pre1985_fda_decisions.csv and must not be duplicated")
    if _a not in _pre_table_appls:
        errors.append(f"pre1985 boundary pin broken: {_a} missing from pre1985_fda_decisions.csv")
# No pre-1985 non-NME row may duplicate ANY application already in the pre-1985 table.
_pre_overlap = sorted(set(_pre_appls) & _pre_table_appls)
if _pre_overlap:
    errors.append(f"orig: pre-1985 rows duplicate pre1985_fda_decisions.csv applications: {_pre_overlap}")
# NDA022046 must carry its irregularity annotation (openFDA lineage artifact).
_r22046 = next((r for r in orig if (r.get("application_number") or "").strip() == "NDA022046"
                and (r.get("decision_date") or "").startswith("1983")), None)
if _r22046 is None:
    errors.append("orig: NDA022046 1983-07-13 row missing (v15 annotated irregularity)")
elif "FLAGGED IRREGULARITY" not in (_r22046.get("verification_status", "") + _r22046.get("notes", "")):
    errors.append("orig: NDA022046 row lost its FLAGGED IRREGULARITY annotation")

# ---- v15/v16 focus-year audit (1980-1985 complete enumeration) ---------------
focus = read("focus_years_1980_1985_audit.csv")
if len(focus) != 517:
    errors.append(f"focus_audit: expected 517 audited ORIG/AP decisions (1980-1985), got {len(focus)}")
_focus_year_counts = Counter(r.get("year", "") for r in focus)
for _y, _n in (("1980", 82), ("1981", 71), ("1982", 103), ("1983", 70), ("1984", 109), ("1985", 82)):
    if _focus_year_counts.get(_y, 0) != _n:
        errors.append(f"focus_audit: year {_y} has {_focus_year_counts.get(_y, 0)} rows, expected {_n}")
_seen_focus_appl = set()
for i, r in enumerate(focus, 2):
    key = (r.get("year", ""), r.get("application_number", ""))
    if key in _seen_focus_appl:
        errors.append(f"focus_audit:{i}: duplicate payload decision {key}")
    _seen_focus_appl.add(key)
    if r.get("verdict") not in {"TRACKED_VERIFIED", "TRACKED_REVIEW", "DISAGREEMENT_REVIEW"}:
        errors.append(f"focus_audit:{i}: invalid verdict {r.get('verdict')!r}")
    if r.get("verdict") == "UNTRACKED" or not (r.get("tracked_in") or "").strip():
        errors.append(f"focus_audit:{i}: payload decision left untracked")
    check_url(r.get("source_url_drugsatfda", ""), f"focus_audit:{i}:source_url_drugsatfda")
    if not (r.get("source_query_url") or "").strip():
        errors.append(f"focus_audit:{i}: missing replayable openFDA query URL")
    if (r.get("date_agreement") or "") != "YES":
        warnings.append(f"focus_audit:{i}: date_agreement={r.get('date_agreement')!r} — manual review")
for _y in ("1980", "1981", "1982", "1983", "1984", "1985"):
    _pdir = _pre_payload_dir if _y != "1985" else ROOT / "data" / "raw" / "openfda_orig_decisions_2011_2026"
    try:
        _pl = json.load(open(_pdir / f"decisions_{_y}.json"))
        _pl_appls = {(x.get("application_number") or "").strip() for x in _pl["decisions"]}
    except Exception as _exc:
        _pl_appls = set()
        errors.append(f"focus_audit: payload {_y} unreadable: {_exc}")
    _csv_appls = {r.get("application_number", "") for r in focus if r.get("year") == _y}
    if _pl_appls != _csv_appls:
        errors.append(f"focus_audit:{_y}: audited application set != payload set "
                      f"(missing {sorted(_pl_appls - _csv_appls)[:5]}, extra {sorted(_csv_appls - _pl_appls)[:5]})")
# Every payload decision must reference a known project table.
for _y in ("1980", "1981", "1982", "1983", "1984", "1985"):
    _tracked = [r for r in focus if r.get("year") == _y]
    _bad = [r["application_number"] for r in _tracked
            if (r.get("tracked_in") or "") not in {
                "pre1985_fda_decisions.csv", "fda_original_non_nme_decisions.csv",
                "fda_decisions_master.csv", "fda_type1_not_in_nme_master.csv"}]
    if _bad:
        errors.append(f"focus_audit:{_y}: rows tracked in unknown tables: {_bad[:5]}")

# v15 pin: 1985 master rows whose application has NO ORIG/AP record in the
# committed payload (Seldane, Protropin, Suprol, Femstat — a documented
# openFDA/Drugs@FDA completeness gap). If this set changes, re-verify.
_pdir85 = ROOT / "data" / "raw" / "openfda_orig_decisions_2011_2026"
_pl85 = json.load(open(_pdir85 / "decisions_1985.json"))
_pl85_appls = {re.sub(r"^(NDA|BLA|ANDA)", "", (x.get("application_number") or "").strip()).zfill(6)
               for x in _pl85["decisions"]}
_m85_appls = set()
for r in master:
    if not (r.get("decision_date") or "").startswith("1985"):
        continue
    blob = " ".join([r.get("notes", ""), r.get("source_url_1", ""),
                     r.get("source_url_2", ""), r.get("classification_basis", "")])
    for m in re.finditer(r"NDA\s*-?\s*(\d{5,6})", blob):
        _m85_appls.add(m.group(1).zfill(6))
_m85_gap = {a for a in _m85_appls if a not in _pl85_appls}
if _m85_gap != {"018217", "018949", "019107", "019215"}:
    errors.append(f"master:1985: applications without a payload ORIG record changed to {sorted(_m85_gap)} "
                  "(pinned: Seldane 018949, Protropin 019107, Suprol 018217, Femstat 019215) — "
                  "the openFDA completeness gap moved; re-verify before updating the pin")

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
if len(yreg) != 47:
    errors.append(f"orig_year_register: {len(yreg)} rows, expected 47 (1980-2026, v15/v16 backward extension)")
published_sum = sum(int(r.get("non_nme_published") or 0) for r in yreg)
if published_sum != len(orig):
    errors.append(f"orig_year_register: sum(non_nme_published)={published_sum} != {len(orig)} orig rows")
# v15/v16 pins: the backward years must register the committed-payload enumeration.
_v15_yreg = {r.get("year"): r for r in yreg}
for _y, _raw, _pub in (("1980", 82, 73), ("1981", 71, 48), ("1982", 103, 78),
                       ("1983", 70, 56), ("1984", 109, 89)):
    _r = _v15_yreg.get(_y)
    if _r is None:
        errors.append(f"orig_year_register: missing backward year {_y}")
    else:
        if int(_r.get("openfda_orig_nda_bla_count") or 0) != _raw or int(_r.get("non_nme_published") or 0) != _pub:
            errors.append(f"orig_year_register:{_y}: raw/published counters changed "
                          f"({_r.get('openfda_orig_nda_bla_count')}/{_r.get('non_nme_published')}, "
                          f"pinned {_raw}/{_pub}) — re-verify the payload first")

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
             "RESOLVED (venue+ticker per period SEC filings)",
             "RESOLVED (documented negative: no exchange listing, no SEC-stated ticker; OTC inter-dealer only)",
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
# v16 pins: the last 7 VENUE-VERIFIED rows must stay resolved as recorded
# (primary SEC text fetched 2026-09-18; scripts/resolve_pre2000_sponsors_v16.py).
_sp16 = {r["decision_id"]: r for r in _sp}
_v16_expect = {
    "D1342": ("WLA", "RESOLVED (venue+ticker per period SEC filings)"),
    "D1366": ("WLA", "RESOLVED (venue+ticker per period SEC filings)"),
    "D1376": ("WLA", "RESOLVED (venue+ticker per period SEC filings)"),
    "D1409": ("WLA", "RESOLVED (venue+ticker per period SEC filings)"),
    "D1347": ("RPCX", "RESOLVED (venue+ticker per period SEC filings)"),
    "D1379": ("RPCX", "RESOLVED (venue+ticker per period SEC filings)"),
    "D1365": ("(blank - documented negative)",
              "RESOLVED (documented negative: no exchange listing, no SEC-stated ticker; OTC inter-dealer only)"),
}
for _d, (_t, _s) in _v16_expect.items():
    _r = _sp16.get(_d)
    if _r is None:
        errors.append(f"pre2000_sponsor_resolution_index: v16 row {_d} missing")
    else:
        if _r["master_ticker"] != _t or _r["status"] != _s:
            errors.append(f"pre2000_sponsor_resolution_index:{_d}: v16 resolution moved to "
                          f"ticker={_r['master_ticker']!r} status={_r['status']!r} (pinned {_t!r})")
for _d, _t in (("D1342", "WLA"), ("D1366", "WLA"), ("D1376", "WLA"), ("D1409", "WLA"),
               ("D1347", "RPCX"), ("D1379", "RPCX")):
    _r = next((x for x in master if x.get("decision_id") == _d), None)
    if _r is None:
        errors.append(f"master: v16 row {_d} missing")
    elif (_r.get("ticker") or "").strip() != _t:
        errors.append(f"master:{_d}: ticker {_r.get('ticker')!r} != v16 pin {_t!r}")
    elif "v16 2026-09-18 TICKER RESOLUTION" not in (_r.get("notes") or ""):
        errors.append(f"master:{_d}: v16 ticker-resolution note missing")
# v10 EDGAR evidence file must exist and cover 19 master rows
if not (ROOT / "data" / "staging" / "pre2000_sponsor_edgar_evidence.json").exists():
    errors.append("pre2000_sponsor_edgar_evidence.json missing")
else:
    _ev = json.load(open(ROOT / "data" / "staging" / "pre2000_sponsor_edgar_evidence.json"))
    _ev_rows = {d for c in _ev["companies"].values() for d in c.get("rows", [])}
    _tagged = {r["decision_id"] for r in master if "SPONSOR-RESOLVED 2026-09-18" in r["notes"]}
    if _ev_rows != _tagged:
        errors.append(f"EDGAR evidence rows {_ev_rows} != master SPONSOR-RESOLVED rows {_tagged}")
    if "v16_update" not in _ev:
        errors.append("pre2000_sponsor_edgar_evidence.json: missing v16_update section "
                      "(the 2026-09-18 seven-row ticker resolution evidence)")
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
        "D1359": ("NYSE:CAR", ""),              # v12: symbol CAR verified from the EX-13 annual report p.7; ticker column deliberately blank
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
    # v12 (2026-09-18) symbol sweep pins (PNU x5 filled; CAR in exchange only; Roberts
    # venue-transfer date pinned; Warner-Lambert negative result kept; Block Drug venue).
    for _did in ("D1330", "D1332", "D1373", "D1382", "D1390"):
        _r = _m_by_id.get(_did)
        if not _r:
            errors.append(f"v12 symbol pass: {_did} missing from the master")
            continue
        if "NYSE:PNU" not in _r["exchange"] or _r["ticker"] != "PNU":
            errors.append(f"v12 symbol pass: {_did} must carry exchange 'NYSE:PNU' and ticker 'PNU' "
                          f"(FY1997 10-K405 Item 5), got {_r['exchange']!r}/{_r['ticker']!r}")
        if "(v12 symbol pass)" not in _r["notes"]:
            errors.append(f"v12 symbol pass: {_did} must carry the dated v12 note with the verbatim quote")
    if _m_by_id.get("D1359") and _m_by_id["D1359"]["ticker"] != "":
        errors.append("v12 symbol pass: D1359 ticker column must stay blank (D1244 same-name split "
                      "hazard); the verified CAR symbol lives in the exchange field")
    if _m_by_id.get("D1359") and "(v12 symbol pass)" not in _m_by_id["D1359"]["notes"]:
        errors.append("v12 symbol pass: D1359 must carry the dated v12 note with the EX-13 p.7 quote")
    for _did in ("D1347", "D1379"):
        _r = _m_by_id.get(_did)
        if not _r or "1997-05-22" not in _r["exchange"]:
            errors.append(f"v12 symbol pass: {_did} exchange must carry the pinned '1997-05-22' AMEX transfer date")
    for _did in ("D1342", "D1366", "D1376", "D1409"):
        _r = _m_by_id.get(_did)
        if not _r or "(v12 negative pass)" not in _r["notes"]:
            errors.append(f"v12 symbol pass: {_did} must keep the documented v12 negative-result note")
    if _m_by_id.get("D1365"):
        _r = _m_by_id["D1365"]
        if "NASD" not in _r["exchange"]:
            errors.append("v12 symbol pass: D1365 exchange must carry the OTC/NASD inter-dealer venue")
        if "Aphthasol" not in _r["notes"]:
            errors.append("v12 symbol pass: D1365 note must keep the verbatim Aphthasol approval quote")
    # index progress guard: these rows are resolved and must stay resolved
    _v11_resolved = {"D1338", "D1345", "D1353", "D1357", "D1363", "D1380", "D1381", "D1394", "D1396",
                     "D1330", "D1332", "D1359", "D1373", "D1382", "D1390"}   # v12: + P&U x5 + Carter-Wallace
    _sp_by_id = {r["decision_id"]: r for r in _sp}
    for _did in sorted(_v11_resolved):
        if _sp_by_id.get(_did, {}).get("status") != "RESOLVED (venue+ticker per period 10-K)":
            errors.append(f"pre2000_sponsor_resolution_index: {_did} must stay "
                          f"'RESOLVED (venue+ticker per period 10-K)'")
    # v12: no row may remain CITATION-LOCATED (Block Drug was promoted to VENUE-VERIFIED)
    _cited = [r["decision_id"] for r in _sp if r["status"].startswith("CITATION-LOCATED")]
    if _cited:
        errors.append(f"pre2000_sponsor_resolution_index: CITATION-LOCATED rows must be cleared "
                      f"after the v12 pass: {_cited}")
    # v12: the manifest recording the runner-403 negative result must stay in the repo
    if not (ROOT / "data" / "raw" / "edgar_pre2000_symbols_2026_09" / "manifest.json").exists():
        errors.append("edgar_pre2000_symbols_2026_09/manifest.json missing - it records the "
                      "Actions-runner HTTP-403 finding")

# 6. Era analysis: 16 rows (1985-2000); approvals match the master counts.
_era = read("pre2000_era_analysis.csv")
if len(_era) != 16:
    errors.append(f"pre2000_era_analysis: expected 16 year rows, got {len(_era)}")
_m_by_year = Counter(r["decision_date"][:4] for r in master)
for r in _era:
    if int(r["master_approvals"]) != _m_by_year.get(r["year"], 0):
        errors.append(f"pre2000_era_analysis:{r['year']}: approvals {r['master_approvals']} "
                      f"!= master {_m_by_year.get(r['year'], 0)}")

# 6b. Pre-1985 era analysis and verified decisions (1980-1985).
#     v14 (2026-09-18) adds the complete committed Drugs@FDA TYPE-1/1-4
#     enumeration for 1980, 1981, and 1982, and moves Hylorel to its actual
#     1982 approval group.  The dedicated CSV contains 1980-1984 rows; the
#     1985 era row is checked against the master table below.
_pre1985_decisions = read("pre1985_fda_decisions.csv")
_p1985_expected = {"1980": 9, "1981": 23, "1982": 25, "1983": 14, "1984": 20}
if len(_pre1985_decisions) != sum(_p1985_expected.values()):
    errors.append(
        f"pre1985_fda_decisions: expected {sum(_p1985_expected.values())} verified rows (v14 baseline), "
        f"got {len(_pre1985_decisions)}"
    )
_p1985_by_year = Counter(r["year"] for r in _pre1985_decisions)
for _y, _n in _p1985_expected.items():
    if _p1985_by_year.get(_y, 0) != _n:
        errors.append(
            f"pre1985_fda_decisions: expected {_n} rows in the {_y} group, "
            f"got {_p1985_by_year.get(_y, 0)}"
        )
_REMOVED_PRE1985 = {
    "PRE1985-1983-06", "PRE1985-1984-09", "PRE1985-1984-10",
    # v13 kept Hylorel as a launch-era boundary row in the 1983 group; v14
    # re-homes it to 1982 and the old ID must not silently return.
    "PRE1985-1983-08",
}
_p1985_ids = set()
for i, r in enumerate(_pre1985_decisions, 2):
    if not r["decision_id"].startswith("PRE1985-"):
        errors.append(f"pre1985_fda_decisions:{i}: invalid ID format {r['decision_id']!r}")
    if r["year"] not in tuple(_p1985_expected):
        errors.append(f"pre1985_fda_decisions:{i}: unexpected year {r['year']!r}")
    if not r["source_url_1"].startswith("http") or not r["source_url_2"].startswith("http"):
        errors.append(f"pre1985_fda_decisions:{i}: missing official source URL")
    if r["verification_status"] != "Verified":
        errors.append(f"pre1985_fda_decisions:{i}: status must be 'Verified', got {r['verification_status']!r}")
    if r["decision_id"] in _REMOVED_PRE1985:
        errors.append(
            f"pre1985_fda_decisions:{i}: {r['decision_id']} was removed or re-homed in v14 "
            "and must not reappear"
        )
    _p1985_ids.add(r["decision_id"])
if len(_p1985_ids) != len(_pre1985_decisions):
    errors.append("pre1985_fda_decisions: duplicate decision_id values")

# v13 corrections remain pinned so they cannot silently revert.
_p1985_row = {r["decision_id"]: r for r in _pre1985_decisions}
for _did, _appl, _cls, _pri in (
    ("PRE1985-1984-07", "NDA 050564", "TYPE 1/4", "PRIORITY"),
    ("PRE1985-1984-08", "NDA 018257", "TYPE 1", "PRIORITY"),
    ("PRE1985-1984-06", "NDA 018716", "TYPE 5", "STANDARD"),
    ("PRE1985-1984-18", "NDA 018686", "TYPE 1", "PRIORITY"),
):
    _r = _p1985_row.get(_did)
    if not _r:
        errors.append(f"pre1985_fda_decisions: {_did} missing (v13 corrected/added row)")
    else:
        if _r["application_number"] != _appl:
            errors.append(f"pre1985_fda_decisions: {_did} application must be {_appl!r}, got {_r['application_number']!r}")
        if _r["chemical_type_code"] != _cls:
            errors.append(f"pre1985_fda_decisions: {_did} chemical type must be {_cls!r}, got {_r['chemical_type_code']!r}")
        if _r["review_priority"] != _pri:
            errors.append(f"pre1985_fda_decisions: {_did} priority must be {_pri!r}, got {_r['review_priority']!r}")
# v14 boundary/application pin.
_hylorel = [r for r in _pre1985_decisions if r["application_number"] == "NDA 018104"]
if len(_hylorel) != 1:
    errors.append(f"pre1985_fda_decisions: expected one re-homed Hylorel NDA 018104, got {len(_hylorel)}")
else:
    _h = _hylorel[0]
    if _h["year"] != "1982" or _h["decision_date"] != "1982-12-29" or _h["chemical_type_code"] != "TYPE 1":
        errors.append("pre1985_fda_decisions: Hylorel must be pinned to the 1982-12-29 TYPE 1 payload")

# Every retained row must match the committed openFDA extraction in date,
# chemical type and priority where the row states those values.
try:
    _pay = {}
    for _y in (1980, 1981, 1982, 1983, 1984):
        _p = json.load(open(ROOT / "data" / "raw" / "openfda_orig_decisions_1980_1984" / f"decisions_{_y}.json"))
        _pay.update({d["application_number"]: d for d in _p["decisions"]})
    _seen_apps = set()
    for r in _pre1985_decisions:
        _appl = r["application_number"].replace(" ", "")
        if _appl in _seen_apps:
            errors.append(f"pre1985_fda_decisions: duplicate application {_appl}")
        _seen_apps.add(_appl)
        _pl = _pay.get(_appl)
        if _pl is None:
            errors.append(f"pre1985_fda_decisions: {r['decision_id']} application {_appl} not in committed payloads")
            continue
        if _pl["decision_date"] != r["decision_date"]:
            errors.append(f"pre1985_fda_decisions: {r['decision_id']} date {r['decision_date']} != payload {_pl['decision_date']}")
        _payload_class = _pl.get("submission_class_code") or "NOT STATED"
        if r["chemical_type_code"] != "NOT STATED" and r["chemical_type_code"] != _payload_class:
            errors.append(f"pre1985_fda_decisions: {r['decision_id']} class {r['chemical_type_code']} != payload {_payload_class}")
        _payload_priority = _pl.get("review_priority") or "NOT STATED"
        if r["review_priority"] != "NOT STATED" and r["review_priority"] != _payload_priority:
            errors.append(f"pre1985_fda_decisions: {r['decision_id']} priority {r['review_priority']} != payload {_payload_priority}")
except FileNotFoundError as _exc:
    errors.append(f"pre1985_fda_decisions: openFDA payload missing: {_exc}")

# For 1980-1982, the table must equal the complete TYPE-1/1-4 application
# enumeration in each committed payload, rather than a hand-curated landmark
# subset.  This is the v14 completeness ratchet.
try:
    for _y in (1980, 1981, 1982):
        _payload_apps = {
            _app for _app, _pl in _pay.items()
            if _pl["decision_date"].startswith(str(_y))
            and str(_pl.get("submission_class_code", "")).startswith("TYPE 1")
        }
        _table_apps = {
            r["application_number"].replace(" ", "")
            for r in _pre1985_decisions if r["year"] == str(_y)
        }
        if _table_apps != _payload_apps:
            errors.append(
                f"pre1985_fda_decisions:{_y}: table applications do not equal payload TYPE-1 enumeration "
                f"(table={len(_table_apps)}, payload={len(_payload_apps)})"
            )
except NameError:
    pass

_pre1985_era = read("pre1985_era_analysis.csv")
if len(_pre1985_era) != 6:
    errors.append(f"pre1985_era_analysis: expected 6 year rows (1980-1985), got {len(_pre1985_era)}")
_era_p1985 = {r["year"]: r for r in _pre1985_era}
for r in _pre1985_era:
    if r["year"] not in ("1980", "1981", "1982", "1983", "1984", "1985"):
        errors.append(f"pre1985_era_analysis: unexpected year {r['year']!r}")
    if not r["primary_source_basis"].strip():
        errors.append(f"pre1985_era_analysis:{r['year']}: missing primary source basis")
_era_expect = {**_p1985_expected, "1985": 31}
for _y, _n in _era_expect.items():
    _er = _era_p1985.get(_y, {})
    if int(_er.get("verified_decisions_tracked", -1)) != _n:
        errors.append(f"pre1985_era_analysis:{_y}: verified_decisions_tracked must be {_n}, got {_er.get('verified_decisions_tracked')!r}")
_era_nme_expect = {"1980": 9, "1981": 23, "1982": 25, "1983": 14, "1984": 19, "1985": 31}
for _y, _n in _era_nme_expect.items():
    _er = _era_p1985.get(_y, {})
    if int(_er.get("total_nmes_approved", -1)) != _n:
        errors.append(f"pre1985_era_analysis:{_y}: total_nmes_approved must be {_n}, got {_er.get('total_nmes_approved')!r}")
# Priority/standard counts for the dedicated 1980-1984 table must equal the
# table; 1985 remains represented by the master-era baseline.
for _y in ("1980", "1981", "1982", "1983", "1984"):
    _pri = sum(1 for r in _pre1985_decisions if r["year"] == _y and r["review_priority"] == "PRIORITY")
    _std = sum(1 for r in _pre1985_decisions if r["year"] == _y and r["review_priority"] == "STANDARD")
    _er = _era_p1985.get(_y, {})
    if int(_er.get("priority_reviews", -1)) != _pri:
        errors.append(f"pre1985_era_analysis:{_y}: priority_reviews {_er.get('priority_reviews')} != table {_pri}")
    if int(_er.get("standard_reviews", -1)) != _std:
        errors.append(f"pre1985_era_analysis:{_y}: standard_reviews {_er.get('standard_reviews')} != table {_std}")
# The 1985 decisions live in the master and use its review_pathway field.
_1985_master = [r for r in master if r.get("decision_date", "").startswith("1985-")]
_1985_pri = sum(1 for r in _1985_master if r.get("review_pathway", "").upper() == "PRIORITY")
_1985_std = sum(1 for r in _1985_master if r.get("review_pathway", "").upper() == "STANDARD")
if int(_era_p1985.get("1985", {}).get("priority_reviews", -1)) != _1985_pri:
    errors.append(f"pre1985_era_analysis:1985: priority_reviews does not match master ({_1985_pri})")
if int(_era_p1985.get("1985", {}).get("standard_reviews", -1)) != _1985_std:
    errors.append(f"pre1985_era_analysis:1985: standard_reviews does not match master ({_1985_std})")

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


# ---- v17 (2026-09-19): official FDA series reconciliation -------------------
# FDA's History Office tabulation and the CDER NME Compilation are now both
# committed captures; these gates keep the reconciliation, the pre-1985 gap
# analysis and the live-capture index pinned to them.
_series = read("fda_official_year_series.csv")
_cross = read("fda_official_series_crosswalk.csv")
_gap = read("pre1985_nme_gap_analysis.csv")
_caps = read("pre1985_primary_captures_index.csv")
_probe = read("pre1980_openfda_probe_2026_09_19.csv")

_hist = json.loads((DATA / "raw" / "source_captures_2026_09_19" /
                    "fda_history_nda_nme_approvals_1938_2022.json").read_text(encoding="utf-8"))
if len(_series) != len(_hist["rows"]):
    errors.append(f"fda_official_year_series: {len(_series)} rows != {len(_hist['rows'])} captured rows")
_official = {r["year"]: r["nmes_approved"] for r in _series}
for _y, _v in {"1980": "12", "1981": "27", "1982": "28", "1983": "14", "1984": "22",
               "1985": "30", "1988": "21", "2013": "29", "2022": "37"}.items():
    if _official.get(_y) != _v:
        errors.append(f"fda_official_year_series: {_y} NMEs = {_official.get(_y)!r}, expected {_v}")
if len(_cross) != 47 or [r["year"] for r in _cross] != [str(y) for y in range(1980, 2027)]:
    errors.append("fda_official_series_crosswalk: expected 47 rows, one per year 1980-2026")
_short = [r["year"] for r in _cross if r["verdict"] == "PROJECT_SHORT_FLAGGED"]
if _short != ["1980", "1981", "1982", "1983", "1984", "1988", "2013"]:
    errors.append(f"crosswalk: PROJECT_SHORT years changed to {_short}")
if len(_gap) != 6 or [r["year"] for r in _gap] != ["1980", "1981", "1982", "1983", "1984", "1985"]:
    errors.append("pre1985_nme_gap_analysis: expected six rows, 1980-1985")
for _r in _gap:
    _want = {"1980": ("12", "-3"), "1981": ("27", "-4"), "1982": ("28", "-3"),
             "1983": ("14", "-1"), "1984": ("22", "-3"), "1985": ("30", "1")}[_r["year"]]
    if (_r["official_nmes_approved"], _r["effective_type1_shortfall_negative_is_short"]) != _want:
        errors.append(f"pre1985_nme_gap_analysis {_r['year']}: official/shortfall drift "
                      f"({_r['official_nmes_approved']}/{_r['effective_type1_shortfall_negative_is_short']})")
_1980 = next(r for r in _gap if r["year"] == "1980")
if not _1980["payload_blank_class_ingredients"].startswith("DEXTROSE; HYDROCORTISONE; LEUCOVORIN CALCIUM"):
    errors.append("pre1985_nme_gap_analysis 1980: blank-class ingredient inventory drift")
_1985 = next(r for r in _gap if r["year"] == "1985")
if "NDA018949 Seldane" not in _1985["payload_invisible_apps_known"]:
    errors.append("pre1985_nme_gap_analysis 1985: payload-invisible application list lost Seldane")
_match_years = [r["year"] for r in _cross if r["verdict"] == "MATCH"]
if len(_match_years) != 17:
    errors.append(f"crosswalk: MATCH years changed to {len(_match_years)} ({_match_years})")
for _r in _cross:
    if _r["official_nmes_approved"] == "":
        continue
    if _r["nme_comparable_rows"] == "":
        errors.append(f"crosswalk {_r['year']}: NME-comparable count missing")
    elif _r["verdict"] in ("MATCH", "PROJECT_SHORT_FLAGGED", "PROJECT_EXCEEDS_OFFICIAL") and \
            int(_r["delta_nme_comparable_vs_official"]) != \
            int(_r["nme_comparable_rows"]) - int(_r["official_nmes_approved"]):
        errors.append(f"crosswalk {_r['year']}: NME-comparable verdict/delta arithmetic broken")
if len(_caps) != 12:
    errors.append(f"pre1985_primary_captures_index: expected 12 live captures, got {len(_caps)}")
if len(_probe) != 1 or "pre-1980" not in _probe[0]["project_implication"]:
    errors.append("pre1980_openfda_probe: the feasibility probe row is missing or malformed")

# The three FDA sources must stay in the committed captures (no unsourced numbers).
for _name in ("fda_history_nda_nme_approvals_1938_2022.json",
              "fda_nme_compilation_landing_2026_09_19.json",
              "live_primary_captures_2026_09_19.json",
              "manifest.json"):
    _p = DATA / "raw" / "source_captures_2026_09_19" / _name
    if not _p.exists():
        errors.append(f"source_captures_2026_09_19: missing {_name}")

# v17 annotations: the dated note must be present on the rows the captures touch.
_v17_marker = "v17 (2026-09-19)"
_by_id = {r["decision_id"]: r for r in master}
for _did in ("D1030", "D1038", "D1040", "D1042", "D1047"):
    if _v17_marker not in (_by_id.get(_did, {}).get("notes") or ""):
        errors.append(f"master {_did}: v17 dated adjudication note missing")
if "CDER.NMENewBiologicApprovals@fda.hhs.gov" not in _by_id["D1040"]["notes"]:
    errors.append("master D1040: v17 note lost the CDER error-reporting route")
_r22046 = next((r for r in orig if (r.get("application_number") or "").strip().replace(" ", "") == "NDA022046"), None)
if _r22046 is None or _v17_marker not in (_r22046.get("notes") or ""):
    errors.append("orig: NDA022046 lost its v17 adjudication note")

# v17.1: the note clause that v17 proved false must be gone, and every row that
# carried it must point at the official year series instead.
_stale_clause = "no CDER NME year table was published"
_resolved = "v17 (2026-09-19): FDA's official NME year series"
_stale_rows = [r["decision_id"] for r in master if _stale_clause in (r.get("notes") or "")]
if _stale_rows:
    errors.append(f"master: {len(_stale_rows)} rows still carry the superseded "
                  f"'no CDER NME year table was published' clause (e.g. {_stale_rows[:3]})")
_resolved_rows = [r["decision_id"] for r in master if _resolved in (r.get("notes") or "")]
if len(_resolved_rows) != 390:
    errors.append(f"master: {len(_resolved_rows)} rows carry the official-year-series resolution "
                  "sentence, expected 390")
_bad_pointer = [r["decision_id"] for r in master if _resolved in (r.get("notes") or "")
                and "data/fda_official_series_crosswalk.csv" not in r["notes"]]
if _bad_pointer:
    errors.append(f"master: {len(_bad_pointer)} resolution notes lost the crosswalk pointer "
                  f"(e.g. {_bad_pointer[:3]})")

# The era table's official-count columns must agree with the gap analysis.
_era = read("pre1985_era_analysis.csv")
_era_by_year = {r["year"]: r for r in _era}
for _r in _gap:
    _e = _era_by_year.get(_r["year"], {})
    if _e.get("official_fda_nme_count") != _r["official_nmes_approved"]:
        errors.append(f"pre1985_era_analysis {_r['year']}: official_fda_nme_count "
                      f"{_e.get('official_fda_nme_count')!r} != gap analysis {_r['official_nmes_approved']!r}")
    if _e.get("official_series_delta") != _r["effective_type1_shortfall_negative_is_short"]:
        errors.append(f"pre1985_era_analysis {_r['year']}: official_series_delta "
                      f"{_e.get('official_series_delta')!r} != gap analysis "
                      f"{_r['effective_type1_shortfall_negative_is_short']!r}")
warnings.append(f"v17: {len(_short)} years remain short of FDA's official NME count "
                f"({', '.join(_short)}) - sized and flagged, not hidden")

print(f"Validated {len(master)} FDA novel-approval rows, {len(suppl)} efficacy-supplement rows, "
      f"{len(orig)} original non-NME rows (incl. {sum(_pre_orig_years.values())} v15/v16 pre-1985 rows), "
      f"{len(focus)} focus-year audit rows (1980-1985), {len(oscores)} orig scorecards, "
      f"{len(t1gap)} Type-1-gap flags, "
      f"{len(exp)} label-expansion scorecards, {len(audit)} cross-check rows, "
      f"{len(scores)} company scorecards, {len(prices)} price snapshots, "
      f"{len(crl)} CRL rows (+{len(new_crl)} new from the openFDA CRL database), "
      f"{len(ctgov)} ClinicalTrials.gov Phase 3 rows, {len(clin_scores)} clinical trial scorecards, "
      f"{len(_pre1985_decisions)} pre-1985 decisions, {len(_pre1985_era)} pre-1985 era rows, "
      f"{len(_series)} official-series rows, {len(_cross)} crosswalk rows, {len(_gap)} NME-gap rows, "
      f"and {len(_caps)} live primary captures.")
print(f"Warnings requiring manual review: {len(warnings)}")
for w in warnings[:12]: print("WARNING", w)
if len(warnings) > 12: print(f"WARNING ... {len(warnings)-12} more")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors: print("ERROR", e)
    sys.exit(1)
print("PASS: schema, IDs, dates, ranges, and source URL checks succeeded.")
