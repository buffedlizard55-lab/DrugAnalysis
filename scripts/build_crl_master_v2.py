#!/usr/bin/env python3
"""Expand the published CRL master from the raw openFDA CRL transparency extract.

Written 2026-09-17 (v2) as a *new* builder, per NEXT_SESSION.md guidance — it does
not reuse scripts/build_crl_expanded.py and never modifies the 58 hand-verified
rows already in data/fda_crl_master.csv.

Input  : data/fda_crl_full_458.csv  — 457 dated CRL rows captured verbatim from
         the official openFDA CRL transparency API
         (https://open.fda.gov/apis/transparency/completeresponseletters/),
         each already carrying two official source links:
           source_url_1 = openFDA CRL transparency API query (reproducible)
           source_url_2 = Drugs@FDA application page (accessdata.fda.gov)
Output : data/fda_crl_master.csv — the existing 58 rows kept row-identical,
         then one new row per raw CRL not already covered by a master row.
         New rows carry the id scheme CR-<APP>-<YYYYMMDD> (stable, self-verifying).
Audit  : data/staging/crl_sponsor_resolution_v2.json — every distinct FDA
         applicant name with its resolution, or the explicit reason it was
         left unresolved. Blank beats guessed.

Ticker resolution policy (deliberately STRICTER than resolve_tickers.py):

  R1 repo-verified exact — the FDA applicant name (modulo legal suffixes) is
     already verified row-by-row in this repository (fda_decisions_master.csv /
     stock_price_snapshots.csv), and comes from a standalone verified row.
     Composite "(current holder) / X" rows encode one drug's corporate history
     and are NOT trusted for unrelated letters (a 2016 Janssen Biotech CRL is
     not Vanda Pharmaceuticals just because one Vanda row lists Janssen as a
     prior developer).
  R2 SEC exact — the FDA applicant name equals an SEC company_tickers.json
     registrant title after case-fold, punctuation-strip and dropping ONLY
     legal-entity suffixes (Inc, Corp, LLC, Ltd, PLC, AG, AB, ADR, USA, ...).
     Distinctive trading names are never dropped: "Clarus Therapeutics" does
     not match "Clarus Corp" (outdoor gear), "RB Health" does not match
     "RB Global" (auctioneers), "Swedish Orphan Biovitrum" does not match
     "Eco Wave Power", "Cadence Pharmaceuticals" does not match "Cadence
     Design Systems", "InnoPharma Licensing" does not match "Music Licensing".

  R3 nothing else. No token/substring matching — the generic fallback in
  resolve_tickers.py produced 7 false positives on this dataset when trialled
  (WAVE, CDNS, SONG, AWI, CLAR, RBA, PLX) and was therefore excluded here.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FULL = DATA / "fda_crl_full_458.csv"
MASTER = DATA / "fda_crl_master.csv"
AUDIT = DATA / "staging" / "crl_sponsor_resolution_v2.json"

MASTER_COLS = ["crl_id", "company_name", "ticker", "exchange", "drug_name",
               "indication", "crl_date", "reason_category", "stock_reaction",
               "source_url_1", "source_url_2", "verification_status", "notes"]

# tokens that carry NO identity because they are purely legal/form-of-entity
LEGAL = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "companies",
    "llc", "llp", "lp", "plc", "ltd", "limited", "ag", "sa", "sas", "se", "nv",
    "bv", "ab", "as", "asa", "oy", "oyj", "spa", "srl", "gmbh", "kgaa", "kk",
    "adr", "ads", "us", "usa", "the", "publ", "pub", "sca", "sociedad",
}


def norm_legal(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    toks = [t for t in s.split() if t and t not in LEGAL]
    return "".join(toks)


def app_key(appno: str) -> str:
    """Normalise 'NDA 218705' / 'NDA206927/Original1;NDA206927' -> 'NDA218705'."""
    m = re.search(r"(NDA|BLA|BL)\s*(\d{5,7})", (appno or "").upper())
    return (m.group(1) + m.group(2)) if m else re.sub(r"[^A-Z0-9]", "", (appno or "").upper())


def load_full() -> list[dict]:
    with FULL.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def load_master() -> list[dict]:
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


# Names whose only repository mapping is itself a flagged irregularity. Not
# propagated to new rows; recorded in VERIFICATION_REPORT.md instead.
# Sunovion: master rows disagree (NO_TICKER vs TSE:4568). TSE 4568 is
# Daiichi Sankyo; Sunovion's parent was Dainippon Sumitomo Pharma
# (TSE 4506). Declining to guess between two repo rows.
REPO_BLOCKLIST = {
    "sunovionpharmaceuticals":
        "repository master rows disagree (NO_TICKER vs TSE:4568); TSE 4568 is "
        "Daiichi Sankyo while Sunovion's parent was Dainippon Sumitomo "
        "Pharma (TSE 4506) - flagged for manual adjudication",
}


def build_repo_map_strict() -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    conflicts: set[str] = set()
    for path, tk_field, ex_field in (
        (DATA / "fda_decisions_master.csv", "ticker", "exchange"),
        (DATA / "stock_price_snapshots.csv", "ticker", None),
    ):
        with path.open(newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                tk = (r.get(tk_field) or "").strip()
                row_name = (r.get("company_name") or r.get("company") or "").strip()
                if not tk or tk.upper() in {"UNRESOLVED", "NO_US_TICKER", "NO_TICKER"} \
                        or "NO_US" in tk.upper() or tk.upper() == "N/A":
                    continue
                composite = "/" in row_name or "current holder" in row_name.lower()
                if composite:
                    continue  # one drug's corporate history is not a general mapping
                for part in re.split(r"/", row_name):
                    part = re.sub(r"\(.*?\)", "", part).strip()
                    key = norm_legal(part)
                    if not key:
                        continue
                    if key in out and out[key][0] != tk:
                        conflicts.add(key)  # repo rows disagree -> refuse to pick
                        continue
                    ex = (r.get(ex_field) or "").strip() if ex_field else "see price snapshot source"
                    out.setdefault(key, (tk, ex, row_name))
    for k in conflicts:
        out.pop(k, None)
    for k in REPO_BLOCKLIST:
        out.pop(k, None)
    return out


def build_sec_map_strict() -> dict[str, list[dict]]:
    raw = json.load(open(DATA / "raw" / "probe" / "sec_company_tickers_alt.json"))
    items = raw.values() if isinstance(raw, dict) else raw
    out: dict[str, list[dict]] = {}
    for it in items:
        ticker = (it.get("ticker") or "").strip()
        title = (it.get("title") or "").strip()
        if not ticker or not title:
            continue
        out.setdefault(norm_legal(title), []).append({"ticker": ticker, "title": title})
    # Identical titles = the same registrant listed twice (e.g. an ADR line and an
    # OTC ordinary line: Jiangsu Hengrui -> JHPCY / JNGHF). Collapse to one entry
    # with the repo's standard preference: shortest clean ticker (ordinary share
    # over longer OTC/F-share lines), then alphabetical.
    # Keys that still hold several DISTINCT titles are genuinely ambiguous -> dropped.
    for k, group in list(out.items()):
        titles = {g["title"] for g in group}
        if len(titles) == 1:
            out[k] = [sorted(group, key=lambda g: (len(g["ticker"]), g["ticker"]))[0]]
        elif len(group) > 1:
            del out[k]
    return out


def master_coverage(master: list[dict], full: list[dict]) -> tuple[set, list[str]]:
    """app_keys already covered by the hand-verified master rows."""
    covered: set[str] = set()
    log: list[str] = []
    full_by_key: dict[str, list[dict]] = {}
    for r in full:
        full_by_key.setdefault(app_key(r["application_number"]), []).append(r)

    for m in master:
        apps = re.findall(r"(?:NDA|BLA|BL)\s*(\d{5,7})", (m.get("notes") or "").upper())
        hit = False
        for a in apps:
            for prefix in ("NDA", "BLA", "BL"):
                k = app_key(prefix + a)
                if k in full_by_key:
                    cands = [r for r in full_by_key[k] if r["crl_date"] == m["crl_date"]]
                    if len(full_by_key[k]) == 1 or cands:
                        covered.add(k)
                        hit = True
                        break
        if not hit:
            key = norm_legal(re.sub(r"\(.*?\)", "", m["company_name"]))
            same_date = [r for r in full if r["crl_date"] == m["crl_date"]]
            cands = [r for r in same_date
                     if (norm_legal(r["raw_company"]) == key or key in norm_legal(r["raw_company"])
                         or norm_legal(r["raw_company"]) in key) and key]
            if len(cands) == 1:
                covered.add(app_key(cands[0]["application_number"]))
                log.append(f"covered-by-name {m['crl_id']} {m['company_name']!r} "
                           f"== {cands[0]['raw_company']!r} on {m['crl_date']}")
        if not hit:
            log.append(f"NOT-COVERED {m['crl_id']} {m['company_name']!r} {m['crl_date']} "
                       f"apps={apps} (master row kept; new rows for the same app are distinct letters)")
    return covered, log


def resolve_strict(name: str, repo: dict, sec: dict) -> dict:
    key = norm_legal(name)
    res = {"input_name": name, "normalized": key, "ticker": "", "exchange": "",
           "method": "unresolved", "matched_name": ""}
    if not key:
        res["basis"] = "empty name"
        return res
    if key in repo:
        tk, ex, row = repo[key]
        res.update(ticker=tk, exchange=ex, method="repo-verified exact", matched_name=row,
                   basis="name verified row-by-row earlier in this repository")
        return res
    if key in REPO_BLOCKLIST:
        res["basis"] = "unresolved: " + REPO_BLOCKLIST[key]
        return res
    if key in sec:
        c = sec[key][0]
        res.update(ticker=c["ticker"], method="SEC exact", matched_name=c["title"],
                   basis="exact match (legal suffixes only removed) against SEC "
                         "company_tickers.json (https://www.sec.gov/files/company_tickers.json)")
        return res
    res["basis"] = ("no standalone repository-verified row and no exact SEC registrant "
                    "title match (legal suffixes removed) — left unresolved, blank beats guessed")
    return res


def main() -> None:
    full = load_full()
    master = load_master()
    covered, cov_log = master_coverage(master, full)
    repo = build_repo_map_strict()
    sec = build_sec_map_strict()

    new_rows: list[dict] = []
    audit: dict = {"generated_by": "scripts/build_crl_master_v2.py",
                   "policy": "R1 repo-verified exact (standalone rows only); "
                             "R2 SEC company_tickers.json exact (legal suffixes removed); "
                             "no token matching; unresolved stays blank",
                   "sources": ["https://open.fda.gov/apis/transparency/completeresponseletters/",
                               "https://www.sec.gov/files/company_tickers.json"],
                   "resolutions": {}}

    for r in full:
        k = app_key(r["application_number"])
        if k in covered:
            continue
        name = (r["raw_company"] or "").strip()
        key = norm_legal(name)
        if name not in audit["resolutions"]:
            audit["resolutions"][name] = resolve_strict(name, repo, sec)
        res = audit["resolutions"][name]
        ticker = res["ticker"]

        if ticker:
            status = "Verified - openFDA CRL transparency API"
            company_out = name if norm_legal(res["matched_name"]) == key else res["matched_name"]
            same = "same name" if norm_legal(res["matched_name"]) == key else \
                f"SEC/repo registrant: {res['matched_name']}"
            note = f"FDA applicant of record: {name}. {same}. {res['basis']}."
            exch = res["exchange"] or ""
        else:
            status = "Verified - FLAGGED (sponsor/equity not yet resolved)"
            company_out = name
            exch = ""
            note = f"FDA applicant of record: {name}. Unresolved — {res['basis']}"

        note += f" Letter dated {r['crl_date']} for application {k}; full text in the " \
                f"openFDA CRL transparency database."
        new_rows.append({
            "crl_id": f"CR-{k}-{r['crl_date'].replace('-', '')}",
            "company_name": company_out,
            "ticker": ticker,
            "exchange": exch,
            "drug_name": r["drug_name"],
            "indication": r["indication"],
            "crl_date": r["crl_date"],
            "reason_category": r["reason_category"],
            "stock_reaction": "",
            "source_url_1": r["source_url_1"],
            "source_url_2": r["source_url_2"],
            "verification_status": status,
            "notes": note,
        })

    new_rows.sort(key=lambda r: (r["crl_date"], r["crl_id"]), reverse=True)
    out_rows = [{c: r[c] for c in MASTER_COLS} for r in master] + \
               [{c: r[c] for c in MASTER_COLS} for r in new_rows]

    # ---- validation before writing anything ----
    ids = [r["crl_id"] for r in out_rows]
    assert len(ids) == len(set(ids)), "duplicate crl_id"
    seen = set()
    for r in new_rows:
        key = (r["crl_id"], r["crl_date"])
        assert key not in seen
        seen.add(key)
    for r in out_rows:
        assert r["source_url_1"] and r["source_url_2"], f"missing source link {r['crl_id']}"
        assert r["crl_date"], f"missing date {r['crl_id']}"
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        before = list(csv.DictReader(fh))
    assert out_rows[:len(before)] == [{c: r.get(c, "") for c in MASTER_COLS} for r in before], \
        "existing 58 master rows must remain identical"

    with MASTER.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MASTER_COLS)
        w.writeheader()
        w.writerows(out_rows)

    audit["full_rows"] = len(full)
    audit["master_before"] = len(master)
    audit["covered_by_master"] = len(covered & {app_key(r["application_number"]) for r in full})
    audit["new_rows"] = len(new_rows)
    audit["resolved_ticker"] = sum(1 for r in new_rows if r["ticker"])
    audit["unresolved"] = sum(1 for r in new_rows if not r["ticker"])
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(audit, AUDIT.open("w"), indent=1)

    by_year = Counter(r["crl_date"][:4] for r in new_rows)
    print(f"master: {len(master)} -> {len(out_rows)} rows (+{len(new_rows)})")
    print(f"resolved: {audit['resolved_ticker']}   unresolved(blank, flagged): {audit['unresolved']}")
    print("new rows per year:", sorted(by_year.items()))
    print("\n--- ALL resolved rows (line-by-line review) ---")
    for r in new_rows:
        if r["ticker"]:
            print(f"  {r['crl_date']}  {r['ticker']:7s} {r['company_name'][:52]}")
    print("\n--- coverage log ---")
    for line in cov_log:
        print(" ", line)


if __name__ == "__main__":
    main()
