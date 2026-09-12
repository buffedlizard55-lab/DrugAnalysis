#!/usr/bin/env python3
"""Append verified 2000-2010 backfill + 2011-2025 gap rows to the master list.

Every appended row must survive a line-by-line verification pass against the
raw official payloads already committed under data/raw:

  * openFDA Drugs@FDA year payloads (data/raw/openfda_approvals_2000_2010) --
    when present, the application number, approval date, brand and sponsor are
    re-read from the verbatim JSON rather than trusted from staging.
  * FDA CDER NME compilation XLSX (data/raw/probe) -- brand/date cross-check.

Tickers are never guessed. They come only from data/sponsor_registry.csv, a
hand-audited table where each entry records the SEC company_tickers.json title
it matched or the reason the company has no US-listed equity.
"""
import csv, json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
STAGING = DATA / "staging"

DAF = "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo={}"
NME_XLSX = "https://www.fda.gov/media/177921/download?attachment"
NME_PAGE = ("https://www.fda.gov/drugs/drug-approvals-and-databases/"
            "compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals")


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def load_registry():
    reg = {}
    with (DATA / "sponsor_registry.csv").open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            reg[norm(r["sponsor_key"])] = r
    return reg


def load_openfda_truth():
    """Rebuild (appl_no -> record) straight from the verbatim openFDA payloads."""
    truth = {}
    d = RAW / "openfda_approvals_2000_2010"
    if not d.is_dir():
        return truth
    for path in sorted(d.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        for res in payload.get("results", []):
            appl_raw = (res.get("application_number") or "").strip()
            appl = re.sub(r"\D", "", appl_raw).zfill(6)
            if not appl_raw:
                continue
            dates = set()
            for sub in res.get("submissions", []) or []:
                if (sub.get("submission_type") == "ORIG"
                        and sub.get("submission_status") == "AP"
                        and sub.get("submission_status_date")):
                    raw = sub["submission_status_date"]
                    dates.add(f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}")
            brands, generics = set(), set()
            for p in res.get("products", []) or []:
                if p.get("brand_name"):
                    brands.add(norm(p["brand_name"]))
                if p.get("active_ingredients"):
                    for ai in p["active_ingredients"]:
                        if ai.get("name"):
                            generics.add(norm(ai["name"]))
            truth[appl] = {
                "dates": dates,
                "brands": brands,
                "generics": generics,
                "sponsor": norm(res.get("sponsor_name", "")),
            }
    return truth


def load_nme_truth():
    """(brand_norm, date) and (generic_norm, year) sets from the FDA XLSX."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        return None
    path = RAW / "probe" / "fda_nme_compilation_1985_2025.xlsx"
    if not path.exists():
        return None
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows)]
    idx = {h: i for i, h in enumerate(header)}

    def cell(r, name):
        i = idx.get(name)
        return r[i] if i is not None and i < len(r) else None

    def as_date(v):
        if v is None:
            return ""
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
        s = str(v).strip()
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2}).*", s)
        return m.group(0)[:10] if m else ""

    truth = {"appl": {}, "brand_date": set(), "brand_year": set()}
    for r in rows:
        if r is None:
            continue
        date = as_date(cell(r, "FDA Approval Date"))
        brand = norm(cell(r, "Proprietary  Name") or cell(r, "Proprietary Name"))
        if date and brand:
            truth["brand_date"].add((brand, date))
            truth["brand_year"].add((brand, date[:4]))
        for key in ("Application Number(1)", "Application Number(2)", "Application Number(3)"):
            v = cell(r, key)
            if v:
                digits = re.sub(r"\D", "", str(v))
                if digits:
                    truth["appl"].setdefault(digits.zfill(6), set()).add(date)
    return truth


def main():
    reg = load_registry()
    openfda = load_openfda_truth()
    nme = load_nme_truth()

    rows = []
    for name in ("candidates_2000_2010.json", "candidate_gaps_2011_2025.json"):
        p = STAGING / name
        if p.exists():
            rows += json.load(p.open())["rows"]

    with (DATA / "fda_decisions_master.csv").open(newline="", encoding="utf-8-sig") as f:
        master = list(csv.DictReader(f))
        fields = list(master[0].keys())

    existing_appl, existing_bd, existing_by = set(), set(), set()
    for r in master:
        for u in (r.get("source_url_1", ""), r.get("source_url_2", "")):
            m = re.search(r"varApplNo=(\d+)", u or "")
            if m:
                existing_appl.add(m.group(1).zfill(6))
        b, d = norm(r.get("drug_brand")), r.get("decision_date", "")
        if b and d:
            existing_bd.add((b, d))
            existing_by.add((b, d[:4]))

    max_id = max((int(r["decision_id"][1:]) for r in master
                  if re.fullmatch(r"D\d+", r.get("decision_id", ""))), default=0)

    appended, rejected, flags = [], [], []
    seen = set()
    for c in rows:
        appl_raw = c.get("application_number", "")
        appl = re.sub(r"\D", "", appl_raw).zfill(6) if appl_raw else ""
        brand = norm(c.get("drug_brand"))
        date = c.get("decision_date", "")
        gen = norm(c.get("drug_generic"))

        if not (brand and date and appl):
            rejected.append({"appl": appl_raw, "brand": c.get("drug_brand"),
                             "reason": "missing application number, brand or decision date"})
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            rejected.append({"appl": appl_raw, "reason": f"non-ISO date {date!r}"})
            continue
        if appl in existing_appl or (brand, date) in existing_bd or (brand, date[:4]) in existing_by:
            rejected.append({"appl": appl_raw, "brand": c.get("drug_brand"),
                             "reason": "already present in fda_decisions_master.csv"})
            continue
        if (appl, date) in seen:
            rejected.append({"appl": appl_raw, "reason": "duplicate within candidate set"})
            continue

        # --- line-by-line verification against the verbatim official payloads ---
        verified_by, row_flags = [], []
        t = openfda.get(appl)
        if t:
            if date not in t["dates"]:
                rejected.append({"appl": appl_raw, "brand": c.get("drug_brand"),
                                 "reason": f"openFDA ORIG/AP dates {sorted(t['dates'])} do not "
                                           f"contain staged date {date}"})
                continue
            if t["brands"] and brand not in t["brands"]:
                if gen and gen in t["generics"]:
                    row_flags.append("brand name not in openFDA product list; matched on active ingredient")
                else:
                    rejected.append({"appl": appl_raw, "brand": c.get("drug_brand"),
                                     "reason": "brand and generic both absent from openFDA products"})
                    continue
            verified_by.append("openFDA Drugs@FDA verbatim payload")

        if nme is not None and c.get("nme_compilation_match"):
            ok = ((brand, date) in nme["brand_date"] or (brand, date[:4]) in nme["brand_year"]
                  or appl in nme["appl"])
            if ok:
                verified_by.append("FDA CDER NME compilation XLSX")
                dates = nme["appl"].get(appl) or set()
                if dates and date not in dates:
                    row_flags.append("IRREGULARITY: CDER NME compilation approval date "
                                     f"{sorted(d for d in dates if d)} differs from Drugs@FDA {date}")
            else:
                row_flags.append("staging marked an NME-compilation match that could not be "
                                 "re-confirmed in the XLSX")

        if not verified_by:
            rejected.append({"appl": appl_raw, "brand": c.get("drug_brand"),
                             "reason": "no official payload available to re-verify this row"})
            continue

        sponsor = (c.get("company_name_current") or c.get("applicant_at_approval") or "").strip()
        e = reg.get(norm(sponsor))
        if e:
            company = e["resolved_company"] or sponsor
            ticker, exch = e["ticker"], e["exchange"]
            klass, basis = e["us_investable_class"], e["basis"]
        else:
            company = sponsor or (c.get("applicant_at_approval") or "").strip()
            ticker, exch = "", ""
            klass = "NOT US-INVESTABLE (UNVERIFIED)"
            basis = ("no audited entry in data/sponsor_registry.csv; ticker deliberately left "
                     "blank rather than guessed")
            row_flags.append("sponsor not yet resolved to a verified issuer")
        if not company:
            rejected.append({"appl": appl_raw, "reason": "no sponsor name in either source"})
            continue

        max_id += 1
        note = (f"{c.get('submission_class','')}; scope: {c.get('decision_scope','')}; "
                f"applicant of record at fetch: {c.get('sponsor_name_raw') or 'n/a'}; "
                f"verified against {' + '.join(verified_by)}.")
        if c.get("applicant_at_approval"):
            note += f" Applicant named in CDER NME compilation: {c['applicant_at_approval']}."
        if row_flags:
            note += " FLAG: " + "; ".join(row_flags)
            flags.append({"decision_id": f"D{max_id:03d}", "appl": appl,
                          "brand": c.get("drug_brand"), "flags": row_flags})

        appended.append({
            "company_name": company,
            "ticker": ticker,
            "drug_brand": c.get("drug_brand", ""),
            "drug_generic": c.get("drug_generic", ""),
            "decision_type": c.get("decision_type", "Approval"),
            "decision_date": date,
            "indication": (c.get("indication") or "").replace("\n", " ").strip(),
            "review_pathway": c.get("review_pathway", ""),
            "source_url_1": c.get("source_url_drugsatfda") or DAF.format(appl),
            "source_url_2": c.get("source_url_nme_compilation") or NME_XLSX,
            "verification_status": "Verified" if not row_flags else "Verified - flagged for review",
            "notes": note,
            "us_investable_class": klass,
            "classification_basis": basis,
            "exchange": exch,
            "decision_id": f"D{max_id:03d}",
        })
        seen.add((appl, date))
        existing_appl.add(appl)
        existing_bd.add((brand, date))

    out = DATA / "fda_decisions_master.csv"
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
        for r in appended:
            w.writerow({k: r.get(k, "") for k in fields})

    report = {
        "appended": len(appended),
        "rejected": len(rejected),
        "flagged_for_review": len(flags),
        "sources": {"drugs_at_fda": DAF, "nme_compilation_xlsx": NME_XLSX,
                    "nme_compilation_page": NME_PAGE},
        "rejections": rejected,
        "flags": flags,
    }
    (STAGING / "append_report.json").write_text(json.dumps(report, indent=2))
    print(f"appended={len(appended)} rejected={len(rejected)} flagged={len(flags)}")
    counts = {}
    for r in appended:
        counts[r["decision_date"][:4]] = counts.get(r["decision_date"][:4], 0) + 1
    print("by year:", dict(sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
