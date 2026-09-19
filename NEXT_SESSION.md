# Remaining work for the next session (written 2026-09-19 v19)

The v19 branch is `arena/01a0bad8-druganalysis` (branched from `main` at `b105d17`). This session verified pre-1980 years 1977–1979 line by line (48 rows), imported the full 1965–1979 payload blocks, ingested 1,869 stock snapshots and 6,452 Phase 3 studies, adjudicated the 2013 −2 gap, and shipped a decision-engine completeness spine. Merge the v19 PR before starting new edits. Repository root: `/home/user/DrugAnalysis`.

## What v19 shipped

- **Pre-1980 payloads imported (1965–1979, 15 files + 3 manifests)** — copied from `origin/arena/01a0b7f7-druganalysis` (Actions run 19); every file SHA-verified against its manifest; all 15 raw responses proven byte-identical to the independent run-18 fetch (~2h earlier) with identical decision arrays. Imported data is verbatim official bytes only — no derived tables were copied.
- **`data/pre1980_fda_decisions.csv` (48 rows)** — 1977 ×17, 1978 ×18 (incl. Type 1/4 Motofen), 1979 ×13. Same schema as the pre-1985 table. No ticker, no indication, no lineage asserted anywhere. Fail-closed builder: `scripts/build_pre1980_decisions_v19.py` (SHA + dual-run + display-map + 1965–1979 first-appearance screen; idempotent).
- **`data/pre1980_year_audit.csv` / `data/pre1980_era_analysis.csv`** — verdicts 1977 −8 `PROJECT_SHORT_FLAGGED`, 1978 +1 `PROJECT_EXCEEDS_OFFICIAL` (the +1 is Motofen; Type-1-only = 17 = official), 1979 −1 `PROJECT_SHORT_FLAGGED`. Official: 25/17/14 NMEs (63/86/94 NDAs).
- **`data/pre1980_primary_captures_index.csv` (12 captures)** — 3 year populations re-queried live (662/756/746, all equal to manifests); verbatim ORIG blocks for Elspar, Motofen (TYPE 1/4), Cyclapen NDA050508 (TYPE 1), Cyclapen NDA050509 (TYPE 3), Forane, Kinlytic (UNKNOWN/UNKNOWN); Tagamet cross-checked on Drugs@FDA (08/16/1977, Type 1, PRIORITY); coexistence probes for Tagamet/Nolvadex. Evidence: `data/raw/source_captures_2026_09_19/live_primary_captures_v19_2026_09_19.json`; run-18 manifest archived alongside for self-contained dual-run proof.
- **Irregularities closed, not smoothed**: Cyclapen tablet-Type-3-before-suspension-Type-1 inversion (genuine FDA-data condition, counted once); Kinlytic urokinase UNKNOWN-candidate (flagged, NOT counted); 1978 Motofen boundary; 1979 blanks inventoried (furosemide→1966, IV electrolytes, KI-Thyro-Block).
- **2013 −2 adjudicated**: the archived CDER 2013 NME table re-read in full (27 rows transcribed verbatim + the Simponi Aria correction footnote) — the master's 27 match CDER's posted 27 exactly, so the gap is inter-FDA-source (History series 29 vs CDER list 27). Dated note appended to the crosswalk 2013 row by `scripts/annotate_v19_2026_09.py` (additive, idempotent). Simponi Aria must NOT be added.
- **+1,869 stock snapshots (979 → 2,848)** from the three `stock_yahoo_*_remaining` batches (2,636 SHA-verified captures; 364 FAILED preserved as unavailable). **Phase 3 expanded registry 4,212 → 10,664** (2024–2029 windows). Total new verified entries this session: **8,369**.
- **`data/decision_engine_year_inputs.csv` (50 rows, 1977–2026)** — per-year completeness ratios; 17 FULL-use years; engine tab carries the data-quality gate + the explicit refusal to print numerator-only likelihoods before CRL↔PDUFA matching.
- **Core + scores refresh (Pass 3)** — `build_company_scores.py` → `build_core_analysis_table.py` rerun on the enlarged snapshot set (core unmatched 356 → 329; 89/751 score rows updated). Rule restated: any snapshot/master/CRL change requires re-running scorecard → core → company-scores builders, then the validator.
- **Validator v19 gates**: PASS, 0 errors — pins the 48-row table, payload agreement, verdicts, 12 captures, 2013 note, engine inputs.
- **Site**: new 🏛️ Pre-1980 Era tab (audit, decisions, era, captures) + Overview card + engine gate notice. All 34 mounts / 26 tabs integrity-checked; JS syntax-checked; served locally with all new CSVs 200.

