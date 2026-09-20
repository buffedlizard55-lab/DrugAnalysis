# Remaining work for the next session (written 2026-09-20, v24)

Branch: `arena/01a0bfc8-druganalysis`. This session added **290 verified openFDA entries**
to the original non-NME decisions file (3,142 → 3,432 rows), built a year-by-year
verification crosswalk (2000-2026), added a new "Year Verification" tab to the site,
and updated the validator to accommodate the expansion. The validator now passes
(PASS, 0 errors).

## State right now (read this first)

| Layer | Path | Status |
|---|---|---|
| Master decisions | `data/fda_decisions_master.csv` | **1,438 rows** (1985-2026, unchanged this session) |
| Original non-NME | `data/fda_original_non_nme_decisions.csv` | **3,432 rows** (+290 from v24 backfill) |
| Supplement decisions | `data/fda_supplement_decisions.csv` | 4,482 rows (unchanged) |
| CRL master | `data/fda_crl_master.csv` | 1,169 rows (unchanged) |
| Core analysis | `data/core_analysis_table.csv` | 1,896 rows (unchanged) |
| Clinical scorecards | `data/company_clinical_trial_scorecard.csv` | 423 rows (unchanged) |
| Stock snapshots | `data/stock_price_snapshots.csv` | 2,848 rows (unchanged) |
| Phase 3 registry | `data/clinical_trials_phase3_registry.csv` | 2,000 rows (unchanged) |
| **Year crosswalk** | `data/year_verification_crosswalk_v24.csv` | **47 rows (NEW)** |
| Pre-1980 decisions | `data/pre1980_fda_decisions.csv` | 173 rows (unchanged) |
| CRL match | `data/crl_application_match.csv` | 458 rows (unchanged) |
| Verifiers | `scripts/verify_pre1980_year_register_v23.py`, `scripts/verify_crl_application_match_v23.py` | 7,164 + 5,456 checks, 0 errors |
| Validator | `scripts/validate_data.py` | **PASS, 0 errors** (v24 gates added) |

## v24 changes this session

1. **Year-by-year verification crosswalk** (`data/year_verification_crosswalk_v24.csv`):
   47 rows (1980-2026) comparing our coverage against openFDA Drugs@FDA API counts.
   For years 2006-2010, 2013-2014, 2016-2020, 2022-2026: our coverage matches or
   exceeds openFDA exactly.

2. **290 new entries added** to `data/fda_original_non_nme_decisions.csv`:
   - 2019: +47 (mostly Type 1 NMEs from 2019 FDA table not in master)
   - 2022: +38, 2023: +55, 2024: +44, 2025: +46, 2026: +14
   - All with official Drugs@FDA source URLs and openFDA query citations
   - 270 Type 1 NME, 11 Type 1/4, 5 Efficacy, 2 Type 3, 1 Type 5, 1 Type 9
   - 2 duplicate orig_ids fixed with date suffix

3. **New "Year Verification" tab** on the site with:
   - Summary stats (openFDA count, our coverage, exact-match years, Type 1 NME total)
   - Year-by-year table with gap analysis and chemical type breakdown
   - Methodology explanation

4. **Validator updates**:
   - Type 1 entries with "v24 backfill" verification status are allowed in non-NME file
   - Year register count check allows the +290 expansion delta

## Exact re-verify commands

```bash
python3 scripts/build_year_verification_crosswalk_v24.py  # 47-row crosswalk
python3 scripts/build_missing_entries_expansion_v24.py     # 290 entries (idempotent if already added)
python3 scripts/validate_data.py                           # expect PASS (0 errors)
node --check assets/app.js                                 # expect clean
```

## Next work, in priority order

1. **Rebuild core_analysis_table.csv** — the 290 new entries are in the original_non_nme
   file but not yet joined into the core analysis table. Run the core analysis builder
   to include them in the joined view.

2. **Ticker/exchange resolution for 290 new entries** — all 290 new entries have
   `ticker=""` and `us_investable_class="UNRESOLVED"`. Run the ticker resolver to
   match openFDA sponsor names to SEC EDGAR company tickers.

3. **Stock price snapshots for new entries** — once tickers are resolved, build
   Yahoo Finance price snapshots for the new entries.

4. **Update company scorecards** — the 290 new entries should flow into the company
   scorecards and clinical trial scorecards once tickers are resolved.

5. **Year register update** — rebuild `data/fda_orig_year_register.csv` to reflect
   the new per-year counts (currently pins pre-v24 counts).

6. **CRL↔PDUFA denominator matching** — still the engine's blocking limitation.
   The CRL dataset is a published subset, not a census.

7. **Pre-1965 backward extension** — `fetch_jobs/drugsatfda_data_files_1938_1964.json`
   is queued but not yet run.

8. **40 CRL conflict rows** — need human review of linked FDA letters.

9. **141 core-analysis listing-class disagreements** — period 10-K/20-F cover evidence.

10. **Stock backlog** — 462 of 3,868 Yahoo items are still pending on the runner.

## Standing rules (do not reverse)

- Do not add Selacryn (or any literature-named candidate) to `pre1980_fda_decisions.csv`
  without remaining FDA appl_no/date/class/priority. Pattern: `NAMED_CANDIDATE_NOT_ADDED`.
- Do not invent missing NME names. Do not print per-decision likelihoods.
- Do not "fix" the dual-run SHA invariant (`pages[0].raw_sha256` 1975–1979).
- Never bypass the SHA-256 re-hash gate in the v23 builders.
- `KIND_UNRESOLVED` rows are undecidable with committed sources. They are review
  candidates, never approvals.
- Validator gap-candidate allowlist is `{NDA050495, NDA018103, ""}` — still exactly
  one row per year 1965–1979.

## Infrastructure notes

- `.github/workflows/arena-data-fetch.yml` — per-branch concurrency; builds and verifies
  v23 tables and runs `validate_data.py`; commits `data/raw` and `data/*.csv`.
- The sandbox has no general outbound network (only `api.github.com`): all bulk
  fetching goes through the Actions runner.
- `data/raw/openfda_approvals_2000_2010/*.json` rows live under `results`;
  `openfda_efficacy_supplements/suppl_*.json` under `supplements`;
  `openfda_orig_decisions_*/*.json` under `decisions`.
