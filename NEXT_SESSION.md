# Remaining work for the next session (written 2026-09-18 v13)

This file is the hand-off for future development. The sandbox that edits the repo has **no general outbound network** (only a page-fetch tool that can reach api.fda.gov, www.fda.gov, www.sec.gov, query1.finance.yahoo.com and web.archive.org one page at a time — the tool WORKED all through v13). Bulk external fetches must go through GitHub Actions (`fetch_jobs/*.json` → `scripts/run_fetch_jobs.py` → `data/raw/<job>/` + SHA-256 manifest), **EXCEPT EDGAR: SEC returns HTTP 403 to the Actions runner's cloud IPs** (all 18 specs of `fetch_jobs/edgar_pre2000_symbols_2026_09.json` FAILED on run 35391279461 — the manifest recording this is kept at `data/raw/edgar_pre2000_symbols_2026_09/manifest.json`). EDGAR primary text must be fetched through the sandbox page-fetch tool, one canonical URL at a time. Nothing may be typed from memory: every row needs an official/primary source link, and blank beats guessed.

## What this session shipped (v13)

- **1983/1984 are now the COMPLETE Drugs@FDA enumeration** (`data/pre1985_fda_decisions.csv`, 18 → 35 rows):
  - 20 new rows (8 × 1983 NMEs: TZ-3, Bumex, Lozol, Chenix, Zinacef, Vepesid, Tracrium, Chymex; 12 × 1984: Normodyne, Norcuron, Micronase, Sufenta, Glucotrol, Precef, Orap, Inocor, Pentam, Nephroflow, Tornalate, Modrastane). Every date/class/priority/brand/application is asserted against the committed ORIG/AP payloads (`data/raw/openfda_orig_decisions_1980_1984/decisions_{1982..1984}.json`) by `scripts/expand_pre1985_decisions_2026_09.py`; the build aborts on mismatch.
  - 3 v12 rows REMOVED (premise disproved): Lithobid (cited app NDA018006 is Meclomen — a 1980 Type-1 NME; real Lithobid NDA018027 approved 1979-04-27), Ambenyl (1954 original; 1984 events were supplements), Valisone (1967 original; 1984 event was a CMC supplement). Validator bans their IDs.
  - 5 corrected: Trandate NDA018716 is TYPE 5 (new-manufacturer app) and the labetalol NME is Schering's Normodyne NDA018686 (added as its own row); Augmentin re-pointed to the tablet app NDA050564 (TYPE 1/4, PRIORITY — an NME-combination; NDA050575 suspension TYPE 3 noted); Tonocard re-pointed to NDA018257 (PRIORITY; NDA018249 is Sodium Lactate); Furosemide oral solution class/priority → NOT STATED; Hylorel 1982-boundary note.
  - Indications quoted from current FDA labeling (label.json fetches) or official FDA/NIH records, each qualified; original applicants cited (Pink Sheet 1984, NYT 1984, Inpharma 1983, NEJM 1986, OOPD) or flagged unpinned (holder named verbatim instead — Lozol, Chenix, Sufenta, Pentam, Nephroflow, Modrastane).
  - Era CSV re-based: 1983 = 14 NMEs (Pink Sheet-pinned; 13 indexed by Drugs@FDA), 1984 = 19 (Drugs@FDA enumeration; the legacy "22" documented as unpinned), 1985 = 31 (compilation; the 4 COMPILATION_ONLY absences verified absent from openFDA by live probes).
- **Pre-2000 sponsor symbol sweep (v12 resolver, `scripts/resolve_pre2000_sponsors_v12.py`)**: worklist now **15 RESOLVED / 7 VENUE-VERIFIED / 0 CITATION-LOCATED** (of 67).
  - RESOLVED: Pharmacia & Upjohn **NYSE:PNU ×5** (FY1997 10-K405 Item 5 verbatim; ticker column FILLED — safe: D996 Detrol already carried PNU, same class) and Carter-Wallace **NYSE:CAR** (1997 Annual Report p.7, EX-13 of the 10-K405; ticker column deliberately BLANK — D1244 Felbatol same-name split hazard; symbol lives in `exchange`).
  - Roberts ×2: venue transfer pinned — NASDAQ NMS through **1997-05-21**, AMEX from **1997-05-22** (FY1998 10-K Item 5); both decisions in the NASDAQ era; symbol NOT stated in FY1996/FY1998 10-Ks (negative result kept).
  - Warner-Lambert ×4: documented negative — FY1997 10-K Item 5 + EX-13 p.48 "Market Prices" read in full, **no symbol anywhere in the submission**; quarterly ranges captured as price-event evidence (1996 Q4 $80/$61⅞, 1997 Q1 $93¼/$69½).
  - Block Drug D1365: promoted CITATION-LOCATED → VENUE-VERIFIED — OTC/NASD inter-dealer bid quotes (12(g), no exchange listing; 507 Class A holders vs 5 Class B); same 10-K confirms the Aphthasol approval verbatim.
  - Derived tables rebuilt and diffed: exactly 5 core rows changed (ticker ''→PNU); §7 ratchet unchanged at 141; company scores regrouped along the real registrant boundary (pre-merger Upjohn 3 rows / post-merger PNU 6 rows incl. Detrol) — deliberate, documented.
- **Validator extended + mutation-tested**: 35-row pre-1985 baseline, group counts, removed-ID ban, corrected-app pins, payload-date cross-check, era↔table consistency, all v12 symbol pins, CITATION-LOCATED cleared, runner-403 manifest presence. PASS, 0 errors, 1,613 warnings (unchanged baseline).
- **Raw data landed**: openFDA ORIG/AP decisions 1980–1984 (5 year-files + manifest) via Actions run 35391279461.

