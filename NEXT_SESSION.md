# Remaining work for the next session (written 2026-09-18 v12)

This file is the hand-off for future development. The sandbox that edits the repo has **no general outbound network** (only a page-fetch tool that can reach api.fda.gov, www.fda.gov, www.sec.gov, query1.finance.yahoo.com and web.archive.org one page at a time). Bulk external fetches must go through GitHub Actions (`fetch_jobs/*.json` → `scripts/run_fetch_jobs.py` → `data/raw/<job>/` + SHA-256 manifest). Nothing may be typed from memory: every row needs an official/primary source link, and blank beats guessed.

## What this session shipped (v12)

- **Pre-1985 FDA Decisions Dataset (`data/pre1985_fda_decisions.csv`)**:
  - Expanded analysis to decisions before 1985 (starting with 1983, 1984, and 1985), verified line-by-line against primary Drugs@FDA applications and openFDA submission records.
  - 18 landmark decisions tracked with exact application numbers, approval dates, chemical classification (Type 1 NME, Type 2, Type 3, Type 4, Type 5), review priorities, indications, corporate successor lineages, and primary official source links.
  - Key approvals include Sandimmune (cyclosporine, 1983, organ transplantation breakthrough), Zantac (ranitidine HCl, 1983, first $1B drug), Cefizox (ceftizoxime, 1983), Lithostat (acetohydroxamic acid, 1983, first Orphan Drug Act approval), Netromycin (netilmicin, 1983), Nicorette (nicotine polacrilex, 1984, first nicotine replacement therapy), Sectral (acebutolol, 1984), Trexan (naltrexone, 1984, opioid dependence blockade under Orphan Drug Act), Rocephin (ceftriaxone, 1984), Augmentin (amoxicillin + clavulanate, 1984, first beta-lactamase inhibitor combo), and Trental (pentoxifylline, 1984).
- **Pre-1985 Regulatory Era Analysis (`data/pre1985_era_analysis.csv`)**:
  - Comparative statutory and regulatory milestone analysis across 1983, 1984, and 1985.
  - Documents the enactment of the Orphan Drug Act of 1983 (P.L. 97-414), the Drug Price Competition and Patent Term Restoration Act of 1984 (Hatch-Waxman Act, P.L. 98-417), and CDER's record 1985 novel drug approval cohort (31 NMEs).
- **Comprehensive Company Clinical Trial Scorecard (`data/company_clinical_trial_scorecard.csv`)**:
  - Maintained and verified 421 company scorecards mapping pipeline progression, phase advancement (Phase 1 → Phase 2 → Phase 3 → Filing), paused/clinical holds, active Phase 3 trials in ClinicalTrials.gov (2026-2027 completion window), total FDA approvals, CRLs, clinical progression rate %, overall FDA conversion rate %, composite score (0-100), and success grades (A–E).
  - Every row links to official ClinicalTrials.gov NCT registries and FDA approval applications.
- **Decision Engine & GitHub Pages UI Enhancement**:
  - New dedicated **📜 Pre-1985 Era** tab in `index.html` and `assets/app.js` with responsive DataTables, year filters, search, and direct links to Drugs@FDA.
  - Decision Engine Bayesian calculator now integrates company clinical trial phase progression rates, advancing vs paused programs, and Phase 3 trial counts alongside FDA review pathways and advisory committee outcomes.
- **Validation Suite Extension (`scripts/validate_data.py`)**:
  - Added strict validation (§6b) for pre-1985 decisions and era tables. Validates schema, ID format, dates (YYYY-MM-DD), official source links, and verification statuses.
  - All QA checks pass with 0 errors.

## Limitations and Work for Future Sessions

1. **Pre-1985 Coverage Expansion Beyond Landmark Approvals**:
   - The current pre-1985 dataset covers 18 landmark approvals across 1983, 1984, and 1985. FDA historical records report 14 total NMEs approved in 1983 and 22 in 1984.
   - Next sessions can systematically add the remaining 6 NMEs from 1983 and 12 NMEs from 1984 from Drugs@FDA records, and continue expanding backwards year-by-year into 1982, 1981, and 1980.
2. **Pre-2000 Sponsor Worklist Completion via Offline EDGAR Queue**:
   - 12 rows remain `VENUE-VERIFIED (ticker pending)` (Warner-Lambert ×4, Pharmacia & Upjohn ×5, Roberts ×2, Carter-Wallace ×1).
   - Once the offline queue in `fetch_jobs/edgar_pre2000_symbols_2026_09.json` runs in GitHub Actions, extract the Item 5 sentences verbatim and resolve them cleanly via `scripts/resolve_pre2000_sponsors_v12.py`.
