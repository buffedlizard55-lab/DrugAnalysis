#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-2000 sponsor resolution, v11 pass (2026-09-18) - ticker SYMBOLS.

v10 verified the decision-date listing VENUE for 19 rows. This pass closes the
next step of hand-off item 1: the ticker SYMBOL, read verbatim out of the
registrant's own period filing on EDGAR (Item 5 / cover 12(b) table), plus the
first pinned delisting year of the pass (Neurex, 1998).

Everything below was fetched live from www.sec.gov on 2026-09-18 (UTC) through
the page-fetch tool. Quotes are verbatim. Nothing is typed from memory, and
where a v9/v10 "expected" symbol disagrees with the filing, the filing wins and
the wrong guess is recorded as wrong:

    Advanced Magnetics  v9/v10 guess "ANM"/"AinM"  -> filing says  AVM  (AMEX)
    Neurex              v10 index guess "NXRX"     -> filing says  NXCO
    IVAX / Baker Norton master note "Nasdaq:IVX"   -> filing says  AMEX:IVX
    Cytogen             v10 guess "CYTO"           -> confirmed    CYTO
    Immunomedics        v10 guess "IMMU"           -> confirmed    IMMU
    Gensia Sicor        v10 guess "GNSA"           -> confirmed    GNSA

Applies to:
  1. data/staging/pre2000_sponsor_edgar_evidence.json - adds the v11 companies
     (ivax_corp_baker_norton and carter_wallace are promoted out of
     citations_located_not_yet_fetched) and the v11 symbol citations for the
     companies v10 had already opened.
  2. data/pre2000_sponsor_resolution_index.csv - 8 rows -> RESOLVED
     (venue+ticker per period 10-K); Carter-Wallace CITATION-LOCATED ->
     VENUE-VERIFIED; Roberts' two rows keep VENUE-VERIFIED but gain the
     Form 15-12G deregistration evidence. Row count stays 67.
  3. data/fda_decisions_master.csv - exchange text upgraded to carry the
     verified symbol, ticker column filled where it is safe to do so, and a
     dated note appended with the verbatim quote + replayable URL. Prior note
     text is never removed.

Deliberate NON-fills, each documented on the row itself:
  * D1338 Immunomedics - the symbol IS verified (IMMU) but the master `ticker`
    column stays blank. build_core_analysis_table.py builds a ticker-keyed
    class map with setdefault() in master order and applies it to EVERY row
    sharing the ticker; IMMU is already carried by D376 (Trodelvy, 2020-04-22,
    class US-LISTED) at master index 97, ahead of D1338 at index 1327, so
    filling IMMU here would re-class this 1996 row as US-LISTED in the core
    table. Symbol recorded in the exchange text + note instead.
  * D1357/D1381 Cytogen - the symbol IS verified (CYTO) but the master `ticker`
    column stays blank. D1231 (OncoScint, 1992-12-29) carries the same
    company_name with a blank ticker, and build_company_scores.py groups by
    ticker when one is present: a partial CYTO fill split Cytogen's record into
    two score rows (3 approvals -> 2 + 1). Observed in a trial run and reverted.
  * D1359 Carter-Wallace - venue verified (NYSE, cover 12(b)); the symbol is
    NOT in the 10-K document because Item 5 is incorporated by reference to
    pages 1 and 7 of the 1997 Annual Report to Stockholders. Blank, flagged.

So 5 of the 8 verified symbols are written to the master `ticker` column
(AVM x2, NXCO, GNSA, IVX) and all 8 are written to the `exchange` field, which
the site displays and searches. Agouron (D1380), the worklist's only previously
RESOLVED row, follows the same exchange-carries-the-symbol convention.

Repo law honoured: no price rows are created from the Item 5 quarterly tables
(price events come from the Yahoo fetch-job pipeline only); the tables are
recorded as evidence text so a future job can be aimed at them.
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

