# Remaining work for the next session (written 2026-09-18 v14)

The v13 branch was pushed and merged to `main` as PR #27 (`dd2ce59`). v14 is committed locally as `322fffa` on `arena/01a0b62c-druganalysis`; it still needs to be pushed, reviewed in a PR, and merged. The repository root is `/home/user/DrugAnalysis`; do not switch branches.

## What v14 shipped

- **Backward pre-1985 expansion is complete through 1980.** `data/pre1985_fda_decisions.csv` now has **91 verified rows for 1980–1984**:
  - 1980: **9/9** committed Drugs@FDA TYPE-1 applications.
  - 1981: **23/23** committed Drugs@FDA TYPE-1/1-4 applications.
  - 1982: **25/25** committed Drugs@FDA TYPE-1 applications, including Hylorel (NDA018104, 1982-12-29).
  - 1983: 14 rows (13 Drugs@FDA-indexed TYPE-1 applications + the separately verified Furosemide oral-solution original application with class/priority not stated).
  - 1984: 20 rows (19 Drugs@FDA-indexed TYPE-1/1-4 applications + Trandate's separately verified TYPE-5 application).
- Hylorel was **re-homed from v13's `PRE1985-1983-08` launch-era group to `PRE1985-1982-23`**, without dropping the approval. The old ID is validator-banned.
- `data/pre1985_era_analysis.csv` now has **six rows, 1980–1985**. For 1980–1982, `total_nmes_approved` is explicitly labeled as the complete committed Drugs@FDA application enumeration, **not** a claimed contemporaneous annual NME statistic. No independent official pre-1985 annual NME table was found.
- `scripts/expand_pre1985_decisions_v14.py` is the authoritative, idempotent builder. It derives application/date/class/priority/product fields from the raw payload and aborts on mismatch. It replaces v14 rows on rerun and preserves the v13 1983/1984 IDs.
- `scripts/build_pre1985_era_analysis.py` is now only a compatibility wrapper to v14; it no longer contains a stale hand-curated writer.
- `data/staging/pre1985_expansion_report_v14.json` records 56 additions, the Hylorel migration, all retained assertions, counts, and limitations.
- `scripts/validate_data.py` now asserts: 91-row shape, 1980–1984 group counts, old-ID bans, Hylorel boundary pin, all five raw payload date/class/priority checks, complete 1980–1982 application-set equality, six era rows, era/table priority counts, and all previous v13/v12 gates.
- `index.html` and `assets/app.js` now describe/render the 1980–1985 historical tab. README and VERIFICATION_REPORT have v14 sections.

## Verification already run

```text
python3 scripts/expand_pre1985_decisions_v14.py
# wrote 91 rows; counts 1980=9, 1981=23, 1982=25, 1983=14, 1984=20; added 56

python3 scripts/validate_data.py
# PASS: 0 errors, 1,612 warnings
```

The warnings are the existing manual-review baseline. The v14 builder was run twice after the idempotence fix and produced byte-identical decision and era CSVs.

## Source discipline and limitations

- Raw official payloads are already committed under `data/raw/openfda_orig_decisions_1980_1984/`; no new fetch is needed for this expansion.
- Every row has an official Drugs@FDA link and an application-specific openFDA query. Notes carry FDA label/Federal Register/NIH/NCATS/contemporaneous scientific links for indication/history review.
- 1980s ORIG records generally have no machine-readable `application_docs`. Approval-era indication wording is therefore qualified when a later FDA label or NIH record is used. Do not silently present current labeling as 1980s labeling.
- The payload's current holder is not automatically treated as the historical applicant. Historical tickers are time-qualified; blank beats a guessed period symbol. The seven remaining pre-2000 sponsor rows are still venue-verified only.
- No independent official annual NME count was found for 1980–1982. Do not replace the explicit application-enumeration wording with a secondary count unless a primary source is fetched and recorded.

## Next work, in priority order

1. **Push and ship v14.** Push commit `322fffa` to `arena/01a0b62c-druganalysis`, open a PR to `main`, wait for checks, and merge. The final local review already ran `python3 -m py_compile`, `python3 scripts/validate_data.py`, `node --check assets/app.js`, idempotence tests, mutation tests, and a static preview smoke test. Do not alter the already merged v13 PR.
2. **Remaining pre-2000 ticker resolution (7 VENUE-VERIFIED rows).** Use the sandbox page-fetch tool only for SEC primary text; the Actions EDGAR route returns HTTP 403 and must not be retried:
   - Warner-Lambert ×4: FY1998 10-K, 1998 DEF 14A, FY1999 10-K (CIK 104669; find canonical accession through the company browse page). The remembered WLA symbol is not evidence.
   - Roberts ×2: FY1997 10-K accession `0000950130-98-001619`, proxies, and 1999 DEFM14A `0000950130-99-006712`.
   - Block Drug ×1: CIK 12654 424/DEF 14A or web-archived NASD/Pink-Sheet evidence.
   Extract Item 5/cover sentences verbatim; blank beats guess.
3. **Adjudicate the 141 core-analysis listing-class disagreements.** Use period 10-K/20-F cover evidence. Main groups: ADR vs direct (GSK, NVS, RHHBY, AZN, SNY) and delisted/current (SHPG, MDCO, CELG, ALXN). Preserve the existing class-disagreement ratchet until each change has a primary citation.
4. **ClinicalTrials.gov Phase 3 depth.** The registry remains the first 2,000 studies in the 2026–2027 completion window. Use the existing ctgov fetch-job pagination machinery and extend only with replayable payloads/manifests.
5. **User-requested 1,000 new 2000–2026 entries.** The project already has 1,427 novel approvals plus 4,482 verified efficacy supplements and 2,798 original non-NME approvals. Continue adding only real FDA decisions with official application/date/source evidence; do not manufacture 1,000 novel approvals that do not exist.
6. **Improve decision-engine analysis.** Continue official pipeline/PDUFA press-release verification, stock-event coverage, and company clinical-trial scorecard quality. Keep approval outcome, stock reaction, and phase-transition success as distinct measures.

## Important repository facts

- Branch: `arena/01a0b62c-druganalysis`; origin: `https://github.com/buffedlizard55-lab/DrugAnalysis.git`.
- v13 is on `main` via PR #27. v14 commit `322fffa` is local on `arena/01a0b62c-druganalysis` and is not yet pushed.
- `data/fda_decisions_master.csv`: 1,427 rows, 1985–2026; do not merge the separate pre-1985 table into the master without a deliberate schema/scorecard decision.
- Derived tables were not changed by v14 because they consume the 1985–2026 master, not the separate historical pre-1985 table.
- Existing data-fetch convention: bulk openFDA/ctgov/Yahoo jobs run through GitHub Actions; SEC EDGAR must use the sandbox page-fetch tool, one canonical URL at a time.
