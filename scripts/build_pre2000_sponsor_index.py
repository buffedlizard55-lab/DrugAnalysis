#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-2000 sponsor-resolution index (manual-verification worklist).

Every 1996-2000 master row WITHOUT a verified ticker, plus the pre-2000 rows
whose verification_status flags the sponsor/equity as unresolved, becomes one
row of data/pre2000_sponsor_resolution_index.csv. Nothing here invents a
ticker: each row carries the legacy applicant string verbatim, the verified
lineage the master already records, a resolved/review status derived ONLY from
the row's own committed fields, and deterministic research links (SEC EDGAR
company search + Drugs@FDA + the FDA year enumeration) so a reviewer can
verify or resolve the listing in one click.

Repo law: blank beats guessed. Rows that the master already documents as
private/no-equity are marked NO-EQUITY (no action); rows whose lineage points
at a once-listed company are marked REVIEW (recoverable via EDGAR/Wayback).
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "fda_decisions_master.csv"
OUT = ROOT / "data" / "pre2000_sponsor_resolution_index.csv"
YEARS = ("1996", "1997", "1998", "1999", "2000")

HEADER = ["decision_id", "decision_date", "drug_brand", "drug_generic",
          "legacy_sponsor_verbatim", "lineage_recorded_in_master",
          "master_ticker", "master_exchange", "us_investable_class",
          "application_number", "status", "action_for_reviewer",
          "sec_edgar_company_search", "drugsatfda_link", "fda_year_enumeration",
          "priority"]

FORMERLY = "FORMERLY US-LISTED (DELISTED/ACQUIRED)"
NON_US = "NON-US LISTING ONLY"
PRIVATE = "PRIVATE / NO EQUITY"
UNVERIFIED = "NOT US-INVESTABLE (UNVERIFIED)"


def appl_of(row):
    m = (re.search(r"varApplNo=(\d{5,6})", row["source_url_1"])
         or re.search(r"applno(?:%3D|=)(\d{5,6})",
                      row["source_url_1"] + row["source_url_2"], re.I)
         or re.search(r"appl (?:N|BL)[ #]?(\d{5,6})", row["notes"], re.I)
         or re.search(r"(?:NDA|BLA)[ -]?(\d{5,6})", row["notes"][:160]))
    return m.group(1).zfill(6) if m else ""


def edgar_search_url(company):
    """EDGAR company browse by name (covers pre-2001 filers; full-text search
    only covers 2001+). Company name trimmed to the pre-lineage part."""
    name = re.split(r"\s*\(|; ", company)[0].strip()
    name = re.sub(r"[^A-Za-z0-9 &.\-]", " ", name).strip()
    from urllib.parse import quote
    return ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company="
            + quote(name) + "&type=10-K&dateb=20010101&owner=include&count=40")


def main():
    with MASTER.open(newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["decision_date"][:4] in YEARS]
    out = []
    for r in rows:
        cls = r["us_investable_class"]
        flagged = "FLAGGED" in r["verification_status"] and "sponsor" in r["verification_status"].lower()
        if r["ticker"].strip() and not flagged:
            continue  # verified ticker present -> not in scope
        lineage = ""
        m = re.search(r"\(([^()]*)\)", r["company_name"])
        if m:
            lineage = m.group(1)
        if cls == PRIVATE:
            status, action, prio = "NO-EQUITY (documented)", \
                "none - master documents private/government/non-profit issuer", "n/a"
        elif cls == UNVERIFIED:
            status, action, prio = "REVIEW (unresolved)", \
                "resolve issuer via EDGAR/Wayback; blank beats guessed", "medium"
        elif cls == FORMERLY:
            status, action, prio = "REVIEW (recoverable)", \
                "verify the decision-date ticker + delisting year from the period 10-K/20-F, " \
                "then normalise the exchange field to 'formerly <VENUE>:<TICKER>, delisted <YYYY>'", "high"
        elif cls == NON_US:
            status, action, prio = "REVIEW (foreign listing)", \
                "verify the primary non-US venue or the absence of any US line from the period annual report", "medium"
        else:
            status, action, prio = "REVIEW", "verify issuer equity", "low"
        year = r["decision_date"][:4]
        enum_url = ("https://www.fda.gov/media/177921/download?attachment" if year in ("1996", "1997")
                    else "see data/fda_year_source_register.csv row " + year)
        out.append({
            "decision_id": r["decision_id"], "decision_date": r["decision_date"],
            "drug_brand": r["drug_brand"], "drug_generic": r["drug_generic"],
            "legacy_sponsor_verbatim": r["company_name"],
            "lineage_recorded_in_master": lineage,
            "master_ticker": r["ticker"], "master_exchange": r["exchange"],
            "us_investable_class": cls, "application_number": appl_of(r),
            "status": status, "action_for_reviewer": action,
            "sec_edgar_company_search": edgar_search_url(r["company_name"]),
            "drugsatfda_link": ("https://www.accessdata.fda.gov/scripts/cder/daf/"
                                "index.cfm?event=overview.process&varApplNo=" + appl_of(r)),
            "fda_year_enumeration": enum_url, "priority": prio,
        })
    out.sort(key=lambda x: (x["priority"], x["decision_date"]))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    print(f"wrote {len(out)} rows -> {OUT.name}")
    print(Counter(r["status"].split(" ")[0] for r in out).most_common())
    print(Counter(r["priority"] for r in out).most_common())
    return 0


if __name__ == "__main__":
    sys.exit(main())
