#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the v17 declarative fetch-job specs (GitHub Actions runner).

The editing sandbox has no general outbound network access, so every bulk
official-source payload is fetched by `.github/workflows/arena-data-fetch.yml`
and committed verbatim under `data/raw/<job-id>/` with a SHA-256 manifest.
This script writes the three job specs the v17 session needs. It is
deterministic: re-running rewrites byte-identical files from the committed
CSVs, and it never invents a request that is not traceable to a committed row.

Jobs produced
-------------
1. ``fetch_jobs/openfda_orig_decisions_1970_1979.json``
   Backward extension of the Drugs@FDA ORIGINAL-approval enumeration to
   1970-1979 (the committed payloads currently start at 1980). Same
   auditable ``ORIG + AP + submission_status_date in year`` filter, same
   per-record projection, same manifest contract as the 1980-1984 and
   1985-2026 jobs.

2. ``fetch_jobs/openfda_efficacy_supplements.json`` (in-place year extension)
   Adds calendar years 1980-1999 to the existing efficacy-supplement job.
   ``skip_existing: true`` means the 27 already-committed 2000-2026 payloads
   are not re-fetched; only the 20 new years are requested, and they land in
   the SAME directory the existing consumer
   ``scripts/build_supplement_decisions.py`` already globs.

3. ``fetch_jobs/stock_yahoo_events_formerly_listed.json``
   The price-event queue for master rows whose ticker is a bare A-Z symbol,
   whose recorded US listing class is FORMERLY US-LISTED (DELISTED/ACQUIRED)
   (plus any still-US-LISTED row) and which have NO committed price snapshot
   and are NOT already queued in the two existing Yahoo jobs. Delisted
   symbols frequently fail on Yahoo, and a retired symbol may since have been
   re-used by an unrelated issuer - so the consumer for this directory
   (``scripts/build_stock_snapshots_formerly_listed.py``) applies an identity
   gate: the payload's own ``meta.longName``/``meta.symbol``/``exchangeName``
   must match the recorded company before a price is published. A failure or
   an identity mismatch is recorded, never retried with a successor ticker
   and never guessed (repo law: the failure IS the data).

Hallucination controls
----------------------
* No URL is written unless it is derived from a committed, already-verified
  row of ``data/fda_decisions_master.csv`` / ``data/stock_price_snapshots.csv``.
* NON-US-LISTING-ONLY rows are deliberately EXCLUDED from the price queue:
  their recorded symbol is a foreign-line symbol and Yahoo requires an
  exchange suffix that this repository has not verified. Queueing them would
  invite a wrong-issuer price. They stay on the carried-over list.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "fetch_jobs"
DATA = ROOT / "data"

MASTER = DATA / "fda_decisions_master.csv"
SNAP = DATA / "stock_price_snapshots.csv"

CLEAN_TICKER = re.compile(r"^[A-Z]{1,5}$")

OPENFDA_ENDPOINT = "https://api.fda.gov/drug/drugsfda.json"
ORIG_SEARCH = ('submissions.submission_type:"ORIG" AND submissions.submission_status:"AP" '
               'AND submissions.submission_status_date:[{start} TO {end}]')
SUPPL_SEARCH = ('submissions.submission_type:"SUPPL" AND submissions.submission_class_code:"EFFICACY" '
                'AND submissions.submission_status:"AP" '
                'AND submissions.submission_status_date:[{start} TO {end}]')

PRE1980_YEARS = list(range(1970, 1980))
SUPPL_EXISTING_YEARS = list(range(2000, 2027))
SUPPL_NEW_YEARS = list(range(1980, 2000))


def epoch(d: str) -> int:
    return int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())


def yahoo_window(decision_date: str):
    """[-12 days, +13 days) around the decision date - the committed convention."""
    dd = dt.date.fromisoformat(decision_date)
    p1 = epoch((dd - dt.timedelta(days=12)).isoformat())
    p2 = epoch((dd + dt.timedelta(days=13)).isoformat()) - 1
    return p1, p2


