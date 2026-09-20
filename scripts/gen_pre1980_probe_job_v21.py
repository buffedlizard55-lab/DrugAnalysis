#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v21 (2026-09-19): generate the three pre-1980 fetch jobs for years 1965-1976.

Deterministic generator — every item is derived from the committed openFDA
payloads, nothing is hand-typed, so the job files can be regenerated and
diffed at any time:

* fetch_jobs/pre1980_row_probes_1965_1976.json
    One live single-application openFDA query per NEW Type 1 / Type 1-4
    decision row of 1965-1976 (125 applications), plus one explicit
    gap-candidate probe (amikacin NDA050495, absent from every committed
    1965-1979 payload per the v20 first-appearance index).
* fetch_jobs/pre1980_year_populations_1965_1976.json
    One live population re-query per year (limit=1 -> meta.results.total),
    the documented workaround for openFDA's NOT_FOUND on count= over nested
    submission fields.
* fetch_jobs/openfda_orig_decisions_1939_1964.json
    The pre-1965 ORIG/AP payload block, so the ingredient first-appearance
    screen reaches back to the start of the Drugs@FDA database instead of
    stopping at 1965.

Usage:  python3 scripts/gen_pre1980_probe_job_v21.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOBS = ROOT / "fetch_jobs"
BLOCKS = ["openfda_orig_decisions_1965_1969", "openfda_orig_decisions_1970_1974",
          "openfda_orig_decisions_1975_1979"]
NEW_YEARS = tuple(range(1965, 1977))

PROBE_URL = ('https://api.fda.gov/drug/drugsfda.json'
             '?search=application_number:%22{appl}%22&limit=1000')
POP_URL = ('https://api.fda.gov/drug/drugsfda.json?search=submissions.submission_type:%22ORIG%22'
           '+AND+submissions.submission_status:%22AP%22+AND+submissions.submission_status_date:'
           '%5B{start}+TO+{end}%5D&limit=1')

# Explicit gap candidate carried forward from the v20 session: NCATS Inxight
# (NIH) records amikacin (Amikin) as NDA050495 "first approved in 1976", and
# the 1965-1979 first-appearance index shows AMIKACIN nowhere in the payloads.
# Probed live so the absence is a recorded observation, not an assumption.
GAP_CANDIDATES = [
    ("1976gap", "NDA050495", "1976", "amikacin (Amikin)"),
]


def load() -> dict[int, list]:
    out: dict[int, list] = {}
    for block in BLOCKS:
        d = DATA / "raw" / block
        for name in sorted(os.listdir(d)):
            if not name.startswith("decisions_"):
                continue
            year = int(name.split("_")[1].split(".")[0])
            out[year] = json.loads((d / name).read_text(encoding="utf-8"))["decisions"]
    return out


def main() -> int:
    alldec = load()
    missing = [y for y in NEW_YEARS if y not in alldec]
    if missing:
        raise SystemExit(f"missing committed payloads for {missing}; refusing to generate jobs")

    # ---- job 1: per-row live probes for every NEW Type 1/1-4 decision row ----
    items = []
    for year in NEW_YEARS:
        rows = [d for d in alldec[year]
                if (d.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4")]
        rows.sort(key=lambda d: (d["decision_date"], d["application_number"]))
        for d in rows:
            appl = d["application_number"]
            items.append({
                "id": f"probe_{year}_{appl}",
                "url": PROBE_URL.format(appl=appl),
                "out": f"probe_{appl}.json",
                "decision_date": d["decision_date"],
                "application_number": appl,
                "payload_class": d.get("submission_class_code") or "",
            })
    for tag, appl, year, label in GAP_CANDIDATES:
        items.append({
            "id": f"probe_{tag}_{appl}",
            "url": PROBE_URL.format(appl=appl),
            "out": f"probe_{appl}.json",
            "decision_date": "",
            "application_number": appl,
            "payload_class": f"GAP-CANDIDATE ({label})",
        })
    probes = [{
        "type": "generic",
        "id": "pre1980_row_probes_1965_1976",
        "skip_existing": True,
        "timeout": 90,
        "retries": 6,
        "sleep": 2.0,
        "items": items,
        "_why": ("v21 pre-1980 backfill: one live single-application openFDA capture per "
                 "NEW 1965-1976 Type 1 / Type 1-4 decision row (complete current record: all "
                 "products and submissions) so every new decision row carries a live primary "
                 "check, not just the committed dual-run payload. Same contract as the v20 "
                 "1977-1979 probe layer (170/170 MATCH). Payloads are written verbatim with "
                 "request URL + SHA-256 in the manifest; the builder cross-checks date, class, "
                 "priority and holder against the payload and aborts on any disagreement."),
    }]

    # ---- job 2: live year-population re-queries (limit=1 -> meta.total) ----
    pops = [{"id": f"population_{y}",
             "url": POP_URL.format(start=f"{y}0101", end=f"{y}1231"),
             "out": f"population_{y}.json",
             "decision_date": "", "application_number": ""} for y in NEW_YEARS]
    populations = [{
        "type": "generic",
        "id": "pre1980_year_populations_1965_1976",
        "skip_existing": True,
        "timeout": 90,
        "retries": 6,
        "sleep": 2.0,
        "items": pops,
        "_why": ("v21 pre-1980 backfill: live re-query of each 1965-1976 ORIG/AP year "
                 "population (meta.results.total via limit=1; count= over nested submission "
                 "fields returns NOT_FOUND). Confirms the committed payload populations are "
                 "still what openFDA reports, the same check the v19 session ran for "
                 "1977/1978/1979 (662/756/746)."),
    }]

    # ---- job 3: pre-1965 ORIG/AP payload block for the first-appearance screen ----
    pre1965 = [{
        "type": "openfda_decisions",
        "id": "orig_decisions",
        "endpoint": "https://api.fda.gov/drug/drugsfda.json",
        "search_template": ('submissions.submission_type:"ORIG" AND '
                            'submissions.submission_status:"AP" AND '
                            'submissions.submission_status_date:[{start} TO {end}]'),
        "years": list(range(1939, 1965)),
        "limit": 1000,
        "max_pages": 12,
        "sleep": 2.0,
        "out_template": "decisions_{year}.json",
        "skip_existing": True,
        "_why": ("v21 pre-1980 backfill: the 1965-1976 ingredient first-appearance screen can "
                 "only prove 'first in the committed payloads' while the payloads start in "
                 "1965. This block extends the same auditable ORIG+AP+date-in-year filter back "
                 "to 1939 (start of the Drugs@FDA database) so a molecule marketed before 1965 "
                 "can be detected instead of being reported as new. Same extraction "
                 "(scripts/openfda_decisions.py) and the same manifest discipline: raw payloads "
                 "not committed, every request URL + raw SHA-256 recorded. Drugs@FDA coverage "
                 "before 1965 is itself incomplete, so this widens the screen without making it "
                 "proof of first marketing - the builder says so explicitly."),
    }]

    for name, spec in (("pre1980_row_probes_1965_1976.json", probes),
                       ("pre1980_year_populations_1965_1976.json", populations),
                       ("openfda_orig_decisions_1939_1964.json", pre1965)):
        path = JOBS / name
        path.write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
        n = sum(len(s.get("items", s.get("years", []))) for s in spec)
        print(f"wrote {path.name}: {n} item(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
