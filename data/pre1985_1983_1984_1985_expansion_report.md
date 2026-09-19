# Pre-1985 Expansion Report — Focus Years 1983, 1984, 1985
Generated: 2026-09-19T04:21:16.010246Z
Validator: PASS 0 errors (v17 baseline 1747 warnings)

## Official FDA Series (History Office)
Source: https://www.fda.gov/about-fda/histories-fda-regulated-products/summary-nda-approvals-receipts-1938-present
Captured: data/raw/source_captures_2026_09_19/fda_history_nda_nme_approvals_1938_2022.json (SHA-256 in manifest)

| Year | NDAs Approved (official) | NMEs Approved (official) | Project NME-comparable | Delta |
|------|--------------------------|--------------------------|------------------------|-------|
| 1983 | 94 | 14 | 13 | -1 |
| 1984 | 142 | 22 | 19 | -3 |
| 1985 | 100 | 30 | 31 | +1 |

## 1983 Deep Dive
- **Payload**: 70 ORIG/AP decisions (decisions_1983.json, SHA-256 582ba513f771…)
- **Type 1/1-4**: 13 rows
- **Blank class**: 25 rows — all legacy duplicative (9 ingredients)
- **Project**: 14 rows = 13 Type1/1-4 + 1 furosemide boundary (NDA018413, molecule first approved 1968-03-20 TYPE 3 per V17-C11)
- **Verification**: Every project row has Drugs@FDA link + openFDA query URL (replayable)
- **Gap**: -1 NME, sits in payload-invisible applications (class proven for 1985). Do NOT infer from blank-class fields.
- **Next source**: CDER 'Offices of Drug Evaluation: Statistical Report' typescript 1989 pp.152-199 (FDA History Office, Rockville MD) — the source FDA's own history page cites for 1951-1989 NME series. Request via FDA Historian john.swann@fda.hhs.gov or contemporaneous FDA annual report.

## 1984 Deep Dive
- **Payload**: 109 ORIG/AP decisions
- **Type 1/1-4**: 19
- **Blank class**: 17 — 9 ingredients: ALLOPURINOL, BETAMETHASONE DIPROPIONATE, FENTANYL CITRATE, FLUOCINONIDE, FUROSEMIDE, INDOMETHACIN, METHYLDOPA, METRONIDAZOLE, TOLAZAMIDE
- **Project**: 20 rows = 19 Type1/1-4 + 1 boundary
- **Gap**: -3 NMEs, payload-invisible (same class as 1985 gap)
- **Next source**: Same 1989 typescript

## 1985 Deep Dive
- **Payload**: 82 ORIG/AP decisions (82) — 27 Type1/1-4 + 1 UNKNOWN (NITRO-DUR NDA020145) + 54 non-Type1
- **Project master**: 31 rows (Compilation spine)
- **Payload-invisible**: 4 apps documented via live captures V17-C03..C07:
  - NDA018949 Seldane (terfenadine): openFDA NOT_FOUND; Drugs@FDA empty shell
  - NDA019107 Protropin (somatrem): openFDA NOT_FOUND (app and brand); Drugs@FDA empty shell
  - NDA019215 Femstat (butoconazole nitrate): openFDA product record NO submissions array — reason ORIG/AP query cannot see it
  - NDA018217 Suprol (suprofen): openFDA NOT_FOUND; absent entirely
- **Reconciliation**: Compilation 31 vs official NME 30 (+1). Leading candidate Protropin biologic (recombinant hGH) — product nature, NOT workbook field (workbook NDA/BLA column types all 31 as NDA, no comment). Baros Effervescent NDA018509 verified Type1 STANDARD 1985-08-07 (V17-C08) rules it out as +1. Status: candidate, not determination.
- **Tambocor NDA018830 (D1040)**: Conflict between FDA systems:
  - Drugs@FDA: STANDARD (third FDA-family STANDARD corroboration via live capture V17-C01, ORIG-1 10/31/1985 Type1 STANDARD)
  - Compilation workbook: Priority (verbatim cell 'Priority' per V17-C10 parse of 31 rows 18P/13S, dataset-wide 1108 NDA/279 BLA)
  - Review PDF: https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf — 5 Wayback captures 2021-2025 exist (V17-C09) but live and raw replay return HTTP 500 to automation. Human browser read required to settle.
  - Project effect: Both values retained, conflict flagged in notes (6 rows carry v17 dated notes: D1030,D1038,D1040,D1042,D1047 and non-NME NDA022046 1983-07-13 lineage artifact).

## No Hallucinations Guarantee
- Every decision_date, application_number, class_code, priority copied verbatim from committed payloads
- No ticker, company, historical applicant asserted from current holder (disclaimer per pre1985_fda_decisions.csv header)
- Blank beats guessed: blank-class rows flagged as legacy duplicative, not guessed as NME
- All counts pinned against official FDA tabulation; abort on edit
- SHA-256 manifests for every payload request

## 1000 New Entries — Verification Path
- Pre-1980 fetch jobs created: 1975-1979, 1970-1974, 1965-1969 (15 years × ~70 avg = ~1050 ORIG/AP decisions)
- ClinicalTrials.gov: additional windows 2024-2025 (4 half-years) + 2028-2029 (4 half-years) = 8 × ~1000 avg = ~8000 studies raw, 4000+ after dedup, feeding 1000+ new registry rows beyond current 2000 cap
- Stock Yahoo: remaining price events (~906) queued via fetch_jobs (when runner succeeds)
- All via declarative fetch_jobs/*.json with manifest SHA-256, verbatim payloads, no synthesis

## Remaining Work & Limitations
- Missing NMEs for 1980 (-3), 1981 (-4), 1982 (-3), 1983 (-1), 1984 (-3) require 1989 CDER statistical typescript pp.152-199 (FDA History Office Files, Rockville MD) or contemporaneous FDA annual reports — no official application-level NME list exists for those years in public data
- 1988 Compilation 20 vs official 21 (-1), 2013 27 vs 29 (-2) — only years Compilation short of official; missing apps not identified in either public dataset; same typescript required
- Tambocor PDF human read is single remaining step to settle designation
- Pre-1980 block: fetch jobs committed this session, need Actions runner execution then expansion of pre1985_fda_decisions.csv and fda_original_non_nme_decisions.csv with same verification method
- NDA022046 lineage artifact (1983-07-13) requires approval letter or Federal Register notice quoting lineage
- 141 core-table listing-class disagreements (ADR vs direct GSK,NVS,RHHBY,AZN; delisted vs current SHPG,MDCO,CELG) need per-ticker EDGAR venue verification (sandbox page-fetch only; Actions returns 403 per manifest)
- CT.gov registry 2000 cap — pagination beyond requires expansion of clinical_trials_phase3_registry.csv builder to consume new windows (4212 raw already fetched, 2000 cap is builder limit, not API limit)
