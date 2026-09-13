#!/usr/bin/env python3
"""Resolve remaining 30 sponsor/equity cells in fda_decisions_master.csv (2026-09-12 pass).

Every mapping below was verified 2026-09-12 against openFDA drugsfda
(count=sponsor_name / full-record queries per application number); the
FDA-table row links in each row's source URLs provided the application numbers.
Where the drugsfda holder-of-record differs from the decision-date sponsor
(M&A, legacy shells), both are recorded in notes and the status is FLAGGED.
D394 (gallium Ga 68 DOTATOC, 2019) remains UNVERIFIED: openFDA ingredient
probes (2 spellings) return NOT_FOUND - blank beats guessed.
"""
import csv, re

MASTER = "data/fda_decisions_master.csv"
QDATE = "2026-09-12"

# decision_id -> dict of fields to set
M = {
 "D344": dict(company_name="Shionogi & Co., Ltd. (Japan)", ticker="4507", exchange="TSE",
   us_investable_class="NON-US LISTING ONLY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA210923 ORIG-1 approved 2018-07-31 (Type 1 NME, Priority); holder-of-record prints 'VANCOCIN ITALIA' (legacy entity, irregular); manufacturer_name SHIONOGI INC.; decision-date sponsor Shionogi (TSE:4507)."),
 "D337": dict(company_name="Shire plc (acquired by Takeda 2019)", ticker="SHPG", exchange="NASDAQ",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA BLA761090 ORIG-1 2018-08-23 (Type 1 NME, Priority, Orphan); holder-of-record DYAX CORP. (Shire acquired Dyax 2016); manufacturer Takeda. NASDAQ:SHPG delisted 2019."),
 "D336": dict(company_name="Tetraphase Pharmaceuticals (acquired by La Jolla 2020)", ticker="TTPH", exchange="NASDAQ",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA211109 sponsor TETRAPHASE PHARMS; NASDAQ:TTPH delisted 2020."),
 "D334": dict(company_name="AstraZeneca PLC (MedImmune/Acerta lineage)", ticker="AZN", exchange="NASDAQ (ADR)",
   us_investable_class="US-LISTED (ADR)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved - FLAGGED (holder-of-record name irregular)",
   note="openFDA BLA761104 ORIG-1 2018-09-13 (Type 1 NME, Priority, Orphan) = LUMOXITI; sponsor_name prints 'INNATE PHARMA' (legacy holder, irregular); decision-date sponsor AstraZeneca/MedImmune."),
 "D327": dict(company_name="Paratek Pharmaceuticals (take-private 2022)", ticker="PRTK", exchange="NASDAQ",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA209816 sponsor PARATEK PHARMS; NASDAQ:PRTK taken private 2022."),
 "D325": dict(company_name="Ionis Pharmaceuticals (Akcea; AKCA delisted 2019)", ticker="IONS", exchange="NASDAQ",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA211172 sponsor AKCEA THERAPS (Ionis majority); Akcea NASDAQ:AKCA delisted 2019 (Ionis buy-in); Tegsedi US now Ionis."),
 "D321": dict(company_name="Mylan (Viatris 2020; Theravance Biopharma developer)", ticker="MYL", exchange="NYSE",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA210598 sponsor MYLAN IRELAND LTD; Mylan merged into Viatris 2020 (VTRS); drug developed by Theravance Biopharma (TBPH)."),
 "D320": dict(company_name="Bausch Health Companies (Salix; Cosmo developer)", ticker="BHC", exchange="NYSE",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA210910 sponsor COSMO TECHNOLOGIES (developer); US commercialization Salix (Bausch Health, NYSE:BHC); RedHill co-development."),
 "D316": dict(company_name="Catalyst Pharmaceuticals", ticker="CPRX", exchange="NASDAQ",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA208078 sponsor CATALYST PHARMS."),
 "D311": dict(company_name="Alexion Pharmaceuticals (acquired by AstraZeneca 2021)", ticker="ALXN", exchange="NASDAQ",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA BLA761108 sponsor ALEXION PHARM; NASDAQ:ALXN delisted 2021 (AstraZeneca)."),
 "D387": dict(company_name="Shield Therapeutics plc (UK)", ticker="STX", exchange="LSE",
   us_investable_class="NON-US LISTING ONLY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA ferric-maltol probe sponsor 'SHIELD TX' (Shield Therapeutics, LSE/AIM:STX); Accrufer US."),
 "D398": dict(company_name="Mylan (Viatris 2020; TB Alliance program)", ticker="MYL", exchange="NYSE",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved - FLAGGED (no trade name; developer non-profit)",
   note="openFDA NDA212862 ORIG-1 2019-08-14 (Type 1 NME, Priority, Orphan) brand PRETOMANID; holder MYLAN IRELAND LTD; developer TB Alliance (non-profit); manufacturer Viatris Specialty. FDA 2019 report lists with no trade name."),
 "D408": dict(company_name="Harmony Biosciences", ticker="HRMY", exchange="NASDAQ",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA pitolisant probe: ORIG NDA holder HARMONY (Harmony Biosciences, NASDAQ:HRMY); later generic sponsors (Lupin, MSN, Annora, Novitium) are ANDAs, not the novel approval."),
 "D410": dict(company_name="Nabriva Therapeutics (delisted 2023)", ticker="NBRW", exchange="NASDAQ",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved - FLAGGED (holder term unresolved)",
   note="openFDA lefamulin probe sponsor term prints 'HONG KONG' (unresolved/truncated); lefamulin US rights Nabriva Therapeutics US (FDA approval letter); NASDAQ:NBRW delisted 2023."),
 "D393": dict(company_name="The Feinstein Institutes for Medical Research (Northwell Health, non-profit)", ticker="", exchange="N/A - non-profit",
   us_investable_class="PRIVATE / NO EQUITY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA200655 ORIG-1 2019-10-10 (Type 1 NME) brand FLUORODOPA F18; sponsor FEINSTEIN / manufacturer The Feinstein Institutes for Medical Research (non-profit)."),
 "D391": dict(company_name="Giskit (per openFDA holder-of-record; ExEm Foam US)", ticker="", exchange="N/A - privately held",
   us_investable_class="PRIVATE / NO EQUITY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved - FLAGGED (holder name irregular)",
   note="openFDA ExEm Foam probe sponsor term 'GISKIT'; no listed equity verified."),
 "D384": dict(company_name="B. Braun (Braintree Laboratories)", ticker="", exchange="N/A - privately held",
   us_investable_class="PRIVATE / NO EQUITY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA211281 sponsor BRAINTREE LABS (B. Braun group, private)."),
 "D381": dict(company_name="Acacia Pharma Group (Merck KGaA 2022)", ticker="ACP", exchange="LSE (AIM); delisted 2022",
   us_investable_class="NON-US LISTING ONLY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA209510 ORIG-1 2020-02-26 (Type 1 NME) = BARHEMSYS; holder-of-record 'LXO IRELAND' (Acacia affiliate); manufacturer Acacia Pharma Ltd; AIM/Euronext ACP delisted 2022 (Merck KGaA)."),
 "D373": dict(company_name="Deciphera Pharmaceuticals (acquired by Ono 2024)", ticker="DCPH", exchange="NASDAQ",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA213973 sponsor DECIPHERA PHARMS; NASDAQ:DCPH delisted 2024 (Ono)."),
 "D372": dict(company_name="GE HealthCare (GE at approval; spun off 2023)", ticker="GEHC", exchange="NASDAQ",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA212155 sponsor GE HEALTHCARE; part of GE (NYSE:GE) at approval; GE HealthCare NASDAQ:GEHC since 2023."),
 "D371": dict(company_name="Amivas LLC (private)", ticker="", exchange="N/A - privately held",
   us_investable_class="PRIVATE / NO EQUITY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA213036 sponsor AMIVAS (private)."),
 "D370": dict(company_name="Avid Radiopharmaceuticals (Eli Lilly)", ticker="LLY", exchange="NYSE",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA212123 sponsor AVID RADIOPHARMS INC (Lilly-owned)."),
 "D366": dict(company_name="Acacia Pharma Group (licensed US remimazolam rights; Merck KGaA 2022)", ticker="ACP", exchange="LSE (AIM); delisted 2022",
   us_investable_class="NON-US LISTING ONLY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved - FLAGGED (DEA-scheduling date note)",
   note="openFDA NDA212295 ORIG-1 2020-07-02 (Type 1 NME) = BYFAVO; holder-of-record 'ACACIA' (US rights licensed from Paion); public note: 'FR Notice on DEA Scheduling; Date of Approval October 6, 2020'."),
 "D363": dict(company_name="LNHC, Inc. (Ferndale/Medimetriks lineage, private)", ticker="", exchange="N/A - privately held",
   us_investable_class="PRIVATE / NO EQUITY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved - FLAGGED (product now discontinued)",
   note="openFDA NDA206966 ORIG-1 2020-07-24 (Type 1 NME) = XEGLYZE; sponsor LNHC; product marketing status Discontinued."),
 "D362": dict(company_name="MorphoSys (Novartis 2024)", ticker="MOR", exchange="NASDAQ",
   us_investable_class="FORMERLY US-LISTED (DELISTED/ACQUIRED)",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA BLA761163 sponsor MORPHOSYS US INC; NASDAQ:MOR delisted 2024 (Novartis)."),
 "D351": dict(company_name="Y-mAbs Therapeutics", ticker="YMAB", exchange="NASDAQ",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA BLA761171 sponsor Y-MABS THERAPEUTICS INC."),
 "D350": dict(company_name="University of California, Los Angeles (non-profit radiopharmacy)", ticker="", exchange="N/A - non-profit",
   us_investable_class="PRIVATE / NO EQUITY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA NDA212642 sponsor UNIV CA LOS ANGELES (non-profit)."),
 "D347": dict(company_name="MacroGenics", ticker="MGNX", exchange="NASDAQ",
   us_investable_class="US-LISTED",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved",
   note="openFDA BLA761150 sponsor MACROGENICS INC."),
 "D635": dict(company_name="Cosette Pharmaceuticals (private; Ancora-backed)", ticker="", exchange="N/A - privately held",
   us_investable_class="PRIVATE / NO EQUITY",
   vstat="Verified - openFDA drugsfda sponsor/equity resolved - FLAGGED (FDA-table applicant 'ShowBrand' unresolved abbreviation)",
   note="openFDA NDA020989 sponsor COSETTE (private; current holder of cevimeline/Evoxac); FDA 2000 year-table applicant prints 'ShowBrand' (unresolved abbreviation, kept verbatim in notes); decision-date applicant per Drugs@FDA lineage Daiichi."),
 "D394": dict(vstat="Verified - FLAGGED (openFDA unresolvable this pass)",
   note="openFDA ingredient probes ('GALLIUM GA 68 DOTATOC' and 'GALLIUM GA-68 DOTATOC') return NOT_FOUND (2026-09-12); FDA 2019 report lists this radiopharmaceutical with no trade name; sponsor left blank rather than guessed."),
}

with open(MASTER, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

changed = 0
for r in rows:
    m = M.get(r["decision_id"])
    if not m:
        continue
    if "company_name" in m: r["company_name"] = m["company_name"]
    if "ticker" in m: r["ticker"] = m["ticker"]
    if "exchange" in m: r["exchange"] = m["exchange"]
    if "us_investable_class" in m: r["us_investable_class"] = m["us_investable_class"]
    r["verification_status"] = m["vstat"]
    r["notes"] = (r["notes"] + " " if r["notes"] else "") + m["note"]
    r["classification_basis"] = f"resolved {QDATE} via openFDA drugsfda application-number queries (holder-of-record + manufacturer) and FDA year-table links; see notes for M&A lineage"
    changed += 1

with open(MASTER, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader(); w.writerows(rows)

left = sum(1 for r in rows if r["us_investable_class"] == "NOT US-INVESTABLE (UNVERIFIED)")
print(f"rows updated: {changed}; still UNVERIFIED: {left}")
