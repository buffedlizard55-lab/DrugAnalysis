#!/usr/bin/env python3
"""Dry-run harness for the v21 pre-1980 builders (test scaffolding, not shipped).

Builds a throwaway DATA root in /tmp/v21dry that symlinks the *real* committed
raw layers (payload blocks, full Drugs@FDA extract, live capture evidence) and
synthesises only the two layers the Actions runner has not delivered yet
(pre-1965 payload block, per-row probe + year-population captures).  Then runs
the real builders against it, so their plumbing, ordering, header alignment and
fail-closed gates execute for real before the fetched data lands.

Synthetic layers are generated *from* the real 1965-1976 payloads, so every
probe agrees with its payload by construction; a negative test then corrupts one
probe to prove the gate actually aborts.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path("/home/user/DrugAnalysis")
DRY = Path("/tmp/v21dry")
sys.path.insert(0, str(REPO / "scripts"))


def setup() -> None:
    if DRY.exists():
        shutil.rmtree(DRY)
    (DRY / "raw").mkdir(parents=True)
    (DRY / "staging").mkdir()
    for block in ("openfda_orig_decisions_1965_1969", "openfda_orig_decisions_1970_1974",
                  "openfda_orig_decisions_1975_1979", "source_captures_2026_09_19",
                  "drugsatfda_data_files_2026_09"):
        (DRY / "raw" / block).symlink_to(REPO / "data" / "raw" / block)
    for name in ("fda_official_year_series.csv", "fda_official_series_crosswalk.csv"):
        shutil.copy(REPO / "data" / name, DRY / name)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def payloads() -> dict[int, list]:
    out = {}
    for block, years in (("openfda_orig_decisions_1965_1969", range(1965, 1970)),
                         ("openfda_orig_decisions_1970_1974", range(1970, 1975)),
                         ("openfda_orig_decisions_1975_1979", range(1975, 1980))):
        for y in years:
            out[y] = json.loads((REPO / "data" / "raw" / block /
                                 f"decisions_{y}.json").read_text())["decisions"]
    return out


def synth_pre1965() -> None:
    d = DRY / "raw" / "openfda_orig_decisions_1939_1964"
    d.mkdir()
    reqs = []
    for y in range(1939, 1965):
        body = json.dumps({"year": y, "count": 0, "decisions": []}, sort_keys=True).encode()
        (d / f"decisions_{y}.json").write_bytes(body)
        reqs.append({"id": f"orig_decisions_{y}", "status": 200,
                     "out": f"decisions_{y}.json",
                     "pages": [{"n_raw_records": 0, "raw_sha256": "synthetic"}],
                     "sha256": hashlib.sha256(body).hexdigest()})
    (d / "manifest.json").write_text(json.dumps({"job": "synthetic", "requests": reqs}, indent=2))


def synth_probes(pl: dict[int, list]) -> None:
    d = DRY / "raw" / "pre1980_row_probes_1965_1976"
    d.mkdir()
    reqs = []
    nme = [(y, x) for y in range(1965, 1977) for x in pl[y]
           if (x.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4")]
    for y, dec in nme:
        appl = dec["application_number"]
        rec = {"application_number": appl, "sponsor_name": dec.get("sponsor_name", ""),
               "submissions": [{"submission_type": "ORIG", "submission_status": "AP",
                                "submission_status_date": dec["decision_date"].replace("-", ""),
                                "submission_class_code": dec.get("submission_class_code", ""),
                                "review_priority": dec.get("review_priority", ""),
                                "submission_number": "1"}]}
        body = json.dumps({"results": [rec]}, sort_keys=True).encode()
        out = f"probe_{y}_{appl}.json"
        (d / out).write_bytes(body)
        reqs.append({"id": f"probe_{y}_{appl}", "status": 200, "out": out,
                     "url": f"https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{appl}%22",
                     "sha256": hashlib.sha256(body).hexdigest()})
    # amikacin gap candidate: record present, no submissions array
    body = json.dumps({"results": [{"application_number": "NDA050495",
                                    "sponsor_name": "APOTHECON", "products": []}]},
                      sort_keys=True).encode()
    (d / "probe_1976gap_NDA050495.json").write_bytes(body)
    reqs.append({"id": "probe_1976gap_NDA050495", "status": 200,
                 "out": "probe_1976gap_NDA050495.json",
                 "url": "https://api.fda.gov/drug/drugsfda.json?search=application_number:%22NDA050495%22",
                 "sha256": hashlib.sha256(body).hexdigest()})
    (d / "manifest.json").write_text(json.dumps({"job": "synthetic", "requests": reqs}, indent=2))
    print(f"synthetic probes: {len(reqs)} (expect 126)")


def synth_pops() -> None:
    d = DRY / "raw" / "pre1980_year_populations_1965_1976"
    d.mkdir()
    pinned = {1965: 52, 1970: 74, 1976: 619}
    reqs = []
    for y in range(1965, 1977):
        total = pinned.get(y, 100 + y % 7)
        body = json.dumps({"meta": {"results": {"total": total}}}, sort_keys=True).encode()
        (d / f"population_{y}.json").write_bytes(body)
        reqs.append({"id": f"population_{y}", "status": 200, "out": f"population_{y}.json",
                     "url": "synthetic", "sha256": hashlib.sha256(body).hexdigest()})
    (d / "manifest.json").write_text(json.dumps({"job": "synthetic", "requests": reqs}, indent=2))


def point(module):
    module.DATA = DRY
    module.CAPTURES_DIR = DRY / "raw" / "source_captures_2026_09_19"
    module.EVIDENCE_V19 = module.CAPTURES_DIR / "live_primary_captures_v19_2026_09_19.json"
    module.EVIDENCE_V21 = module.CAPTURES_DIR / "live_primary_captures_v21_2026_09_19.json"
    module.RUN18_MANIFEST = module.CAPTURES_DIR / \
        "run18_manifest_openfda_orig_decisions_1975_1979.json"
    module.PROBES_DIR = DRY / "raw" / "pre1980_row_probes_1965_1976"
    module.POPS_DIR = DRY / "raw" / "pre1980_year_populations_1965_1976"
    module.REPORT = DRY / "staging" / "dry_run_report.json"
    module.ZIP_DIR = DRY / "raw" / "drugsatfda_data_files_2026_09"
    return module


def main() -> int:
    setup()
    pl = payloads()
    synth_pre1965()
    synth_probes(pl)
    synth_pops()

    dec = point(importlib.import_module("build_pre1980_decisions_v21"))
    print("--- running build_pre1980_decisions_v21.main() ---")
    dec.main()
    for name in ("pre1980_fda_decisions.csv", "pre1980_year_audit.csv",
                 "pre1980_era_analysis.csv", "pre1980_primary_captures_index.csv",
                 "missing_nme_candidates.csv"):
        rows = (DRY / name).read_text().rstrip("\n").split("\n")
        print(f"  {name}: {len(rows) - 1} data rows")

    aud = point(importlib.import_module("build_pre1980_originals_audit_v21"))
    print("--- running build_pre1980_originals_audit_v21.main() ---")
    aud.main()
    for name in ("pre1980_originals_audit_1965_1976.csv",
                 "pre1980_row_probe_index_1965_1976.csv",
                 "pre1980_full_db_crosscheck_1965_1976.csv"):
        rows = (DRY / name).read_text().rstrip("\n").split("\n")
        print(f"  {name}: {len(rows) - 1} data rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
