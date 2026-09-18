#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-2000 sponsor resolution, v11 second wave (2026-09-18) - Warner-Lambert cover.

The v11 first wave resolved 8 rows to venue+ticker. This wave records what was
recovered before the page-fetch tool failed mid-pass: the cover page of
Warner-Lambert's FY1997 Form 10-K (chunk 0 of 43) was fetched successfully from
www.sec.gov, and it changes the search plan for the four Parke-Davis rows.

New verified facts (all quoted verbatim from that chunk):
  * 12(b): Common Stock (Par Value $1 Per Share) is registered on THREE US
    exchanges - The New York Stock Exchange, The Chicago Stock Exchange and The
    Pacific Stock Exchange - plus "Rights to Purchase Series A Junior
    Participating Preferred Stock" on the same three. 12(g): None. SEC header
    lists SROS: CSX, NYSE, PCX. Commission file number 1-3608.
  * "DOCUMENTS INCORPORATED BY REFERENCE: Portions of the Warner-Lambert Company
    Annual Report to Shareholders for 1997 -- Part I, Part II and Part IV."
    Item 5 is in Part II, so - exactly as with Carter-Wallace - the trading
    symbol is probably NOT in the 10-K document but in the Annual Report exhibit
    inside the same submission. The hunt should skip the 10-K body.
  * Item 1 names the sponsor chain verbatim: "ethical pharmaceuticals and
    biologicals under trademarks and trade names such as PARKE-DAVIS and
    GOEDECKE", and lists CEREBYX (D1342) and OMNICEF (D1409) among its products.
  * 272,614,910 shares outstanding and ~$39.9bn non-affiliate market value as of
    1998-02-27.

Nothing here is a ticker symbol, so no symbol is written and no row moves to
RESOLVED. One UNVERIFIED POINTER found by web search while the fetch tool was
down is recorded as such, with an explicit do-not-use warning: it ends the
AMAG-on-Nasdaq line (2020), not the AVM-on-AMEX line the two Advanced Magnetics
rows are about.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "data" / "staging" / "pre2000_sponsor_edgar_evidence.json"
INDEX = ROOT / "data" / "pre2000_sponsor_resolution_index.csv"
MASTER = ROOT / "data" / "fda_decisions_master.csv"
TAG = "SPONSOR-RESOLVED 2026-09-18 (v11 second wave)"

WL_URL = "https://www.sec.gov/Archives/edgar/data/104669/0000950117-98-000602.txt"
WL_DOC = ("FY1997 Form 10-K (period 1997-12-31, filed 1998-03-24, acc 0000950117-98-000602), "
          "cover page and Item 1 (chunk 0 of 43)")
