# Remaining work for the next session (written 2026-09-17 v6)

This file is the hand-off for future development. The sandbox that edits the repo has **no general outbound network**. Every external fetch must go through GitHub Actions (`fetch_jobs/*.json` → `scripts/run_fetch_jobs.py` → `data/raw/<job>/` + SHA-256 manifest). Blank beats guessed.

## What this session shipped (v6)

- `data/company_clinical_trial_scorecard.csv` — **402 company scorecards** integrating Phase 3 trials (2026–2027 completion window), pipeline phase progression (advanced vs. clinical hold), and FDA conversion rates (NME, non-NME original approvals, efficacy supplements vs. CRLs). Builder: `scripts/build_clinical_trial_scorecard.py`.
- `data/sponsor_registry.csv` — Expanded from 171 to **265 sponsors (+94 exact mappings)**, mapping biopharmas from FDA and ClinicalTrials.gov to exact US tickers or verified Non-US / Private status.
- `data/fda_crl_master.csv` & `data/clinical_trials_phase3_registry.csv` — Regenerated with updated sponsor registry: **156 CRL rows** and **409 Phase 3 studies** resolved to US-listed issuers.
- `data/stock_price_snapshots.csv` — Expanded from 93 to **152 verified price snapshots** around FDA decision dates (cleaned staging files and eliminated test artifact `ASND2`).
- Master data integrity fix: Corrected Sunovion / Dainippon Pharmaceutical in rows D631, D640, and D887 to `Sumitomo Pharma Co., Ltd.` (TSE: 4506, NON-US LISTING ONLY), eliminating the Daiichi Sankyo (TSE: 4568) collision.
- Decision Engine UI (`index.html`, `assets/app.js`, `assets/style.css`): Added `🧬 Clinical Scorecard` tab with interactive DataTable, live counters, dark-mode CSS styling, and Decision Engine company picker enrichments.
- QA Validator (`scripts/validate_data.py`): Validates all 11 core datasets (980 NMEs, 4,482 efficacy supplements, 1,997 original non-NME approvals, 659 company scores, 152 stock price snapshots, 458 CRLs, 2,000 CT.gov Phase 3 trials, and 402 clinical trial scorecards).

## Highest-value next steps

1. **Continue resolving remaining unmapped sponsors:**
   - 302 CRL rows and ~1,591 CT.gov studies remain unmapped (many are private biotechs, foreign entities, or non-commercial research institutes).
   - Continue exact-matching against SEC `company_tickers.json` and European/Asian exchange registers (TSE, LSE, Euronext, SIX) using `norm_legal()` exact equality.
   - Do NOT use substring/token fuzzy matching.
2. **Paging beyond 2,000 ClinicalTrials.gov Phase 3 records:**
   - The current registry contains the first 2,000 matching Phase 3 studies (primary completion 2026–2027).
   - Queue a GitHub Actions fetch job with `pageToken` pagination to ingest subsequent pages.
3. **Price reaction coverage expansion:**
   - Queue a GitHub Actions Yahoo Finance chart job for newly resolved US-listed CRLs and novel approvals (e.g. 2024–2026 decision dates).
   - Verify close prices on $T-1$, $T_0$, and $T+1$ trading days. Leave degenerate or pre-IPO price series blank.
4. **CBER Type 1 biologics gap (41 rows):**
   - Cross-check against FDA CBER annual approval lists and FDA Purple Book before considering any merge into the NME master list.
5. **PDUFA Calendar updates:**
   - For remaining secondary-aggregated rows in `data/upcoming_pdufa_calendar.csv`, capture company press releases / SEC Form 8-K filings directly into `data/raw/pdufa/` to ensure primary source verification for all rows.

## Do not

- Invent novel approvals to pad toward "1000 new NMEs" — the NME master matches FDA's official year counts.
- Re-introduce token/substring ticker matching. Blank beats guessed.
- Merge the 41 Type 1 gap rows without an official year-count check.
- Treat Type 5 manufacturer changes or medical gases as clinical-trial conversions.
- Fill missing prices, dates, indications, or tickers without verifiable primary sources.
- Claim the 2,000-study CT.gov capture is exhaustive — it is the API's first 2,000 matches.

## Highest-value next steps

1. **Resolve the 314 flagged CRL sponsors + 609 unresolved CT.gov sponsors.** Extend `data/sponsor_registry.csv` from SEC `company_tickers.json` exact-title match only (the raw FDA strings need legal-suffix normalization — reuse `norm_legal()` from `build_crl_master_v2.py`). Do NOT fuzzy-match. For private/foreign applicants (Fresenius Kabi, Chiesi, Jiangsu Hengrui US agents, etc.) set an explicit foreign/private class instead of a ticker.
2. **Capture the REST of the CT.gov window.** The 2,000-study capture is the API's first 2,000 matches. Queue a second fetch job with `query.term` + `countTotal=true` and page through with `pageToken` offsets beyond 2,000 (job type `ctgov` already supports paging via `max_pages`; add a `skip` param or use `query.term` sorts). Append with the same schema; never overwrite.
3. **Price the US-listed CRL events.** 314 unresolved→86 resolved rows now have tickers but no stock snapshots. Queue a `generic` Yahoo-chart job for the resolved tickers × letter dates (start with 2024–2026 letters, ~30 per job per the 350-min runner limit). Degenerate series: flag, leave blank (precedents: NUVL, Trevena).
4. **Adjudicate Sunovion** against Sumitomo Pharma's official IR (TSE 4506) and FDA letters; fix the disagreeing master rows with 2 official links each, or keep both with the flag.
5. **CBER Type 1 gap (41 rows)** — still open. Adjudicate against FDA CBER year tables / Purple Book; merge into `fda_decisions_master.csv` only if an official year table confirms the count would still match.
6. **Purple Book biosimilars** — label the 351(k) originals in `fda_original_non_nme_decisions.csv` without guessing class codes.
7. **Indication text** for orig rows — copy from Drugs@FDA label/approval letter verbatim, never paraphrase.
8. **PDUFA calendar** — 32 rows; the 16 secondary-aggregation rows still need primary press-release verification (fetch job capturing company IR/8-K verbatim).

## Do not

- Invent novel approvals to pad toward "1000 new NMEs" — the NME master matches FDA's official year counts.
- Re-introduce token/substring ticker matching. 7 documented false positives; blank beats guessed.
- Merge the 41 Type 1 gap rows without an official year-count check.
- Treat Type 5 manufacturer changes or medical gases as clinical-trial conversions.
- Fill missing prices, dates, indications, or tickers; silently overwrite a source conflict; overwrite the 58 hand-verified CRL rows or the 8 hand-verified trial endpoints.
- Claim the 2,000-study CT.gov capture is exhaustive — it is the API's first 2,000 matches (see item 2).