# --------------------------------------------------------------------------
# 1. v11 EDGAR evidence (verbatim quotes; captured 2026-09-18 UTC)
# --------------------------------------------------------------------------
EVIDENCE = {
    "advanced_magnetics": {
        "cik": "0000792977",
        "rows": ["D1345", "D1363"],
        "venue": "American Stock Exchange (AMEX)",
        "symbol": "AVM",
        "symbol_verbatim": ("The Company's common stock is listed on the American Stock Exchange "
                            "under the symbol AVM. The table below sets forth the high and low sales "
                            "price of the Company's common stock on the American Stock Exchange for "
                            "the fiscal quarters of 1996 and 1995."),
        "citations": [{
            "doc": ("FY1996 Form 10-K405 (period 1996-09-30, filed 1996-12-23, acc "
                    "0000950135-96-005384), Item 5 'Market for the Company's Common Equity and "
                    "Related Stockholder Matters'"),
            "url": "https://www.sec.gov/Archives/edgar/data/792977/0000950135-96-005384.txt",
            "evidence": (
                "Item 5 symbol statement quoted in symbol_verbatim (AMEX:AVM). Item 5 fiscal-quarter "
                "high/low sales-price table (FYE 30 Sep): FY1996 Q1 $29 1/2 / $24, Q2 $30 / $19 1/2, "
                "Q3 $23 / $16 1/8, Q4 $19 7/8 / $16 1/4; FY1995 Q1 $16 3/4 / $13 1/4, Q2 $19 1/4 / "
                "$14 1/4, Q3 $23 3/8 / $17 1/2, Q4 $29 / $21. The Feridex decision date 1996-08-30 "
                "falls in FY1996 Q4 (Jul-Sep 1996). Cover: 'The aggregate market value of Common "
                "Stock held by nonaffiliates of the registrant at December 16, 1996 was approximately "
                "$93,373,851, based upon the last reported sale price of the Common Stock on The "
                "American Stock Exchange'; 'The last reported sale price of the Common Stock on "
                "December 16, 1996 was $15.375 per share' (six days after the 1996-12-06 GastroMARK "
                "decision, so the filing is contemporaneous with BOTH decision dates); 306 holders of "
                "record; securities registered under Section 12(g); commission file number 000-14732; "
                "SEC header 'SROS: AMEX'. Business section: 'The Company received U.S. Food and Drug "
                "Administration (\"FDA\") approval to market Feridex I.V. in August 1996' and 'the "
                "Company received approval to market GastroMARK in the United States in December 1996'."
            ),
        }],
        "note": (
            "v11 2026-09-18: SYMBOL VERIFIED = AVM on the American Stock Exchange. This corrects two "
            "earlier assumptions: the v9 hand-off's 'ANM/AinM' and the master note's 'NASDAQ:AMAG from "
            "its 1997 IPO'. AMAG is the ticker of the renamed registrant (EDGAR name change to AMAG "
            "Pharmaceuticals 2007-07-05) and is NOT the decision-date symbol; AVM/AMEX is. Delisting "
            "year still pending a primary citation. The GastroMARK decision (1996-12-06) falls in "
            "FY1997 Q1, which this filing's Item 5 table does not cover; the cover's 1996-12-16 AMEX "
            "sale price is the contemporaneous anchor for that row."
        ),
    },
    "neurex": {
        "cik": "0000884065",
        "rows": ["D1396"],
        "venue": "NASDAQ National Market System",
        "symbol": "NXCO",
        "symbol_verbatim": ("Since the Company's initial public offering of its common stock, $0.01 par "
                            "value (\"Common Stock\"), on September 22, 1993, the Company's Common Stock "
                            "has been traded on the NASDAQ National Market System under the symbol NXCO. "
                            "The closing price of the Company's Common Stock on March 5, 1998 was $18.13 "
                            "per share."),
        "citations": [
            {
                "doc": ("FY1997 Form 10-K (period 1997-12-31, filed 1998-03-30, acc 0000884065-98-000003), "
                        "Item 5 'Market for the Registrant's Common Equity and Related Stockholder Matters'"),
                "url": "https://www.sec.gov/Archives/edgar/data/884065/0000884065-98-000003.txt",
                "evidence": (
                    "Item 5 symbol statement quoted in symbol_verbatim (NASDAQ NMS:NXCO). Item 5 high/low "
                    "bid table 'as reported by NASDAQ': 1996 Q1 21.75/7.25, Q2 24.50/16.50, Q3 22.25/13.25, "
                    "Q4 17.75/12.00; 1997 Q1 17.50/11.88, Q2 17.13/9.88, Q3 16.00/11.63, Q4 18.50/13.00. "
                    "The Corlopam decision date 1997-09-23 falls in 1997 Q3 (high $16.00, low $11.63). "
                    "SEC header 'SROS: NASD'; commission file number 033-96840; approximately 4,000 "
                    "stockholders of record as of March 5, 1998."
                ),
            },
            {
                "doc": ("Form DEF 14A (period 1998-08-11, filed 1998-07-02, acc 0000950130-98-003434) - "
                        "Elan merger proxy; delisting-year evidence"),
                "url": "https://www.sec.gov/Archives/edgar/data/884065/0000950130-98-003434.txt",
                "evidence": (
                    "Verbatim: '...an Agreement and Plan of Merger, dated as of April 29, 1998 (the "
                    "\"Merger Agreement\"), providing for the merger (the \"Merger\") of Neurex with a "
                    "wholly-owned subsidiary of Elan Corporation, plc (\"Elan\"). Upon consummation of the "
                    "Merger, (a) Neurex will become a wholly-owned subsidiary of Elan and (b) Neurex "
                    "stockholders (other than Elan) will be entitled to receive 0.51 of an American "
                    "Depositary Share of Elan (an \"Elan ADS,\" each Elan ADS representing one ordinary "
                    "share, par value 4 Irish pence, of Elan, evidenced by one American Depositary Receipt "
                    "of Elan) for each share of Neurex common stock, par value $.01 (a \"Neurex Share\"), "
                    "held by them (the \"Exchange Ratio\").' Annual meeting date 1998-08-11. Fee-table "
                    "note: 'Based upon the average of the high and low sale prices of American Depositary "
                    "Shares of Elan Corporation, plc on The New York Stock Exchange on June 2, 1998 "
                    "multiplied by the exchange ratio of 0.51.' Prior filing identified: 'Registration "
                    "Statement on Form F-4, Registration No. 333-9056 ... Filing Party: Elan Corporation, "
                    "plc ... Date Filed: July 1, 1998'. Fee table: 26,291,827 shares at $30.9825 = "
                    "$814,586,530."
                ),
            },
            {
                "doc": ("Form 15-15D filed 1998-08-14 (acc 0000950162-98-000894, file no. 033-96840) - "
                        "suspension of duty to report; deregistration evidence"),
                "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000884065&type=&dateb=&owner=include&count=100",
                "evidence": (
                    "EDGAR filing list for CIK 0000884065 (atom feed, retrieved 2026-09-18): Form 15-15D "
                    "'Suspension of duty to report [Section 13 and 15(d)]' filed 1998-08-14 (3 KB); three "
                    "Form RW registration-withdrawal requests filed 1998-08-14 (file numbers 033-76976, "
                    "333-04682, 333-31935); three S-8 POS filed 1998-10-14; last Form 10-Q filed "
                    "1998-08-10; Form 8-K item 5 filed 1998-07-22. The registrant's reporting series "
                    "therefore ends in 1998, consistent with the Elan merger completing that year."
                ),
            },
        ],
        "note": (
            "v11 2026-09-18: SYMBOL VERIFIED = NXCO on the NASDAQ National Market System (the v10 index's "
            "'NXRX expected' guess is WRONG; the master's pre-existing 'NASDAQ:NXCO era' note is confirmed "
            "by the filing). DELISTING YEAR PINNED = 1998 (Elan Corporation plc merger; Merger Agreement "
            "1998-04-29, stockholder vote 1998-08-11, Form 15-15D filed 1998-08-14). This is the first "
            "row of the worklist to reach the full 'formerly <VENUE>:<TICKER>, delisted <YYYY>' form since "
            "Agouron. BONUS primary fact for the Athena/Zanaflex attribution case (D1362): the same proxy "
            "states Elan's American Depositary Shares traded on The New York Stock Exchange in 1998."
        ),
    },
    "cytogen": {
        "cik": "0000725058",
        "rows": ["D1357", "D1381"],
        "venue": "NASDAQ National Market",
        "symbol": "CYTO",
        "symbol_verbatim": ('CYTOGEN Common Stock is traded on the NASDAQ National Market tier of '
                            'The NASDAQ Stock Market under the trading symbol "CYTO."'),
        "citations": [{
            "doc": ("FY1996 Form 10-K (period 1996-12-31, filed 1997-03-24, acc 0000950109-97-002390), "
                    "Item 5 'Market for Registrant's Common Equity and Related Stockholder Matters'"),
            "url": "https://www.sec.gov/Archives/edgar/data/725058/0000950109-97-002390.txt",
            "evidence": (
                "Item 5 symbol statement quoted in symbol_verbatim (NASDAQ NMS:CYTO), followed by 'The "
                "table below sets forth the high and low sale prices for CYTOGEN Common Stock for each of "
                "the calendar quarters indicated, as reported by the NASDAQ National Market.' The FY1996 "
                "10-K list on EDGAR (atom, retrieved 2026-09-18) also gives: FY1998 10-K filed 1999-02-22 "
                "acc 0000725058-99-000007 (216 KB); FY1997 10-K/A filed 1998-04-10 acc "
                "0000725058-98-000017 (242 KB); FY1997 10-K filed 1998-03-31 acc 0000725058-98-000010 "
                "(241 KB); FY1996 filed 1997-03-24 acc 0000950109-97-002390 (227 KB); FY1995 filed "
                "1996-03-28 acc 0000950109-96-001807 (460 KB); FY1994 filed 1995-03-17 acc "
                "0000950109-95-000766 (320 KB). SEC file numbers 000-14879 (through 1997) and 333-02015 "
                "(1998+)."
            ),
        }],
        "note": (
            "v11 2026-09-18: SYMBOL VERIFIED = CYTO on the NASDAQ National Market (v10 guess confirmed). "
            "COVERAGE CAVEAT recorded on the row: this 10-K was filed 1997-03-24, four days BEFORE the "
            "Quadramet decision date 1997-03-28 (D1381), so for D1381 the filing is contemporaneous but "
            "not post-decision; symbol continuity through that date should be confirmed from the FY1997 "
            "10-K (acc 0000725058-98-000010, filed 1998-03-31). ProstaScint (D1357, 1996-10-28) is fully "
            "inside this filing's period. Delisting year still pending."
        ),
    },
    "immunomedics": {
        "cik": "0000722830",
        "rows": ["D1338"],
        "venue": "Nasdaq National Market",
        "symbol": "IMMU",
        "symbol_verbatim": ('The Company\'s Common Stock is traded on The Nasdaq National Market under '
                            'the symbol "IMMU". The table below sets forth for the periods indicated the '
                            'high and low sales prices for the Company\'s Common Stock, as reported by '
                            'The Nasdaq Stock Market.'),
        "citations": [{
            "doc": ("FY1996 Form 10-K (FYE 1996-06-30, filed 1996-09-30, acc 0000950109-96-006351), "
                    "Item 5 'Market for Registrant's Common Stock and Related Stockholders Matters'"),
            "url": "https://www.sec.gov/Archives/edgar/data/722830/0000950109-96-006351.txt",
            "evidence": (
                "Item 5 symbol statement quoted in symbol_verbatim (NASDAQ NMS:IMMU). Item 5 "
                "fiscal-quarter high/low table (FYE 30 Jun): Sep-30-1994 5 3/8 / 3; Dec-31-1994 5 1/8 / 3; "
                "Mar-31-1995 4 1/8 / 2 3/4; Jun-30-1995 3 5/8 / 2 1/8; Sep-30-1995 8 1/2 / 2 1/4; "
                "Dec-31-1995 8 1/4 / 3 3/4; Mar-31-1996 10 3/8 / 5 1/8; Jun-30-1996 9 7/8 / 6 1/2 - the "
                "CEA-Scan decision date 1996-06-28 falls in the quarter ended June 30, 1996. 'As of "
                "September 23, 1996, there were approximately 1,200 holders of record of the Company's "
                "Common Stock.' MD&A: 'On June 28, 1996, the FDA licensed CEA-Scan(R) for the detection "
                "of recurrent and/or metastatic colorectal cancer.' (exact match to master D1338). EDGAR "
                "10-K list (atom, retrieved 2026-09-18): FY1998 filed 1998-09-28 acc 0000722830-98-000009 "
                "(247 KB); FY1997 filed 1997-09-29 acc 0001019056-97-000232 (225 KB); FY1996 10-K/A filed "
                "1997-02-05 acc 0000950117-97-000144 (92 KB); FY1996 10-K/A filed 1996-12-04 acc "
                "0000950117-96-001539 (18 KB); FY1995 filed 1995-09-27 acc 0000722830-95-000006 (169 KB). "
                "SEC file number 000-12104."
            ),
        }],
        "note": (
            "v11 2026-09-18: SYMBOL VERIFIED = IMMU on The Nasdaq National Market (v10 guess confirmed; "
            "the master's 'not re-verified this pass' caveat is now discharged). TICKER COLUMN LEFT BLANK "
            "ON PURPOSE: build_core_analysis_table.py derives class_by_ticker with setdefault() in master "
            "order and applies it to every row sharing a ticker; IMMU is already carried by D376 "
            "(Trodelvy, 2020-04-22, us_investable_class US-LISTED) at master index 97, ahead of D1338 at "
            "index 1327. Filling IMMU on this 1996 row would therefore re-class it as US-LISTED in the "
            "core table, which is wrong (Immunomedics was acquired in 2020). The symbol is recorded in "
            "the exchange text and in this note instead; a decision-date-aware class model is the "
            "prerequisite for filling it."
        ),
    },
    "gensia_sicor": {
        "cik": "0000807873",
        "rows": ["D1394"],
        "venue": "Nasdaq National Market",
        "symbol": "GNSA",
        "symbol_verbatim": ('The Company\'s Common Stock is traded in the over-the-counter market on the '
                            'Nasdaq National Market under the symbol "GNSA". The following table sets '
                            'forth, for the periods indicated, the range of high and low reported bid '
                            'prices for the Company\'s Common Stock on the Nasdaq National Market.'),
        "citations": [{
            "doc": ("FY1997 Form 10-K (period 1997-12-31, filed 1998-03-31, acc 0001012870-98-000824), "
                    "Item 5 'Market for Registrant's Common Equity and Related Stockholder Matters'"),
            "url": "https://www.sec.gov/Archives/edgar/data/807873/0001012870-98-000824.txt",
            "evidence": (
                "Item 5 symbol statement quoted in symbol_verbatim (NASDAQ NMS:GNSA). Item 5 high/low bid "
                "table: 1996 Jan-Mar 6.13/4.38, Apr-Jun 5.88/3.94, Jul-Sep 5.69/4.56, Oct-Dec 5.50/3.88; "
                "1997 Jan-Mar 4.94/3.94, Apr-Jun 5.19/3.13, Jul-Sep 7.81/4.41, Oct-Dec 7.00/4.50 - the "
                "Genesa decision date 1997-09-12 falls in the Jul 1 - Sep 30, 1997 quarter (high $7.81, "
                "low $4.41). 'As of March 23, 1998 there were approximately 944 holders of record of the "
                "Company's Common Stock.' Registrant name on the filing: GENSIA SICOR INC. (formerly "
                "Gensia, Inc.). Submission is 56 chunks; Item 5 is on printed page 20-21."
            ),
        }],
        "note": (
            "v11 2026-09-18: SYMBOL VERIFIED = GNSA on the Nasdaq National Market (v10 guess confirmed). "
            "Delisting year still pending: the recorded lineage is 'merged into Sicor, which TEVA acquired "
            "2003' - the Sicor Inc. renaming (1999) and any symbol change need a primary citation before a "
            "delisting year is written."
        ),
    },
    "ivax_corp_baker_norton": {
        "cik": "0000772197",
        "rows": ["D1353"],
        "venue": "American Stock Exchange (AMEX)",
        "symbol": "IVX",
        "symbol_verbatim": ("IVAX' common stock is listed on the American Stock Exchange and is traded "
                            "under the symbol IVX. The following table sets forth the high and low closing "
                            "prices of IVAX' common stock as reported on the composite tape of the "
                            "American Stock Exchange and the cash dividends paid by IVAX for each of the "
                            "quarters indicated"),
        "citations": [{
            "doc": ("FY1996 Form 10-K405 (period 1996-12-31, filed 1997-03-31, acc 0000950170-97-000359), "
                    "cover Section 12(b) table + Item 5"),
            "url": "https://www.sec.gov/Archives/edgar/data/772197/0000950170-97-000359.txt",
            "evidence": (
                "Cover 12(b) table verbatim: 'SECURITIES REGISTERED PURSUANT TO SECTION 12(b) OF THE ACT / "
                "Title of each class: COMMON STOCK, PAR VALUE $.10 / Name of each exchange on which "
                "registered: AMERICAN STOCK EXCHANGE'. Commission File Number 1-09623; SEC header 'SROS: "
                "AMEX'. Item 5 symbol statement quoted in symbol_verbatim (AMEX:IVX). Item 1 verbatim: "
                "'IVAX markets brand name products under the Baker Norton(trademark) name, including the "
                "following products which are marketed primarily in the United States: Elmiron(R), an "
                "innovative drug used for the treatment of interstitial cystitis; Proglycem(R), used to "
                "treat hyperinsulinemia; and the urological medications Bicitra(R), Polycitra(R), "
                "Polycitra-K Crystals(R), Polycitra-LC(trademark, Neutra-Phos(R), and Neutra-Phos-K"
                "(trademark).' - Baker Norton is named as IVAX's own brand-name arm, so IVAX Corporation "
                "is the decision-date listed equity for the Elmiron row. 'As of March 20, 1997, there "
                "were 121,482,617 shares of Common Stock outstanding'; aggregate market value of voting "
                "stock held by non-affiliates on 1997-03-20 approximately $1.3 billion. Registrant "
                "'IVAX CORP /DE', former names IVAX CORP (1992-07-03), IVACO INDUSTRIES INC (1987-12-13), "
                "INLAND VACUUM INDUSTRIES INC (1987-06-11). Submission is 44 chunks; Item 5 is on printed "
                "page 17 per the filing's own table of contents."
            ),
        }],
        "note": (
            "v11 2026-09-18: VENUE AND SYMBOL VERIFIED for the FY1996 period that contains the Elmiron "
            "decision date 1996-09-26: AMEX:IVX. This CORRECTS the master's existing note wording "
            "'Nasdaq:IVX era' - the venue at the decision date was the AMERICAN STOCK EXCHANGE, not "
            "Nasdaq, per both the cover 12(b) table and Item 5. METHODOLOGICAL WARNING for the rest of "
            "the worklist: IVAX's FY1996 SEC file number is already 001-09623 (a '001-' prefix) while the "
            "12(b) exchange is AMEX, so the file-number prefix is NOT a venue indicator - venue must be "
            "read from the filing text, exactly as the hand-off requires. Delisting year still pending "
            "(recorded lineage: Teva acquired IVAX 2006); IVAX's EDGAR 10-K series runs to the FY2004 "
            "10-K filed 2005-03-16 (acc 0001193125-04-040619), so a Form 15 from 2006 should exist."
        ),
    },
    "carter_wallace": {
        "cik": "0000018000",
        "rows": ["D1359"],
        "venue": "New York Stock Exchange (Common Stock only; Class B Common Stock is 12(g))",
        "symbol": None,
        "citations": [{
            "doc": ("FY1997 Form 10-K405 (FYE 1997-03-31, filed 1997-06-17, acc 0000890163-97-000093), "
                    "cover Section 12(b)/12(g) tables + Item 5"),
            "url": "https://www.sec.gov/Archives/edgar/data/18000/0000890163-97-000093.txt",
            "evidence": (
                "Cover 12(b) table verbatim: 'Securities registered pursuant to Section 12(b) of the Act: "
                "TITLE OF EACH CLASS: Common Stock Par value $1.00 per share / NAME OF EACH EXCHANGE ON "
                "WHICH REGISTERED: New York Stock Exchange'. Cover 12(g) verbatim: 'Securities registered "
                "pursuant to Section 12(g) of the Act: Class B Common Stock, par value $1.00 per share "
                "(Title of Class)' - so the registrant had TWO classes and only the Common Stock was "
                "exchange-listed. Commission File Number 1-5910; SEC header 'SROS: NYSE'; fiscal year end "
                "0331. 'The number of shares of the registrant's Common Stock and Class B Common Stock "
                "outstanding at June 2, 1997 was 33,951,256 and 12,389,361, respectively. The aggregate "
                "market value of voting stock held by non-affiliates of the registrant as of June 2, 1997 "
                "was approximately $370,068,000.' Item 5 verbatim: 'ITEM 5. MARKET FOR REGISTRANT'S COMMON "
                "EQUITY AND RELATED STOCK-HOLDER MATTERS - Information required by this item is presented "
                "on pages 1 and 7 of the 1997 Annual Report to Stockholders and is herein expressly "
                "incorporated by reference.' Cover 'DOCUMENTS INCORPORATED BY REFERENCE: Annual Report to "
                "Stockholders for the fiscal year ended March 31, 1997 -> Parts I & II; Proxy Statement "
                "for the Annual Meeting of Stockholders to be held July 15, 1997 -> Parts III & IV'. The "
                "submission's document 1 also carries the financial statements and Schedule II through "
                "printed page 16; EX-10 (employment agreements dated April 1 and April 15, 1997) begins "
                "immediately after. Submission is 33 chunks."
            ),
        }],
        "note": (
            "v11 2026-09-18: VENUE VERIFIED = New York Stock Exchange for Carter-Wallace Common Stock, "
            "which is the class that owns the Astelin/Wallace Laboratories decision date 1996-11-01 (the "
            "FY1997 fiscal year runs 1996-04-01 to 1997-03-31). SYMBOL NOT LOCATED: Item 5 is incorporated "
            "by reference to pages 1 and 7 of the 1997 Annual Report to Stockholders, so the symbol is not "
            "in the 10-K document itself. The v10 'expected NYSE:CAR' remains an unverified guess and is "
            "NOT written to any field. Next step: read pages 1 and 7 of the 1997 Annual Report to "
            "Stockholders (an EX-21-type exhibit later in acc 0000890163-97-000093, chunks ~15-30), or the "
            "Item 5 of the FY1998/FY1999/FY2000 10-K, or the DEF 14A dated 1997-06-16 for the July 15, "
            "1997 annual meeting. Delisting year also pending (recorded lineage: MedPointe 2001)."
        ),
    },
    "roberts_pharmaceutical": {
        "cik": "0000853022",
        "rows": ["D1347", "D1379"],
        "venue": "NASDAQ National Market System at both decision dates",
        "symbol": None,
        "citations": [
            {
                "doc": ("Form 424B3 filed 1996-12-20 (acc 0000950130-96-004873, 15 KB) - 'First Supplement "
                        "to Prospectus dated November 7, 1996', Registration No. 333-13729"),
                "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-96-004873.txt",
                "evidence": (
                    "Fetched in full (2 chunks): this is a rights-plan supplement, NOT an offering "
                    "prospectus, and it does not state a trading symbol. Verbatim: 'The Board of Directors "
                    "of Roberts Pharmaceutical Corporation (the \"Company\") has declared a dividend "
                    "distribution of one Right for each outstanding share of the Company's Common Stock, "
                    "par value $.01 per share (the \"Common Stock\"), to shareholders of record at the "
                    "close of business on February 6, 1997.' Each Right is exercisable for one "
                    "one-hundredth of a share of Class B - Series A Junior Participating Preferred Stock "
                    "at $80. The supplement carves out Yamanouchi Pharmaceutical Co., Ltd. as an existing "
                    "15% beneficial owner. SEC header 'SROS: NASD'; SEC file number 333-13729. => the "
                    "hand-off's '424B prospectus cover' route is exhausted for Roberts: the only two "
                    "424-series filings on EDGAR (this one and acc 0000950130-97-000563 filed 1997-02-13, "
                    "5 KB) are both supplements to the November 7, 1996 prospectus."
                ),
            },
            {
                "doc": ("EDGAR filing list for CIK 0000853022 (browse-edgar, all types, retrieved "
                        "2026-09-18) - registration-history / deregistration evidence"),
                "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000853022&type=&dateb=&owner=include&count=100",
                "evidence": (
                    "The registrant held TWO SEC file numbers: 000-19173 (Section 12(g) registration, the "
                    "number on the 1999 Form 15-12G) and 001-10432 (Section 12(b) registration, the number "
                    "on the 1999 periodic filings), with a Form 8-A12B/A 'Registration of securities "
                    "[Section 12(b)]' filed 1999-07-27 (acc 0000950130-99-004255, 9 KB). Terminal filings: "
                    "Form 15-12G 'Securities registration termination [Section 12(g)]' filed 1999-12-22 "
                    "(acc 0000950162-99-001212, 4 KB); DEFM14A 'Definitive proxy statement relating to "
                    "merger or acquisition' filed 1999-11-23 (acc 0000950130-99-006712, 665 KB); 10-K/A and "
                    "10-Q/A filed 1999-11-22; last 10-Q filed 1999-11-08. => deregistration year 1999, "
                    "consistent with the recorded 'acquired by Shire 1999' lineage; and the 12(b) "
                    "registration only appears in 1999, AFTER both decision dates (1996-09-06, "
                    "1997-03-14), so the NASDAQ NMS venue recorded from the FY1996 10-K stands for both "
                    "rows."
                ),
            },
        ],
        "note": (
            "v11 2026-09-18: SYMBOL STILL NOT LOCATED, but the search space is now closed on two routes. "
            "(1) The 424-series route is exhausted - both 424B3s are rights-plan supplements without a "
            "symbol. (2) The FY1996 10-K Item 5 (captured in v10) says only 'The Company's Common Stock is "
            "traded in the over-the-counter market on the NASDAQ National Market System' with no symbol. "
            "Remaining routes, in cost order: FY1997/FY1998 10-K Item 5; the DEFM14A filed 1999-11-23 (acc "
            "0000950130-99-006712) whose market-price section should name the symbol; the Form 8-A12B/A "
            "filed 1999-07-27 (acc 0000950130-99-004255, 9 KB - cheap, but an 8-A names the exchange and "
            "class, not necessarily the symbol). NEW PRIMARY FACT recorded: Form 15-12G filed 1999-12-22 "
            "pins the deregistration year to 1999. The v10 'expected RPI' guess remains unverified and is "
            "NOT written to any field."
        ),
    },
    "pharmacia_upjohn": {
        "cik": "0000949573",
        "rows": ["D1330", "D1332", "D1373", "D1382", "D1390"],
        "venue": "NYSE",
        "symbol": None,
        "citations": [{
            "doc": ("FY1997 Form 10-K405 (period 1997-12-31, filed 1998-03-30, acc 0000950124-98-001758), "
                    "Exhibit 13 'PHARMACIA & UPJOHN Financial review', OVERVIEW"),
            "url": "https://www.sec.gov/Archives/edgar/data/949573/0000950124-98-001758.txt",
            "evidence": (
                "EX-13 verbatim: 'Pharmacia & Upjohn, Inc. (the company) was formed through the merger of "
                "Pharmacia AB and The Upjohn Company and began operating in November 1995. The merger was "
                "accounted for as a pooling of interests under U.S. generally accepted accounting "
                "principles. All data prior to the November 2, 1995 merger date have been combined as if "
                "the companies had been merged during the prior periods.' => pins the Upjohn/Pharmacia AB "
                "merger date to 1995-11-02, corroborating the master's recorded 'merged into Pharmacia & "
                "Upjohn Nov-1995' lineage for all five Upjohn rows, and confirming Pharmacia & Upjohn, "
                "Inc. is the registrant at every one of the five decision dates (1996-06-05 through "
                "1997-07-01). Same EX-13: restructuring charges $316 million ($.39/share) in 1997, $518 "
                "million ($.62/share) in 1996, $104 million ($.13/share) in 1995; 1997 total revenue "
                "$6,710 million vs $7,286 million in 1996; 1997 net earnings $323 million, diluted $.61 "
                "per share; Pharmacia Biotech merged with Amersham Life Science in 1997 (Pharmacia & "
                "Upjohn owns 45 percent of Amersham Pharmacia Biotech Ltd). Submission structure mapped "
                "this pass: 38 chunks; the main 10-K document (Items 1-14 plus the EX-12 ratio-of-earnings "
                "schedule) ends mid-chunk-15 and EX-13 begins there, so Item 5 is inside chunks 0-14."
            ),
        }],
        "note": (
            "v11 2026-09-18: SYMBOL STILL PENDING, but the hunt is now bounded - the FY1997 10-K405 "
            "submission is 38 chunks, its main document occupies chunks 0-14, and Item 5 must be inside "
            "that range (v10 already has the cover 12(b) table 'Common Stock (par value $.01) - New York "
            "Stock Exchange' from chunk 0). Next step: probe chunks ~4-8 of acc 0000950124-98-001758 for "
            "the Item 5 market paragraph. NEW PRIMARY FACT recorded this pass: the exact merger date "
            "1995-11-02 from EX-13. The v10 'expected PNU' guess remains unverified and is NOT written to "
            "any field."
        ),
    },
}

