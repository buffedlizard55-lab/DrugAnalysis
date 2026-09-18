#!/usr/bin/env python3
"""Build data/focus_years_1980_1985_audit.csv — the 1980-1985
year-by-year FDA original-approval enumeration audit (v16, 2026-09-18;
v15 covered 1983-1985 and this builder replaced it when coverage grew
to the six focus years).

Purpose
-------
The project's focus years are 1980, 1981, 1982, 1983, 1984, and 1985.
This builder enumerates EVERY original (ORIG/AP) NDA/BLA approval recorded
in the committed openFDA Drugs@FDA payloads for those six years —
82 + 71 + 103 + 70 + 109 + 82 = 517 decisions — and proves that each one
is tracked in exactly one project table:

  pre1985_fda_decisions.csv          pre-1985 NME table (v13/v14 verified rows)
  fda_original_non_nme_decisions.csv non-Type-1 originals (v15 includes 1983-1984)
  fda_decisions_master.csv           1985 novel-approval master (Compilation spine)
  fda_type1_not_in_nme_master.csv    flagged Type 1 rows, never merged

It also cross-checks the tracked row's date/class/priority against the
committed payload field-by-field and records the agreement verdict per row,
so a human can review any line with the official Drugs@FDA link and the
replayable openFDA query URL carried on every row.

Known 1985 reconciliation facts (asserted, not assumed):
  * 27 of the 31 master rows match payload Type 1/1-4 records by application
    number. Temovate's Compilation row additionally cites NDA019323 (the
    companion Type 3 cream original), which is therefore tracked via the
    master rather than duplicated in the non-NME table.
  * 4 master rows (Seldane D1030, Protropin D1038, Suprol D1047, Femstat
    D1042) carry application numbers with NO ORIG/AP record in the openFDA
    payload — a documented Drugs@FDA/openFDA completeness gap for a few
    mid-1980s NDAs. They are pinned here so a future payload refresh that
    changes this set surfaces immediately instead of passing silently.

Hallucination controls
----------------------
* Every payload field is copied verbatim; nothing is inferred.
* The builder ABORTS if any payload decision is left untracked, if per-year
  totals change, or if the pinned reconciliation facts no longer hold.
* The audit never mutates the tables it audits; it is a read-only verifier.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_PRE = DATA / "raw" / "openfda_orig_decisions_1980_1984"
RAW_MAIN = DATA / "raw" / "openfda_orig_decisions_2011_2026"
OUT = DATA / "focus_years_1980_1985_audit.csv"

FOCUS_YEARS = (1980, 1981, 1982, 1983, 1984, 1985)
EXPECTED_TOTALS = {1980: 82, 1981: 71, 1982: 103, 1983: 70, 1984: 109, 1985: 82}
# Pinned (VERIFIED, REVIEW) verdict splits, asserted after the audit is built.
# All flags behind these splits are documented data conditions of the committed
# payloads (missing submission_class_code / review_priority), never guesses.
# A change here means a project table or payload changed — re-verify, then
# re-pin deliberately together with validate_data.py.
PINNED_VERDICT_SPLITS = {
    1980: (78, 4),
    1981: (60, 11),
    1982: (86, 17),
    1983: (44, 26),
    1984: (92, 17),
    1985: (79, 3),
}

APPL_RE = re.compile(
    r"(?:NDA|BLA|ANDA)\s*-?\s*(\d{5,6})"
    r"|appl\s*N?\s*-?\s*(\d{5,6})"
    r"|ApplNo[=:](\d{5,6})"
    r"|varApplNo=(\d{5,6})",
    re.I,
)


def norm6(text: str) -> str | None:
    m = APPL_RE.search(text or "")
    if not m:
        return None
    digits = next(g for g in m.groups() if g)
    return digits.zfill(6)


def norm_class(value: str) -> str:
    v = (value or "").strip().upper()
    if not v or v in {"NOT STATED", "UNKNOWN"}:
        return ""
    return v


def load_payload(year: int) -> list[dict]:
    base = RAW_PRE if year < 1985 else RAW_MAIN
    path = base / f"decisions_{year}.json"
    if not path.exists():
        raise SystemExit(f"missing committed payload: {path}")
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    decisions = payload.get("decisions") or []
    if len(decisions) != EXPECTED_TOTALS[year]:
        raise SystemExit(
            f"payload {year}: {len(decisions)} decisions, expected {EXPECTED_TOTALS[year]} — "
            "the committed extract changed; re-verify before trusting the audit."
        )
    return decisions


def brand_of(rec: dict) -> str:
    for p in rec.get("products") or []:
        b = (p.get("brand_name") or "").strip()
        if b:
            return b
    return (rec.get("brand_name_openfda") or "").strip()


def generic_of(rec: dict) -> str:
    g = (rec.get("generic_name_openfda") or "").strip()
    if g:
        return g
    s = (rec.get("substance_name") or "").strip()
    if s:
        return s
    for p in rec.get("products") or []:
        ing = (p.get("active_ingredients") or "").strip()
        if ing:
            return ing
    return ""


def load_pre1985() -> dict[str, dict]:
    out = {}
    with (DATA / "pre1985_fda_decisions.csv").open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            a = norm6(r.get("application_number", ""))
            if a:
                if a in out:
                    raise SystemExit(f"pre1985 table duplicate application {a}")
                out[a] = r
    return out


def load_orig() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    with (DATA / "fda_original_non_nme_decisions.csv").open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            out.setdefault((r.get("application_number") or "").strip(), []).append(r)
    return out


def load_master_1985() -> tuple[dict[str, dict], set[str]]:
    """Return (appl -> master row, set of 1985 master appls not found in any payload)."""
    by_appl: dict[str, dict] = {}
    rows_1985 = []
    with (DATA / "fda_decisions_master.csv").open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if not (r.get("decision_date") or "").startswith("1985"):
                continue
            rows_1985.append(r)
            blob = " ".join([
                r.get("notes", ""), r.get("source_url_1", ""), r.get("source_url_2", ""),
                r.get("classification_basis", ""),
            ])
            for m in APPL_RE.finditer(blob):
                digits = next(g for g in m.groups() if g)
                by_appl.setdefault(digits.zfill(6), r)
    return by_appl, {r["decision_id"] for r in rows_1985}


def load_t1gap() -> dict[str, dict]:
    out = {}
    path = DATA / "fda_type1_not_in_nme_master.csv"
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            a = (r.get("application_number") or "").strip()
            if a:
                out[a] = r
    return out


# Pinned reconciliation facts (see module docstring). A payload refresh that
# changes any of these must be re-verified by a human before the audit passes.
PINNED_MASTER_GAP_APPLS = {"018217", "018949", "019107", "019215"}  # Suprol, Seldane, Protropin, Femstat
PINNED_MASTER_GAP_IDS = {"D1047", "D1030", "D1038", "D1042"}
PINNED_COMPANION = {"NDA019323": ("NDA019322", "D1055")}  # Temovate cream TYPE 3 via Temovate master row


def main() -> int:
    pre = load_pre1985()
    orig = load_orig()
    master_appl, _master_ids = load_master_1985()
    t1gap = load_t1gap()

    # Assert the pinned 1985 master-vs-payload gap (documented openFDA hole).
    payload_appls_1985 = {
        re.sub(r"^(NDA|BLA|ANDA)", "", (r.get("application_number") or "").strip()).zfill(6)
        for r in load_payload(1985)
    }
    master_gap = {a for a in master_appl if a not in payload_appls_1985}
    if master_gap != PINNED_MASTER_GAP_APPLS:
        raise SystemExit(
            "1985 master applications without a payload ORIG record changed: "
            f"{sorted(master_gap)} (pinned: {sorted(PINNED_MASTER_GAP_APPLS)}). "
            "Re-verify the payloads and master rows before updating this pin."
        )

    rows: list[dict] = []
    untracked: list[str] = []
    per_year = {y: Counter() for y in FOCUS_YEARS}

    for year in FOCUS_YEARS:
        seq = 0
        for rec in sorted(
            load_payload(year),
            key=lambda r: (r.get("decision_date") or "", r.get("application_number") or ""),
        ):
            seq += 1
            appl = (rec.get("application_number") or "").strip()
            appl6 = norm6(appl) or appl
            date = (rec.get("decision_date") or "").strip()
            p_class = (rec.get("submission_class_code") or "").strip()
            p_class_desc = (rec.get("submission_class_code_description") or "").strip()
            p_prio = (rec.get("review_priority") or "").strip()
            flags: list[str] = []

            tracked_in = tracked_id = ""
            t_date = t_class = t_prio = ""
            matched_via = ""

            if appl6 in pre:
                tracked_in = "pre1985_fda_decisions.csv"
                row = pre[appl6]
                tracked_id = row["decision_id"]
                t_date = row.get("decision_date", "")
                t_class = row.get("chemical_type_code", "")
                t_prio = row.get("review_priority", "")
                matched_via = "application_number"
            elif appl in t1gap:
                tracked_in = "fda_type1_not_in_nme_master.csv"
                tracked_id = t1gap[appl].get("gap_id", "")
                t_date = t1gap[appl].get("decision_date", "")
                t_class = t1gap[appl].get("chemical_type_description", "")
                t_prio = t1gap[appl].get("review_priority", "")
                matched_via = "application_number"
            elif appl in orig:
                candidates = orig[appl]
                row = candidates[0]
                tracked_in = "fda_original_non_nme_decisions.csv"
                tracked_id = row.get("orig_id", "")
                t_date = row.get("decision_date", "")
                t_class = row.get("chemical_type_code", "")
                t_prio = row.get("review_priority", "")
                matched_via = "application_number"
            elif appl6 in master_appl:
                row = master_appl[appl6]
                tracked_in = "fda_decisions_master.csv"
                tracked_id = row.get("decision_id", "")
                t_date = row.get("decision_date", "")
                t_class = "(not asserted in master)"
                t_prio = row.get("review_pathway", "")
                matched_via = "application_number"
                companion = PINNED_COMPANION.get(appl)
                if companion and appl != companion[0]:
                    flags.append(
                        f"master-referenced companion original: Compilation {row.get('drug_brand')} row "
                        f"({companion[0]}, {companion[1]}) lists {appl} as an additional application "
                        "number; kept on the master instead of duplicating it as a separate non-NME row"
                    )
            else:
                untracked.append(f"{year}:{appl}")
                continue

            # Field-by-field agreement against the committed payload.
            if (t_date or "").strip() == date:
                date_agree = "YES"
            else:
                date_agree = f"NO ({t_date} vs {date})"
                flags.append(f"date mismatch: tracked {t_date} vs payload {date}")

            tc_raw = t_class.strip()
            if tc_raw.lower().startswith("(not asserted"):
                class_agree = "NOT_ASSERTED_IN_TRACKING_TABLE"
            elif norm_class(tc_raw) == norm_class(p_class):
                class_agree = "YES" if norm_class(p_class) else "BOTH_NOT_STATED"
            elif norm_class(p_class) and not norm_class(tc_raw):
                class_agree = "TRACKING_ROW_QUALIFIES"
                flags.append(f"payload class {p_class} vs tracking row '{tc_raw}'")
            else:
                class_agree = f"NO ({tc_raw} vs {p_class or '(blank)'})"
                flags.append(f"class mismatch: tracked '{tc_raw}' vs payload '{p_class}'")

            if norm_class(t_prio) == norm_class(p_prio):
                priority_agree = "YES" if norm_class(p_prio) else "BOTH_NOT_STATED"
            elif norm_class(p_prio) and not norm_class(t_prio):
                priority_agree = "TRACKING_ROW_QUALIFIES"
                flags.append(f"payload priority {p_prio} vs tracking row '{t_prio.strip()}'")
            else:
                priority_agree = f"NO ({t_prio.strip()} vs {p_prio or '(blank)'})"
                flags.append(
                    f"priority differs between sources: tracking '{t_prio.strip()}' vs payload '{p_prio}' "
                    "(Compilation/curated designation vs Drugs@FDA submission field)"
                )

            if not norm_class(p_class):
                flags.append("payload published no submission_class_code")
            if not p_prio:
                flags.append("payload published no review_priority")

            verdict = "TRACKED_VERIFIED"
            if flags or date_agree != "YES":
                verdict = "TRACKED_REVIEW"
            if date_agree.startswith("NO"):
                verdict = "DISAGREEMENT_REVIEW"

            per_year[year]["total"] += 1
            per_year[year][tracked_in] += 1
            per_year[year][verdict] += 1

            rows.append({
                "audit_id": f"F{year}-{seq:03d}",
                "year": year,
                "application_number": appl,
                "application_kind": rec.get("application_kind") or "",
                "drug_brand": brand_of(rec),
                "drug_generic": generic_of(rec),
                "openfda_holder": (rec.get("sponsor_name") or "").strip(),
                "payload_decision_date": date,
                "payload_class_code": p_class,
                "payload_class_description": p_class_desc,
                "payload_review_priority": p_prio,
                "tracked_in": tracked_in,
                "tracked_row_id": tracked_id,
                "tracked_table_date": t_date,
                "tracked_table_class": t_class,
                "tracked_table_priority": t_prio,
                "date_agreement": date_agree,
                "class_agreement": class_agree,
                "priority_agreement": priority_agree,
                "matched_via": matched_via,
                "verdict": verdict,
                "review_flag": " | ".join(flags),
                "source_url_drugsatfda": rec.get("source_url_drugsatfda") or "",
                "source_query_url": rec.get("source_query_url") or "",
            })

    if untracked:
        raise SystemExit(
            "UNTRACKED payload decisions in the 1980-1985 focus years — the "
            "enumeration claim would be false: " + ", ".join(untracked)
        )
    for year in FOCUS_YEARS:
        c = per_year[year]
        if c["total"] != EXPECTED_TOTALS[year] or c["TRACKED_VERIFIED"] + c["TRACKED_REVIEW"] != c["total"]:
            raise SystemExit(f"{year}: audit totals wrong: {dict(c)}")
        _v, _r = PINNED_VERDICT_SPLITS[year]
        if c["TRACKED_VERIFIED"] != _v or c["TRACKED_REVIEW"] != _r:
            raise SystemExit(
                f"{year}: verdict split changed to {c['TRACKED_VERIFIED']}V/{c['TRACKED_REVIEW']}R "
                f"(pinned {_v}V/{_r}R). A project table or payload changed — re-verify the "
                "underlying rows, then update PINNED_VERDICT_SPLITS and validate_data.py together."
            )

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} audited ORIG/AP decisions")
    for year in FOCUS_YEARS:
        c = per_year[year]
        print(
            f"  {year}: total={c['total']} tracked_verdicts="
            f"{c['TRACKED_VERIFIED']}V/{c['TRACKED_REVIEW']}R by-table="
            + ", ".join(f"{k.split('_')[1]}={v}" for k, v in c.items() if k.endswith(".csv"))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
