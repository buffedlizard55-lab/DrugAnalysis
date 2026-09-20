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
  company_score / _grade / _confidence
                                  -> the NUMERIC company scorecard from
                                     data/company_scores.csv (see
                                     scripts/build_company_scores.py for the
                                     formula). Blank where no verified FDA
                                     decision exists for that entity.
  us_investable_class             -> scope filter: US-LISTED / US-LISTED (ADR) /
                                     FORMERLY US-LISTED / NON-US LISTING ONLY /
                                     PRIVATE / NO EQUITY
  flags                           -> rows that need manual review

Fix applied 2026-09-12: the CRL loop previously looked the price snapshot up
with `d["decision_date"]` (the last APPROVAL row's date) instead of
`c["crl_date"]`, so every CRL row matched the wrong snapshot or none at all.
"""
import csv
import re

decisions = list(csv.DictReader(open("data/fda_decisions_master.csv")))
crls = list(csv.DictReader(open("data/fda_crl_master.csv")))
snapshots = {(r["ticker"], r["decision_date"]): r
             for r in csv.DictReader(open("data/stock_price_snapshots.csv"))}
scorecards = {r["ticker"]: r for r in csv.DictReader(open("data/company_scorecards.csv"))}

# numeric company scorecard (scripts/build_company_scores.py)
_scores = list(csv.DictReader(open("data/company_scores.csv")))
scores_by_ticker = {r["ticker"].strip(): r for r in _scores if r["ticker"].strip()}
scores_by_name = {r["company_name"].strip().lower(): r for r in _scores if not r["ticker"].strip()}

# Ticker-column values that mean "no symbol", not a symbol. Mirrors
# TICKER_SENTINELS in scripts/build_company_scores.py, which was already fixed for
# this during the 2018-2020 backfill. The core table used to exclude only
# "NO_TICKER", so the 14 rows carrying the NO_US_TICKER sentinel - ELEVEN
# unrelated companies (Fresenius Kabi, Kyowa Kirin x2, Almirall x2, Clinuvel,
# SK Life Science, Lundbeck, Recordati, Nippon Shinyaku, Actelion, Allergan x2,
# Forest Laboratories) - were joined as if they were one security:
#   * all 14 published Fresenius Kabi's pipeline card as their
#     company_success_rate_summary ("14/14 tracked programs approved");
#   * all 14 inherited the first such row's class (D345 Fresenius Kabi, NON-US
#     LISTING ONLY) through class_by_ticker, contradicting the master's own
#     committed class on 4 of them - Allergan D442/D452 are US-LISTED, Actelion
#     D425 and Forest D627 are PRIVATE / NO EQUITY. That is the exact
#     "ticker/class irregularity" v10 flagged notes-only; the cause is this join.
#   * 6 of them (Kyowa Kirin x2, Almirall x2, Clinuvel, Nippon Shinyaku) have
#     their own name-keyed row in company_scores.csv but were denied it, because
#     the sentinel is truthy so the name fallback never ran.
# Fixed 2026-09-18 (v11). Repo law: corrections belong in builders.
TICKER_SENTINELS = {"", "NO_TICKER", "NO_US_TICKER", "N/A", "NONE", "PRIVATE"}


def real_ticker(t):
    """The ticker if it identifies a security, otherwise '' (blank/sentinel)."""
    t = (t or "").strip()
    return "" if t in TICKER_SENTINELS else t


# a sentinel-keyed scorecard belongs to the company named on it, not to every row
# that happens to share the sentinel (there is exactly one such card today:
# NO_US_TICKER -> Fresenius Kabi)
scorecards_by_name = {(r["company_name"] or "").strip().lower(): r
                      for r in scorecards.values() if not real_ticker(r["ticker"])}

# verified US-investability class per ticker (scripts/classify_listing.py)
class_by_ticker = {}
for r in decisions:
    t = real_ticker(r["ticker"])
    if t:
        class_by_ticker.setdefault(t, r.get("us_investable_class", ""))


def score_cells(ticker, company):
    """(score, grade, confidence, class) for a decision row."""
    t = real_ticker(ticker)
    s = scores_by_ticker.get(t) if t else scores_by_name.get((company or "").strip().lower())
    cls = class_by_ticker.get(t, "") if t else ""
    if not s:
        return "", "", "Not scored - no verified FDA decisions tracked", cls
    return (s["total_score_0_100"], s["grade"], s["confidence"], cls or s.get("us_investable_class", ""))

HEADER = ["company_name", "ticker", "drug_name", "decision_type", "decision_date",
          "indication", "review_pathway",
          "stock_price_before", "stock_price_after", "pct_change",
          "price_t1", "pct_change_t1",
          "price_data_status", "company_success_rate_summary",
          "company_score", "company_score_grade", "company_score_confidence",
          "us_investable_class",
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


def summary_for(ticker, company=""):
    """Pipeline summary for the row's own company. A sentinel ticker is not a
    lookup key: fall back to the name-keyed sentinel cards (see TICKER_SENTINELS)."""
    t = real_ticker(ticker)
    sc = scorecards.get(t) if t else scorecards_by_name.get((company or "").strip().lower())
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
    score, grade, conf, cls = score_cells(t, d["company_name"])
    rows.append([
        d["company_name"], t, f"{d['drug_brand']} ({d['drug_generic']})",
        d["decision_type"], d["decision_date"], d["indication"], d.get("review_pathway", ""),
        before, after, pct, t1, t1_pct, status, summary_for(t, d["company_name"]),
        score, grade, conf, cls or d.get("us_investable_class", ""),
        d["source_url_1"], d.get("source_url_2", ""),
        flag_of(d["verification_status"], d.get("notes", "")), d["verification_status"],
    ])

for c in crls:
    t = c["ticker"]
    snap = snapshots.get((t, c["crl_date"]))          # <- was d["decision_date"] (bug)
    before, after, pct, t1, t1_pct, status = price_cells(snap, t)
    score, grade, conf, cls = score_cells(t, c["company_name"])
    rows.append([
        c["company_name"], t, c["drug_name"],
        "Complete Response Letter (Rejection)", c["crl_date"], c["indication"], "",
        before, after, pct, t1, t1_pct, status, summary_for(t, c["company_name"]),
        score, grade, conf, cls or c.get("us_investable_class", ""),
        c["source_url_1"], c.get("source_url_2", ""),
        flag_of(c["verification_status"], c.get("notes", "")), c["verification_status"],
    ])

# ---- v25 (2026-09-20): join the v24 openFDA backfill entries ---------------
# The 290 v24 rows in fda_original_non_nme_decisions.csv (marked "v24 backfill"
# in verification_status) are openFDA-verified ORIG/AP decisions. 242 of the 290
# are already present in fda_decisions_master.csv under the same drug_brand +
# decision_date, so they are already in this table through the master loop
# above; appending them again would double-count the same FDA decision. The
# rest (48 today) are joined here exactly once, with their openFDA provenance
# kept intact: no ticker is invented (blank until the ticker resolution pass
# fills it), no listing class is asserted (the row's UNRESOLVED class string is
# not a class), and no indication is invented (the openFDA original-approval
# extract carries no structured indication field - same convention as the
# pre-1985 rows). Fail-closed on the one case that would make the dedupe
# ambiguous: a v24 row sharing (company, date) with a master row under a
# DIFFERENT brand.
_orig = list(csv.DictReader(open("data/fda_original_non_nme_decisions.csv")))


def _norm_key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


_master_brand_date = {(_norm_key(d["drug_brand"]), d["decision_date"]) for d in decisions}
_master_company_date = {(_norm_key(d["company_name"]), d["decision_date"]) for d in decisions}
_v24_rows = [r for r in _orig if "v24 backfill" in (r.get("verification_status") or "").lower()]
# TYPE 1 / TYPE 1/4 are NME decisions: they read as approvals in the engine's
# statistics (which bucket on decision_type.startswith("Approval")). Every
# other class is labelled as a non-NME original so it never mixes into them.
_NME_CLASSES = {"TYPE 1", "TYPE 1/4"}
_v24_joined = 0
_v24_already = 0
for r in _v24_rows:
    dt = r["decision_date"]
    if (_norm_key(r["drug_brand"]), dt) in _master_brand_date:
        _v24_already += 1            # already in the table via its master row
        continue
    if (_norm_key(r["company_name"]), dt) in _master_company_date:
        raise SystemExit(
            f"FATAL v25 join: {r.get('orig_id')} ({r['drug_brand']}, {dt}) shares "
            "(company, date) with a master row under a different brand - ambiguous "
            "dedupe, needs human review before joining")
    t = real_ticker(r.get("ticker", ""))
    snap = snapshots.get((t, dt)) if t else None
    before, after, pct, t1, t1_pct, status = price_cells(snap, t)
    score, grade, conf, cls = score_cells(t, r["company_name"])
    # 22 of the 48 v24 rows carry no product name at all in the openFDA
    # payload; the application number is then the only verifiable identifier
    # (blank beats guessed), and a NO-PRODUCT-NAME flag marks the gap.
    brand = (r.get("drug_brand") or "").strip()
    generic = (r.get("drug_generic") or "").strip()
    if brand:
        drug = f"{brand} ({generic})" if generic else brand
    else:
        drug = r.get("application_number") or "UNKNOWN"
    # the row's own committed class, only if it is a real listing class
    own_cls = (r.get("us_investable_class") or "").strip()
    if own_cls.startswith("UNRESOLVED"):
        own_cls = ""
    ctype = (r.get("chemical_type_code") or "").strip()
    cdesc = (r.get("chemical_type_description") or "").strip()
    if ctype in _NME_CLASSES:
        dtype = f"Approval ({cdesc}; v24 openFDA backfill)"
    else:
        dtype = f"Original Approval (non-NME; {cdesc}; v24 openFDA backfill)"
    flags = flag_of(r.get("verification_status"), r.get("notes"))
    if not t:
        flags = (flags + "; " if flags else "") + "TICKER-UNRESOLVED"
    if not brand:
        flags = (flags + "; " if flags else "") + "NO-PRODUCT-NAME"
    rows.append([
        r["company_name"], t, drug,
        dtype, dt, "", r.get("review_priority", ""),
        before, after, pct, t1, t1_pct, status, summary_for(t, r["company_name"]),
        score, grade, conf, cls or own_cls,
        r.get("source_url_1", ""), r.get("source_url_2", ""),
        flags, r.get("verification_status", ""),
    ])
    _v24_joined += 1

# newest decisions first - the table is used as a forward-looking decision engine
rows.sort(key=lambda r: r[4], reverse=True)

with open("data/core_analysis_table.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(HEADER)
    w.writerows(rows)

matched = sum(1 for r in rows if str(r[12]).startswith("Verified"))
print(f"Wrote {len(rows)} core analysis rows ({matched} with verified price data)")
print(f"v25 join: {len(_v24_rows)} v24-backfill rows -> {_v24_joined} joined "
      f"(not in master), {_v24_already} already covered by the master")
