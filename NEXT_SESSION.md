# Remaining work for the next session (written 2026-09-18 v15)

The v15 branch is `arena/01a0b6a2-druganalysis` (branched from `main` at `1273034`). v14 was merged via PR #28. This session completed the user-requested focus years **1985, 1984, 1983**; open a fresh PR from `arena/01a0b6a2-druganalysis` and merge it before starting new edits. The repository root is `/home/user/DrugAnalysis`.

## What v15 shipped

- **1983/1984 backward extension of the non-NME original-approval table (+145 rows).** `data/fda_original_non_nme_decisions.csv` now spans **1983–2026 with 2,943 rows** (1983: 56, 1984: 89). Every field is copied verbatim from the committed openFDA payloads `data/raw/openfda_orig_decisions_1980_1984/decisions_{1983,1984}.json`. Type 1/1-4 NMEs stay in the curated pre-1985 table; furosemide NDA018413 and Trandate NDA018716 are excluded as already tracked; a payload Type 1 missing from the pre-1985 table **aborts the build** rather than being invented. Each pre-1985 row states that the openFDA sponsor is the **current** Drugs@FDA holder, never asserted as the historical applicant.
- **`data/focus_years_1983_1985_audit.csv` (261 rows)** — read-only enumeration audit built by `scripts/build_focus_year_audit_1983_1985.py`: every ORIG/AP NDA/BLA decision in the committed payloads for 1983 (70), 1984 (109), and 1985 (82) is shown tracked in exactly one project table, with date/class/priority agreement columns. **All 261 dates agree.** Zero untracked rows (the builder aborts if any appear).
- **1985 boundary reconciliation:** 27 master NMEs match payload TYPE 1/1-4 records; Temovate cream NDA019323 is tracked via the Compilation's own cross-reference on master D1055 (NDA019322); 54 non-NME originals published = 82/82 accounted. The four 1985 master rows with **no** payload ORIG record (Seldane 018949, Protropin 019107, Suprol 018217, Femstat 019215) are a pinned, documented openFDA/Drugs@FDA completeness gap.
- **Two flagged source conflicts / irregularities** (documented, never harmonised): Tambocor NDA018830 *Priority* (Compilation) vs *STANDARD* (Drugs@FDA submission field), audit row F1985-054; NDA022046 bupivacaine 1983-07-13 ORIG/AP on a late-1990s application-number series (FDA's 2012 approval letter cross-references NDA016964/NDA018692), annotated `FLAGGED IRREGULARITY` in the orig table.
- **`fda_orig_year_register.csv` now 44 years** (1983–2026); `company_original_approval_scorecard.csv` rebuilt (100 issuers, 1,414 attributed originals, earliest 1983-04-06); `company_clinical_trial_scorecard.csv` rebuilt (421 rows).
- **Validator v15 gates** (`scripts/validate_data.py`): exact 56/89 counts; verbatim payload cross-check of all 145 rows; Type 1/1-4 ban in the extension; furosemide/Trandate pins; NDA022046 annotation pin; 261-row audit shape + per-year pins + payload-set equality; 1985 master-gap pin; year-register pins. **PASS, 0 errors, 1,681 warnings** (intended manual-review baseline).
- **Site:** Pre-1985 tab gained the focus-year audit grid (`#focus-year-audit-view`, filter by year/verdict/tracking table); orig-coverage chart extended to 44 years; counts and methodology text updated in `index.html` and `assets/app.js`.

## Verification already run

```text
python3 scripts/build_original_non_nme.py        # 2,943 rows; register 44 years; v15 gates pass
python3 scripts/build_focus_year_audit_1983_1985.py  # 261 rows; 215 TRACKED_VERIFIED / 46 TRACKED_REVIEW; 0 untracked
python3 scripts/build_orig_scorecard.py          # 100 issuers rebuilt
python3 scripts/build_clinical_trial_scorecard.py    # 421 rows rebuilt
python3 scripts/validate_data.py                 # PASS: 0 errors, 1,681 warnings
```

The orig builder was run three times with a byte-identical CSV (idempotence proven). Existing 1985–2026 rows were diffed against the pre-change snapshot: **zero content changes, zero missing rows**.

## Next work, in priority order

1. **Confirm the merged base still passes** (`python3 scripts/validate_data.py`) before editing anything.
2. **1980–1982 non-NME backward extension (next year-by-year block).** The committed payloads enumerate 73 (1980) + 48 (1981) + 78 (1982) non-Type-1 originals. `build_original_non_nme.py` needs only `FIRST_YEAR = 1980` plus the same pre-1985 ownership rules (the pre-1985 table already owns all 1980–1982 Type 1/1-4 rows and the validator asserts that set equality). Do it **one year at a time** with the focus-audit builder extended to those years, exactly as v15 did for 1983/1984.
3. **Adjudicate the two open v15 review rows** (manual, primary-source): (a) Tambocor NDA018830 Compilation *Priority* vs Drugs@FDA *STANDARD* — check the 1985 annual report (Approvals via PubMed/Pink Sheet) for the contemporaneous designation; (b) NDA022046's 1983 ORIG date — Drugs@FDA application history page review; keep FDA-recorded wording unless a primary 1983 document contradicts it.
4. **Remaining pre-2000 ticker resolution (7 VENUE-VERIFIED rows).** Warner-Lambert ×4 (CIK 104669 FY1998 10-K/DEF 14A/FY1999 10-K), Roberts ×2 (FY1997 10-K accession `0000950130-98-001619`; 1999 DEFM14A `0000950130-99-006712`), Block Drug ×1 (CIK 12654). Use the sandbox page-fetch tool only for SEC primary text (Actions EDGAR returns HTTP 403 — do not retry); extract Item 5/cover sentences verbatim; blank beats guess.
5. **Adjudicate the 141 core-analysis listing-class disagreements** with period 10-K/20-F cover evidence (ADR vs direct: GSK/NVS/RHHBY/AZN/SNY; delisted vs current: SHPG/MDCO/CELG/ALXN). Keep the CORE_CLASS_BASELINE ratchet; change only with a primary citation.
6. **ClinicalTrials.gov Phase 3 depth.** Registry remains the first 2,000 studies in the 2026–2027 completion window; extend via the existing fetch-job pagination machinery with replayable payloads/manifests only.
7. **Decision-engine analysis:** keep expanding PDUFA press-release verification, stock-event coverage, and scorecard quality; keep approval outcome, stock reaction, and phase-transition success as distinct measures.

## Important repository facts

- Branch for all work: `arena/01a0b6a2-druganalysis` (this session fixed to it); origin `https://github.com/buffedlizard55-lab/DrugAnalysis.git`.
- `data/fda_decisions_master.csv` (1,427 rows, 1985–2026) and `data/pre1985_fda_decisions.csv` (91 rows, 1980–1984) were **not modified** in v15; the 1983/1984 additions live in the separate non-NME table by design. Do not merge the tables without a deliberate schema/scorecard decision.
- Single-writer discipline: `build_original_non_nme.py` owns the non-NME CSV + year register; `expand_pre1985_decisions_v14.py` owns the pre-1985 CSV + era CSV; `build_focus_year_audit_1983_1985.py` is read-only over all of them. Rerun the two scorecard builders after any non-NME change.
- Data-fetch convention: bulk openFDA/ctgov/Yahoo jobs run through GitHub Actions; SEC EDGAR uses the sandbox page-fetch tool, one canonical URL at a time; the sandbox has **no direct outbound network** (curl fails — use the page-fetch tool for one-off primary-source checks).
