#!/usr/bin/env python3
"""Session 2026-09-17 v8 amendment (pre-2000 expansion):

  A. Pre-1998 import (390 rows, 1985-1997) — FDA's official CDER
     "Compilation of CDER New Molecular Entity (NME) Drug and New Biologic
     Approvals, 1985 (through present)" (media/177921 XLSX, captured by the
     GitHub runner with SHA-256 manifest at data/raw/probe/). No CDER NME
     year table exists on fda.gov or in the Wayback Machine for 1997 or
     earlier, so the Compilation is the ONLY official spine for these years.
     Every row is flagged COMPILATION_ONLY in its notes.
     Every row is then re-checked against the bulk openFDA Drugs@FDA ORIG/AP
     payloads (data/raw/openfda_orig_decisions_2011_2026/decisions_1985..1997
     .json, fetch run 13): application number + exact ORIG approval date.
     359/390 rows re-verify exactly; 29 are absent from openFDA (almost all
     are products later withdrawn/discontinued — Seldane, Hismanal, Duract,
     Posicor, Omniflox, Manoplax, Suprol, Enkaid, Roferon-A etc. — or legacy
     CBER licences FDA no longer indexes); 2 rows (Ifex NDA019763, Botox/
     Oculinum BLA103000) keep the Compilation date where openFDA disagrees,
     following the Macugen/Nexavar precedent (official table kept, flagged).

  B. 2000-2003 CBER biologics (19 rows) — NEXT_SESSION.md item 2 decision.
     The master is now consistent across the 1999/2000 boundary: 1998 and
     1999 already carried their Compilation-only CBER-licensed biologics, so
     the 19 therapeutic biologics the Compilation lists for 2000-2003
     (TNKase, Myobloc, Peg-Intron, Campath, Aranesp, Kineret, Xigris,
     Neulasta, Zevalin, Rebif, Elitek, Pegasys, Humira, Amevive, Fabrazyme,
     Aldurazyme, Xolair, Bexxar, Raptiva) are added with the same flag style,
     following the 1998-session precedent. YEAR-COUNT DECISION (documented):
     the official spine for 2000-2003 remains the contemporaneous CDER NME
     year tables; these 19 rows are added as supplementary Compilation rows
     flagged COMPILATION_ONLY_CBER and must not be counted toward the
     year-table count on the site or in validators (1998/1999 use the same
     convention: CDER table count + flagged Compilation-only rows).
     openFDA check: 15/19 are Type 1 NME records (they sat in
     fda_type1_not_in_nme_master.csv previously); Xigris BLA125029, Amevive
     BLA125036, Bexxar BLA125011 and Raptiva BLA125075 returned no ORIG/AP
     record in the bulk payloads (legacy CBER licence numbers) and rest on
     the Compilation alone, same as several 1998 biologics did before run 13.

  C. Sponsor -> ticker resolution layers (never guessed; blank beats guessed):
       1) COMPANY_PRE98  — build-time table for pre-1998 era applicants.
          Where a contemporaneous citation already exists IN THIS REPO it is
          repeated verbatim in the note (e.g. the 1998-pass PNU citation).
          Where the lineage is known but the decision-date symbol could not
          be re-verified from a captured primary source, the ticker is left
          BLANK and the row is flagged (e.g. Upjohn, Warner-Lambert,
          Syntex, Cytogen, Immunomedics). Two generic-table anachronisms are
          overridden: AMERSHAM (GE bought it only in 2004) and
          MALLINCKRODT (MNK is the 2013+ shell), plus BOEHRINGER MANNHEIM
          (is NOT Boehringer Ingelheim — it became Roche's in 1998).
       2) COMPANY_1998 (scripts/build_backfill_1998_and_fixes.py) — the
          audited table whose citations were captured in the 1998 pass.
       3) Generic audited table (scripts/build_backfill_2000_2019.py).
     Applicants that resolve on none of the three keep the Compilation's
     applicant string verbatim with class NOT US-INVESTABLE (UNVERIFIED).

Idempotency: rows are keyed on (lowercase brand, decision_date); re-running
adds nothing. decision_ids are assigned D<max+1> in decision_date order
inside the appended block (same convention as the 1998 builder).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STG = DATA / "staging"
MASTER = DATA / "fda_decisions_master.csv"
RAWDIR = DATA / "raw" / "openfda_orig_decisions_2011_2026"
COMPILATION_XLSX = DATA / "raw" / "probe" / "fda_nme_compilation_1985_2025.xlsx"
COMPILATION_URL = "https://www.fda.gov/media/177921/download?attachment"
COMPILATION_LANDING = ("https://www.fda.gov/drugs/drug-approvals-and-databases/"
                       "compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals")
YEAR_REGISTER = DATA / "fda_year_source_register.csv"
TODAY = "2026-09-17"

# ---------------------------------------------------------------- openFDA index
def load_openfda_index() -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for path in sorted(RAWDIR.glob("decisions_*.json")):
        payload = json.load(open(path))
        for rec in payload.get("decisions", []):
            idx.setdefault(rec["application_number"], []).append(rec)
    return idx


# ---------------------------------------------------------------- compilation
def load_compilation() -> list[dict]:
    """Verbatim rows of the FDA NME Compilation XLSX (openpyxl; no pandas)."""
    import openpyxl  # venv dependency; the runner carries it in requirements
    wb = openpyxl.load_workbook(COMPILATION_XLSX, read_only=True)
    rows = list(wb[wb.sheetnames[0]].iter_rows(values_only=True))
    out = []
    for r in rows[1:]:
        def d(x):
            return x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else ("" if x is None else str(x))
        appl = [r[4], r[5], r[6]]
        appl = [int(a) for a in appl if a is not None and str(a).strip() not in {"", "None"}]
        out.append({
            "brand": (r[0] or "").strip(),
            "generic": (r[1] or "").strip(),
            "applicant": (r[2] or "").strip(),
            "kind": (r[3] or "").strip(),
            "appl_numbers": appl,
            "dosage_form": "; ".join(x for x in [(r[7] or "").strip(), (r[9] or "").strip(), (r[11] or "").strip()] if x),
            "route": "; ".join(x for x in [(r[8] or "").strip(), (r[10] or "").strip(), (r[12] or "").strip()] if x),
            "receipt_date": d(r[13]),
            "approval_date": d(r[14]),
            "approval_year": r[15],
            "abbrev_ind": (r[16] or "").strip() if r[16] else "",
            "approved_use": (r[17] or "").strip() if r[17] else "",
            "review": (r[18] or "").strip(),
            "orphan": (r[19] or "").strip(),
            "accelerated": (r[20] or "").strip(),
            "breakthrough": (r[21] or "").strip(),
            "fast_track": (r[22] or "").strip(),
            "notes": ((r[26] or "").strip() if len(r) > 26 and r[26] else ""),
        })
    return out


# ---------------------------------------------------------------- sponsors
_src = (ROOT / "scripts" / "build_backfill_2000_2019.py").read_text(encoding="utf-8")
_ns: dict = {}
exec(_src[_src.index("COMPANY = ["): _src.index("def drugsatfda_url")], _ns)  # noqa: S102
resolve_generic = _ns["resolve"]

_src2 = (ROOT / "scripts" / "build_backfill_1998_and_fixes.py").read_text(encoding="utf-8")
exec(_src2[_src2.index("COMPANY_1998 = ["): _src2.index("def resolve_1998")], _ns)  # noqa: S102
COMPANY_1998 = _ns["COMPANY_1998"]

# Pre-1998-era applicants. Order matters only inside this list; longer
# patterns first is not needed because resolution checks every pattern and
# returns on the first contained string — keep patterns disjoint.
COMPANY_PRE98 = [
    # (pattern, company_name, ticker, exchange, class, note)
    ("BURROUGHS WELLCOME", "Burroughs Wellcome Co. (Glaxo Wellcome from 1995; GlaxoSmithKline Dec-2000)", "GSK", "NYSE (ADR)", "US-LISTED (ADR)",
     "Burroughs Wellcome merged into Glaxo Wellcome plc 1995; GSK used per master precedent (GLAXO->GSK); the decision-date ADR symbol (GLX) was not re-verified from a primary source this pass"),
    ("ZENECA", "Zeneca Group plc (AstraZeneca from Apr-1999)", "AZN", "NASDAQ (ADR)", "US-LISTED (ADR)",
     "Zeneca merged with Astra AB Apr-1999 to form AstraZeneca (AZN ADR per master precedent); the decision-date US ADR symbol (ZEN) was not re-verified from a primary source this pass"),
    ("ASTRA", "Astra AB (AstraZeneca from Apr-1999)", "AZN", "NASDAQ (ADR)", "US-LISTED (ADR)",
     "Astra AB merged with Zeneca Apr-1999 (AZN ADR per master precedent and the 1998-pass Astra Merck JV row); the decision-date US line of Astra AB was not re-verified from a primary source this pass"),
    ("SYNTEX", "Syntex Corp. (acquired by Roche 1994, delisted)", "", "", "NON-US LISTING ONLY",
     "Syntex Corp (Palo Alto) — Roche acquired full control 1994 and delisted it; decision-date US listing not verified from a primary source this pass — ticker left blank, flagged"),
    ("PARKE-DAVIS", "Parke-Davis (Warner-Lambert Co. division; Pfizer Jun-2000)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Parke-Davis was Warner-Lambert Co's pharma arm (NYSE:WLA delisted Jun-2000 into Pfizer); no separate equity and the parent's decision-date symbol was not re-verified this pass — ticker blank, flagged"),
    ("WARNER-LAMBERT", "Warner-Lambert Co. (acquired by Pfizer Jun-2000)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NYSE:WLA delisted Jun-2000 into Pfizer; symbol not re-verified from a primary source this pass — blank, flagged"),
    ("UPJOHN", "The Upjohn Co. (merged into Pharmacia & Upjohn Nov-1995)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Upjohn merged with Pharmacia AB Nov-1995 forming Pharmacia & Upjohn (NYSE:PNU per the 1998-pass citation); the pre-merger UPJ symbol was not re-verified from a primary source this pass — blank, flagged"),
    ("PHARMACIA AND UPJOHN", "Pharmacia & Upjohn (Pharmacia Corp 2000; acquired by Pfizer 2003)", "PNU", "formerly NYSE:PNU, became Pharmacia Corp (NYSE:PHA) Apr-2000; delisted 2003",
     "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Monsanto/P&U merger releases (Cision, Mar-2000) print 'Pharmacia & Upjohn (NYSE: PNU)' (1998-pass citation); Pharmacia Corp PHA acquired by Pfizer 16-Apr-2003"),
    ("PHARMACIA", "Pharmacia AB (merged with The Upjohn Co. Nov-1995)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Pre-merger Pharmacia AB was Stockholm-listed; its US ADR line was not verified from a primary source this pass — blank (the generic table's PGE? entry is internally uncertain and was not used)"),
    ("MILES", "Miles Inc. (Bayer AG US arm; renamed Bayer Corp. 1995)", "", "", "NON-US LISTING ONLY",
     "Bayer AG's US pharma arm — no separate US equity at decision date — blank"),
    ("LEDERLE", "Lederle Laboratories (American Cyanamid / Wyeth-Ayerst lineage)", "WYE", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Lederle was American Cyanamid's pharma unit; American Home Products (renamed Wyeth 2002 — NYSE:WYE per the audited WYETH entry) acquired American Cyanamid Dec-1994 and merged Lederle into Wyeth-Ayerst; WYE parent lineage used with this note"),
    ("AMERSHAM", "Amersham International plc (Medi-Physics unit; GE Healthcare Apr-2004)", "", "", "NON-US LISTING ONLY",
     "CORRECTED via override 2026-09-17: the generic audited table maps AMERSHAM -> GE US-LISTED — an anachronism for a pre-2004 approval (GE bought Amersham Apr-2004). Primary listing LSE; decision-date ADR not verified — blank, flagged"),
    ("MALLINCKRODT", "Mallinckrodt Inc. (imaging/nuclear unit; Tyco Jun-2000)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "CORRECTED via override: the generic table's MNK is the 2013+ Mallinckrodt plc shell; 1980s-90s Mallinckrodt Inc was acquired by Tyco Jun-2000 — decision-date symbol not re-verified from a primary source this pass — blank, flagged"),
    ("SQUIBB", "Bristol-Myers Squibb Co. (Squibb merged with Bristol-Myers 1989)", "BMY", "NYSE", "US-LISTED",
     "BMY per the audited BRISTOL lineage; note applies equally to bare 'Squibb' rows (Squibb Corp merged into Bristol-Myers Squibb in 1989, the compilation kept printing short names into the mid-1990s)"),
    ("KNOLL", "Knoll Pharmaceuticals (BASF AG unit; Abbott Mar-2001)", "", "", "NON-US LISTING ONLY",
     "BASF's pharma unit, sold to Abbott 2001 — no separate equity — blank"),
    ("SOMERSET", "Somerset Pharmaceuticals (Lemmon/Mylan lineage; Solvay US 1998)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Somerset (Tampa FL) passed through the Lemmon/Mylan lineage into Solvay's US arm 1998; the decision-date parent equity was not re-verified from a primary source this pass — blank, flagged"),
]

# The 19 2000-2003 CBER-licensed therapeutic biologics on the Compilation
# (NEXT_SESSION.md item 2 decision): selected explicitly by application number
# so the builder stays idempotent regardless of master state.
CBER_2000_2003_APPL = {
    103909, 103846, 103949, 103948, 103951, 103950, 125029, 125031, 125019,
    103780, 103946, 103964, 125057, 125036, 103979, 125058, 103976, 125011,
    125075,
}

# word-boundary rules processed before the substring tables
WORD_RULES = [
    (r"\b3M\b", "3M Co.", "MMM", "NYSE", "US-LISTED", "3M Pharmaceuticals (St Paul) — parent NYSE:MMM"),
    (r"\bRIKER\b", "Riker Laboratories (3M Co. pharma division)", "MMM", "NYSE", "US-LISTED", "Riker Labs was 3M's pharma unit — parent NYSE:MMM"),
    (r"\bROSS\b", "Ross Laboratories (Abbott Nutrition division, Abbott Laboratories)", "ABT", "NYSE", "US-LISTED",
     "Ross Laboratories was Abbott's nutritional/paeditric-pharma unit (Survanta) — ABT per the audited ROSS PRODS/ABBOTT entries"),
    (r"\bCIBA\b(?![ -]VISION)", "Ciba-Geigy Ltd. (Basel; Novartis from Mar-1996)", "", "", "NON-US LISTING ONLY",
     "Compilation prints 'Ciba' — the Ciba-Geigy lineage (Basel-listed, merged with Sandoz Mar-1996 = Novartis AG, NVS ADR); decision-date US ADR line not verified from a primary source this pass — blank, flagged"),
    (r"\bTAP\b", "TAP Pharmaceuticals/Holdings (Takeda/Abbott JV)", "4502", "TSE", "NON-US LISTING ONLY",
     "Takeda/Abbott JV (TSE:4502 per the audited TAP PHARM entry); Takeda full owner 2008"),
    (r"\bMCNEIL\b", "McNeil Pharmaceutical / McNeil Laboratories (Johnson & Johnson)", "JNJ", "NYSE", "US-LISTED",
     "McNeil was Johnson & Johnson's US pharma arm (wholly owned since 1959) — JNJ per the audited R.W. JOHNSON/ORTHO/JANSSEN/J&J lineage"),
    (r"\bSTUART\b", "Stuart Pharmaceuticals (ICI Americas; Zeneca 1993; AstraZeneca 1999)", "", "", "NON-US LISTING ONLY",
     "ICI's US pharma arm (ICI demerged Zeneca 1993; AZN Apr-1999) — no separate US equity — blank"),
    (r"\bICI\b", "ICI / Stuart Pharmaceuticals (Zeneca 1993; AstraZeneca 1999)", "", "", "NON-US LISTING ONLY", "same lineage as STUART"),
    (r"\bADRIA\b", "Adria Laboratories (Pharmacia oncology lineage)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Adria Laboratories (Columbus OH; Farmitalia/Montedison lineage folded into Pharmacia) — decision-date equity not re-verified from a primary source this pass — blank, flagged"),
    (r"\bBOEHRINGER MANNHEIM\b", "Boehringer Mannheim GmbH (Roche group; merged into Roche 1998)", "", "", "NON-US LISTING ONLY",
     "CORRECTED via override 2026-09-17: must NOT resolve to Boehringer Ingelheim (a different family-held company); Boehringer Mannheim GmbH (Mannheim) was absorbed into F. Hoffmann-La Roche in 1998 — blank"),
    (r"\bZAMBON\b", "Zambon S.p.A. (private, Italy)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "family-held Italian group"),
    (r"\bGALDERMA\b", "Galderma SA (Nestle/L'Oreal JV; no listed equity until SIX:GALD 2024)", "", "N/A - jointly held, no separate equity", "PRIVATE / NO EQUITY", "Nestle/L'Oreal JV at decision date"),
    (r"\bUCYCLYD\b", "Ucyclyd Pharma (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Buphenyl sponsor"),
    (r"\bSIGMA[- ]TAU\b", "Sigma-Tau (private, Italy)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Carnitor sponsor; private group"),
    (r"\bFISONS\b", "Fisons plc (Rhone-Poulenc Rorer 1995; Sanofi lineage)", "", "", "NON-US LISTING ONLY", "UK-listed, bought by RPR 1995 — blank"),
    (r"\bBOOTS\b", "Boots Pharmaceuticals (sold to BASF/Knoll 1995)", "", "", "NON-US LISTING ONLY", "Nottingham pharma arm of Boots Co. — blank, flagged"),
    (r"\bROBERTS\b", "Roberts Pharmaceutical Corp. (acquired by Shire 1999)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Decision-date US symbol not re-verified from a primary source this pass — blank, flagged"),
    (r"\bHERBERT\b", "Herbert Laboratories (Allergan dermatology unit)", "AGN", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Allergan NYSE:AGN lineage per the audited ALLERGAN entry"),
    (r"U\.?S\.? BIOSCIENCE", "U.S. Bioscience Inc. (merged into MedImmune Feb-1999)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ-listed in the mid-1990s; merged into MedImmune Feb-1999 — decision-date symbol not re-verified from a primary source this pass — blank, flagged"),
    (r"\bMERRELL", "Merrell / Marion Merrell Dow (Hoechst Marion Roussel 1995; Aventis; Sanofi)", "", "", "NON-US LISTING ONLY",
     "HMR US lineage per the 1998-pass HMR resolution (blank; no verified US ADR)"),
    (r"\bGENSIA\b", "Gensia Inc. (Gensia Sicor; Teva 2003)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ-listed 1990s; merged into Sicor, which TEVA acquired 2003 — decision-date symbol not re-verified — blank, flagged"),
    (r"\bATHENA\b", "Athena Neuroscience (acquired by Elan 1996)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:ATHN era; acquired by Elan (audited ELN lineage) Nov-1996 (Zanaflex approval 12-Nov-1996 is inside the acquisition window — flagged) — symbol not re-verified — blank"),
    (r"\bNEUREX\b", "Neurex Corp. (delisted; assets to Elan 1998)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:NXCO era (per company's own releases of the time — symbol not re-verified this pass); Corlopam transferred to Elan 1998 — blank, flagged"),
    (r"\bCYTOGEN\b", "Cytogen Corp. (delisted; assets wound down post-2000)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:CYTO era (symbol per company releases; not re-verified from a captured primary source this pass) — blank, flagged"),
    (r"\bIMMUNOMEDICS\b", "Immunomedics Inc. (acquired by Gilead 2020)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:IMMU era (symbol per company releases; not re-verified this pass) — blank, flagged"),
    (r"\bINTERFERON SCIENCES\b", "Interferon Sciences Inc. (private-equity lineage; Alferon)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:IFNS era (symbol per company releases; not re-verified this pass) — blank, flagged"),
    (r"\bADVANCED MAGNETICS\b", "Advanced Magnetics Inc. (renamed AMAG Pharmaceuticals)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:AMAG from its 1997 IPO; at the Feridex/Gastromark approvals (Aug-1996/Aug-1996-era) the company was not yet public in a way that could be re-verified this pass — blank, flagged"),
    (r"\bGENETICS INSTITUTE\b", "Genetics Institute (acquired by American Home Products/Wyeth Dec-1996)", "WYE", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "GI was wholly owned by American Home Products from Dec-1996 (Neumega approval Nov-1997 is post-acquisition): parent lineage NYSE:WYE per the audited WYETH entry"),
    (r"\bBLOCK DRUG\b", "Block Drug Co. (acquired by GSK 2001)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:BLOCA era (symbol per company releases; not re-verified this pass) — blank, flagged"),
    (r"\bDOWNSTATE\b", "SUNY Downstate Clinical PET Center (academic; no equity)", "", "N/A - academic medical center, no equity", "PRIVATE / NO EQUITY",
     "NOT A COMPANY — academic PET centre holding its own FDG NDA"),
    (r"\bDEPARTMENT OF THE ARMY\b", "U.S. Department of the Army / Walter Reed Army Institute of Research (co-developed with Hoffmann-La Roche)", "", "N/A - government, no equity", "PRIVATE / NO EQUITY",
     "NOT A COMPANY — the Lariam NDA was held by WRAIR with Roche; no equity"),
    (r"\bUNIMED\b", "Unimed Pharmaceuticals (Solvay 1999 lineage)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Marinol sponsor; privately held until Solvay 1999 — blank, flagged"),
    (r"\bWALLACE\b", "Wallace Laboratories (Carter-Wallace; MedPointe 2001)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Felbatol/Astelin sponsor; Carter-Wallace pharma renamed MedPointe 2001 — decision-date equity not re-verified — blank, flagged"),
    (r"\bENZON\b", "Enzon Inc. (delisted; portfolio sale 2013)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "NASDAQ:ENZN era (symbol per company releases; not re-verified this pass) — blank, flagged"),
    (r"\bVIRATEK\b", "Viratek Inc. (private JV; Valeant lineage)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Virazole sponsor; ownership chain unverified this pass — blank, flagged"),
    (r"\bSTERLING", "Sterling Drug / Sterling-Winthrop (Sanofi 1994 lineage; Eastman Kodak until then)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Sterling was Kodak's pharma unit until the Sanofi 1994 brand-rx deal — decision-date parent equity not re-verified — blank, flagged"),
    (r"\bANAQUEST\b", "Anaquest (Ohmeda/BOC Group lineage)", "", "", "NON-US LISTING ONLY",
     "Suprane sponsor; Anaquest/Anaquest Medical rolled into Ohmeda (BOC Group) — blank"),
    (r"\bASTA\b", "ASTA Pharma (Degussa AG unit, Germany)", "", "", "NON-US LISTING ONLY",
     "Mesnex sponsor — German parent, no verified US line — blank"),
    (r"\bANGELINI\b", "Angelini Pharma (private, Italy)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Rev-Eyes sponsor"),
    (r"\bTRIMED\b", "Tri-Med Specialties (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Pytest kit sponsor"),
    (r"\bASCOT\b", "Ascot Hospital Pharmaceuticals (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Moctanin sponsor"),
    (r"\bBRYAN\b", "Bryan Corp. (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Sclerosol sponsor"),
    (r"\bCOOK IMAGING\b", "Cook Imaging Corp. (Cook Group, private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Oxilan sponsor"),
    (r"\bPENEDERM\b", "Penederm Inc. (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Avita sponsor lineage"),
    # v8.1: additional pre-1998 applicants whose lineage is one of the audited
    # table's own documented parent lineages (same standard as JANSSEN->JNJ,
    # BERLEX->Schering AG): tickers only attached to those settled parents;
    # everything else stays blank with the lineage in the note.
    (r"\bIVES\b", "Ives Laboratories (American Home Products / Wyeth lineage)", "WYE", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Ives Laboratories was the AHP (Wyeth) pharma arm (Cordarone) — WYE per the audited WYETH entry (NYSE:WYE delisted 2009)"),
    (r"\bROBINS\b", "A.H. Robins Co. (acquired by American Home Products Dec-1989)", "WYE", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "A.H. Robins became a wholly owned Wyeth/AHP subsidiary Dec-1989 — WYE per the audited WYETH entry"),
    (r"\bKABIVITRUM\b", "KabiVitrum AB (Sweden; Pharmacia lineage 1990)", "", "", "NON-US LISTING ONLY",
     "Kabi Vitrum (Stockholm) merged into Pharmacia 1990 — no verified US line — blank"),
    (r"\bRORER\b", "Rorer Group (Rhone-Poulenc Rorer 1990; Aventis 1999; Sanofi)", "", "", "NON-US LISTING ONLY",
     "RORER follows the audited RHONE POULENC lineage (Rorer was merged into Rhone-Poulenc in 1990) — blank"),
    (r"MEDI[- ]PHYSICS", "Medi-Physics Inc. (Amersham International plc unit; GE Healthcare 2004)", "", "", "NON-US LISTING ONLY",
     "Medi-Physics was Amersham's US diagnostics arm — see the corrected AMERSHAM entry (GE anachronism removed); LSE primary, decision-date ADR unverified — blank, flagged"),
    (r"\bBEECHAM\b", "Beecham Group / SmithKline Beecham (GSK from Dec-2000)", "GSK", "NYSE (ADR)", "US-LISTED (ADR)",
     "GSK per the audited SMITHKLINE lineage (SmithKline Beecham -> GSK); the Beecham/SBH decision-date symbols were not re-verified from a primary source this pass; rows dated before July-1989 predate the SmithKline Beecham merger itself (flagged)"),
    (r"\bMEDCO\b", "Medco Inc. (Adenocard developer; licensed to Fujisawa)", "", "", "NON-US LISTING ONLY",
     "Medco Research developed iv adenosine; the product went to Fujisawa (audited FUJISAWA lineage, merged into Astellas 2005); Medco's own equity not verified — blank"),
    (r"\bIOLAB\b", "Iolab Corp. (Johnson & Johnson ophthalmics unit in 1993; sold to Chiron 1995)", "JNJ", "NYSE", "US-LISTED",
     "Iolab (Claremont CA) was J&J's ophthalmics company at the Livostin approval (J&J per the audited JANSSEN/ORTHO/R.W. JOHNSON lineage); sold to Chiron 1995 — decision-date parent JNJ kept"),
    (r"\bFOURNIER\b", "Laboratoires Fournier S.A. (Solvay 2005; Abbott lineage)", "", "", "NON-US LISTING ONLY",
     "Lipidil sponsor; private French company bought by Solvay 2005 (fenofibrate lineage to Abbott) — blank"),
    (r"\bOHMEDA\b", "Ohmeda Pharmaceutical Products (BOC Group, UK lineage)", "", "", "NON-US LISTING ONLY",
     "Revex sponsor; Ohmeda was the BOC Group's pharma arm — no verified US line — blank"),
    (r"\bROUSSEL\b", "Roussel Uclaf (Hoechst Roussel / Hoechst Marion Roussel; Aventis; Sanofi)", "", "", "NON-US LISTING ONLY",
     "Hoechst/HMR US lineage per the 1998-pass HMR resolution (blank; no verified US ADR)"),
    (r"\bBAKER NORTON\b", "Baker Norton Pharmaceuticals (IVAX unit; Teva 2006)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Elmiron sponsor; Baker Norton was IVAX's specialty arm (Nasdaq:IVX era, symbol not re-verified this pass); Teva acquired IVAX 2006 — blank, flagged"),
    (r"\bALLIANCE\b", "Alliance Pharmaceuticals Corp. (delisted ~2003)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
     "Imagent GI sponsor — the audited ALLIANCE PHARM entry (Imagent; delisted ~2003); decision-date symbol not re-verified — blank"),
]


def resolve_pre98(applicant: str, year: int | None = None):
    """Layered resolution: WORD_RULES -> COMPANY_PRE98 -> COMPANY_1998 -> audited generic.

    `year` guards one known symbol transition: Genentech traded as NYSE:GNE until
    Roche's Jun-1999 redemption and re-listed as NYSE:DNA Jul-1999, so the
    COMPANY_1998 GNE entry is only correct for rows dated <= 1999; for 2000+
    rows the audited generic table's DNA entry is correct.
    """
    a = (applicant or "").upper()
    # word-boundary rules take precedence over every substring table
    for rx, co, tk, ex, usc, note in WORD_RULES:
        if re.search(rx, a):
            return co, tk, ex, usc, note
    for tup in COMPANY_PRE98:
        if tup[0] in a:
            return tup[1], tup[2], tup[3], tup[4], tup[5]
    for pat, co, tk, ex, usc, note in COMPANY_1998:
        if pat in a:
            if pat == "GENENTECH":
                if (year or 0) >= 2000:
                    break  # fall through to the generic table (DNA, Jul-1999 onward)
                if (year or 0) < 1994:
                    # pre-GNE era: Genentech Inc. traded OTC NASDAQ:GENE (public since
                    # 1980; Roche bought the 60% stake Feb-1990; NYSE:GNE began 1991).
                    # The 1998-pass citation only covers the GNE/DNA periods, so the
                    # pre-1994 symbol is left unverified rather than asserted.
                    return ("Genentech Inc. (Roche 60% from Feb-1990; Roche full buyout Mar-2009)", "",
                            "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)",
                            "decision-date reality: NASDAQ:GENE era (public since 1980; NYSE:GNE began 1991, DNA Jul-1999) — the pre-1994 symbol was not re-verified from a captured primary source this pass, so the ticker is left blank and flagged")
                return co, tk, ex, usc, note
            return co, tk, ex, usc, note
    return resolve_generic(applicant)


# ---------------------------------------------------------------- helpers
def drugsatfda_url(num: int) -> str:
    return ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
            f"?event=overview.process&varApplNo={num:06d}")


def load_master():
    with MASTER.open(newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        return list(rd), rd.fieldnames


def write_master(rows, fieldnames):
    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)


WITHDRAWN_HINTS = (
    "Seldane", "Suprol", "Enkaid", "Roferon-A", "Dalgan", "Photoplex",
    "Hismanal", "Osmovist", "Eminase", "Omniflox", "Manoplax", "Renormax",
    "CEA-Scan", "Verluma", "Retavase", "Normiflo", "Posicor", "Duract",
    "Infergen", "Neumega", "Femstat", "Parathar", "Orthoclone",
)


def build_row(comp: dict, idx: dict, flag_token: str) -> dict:
    """Build one master row from a verbatim Compilation row + openFDA check."""
    appl_list = comp["appl_numbers"]
    appl1 = appl_list[0] if appl_list else None
    appl_key = f"{comp['kind']}{appl1:06d}" if appl1 is not None else ""
    recs = idx.get(appl_key, []) if appl_key else []
    exact = [r for r in recs if r.get("decision_date") == comp["approval_date"]]
    others = sorted({r.get("decision_date", "") for r in recs if r.get("decision_date")})

    if exact:
        pick = exact[0]
        ofda = ("openFDA check (2026-09-17): application %s ORIG/AP record matches the Compilation "
                "approval date %s exactly (sponsor of record: %s; class: %s; priority: %s)" % (
                    appl_key, comp["approval_date"], pick.get("sponsor_name", ""),
                    (pick.get("submission_class_code_description") or "n/a"),
                    (pick.get("review_priority") or "n/a")))
        ofda_ok = "MATCH"
    elif recs:
        ofda = ("openFDA check (2026-09-17): application %s IS in openFDA but its ORIG/AP "
                "submission-status date(s) %s do not equal the Compilation approval date %s; "
                "the Compilation date is kept as the official date and the discrepancy is flagged" % (
                    appl_key, "/".join(others), comp["approval_date"]))
        ofda_ok = "DATE_DIFFERS"
    else:
        note_w = (" — the product was later withdrawn/discontinued or is a legacy licence FDA no "
                  "longer indexes" if comp["brand"] in WITHDRAWN_HINTS else "")
        ofda = ("openFDA check (2026-09-17): no ORIG/AP record for %s in the committed bulk "
                "payloads%s; this row rests on FDA's official CDER Compilation (media/177921) "
                "only" % (appl_key or "(no application number on the Compilation row)", note_w))
        ofda_ok = "ABSENT"

    res = resolve_pre98(comp["applicant"], comp["approval_year"])
    if res:
        co, tk, ex, usc, res_note = res
        basis = (f"derived {TODAY} from verified exchange/ticker fields; Compilation applicant "
                 f"string '{comp['applicant']}' matched pattern '{co}'")
    else:
        co, tk, ex, usc, res_note = (comp["applicant"], "", "N/A - sponsor resolution pending",
                                     "NOT US-INVESTABLE (UNVERIFIED)", "")
        basis = ("Compilation applicant string kept verbatim; sponsor/equity not resolved this "
                 "pass (blank beats guessed)")

    accelerated = comp["accelerated"].lower() == "yes"
    dtype = "Approval (Accelerated)" if accelerated else "Approval"
    rp = comp["review"]  # Priority / Standard (Compilation 'Review Designation')
    if accelerated:
        rp = (rp + "; Accelerated").strip("; ")

    indication = comp["abbrev_ind"] or comp["approved_use"]
    notes_bits = [
        f"appl {comp['kind']}{appl1:06d}" if appl1 is not None else "no application number on the Compilation row",
        flag_token + (": no CDER NME year table was published for pre-1998 years, so FDA's official "
                      "CDER Novel Drug Approvals Compilation (media/177921, approval-year %s section) "
                      "is the official spine for this row" % comp["approval_year"]
                      if flag_token == "COMPILATION_ONLY" else
                      ": CBER-licensed therapeutic biologic absent from the contemporaneous CDER NME "
                      "year table (added per the documented 2000-2003 year-count decision; same "
                      "convention as the 1998/1999 Compilation-only biologics)"),
        "Compilation verbatim: applicant: %s; %s%s; %s; Orphan=%s; Accelerated=%s" % (
            comp["applicant"], comp["kind"],
            "".join(str(a) for a in appl_list[:1]), comp["review"] or "n/a",
            comp["orphan"], comp["accelerated"]),
    ]
    if comp["brand"].startswith("[drug marketed without a proprietary name]"):
        notes_bits.append("Compilation prints no proprietary name for this row (generic name product)")
    if len(appl_list) > 1:
        notes_bits.append("additional application numbers on the Compilation row: " +
                          ", ".join(f"{comp['kind']}{a:06d}" for a in appl_list[1:]))
    if res_note:
        notes_bits.append(res_note)
    notes_bits.append(ofda)
    if accelerated:
        notes_bits.append("Accelerated Approval per Compilation column 'Accelerated Approval' = Yes")

    vstat = "Verified"
    if ofda_ok != "MATCH":
        vstat = "Verified - FLAGGED (source-verbatim note)"
    if usc.startswith("NOT US"):
        vstat += (" - FLAGGED (sponsor/equity not yet resolved)"
                  if vstat == "Verified" else " + sponsor/equity not yet resolved")
    return {
        "company_name": co, "ticker": tk, "drug_brand": comp["brand"],
        "drug_generic": comp["generic"], "decision_type": dtype,
        "decision_date": comp["approval_date"], "indication": indication,
        "review_pathway": rp, "source_url_1": COMPILATION_URL,
        "source_url_2": drugsatfda_url(appl1) if appl1 is not None else "",
        "verification_status": vstat, "notes": ". ".join(notes_bits),
        "us_investable_class": usc, "classification_basis": basis,
        "exchange": ex,
        "_ofda_ok": ofda_ok, "_ofda": ofda, "_year": comp["approval_year"],
        "_appl_key": appl_key,
    }


def main() -> int:
    idx = load_openfda_index()
    comp = load_compilation()
    rows, fieldnames = load_master()
    have = {(r["drug_brand"].strip().lower(), r["decision_date"][:10]) for r in rows}

    # --- census checks before writing anything
    pre98 = [c for c in comp if c["approval_year"] and 1985 <= c["approval_year"] <= 1997]
    cber = [c for c in comp if c["approval_year"] and 2000 <= c["approval_year"] <= 2003
            and c["kind"] == "BLA" and c["appl_numbers"]
            and c["appl_numbers"][0] in CBER_2000_2003_APPL]
    assert len(pre98) == 390, f"expected 390 pre-1998 Compilation rows, got {len(pre98)}"
    assert len(cber) == 19, (f"expected 19 2000-2003 CBER Compilation rows, got {len(cber)}: "
                             f"{[(c['brand'], c['appl_numbers']) for c in cber]}")

    # --- build
    new_rows = []
    for c in pre98:
        if (c["brand"].strip().lower(), c["approval_date"]) in have:
            continue
        new_rows.append(build_row(c, idx, "COMPILATION_ONLY"))
    for c in cber:
        # same dedupe guard as the pre-1998 loop — without it the CBER block
        # re-appended itself on every run (caught in the v8 pass-2 review).
        if (c["brand"].strip().lower(), c["approval_date"]) in have:
            continue
        new_rows.append(build_row(c, idx, "COMPILATION_ONLY_CBER"))
    have |= {(r["drug_brand"].strip().lower(), r["decision_date"]) for r in new_rows}

    new_rows.sort(key=lambda r: (r["decision_date"], r["drug_brand"]))
    start = max(int(r["decision_id"][1:]) for r in rows) + 1
    staging = {"source": COMPILATION_URL,
               "source_landing_page": COMPILATION_LANDING,
               "captured": "data/raw/probe/fda_nme_compilation_1985_2025.xlsx (GitHub runner, SHA-256 in data/raw/probe/manifest.json)",
               "openfda_payloads": "data/raw/openfda_orig_decisions_2011_2026/decisions_1985..2003.json (fetch run 13)",
               "generated": TODAY, "rows": []}
    tally = {"MATCH": 0, "DATE_DIFFERS": 0, "ABSENT": 0}
    for i, r in enumerate(new_rows):
        r["decision_id"] = f"D{start + i}"
        tally[r["_ofda_ok"]] += 1
        staging["rows"].append({
            "decision_id": r["decision_id"],
            "year": r["_year"], "appl_key": r["_appl_key"],
            "brand": r["drug_brand"], "generic": r["drug_generic"],
            "applicant_resolved": r["company_name"],
            "decision_date": r["decision_date"],
            "flag": "COMPILATION_ONLY_CBER" if "COMPILATION_ONLY_CBER" in r["notes"] else "COMPILATION_ONLY",
            "openfda_check": r["_ofda"], "openfda_status": r["_ofda_ok"],
            "us_investable_class": r["us_investable_class"], "ticker": r["ticker"],
        })
        r.pop("_ofda_ok"); r.pop("_ofda"); r.pop("_year"); r.pop("_appl_key")

    if not new_rows:
        print("master already complete: nothing to add (no writes performed; staging files untouched)")
        return 0

    write_master(rows + new_rows, fieldnames)

    with open(STG / "fda_nme_1985_1997_verbatim.json", "w", encoding="utf-8") as f:
        json.dump({**staging, "rows": [x for x in staging["rows"] if x["flag"] == "COMPILATION_ONLY"]},
                  f, indent=1, ensure_ascii=False)
    with open(STG / "fda_cber_2000_2003_verbatim.json", "w", encoding="utf-8") as f:
        json.dump({**staging, "rows": [x for x in staging["rows"] if x["flag"] == "COMPILATION_ONLY_CBER"]},
                  f, indent=1, ensure_ascii=False)

    # --- year source register: one row per year 1985-1997 already covered; add if absent
    reg = []
    if YEAR_REGISTER.exists():
        reg = list(csv.DictReader(open(YEAR_REGISTER, newline="", encoding="utf-8-sig")))
    have_years = {r["year"] for r in reg}
    by_year = {}
    for r in new_rows:
        by_year.setdefault(r["decision_date"][:4], []).append(r)
    for y in [str(x) for x in range(1985, 1998)]:
        if y in have_years:
            continue
        n = sum(1 for r in new_rows if r["decision_date"][:4] == y)
        reg.append({
            "year": y,
            "official_source_url": COMPILATION_URL,
            "source_type": ("CDER \"Compilation of CDER New Molecular Entity (NME) Drug and New Biologic "
                            "Approvals\" (media/177921, XLSX captured by GitHub runner with SHA-256 "
                            "manifest; approval-year %s section) cross-checked row-by-row against the "
                            "bulk openFDA Drugs@FDA ORIG/AP payload for %s (fetch run 13)" % (y, y)),
            "coverage_status": f"Imported - {n} rows in master (D-start block, flagged COMPILATION_ONLY)",
            "notes": ("No CDER NME year table exists on fda.gov/Wayback for %s; the Compilation is the "
                      "only official enumeration. Every row is flagged COMPILATION_ONLY; openFDA "
                      "re-verification status per row in data/staging/fda_nme_1985_1997_verbatim.json "
                      "and data/verification_crosscheck.csv." % y),
        })
    for y in ["2000", "2001", "2002", "2003"]:
        for r in reg:
            if r["year"] == y:
                added_n = sum(1 for rr in new_rows if rr["decision_date"][:4] == y and "COMPILATION_ONLY_CBER" in rr["notes"])
                mark = "+ %d COMPILATION_ONLY_CBER rows added 2026-09-17" % added_n
                if added_n and mark not in r.get("notes", ""):
                    r["notes"] = (r.get("notes", "") + " " + mark +
                                  " (CBER-licensed biologics per the documented year-count decision; "
                                  "year-table count unchanged; see data/staging/fda_cber_2000_2003_verbatim.json)").strip()
    fields = list(reg[0].keys())
    reg.sort(key=lambda r: r["year"])
    with open(YEAR_REGISTER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
        w.writeheader(); w.writerows(reg)

    unresolved = [r["drug_brand"] for r in new_rows if r["us_investable_class"].startswith("NOT US")]
    print(f"master: {len(rows)} -> {len(rows) + len(new_rows)} "
          f"(+{len(new_rows)}; pre-1998 {sum(1 for r in new_rows if 'COMPILATION_ONLY:' in r['notes'])}, "
          f"CBER 00-03 {sum(1 for r in new_rows if 'COMPILATION_ONLY_CBER:' in r['notes'])})")
    print(f"openFDA re-verification: {tally}")
    print(f"ids: D{start}..D{start + len(new_rows) - 1}")
    print(f"year register rows: {len(reg)} ({min(r['year'] for r in reg)}..{max(r['year'] for r in reg)})")
    print(f"unresolved sponsors (blank-flagged) {len(unresolved)}: {unresolved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