## Verification already run

```text
python3 scripts/build_pre1980_decisions_v19.py        # 48/3/3/12; rerun = no-op
python3 scripts/build_decision_engine_inputs_v19.py   # 50 year rows; rerun = no-op
python3 scripts/annotate_v19_2026_09.py               # crosswalk 2013 note; rerun = no-op
python3 scripts/build_stock_snapshots_from_all_events.py  # +1869; rerun appends 0
python3 scripts/build_ctgov_expanded_registry.py      # 10664 rows
python3 scripts/validate_data.py                      # PASS: 0 errors
node --check assets/app.js                            # JS syntax OK
```

## Next work, in priority order

1. **Pre-1980 years 1976 → 1965.** Payloads are committed; Type-1 counts per year are known (1976: 21, 1975: 9, 1974: 16, 1973: 11, 1972: 7, 1971: 7, 1970: 11, 1969: 8, 1968: 4, 1967: 13, 1966: 7, 1965: 11). Extend `build_pre1980_decisions_v19.py` (or a v20 successor) with explicit display maps + first-appearance assertions per year, working backward one year at a time with live spot probes. The 1965–1974 manifests verify the same way.
2. **Name the missing NMEs: 1977 ×8, 1979 ×1 (plus 1980–84, 1988 ×1).** Same route as before: the 1989 CDER *Offices of Drug Evaluation: Statistical Report* (pp. 152–199, FDA History Office Files) or the contemporaneous FDA annual report. Contacts: FDA Historian john.swann@fda.hhs.gov; CDER factual-error address CDER.NMENewBiologicApprovals@fda.hhs.gov.
3. **2013 −2, second half.** The CDER posted list (27) is now fully captured; check the **2013 NDA/BLA calendar-year approvals page** to see which 2 the History Office series counts. Do not add Simponi Aria (FDA: "inadvertently posted").
4. **CRL↔PDUFA denominator matching.** The engine's blocking limitation: match `fda_crl_master.csv` rows to PDUFA action dates so priority-conditioned approval likelihoods can be computed from a matched set instead of refused. Until then the engine-gate notice stays.
5. **Tambocor 1985 review PDF (human, 2 minutes).** `https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf` or Wayback `https://web.archive.org/web/20240929073454/https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf` — read the review classification block. Do not harmonise without it.
6. **NDA022046 lineage artifact** — still open; needs a 1983 approval letter or Federal Register notice.
7. **141 core-analysis listing-class disagreements** — adjudicate with period 10-K/20-F cover evidence. Keep the `CORE_CLASS_BASELINE` ratchet.
8. **Pre-1980 non-Type-1 enumeration audit** — mirror the 517-row focus-year audit for 1977–1979 (170 payload ORIG/AP rows: 42+66+62) so every pre-1980 original is tracked in exactly one table. The `expand_pre1980_decisions.py` + non-NME builder path exists but writes into the pre-1985 table — a schema decision is still needed (separate pre-1980 non-NME table recommended).

## Important repository facts

- Branch for all work: `arena/01a0bad8-druganalysis` (this session fixed to it); origin `https://github.com/buffedlizard55-lab/DrugAnalysis.git`.
- Single-writer discipline: `build_pre1980_decisions_v19.py` owns the four pre-1980 tables; `annotate_v19_2026_09.py` owns the v19 crosswalk note; `build_decision_engine_inputs_v19.py` owns the engine year inputs; stock ingestion via `build_stock_snapshots_from_all_events.py`; ctgov via `build_ctgov_expanded_registry.py`. Do not hand-edit owned files.
- `data/fda_decisions_master.csv` (1,427 comparable rows, 1985–2026), `data/pre1985_fda_decisions.csv` (91 rows, 1980–1984) and `data/pre1980_fda_decisions.csv` (48 rows, 1977–1979) keep their roles. Do not merge them without a deliberate schema/scorecard decision.
- Data-fetch convention: bulk jobs run through GitHub Actions; the sandbox page-fetch tool works for `accessdata.fda.gov` HTML, `drugsatfda_docs` label PDFs, `api.fda.gov` JSON and Wayback captures (one-off checks; keep quotes verbatim). `api.fda.gov` `count=` on nested submission fields returns NOT_FOUND — use `limit=1` + `meta.total` instead. Bash has no outbound network (TLS blocked). `gh workflow run` dispatch is 403 for the bot token — push-to-`arena/**` touching `fetch_jobs/**` is the trigger path.
- Pre-1980 raw payloads on disk came from `origin/arena/01a0b7f7-druganalysis` (Actions run 19) with `origin/arena/01a0b7e1-druganalysis` (Actions run 18) as the cross-check — both are the same bot workflow's verbatim output, SHA-pinned. If those branches are ever deleted, the manifests + archived run-18 manifest in this repo preserve the provenance chain.