3. **Core Analysis Class Disagreements (Audited Baseline = 141)**:
   - Adjudicate the 141 legacy core-vs-master ticker-internally-inconsistent listing classes (ADR vs direct: GSK, NVS, RHHBY, AZN, SNY; delisted vs current: SHPG, MDCO, CELG, ALXN).
4. **Clinical Trials Phase 3 Registry Expansion**:
   - Currently indexes the first 2,000 studies from ClinicalTrials.gov (2026-2027 primary completion window). Can page deeper into the ClinicalTrials.gov API to capture earlier and subsequent completion windows.

---


**The page-fetch tool was DOWN at the end of the v11 session** — after Warner-Lambert's FY1997 10-K cover (chunk 0 of 43) came back cleanly, every later `fetch_page` call returned `SignatureDoesNotMatch` from the tool's internal file proxy (other chunks, another EDGAR submission, and a non-EDGAR URL alike; a 75-second wait did not help). `web_search` still worked, so it is specific to the fetch path. **First action next session: retry one cheap `fetch_page` before planning anything that needs primary text.** If it is still down, only local work is possible.

**EDGAR fetch discipline learned the hard way (v11, ~25 wasted fetches):** pass only the canonical URL `https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}.txt`, one call at a time. Parallel calls fail, rewritten/proxied URLs fail with `SignatureDoesNotMatch`, and a valid chunk occasionally returns HTTP 500 — just retry it. The directory `index.json` for 1990s submissions returns empty filenames, so the full-submission `.txt` is the only usable form. EDGAR full-text search covers 2001+ only, so pre-2001 evidence must come from the company-browse filing list + direct `.txt` fetches.

## What this session shipped (v11)

