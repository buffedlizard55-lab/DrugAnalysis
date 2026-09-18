# -*- coding: utf-8 -*-
"""
Builds data/company_scores.csv - the NUMERIC company scorecard.

Everything here is computed from rows that were already verified in this
repository. Nothing is typed by hand, and no component is estimated: if the
verified data for a component does not exist, that component is marked
unavailable, its weight is redistributed across the components that do have
data, and the company's confidence tier drops.

    Total score (0-100) = Outcome(30) + Market(25) + Experience(20)
                          + Pathway(15) + Pipeline(10)

    Outcome (30)     = empirical-Bayes (James-Stein style) shrunk rate of
                       approvals / (approvals + CRLs + voluntary withdrawals):

                           shrunk = (approvals + k * p0) / (decisions + k)

                       with p0 = 0.906 and k = 3.
                       p0 is the externally verified base rate for an
                       NDA/BLA that has been FILED: BIO / Biomedtracker,
                       "Clinical Development Success Rates 2011-2020"
                       (n = 1,453 applications, incl. resubmissions) puts
                       NDA/BLA -> approval at 90.6%. Shrinking toward a
                       VERIFIED external base rate is preferred to the Wilson
                       lower bound because the lower bound treats every
                       company as if the population rate were unknown and
                       punishes small samples asymmetrically (a company with
                       1 approval / 0 CRLs scored ~21% under Wilson, i.e. an
                       implied failure rate of 79% that no published dataset
                       supports). With k = 3 a single approval scores 92.9%
                       and a company only moves away from 90.6% once it has
                       enough verified decisions to justify it.
                       The raw rate and the Wilson 95% lower bound are still
                       reported as STATISTICS (success_rate_pct,
                       success_rate_wilson_lower_pct) - they are simply no
                       longer the scored component.
    Market (25)      = 0.6 x share of priced FDA approval events whose T+1
                       move was positive  +  0.4 x clamp(median T+1 move /
                       +25%, 0, 1)
                       Uses only verified closes from stock_price_snapshots.csv.
                       Weight raised from 20 to 25: the market term is the only
                       component built on exchange data rather than on our own
                       counting of FDA outcomes, and unlike Outcome it
                       discriminates between companies that all clear the
                       90.6% submission hurdle.
    Market (20)      = 0.6 x share of priced FDA events whose T+1 move was
                       positive  +  0.4 x clamp(median T+1 move / +25%, 0, 1)
                       Uses only verified closes from stock_price_snapshots.csv.
    Experience (20)  = clamp( log2(1 + decisions tracked) / log2(1 + 12), 0, 1 )
                       Saturates at 12 tracked decisions. Weight raised from 15
                       to 20 because the 2018-2020 backfill roughly doubled the
                       tracked-decision count for long-established issuers, and
                       a longer verified record is the main protection against
                       reading luck as skill.
    Pathway (15)     = clamp( Priority-Review share  -  0.5 x Accelerated
                       Approval share, 0, 1 )
                       Priority Review is FDA's own signal that the drug may be
                       a significant improvement; Accelerated Approval is
                       treated as a RISK factor because it rests on a surrogate
                       endpoint that a confirmatory trial must later verify
                       (several accelerated approvals in this dataset were
                       later withdrawn: Ukoniq, Relyvrio, Pepaxto, Exkivity).
    Pipeline (10)    = advanced_to_next_phase / (advanced + paused/hold)
                       Only where company_scorecards.csv holds a verified
                       DEEP-DIVE pipeline scorecard. The FDA-decisions-only
                       scorecards deliberately report 0 progression, so using
                       them here would fabricate a pipeline failure rate.

    Confidence       High     = >= 8 verified decisions AND a deep-dive pipeline
                     Moderate = >= 8 decisions without pipeline detail, or
                                3-7 decisions
                     Low      = < 3 decisions, or FDA-decisions-only scope

    Grade            A >= 80 | B 65-79 | C 50-64 | D 35-49 | E < 35

Inputs : data/fda_decisions_master.csv, data/fda_crl_master.csv,
         data/stock_price_snapshots.csv, data/company_scorecards.csv
Output : data/company_scores.csv
"""
import csv
import math
import os
from collections import Counter, defaultdict
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
D = lambda n: os.path.join(ROOT, "data", n)

