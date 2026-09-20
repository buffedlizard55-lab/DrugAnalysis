# Remaining work for the next session (written 2026-09-20, v21.1)

Branch: `arena/01a0bc8d-druganalysis` (from `main` at `6cb77f6`). This session merged the
v21 runner commit (`24ab5ca`, Actions run 26) into the branch, ran all three pre-1980
builders, adjudicated every newly-visible earlier appearance in the extended 1939–1979
first-appearance screen, classified the 308-row gap class with the delivered
`Applications_all_types.txt`, re-derived the 1977–1979 full-DB cross-check the same way,
and updated the site. **`python3 scripts/validate_data.py` now reports PASS with 0 errors.**
Repository root: `/home/user/DrugAnalysis`.

## State right now (read this first)

All v21 data has landed and been built:

| Layer | Path | Items | Status |
|---|---|---|---|
| Pre-1965 payload block | `data/raw/openfda_orig_decisions_1939_1964/` | 26 year payloads + manifest | LANDED (run 26), SHA-verified by the builder |
| Per-row live probes | `data/raw/pre1980_row_probes_1965_1976/` | 126 (125 decision rows + amikacin NDA050495) | LANDED, 125/125 MATCH |
| Live year populations | `data/raw/pre1980_year_populations_1965_1976/` | 12 | LANDED; 1965/1970/1976 pinned 52/74/619 |
| Unfiltered application map | `data/raw/drugsatfda_data_files_2026_09/Applications_all_types.txt` | 29,336 applications | LANDED; verified strict superset of the window file (2,325/2,325, 0 type disagreements) |

Built tables (all validator-green): 173 pre-1980 decisions (1965–1979; 125 live MATCH
probes), 15 year-audit rows, 15 era rows, 23 captures, 15 gap-candidate rows, 477-row
1965–1976 original-application audit + 125-row probe index + 12 SUMMARY-row full-DB
cross-check (320 rows total), 170-row 1977–1979 audit + 170-row probe index + 3 SUMMARY
cross-check (82 rows total).

## What v21.1 verified this session (re-derive if in doubt)

- **The 308 1965–1976 `KIND_UNRESOLVED` rows are now CLASSIFIED, not pending.** All 308
  ApplNos are absent from the unfiltered `Applications_all_types.txt` — i.e. **no
  `Applications` record exists for any of them anywhere in the Drugs@FDA database**. This
  is a deeper invisibility class than the Seldane purge: the application is present in the
  official Submissions file, absent from the Applications table, and renders an empty
  application shell on Drugs@FDA (already spot-checked for 014262/017383/016486 in v21,
  control NDA050495 renders in full). The six NME-comparable rows (1966 014262 TYPE 1/4,
  1969 016486 TYPE 1/4, 1970 016771 TYPE 1/4, 1973 017383 TYPE 1 PRIORITY, 1973 017024
  TYPE 1, 1973 017267 TYPE 1 PRIORITY) plus 1976 017834 TYPE 2 remain review candidates —
  named, never added.
- **1977–1979 cross-check re-derived (v20.1):** `build_pre1980_originals_audit_v20.py` now
  uses the unfiltered map when present and reports (instead of silently dropping) untypeable
  rows. Result: 42/42, 66/66, 62/62 — **0 payload-invisible**, 479 ANDA originals excluded,
  **79 `KIND_UNRESOLVED` rows** (32/28/19). **New named candidate: 012043, 1978-10-16,
  TYPE 1/4** (NME-comparable; 1978 has no official shortfall, so it is inventory, not a
  gap-filler). The v20 "0 payload-invisible" claim for 1977–1979 now rests on the same
  unfiltered-map basis as v21 — the circularity called out in the previous note is closed.
- **First-appearance screen now spans 1939–1979** in all three pre-1980 builders. Six new
  `ALLOWED_EARLIER` adjudications (each with payload evidence) and five wording corrections:
  1965 Cordran flurandrenolide (first on NDA013790, 1963-03-19, TYPE 3 — a new class/date
  inversion, 27 months before the TYPE 1), 1965 Citanest epinephrine bitartrate (first on
  Medihaler-Epi NDA010374, 1956), 1966 Ovulen-21 mestranol (first on Enovid NDA010976,
  1961), 1968 Ovral ethinyl estradiol (first on Estinyl NDA005292, 1943), 1974 Combipres
  chlorthalidone (first on Hygroton NDA012283, 1960), 1978 Motofen atropine sulfate (first
  on Lomotil NDA012462, 1960, TYPE 4). Corrected wording for epinephrine ×3,
  sulfamethoxazole (now NDA013664 first, then NDA012715), and **clonidine**: the old
  "12 days earlier on Catapres" claim had no payload support — NDA017407's committed
  top-level date is the same as Combipres' (1974-09-03) and it publishes no submissions
  array, so the pairing is published as same-day.
