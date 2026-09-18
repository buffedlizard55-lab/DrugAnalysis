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

  0. "No US-listed equity verified..." / "not machine-verifiable"  -> NOT US-INVESTABLE (UNVERIFIED)
  1. exchange mentions a former US venue ("formerly NYSE:...")     -> FORMERLY US-LISTED (DELISTED/ACQUIRED)
  2. exchange mentions a former NON-US venue                       -> NON-US LISTING ONLY
  3. exchange absent or N/A                                        -> PRIVATE / NO EQUITY
     (unless the ticker alone is blank - see fixed-point rule below)
  3b. exchange explicitly says no US equity                        -> NON-US LISTING ONLY
  4. exchange contains ADR / ADS / OTC                             -> US-LISTED (ADR)
  5. exchange is a US venue (NASDAQ / NYSE), incl. "(... proxy)"   -> US-LISTED
  6. anything else                                                 -> NON-US LISTING ONLY

Fixed-point rule (added 2026-09-18, closes the v7 irregularity "the script is
not a fixed point of the committed master"):

  * For rows that ALREADY carry a committed class written by a builder from
    verified per-row research, this script never overwrites that class with a
    less-informative text-match default. Blank/N-A exchange fields cannot
    distinguish PRIVATE from "formerly NYSE:XXX" or a foreign-listed lineage,
    and a bare "NASDAQ" cannot know the company was later acquired - but the
    committed classes do. So: committed class wins; where the re-derivation
    DISAGREES a dated note is appended documenting both readings (surfaced,
    never silently resolved). Rows with a blank committed class (new rows) are
    classified purely from the fields, as before.
  * classification_basis is only written when the class is newly derived or
    was blank - a no-op re-run no longer clobbers builder provenance text.

Idempotent: re-running the script on a classified master changes nothing.
"""
import csv
import os
import re

MASTER = os.path.join(os.path.dirname(__file__), "..", "data", "fda_decisions_master.csv")
MASTER = os.path.abspath(MASTER)

US_LISTED = "US-LISTED"
US_ADR = "US-LISTED (ADR)"
FORMERLY_US = "FORMERLY US-LISTED (DELISTED/ACQUIRED)"
NON_US = "NON-US LISTING ONLY"
PRIVATE = "PRIVATE / NO EQUITY"
UNVERIFIED = "NOT US-INVESTABLE (UNVERIFIED)"

# AMEX (the American Stock Exchange) is a US venue and must be recognised as
# such: without it, classify("formerly AMEX:AVM, ...") returned NON-US LISTING
# ONLY for a US listing. v11 2026-09-18. Behaviour-preserving on the committed
# master (the script keeps committed classes; verified by re-run + diff).
US_VENUES = ("NASDAQ", "NYSE", "AMEX")  # NYSE American is covered by the NYSE prefix

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

NOTE_MARKER = "listing-class note (2026-09-18)"


def classify(exchange, ticker, company):
    """Derive (class, basis) purely from the verified field text."""
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

    # 3 - no equity at all (field evidence only; the caller keeps a committed
    #     class here when one exists - a blank field cannot distinguish PRIVATE
    #     from a delisted or foreign lineage)
    if not ex or ex.upper().startswith("N/A"):
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


KEEP_ELIGIBLE = {FORMERLY_US, NON_US, UNVERIFIED, PRIVATE, US_LISTED, US_ADR}


def main():
    with open(MASTER, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames)
        rows = list(reader)

    for col in ("us_investable_class", "classification_basis"):
        if col not in header:
            header.append(col)

    counts = {}
    n_new, n_kept, n_noted = 0, 0, 0
    for r in rows:
        derived, basis = classify(r.get("exchange", ""), r.get("ticker", ""),
                                  r.get("company_name", ""))
        committed = (r.get("us_investable_class") or "").strip()
        if not committed:
            r["us_investable_class"] = derived
            r["classification_basis"] = ("derived " + os.environ.get("CLASSIFY_DATE", "2026-09-18") +
                                         " from verified exchange/ticker fields; " + basis)
            counts[derived] = counts.get(derived, 0) + 1
            n_new += 1
            continue
        # committed class present: it came from verified builder research that
        # is more specific than the field text (e.g. a delisting year). Never
        # downgrade it; surface any disagreement as a dated note.
        counts[committed] = counts.get(committed, 0) + 1
        if derived != committed:
            if committed in KEEP_ELIGIBLE and NOTE_MARKER not in (r.get("notes") or ""):
                note = (f"{NOTE_MARKER}: field re-derivation would classify as '{derived}' "
                        f"({basis}); kept committed class '{committed}' whose "
                        "classification_basis documents the more specific verification")
                r["notes"] = (r["notes"] + " | " if (r.get("notes") or "").strip() else "") + note
                n_noted += 1
        n_kept += 1
        if not (r.get("classification_basis") or "").strip():
            r["classification_basis"] = ("derived " + os.environ.get("CLASSIFY_DATE", "2026-09-18") +
                                         " from verified exchange/ticker fields; " + basis)

    # Keep the public master-list layout human-readable: the stable row ID is
    # last, while exchange remains immediately before it for quick investability
    # review. DictReader keeps this independent of the order used by builders.
    header = [c for c in header if c not in ("exchange", "decision_id")] + ["exchange", "decision_id"]

    with open(MASTER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)

    print(f"Classified {len(rows)} rows in {os.path.relpath(MASTER)} "
          f"({n_new} newly derived, {n_kept} committed classes kept, {n_noted} disagreements noted)")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>4}  {k}")


if __name__ == "__main__":
    main()
