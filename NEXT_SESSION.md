# Remaining work for the next session (written 2026-09-21, v26)

Branch: `arena/01a0c21f-druganalysis` (merged to main 2026-09-21). This session
(v26) completed the **backward extension before the previous earliest year**:
the project's verified FDA decision coverage now reaches **1939** — the start
of the Drugs@FDA database — with 535 verified original-approval rows
(1939-1964), 178 of them NME-comparable (Type 1 / Type 1-4), a 26-row year
register reconciled verbatim against FDA's official series, a 26-row era
analysis, an independent 16,157-check verifier, a new validator gate, and the
site's **Pre-1965 Era** tab. A **535-item per-row live-probe job** was pushed
and the Actions runner commits the captures to
`data/raw/pre1965_row_probes_1939_1964/` (check `data/raw/last_run.log` and
the branch for the landed captures; the builder auto-joins them on its next
run and the probe index table `data/pre1965_row_probe_index.csv` then appears).

## State right now (read this first)

| Layer | Path | Status |
|---|---|---|
| Master decisions | `data/fda_decisions_master.csv` | 1,427 rows (1985-2026, unchanged) |
| Original non-NME | `data/fda_original_non_nme_decisions.csv` | 3,432 rows (unchanged) |
| Supplement decisions | `data/fda_supplement_decisions.csv` | 4,482 rows (unchanged) |
| CRL master | `data/fda_crl_master.csv` | 458 rows (unchanged) |
| Core analysis | `data/core_analysis_table.csv` | 1,933 rows (unchanged) |
| Clinical scorecards | `data/company_clinical_trial_scorecard.csv` | 423 rows (unchanged) |
| Stock snapshots | `data/stock_price_snapshots.csv` | 2,848 rows (unchanged) |
| Phase 3 registry | `data/clinical_trials_phase3_registry.csv` | 2,000 rows (unchanged) |
| Pre-1985 | `data/pre1985_fda_decisions.csv` | 91 rows (1980-1984, unchanged) |
| Pre-1980 | `data/pre1980_fda_decisions.csv` | 173 rows (1965-1979, unchanged) |
| **Pre-1965 (NEW v26)** | `data/pre1965_fda_decisions.csv` | **178 rows (1939-1964 NME-comparable; counted-once 173)** |
| **Pre-1965 census (NEW v26)** | `data/pre1965_originals_audit_1939_1964.csv` | **535 rows (every ORIG/AP row 1939-1964)** |
| **Pre-1965 register (NEW v26)** | `data/pre1965_year_register.csv` | 26 rows (per-year census vs official series) |
| **Pre-1965 era (NEW v26)** | `data/pre1965_era_analysis.csv` | 26 rows |
| Pre-1965 probe index | `data/pre1965_row_probe_index.csv` | appears when the runner's 535 probes land + builder re-run |
| Pre-1965 probes (raw) | `data/raw/pre1965_row_probes_1939_1964/` | 535 captures land via the Actions runner on push (job `fetch_jobs/pre1965_row_probes_1939_1964.json`) |
| Verifiers | `scripts/verify_pre1965_year_register_v26.py`, `scripts/verify_pre1980_year_register_v23.py`, `scripts/verify_crl_application_match_v23.py` | v26: **16,157 checks, 0 errors**; v23 pair unchanged |
| Validator | `scripts/validate_data.py` | **PASS, 0 errors** (v26 gate added) |

## v26 changes this session

