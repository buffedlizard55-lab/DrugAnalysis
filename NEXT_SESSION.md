# Remaining work for the next session (written 2026-09-19 v21)

Branch: `arena/01a0bba6-druganalysis` (from `main` at `d677b67`). This session extended the
pre-1980 spine from 1977–1979 back to **1965**, built the twelve-year original-application
audit, re-verified the dual-run payload evidence field by field, and cross-checked all of
1965–1976 against the official Drugs@FDA database files. Repository root:
`/home/user/DrugAnalysis`.

## State right now (read this first)

The v21 **builders, validator gates and site are complete and committed**; the **data they
consume has not landed yet**, because it is produced by the GitHub Actions fetch runner and
this sandbox cannot reach the network. Three raw layers are outstanding:

| Layer | Path | Items | Why it is required |
|---|---|---|---|
| Pre-1965 payload block | `data/raw/openfda_orig_decisions_1939_1964/` | 26 year payloads + manifest | the first-appearance screen must be able to see before 1965; the builder aborts without it |
| Per-row live probes | `data/raw/pre1980_row_probes_1965_1976/` | 126 (125 decision rows + amikacin NDA050495) | every new decision row must carry a live MATCH probe; aborts without it |
| Live year populations | `data/raw/pre1980_year_populations_1965_1976/` | 12 | the year-audit `live_population_total` column; 1965/1970/1976 are pinned to 52/74/619 |

`python3 scripts/validate_data.py` currently reports **exactly 75 errors, all of them "v21
data not built yet"** (48-row table vs the 173 baseline, missing probe/cross-check tables,
missing pre-1965 manifest). That is the expected pre-landing state, not a regression: the
v20 gates still pass (170 audit rows, 170 probe rows, 0 payload-invisible).

## Exact next steps

```bash
git pull --rebase origin arena/01a0bba6-druganalysis     # pick up the runner's commit
ls data/raw/openfda_orig_decisions_1939_1964 | head      # expect 26 decisions_YYYY.json + manifest.json
python3 -c "import json;m=json.load(open('data/raw/pre1980_row_probes_1965_1976/manifest.json'));print(len(m['requests']))"   # 126
python3 scripts/build_pre1980_decisions_v21.py           # -> 173 decisions, 15 audit, 15 era, 23 captures, 15 gap rows
python3 scripts/build_pre1980_originals_audit_v21.py     # -> 477 rows, 125 probes, 12 cross-check summaries
python3 scripts/validate_data.py                         # expect 0 errors
node --check assets/app.js
```

**Expect the first build to abort on unadjudicated earlier appearances.** The screen now spans
1939–1979 instead of 1965–1979, so ingredients that first appeared before 1965 (epinephrine and
chlorthalidone are the likely movers) will newly trip the gate. That is the intended behaviour:
read the payload rows the message names, decide whether the ingredient is a combination
component or a same-ingredient sibling, and add a key to `ALLOWED_EARLIER` in
`scripts/build_pre1980_decisions_v21.py` **with its evidence sentence**. Also re-check the
`ALLOWED_EARLIER` note wording: several entries say "first appears on <application> <date>"
using the 1965–1979 screen, and the true first appearance may now be earlier — the computed
`ingredient_first_appearance` column is authoritative, so the notes must not contradict it.

If the runner died instead, re-push anything touching `fetch_jobs/**` to trigger a fresh run
(the bot token cannot dispatch workflows manually, and `gh run cancel` returns 403).

## What v21 shipped (all committed, all verified by execution)

- **`scripts/build_pre1980_decisions_v21.py`** — owns the four pre-1980 tables for 1965–1979
  (173 Type 1/1-4 rows: 11/7/13/4/8/11/7/7/11/16/9/21 for 1965–1976 + 17/18/13 for
  1977–1979). Gates: payload SHA vs manifest, run-18/run-19 `raw_sha256` agreement,
  display-map drift, first-appearance adjudication, per-row live probe equality
  (date + class + priority + holder), pinned live populations, pinned official series.
- **`scripts/build_pre1980_decisions_v19.py`** — marked SUPERSEDED; `main()` fails before
  writing anything. Its `DISPLAY` map is still importable and its 48 entries are
  **byte-identical** to v21's (verified programmatically: 0 value differences).
- **`scripts/build_pre1980_originals_audit_v21.py`** — the v20 three-layer audit for
  1965–1976: 477 payload rows, 125-row probe index, 12-row full-DB cross-check.
- **`scripts/build_pre1980_originals_audit_v20.py`** — display map now imported from v21 and
  its 48-row pin scoped to the 1977–1979 slice of the (now 173-row) decision table.
- **`scripts/validate_data.py`** — 15-year pre-1980 gates + v21 table gates + `read_opt()`
  (a missing table reports an error instead of raising and hiding every other gate).
- **`scripts/tests/dry_run_v21_builders.py`** — harness that runs both builders against a
  `/tmp/v21dry` DATA root: the real committed payloads and full-DB extract are symlinked, only
  the three pending layers are synthesised. This is how the plumbing was verified before the
  data existed, and how the four fail-closed gates were proven to abort.
