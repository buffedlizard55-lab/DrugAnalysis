#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v28 (2026-09-21): deterministic generator for the pre-1939 boundary-census
fetch job.

Why this job exists
-------------------
Every pre-1965 fact in this repository so far rests on *year-filtered windows*
of the official Drugs@FDA data files:

* ``data/raw/drugsatfda_data_files_1938_1964/Submissions_1938_1964.txt``
  (1,215 of 193,752 rows kept - filter ``date_year_in`` 1938..1964)
* ``data/raw/drugsatfda_data_files_2026_09/Submissions_1965_1979.txt``
  (10,753 rows - filter ``date_year_in`` 1965..1979)

A year filter can only prove something about the rows it kept. Three questions
therefore remain open on the committed evidence alone, and this job closes all
three against the COMPLETE official table:

1. **Is there any submission action dated before 1939 at all?**
   ``date_year_before 1939`` over all 193,752 rows. Expected: 0 rows.
2. **Could a row be hiding behind an empty/unparseable status date?**
   ``date_unparseable`` counts exactly the rows a year filter can never see.
3. **Does the official Submissions table publish non-approval decisions?**
   ``column_counts`` on ``SubmissionStatus`` / ``SubmissionType`` over the
   whole table. The two committed windows are 100% ``AP``; v27's site copy
   claimed ``RE``/``W`` rows also lived there. This census settles it with a
   count that the verifier can re-check (``sum(count) == rows_total``).

Plus the low-application-number census: every application in the official
``Applications.txt`` numbered below 000552 (the first recorded 1939 approval),
with the COMPLETE submission history of each - so the census of "what exists
below the boundary" is exhaustive rather than inferred from two windows.

Values are copied verbatim; the only transformation is the recorded row
selector, exactly as the existing ``zip_extract`` jobs do.

Usage::

    python3 scripts/gen_pre1939_census_job_v28.py   # rewrites the job file
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOB_FILE = ROOT / "fetch_jobs" / "drugsatfda_pre1939_census_v28.json"

# Same official surface the committed 1938-1964 and 1965-1979 windows came
# from: the FDA Drugs@FDA data-files ZIP.
OFFICIAL_ZIP = "https://www.fda.gov/media/89850/download?attachment"

# Applications numbered below the first recorded 1939 approval (NDA000552).
# Derived from the committed unfiltered official map
# data/raw/drugsatfda_data_files_2026_09/Applications_all_types.txt (29,336
# applications): exactly 000004 (NDA, PHARMICS) and 000159 (NDA, LILLY).
# The builder re-derives this set and aborts if it ever differs, so this list
# can never silently drift from the source of record.
LOW_APPLNOS = ["000004", "000159"]
BOUNDARY_APPLNO = 552


def build() -> list[dict]:
    return [{
        "type": "zip_extract",
        "id": "drugsatfda_pre1939_census_v28",
        "url": OFFICIAL_ZIP,
        "timeout": 900,
        "retries": 4,
        "max_member_out_bytes": 45_000_000,
        "members": [
            {"name": "Submissions.txt",
             "out": "Submissions_before_1939.txt",
             "filter": {"type": "date_year_before",
                        "column": "SubmissionStatusDate",
                        "before_year": 1939}},
            {"name": "Submissions.txt",
             "out": "Submissions_undated.txt",
             "filter": {"type": "date_unparseable",
                        "column": "SubmissionStatusDate"}},
            {"name": "Submissions.txt",
             "out": "Submissions_status_counts.txt",
             "filter": {"type": "column_counts",
                        "column": "SubmissionStatus"}},
            {"name": "Submissions.txt",
             "out": "Submissions_type_counts.txt",
             "filter": {"type": "column_counts",
                        "column": "SubmissionType"}},
            {"name": "Submissions.txt",
             "out": "Submissions_applno_below_boundary.txt",
             "filter": {"type": "applno_in_list",
                        "column": "ApplNo",
                        "values": LOW_APPLNOS}},
            {"name": "Applications.txt",
             "out": "Applications_below_boundary.txt",
             "filter": {"type": "applno_numeric_below",
                        "column": "ApplNo",
                        "below": BOUNDARY_APPLNO}},
        ],
        "_why": (
            "v28 pre-1939 boundary census. Closes three questions the committed "
            "year-filtered windows cannot answer: (1) any submission action dated "
            "before 1939 anywhere in the 193,752-row official Submissions table "
            "(expect 0); (2) how many rows carry an empty/unparseable status date "
            "and are therefore invisible to every year filter used in this "
            "repository; (3) the complete SubmissionStatus / SubmissionType census "
            "of the official table, which settles whether Drugs@FDA publishes "
            "non-approval decisions (RE/W) at all - both committed windows are "
            "100% AP, so the v27 claim that rejections and withdrawals 'live' in "
            "the 1938-1964 register is not supported by the data and is corrected "
            "in v28. Also captures the complete submission history of every "
            "official application numbered below NDA000552 (000004, 000159) so the "
            "below-boundary census is exhaustive. Values verbatim; only the "
            "recorded row selectors transform the extract."
        ),
    }]


def main() -> None:
    spec = build()
    JOB_FILE.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {JOB_FILE.relative_to(ROOT)}: {len(spec[0]['members'])} member extracts "
          f"from {OFFICIAL_ZIP}")


if __name__ == "__main__":
    main()
