# Remaining work for the next session (written 2026-09-17 v8)

This file is the hand-off for future development. The sandbox that edits the repo has **no general outbound network** (only a page-fetch tool that can reach api.fda.gov, web.archive.org and finance.yahoo.com one page at a time). Bulk external fetches must go through GitHub Actions (`fetch_jobs/*.json` → `scripts/run_fetch_jobs.py` → `data/raw/<job>/` + SHA-256 manifest). Nothing may be typed from memory: every row needs an official/primary source link, and blank beats guessed.

## What this session shipped (v8)

- **Full-era master** — `data/fda_decisions_master.csv` 1,018 → **1,427 rows (1985–2026)**: +390 pre-1998 rows (D1029–D1418) from FDA's official CDER Novel Drug Approvals Compilation (all flagged `COMPILATION_ONLY`, no year table exists pre-1998) + 19 CBER biologics 2000–2003 (D1419–D1437) under the documented year-count decision (option a; flags `COMPILATION_ONLY_CBER`; year pins 29/29/23/27 = year-table + flagged splits).
- **Official-Compilation reconciliation** — `data/compilation_reconciliation.csv` + `data/year_audit_summary.csv` (42-year grid): **1,386/1,387 official rows matched**; sole exclusion Emend IV NDA 022023 (2008), which FDA's own 2008 table excluded — documented, surfaced, never silently dropped. Reverse: 41 master-only rows (40 × 2026 + flagged Contrave).
- **Non-NME originals** extended to 1985: 1,995 → **2,798 rows** (+803 pre-2000 from the verified runner captures).
- **Cross-check at 1,427**: MATCH 890 / DATE_ONLY 464 / VIA_GENERIC 20 / NOT_IN_OPENFDA 41 / ±1–3d 5 / MISMATCH 6 / NO_APPL 1.
- **T1GAP 21 → 11, all adjudicated** (the 15 CBER rows are now in the master).
- **Pass-2 fixes**: reconciliation XLSX column-offset bug rewritten against the real 27-column schema; NOT_ON_FDA_NME_TABLE detector now provably isolates D634 (validator + reconciliation + site coverage all share the corrected rule — the old rule excluded Ofev instead of Contrave by coincidence).
- Derived tables regenerated (751 company scores, 1,885 core rows with 145 priced, 100 orig scorecards); validator PASS with 42-year assertions; new site tab 📑 Compilation Audit; fetch job `fetch_jobs/stock_yahoo_events_1985_1998.json` (181 events) queued for the runner.

## Highest-value next steps

1. **Run the pre-1998 price fetch on Actions** (`fetch_jobs/stock_yahoo_events_1985_1998.json`), then `python3 scripts/build_stock_snapshots_from_events.py` and commit the captured payloads + manifest. Delisted symbols (ORPH, VTRS-on-Mylan-era dates, ALC-on-1990s dates, etc.) will fail — that failure is data: blank cells + recorded HTTP status, **never retried with successor tickers**. Also still open from v7: 76 failed Yahoo chart requests in `data/raw/stock_yahoo_events_1998_2026/` stay failed.
2. **`scripts/classify_listing.py` fixed-point problem** (v7 irregularity #1, untouched): re-running it on the committed master flips 154 legacy rows. Either make it honour explicit builder classes for blank/“formerly …” exchanges, or normalise the 50 legacy blank-exchange rows to "formerly NYSE:XXX, delisted YYYY" strings (delisting-year research list from v7 preserved: WYE 2009, PHA 2003, SGP 2009, MLNM 2008, FRX 2014, IMCL 2008, DNA 2009, SHPG 2019, SEPR 2014, GENZ 2011, AMLN 2012, CELG 2019, CEPH 2011, XNPT 2016, AFFY 2013, ARIA 2017, HGSI 2012, DSCO→WINT; non-US: MKGAF→ETR:MRK, SOBI→STO:SOBI, REC→BIT:REC, TH→TSX:TH). Each needs a primary citation.
3. **Accelerated-approval labelling gap** — 71 Compilation rows with “Accelerated Approval = Yes” are plain “Approval” in the master (the 1998/1999 and pre-1998 imports use “Approval (Accelerated)” inconsistently). A notes-only labelling pass from `data/raw/probe/fda_nme_compilation_1985_2025.xlsx` columns 18/20 would make the pathway column consistent; year counts must not change.
4. **2014 dead Wayback URL** — all 41+1 rows of 2014 cite the dead `…/20190207172014/…/ucm429249.htm`; `…/20150123034253/…/ucm429247.htm` works. Bulk rewrite of source_url_1 with a script.
5. **Pre-1998 sponsor resolution deep-dive** — ~900 of the 2,798 orig rows remain UNRESOLVED (REVIEW), most of them pre-2000 legacy sponsors. Exact-match-only aliases against SEC `company_tickers.json` and contemporaneous 10-K/20-F evidence; add registry keys, never token-match. Known collisions from v7: "SUN PHARM" (3 keys), "NYCOMED" (no key), "CUBIST" (2 keys).
6. **Un-adjudicated T1GAP sponsor strings** — 11 rows stay in the gap file deliberately; three still say `UNRESOLVED (REVIEW)` sponsor/company (T1GAP-NDA019841 Curium; T1GAP-BLA103786 Retavase EKR Therap; T1GAP-NDA211617 Esperion; T1GAP-NDA212643 UCSF). They are annotated “do not re-investigate the product”, but the sponsor column could still be cleaned with primary sources.
7. **Price coverage beyond the pre-1998 job** — 145/1,885 core rows priced. After item 1 lands: CRL events (86 resolved) and the 2026 NME rows without snapshots.
8. **Carry-overs from v5/v6/v7**: 314 flagged CRL sponsors + 609 unresolved CT.gov sponsors (exact SEC-title matching only); page the CT.gov Phase 3 registry beyond the first 2,000; PDUFA calendar — 16 secondary-aggregation rows still need primary press-release/8-K captures; Purple Book 351(k) labelling for the non-NME file; verbatim indication text for orig rows; Hoechst/Glaxo-Wellcome 1998 decision-date ADR symbols (SEC 20-F 1997–1999).

## Do not

- Invent novel approvals to pad counts — the master equals FDA's official NME Compilation 1985–2025 + the pinned 2026 year table; 1,000 extra novel approvals do not exist.
- Re-run `scripts/classify_listing.py` on the committed master without fixing item 2 first (it flips 154 legacy rows).
- Re-introduce token/substring ticker matching (7 documented false positives in v5). Blank beats guessed.
- Merge T1GAP rows into the master — every remaining row is adjudicated with a reason (legacy status artifacts, second licences, same-moiety second products). Emend IV in particular is a *documented exclusion*, not a missed row.
- Retry failed Yahoo chart requests with successor tickers (recorded repo law: the failure IS the data).
- Link Blenrep 2020 (D306) to BLA 761440 — that is the 2025 re-approval, a different decision.
- Treat Type 5 manufacturer changes or medical gases as clinical-trial conversions.
- Fill missing prices, dates, indications, or tickers; silently overwrite a source conflict; overwrite the 58 hand-verified CRL rows or the 8 hand-verified trial endpoints.
- Claim the 2,000-study CT.gov capture is exhaustive — it is the API's first 2,000 matches.
