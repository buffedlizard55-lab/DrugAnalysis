# Remaining work for the next session (written 2026-09-20, v25)

Branch: `arena/01a0c036-druganalysis`. This session (v25) completed the v24
list's top priority item: the **v24 openFDA backfill entries are now joined
into the core analysis table**. `data/core_analysis_table.csv` went
1,885 → **1,933 rows**: 48 of the 290 v24 entries were joined (the other 242
already exist in the NME master and were therefore already in the table —
appending them again would have double-counted the same FDA decisions). The
builder now fails closed on an ambiguous dedupe, and the validator's core
gate (§7) mirrors the join: shape (master + CRL + v24-not-in-master) and
per-row coverage of the 48, plus the ambiguity check. Validator: **PASS,
0 errors**.

## State right now (read this first)

| Layer | Path | Status |
|---|---|---|
| Master decisions | `data/fda_decisions_master.csv` | **1,427 rows** (1985-2026, unchanged — the 48 new v25 rows are NOT merged into the master, by design, see "v25 changes") |
| Original non-NME | `data/fda_original_non_nme_decisions.csv` | 3,432 rows (unchanged) |
| Supplement decisions | `data/fda_supplement_decisions.csv` | 4,482 rows (unchanged) |
| CRL master | `data/fda_crl_master.csv` | 458 rows (unchanged) |
| **Core analysis** | `data/core_analysis_table.csv` | **1,933 rows** (1,427 master + 458 CRL + 48 v24-backfill joined in v25; 861 with verified price data, unchanged) |
| Clinical scorecards | `data/company_clinical_trial_scorecard.csv` | 423 rows (unchanged) |
| Stock snapshots | `data/stock_price_snapshots.csv` | 2,848 rows (unchanged) |
| Phase 3 registry | `data/clinical_trials_phase3_registry.csv` | 2,000 rows (unchanged) |
| Year crosswalk | `data/year_verification_crosswalk_v24.csv` | 47 rows (unchanged) |
| Pre-1980 decisions | `data/pre1980_fda_decisions.csv` | 173 rows (unchanged) |
| CRL match | `data/crl_application_match.csv` | 458 rows (unchanged) |
| Verifiers | `scripts/verify_pre1980_year_register_v23.py`, `scripts/verify_crl_application_match_v23.py` | 7,164 + 5,456 checks, 0 errors |
| Validator | `scripts/validate_data.py` | **PASS, 0 errors** (v25 core-join gates added) |

## v25 changes this session

1. **Core analysis table joins the v24 backfill** (`data/core_analysis_table.csv`,
   1,885 → 1,933 rows):
   - `scripts/build_core_analysis_table.py` gained a v25 join section. It reads
     the 290 `v24 backfill` rows from `fda_original_non_nme_decisions.csv` and
     dedupes them against the master on (normalised drug_brand, decision_date):
     **242 are already in the master** (e.g. ZYDELIG 2014-07-23, OLUMIANT
     2018-05-31, EMFLAZA 2017-02-09) and are skipped — they are in the table
     through their master row; **48 are joined exactly once**.
   - Fail-closed guard: if a v24 row shares (company, date) with a master row
     under a DIFFERENT brand, the builder aborts (ambiguous dedupe, needs human
     review). Currently 0 such rows.
   - Labels: TYPE 1 / TYPE 1/4 read `Approval (<class>; v24 openFDA backfill)`
     so the engine's approval statistics count them (34 + 5 rows); every other
     class reads `Original Approval (non-NME; <class>; ...)` (5 Efficacy, 2
     Type 3, 1 Type 5, 1 Type 9) and is excluded from the NME statistics, same
     discipline as `NOT_ON_FDA_NME_TABLE`.
   - No facts invented: all 48 carry `TICKER-UNRESOLVED` in flags (tickers are
     blank, price status "No public ticker", no class asserted — the UNRESOLVED
     class string is not a listing class). 22 of the 48 have no product name in
     the openFDA payload at all; the application number is used as the
     identifier and `NO-PRODUCT-NAME` marks the gap. Indication stays empty
     (the openFDA original-approval extract has no structured indication field,
     same convention as the pre-1985 rows).
   - Each row keeps its openFDA provenance: `fda_source_url` = Drugs@FDA page,
     `secondary_source_url` = the openFDA query that returned it.