WL_EVIDENCE = (
    "Cover verbatim: 'SECURITIES REGISTERED PURSUANT TO SECTION 12(B) OF THE ACT: TITLE OF EACH CLASS: "
    "Common Stock (Par Value $1 Per Share) / NAME OF EACH EXCHANGE ON WHICH REGISTERED: The New York "
    "Stock Exchange, Inc. | The Chicago Stock Exchange, Inc. | The Pacific Stock Exchange, Inc.' and a "
    "second 12(b) class 'Rights to Purchase Series A Junior Participating Preferred Stock' on the same "
    "three exchanges. 'SECURITIES REGISTERED PURSUANT TO SECTION 12(g) OF THE ACT: None.' SEC header "
    "'SROS: CSX / SROS: NYSE / SROS: PCX'; 'SEC FILE NUMBER: 001-03608'; printed cover 'COMMISSION FILE "
    "NUMBER 1-3608'; registrant 'WARNER-LAMBERT COMPANY', a Delaware corporation organized in 1920, CIK "
    "0000104669, SIC 2834, FYE 1231, former name 'WARNER LAMBERT PHARMACEUTICAL CO' (name change "
    "1970-12-30); 9 public documents in the submission; filed 19980324 for period 19971231. "
    "'The aggregate market value of the voting stock held by non-affiliates of Warner-Lambert Company as "
    "of February 27, 1998 was approximately $39.9 billion. The number of shares outstanding of the "
    "registrant's Common Stock as of February 27, 1998 was 272,614,910 shares, Common Stock, par value "
    "$1.00 per share.' 'DOCUMENTS INCORPORATED BY REFERENCE: Portions of the Warner-Lambert Company "
    "Annual Report to Shareholders for 1997 -- Part I, Part II and Part IV. Portions of the Proxy "
    "Statement for Annual Meeting of Stockholders of Warner-Lambert Company to be held April 28, 1998 -- "
    "Part III.' Item 1 verbatim: 'The principal products of Warner-Lambert in its Pharmaceutical Products "
    "segment are ethical pharmaceuticals, biologicals and capsules. Ethical Pharmaceuticals and "
    "Biologicals: Warner-Lambert manufactures and/or sells, in the United States and/or internationally, "
    "an extensive line of ethical pharmaceuticals and biologicals under trademarks and trade names such "
    "as PARKE-DAVIS and GOEDECKE. Among these products are analgesics (PONSTAN, PONSTEL, VALORON, "
    "VALORON-N, VEGANIN and VALTRAN), anesthetics (KETALAR), anthelmintics (VANQUIN), anticonvulsants "
    "(CELONTIN, CEREBYX, DILANTIN, NEURONTIN and ZARONTIN), anti-infectives (CHLOROMYCETIN, COLYMYCIN and "
    "OMNICEF), antivaricosities (HEPATHROMBIN), anti-viral agents...' - PARKE-DAVIS is named as "
    "Warner-Lambert's own trade name, and CEREBYX (master D1342) and OMNICEF (master D1409) appear in the "
    "product list, corroborating the sponsor chain for both rows from the registrant's own filing."
)
WL_NOTE = (
    "v11 second wave 2026-09-18: cover page fetched (chunk 0 of 43) - venue upgraded from 'NYSE' to the "
    "three exchanges the 12(b) table actually names (NYSE + Chicago + Pacific; NYSE kept first because it "
    "is the primary listing and because scripts/classify_listing.py keys on the leading venue token). "
    "SYMBOL STILL PENDING, and the search plan changed: Part II (which contains Item 5) is incorporated by "
    "reference to the 1997 Annual Report to Shareholders, so the trading symbol is most likely in that "
    "Annual Report exhibit inside the same submission rather than in the 10-K body - the same trap as "
    "Carter-Wallace. Next step: list the submission's 9 documents and open the Annual Report exhibit "
    "(EX-13-class) market-for-common-equity page, or fall back to the DEF 14A for the 1998-04-28 annual "
    "meeting. The v10 'expected WLA' guess remains unverified and is written to nothing. NOTE: the page-"
    "fetch tool failed immediately after this chunk (every later call returned SignatureDoesNotMatch from "
    "its internal file proxy, including for other submissions and non-EDGAR URLs), so chunks 1-42 were "
    "never retrieved."
)

AMAG_POINTER = {
    "doc": ("UNVERIFIED POINTER - Form 8-K dated 2020-11-16 on the same CIK 792977 lineage "
            "(Advanced Magnetics Inc. -> AMAG Pharmaceuticals Inc.)"),
    "url": "https://www.sec.gov/Archives/edgar/data/792977/000110465920125941/tm2036059d2_8k.htm",
    "evidence": (
        "DO NOT WRITE A VALUE FROM THIS ENTRY. It was located by web search on 2026-09-18 while the page-"
        "fetch tool was down, so the document has NOT been read verbatim in full and its context is "
        "unverified; a search snippet is not a primary-source read. What the snippet says: after the Covis "
        "merger closed on 2020-11-16, 'AMAG notified The Nasdaq Global Select Market (\"NASDAQ\") of the "
        "consummation of the Merger and requested that NASDAQ (i) halt trading in the Shares, (ii) suspend "
        "trading of and delist the Shares and (iii) file with the SEC a notification of removal from "
        "listing and/or registration on Form 25'; 'NASDAQ filed the Form 25 with the SEC on November 16, "
        "2020'; and AMAG intended to file a Form 15 terminating Section 12(g) registration. WHY IT IS NOT "
        "ENOUGH EVEN ONCE FETCHED: this ends the AMAG-on-Nasdaq line. Master rows D1345/D1363 are about "
        "the AVM-on-AMEX line, which ended earlier - EDGAR records this registrant's name change to AMAG "
        "PHARMACEUTICALS INC on 2007-07-05. The citation still needed for those rows is a Form 25 for the "
        "AMEX line or the 2007 name/symbol-change 8-K. Recorded so the pointer is not lost, and so nobody "
        "mistakes it for a delisting year for AVM."
    ),
}

