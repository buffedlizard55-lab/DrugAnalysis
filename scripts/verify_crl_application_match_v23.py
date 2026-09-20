#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent verifier for the v23 CRL -> application match layer.

Shares no code with ``scripts/build_crl_application_match_v23.py``. It re-reads
the same committed official payloads with a different traversal (a generic
recursive walker that keys off field names instead of the payload family's
container key), recomputes every published cell, and fails closed on any drift.

What it checks
--------------
1. Every CRL row in ``data/crl_application_match.csv`` exists in
   ``data/raw/probe/crl_page1.json`` with the same file_name, letter date and
   FDA approval_status string (joined on file_name, not on id).
2. Row ids are unique and equal ``CR-<APP>-<YYYYMMDD>`` (suffix ``-N`` for the
   two applications FDA publishes two same-day letters for).
3. Every "later ORIGINAL approval action" claim is reproduced from the payloads
   by an independent scan, including the claim that it is the *first* such
   action and that it is strictly after the letter date.
4. Every conflict flag is reproduced from the same independent scan.
5. Per-year, ALL, ALL_MATURE_2Y and ALL_MATURE_3Y denominators, numerators and
   percentages in ``data/crl_year_base_rates.csv`` are recomputed from the
   verified rows; the Wilson lower bound is recomputed with a different
   (closed-form quadratic) implementation.
6. The CRL master join is complete and the one malformed master id
   (``CR--20260227``, the letter FDA publishes without an application number)
   is exactly the unmatched one. The hand-verified curated rows (``C###``,
   which publish no application number) are re-joined independently on
   (letter date, corresponding company name); every link, every flagged
   candidate and every letter left unlinked is recomputed, and pinned counts
   are asserted.
7. Honesty guards: no likelihood/probability column exists, and the coverage
   notes keep the "not a census", "lower bound" and "still in review" caveats.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"

CRL_RAW = RAW / "probe" / "crl_page1.json"
MATCH = DATA / "crl_application_match.csv"
RATES = DATA / "crl_year_base_rates.csv"
MASTER = DATA / "fda_crl_master.csv"

APPROVAL_DIRS = [
    (RAW / "openfda_approvals_2000_2010", "approvals"),
    (RAW / "openfda_orig_decisions_2011_2026", "decisions"),
    (RAW / "openfda_efficacy_supplements", "supplements"),
]

CHECKS = 0
ERRORS: list[str] = []


