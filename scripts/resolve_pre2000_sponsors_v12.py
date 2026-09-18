#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-2000 sponsor resolution, v12 pass (2026-09-18) - the EDGAR symbol sweep.

The fetch_jobs/edgar_pre2000_symbols_2026_09.json queue proved one thing
immediately when the GitHub runner executed it (run 35391279461): every
www.sec.gov request returns HTTP 403 from the Actions runner's cloud IPs
(all 18 specs FAILED, recorded in
data/raw/edgar_pre2000_symbols_2026_09/manifest.json). The sandbox page-fetch
tool CAN still reach EDGAR directly, so this pass read the needed documents
live from www.sec.gov on 2026-09-18, one call at a time.

Results (verbatim quotes captured below; nothing typed from memory):

  RESOLVED - venue + ticker:
    * Pharmacia & Upjohn (D1330, D1332, D1373, D1382, D1390) -> NYSE: PNU.
      FY1997 10-K405 (acc 0000950124-98-001758) Item 5: "The Common Stock is
      listed and traded on the New York Stock Exchange (the 'NYSE') under the
      symbol PNU... Swedish Depositary Shares... traded on the Stockholm Stock
      Exchange under the symbol PH&U." All five decision dates (1996-06 ...
      1997-07) post-date the November 1995 merger pinned in v11, so
      Pharmacia & Upjohn, Inc. was the registrant at every decision date.
      Master `ticker` column FILLED (PNU already exists on D996 Detrol with
      the same us_investable_class, so the core-table class map is unaffected;
      the score grouping merges the post-merger rows with Detrol under PNU
      while pre-merger Upjohn rows D1143/D1218/D1316 stay name-keyed - the
      correct registrant split, observed and accepted rather than reverted).
    * Carter-Wallace (D1359 Astelin) -> NYSE: CAR. The symbol is NOT in the
      10-K405 body (Item 5 is incorporated by reference) - it is on page 7 of
      the 1997 Annual Report (EX-13 of the same submission, acc
      0000890163-97-000093): "The high and low selling prices of the
      Company's common stock, principally traded on the New York Stock
      Exchange (symbol CAR), for the two most recent fiscal years were as
      follows:" - the December 31, 1996 quarter (the Astelin decision
      quarter) range is High $16 1/2, Low $11 3/8. The v10 "expected NYSE:CAR"
      guess is thereby CONFIRMED from the primary document.
      Master `ticker` column stays BLANK (deliberate, like IMMU/CYTO):
      D1244 (Felbatol 1993-07-29) shares the same company_name with a blank
      ticker, and build_company_scores.py groups by ticker when present, so a
      partial CAR fill would split Carter-Wallace's scorecard (2 approvals ->
      1 + 1) - the exact D1357/D1381 Cytogen hazard documented in v11. The
      symbol lives in the `exchange` field and the note.

  VENUE-VERIFIED (ticker still pending), with new evidence:
    * Roberts Pharmaceutical (D1347, D1379) - the FY1996 10-K (acc
      0000950130-97-001485) Item 5 states the venue but NOT the symbol:
      "The Company's Common Stock is traded in the over-the-counter market on
      the NASDAQ National Market System..." (quarterly table 1996 Q3
      $20 3/4/$15 5/16 - the ProAmatine quarter). The FY1998 10-K (acc
      0000950130-99-001681) Item 5 then pins the exact venue transfer:
      "...as reported on the NASDAQ National Market System from January 1,
      1997 through May 21, 1997 and as reported by the American Stock
      Exchange from May 22, 1997 through December 31, 1998." Both decision
      dates (1996-09-06, 1997-03-14) fall in the NASDAQ NMS era. The FY1998
      10-K/A cover (acc 0000950130-99-006680) confirms the AMEX registration
      (Common Stock $.01 par + Rights, 12(b) file 001-10432) as of 1999.
      Symbol still not stated in any 10-K read; remaining routes recorded.
    * Warner-Lambert (D1342, D1366, D1376, D1409) - documented NEGATIVE
      result: the FY1997 10-K Item 5 was read in full ("The principal market
      on which the Company's stock is traded is the New York Stock Exchange,
      but the stock is also listed and traded on the following domestic and
      international stock exchanges: Chicago, Pacific, London and Zurich")
      AND the incorporated "Market Prices of Common Stock and Dividends"
      section on page 48 of the 1997 Annual Report (EX-13) was read in full -
      quarterly ranges only, NO symbol stated anywhere in the submission.
      Ranges captured as price-event evidence (1996 Q4 $80/$61 7/8 covers the
      Cerebyx and Lipitor decisions; 1997 Q1 $93 1/4/$69 1/2 covers Rezulin).
    * Block Drug (D1365 Aphthasol) - promoted from CITATION-LOCATED. The
      FY1997 10-K (acc 0000012654-97-000004) cover shows NO 12(b) listing:
      "Securities registered pursuant to Section 12(b) of the Act: Title of
      Each Class: None" with Class A Common Stock registered under 12(g)
      (SROS: NASD), and Item 5 gives quarterly ranges of Class A Common Stock
      with the footnote "These are high and low bid quotes and reflect
      inter-dealer prices..." (i.e. the OTC/NASD inter-dealer market), 507
      Class A (non-voting) holders of record vs 5 Class B (voting) holders -
      the Block family. NO ticker symbol stated. Bonus verification: the same
      10-K states verbatim "In December, 1996, the Company received Food and
      Drug Administration (FDA) approval for Aphthasol, a new chemical entity
      for the treatment of aphthous ulcers" - the registrant's own period
      confirmation of the D1365 decision.

Applies to (same targets as v11):
  1. data/staging/pre2000_sponsor_edgar_evidence.json - symbol citations for
     pharmacia_upjohn and carter_wallace; new company entry for block_drug
     (promoted out of citations_located_not_yet_fetched); v12_update block
     with the Roberts/Warner-Lambert evidence and the runner-403 finding.
  2. data/pre2000_sponsor_resolution_index.csv - 6 rows -> RESOLVED
     (P&U x5 + Carter-Wallace); Block Drug CITATION-LOCATED -> VENUE-VERIFIED.
     New split: 15 RESOLVED, 7 VENUE-VERIFIED, 0 CITATION-LOCATED,
     3 ATTRIBUTION-CASE, 22 NO-EQUITY, 18 REVIEW (foreign), 2 REVIEW.
  3. data/fda_decisions_master.csv - exchange text upgraded, ticker filled
     ONLY where safe (PNU x5), dated notes appended with verbatim quotes and
     replayable URLs. Prior note text is never removed.

Repo law honoured: no price rows are created from the Item 5 quarterly
tables; they are recorded as evidence text so a future fetch job can be
aimed at them deliberately.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "data" / "staging" / "pre2000_sponsor_edgar_evidence.json"
INDEX = ROOT / "data" / "pre2000_sponsor_resolution_index.csv"
MASTER = ROOT / "data" / "fda_decisions_master.csv"
DATE = "2026-09-18"
TAG = "SPONSOR-RESOLVED 2026-09-18"
RESOLVED = "RESOLVED (venue+ticker per period 10-K)"
VENUE_PENDING = "VENUE-VERIFIED (ticker pending)"

PNU_URL = "https://www.sec.gov/Archives/edgar/data/949573/0000950124-98-001758.txt"
CAR_URL = "https://www.sec.gov/Archives/edgar/data/18000/0000890163-97-000093.txt"
ROB_96_URL = "https://www.sec.gov/Archives/edgar/data/853022/0000950130-97-001485.txt"
ROB_98_URL = "https://www.sec.gov/Archives/edgar/data/853022/0000950130-99-001681.txt"
ROB_A_URL = "https://www.sec.gov/Archives/edgar/data/853022/0000950130-99-006680.txt"
WL_URL = "https://www.sec.gov/Archives/edgar/data/104669/0000950117-98-000602.txt"
BLK_URL = "https://www.sec.gov/Archives/edgar/data/12654/0000012654-97-000004.txt"

PNU_QUOTE = ("The Common Stock is listed and traded on the New York Stock Exchange "
             "(the \"NYSE\") under the symbol PNU. As of January 31, 1998, there were "
             "36,914 holders of record of the Common Stock. Swedish Depositary Shares, "
             "each representing one share of Common Stock, are traded on the Stockholm "
             "Stock Exchange under the symbol PH&U.")
CAR_QUOTE = ("The high and low selling prices of the Company's common stock, principally "
             "traded on the New York Stock Exchange (symbol CAR), for the two most recent "
             "fiscal years were as follows: ... December 31 [1996 quarter]: High $16 1/2, "
             "Low $11 3/8")
ROB_96_QUOTE = ("The Company's Common Stock is traded in the over-the-counter market on "
                "the NASDAQ National Market System and was held by approximately 900 "
                "shareholders of record as of March 19, 1997. [1996 Q3 range $20 3/4 / "
                "$15 5/16 - the ProAmatine decision quarter]")
ROB_98_QUOTE = ("The Company's Common Stock is traded on the American Stock Exchange and "
                "was held by approximately 960 shareholders of record as of March 15, "
                "1999. ... as reported on the NASDAQ National Market System from January "
                "1, 1997 through May 21, 1997 and as reported by the American Stock "
                "Exchange from May 22, 1997 through December 31, 1998.")
WL_ITEM5_QUOTE = ("The principal market on which the Company's stock is traded is the New "
                  "York Stock Exchange, but the stock is also listed and traded on the "
                  "following domestic and international stock exchanges: Chicago, Pacific, "
                  "London and Zurich.")
WL_AR_QUOTE = ("Market Prices of Common Stock and Dividends [1997 Annual Report p.48]: "
               "1996 Q4 High $80 / Low $61 7/8; 1997 Q1 High $93 1/4 / Low $69 1/2 - "
               "quarterly ranges only, no ticker symbol stated anywhere in the submission.")
BLK_ITEM5_QUOTE = ("Item 5 'STOCK PRICE AND DIVIDEND INFORMATION' - 'Range of Class A "
                   "Common Stock*' with the footnote '* These are high and low bid quotes "
                   "and reflect inter-dealer prices without retail mark-up, mark-down or "
                   "commission and may not necessarily represent actual transactions.' "
                   "[FY1997 Q3 = Oct-Dec 1996, the Aphthasol quarter: $48 / $44 1/8]")
BLK_APH_QUOTE = ("In December, 1996, the Company received Food and Drug Administration "
                 "(FDA) approval for Aphthasol, a new chemical entity for the treatment "
                 "of aphthous ulcers, commonly known as canker sores.")

PNU_IDS = ["D1330", "D1332", "D1373", "D1382", "D1390"]
WL_IDS = ["D1342", "D1366", "D1376", "D1409"]
ROB_IDS = ["D1347", "D1379"]


def append_note(existing, addition):
    base = existing.rstrip()
    if base and not base.endswith("."):
        base += "."
    return base + " " + addition


def main():
    # ---------------- 1. master ----------------
    with open(MASTER, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        mfield = reader.fieldnames
        master = list(reader)
    by_id = {r["decision_id"]: r for r in master}

    # P&U x5 -> RESOLVED, ticker filled
    for did in PNU_IDS:
        r = by_id[did]
        r["ticker"] = "PNU"
        r["exchange"] = ("NYSE:PNU (Pharmacia & Upjohn, Inc.; ticker per FY1997 10-K405 "
                         "Item 5, fetched 2026-09-18)")
        r["notes"] = append_note(r["notes"],
            f"SPONSOR-RESOLVED {DATE} (v12 symbol pass): Item 5 of the FY1997 10-K405 "
            f"(acc 0000950124-98-001758) states verbatim: '{PNU_QUOTE}' "
            f"({PNU_URL}). All five P&U decision dates post-date the 1995-11-02 merger "
            f"pinned in v11, so Pharmacia & Upjohn, Inc. was the NYSE:PNU registrant at "
            f"every decision date. Ticker column filled: PNU already exists on D996 "
            f"(Detrol, same FORMERLY US-LISTED class), so the core-table class map is "
            f"unaffected; the Upjohn-era name group splits along the real registrant "
            f"boundary (pre-merger D1143/D1218/D1316 stay name-keyed).")
        print("master", did, "-> ticker PNU, exchange NYSE:PNU")

    # Carter-Wallace D1359 -> RESOLVED, symbol in exchange only (D1244 split hazard)
    r = by_id["D1359"]
    r["exchange"] = ("NYSE:CAR (Carter-Wallace, Inc.; symbol per page 7 of the 1997 "
                     "Annual Report, EX-13 of the FY1997 10-K405, fetched 2026-09-18; "
                     "ticker column deliberately blank - see note)")
    r["notes"] = append_note(r["notes"],
        f"SPONSOR-RESOLVED {DATE} (v12 symbol pass): page 7 of the 1997 Annual Report to "
        f"Stockholders (EX-13 inside the FY1997 10-K405 submission, acc 0000890163-97-000093) "
        f"states verbatim: '{CAR_QUOTE}' ({CAR_URL}). The v10 'expected NYSE:CAR' guess is "
        f"CONFIRMED from the primary document. Ticker column deliberately left blank: "
        f"D1244 (Felbatol, 1993-07-29) shares the same company_name with a blank ticker, "
        f"and build_company_scores groups by ticker when present - a partial CAR fill "
        f"would split Carter-Wallace's scorecard (the D1357/D1381 Cytogen hazard).")
    print("master D1359 -> exchange NYSE:CAR (ticker blank by policy)")

    # Roberts x2 - venue transfer pinned, symbol still pending
    for did in ROB_IDS:
        r = by_id[did]
        r["exchange"] = ("NASDAQ NMS at decision date (Roberts Pharmaceutical Corp.); "
                         "transferred to the American Stock Exchange 1997-05-22 (per FY1998 "
                         "10-K Item 5: NASDAQ NMS through 1997-05-21, AMEX from 1997-05-22); "
                         "12(b) file 001-10432 from 1999-07-27; ticker pending")
        r["notes"] = append_note(r["notes"],
            f"SPONSOR-RESOLVED {DATE} (v12 venue pass): FY1996 10-K (acc 0000950130-97-001485) "
            f"Item 5 verbatim: '{ROB_96_QUOTE}' - venue confirmed, NO symbol stated. FY1998 "
            f"10-K (acc 0000950130-99-001681) Item 5 verbatim: '{ROB_98_QUOTE}' - the venue "
            f"transfer is pinned to 1997-05-22, AFTER both decision dates. FY1998 10-K/A "
            f"cover (acc 0000950130-99-006680): 'Common Stock $.01 par value per share / "
            f"American Stock Exchange' + Rights, 12(b) file 001-10432. Symbol still not "
            f"found in any period 10-K read; remaining routes: FY1997 10-K (acc "
            f"0000950130-98-001619), 1997/1998 DEF 14A proxies, 1999 DEFM14A.")
        print("master", did, "-> venue-transfer note appended")

    # Warner-Lambert x4 - documented negative result
    for did in WL_IDS:
        r = by_id[did]
        r["notes"] = append_note(r["notes"],
            f"SPONSOR-RESOLVED {DATE} (v12 negative pass): the FY1997 10-K (acc "
            f"0000950117-98-000602) was read in full for Item 5 - verbatim: "
            f"'{WL_ITEM5_QUOTE}' - and the incorporated 'Market Prices of Common Stock and "
            f"Dividends' on page 48 of the 1997 Annual Report (EX-13 of the same "
            f"submission) was read in full: '{WL_AR_QUOTE}' NO ticker symbol is stated "
            f"anywhere in the submission ({WL_URL}). Remaining routes: FY1998/FY1999 10-Ks, "
            f"DEF 14A proxies.")
        print("master", did, "-> negative-result note appended")

    # Block Drug D1365 - venue evidence, symbol pending
    r = by_id["D1365"]
    r["exchange"] = ("OTC: NASD inter-dealer market (Block Drug Company, Inc. Class A "
                     "Common Stock, non-voting, 12(g)-registered - no exchange listing per "
                     "FY1997 10-K cover/Item 5, fetched 2026-09-18; ticker pending)")
    r["notes"] = append_note(r["notes"],
        f"SPONSOR-RESOLVED {DATE} (v12 venue pass): FY1997 10-K (period ended 1997-03-31, "
        f"filed 1997-06-30, acc 0000012654-97-000004) cover: 12(b) 'Title of Each Class: "
        f"None'; 12(g) 'Class A Common Stock - $.10 par value'; SROS: NASD. Item 5: "
        f"'{BLK_ITEM5_QUOTE}' ({BLK_URL}). 507 Class A holders of record vs 5 Class B "
        f"(voting) holders - the Block family. Same 10-K, Item 1, verbatim: "
        f"'{BLK_APH_QUOTE}' - the registrant's own period confirmation of the D1365 "
        f"Aphthasol decision (Drugs@FDA date 1996-11-01 stands as primary). No ticker "
        f"symbol stated; remaining routes: 424-series/DEF 14A, NASD Pink Sheets archives.")
    print("master D1365 -> venue OTC/NASD, decision confirmed verbatim")

    with open(MASTER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=mfield)
        w.writeheader()
        w.writerows(master)

    # ---------------- 2. index ----------------
    with open(INDEX, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        ifield = reader.fieldnames
        index = list(reader)
    iby = {r["decision_id"]: r for r in index}
    for did in PNU_IDS + ["D1359"]:
        iby[did]["status"] = RESOLVED
        iby[did]["action_for_reviewer"] = append_note(iby[did]["action_for_reviewer"],
            f"v12 {DATE}: RESOLVED - ticker read verbatim from the period filing (see notes/master).")
    iby["D1365"]["status"] = VENUE_PENDING
    iby["D1365"]["action_for_reviewer"] = append_note(iby["D1365"]["action_for_reviewer"],
        f"v12 {DATE}: VENUE-VERIFIED (OTC/NASD inter-dealer, bid quotes; no 12(b) listing; "
        f"Aphthasol approval confirmed verbatim in the same 10-K). Ticker still pending.")
    for did in ROB_IDS:
        iby[did]["action_for_reviewer"] = append_note(iby[did]["action_for_reviewer"],
            f"v12 {DATE}: NASDAQ NMS venue re-confirmed via FY1996 10-K Item 5; AMEX transfer "
            f"pinned to 1997-05-22 (post-both-decisions) via FY1998 10-K Item 5. Symbol not "
            f"stated in either 10-K - still pending.")
    for did in WL_IDS:
        iby[did]["action_for_reviewer"] = append_note(iby[did]["action_for_reviewer"],
            f"v12 {DATE}: FY1997 10-K read in full (Item 5 + EX-13 p.48 market prices): no "
            f"symbol stated anywhere in the submission. Negative result recorded.")
    with open(INDEX, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ifield)
        w.writeheader()
        w.writerows(index)

    # ---------------- 3. evidence ----------------
    ev = json.load(open(EV, encoding="utf-8"))
    ev["companies"]["pharmacia_upjohn"]["symbol"] = "PNU"
    ev["companies"]["pharmacia_upjohn"]["citations"].append({
        "doc": "FY1997 Form 10-K405 (period 1997-12-31, filed 1998-03-31), Item 5 (v12 symbol pass)",
        "url": PNU_URL,
        "evidence": PNU_QUOTE,
        "note": "All five decision dates (1996-06 through 1997-07) post-date the 1995-11-02 "
                "merger (pinned in v11 from the same registrant's EX-13), so PNU was the "
                "symbol at every decision date. Stockholm SDS symbol PH&U also recorded.",
    })
    ev["companies"]["carter_wallace"]["symbol"] = "CAR"
    ev["companies"]["carter_wallace"]["citations"].append({
        "doc": "1997 Annual Report to Stockholders, page 7 (EX-13 of the FY1997 10-K405, acc 0000890163-97-000093)",
        "url": CAR_URL,
        "evidence": CAR_QUOTE,
        "note": "Symbol NOT in the 10-K405 body (Item 5 incorporated by reference to pages 1 "
                "and 7 of the Annual Report). Master ticker column deliberately blank "
                "(D1244 same-name split hazard); symbol carried in the exchange field.",
    })
    ev["companies"]["block_drug"] = {
        "cik": "0000012654",
        "rows": ["D1365"],
        "venue": "Over-the-counter: NASD inter-dealer market (bid quotes); no Section 12(b) exchange listing",
        "symbol": None,
        "citations": [
            {"doc": "FY1997 Form 10-K (period 1997-03-31, filed 1997-06-30)",
             "url": BLK_URL,
             "evidence": "Cover: 'Securities registered pursuant to Section 12(b) of the Act: "
                         "Title of Each Class: None' / 12(g): 'Class A Common Stock - $.10 par "
                         "value' / SROS: NASD. " + BLK_ITEM5_QUOTE,
             "note": "507 Class A (non-voting) holders of record vs 5 Class B (voting) "
                     "holders (the Block family). Same 10-K Item 1: " + BLK_APH_QUOTE},
        ],
        "note": "Promoted from citations_located_not_yet_fetched in v12. Ticker symbol not "
                "stated in the 10-K; status VENUE-VERIFIED (ticker pending).",
    }
    # remove Block Drug from the not-yet-fetched holding pen
    pen = ev["companies"].get("citations_located_not_yet_fetched", {})
    if "block_drug" in pen:
        pen["block_drug"] = "FETCHED in v12 (see companies.block_drug)"
    ev["v12_update"] = {
        "captured_utc": DATE,
        "runner_finding": "All 18 fetch_jobs/edgar_pre2000_symbols_2026_09.json specs returned "
                          "HTTP 403 Forbidden from the GitHub Actions runner (run 35391279461; "
                          "manifest in data/raw/edgar_pre2000_symbols_2026_09/manifest.json) - "
                          "SEC blocks the runner's cloud IPs. EDGAR must be fetched through the "
                          "sandbox page-fetch tool (still works, one URL at a time).",
        "what_changed": [
            "pharmacia_upjohn symbol PNU (5 rows RESOLVED, ticker column filled)",
            "carter_wallace symbol CAR (D1359 RESOLVED, ticker column deliberately blank)",
            "block_drug promoted: OTC/NASD venue verified, Aphthasol approval quoted verbatim, symbol pending",
            "roberts_pharmaceutical: venue transfer pinned - NASDAQ NMS through 1997-05-21, AMEX from 1997-05-22 (post-both-decisions); symbol not stated in FY1996/FY1998 10-Ks",
            "warner_lambert: negative result - FY1997 submission read in full (Item 5 + EX-13 p.48), no symbol stated",
        ],
        "roberts_evidence": [
            {"doc": "FY1996 Form 10-K (filed 1997-04-02), Item 5", "url": ROB_96_URL, "evidence": ROB_96_QUOTE},
            {"doc": "FY1998 Form 10-K (filed 1999-03-26), Item 5", "url": ROB_98_URL, "evidence": ROB_98_QUOTE},
            {"doc": "FY1998 Form 10-K/A (filed 1999-11-22), cover 12(b)", "url": ROB_A_URL,
             "evidence": "Common Stock $.01 par value per share / American Stock Exchange; Rights / "
                         "American Stock Exchange; SEC file 001-10432; last sale price 'as reported "
                         "by the American Stock Exchange as of October 15, 1999'."},
        ],
        "warner_lambert_evidence": [
            {"doc": "FY1997 Form 10-K, Item 5", "url": WL_URL, "evidence": WL_ITEM5_QUOTE},
            {"doc": "1997 Annual Report (EX-13), page 48 'Market Prices of Common Stock and Dividends'",
             "url": WL_URL, "evidence": WL_AR_QUOTE},
        ],
    }
    with open(EV, "w", encoding="utf-8") as f:
        json.dump(ev, f, indent=1)

    from collections import Counter
    print("index statuses:", dict(Counter(r["status"] for r in index)))
    print("evidence updated")


if __name__ == "__main__":
    main()