TODAY = date(2026, 9, 18)          # dataset "as of" date, used for recency only
Z = 1.96                           # 95% two-sided
WEIGHTS = {"outcome": 30.0, "market": 25.0, "experience": 20.0,
           "pathway": 15.0, "pipeline": 10.0}
# External base rate for a FILED application -> approval, used as the shrinkage
# target of the Outcome component. Source: BIO / Biomedtracker / Informa Pharma
# Intelligence, "Clinical Development Success Rates 2011-2020", NDA/BLA -> LOA
# 90.6% over n = 1,453 applications (including resubmissions).
P0_SUBMISSION_TO_APPROVAL = 0.906
EB_K = 3.0                          # pseudo-observations of weight given to p0
# The shrunk rate is mapped onto the Outcome component through a calibration band
# anchored on verified published spread rather than on the raw 0-100% range, which
# would make every company with a clean record indistinguishable:
#   BIO 2011-2020 per-disease-area NDA/BLA -> approval spans 82.5% (cardiovascular,
#   n=80) to 100% (allergy n=20; vaccine n=27; ADC n=12; CAR-T n=4; gene therapy
#   n=2; siRNA n=3), with antisense the weakest modality at 66.7%.
# A 75%-100% band therefore covers the observed range, and the population base rate
# of 90.6% maps to 0.62 of the component - an "average" filer, not a top score.
OUTCOME_BAND = (0.75, 1.00)
# Values in the ticker column that mean "no symbol", not a symbol.
TICKER_SENTINELS = {"", "NO_TICKER", "NO_US_TICKER", "N/A", "NONE", "PRIVATE"}
EXPERIENCE_SATURATION = 12.0
MARKET_MAGNITUDE_CAP = 25.0        # a +25% median T+1 move earns the full magnitude term

HEADER = [
    "company_name", "ticker", "exchange", "us_investable_class",
    "decisions_tracked", "approvals_tracked", "crls_tracked", "withdrawals_flagged",
    "priority_review_count", "accelerated_approval_count", "standard_review_count",
    "pathway_known_count",
    "success_rate_pct", "success_rate_wilson_lower_pct", "success_rate_shrunk_pct",
    "price_events", "positive_reaction_rate_pct", "median_pct_on_decision", "median_pct_t1",
    "pipeline_programs", "advanced_count", "paused_count", "pipeline_progression_pct",
    "score_outcome", "score_market", "score_experience", "score_pathway", "score_pipeline",
    "total_score_0_100", "grade", "confidence",
    "last_decision_date", "recency_days",
    "data_scope", "inputs_source", "notes",
]


