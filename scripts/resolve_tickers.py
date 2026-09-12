#!/usr/bin/env python3
"""Resolve FDA applicant / sponsor names to listed securities - without guessing.

Sources, in strict priority order:

1. ``data/fda_decisions_master.csv`` + ``data/stock_price_snapshots.csv``
   Mappings this project has *already verified row by row* in earlier passes.
   Re-using them introduces no new fact.
2. ``data/raw/probe/sec_company_tickers_alt.json``
   The official SEC list of registrants (https://www.sec.gov/files/company_tickers.json),
   fetched by .github/workflows/arena-data-fetch.yml.

A name is matched only when the normalised strings are *equal*, or when one
normalised name is a token-complete prefix of the other **and** exactly one SEC
registrant matches. Anything ambiguous is deliberately left unresolved: a wrong
ticker is worse than no ticker, and unresolved rows are published on the
Non-US & Unverified tab with the reason recorded.

Output: ``data/staging/ticker_resolution.json`` (machine readable) plus a
human-readable summary printed to stdout for review.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STAGING = DATA / "staging"

MASTER = DATA / "fda_decisions_master.csv"
SNAPSHOTS = DATA / "stock_price_snapshots.csv"
SEC_FILE = DATA / "raw" / "probe" / "sec_company_tickers_alt.json"

# Tokens that carry no identity signal for matching purposes.
GENERIC = {
    "inc", "incorporated", "corp", "corporation", "company", "companies", "co",
    "ltd", "limited", "llc", "lp", "plc", "ag", "sa", "sas", "se", "nv", "bv",
    "ab", "as", "oy", "spa", "srl", "gmbh", "holdings", "holding", "group",
    "gruppe", "pharmaceuticals", "pharmaceutical", "pharma", "pharms", "pharm",
    "labs", "laboratories", "laboratory", "therapeutics", "therapeutic",
    "biosciences", "bioscience", "biopharma", "biotech", "biotechnology",
    "technologies", "technology", "health", "healthcare", "hlthcare", "healthcare",
    "us", "usa", "america", "american", "international", "global", "research",
    "rx", "drugs", "drug", "medicines", "medicine", "products", "product",
    "brands", "consumer", "division", "partners", "ventures", "medicines",
    "the", "and", "of", "for", "de", "du", "van", "der",
    # descriptor words that appear in FDA sponsor strings and carry no identity
    "branded", "specialty", "specialities", "generic", "generics", "medcl",
    "operations", "medical", "clinical", "sciences", "science", "therapies",
    "therapy", "diagnostics", "diagnostic", "devices", "device", "solutions",
    "innovative", "novel", "advanced", "medtech", "biologics", "oncology",
    "institute", "institutes", "development", "europe", "pacific", "asia",
    "americas", "north", "south", "east", "west", "worldwide", "trading",
    "manufacturing", "sales", "marketing", "services", "service", "capital",
    "industries", "industry", "enterprises", "venture", "trust", "funds",
    "canada", "europe", "uk", "us", "usa", "america", "international",
}


def norm(name: str) -> str:
    s = re.sub(r"[^a-z0-9\s]+", " ", (name or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    tokens = [t for t in s.split() if t and t not in GENERIC]
    # keep at least one token so that names made only of generic words still match
    if not tokens:
        tokens = [t for t in s.split() if t]
    return "".join(tokens)


def load_repo_map():
    """company name -> (ticker, exchange) already verified in this repository."""
    out = {}
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            tk = (r.get("ticker") or "").strip()
            if not tk or tk.upper() in {"NO_US_TICKER", "NO_TICKER"} or "NO_US" in tk.upper():
                continue
            # a row can carry "current holder / applicant at approval"; both halves are known
            for part in re.split(r"/", r.get("company_name") or ""):
                part = re.sub(r"\(.*?\)", "", part).strip()
                key = norm(part)
                if key and key not in out:
                    out[key] = (tk, (r.get("exchange") or "").strip(), r.get("company_name", "").strip())
    with SNAPSHOTS.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            key = norm(r.get("company") or "")
            if key and key not in out:
                out[key] = ((r.get("ticker") or "").strip(), "see price snapshot source",
                            (r.get("company") or "").strip())
    return out


sec_map_keyed = {}


def load_sec():
    raw = json.load(open(SEC_FILE))
    # company_tickers.json is { "0": {"cik_str":..,"ticker":..,"title":..}, ... }
    items = raw.values() if isinstance(raw, dict) else raw
    out = {}
    for it in items:
        ticker = (it.get("ticker") or "").strip()
        title = (it.get("title") or "").strip()
        if not ticker or not title:
            continue
        out.setdefault(norm(title), []).append({
            "ticker": ticker, "cik": it.get("cik_str"), "title": title,
        })
    return out


def tokens(name: str) -> list:
    return [t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if t and t not in GENERIC]


def distinctive(toks: list) -> list:
    """Tokens long enough to identify a company (4+ chars, e.g. 'teva')."""
    return [t for t in toks if len(t) >= 4]


def dedupe_candidates(cands: list, repo_map: dict) -> list:
    """Collapse several SEC rows for the same registrant (e.g. HLN / HLNCF).

    Preference order: a name this repository already verified, then the
    shortest clean ticker (ordinary share over warrant/unit/preferred lines).
    """
    by_title = {}
    for c in cands:
        by_title.setdefault((c["title"] or "").strip(), []).append(c)
    out = []
    for title, group in by_title.items():
        repo_hits = [c for c in group if norm(title) in repo_map]
        if repo_hits:
            out.append(repo_hits[0])
            continue
        clean = [c for c in group if "-" not in c["ticker"] and not c["ticker"].endswith(("W", "R", "U"))]
        pool = clean or group
        out.append(sorted(pool, key=lambda c: (len(c["ticker"]), c["ticker"]))[0])
    return out


def resolve(name: str, repo_map: dict, sec_map: dict, sec_tokens: dict):
    """Return (result_dict, candidates) for one company name."""
    key = norm(name)
    qtok = tokens(name)
    qdist = distinctive(qtok)
    res = {"input_name": name, "normalized": key, "ticker": "", "exchange": "",
           "method": "unresolved", "basis": "", "cik": "", "matched_name": "",
           "ambiguous_alternatives": []}
    if not key:
        res["basis"] = "empty name"
        return res, []

    if key in repo_map:
        tk, ex, matched = repo_map[key]
        res.update({"ticker": tk, "exchange": ex, "method": "repo-verified exact",
                    "basis": "name already verified in this repository (fda_decisions_master.csv / "
                             "stock_price_snapshots.csv)",
                    "matched_name": matched})
        return res, []

    if key in sec_map:
        cands = dedupe_candidates(sec_map[key], repo_map)
        if len(cands) == 1:
            c = cands[0]
            res.update({"ticker": c["ticker"], "method": "SEC exact", "cik": str(c.get("cik") or ""),
                        "basis": "exact normalised match against SEC company_tickers.json "
                                 "(https://www.sec.gov/files/company_tickers.json)",
                        "matched_name": c["title"]})
        else:
            res["ambiguous_alternatives"] = [c["title"] + f" ({c['ticker']})" for c in cands]
            res["basis"] = "several SEC registrants share the normalised name"
        return res, cands

    if not qdist:
        res["basis"] = "name carries no distinctive token - not matched to avoid guessing"
        return res, []

    # token containment: every distinctive query token appears in the registrant name
    cands = []
    for idx, ctok in sec_tokens.items():
        if set(qdist).issubset(set(ctok)):
            cands.extend(sec_map_keyed[idx])
    # fall back to a single distinctive token shared with the registrant
    if not cands:
        for idx, ctok in sec_tokens.items():
            if set(qdist) & set(ctok):
                cands.extend(sec_map_keyed[idx])
    cands = dedupe_candidates(cands, repo_map)
    repo_hits = [c for c in cands if norm(c["title"]) in repo_map]
    if repo_hits:
        c = repo_hits[0]
        res.update({"ticker": c["ticker"], "method": "SEC token + repo tie-break",
                    "cik": str(c.get("cik") or ""),
                    "basis": "SEC company_tickers.json token match disambiguated by a name this "
                             "repository has already verified (" + repo_map[norm(c["title"])][2] + ")",
                    "matched_name": c["title"]})
        return res, cands
    if len(cands) == 1:
        c = cands[0]
        res.update({"ticker": c["ticker"], "method": "SEC token match", "cik": str(c.get("cik") or ""),
                    "basis": "unique SEC registrant whose name contains every distinctive token of "
                             "the FDA applicant name (SEC company_tickers.json)",
                    "matched_name": c["title"]})
    elif cands:
        res["ambiguous_alternatives"] = sorted({c["title"] + f" ({c['ticker']})" for c in cands})
        res["basis"] = f"{len(cands)} SEC registrants match on distinctive tokens"
    else:
        res["basis"] = "no SEC registrant and no repository record matches this name"
    return res, cands


def main() -> None:
    global sec_map_keyed
    repo_map = load_repo_map()
    sec_map = load_sec()
    sec_map_keyed = sec_map
    sec_tokens = {k: tokens(title_list[0]["title"]) for k, title_list in sec_map.items()}
    print(f"repo-verified names: {len(repo_map)}   SEC registrants: {len(sec_map)}")

    names = {}
    for f in ("candidates_2000_2010.json", "candidate_gaps_2011_2025.json"):
        path = STAGING / f
        if not path.exists():
            continue
        for row in json.load(open(path))["rows"]:
            for field in ("company_name_current", "applicant_at_approval"):
                v = (row.get(field) or "").strip()
                if v and v.lower() not in {"n/a", "unknown"}:
                    names.setdefault(v, 0)
                    names[v] += 1

    results = {}
    for name in sorted(names):
        res, _ = resolve(name, repo_map, sec_map, sec_tokens)
        res["rows_affected"] = names[name]
        results[name] = res

    STAGING.mkdir(parents=True, exist_ok=True)
    json.dump({"generated_by": "scripts/resolve_tickers.py",
               "sources": ["https://www.sec.gov/files/company_tickers.json",
                           "data/fda_decisions_master.csv", "data/stock_price_snapshots.csv"],
               "count": len(results), "resolutions": results},
              open(STAGING / "ticker_resolution.json", "w"), indent=1)

    ok = [r for r in results.values() if r["ticker"]]
    amb = [r for r in results.values() if not r["ticker"] and r["ambiguous_alternatives"]]
    un = [r for r in results.values() if not r["ticker"] and not r["ambiguous_alternatives"]]
    print(f"\nresolved: {len(ok)}   ambiguous: {len(amb)}   unresolved: {len(un)}   (of {len(results)})")
    print("\n--- ambiguous (needs a rule, never guessed) ---")
    for r in sorted(amb, key=lambda r: -r["rows_affected"])[:30]:
        print(f"  {r['rows_affected']:3d}  {r['input_name'][:38]:38s} -> {r['ambiguous_alternatives'][:4]}")
    print("\n--- top unresolved ---")
    for r in sorted(un, key=lambda r: -r["rows_affected"])[:40]:
        print(f"  {r['rows_affected']:3d}  {r['input_name'][:60]}")


if __name__ == "__main__":
    main()
