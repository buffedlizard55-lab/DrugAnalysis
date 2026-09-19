#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v17 (2026-09-19): append dated, additive adjudication notes to the rows the
live captures touch.  No value is changed - only the ``notes`` field grows.

Rows annotated
--------------
master (fda_decisions_master.csv)
  D1030 Seldane   - openFDA NOT_FOUND; Drugs@FDA publishes an empty record.
  D1038 Protropin - openFDA NOT_FOUND (application and brand); Drugs@FDA empty
                    record; named as the 1985 +1 reconciliation candidate.
  D1040 Tambocor  - 1985 designation conflict: Drugs@FDA page re-read live and
                    the Compilation workbook parsed directly; the 1985 review
                    PDF exists and is Wayback-archived but returned HTTP 500 to
                    automation on three attempts across two days.
  D1042 Femstat   - openFDA carries the product record with NO submissions
                    array; that is why the ORIG/AP payload query cannot see it.
  D1047 Suprol    - openFDA NOT_FOUND; absent from the published dataset.

non-NME originals (fda_original_non_nme_decisions.csv)
  NDA022046       - lineage artifact still open; the v17 live captures confirm
                    that legacy 1983 originals are genuinely under-populated in
                    FDA's systems (NDA018615), without resolving this row.

Second, a systematic correction: 390 pre-1998 master rows carried the note
clause "no CDER NME year table was published for pre-1998 years".  v17 located
exactly such a table (FDA's Summary of NDA Approvals and Receipts, 1938-2022,
captured verbatim on 2026-09-19), so that clause is now false.  It is rewritten
to the historically accurate "at the time of entry no CDER NME year table had
been located" and each of those rows gains a one-sentence pointer to the
official series and to that year's crosswalk verdict.  Nothing else in the
note changes, and no other field changes.

Idempotent: a row already carrying the dated marker is left untouched, and
rows already carrying the year-series resolution sentence are left untouched.
The script hard-asserts the pre-existing text before every write and records
what it did in data/staging/v17_annotation_report.json.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MASTER = DATA / "fda_decisions_master.csv"
ORIG = DATA / "fda_original_non_nme_decisions.csv"
REPORT = DATA / "staging" / "v17_annotation_report.json"

MARKER = "v17 (2026-09-19)"

# The now-false clause (v17 located FDA's official NME year series) and its
# replacement.  The replacement keeps the row's provenance sentence intact and
# adds the resolution pointer, so the note reads as a dated correction chain.
STALE_CLAUSE_RE = re.compile(
    r"COMPILATION_ONLY: no CDER NME year table was published for pre-1998 years, "
    r"so FDA's official CDER Novel Drug Approvals Compilation "
    r"\((media/177921, approval-year (\d{4}) section)\) is the official spine for this row\."
)
RESOLUTION_SENTENCE = (
    "v17 (2026-09-19): FDA's official NME year series (1938-2022) was located and captured "
    "(data/fda_official_year_series.csv); this year's official-vs-project verdict is in "
    "data/fda_official_series_crosswalk.csv."
)


def stale_replacement(match: "re.Match[str]") -> str:
    return (
        "COMPILATION_ONLY: at the time of entry no CDER NME year table had been located, so "
        "FDA's official CDER Novel Drug Approvals Compilation "
        f"({match.group(1)}) is the official spine for this row. {RESOLUTION_SENTENCE}"
    )

REF = "data/raw/source_captures_2026_09_19/live_primary_captures_2026_09_19.json"

