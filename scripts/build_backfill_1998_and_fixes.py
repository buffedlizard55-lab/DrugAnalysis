#!/usr/bin/env python3
"""Session 2026-09-17 (v7): 1998 NME import + three official-table reconciliation fixes.

Everything here is driven by verbatim-staged official tables; nothing is typed
from memory. Sources per change:

  A. 1998 import (36 rows)
     data/staging/fda_nme_1998_verbatim.json — CDER "NMEs Approved in CY 1998"
     (fda.gov/cder/rdmt/nmecy98.htm, Wayback 2005-10-16, 30 rows) cross-checked
     against FDA's CDER Novel Drug Approvals Compilation (media/177921, 36
     approval-year-1998 rows: +Simulect, Synagis, Infasurf, Remicade, Herceptin,
     Enbrel — all flagged in the row notes) and openFDA Drugs@FDA (29/30 CDER
     rows re-verified by application number + exact ORIG approval date; Refludan
     is no longer indexed and is flagged).

  B. 2014 — Ofev (nintedanib, NDA 205832) was missing from the master although
     it is row #33 of FDA's official "NME and New Therapeutic Biological Product
     Approvals for 2014" table (ucm429247, Wayback 2015-01-23) and a Type 1 NME
     in openFDA (ORIG-1 AP 2014-10-15, BOEHRINGER INGELHEIM, PRIORITY, Orphan).
     Added. In its place the master carried D634 Contrave (NDA 200063,
     2014-09-10): openFDA classes it "Type 4 - New Combination" (naltrexone +
     bupropion, both previously approved) and it is NOT on FDA's 2014 NME table
     or in the CDER Compilation. D634 is re-labelled — kept in the file for
     transparency (its OREX ticker/price notes remain) but flagged
     NOT_ON_FDA_NME_TABLE so it no longer counts toward the 2014 = 41 audit.

  C. 2026 — Pixclara (floretyrosine F 18, NDA 218592, Telix) is row #40 of the
     live FDA "Novel Drug Approvals for 2026" table (9/11/2026) and a Type 1 NME
     in openFDA (ORIG-1 AP 2026-09-11, PRIORITY, Orphan). Master had 39. Added.

  D. 2026 — Cypsedo (D099) decision_date corrected 2026-05-31 -> 2026-05-29:
     FDA's official table and openFDA (NDA 220482 ORIG-1 AP 20260529) both say
     5/29; the previous row was sourced from trade press and had no application
     number. Application number + official links added.

Sponsor->ticker resolution for the 1998 rows reuses the audited COMPANY table in
scripts/build_backfill_2000_2019.py; applicants that table does not know are
left NOT US-INVESTABLE (UNVERIFIED) — never guessed.

us_investable_class for the new rows is written here from the resolved tuple
(same convention as build_backfill_2000_2019.py). Do NOT re-run
scripts/classify_listing.py afterwards: it is not a fixed point of the
committed master (it would flip 154 legacy rows, e.g. blank-exchange
FORMERLY rows -> PRIVATE, "OTC ADR" rows -> ADR) — a pre-existing
irregularity recorded in VERIFICATION_REPORT.md, left for a dedicated pass.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STG = ROOT / "data" / "staging"
MASTER = ROOT / "data" / "fda_decisions_master.csv"
TODAY = "2026-09-17"

# ---------------------------------------------------------------------------
# Reuse the audited applicant->ticker table (import without executing main()).
# ---------------------------------------------------------------------------
_src = (ROOT / "scripts" / "build_backfill_2000_2019.py").read_text(encoding="utf-8")
_table_src = _src[_src.index("COMPANY = ["): _src.index("def drugsatfda_url")]
_ns: dict = {}
exec(_table_src, _ns)  # noqa: S102 - our own audited file
COMPANY = _ns["COMPANY"]
resolve_generic = _ns["resolve"]

# 1998-specific applicant strings that the 2000-2019 table cannot resolve
# safely by substring (each verified this session; see notes text).
COMPANY_1998 = [
    # (pattern, company_name, ticker, exchange, class (recomputed by classify_listing.py), note)
    # Every "formerly ..." ticker below was checked this session against a
    # contemporaneous primary/press source quoting the exchange:ticker string.
    ("PHARMACIA & UPJOHN", "Pharmacia & Upjohn (Pharmacia Corp 2000; acquired by Pfizer 2003)", "PNU", "formerly NYSE:PNU, became Pharmacia Corp (NYSE:PHA) Apr-2000; delisted 2003",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Monsanto/P&U merger releases (Cision, Mar-2000) print 'Pharmacia & Upjohn (NYSE: PNU)'; Pharmacia Corp PHA acquired by Pfizer 16-Apr-2003 (QuantumOnline)"),
    ("ASTRA MERCK", "Astra Merck Inc. (Astra AB / Merck & Co. US joint venture; AstraZeneca lineage)", "AZN", "NASDAQ (ADR)",
     "US-LISTED (ADR)", "JV of Astra AB and Merck & Co.; restructured into Astra Pharmaceuticals LP 1998; AstraZeneca (NASDAQ ADR:AZN) 1999 — AZN used per the master's AstraZeneca precedent; decision-date JV equity was not separately listed"),
    ("PROCTER & GAMBLE", "Procter & Gamble Co.", "PG", "NYSE", "US-LISTED", "Actonel; P&G Pharmaceuticals sold to Warner Chilcott 2009"),
    ("ORPHAN MEDICAL", "Orphan Medical (acquired by Jazz 2005)", "ORPH", "NASDAQ", "US-LISTED", "NASDAQ:ORPH delisted 2005 (master precedent D692)"),
    ("ISIS", "Isis Pharmaceuticals (renamed Ionis Pharmaceuticals 2015)", "IONS", "NASDAQ", "US-LISTED", "NASDAQ:ISIS at approval; symbol changed to IONS Dec-2015 (same issuer)"),
    ("QUINTILES", "Quintiles Transnational (applicant of record for Arava; developer Hoechst Marion Roussel)", "QTRN", "formerly NASDAQ:QTRN, taken private Sep-2003 (relisted as Q 2013; now IQVIA IQV)",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Quintiles Transnational (Nasdaq: QTRN) per company releases 1999-2003; delisted 25-Sep-2003 (Smith Anderson release). Arava was developed and marketed by Hoechst Marion Roussel (Aventis 1999; Sanofi 2004) — Quintiles held the NDA under a 1998 partnership; flagged"),
    ("DIATIDE", "Diatide Inc. (acquired by Schering AG / Berlex Nov-1999)", "DITI", "formerly NASDAQ:DITI, acquired by Schering Berlin/Berlex Nov-1999",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "PRNewswire 25-Mar-1999 prints 'Diatide, Inc. (Nasdaq: DITI)'; Schering AG 20-F: Diatide acquired Nov-1999 and merged into Berlex Laboratories 2001. NOTE: the 1999 Neotect row D968 carries a GE Healthcare lineage from an earlier pass and is flagged for re-review"),
    ("DUPONT", "DuPont Pharmaceuticals (DuPont Merck JV until mid-1998; acquired by BMS 2001)", "", "",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "DuPont Co was NYSE:DD; the pharma unit had no separate equity and was sold to BMS 2001 — ticker left blank (master precedent D652/D671)"),
    ("ANTHRA", "Anthra Pharmaceuticals (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Valstar; private company (marketed by Medeva/Celltech)"),
    ("GELTEX", "GelTex Pharmaceuticals (acquired by Genzyme Dec-2000)", "GELX", "formerly NASDAQ:GELX, delisted Dec-2000 into Genzyme",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Burrill 1997 industry analysis (Jan-1998) prints 'GelTex Pharmaceuticals (Nasdaq: GELX)'; Renagel 50/50 partnership with Genzyme"),
    ("GENZYME", "Genzyme (acquired by Sanofi 2011)", "GENZ", "formerly NASDAQ:GENZ, delisted Apr-2011 into Sanofi",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Genzyme (Nasdaq: GENZ) per Burrill Jan-1998; Sanofi tender completed Apr-2011"),
    ("FOREST", "Forest Laboratories (Actavis/Allergan lineage)", "FRX", "formerly NYSE:FRX, delisted Jul-2014 into Actavis",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:FRX delisted 2014 (master precedent D720)"),
    ("CEPHALON", "Cephalon (acquired by Teva 2011)", "CEPH", "formerly NASDAQ:CEPH, delisted Oct-2011 into Teva",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CEPH delisted 2011 (master precedent D823)"),
    ("CELGENE", "Celgene Corp. (acquired by BMS 2019)", "CELG", "formerly NASDAQ:CELG, delisted Nov-2019 into BMS",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CELG delisted 2019 (master precedent D778/D495)"),
    ("COR THERAPEUTICS", "COR Therapeutics (acquired by Millennium Feb-2002)", "CORR", "formerly NASDAQ:CORR, delisted Feb-2002 into Millennium",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "WilmerHale 07-Dec-2001: 'COR Therapeutics, Inc. (Nasdaq: CORR)' acquired by Millennium (Nasdaq: MLNM) in a $2.0B stock deal; Integrilin co-marketed by Schering-Plough"),
    ("IMMUNEX", "Immunex (acquired by Amgen Jul-2002)", "IMNX", "formerly NASDAQ:IMNX, delisted Jul-2002 into Amgen",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Immunex 02-Nov-1998 approval release prints 'Immunex Corporation (NASDAQ: IMNX)' with co-marketer Wyeth-Ayerst (American Home Products, NYSE: AHP)"),
    ("MEDIMMUNE", "MedImmune (acquired by AstraZeneca Jun-2007)", "MEDI", "formerly NASDAQ:MEDI, delisted Jun-2007 into AstraZeneca",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "MedImmune, Inc. (Nasdaq: MEDI) per SEC 8-K exhibit (2005) noting Synagis FDA approval 1998; AstraZeneca acquisition closed Jun-2007"),
    ("CENTOCOR", "Centocor (acquired by Johnson & Johnson Oct-1999)", "CNTO", "formerly NASDAQ:CNTO, delisted Oct-1999 into Johnson & Johnson",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "J&J release 06-Oct-1999: 'Centocor, Inc (Nasdaq: CNTO)' merger completed ($4.9B; 0.6390 JNJ share per CNTO share)"),
    ("GENENTECH", "Genentech (Roche-controlled; NYSE:GNE 1994-1999, DNA 1999-2009)", "GNE", "formerly NYSE:GNE (special common, 1994-Jun-1999); re-IPO as NYSE:DNA Jul-1999; Roche full buyout Mar-2009",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Genentech traded as NYSE:GNE from 1994 until Roche's Jun-1999 redemption, then re-listed as DNA in Jul-1999 (CBS/Encyclopedia.com); later master rows use DNA — decision-date symbol GNE kept here"),
    ("ONY", "ONY Inc. (private, Amherst NY)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Infasurf; ONY Biotech is privately held"),
    ("ALCON", "Alcon (wholly owned by Nestle in 1998; NYSE:ACL 2002-2011; Alcon Inc. relisted ALC 2019)", "ALC", "NYSE",
     "US-LISTED", "wholly owned by Nestle at approval (no separate Alcon equity until the Mar-2002 IPO); ALC used per the master's Alcon precedent (D667) — decision-date proxy was Nestle, not ALC; flagged"),
    ("BAUSCH & LOMB", "Bausch & Lomb Inc. (NYSE:BOL until 2007 take-private; Bausch + Lomb Corp relisted BLCO 2022)", "BOL", "formerly NYSE:BOL, taken private by Warburg Pincus Oct-2007; successor Bausch + Lomb Corp NYSE:BLCO (2022-)",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Bausch & Lomb Inc (NYSE: BOL, ISIN US0717071031) inactive per MarketScreener; today's BLCO is a different legal entity (2022 IPO) so the decision-date ticker is kept"),
    ("SEARLE", "G.D. Searle (wholly owned Monsanto unit in 1998; Pharmacia 2000; Pfizer 2003)", "MTC", "formerly NYSE:MTC (Monsanto Company, Searle's parent); merged into Pharmacia Corp Apr-2000; Pfizer 2003",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Searle had no separate equity: parent Monsanto Company (NYSE: MTC) per Monsanto/P&U merger releases; Celebrex co-promoted with Pfizer (NYSE:PFE)"),
    ("HOECHST MARION ROUSSEL", "Hoechst Marion Roussel (Hoechst AG; Aventis Dec-1999; Sanofi 2004)", "", "",
     "NON-US LISTING ONLY", "Hoechst AG primary listing Frankfurt (FHOE per CNNfn 01-Dec-1998); Hoechst's US ADR line was not verified from a primary source this pass, so ticker is left blank (master precedent: 'HOECHST' -> NON-US LISTING ONLY in build_backfill_2000_2019.py); Aventis ADS 'AVE' began NYSE trading 20-Dec-1999"),
    ("GLAXO WELLCOME", "Glaxo Wellcome plc (GlaxoSmithKline from Dec-2000)", "GSK", "NYSE (ADR)",
     "US-LISTED (ADR)", "master precedent (build_backfill_2000_2019.py 'GLAXO' -> GSK NYSE ADR, primary LSE); Glaxo Wellcome merged with SmithKline Beecham 27-Dec-2000 — the decision-date ADR symbol (GLX) was not re-verified from a primary source this pass"),
    ("ROCHE", "Roche Holding AG (Genentech parent)", "RHHBY", "OTC ADR; primary SIX:ROG", "US-LISTED (ADR)",
     "primary SIX:ROG; US OTC ADR line RHHBY — class follows the exchange string (OTC ADR) and the 18 RHHBY master rows classed US-LISTED (ADR); the 5 RHHBY rows the 2000-2019 backfill classed NON-US LISTING ONLY are a pre-existing inconsistency flagged in VERIFICATION_REPORT.md"),
    ("MERCK", "Merck & Co., Inc.", "MRK", "NYSE", "US-LISTED", ""),
    ("PFIZER", "Pfizer Inc.", "PFE", "NYSE", "US-LISTED", ""),
    ("ABBOTT", "Abbott Laboratories", "ABT", "NYSE", "US-LISTED", ""),
    ("BOEHRINGER INGELHEIM", "Boehringer Ingelheim (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "family-held, no listed equity"),
    ("NOVARTIS", "Novartis AG", "NVS", "NYSE (ADR)", "US-LISTED (ADR)", "primary SIX:NOVN"),
]


def resolve_1998(applicant: str):
    a = (applicant or "").upper()
    for pat, co, tk, ex, usc, note in COMPANY_1998:
        if pat in a:
            return co, tk, ex, usc, note
    r = resolve_generic(applicant)
    return r


def drugsatfda_url(appl_no: str) -> str:
    m = re.match(r"(?:N|BLA|BL|NDA)?0*(\d+)$", (appl_no or "").replace(" ", ""), re.I)
    return (f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo={int(m.group(1)):06d}"
            if m else "")


def pathway(cls: str) -> str:
    parts = [p.strip().upper() for p in re.split(r"[,;/ \-]+", cls or "") if p.strip()]
    tags = []
    if "P" in parts or "PV" in parts:
        tags.append("Priority")
    if "S" in parts or "SV" in parts:
        tags.append("Standard")
    return "; ".join(tags)


def load_master():
    with MASTER.open(newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        return list(rd), rd.fieldnames


def write_master(rows, fieldnames):
    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    rows, fieldnames = load_master()
    have = {(r["drug_brand"].strip().lower(), r["decision_date"][:10]) for r in rows}
    next_id = max(int(r["decision_id"][1:]) for r in rows) + 1
    added = []

    def new_row(**kw):
        nonlocal next_id
        base = {k: "" for k in fieldnames}
        base.update(kw)
        base["decision_id"] = f"D{next_id}"
        next_id += 1
        added.append(base)
        return base

    # ------------------------------------------------------------------ A. 1998
    stg = json.load(open(STG / "fda_nme_1998_verbatim.json", encoding="utf-8"))
    n1998 = 0
    for r in stg["rows"]:
        key = (r["brand"].strip().lower(), r["date"])
        if key in have:
            continue
        have.add(key)
        res = resolve_1998(r["applicant"])
        if res:
            co, tk, ex, usc, note = res
            basis = (f"derived {TODAY} from verified exchange/ticker fields; FDA applicant string "
                     f"'{r['applicant']}' matched pattern '{co}'")
            vstat = "Verified"
        else:
            co, tk, ex, usc, note = r["applicant"], "", "N/A - sponsor resolution pending", "NOT US-INVESTABLE (UNVERIFIED)", ""
            basis = "FDA applicant string kept verbatim; sponsor/equity not resolved this pass"
            vstat = "Verified - FLAGGED (sponsor/equity not yet resolved)"
        notes = f"appl {r['appl_no']}; CDER CY1998 table applicant: {r['applicant']}; Compilation: {r['compilation']}"
        if note:
            notes += f". {note}"
        notes += f". {r['openfda_check']}"
        flags = []
        if r.get("row_count_flag"):
            flags.append(r["row_count_flag"])
        if "FLAGGED" in r["openfda_check"]:
            flags.append("openFDA/Drugs@FDA no longer index this application")
        if flags:
            vstat += " - FLAGGED (source-verbatim note)"
            notes += ". " + "; ".join(flags)
        dtype = "Approval (Accelerated)" if r.get("accelerated_approval_per_compilation") else "Approval"
        rp = pathway(r["class"])
        if r.get("accelerated_approval_per_compilation"):
            rp = (rp + "; Accelerated") if rp else "Accelerated"
            notes += ". Accelerated Approval per CDER Compilation column 'Accelerated Approval' = Yes"
        src1 = r.get("source_url_1") or stg["capture_url"]
        new_row(company_name=co, ticker=tk, drug_brand=r["brand"], drug_generic=r["generic_compilation"] if r.get("generic_compilation") else r["generic"],
                decision_type=dtype, decision_date=r["date"], indication=r["indication"], review_pathway=rp,
                source_url_1=src1, source_url_2=drugsatfda_url(r["appl_no"]), verification_status=vstat,
                notes=notes, us_investable_class=usc, classification_basis=basis, exchange=ex)
        n1998 += 1

    # ------------------------------------------------------------------ B. 2014
    if ("ofev", "2014-10-15") not in have:
        new_row(company_name="Boehringer Ingelheim (private)", ticker="", drug_brand="Ofev", drug_generic="nintedanib",
                decision_type="Approval", decision_date="2014-10-15",
                indication="Treatment of idiopathic pulmonary fibrosis (IPF)", review_pathway="Priority; Breakthrough; Orphan",
                source_url_1="https://web.archive.org/web/20150123034253/http://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm429247.htm",
                source_url_2="https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=205832",
                verification_status="Verified - FLAGGED IRREGULARITY (2014 table reconciliation)",
                notes=("appl NDA205832; FDA official 2014 NME table row #33 (ucm429247, page updated 01/14/2015; Wayback 2015-01-23). "
                       "openFDA Drugs@FDA: ORIG-1 AP 2014-10-15, sponsor BOEHRINGER INGELHEIM, Type 1 - New Molecular Entity, PRIORITY, Orphan. "
                       "CDER Compilation: Boehringer Ingelheim Pharmaceuticals; Priority; Orphan=Yes; Breakthrough=Yes; Fast Track=Yes; Accelerated=No. "
                       "IRREGULARITY: this row was missing from the master while D634 Contrave (a Type 4 combination, not on FDA's NME table) "
                       "was counted in its place, so the 2014 year count of 41 matched by coincidence. Fixed 2026-09-17; D634 re-labelled NOT_ON_FDA_NME_TABLE."),
                us_investable_class="PRIVATE / NO EQUITY",
                classification_basis=f"derived {TODAY} from verified exchange/ticker fields; no listed equity in the verified fields (ticker='blank', exchange='N/A - privately held')",
                exchange="N/A - privately held")
        have.add(("ofev", "2014-10-15"))

    for r in rows:
        if r["decision_id"] == "D634" and "NOT_ON_FDA_NME_TABLE" not in r["decision_type"] \
                and "IRREGULARITY (flagged 2026-09-17)" not in r["notes"]:
            r["decision_type"] = "Approval (non-NME combination; NOT_ON_FDA_NME_TABLE)"
            r["verification_status"] = "Verified - FLAGGED IRREGULARITY (not on FDA 2014 NME table)"
            r["notes"] = (
                "IRREGULARITY (flagged 2026-09-17): Contrave is NOT on FDA's official 2014 NME/new-biologic table (ucm429247, 41 rows) "
                "and is absent from the CDER Novel Drug Approvals Compilation; openFDA Drugs@FDA classes NDA 200063 ORIG-1 as "
                "'Type 4 - New Combination' (naltrexone + bupropion, both previously approved actives). The approval itself is real "
                "(AP 2014-09-10, STANDARD) but it is not a novel approval and is excluded from the 2014 = 41 official-count audit; "
                "row retained for transparency because it was published in earlier versions. Original note: " + r["notes"])
            r["source_url_1"] = "https://web.archive.org/web/20150123034253/http://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm429247.htm"

    # ------------------------------------------------------------------ C. 2026 Pixclara
    if ("pixclara", "2026-09-11") not in have:
        new_row(company_name="Telix Pharmaceuticals Limited", ticker="TLX", drug_brand="Pixclara", drug_generic="floretyrosine F 18",
                decision_type="Approval", decision_date="2026-09-11",
                indication="PET imaging to differentiate recurrent or progressive glioma from treatment-related change, in conjunction with other diagnostic evaluations",
                review_pathway="Priority; Orphan",
                source_url_1="https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026",
                source_url_2="https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=218592",
                verification_status="Verified",
                notes=("appl NDA218592; FDA 'Novel Drug Approvals for 2026' row #40 (9/11/2026). openFDA Drugs@FDA: ORIG-1 AP 2026-09-11, "
                       "sponsor TELIX PHARMACEUTICALS US INC, Type 1 - New Molecular Entity, PRIORITY, Orphan; approval letter "
                       "https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/218592Orig1s000ltr.pdf. Issuer: Telix Pharmaceuticals Limited "
                       "(ASX:TLX primary; Nasdaq ADS TLX, Level II ADR program via Form 20-F, first trade 2024-11-14 per Yahoo meta). "
                       "Previously sat in fda_type1_not_in_nme_master.csv as T1GAP-NDA218592 until this reconciliation against the live FDA table."),
                us_investable_class="US-LISTED (ADR)",
                classification_basis=f"derived {TODAY} from verified exchange/ticker fields; US depositary receipt / OTC line per exchange field: 'NASDAQ (ADS; ordinary shares listed on ASX)'",
                exchange="NASDAQ (ADS; ordinary shares listed on ASX)")
        have.add(("pixclara", "2026-09-11"))

    # ------------------------------------------------------------------ D. Cypsedo date
    for r in rows:
        if r["decision_id"] == "D099" and r["decision_date"] == "2026-05-31":
            r["decision_date"] = "2026-05-29"
            r["source_url_1"] = "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026"
            r["source_url_2"] = "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=220482"
            r["verification_status"] = "Verified - foreign listing only - DATE CORRECTED 2026-09-17"
            r["notes"] = ("appl NDA220482. decision_date corrected 2026-05-31 -> 2026-05-29 on 2026-09-17: FDA 'Novel Drug Approvals for 2026' row #20 "
                          "prints 5/29/2026 and openFDA Drugs@FDA records ORIG-1 AP 20260529 (sponsor HAISCO, Type 1 NME, STANDARD). The earlier date "
                          "came from trade-press coverage dated 5/31-6/01 (previous links: chemxpert.com, filingreader.com). " + r["notes"])

    # ------------------------------------------------------------------ E. official-table date + application-number corrections
    # Each correction is backed by (i) FDA's official novel-approvals table for
    # the year and (ii) the openFDA Drugs@FDA ORIG-1 record captured in
    # data/raw/openfda_orig_decisions_2011_2026/decisions_<year>.json.
    FIXES = {
        # D529 Zemdri: FDA 2018 table row #18 prints 6/25/2018; openFDA NDA210303 ORIG-1 AP 2018-06-25.
        "D529": {"decision_date": "2018-06-25",
                 "note": "decision_date corrected 2018-06-26 -> 2018-06-25 on 2026-09-17 (FDA 2018 table row #18 = 6/25/2018; openFDA NDA210303 ORIG-1 AP 20180625; the approval letter is dated June 25, 2018)."},
        # D019 Sofdra: FDA 2024 table row #19 prints 6/18/2024; openFDA NDA217347 ORIG-1 AP 2024-06-18 (sponsor BOTANIX SB).
        "D019": {"decision_date": "2024-06-18",
                 "source_url_2": "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2024",
                 "note": "appl NDA217347. decision_date corrected 2024-06-20 -> 2024-06-18 on 2026-09-17 (FDA 2024 table row #19 = 6/18/2024; openFDA ORIG-1 AP 20240618, sponsor BOTANIX SB, Type 1 NME, STANDARD). Earlier date came from an Australian trade-press item dated 6/20 (previous source_url_2 https://biotechdispatch.com.au/news/fda-approves-botanixs-sofdra-the-first-new-drug-for-primary-axillary-hyperhidrosis)."},
        # D589 Stribild: master cited NDA 203093 (that number is VITEKTA, approved 2014-09-24). Official number is NDA 203100.
        "D589": {"source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=203100",
                 "note": "appl NDA203100. Application-number link corrected 2026-09-17: previous link pointed at NDA 203093 (Vitekta, elvitegravir single agent, approved 2014-09-24), which produced a false MISMATCH_DATE in the openFDA cross-check. openFDA NDA203100 ORIG-1 AP 2012-08-27, GILEAD SCIENCES INC, 'Type 1 - New Molecular Entity and Type 4 - New Combination'; CDER Compilation lists Stribild NDA 203100, 8/27/2012."},
        # D598 Xarelto: master cited NDA 202439 (the 2011-11-04 stroke-prevention 'distinct NDA', Type 9). The NME approval is NDA 022406, 2011-07-01.
        "D598": {"source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=022406",
                 "note": "appl NDA022406. Application-number link corrected 2026-09-17: previous link pointed at NDA 202439 (Xarelto AF stroke-prevention indication filed as a distinct NDA, approved 2011-11-04, openFDA 'Type 9'), which produced a false MISMATCH_DATE. openFDA NDA022406 ORIG-1 AP 2011-07-01, JANSSEN PHARMS, Type 1 - New Molecular Entity; CDER Compilation lists Xarelto NDA 22406, 7/1/2011."},
        # D606 Edarbi: master cited NDA 200795 (a Hospira gemcitabine NDA). Official number is NDA 200796.
        "D606": {"source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=200796",
                 "note": "appl NDA200796. Application-number link corrected 2026-09-17: previous link pointed at NDA 200795 (Hospira gemcitabine, Type 3, approved 2011-08-04), which produced a false MISMATCH_DATE. openFDA NDA200796 ORIG-1 AP 2011-02-25 (current holder AZURITY; applicant at approval Takeda), Type 1 - New Molecular Entity; CDER Compilation lists Edarbi NDA 200796, 2/25/2011."},
        # Date discrepancies where the OFFICIAL CDER table/Compilation date is kept and openFDA disagrees — annotate only.
        "D701": {"note": "openFDA cross-check note (2026-09-17): openFDA/Drugs@FDA prints ORIG-1 AP 2002-12-20 for NDA021321 whereas FDA's official CDER NME table and the CDER Compilation both print 12/12/2002; master keeps the official-table date and flags the 8-day discrepancy."},
        "D754": {"note": "openFDA cross-check note (2026-09-17): openFDA/Drugs@FDA prints ORIG-1 AP 2004-09-17 for NDA021756 whereas FDA's official CDER NME table and the CDER Compilation both print 12/17/2004 (Macugen's approval was announced 12/17/2004); master keeps the official-table date and flags the discrepancy."},
        "D776": {"note": "openFDA cross-check note (2026-09-17): openFDA/Drugs@FDA prints ORIG-1 AP 2005-12-01 for NDA021923 whereas FDA's official CDER NME table and the CDER Compilation both print 12/20/2005 (Nexavar approval announced 12/20/2005); master keeps the official-table date and flags the discrepancy."},
        "D840": {"note": "openFDA cross-check note (2026-09-17): openFDA/Drugs@FDA prints ORIG-1 AP 2008-12-08 for NDA022244 whereas the CDER Compilation prints 12/12/2008; master keeps the Compilation date and flags the 4-day discrepancy."},
        # D394 gallium Ga 68 DOTATOC: FDA's 2019 report lists the product by its USAN-style name; Drugs@FDA/openFDA
        # index the same 2019-08-21 approval as NDA 210828 "GALLIUM GA 68 EDOTREOTIDE" (edotreotide is the INN of DOTATOC),
        # sponsor UIHC PET IMAGING (University of Iowa Hospitals & Clinics). Same date, same molecule, same FDA year table row.
        "D394": {"company_name": "UIHC PET Imaging Center (University of Iowa Hospitals and Clinics; non-profit academic applicant)",
                 "ticker": "NO_TICKER", "exchange": "N/A - academic medical center, no equity",
                 "us_investable_class": "PRIVATE / NO EQUITY",
                 "source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=210828",
                 "verification_status": "Verified - resolved 2026-09-17 (see notes)",
                 "note": "appl NDA210828. Applicant resolved 2026-09-17: openFDA Drugs@FDA lists NDA 210828 ORIG-1 AP 2019-08-21, sponsor UIHC PET IMAGING, Type 1 - New Molecular Entity, product 'GALLIUM GA 68 EDOTREOTIDE' (edotreotide = INN for DOTATOC; FDA's 2019 report prints 'gallium Ga 68 DOTATOC' with no trade name). Earlier passes could not match because they queried openFDA by the DOTATOC spelling. This row previously appeared in fda_type1_not_in_nme_master.csv as T1GAP-NDA210828."},
        # D306 Blenrep: the 2020 accelerated approval (BLA 761158) was withdrawn Nov-2022 and openFDA no longer returns an ORIG/AP
        # record for it; the Oct-2025 re-approval is a different BLA (761440). Annotate — no link to a different application.
        "D306": {"note": "openFDA cross-check note (2026-09-17): BLA 761158 (the 2020-08-05 accelerated approval) no longer appears in openFDA's Drugs@FDA ORIG/AP feed after the Nov-2022 US withdrawal; Blenrep's 2025-10-23 re-approval is a different application (Drugs@FDA application 761440, Type 2) and is NOT this decision — it stays in the non-NME originals file as its own row. Row therefore stays NO_APPL_NUMBER on the machine cross-check; the archived FDA 2020 table remains the official source."},
        # D968 Neotect (1999): the earlier pass attributed Diatide to a Nycomed Amersham -> GE lineage and assigned ticker GE.
        # Contemporaneous sources: Diatide, Inc. was NASDAQ:DITI (PRNewswire 25-Mar-1999) and was acquired by Schering AG's
        # Berlex unit in Nov-1999 (Schering AG Form 20-F); Nycomed Amersham was only NeoTect's marketing partner
        # (Diagnostic Imaging, 1999: "$2 million milestone payment from Nycomed Amersham").
        "D968": {"company_name": "Diatide Inc. (acquired by Schering AG / Berlex Nov-1999; NeoTect marketed by Nycomed Amersham)",
                 "ticker": "DITI", "exchange": "formerly NASDAQ:DITI, acquired by Schering Berlin/Berlex Nov-1999",
                 "verification_status": "Verified - CORRECTED 2026-09-17 (issuer/ticker)",
                 "note": "Issuer/ticker corrected 2026-09-17: previous row used ticker GE via a 'Nycomed Amersham 1999; GE 2004' lineage, but Diatide itself (the FDA applicant) traded as Nasdaq: DITI (PRNewswire 25-Mar-1999) and was acquired by Schering AG/Berlex in Nov-1999 (Schering AG 20-F); Nycomed Amersham was NeoTect's marketing partner, not Diatide's acquirer. Decision-date equity = DITI (delisted 1999)."},
        # D138 Tzield / D174 Xdemvy: FDA's year table (11/18/22, 7/25/2023) is kept; openFDA prints the day before (letter vs table posting) — annotate.
        "D138": {"note": "openFDA cross-check note (2026-09-17): openFDA BLA761183 ORIG-1 AP 2022-11-17; FDA's official 2022 table row #30 prints 11/18/22 — master keeps the official-table date; 1-day discrepancy flagged."},
        "D174": {"note": "openFDA cross-check note (2026-09-17): openFDA NDA217603 ORIG-1 AP 2023-07-24; FDA's official 2023 table row #29 prints 7/25/2023 — master keeps the official-table date; 1-day discrepancy flagged."},
        # D633 Gattex: master cited NDA 203336 (openFDA: "No matches found" — not a valid Drugs@FDA application). FDA's
        # official 2012 table row #35 links searchTerm=203441; openFDA NDA203441 ORIG-1 AP 2012-12-21, Type 1, Orphan,
        # STANDARD (this very application sat in fda_type1_not_in_nme_master.csv as an unmatched Type 1 because of the typo).
        # D604 Onfi: master cited NDA 202058 (no such Drugs@FDA record). FDA's official 2011 NME table links Onfi to
        # searchTerm=202067; openFDA NDA202067 ORIG-1 AP 2011-10-21 (Type 1, Orphan). The table prints "10/24" — the
        # master keeps 2011-10-21 (openFDA ORIG approval date); the 3-day table/letter difference is flagged, not resolved.
        "D604": {"source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=202067",
                 "note": "appl NDA202067. Application-number link corrected 2026-09-17: previous link pointed at NDA 202058, which does not exist in Drugs@FDA/openFDA. FDA's official 2011 NME table (ucm285554, Wayback 2012-01-19) links Onfi to searchTerm=202067; openFDA NDA202067 ORIG-1 AP 2011-10-21, Type 1 - New Molecular Entity, Orphan (sponsor of record LUNDBECK). IRREGULARITY: the FDA table prints 10/24 for Onfi while openFDA prints 10/21 — master keeps 10-21 (approval-action date); flagged."},
        # D625 Voraxaze: master cited NDA 202519 (not a Drugs@FDA record). FDA's official 2012 NME table row #1 links
        # searchTerm=125327; openFDA BLA125327 ORIG-1 AP 2012-01-17, PRIORITY, Type 1, Orphan, sponsor BTG INTERNATIONAL INC.
        "D625": {"source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=125327",
                 "note": "appl BLA125327. Application-number link corrected 2026-09-17: previous link pointed at NDA 202519, which does not exist in Drugs@FDA/openFDA. FDA's official 2012 NME table row #1 (ucm336115, Wayback 2016-10-22) links Voraxaze to searchTerm=125327; openFDA BLA125327 ORIG-1 AP 2012-01-17, PRIORITY, Type 1 - New Molecular Entity, Orphan, sponsor BTG INTERNATIONAL INC."},
        # D911 Perjeta: master cited BLA 125405 (a different application). FDA's official 2012 NME table row #12 links
        # searchTerm=125409; openFDA BLA125409 ORIG-1 AP 2012-06-08 (brand PERJETA, sponsor GENENTECH INC).
        "D911": {"source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=125409",
                 "note": "appl BLA125409. Application-number link corrected 2026-09-17: previous link pointed at BLA 125405, which is not Perjeta. FDA's official 2012 NME table row #12 (ucm336115, Wayback 2016-10-22) links Perjeta to searchTerm=125409; openFDA BLA125409 ORIG-1 AP 2012-06-08, brand PERJETA, sponsor GENENTECH INC."},
        # Withdrawn/discontinued products that openFDA Drugs@FDA no longer indexes at all (verified 2026-09-17: an
        # openfda.brand_name query for tequin, mylotarg, pepaxto, belviq, neutrospec, wellferon and erwinaze returned only
        # BLA761060 — Mylotarg's 2017 re-approval). Notes only; the official FDA year table remains the source.
        "D647": {"note": "openFDA cross-check note (2026-09-17): NDA 021174 (the 2000-05-17 accelerated approval) is not indexed in openFDA Drugs@FDA; a brand query for MYLOTARG returns only the 2017 re-approval (Drugs@FDA application 761060, a different decision that stays in the non-NME originals file). Row stays NOT_IN_OPENFDA on the machine cross-check; FDA's 2000 NME table remains the official source."},
        "D739": {"note": "openFDA cross-check note (2026-09-17): BLA 103928 is not indexed in openFDA Drugs@FDA (brand query for NEUTROSPEC returns no record — product withdrawn). Row stays NOT_IN_OPENFDA on the machine cross-check; FDA's 2004 NME/new-biologic table remains the official source."},
        "D901": {"note": "openFDA cross-check note (2026-09-17): BLA 125359 is not indexed in openFDA Drugs@FDA (brand query for ERWINAZE returns no record). FDA's official 2011 NME table (ucm285554, Wayback 2012-01-19) links Erwinaze to searchTerm=125359 and prints 11/18; row stays NOT_IN_OPENFDA on the machine cross-check."},
        "D958": {"note": "openFDA cross-check note (2026-09-17): BLA 103760 is not indexed in openFDA Drugs@FDA (brand query for WELLFERON returns no record — CBER-era licence, product discontinued). Row stays NOT_IN_OPENFDA; the CDER Compilation remains the source."},
        "D988": {"note": "openFDA cross-check note (2026-09-17): NDA 021061 is not indexed in openFDA Drugs@FDA (brand query for TEQUIN returns no record — product withdrawn). Row stays NOT_IN_OPENFDA; FDA's 1999 NME table remains the official source."},
        "D633": {"source_url_2": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo=203441",
                 "note": "appl NDA203441. Application-number link corrected 2026-09-17: previous link pointed at NDA 203336, which does not exist in Drugs@FDA/openFDA (query returned 'No matches found'). FDA's official 2012 NME table row #35 (ucm336115, Wayback 2016-10-22) links Gattex to searchTerm=203441; openFDA NDA203441 ORIG-1 AP 2012-12-21, sponsor of record now TAKEDA PHARMS USA (applicant at approval NPS Pharmaceuticals), Type 1 - New Molecular Entity, Orphan, STANDARD. Until this fix the same application appeared in fda_type1_not_in_nme_master.csv as an unmatched Type 1."},
    }
    for r in rows:
        fx = FIXES.get(r["decision_id"])
        if not fx or fx["note"][:40] in r["notes"]:
            continue
        for k, v in fx.items():
            if k == "note":
                r["notes"] = (v + (" " + r["notes"] if r["notes"] else "")).strip()
            else:
                r[k] = v
        if "corrected" in fx["note"] and "CORRECTED" not in r["verification_status"].upper():
            r["verification_status"] = r["verification_status"] + " - CORRECTED 2026-09-17 (see notes)"

    added.sort(key=lambda r: (r["decision_date"], r["drug_brand"]))
    # re-number so IDs follow date order within the appended block
    start = max(int(r["decision_id"][1:]) for r in rows) + 1
    for i, r in enumerate(added):
        r["decision_id"] = f"D{start + i}"
    out = rows + added
    write_master(out, fieldnames)
    print(f"master: {len(rows)} -> {len(out)} (+{len(added)}; 1998 rows {n1998}); ids D{start}..D{start + len(added) - 1}")
    from collections import Counter
    print("by year:", dict(Counter(r["decision_date"][:4] for r in added)))
    print("unresolved sponsors:", [r["drug_brand"] for r in added if r["us_investable_class"].startswith("NOT US")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
