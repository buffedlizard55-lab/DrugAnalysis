# Remaining work for the next session (written 2026-09-21, v28)

Branch: `arena/01a0c638-druganalysis`. This session (v28) answered the task
"expand, add and analyse FDA decisions **before the earliest year currently in
the project**". After v26/v27 that year was **1939**, so v28 does not invent
anything earlier: it **proves the boundary** from committed official primary
sources, **exhaustively enumerates** everything the official database holds
below it, documents **year by year 1902-1938** what actually governed drugs
before the approval system existed, and **corrects two false claims** that were
in the repository (one published by v27, one written in this session's own
first draft and caught by the new verifier).

**Earliest verified FDA drug-approval action: 1939-02-09, NDA000552
(ORIG 1, AP, class 19). 0 actions dated 1938. Nothing earlier exists in any
official record this project can cite, and no pre-1939 decision row is asserted
anywhere.**

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
| **Pre-1939 boundary (NEW v28)** | `data/pre1939_boundary_determination.csv` | **12 evidence lines** |
| **Pre-1939 application census (NEW v28)** | `data/pre1939_application_census.csv` | **2 rows** (NDA000004, NDA000159 — exhaustive) |
| **Pre-1939 regulatory register (NEW v28)** | `data/pre1939_regulatory_register_1902_1938.csv` | **37 rows** (1902-1938, 0 decisions each) |
| **Pre-1939 status census (NEW v28)** | `data/pre1939_submission_status_census.csv` | **41 rows** (all AP; Drugs@FDA publishes no RE/W) |
| Pre-1939 runner captures | `data/raw/drugsatfda_pre1939_census_v28/` | **PENDING** — lands on the next Actions run (job `fetch_jobs/drugsatfda_pre1939_census_v28.json`) |
| Verifiers | `verify_pre1939_boundary_v28.py` **2,428 checks / 0 errors** · `verify_pre1965_year_register_v26.py` 22,105 / 0 · `verify_pre1980_year_register_v23.py` 7,164 / 0 · `verify_crl_application_match_v23.py` 5,456 / 0 | all green |
| Validator | `scripts/validate_data.py` | **PASS, 0 errors** (1,751 warnings = standing baseline) |
| Site | `index.html` + `assets/app_v27.js` | 11 tabs; new **🏛️ Pre-1939 Boundary** tab; `node --check` clean |

## v28 changes this session

1. **Pre-1939 boundary tables** — `scripts/build_pre1939_boundary_v28.py`
   (fail-closed: input SHA-256 vs runner manifests, 29,336-row application map,
   0 rows dated 1938, earliest date 1939-02-09 on ApplNo 000552, all statuses
   `AP`, payload block starts 1939, v27 register reproduces the official
   extract key-for-key — any drift aborts). Writes the four tables above.
   Auto-joins the runner captures when their manifest lands and **aborts** on
   any disagreement with the window facts.
2. **Two corrections.**
   - *Published by v27:* the site and README said
     `data/fda_1938_1964_full_submission_register.csv` held "ORIG/AP plus
     RE, W, etc." and that "non-approval decisions (rejections/withdrawals)
     live" there. **Re-counted: 0 non-AP rows in all 1,215** (850 ORIG +
     365 SUPPL, all `AP`). The official Drugs@FDA `Submissions.txt` publishes
     approval actions only. Site, README and evidence line `PRE1939EV-08`
     corrected; the validator now fails the build if a non-AP row ever appears.
   - *Written in this session's own draft:* NDA000004 was described as tracked
     in `data/pre1980_fda_decisions.csv`. **The verifier rejected it** — that
     table is Type 1 / 1-4 NME rows only and NDA000004's class is UNKNOWN.
     Correct location `data/pre1980_originals_audit_1965_1976.csv` row
     `PRE1980AUDIT-1969-10`. This is the verifier doing its job; keep it.
3. **Independent verifier** `scripts/verify_pre1939_boundary_v28.py` (shares no
   code with the builder): re-hashes inputs, recomputes every fact, reproduces
   **every cell of all four tables**, and enforces an official-host allow-list
   on every URL in every cell (137 citations). Mutation-tested: a fabricated
   1937 decision count and a Wikipedia statute URL both fail.
4. **Validator v28 gate** — pins register shape (exactly 1902-1938, `0`
   decisions/year), the four Statutes-at-Large citations and dates, census
   shape (`[000004, 000159]`), the 1930/1931 conflict flag + FSIS citation,
   status-census sums, `non_ap_rows == 0`, and the absence of
   likelihood/probability/ticker columns.
5. **Runner job + 5 new recorded row selectors** in `scripts/run_fetch_jobs.py`
   (`date_year_before`, `date_unparseable`, `applno_in_list`,
   `applno_numeric_below`, `column_counts`), each exercised end-to-end through
   the real job code path against a synthetic official-shaped ZIP first. The
   exercise caught and fixed a variable-shadowing bug (`want` used for both the
   member spec and a value set) before the job was ever pushed.
6. **Site**: new **🏛️ Pre-1939 Boundary** tab (KPIs + the four tables, every
   row expandable with method / observed value / SHA prefix / official link);
   corrected the Historical tab's register description; hero and overview KPI
   now driven live from the register CSV.
