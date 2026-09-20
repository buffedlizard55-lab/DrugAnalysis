# Remaining work for the next session (written 2026-09-20, v23)

Branch: `arena/01a0bfa7-druganalysis`. This session built the complete 1977–1979
action register (**728 rows**, three named classes) with two independent verifiers,
added the project's first **CRL-level denominator** from FDA-published data
(458 letters, maturity-restricted cohorts), extended the validator and the
Actions workflow, and wired every new table into the site. **PR #42 is merged into
`main` (merge commit `42daaa3`, 2026-09-20 17:00 UTC)** and the Pages deployment
for that merge succeeded (run 35524487455).

Three-pass review after the first push (v23.2 / v23.3) fixed two real defects and
one engine gap before the merge:

* the CRL layer labelled 58 letters `NO_MASTER_ROW`, which was false for the 55
  whose letter date matches a hand-verified curated `C###` master row (those rows
  publish no application number). Now joined on **both** keys: 399
  application-keyed + **36 curated (letter date + corresponding company name)** +
  **19 flagged** candidates (`curated_candidate_ids`) + **3** with no curated row;
* `scripts/validate_data.py` carried a latent `errs.append` (undefined) in the
  `NOT_ON_FDA_NME_TABLE` guard — dead branch, a NameError if the pin ever moves;
* the engine's only CRL input was the unverified 0.81 assumption. The v23
  observation now ships as its own labelled prior (301/342 = 88.0%, Wilson lower
  84.1%) and a validator gate fails if the engine number drifts from the CSV.

## State right now (read this first)

| Layer | Path | Status |
|---|---|---|
| Decision table | `data/pre1980_fda_decisions.csv` | **173 rows, unchanged.** Selacryn / 018103 / 012043 are **not** in it |
| 1977–1979 register | `data/pre1980_1977_1979_original_actions.csv` | 728 rows = 170 tracked + 479 ANDA-excluded + 79 `KIND_UNRESOLVED`, each citing its source line |
| 1977–1979 actions | `data/pre1980_1977_1979_submission_actions.csv` | 5,483 rows (1,489 / 2,061 / 1,933), all status `AP` |
| Document index | `data/pre1980_1977_1979_application_docs.csv` | 899 rows across 120 applications |
| Year analysis | `data/pre1980_1977_1979_year_analysis.csv` | 3 rows with the verdicts, supplement mix, priority split, marketing census, caveats |
| CRL match | `data/crl_application_match.csv` | 458 rows; 327 later-ORIG observed; 40 conflict flags for human review; master link 399 application-keyed + 36 curated (date+company) + 19 flagged candidates + 3 no-key + 1 no-appl |
| CRL rates | `data/crl_year_base_rates.csv` | 25 rows incl. `ALL_MATURE_2Y` 301/342 = 88.0% (Wilson LB 84.1%) and `ALL_MATURE_3Y` 282/290 = 97.2% (LB 94.7%) |
| Verifiers | `scripts/verify_pre1980_year_register_v23.py`, `scripts/verify_crl_application_match_v23.py` | **7,164 checks / 0 errors** and **5,456 checks / 0 errors**; neither shares code with its builder |
| Validator | `scripts/validate_data.py` | **PASS, 0 errors** (1751 standing warnings); v23 gates are fail-closed, incl. the master-link status split (399/36/19/3/1) and the engine prior == published `ALL_MATURE_2Y` cross-file gate |

Official vs enumerated: **1977 25 vs 17 (−8 unnamed)**; **1978 17 vs 18 (+1 Motofen TYPE 1/4, CLOSED)**;
**1979 14 vs 13 (−1 named Selacryn, not added)**. `KIND_UNRESOLVED` 32/28/19; 1977 and 1979 have **0**
`KIND_UNRESOLVED` TYPE 1/1-4.

## Exact re-verify commands

```bash
python3 scripts/build_pre1980_decisions_v21.py        # 173-row decision table (unchanged)
python3 scripts/build_pre1980_focus_1977_1979_v22.py  # year-focus / gap ledger
python3 scripts/build_pre1980_year_register_v23.py    # 728 / 5,483 / 899 / 3 / sources
python3 scripts/verify_pre1980_year_register_v23.py   # expect 7164 checks, 0 errors
python3 scripts/build_crl_application_match_v23.py    # 458 rows + 25 rate rows
python3 scripts/verify_crl_application_match_v23.py   # expect 5456 checks, 0 errors
python3 scripts/validate_data.py                      # expect PASS (0 errors)
node --check assets/app.js
```

