#!/usr/bin/env python3
"""Declarative collector for officially-sourced payloads.

Runs on the GitHub Actions runner (see .github/workflows/arena-data-fetch.yml)
because the editing sandbox has no general outbound network access.

Design rules — these exist so the data cannot drift into hallucination:

* Payloads are written **verbatim**. The only transformation allowed is an
  explicit *projection* (a whitelist of fields copied value-for-value) used to
  keep the repository small; no value is ever rewritten, derived or filled in.
* Every output file is accompanied by a `manifest.json` recording the exact
  request URL, HTTP status, byte count and SHA-256 of the payload that was
  received, so any downstream row can be re-verified against its primary
  source by re-issuing the recorded request.
* Failed fetches are recorded as failures in the manifest. Nothing is retried
  into existence and nothing is synthesised.

Usage:
    python3 scripts/run_fetch_jobs.py fetch_jobs/<job>.json [...]
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = (
    "DrugAnalysis-Research-Bot/1.0 (open academic data collection; "
    "repository: github.com/buffedlizard55-lab/DrugAnalysis; "
    "contact: buffedlizard55-lab@users.noreply.github.com)"
)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def http_get(url: str, timeout: float = 180.0, retries: int = 4, sleep: float = 3.0,
             headers: dict | None = None):
    """Return (status, body_bytes). Raises on final failure."""
    last = None
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/csv,text/plain,*/*",
    }
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except Exception as exc:  # noqa: BLE001 - record whatever went wrong
            last = f"{type(exc).__name__}: {exc}"
            if attempt < retries - 1:
                time.sleep(sleep * (attempt + 1))
    raise RuntimeError(last or "unknown fetch error")


def project(obj, spec):
    """Whitelist-copy values out of decoded JSON (values never modified)."""
    if spec is None:
        return obj
    if isinstance(spec, dict) and spec.get("__all__"):
        return obj
    if isinstance(obj, dict):
        out = {}
        for key, sub in spec.items():
            if key in obj:
                out[key] = project(obj[key], sub)
        return out
    if isinstance(obj, list):
        return [project(item, spec[0] if isinstance(spec, list) and spec else {}) for item in obj]
    return obj


def write_payload(dest: str, body: bytes, meta: dict) -> None:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(body)
    meta["bytes"] = len(body)
    meta["sha256"] = hashlib.sha256(body).hexdigest()
    meta["written_at_utc"] = _now()


def load_manifest(outdir: str) -> dict:
    path = os.path.join(outdir, "manifest.json")
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:  # noqa: BLE001
            pass
    return {"job": os.path.basename(outdir), "generated_utc": _now(), "requests": []}


# --------------------------------------------------------------------------
# job kinds
# --------------------------------------------------------------------------

def job_url(spec: dict, outdir: str, entries: list) -> None:
    sid = spec["id"]
    dest = os.path.join(outdir, spec.get("out", f"{sid}.json"))
    if spec.get("skip_existing") and os.path.exists(dest) and os.path.getsize(dest) > 0:
        entries.append({"id": sid, "status": "skipped-existing", "out": spec.get("out")})
        return
    url = spec["url"]
    try:
        status, body = http_get(url, timeout=spec.get("timeout", 180), retries=spec.get("retries", 4),
                                headers=spec.get("headers"))
    except RuntimeError as exc:
        entries.append({"id": sid, "url": url, "status": "FAILED", "error": str(exc), "at_utc": _now()})
        print(f"FAIL {sid}: {exc}", flush=True)
        return
    meta = {"id": sid, "url": url, "status": status}
    if spec.get("project") and spec.get("out", "").endswith(".json"):
        try:
            decoded = json.loads(body.decode("utf-8"))
            meta["raw_sha256"] = hashlib.sha256(body).hexdigest()
            meta["raw_bytes"] = len(body)
            if isinstance(decoded, dict) and isinstance(decoded.get("results"), list):
                decoded = {
                    "meta": decoded.get("meta"),
                    "results": [project(r, spec["project"]) for r in decoded["results"]],
                }
            else:
                decoded = project(decoded, spec["project"])
            body = json.dumps(decoded, separators=(",", ":")).encode("utf-8")
            meta["projected"] = True
        except Exception as exc:  # noqa: BLE001
            meta["project_error"] = str(exc)
    write_payload(dest, body, meta)
    entries.append(meta)
    print(f"ok {sid} {status} {meta.get('bytes')} bytes -> {dest}", flush=True)
    time.sleep(spec.get("sleep", 0.3))


def job_openfda_years(spec: dict, outdir: str, entries: list) -> None:
    """Paged openFDA search, one output file per year."""
    endpoint = spec["endpoint"]
    template = spec["search_template"]
    limit = int(spec.get("limit", 1000))
    max_pages = int(spec.get("max_pages", 25))
    years = spec["years"]
    for year in years:
        sid = f"{spec['id']}_{year}"
        out_name = spec.get("out_template", "{year}.json").format(year=year)
        dest = os.path.join(outdir, out_name)
        if spec.get("skip_existing") and os.path.exists(dest) and os.path.getsize(dest) > 0:
            entries.append({"id": sid, "status": "skipped-existing", "out": out_name})
            continue
        search = template.format(year=year, start=f"{year}0101", end=f"{year}1231")
        collected, page, requests = [], 0, []
        while page < max_pages:
            skip = page * limit
            qsearch = urllib.parse.quote(search, safe=':+[]"')
            url = f"{endpoint}?search={qsearch}&limit={limit}&skip={skip}"
            try:
                status, body = http_get(url, timeout=spec.get("timeout", 180), retries=spec.get("retries", 4))
            except RuntimeError as exc:
                entries.append({"id": sid, "url": url, "status": "FAILED", "error": str(exc), "at_utc": _now()})
                print(f"FAIL {sid} page {page}: {exc}", flush=True)
                break
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                entries.append({"id": sid, "url": url, "status": "BAD_JSON", "error": str(exc)})
                break
            results = payload.get("results", [])
            requests.append({"url": url, "status": status, "n": len(results),
                             "sha256": hashlib.sha256(body).hexdigest(), "at_utc": _now()})
            collected.extend(results)
            if len(results) < limit:
                break
            page += 1
            time.sleep(spec.get("sleep", 0.3))
        payload_out = {
            "meta": {
                "source_endpoint": endpoint,
                "search": search,
                "year": year,
                "record_count": len(collected),
                "fetched_utc": _now(),
            },
            "results": collected,
        }
        body = json.dumps(payload_out, separators=(",", ":")).encode("utf-8")
        if spec.get("project"):
            trimmed = project(payload_out, {"meta": {"__all__": True}, "results": spec["project"]})
            body = json.dumps(trimmed, separators=(",", ":")).encode("utf-8")
        meta = {"id": sid, "endpoint": endpoint, "search": search, "pages": requests,
                "records": len(collected), "status": 200}
        write_payload(dest, body, meta)
        entries.append(meta)
        print(f"ok {sid}: {len(collected)} records -> {dest}", flush=True)


def job_openfda_decisions(spec: dict, outdir: str, entries: list) -> None:
    """Fetch openFDA Drugs@FDA pages per year and commit *only* the extracted
    original-approval decisions.

    The raw payloads for a single year run to ~10-15 MB (every supplement ever
    filed against every application), which is far too large to keep in git.
    The extraction is a pure, deterministic filter implemented in
    scripts/openfda_decisions.py: it emits one record per NDA/BLA whose ORIG
    submission was approved in the target year. The manifest records every
    request URL and the SHA-256 of each raw payload, so the extraction can be
    reproduced and audited at any time.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from openfda_decisions import extract_year  # noqa: WPS433

    endpoint = spec["endpoint"]
    template = spec["search_template"]
    limit = int(spec.get("limit", 1000))
    max_pages = int(spec.get("max_pages", 25))
    for year in spec["years"]:
        sid = f"{spec['id']}_{year}"
        out_name = spec.get("out_template", "decisions_{year}.json").format(year=year)
        dest = os.path.join(outdir, out_name)
        if spec.get("skip_existing") and os.path.exists(dest) and os.path.getsize(dest) > 0:
            entries.append({"id": sid, "status": "skipped-existing", "out": out_name})
            continue
        search = template.format(year=year, start=f"{year}0101", end=f"{year}1231")
        collected, page, requests = [], 0, []
        while page < max_pages:
            skip = page * limit
            qsearch = urllib.parse.quote(search, safe=':+[]"')
            url = f"{endpoint}?search={qsearch}&limit={limit}&skip={skip}"
            try:
                status, body = http_get(url, timeout=spec.get("timeout", 180),
                                        retries=spec.get("retries", 4))
            except RuntimeError as exc:
                entries.append({"id": sid, "url": url, "status": "FAILED", "error": str(exc),
                                "at_utc": _now()})
                print(f"FAIL {sid} page {page}: {exc}", flush=True)
                break
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                entries.append({"id": sid, "url": url, "status": "BAD_JSON", "error": str(exc)})
                break
            results = payload.get("results", [])
            requests.append({"url": url, "status": status, "n_raw_records": len(results),
                             "raw_sha256": hashlib.sha256(body).hexdigest(), "at_utc": _now()})
            collected.extend(extract_year(payload, year, url))
            if len(results) < limit:
                break
            page += 1
            time.sleep(spec.get("sleep", 0.3))
        # de-duplicate across pages
        seen, uniq = set(), []
        for d in collected:
            key = (d["application_number"], d["decision_date"])
            if key not in seen:
                seen.add(key)
                uniq.append(d)
        uniq.sort(key=lambda d: (d["decision_date"], d["application_number"]))
        body = json.dumps({"year": year, "source_endpoint": endpoint, "search": search,
                           "count": len(uniq), "extracted_utc": _now(), "decisions": uniq},
                          separators=(",", ":")).encode("utf-8")
        meta = {"id": sid, "endpoint": endpoint, "search": search, "pages": requests,
                "decisions": len(uniq), "status": 200}
        write_payload(dest, body, meta)
        entries.append(meta)
        print(f"ok {sid}: {len(uniq)} decisions -> {dest}", flush=True)