NOTES: dict[str, dict] = {
    "D1030": {
        "must_contain": "appl NDA018949",
        "text": (
            f"{MARKER} completeness-gap precision, live re-check: openFDA returns NOT_FOUND for NDA018949 "
            "(api.fda.gov) and FDA's own Drugs@FDA page for 018949 renders an empty application shell - the "
            "number resolves but FDA publishes no products and no approval history for it. The row therefore "
            "rests on the CDER NME Compilation alone, as stated; the earlier note's alternative wording "
            "('the product was later withdrawn/discontinued') is superseded - Seldane's withdrawal is not the "
            "reason, because discontinued products are normally retained in both systems. Evidence: "
            f"{REF} (V17-C03, V17-C04)."
        ),
    },
    "D1038": {
        "must_contain": "appl NDA019107",
        "text": (
            f"{MARKER} live re-check: openFDA returns NOT_FOUND for NDA019107 and for brand 'PROTROPIN', and "
            "FDA's Drugs@FDA page for 019107 renders an empty application shell. 1985 reconciliation: FDA's own "
            "historical tabulation counts 30 NMEs for 1985 while the Compilation carries 31 rows; the Compilation "
            "counts Type 1/1-4 NDAs plus new biologics by design, and Protropin (recombinant somatrem) is the "
            "only 1985 Compilation row that is a biological product - recorded as the leading candidate for that "
            "single-row difference and NOT asserted (see data/pre1985_nme_gap_analysis.csv and "
            "data/fda_official_series_crosswalk.csv). Baros Effervescent was independently re-verified as a "
            f"Type 1 NDA (NDA018509, 1985-08-07) and is ruled out. Evidence: {REF} (V17-C05, V17-C06, V17-C08)."
        ),
    },
    "D1040": {
        "must_contain": "TAMBOCOR DESIGNATION CHECK (2026-09-18, v16)",
        "text": (
            f"{MARKER} designation re-probe with live captures. (1) Drugs@FDA application-history page for "
            "NDA018830 fetched live: '10/31/1985 | ORIG-1 | Approval | Type 1 - New Molecular Entity | STANDARD', "
            "holder ALVOGEN, all four strengths Discontinued with Federal Register non-discontinuation markers. "
            "(2) The committed CDER NME Compilation workbook (media/177921, SHA-256 in data/raw/probe/manifest.json) "
            "was parsed directly: the Tambocor row reads Riker | NDA 18830 | 1985-10-31 | Review Designation "
            "'Priority' - the master's value traces to FDA's own cell, not a transcription error. (3) The "
            "Compilation's landing page (fetched live) states the dataset covers Type 1/1-4 NMEs plus new "
            "biologics and reflects each application at original approval. (4) The 1985 medical review that would "
            "settle the conflict is registered on FDA's page as "
            "https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf ; it returned HTTP "
            "500 to the automated fetcher on 2026-09-18 and again on 2026-09-19, and the Wayback Machine's five "
            "captures of that URL (30 Mar 2021 - 30 Mar 2025) also returned HTTP 500 through both raw replay "
            "endpoints. NET: both FDA values stay as published (review_pathway stays 'Priority' per "
            "COMPILATION_ONLY policy; Drugs@FDA's 'STANDARD' stays recorded here); nothing was harmonised and no "
            "value changed. The single remaining step is a human browser read of the review PDF - live URL or "
            f"Wayback capture - and CDER invites factual-error reports at CDER.NMENewBiologicApprovals@fda.hhs.gov. "
            f"Evidence: {REF} (V17-C01, V17-C09, V17-C10); data/fda_official_series_crosswalk.csv."
        ),
    },
    "D1042": {
        "must_contain": "appl NDA019215",
        "text": (
            f"{MARKER} completeness-gap precision, live re-check: openFDA DOES carry NDA019215 (sponsor 'ROCHE "
            "PALO', product FEMSTAT, butoconazole nitrate 2% cream, Discontinued) but publishes NO submissions "
            "array for it - that missing submission history is exactly why the ORIG/AP payload query cannot "
            "enumerate the application. This supersedes the earlier 'legacy licence FDA no longer indexes' "
            f"wording. Evidence: {REF} (V17-C07)."
        ),
    },
    "D1047": {
        "must_contain": "appl NDA018217",
        "text": (
            f"{MARKER} completeness-gap precision, live re-check: openFDA returns NOT_FOUND for NDA018217 - the "
            "application is absent from the published dataset entirely (no product record, not merely no "
            "submission history). The Compilation row remains the only FDA source for the 1985 approval. "
            f"Evidence: {REF} (V17-C07)."
        ),
    },
}