## Limitations and Work for Future Sessions

1. **Pre-1985 backward expansion to 1982/1981/1980** — the payloads are ALREADY in `data/raw/openfda_orig_decisions_1980_1984/` (no fetch needed): 1982 has **25** TYPE-1 ORIG/APs, 1981 has **23** (22 TYPE 1 + 1 TYPE 1/4), 1980 has **9**. Methodology is proven: extend `PRE1985_DECISIONS` (schema in the expansion script), assert every row against the payload, verify original applicants/indications, update era rows + validator ratchets. Notes for that pass: NDA018006 Meclomen (meclofenamate, Parke-Davis) is a 1980 NME (the old Lithobid row's wrong app); no official per-year NME table exists pre-1985 (only Drugs@FDA enumeration + contemporaneous trade-press counts — find year-end Pink Sheet/FDA-report counts for 1980–1982 the way 1983's "14" was pinned).
2. **Remaining 7 VENUE-VERIFIED ticker hunts** (EDGAR via sandbox tool only — the Actions route 403s):
   - Warner-Lambert ×4: FY1998 10-K (filed 1999-03, accession findable via the company browse page CIK 104669), 1998 DEF 14A (performance-graph sections often name the symbol), FY1999 10-K. The 1997-era symbol (WLA) is widely remembered but MUST NOT be typed from memory.
   - Roberts ×2: FY1997 10-K acc 0000950130-98-001619 (411 KB), 1997/1998 DEF 14A proxies, 1999 DEFM14A acc 0000950130-99-006712 (AMEX-era).
   - Block Drug ×1: 424-series/DEF 14A on CIK 12654, or NASD/Pink-Sheet archives via web.archive.org.
3. **Core analysis class disagreements (audited baseline = 141)** — unchanged this session (the PNU fills added 0): adjudicate the legacy ADR-vs-direct (GSK, NVS, RHHBY, AZN, SNY) and delisted-vs-current (SHPG, MDCO, CELG, ALXN) classes with period 10-K/20-F cover evidence.
4. **Clinical Trials Phase 3 registry**: still the first 2,000 studies (2026–2027 window); page deeper via the ctgov job kind.
5. **User-requested "1000 new entries" for 2000–2026** and the standing goals (pipeline/PDUFA press-release verification via 8-K fetches; price-event coverage for the newly pinned pre-2000 tickers — the Item 5 quarterly ranges are staged in the evidence JSON as targets for a deliberate Yahoo job).
6. **Site**: the Pre-1985 tab now renders 35 rows; if a 1980–1982 expansion happens, add era rows and update the section copy (no hardcoded counts beyond the ones already fixed).

## Key facts pinned this session (do not re-derive)

- PNU quote: "The Common Stock is listed and traded on the New York Stock Exchange (the "NYSE") under the symbol PNU." — P&U FY1997 10-K405 acc 0000950124-98-001758, Item 5 (chunk 6 of 38). Stockholm SDS symbol PH&U.
- CAR quote: "principally traded on the New York Stock Exchange (symbol CAR)" — 1997 Annual Report p.7, EX-13 of Carter-Wallace FY1997 10-K405 acc 0000890163-97-000093 (chunk 15 of 33). Dec-1996 quarter $16½/$11⅜.
- Roberts transfer: "as reported on the NASDAQ National Market System from January 1, 1997 through May 21, 1997 and as reported by the American Stock Exchange from May 22, 1997" — FY1998 10-K acc 0000950130-99-001681, Item 5 (chunk 7 of 75).
- Warner-Lambert Item 5 (10-K body): "The principal market on which the Company's stock is traded is the New York Stock Exchange... also listed and traded on... Chicago, Pacific, London and Zurich" — acc 0000950117-98-000602, chunk 7 of 43; market-prices table on EX-13 p.48 (chunk 36). NO symbol.
- Block Drug: 12(b) "None", 12(g) Class A Common, SROS NASD, bid quotes — FY1997 10-K acc 0000012654-97-000004, cover (chunk 0) + Item 5 (chunk 2 of 21); "In December, 1996, the Company received Food and Drug Administration (FDA) approval for Aphthasol, a new chemical entity..." (Item 1, chunk 0).
- 1983 NME count 14: Pink Sheet 1984-01-16 (Chymex article): "The drug was the last of 14 new molecular entities cleared by the agency during 1983." Drugs@FDA indexes 13 (the 14th is unindexed — same pattern as 1985's 4/31 gap).
- Drugs@FDA ORIG/AP Type-1 enumerations from the committed payloads: 1980: 9 · 1981: 23 · 1982: 25 · 1983: 13 · 1984: 19 · 1985: 27 (compilation 31).
- openFDA label endpoint (api.fda.gov/drug/label.json) works through the sandbox fetch tool and `indications_and_usage` usually lands in chunk 0–2; Drugs@FDA ORIG submissions for 1980s apps carry NO application_docs (docs begin with late-1980s supplements), so original-era indications are unavailable in machine-readable form — current-label text (qualified) or contemporaneous press quotes are the only citable options.

## Process notes

- After any Actions run that commits data, `git fetch origin arena/01a0b62c-druganalysis` and reset to the remote tip BEFORE committing (the workflow has rolled the local object store back before).
- The fetch_workflow outdir is `data/raw/<fetch-job-stem>/` — new EDGAR jobs are pointless (403), but openFDA/ctgov/stooq jobs still work.
- When fetching EDGAR interactively: only canonical URLs `https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}.txt`, one at a time; chunk positions for the filings already read are listed above to avoid re-fetching.
