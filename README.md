# DrugAnalysis

Tracking publicly traded biotech &amp; pharma companies against **FDA drug decisions**, **stock-price reactions**, and **clinical-pipeline success rates** — built entirely from official, verifiable sources.

**Live site:** https://buffedlizard55-lab.github.io/DrugAnalysis/ — served directly from this repository's root by GitHub Pages. The site reads the CSVs in [`/data`](https://github.com/buffedlizard55-lab/DrugAnalysis/tree/main/data) directly, so there is no separate copy to keep in sync: every commit to `main` publishes the current data automatically.

## What's here

| File | Description |
|---|---|
| `data/fda_decisions_master.csv` | 200 verified FDA novel drug approvals (D001–D200): 100 from 2024–2026 plus 100 from 2021–2023. Company (current holder + original applicant where ownership changed), ticker/exchange, drug, decision type/date, indication, review pathway (Priority/Standard/Accelerated per FDA annual reports), two source links per row, verification status, and notes. |
| `data/fda_crl_master.csv` | Complete Response Letters (FDA rejections) for publicly traded companies — flagged irregularities including repeat-CRL cases. |
| `data/stock_price_snapshots.csv` | 154 rows of closing prices immediately before/after each FDA decision, pulled live from the Yahoo Finance chart API (each fetch's reported company name was checked against the expected issuer before use). Non-US listings are in native currency (JPY/EUR/CHF) and noted. Rows are left blank (never estimated) where historical data could not be retrieved, e.g. for delisted/acquired tickers — the 2021–2023 cohort includes several applicants later acquired (Reata, Iveric, ImmunoGen, Mirati, CTI BioPharma, Marinus, Spectrum, G1, SpringWorks, Amicus, Revance, Mallinckrodt, Polarean, Cidara). |
| `data/company_scorecards.csv` | 36 per-company scorecards: 7 deep-dive scorecards (CRL recipients) plus 29 generated scorecards for every company with two or more tracked FDA decisions 2021–2026 (Pfizer, Lilly, BMS, Roche/Genentech, GSK, AstraZeneca, Novartis, J&J, UCB, Sanofi, Merck, Ionis, Takeda, Otsuka, and more) — each lists every tracked approval with pathway and verified post-approval status (withdrawals, accelerated-to-traditional conversions). |
| `data/core_analysis_table.csv` | The primary joined table (207 rows: 200 approvals + 7 CRLs) — company, drug, FDA decision, stock-price reaction, and a pipeline success-rate summary in one place, joined on ticker + decision date. |
| `index.html` + `assets/` | A static GitHub Pages site (plain HTML/CSS/JS, no build step) that renders all of the above as searchable tables and scorecards. It is served from the repository root and loads the CSVs from `/data` directly. |
| `scripts/` | Python scripts used to (re)generate each CSV from the sourced data. |

## Sourcing &amp; verification approach

- **FDA decisions** come from FDA.gov's Novel Drug Approvals pages, `accessdata.fda.gov` drug label PDFs, and the official openFDA CRL transparency API (`api.fda.gov/transparency/crl.json`).
- **Stock prices** come from the Yahoo Finance chart API (`query1.finance.yahoo.com/v8/finance/chart/{ticker}`), cross-checked against stockanalysis.com where available.
- **Company/pipeline detail** comes from investor-relations press releases, SEC filings, and reputable biotech trade press, always cited with a direct link.
- Every approval/CRL row carries a `verification_status` value. Rows are marked **Verified** only when corroborated by at least one official or primary source. Anything uncertain (disputed sponsor/ticker, ambiguous stock-reaction causality, foreign-only listings, data gaps) is explicitly flagged in the `notes` column rather than silently resolved or guessed.
- No prices, dates, or outcomes in this dataset are fabricated or estimated. Where data could not be verified in this pass, the cell is left blank and the reason is noted — never filled with a plausible-looking guess.

## Known limitations / in-progress work

- Stock-price snapshots cover all 100 of the 2021–2023 approvals that have a listed ticker (delisted/acquired applicants are recorded with explicit unavailable-data notes). ~35 of the 2024–2026 approvals still need price fetches; unmatched rows show blank price cells.
- Company scorecards cover all CRL recipients plus every company with ≥2 tracked FDA decisions 2021–2026. Single-approval companies from 2021–2023 do not yet have generated scorecards.
- Two ticker assignments required correction after initial research and are now fixed and re-verified: Xolremdi/X4 Pharmaceuticals → `XFOR`; Cardamyst/Milestone Pharmaceuticals → `MIST`.
- 2021–2023 verification status: every drug's brand/generic/date/label link was captured from FDA.gov Novel Drug Approvals pages; every application holder was verified via openFDA; original applicants (where ownership changed) were verified from the original FDA approval letters; review priority and Accelerated Approval status were taken from FDA's official annual reports; Drugs@FDA pages were used to confirm action dates (e.g. Quviviq 01/07/2022, Kimmtrak 01/25/2022, Verquvo 01/19/2021). Flagged irregularities: Ukoniq and Relyvrio voluntary market withdrawals; multiple approval-time applicants later acquired (see notes columns).

## Regenerating the data

Each CSV has a matching builder script in `scripts/` (e.g. `scripts/build_fda_master.py`) that writes the file from an explicit, source-cited Python list — this avoids CSV-escaping bugs and makes every entry easy to diff/review in version control.

```bash
python3 scripts/build_fda_master.py                # D001-D100 (2024-2026)
python3 scripts/build_fda_master_2021_2023.py      # appends D101-D200 (2021-2023)
python3 scripts/build_crl_master.py
python3 scripts/build_stock_snapshots.py           # 2024-2026 snapshots
python3 scripts/build_stock_snapshots_2021_2023.py # appends 2021-2023 snapshots
python3 scripts/build_company_scorecards.py        # CRL-recipient deep dives
python3 scripts/build_company_scorecards_multi.py  # appends multi-approval scorecards
python3 scripts/build_core_analysis_table.py       # joins everything
```

The 2021–2023 builders read verified raw data from `data/staging/` (`drugs_base.json` = FDA Novel Drug Approvals page captures, `sponsors.json` = openFDA-verified application holders, `prices.py` = verbatim Yahoo Finance chart-API close series with each fetch's reported company name for ticker verification).

## Disclaimer

This is a research/analysis project, not investment advice. Always verify against the linked primary sources before making any decisions.