def job_orig_1970_1979() -> Path:
    out = JOBS / "openfda_orig_decisions_1970_1979.json"
    spec = [{
        "type": "openfda_decisions",
        "id": "orig_decisions",
        "endpoint": OPENFDA_ENDPOINT,
        "search_template": ORIG_SEARCH,
        "years": PRE1980_YEARS,
        "limit": 1000,
        "max_pages": 12,
        "sleep": 0.4,
        "out_template": "decisions_{year}.json",
        "skip_existing": True,
        "_why": ("Pre-1980 backward extension of the Drugs@FDA ORIGINAL-approval enumeration. "
                 "The committed payloads currently start at 1980 "
                 "(data/raw/openfda_orig_decisions_1980_1984). This job adds 1970-1979 with the "
                 "identical auditable filter (ORIG + AP + submission_status_date inside the year, "
                 "NDA/BLA only, ANDA excluded at extraction) so the same year-by-year treatment can "
                 "be applied: Type 1/1-4 NMEs to data/pre1985_fda_decisions.csv, every other "
                 "chemical type to data/fda_original_non_nme_decisions.csv, and the complete "
                 "enumeration audited in data/focus_years_pre1980_audit.csv. Caveat recorded up "
                 "front: Drugs@FDA submission records for the 1970s are less complete than for "
                 "later decades (many pre-1975 NDAs predate electronic application tracking and the "
                 "DESI reclassification programme), so a year count from this extract is an "
                 "application-level enumeration of what FDA publishes today, never a claimed "
                 "contemporaneous FDA annual statistic."),
    }]
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def job_supplements_extend() -> Path:
    out = JOBS / "openfda_efficacy_supplements.json"
    spec = [{
        "type": "openfda_supplements",
        "id": "eff_suppl",
        "endpoint": OPENFDA_ENDPOINT,
        "search_template": SUPPL_SEARCH,
        "years": SUPPL_NEW_YEARS + SUPPL_EXISTING_YEARS,
        "limit": 1000,
        "max_pages": 12,
        "sleep": 0.4,
        "out_template": "suppl_{year}.json",
        "skip_existing": True,
        "_why": ("v17 extension: calendar years 1980-1999 added ahead of the already-committed "
                 "2000-2026 block. skip_existing=true leaves the 27 committed payloads untouched, "
                 "so only the 20 new years are requested and they land in the same directory "
                 "(data/raw/openfda_efficacy_supplements) that scripts/build_supplement_decisions.py "
                 "already globs. This closes the label-expansion blind spot for the pre-2000 era: "
                 "efficacy supplements are FDA's dated decisions on whether NEW clinical trial data "
                 "support a NEW indication for an already-marketed drug, and they are the largest "
                 "body of officially documented FDA efficacy decisions per year."),
    }]
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def job_yahoo_formerly_listed() -> tuple[Path, int, dict]:
    """Queue price events for FORMERLY-US-LISTED master rows with a bare symbol."""
    have_snap = set()
    for r in csv.DictReader(open(SNAP, newline="", encoding="utf-8-sig")):
        have_snap.add((r["ticker"].strip(), r["decision_date"].strip()))

    queued = set()
    for job in ("stock_yahoo_events_1985_1998.json", "stock_yahoo_events_1998_2026.json"):
        p = JOBS / job
        if p.exists():
            for spec in json.load(open(p)):
                for it in spec.get("items", []):
                    queued.add((it["ticker"], it["decision_date"]))

    items, seen = [], set()
    skipped_non_us = 0
    for r in csv.DictReader(open(MASTER, newline="", encoding="utf-8-sig")):
        tk = (r.get("ticker") or "").strip()
        cls = (r.get("us_investable_class") or "").strip()
        d = (r.get("decision_date") or "").strip()
        if not CLEAN_TICKER.match(tk) or not d:
            continue
        if cls == "NON-US LISTING ONLY":
            skipped_non_us += 1
            continue
        if not (cls.startswith("FORMERLY US-LISTED") or cls.startswith("US-LISTED")):
            continue
        key = (tk, d)
        if key in have_snap or key in queued or key in seen:
            continue
        seen.add(key)
        p1, p2 = yahoo_window(d)
        items.append({
            "id": f"{tk}_{d}",
            "url": (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
                    f"?period1={p1}&period2={p2}&interval=1d&includePrePost=false"),
            "out": f"{tk}_{d}.json",
            "ticker": tk,
            "decision_date": d,
            "decision_type": r.get("decision_type", ""),
            "expected_company": r.get("company_name", ""),
            "expected_class": cls,
            "exchange_recorded": (r.get("exchange") or "").strip(),
            "source": "Yahoo Finance chart API",
            "event_source": r.get("decision_id", ""),
            "identity_gate": ("consumer must match payload meta.longName/shortName/symbol against "
                              "expected_company before publishing a price; a retired symbol may have "
                              "been re-used by an unrelated issuer"),
        })
    items.sort(key=lambda x: (x["decision_date"], x["ticker"]))
    spec = [{
        "type": "generic",
        "id": "yahoo_chart_events_formerly_listed",
        "sleep": 0.6,
        "timeout": 60,
        "retries": 3,
        "skip_existing": True,
        "_why": ("Price-event queue for master rows that carry a period US ticker but no committed "
                 "snapshot: FORMERLY US-LISTED (DELISTED/ACQUIRED) issuers (including the six rows "
                 "resolved from primary SEC text in v16 - Warner-Lambert NYSE:WLA x4 and Roberts "
                 "Nasdaq NMS:RPCX x2) plus any still-US-LISTED row missed by the two existing jobs. "
                 "NON-US-LISTING-ONLY rows are excluded on purpose: their recorded symbol is a "
                 "foreign-line symbol and the Yahoo exchange suffix has not been verified in this "
                 "repository, so queueing them would risk a wrong-issuer price. Delisted symbols "
                 "often fail; failures are recorded in the manifest and never retried with a "
                 "successor ticker."),
        "items": items,
    }]
    out = JOBS / "stock_yahoo_events_formerly_listed.json"
    out.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out, len(items), {"skipped_non_us_listing_only": skipped_non_us,
                             "already_queued_or_priced": len(queued | have_snap)}


def main() -> int:
    a = job_orig_1970_1979()
    b = job_supplements_extend()
    c, n, extra = job_yahoo_formerly_listed()
    print(f"wrote {a.relative_to(ROOT)}  (years {PRE1980_YEARS[0]}-{PRE1980_YEARS[-1]})")
    print(f"wrote {b.relative_to(ROOT)}  (years {SUPPL_NEW_YEARS[0]}-{SUPPL_NEW_YEARS[-1]} new + "
          f"{SUPPL_EXISTING_YEARS[0]}-{SUPPL_EXISTING_YEARS[-1]} existing, skip_existing)")
    print(f"wrote {c.relative_to(ROOT)}  ({n} price events; {extra})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
