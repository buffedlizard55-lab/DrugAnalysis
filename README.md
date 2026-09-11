# DrugAnalysis

Tracking publicly traded biotech &amp; pharma companies against **FDA drug decisions**, **stock-price reactions**, and **clinical-pipeline success rates** — built entirely from official, verifiable sources.

**Live site:** enable GitHub Pages on this repo (Settings → Pages → source: `main` branch, `/docs` folder) to publish the dashboard at `https://<org>.github.io/DrugAnalysis/`.

## What's here

| File | Description |
|---|---|
| `data/fda_decisions_master.csv` | 100 verified FDA drug approvals (2024–2026): company, ticker, exchange, drug, decision type/date, indication, review pathway, two source links per row, verification status, and notes. |
| `data/fda_crl_master.csv` | Complete Response Letters (FDA rejections) for publicly traded companies — flagged irregularities including repeat-CRL cases. |
| `data/stock_price_snapshots.csv` | Closing stock prices immediately before/after each FDA decision, pulled live from the Yahoo Finance chart API. Rows are left blank (never estimated) where historical data could not be retrieved, e.g. for delisted/acquired tickers. |
| `data/company_scorecards.csv` | Per-company pipeline scorecards: how many programs advanced, paused/held, or were rejected, with phase-by-phase detail and links. |
| `data/core_analysis_table.csv` | The primary joined table — company, drug, FDA decision, stock-price reaction, and a pipeline success-rate summary in one place. |
| `docs/` | A static GitHub Pages site (plain HTML/CSS/JS, no build step) that renders all of the above as searchable tables and scorecards. |
| `scripts/` | Python scripts used to (re)generate each CSV from the sourced data. |

## Sourcing &amp; verification approach

- **FDA decisions** come from FDA.gov's Novel Drug Approvals pages, `accessdata.fda.gov` drug label PDFs, and the official openFDA CRL transparency API (`api.fda.gov/transparency/crl.json`).
- **Stock prices** come from the Yahoo Finance chart API (`query1.finance.yahoo.com/v8/finance/chart/{ticker}`), cross-checked against stockanalysis.com where available.
- **Company/pipeline detail** comes from investor-relations press releases, SEC filings, and reputable biotech trade press, always cited with a direct link.
- Every approval/CRL row carries a `verification_status` value. Rows are marked **Verified** only when corroborated by at least one official or primary source. Anything uncertain (disputed sponsor/ticker, ambiguous stock-reaction causality, foreign-only listings, data gaps) is explicitly flagged in the `notes` column rather than silently resolved or guessed.
- No prices, dates, or outcomes in this dataset are fabricated or estimated. Where data could not be verified in this pass, the cell is left blank and the reason is noted — never filled with a plausible-looking guess.

## Known limitations / in-progress work

- Stock-price snapshots don't yet cover every decision in the master list; unmatched rows show blank price cells.
- Company scorecards currently cover a focused subset (CRL recipients + companies with the most FDA-decision activity in this dataset); broader coverage is planned.
- Two ticker assignments required correction after initial research and are now fixed and re-verified: Xolremdi/X4 Pharmaceuticals → `XFOR`; Cardamyst/Milestone Pharmaceuticals → `MIST`.
- Source URLs have not all been individually re-fetched to confirm they resolve; spot-checks were performed but a full line-by-line re-fetch pass is a recommended next step before treating the dataset as fully audited.

## Regenerating the data

Each CSV has a matching builder script in `scripts/` (e.g. `scripts/build_fda_master.py`) that writes the file from an explicit, source-cited Python list — this avoids CSV-escaping bugs and makes every entry easy to diff/review in version control.

```bash
python3 scripts/build_fda_master.py
python3 scripts/build_crl_master.py
python3 scripts/build_stock_snapshots.py
python3 scripts/build_company_scorecards.py
python3 scripts/build_core_analysis_table.py
```

## Disclaimer

This is a research/analysis project, not investment advice. Always verify against the linked primary sources before making any decisions.
