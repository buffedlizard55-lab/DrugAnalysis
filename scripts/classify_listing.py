# -*- coding: utf-8 -*-
"""
Adds two columns to data/fda_decisions_master.csv:

    us_investable_class   - the project scope filter. Only companies a US-based
                            investor can actually buy belong in the main
                            analysis; private applicants and non-US-only
                            listings are shown on their own tabs.
    classification_basis  - exactly which verified field the class came from,
                            so the classification itself is auditable.

The class is DERIVED, not researched: it is a deterministic mapping of the
`exchange` / `ticker` values that were already verified row-by-row when the
row was added (see the builder scripts and data/staging/). No company is
re-labelled by hand and nothing here can introduce a new fact.

Rules (applied in this order):

  1. exchange mentions a former US venue ("formerly NASDAQ:...", "formerly
     NYSE:...")                                   -> FORMERLY US-LISTED (DELISTED/ACQUIRED)
     (still US-investable *at the time of the decision*, and its price
      reaction is part of the historical record)
  2. exchange mentions a former NON-US venue ("formerly SIX:...", "formerly
     LSE AIM:...")                                 -> NON-US LISTING ONLY
  3. exchange/ticker absent or marked N/A/private  -> PRIVATE / NO EQUITY
  4. exchange contains ADR / ADS / OTC             -> US-LISTED (ADR)
     (a US investor can buy the depositary receipt or the OTC line)
  5. exchange is a US venue (NASDAQ / NYSE / NYSE
     American), including "(... proxy)" rows        -> US-LISTED
  6. exchange says a non-US venue, or explicitly says
     there is no US ticker / no US ADR / no US listing
     (Tokyo, SIX, Euronext, HKEX, NSE/BSE India, ASX,
     TPEx, SZSE, Xetra, Nasdaq Stockholm/Copenhagen) -> NON-US LISTING ONLY
  7. anything else                                   -> NON-US LISTING ONLY

Two additional classes were added with the 2018-2020 backfill (2026-09-12):

  0a. "No US-listed equity verified in this pass"    -> NOT US-INVESTABLE (UNVERIFIED)
  0b. "N/A - applicant not machine-verifiable..."    -> NOT US-INVESTABLE (UNVERIFIED)

Those rows are real, source-verified FDA decisions whose ISSUER could not be
tied to a listed security without guessing (openFDA no longer returns the
applicant, the openFDA sponsor term is unresolvable, or the symbol stopped
returning data). They are kept out of the main US-investable analysis and out
of the private tab, and shown on the Non-US & Unverified tab with the reason
in the row notes - excluded rather than attributed.

Idempotent: re-running leaves already-classified rows unchanged unless the
underlying `exchange`/`ticker` value changed.
"""
import csv
import os

MASTER = os.path.join(os.path.dirname(__file__), "..", "data", "fda_decisions_master.csv")
MASTER = os.path.abspath(MASTER)

US_LISTED = "US-LISTED"
US_ADR = "US-LISTED (ADR)"
FORMERLY_US = "FORMERLY US-LISTED (DELISTED/ACQUIRED)"
NON_US = "NON-US LISTING ONLY"
PRIVATE = "PRIVATE / NO EQUITY"
UNVERIFIED = "NOT US-INVESTABLE (UNVERIFIED)"

US_VENUES = ("NASDAQ", "NYSE")          # NYSE American is covered by the NYSE prefix

# Venues that make a listing non-US. Checked BEFORE the US-venue prefix rule so
# that strings such as "Nasdaq Copenhagen (parent)" are never read as NASDAQ.
FOREIGN_VENUES = ("COPENHAGEN", "STOCKHOLM", "HELSINKI", "OSLO", "SIX", "EURONEXT",
                  "XETRA", "FRANKFURT", "PARIS", "MILAN", "BORSA", "MADRID", "ZURICH",
                  "VIENNA", "LONDON", "LSE", "AIM", "TOKYO", "TSE", "TYO", "OSAKA",
                  "KOREA EXCHANGE", "KOSPI", "HKEX", "HONG KONG", "SHANGHAI", "SHENZHE",
                  "SZSE", "SSE", "TPEX", "TAIPEI", "ASX", "SYDNEY", "NSE", "BSE",
                  "INDIA", "TEL AVIV", "TASE", "TORONTO", "TSX", "SAO PAULO",
                  "MEXICO", "JOHANNESBURG", "SINGAPORE", "SGX")

# Explicit statements that no US-accessible equity exists for the row.
NO_US_EQUITY = ("NO US ADR", "NO US TICKER", "NO US LISTING", "NO US-LISTED",
                "NO US OTC", "WITHOUT AN ADR")


def classify(exchange, ticker, company):
    ex = (exchange or "").strip()
    tk = (ticker or "").strip()
    up = ex.upper()

    # 0 - issuer known but no investable equity could be verified (backfill 2018-2020)
    if up.startswith("NO US-LISTED EQUITY VERIFIED") or "NOT MACHINE-VERIFIABLE" in up:
        return UNVERIFIED, f"issuer could not be tied to a listed security without guessing: '{ex}'"

    # 1 / 2 - delisted tickers
    if up.startswith("FORMERLY"):
        if any(v in up for v in US_VENUES):
            return FORMERLY_US, f"exchange field states a former US venue: '{ex}'"
        return NON_US, f"exchange field states a former non-US venue: '{ex}'"

    # 3 - no equity at all
    if not ex or ex.upper().startswith("N/A") or not tk or tk.upper() == "NO_TICKER":
        return PRIVATE, f"no listed equity in the verified fields (ticker='{tk or 'blank'}', exchange='{ex or 'blank'}')"

    # 3b - the field explicitly says there is nothing US-listed to buy
    if any(k in up for k in NO_US_EQUITY):
        return NON_US, f"exchange field states there is no US-listed equity: '{ex}'"

    # 4 - depositary receipts / OTC lines a US investor can buy
    if "ADR" in up or "ADS" in up or "OTC" in up or "US OTC" in up:
        return US_ADR, f"US depositary receipt / OTC line per exchange field: '{ex}'"

    # 4b - a named non-US venue outranks the US-venue prefix test
    if any(v in up for v in FOREIGN_VENUES):
        return NON_US, f"non-US venue named in exchange field: '{ex}'"

    # 5 - direct US listing (includes "<venue> (<parent> proxy)" rows)
    if any(up.startswith(v) for v in US_VENUES):
        return US_LISTED, f"US primary listing per exchange field: '{ex}'"

    # 6 - everything else is a non-US listing with no US-accessible equity
    return NON_US, f"non-US listing with no US ticker per exchange field: '{ex}'"


def main():
    with open(MASTER, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames)
        rows = list(reader)

    for col in ("us_investable_class", "classification_basis"):
        if col not in header:
            header.append(col)

    counts = {}
    for r in rows:
        cls, basis = classify(r.get("exchange", ""), r.get("ticker", ""), r.get("company_name", ""))
        r["us_investable_class"] = cls
        r["classification_basis"] = ("derived " + os.environ.get("CLASSIFY_DATE", "2026-09-12") +
                                     " from verified exchange/ticker fields; " + basis)
        counts[cls] = counts.get(cls, 0) + 1

    with open(MASTER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)

    print(f"Classified {len(rows)} rows in {os.path.relpath(MASTER)}")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>4}  {k}")


if __name__ == "__main__":
    main()