def job_openfda_supplements(spec: dict, outdir: str, entries: list) -> None:
    """Fetch openFDA Drugs@FDA pages per year and commit *only* the extracted
    **efficacy supplement** approvals (new indications / new populations).

    Same contract as ``job_openfda_decisions``: the multi-megabyte raw payload
    is never committed, but the manifest records every request URL and the
    SHA-256 of each raw page so the deterministic extraction implemented in
    scripts/openfda_supplements.py can be reproduced and audited.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from openfda_supplements import extract_year as extract_suppl_year  # noqa: WPS433

    endpoint = spec["endpoint"]
    template = spec["search_template"]
    limit = int(spec.get("limit", 1000))
    max_pages = int(spec.get("max_pages", 25))
    for year in spec["years"]:
        sid = f"{spec['id']}_{year}"
        out_name = spec.get("out_template", "suppl_{year}.json").format(year=year)
        dest = os.path.join(outdir, out_name)
        if spec.get("skip_existing") and os.path.exists(dest) and os.path.getsize(dest) > 0:
            entries.append({"id": sid, "status": "skipped-existing", "out": out_name})
            continue
        search = template.format(year=year, start=f"{year}0101", end=f"{year}1231")
        collected, page, requests = [], 0, []
        while page < max_pages:
            skip = page * limit
            qsearch = urllib.parse.quote(search, safe=':+[]"')
            url = f"{endpoint}?search={qsearch}&limit={limit}&skip={skip}"
            try:
                status, body = http_get(url, timeout=spec.get("timeout", 180),
                                        retries=spec.get("retries", 4))
            except RuntimeError as exc:
                entries.append({"id": sid, "url": url, "status": "FAILED", "error": str(exc),
                                "at_utc": _now()})
                print(f"FAIL {sid} page {page}: {exc}", flush=True)
                break
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                entries.append({"id": sid, "url": url, "status": "BAD_JSON", "error": str(exc)})
                break
            results = payload.get("results", [])
            requests.append({"url": url, "status": status, "n_raw_records": len(results),
                             "raw_sha256": hashlib.sha256(body).hexdigest(), "at_utc": _now()})
            collected.extend(extract_suppl_year(payload, year, url))
            if len(results) < limit:
                break
            page += 1
            time.sleep(spec.get("sleep", 0.3))
        seen, uniq = set(), []
        for s in collected:
            key = (s["application_number"], s["submission_number"], s["decision_date"])
            if key not in seen:
                seen.add(key)
                uniq.append(s)
        uniq.sort(key=lambda s: (s["decision_date"], s["application_number"], s["submission_number"]))
        body = json.dumps({"year": year, "source_endpoint": endpoint, "search": search,
                           "count": len(uniq), "extracted_utc": _now(), "supplements": uniq},
                          separators=(",", ":")).encode("utf-8")
        meta = {"id": sid, "endpoint": endpoint, "search": search, "pages": requests,
                "supplements": len(uniq), "status": 200}
        write_payload(dest, body, meta)
        entries.append(meta)
        print(f"ok {sid}: {len(uniq)} efficacy supplements -> {dest}", flush=True)


def job_stooq(spec: dict, outdir: str, entries: list) -> None:
    """Daily OHLC history per symbol from Stooq (verbatim CSV per symbol).

    One request per symbol returns the full daily series; only the rows inside
    the requested window are kept, verbatim, to keep the repository small. The
    manifest stores the request URL plus the SHA-256 of the *complete* payload
    so the slice can always be re-derived and checked.
    """
    base = spec.get("base", "https://stooq.com/q/d/l/")
    d1 = spec.get("d1", "19900101")
    d2 = spec.get("d2", _dt.date.today().isoformat().replace("-", ""))
    kept_rows = int(spec.get("kept_rows", 0))
    for sym in spec["symbols"]:
        sid = f"{spec['id']}_{sym}"
        out_name = spec.get("out_template", "{sym}.csv").format(sym=sym)
        dest = os.path.join(outdir, out_name)
        if spec.get("skip_existing") and os.path.exists(dest) and os.path.getsize(dest) > 0:
            entries.append({"id": sid, "status": "skipped-existing", "out": out_name})
            continue
        url = f"{base}?s={urllib.parse.quote(sym)}&d1={d1}&d2={d2}&i=d"
        try:
            status, body = http_get(url, timeout=spec.get("timeout", 120), retries=spec.get("retries", 3))
        except RuntimeError as exc:
            entries.append({"id": sid, "url": url, "status": "FAILED", "error": str(exc), "at_utc": _now()})
            print(f"FAIL {sid}: {exc}", flush=True)
            continue
        text = body.decode("utf-8", errors="replace")
        meta = {"id": sid, "url": url, "status": status, "symbol": sym,
                "raw_sha256": hashlib.sha256(body).hexdigest(), "raw_bytes": len(body)}
        if text.lstrip().startswith("<") or "Date,Open,High,Low,Close,Volume" not in text:
            entries.append({**meta, "status": "NO_DATA", "note": text[:120].replace("\n", " ")})
            print(f"empty {sid}: {text[:80]!r}", flush=True)
            continue
        lines = [ln for ln in text.strip().splitlines() if ln.strip()]
        header, rows = lines[0], lines[1:]
        if kept_rows:
            rows = rows[-kept_rows:] if spec.get("keep_last") else rows
        body = ("\n".join([header] + rows) + "\n").encode("utf-8")
        write_payload(dest, body, meta)
        meta["rows_kept"] = len(rows)
        meta["first_date"] = rows[0].split(",")[0] if rows else ""
        meta["last_date"] = rows[-1].split(",")[0] if rows else ""
        entries.append(meta)
        print(f"ok {sid}: {len(rows)} rows {meta.get('first_date')}..{meta.get('last_date')}", flush=True)
        time.sleep(spec.get("sleep", 0.25))


def job_generic_csv(spec: dict, outdir: str, entries: list) -> None:
    """Fetch a list of URLs as-is (used for per-event Yahoo chart payloads)."""
    for item in spec["items"]:
        sid = item["id"]
        dest = os.path.join(outdir, item.get("out", f"{sid}.json"))
        if spec.get("skip_existing") and os.path.exists(dest) and os.path.getsize(dest) > 0:
            entries.append({"id": sid, "status": "skipped-existing"})
            continue
        try:
            status, body = http_get(item["url"], timeout=spec.get("timeout", 60), retries=spec.get("retries", 3))
        except RuntimeError as exc:
            entries.append({"id": sid, "url": item["url"], "status": "FAILED", "error": str(exc), "at_utc": _now()})
            print(f"FAIL {sid}: {exc}", flush=True)
            continue
        meta = {"id": sid, "url": item["url"], "status": status, "ticker": item.get("ticker", ""),
                "decision_date": item.get("decision_date", ""), "source": item.get("source", "")}
        write_payload(dest, body, meta)
        entries.append(meta)
        print(f"ok {sid} {status} {meta.get('bytes')} bytes", flush=True)
        time.sleep(spec.get("sleep", 0.2))


def job_ctgov(spec: dict, outdir: str, entries: list) -> None:
    """Page ClinicalTrials.gov API v2. Studies are written verbatim (or
    projected through a whitelist). Nothing is rewritten or inferred.

    Next-session universe: Phase 3 trials with a primary-completion date in
    2026–2027. The sandbox cannot reach clinicaltrials.gov; this job runs on
    GitHub Actions and commits the payload + per-request SHA-256.
    """
    endpoint = spec["endpoint"]
    params = dict(spec.get("params") or {})
    page_size = int(params.get("pageSize", 100))
    max_pages = int(spec.get("max_pages", 10))
    sid = spec["id"]
    dest = os.path.join(outdir, spec.get("out", f"{sid}.json"))
    if spec.get("skip_existing") and os.path.exists(dest) and os.path.getsize(dest) > 0:
        entries.append({"id": sid, "status": "skipped-existing", "out": spec.get("out")})
        return
    collected, requests, token, page = [], [], None, 0
    while page < max_pages:
        q = dict(params)
        q["pageSize"] = str(page_size)
        if token:
            q["pageToken"] = token
        url = endpoint + "?" + urllib.parse.urlencode(q, safe="[]:,")
        try:
            status, body = http_get(url, timeout=spec.get("timeout", 180),
                                    retries=spec.get("retries", 4),
                                    headers=spec.get("headers"))
        except RuntimeError as exc:
            entries.append({"id": f"{sid}_p{page}", "url": url, "status": "FAILED",
                            "error": str(exc), "at_utc": _now()})
            print(f"FAIL {sid} page {page}: {exc}", flush=True)
            break
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            entries.append({"id": f"{sid}_p{page}", "url": url, "status": "BAD_JSON",
                            "error": str(exc)})
            break
        studies = payload.get("studies") or []
        requests.append({"url": url, "status": status, "n": len(studies),
                         "sha256": hashlib.sha256(body).hexdigest(), "at_utc": _now()})
        if spec.get("project"):
            studies = [project(s, spec["project"]) for s in studies]
        collected.extend(studies)
        token = payload.get("nextPageToken")
        page += 1
        print(f"ok {sid} page {page}: {len(studies)} studies (running {len(collected)})", flush=True)
        if not token or len(studies) < page_size:
            break
        time.sleep(spec.get("sleep", 0.4))
    out = {
        "source_endpoint": endpoint,
        "params": params,
        "count": len(collected),
        "pages": len(requests),
        "fetched_utc": _now(),
        "studies": collected,
    }
    body = json.dumps(out, separators=(",", ":")).encode("utf-8")
    meta = {"id": sid, "endpoint": endpoint, "pages": requests,
            "studies": len(collected), "status": 200}
    write_payload(dest, body, meta)
    entries.append(meta)
    print(f"ok {sid}: {len(collected)} studies -> {dest}", flush=True)


KINDS = {
    "url": job_url,
    "openfda_years": job_openfda_years,
    "openfda_decisions": job_openfda_decisions,
    "openfda_supplements": job_openfda_supplements,
    "stooq": job_stooq,
    "generic": job_generic_csv,
    "ctgov": job_ctgov,
}


def run_job(job_path: str) -> None:
    specs = json.load(open(job_path))
    if isinstance(specs, dict):
        specs = [specs]
    outdir = os.path.dirname(job_path).replace("fetch_jobs", "data/raw") or "data/raw"
    job_id = os.path.basename(job_path).rsplit(".", 1)[0]
    outdir = os.path.join("data/raw", job_id)
    os.makedirs(outdir, exist_ok=True)
    manifest = load_manifest(outdir)
    entries = manifest.setdefault("requests", [])
    done = {e.get("id") for e in entries if e.get("status") not in (None, "FAILED", "BAD_JSON", "NO_DATA")}
    print(f"== job {job_id} ({len(specs)} spec(s)) ==", flush=True)
    for spec in specs:
        kind = spec.get("type", "url")
        fn = KINDS.get(kind)
        if fn is None:
            print(f"unknown job type {kind!r} in {job_path}", flush=True)
            continue
        fn(spec, outdir, entries)
    manifest["generated_utc"] = _now()
    manifest["job_file"] = job_path
    with open(os.path.join(outdir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        run_job(path)
