# Remaining work for the next session (written 2026-09-22, v29)

Branch: `arena/01a0c7ef-druganalysis`. This session (v29) did what the v28
handoff put first: it **landed and joined the pre-1939 whole-table census**
(runner capture of the complete official Drugs@FDA `Submissions.txt`, all
193,810 rows) and dealt honestly with what it showed - the census contradicted
two v28 working hypotheses, and v29 publishes the contradiction verbatim
instead of smoothing it. It also **fixed the runner defect that made Actions
runs 32 and 33 fail** (re-download of the daily-updated official ZIP over the
SHA-pinned extracts) and **corrected one more false v28 note** (EV-03).

**Earliest verified FDA drug-approval action: still 1939-02-09, NDA000552.
0 of all 193,810 official submission rows are dated between the FD&C Act
(1938-06-25) and 1938-12-31. The one row dated before 1939 (ApplNo 060904,
`1900-01-01 00:00:00`) is a pre-statute placeholder - flagged, published
verbatim, never counted. No pre-1939 decision row is asserted anywhere.**

## State right now (read this first)

| Layer | Path | Status |
|---|---|---|
| Master decisions | `data/fda_decisions_master.csv` | 1,427 rows (1985-2026, unchanged) |
| Original non-NME | `data/fda_original_non_nme_decisions.csv` | 3,432 rows (unchanged) |
| Supplement decisions | `data/fda_supplement_decisions.csv` | 4,482 rows (unchanged) |
| CRL master | `data/fda_crl_master.csv` | 458 rows (unchanged) |
| Core analysis | `data/core_analysis_table.csv` | 1,933 rows (unchanged) |
| Decision-engine analysis | `data/decision_engine_analysis_table.csv` | 1,933 rows (unchanged) |
| 1000 new verified 2000-2026 | `data/fda_verified_decisions_2000_2026_1000_new.csv` | 1,000 rows (unchanged) |
| Clinical scorecards | `data/company_clinical_trial_scorecard.csv` | 423 rows (unchanged) |
| Detailed success scorecard | `data/company_success_rate_detailed_scorecard.csv` | 485 rows (unchanged) |
| Stock snapshots / index | `data/stock_price_snapshots.csv`, `data/stock_price_verified_index.csv` | 2,848 rows each (unchanged) |
| Phase 3 registry | `data/clinical_trials_phase3_registry.csv` | 2,000 rows (unchanged) |
| Pre-1985 / Pre-1980 / Pre-1965 | `data/pre1985_fda_decisions.csv` 91 · `data/pre1980_fda_decisions.csv` 173 · `data/pre1965_fda_decisions.csv` 178 | unchanged |
| Pre-1965 audit + probes | `data/pre1965_originals_audit_1939_1964.csv` 535 · `data/pre1965_row_probe_index.csv` 535 | unchanged, probe layer complete |
| Pre-1939 boundary (v28, extended v29) | `data/pre1939_boundary_determination.csv` | **16 evidence lines** (EV-12..EV-16 from the whole-table census; EV-03 corrected) |
| Pre-1939 application census (v28) | `data/pre1939_application_census.csv` | 2 rows (NDA000004, NDA000159 — exhaustive; unchanged) |
| Pre-1939 regulatory register (v28) | `data/pre1939_regulatory_register_1902_1938.csv` | 37 rows (1902-1938, 0 decisions each; 1938 row's basis now cites the whole-table census) |
| Pre-1939 status census (v28) | `data/pre1939_submission_status_census.csv` | 41 rows (all AP; unchanged) |
| **Pre-1939 whole-table census (NEW v29)** | `data/pre1939_complete_table_census.csv` | **6 rows**, one per capture file, verbatim + SHA-manifested |
| Pre-1939 runner captures | `data/raw/drugsatfda_pre1939_census_v28/` | **LANDED** (Actions run 33, 2026-09-21T23:34Z; ZIP `2e734224…`, Submissions member `b006c37c…` 193,810 rows, Applications 29,343 rows) |
| Overview-page captures for EV-16 | `data/raw/drugsatfda_overview_pages_v29/` | **PENDING** — job `fetch_jobs/drugsatfda_overview_pages_v29.json` (060904, 009658, control 000552); nothing is built from it |
| Verifiers | `verify_pre1939_boundary_v28.py` **2,763 checks / 0 errors** · `verify_pre1965_year_register_v26.py` 22,105 / 0 · `verify_pre1980_year_register_v23.py` 7,164 / 0 · `verify_crl_application_match_v23.py` 5,456 / 0 | all green |
| Validator | `scripts/validate_data.py` | **PASS, 0 errors** (1,751 warnings = standing baseline) |
| Runner self-test (NEW v29) | `scripts/tests/test_run_fetch_jobs_zip_skip_existing.py` | green; runs first in the workflow |
| Site | `index.html` + `assets/app_v27.js` | 11 tabs; Pre-1939 tab gains 2 KPI cards, the irregular-rows callout and the whole-table census table; `node --check` clean |

## v29 changes this session

1. **Whole-table census joined** (`scripts/build_pre1939_boundary_v28.py`,
   filename kept; `V29` label only on rows the census produced or changed).
   The capture landed on run 33 and was staged from that branch commit
   (`e6bd9b2`, SHAs re-verified). What it showed, cell for cell:
   - `Submissions_before_1939.txt`: **1 row, not 0** - ApplNo `060904`, ORIG 1,
     AP, `1900-01-01 00:00:00`. Dated before every federal drug statute in the
     register, so it cannot be an action on an application. Published verbatim
     as `FLAG-PRE-STATUTE-DATE`, `counted_as_fda_decision = False`.
     **0 rows dated 1938-06-25..1938-12-31** - the boundary stands. The builder
     still aborts on any row dated on/after the FD&C Act and before 1939.
   - `Submissions_undated.txt`: **8 rows** (1 ORIG on `009658` + 7 SUPPL,
     empty status date) - the rows no year filter could see, now enumerated
     (`FLAG-UNDATED-ROW`). Arithmetic: 193,810 = 1 + 8 + 193,801 dated >= 1939.
   - `Submissions_status_counts.txt`: **AP 192,604 / TA 1,205 / empty 1** -
     not "AP only". TA = tentative approval (FDA glossary quoted verbatim in
     EV-14) - an approval-family action. **Still no RE / W / CR anywhere**, so
     the v28 correction stands; wording refined to "approval-family actions
     only". Any other status aborts the build.
   - `Submissions_type_counts.txt`: ORIG 27,862 / SUPPL 165,948 (sum = member).
   - `Applications_below_boundary.txt`: exactly `000004`, `000159` - identical
     to the map-derived set. `Submissions_applno_below_boundary.txt`: their
     complete 6-row history; both window rows present; the other 4 are
     supplements dated 1980-1987, asserted nowhere.
   - `060904` and `009658` have **no row in the official Applications table**
     (either publication), appear in no committed window or project table, and
     their official Drugs@FDA overview pages render no application section
     (session observation; capture queued, see below). No cause is inferred.
2. **Publication drift made explicit (EV-15), not silently absorbed.** The
   census ZIP (`2e734224…`, 193,810 submission rows, 29,343 applications) is a
   later publication than the one the committed windows are pinned to
   (`e145bc0f…`, 193,752 / 29,336; 6 identical downloads 2026-09-19..21). FDA:
   "The data file is updated each morning, Monday through Friday." The
   windows stay SHA-pinned to their own publication; the +58/+7 delta is an
   evidence line. Run 33 also re-cut both windows from the later publication
   (identical row sets, different order) - that commit was deliberately **not**
   merged; it is recorded as a session observation only.
3. **Runner defect fixed** (`scripts/run_fetch_jobs.py`): `zip_extract` now
   honours `skip_existing` like every other job kind, and a run that produces
   nothing but `skipped-existing` stubs leaves `manifest.json` byte-identical
   (runs 32/33 each appended ~20,000 stub lines and pushed data commits after
   the PR had merged). `skip_existing: true` set on all three landed zip jobs
   (generator regenerates byte-identically). Also fixed: a FAILED page-0 fetch
   in the three paged openFDA kinds fell through to write a **0-record payload
   with status 200** over the committed file - it now leaves the payload
   untouched. All of this is exercised end-to-end through `run_job()` in
   `scripts/tests/test_run_fetch_jobs_zip_skip_existing.py` (runs first in the
   workflow). Simulated the full job set with the network disabled: no landed
   job re-downloads, no manifest rewrites, no payload touched.
4. **EV-03 corrected.** v28 wrote that NDA000159 was "already counted in
   `data/pre1965_fda_decisions.csv`". False: that table holds NME-comparable
   rows only (earliest row 1942). NDA000159 (class not published,
   `nme_comparable FALSE`) is row `PRE1965AUDIT-1939-02` of the pre-1965
   originals **audit** table - same error class as v28's own EV-02 catch. The
   note is now derived from the era index, and the verifier + validator pin
   it. The same false sentence was caught in this session's first draft of the
   new fifth table and removed before commit.
5. **Builder bug fixed:** the v28 join re-hashed captures against a manifest
   key `sha256` that `zip_extract` never writes (`out_sha256`), so the first
   real join would have failed on every file.
6. **Verifier** extended (2,763 checks): re-hashes every capture against its
   manifest, re-applies the adjudication rules independently, re-derives every
   cell of the fifth table, pins EV-03/EV-12..EV-16 and the register 1938 row.
   Mutation-tested: the false EV-03 sentence, a changed placeholder date in a
   flags cell, and one appended byte in a raw capture all fail.
7. **Validator v29 gate**: fifth-table shape, `counted_as_fda_decision`
   starts with `False` for the irregular rows, flags present, no RE/W/CR
   token, no `pre1965_fda_decisions.csv` claim, official hosts, 16-hex SHA
   prefixes; fails if the CSV exists without its capture layer.
8. **Site**: Pre-1939 tab - 2 new KPI cards (193,810 rows; AP/TA/empty), the
   "two irregular rows" callout, the whole-table census table; overview and
   historical-tab copy updated (approval-family wording; 16 evidence lines).
9. **New queued capture** `fetch_jobs/drugsatfda_overview_pages_v29.json`
   (official overview pages of 060904, 009658 and control 000552) so the EV-16
   web observation becomes reproducible from the committed tree.

## v28 summary (kept for context)

Boundary proven from committed official sources (earliest action 1939-02-09,
NDA000552; 0 rows dated 1938; exactly NDA000004 + NDA000159 below the
boundary); 1902-1938 regulatory register (37 years, 0 decisions each);
1939-1979 status census (all AP). Two corrections: the v27 "RE/W live in the
1938-1964 register" claim and v28's own EV-02 draft (NDA000004 tracked in the
pre-1980 originals audit, not the NME decision table).

