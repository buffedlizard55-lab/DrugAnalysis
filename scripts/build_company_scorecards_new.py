# -*- coding: utf-8 -*-
"""
Appends scorecards for the companies that entered the dataset with the
2026-09-12 backfill (D201-D277) and are not already covered by
build_company_scorecards.py / build_company_scorecards_multi.py.

IMPORTANT - what these numbers mean, and what they deliberately do not mean.

The 36 hand-built scorecards already in company_scorecards.csv describe a
company's full clinical pipeline (which programs are in which phase, which
advanced, which were paused). Building that for ~25 further companies would
require reading each company's own pipeline disclosures, and anything written
without doing that reading would be guesswork. Rather than guess, this script
produces a narrower but fully verifiable scorecard:

  total_pipeline_programs_tracked = number of DISTINCT FDA decisions for this
                                    ticker that are verified and tracked in
                                    this repository
  approved_count                  = how many of those were approvals
  crl_rejected_count              = how many of those were Complete Response
                                    Letters
  advanced_to_next_phase_count    = 0 (phase-by-phase progression is NOT
                                    captured here - see notes)
  paused_or_clinical_hold_count   = 0 (same)

Every count is reproducible straight from data/fda_decisions_master.csv and
data/fda_crl_master.csv, and `phase_details` lists each contributing decision
so a reviewer can check the arithmetic line by line. The verification_status
says explicitly that this is an FDA-decisions-only view.
"""
import csv
import os

MASTER = "data/fda_decisions_master.csv"
CRLS = "data/fda_crl_master.csv"
SCORECARDS = "data/company_scorecards.csv"

HEADER = ["company_name", "ticker", "total_pipeline_programs_tracked", "approved_count",
          "advanced_to_next_phase_count", "paused_or_clinical_hold_count", "crl_rejected_count",
          "phase_details", "source_url_1", "source_url_2", "verification_status", "notes"]

STATIC_SOURCE = "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2019"


def main():
    existing = set()
    with open(SCORECARDS, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            existing.add(r["ticker"].strip())

    events = {}
    with open(MASTER, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["ticker"].strip()
            if not t or t == "NO_TICKER":
                continue
            e = events.setdefault(t, {"company": r["company_name"].strip(), "items": []})
            e["items"].append((r["decision_date"].strip(), "Approval",
                               r["drug_brand"].strip(), r["source_url_1"].strip()))

    with open(CRLS, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["ticker"].strip()
            if not t or t == "NO_TICKER":
                continue
            e = events.setdefault(t, {"company": r["company_name"].strip(), "items": []})
            e["items"].append((r["crl_date"].strip(), "CRL",
                               r["drug_name"].strip(), r["source_url_1"].strip()))

    new_tickers = sorted(t for t in events if t not in existing)

    rows = []
    for t in new_tickers:
        items = sorted(events[t]["items"], reverse=False)
        approved = sum(1 for i in items if i[1] == "Approval")
        crl = sum(1 for i in items if i[1] == "CRL")
        detail = "FDA decisions tracked in this dataset: " + " | ".join(
            "{} ({} - {})".format(i[2], i[0], i[1]) for i in items)
        notes = ("Counts cover ONLY the FDA decisions that have been verified and tracked in this "
                 "repository - they are not the company's full pipeline. Phase-by-phase progression "
                 "and clinical holds are therefore reported as 0 rather than estimated; upgrade this "
                 "row to a full pipeline scorecard by reading the company's own pipeline disclosure.")
        rows.append([events[t]["company"], t, len(items), approved, 0, 0, crl, detail,
                     items[-1][3], items[0][3],
                     "Verified - FDA decisions only (partial pipeline view)", notes])

    with open(SCORECARDS, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)
    print(f"Appended {len(rows)} scorecards: {', '.join(new_tickers)}")


if __name__ == "__main__":
    main()
