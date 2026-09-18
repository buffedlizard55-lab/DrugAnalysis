# Remaining work for the next session (written 2026-09-18 v9)

This file is the hand-off for future development. The sandbox that edits the repo has **no general outbound network** (only a page-fetch tool that can reach api.fda.gov, web.archive.org and finance.yahoo.com one page at a time). Bulk external fetches must go through GitHub Actions (`fetch_jobs/*.json` → `scripts/run_fetch_jobs.py` → `data/raw/<job>/` + SHA-256 manifest). Nothing may be typed from memory: every row needs an official/primary source link, and blank beats guessed.

## What this session shipped (v9)

- **Year-by-year pre-2000 audit (2000→1996)** — `data/pre2000_year_audit.csv`: every one of the 204 master rows 1996–2000 re-verified against three official layers (year table / Compilation / openFDA runner payloads). **188 VERIFIED_ALL_LAYERS, 12 table+Compilation, 3 Compilation+openFDA, 1 Compilation-only, 0 UNRESOLVED, 0 date conflicts**, 14 flags all of the "openFDA does not index this record" kind, each with a live api.fda.gov re-check (13 absences by number+brand, Normiflo's submissions-less record, 4 positive controls) staged verbatim in `data/staging/pre2000_live_checks.json`.
- **Price-event ingestion bug fixed**: `data/raw/stock_yahoo_events_1998_2026/` had been fetched (v7/v8 runner runs) but never consumed. New consumer `scripts/build_stock_snapshots_events_1998_2026.py` ingested 647 events (31 for 1998–2000 alone; 5 recorded failures preserved), snapshots **334 → 978** (after collapsing 3 byte-identical duplicates), priced core rows **301 → 859**.
- **Pathway-consistency pass** from the official Compilation: 268 filled / 46 Accelerated appended / 53 normalised / 35 FDA-vs-FDA conflicts flagged notes-only / 25 blanks left (all 2026). Changelog: `data/staging/pathway_labelling_changelog.json`.
- **77 dead Wayback URLs (2011–2014) rewritten** to register-pinned, live-verified captures; validator bans the dead timestamp.
- **classify_listing fixed point**: 0 flips, 0 provenance clobbers, idempotent; 349 field-vs-committed disagreements surfaced as dated notes (v7 irregularity #1 closed without touching a single committed class).
- **Sponsor-resolution index** `data/pre2000_sponsor_resolution_index.csv` (67 rows: 25 high-priority recoverable / 20 foreign-listing / 22 documented no-equity) with deterministic EDGAR + Drugs@FDA links per row.
- **Era analysis** `data/pre2000_era_analysis.csv` (1985–2000) + site tab 🕰️ Pre-2000 Audit; derived tables regenerated; validator extended (PASS).

## Highest-value next steps

1. **2024 pathway reconciliation (NEW, v9)** — the labelling pass surfaced **35 rows of 2024** where the master's pathway (derived from FDA's 2024 annual-report data) contradicts the Compilation's Review Designation (21 master-Standard-vs-Compilation-Priority, 14 master-Priority-vs-Compilation-Standard; e.g. D002 Exblifep, D004 Tevimbra, D013 Anktiva). FDA's 2024 report table carries no review column (verified live), so the master's 2024 pathway provenance needs a per-row re-check against the report PDF (media/184967) Appendix or FDA action letters, then a dated correction with both sources kept in notes.
2. **Resolve the 25 high-priority rows of the pre-2000 sponsor index** — once-listed issuers (The Upjohn Co. → PNU, Parke-Davis, Marion Merrell Dow, Immunomedics IMMU, Agouron AGRN, Athena ATHN, Roberts RPI, Advanced Magnetics ANM/AinM, Gensia GNSA, Neurex, Cytogen CYTO, IVAX/Baker Norton…) each need one primary citation (period 10-K/20-F via EDGAR company browse — links are in the index; EDGAR full-text only covers 2001+, so use the browse endpoint or Wayback) before the exchange field is normalised to "formerly VENUE:TICKER, delisted YYYY". Then re-run `classify_listing.py` (now safe: fixed-point).
3. **Run the CRL + 2026-NME price fetch job** (v8 item 7, still open): 86 resolved CRL events and the 2026 NME rows without snapshots. Queue `fetch_jobs/stock_yahoo_crl_events_2002_2026.json` (deterministic from `fda_crl_master.csv` resolved tickers); ingest with a consumer clone of `build_stock_snapshots_events_1998_2026.py`.
4. **Pre-2000 sponsor resolution deep-dive on the non-NME originals** (~900 of 2,798 orig rows UNRESOLVED, mostly pre-2000 legacy sponsors) — unchanged from v8 item 5: exact-match-only aliases against SEC `company_tickers.json` and contemporaneous 10-K/20-F evidence; add registry keys, never token-match. Known collisions: "SUN PHARM" (3 keys), "NYCOMED" (no key), "CUBIST" (2 keys).
5. **Vintage-indication enrichment** — the 390 pre-1998 master rows and the orig file carry terse/blank indication text; FDA's compilation XLSX columns 16/17 ("Abbreviated Indication(s)", "Approved Use(s)") are the official source for a verbatim fill pass (notes-only, links already on the rows).
6. **Purple Book 351(k) labelling** for the non-NME file (v8 carry-over); **PDUFA calendar** — 16 secondary-aggregation rows still need primary press-release/8-K captures (v5 carry-over); **CT.gov Phase 3 registry** paging beyond the first 2,000 (v6 carry-over).
7. **2016 NME audit** — FDA's 2016 table had a known USP-facing quirk (ETC-1002/Vascepa); a full line-by-line 2016 reconciliation like v7's 2014 pass would close the last year without a dedicated row-level reconciliation note. (2016 master pin is 22/22 vs the official count, so this is polish, not a gap.)
8. **Company-score confidence widening** — 615/750 scores are Low-confidence because the market component has few priced events; the v9 price backfill (301→859) already moved 122 score rows. A second wave (CRL events, item 3) would push most 1990s-2000s constituents above the 5-event floor.

## Do not

- Invent novel approvals to pad counts — the master equals FDA's official NME Compilation 1985–2025 + the pinned 2026 year table; 1,000 extra novel approvals do not exist.
- Retry failed Yahoo chart requests with successor tickers (recorded repo law: the failure IS the data).
- Re-introduce token/substring ticker matching (7 documented false positives in v5). Blank beats guessed.
- Merge T1GAP rows into the master — every remaining row is adjudicated with a reason (legacy status artifacts, second licences, same-moiety second products). Emend IV in particular is a *documented exclusion*, not a missed row.
- Link Blenrep 2020 (D306) to BLA 761440 — that is the 2025 re-approval, a different decision.
- Treat Type 5 manufacturer changes or medical gases as clinical-trial conversions.
- Fill missing prices, dates, indications, or tickers; silently overwrite a source conflict; overwrite the 58 hand-verified CRL rows or the 8 hand-verified trial endpoints.
- Overwrite the 35 flagged 2024 pathway rows with the Compilation value (or vice versa) — that is item 1's dedicated reconciliation, to be done per-row with both FDA sources cited.
- `scripts/classify_listing.py` is now a fixed point (v9) — but only because it PRESERVES committed classes; its derived classes for NEW rows are still field-text only. Corrections belong in builders, not in this script.
- Claim the 2,000-study CT.gov capture is exhaustive — it is the API's first 2,000 matches.
