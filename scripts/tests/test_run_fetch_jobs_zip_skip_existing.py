#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v29 (2026-09-22): end-to-end exercise of the runner's zip_extract path.

Why this test exists
--------------------
Run 33 of the Actions workflow (2026-09-21T23:34Z) re-downloaded the official
Drugs@FDA ZIP for every committed ``zip_extract`` job, overwrote the SHA-pinned
1938-1964 / 1965-1979 window extracts with a later publication of the same
table, and every SHA-gated builder step aborted. Two runner changes fix that:

1. ``zip_extract`` honours ``skip_existing`` (every other job kind already did);
2. a run that adds nothing but ``skipped-existing`` stubs leaves the job's
   ``manifest.json`` byte-identical instead of appending stubs and bumping
   ``generated_utc`` (which produced a data commit on every run, orphaned on
   the branch once the session PR had merged).

This test drives ``run_fetch_jobs.run_job`` itself - the real code path the
workflow uses - against a synthetic official-shaped ZIP served by a stubbed
``http_get``. Nothing touches the network and nothing touches the repository's
``data/`` tree: the job runs inside a temporary working directory.

Run::

    python3 scripts/tests/test_run_fetch_jobs_zip_skip_existing.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_fetch_jobs.py"

SUBMISSIONS = (
    "ApplNo\tSubmissionClassCodeID\tSubmissionType\tSubmissionNo\tSubmissionStatus\t"
    "SubmissionStatusDate\tSubmissionsPublicNotes\tReviewPriority\n"
    "000552\t19\tORIG\t1\tAP\t1939-02-09 00:00:00\t\tUNKNOWN\n"
    "060904\t\tORIG\t1\tAP\t1900-01-01 00:00:00\t\t\n"          # pre-statute placeholder date
    "009658\t\tORIG\t1\tAP\t\t\t\n"                              # undated
    "021014\t4\tSUPPL\t51\tAP\t\t\tSTANDARD\n"                   # undated
    "200001\t\tORIG\t1\tTA\t2015-03-03 00:00:00\t\tSTANDARD\n"   # tentative approval
    "200002\t3\tSUPPL\t2\t\t2016-04-04 00:00:00\t\t\n"           # empty status
    "000004\t19\tORIG\t1\tAP\t1969-07-16 00:00:00\t\tUNKNOWN\n"
    "000159\t\tORIG\t1\tAP\t1939-03-09 00:00:00\t\t\n"
)
APPLICATIONS = (
    "ApplNo\tApplType\tApplPublicNotes\tSponsorName\n"
    "000004\tNDA\t\tPHARMICS\n"
    "000159\tNDA\t\tLILLY\n"
    "000552\tNDA\t\tASPEN GLOBAL INC\n"
    "200001\tANDA\t\tEXAMPLE\n"
)


def build_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Submissions.txt", SUBMISSIONS)
        zf.writestr("Applications.txt", APPLICATIONS)
    return buf.getvalue()