- **8 pre-2000 worklist rows went from VENUE-VERIFIED / CITATION-LOCATED to RESOLVED (venue+ticker per period 10-K)** — every symbol read verbatim out of the registrant's own Item 5 or cover 12(b) table, fetched live from `www.sec.gov`:
  - Advanced Magnetics **AMEX:AVM** (D1345 Feridex, D1363 GastroMARK) — FY1996 10-K405 acc 0000950135-96-005384
  - Neurex **NASDAQ NMS:NXCO** (D1396 Corlopam) — FY1997 10-K acc 0000884065-98-000003
  - Cytogen **NASDAQ NMS:CYTO** (D1357 ProstaScint, D1381 Quadramet) — FY1996 10-K acc 0000950109-97-002390
  - Immunomedics **NASDAQ NMS:IMMU** (D1338 CEA-Scan) — FY1996 10-K acc 0000950109-96-006351
  - Gensia Sicor **NASDAQ NMS:GNSA** (D1394 Genesa) — FY1997 10-K acc 0001012870-98-000824
  - IVAX Corporation **AMEX:IVX** (D1353 Elmiron; Baker Norton is IVAX's own brand-name arm per Item 1 of the same filing) — FY1996 10-K405 acc 0000950170-97-000359
- **First EDGAR-pinned delisting year on the worklist:** Neurex → `formerly NASDAQ NMS:NXCO, delisted 1998 (Elan Corporation plc merger)`, from the DEF 14A filed 1998-07-02 (acc 0000950130-98-003434: "Agreement and Plan of Merger, dated as of April 29, 1998", 0.51 Elan ADS per Neurex share, vote 1998-08-11) plus Form 15-15D filed 1998-08-14. The same proxy states Elan's ADSs traded on **The New York Stock Exchange** — usable primary evidence for the Athena/Zanaflex attribution case (D1362).
- **Three remembered symbols falsified by primary text:** Advanced Magnetics "ANM"/"AinM" → **AVM/AMEX**; Neurex "NXRX" → **NXCO**; this repo's own note "Nasdaq:IVX era" → **AMEX:IVX** (American Stock Exchange per both the cover 12(b) table and Item 5). Cytogen/Immunomedics/Gensia guesses were confirmed. Superseded wording is preserved (`v10_note_superseded` in the evidence file; dated corrections in the row notes) — corrected, never erased.
- **Carter-Wallace D1359 (Astelin): venue verified, symbol NOT located.** FY1997 10-K405 (acc 0000890163-97-000093) cover 12(b) says "Common Stock Par value $1.00 per share / New York Stock Exchange" (plus a second, 12(g)-only "Class B Common Stock"), but Item 5 reads "Information required by this item is presented on pages 1 and 7 of the 1997 Annual Report to Stockholders and is herein expressly incorporated by reference" — the symbol is not in the 10-K document. Status moved CITATION-LOCATED → VENUE-VERIFIED (ticker pending); "NYSE:CAR" remains an unverified guess written to nothing.
- **Roberts (D1347 ProAmatine, D1379 Agrylin): 424-series route closed, deregistration year pinned.** Both EDGAR 424-series filings are supplements to the Prospectus dated November 7, 1996 (Reg. No. 333-13729) and name no symbol (the 1996-12-20 one, acc 0000950130-96-004873, is a rights-plan supplement). File numbers: 000-19173 (12(g)) and 001-10432 (12(b), first appearing on 1999 filings incl. Form 8-A12B/A 1999-07-27) — i.e. the 12(b) registration post-dates both decision dates, so NASDAQ NMS stands. **Form 15-12G filed 1999-12-22** pins deregistration to 1999.
- **Pharmacia & Upjohn (D1330, D1332, D1373, D1382, D1390): lineage date pinned, hunt bounded.** EX-13 "PHARMACIA & UPJOHN Financial review" of the FY1997 10-K405 (acc 0000950124-98-001758) states "All data prior to the **November 2, 1995** merger date have been combined as if the companies had been merged during the prior periods" — corroborating the recorded Nov-1995 Upjohn lineage on all five rows. The 38-chunk submission is now mapped: main 10-K document in chunks 0–14 (Item 5 is in there), EX-12/EX-13 from mid-chunk-15.
- **Second wave (partial — the fetch tool then failed): Warner-Lambert's FY1997 10-K cover read in full** (acc 0000950117-98-000602, chunk 0 of 43). Venue upgraded from plain "NYSE" to the three exchanges its 12(b) table names (New York + Chicago + Pacific, plus a second 12(b) class of Rights to Purchase Series A Junior Participating Preferred Stock); Item 1 corroborates the Parke-Davis chain in the registrant's own words and lists CEREBYX and OMNICEF. **No symbol written** — Part II is incorporated by reference to the 1997 Annual Report to Shareholders, so Item 5 is in that exhibit, not the 10-K body. 4 master rows + 4 index rows updated with the finding and the revised search plan.
- **New validator §7 (core table ↔ master)**: shape, coverage, and a ratchet pinning the 145 rows whose core class contradicts their own master class — the mechanism behind the three deliberate ticker blanks is now measured, mutation-tested (IMMU on D1338 → 146 → hard error), and the core analysis table is validated for the first time.
- **Three deliberate `ticker`-column blanks** (hazards, not doubts) — symbols are in the site-visible `exchange` field for all 8 rows; the `ticker` column was filled for 5 (AVM ×2, NXCO, GNSA, IVX) and left blank for D1338/D1357/D1381, reasons in `NO_TICKER_FILL` in `scripts/resolve_pre2000_sponsors_v11.py` and in each row note. See "Do not" below.
- **`classify_listing.py` AMEX gap fixed** (`US_VENUES` now includes `"AMEX"`; without it `classify("formerly AMEX:AVM, …")` returned NON-US LISTING ONLY for a US venue). Proven behaviour-preserving: the re-run reports "0 newly derived, 1427 committed classes kept, 0 disagreements noted" and leaves the master byte-identical, so the fixed-point property is intact.
- **Derived tables regenerated** after proving both builders byte-reproducible on the unmodified master: core table gained 5 tickers (`No public ticker` → `Not yet matched to price snapshot`); company scores updated 7 rows in place with **0 rows added or removed** (no company fragmentation). **0 new price snapshots** — Item 5 quarterly high/low brackets are staged as evidence text only.
- **Validator extended and mutation-tested**: pins the 9 verified venue:symbol strings, the 5 ticker fills *and* the 3 documented blanks, Neurex's `delisted 1998`, the dated v11 note on each of the 9 rows, and the 9 RESOLVED index statuses. PASS, 0 errors, 1,612 warnings (identical to the v10 baseline).

**Worklist position (67 rows, unchanged):** 9 RESOLVED · 12 VENUE-VERIFIED (ticker pending) · 1 CITATION-LOCATED (Block Drug) · 3 ATTRIBUTION-CASE · 22 NO-EQUITY (documented) · 18 REVIEW (foreign listing) · 2 REVIEW (unresolved).

## Unblock route: queue the remaining EDGAR fetches on GitHub Actions (spec ready to paste)

The sandbox page-fetch tool is what blocked the second half of v11. The repo already has a sanctioned route around it: `.github/workflows/arena-data-fetch.yml` runs `scripts/run_fetch_jobs.py` **on GitHub's runner**, which has real network, and commits the payloads **verbatim** to `data/raw/<job-id>/` with a `manifest.json` recording the exact request URL, HTTP status, byte count and SHA-256. Failed fetches are recorded as failures — nothing is retried into existence.

**Do this on the NEXT branch, after PR #25 is merged** (deliberately not on the PR branch: the workflow triggers on any change to `fetch_jobs/**`, and #25 is meant to stay a verified-data-only diff).

1. Create `fetch_jobs/edgar_pre2000_symbols_2026_09.json` with exactly the JSON below (validated: 18 specs, unique ids, all URLs on `www.sec.gov`).
2. Commit and push it to the new arena branch. The path filter (`fetch_jobs/**`) fires the workflow; the v10 run of the same workflow took ~17 minutes. It has `permissions: contents: write` and commits `data/raw/` back to the branch, so pull before doing anything else. It has also rolled the local object store back to the base commit twice while the pushed branch stayed intact, so re-`git fetch origin <branch>` and reset to the remote tip before committing anything — never assume local history survived between turns.
3. Read the payloads **locally** — no fetch tool needed — and extract each Item 5 / Annual Report sentence verbatim, then write `scripts/resolve_pre2000_sponsors_v12.py` in the same shape as the v11 one and re-pin whatever validator constants move.

Size check before pushing: `data/raw/` is already 130 MB and tracked (not gitignored), so six 1990s full submissions (~2-4 MB each) are consistent with the existing convention. `"sleep": 1.0` is set on every spec to stay well inside SEC's 10-requests-per-second limit; the runner's `USER_AGENT` already carries the contact address SEC asks for.

```json
[
  {
    "type": "url",
    "id": "pnu_fy1997_10k405",
    "url": "https://www.sec.gov/Archives/edgar/data/949573/0000950124-98-001758.txt",
    "out": "pnu_fy1997_10k405.txt",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "5 rows (D1330 D1332 D1373 D1382 D1390). 38 chunks; main 10-K document = chunks 0-14 and Item 5 is inside that range (EX-13 starts mid-chunk-15). NYSE venue already proven from the 12(b) cover."
  },
  {
    "type": "url",
    "id": "warner_lambert_fy1997_10k",
    "url": "https://www.sec.gov/Archives/edgar/data/104669/0000950117-98-000602.txt",
    "out": "warner_lambert_fy1997_10k.txt",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "4 rows (D1342 D1366 D1376 D1409). 43 chunks; cover already read. Part II is incorporated by reference to the 1997 Annual Report to Shareholders, so open the Annual Report EXHIBIT inside this submission (9 public documents) - not the 10-K body."
  },
  {
    "type": "url",
    "id": "carter_wallace_fy1997_10k405",
    "url": "https://www.sec.gov/Archives/edgar/data/18000/0000890163-97-000093.txt",
    "out": "carter_wallace_fy1997_10k405.txt",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "1 row (D1359). 33 chunks; NYSE venue proven from 12(b). Item 5 -> 'pages 1 and 7 of the 1997 Annual Report to Stockholders'. Chunks ~15-30 unexplored. Two classes: only Common Stock was exchange-listed."
  },
  {
    "type": "url",
    "id": "block_drug_fy1997_10k",
    "url": "https://www.sec.gov/Archives/edgar/data/12654/0000012654-97-000004.txt",
    "out": "block_drug_fy1997_10k.txt",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "1 row (D1365) - the last CITATION-LOCATED row on the worklist. FY1997 10-K (FYE 1997-03-31) filed 1997-06-30; the 1996-12-17 Aphthasol decision falls inside that fiscal year."
  },
  {
    "type": "url",
    "id": "roberts_defm14a_1999",
    "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-99-006712.txt",
    "out": "roberts_defm14a_1999.txt",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "2 rows (D1347 D1379). Merger proxy filed 1999-11-23 (665 KB); its market-price section should name the symbol the 424-series supplements never stated."
  },
  {
    "type": "url",
    "id": "roberts_fy1996_10k",
    "url": "https://www.sec.gov/Archives/edgar/data/853022/0000950130-97-001485.txt",
    "out": "roberts_fy1996_10k.txt",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "2 rows. The FY1996 10-K v10 cited for the NASDAQ NMS venue - re-fetch so the Item 5 wording and any symbol can be quoted verbatim from the payload instead of from the v10 note."
  },
  {
    "type": "url",
    "id": "amag_form25_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000792977&type=25&dateb=&owner=include&count=40",
    "out": "amag_form25_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "AVM (D1345 D1363). Need the Form 25 for the AMEX line, NOT the 2020 Nasdaq/AMAG one. EDGAR records the rename to AMAG Pharmaceuticals 2007-07-05, so expect the AMEX-line filing around then."
  },
  {
    "type": "url",
    "id": "amag_form15_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000792977&type=15&dateb=&owner=include&count=40",
    "out": "amag_form15_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "AVM (D1345 D1363) - companion 15-series list on the same CIK lineage."
  },
  {
    "type": "url",
    "id": "cytogen_form15_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000725058&type=15&dateb=&owner=include&count=40",
    "out": "cytogen_form15_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "CYTO (D1357 D1381). 10-K series ends FY1998 (filed 1999-02-22) but filings continue to 2008, so the end-of-listing year needs its own citation."
  },
  {
    "type": "url",
    "id": "cytogen_form25_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000725058&type=25&dateb=&owner=include&count=40",
    "out": "cytogen_form25_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "CYTO (D1357 D1381) - exchange-side removal-from-listing."
  },
  {
    "type": "url",
    "id": "immunomedics_form25_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000722830&type=25&dateb=&owner=include&count=40",
    "out": "immunomedics_form25_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "IMMU (D1338). Recorded lineage: acquired by Gilead 2020."
  },
  {
    "type": "url",
    "id": "immunomedics_form15_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000722830&type=15&dateb=&owner=include&count=40",
    "out": "immunomedics_form15_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "IMMU (D1338) - companion 15-series list."
  },
  {
    "type": "url",
    "id": "gensia_sicor_form15_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000807873&type=15&dateb=&owner=include&count=40",
    "out": "gensia_sicor_form15_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "GNSA (D1394). Recorded lineage: renamed Sicor Inc. 1999, TEVA acquired 2003/2004 - the renaming and any symbol change need citing before a year is written."
  },
  {
    "type": "url",
    "id": "gensia_sicor_form25_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000807873&type=25&dateb=&owner=include&count=40",
    "out": "gensia_sicor_form25_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "GNSA (D1394) - exchange-side removal-from-listing."
  },
  {
    "type": "url",
    "id": "ivax_form15_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000772197&type=15&dateb=&owner=include&count=40",
    "out": "ivax_form15_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "IVX (D1353). 10-K series ends with FY2004 filed 2005-03-16 (acc 0001193125-04-040619); recorded lineage Teva 2006, so a 2006 Form 15/25 should exist."
  },
  {
    "type": "url",
    "id": "ivax_form25_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000772197&type=25&dateb=&owner=include&count=40",
    "out": "ivax_form25_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "IVX (D1353) - exchange-side removal-from-listing (AMEX line)."
  },
  {
    "type": "url",
    "id": "roberts_10k_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000853022&type=10-K&dateb=&owner=include&count=40",
    "out": "roberts_10k_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "Locate the FY1997/FY1998 10-K accessions so their Item 5 can be fetched in a follow-up job."
  },
  {
    "type": "url",
    "id": "carter_wallace_10k_list",
    "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000018000&type=10-K&dateb=&owner=include&count=40",
    "out": "carter_wallace_10k_list.html",
    "timeout": 180,
    "retries": 4,
    "skip_existing": true,
    "sleep": 1.0,
    "_why": "Locate the FY1998/FY1999/FY2000 10-K accessions as a fallback route to the symbol."
  }
]
```

The `_why` keys are documentation for the next reader — `job_url` ignores unknown keys, so they are harmless, but delete them if you prefer a minimal spec.

## Highest-value next steps

1. **Finish the pre-2000 sponsor worklist — cheapest first.** Every route below needs primary text, so **start by queuing the fetch job in the section above** — it retrieves all of these submissions and filing lists in one runner pass, after which the extraction is local work.
   - *Delisting years for the 5 symbols that still lack one* (AVM, CYTO, IMMU, GNSA, IVX): each turns its row into the full `formerly <VENUE>:<TICKER>, delisted <YYYY>` form. Look for the terminal Form 15 / 15-12B / 15-15D **or the exchange's Form 25** on the company's EDGAR filing list — IVAX's 10-K series ends with FY2004 filed 2005-03-16 (acc 0001193125-04-040619), so a 2006 Form 15/25 should exist for the Teva acquisition; Cytogen's ends with the FY1998 10-K filed 1999-02-22 (acc 0000725058-99-000007) but filings continue to 2008.
     - **AVM trap, already recorded as an UNVERIFIED POINTER in the evidence file:** a web search surfaced an 8-K dated 2020-11-16 on the same CIK 792977 lineage (`.../792977/000110465920125941/tm2036059d2_8k.htm`) in which NASDAQ files a Form 25 after the Covis merger. That ends the **AMAG-on-Nasdaq** line — NOT the **AVM-on-AMEX** line rows D1345/D1363 are about. EDGAR records this registrant's name change to AMAG Pharmaceuticals on 2007-07-05, so the citation actually needed is a Form 25 for the AMEX line or the 2007 name/symbol-change 8-K. Do not write "delisted 2020" onto those rows.
     - **Search cannot substitute for EDGAR's filing lists.** A search for Cytogen's delisting returned Cyteir Therapeutics (Nasdaq: CYT), an unrelated company — a live instance of the token/substring failure mode this repo bans. Terminal-filing lookups must be by CIK on `browse-edgar`.
   - *Carter-Wallace symbol (D1359)*: pages 1 and 7 of the 1997 Annual Report to Stockholders, which is an exhibit later in acc 0000890163-97-000093 (33 chunks; chunks ~15–30 unexplored), or Item 5 of the FY1998/FY1999/FY2000 10-K, or the DEF 14A dated 1997-06-16 for the 1997-07-15 meeting. Remember the two-class structure: only Common Stock was exchange-listed.
   - *Pharmacia & Upjohn symbol (5 rows)*: probe chunks ~4–8 of acc 0000950124-98-001758 for the Item 5 market paragraph (the search is bounded; three attempts on chunk 5 failed on proxy corruption, not on a missing page). Then the 2000 Monsanto/Pharmacia Corp demerger year.
   - *Warner-Lambert symbol (4 rows: D1342, D1366, D1376, D1409)*: the FY1997 10-K cover **has now been read** (acc 0000950117-98-000602, CIK 104669, chunk 0 of 43) and it changes the plan — "DOCUMENTS INCORPORATED BY REFERENCE: Portions of the Warner-Lambert Company Annual Report to Shareholders for 1997 -- Part I, Part II and Part IV", and Item 5 is in Part II, so the symbol is in the **Annual Report exhibit inside the same submission**, not the 10-K body (the Carter-Wallace trap). Open the submission's document list (9 public documents) and go straight to that exhibit's market-for-common-equity page, or use the DEF 14A for the 1998-04-28 annual meeting. The 12(b) cover also names **three** exchanges for Common Stock (Par Value $1): New York, Chicago and Pacific (plus a second 12(b) class, Rights to Purchase Series A Junior Participating Preferred Stock, on the same three); 12(g): None; file number 1-3608. Item 1 corroborates the sponsor chain in the registrant's own words — "under trademarks and trade names such as PARKE-DAVIS and GOEDECKE", with CEREBYX and OMNICEF in the product list.
   - *Roberts symbol (2 rows)*: FY1997/FY1998 10-K Item 5, or the DEFM14A filed 1999-11-23 (acc 0000950130-99-006712); the cheap Form 8-A12B/A (acc 0000950130-99-004255, 9 KB) names the exchange and class but not necessarily the symbol.
   - *Block Drug (D1365)*: the only remaining CITATION-LOCATED row — fetch acc 0000012654-97-000004 (CIK 12654).
   - *Cytogen D1381 continuity caveat*: the FY1996 10-K was filed 1997-03-24, four days **before** the 1997-03-28 Quadramet decision; confirm CYTO through that date from the FY1997 10-K (acc 0000725058-98-000010, filed 1998-03-31).
   - *3 ATTRIBUTION-CASE rows*: Elan 20-F FY1996 for Athena/Zanaflex (D1362) — the v11 Neurex proxy already proves Elan's ADSs were on the NYSE in 1998; DuPont FY1998/FY2000 10-K for Sustiva (D1017) and Innohep (D652).
   - Then the **18 REVIEW (foreign listing)** rows. Re-run `scripts/classify_listing.py` afterwards (safe: still a proven fixed point).
2. **Adjudicate the 141 core-vs-master class contradictions (itemised, needs network).** `scripts/audit_core_class_disagreements.py` writes `data/staging/core_class_disagreements.csv` and `validate_data.py` §7 pins the count at `CORE_CLASS_BASELINE = 141`. Every one is TICKER-INTERNALLY-INCONSISTENT: the master assigns different committed classes to rows sharing one real ticker, so the core table's ticker-keyed class (first row in master order wins) contradicts the other rows. Two families:
   - *ADR-vs-direct* — GSK (17 `US-LISTED` / 54 `US-LISTED (ADR)`), NVS (15/25), RHHBY (5 `NON-US LISTING ONLY` / 31 ADR), AZN (13/21), SNY (3/21), BAYRY (9 NON-US / 10 ADR), TAK (7/3), NVO (4/6), TEVA (4/3). These need a decision-date answer per company (was the US line an ADS/ADR, an ordinary NYSE/Nasdaq listing, or nothing at all?), which is a period-filing question — the 20-F/10-K cover 12(b) table settles it, exactly as it did for the pre-2000 worklist.
   - *delisted-vs-current* — SHPG, MDCO, CELG, ALXN, ORPH, SGEN, CBST, SLXP, BPMC, SPPI, BLCO, SWTX, AAAP: some rows still say `US-LISTED` for companies that have since been acquired. Each needs the terminal Form 25/15 or merger proxy cited, then the stale rows corrected to `FORMERLY US-LISTED (DELISTED/ACQUIRED)` with a dated note.
   Alternative if the maintainer prefers: make `build_core_analysis_table.py` publish each row's OWN committed class instead of the ticker-level one (a one-line change), which removes all 141 contradictions by construction — but that changes 141 published rows and should be a deliberate decision, not a side effect. Re-pin `CORE_CLASS_BASELINE` explicitly either way.
   **Already fixed this pass:** the `NO_US_TICKER` sentinel was being joined as a symbol (11 unrelated companies shared Fresenius Kabi's class and pipeline card; 6 were denied their own score). The builder now mirrors `TICKER_SENTINELS` from `build_company_scores.py`. That was the cause of the D442/D452 irregularity v10 flagged notes-only.
   **Still deliberately blank:** D1338 `IMMU` (class propagation via D376) and D1357/D1381 `CYTO` (D1231 shares the company name with a blank ticker, so a partial fill splits Cytogen's score row). Fill them only after the row-level class decision above.

3. **Optional third-source polish for the 2011–2016 pathway corrections** — FDA's "Novel New Drugs 2013/2015" and "New Drug Therapy Approvals 2016" reports publish priority-review lists; confirming the 10 corrected rows (Xarelto, Brilinta, Kyprolis, Xeljanz, Gattex, Bosulif, Tafinlar, Mekinist, Kengreal, Anthim) against them would add a third official source to each note (Compilation + Drugs@FDA already agree; low risk, moderate value).
4. **Pre-2000 sponsor resolution deep-dive on the non-NME originals** (~900 of 2,798 orig rows UNRESOLVED, mostly pre-2000 legacy sponsors) — exact-match-only aliases against SEC `company_tickers.json` and contemporaneous 10-K/20-F evidence; add registry keys, never token-match. Known collisions: "SUN PHARM" (3 keys), "NYCOMED" (no key), "CUBIST" (2 keys).
5. **Vintage-indication enrichment** — the 390 pre-1998 master rows and the orig file carry terse/blank indication text; FDA's compilation XLSX columns 16/17 ("Abbreviated Indication(s)", "Approved Use(s)") are the official source for a verbatim fill pass (notes-only, links already on the rows).
6. **Allergan AGN decision-date price series (D442 Vraylar, D452 Viberzi)** — both flagged; needs AGN 2015 chart captures (Yahoo may still return the delisted AGN series — if it fails, the failure is recorded, never a successor ticker).
7. **Purple Book 351(k) labelling** for the non-NME file (v8 carry-over); **PDUFA calendar** — 16 secondary-aggregation rows still need primary press-release/8-K captures (v5 carry-over); **CT.gov Phase 3 registry** paging beyond the first 2,000 (v6 carry-over).
8. **2016 NME audit** — FDA's 2016 table had a known USP-facing quirk (ETC-1002/Vascepa); a full line-by-line 2016 reconciliation like v7's 2014 pass would close the last year without a dedicated row-level reconciliation note. (2016 master pin is 22/22 vs the official count, so this is polish, not a gap.)
9. **Company-score confidence widening** — most scores are still Low-confidence because the market component has few priced events per company; the completed price universe means future widening must come from NEW events (or the CRL-event deep capture, e.g. foreign-listed parents), not from US-listed gaps (there are none). The v11 Item 5 quarterly brackets are *evidence text*, not price events — turning any of them into a snapshot needs a deliberate Yahoo fetch job for a 1990s delisted symbol, which will probably fail; if it fails, record the failure.

## Do not

- Invent novel approvals to pad counts — the master equals FDA's official NME Compilation 1985–2025 + the pinned 2026 year table; 1,000 extra novel approvals do not exist.
- Retry failed Yahoo chart requests with successor tickers (recorded repo law: the failure IS the data — ORPH/AKAO in v10 are the latest examples).
- Put files under `fetch_jobs/**` on a branch whose PR is meant to be a verified-data-only diff. That path filter fires `.github/workflows/arena-data-fetch.yml`, which commits multi-megabyte `data/raw/` payloads back onto the branch and buries the reviewable data changes. Queue fetch jobs on their own branch (see "Unblock route" above) — this is why PR #25 carries no job spec.
- Re-introduce token/substring ticker matching (7 documented false positives in v5). Blank beats guessed. **Ticker symbols for the pre-2000 rows must come from a period filing, never from memory or a modern ticker map** — the tally of memory-guesses falsified by primary text is now four: "AGRN" for Agouron (actually AGPH), "ANM/Nasdaq" for Advanced Magnetics (actually **AVM/AMEX**), "NXRX" for Neurex (actually **NXCO**), and this repo's own "Nasdaq:IVX era" (actually **AMEX:IVX**).
- Infer a listing venue from an SEC file-number prefix. IVAX's FY1996 10-K carried file number 001-09623 while its cover 12(b) table said AMERICAN STOCK EXCHANGE. Read the venue from the filing text.
- Fill the master `ticker` column for D1338 (IMMU) or D1357/D1381 (CYTO) without first fixing the two ticker-keyed side effects described in next step 2 — a trial run in v11 split Cytogen's company score into two rows and would have re-classified a 1996 Immunomedics row as US-LISTED. The validator pins those blanks deliberately.
- Turn an Item 5 quarterly high/low bracket into a price row. Those tables are staged as evidence text; price events come only from the Yahoo fetch-job pipeline.
- Merge T1GAP rows into the master — every remaining row is adjudicated with a reason. Emend IV in particular is a *documented exclusion*, not a missed row.
- Link Blenrep 2020 (D306) to BLA 761440 — that is the 2025 re-approval, a different decision.
- Treat Type 5 manufacturer changes or medical gases as clinical-trial conversions.
- Fill missing prices, dates, indications, or tickers; silently overwrite a source conflict; overwrite the 58 hand-verified CRL rows or the 8 hand-verified trial endpoints.
- Re-open the pathway reconciliation: the 64 v10 corrections each cite ≥2 agreeing official sources with both prior values preserved in notes. If a THIRD source ever disagrees, add a dated note — never blanket-revert.
- Build the derived tables in the wrong order. `build_core_analysis_table.py` READS `data/company_scores.csv`, so the order is master → `build_company_scores.py` → `build_core_analysis_table.py`. Doing it the other way leaves the core table's `company_score` / `_grade` / `_confidence` cells stale — this actually happened in the v11 first wave, where the 5 rows that gained a ticker were published as "Not scored - no verified FDA decisions tracked" and only picked up their real scores (41.5 / D / Low) when the builders were re-run in the right order in the second wave.
- Re-run `build_company_scorecards.py` (overwrite) without immediately re-running the two append builders (`_multi`, `_new`) — `company_scorecards.csv` is a cumulative hand-curated artifact, not a deterministic output.
- Delete a superseded guess from a row note. Corrections are appended with a date and the old wording preserved (`v10_note_superseded` in the evidence file) so the audit trail stays honest.
- `scripts/classify_listing.py` is a fixed point (v9, re-proven in v11) — but only because it PRESERVES committed classes; data corrections belong in builders, not in this script. Vocabulary fixes to its venue lists are allowed, provided the re-run is proven byte-identical on the committed master.
- Claim the 2,000-study CT.gov capture is exhaustive — it is the API's first 2,000 matches.
- Price D999 Azopt 1998 with the modern ALC line — Alcon had no separate equity in 1998 (flagged TICKER_FLAG note).
