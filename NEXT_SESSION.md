# Remaining work for the next session (written 2026-09-17 v5)

This file is the hand-off. The sandbox that edits the repo has **no general outbound network**. Every external fetch must go through GitHub Actions (`fetch_jobs/*.json` → `scripts/run_fetch_jobs.py` → `data/raw/<job>/` + SHA-256 manifest). Blank beats guessed.

## What this session shipped

- `data/fda_crl_master.csv` — **458 CRL rows** (58 deep-verified untouched + 400 new from the official openFDA CRL transparency database, ids `CR-<APP>-<YYYYMMDD>`). Builder: `scripts/build_crl_master_v2.py`. Resolution audit: `data/staging/crl_sponsor_resolution_v2.json`. **86 resolved, 314 flagged-blank.**
- `data/clinical_trials_phase3_registry.csv` — **2,000 Phase 3 studies** with primary completion 2026–2027 from the official ClinicalTrials.gov API v2 (verbatim capture `data/raw/clinicaltrials_phase3_2026_2027/`, 40 pages × 50, SHA-256 manifest). Builder: `scripts/build_ctgov_phase3_registry.py`. 314 US-listed / 1,077 non-commercial / 609 unresolved-flagged. Every row links `https://clinicaltrials.gov/study/<NCT>`.
- A looser token-based ticker matcher was trialled for the CRL expansion, produced **7 provably wrong matches** (Swedish Orphan Biovitrum→Eco Wave Power, Cadence Pharma→Cadence Design, InnoPharma→Music Licensing, Armstrong Pharma→Armstrong World, Clarus Therapeutics→Clarus Corp, RB Health→RB Global, Conjupro→Protalix) and was **excluded**. Published resolver = repo-verified standalone rows + exact SEC titles (legal suffixes only).
- Flagged (not fixed): two master rows disagree on Sunovion (`NO_TICKER` vs `TSE:4568` = Daiichi Sankyo; Sunovion's parent was Dainippon Sumitomo, TSE 4506). Block-listed in the CRL builder so it cannot propagate.
- Site: 🗃️ Phase 3 Registry tab, ⚠️ CRLs tab (458), header counts, methodology updates. Validator extended to both new tables — PASS.

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