# index-row status/action text (v11)
EX_CYTO = ("NASDAQ NMS:CYTO (Cytogen Corp; venue+symbol per FY1996 10-K Item 5; ticker column "
           "deliberately blank - see note; delisting year pending)")
INDEX_ROWS = {
    "D1345": (RESOLVED, "AMEX:AVM (Advanced Magnetics Inc.; venue+symbol per FY1996 10-K405 Item 5, delisting year pending)"),
    "D1363": (RESOLVED, "AMEX:AVM (Advanced Magnetics Inc.; venue+symbol per FY1996 10-K405 Item 5, delisting year pending)"),
    "D1396": (RESOLVED, "formerly NASDAQ NMS:NXCO, delisted 1998 (Elan Corporation plc merger)"),
    "D1357": (RESOLVED, EX_CYTO),
    "D1381": (RESOLVED, EX_CYTO),
    "D1338": (RESOLVED, "NASDAQ NMS:IMMU (Immunomedics Inc.; venue+symbol per FY1996 10-K Item 5; ticker column deliberately blank - see note; delisting year pending)"),
    "D1394": (RESOLVED, "NASDAQ NMS:GNSA (Gensia Sicor Inc.; venue+symbol per FY1997 10-K Item 5, delisting year pending)"),
    "D1353": (RESOLVED, "AMEX:IVX (IVAX Corporation - Baker Norton was IVAX's brand-name arm; venue+symbol per FY1996 10-K405 cover 12(b) + Item 5, delisting year pending)"),
    "D1359": (VENUE_PENDING, "NYSE (Carter-Wallace, Inc.; venue per FY1997 10-K405 12(b) cover, ticker pending)"),
}

