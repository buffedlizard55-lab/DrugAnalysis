# Remaining work for the next session (written 2026-09-20, v22)

Branch: `arena/01a0bd2c-druganalysis` (from `main` at `b6cdb8a`). This session implemented
the 1977–1979 year-by-year workbench: named 1979×1 Selacryn (NDA 18-103) as
`NAMED_CANDIDATE_NOT_ADDED`, adjudicated the 7 KIND_UNRESOLVED NME-comparable rows
(012043 = 1978 inventory), and left 1977×8 unnamed. **Do not merge or switch to
`main`.** Open the PR from this arena branch only.

## State right now (read this first)

| Layer | Path | Status |
|---|---|---|
| Decision table | `data/pre1980_fda_decisions.csv` | **173 rows, unchanged.** Selacryn / 018103 / 012043 are **not** in it |
| Gap ledger | `data/missing_nme_candidates.csv` | 15 years, one row each. Named: 1976 amikacin NDA050495, **1979 Selacryn NDA018103** |
| Year focus | `data/pre1980_year_focus_1977_1979.csv` | 1979 named-not-added; 1978 CLOSED; 1977 remaining 8 unnamed |
| KIND_UNRESOLVED NME | `data/pre1980_kind_unresolved_nme_adjudication.csv` | 7 rows, all `KIND_UNRESOLVED_NOT_ADDED` |
| Search log | `data/pre1980_1977_gap_search_log.csv` | Public-data searches; **no invented 1977 names** |
| FR capture | `data/raw/source_captures_2026_09_20/live_primary_captures_v22_2026_09_20.json` | V22-C01..C03 |

Official vs enumerated: **1977 25 vs 17 (−8 unnamed)**; **1978 17 vs 18 (+1 Motofen, CLOSED)**;
**1979 14 vs 13 (−1 named Selacryn, not added)**. 170/170 probes MATCH. 79 KIND_UNRESOLVED
(32/28/19); 1977 and 1979 have **0** KIND_UNRESOLVED TYPE 1/1-4.

## What v22 verified (do not re-query Applications/Submissions/Products to name NMEs)

- **Selacryn (ticrynafen) NDA 18-103 / 018103** is named by Federal Register 61 FR 25228
  (1996-05-20, Docket 96N-0151). Marketing stopped 1980 for post-approval liver toxicity.
  The FR does **not** state the original approval date. Application 018103 = **0 hits** in
  Applications_all_types (29,336), Submissions_1965_1979, Products, and every 1965–1979
  payload. This is the Seldane-class purge proven by a named NDA, distinct from amikacin
  NDA050495 (openFDA shell, no submissions array).
- Literature 1979-05-02 is **not** an FDA-database date. The 1979 TYPE 1 list has no May 2
  (gap Apr 4 Ceclor → May 15 Nubain).
- **012043** is Submissions-only ORIG/AP 1978-10-16 TYPE 1/4 STANDARD. 1978 has no shortfall.
- **1977×8:** Hussar 1978 AJN is paywalled and was not used as names. KIND_UNRESOLVED 1977
  has 0 TYPE 1/1-4. Do not invent the eight names.

## Exact re-verify commands

```bash
python3 scripts/build_pre1980_decisions_v21.py
python3 scripts/build_pre1980_focus_1977_1979_v22.py
python3 scripts/validate_data.py
node --check assets/app.js
```

## Next work, in priority order

1. **Name 1977×8 and confirm Selacryn as the 1979 NME.** Route: 1989 CDER *Offices of Drug
   Evaluation: Statistical Report* (pp. 152–199, FDA History Office Files) or the
   contemporaneous FDA annual report. Contacts: FDA Historian john.swann@fda.hhs.gov;
   CDER.NMENewBiologicApprovals@fda.hhs.gov. Public Drugs@FDA / openFDA / remaining FDA
   files are exhausted for naming purged NMEs (018103 is the proof).
2. **1965–1975 shortfalls (−52)** — same typescript route. The 6 NME-comparable
   KIND_UNRESOLVED rows (014262 / 016486 / 016771 / 017383 / 017024 / 017267) stay review
   candidates, never approvals.
3. **CRL↔PDUFA denominator matching** — the engine's blocking limitation; until it is
   solved the engine-gate notice stays and priority-conditioned likelihoods remain refused.
4. **Tambocor 1985 review PDF (human, 2 minutes)** —
   `https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf`
   (Wayback 20240929073454). Automated read returns HTTP 500.
5. **NDA022046 lineage artifact** — 1983 approval letter or Federal Register notice.
6. **141 core-analysis listing-class disagreements** — period 10-K/20-F cover evidence;
   keep the `CORE_CLASS_BASELINE` ratchet.
7. **2013 second half** — CDER posted list (27) is captured; do not add Simponi Aria.
8. **1,000 new 2000–2026 NME entries** — still blocked. The NME master already matches
   the official series; ~50 NMEs/year means 1,000 *new novels* do not exist. Growth =
   supplements / originals / prices / pre-1980 backfill. Bulk fetch still depends on the
   Actions runner (`fetch_jobs/**` push). Do not invent rows.
9. **Pre-1980 backfill beyond 1965** — 1964 → 1939 payloads already exist (566 ORIG/AP);
   Drugs@FDA coverage before 1965 is incomplete.

## Standing rules (do not reverse)

- Do not add Selacryn (or any literature-named candidate) to `pre1980_fda_decisions.csv`
  without remaining FDA appl_no/date/class/priority. Pattern: `NAMED_CANDIDATE_NOT_ADDED`.
- Do not invent missing NME names. Do not print likelihoods without CRL↔PDUFA matching.
- Do not “fix” the dual-run SHA invariant (`pages[0].raw_sha256` 1975–1979).
- Do not json.dump fetch job files. Do not merge to `main` from this session.
- Validator gap-candidate allowlist is `{NDA050495, NDA018103, ""}` — still exactly one
  row per year 1965–1979.

## Infrastructure notes (unchanged)

- `.github/workflows/arena-data-fetch.yml` — concurrency group is per-branch.
- Bulk fetching still depends on the Actions runner; sandbox limited to one-off primary
  checks.
- Edit fetch job JSON files with targeted line edits, never `json.dump`.
