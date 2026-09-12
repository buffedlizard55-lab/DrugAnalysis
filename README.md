# DrugAnalysis

Tracking publicly traded biotech &amp; pharma companies against **FDA drug decisions**, **stock-price reactions**, and **clinical-pipeline success rates** — built entirely from official, verifiable sources.

**Live site:** https://buffedlizard55-lab.github.io/DrugAnalysis/ — served directly from this repository's root by GitHub Pages. The site reads the CSVs in [`/data`](https://github.com/buffedlizard55-lab/DrugAnalysis/tree/main/data) directly, so there is no separate copy to keep in sync: every commit to `main` publishes the current data automatically.

## What's here

| File | Description |
|---|---|
| `data/fda_decisions_master.csv` | 310 verified FDA novel drug approvals (D001–D310): 100 from 2024–2026, 100 from 2021–2023, 77 backfilled 2021–2026 gaps (D201–D277) on 2026-09-12, 23 of the 48 2019 novel approvals (D278–D300) recovered from FDA's 2019 annual report, and 10 of the 53 2020 novel approvals (D301–D310) recovered from the Internet Archive's capture of FDA's 2020 page. Coverage of FDA's official novel-approval tables is **complete** for 2021 (50/50), 2024 (50/50), 2025 (46/46) and 2026 (39/39 to date). FDA has taken its 2019/2020 novel-approval pages offline, so 23 of the 48 drugs listed in FDA's 2019 annual report were recovered from that report instead (D278–D300); 2020 remains uncovered. Company (current holder + original applicant where ownership changed), ticker/exchange, drug, decision type/date, indication, review pathway (Priority/Standard/Accelerated per FDA annual reports), two source links per row, verification status, and notes. |
| `data/fda_crl_master.csv` | Complete Response Letters (FDA rejections) for publicly traded companies — flagged irregularities including repeat-CRL cases. C004 (Outlook Therapeutics / Lytenava) is now marked **RESOLVED**: after a third CRL on 2025-12-31 the BLA was resubmitted and approved on 2026-07-24. |
| `data/stock_price_snapshots.csv` | 239 rows of closing prices immediately before/after each FDA decision, pulled live from the Yahoo Finance chart API (each fetch's reported company name was checked against the expected issuer before use). Non-US listings are in native currency (JPY/EUR/CHF) and noted. Rows are left blank (never estimated) where historical data could not be retrieved, e.g. for delisted/acquired tickers — the 2021–2023 cohort includes several applicants later acquired (Reata, Iveric, ImmunoGen, Mirati, CTI BioPharma, Marinus, Spectrum, G1, SpringWorks, Amicus, Revance, Mallinckrodt, Polarean, Cidara). |
| `data/company_scorecards.csv` | 155 per-company scorecards. 36 are deep-dive pipeline scorecards (CRL recipients plus every company with ≥2 tracked FDA decisions — Pfizer, Lilly, BMS, Roche/Genentech, GSK, AstraZeneca, Novartis, J&J, UCB, Sanofi, Merck, Ionis, Takeda, Otsuka and more), listing which programs are in which phase, which advanced, and which were paused/halted. The other 119 cover every remaining company in the dataset and count **only** FDA decisions verified and tracked here — they are labelled "Verified – FDA decisions only (partial pipeline view)" and report phase progression as 0 rather than estimating it. |
| `data/core_analysis_table.csv` | The primary joined table (317 rows: 310 approvals + 7 CRLs), newest first — company, drug, FDA decision, stock-price reaction, and a pipeline success-rate summary in one place, joined on ticker + decision date. |
| `index.html` + `assets/` | A static GitHub Pages site (plain HTML/CSS/JS, no build step) that renders all of the above as searchable tables and scorecards. It is served from the repository root and loads the CSVs from `/data` directly. |
| `scripts/` | Python scripts used to (re)generate each CSV from the sourced data. |

## Sourcing &amp; verification approach

- **FDA decisions** come from FDA.gov's Novel Drug Approvals pages, `accessdata.fda.gov` drug label PDFs, the official openFDA Drugs@FDA API (`api.fda.gov/drug/drugsfda.json`, used to resolve the *applicant of record* for every application number), the official openFDA CRL transparency API (`api.fda.gov/transparency/crl.json`), and FDA Drug Trials Snapshots.
- **Stock prices** come from the Yahoo Finance chart API (`query1.finance.yahoo.com/v8/finance/chart/{ticker}`), cross-checked against stockanalysis.com where available.
- **Company/pipeline detail** comes from investor-relations press releases, SEC filings, and reputable biotech trade press, always cited with a direct link.
- Every approval/CRL row carries a `verification_status` value. Rows are marked **Verified** only when corroborated by at least one official or primary source. Anything uncertain (disputed sponsor/ticker, ambiguous stock-reaction causality, foreign-only listings, data gaps) is explicitly flagged in the `notes` column rather than silently resolved or guessed.
- No prices, dates, or outcomes in this dataset are fabricated or estimated. Where data could not be verified in this pass, the cell is left blank and the reason is noted — never filled with a plausible-looking guess.
- **Conflicts are surfaced, not smoothed over.** FDA lists the *current* applicant of record, which changes after a licence-out or acquisition, so rows state both names: Veppanu (NDA 219835) was approved to Arvinas/Pfizer and licensed to Rigel eleven days later; Lynavoy (NDA 220295) was approved to GSK and licensed to Alfasigma, which is why the FDA record reads "INTERCEPT". FDA dates Lynavoy's approval 2026-03-17 while GSK announced it 2026-03-19; both are recorded. Pepaxto (NDA 214383) is absent from the FDA application database because it was withdrawn in Oct 2021 — its sponsor is marked unverifiable rather than guessed. One price series (Nuvalent, 2026-07-22) was **discarded** because the API returned a degenerate zero-volume series; the cells are blank, not filled in.

## Known limitations / in-progress work (as of 2026-09-12)

- `review_pathway` (Priority / Standard / Accelerated) is populated for D001–D200 and D278–D300 (both from FDA's official annual reports) but is **deliberately blank** for D201–D277: FDA publishes those designations in its annual *New Drug Therapy Approvals* reports, which do not exist yet for 2026 and were not re-parsed in this pass. Blank beats guessed.
- FDA has removed its 2019 and 2020 novel-approval web pages. 2021–2026 is complete; 23 of the 48 drugs in FDA's 2019 annual report are covered from that report, and 10 of the 53 drugs from 2020 are covered from the Internet Archive's capture of FDA's 2020 page.
- Pre-2021 approvals whose applicant was later acquired (ChemoCentryx, Seagen, Kadmon, AVEO, Checkpoint, Merus, Apellis) have no retrievable history from the chart API; each row says so explicitly rather than showing an estimate.
- The 2026-09-11 Scholar Rock daily bar had not been published when it was captured, so that one `close_on` cell is pending a re-fetch.
- Scorecards added on 2026-09-12 count **only** the FDA decisions verified and tracked in this repository (labelled "Verified – FDA decisions only (partial pipeline view)") and report phase progression as 0 rather than estimating it. The 36 deep-dive pipeline scorecards were hand-built from company disclosures.
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
python3 scripts/build_fda_master_backfill_2026_09.py  # appends D201-D277 (77 missing approvals)
python3 scripts/build_fda_master_2019.py              # appends D278-D300 (23 2019 approvals)
python3 scripts/build_fda_master_2020.py              # appends D301-D310 (10 2020 approvals)
python3 scripts/build_stock_snapshots_new.py       # appends the 57 new price snapshots
python3 scripts/build_company_scorecards_new.py    # appends scorecards for newly-added companies
python3 scripts/build_core_analysis_table.py       # joins everything
```

The builders read verified raw data from `data/staging/`:

- `drugs_base.json` — FDA Novel Drug Approvals page captures (2021–2023)
- `sponsors.json` — openFDA-verified application holders
- `prices.py` — verbatim Yahoo Finance chart-API close series with each fetch's reported company name for ticker verification
- `fda_novel_2021_full.json`, `fda_novel_2024_full.json`, `fda_novel_2025_full.json`, `fda_novel_2026_full.json` — the FDA 2021/2024/2025/2026 novel-approval tables captured **verbatim** (all 50/50/46/39 rows) and used for the D201–D277 gap analysis
- `openfda_sponsor_resolution.json` — the applicant of record returned by openFDA for every application number in the backfill
- `prices_new_2026_09.py` — the verbatim ±6-day daily-close series behind the 57 new snapshots, including the tickers that returned no data and the one series that was rejected as unreliable

## Disclaimer

This is a research/analysis project, not investment advice. Always verify against the linked primary sources before making any decisions.