---

## v20 session addendum (2026-09-19, later the same day) — RESUME HERE

**Where this session stopped:** the sandbox's GitHub token expired mid-run
(`gh auth status` → "token in GH_TOKEN is no longer valid"; `git push`/`git fetch`
fail). All work through that point is committed locally on
`arena/01a0baff-druganalysis` at `67088ef` (part 1 of v20). Reconnect GitHub in
Arena, then execute the checklist below in order.

**What was already done (committed):**
1. `fetch_jobs/drugsatfda_data_files_2026_09.json` + new `zip_extract` kind in
   `scripts/run_fetch_jobs.py` (verbatim member/row whitelists, full member
   SHA + kept-row counts + recorded filter, per-member output budget). Pushed
   as `dc22bca`; Actions run 35462829803 was still executing at token loss
   (fda.gov media/89850 was returning HTTP 500 to the sandbox fetcher, so the
   zip may have FAILED after retries — check `data/raw/last_run.log` and the
   manifest entries).
2. `fetch_jobs/pre1980_row_probes_1977_1979.json` — 170 single-application
   live probes (one per payload row), generated by
   `scripts/gen_pre1980_probe_job_v20.py`.
3. `scripts/build_pre1980_originals_audit_v20.py` + tables (part 1):
   `data/pre1980_originals_audit_1977_1979.csv` (170 rows: 42/66/62;
   NME-comparable 17/18/13), `data/pre1980_row_probe_index.csv` (170),
   staging report. Fail-closed builder, fixture-tested end-to-end including
   SHA-drift and probe-mismatch aborts.
4. Validator v20 gates + Pre-1980 site tab (originals audit / probe index /
   full-DB cross-check tables) + overview card. JS syntax-checked.

**Resume checklist (in order):**
1. Reconnect GitHub in Arena. `git fetch origin arena/01a0baff-druganalysis`
   and inspect what run 35462829803 committed (expect
   `data/raw/pre1980_row_probes_1977_1979/` (170 probes + manifest) and
   possibly `data/raw/drugsatfda_data_files_2026_09/`).
2. If the zip layer FAILED (likely — fda.gov media 500): re-point the job at
   a Wayback `id_` capture of
   `https://www.fda.gov/media/89850/download?attachment` (find a timestamp via
   the CDX API; the runner's IP is not rate-limited), push to re-trigger, or
   retry the same job if fda.gov recovered (skip_existing=True protects the
   probes).
3. `git pull --rebase`; run `python3 scripts/build_pre1980_originals_audit_v20.py`
   (must report probes complete + full-DB cross-checked), then
   `python3 scripts/validate_data.py` (0 errors required).
4. Read `data/pre1980_full_db_crosscheck_1977_1979.csv`: every
   `in_openfda_payload=FALSE` row is a NAMED payload-invisible approval.
   NME-comparable ones (Type 1/1-4) are the missing-NME candidates for
   1977×8 / 1979×1 — cross-check each against the Drugs@FDA website page and
   the year's official count before touching any verdict.
5. Update `data/pre1980_year_audit.csv` / `pre1980_era_analysis.csv` notes and
   the README v20 section with the outcomes; do NOT modify v19 verdicts
   without naming evidence.
6. Three review passes, then PR `arena/01a0baff-druganalysis` → `main` and
   merge (this session could not reach that step).

**Primary-source findings banked this session (all verbatim-checkable):**
- Seldane-class invisibility is now proven on THREE official surfaces:
  openFDA `drug/drugsfda` NOT_FOUND for NDA019180; openFDA `drug/label`
  NOT_FOUND; Drugs@FDA website overview page renders empty (live 2026-09-19).
  NDA050452 likewise NOT_FOUND on openFDA + empty website page.
- NCATS Inxight (NIH) records carry "First approved in YYYY" with FDA source
  URLs and cite an official FDA **"OB NME Appendix 1950-1985/1993"** (the
  printed Orange Book NME appendix) — a lead for naming ALL pre-1985 missing
  NMEs if a scan surfaces (archive.org holds 1995/1997 OB editions;
  DrugPatentWatch holds PDFs from 1980).
- Amikacin (Amikin) = NDA050495 per NCATS, "First approved in 1976", absent
  from every 1965-1979 payload (verified against the first-appearance index)
  → the concrete, sourced first candidate for the **1976** gap (21 official
  NMEs vs 21 payload Type-1s — reconcile when 1976 is built).
