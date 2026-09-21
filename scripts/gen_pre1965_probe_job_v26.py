#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v26 (2026-09-21): generate the per-row live probe fetch job for all 535
1939-1964 applications (one complete openFDA record per application number,
exactly the fetch_jobs/pre1980_row_probes_1965_1976.json discipline).

The GitHub Actions runner executes fetch_jobs/*.json on push
(workflow .github/workflows/arena-data-fetch.yml), commits the raw responses
to data/raw/pre1965_row_probes_1939_1964/ with per-file SHA-256 in the
manifest, and the v26 builder (--join-probes) then compares live
date/class/priority/holder with the payload for every row.

The job file is regenerated deterministically from the committed payloads;
re-running this script with unchanged payloads produces a byte-identical
file, so it is safe to regenerate before every push.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK = ROOT / "data" / "raw" / "openfda_orig_decisions_1939_1964"
OUT = ROOT / "fetch_jobs" / "pre1965_row_probes_1939_1964.json"


def main() -> int:
    items = []
    for path in sorted(glob.glob(str(BLOCK / "decisions_*.json"))):
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        year = obj["year"]
        for d in obj["decisions"]:
            appl = d["application_number"]
            items.append({
                "id": f"probe_{year}_{appl}",
                "url": f"https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{appl}%22&limit=1000",
                "out": f"probe_{appl}.json",
                "decision_date": d["decision_date"],
                "application_number": appl,
                "payload_class": (d.get("submission_class_code") or "").strip(),
            })
    items.sort(key=lambda i: (i["decision_date"], i["application_number"]))
    job = [{
        "type": "generic",
        "id": "pre1965_row_probes_1939_1964",
        "skip_existing": True,
        "timeout": 90,
        "retries": 6,
        "sleep": 2.0,
        "items": items,
        "_why": "v26 pre-1965 backward extension (2026-09-21): one complete live openFDA record per 1939-1964 ORIG/AP application (535), the same per-row probe discipline as pre1980_row_probes_1965_1976 and pre1980_row_probes_1977_1979. Raw responses are committed verbatim with SHA-256 in the manifest; scripts/build_pre1965_decisions_v26.py --join-probes compares live ORIG-AP date/class/priority/holder against the committed year payload for every row (field disagreement aborts; empty live records are flagged ABSENT_LIVE, never auto-corrected).",
    }]
    OUT.write_text(json.dumps(job, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} with {len(items)} probe items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
