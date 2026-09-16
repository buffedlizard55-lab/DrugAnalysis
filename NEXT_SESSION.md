# Remaining work for the next session (written 2026-09-16 v4)

This file is the hand-off. The sandbox that edits the repo has **no general outbound network**. Every external fetch must go through GitHub Actions (`fetch_jobs/*.json` → `scripts/run_fetch_jobs.py` → `data/raw/<job>/` + SHA-256 manifest). Blank beats guessed. Do not invent 1,000 novel approvals — the NME master already matches FDA’s official year counts.

## What this session shipped

- `data/fda_original_non_nme_decisions.csv` — **1,997** original NDA/BLA approvals 2000–2026 that are **not** Type 1 NMEs. IDs `O-{appl}`. 819 US-listed, 781 unresolved sponsors left unresolved.
- `data/company_original_approval_scorecard.csv` — 88 issuers, clinical-relevant = Type 2+3+4+new-indication originals. Type 5 and medical gases excluded from that numerator.
- `data/fda_type1_not_in_nme_master.csv` — 41 Type 1 openFDA rows not matched to the NME master. **FLAGGED, not merged.**
- `data/fda_orig_year_register.csv` — 27 years, `sum(non_nme_published)=1997`.
- Site: Originals tab, Orig Scorecard, Private & Non-US tabs restored, dark mode.
- Validator: orig schema, no Type 1 leak, 2000–2026 coverage, scorecard counts must match.

Do **not** recount the 980 NMEs or the 4,482 efficacy supplements. Do **not** run `scripts/build_crl_expanded.py`.

## Highest-value next universe: ClinicalTrials.gov Phase 3

Queued, not yet collected:

- `fetch_jobs/clinicaltrials_phase3_2026_2027.json` (type `ctgov`, implemented in `scripts/run_fetch_jobs.py`)
- After Actions writes `data/raw/clinicaltrials_phase3_2026_2027/studies.json`, build a **new** table `data/clinical_trial_endpoints.csv` expansion (do not overwrite the existing 8 hand-verified rows — append with a distinct id scheme, e.g. `CT-{nctid}`).
- Join lead sponsor to `sponsor_registry.csv`. Unresolved sponsors stay `UNRESOLVED`. Never guess a ticker.
- Official source on every row: `https://clinicaltrials.gov/study/{NCTId}`.
- Do not fill expected dates that CT.gov left blank.

## Other official universes still unused

1. **Remaining CRLs.** `data/fda_crl_full_458.csv` has the raw 457. The published master has 58. Write a *new* builder (do not reuse `build_crl_expanded.py`) that only adds US-investable CRLs with two official source links. Flag letters that name no public company.
2. **CBER Type 1 gap (41 rows).** Humira, Neulasta, Fabrazyme, Xolair, Aranesp, etc. are real CBER biologics missing from the CDER NME master. Adjudicate against FDA CBER year tables / Purple Book. Merge into `fda_decisions_master.csv` **only** if an official year table confirms the count would still match; otherwise leave them in the gap file. Blank beats guessed.
3. **Purple Book biosimilars.** 351(k) originals in the orig file often have unpublished class codes. A dedicated Purple Book extract would label them without guessing.
4. **Orig-event prices.** 819 US-listed original approvals have no Yahoo/Stooq snapshot. Queue a `generic`/`stooq` fetch job for a *sample* of high-signal Type 2/3/4 dates — not Type 5 manufacturer changes, not medical gases. Degenerate series: flag, leave blank.
5. **781 unresolved orig sponsors.** Extend `data/sponsor_registry.csv` from SEC `company_tickers.json` exact-title match only. No fuzzy “looks like Pfizer”.
6. **Indication text.** Orig rows deliberately have none. If a next session adds indications, copy from the Drugs@FDA label / approval letter, never paraphrase.

## Known limitations that still apply

- NME master is CDER-complete vs official year counts; CBER 2000–2003 biologics (Humira, Neulasta, …) are still absent from it on purpose.
- 9 source-vs-source date/brand mismatches on the NME audit (`verification_crosscheck.csv`) remain flagged, not overwritten.
- `review_pathway` still blank for most pre-2021 NME rows (FDA archived tables publish no designation column).
- Only 93 priced NME/CRL events; orig events unpriced.
- Pipeline tracker is 34 deep-dives; the rest of the 434 scorecards are FDA-decisions-only.
- Sandbox network is dead — do not retry `curl` to FDA/CT.gov from the editor.

## Do not

- Invent novel approvals to pad toward “1000 new NMEs”.
- Merge the 41 Type 1 gap rows into the master without an official year-count check.
- Treat Type 5 manufacturer changes or medical gases as clinical-trial conversions.
- Fill missing prices, dates, indications, or tickers.
- Silently overwrite a source conflict.