2. **Validator core gate extended** (`scripts/validate_data.py` §7):
   - Shape now expects `master + CRL + v24-backfill-not-in-master`
     (1,427 + 458 + 48 = 1,933).
   - New coverage check: every joined v24 row must be present, keyed the way
     the builder writes it (company, date, drug name — "brand (generic)",
     brand, or application number when nameless).
   - New fail-closed check for the ambiguous-dedupe case, mirroring the
     builder.
   - Mutation-tested: deleting the 48 rows fails the build with the shape,
     coverage, and ratchet errors pointing at the v24 join; restoring them
     returns PASS, 0 errors.

## Exact re-verify commands

```bash
python3 scripts/build_core_analysis_table.py   # expect 1,933 rows; "48 joined, 242 already covered"
python3 scripts/validate_data.py               # expect PASS (0 errors)
node --check assets/app.js                     # expect clean
```

## Next work, in priority order

1. **Ticker/exchange resolution for the 290 v24 entries** — all 290 still have
   `ticker=""` and `us_investable_class="UNRESOLVED"`; the 48 core rows are
   flagged `TICKER-UNRESOLVED`. Match the openFDA sponsor names against the
   committed SEC list (`data/raw/probe/sec_company_tickers_alt.json`, the same
   conservative exact/tie-break rules as `scripts/resolve_tickers.py`) and fill
   ticker/exchange/class in `data/fda_original_non_nme_decisions.csv` with a
   `sponsor_resolution_basis` per row (validator requires the basis whenever a
   ticker is filled). Wrong ticker is worse than no ticker.

2. **Stock price snapshots for resolved tickers** — once tickers resolve,
   build Yahoo Finance snapshots for the new entries via the Actions runner
   (no general outbound network in the sandbox), then rerun
   `build_company_scores.py` → `build_core_analysis_table.py` so prices flow
   into the 48 core rows.

3. **Update company scorecards** — the newly resolved entries should flow into
   `company_scorecards.csv` / `company_scores.csv` / the clinical trial
   scorecards.

4. **Year register update** — rebuild `data/fda_orig_year_register.csv` to
   reflect the post-v24 per-year counts (currently pins pre-v24 counts; the
   validator allows the +290 delta).

5. **CRL↔PDUFA denominator matching** — still the engine's blocking limitation.
   The CRL dataset is a published subset, not a census.

6. **Pre-1965 backward extension** — `fetch_jobs/drugsatfda_data_files_1938_1964.json`
   is queued but not yet run.

7. **40 CRL conflict rows** — need human review of linked FDA letters.

8. **141 core-analysis listing-class disagreements** — period 10-K/20-F cover
   evidence (validator §7 ratchet baseline 141).

9. **Stock backlog** — 462 of 3,868 Yahoo items are still pending on the runner.

10. **242 v24 rows that duplicate the master** — openFDA names the current
    application holder, not the 1985-2026 applicant (e.g. NDA021321 shows
    brand "EXTRANEAL" under Vantive). Reconciling the v24 rows'
    sponsor/brand text against the master rows' verified applicant is a
    candidate cleanup pass; do not "fix" master values without primary
    evidence.

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
- The NME master stays a year-table file: v24/v25 openFDA-backfill NMEs are joined
  into the core table, NOT merged into `fda_decisions_master.csv` (merging would
  break the official CDER year-count audit — same rule as
  `data/fda_type1_not_in_nme_master.csv`).

## Infrastructure notes

- `.github/workflows/arena-data-fetch.yml` — per-branch concurrency; builds and verifies
  v23 tables and runs `validate_data.py`; commits `data/raw` and `data/*.csv`.
- The sandbox has no general outbound network (only `api.github.com`): all bulk
  fetching goes through the Actions runner.
- `data/raw/openfda_approvals_2000_2010/*.json` rows live under `results`;
  `openfda_efficacy_supplements/suppl_*.json` under `supplements`;
  `openfda_orig_decisions_*/*.json` under `decisions`.
