#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-2000 sponsor resolution, v10 pass (2026-09-18).

Applies the EDGAR evidence captured in data/staging/pre2000_sponsor_edgar_evidence.json
(fetched live 2026-09-18) to:

  1. data/pre2000_sponsor_resolution_index.csv - updates the 25 'REVIEW
     (recoverable)' rows: 18 rows get VENUE-VERIFIED status with direct
     filing-URL citations; Agouron is fully resolved (venue + ticker AGPH,
     correcting the v9 hand-off's wrong 'AGRN'); 4 companies (IVAX,
     Carter-Wallace, Block Drug) get located citations with exact next
     documents; 2 special cases (Athena/Elan, DuPont) get documented
     attribution paths.
  2. data/fda_decisions_master.csv - fills the exchange field on the 18
     evidence-backed rows (venue per the period 10-K; Agouron gets the full
     'formerly NASDAQ:AGPH, delisted 1999' form) and appends a dated note
     with the verbatim primary-source quote + replayable URL.

Nothing is guessed: ticker symbols are recorded ONLY where a fetched filing
states them (Agouron AGPH); all other symbols remain pending.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "data" / "staging" / "pre2000_sponsor_edgar_evidence.json"
INDEX = ROOT / "data" / "pre2000_sponsor_resolution_index.csv"
MASTER = ROOT / "data" / "fda_decisions_master.csv"
DATE = "2026-09-18"

VENUE_EXCHANGE = {  # what goes into master.exchange (plain-venue precedent in the data)
    "agouron_pharmaceuticals": "formerly NASDAQ:AGPH, delisted 1999 (Pfizer acquisition)",
    "warner_lambert": "NYSE (Warner-Lambert Co.; venue per FY1997 10-K, ticker pending)",
    "pharmacia_upjohn": "NYSE (Pharmacia & Upjohn Inc.; venue per FY1997/FY1999 10-Ks, ticker pending)",
    "roberts_pharmaceutical": "NASDAQ NMS (Roberts Pharmaceutical Corp.; venue per FY1996 10-K, ticker pending)",
    "cytogen": "NASDAQ NMS (Cytogen Corp; venue per FY1996 10-K, ticker pending)",
    "advanced_magnetics": "AMEX (Advanced Magnetics Inc.; venue per FY1996 10-K, ticker pending)",
    "immunomedics": "NASDAQ NMS (Immunomedics Inc.; venue per FY1996 10-K, ticker pending)",
    "gensia_sicor": "NASDAQ NMS (Gensia Sicor Inc.; venue per FY1997 10-K, ticker pending)",
    "neurex": "NASDAQ NMS (Neurex Corp; venue per FY1997 10-K, ticker pending)",
}
STATUS = {  # index status per company (controlled vocabulary for validate_data.py)
    "agouron_pharmaceuticals": "RESOLVED (venue+ticker per period 10-K)",
    "warner_lambert": "VENUE-VERIFIED (ticker pending)",
    "pharmacia_upjohn": "VENUE-VERIFIED (ticker pending)",
    "roberts_pharmaceutical": "VENUE-VERIFIED (ticker pending)",
    "cytogen": "VENUE-VERIFIED (ticker pending)",
    "advanced_magnetics": "VENUE-VERIFIED (ticker pending)",
    "immunomedics": "VENUE-VERIFIED (ticker pending)",
    "gensia_sicor": "VENUE-VERIFIED (ticker pending)",
    "neurex": "VENUE-VERIFIED (ticker pending)",
}
STATUS_DETAIL = {
    "agouron_pharmaceuticals": "venue Nasdaq National Market + ticker AGPH per FY1998 10-K Item 5 ('trades on The Nasdaq Stock Market under the symbol AGPH'); FY1998 Item 5 quarterly table covers Q1 1997 (decision quarter); delisting 1999 on Pfizer acquisition per lineage index, EDGAR 10-K series ends 1998 - consistent",
    "warner_lambert": "NYSE per FY1997 10-K cover 12(b) table; ticker + delisting year pending",
    "pharmacia_upjohn": "NYSE per FY1997 + FY1999 10-K covers; ticker + 2000 Monsanto/Pharmacia-Corp demerger year pending",
    "roberts_pharmaceutical": "NASDAQ NMS per FY1996 10-K cover + Item 5 (1996 quarterly price table covers the decision); ticker pending",
    "cytogen": "NASDAQ NMS per FY1996 10-K cover; 10-K also confirms ProstaScint FDA licensure 1996-10-28; ticker pending",
    "advanced_magnetics": "AMEX per FY1996 10-K cover (NOT Nasdaq as the v9 hand-off assumed); 10-K confirms both Feridex (Aug 1996) and GastroMARK (Dec 1996) approvals; ticker pending",
    "immunomedics": "NASDAQ NMS per FY1996 10-K cover; 10-K confirms CEA-Scan FDA licensure 1996-06-28; ticker pending",
    "gensia_sicor": "NASDAQ NMS per FY1997 10-K cover (registrant Gensia Sicor Inc., formerly Gensia, Inc.); ticker pending",
    "neurex": "NASDAQ NMS per FY1997 10-K 12(b) cover; 10-K states Corlopam approval Sept 24 1997 vs FDA records 1997-09-23 (kept; sponsor-side imprecision); ticker pending",
}