ORIG_NOTE = {
    "app": "NDA022046",
    "must_contain": "ADJUDICATION PROGRESS (checked 2026-09-18",
    "text": (
        f"{MARKER} adjudication re-check with live captures: no 1983 primary document for this application "
        "surfaced. Two live FDA captures are relevant context rather than resolution: (a) Drugs@FDA publishes "
        "NDA018615 - a genuine 1983 original - with BOTH the Submission Classification and the Review Priority "
        "cells blank, and openFDA reproduces the same blanks, so legacy 1983 originals really are "
        "under-populated in FDA's systems; (b) the openFDA API (queried live for furosemide) returns an ORIG-1 "
        "of 1983-11-30 with no class code, matching the project's NDA018413 row exactly. Neither finding dates "
        "NDA022046's original, so the FDA-recorded 1983-07-13 ORIG/AP continues to stand as an FDA-recorded "
        f"value and the lineage artifact remains flagged for a human with a 1983 source. Evidence: {REF} "
        "(V17-C02, V17-C11, V17-C12)."
    ),
}


def correct_stale_year_table_claim(master: list[dict]) -> dict:
    """Rewrite the pre-1998 note clause that v17 proved false, additively.

    Returns a small report dict.  Raises if any row still carries the stale
    clause afterwards, so a partial rewrite can never be written silently.
    """
    corrected: list[str] = []
    already: list[str] = []
    for row in master:
        notes = row.get("notes") or ""
        if RESOLUTION_SENTENCE in notes:
            already.append(row["decision_id"])
            continue
        new_notes, hits = STALE_CLAUSE_RE.subn(stale_replacement, notes)
        if hits:
            row["notes"] = new_notes
            corrected.append(row["decision_id"])
    leftovers = [r["decision_id"] for r in master if "no CDER NME year table was published" in (r.get("notes") or "")]
    if leftovers:
        raise SystemExit(
            "annotate_v17: stale year-table clause survived the rewrite on "
            f"{len(leftovers)} rows: {leftovers[:5]}"
        )
    return {"corrected": corrected, "already_resolved": already, "leftovers": leftovers}


def read_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    report = {"generated": "2026-09-19", "marker": MARKER, "applied": [], "skipped": []}

    master, master_fields = read_rows(MASTER)
    year_table_fix = correct_stale_year_table_claim(master)
    report["stale_year_table_clause"] = {
        "corrected_rows": len(year_table_fix["corrected"]),
        "already_resolved_rows": len(year_table_fix["already_resolved"]),
        "leftover_rows": len(year_table_fix["leftovers"]),
        "resolution_sentence": RESOLUTION_SENTENCE,
    }
    by_id = {r["decision_id"]: r for r in master}
    for did, spec in NOTES.items():
        row = by_id.get(did)
        if row is None:
            raise SystemExit(f"annotate_v17: master row {did} not found")
        if MARKER in (row["notes"] or ""):
            report["skipped"].append(did)
            continue
        if spec["must_contain"] not in (row["notes"] or ""):
            raise SystemExit(f"annotate_v17: {did} notes lost expected text {spec['must_contain']!r}")
        row["notes"] = (row["notes"] or "").rstrip() + " | " + spec["text"]
        report["applied"].append({"table": MASTER.name, "row": did})
    write_rows(MASTER, master, master_fields)

    orig, orig_fields = read_rows(ORIG)
    hit = [r for r in orig if (r["application_number"] or "").strip().replace(" ", "") == ORIG_NOTE["app"]]
    if len(hit) != 1:
        raise SystemExit(f"annotate_v17: expected exactly one {ORIG_NOTE['app']} row, found {len(hit)}")
    row = hit[0]
    if MARKER in (row["notes"] or ""):
        report["skipped"].append(ORIG_NOTE["app"])
    else:
        if ORIG_NOTE["must_contain"] not in (row["notes"] or ""):
            raise SystemExit(f"annotate_v17: {ORIG_NOTE['app']} notes lost expected text")
        row["notes"] = (row["notes"] or "").rstrip() + " | " + ORIG_NOTE["text"]
        report["applied"].append({"table": ORIG.name, "row": ORIG_NOTE["app"]})
    write_rows(ORIG, orig, orig_fields)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    print(f"stale year-table clause rewritten on {report['stale_year_table_clause']['corrected_rows']} rows "
          f"(already resolved: {report['stale_year_table_clause']['already_resolved_rows']})")
    print(f"applied: {report['applied']}")
    print(f"already present (skipped): {report['skipped']}")


if __name__ == "__main__":
    main()