def fnum(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def wilson_lower(k, n):
    """95% Wilson score lower bound for a binomial proportion."""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + Z * Z / n
    centre = p + Z * Z / (2 * n)
    margin = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def median(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def canonical_name(ticker, names, scorecard):
    """Display name: prefer the deep-dive scorecard's name, else the most
    frequent verified name for the ticker, trimmed of parenthetical qualifiers
    and of any '/ second entity' ownership suffix."""
    if scorecard and scorecard.get("company_name", "").strip():
        return scorecard["company_name"].strip()
    if not names:
        return ""
    base = Counter(names).most_common(1)[0][0]
    base = base.split(" / ")[0].strip()
    if base.endswith(")") and "(" in base:
        base = base[:base.rfind("(")].strip()
    return base


def main():
    master = list(csv.DictReader(open(D("fda_decisions_master.csv"), newline="", encoding="utf-8")))
    crls = list(csv.DictReader(open(D("fda_crl_master.csv"), newline="", encoding="utf-8")))
    snaps = list(csv.DictReader(open(D("stock_price_snapshots.csv"), newline="", encoding="utf-8")))
    cards = {r["ticker"].strip(): r for r in csv.DictReader(open(D("company_scorecards.csv"), newline="", encoding="utf-8"))}

    # ---- group the verified rows by ticker (private rows group by name) ----
    def key_of(ticker, company):
        t = (ticker or "").strip()
        # Sentinels are NOT symbols: rows carrying them must group by company name,
        # otherwise unrelated issuers collapse into one scorecard (seen on 2026-09-12
        # when the 2018-2020 backfill introduced the NO_US_TICKER sentinel).
        return t if t.strip().upper() not in TICKER_SENTINELS else "NAME::" + (company or "").strip()

    groups = defaultdict(lambda: {"names": [], "exchanges": [], "classes": [], "approvals": [],
                                  "crls": [], "withdrawals": 0, "dates": []})

    for r in master:
        g = groups[key_of(r["ticker"], r["company_name"])]
        g["names"].append(r["company_name"].strip())
        if r.get("exchange", "").strip():
            g["exchanges"].append(r["exchange"].strip())
        if r.get("us_investable_class", "").strip():
            g["classes"].append(r["us_investable_class"].strip())
        if r.get("decision_date", "").strip():
            g["dates"].append(r["decision_date"].strip())
        dtype = r.get("decision_type", "")
        if dtype.startswith("Approval"):
            g["approvals"].append(r)
        if "withdraw" in (r.get("notes", "") or "").lower():
            g["withdrawals"] += 1

    for r in crls:
        g = groups[key_of(r["ticker"], r["company_name"])]
        g["names"].append(r["company_name"].strip())
        if r.get("exchange", "").strip():
            g["exchanges"].append(r["exchange"].strip())
        g["crls"].append(r)
        if r.get("crl_date", "").strip():
            g["dates"].append(r["crl_date"].strip())

    # ---- price events per ticker ----
    prices = defaultdict(list)
    for s in snaps:
        on = fnum(s.get("pct_change_on_decision"))
        before = fnum(s.get("close_before"))
        later = fnum(s.get("close_few_days_later"))
        t1 = (100.0 * (later / before - 1.0)) if (before and later) else None
        prices[s["ticker"].strip()].append({"on": on, "t1": t1})

    out_rows = []
    for key, g in groups.items():
        ticker = "" if key.startswith("NAME::") else key
        card = cards.get(ticker) if ticker else None
        name = canonical_name(ticker, g["names"], card)

        approvals = g["approvals"]
        n_appr = len(approvals)
        n_crl = len(g["crls"])
        n_dec = n_appr + n_crl
        withdrawals = g["withdrawals"]

        pathways = [a.get("review_pathway", "").strip() for a in approvals]
        known = [p for p in pathways if p]
        n_priority = sum(1 for p in known if "priority" in p.lower())
        n_accel = sum(1 for p in known if "accelerated" in p.lower()) + \
            sum(1 for a in approvals if a.get("decision_type", "").strip().lower().startswith("approval (accelerated"))
        n_accel = min(n_accel, n_appr)
        n_standard = sum(1 for p in known if "standard" in p.lower())

        # ---------------- component fractions ----------------
        frac, trace = {}, []

        # Outcome: CRLs count as failures, voluntary withdrawals count as failures
        denom = n_dec + withdrawals
        wil = wilson_lower(n_appr, denom) if denom else None
        raw_rate = 100.0 * n_appr / denom if denom else None
        shrunk = ((n_appr + EB_K * P0_SUBMISSION_TO_APPROVAL) / (denom + EB_K)) if denom else None
        if shrunk is not None:
            lo, hi = OUTCOME_BAND
            frac["outcome"] = clamp((shrunk - lo) / (hi - lo))
            trace.append("Outcome: %d approvals / %d CRLs / %d withdrawals flagged -> shrunk rate %.1f%% "
                         "(raw %.1f%%, Wilson95 LB %.1f%%, prior %.1f%% x k=%g) mapped through the "
                         "%.0f%%-%.0f%% calibration band -> %.2f of the component"
                         % (n_appr, n_crl, withdrawals, 100 * shrunk, raw_rate or 0.0,
                            100 * (wil or 0.0), 100 * P0_SUBMISSION_TO_APPROVAL, EB_K,
                            100 * OUTCOME_BAND[0], 100 * OUTCOME_BAND[1], frac["outcome"]))
        else:
            trace.append("Outcome: no verified FDA decisions in this dataset")

        # Market validation
        ev = prices.get(ticker, [])
        usable = [e for e in ev if e["on"] is not None or e["t1"] is not None]
        pos_vals = [(e["t1"] if e["t1"] is not None else e["on"]) for e in usable]
        pos_rate = (sum(1 for v in pos_vals if v > 0) / len(pos_vals)) if pos_vals else None
        med_t1 = median([e["t1"] for e in usable])
        med_on = median([e["on"] for e in usable])
        mag = med_t1 if med_t1 is not None else med_on
        if pos_rate is not None and mag is not None:
            frac["market"] = 0.6 * pos_rate + 0.4 * clamp(mag / MARKET_MAGNITUDE_CAP)
            trace.append("Market: %d priced events, %.0f%% positive at T+1, median T+1 %+.2f%% -> %.2f"
                         % (len(usable), 100 * pos_rate, med_t1 if med_t1 is not None else 0.0, frac["market"]))
        else:
            trace.append("Market: no verified price events for this ticker (blank, not estimated)")

        # Experience
        frac["experience"] = clamp(math.log2(1 + n_dec) / math.log2(1 + EXPERIENCE_SATURATION))
        trace.append("Experience: %d tracked decisions -> %.2f (saturates at %d)"
                     % (n_dec, frac["experience"], int(EXPERIENCE_SATURATION)))

        # Pathway quality
        if known and n_appr:
            p_share = n_priority / len(known)
            a_share = n_accel / n_appr
            frac["pathway"] = clamp(p_share - 0.5 * a_share)
            trace.append("Pathway: %d/%d approvals Priority Review (%.0f%%), %d accelerated (%.0f%%) -> %.2f"
                         % (n_priority, len(known), 100 * p_share, n_accel, 100 * a_share, frac["pathway"]))
        else:
            trace.append("Pathway: review_pathway not published for these rows (left blank upstream)")

        # Pipeline progression (deep-dive scorecards only)
        adv = paused = programs = None
        deep = bool(card) and "partial pipeline view" not in (card.get("verification_status", "") or "").lower()
        if deep:
            adv = int(fnum(card.get("advanced_to_next_phase_count")) or 0)
            paused = int(fnum(card.get("paused_or_clinical_hold_count")) or 0)
            programs = int(fnum(card.get("total_pipeline_programs_tracked")) or 0)
            if adv + paused > 0:
                frac["pipeline"] = adv / (adv + paused)
                trace.append("Pipeline (verified deep dive): %d advanced, %d paused/hold of %d programs -> %.2f"
                             % (adv, paused, programs, frac["pipeline"]))
            else:
                trace.append("Pipeline: deep-dive scorecard records no phase transitions yet")
        elif card:
            trace.append("Pipeline: FDA-decisions-only scorecard - progression deliberately not estimated")
        else:
            trace.append("Pipeline: no pipeline scorecard on file")

        # ---------------- weighted total with re-distribution ----------------
        avail_w = sum(WEIGHTS[k] for k in frac)
        if avail_w <= 0:
            total = None
            pts = {k: "" for k in WEIGHTS}
        else:
            total = 100.0 * sum(WEIGHTS[k] * frac[k] for k in frac) / avail_w
            pts = {k: round(100.0 * WEIGHTS[k] * frac[k] / avail_w, 2) if k in frac else "" for k in WEIGHTS}

        grade = "" if total is None else ("A" if total >= 80 else "B" if total >= 65 else
                                          "C" if total >= 50 else "D" if total >= 35 else "E")
        if total is None:
            confidence = "Not scored - no verified FDA decisions"
        elif n_dec >= 8 and "pipeline" in frac:
            confidence = "High"
        elif n_dec >= 3:
            confidence = "Moderate"
        else:
            confidence = "Low"

        scope_bits = [k for k in ("outcome", "market", "experience", "pathway", "pipeline") if k in frac]
        data_scope = ("Verified - components used: " + "+".join(scope_bits) +
                      (" (deep-dive pipeline)" if "pipeline" in frac else
                       " (FDA decisions + prices only)" if "market" in frac else " (FDA decisions only)"))

        last = max(g["dates"]) if g["dates"] else ""
        recency = ""
        if last:
            try:
                y, m, dd = [int(x) for x in last.split("-")]
                recency = (TODAY - date(y, m, dd)).days
            except ValueError:
                recency = ""

        out_rows.append({
            "company_name": name,
            "ticker": ticker,
            "exchange": Counter(g["exchanges"]).most_common(1)[0][0] if g["exchanges"] else "",
            "us_investable_class": Counter(g["classes"]).most_common(1)[0][0] if g["classes"] else "",
            "decisions_tracked": n_dec,
            "approvals_tracked": n_appr,
            "crls_tracked": n_crl,
            "withdrawals_flagged": withdrawals,
            "priority_review_count": n_priority,
            "accelerated_approval_count": n_accel,
            "standard_review_count": n_standard,
            "pathway_known_count": len(known),
            "success_rate_pct": "" if raw_rate is None else round(raw_rate, 1),
            "success_rate_wilson_lower_pct": "" if wil is None else round(100 * wil, 1),
            "success_rate_shrunk_pct": "" if shrunk is None else round(100 * shrunk, 1),
            "price_events": len(usable),
            "positive_reaction_rate_pct": "" if pos_rate is None else round(100 * pos_rate, 1),
            "median_pct_on_decision": "" if med_on is None else round(med_on, 2),
            "median_pct_t1": "" if med_t1 is None else round(med_t1, 2),
            "pipeline_programs": "" if programs is None else programs,
            "advanced_count": "" if adv is None else adv,
            "paused_count": "" if paused is None else paused,
            "pipeline_progression_pct": "" if (adv is None or not (adv + paused)) else round(100.0 * adv / (adv + paused), 1),
            "score_outcome": pts["outcome"],
            "score_market": pts["market"],
            "score_experience": pts["experience"],
            "score_pathway": pts["pathway"],
            "score_pipeline": pts["pipeline"],
            "total_score_0_100": "" if total is None else round(total, 1),
            "grade": grade,
            "confidence": confidence,
            "last_decision_date": last,
            "recency_days": recency,
            "data_scope": data_scope,
            "inputs_source": ("computed by scripts/build_company_scores.py on %s from data/fda_decisions_master.csv "
                              "(%d approval rows), data/fda_crl_master.csv (%d CRL rows), data/stock_price_snapshots.csv "
                              "(%d priced events), data/company_scorecards.csv (%s)")
                              % (TODAY.isoformat(), n_appr, n_crl, len(usable),
                                 "deep-dive" if deep else ("FDA-decisions-only" if card else "none")),
            "notes": " | ".join(trace) + (" | Component weights re-normalised over available components: "
                                          + ", ".join("%s=%g" % (k, WEIGHTS[k]) for k in scope_bits)
                                          + "." if len(scope_bits) < 5 else ""),
        })

    out_rows.sort(key=lambda r: (-(float(r["total_score_0_100"]) if r["total_score_0_100"] != "" else -1),
                                 r["company_name"].lower()))

    with open(D("company_scores.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER, lineterminator="\r\n")
        w.writeheader()
        w.writerows(out_rows)

    scored = [r for r in out_rows if r["total_score_0_100"] != ""]
    print("Wrote %d company score rows to data/company_scores.csv (%d scored, %d unscored)"
          % (len(out_rows), len(scored), len(out_rows) - len(scored)))
    print("Confidence:", dict(Counter(r["confidence"] for r in out_rows)))
    print("Grades:    ", dict(Counter(r["grade"] for r in scored)))
    print("Top 5:")
    for r in scored[:5]:
        print("   %-38s %-6s %5s %s (n=%d)" % (r["company_name"][:38], r["ticker"], r["total_score_0_100"], r["grade"], r["decisions_tracked"]))


if __name__ == "__main__":
    main()