def load_runner():
    spec = importlib.util.spec_from_file_location("run_fetch_jobs", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


JOB_ID = "zip_skip_existing_probe"
MEMBERS = [
    {"name": "Submissions.txt", "out": "Submissions_before_1939.txt",
     "filter": {"type": "date_year_before", "column": "SubmissionStatusDate", "before_year": 1939}},
    {"name": "Submissions.txt", "out": "Submissions_undated.txt",
     "filter": {"type": "date_unparseable", "column": "SubmissionStatusDate"}},
    {"name": "Submissions.txt", "out": "Submissions_status_counts.txt",
     "filter": {"type": "column_counts", "column": "SubmissionStatus"}},
    {"name": "Submissions.txt", "out": "Submissions_type_counts.txt",
     "filter": {"type": "column_counts", "column": "SubmissionType"}},
    {"name": "Submissions.txt", "out": "Submissions_applno_below_boundary.txt",
     "filter": {"type": "applno_in_list", "column": "ApplNo", "values": ["000004", "000159"]}},
    {"name": "Applications.txt", "out": "Applications_below_boundary.txt",
     "filter": {"type": "applno_numeric_below", "column": "ApplNo", "below": 552}},
]


def main() -> int:
    mod = load_runner()
    zbytes = build_zip()
    calls = {"n": 0}

    def fake_http_get(url, timeout=0, retries=0, sleep=0, headers=None):  # noqa: ARG001
        calls["n"] += 1
        return 200, zbytes

    mod.http_get = fake_http_get
    failures: list[str] = []

    def check(cond: bool, label: str) -> None:
        if not cond:
            failures.append(label)
        print(("ok   " if cond else "FAIL ") + label)

    with tempfile.TemporaryDirectory() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            os.makedirs("fetch_jobs", exist_ok=True)
            job_path = os.path.join("fetch_jobs", f"{JOB_ID}.json")
            spec = {"type": "zip_extract", "id": JOB_ID, "url": "https://example.invalid/drugsatfda.zip",
                    "skip_existing": True, "members": MEMBERS}
            with open(job_path, "w") as fh:
                json.dump([spec], fh)
            outdir = os.path.join("data", "raw", JOB_ID)

            # ---- run 1: nothing on disk -> must download and extract --------
            mod.run_job(job_path)
            check(calls["n"] == 1, "run 1 downloads the ZIP exactly once")
            for m in MEMBERS:
                check(os.path.getsize(os.path.join(outdir, m["out"])) > 0, f"run 1 wrote {m['out']}")
            man_path = os.path.join(outdir, "manifest.json")
            check(os.path.exists(man_path), "run 1 wrote manifest.json")
            man1 = Path(man_path).read_bytes()
            m1 = json.loads(man1)
            real = [e for e in m1["requests"] if e.get("out")]
            check(len(real) == len(MEMBERS), f"run 1 manifest has {len(real)} extract entries")
            for e in real:
                got = hashlib.sha256(Path(outdir, e["out"]).read_bytes()).hexdigest()
                check(got == e["out_sha256"], f"{e['out']}: out_sha256 re-hashes")
                kept = [ln for ln in Path(outdir, e["out"]).read_text().splitlines()[1:] if ln.strip()]
                check(len(kept) == e["rows_kept"], f"{e['out']}: rows_kept {e['rows_kept']} == {len(kept)} on disk")

            # ---- the selectors themselves, on the synthetic table -----------
            def rows(name):
                return [ln.split("\t") for ln in Path(outdir, name).read_text().splitlines()[1:] if ln.strip()]
            before = rows("Submissions_before_1939.txt")
            check([r[0] for r in before] == ["060904"], "date_year_before 1939 keeps only the 1900-01-01 row")
            undated = rows("Submissions_undated.txt")
            check(sorted(r[0] for r in undated) == ["009658", "021014"], "date_unparseable keeps exactly the 2 undated rows")
            st = {r[0]: int(r[1]) for r in rows("Submissions_status_counts.txt")}
            check(st == {"<EMPTY>": 1, "AP": 6, "TA": 1}, f"status census {st}")
            check(sum(st.values()) == 8, "status census sums to the member row count")
            ty = {r[0]: int(r[1]) for r in rows("Submissions_type_counts.txt")}
            check(ty == {"ORIG": 6, "SUPPL": 2} and sum(ty.values()) == 8, f"type census {ty}")
            low = rows("Submissions_applno_below_boundary.txt")
            check(sorted(r[0] for r in low) == ["000004", "000159"], "applno_in_list keeps 000004/000159 history")
            apps = rows("Applications_below_boundary.txt")
            check([r[0] for r in apps] == ["000004", "000159"], "applno_numeric_below 552 keeps exactly 000004/000159")

            # ---- run 2: everything present -> no download, manifest untouched
            mod.run_job(job_path)
            check(calls["n"] == 1, "run 2 does not download (skip_existing)")
            man2 = Path(man_path).read_bytes()
            check(man2 == man1, "run 2 leaves manifest.json byte-identical (no stub churn)")
            for m in MEMBERS:
                check(hashlib.sha256(Path(outdir, m["out"]).read_bytes()).hexdigest()
                      == next(e["out_sha256"] for e in real if e["out"] == m["out"]),
                      f"run 2 leaves {m['out']} untouched")

            # ---- run 3: one extract deleted -> full re-extract, manifest grows
            os.remove(os.path.join(outdir, "Submissions_undated.txt"))
            mod.run_job(job_path)
            check(calls["n"] == 2, "run 3 re-downloads when an extract is missing")
            check(os.path.getsize(os.path.join(outdir, "Submissions_undated.txt")) > 0, "run 3 restored the missing extract")
            m3 = json.loads(Path(man_path).read_text())
            check(len([e for e in m3["requests"] if e.get("out")]) == 2 * len(MEMBERS),
                  "run 3 appended a second set of real extract entries")

            # ---- control: without skip_existing the legacy re-download stays
            spec_legacy = dict(spec, id=JOB_ID + "_legacy")
            spec_legacy.pop("skip_existing")
            job_legacy = os.path.join("fetch_jobs", f"{JOB_ID}_legacy.json")
            with open(job_legacy, "w") as fh:
                json.dump([spec_legacy], fh)
            mod.run_job(job_legacy)
            mod.run_job(job_legacy)
            check(calls["n"] == 4, "a job without skip_existing still re-downloads on every run (unchanged legacy behaviour)")

            # ---- v29 guard: a FAILED paged openFDA fetch must not zero a payload
            # (before v29 a FAILED page 0 fell through to write 0 records + status 200)
            spec_years = {"type": "openfda_years", "id": "orig_ap", "endpoint": "https://api.fda.gov/drug/drugsfda.json",
                          "search_template": "x:[{start} TO {end}]", "years": [2000], "limit": 1000, "max_pages": 2,
                          "out_template": "{year}.json"}
            job_years = os.path.join("fetch_jobs", "openfda_years_probe.json")
            with open(job_years, "w") as fh:
                json.dump([spec_years], fh)
            ydir = os.path.join("data", "raw", "openfda_years_probe")
            os.makedirs(ydir, exist_ok=True)
            committed = b'{"meta":{"record_count":1},"results":[{"application_number":"NDA000552"}]}'
            with open(os.path.join(ydir, "2000.json"), "wb") as fh:
                fh.write(committed)

            def failing_http_get(url, timeout=0, retries=0, sleep=0, headers=None):  # noqa: ARG001
                raise RuntimeError("simulated outage")

            mod.http_get = failing_http_get
            mod.run_job(job_years)
            check(Path(ydir, "2000.json").read_bytes() == committed,
                  "openfda_years: a FAILED fetch leaves the committed payload byte-identical")
            ym = json.loads(Path(ydir, "manifest.json").read_text())
            check(all(e.get("status") != 200 for e in ym["requests"]),
                  "openfda_years: no status-200 entry is recorded for a failed fetch")
        finally:
            os.chdir(cwd)

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        for f in failures:
            print("  -", f)
        return 1
    print("OK: zip_extract skip_existing + no-op manifest behaviour verified end-to-end through run_job()")
    return 0


if __name__ == "__main__":
    sys.exit(main())