# Rows whose verified symbol is written to the EXCHANGE field only, never to the
# master `ticker` column. Both reasons are downstream-data hazards observed by
# running the builders, not data doubts - the symbols themselves are verified:
#   * D1338 IMMU  - build_core_analysis_table.py builds class_by_ticker with
#     setdefault() in master order and applies it to EVERY row sharing a ticker;
#     IMMU is already carried by D376 (Trodelvy, 2020-04-22, US-LISTED) at master
#     index 97, ahead of D1338 at index 1327, so filling it would re-class this
#     1996 row as US-LISTED.
#   * D1357/D1381 CYTO - build_company_scores.py groups by ticker when one is
#     present and by normalised company_name when it is not. D1231 (OncoScint,
#     1992-12-29) carries the SAME company_name as these two rows but a blank
#     ticker (its 1992 symbol was never verified from a period filing, and the
#     FY1996 10-K only proves CYTO as of its 1997-03-24 filing date). Filling
#     CYTO here splits one company's track record into two score rows (3
#     approvals -> 2 + 1), which was observed in a trial run and reverted.
NO_TICKER_FILL = {"D1338", "D1357", "D1381"}

ACTION = {
    "D1345": ("v11 2026-09-18: SYMBOL VERIFIED from the period filing - AMEX:AVM (Item 5: 'The Company's "
              "common stock is listed on the American Stock Exchange under the symbol AVM.'). Corrects the "
              "v9/v10 guesses 'ANM'/'AinM' and the master note's 'NASDAQ:AMAG from its 1997 IPO' (AMAG is "
              "the post-2007 rename ticker, not the decision-date symbol). Remaining: delisting year."),
    "D1363": ("v11 2026-09-18: SYMBOL VERIFIED from the period filing - AMEX:AVM (same Item 5 quote as "
              "D1345). The 1996-12-06 decision falls in FY1997 Q1, which this filing's Item 5 table does "
              "not cover, but the cover prices the AMEX line at 1996-12-16 ($15.375 last sale), six days "
              "after the decision - contemporaneous. Remaining: delisting year."),
    "D1396": ("v11 2026-09-18: FULLY RESOLVED - NASDAQ NMS:NXCO per FY1997 10-K Item 5 ('the Company's "
              "Common Stock has been traded on the NASDAQ National Market System under the symbol NXCO'), "
              "delisting year 1998 pinned by the Elan merger DEF 14A filed 1998-07-02 (Merger Agreement "
              "dated 1998-04-29; vote 1998-08-11; 0.51 Elan ADS per Neurex share) plus Form 15-15D filed "
              "1998-08-14. Corrects the v10 index guess 'NXRX'. Nothing remaining."),
    "D1357": ("v11 2026-09-18: SYMBOL VERIFIED from the period filing - NASDAQ NMS:CYTO (FY1996 10-K "
              "Item 5: 'CYTOGEN Common Stock is traded on the NASDAQ National Market tier of The NASDAQ "
              "Stock Market under the trading symbol \"CYTO.\"'). The 1996-10-28 ProstaScint decision is "
              "inside this filing's period. The master TICKER COLUMN IS DELIBERATELY BLANK: D1231 "
              "(OncoScint, 1992-12-29) shares this company_name with a blank ticker and "
              "build_company_scores.py groups by ticker when present, so a partial CYTO fill would split "
              "Cytogen's record across two score rows. Remaining: delisting year."),
    "D1381": ("v11 2026-09-18: SYMBOL VERIFIED from the period filing - NASDAQ NMS:CYTO (same Item 5 quote "
              "as D1357). CAVEAT: the FY1996 10-K was filed 1997-03-24, four days BEFORE the 1997-03-28 "
              "Quadramet decision, so continuity of the symbol through the decision date should be "
              "confirmed from the FY1997 10-K (acc 0000725058-98-000010, filed 1998-03-31). The master "
              "TICKER COLUMN IS DELIBERATELY BLANK (same D1231 grouping reason as D1357). Remaining: "
              "that confirmation + delisting year."),
    "D1338": ("v11 2026-09-18: SYMBOL VERIFIED from the period filing - NASDAQ NMS:IMMU (FY1996 10-K "
              "Item 5: 'The Company's Common Stock is traded on The Nasdaq National Market under the "
              "symbol \"IMMU\".'); the decision-date quarter (FYE 1996-06-30) is priced in that Item 5 "
              "table at $9 7/8 high / $6 1/2 low. The master TICKER COLUMN IS DELIBERATELY LEFT BLANK: "
              "IMMU is already carried by D376 (Trodelvy 2020-04-22, class US-LISTED) earlier in the "
              "master, and build_core_analysis_table.py propagates a ticker-keyed class to every row "
              "sharing the ticker, so filling it here would mis-class this 1996 row as US-LISTED. "
              "Remaining: delisting year + a decision-date-aware class model before the column is filled."),
    "D1394": ("v11 2026-09-18: SYMBOL VERIFIED from the period filing - NASDAQ NMS:GNSA (FY1997 10-K "
              "Item 5: 'The Company's Common Stock is traded in the over-the-counter market on the Nasdaq "
              "National Market under the symbol \"GNSA\".'); the decision quarter Jul 1 - Sep 30 1997 is "
              "priced in that table at $7.81 high / $4.41 low. Remaining: delisting year (needs the Sicor "
              "Inc. 1999 renaming / Teva 2003 lineage cited from a filing)."),
    "D1353": ("v11 2026-09-18: VENUE + SYMBOL VERIFIED - AMEX:IVX. FY1996 10-K405 cover 12(b): 'COMMON "
              "STOCK, PAR VALUE $.10 / AMERICAN STOCK EXCHANGE'; Item 5: 'IVAX' common stock is listed on "
              "the American Stock Exchange and is traded under the symbol IVX.' Item 1 names Baker Norton "
              "as IVAX's own brand-name arm and lists Elmiron(R) for interstitial cystitis. CORRECTS the "
              "master's 'Nasdaq:IVX era' wording - the venue was AMEX. WARNING: IVAX's SEC file number was "
              "already 001-09623 while the 12(b) exchange was AMEX, so file-number prefixes are not a "
              "venue indicator. Remaining: delisting year (lineage says Teva 2006; a Form 15 should exist)."),
    "D1359": ("v11 2026-09-18: VENUE VERIFIED, SYMBOL NOT LOCATED. FY1997 10-K405 cover 12(b): 'Common "
              "Stock Par value $1.00 per share / New York Stock Exchange' (and a second, 12(g)-only "
              "class: 'Class B Common Stock, par value $1.00 per share'). Item 5 is incorporated by "
              "reference: 'Information required by this item is presented on pages 1 and 7 of the 1997 "
              "Annual Report to Stockholders'. Remaining: read those two pages (an Annual Report exhibit "
              "later in acc 0000890163-97-000093) or the FY1998/FY1999/FY2000 10-K Item 5, then the "
              "delisting year. The v10 'expected NYSE:CAR' is still an unverified guess."),
    "D1347": ("v10 2026-09-18: venue verified from the period filing. v11 2026-09-18: the 424-series route "
              "is now exhausted - both 424B3s on EDGAR (1996-12-20 acc 0000950130-96-004873, 1997-02-13 "
              "acc 0000950130-97-000563) are supplements to the November 7, 1996 prospectus and the "
              "1996-12-20 one is a rights-plan supplement with no symbol. NEW: Form 15-12G filed "
              "1999-12-22 pins the deregistration year to 1999, and the Section 12(b) file number "
              "001-10432 first appears on 1999 filings (8-A12B/A 1999-07-27), i.e. AFTER both decision "
              "dates, so NASDAQ NMS stands. Remaining: symbol from the FY1997/FY1998 10-K Item 5 or the "
              "DEFM14A filed 1999-11-23 (acc 0000950130-99-006712)."),
    "D1379": ("v10 2026-09-18: venue verified from the period filing. v11 2026-09-18: the 424-series route "
              "is now exhausted - both 424B3s on EDGAR (1996-12-20 acc 0000950130-96-004873, 1997-02-13 "
              "acc 0000950130-97-000563) are supplements to the November 7, 1996 prospectus and the "
              "1996-12-20 one is a rights-plan supplement with no symbol. NEW: Form 15-12G filed "
              "1999-12-22 pins the deregistration year to 1999, and the Section 12(b) file number "
              "001-10432 first appears on 1999 filings (8-A12B/A 1999-07-27), i.e. AFTER both decision "
              "dates, so NASDAQ NMS stands. Remaining: symbol from the FY1997/FY1998 10-K Item 5 or the "
              "DEFM14A filed 1999-11-23 (acc 0000950130-99-006712)."),
    # rows whose evidence changed but whose index action text only needs the v11 pointer
    "D1330": "PNU_SYMBOL_PENDING",
    "D1332": "PNU_SYMBOL_PENDING",
    "D1373": "PNU_SYMBOL_PENDING",
    "D1382": "PNU_SYMBOL_PENDING",
    "D1390": "PNU_SYMBOL_PENDING",
}
PNU_ACTION = ("v10 2026-09-18: venue verified from the period filing (see sec_edgar_company_search). "
              "v11 2026-09-18: the hunt is now bounded - the FY1997 10-K405 submission (acc "
              "0000950124-98-001758) is 38 chunks, its main 10-K document occupies chunks 0-14, and Item 5 "
              "is inside that range; EX-13 'PHARMACIA & UPJOHN Financial review' begins mid-chunk-15 and "
              "pins the Upjohn/Pharmacia AB merger date to 1995-11-02 ('All data prior to the November 2, "
              "1995 merger date have been combined as if the companies had been merged during the prior "
              "periods'), corroborating the recorded Nov-1995 lineage for all five Upjohn rows. Remaining: "
              "probe chunks ~4-8 for the Item 5 symbol, then the 2000 Monsanto/Pharmacia Corp demerger "
              "year. The v10 'expected PNU' guess is still unverified.")