- **Site** — Pre-1980 tab: four new tables (1965–1976 audit, probe index, full-DB cross-check,
  gap-candidate ledger) and a rewritten narrative stating the verified findings.

## Verified facts worth keeping (re-derive if in doubt)

- **Full-DB cross-check 1965–1976: 477 = 477.** Per year 32/32, 16/16, 32/32, 22/22, 25/25,
  38/38, 48/48, 29/29, 43/43, 73/73, 39/39, 80/80 — **0 payload-invisible, 0 payload-not-in-DB**.
  Consequence: the −52 NME gap for 1965–1976 is a *source-definition* gap, not a fetch gap
  (1967: 189 official NDAs vs 32 ORIG/AP rows). This is different in kind from 1977–1979, where
  the gap class is the Seldane purge.
- **Dual-run evidence:** the archived run-18 manifest and the committed manifest agree on
  `pages[0].raw_sha256` for 1975–1979 and their `decisions` arrays compare equal; the derived
  files differ **only** in `extracted_utc` (04:30:16Z vs 06:19:43Z), which is why the
  file-level SHA differs while the byte counts match exactly. `raw_sha256` is the invariant the
  builder checks — do not "fix" it to compare file SHAs.
- **Four `regulatory_milestone` cells change vs the published 48-row table** (all other 17
  columns of all 48 rows are byte-identical): DDAVP NDA017922, Parlodel NDA017962, Thallous
  Chloride Tl 201 NDA017806 now disclose the multi-product condition instead of asserting one
  dosage form; Motofen NDA017744 describes the `MOTOFEN` record rather than the payload's first
  product, so its marketing status reads `Prescription` (not `Discontinued`).
- **Product selection rule:** payload product whose `brand_name` equals the display brand and
  whose `active_ingredients` contain the mapped ingredient; `PRODUCT_STARTSWITH` pins the exact
  leading ingredient string where that is ambiguous (Duranest → plain etidocaine). Display map:
  173 entries, 0 drift.
- **Live populations:** 1965 = 52, 1970 = 74, 1976 = 619 (V21-C01..C03); 1977/1978/1979 =
  662/756/746 (V19-C01..C03).
- **1976 gap candidate:** amikacin / AMIKIN **NDA050495** — openFDA record exists with **no
  `submissions` array**; Drugs@FDA renders products with no approval-history section. Recorded
  as `NAMED_CANDIDATE_NOT_ADDED`; never an approval row.

## Infrastructure fixes made this session

- `.github/workflows/arena-data-fetch.yml` — concurrency group is now
  `arena-data-fetch-${{ github.ref_name }}`. The old global group let one branch's bulk fetch
  serialise every other branch's (run 22 held the queue ~1.5 h and could not be cancelled:
  `gh run cancel` → 403 for the bot token).
- `fetch_jobs/stock_yahoo_{batch_2026_09,events_remaining,orig_remaining,suppl_remaining}.json`
  — added `"skip_existing": true` (101 line insertions, 0 deletions, so formatting is
  untouched). Without it every run re-downloaded ~3,030 already-committed captures.
  **Edit these job files with targeted line edits, never `json.dump`** — it reformats ~29k lines.

## Next work, in priority order

1. **Land the v21 data and publish** (steps above). Then: scorecards →
   `build_core_analysis_table.py` → `build_company_scores.py` → `validate_data.py`; PR → merge.
2. **Name the missing NMEs: 1977 ×8, 1979 ×1, 1980–84, 1988 ×1.** Route: the 1989 CDER *Offices
   of Drug Evaluation: Statistical Report* (pp. 152–199, FDA History Office Files) or the
   contemporaneous FDA annual report. Contacts: FDA Historian john.swann@fda.hhs.gov;
   CDER.NMENewBiologicApprovals@fda.hhs.gov. Unfixable from public data.
3. **2013 −2, second half** — the CDER posted list (27) is captured; check the 2013 NDA/BLA
   calendar-year approvals page. Do not add Simponi Aria ("inadvertently posted").
4. **CRL↔PDUFA denominator matching** — the engine's blocking limitation; until it is solved
   the engine-gate notice stays and priority-conditioned likelihoods remain refused.
5. **Tambocor 1985 review PDF (human, 2 minutes)** —
   `https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf` (Wayback:
   `https://web.archive.org/web/20240929073454/https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/018830Orig1s000rev.pdf`).
   Automated read returns HTTP 500; do not harmonise the STANDARD/Priority conflict without it.
6. **NDA022046 lineage artifact** — needs a 1983 approval letter or Federal Register notice.
7. **141 core-analysis listing-class disagreements** — adjudicate with period 10-K/20-F cover
   evidence; keep the `CORE_CLASS_BASELINE` ratchet.
8. **Pre-1980 backfill beyond 1965** — 1964 → 1939 is the natural continuation. The payload job
   already covers 1939–1964 (fetched for the screen); Drugs@FDA coverage before 1965 is
   incomplete, so those rows would need a different primary source (FDA annual reports) and the
   screen must stay labelled a re-approval screen, not proof of first marketing.