The Actions workflow runs the same chain (plus `validate_data.py`) on any push touching
`fetch_jobs/**`, so a runner-side regression fails the run instead of silently publishing.

## Next work, in priority order

1. **CRL↔PDUFA denominator matching** — still the engine's blocking limitation. The v23 layer
   is the first honest step (a published-subset cohort with maturity cuts), *not* the solution:
   the CRL dataset is not a census, one letter publishes no application number, and no committed
   source matches letters to action dates. Until that matching exists the engine gate stays and
   per-decision likelihoods remain refused.
2. **Name 1977×8 and confirm Selacryn as the 1979 NME.** Route: 1989 CDER *Offices of Drug
   Evaluation: Statistical Report* (pp. 152–199, FDA History Office Files) or the contemporaneous
   FDA annual report. Contacts: FDA Historian john.swann@fda.hhs.gov;
   CDER.NMENewBiologicApprovals@fda.hhs.gov. Public Drugs@FDA / openFDA / remaining FDA files are
   exhausted for naming purged NMEs (018103 is the proof).
3. **1965–1975 shortfalls (−52)** — same typescript route. The 6 NME-comparable `KIND_UNRESOLVED`
   rows (014262 / 016486 / 016771 / 017383 / 017024 / 017267) stay review candidates, never approvals.
4. **Pre-1965 backward extension** — `fetch_jobs/drugsatfda_data_files_1938_1964.json` is queued:
   it windows Submissions/Applications/Products/ApplicationDocs to 1938–1964 so the same register
   and verifier can run on the 566 committed 1939–1964 ORIG/AP payload rows. The runner's filter
   types have not yet been exercised on a real run — watch the first run for a job-type error.
5. **40 CRL conflict rows** — 29 "later original action observed while FDA's field is not Approved"
   and 11 "FDA field Approved, no later original action in committed coverage". Each needs a human
   read of the linked FDA letter; do not auto-resolve either direction.
6. **Tambocor 1985 review PDF (human, 2 minutes)** —
   `https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf`
   (Wayback 20240929073454). Automated read returns HTTP 500.
7. **NDA022046 lineage artifact** — 1983 approval letter or Federal Register notice.
8. **141 core-analysis listing-class disagreements** — period 10-K/20-F cover evidence; keep the
   `CORE_CLASS_BASELINE` ratchet.
9. **2013 second half** — CDER posted list (27) is captured; do not add Simponi Aria.
10. **1,000 new 2000–2026 NME entries** — still blocked. The NME master already matches the official
    series; growth comes from supplements / originals / prices / pre-1980 backfill. Do not invent rows.
11. **Stock backlog** — 462 of 3,868 Yahoo items are still pending on the runner.
12. **Confirm the runner re-verified the merged tip.** The push that carried the v23.1
    workflow change queued Actions run `35523666004`; it starts after the older
    in-progress run finishes and re-runs both v23 builders, both verifiers and
    `validate_data.py` on the runner against the branch tip that was merged. Check
    its conclusion first; the runner also commits `data/raw` + `data/*.csv` back to
    **this branch only**, so `main`'s raw payloads can lag the branch's by design.

## Standing rules (do not reverse)

- Do not add Selacryn (or any literature-named candidate) to `pre1980_fda_decisions.csv` without
  remaining FDA appl_no/date/class/priority. Pattern: `NAMED_CANDIDATE_NOT_ADDED`.
- Do not invent missing NME names. Do not print per-decision likelihoods.
- Do not "fix" the dual-run SHA invariant (`pages[0].raw_sha256` 1975–1979). Do not `json.dump`
  any `fetch_jobs/**` file — targeted line edits only.
- Never bypass the SHA-256 re-hash gate in the v23 builders: it is what ties a published cell to
  the official file the runner recorded.
- `KIND_UNRESOLVED` rows are undecidable with the committed sources (no `Applications` record
  anywhere in the Drugs@FDA database). They are review candidates, never approvals.
- Validator gap-candidate allowlist is `{NDA050495, NDA018103, ""}` — still exactly one row per
  year 1965–1979.

## Infrastructure notes

- `.github/workflows/arena-data-fetch.yml` — per-branch concurrency; builds and verifies v23 tables
  and runs `validate_data.py`; commits `data/raw` and `data/*.csv`.
- The sandbox has no general outbound network (only `api.github.com`): all bulk fetching goes
  through the Actions runner.
- `data/raw/openfda_approvals_2000_2010/*.json` rows live under `results`; `openfda_efficacy_supplements/suppl_*.json`
  under `supplements`; `openfda_orig_decisions_*/*.json` under `decisions`.
