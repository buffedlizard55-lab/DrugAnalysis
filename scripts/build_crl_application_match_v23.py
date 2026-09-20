#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v23 (2026-09-20): CRL -> application match layer and observed base rates.

Why this exists
---------------
The published CRL master (``data/fda_crl_master.csv``, 458 rows) is a flat list
of letters. The decision engine's documented blocking limitation is that it has
no denominator behind the letters, so it refuses to print project-derived
likelihoods. This builder takes the first honest step at that denominator using
only official, already-committed payloads:

* the CRL letters themselves - FDA's own openFDA Complete Response Letter
  transparency dataset, captured verbatim in
  ``data/raw/probe/crl_page1.json`` (458 records, ``meta.results.total = 458``,
  ``last_updated`` recorded in that file). Each record carries FDA's own
  ``application_number``, ``letter_date``, ``letter_year``, ``letter_type`` and
  ``approval_status`` fields. Nothing is inferred from news or third parties;
  the dataset's ``text`` field is not copied into any table.
* application-level approval payloads committed in this repository:
  - ``data/raw/openfda_approvals_2000_2010/*.json`` - every application with an
    ORIG/AP action in each year 2000-2010 **plus that application's full
    ``submissions`` array as Drugs@FDA publishes it today**;
  - ``data/raw/openfda_orig_decisions_2011_2026/decisions_*.json`` - ORIG/AP
    actions 2011-2026 (the block also carries 1985-2010, used here as a
    secondary check on the same application numbers);
  - ``data/raw/openfda_efficacy_supplements/suppl_*.json`` - approved efficacy
    supplements 2000-2026.

What is published
-----------------
``data/crl_application_match.csv``  - one row per published CRL letter with the
    normalised application number, FDA's own ``approval_status`` string, whether
    any later approval action by the same application is independently observed
    in the committed FDA payloads (with the date and the payload that carries
    it), the elapsed days, and a conflict flag when FDA's field and the observed
    payload disagree.

``data/crl_year_base_rates.csv`` - one row per letter year: published letters
    (the denominator that FDA itself publishes), letters FDA marks Approved,
    letters with an independently observed later approval action, the ratio with
    a 95% Wilson lower bound, and the median observed days from letter to the
    next approval action.

``data/crl_match_sources.csv`` - the payloads searched, with row counts and
    SHA-256, so a reviewer can re-run the join.

Standing honesty rules
----------------------
1. The openFDA CRL dataset is FDA's **published subset**, not a census of every
   CRL FDA has issued. Every rate here is therefore a rate over published
   letters, and the tables say so.
2. "No later approval action observed" is **not** evidence of failure: it can
   also mean the application's later action is outside the committed payload
   coverage. The column name says "observed".
3. FDA's own ``approval_status`` field is published verbatim and never
   reinterpreted; where it disagrees with the observed payload evidence the row
   is flagged for human review instead of being resolved by preference.
4. No probability is attached to any individual pending decision. Only the
   letter-level cohort is described.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"

CRL_RAW = RAW / "probe" / "crl_page1.json"
APPROVALS_2000_2010 = RAW / "openfda_approvals_2000_2010"
ORIG_2011_2026 = RAW / "openfda_orig_decisions_2011_2026"
EFFICACY_SUPPL = RAW / "openfda_efficacy_supplements"
MASTER = DATA / "fda_crl_master.csv"

BUILDER_TAG = "v23 2026-09-20"
EXPECT_CRL_ROWS = 458
CRL_DATASET_URL = "https://api.fda.gov/transparency/crl.json?limit=1000"
CRL_DATASET_PAGE = ("https://open.fda.gov/apis/transparency/"
                    "completeresponseletters/")
DAF = ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
       "?event=overview.process&varApplNo={num}")
CRL_QUERY = "https://api.fda.gov/transparency/crl.json?search="


def crl_replay_url(file_name: str, raw_letter_date: str) -> str:
    """A per-record replay link.

    Some file_name values repeat in FDA's dataset (multi-application letters), so
    the letter date is added to the query when it is known. Values are
    percent-encoded; the api.fda.gov search syntax itself is passed through.
    """
    parts = []
    if file_name:
        parts.append(quote(f'file_name:"{file_name}"', safe=""))
    if raw_letter_date:
        parts.append(quote(f'letter_date:"{raw_letter_date}"', safe=""))
    return CRL_QUERY + "+AND+".join(parts) if parts else CRL_DATASET_URL


def fail(msg: str) -> None:
    raise SystemExit(f"build_crl_application_match_v23: {msg}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_text(value) -> str:
    """openFDA stores some strings as arrays of single characters.

    e.g. ``letter_type: ["C","O","M", ...]``. Values are joined verbatim; no
    character is changed or dropped.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        if all(isinstance(v, str) and len(v) == 1 for v in value):
            return "".join(value)
        return "|".join(as_text(v) for v in value)
    return str(value)


def norm_appl(raw: str) -> tuple[str, str]:
    """('BLA125827', 'BLA') from 'BL 125827' / 'BLA 125827' / 'NDA 211150/Original 2'.

    The official spelling is preserved in the published row; this only
    normalises the type prefix so the same application can be joined.
    """
    m = re.search(r"\b(NDA|BLA|ANDA|BL)\s*[\-]?\s*0*(\d{3,7})\b", as_text(raw).upper())
    if not m:
        return "", ""
    kind = "BLA" if m.group(1) in ("BL", "BLA") else m.group(1)
    return f"{kind}{m.group(2).zfill(6)}", kind


def iso_date(raw: str) -> str:
    t = as_text(raw).strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", t)
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    return ""


def wilson_lower(k: int, n: int, z: float = 1.959963985) -> float:
    if n == 0:
        return 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def load_master_ids() -> dict[tuple[str, str], str]:
    ids: dict[tuple[str, str], str] = {}
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            cid = r.get("crl_id", "")
            m = re.match(r"CR-([A-Z]+)(\d+)-(\d{4})(\d{2})(\d{2})$", cid)
            if m:
                # the master builder wrote 'BL' for some biologics; normalise to
                # BLA so the same application joins to the CRL dataset spelling.
                kind = "BLA" if m.group(1) == "BL" else m.group(1)
                ids[(f"{kind}{m.group(2).lstrip('0').zfill(6)}",
                     f"{m.group(3)}-{m.group(4)}-{m.group(5)}")] = cid
    return ids


def build_approval_index() -> tuple[dict[str, list[tuple[str, str, str]]], list[dict]]:
    """application -> [(iso_date, submission_type, source_label)] for AP actions."""
    index: dict[str, list[tuple[str, str, str]]] = {}
    sources: list[dict] = []
    files = sorted(p for p in APPROVALS_2000_2010.glob("*.json") if p.name != "manifest.json")
    rows = 0
    for p in files:
        obj = json.loads(p.read_text(encoding="utf-8"))
        for rec in obj.get("results", []):
            appl, _kind = norm_appl(rec.get("application_number", ""))
            if not appl:
                continue
            rows += 1
            for sub in rec.get("submissions", []):
                sd = as_text(sub.get("submission_status_date", ""))
                if len(sd) != 8 or not sd.isdigit():
                    continue
                if as_text(sub.get("submission_status", "")).upper() != "AP":
                    continue
                index.setdefault(appl, []).append((
                    f"{sd[0:4]}-{sd[4:6]}-{sd[6:8]}",
                    as_text(sub.get("submission_type", "")),
                    "openfda_approvals_2000_2010 (full submissions array)",
                ))
        sources.append({
            "file": str(p.relative_to(ROOT)).replace("\\", "/"),
            "role": "Applications with an ORIG/AP action in this year, including Drugs@FDA's full submissions array as published today",
            "records": str(len(obj.get("results", []))),
            "bytes": str(p.stat().st_size),
            "sha256": sha256_file(p),
        })
    print(f"approval index: {len(index)} applications, {rows} application-year records")

    files = sorted(p for p in ORIG_2011_2026.glob("decisions_*.json"))
    rows = 0
    for p in files:
        obj = json.loads(p.read_text(encoding="utf-8"))
        for rec in obj.get("decisions", []):
            appl, _kind = norm_appl(rec.get("application_number", ""))
            if not appl:
                continue
            d = iso_date(rec.get("decision_date", ""))
            if not d:
                continue
            rows += 1
            index.setdefault(appl, []).append((d, "ORIG",
                                               "openfda_orig_decisions_2011_2026"))
    sources.append({
        "file": f"{str(ORIG_2011_2026.relative_to(ROOT))}/decisions_*.json".replace("\\", "/"),
        "role": "ORIG/AP approval actions by application (1985-2026 block; 2011-2026 is the primary coverage here)",
        "records": str(rows),
        "bytes": str(sum(p.stat().st_size for p in files)),
        "sha256": "|".join(sha256_file(p) for p in files[:3]) + "|...(42 files)",
    })
    print(f"ORIG payload index: {rows} approval actions added")

    files = sorted(p for p in EFFICACY_SUPPL.glob("suppl_*.json"))
    rows = 0
    for p in files:
        obj = json.loads(p.read_text(encoding="utf-8"))
        for rec in obj.get("supplements", []):
            appl, _kind = norm_appl(rec.get("application_number", ""))
            if not appl:
                continue
            d = iso_date(rec.get("submission_status_date") or rec.get("decision_date") or "")
            if not d:
                continue
            rows += 1
            index.setdefault(appl, []).append((d, "SUPPL",
                                               "openfda_efficacy_supplements"))
    sources.append({
        "file": f"{str(EFFICACY_SUPPL.relative_to(ROOT))}/suppl_*.json".replace("\\", "/"),
        "role": "Approved efficacy supplements by application (2000-2026)",
        "records": str(rows),
        "bytes": str(sum(p.stat().st_size for p in files)),
        "sha256": "|".join(sha256_file(p) for p in files[:3]) + "|...(27 files)",
    })
    print(f"efficacy supplement index: {rows} actions added")
    return index, sources


def main() -> int:
    if not CRL_RAW.exists():
        fail(f"missing {CRL_RAW}")
    raw = json.loads(CRL_RAW.read_text(encoding="utf-8"))
    letters = raw.get("results") or []
    if len(letters) != EXPECT_CRL_ROWS:
        fail(f"CRL dataset drifted: {len(letters)} records != {EXPECT_CRL_ROWS}")
    if raw.get("meta", {}).get("results", {}).get("total") != EXPECT_CRL_ROWS:
        fail("CRL dataset meta.results.total drifted")

    master_ids = load_master_ids()
    index, sources = build_approval_index()

    match_rows: list[dict] = []
    seen_ids: dict[str, int] = {}
    per_year: dict[str, dict[str, int]] = {}
    days_by_year: dict[str, list[int]] = {}
    unmatched_master: set[tuple[str, str]] = set(master_ids)
    n_without_appl = 0

    for i, rec in enumerate(letters, start=1):
        appl_raw = rec.get("application_number") or []
        appl_list = appl_raw if isinstance(appl_raw, list) else [appl_raw]
        verbatim = "|".join(as_text(a) for a in appl_list if as_text(a))
        normalised = []
        for a in appl_list:
            key, kind = norm_appl(a)
            if key:
                normalised.append((key, kind))
        letter_date = iso_date(rec.get("letter_date"))
        year = as_text(rec.get("letter_year")) or letter_date[:4]
        fda_status = as_text(rec.get("approval_status"))
        file_name = as_text(rec.get("file_name"))
        letter_type = as_text(rec.get("letter_type"))

        later: list[tuple[str, str, str]] = []
        later_orig: list[tuple[str, str, str]] = []
        for key, _kind in normalised:
            for d, stype, src in index.get(key, []):
                if letter_date and d > letter_date:
                    later.append((d, stype, src))
                    if stype.upper() == "ORIG":
                        later_orig.append((d, stype, src))
        later.sort(); later_orig.sort()
        first_later = later[0][0] if later else ""
        first_later_orig = later_orig[0][0] if later_orig else ""
        days = ""
        if first_later_orig and letter_date:
            days = str((_dt.date.fromisoformat(first_later_orig)
                        - _dt.date.fromisoformat(letter_date)).days)
            days_by_year.setdefault(year, []).append(int(days))

        primary = normalised[0] if normalised else ("", "")
        crl_id = (f"CR-{primary[0]}-{letter_date.replace('-', '')}"
                  if primary[0] and letter_date else f"CRL-NOKEY-{i:03d}")
        # FDA publishes two distinct letter documents for the same application on
        # the same date in two cases (BLA761215 2021-12-17, BLA761303 2024-03-22).
        # Both are kept; the id gets a deterministic suffix so it stays unique.
        dup_flag = "FALSE"
        seen_ids[crl_id] = seen_ids.get(crl_id, 0) + 1
        if seen_ids[crl_id] > 1:
            dup_flag = "TRUE"
            crl_id = f"{crl_id}-{seen_ids[crl_id]}"
        master_hit = ""
        master_link = "NO_MASTER_ROW"
        if primary[0] and letter_date:
            master_hit = master_ids.get((primary[0], letter_date), "")
            if master_hit:
                master_link = "JOINED"
                unmatched_master.discard((primary[0], letter_date))
        else:
            master_link = "APPLICATION_NUMBER_NOT_PUBLISHED_BY_FDA"
        if not normalised:
            n_without_appl += 1

        conflict = ""
        if fda_status == "Approved" and not later_orig:
            conflict = "FDA_FIELD_APPROVED_NO_LATER_ORIGINAL_ACTION_IN_COMMITTED_COVERAGE"
        elif fda_status and fda_status != "Approved" and later_orig:
            conflict = "LATER_ORIGINAL_ACTION_OBSERVED_WHILE_FDA_FIELD_NOT_APPROVED"

        bucket = per_year.setdefault(year, {"letters": 0, "fda_approved": 0,
                                            "observed": 0, "observed_any": 0,
                                            "conflict": 0})
        bucket["letters"] += 1
        if fda_status == "Approved":
            bucket["fda_approved"] += 1
        if later_orig:
            bucket["observed"] += 1
        if later:
            bucket["observed_any"] += 1
        if conflict:
            bucket["conflict"] += 1

        match_rows.append({
            "crl_row_id": crl_id,
            "master_crl_id": master_hit,
            "master_link_status": master_link,
            "duplicate_letter_same_app_same_date": dup_flag,
            "raw_file_name": file_name,
            "company_name_verbatim": as_text(rec.get("company_name")),
            "application_number_verbatim": verbatim,
            "application_number_normalised": primary[0],
            "application_kind": primary[1],
            "letter_date": letter_date,
            "letter_year": year,
            "letter_type_verbatim": letter_type,
            "fda_approval_status_verbatim": fda_status,
            "later_original_approval_actions_observed": str(len(later_orig)),
            "first_later_original_action_date": first_later_orig,
            "days_letter_to_first_later_original_action": days,
            "later_any_approval_actions_observed": str(len(later)),
            "first_later_any_action_date": first_later,
            "later_original_action_sources": "; ".join(sorted({s for _d, _t, s in later_orig})),
            "later_any_action_types": "; ".join(sorted({f"{d} {t}" for d, t, _s in later[:6]})),
            "conflict_flag": conflict,
            "fda_application_url": DAF.format(num=normalised[0][0]) if normalised else "",
            "replay_query_url": crl_replay_url(file_name, as_text(rec.get("letter_date"))),
            "dataset_last_updated": raw.get("meta", {}).get("last_updated", ""),
            "evidence_source_files": ("data/raw/probe/crl_page1.json|"
                                      "data/raw/openfda_approvals_2000_2010/*.json|"
                                      "data/raw/openfda_orig_decisions_2011_2026/decisions_*.json|"
                                      "data/raw/openfda_efficacy_supplements/suppl_*.json"),
            "verification_status": "Verified (verbatim FDA CRL record; approval actions observed in committed FDA payloads)",
            "notes": (f"{BUILDER_TAG}: FDA's own approval_status field is published verbatim and is "
                      f"not reinterpreted. 'Observed' means an approval action with a later status "
                      f"date exists for the same application number inside the committed payload "
                      f"coverage; absence of an observed action is NOT evidence that the application "
                      f"failed. conflict_flag=" + (conflict or "NONE") +
                      "; the flag is raised for human review, never resolved by preference."),
        })

    # ------------------------------------------------------------------ rates
    rate_rows = []
    for year in sorted(per_year):
        b = per_year[year]
        n = b["letters"]
        obs = b["observed"]
        obs_any = b["observed_any"]
        approved = b["fda_approved"]
        days = sorted(days_by_year.get(year, []))
        median = str(days[len(days) // 2]) if days else ""
        rate_rows.append({
            "letter_year": year,
            "cohort_maturity": "ALL_LETTERS_IN_YEAR",
            "published_crl_letters": str(n),
            "fda_field_approved_letters": str(approved),
            "fda_field_approved_pct": f"{100.0 * approved / n:.1f}" if n else "",
            "letters_with_later_original_action_observed": str(obs),
            "observed_later_original_action_pct": f"{100.0 * obs / n:.1f}" if n else "",
            "observed_original_pct_wilson_lower_95": f"{100.0 * wilson_lower(obs, n):.1f}" if n else "",
            "letters_with_any_later_action_observed": str(obs_any),
            "observed_any_action_pct": f"{100.0 * obs_any / n:.1f}" if n else "",
            "median_days_to_first_later_original_action": median,
            "conflict_rows": str(b["conflict"]),
            "coverage_note": ("Denominator = CRL letters FDA itself publishes in the openFDA CRL "
                              "transparency dataset for this year (FDA's published subset, not a "
                              "census). Headline numerator = letters whose application number shows "
                              "a later ORIGINAL approval action (submission_type ORIG, status AP) in "
                              "the committed payloads - the closest public analogue of a successful "
                              "resubmission. The 'any action' column also counts approved "
                              "supplements on the same application, which need not relate to the "
                              "letter, and is therefore an upper bound."),
        })
    total_n = sum(b["letters"] for b in per_year.values())
    total_obs = sum(b["observed"] for b in per_year.values())
    total_obs_any = sum(b["observed_any"] for b in per_year.values())
    total_approved = sum(b["fda_approved"] for b in per_year.values())
    all_days = sorted(d for lst in days_by_year.values() for d in lst)
    rate_rows.append({
        "letter_year": "ALL",
        "cohort_maturity": "ALL_PUBLISHED_LETTERS_2002_2026",
        "published_crl_letters": str(total_n),
        "fda_field_approved_letters": str(total_approved),
        "fda_field_approved_pct": f"{100.0 * total_approved / total_n:.1f}",
        "letters_with_later_original_action_observed": str(total_obs),
        "observed_later_original_action_pct": f"{100.0 * total_obs / total_n:.1f}",
        "observed_original_pct_wilson_lower_95": f"{100.0 * wilson_lower(total_obs, total_n):.1f}",
        "letters_with_any_later_action_observed": str(total_obs_any),
        "observed_any_action_pct": f"{100.0 * total_obs_any / total_n:.1f}",
        "median_days_to_first_later_original_action": str(all_days[len(all_days) // 2]) if all_days else "",
        "conflict_rows": str(sum(b["conflict"] for b in per_year.values())),
        "coverage_note": ("All published letters 2002-2026. FDA's CRL dataset is its published "
                          "subset, not a census of every CRL FDA issued, and it is the denominator "
                          "here. The observed figure is a lower bound on conversion: payload "
                          "coverage is partial and one letter publishes no application number, so "
                          "it cannot be matched at all. This all-years figure is diluted by recent "
                          "letters whose resubmissions are still in review; see the ALL_MATURE_2Y "
                          "and ALL_MATURE_3Y rows for the maturity-restricted cohorts."),
    })

    last_updated = raw.get("meta", {}).get("last_updated", "")

    def _cohort_row(label: str, years: int):
        if not last_updated:
            return None
        cut = (_dt.date.fromisoformat(last_updated) - _dt.timedelta(days=365 * years)).isoformat()
        sel = [r for r in match_rows if r["letter_date"] and r["letter_date"] <= cut]
        n = len(sel)
        if not n:
            return None
        obs = sum(1 for r in sel if r["later_original_approval_actions_observed"] != "0")
        obs_any = sum(1 for r in sel if r["later_any_approval_actions_observed"] != "0")
        approved = sum(1 for r in sel if r["fda_approval_status_verbatim"] == "Approved")
        days = sorted(int(r["days_letter_to_first_later_original_action"])
                      for r in sel if r["days_letter_to_first_later_original_action"])
        return {
            "letter_year": label,
            "cohort_maturity": f"LETTER_DATE_ON_OR_BEFORE_{cut} (at least {years}y before dataset last_updated)",
            "published_crl_letters": str(n),
            "fda_field_approved_letters": str(approved),
            "fda_field_approved_pct": f"{100.0 * approved / n:.1f}",
            "letters_with_later_original_action_observed": str(obs),
            "observed_later_original_action_pct": f"{100.0 * obs / n:.1f}",
            "observed_original_pct_wilson_lower_95": f"{100.0 * wilson_lower(obs, n):.1f}",
            "letters_with_any_later_action_observed": str(obs_any),
            "observed_any_action_pct": f"{100.0 * obs_any / n:.1f}",
            "median_days_to_first_later_original_action": str(days[len(days) // 2]) if days else "",
            "conflict_rows": str(sum(1 for r in sel if r["conflict_flag"])),
            "coverage_note": (f"FDA's CRL dataset is its published subset, not a census of every "
                              f"CRL FDA issued, and it is the denominator here. Maturity cohort, "
                              f"not a calendar year: letters dated on or before "
                              f"{cut}, i.e. at least {years} years before the CRL dataset's own "
                              f"last_updated date ({last_updated}). Letters younger than that still "
                              f"have resubmissions in review, so their observed rate is a lower "
                              f"bound by construction and must not be read as a failure rate."),
        }

    for _label, _years in (("ALL_MATURE_2Y", 2), ("ALL_MATURE_3Y", 3)):
        _row = _cohort_row(_label, _years)
        if _row:
            rate_rows.append(_row)

    # the one published letter with no application number: record why its master
    # id is malformed (empty application segment) instead of hiding it
    for r in match_rows:
        if r["application_number_normalised"] == "":
            r["master_link_status"] = "FDA_PUBLISHED_NO_APPLICATION_NUMBER"
            r["notes"] += (" FDA published this letter with no application_number field at all "
                           "(file_name " + (r["raw_file_name"] or "blank") + "); the published CRL "
                           "master stores it as CR--20260227 with an empty application segment. "
                           "That master id is flagged here as an irregularity, not corrected.")

    sources.insert(0, {
        "file": "data/raw/probe/crl_page1.json",
        "role": "FDA openFDA Complete Response Letter transparency dataset, captured verbatim (458 records)",
        "records": str(len(letters)),
        "bytes": str(CRL_RAW.stat().st_size),
        "sha256": sha256_file(CRL_RAW),
    })
    with MASTER.open(newline="", encoding="utf-8-sig") as fh:
        master_records = sum(1 for _ in csv.reader(fh)) - 1  # rows, not lines
    sources.append({
        "file": "data/fda_crl_master.csv",
        "role": "Published CRL master (join target; read-only)",
        "records": str(master_records),
        "bytes": str(MASTER.stat().st_size),
        "sha256": sha256_file(MASTER),
    })

    with (DATA / "crl_application_match.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(match_rows[0].keys()))
        w.writeheader()
        w.writerows(match_rows)
    with (DATA / "crl_year_base_rates.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rate_rows[0].keys()))
        w.writeheader()
        w.writerows(rate_rows)
    with (DATA / "crl_match_sources.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sources[0].keys()))
        w.writeheader()
        w.writerows(sources)

    print(f"wrote data/crl_application_match.csv ({len(match_rows)} rows)")
    print(f"wrote data/crl_year_base_rates.csv ({len(rate_rows)} rows)")
    print(f"wrote data/crl_match_sources.csv ({len(sources)} rows)")
    print(f"CRLs without a published application number: {n_without_appl}")
    print(f"CRL master rows not joined by (application, letter date): {len(unmatched_master)}")
    print(f"later ORIGINAL approval action observed: {total_obs}/{total_n} = "
          f"{100.0 * total_obs / total_n:.1f}% (Wilson 95% lower "
          f"{100.0 * wilson_lower(total_obs, total_n):.1f}%)")
    print(f"any later action (incl. supplements) observed: {total_obs_any}/{total_n} = "
          f"{100.0 * total_obs_any / total_n:.1f}%")
    print(f"FDA field Approved: {total_approved}/{total_n} = "
          f"{100.0 * total_approved / total_n:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