- **Two pre-existing validator gate bugs were caught by the first real run** and fixed:
  the 1939–1964 block gate matched request ids `decisions_YYYY` but the runner writes
  `orig_decisions_YYYY` (now matched by year suffix + the job's `out_template` filename);
  the amikacin mechanism needle is case-insensitive.
- **48 v19 decision rows (1977–1979):** only the `notes` column changed (screen label
  1965–1979 → 1939–1979, Motofen gains the atropine adjudication) plus the four already-
  documented `regulatory_milestone` cells (DDAVP 017922, Parlodel 017962, Thallous 017806,
  Motofen 017744). All other 17 columns byte-identical to the v20-published table.
- **Dual-run evidence:** unchanged invariant — the builder checks `pages[0].raw_sha256`
  agreement for 1975–1979, not file SHA. Do not "fix" it.

## Exact re-verify commands

```bash
python3 scripts/build_pre1980_decisions_v21.py    # -> 173 decisions, 15 audit, 15 era, 23 captures, 15 gap rows
python3 scripts/build_pre1980_originals_audit_v21.py  # -> 477 rows, 125 probes, 12 cross-check summaries
python3 scripts/build_pre1980_originals_audit_v20.py  # -> 170 rows, 170 probes, 3 cross-check summaries (82 cross rows)
python3 scripts/validate_data.py                  # -> PASS, 0 errors
node --check assets/app.js
python3 scripts/tests/dry_run_v21_builders.py     # fail-closed gates still abort
```

## Next work, in priority order

1. **Name the missing NMEs: 1977 ×8, 1979 ×1, and the 1965–1975 shortfalls (−52).** Route:
   the 1989 CDER *Offices of Drug Evaluation: Statistical Report* (pp. 152–199, FDA History
   Office Files) or the contemporaneous FDA annual report. Contacts: FDA Historian
   john.swann@fda.hhs.gov; CDER.NMENewBiologicApprovals@fda.hhs.gov. The public-data route is
   now exhausted: full-DB cross-checks are re-derived on the unfiltered map for 1965–1979,
   0 payload-invisible everywhere, and the 6+1 NME-comparable `KIND_UNRESOLVED` candidates
   have no Applications record anywhere (so Drugs@FDA cannot name them either).
   1980–1984 and 1988 ×1: still need the same 1989 CDER typescript route.
2. **2013 second half** — the CDER posted list (27) is captured; check the 2013 NDA/BLA
   calendar-year approvals page. Do not add Simponi Aria ("inadvertently posted").
3. **CRL↔PDUFA denominator matching** — the engine's blocking limitation; until it is
   solved the engine-gate notice stays and priority-conditioned likelihoods remain refused.
4. **Tambocor 1985 review PDF (human, 2 minutes)** —
   `https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf`
   (Wayback: `https://web.archive.org/web/20240929073454/https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf`).
   Automated read returns HTTP 500; do not harmonise the STANDARD/Priority conflict without it.
5. **NDA022046 lineage artifact** — needs a 1983 approval letter or Federal Register notice.
6. **141 core-analysis listing-class disagreements** — adjudicate with period 10-K/20-F cover
   evidence; keep the `CORE_CLASS_BASELINE` ratchet.
7. **New `KIND_UNRESOLVED` review candidates to adjudicate year by year** (from the
   re-derived cross-checks): 1966 014262, 1969 016486, 1970 016771, 1973 017383/017024/
   017267, 1976 017834 (TYPE 2), and **012043 (1978, TYPE 1/4 — new this session)**.
   All have no Applications record in the full DB; the only naming route is the
   contemporaneous record (item 1).
8. **Pre-1980 backfill beyond 1965** — 1964 → 1939 is the natural continuation. The payload
   block already covers 1939–1964 (fetched for the screen, 566 ORIG/AP rows enumerated).
   Drugs@FDA coverage before 1965 is incomplete, so those rows would need a different
   primary source (FDA annual reports) and the screen must stay labelled a re-approval
   screen, not proof of first marketing. The 1965–1979 decision table currently stops at
   1965 by design (Drugs@FDA's reliable application-level window).
9. **Amikacin 1976 confirmation** — the named candidate for 1976's single gap slot needs the
   contemporaneous record to confirm (no submission history published by FDA).

## Infrastructure notes (unchanged from v21)

- `.github/workflows/arena-data-fetch.yml` — concurrency group is per-branch
  (`arena-data-fetch-${{ github.ref_name }}`).
- Bulk fetching still depends on the Actions runner (bot token can't dispatch manually;
  pushes touching `fetch_jobs/**` are the trigger), sandbox limited to one-off primary
  checks.
- Edit fetch job JSON files with targeted line edits, never `json.dump` (reformats ~29k lines).
- The v21 runner commit pattern to remember: the v21 branch merged to main *before* its
  runner commit landed; always check the session branch for runner commits after a merge.