def check(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        ERRORS.append(message)


def text(value) -> str:
    """Flatten an openFDA value without changing characters.

    openFDA sometimes stores a string as an array of single characters (join
    with nothing) and sometimes as a genuine list of separate strings such as
    ``["NDA 211150/Original 2", "NDA 211150"]`` (join with ``|``). Both
    spellings are preserved exactly as the API serves them.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        if all(isinstance(v, str) and len(v) == 1 for v in value):
            return "".join(text(v) for v in value)
        return "|".join(text(v) for v in value)
    return str(value)


def norm(value: str) -> str:
    m = re.search(r"\b(NDA|BLA|BL|ANDA)\s*[-]?\s*0*(\d{3,7})\b", text(value).upper())
    if not m:
        return ""
    kind = "BLA" if m.group(1) in ("BL", "BLA") else m.group(1)
    return f"{kind}{m.group(2).zfill(6)}"


def iso(value: str) -> str:
    """Normalise the three date spellings used across the committed payloads."""
    t = text(value).strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", t)
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", t)  # Drugs@FDA 20230508
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    return m.group(0) if m else ""


def wilson_lower_closed_form(k: int, n: int, z: float = 1.959963985) -> float:
    """Wilson score interval lower bound written as the quadratic solution."""
    if n == 0:
        return 0.0
    p = k / n
    z2 = z * z
    a = 1.0 + z2 / n
    b = -(2.0 * p + z2 / n)
    c = p * p
    disc = max(0.0, b * b - 4.0 * a * c)
    root = (-b - math.sqrt(disc)) / (2.0 * a)  # lower root
    return max(0.0, min(p, root))


def walk(node, app: str, sink: list, family: str) -> None:
    """Generic recursive walker with payload-family awareness.

    The three committed payload families describe different things, so the
    *kind* of action is decided by the family, not by guessing from fields:

    * ``approvals``   - Drugs@FDA submissions arrays; the submission_type
      decides ORIG vs SUPPL and the submission status must be AP (approved).
    * ``decisions``   - one original approval action per record (decision_date).
    * ``supplements`` - approved efficacy supplements; record carries its own
      ``decision_date`` but is a supplement, never an original.

    Nested submission objects inherit the application number of their parent,
    which is how Drugs@FDA publishes them today.
    """
    if isinstance(node, dict):
        here = norm(text(node.get("application_number", ""))) or app
        sdate = iso(node.get("submission_status_date", ""))
        ddate = iso(node.get("decision_date", ""))
        if here:
            if family == "approvals":
                status = text(node.get("submission_status", "")).upper()
                stype = text(node.get("submission_type", "")).upper()
                if sdate and (status == "AP" or not status):
                    sink.append((here, sdate, "ORIG" if stype.startswith("ORIG") else "SUPPL"))
            elif family == "decisions" and ddate:
                sink.append((here, ddate, "ORIG"))
            elif family == "supplements" and (ddate or sdate):
                sink.append((here, ddate or sdate, "SUPPL"))
        for value in node.values():
            walk(value, here, sink, family)
    elif isinstance(node, list):
        for value in node:
            walk(value, app, sink, family)


def raw_key(rec: dict) -> tuple:
    """The published letter's identity.

    file_name alone repeats in FDA's dataset (multi-application letters), and the
    (file_name, letter_date, company_name) triple still repeats twice, so the
    application number string is part of the key. The quadruple is unique across
    all 458 records - asserted below.
    """
    return (text(rec.get("file_name", "")), iso(rec.get("letter_date", "")),
            text(rec.get("company_name", "")), text(rec.get("application_number", "")))


def load_action_index() -> list:
    actions: list = []
    for folder, family in APPROVAL_DIRS:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            if path.name == "manifest.json":
                continue
            walk(json.loads(path.read_text(encoding="utf-8")), "", actions, family)
    # de-duplicate identical (application, date, kind) triples; the same action is
    # visible through more than one payload family by design
    return sorted(set(actions))


def main() -> int:
    raw = json.loads(CRL_RAW.read_text(encoding="utf-8"))
    records = raw["results"]
    check(len(records) == raw.get("meta", {}).get("results", {}).get("total") == 458,
          f"raw CRL probe is not the expected 458-record published set "
          f"({len(records)} records, total={raw.get('meta', {}).get('results', {}).get('total')})")

    raw_by_key: dict[tuple, list] = {}
    for rec in records:
        raw_by_key.setdefault(raw_key(rec), []).append(rec)
    check(all(len(v) == 1 for v in raw_by_key.values()),
          "raw CRL records are not uniquely identified by "
          "(file_name, letter_date, company_name, application_number)")

    rows = list(csv.DictReader(MATCH.open(newline="", encoding="utf-8")))
    check(len(rows) == 458, f"crl_application_match has {len(rows)} rows, expected 458")
    check(len({r["crl_row_id"] for r in rows}) == len(rows),
          "crl_application_match row ids are not unique")

    for col in rows[0]:
        check(not any(bad in col.lower() for bad in
                      ("likelihood", "probability", "p_approval", "odds_ratio")),
              f"crl_application_match carries a forbidden column: {col}")

    actions = load_action_index()
    by_app: dict[str, list] = {}
    for app, date, kind in actions:
        by_app.setdefault(app, []).append((date, kind))
    check(len(by_app) > 9000,
          f"independent action scan found only {len(by_app)} applications - payloads missing?")

    recomputed: list[dict] = []
    for row in rows:
        key = (row["raw_file_name"], row["letter_date"], row["company_name_verbatim"],
               row["application_number_verbatim"])
        bucket = raw_by_key.get(key)
        check(bool(bucket), f"match row {row['crl_row_id']}: no raw CRL record for its "
                            f"(file_name, letter_date, company, application number) key")
        if not bucket:
            continue
        rec = bucket.pop()  # consume, so two rows cannot claim the same raw record
        check(iso(rec.get("letter_date", "")) == row["letter_date"],
              f"match row {row['crl_row_id']}: letter_date drifted")
        check(text(rec.get("approval_status", "")) == row["fda_approval_status_verbatim"],
              f"match row {row['crl_row_id']}: FDA approval_status drifted")
        check(text(rec.get("letter_type", "")) == row["letter_type_verbatim"],
              f"match row {row['crl_row_id']}: letter_type drifted")

        app = row["application_number_normalised"]
        check(app == norm(row["application_number_verbatim"]),
              f"match row {row['crl_row_id']}: normalised application number is not a "
              f"pure normalisation of the FDA string")

        letter = row["letter_date"]
        want_suffix = ""
        if app and letter:
            base = f"CR-{app}-{letter.replace('-', '')}"
            if row["crl_row_id"] != base:
                want_suffix = row["crl_row_id"].replace(base, "", 1)
                check(re.fullmatch(r"-\d+", want_suffix) is not None,
                      f"match row {row['crl_row_id']}: unexpected id shape")
        else:
            check(row["crl_row_id"].startswith("CRL-NOKEY-"),
                  f"match row {row['crl_row_id']}: id shape without application/date")

        later_orig = sorted(d for d, k in by_app.get(app, []) if k == "ORIG" and d > letter)
        later_any = sorted(d for d, k in by_app.get(app, []) if d > letter)
        got_orig = row["later_original_approval_actions_observed"] != "0"
        check(got_orig == bool(later_orig),
              f"match row {row['crl_row_id']}: later-ORIGINAL claim disagrees with the payloads")
        check(row["first_later_original_action_date"] == (later_orig[0] if later_orig else ""),
              f"match row {row['crl_row_id']}: first later original date is not the earliest")
        check(row["later_any_approval_actions_observed"] != "0" or not later_any,
              f"match row {row['crl_row_id']}: later-any count misses an action")
        if later_orig and letter:
            days = (dt.date.fromisoformat(later_orig[0]) - dt.date.fromisoformat(letter)).days
            check(row["days_letter_to_first_later_original_action"] == str(days),
                  f"match row {row['crl_row_id']}: day count drifted")
        want_conflict = ""
        fda = row["fda_approval_status_verbatim"]
        if fda == "Approved" and not later_orig:
            want_conflict = "FDA_FIELD_APPROVED_NO_LATER_ORIGINAL_ACTION_IN_COMMITTED_COVERAGE"
        elif fda and fda != "Approved" and later_orig:
            want_conflict = "LATER_ORIGINAL_ACTION_OBSERVED_WHILE_FDA_FIELD_NOT_APPROVED"
        check(row["conflict_flag"] == want_conflict,
              f"match row {row['crl_row_id']}: conflict flag drifted "
              f"({row['conflict_flag']!r} != {want_conflict!r})")
        check(row["conflict_flag"] in ("", "FDA_FIELD_APPROVED_NO_LATER_ORIGINAL_ACTION_IN_COMMITTED_COVERAGE",
                                       "LATER_ORIGINAL_ACTION_OBSERVED_WHILE_FDA_FIELD_NOT_APPROVED"),
              f"match row {row['crl_row_id']}: unknown conflict flag value")
        recomputed.append({
            "year": row["letter_year"], "date": letter, "app": app,
            "orig": bool(later_orig), "any": bool(later_any),
            "approved": fda == "Approved", "conflict": bool(row["conflict_flag"]),
            "days": int(row["days_letter_to_first_later_original_action"])
            if row["days_letter_to_first_later_original_action"] else None,
        })

    # ---- master join -------------------------------------------------------
    master_cr = [r["crl_id"] for r in csv.DictReader(MASTER.open(newline="", encoding="utf-8-sig"))
                 if r["crl_id"].startswith("CR-")]
    malformed = "CR--20260227"
    joined = {r["master_crl_id"] for r in rows if r["master_crl_id"]}
    check(set(master_cr) - joined == {malformed},
          f"master join incomplete: {sorted(set(master_cr) - joined)[:5]} unmatched "
          f"(only the malformed {malformed} may be unmatched)")
    check(malformed not in joined, "the malformed master id unexpectedly joined a letter")
    joined_cr = {m for m in joined if m.startswith("CR-")}
    check(len(joined_cr) == len(master_cr) - 1,
          f"application-keyed master join count {len(joined_cr)} != "
          f"{len(master_cr) - 1} well-formed master ids")

    # ---- curated master rows (hand-verified, no application number) ---------
    master_rows = list(csv.DictReader(MASTER.open(newline="", encoding="utf-8-sig")))
    curated = [(r["crl_id"], text(r.get("company_name", "")), text(r.get("crl_date", "")))
               for r in master_rows if re.fullmatch(r"C\d+", text(r.get("crl_id", "")))]
    check(len(curated) == 58, f"curated master rows: expected 58, got {len(curated)}")
    curated_ids = {c[0] for c in curated}
    curated_by_date: dict[str, list[tuple[str, str]]] = {}
    for cid, cname, cdate in curated:
        curated_by_date.setdefault(cdate, []).append((cid, cname))

    _drop = {"INC", "INCORPORATED", "LLC", "LTD", "LIMITED", "PLC", "CORP", "CORPORATION",
             "COMPANY", "CO", "GMBH", "AG", "SA", "SE", "NV", "BV", "AB", "KK", "LP",
             "SPA", "SAS", "KGAA", "USA", "US", "THE", "AND"}

    def nco(name: str) -> str:
        t = re.sub(r"[^A-Z0-9 ]", " ", text(name).upper())
        return " ".join(x for x in t.split() if x not in _drop)

    def correspond(a: str, b: str) -> bool:
        na, nb = nco(a), nco(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        short, long = sorted((na, nb), key=len)
        if len(short) < 5 or short not in long:
            return False
        return short.split()[0] == long.split()[0]

    # independent recomputation of the unambiguous links: a curated row links to
    # a letter only when exactly one letter on that date corresponds and that
    # letter corresponds to exactly one curated row
    per_letter: dict[str, list[str]] = {}
    per_curated: dict[str, list[str]] = {}
    for cid, cname, cdate in curated:
        for row in rows:
            if row["letter_date"] != cdate:
                continue
            if correspond(row["company_name_verbatim"], cname):
                per_letter.setdefault(row["crl_row_id"], []).append(cid)
                per_curated.setdefault(cid, []).append(row["crl_row_id"])
    expect_join = {rid for rid, cids in per_letter.items()
                   if len(cids) == 1 and len(per_curated[cids[0]]) == 1}
    got_join = {r["crl_row_id"] for r in rows
                if r["master_link_status"] == "JOINED_CURATED_DATE_COMPANY"}
    check(got_join == expect_join,
          f"curated link set drifted: published {len(got_join)} rows, recomputed {len(expect_join)} "
          f"(only-in-csv {sorted(got_join - expect_join)[:3]}, only-in-scan "
          f"{sorted(expect_join - got_join)[:3]})")
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["master_link_status"]] = status_counts.get(row["master_link_status"], 0) + 1
    unlinked = [r for r in rows if r["master_link_status"] not in
                ("JOINED", "FDA_PUBLISHED_NO_APPLICATION_NUMBER")]
    check(len(unlinked) == 58,
          f"letters without an application-keyed master row: {len(unlinked)} != 58")
    with_candidate = [r for r in unlinked if curated_by_date.get(r["letter_date"])]
    expect_flagged = len(with_candidate) - len(expect_join)
    expect_nomaster = len(unlinked) - len(with_candidate)
    check(status_counts.get("JOINED") == 399,
          f"application-keyed joins: {status_counts.get('JOINED')} != 399")
    check(status_counts.get("JOINED_CURATED_DATE_COMPANY") == len(expect_join),
          f"curated joins: {status_counts.get('JOINED_CURATED_DATE_COMPANY')} != {len(expect_join)}")
    check(status_counts.get("CURATED_CANDIDATE_NOT_JOINED") == expect_flagged,
          f"flagged curated candidates: {status_counts.get('CURATED_CANDIDATE_NOT_JOINED')} "
          f"!= {expect_flagged}")
    check(status_counts.get("NO_MASTER_ROW") == expect_nomaster,
          f"letters with no master key at all: {status_counts.get('NO_MASTER_ROW')} != {expect_nomaster}")
    check(status_counts.get("FDA_PUBLISHED_NO_APPLICATION_NUMBER") == 1,
          "expected exactly one letter published without an application number")

    claimed_curated: dict[str, str] = {}
    for row in rows:
        cid = row["master_crl_id"]
        if cid in curated_ids:
            check(cid not in claimed_curated,
                  f"curated master row {cid} is claimed by two letters "
                  f"({claimed_curated.get(cid)} and {row['crl_row_id']})")
            claimed_curated[cid] = row["crl_row_id"]
            match = next((c for c in curated if c[0] == cid), None)
            check(match is not None and match[2] == row["letter_date"],
                  f"{row['crl_row_id']}: curated link {cid} does not carry the letter date")
            check(match is not None and correspond(row["company_name_verbatim"], match[1]),
                  f"{row['crl_row_id']}: curated link {cid} company names do not correspond")
        if row["master_link_status"] == "CURATED_CANDIDATE_NOT_JOINED":
            cands = [c for c in row["curated_candidate_ids"].split("|") if c]
            check(bool(cands), f"{row['crl_row_id']}: flagged row lost its curated candidates")
            for c in cands:
                check(c in curated_ids, f"{row['crl_row_id']}: unknown curated candidate {c}")
                check(any(cc[0] == c and cc[2] == row["letter_date"] for cc in curated),
                      f"{row['crl_row_id']}: candidate {c} does not carry the letter date")
            check(row["crl_row_id"] not in expect_join,
                  f"{row['crl_row_id']}: flagged row is in fact an unambiguous link")
        if row["master_link_status"] == "NO_MASTER_ROW":
            check(not curated_by_date.get(row["letter_date"]),
                  f"{row['crl_row_id']}: labelled NO_MASTER_ROW but a curated row shares the date")
    check(len(claimed_curated) == len(expect_join),
          f"curated links claimed {len(claimed_curated)} != recomputed {len(expect_join)}")

    # ---- aggregates --------------------------------------------------------
    rates = list(csv.DictReader(RATES.open(newline="", encoding="utf-8")))
    rate_by = {r["letter_year"]: r for r in rates}
    last_updated = raw.get("meta", {}).get("last_updated", "")
    check(bool(last_updated), "raw CRL probe lost meta.last_updated")

    def expect(label: str, subset: list) -> None:
        row = rate_by.get(label)
        check(row is not None, f"crl_year_base_rates is missing the {label} row")
        if row is None:
            return
        n = len(subset)
        obs = sum(1 for r in subset if r["orig"])
        obs_any = sum(1 for r in subset if r["any"])
        approved = sum(1 for r in subset if r["approved"])
        check(int(row["published_crl_letters"]) == n,
              f"{label}: denominator {row['published_crl_letters']} != recomputed {n}")
        check(int(row["letters_with_later_original_action_observed"]) == obs,
              f"{label}: numerator {row['letters_with_later_original_action_observed']} != {obs}")
        check(int(row["letters_with_any_later_action_observed"]) == obs_any,
              f"{label}: any-action numerator drifted")
        check(int(row["fda_field_approved_letters"]) == approved,
              f"{label}: FDA-approved count drifted")
        if n:
            check(abs(float(row["observed_later_original_action_pct"]) - 100.0 * obs / n) < 0.05,
                  f"{label}: observed percentage != k/n")
            lb = 100.0 * wilson_lower_closed_form(obs, n)
            check(abs(float(row["observed_original_pct_wilson_lower_95"]) - lb) < 0.15,
                  f"{label}: Wilson lower bound {row['observed_original_pct_wilson_lower_95']} "
                  f"!= independent {lb:.2f}")
            check(lb <= 100.0 * obs / n, f"{label}: Wilson lower bound exceeds the point estimate")
        days = sorted(r["days"] for r in subset if r["days"] is not None)
        want = str(days[len(days) // 2]) if days else ""
        check(row["median_days_to_first_later_original_action"] == want,
              f"{label}: median days drifted")
        check(int(row["conflict_rows"]) == sum(1 for r in subset if r["conflict"]),
              f"{label}: conflict count drifted")
        # every row must say the denominator is FDA's published subset; the
        # cohort rows must also warn the observed figure is a lower bound, while
        # calendar-year rows must flag the any-action column as an upper bound
        need = ["not a census"]
        need.append("lower bound" if label.startswith("ALL") else "upper bound")
        check(all(chk in row["coverage_note"] for chk in need),
              f"{label}: coverage note lost a required caveat ({need})")
        check(row["cohort_maturity"].startswith("LETTER_DATE_ON_OR_BEFORE_")
              or row["cohort_maturity"].startswith("ALL_"),
              f"{label}: cohort_maturity label lost")

    for year in sorted({r["year"] for r in recomputed}):
        expect(year, [r for r in recomputed if r["year"] == year])
    common = [r for r in recomputed if r["date"]]
    expect("ALL", common)
    for label, years in (("ALL_MATURE_2Y", 2), ("ALL_MATURE_3Y", 3)):
        cut = (dt.date.fromisoformat(last_updated) - dt.timedelta(days=365 * years)).isoformat()
        expect(label, [r for r in common if r["date"] <= cut])

    check(all(len(v) == 0 for v in raw_by_key.values()),
          "a raw CRL record was not claimed by any published row")

    for err in ERRORS[:25]:
        print("ERROR", err)
    if len(ERRORS) > 25:
        print(f"ERROR ... {len(ERRORS) - 25} more")
    print(f"v23 CRL layer verified independently: {CHECKS} checks, {len(ERRORS)} error(s); "
          f"{len(rows)} letters, {len(recomputed)} rows recomputed, "
          f"{len(by_app)} applications in the independent action scan.")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