def note_for(did, key):
    """Dated note appended to master.notes (prior text is never removed)."""
    co = EVIDENCE[key]
    cite = co["citations"][0]
    ex = INDEX_ROWS[did][1] if did in INDEX_ROWS else None
    if co.get("symbol") and co["symbol"] in (ex or ""):
        head = (f"{TAG} (v11 symbol pass): decision-date listing SYMBOL verified from the registrant's "
                f"own period filing on EDGAR - {co['venue']}: {co['symbol']} ({cite['doc']}, {cite['url']}). "
                f"Item 5 verbatim: \"{co['symbol_verbatim']}\"")
    else:
        head = (f"{TAG} (v11 symbol pass): {cite['doc']} fetched live ({cite['url']}). "
                f"Symbol NOT written - see the recorded evidence and next step.")
    extra = {
        "D1345": (" Corrects the earlier note's 'NASDAQ:AMAG from its 1997 IPO': AMAG is the ticker of the "
                  "renamed registrant (EDGAR name change to AMAG Pharmaceuticals 2007-07-05); the "
                  "decision-date security was AMEX:AVM. Item 5 prices FY1996 Q4 (Jul-Sep 1996, the Feridex "
                  "quarter) at $19 7/8 high / $16 1/4 low - evidence only, no price row created (repo law: "
                  "price events come from the Yahoo fetch-job pipeline)."),
        "D1363": (" Corrects the earlier note's 'NASDAQ:AMAG from its 1997 IPO': the decision-date security "
                  "was AMEX:AVM. The 1996-12-06 GastroMARK decision falls in FY1997 Q1, outside this "
                  "filing's Item 5 table, but the cover prices the AMEX line at 1996-12-16 ($15.375 last "
                  "reported sale) - six days after the decision."),
        "D1396": (" Corrects the v10 index's 'NXRX expected' guess; confirms this row's pre-existing "
                  "'NASDAQ:NXCO era' note. DELISTING YEAR NOW PINNED = 1998: DEF 14A filed 1998-07-02 (acc "
                  "0000950130-98-003434) recites the 'Agreement and Plan of Merger, dated as of April 29, "
                  "1998' with a wholly-owned subsidiary of Elan Corporation, plc, 0.51 Elan ADS per Neurex "
                  "share, stockholder vote 1998-08-11; Form 15-15D filed 1998-08-14 (acc "
                  "0000950162-98-000894) suspends the duty to report. The same proxy states Elan's ADSs "
                  "traded on The New York Stock Exchange - usable for the Athena/Zanaflex attribution case "
                  "(D1362). Item 5 prices 1997 Q3 (the Corlopam quarter) at $16.00 high / $11.63 low - "
                  "evidence only, no price row created."),
        "D1357": (" TICKER COLUMN DELIBERATELY LEFT BLANK although the symbol is verified: D1231 "
                  "(OncoScint, 1992-12-29) carries the same company_name with a blank ticker, and "
                  "build_company_scores.py groups by ticker when present - filling CYTO on these two rows "
                  "only would split Cytogen's record into two score rows (observed in a trial run, then "
                  "reverted). The 1996-10-28 ProstaScint decision is inside this filing's period. Delisting year "
                  "still pending; Cytogen's EDGAR 10-K series runs to the FY1998 10-K filed 1999-02-22 "
                  "(acc 0000725058-99-000007) and filings continue to 2008, so the end-of-listing year "
                  "needs its own citation."),
        "D1381": (" TICKER COLUMN DELIBERATELY LEFT BLANK (same reason as D1357: D1231 shares this "
                  "company_name with a blank ticker, and a partial CYTO fill splits the company across two "
                  "score rows). CAVEAT: this 10-K was filed 1997-03-24, four days BEFORE the 1997-03-28 Quadramet "
                  "decision, so symbol continuity through the decision date should be confirmed from the "
                  "FY1997 10-K (acc 0000725058-98-000010, filed 1998-03-31). Delisting year still pending."),
        "D1338": (" TICKER COLUMN DELIBERATELY LEFT BLANK although the symbol is verified: IMMU is already "
                  "carried by D376 (Trodelvy, 2020-04-22, us_investable_class US-LISTED) at master index "
                  "97, ahead of this row at index 1327, and build_core_analysis_table.py propagates a "
                  "ticker-keyed class (setdefault in master order) to every row sharing the ticker - "
                  "filling IMMU here would re-class this 1996 row as US-LISTED. Item 5 prices the quarter "
                  "ended 1996-06-30 (the CEA-Scan quarter) at $9 7/8 high / $6 1/2 low - evidence only, no "
                  "price row created."),
        "D1394": (" Item 5 prices the Jul 1 - Sep 30 1997 quarter (the Genesa quarter) at $7.81 high / "
                  "$4.41 low - evidence only, no price row created. Delisting year still pending: the "
                  "recorded lineage ('merged into Sicor, which TEVA acquired 2003') needs the Sicor Inc. "
                  "1999 renaming and any symbol change cited from a filing before a year is written."),
        "D1353": (" CORRECTS this row's earlier note wording 'Nasdaq:IVX era' - the venue at the decision "
                  "date was the AMERICAN STOCK EXCHANGE, per BOTH the cover 12(b) table ('COMMON STOCK, "
                  "PAR VALUE $.10 / AMERICAN STOCK EXCHANGE') and Item 5. Item 1 also confirms the "
                  "sponsor chain: 'IVAX markets brand name products under the Baker Norton(trademark) "
                  "name, including ... Elmiron(R), an innovative drug used for the treatment of "
                  "interstitial cystitis'. METHODOLOGICAL WARNING: IVAX's SEC file number was already "
                  "001-09623 while the 12(b) exchange was AMEX, so file-number prefixes are not a venue "
                  "indicator. Delisting year still pending (recorded lineage: Teva 2006)."),
        "D1359": (" VENUE VERIFIED = New York Stock Exchange for Carter-Wallace Common Stock; the registrant "
                  "had a second, 12(g)-only class ('Class B Common Stock, par value $1.00 per share'). "
                  "SYMBOL NOT LOCATED and left blank: Item 5 of this 10-K reads 'Information required by "
                  "this item is presented on pages 1 and 7 of the 1997 Annual Report to Stockholders and "
                  "is herein expressly incorporated by reference', so the symbol is not in the 10-K "
                  "document. The v10 'expected NYSE:CAR' remains an unverified guess. FY1997 covers the "
                  "1996-11-01 Astelin decision (fiscal year 1996-04-01 to 1997-03-31); Wallace "
                  "Laboratories was the Carter-Wallace division."),
        "D1347": (" NEW v11 primary facts: the 424-series route is exhausted (both 424B3s are supplements "
                  "to the November 7, 1996 prospectus; the 1996-12-20 one, acc 0000950130-96-004873, is a "
                  "rights-plan supplement that names no symbol and carves out Yamanouchi Pharmaceutical "
                  "Co., Ltd. as a 15% holder); Form 15-12G filed 1999-12-22 (acc 0000950162-99-001212) pins "
                  "the deregistration year to 1999; the Section 12(b) file number 001-10432 first appears "
                  "on 1999 filings (Form 8-A12B/A 1999-07-27, acc 0000950130-99-004255), i.e. after this "
                  "decision date, so the NASDAQ NMS venue recorded from the FY1996 10-K stands. Symbol "
                  "still blank; the v10 'expected RPI' is an unverified guess."),
        "D1379": (" NEW v11 primary facts: the 424-series route is exhausted (both 424B3s are supplements "
                  "to the November 7, 1996 prospectus; the 1996-12-20 one, acc 0000950130-96-004873, is a "
                  "rights-plan supplement that names no symbol and carves out Yamanouchi Pharmaceutical "
                  "Co., Ltd. as a 15% holder); Form 15-12G filed 1999-12-22 (acc 0000950162-99-001212) pins "
                  "the deregistration year to 1999; the Section 12(b) file number 001-10432 first appears "
                  "on 1999 filings (Form 8-A12B/A 1999-07-27, acc 0000950130-99-004255), i.e. after both "
                  "decision dates, so the NASDAQ NMS venue recorded from the FY1996 10-K stands. Symbol "
                  "still blank; the v10 'expected RPI' is an unverified guess."),
    }
    tail = (" Evidence: data/staging/pre2000_sponsor_edgar_evidence.json (v11 additions)."
            if key in EVIDENCE else "")
    return head + extra.get(did, "") + tail


