#!/usr/bin/env python3
"""v16 (2026-09-18): resolve the last 7 VENUE-VERIFIED pre-2000 ticker rows
using primary SEC text fetched live through the sandbox page-fetch tool.

All seven rows were waiting on ticker SYMBOLS (venue was already verified
v10-v12). Every quote below was read from sec.gov primary filings on
2026-09-18 (UTC) and is recorded verbatim; nothing is inferred and no
external ticker service is used. Resolutions:

  Warner-Lambert x4 (D1342 Cerebyx, D1366 Lipitor, D1376 Rezulin, D1409
    Omnicef)  -> NYSE: WLA
      * FY1997 10-K Item 5 (acc 0000950117-98-000602, filed 1998-03-24)
        states the venue for the decision period; no symbol is stated
        anywhere in the FY1997/FY1998 10-Ks or the 1998/1999 proxies
        (negative finding re-confirmed 2026-09-18).
      * Warner-Lambert's own DEFA14A (acc 0000950172-99-001807, filed
        1999-12-22) states "(NYSE: WLA)" verbatim - the SEC-stated symbol.

  Roberts Pharmaceutical x2 (D1347 ProAmatine, D1379 Agrylin)
    -> NASDAQ National Market: RPCX at both decision dates
      * Form S-3 (acc 0000950130-96-003846, filed 1996-10-09) and Form
        S-3/A (acc 0000950130-96-004222, filed 1996-11-06, effective
        1996-11-07) prospectus covers state verbatim: "The Common Stock of
        the Company is traded on the Nasdaq National Market under the
        symbol 'RPCX.'" (with NASDAQ last-sale prices of 1996-10-04 and
        1996-11-01 respectively) - both filings inside the decision
        window (ProAmatine approved 1996-09-06, Agrylin 1997-01-29).
      * FY1996 10-K Item 5 (acc 0000950130-97-001485, filed 1997-04-02)
        confirms the NASDAQ National Market System venue without a symbol.
      * FY1997 10-K Item 5 (acc 0000950130-98-001619, filed 1998-03-31)
        pins the transfer: NASDAQ NMS through 1997-05-21, AMEX from
        1997-05-22 - so both decision dates are NASDAQ-era.
      * 1999 DEFM14A (acc 0000950130-99-006712, filed 1999-11-23) states
        the later AMEX symbol "RPC" and the Shire merger lineage.
      * NOTE: the v13 hand-off's assumed NASDAQ symbol "ROBE" is WRONG;
        the SEC-stated symbol is RPCX. Primary text over memory.

  Block Drug x1 (D1365 Aphthasol) -> RESOLVED AS A DOCUMENTED NEGATIVE
      * FY1997 10-K (acc 0000012654-97-000004, filed 1997-06-30): Section
        12(b) registration "None"; 12(g)-registered Class A Common Stock;
        Item 5 prices are "high and low bid quotes ... inter-dealer
        prices"; holders of Class A (non-voting) = 507, Class B (voting)
        = 5; the Aphthasol approval is confirmed verbatim in Item 1.
      * No proxy (DEF 14A/14C) or 424 prospectus was ever filed on EDGAR
        (verified 2026-09-18: none exist 1993-2001), so NO SEC filing
        states a ticker symbol. Blank beats guessed: the ticker stays
        blank and the row stays out of the investable universe.

Idempotent: refuses to double-apply; hard-asserts current state before
every write. Also records the evidence into
data/staging/pre2000_sponsor_edgar_evidence.json (v16_update section).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INDEX = DATA / "pre2000_sponsor_resolution_index.csv"
MASTER = DATA / "fda_decisions_master.csv"
EVIDENCE = DATA / "staging" / "pre2000_sponsor_edgar_evidence.json"

V16_TAG = "v16 2026-09-18"

RESOLVED = {
    "D1342": {
        "brand": "Cerebyx",
        "ticker": "WLA",
        "status": "RESOLVED (venue+ticker per period SEC filings)",
        "exchange": (
            "NYSE at decision date - Warner-Lambert Co. principal market "
            "(FY1997 10-K Item 5, filed 1998-03-24: 'The principal market on which the "
            "Company's stock is traded is the New York Stock Exchange, but the stock is "
            "also listed and traded on the following domestic and international stock "
            "exchanges: Chicago, Pacific, London and Zurich.'); symbol WLA per "
            "Warner-Lambert DEFA14A 1999-12-22 (acc 0000950172-99-001807): 'Warner-Lambert "
            "Company (NYSE: WLA) announced today...'; no symbol stated in the FY1997/FY1998 "
            "10-Ks or 1998/1999 proxies (negative finding, re-confirmed 2026-09-18)"
        ),
        "citation": (
            "https://www.sec.gov/Archives/edgar/data/104669/0000950117-98-000602.txt ; "
            "https://www.sec.gov/Archives/edgar/data/104669/0000950172-99-001807.txt"
        ),
    },
    "D1366": None,  # filled below from D1342 template (same issuer)
    "D1376": None,
    "D1409": None,
    "D1347": {
        "brand": "ProAmatine",
        "ticker": "RPCX",
        "status": "RESOLVED (venue+ticker per period SEC filings)",
        "exchange": (
            "NASDAQ National Market at decision date (1996-09-06), symbol RPCX - Form S-3 "
            "filed 1996-10-09 and S-3/A effective 1996-11-07 (acc 0000950130-96-003846 / "
            "0000950130-96-004222): 'The Common Stock of the Company is traded on the Nasdaq "
            "National Market under the symbol \"RPCX.\"' with NASDAQ last-sale prices of "
            "1996-10-04 ($18-1/8) and 1996-11-01 ($14-1/16); NASDAQ NMS venue confirmed by "
            "FY1996 10-K Item 5 (filed 1997-04-02) and by FY1997 10-K Item 5 (filed "
            "1998-03-31: NASDAQ NMS through 1997-05-21, AMEX from 1997-05-22 under symbol "
            "'RPC' per the 1999-11-23 DEFM14A); Shire acquired Roberts (merger effective "
            "2000-01); the v13 hand-off's 'ROBE' assumption was wrong - SEC text says RPCX"
        ),
        "citation": (
            "https://www.sec.gov/Archives/edgar/data/853022/0000950130-96-003846.txt ; "
            "https://www.sec.gov/Archives/edgar/data/853022/0000950130-96-004222.txt ; "
            "https://www.sec.gov/Archives/edgar/data/853022/0000950130-97-001485.txt ; "
            "https://www.sec.gov/Archives/edgar/data/853022/0000950130-98-001619.txt ; "
            "https://www.sec.gov/Archives/edgar/data/853022/0000950130-99-006712.txt"
        ),
    },
    "D1379": None,  # same issuer as D1347
    "D1365": {
        "brand": "Aphthasol",
        "ticker": "",  # documented negative - blank beats guessed
        "status": "RESOLVED (documented negative: no exchange listing, no SEC-stated ticker; OTC inter-dealer only)",
        "exchange": (
            "OTC: NASD inter-dealer market only (Block Drug Company, Inc. Class A Common "
            "Stock, non-voting, 12(g)-registered; Section 12(b) table = 'None'); Item 5 "
            "prices are 'high and low bid quotes and reflect inter-dealer prices without "
            "retail mark-up, mark-down or commission'; holders: Class A (non-voting) 507, "
            "Class B (voting) 5. RESOLVED NEGATIVE 2026-09-18: no SEC filing states a ticker "
            "symbol - no DEF 14A/14C proxy or 424 prospectus exists on EDGAR for CIK 12654 "
            "(verified 1993-2001), and the FY1997 10-K (acc 0000012654-97-000004) states no "
            "symbol; the FY1997 10-K Item 1 confirms the FDA approval verbatim: 'In December, "
            "1996, the Company received Food and Drug Administration (FDA) approval for "
            "Aphthasol, a new chemical entity for the treatment of aphthous ulcers' - ticker "
            "stays blank (blank beats guessed); row stays out of the investable universe"
        ),
        "citation": "https://www.sec.gov/Archives/edgar/data/12654/0000012654-97-000004.txt",
    },
}
# The three Parke-Davis/Warner-Lambert rows share the issuer resolution.
RESOLVED["D1366"] = dict(RESOLVED["D1342"], brand="Lipitor")
RESOLVED["D1376"] = dict(RESOLVED["D1342"], brand="Rezulin")
RESOLVED["D1409"] = dict(RESOLVED["D1342"], brand="Omnicef")
# The second Roberts row shares the issuer resolution.
RESOLVED["D1379"] = dict(RESOLVED["D1347"], brand="Agrylin")

WL_SYMBOL_VERBATIM = (
    "Warner-Lambert Company (NYSE: WLA) announced today that it has filed consent "
    "solicitation revocation materials with the Securities and Exchange Commission (SEC)"
)
WL_ITEM5_VERBATIM = (
    "The principal market on which the Company's stock is traded is the New York "
    "Stock Exchange, but the stock is also listed and traded on the following domestic "
    "and international stock exchanges: Chicago, Pacific, London and Zurich."
)
RPCX_VERBATIM = (
    "The Common Stock of the Company is traded on the Nasdaq National Market under the "
    "symbol \"RPCX.\""
)
RPC_VERBATIM = (
    "Roberts common stock is listed and traded on the American Stock Exchange under the "
    "symbol \"RPC.\""
)
ROBERTS_TRANSFER_VERBATIM = (
    "as reported on the NASDAQ National Market System in 1996 and from January 1, 1997 "
    "through May 21, 1997 and as reported by the American Stock Exchange from May 22, 1997 "
    "through December 31, 1997"
)
BLOCK_12B_VERBATIM = (
    "Securities registered pursuant to Section 12(b) of the Act: Title of Each Class None / "
    "Name of each exchange on which registered None"
)
BLOCK_ITEM5_VERBATIM = (
    "These are high and low bid quotes and reflect inter-dealer prices without retail "
    "mark-up, mark-down or commission and may not necessarily represent actual transactions."
)
BLOCK_APHTHASOL_VERBATIM = (
    "In December, 1996, the Company received Food and Drug Administration (FDA) approval "
    "for Aphthasol, a new chemical entity for the treatment of aphthous ulcers, commonly "
    "known as canker sores."
)

EVIDENCE_V16 = {
    "captured_utc": "2026-09-18",
    "route": "sandbox page-fetch tool, one canonical sec.gov URL at a time (Actions runner still blocked per v12 finding - not retried)",
    "warner_lambert": {
        "rows": ["D1342", "D1366", "D1376", "D1409"],
        "resolution": "NYSE: WLA at decision dates 1996-08-05 / 1996-12-17 / 1997-01-29 / 1997-12-04",
        "quotes": [
            {
                "doc": "FY1997 Form 10-K (filed 1998-03-24), Item 5",
                "url": "https://www.sec.gov/Archives/edgar/data/104669/0000950117-98-000602.txt",
                "evidence": WL_ITEM5_VERBATIM,
                "note": "decision-period venue; no symbol stated anywhere in this filing (v11 read all 43 chunks; Item 5 re-read 2026-09-18)",
            },
            {
                "doc": "DEFA14A soliciting material (filed 1999-12-22, acc 0000950172-99-001807)",
                "url": "https://www.sec.gov/Archives/edgar/data/104669/0000950172-99-001807.txt",
                "evidence": WL_SYMBOL_VERBATIM,
                "note": "the only SEC-stated symbol found for the issuer; line-wrapped in the raw text as 'NYSE: / WLA'",
            },
            {
                "doc": "DEF 14A 1999-03-08 (acc 0000950117-99-000459) incl. PERFORMANCE GRAPH p.22",
                "url": "https://www.sec.gov/Archives/edgar/data/104669/0000950117-99-000459.txt",
                "evidence": "negative: no ticker symbol stated (performance graph labels the line 'Warner-Lambert' only)",
            },
        ],
    },
    "roberts_pharmaceutical": {
        "rows": ["D1347", "D1379"],
        "resolution": "NASDAQ National Market: RPCX at both decision dates (1996-09-06, 1997-01-29); AMEX: RPC after 1997-05-22",
        "quotes": [
            {
                "doc": "Form S-3 prospectus cover (filed 1996-10-09, acc 0000950130-96-003846)",
                "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-96-003846.txt",
                "evidence": RPCX_VERBATIM + " On October 4, 1996, the last reported sale price of the Company's Common Stock, as reported on the Nasdaq National Market, was $18-1/8 per share.",
            },
            {
                "doc": "Form S-3/A Amendment No. 1 (filed 1996-11-06, effective 1996-11-07, acc 0000950130-96-004222)",
                "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-96-004222.txt",
                "evidence": RPCX_VERBATIM + " On November 1, 1996, the last reported sale price of the Company's Common Stock, as reported on the Nasdaq National Market, was $14-1/16 per share.",
            },
            {
                "doc": "FY1996 Form 10-K (filed 1997-04-02), Item 5",
                "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-97-001485.txt",
                "evidence": "...traded over-the-counter market on the NASDAQ National Market System and was held by approximately 900 shareholders of record as of March 19, 1997. ... high and low last sale prices for the Company's Common Stock, as reported on the NASDAQ National Market System.",
                "note": "venue only; no symbol in Item 5 (chunks 9-13 read)",
            },
            {
                "doc": "FY1997 Form 10-K (filed 1998-03-31), Item 5",
                "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-98-001619.txt",
                "evidence": "The Company's Common Stock is traded on the American Stock Exchange and was held by approximately 900 shareholders of record as of March 20, 1998. ... " + ROBERTS_TRANSFER_VERBATIM,
                "note": "pins the NASDAQ->AMEX transfer: both decision dates are NASDAQ-era",
            },
            {
                "doc": "DEFM14A merger proxy (filed 1999-11-23, acc 0000950130-99-006712), p.1",
                "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-99-006712.txt",
                "evidence": RPC_VERBATIM + " The Shire ordinary shares are listed and traded on the London Stock Exchange Limited under the symbol \"SHP.L.\" The Shire American depositary shares are listed and traded on the Nasdaq National Market under the symbol \"SHPGY.\"",
                "note": "documents the AMEX-era symbol and the Shire acquisition lineage",
            },
        ],
        "handoff_correction": "the v13 NEXT_SESSION assumption 'expected NASDAQ:BLOCA / ROBE' is wrong for Roberts: the SEC-stated NASDAQ-era symbol is RPCX (S-3 1996-10-09 and S-3/A 1996-11-06), not ROBE",
    },
    "block_drug": {
        "rows": ["D1365"],
        "resolution": "DOCUMENTED NEGATIVE - no exchange listing, no SEC-stated ticker symbol; OTC inter-dealer quotes only; ticker stays blank",
        "quotes": [
            {
                "doc": "FY1997 Form 10-K (filed 1997-06-30, acc 0000012654-97-000004), cover",
                "url": "https://www.sec.gov/Archives/edgar/data/12654/0000012654-97-000004.txt",
                "evidence": BLOCK_12B_VERBATIM + " ; Section 12(g): 'Class A Common Stock - $.10 par value'",
            },
            {
                "doc": "same 10-K, Item 5",
                "url": "https://www.sec.gov/Archives/edgar/data/12654/0000012654-97-000004.txt",
                "evidence": BLOCK_ITEM5_VERBATIM + " Holders: 'Common Stock, Class A (non-voting) 507 / Common Stock, Class B (voting) 5'",
            },
            {
                "doc": "same 10-K, Item 1 Business",
                "url": "https://www.sec.gov/Archives/edgar/data/12654/0000012654-97-000004.txt",
                "evidence": BLOCK_APHTHASOL_VERBATIM,
                "note": "the FDA approval is confirmed verbatim in the period annual report",
            },
            {
                "doc": "EDGAR company-browse negative checks 2026-09-18",
                "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000012654&type=DEF&dateb=20020101&owner=include&count=20",
                "evidence": "no DEF 14A/14C proxy and no 424 prospectus filings exist for CIK 0000012654 (lists empty); 10-K/10-Q are the only period filings - no SEC document states a ticker symbol",
            },
        ],
    },
}


def apply_index() -> list[str]:
    with INDEX.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames

    changed = []
    for r in rows:
        did = r["decision_id"]
        if did not in RESOLVED:
            continue
        res = RESOLVED[did]
        assert r["drug_brand"] == res["brand"], (did, r["drug_brand"])
        if V16_TAG in (r.get("action_for_reviewer") or ""):
            continue
        assert "VENUE-VERIFIED" in r["status"], (did, r["status"])
        r["status"] = res["status"]
        r["master_ticker"] = res["ticker"] or "(blank - documented negative)"
        r["master_exchange"] = res["exchange"]
        r["action_for_reviewer"] = (
            f"{V16_TAG}: primary SEC text fetched via the sandbox page-fetch tool. "
            f"Ticker resolution: {res['ticker'] or '(none stated in any SEC filing - blank beats guessed)'}. "
            f"Evidence: {res['citation']} {res['exchange']}"
        )
        changed.append(did)

    if changed:
        with INDEX.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def apply_master() -> list[str]:
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames

    changed = []
    for r in rows:
        did = r["decision_id"]
        if did not in RESOLVED:
            continue
        res = RESOLVED[did]
        if V16_TAG in (r.get("notes") or ""):
            continue
        assert r["drug_brand"] == res["brand"], (did, r["drug_brand"])
        assert (r.get("ticker") or "").strip() == "", (did, r.get("ticker"))
        if res["ticker"]:
            r["ticker"] = res["ticker"]
            r["exchange"] = res["exchange"]
        else:
            r["exchange"] = res["exchange"]
        r["notes"] = (r.get("notes") or "").rstrip() + (
            f" {V16_TAG} TICKER RESOLUTION: period SEC filings fetched 2026-09-18 "
            f"(see data/staging/pre2000_sponsor_edgar_evidence.json v16_update). "
            + (
                f"Decision-date ticker = {res['ticker']} ({res['status']})."
                if res["ticker"]
                else "No exchange listing and no SEC-stated ticker symbol (documented negative; blank beats guessed) - row remains outside the investable universe."
            )
        )
        changed.append(did)

    if changed:
        with MASTER.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def apply_evidence() -> bool:
    doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if "v16_update" in doc:
        return False
    doc["v16_update"] = EVIDENCE_V16
    EVIDENCE.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return True


def main() -> int:
    idx_changed = apply_index()
    master_changed = apply_master()
    ev_changed = apply_evidence()
    print(f"index rows updated: {idx_changed or 'none (already applied)'}")
    print(f"master rows updated: {master_changed or 'none (already applied)'}")
    print(f"evidence JSON updated: {ev_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
