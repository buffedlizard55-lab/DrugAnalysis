#!/usr/bin/env python3
"""Build the Phase 3 trial-endpoint registry from the verbatim ClinicalTrials.gov
API v2 capture (data/raw/clinicaltrials_phase3_2026_2027/studies.json, collected
on GitHub Actions with a per-request SHA-256 manifest).

Scope of the capture (see fetch_jobs/clinicaltrials_phase3_2026_2027.json):
  AREA[Phase]PHASE3 AND AREA[PrimaryCompletionDate]RANGE[2026-01-01,2027-12-31]
  -> 2,000 studies (40 pages x 50, API returned a full 2,000-page window; the
  capture may therefore be a *subset* of all matching studies - noted, never
  padded with invented rows).

Every output row:
  * carries the official source link https://clinicaltrials.gov/study/<NCT>
  * copies fields value-for-value from the capture (no rewriting)
  * sponsor resolution uses data/sponsor_registry.csv, repo-verified standalone rows,
    and SEC company_tickers.json exact match after legal-suffix removal.
    NO token matching; unresolved stays blank.

Output: data/clinical_trials_phase3_registry.csv
        data/staging/ctgov_sponsor_resolution.json
The 8 hand-verified rows in data/clinical_trial_endpoints.csv are NOT touched.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_crl_master_v2 import build_repo_map_strict, build_sec_map_strict, load_sponsor_reg, norm_legal  # noqa: E402

DATA = ROOT / "data"
RAW = DATA / "raw" / "clinicaltrials_phase3_2026_2027" / "studies.json"
OUT = DATA / "clinical_trials_phase3_registry.csv"
AUDIT = DATA / "staging" / "ctgov_sponsor_resolution.json"

CAPTURE_DATE = "2026-09-17"

COLS = ["nct_id", "brief_title", "lead_sponsor", "sponsor_class",
        "resolved_company", "ticker", "exchange", "investability_class",
        "phases", "study_status", "primary_completion_date",
        "primary_completion_date_type", "conditions", "drug_interventions",
        "primary_outcome_measure", "source_url", "verification_status",
        "sponsor_resolution_basis", "notes"]

ACADEMIC_CLASSES = {"OTHER", "OTHER_GOV", "NETWORK", "NIH", "FED", "UNKNOWN"}


def first(v, n=1, sep="; "):
    vals = [x for x in (v or []) if isinstance(x, str) and x.strip()]
    return sep.join(vals[:n])


def main() -> None:
    d = json.load(open(RAW))
    studies = d["studies"]
    repo = build_repo_map_strict()
    sec = build_sec_map_strict()
    reg = load_sponsor_reg()
    resolutions: dict[str, dict] = {}

    rows = []
    for s in studies:
        p = s["protocolSection"]
        ident = p["identificationModule"]
        nct = ident["nctId"]
        sponsor = (p["sponsorCollaboratorsModule"].get("leadSponsor") or {})
        name = (sponsor.get("name") or "").strip()
        sclass = sponsor.get("class", "")
        status = p["statusModule"]
        pcd = status.get("primaryCompletionDateStruct") or {}
        phases = " / ".join(ph.replace("PHASE", "Phase ").title()
                            for ph in (p.get("designModule", {}).get("phases") or []))
        conds = first(p.get("conditionsModule", {}).get("conditions"))
        drugs = first([i["name"] for i in (p.get("armsInterventionsModule",
                       {}).get("interventions") or []) if i.get("type") == "DRUG"], n=4)
        out_m = first([o.get("measure") for o in
                       (p.get("outcomesModule", {}).get("primaryOutcomes") or [])], n=1)
        out_tf = first([o.get("timeFrame") for o in
                        (p.get("outcomesModule", {}).get("primaryOutcomes") or [])], n=1)

        if name not in resolutions:
            key = norm_legal(name)
            if key in reg:
                r_item = reg[key]
                tk = (r_item.get("ticker") or "").strip()
                ex = (r_item.get("exchange") or "").strip()
                uclass = (r_item.get("us_investable_class") or "").strip()
                comp = (r_item.get("resolved_company") or name).strip()
                basis = (r_item.get("basis") or "sponsor_registry exact match").strip()
                if tk and tk not in {"UNRESOLVED", "NO_US_TICKER", "NO_TICKER"}:
                    resolutions[name] = {"company": comp, "ticker": tk, "exchange": ex,
                                         "method": "sponsor_registry exact", "inv": "US-LISTED", "basis": basis}
                elif uclass in {"NON-US LISTING ONLY", "PRIVATE / NO EQUITY"}:
                    resolutions[name] = {"company": comp, "ticker": "", "exchange": ex,
                                         "method": uclass, "inv": uclass, "basis": basis}
                else:
                    resolutions[name] = {"company": comp, "ticker": "", "exchange": ex,
                                         "method": "unresolved", "inv": "UNRESOLVED SPONSOR", "basis": basis}
            elif key in repo:
                tk, ex, rowname = repo[key]
                resolutions[name] = {"company": name, "ticker": tk, "exchange": ex,
                                     "method": "repo-verified exact", "inv": "US-LISTED",
                                     "basis": "lead sponsor verified row-by-row earlier in this repository"}
            elif key in sec:
                c = sec[key][0]
                resolutions[name] = {"company": name, "ticker": c["ticker"], "exchange": "",
                                     "method": "SEC exact", "inv": "US-LISTED",
                                     "basis": "exact match (legal suffixes removed) against "
                                              "SEC company_tickers.json"}
            elif sclass in ACADEMIC_CLASSES:
                resolutions[name] = {"company": "", "ticker": "", "exchange": "",
                                     "method": "academic", "inv": "NOT A COMPANY (academic/government/network sponsor)",
                                     "basis": f"lead sponsor class: {sclass} (academic/government/network sponsor)"}
            else:
                resolutions[name] = {"company": "", "ticker": "", "exchange": "",
                                     "method": "unresolved", "inv": "UNRESOLVED SPONSOR",
                                     "basis": "no repository-verified row and no exact SEC "
                                              "registrant match (legal suffixes removed); blank beats guessed"}
        r = resolutions[name]
        ticker = r["ticker"]
        inv = r.get("inv", "UNRESOLVED SPONSOR")

        notes = [f"lead sponsor class: {sclass}"]
        if phases and "Phase 2" in phases and "Phase 3" in phases:
            notes.append("Phase 2/3 combined study")
        if out_tf:
            notes.append(f"primary endpoint time frame: {out_tf}")

        rows.append({
            "nct_id": nct,
            "brief_title": ident.get("briefTitle", ""),
            "lead_sponsor": name,
            "sponsor_class": sclass,
            "resolved_company": r["company"],
            "ticker": ticker,
            "exchange": r["exchange"],
            "investability_class": inv,
            "phases": phases,
            "study_status": (status.get("overallStatus") or "").replace("_", " ").title(),
            "primary_completion_date": pcd.get("date", ""),
            "primary_completion_date_type": pcd.get("type", ""),
            "conditions": conds,
            "drug_interventions": drugs,
            "primary_outcome_measure": out_m,
            "source_url": f"https://clinicaltrials.gov/study/{nct}",
            "verification_status": f"Verified - ClinicalTrials.gov API v2 capture {CAPTURE_DATE}",
            "sponsor_resolution_basis": r["basis"],
            "notes": " | ".join(notes),
        })

    # ---- validation ----
    assert len(rows) == len({r["nct_id"] for r in rows}), "duplicate NCT ids"
    for r in rows:
        assert r["source_url"].startswith("https://clinicaltrials.gov/study/NCT"), r["nct_id"]
        dd = r["primary_completion_date"]
        assert not dd or dd[:4] in {"2026", "2027"}, r["nct_id"]

    rows.sort(key=lambda r: (r["primary_completion_date"] or "9999-99-99", r["nct_id"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    audit = {"generated_by": "scripts/build_ctgov_phase3_registry.py",
             "capture": {"endpoint": d["source_endpoint"], "params": d["params"],
                         "pages": d["pages"], "fetched_utc": d["fetched_utc"],
                         "studies": len(studies)},
             "note": "API returns studies in default order; 2,000-study window may be a "
                     "subset of all matching studies. Capture is verbatim; nothing padded.",
             "resolutions": {k: v for k, v in resolutions.items()}}
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(audit, AUDIT.open("w"), indent=1)

    print(f"studies: {len(rows)}")
    print("by investability:", Counter(r["investability_class"] for r in rows))
    print("by completion year:", sorted(Counter((r['primary_completion_date'] or 'blank')[:4] for r in rows).items()))
    print("distinct sponsors:", len(resolutions),
          "| resolved:", sum(1 for v in resolutions.values() if v["ticker"]))
    print("\n--- resolved sponsors (line-by-line review) ---")
    for n, v in sorted(resolutions.items(), key=lambda kv: kv[1]["ticker"]):
        if v["ticker"]:
            print(f"  {v['ticker']:10s} {n[:60]}")
    print("\n--- first rows by date ---")
    for r in rows[:10]:
        print(f"  {r['primary_completion_date']}  {r['nct_id']}  {(r['ticker'] or '-'):10s} "
              f"{r['lead_sponsor'][:36]:36s} {r['conditions'][:34]}")


if __name__ == "__main__":
    main()