# --------------------------------------------------------------------------
def main() -> None:
    ev = json.load(open(EV, encoding="utf-8"))

    # --- merge the v11 evidence into the shared store ---------------------
    pending = ev["companies"].get("citations_located_not_yet_fetched", {})
    for key, co in EVIDENCE.items():
        old = ev["companies"].get(key)
        if old:
            # keep every v10 citation verbatim, append the v11 ones, refresh
            merged = dict(old)
            merged["cik"] = co.get("cik") or old.get("cik")
            merged["rows"] = co["rows"]
            merged["venue"] = co["venue"]
            if co.get("symbol"):
                merged["symbol"] = co["symbol"]
                merged["symbol_verbatim"] = co["symbol_verbatim"]
            have = {c["url"] for c in merged.get("citations", [])}
            merged["citations"] = list(merged.get("citations", [])) + [
                c for c in co["citations"] if c["url"] not in have]
            merged["note"] = co["note"]
            merged["v10_note_superseded"] = old.get("note")
            ev["companies"][key] = merged
        else:
            ev["companies"][key] = co
        pending.pop(key, None)
    ev["companies"]["citations_located_not_yet_fetched"] = pending
    ev["v11_update"] = {
        "captured_utc": "2026-09-18T07:20:00Z",
        "what_changed": ("v11 symbol pass: 8 rows reach RESOLVED (venue+ticker per period 10-K) - "
                         "Advanced Magnetics AMEX:AVM (D1345, D1363), Neurex NASDAQ NMS:NXCO delisted 1998 "
                         "(D1396), Cytogen NASDAQ NMS:CYTO (D1357, D1381), Immunomedics NASDAQ NMS:IMMU "
                         "(D1338, ticker column deliberately blank), Gensia Sicor NASDAQ NMS:GNSA (D1394), "
                         "IVAX/Baker Norton AMEX:IVX (D1353). Carter-Wallace moves CITATION-LOCATED -> "
                         "VENUE-VERIFIED (NYSE per the FY1997 12(b) cover; Item 5 is incorporated by "
                         "reference to pages 1 and 7 of the 1997 Annual Report to Stockholders, so the "
                         "symbol is not in the 10-K). Roberts keeps VENUE-VERIFIED with the 424-series "
                         "route closed and Form 15-12G 1999-12-22 pinning deregistration to 1999. "
                         "Pharmacia & Upjohn keeps VENUE-VERIFIED with EX-13 pinning the merger date to "
                         "1995-11-02 and the Item 5 search bounded to chunks 0-14 of 38."),
        "wrong_guesses_corrected": {
            "advanced_magnetics": "v9/v10 'ANM'/'AinM' -> AMEX:AVM per FY1996 10-K405 Item 5",
            "neurex": "v10 index 'NXRX expected' -> NASDAQ NMS:NXCO per FY1997 10-K Item 5",
            "ivax_corp_baker_norton": "master note 'Nasdaq:IVX era' -> AMEX:IVX per FY1996 10-K405 cover 12(b) + Item 5",
        },
        "guesses_confirmed": {"cytogen": "CYTO", "immunomedics": "IMMU", "gensia_sicor": "GNSA"},
        "guesses_still_unverified_and_not_written": {
            "warner_lambert": "WLA", "pharmacia_upjohn": "PNU", "roberts_pharmaceutical": "RPI",
            "carter_wallace": "CAR", "block_drug": "BLOCA", "athena_neurosciences/elan": "ELN",
            "dupont_pharmaceuticals/dupont": "DD",
        },
        "classifier_gap_found": ("scripts/classify_listing.py US_VENUES = ('NASDAQ', 'NYSE') has no AMEX "
                                 "entry, so classify('formerly AMEX:AVM, ...') returns NON-US LISTING ONLY "
                                 "for a US venue. It cannot corrupt committed classes (the script preserves "
                                 "them and only appends a dated note), which is why the two AMEX rows in "
                                 "this pass use the descriptive 'AMEX:AVM (...)' form rather than the "
                                 "'formerly AMEX:...' form. Adding 'AMEX' to US_VENUES is the one-line fix; "
                                 "it is behaviour-preserving on the current master (verified by re-running "
                                 "the classifier and diffing)."),
    }
    with EV.open("w", encoding="utf-8") as f:
        json.dump(ev, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"evidence: {len(EVIDENCE)} company entries merged into {EV.name}")

    # --- master ----------------------------------------------------------
    master = list(csv.DictReader(open(MASTER, newline="", encoding="utf-8-sig")))
    header = list(master[0].keys())
    by_id = {r["decision_id"]: r for r in master}
    key_of_row = {}
    for key, co in EVIDENCE.items():
        for did in co["rows"]:
            key_of_row[did] = key

    touched_ex = touched_tk = touched_note = 0
    for did, key in sorted(key_of_row.items()):
        if did not in ACTION:
            continue
        r = by_id[did]
        note = note_for(did, key)
        if did in INDEX_ROWS:
            status, ex = INDEX_ROWS[did]
            if r["exchange"] != ex:
                r["exchange"] = ex
                touched_ex += 1
            co = EVIDENCE[key]
            if co.get("symbol") and did not in NO_TICKER_FILL and co["symbol"] in ex:
                if r["ticker"] != co["symbol"]:
                    r["ticker"] = co["symbol"]
                    touched_tk += 1
        r["notes"] = (r["notes"].rstrip(" |") + " | " + note) if r["notes"].strip() else note
        touched_note += 1

    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(master)
    print(f"master: exchange rewritten on {touched_ex} rows, ticker filled on {touched_tk} rows, "
          f"dated notes appended to {touched_note} rows")

    # --- index ------------------------------------------------------------
    idx = list(csv.DictReader(open(INDEX, newline="", encoding="utf-8-sig")))
    idx_header = list(idx[0].keys())
    n_status = n_ex = n_act = n_cite = 0
    for r in idx:
        did = r["decision_id"]
        key = key_of_row.get(did)
        if not key:
            continue
        co = EVIDENCE[key]
        if did in INDEX_ROWS:
            status, ex = INDEX_ROWS[did]
            if r["status"] != status:
                r["status"] = status
                n_status += 1
            if r["master_exchange"] != ex:
                r["master_exchange"] = ex
                n_ex += 1
            # some rows keep a blank ticker on purpose - see NO_TICKER_FILL
            if co.get("symbol") and did not in NO_TICKER_FILL:
                r["master_ticker"] = co["symbol"]
        if did in ACTION:
            act = PNU_ACTION if ACTION[did] == "PNU_SYMBOL_PENDING" else ACTION[did]
            r["action_for_reviewer"] = act
            n_act += 1
        # lossless: keep any descriptive text v10 wrote, add the replayable URL
        url = co["citations"][0]["url"]
        cur = r["sec_edgar_company_search"].strip()
        if cur and cur != url and not cur.startswith("http"):
            r["sec_edgar_company_search"] = f"{cur} | {url}"
        elif not cur:
            r["sec_edgar_company_search"] = url
        n_cite += 1
    assert len(idx) == 67, f"index must stay at 67 rows, got {len(idx)}"
    with INDEX.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=idx_header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(idx)
    print(f"index: {n_status} statuses changed, {n_ex} exchange strings upgraded, "
          f"{n_act} reviewer actions rewritten, {n_cite} citations repointed")


if __name__ == "__main__":
    main()