WL_ROWS = ["D1342", "D1366", "D1376", "D1409"]
WL_EXCHANGE = ("NYSE (Warner-Lambert Co.; Common Stock also registered on the Chicago and Pacific Stock "
               "Exchanges per FY1997 10-K 12(b) cover; ticker pending)")
WL_ACTION = (
    "v10 2026-09-18: venue verified from the period filing (NYSE, 12(b) cover). v11 second wave "
    "2026-09-18: cover page re-read in full (chunk 0 of 43 of acc 0000950117-98-000602) - the 12(b) table "
    "names THREE exchanges for Common Stock (Par Value $1 Per Share): The New York Stock Exchange, The "
    "Chicago Stock Exchange and The Pacific Stock Exchange (plus a second 12(b) class, Rights to Purchase "
    "Series A Junior Participating Preferred Stock, on the same three); 12(g): None; commission file "
    "number 1-3608; SROS CSX/NYSE/PCX. Item 1 names PARKE-DAVIS as Warner-Lambert's own trade name and "
    "lists CEREBYX and OMNICEF among its products, corroborating the sponsor chain from the registrant's "
    "own filing. SEARCH PLAN CHANGED: 'DOCUMENTS INCORPORATED BY REFERENCE: Portions of the Warner-Lambert "
    "Company Annual Report to Shareholders for 1997 -- Part I, Part II and Part IV' - Item 5 is in Part II, "
    "so the symbol is most likely in the Annual Report exhibit inside the same submission, not in the 10-K "
    "body (the Carter-Wallace trap). Remaining: that symbol, then the delisting year (lineage: Pfizer 2000). "
    "The v10 'expected WLA' guess is still unverified. NOTE: the page-fetch tool failed right after this "
    "chunk, so chunks 1-42 were never retrieved."
)