7. **Workflow**: v28 build → verify → validate step added **ahead of** the v27
   step in `.github/workflows/arena-data-fetch.yml`.

## Exact re-verify commands

```bash
python3 scripts/build_pre1939_boundary_v28.py   # 12 evidence, 2 census, 37 register, 41 status
python3 scripts/verify_pre1939_boundary_v28.py  # expect "2,428 checks, 0 error(s)"
python3 scripts/validate_data.py                # expect PASS (0 errors)
python3 scripts/verify_pre1965_year_register_v26.py   # expect 22,105 checks, 0 errors
node --check assets/app_v27.js                  # expect clean
```

## Next work, in priority order

1. **Land the pre-1939 runner captures.** Job
   `fetch_jobs/drugsatfda_pre1939_census_v28.json` (6 extracts) runs on the
   next push. When `data/raw/drugsatfda_pre1939_census_v28/manifest.json`
   exists the builder auto-joins and evidence line `PRE1939EV-12` is replaced
   by a real whole-table result. Then:
   - confirm `Submissions_before_1939.txt` has **0** rows (the builder aborts
     if it does not — that would mean the 1939 boundary is wrong);
   - report the **undated-row count** (`Submissions_undated.txt`): this is how
     many rows no year filter in this repository could ever see, and it is the
     only remaining scope caveat on the "0 rows in 1938" claim;
   - confirm the whole-table `SubmissionStatus` census is `AP`-only, which
     upgrades the RE/W correction from "true in both committed windows" to
     "true in the complete official table".
2. **CRL↔PDUFA denominator matching** — still the decision engine's blocking
   limitation. The CRL dataset is a published subset (458 letters, 2011+), not
   a census, so per-decision likelihoods are still refused by design. v28 made
   this worse in a useful way: it proved refused/withdrawn actions cannot be
   read out of Drugs@FDA `Submissions.txt` at all, so the CRL database is the
   *only* source. Closing this needs a targeted capture of FDA's CRL list per
   fiscal year plus PDUFA goal dates.
3. **Ticker/exchange resolution for the 290 v24 backfill entries** (open since
   v25): match openFDA sponsor names against the committed SEC list
   (`data/raw/probe/sec_company_tickers_alt.json`) with a
   `sponsor_resolution_basis` per row, then Yahoo snapshots via the runner,
   then rebuild scores/core so prices flow in.
4. **40 CRL conflict rows** — need human review of the linked FDA letters.
5. **141 core-analysis listing-class disagreements** — period 10-K/20-F cover
   evidence (validator §7 ratchet baseline 141).
6. **Stock backlog** — remaining Yahoo items pending on the runner.
7. **242 v24 rows that duplicate the master** — openFDA names the *current*
   application holder, not the historical applicant; do not "fix" master values
   without primary evidence.
8. **Year register refresh** — rebuild `data/fda_orig_year_register.csv` for
   post-v24 per-year counts (still pins pre-v24 counts).
9. **Repository hygiene** — `index_v27.html` and `assets/app.js` (2,767 lines)
   are no longer referenced by `index.html`; `.venv/` (~5,600 files) is
   committed and is not in `.gitignore`. Neither is load-bearing for the site,
   but both should be removed or ignored before the tree grows further.
   **Not touched this session** to keep the v28 diff auditable.
10. **1902-1938 biologic licenses** (research-heavy, optional): the only
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
  `FLAG-LOWEST-APPLNO-APPROVED-1969` (NDA000004), and the FDA(1930)/FSIS(1931)
  renaming conflict.
- **Drugs@FDA `Submissions.txt` publishes approvals only.** Do not re-introduce
  the "RE/W live here" claim; `non_ap_rows` is pinned at 0.
- Every v28 URL must be on the official allow-list (govinfo.gov, fda.gov,
  uscode.house.gov, accessdata.fda.gov, api.fda.gov, fsis.usda.gov). Adding a
  secondary source to a v28 cell fails the verifier.
- Do not add Selacryn (or any literature-named candidate) without remaining
  FDA appl_no/date/class/priority — `NAMED_CANDIDATE_NOT_ADDED`.
- Do not invent missing NME names. Do not print per-decision likelihoods.
- Never bypass the SHA-256 re-hash gates in any builder.
- The NME master stays a year-table file: openFDA-backfill NMEs are joined into
  the core table, NOT merged into `fda_decisions_master.csv`.

## Infrastructure notes

- `.github/workflows/arena-data-fetch.yml` — per-branch concurrency; v28
  build+verify now runs first, then v27, v26, v23; commits `data/raw` and
  `data/*.csv`.
- Sandbox network: only `api.github.com` is reachable by `curl`. **`fetch_page`
  works in this session** (it was broken on 2026-09-21 earlier) — it was used
  to read all four Statutes-at-Large PDFs, 21 U.S.C. 355, and both agency
  history pages. Bulk payloads still go through the Actions runner.
- Row layout conventions: `openfda_orig_decisions_*/decisions_*.json` under
  `decisions`; `openfda_efficacy_supplements/suppl_*.json` under `supplements`;
  `openfda_approvals_2000_2010/*.json` under `results`.
- `scripts/run_fetch_jobs.py` derives the output directory from the **job file
  name**, not the job `id` — name the file the same as the `id` or the captures
  land in an unexpected folder.