def main() -> int:
    ev = json.load(open(EV))
    rows_of = {}
    for key, co in ev["companies"].items():
        for did in co.get("rows", []):
            cite = co["citations"][0]
            note = (f"SPONSOR-RESOLVED {DATE} (partial): decision-date listing venue verified from the "
                    f"registrant's period filing on EDGAR ({cite['doc']}, {cite['url']}); "
                    f"exchange set to {VENUE_EXCHANGE[key]!r}. Ticker symbol still pending a primary "
                    f"citation. Evidence: data/staging/pre2000_sponsor_edgar_evidence.json.")
            rows_of[did] = (key, note)

    # ---- master ----------------------------------------------------------
    master = list(csv.DictReader(open(MASTER, newline="", encoding="utf-8-sig")))
    by_id = {r["decision_id"]: r for r in master}
    touched = 0
    for did, (key, note) in rows_of.items():
        r = by_id[did]
        if "SPONSOR-RESOLVED 2026-09-18" in r["notes"]:
            continue
        r["exchange"] = VENUE_EXCHANGE[key]
        r["notes"] = (r["notes"].rstrip(" |") + " | " + note)
        touched += 1
    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(master[0].keys()), lineterminator="\r\n")
        w.writeheader()
        w.writerows(master)
    print(f"master: exchange filled on {touched} rows")

    # ---- index ------------------------------------------------------------
    idx = list(csv.DictReader(open(INDEX, newline="", encoding="utf-8-sig")))
    for r in idx:
        did = r["decision_id"]
        if did in rows_of:
            key, _ = rows_of[did]
            co = ev["companies"][key]
            r["status"] = STATUS[key]
            r["action_for_reviewer"] = ("v10 2026-09-18: " + STATUS_DETAIL[key] +
                                        " | remaining: extract the ticker symbol from a period filing "
                                        "(Item 5 / 424B cover) + delisting year, then upgrade the "
                                        "exchange field to 'formerly <VENUE>:<TICKER>, delisted <YYYY>'")
            r["master_exchange"] = VENUE_EXCHANGE[key]
            r["sec_edgar_company_search"] = co["citations"][0]["url"]
            r["action_for_reviewer"] = (
                "v10 2026-09-18: venue verified from the period filing (see sec_edgar_company_search); "
                "remaining step = extract the ticker symbol (Item 5 of the same/later 10-K or a 424B "
                "prospectus cover) + delisting year, then upgrade the exchange field to "
                "'formerly <VENUE>:<TICKER>, delisted <YYYY>'")
        else:
            loc = ev["companies"]["citations_located_not_yet_fetched"]
            for lkey, lco in loc.items():
                if did in lco.get("rows", []):
                    if "next_doc" in lco:
                        r["sec_edgar_company_search"] = lco["next_doc"]
                        r["status"] = "CITATION-LOCATED (fetch the period 10-K and extract venue+ticker)"
                        r["action_for_reviewer"] = (
                            f"v10 2026-09-18: registrant CIK {lco['cik']} identified and the period "
                            f"10-K URL located (see sec_edgar_company_search); fetch it and extract "
                            f"venue + ticker + delisting year, then normalise the exchange field")
                    else:
                        r["status"] = "ATTRIBUTION-CASE (parent/subsidiary)"
                        r["action_for_reviewer"] = (
                            f"v10 2026-09-18: {lco['note']} Resolve the parent registrant's period "
                            f"20-F/10-K and attribute the decision-date equity accordingly")
    with INDEX.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(idx[0].keys()), lineterminator="\r\n")
        w.writeheader()
        w.writerows(idx)
    from collections import Counter
    print("index statuses:", dict(Counter(r["status"] for r in idx)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