def main() -> None:
    ev = json.load(open(EV, encoding="utf-8"))

    wl = ev["companies"]["warner_lambert"]
    assert sorted(wl["rows"]) == sorted(WL_ROWS), wl["rows"]
    have = {c["url"] for c in wl.get("citations", [])}
    if WL_URL not in have:
        wl["citations"].append({"doc": WL_DOC, "url": WL_URL, "evidence": WL_EVIDENCE})
    wl["v10_note_superseded"] = wl.get("note")
    wl["note"] = WL_NOTE
    wl["venue"] = ("New York Stock Exchange (primary) + Chicago Stock Exchange + Pacific Stock Exchange, "
                   "all three per the FY1997 10-K 12(b) cover")

    am = ev["companies"]["advanced_magnetics"]
    if not any(c["doc"].startswith("UNVERIFIED POINTER") for c in am["citations"]):
        am["citations"].append(dict(AMAG_POINTER))
    am["note"] = am["note"] + (
        " v11 second wave 2026-09-18: an UNVERIFIED POINTER to the end of the AMAG-on-Nasdaq line (8-K "
        "dated 2020-11-16, Form 25 filed by NASDAQ that day) was recorded in citations[] while the page-"
        "fetch tool was down. It is NOT a delisting year for AVM: the AVM-on-AMEX line ended earlier "
        "(EDGAR name change to AMAG Pharmaceuticals 2007-07-05). No value written.")

    ev["v11_second_wave"] = {
        "captured_utc": "2026-09-18T12:35:00Z",
        "fetch_tool_status": ("FAILED mid-pass. Warner-Lambert FY1997 10-K chunk 0 of 43 was retrieved "
                              "successfully; every subsequent fetch_page call returned SignatureDoesNotMatch "
                              "from the tool's internal file proxy (other chunks of the same submission, a "
                              "different EDGAR submission, a non-EDGAR URL), including after a 75-second "
                              "wait. web_search still worked, so this is specific to the fetch path. "
                              "Consequence: no second-wave symbol or delisting-year values were written."),
        "what_changed": ("Warner-Lambert venue upgraded from plain 'NYSE' to the three exchanges its 12(b) "
                         "cover names, with the incorporated-by-reference finding recorded (Item 5 lives in "
                         "the 1997 Annual Report to Shareholders, so the symbol hunt must target that "
                         "exhibit). One unverified pointer recorded for Advanced Magnetics with an explicit "
                         "do-not-use warning. No status changed: the index is still 9 RESOLVED / 12 "
                         "VENUE-VERIFIED / 1 CITATION-LOCATED / 3 ATTRIBUTION-CASE."),
    }
    with EV.open("w", encoding="utf-8") as f:
        json.dump(ev, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("evidence: warner_lambert citation + AMAG pointer merged")

    master = list(csv.DictReader(open(MASTER, newline="", encoding="utf-8-sig")))
    header = list(master[0].keys())
    n = 0
    for r in master:
        if r["decision_id"] in WL_ROWS:
            r["exchange"] = WL_EXCHANGE
            note = (f"{TAG}: Warner-Lambert FY1997 10-K cover page fetched live ({WL_DOC}, {WL_URL}). "
                    f"12(b) verbatim: 'Common Stock (Par Value $1 Per Share)' registered on 'The New York "
                    f"Stock Exchange, Inc. / The Chicago Stock Exchange, Inc. / The Pacific Stock Exchange, "
                    f"Inc.' (plus a second 12(b) class, 'Rights to Purchase Series A Junior Participating "
                    f"Preferred Stock', on the same three); 12(g): 'None.'; commission file number 1-3608. "
                    f"Item 1 names 'PARKE-DAVIS' as Warner-Lambert's own trade name and lists CEREBYX and "
                    f"OMNICEF among its products. SYMBOL NOT WRITTEN: 'DOCUMENTS INCORPORATED BY REFERENCE: "
                    f"Portions of the Warner-Lambert Company Annual Report to Shareholders for 1997 -- Part "
                    f"I, Part II and Part IV' - Item 5 is in Part II, so the symbol is in that Annual Report "
                    f"exhibit, not the 10-K body. The page-fetch tool failed immediately after this chunk, "
                    f"so chunks 1-42 were never retrieved. Evidence: "
                    f"data/staging/pre2000_sponsor_edgar_evidence.json (v11 second wave).")
            r["notes"] = r["notes"].rstrip(" |") + " | " + note
            n += 1
    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(master)
    print(f"master: {n} Warner-Lambert rows updated (exchange text + dated note; no symbol written)")

    idx = list(csv.DictReader(open(INDEX, newline="", encoding="utf-8-sig")))
    idx_header = list(idx[0].keys())
    k = 0
    for r in idx:
        if r["decision_id"] in WL_ROWS:
            r["master_exchange"] = WL_EXCHANGE
            r["action_for_reviewer"] = WL_ACTION
            cur = r["sec_edgar_company_search"].strip()
            if cur != WL_URL:
                r["sec_edgar_company_search"] = f"{cur} | cover page: {WL_URL}" if cur else WL_URL
            k += 1
    assert len(idx) == 67
    with INDEX.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=idx_header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(idx)
    print(f"index: {k} Warner-Lambert rows updated")


if __name__ == "__main__":
    main()