## Exact re-verify commands

```bash
python3 scripts/tests/test_run_fetch_jobs_zip_skip_existing.py   # runner self-test, expect OK
python3 scripts/build_pre1939_boundary_v28.py   # 16 evidence, 2 census, 37 register, 41 status, 6 whole-table rows
python3 scripts/verify_pre1939_boundary_v28.py  # expect "2,763 checks, 0 error(s)"
python3 scripts/validate_data.py                # expect PASS (0 errors)
python3 scripts/verify_pre1965_year_register_v26.py   # expect 22,105 checks, 0 errors
node --check assets/app_v27.js                  # expect clean
```

## Next work, in priority order

1. **Run 34 outcome (2026-09-22T07:38-08:57Z) - first fully green run since
   FDA republished the data file.** Runner self-test green; all three zip
   jobs printed `skip … (skip_existing)` / `no-op … manifest unchanged`; the
   SHA-pinned windows were untouched and every build/verify step (v28/v29,
   v27, v26, v23, stock ingest) succeeded on the runner. Its data commit
   (`46d4d6e`) landed **before** the merge this time and is in `main`. It
   contains, besides `last_run.log`: refreshed `openfda_approvals_2000_2010`
   payloads (job has no `skip_existing`, see item 2; record counts and byte
   sizes identical, only `sha256` cells of `data/crl_match_sources.csv`
   changed; v23 verifier green), refreshed live probes/source captures, and
   ~17,000 lines of FAILED-retry entries in the stock/EDGAR manifests
   (pre-existing backlog, items 7/8 below).
   **The overview-page capture did not land: HTTP 404 on all three pages,
   including the control (NDA000552).** Because the control failed too, this
   is the runner's plain `urllib` request being refused by
   `accessdata.fda.gov`, not evidence about the orphan numbers (the same
   pages rendered in the sandbox's browser-style fetch on 2026-09-22). Next
   step: add a `headers` block with a browser User-Agent to
   `fetch_jobs/drugsatfda_overview_pages_v29.json` (pattern:
   `fetch_jobs/probe.json` SEC items) and re-run; if the control still fails,
   record the page as not machine-capturable and leave EV-16 as a session
   observation. Do not build anything on it until the control captures.
2. **`fetch_jobs/openfda_approvals_2000_2010.json` has no `skip_existing`.**
   It re-downloads 11 × ~13 MB openFDA payloads on every run (12 copies of
   `orig_ap_2000` in its manifest) and those payloads feed
   `build_crl_application_match_v23.py`. Pinning them is a data decision
   (the CRL match output would freeze at the current publication) - decide
   deliberately; v29 only stopped a failed fetch from zeroing them.
3. **CRL↔PDUFA denominator matching** — still the decision engine's blocking
   limitation. The CRL dataset is a published subset (458 letters, 2011+), not
   a census, so per-decision likelihoods are still refused by design. v28 made
   this worse in a useful way: it proved refused/withdrawn actions cannot be
   read out of Drugs@FDA `Submissions.txt` at all, so the CRL database is the
   *only* source. Closing this needs a targeted capture of FDA's CRL list per
   fiscal year plus PDUFA goal dates.
4. **Ticker/exchange resolution for the 290 v24 backfill entries** (open since
   v25): match openFDA sponsor names against the committed SEC list
   (`data/raw/probe/sec_company_tickers_alt.json`) with a
   `sponsor_resolution_basis` per row, then Yahoo snapshots via the runner,
   then rebuild scores/core so prices flow in.
5. **40 CRL conflict rows** — need human review of the linked FDA letters.
6. **141 core-analysis listing-class disagreements** — period 10-K/20-F cover
   evidence (validator §7 ratchet baseline 141).
7. **Stock backlog** — remaining Yahoo items pending on the runner.
8. **242 v24 rows that duplicate the master** — openFDA names the *current*
   application holder, not the historical applicant; do not "fix" master values
   without primary evidence.
9. **Year register refresh** — rebuild `data/fda_orig_year_register.csv` for
   post-v24 per-year counts (still pins pre-v24 counts).
10. **Repository hygiene** — `index_v27.html` and `assets/app.js` (2,767 lines)
   are no longer referenced by `index.html`; `.venv/` (~5,600 files) is
   committed and is not in `.gitignore`. Neither is load-bearing for the site,
   but both should be removed or ignored before the tree grows further.
   **Not touched in v28 or v29** to keep each diff auditable.
11. **1902-1938 biologic licenses** (research-heavy, optional): the only
    pre-1938 federal drug pre-market authorisation regime. No official
    machine-readable census exists; a path would be FDA/NIH Office of History
    annual-report license counts. Until then, zero rows are asserted — do not
    fill this with names from secondary literature.

## Standing rules (do not reverse)

- **No pre-1939 decision row, ever.** The 1906 Act created no application and
  no approval; the NDA was created by the 1938 FD&C Act (21 U.S.C. 355(a)).
  A pre-1938 approval table would have to be fabricated.
- Where the official record is silent, **publish the silence plus the evidence
  line that establishes it** — never a plausible-looking row.
- Flagged irregularities keep their verbatim row and are **never corrected**:
  the five pre-1965 re-screening flags, the 1957 +2 official-series anomaly,
  `FLAG-LOWEST-APPLNO-APPROVED-1969` (NDA000004), the FDA(1930)/FSIS(1931)
  renaming conflict, and (v29) `FLAG-PRE-STATUTE-DATE` (ApplNo 060904,
  `1900-01-01`) plus the 8 `FLAG-UNDATED-ROW` rows. None is ever counted as a
  decision and none is "repaired" to a plausible date.
- **Drugs@FDA `Submissions.txt` publishes approval-family actions only (AP,
  TA).** Whole-table census: no RE / W / CR status exists in any of the
  193,810 rows. Do not re-introduce the "RE/W live here" claim;
  `non_ap_rows` is pinned at 0 in the windows and the builder aborts on any
  status outside {AP, TA, empty}.
- **A landed capture is never re-downloaded.** Every `zip_extract` job carries
  `skip_existing: true`; a new publication of the official file needs a new
  job file (new outdir) so both captures stay datable and SHA-pinned. Do not
  "refresh" the 1938-1979 windows in place.
- Every v28/v29 URL must be on the official allow-list (govinfo.gov, fda.gov,
  uscode.house.gov, accessdata.fda.gov, api.fda.gov, fsis.usda.gov). Adding a
  secondary source to a v28/v29 cell fails the verifier.
- Do not add Selacryn (or any literature-named candidate) without remaining
  FDA appl_no/date/class/priority — `NAMED_CANDIDATE_NOT_ADDED`.
- Do not invent missing NME names. Do not print per-decision likelihoods.
- Never bypass the SHA-256 re-hash gates in any builder.
- The NME master stays a year-table file: openFDA-backfill NMEs are joined into
  the core table, NOT merged into `fda_decisions_master.csv`.

## Infrastructure notes

- `.github/workflows/arena-data-fetch.yml` — per-branch concurrency; runner
  self-test first, then fetch, then v28/v29 build+verify, v27, v26, v23;
  commits `data/raw` and `data/*.csv`. Build steps use `if: always()`, so a
  runner failure does not block the builders, and the commit step pushes to
  the **branch** - runner commits land after the session PR has merged (runs
  32/33 did exactly that; their re-pinned windows were deliberately not
  merged).
- Actions log bodies cannot be read from the sandbox (the API redirects to
  blob storage that is unreachable); use `gh api .../check-runs` annotations
  + the steps API, then reproduce locally.
- Sandbox network: only `api.github.com` is reachable by `curl`. `fetch_page`
  worked in v28 and v29 (used for the statutes, 21 U.S.C. 355, the agency
  history pages, the Drugs@FDA data-files page + glossary and the three
  overview pages). Bulk payloads still go through the Actions runner.
- Row layout conventions: `openfda_orig_decisions_*/decisions_*.json` under
  `decisions`; `openfda_efficacy_supplements/suppl_*.json` under `supplements`;
  `openfda_approvals_2000_2010/*.json` under `results`.
- `scripts/run_fetch_jobs.py` derives the output directory from the **job file
  name**, not the job `id` — name the file the same as the `id` or the captures
  land in an unexpected folder.
