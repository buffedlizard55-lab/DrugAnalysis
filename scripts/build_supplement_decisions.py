#!/usr/bin/env python3
"""Build data/fda_supplement_decisions.csv — FDA **efficacy supplement**
approvals 2000-2026 (new indications / new populations / new efficacy claims).

Source
------
data/raw/openfda_efficacy_supplements/suppl_<year>.json, produced on the
GitHub Actions runner by scripts/run_fetch_jobs.py from the openFDA Drugs@FDA
endpoint, with every request URL and payload SHA-256 recorded in that
directory's manifest.json.

Why these rows matter to the decision engine
--------------------------------------------
Novel (NME) approvals are only ~50 per year, and they are the *first* decision
on a molecule. Efficacy supplements are FDA's decisions on whether an
already-marketed drug's NEW clinical trial data support a NEW indication —
several hundred per year. For an investor, a label expansion is frequently
the larger revenue event, and for the scorecard it is direct evidence of
whether a company's late-stage trials keep converting into FDA approvals.

Hallucination controls
----------------------
* Every field is copied verbatim from the openFDA record. Nothing is inferred.
* The *indication* is NOT synthesised: FDA publishes no structured indication
  field for supplements, so each row instead links its own FDA approval-letter
  PDF (`approval_letter_url`) and label PDF, which state the indication.
  A row without a letter is marked so in verification_status.
* Company/ticker resolution reuses data/sponsor_registry.csv, which was built
  from SEC company_tickers.json. A sponsor that cannot be resolved gets
  ticker `UNRESOLVED` and us_investable_class `UNRESOLVED (REVIEW)` — it is
  never guessed.
* Rows are keyed `S<year>-<application>-<submission>` so they can never
  collide with the master list's D-prefixed novel-approval IDs.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw" / "openfda_efficacy_supplements"
OUT = DATA / "fda_supplement_decisions.csv"

NONWORD = re.compile(r"[^a-z0-9]+")

# Corporate-suffix noise that must not influence sponsor matching.
SUFFIXES = {
    "inc", "llc", "ltd", "plc", "corp", "corporation", "company", "co", "the",
    "holdings", "holding", "group", "ag", "sa", "nv", "as", "ab", "gmbh",
    "kgaa", "aps", "oy", "srl", "spa", "kk", "limited", "lp", "llp", "us",
    "usa", "america", "american", "intl", "international", "division", "sub",
    "subs", "hlthcare", "healthcare", "health", "pharms", "pharm", "pharma",
    "pharmaceutical", "pharmaceuticals", "therapeutics", "biosciences",
    "bioscience", "biopharma", "biopharmaceuticals", "labs", "laboratories",
    "laboratory", "sciences", "science", "products", "prods", "operations",
    "research", "development", "randd", "and", "of",
}


def norm(s: str) -> str:
    return NONWORD.sub(" ", (s or "").lower()).strip()


def sponsor_key(s: str) -> str:
    return " ".join(t for t in norm(s).split() if t not in SUFFIXES)


def load_registry():
    """sponsor_key -> registry row.

    Two sources, both already verified inside this repository:

    1. data/sponsor_registry.csv — built from SEC company_tickers.json.
    2. data/fda_decisions_master.csv — the novel-approval master list, whose
       company/ticker/exchange fields were verified line-by-line in earlier
       passes. A master company name is only admitted when every master row
       bearing that name agrees on a single ticker; conflicting names are
       dropped rather than guessed.
    """
    reg: dict[str, dict] = {}

    path = DATA / "sponsor_registry.csv"
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                for candidate in (r.get("sponsor_key", ""), r.get("resolved_company", ""),
                                  r.get("sec_title", "")):
                    k = sponsor_key(candidate)
                    if k:
                        reg.setdefault(k, r)

    master = DATA / "fda_decisions_master.csv"
    if master.exists():
        by_key: dict[str, set] = {}
        rows_by_key: dict[str, dict] = {}
        with master.open(newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                ticker = (r.get("ticker") or "").strip()
                cls = (r.get("us_investable_class") or "").strip()
                # Only reuse rows that actually name a listed security.
                if not ticker or ticker in {"NO_US_TICKER", "UNRESOLVED", ""}:
                    continue
                if "?" in ticker or not cls.startswith("US-LISTED"):
                    continue
                k = sponsor_key(r.get("company_name", ""))
                if not k:
                    continue
                by_key.setdefault(k, set()).add(ticker)
                rows_by_key.setdefault(k, {
                    "resolved_company": r.get("company_name", ""),
                    "ticker": ticker,
                    "exchange": r.get("exchange", ""),
                    "us_investable_class": cls,
                    "basis": "fda_decisions_master.csv verified row (company/ticker confirmed in earlier verification pass)",
                })
        for k, tickers in by_key.items():
            if len(tickers) != 1:
                continue
            existing = reg.get(k)
            # The SEC-derived registry sometimes carries no ticker for an issuer
            # that the master list has already verified as US-listed (e.g. GSK
            # plc, ticker GSK on NYSE, is marked "NOT US-INVESTABLE (UNVERIFIED)"
            # in the registry). Prefer whichever source actually names a listed
            # security; never downgrade a verified listing to "unresolved".
            if existing is None or not (existing.get("ticker") or "").strip() or \
                    (existing.get("ticker") or "").strip() in {"NO_US_TICKER", "UNRESOLVED"}:
                reg[k] = rows_by_key[k]

    return reg


def resolve(sponsor: str, reg: dict):
    """Resolve an openFDA sponsor string to a registry issuer.

    Rules are applied in order, most-defensible first, and the two containment
    directions are handled SEPARATELY — mixing them manufactures false
    ambiguity (sponsor "BRISTOL" contains the registry key 'bristol myers'
    *and* is contained by 'celgene acquired by bristol myers squibb 2019',
    which are different issuers).

      1. Exact normalised-key match.
      2. A registry key that is a SUBSET of the sponsor's tokens — the sponsor
         string is a more specific spelling of a known issuer
         ("ASTRAZENECA UK LTD" -> 'astrazeneca'). The LONGEST such key wins,
         because it is the most specific consistent issuer.
      3. The sponsor's tokens are a subset of a registry key — the sponsor is
         an abbreviation ("BRISTOL"). The SHORTEST such key wins, because
         longer keys are acquisition-history strings describing a *different*
         original issuer. Requires a strictly unique shortest key.

    Anything still unresolved is returned as unresolved. Nothing is guessed.
    """
    key = sponsor_key(sponsor)
    if not key:
        return None, "sponsor_name empty in openFDA record"
    if key in reg:
        return reg[key], "sponsor_registry exact key match (SEC company_tickers.json / verified master lineage)"

    toks = set(key.split())
    if not toks:
        return None, "sponsor_name reduced to corporate suffixes only"

    # Rule 2 — registry key generalises the sponsor string.
    subset = [(k, v) for k, v in reg.items() if k and set(k.split()) <= toks]
    if subset:
        subset.sort(key=lambda kv: -len(kv[0].split()))
        best_len = len(subset[0][0].split())
        top = [kv for kv in subset if len(kv[0].split()) == best_len]
        if len({v.get("ticker", "") for _, v in top}) == 1:
            return top[0][1], (f"sponsor_registry match: registry key {top[0][0]!r} is contained in "
                               f"sponsor string {key!r} (most specific consistent issuer)")
        return None, (f"ambiguous: {len(top)} equally specific registry keys match {key!r} "
                      f"with different tickers — left unresolved")

    # Rule 3 — sponsor string is an abbreviation of a registry key.
    superset = [(k, v) for k, v in reg.items() if k and toks <= set(k.split())]
    if superset:
        superset.sort(key=lambda kv: len(kv[0].split()))
        if len(superset) == 1 or len(superset[0][0].split()) < len(superset[1][0].split()):
            return superset[0][1], (f"sponsor_registry match: sponsor {key!r} is an abbreviation of "
                                    f"registry key {superset[0][0]!r} (shortest/most direct entry)")
        tied = [kv for kv in superset if len(kv[0].split()) == len(superset[0][0].split())]
        if len({v.get("ticker", "") for _, v in tied}) == 1:
            return tied[0][1], (f"sponsor_registry match: sponsor {key!r} abbreviates {tied[0][0]!r} "
                                f"(tied keys all resolve to one ticker)")
        return None, (f"ambiguous: {key!r} abbreviates {len(tied)} registry keys with different "
                      f"tickers — left unresolved")

    return None, f"no sponsor_registry entry for {key!r}"


def main() -> int:
    reg = load_registry()
    print(f"sponsor registry keys: {len(reg)}")

    rows, tally = [], Counter()
    for path in sorted(RAW.glob("suppl_*.json")):
        payload = json.load(open(path))
        year = payload["year"]
        for s in payload.get("supplements", []):
            entry, basis = resolve(s["sponsor_name"], reg)
            letter = s.get("approval_letter_url", "")
            label = s.get("label_url", "")

            if entry:
                company = entry.get("resolved_company", "") or s["sponsor_name"]
                exchange = entry.get("exchange", "")
                cls = entry.get("us_investable_class", "") or "UNRESOLVED (REVIEW)"
                ticker = (entry.get("ticker", "") or "").strip()
                if not ticker:
                    # The issuer IS identified, it simply has no US-listed equity
                    # (private, or foreign-listed only). Saying "UNRESOLVED" here
                    # would be wrong: the company is known, the ticker does not
                    # exist. Distinguish the two cases explicitly.
                    ticker = "NO_US_TICKER"
            else:
                company = s["sponsor_name"]
                ticker = "UNRESOLVED"
                exchange = ""
                cls = "UNRESOLVED (REVIEW)"

            # A registry name such as "Cubist Pharmaceuticals (acquired by Merck
            # 2015)" resolves to the HISTORICAL ticker (CBST) that no longer
            # trades. That is the correct issuer for the decision date, but it
            # must never be presented as a currently investable security.
            historical = bool(re.search(r"acquired by|merged|delisted|\bvia\b|applicant at approval",
                                        company, re.I))
            if historical and cls.startswith("US-LISTED"):
                cls = "FORMERLY US-LISTED (DELISTED/ACQUIRED)"

            if letter:
                vstatus = "Verified - FDA approval letter"
            elif label:
                vstatus = "Verified - FDA label document (no approval letter published)"
            else:
                vstatus = "Verified - Drugs@FDA record only (FLAGGED: no FDA PDF published for this submission)"
            if historical:
                vstatus += " - FLAGGED: ticker is historical (issuer since acquired/delisted)"

            tally[vstatus.split(" (")[0]] += 1
            tally["resolved" if entry else "unresolved_sponsor"] += 1

            rows.append({
                "supplement_id": f"S{year}-{s['application_number']}-{s['submission_number']}",
                "company_name": company,
                "openfda_sponsor_name": s["sponsor_name"],
                "ticker": ticker,
                "exchange": exchange,
                "us_investable_class": cls,
                "drug_brand": s.get("brand_name", ""),
                "drug_generic": s.get("generic_name", "") or s.get("substance_name", ""),
                "application_number": s["application_number"],
                "submission_number": s["submission_number"],
                "decision_type": "Efficacy Supplement Approval",
                "decision_date": s["decision_date"],
                "review_priority": s.get("review_priority", ""),
                "submission_property_type": s.get("submission_property_type", ""),
                "pharm_class_epc": s.get("pharm_class_epc", ""),
                "route": s.get("route", ""),
                "approval_letter_url": letter,
                "label_url": label,
                "source_url_drugsatfda": s.get("source_url_drugsatfda", ""),
                "source_query_url": s.get("source_query_url", ""),
                "verification_status": vstatus,
                "sponsor_resolution_basis": basis,
                "notes": ("Indication text is intentionally not recorded: FDA publishes no "
                          "structured indication field for supplements. Read the linked FDA "
                          "approval letter / label for the approved indication."),
            })

    rows.sort(key=lambda r: (r["decision_date"], r["application_number"], r["submission_number"]))

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} efficacy-supplement decisions")
    for k, v in tally.most_common():
        print(f"  {k:<62} {v}")
    us = sum(1 for r in rows if r["us_investable_class"].startswith("US-LISTED"))
    print(f"  {'US-LISTED (investable universe)':<62} {us}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
