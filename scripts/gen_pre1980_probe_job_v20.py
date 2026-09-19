#!/usr/bin/env python3
"""Generate fetch_jobs/pre1980_row_probes_1977_1979.json.

One openFDA single-application probe per original approval enumerated in the
committed 1977-1979 payloads (42 + 66 + 62 = 170 rows).  Each item re-issues
`api.fda.gov/drug/drugsfda.json?search=application_number:"<appl>"&limit=1000`,
which returns the *complete current record* (all products and submissions) for
exactly that application.  These are the per-row live-verification layer for
data/pre1980_originals_audit_1977_1979.csv.

Deterministic: identical payloads produce an identical job file.  Existing
files are never overwritten (move the old job aside explicitly if the
universe changes).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "fetch_jobs", "pre1980_row_probes_1977_1979.json")

years = (1977, 1978, 1979)
apps: list[tuple[int, str, str, str, str]] = []
for year in years:
    path = os.path.join(ROOT, "data", "raw", "openfda_orig_decisions_1975_1979",
                        f"decisions_{year}.json")
    obj = json.load(open(path))
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    for d in obj["decisions"]:
        apps.append((year, d["application_number"], d["decision_date"],
                     d.get("submission_class_code") or "", sha))

apps.sort()
if len(apps) != 170:
    sys.exit(f"expected 170 payload rows, found {len(apps)}; refusing to emit job")

items = []
for year, appl, ddate, cls, sha in apps:
    items.append({
        "id": f"probe_{year}_{appl}",
        "url": ('https://api.fda.gov/drug/drugsfda.json?search=application_number:%22'
                f"{appl}%22&limit=1000"),
        "out": f"probe_{appl}.json",
        "decision_date": ddate,
        "application_number": appl,
        "payload_class": cls,
        "payload_sha": sha[:16],
    })

spec = [{
    "type": "generic",
    "id": "pre1980_row_probes",
    "skip_existing": True,
    "timeout": 90,
    "retries": 4,
    "sleep": 0.35,
    "items": items,
    "_why": ("Per-row live single-application probes for every 1977-1979 ORIG/AP "
             "payload row (170). Each response is the complete current "
             "Drugs@FDA record for that application, committed verbatim with "
             "request URL + SHA-256 in the manifest, so every row of "
             "data/pre1980_originals_audit_1977_1979.csv carries its own live "
             "official-source capture."),
}]

if os.path.exists(OUT):
    print(f"{OUT} already exists; leaving unchanged")
else:
    with open(OUT, "w") as fh:
        json.dump(spec, fh, indent=1)
    print(f"wrote {OUT} with {len(items)} probes")