1. **1939-1964 decision tables** (new, from the already-committed,
   SHA-manifested openFDA payloads `data/raw/openfda_orig_decisions_1939_1964/`):
   - `scripts/build_pre1965_decisions_v26.py` (fail-closed: payload SHA vs
     manifest, count-field consistency, decision_date-in-year, full-DB
     type/holder cross-check that aborts on any mismatch). Writes the four
     tables above. Auto-joins the live probes when their manifest exists.
   - Full official-database cross-check: **535/535 applications present in
     `Applications_all_types.txt` (29,336 apps), 0 type mismatches, 0 holder
     mismatches** — recorded per row in `full_db_holder_match`.
   - Official series quoted verbatim per year from
     `data/fda_official_year_series.csv` (FDA "Summary of NDA approvals and
     receipts, 1938-present"): 1941-1964 have per-year NME figures; 1938-40
     published combined (1,782 NDAs; NMEs 14 "1940 only"); 1939 has no
     official per-year figure. **1957 shows +2** (18 Type 1 rows vs 16
     official) — an excess of the 1969 +3 class, reported and pinned, never
     smoothed.
   - **Five irregularities flagged, never corrected** (validator pins all
     five): NDA008592 (1952 norepinephrine, after NDA007513 1950-07-13),
     NDA010028 (1955 meprobamate, after NDA009698 1955-04-28), NDA009149
     (1957 chlorpromazine, after NDA011120 1957-09-18 — earlier original
     absent from the payloads: coverage gap), NDA012265 (1960 reserpine,
     after NDA009296 1954-04-01), NDA012486 (1962 chlorprothixene, sibling of
     NDA012487 1962-03-23). Counted-once statistic: 173 (178 rows minus the 5).
   - Historical facts in the era table are source-checked: 1939 first heparin
     NDA (NDA000552, Federal Register 91 FR 2026-03-09), Premarin NDA 004782
     1942 (HHS-OIG 1997 report; Pfizer 2018 petition), thalidomide 1961
     (application pending, never approved, withdrawn 1962), Kefauver-Harris
     enacted 1962-09-22 with per-approval dating.
2. **Per-row live probes queued (535)** —
   `fetch_jobs/pre1965_row_probes_1939_1964.json` (deterministically
   generated by `scripts/gen_pre1965_probe_job_v26.py`; regenerate before
   pushing any payload change). On push the runner commits the captures;
   the builder auto-joins (date/class/priority/holder field-by-field;
   mismatch aborts; empty live record → `ABSENT_LIVE` flag; no ORIG-AP on the
   payload date → `NO_ORIG_AP_LIVE` flag). Expect some ABSENT_LIVE rows —
   that is the Seldane-class invisibility surfacing in the pre-1965 era,
   exactly what the flag is for.
3. **Validator v26 gate** (`scripts/validate_data.py`): re-derives per-year
   payload counts, pins 535/178/26/26, cross-checks the decision table
   against the payload TYPE 1/1-4 enumeration, enforces source-URL /
   ticker / indication discipline, pins the five re-screening flags and the
   1957 +2 anomaly, and (when the probe manifest is complete at 535/535)
   requires every row resolved.
4. **Site**: new **Pre-1965 Era** tab (register, 178-row decisions, 535-row
   audit, era analysis, probe index) — `index.html` + `assets/app.js`
   (`node --check` clean). The Pre-1980 tab's earliest-year claim now points
   at 1939.
5. **Workflow**: v26 step (build → auto probe-join → verify → validate)
   added to `.github/workflows/arena-data-fetch.yml`.

## Exact re-verify commands

```bash
python3 scripts/build_pre1965_decisions_v26.py   # expect "535 audit rows ... 178 NME-comparable ... counted-once 173, 5 flags"
python3 scripts/verify_pre1965_year_register_v26.py  # expect "16,157 checks, 0 errors" (more once probes land)
python3 scripts/validate_data.py                 # expect PASS (0 errors)
node --check assets/app.js                       # expect clean
```

## Next work, in priority order

1. **Land the 535 live probes** (should already be committed to this branch
   by the time you read this — the runner runs on push and the job's
   `skip_existing: true` retries stragglers on the next push). Re-run
   `build_pre1965_decisions_v26.py` + the verifier once the captures exist;
   the probe index table then populates on the site. Triage any
   ABSENT_LIVE / NO_ORIG_AP_LIVE rows (named invisibility class, never
   auto-corrected).

2. **Submissions-level census for 1938-1964** — the queued job
   `fetch_jobs/drugsatfda_data_files_1938_1964.json` (zip_extract of the
   official Drugs@FDA data files, Submissions filtered to 1938-1964 plus the
   application/product/document windows, same discipline as the 1965-1979
   window) should also have run on this session's push; check
   `data/raw/drugsatfda_data_files_1938_1964/`. When the window lands, build
   the 1938-1964 submission-action register (every status: AP, RE, W, …) —
   this is where the **non-approval decisions** (rejections/withdrawals) for
   the period live, and it is the step that turns the 535-row approval census
   into the full decision census the task asked for (and the main path to
   the 1,000-new-entry target: 535 approvals + submission-level rows).

3. **1938 determination** — with the 1938-1964 Submissions window in hand,
   establish whether the official database contains any 1938 submission
   action (the FDA official series starts 1938). If yes: name the rows
   verbatim; if no: write the negative result into the year register (a
   documented boundary, not an omission).

4. **Ticker/exchange resolution for the 290 v24 backfill entries** (v25's
   top item, still open): match openFDA sponsor names against the committed
   SEC list (`data/raw/probe/sec_company_tickers_alt.json`) with
   `sponsor_resolution_basis` per row; then Yahoo Finance snapshots via the
   runner; then rebuild scores/core so prices flow in.

5. **Pre-1965 corporate lineage** (optional, research-heavy): for the 178
   NME holders of record, resolve approval-era applicants vs current holders
   only where a primary source pins it (most pre-1965 applicants are not
   current listed issuers; no inference — the standing rule).

6. **Year register update** — rebuild `data/fda_orig_year_register.csv` to
   reflect post-v24 per-year counts (still pins pre-v24 counts; validator
   allows the +290 delta).

7. **CRL↔PDUFA denominator matching** — still the engine's blocking
   limitation (CRL dataset is a published subset, not a census).

8. **40 CRL conflict rows** — need human review of linked FDA letters.

9. **141 core-analysis listing-class disagreements** — period 10-K/20-F cover
   evidence (validator §7 ratchet baseline 141).

10. **Stock backlog** — 462 of 3,868 Yahoo items still pending on the runner.

11. **242 v24 rows that duplicate the master** — openFDA names the current
    application holder, not the historical applicant; do not "fix" master
    values without primary evidence.

## Standing rules (do not reverse)

- Do not add Selacryn (or any literature-named candidate) to the decision
  tables without remaining FDA appl_no/date/class/priority.
  Pattern: `NAMED_CANDIDATE_NOT_ADDED`.
- Do not invent missing NME names. Do not print per-decision likelihoods.
- Do not "fix" the dual-run SHA invariant (`pages[0].raw_sha256` 1975-1979).
- Never bypass the SHA-256 re-hash gates in any builder.
- `KIND_UNRESOLVED` rows are undecidable with committed sources. Review
  candidates, never approvals.
- The NME master stays a year-table file: openFDA-backfill NMEs are joined
  into the core table, NOT merged into `fda_decisions_master.csv`.
- v26: flagged re-screening rows (the five) keep their verbatim row and are
  excluded only from the counted-once statistic — never "corrected".
- v26: 1938 gets rows only if the official 1938-1964 Submissions window
  actually contains 1938 actions; otherwise the boundary is documented.

## Infrastructure notes

- `.github/workflows/arena-data-fetch.yml` — per-branch concurrency; now
  builds and verifies the v26 tables (with auto probe-join) on every push
  alongside the v23 tables; commits `data/raw` and `data/*.csv`.
- The sandbox has no general outbound network (only `api.github.com`): all
  bulk fetching goes through the Actions runner. Agent-side `fetch_page`
  was broken in the 2026-09-21 session (proxy error) — rely on
  web_search for spot citations and the runner for payloads.
- `data/raw/openfda_orig_decisions_1939_1964/*.json` rows live under
  `decisions`; `openfda_efficacy_supplements/suppl_*.json` under
  `supplements`; `openfda_approvals_2000_2010/*.json` under `results`;
  `openfda_orig_decisions_*/*.json` under `decisions`.
