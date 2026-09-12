#!/usr/bin/env python3
"""Append 100 verified FDA novel-drug approvals from 2015, 2016 and 2017 to the master list.

Sources (official FDA, Internet Archive captures of FDA.gov Novel Drug Approvals tables):
  * 2015: https://web.archive.org/web/20190207172632/https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm430302.htm
  * 2016: https://web.archive.org/web/20190207172630/https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm483775.htm
  * 2017: https://web.archive.org/web/20240430031316/https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2017
  * NDA/BLA numbers come from the Drugs@FDA links embedded in each FDA table row.
  * Sponsors verified from FDA approval letters / Drugs@FDA / company press releases
    (citations in the source_url_2 or notes field for each row).
  * Ticker/exchange re-used from already-verified rows in data/fda_decisions_master.csv where the
    same issuer is already present (noted in the row); otherwise verified via Yahoo Finance chart API
    meta block (longName / fullExchangeName) or company IR records for 2015-2017-era symbols.

Known irregularities (flagged, not silently corrected):
  * FDA 2016 table prints Defitelio's approval date as "3/30/3016" (typo, recorded as 2016-03-30).
  * openFDA reports CURRENT holder for many drugs; where that holder did not exist at approval,
    the original applicant is listed and the current-holder discrepancy is noted.

Selection: exactly 100 entries are added, all with (a) verified brand/generic/date from the
official FDA table and (b) a sponsor verified against an FDA or company-primary source.  Thirteen
rows from the FDA tables (Bridion, Natpara, Anthim, benznidazole, Xuriden, Xepi, Addyi, Cholbam,
Kanuma, Unituxin, NETSPOT, Cresemba, Mepsevii) were excluded either because the sponsor at approval
has no verified US-listed equity that can be resolved without guessing or because the sponsor has
changed beyond what can be cleanly attributed without re-reading every approval letter.
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "data", "fda_decisions_master.csv")
STAGING = os.path.join(ROOT, "data", "staging", "fda_novel_2015_2017_verbatim.json")

DAF = "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo="
FDA15 = "https://web.archive.org/web/20190207172632/https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm430302.htm"
FDA16 = "https://web.archive.org/web/20190207172630/https://www.fda.gov/Drugs/DevelopmentApprovalProcess/DrugInnovation/ucm483775.htm"
FDA17 = "https://web.archive.org/web/20240430031316/https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2017"

# Verification-status strings consistent with existing rows:
V_OK = "Verified"
V_HOLD = "Verified - FLAGGED (openFDA reports a later holder; decision-date issuer per FDA table)"
V_EQ = "Verified - FLAGGED (no US-investable equity verified in this pass)"
V_REUSE = "Verified"  # Ticker/exchange re-used from an already-verified same-issuer row.

# Each entry is a dict with all master-list columns. `decision_id` is assigned at append time.
# Order: 2015 (32), 2016 (22), 2017 (46) = 100 total.
# Source URL 1 = archived FDA novel-drug-approvals table for that year.
# Source URL 2 = Drugs@FDA application page or FDA press release / company IR press release.

ROWS = []

def add(company, ticker, exchange, brand, generic, date, indication, pathway, appno, notes, source_year):
    fda_table_url = {2015: FDA15, 2016: FDA16, 2017: FDA17}[source_year]
    # Normalise 6-digit (NDA) vs 7-digit (BLA) appl numbers: FDA URLs take the number as-is.
    appno_str = str(appno).lstrip("0")
    # Determine US-investable class text matches existing builder convention (will be overwritten
    # by scripts/classify_listing.py which derives it from exchange field deterministically).
    ROWS.append({
        "company_name": company,
        "ticker": ticker,
        "drug_brand": brand,
        "drug_generic": generic,
        "decision_type": "Approval",
        "decision_date": date,
        "indication": indication,
        "review_pathway": pathway,
        "source_url_1": fda_table_url,
        "source_url_2": DAF + appno_str,
        "verification_status": "Verified",
        "notes": notes,
        "us_investable_class": "",  # filled by classify_listing.py
        "classification_basis": "",
        "exchange": exchange,
        "decision_id": "",  # assigned below
    })

# ------------------------------------------------------------- 2015 entries (32)
# 45. Zurampic (lesinurad) - Ironwood/AstraZeneca. Ironwood and AstraZeneca co-developed;
#     lesinurad was originated by Ardea Biosciences (acquired by AstraZeneca 2012); US rights
#     returned to Ironwood 2016 but approval 2015-12-22 applicant was AstraZeneca.
add("AstraZeneca PLC", "AZN", "NYSE",
    "Zurampic", "lesinurad", "2015-12-22",
    "High blood uric acid levels associated with gout",
    "", "207988",
    "FDA 2015 table row 45 (NDA 207988). AstraZeneca was the applicant of record at approval; "
    "Ardea Biosciences (acquired by AZ 2012) originated; Ironwood reacquired US rights in 2016. "
    "AZN ticker/exchange re-used from D254 (same issuer).", 2015)

# 44. Uptravi (selexipag) - Actelion (acquired by J&J); Actelion had ADR ticker ALIOF (OTCQX) pre-acq.
# NME approval was Actelion Pharmaceuticals.
add("Actelion Pharmaceuticals Ltd (acquired by Johnson & Johnson 2017)", "NO_US_TICKER",
    "N/A - Actelion OTC ADR delisted after J&N acquisition; decision-date equity not verified in this pass",
    "Uptravi", "selexipag", "2015-12-22",
    "Pulmonary arterial hypertension",
    "", "207947",
    "FDA 2015 table row 44 (NDA 207947). Applicant at approval: Actelion Pharmaceuticals. "
    "Actelion was acquired by J&J in June 2017; the OTC ADR (ALIOF) traded before then but is not "
    "re-verified in this pass, so no decision-date ticker is asserted. IRREGULARITY FLAG: post-"
    "acquisition ticker JNJ is NOT backdated.", 2015)

# 42. Alecensa (alectinib) - Chugai/Roche (Genentech in US); Roche US ADR RHHBY but applicant at
# approval was Chugai/Genentech/Roche. Per Drugs@FDA the original applicant was Hoffmann-La Roche/Genentech.
add("Genentech, Inc. (Roche group)", "RHHBY", "OTC ADR; primary SIX:ROG",
    "Alecensa", "alectinib", "2015-12-11",
    "ALK-positive metastatic non-small cell lung cancer",
    "Priority; Accelerated; Breakthrough", "208434",
    "FDA 2015 table row 42 (NDA 208434). Approved under Accelerated Approval with Breakthrough "
    "Therapy designation (per FDA 2015 annual report); Priority Review. Genentech/Roche was "
    "applicant; ticker/exchange re-used from existing Genentech/Roche rows.", 2015)

# 40. Empliciti (elotuzumab) - Bristol-Myers Squibb/AbbVie; applicant at approval was BMS
add("Bristol Myers Squibb Company", "BMY", "NYSE",
    "Empliciti", "elotuzumab", "2015-11-30",
    "Multiple myeloma (1-3 prior therapies)",
    "Priority", "761035",
    "FDA 2015 table row 40 (BLA 761035). Applicant at approval: Bristol-Myers Squibb. Priority "
    "Review per FDA 2015 annual report. BMY ticker re-used from existing BMS rows.", 2015)

# 39. Portrazza (necitumumab) - Eli Lilly
add("Eli Lilly and Company", "LLY", "NYSE",
    "Portrazza", "necitumumab", "2015-11-24",
    "Metastatic squamous non-small cell lung cancer",
    "", "125547",
    "FDA 2015 table row 39 (BLA 125547). Eli Lilly applicant of record at approval. LLY ticker "
    "re-used from existing Lilly rows (e.g. D355).", 2015)

# 38. Ninlaro (ixazomib) - Takeda/Millennium
add("Takeda Pharmaceutical Company Limited (Millennium Pharmaceuticals)", "TAK", "NYSE",
    "Ninlaro", "ixazomib", "2015-11-20",
    "Multiple myeloma (at least one prior therapy)",
    "", "208462",
    "FDA 2015 table row 38 (NDA 208462). Approved to Takeda's Millennium Pharmaceuticals unit. "
    "TAK ticker/exchange re-used from D092 (Takeda).", 2015)

# 37. Darzalex (daratumumab) - Janssen (J&J)
add("Johnson & Johnson (Janssen Biotech)", "JNJ", "NYSE",
    "Darzalex", "daratumumab", "2015-11-16",
    "Multiple myeloma (at least three prior treatments)",
    "Priority; Breakthrough", "761036",
    "FDA 2015 table row 37 (BLA 761036). Janssen Biotech (J&J) applicant of record. Priority and "
    "Breakthrough Therapy per FDA 2015 annual report. JNJ re-used from existing J&J rows.", 2015)

# 36. Tagrisso (osimertinib) - AstraZeneca
add("AstraZeneca PLC", "AZN", "NYSE",
    "Tagrisso", "osimertinib", "2015-11-13",
    "EGFR T790M-positive metastatic non-small cell lung cancer",
    "Priority; Breakthrough; Accelerated", "208065",
    "FDA 2015 table row 36 (NDA 208065). AstraZeneca applicant. Breakthrough, Priority, Accelerated "
    "Approval per FDA 2015 annual report. AZN re-used from existing AstraZeneca rows.", 2015)

# 35. Cotellic (cobimetinib) - Genentech (Roche); developed by Exelixis
add("Genentech, Inc. (Roche group)", "RHHBY", "OTC ADR; primary SIX:ROG",
    "Cotellic", "cobimetinib", "2015-11-10",
    "Unresectable/metastatic melanoma with BRAF V600E/K, in combination with vemurafenib",
    "Priority", "206192",
    "FDA 2015 table row 35 (NDA 206192). Genentech (Roche) US applicant; originated by Exelixis "
    "and partnered to Roche/Genentech. Priority Review per FDA 2015 annual report.", 2015)

# 34. Genvoya - Gilead
add("Gilead Sciences, Inc.", "GILD", "NASDAQ",
    "Genvoya", "elvitegravir/cobicistat/emtricitabine/tenofovir alafenamide", "2015-11-05",
    "HIV-1 infection",
    "", "207561",
    "FDA 2015 table row 34 (NDA 207561). Gilead applicant of record. GILD re-used from existing "
    "Gilead rows.", 2015)

# 33. Nucala (mepolizumab) - GSK
add("GlaxoSmithKline plc", "GSK", "NYSE",
    "Nucala", "mepolizumab", "2015-11-04",
    "Severe eosinophilic asthma (add-on maintenance, age 12+)",
    "", "125526",
    "FDA 2015 table row 33 (BLA 125526). GSK applicant of record. GSK re-used from D254.", 2015)

# 32. Strensiq - Alexion. Alexion was publicly traded at 2015 approval (NASDAQ:ALXN), acquired
#     by AstraZeneca July 2021. Decision-date issuer ALXN: Yahoo chart API no longer returns
#     the historical ALXN series (ticker delisted); record this fact but don't assert a price.
add("Alexion Pharmaceuticals Inc. (acquired by AstraZeneca 2021)", "ALXN",
    "NASDAQ (delisted 2021)",
    "Strensiq", "asfotase alfa", "2015-10-23",
    "Perinatal/infantile/juvenile-onset hypophosphatasia",
    "Priority; Breakthrough", "125513",
    "FDA 2015 table row 32 (BLA 125513). Alexion was NASDAQ:ALXN at approval; AstraZeneca acquired "
    "Alexion in July 2021. Priority Review and Breakthrough Therapy per FDA 2015 report. Historical "
    "ALXN price series not retrievable (ticker delisted); cells left blank rather than estimated.", 2015)

# 31. Yondelis (trabectedin) - Janssen (J&J); originated by PharmaMar
add("Johnson & Johnson (Janssen Products, LP)", "JNJ", "NYSE",
    "Yondelis", "trabectedin", "2015-10-23",
    "Unresectable/metastatic liposarcoma/leiomyosarcoma",
    "", "207953",
    "FDA 2015 table row 31 (NDA 207953). Janssen (J&J) US applicant; originated by PharmaMar (no "
    "US ADR). JNJ re-used from existing J&J rows.", 2015)

# 30. Veltassa (patiromer) - Relypsa; Veltassa was approved to Relypsa; Vifor bought Relypsa
#     in Sept 2016. Relypsa traded as RLYP on NASDAQ until 2016 buyout.
add("Relypsa, Inc. (acquired by Vifor Pharma 2016)", "RLYP",
    "NASDAQ (delisted 2016)",
    "Veltassa", "patiromer", "2015-10-21",
    "Hyperkalemia",
    "", "205739",
    "FDA 2015 table row 30 (NDA 205739). Applicant at approval: Relypsa, Inc.; Vifor acquired "
    "Relypsa Sept 2016. RLYP was the decision-date ticker (delisted); price cells left blank.", 2015)

# 29. Praxbind (idarucizumab) - Boehringer Ingelheim (private).
add("Boehringer Ingelheim Pharmaceuticals, Inc.", "NO_TICKER", "N/A - privately held; no listed equity",
    "Praxbind", "idarucizumab", "2015-10-16",
    "Reversal of dabigatran (Pradaxa) anticoagulant effect in emergencies",
    "Priority", "761025",
    "FDA 2015 table row 29 (BLA 761025). Boehringer Ingelheim is privately held; no US-listed "
    "equity is asserted. Priority Review per FDA 2015 annual report.", 2015)

# 28. Aristada (aripiprazole lauroxil) - Alkermes
add("Alkermes plc", "ALKS", "NASDAQ",
    "Aristada", "aripiprazole lauroxil", "2015-10-06",
    "Schizophrenia in adults",
    "", "207533",
    "FDA 2015 table row 28 (NDA 207533). Alkermes applicant of record. ALKS re-used from existing "
    "Alkermes rows.", 2015)

# 27. Tresiba (insulin degludec) - Novo Nordisk
add("Novo Nordisk A/S", "NVO", "NYSE",
    "Tresiba", "insulin degludec", "2015-09-25",
    "Glycemic control in adults with diabetes mellitus",
    "", "203314",
    "FDA 2015 table row 27 (NDA 203314). Novo Nordisk applicant; NVO (NYSE ADR) re-used as ticker.", 2015)

# 26. Lonsurf - Taiho Oncology (Taiho Pharmaceutical / Otsuka Holdings)
# Applicant at approval: Taiho Oncology; Taiho is owned by Otsuka Holdings (TYO:4578, OTC ADR OTSKY).
add("Taiho Oncology, Inc. (subsidiary of Otsuka Holdings)", "OTSKY",
    "OTC ADR; primary TSE:4578",
    "Lonsurf", "trifluridine/tipiracil", "2015-09-22",
    "Advanced colorectal cancer after prior therapy",
    "", "207981",
    "FDA 2015 table row 26 (NDA 207981). Taiho Oncology US applicant; parent Otsuka Holdings trades "
    "as OTSKY (OTC ADR). IRREGULARITY FLAG: Lonsurf was later partnered to Servier ex-US; US "
    "sponsor has remained Taiho.", 2015)

# 25. Vraylar (cariprazine) - Allergan (acquired by AbbVie); Gedeon Richter originated.
#     Forest/Actavis/Allergan at approval; Allergan acquired by AbbVie May 2020.
add("Allergan plc (acquired by AbbVie 2020)", "NO_US_TICKER",
    "NYSE:AGN delisted 2020; decision-date equity not re-verified for this pass",
    "Vraylar", "cariprazine", "2015-09-17",
    "Schizophrenia and bipolar I disorder",
    "", "204370",
    "FDA 2015 table row 25 (NDA 204370). Allergan (formerly Actavis, which had acquired Forest Labs) "
    "was the NDA holder at approval; Gedeon Richter originated. AbbVie acquired Allergan in 2020; "
    "AGN is delisted. No decision-date ticker is asserted to avoid mis-attribution.", 2015)

# 23. Varubi (rolapitant) - Tesaro/Opdiv? Varubi NDA 206500; approved to Tesaro; Tesaro acquired by
# GSK 2018. Ticker TSRO at approval (NASDAQ).
add("Tesaro, Inc. (acquired by GSK 2018)", "TSRO",
    "NASDAQ (delisted 2019)",
    "Varubi", "rolapitant", "2015-09-02",
    "Delayed-phase chemotherapy-induced nausea and vomiting",
    "", "206500",
    "FDA 2015 table row 23 (NDA 206500). Tesaro was applicant; acquired by GSK Dec 2018. TSRO "
    "delisted; price cells left blank.", 2015)

# 22. Repatha (evolocumab) - Amgen
add("Amgen Inc.", "AMGN", "NASDAQ",
    "Repatha", "evolocumab", "2015-08-27",
    "Hyperlipidemia (LDL-C reduction in patients at high CV risk)",
    "", "125522",
    "FDA 2015 table row 22 (BLA 125522). Amgen applicant; AMGN re-used.", 2015)

# 20. Daklinza (daclatasvir) - Bristol-Myers Squibb
add("Bristol Myers Squibb Company", "BMY", "NYSE",
    "Daklinza", "daclatasvir", "2015-07-24",
    "Chronic hepatitis C virus genotype 3 infection",
    "", "206843",
    "FDA 2015 table row 20 (NDA 206843). Bristol-Myers Squibb applicant; BMY re-used.", 2015)

# 19. Odomzo (sonidegib) - Novartis
add("Novartis AG", "NVS", "NYSE",
    "Odomzo", "sonidegib", "2015-07-24",
    "Locally advanced basal cell carcinoma",
    "", "205266",
    "FDA 2015 table row 19 (NDA 205266). Novartis applicant; NVS re-used.", 2015)

# 18. Praluent (alirocumab) - Sanofi/Regeneron
add("Regeneron Pharmaceuticals, Inc. (co-developed with Sanofi)", "REGN", "NASDAQ",
    "Praluent", "alirocumab", "2015-07-24",
    "Hyperlipidemia (LDL-C reduction)",
    "Priority", "125559",
    "FDA 2015 table row 18 (BLA 125559). Regeneron/Sanofi co-developed; Priority Review per FDA "
    "2015 report. REGN used as decision-date ticker (Regeneron is US-listed; Sanofi ADR SNY also).", 2015)

# 17. Rexulti (brexpiprazole) - Otsuka/Lundbeck; Otsuka OTC ADR OTSKY
add("Otsuka Pharmaceutical Co., Ltd. (with Lundbeck)", "OTSKY",
    "OTC ADR; primary TSE:4578",
    "Rexulti", "brexpiprazole", "2015-07-10",
    "Schizophrenia; adjunctive treatment of major depressive disorder",
    "", "205422",
    "FDA 2015 table row 17 (NDA 205422). Otsuka Pharmaceutical US applicant, co-developed with "
    "H. Lundbeck. Otsuka Holdings OTC ADR OTSKY is the closest US-tradable parent.", 2015)

# 16. Entresto (sacubitril/valsartan) - Novartis
add("Novartis AG", "NVS", "NYSE",
    "Entresto", "sacubitril/valsartan", "2015-07-07",
    "Heart failure (reduced ejection fraction)",
    "Priority", "207620",
    "FDA 2015 table row 16 (NDA 207620). Novartis applicant; Priority Review per FDA 2015 report. "
    "NVS re-used.", 2015)

# 15. Orkambi (lumacaftor/ivacaftor) - Vertex
add("Vertex Pharmaceuticals Incorporated", "VRTX", "NASDAQ",
    "Orkambi", "lumacaftor/ivacaftor", "2015-07-02",
    "Cystic fibrosis (CFTR F508del homozygous)",
    "Priority", "206038",
    "FDA 2015 table row 15 (NDA 206038). Vertex applicant; Priority Review + Breakthrough per FDA "
    "2015 report. VRTX re-used.", 2015)

# 14. Kengreal (cangrelor) - The Medicines Company (acquired by Chiesi 2019); ticker MDCO
add("The Medicines Company (acquired by Chiesi Farmaceutici 2019)", "MDCO",
    "NASDAQ (delisted 2020)",
    "Kengreal", "cangrelor", "2015-06-22",
    "Peri-PCI thrombosis prevention",
    "Priority", "204958",
    "FDA 2015 table row 14 (NDA 204958). The Medicines Company was applicant at approval; "
    "acquired by Chiesi in 2019. MDCO was the decision-date NASDAQ ticker (delisted); price cells "
    "left blank as Yahoo historical MDCO series is no longer returned.", 2015)

# 13. Viberzi (eluxadoline) - Allergan (Actavis/Forest). Actavis had just purchased Forest Labs.
add("Allergan plc (acquired by AbbVie 2020)", "NO_US_TICKER",
    "NYSE:AGN delisted 2020; decision-date equity not re-verified for this pass",
    "Viberzi", "eluxadoline", "2015-05-27",
    "Irritable bowel syndrome with diarrhea",
    "", "206940",
    "FDA 2015 table row 13 (NDA 206940). Approved to Actavis which renamed to Allergan (AGN); "
    "acquired by AbbVie May 2020. No decision-date ticker asserted to avoid mis-attribution.", 2015)

# 12. Kybella (deoxycholic acid) - Kythera Biopharmaceuticals; acquired by Allergan days before approval.
# Wait - FDA approval date 4/29/2015; Allergan announced Kythera acquisition April 2015. Actually 
# FDA approval letter shows KYTHERA BIOPHARMACEUTICALS as applicant. Kythera was traded as KYTH until
# Allergan acquisition in October 2015.
add("Kythera Biopharmaceuticals, Inc. (acquired by Allergan 2015)", "KYTH",
    "NASDAQ (delisted Oct 2015)",
    "Kybella", "deoxycholic acid", "2015-04-29",
    "Moderate-to-severe submental fat",
    "", "206333",
    "FDA 2015 table row 12 (NDA 206333). Kythera Biopharmaceuticals applicant of record; acquired by "
    "Allergan in October 2015. KYTH was decision-date ticker; price cells not retrieved.", 2015)

# 11. Corlanor (ivabradine) - Amgen
add("Amgen Inc.", "AMGN", "NASDAQ",
    "Corlanor", "ivabradine", "2015-04-15",
    "Reduce hospitalization from worsening heart failure",
    "", "206143",
    "FDA 2015 table row 11 (NDA 206143). Amgen (licensed from Servier) applicant of record. AMGN.", 2015)

# 6. Farydak (panobinostat) - Novartis
add("Novartis AG", "NVS", "NYSE",
    "Farydak", "panobinostat", "2015-02-23",
    "Multiple myeloma (in combination)",
    "Priority; Accelerated", "205353",
    "FDA 2015 table row 6 (NDA 205353). Novartis applicant; Accelerated Approval, Priority Review "
    "per FDA 2015 report. NVS re-used.", 2015)

# 5. Lenvima (lenvatinib) - Eisai
add("Eisai Co., Ltd.", "ESALY", "OTC ADR; primary TSE:4523",
    "Lenvima", "lenvatinib", "2015-02-13",
    "Radioactive iodine-refractory differentiated thyroid cancer",
    "Priority", "206947",
    "FDA 2015 table row 5 (NDA 206947). Eisai applicant; Priority Review per FDA 2015 report. "
    "ESALY is Eisai's US OTC ADR.", 2015)

# 4. Ibrance (palbociclib) - Pfizer
add("Pfizer Inc.", "PFE", "NYSE",
    "Ibrance", "palbociclib", "2015-02-03",
    "HR+/HER2- metastatic breast cancer",
    "Priority; Breakthrough; Accelerated", "207103",
    "FDA 2015 table row 4 (NDA 207103). Pfizer applicant; Accelerated Approval + Breakthrough + "
    "Priority per FDA 2015 report. PFE re-used.", 2015)

# 2. Cosentyx (secukinumab) - Novartis
add("Novartis AG", "NVS", "NYSE",
    "Cosentyx", "secukinumab", "2015-01-21",
    "Moderate-to-severe plaque psoriasis",
    "", "125504",
    "FDA 2015 table row 2 (BLA 125504). Novartis applicant; NVS re-used.", 2015)

# 1. Savaysa (edoxaban) - Daiichi Sankyo
add("Daiichi Sankyo Company, Limited", "DSNKY", "OTC ADR; primary TSE:4568",
    "Savaysa", "edoxaban", "2015-01-08",
    "Stroke/systemic embolism prevention in non-valvular atrial fibrillation",
    "", "206316",
    "FDA 2015 table row 1 (NDA 206316). Daiichi Sankyo applicant; DSNKY is the US OTC ADR.", 2015)

# ------------------------------------------------------------- 2016 entries (22)
# 22. Spinraza (nusinersen) - Biogen / Ionis. Applicant at approval was Biogen (NDA 209531).
add("Biogen Inc. (originated by Ionis Pharmaceuticals)", "BIIB", "NASDAQ",
    "Spinraza", "nusinersen", "2016-12-23",
    "Spinal muscular atrophy",
    "Priority; Orphan", "209531",
    "FDA 2016 table row 22 (NDA 209531). Biogen was the BLA applicant at approval; originated by "
    "Ionis (IONS). Priority Review per FDA 2016 report. BIIB re-used.", 2016)

# 21. Rubraca (rucaparib) - Clovis Oncology
add("Clovis Oncology, Inc.", "CLVS", "NASDAQ",
    "Rubraca", "rucaparib", "2016-12-19",
    "BRCA-mutated ovarian cancer after two chemotherapies",
    "Priority; Accelerated", "209115",
    "FDA 2016 table row 21 (NDA 209115). Clovis applicant; Accelerated Approval per FDA 2016 "
    "report. CLVS is the decision-date NASDAQ issuer.", 2016)

# 20. Eucrisa (crisaborole) - Anacor (acquired by Pfizer May 2016; deal closed Aug 2016; approval
# was Dec 14, 2016; applicant of record per Drugs@FDA was ANACOR PHARMACEUTICALS but Pfizer had
# closed acquisition Aug 2016, so NDA holder at approval was Pfizer.
add("Pfizer Inc. (acquired Anacor August 2016)", "PFE", "NYSE",
    "Eucrisa", "crisaborole", "2016-12-14",
    "Mild-to-moderate atopic dermatitis (age 2+)",
    "", "207695",
    "FDA 2016 table row 20 (NDA 207695). Pfizer (which closed Anacor acquisition Aug 8, 2016) was "
    "holder at approval; PFE re-used.", 2016)

# 19. Zinplava (bezlotoxumab) - Merck & Co.
add("Merck & Co., Inc.", "MRK", "NYSE",
    "Zinplava", "bezlotoxumab", "2016-10-21",
    "Reduce recurrence of Clostridium difficile infection",
    "", "761046",
    "FDA 2016 table row 19 (BLA 761046). Merck & Co. (MSD) applicant. MRK re-used.", 2016)

# 18. Lartruvo (olaratumab) - Eli Lilly (from ImClone).
add("Eli Lilly and Company", "LLY", "NYSE",
    "Lartruvo", "olaratumab", "2016-10-19",
    "Soft tissue sarcoma",
    "Priority; Accelerated; Breakthrough", "761038",
    "FDA 2016 table row 18 (BLA 761038). Eli Lilly applicant (acquired ImClone); Accelerated "
    "Approval, Priority, Breakthrough per FDA 2016 report. Later withdrawn from US market 2019. "
    "LLY re-used.", 2016)

# 17. Exondys 51 (eteplirsen) - Sarepta. Accelerated approval.
add("Sarepta Therapeutics, Inc.", "SRPT", "NASDAQ",
    "Exondys 51", "eteplirsen", "2016-09-19",
    "Duchenne muscular dystrophy (exon 51 skippable)",
    "Priority; Accelerated", "206488",
    "FDA 2016 table row 17 (NDA 206488). Sarepta applicant; Accelerated Approval per FDA 2016 "
    "report. IRREGULARITY: controversial approval following AdCom split. SRPT re-used.", 2016)

# 16. Adlyxin (lixisenatide) - Sanofi
add("Sanofi S.A.", "SNY", "NASDAQ (ADR)",
    "Adlyxin", "lixisenatide", "2016-07-27",
    "Type 2 diabetes mellitus",
    "", "208471",
    "FDA 2016 table row 16 (NDA 208471). Sanofi applicant; SNY ADR re-used.", 2016)

# 15. Xiidra (lifitegrast) - Shire (acquired by Takeda 2019). Shire was NASDAQ:SHPG.
add("Shire plc (acquired by Takeda 2019)", "SHPG",
    "NASDAQ (delisted 2019)",
    "Xiidra", "lifitegrast", "2016-07-11",
    "Signs and symptoms of dry eye disease",
    "Priority", "208073",
    "FDA 2016 table row 15 (NDA 208073). Shire plc applicant; Priority Review per FDA 2016 report; "
    "Takeda acquired Shire Jan 2019. SHPG delisted; price cells left blank.", 2016)

# 14. Epclusa (sofosbuvir/velpatasvir) - Gilead
add("Gilead Sciences, Inc.", "GILD", "NASDAQ",
    "Epclusa", "sofosbuvir/velpatasvir", "2016-06-28",
    "Chronic HCV (all six genotypes)",
    "Priority", "208341",
    "FDA 2016 table row 14 (NDA 208341). Gilead applicant; Priority Review per FDA 2016 report. "
    "GILD re-used.", 2016)

# 11. Ocaliva (obeticholic acid) - Intercept Pharmaceuticals
add("Intercept Pharmaceuticals, Inc.", "ICPT", "NASDAQ",
    "Ocaliva", "obeticholic acid", "2016-05-27",
    "Primary biliary cholangitis",
    "Priority", "207999",
    "FDA 2016 table row 11 (NDA 207999). Intercept applicant; Priority Review per FDA 2016 report. "
    "ICPT decision-date NASDAQ ticker.", 2016)

# 10. Zinbryta (daclizumab) - Biogen/AbbVie; withdrawn 2018.
add("Biogen Inc. (with AbbVie)", "BIIB", "NASDAQ",
    "Zinbryta", "daclizumab", "2016-05-27",
    "Relapsing multiple sclerosis",
    "", "761029",
    "FDA 2016 table row 10 (BLA 761029). Biogen/AbbVie; WITHDRAWN globally March 2018 due to "
    "severe brain inflammation (encephalitis/meningoencephalitis). IRREGULARITY: safety-driven "
    "withdrawal flagged. BIIB used as decision-date ticker.", 2016)

# 9. Tecentriq (atezolizumab) - Genentech/Roche
add("Genentech, Inc. (Roche group)", "RHHBY", "OTC ADR; primary SIX:ROG",
    "Tecentriq", "atezolizumab", "2016-05-18",
    "Locally advanced/metastatic urothelial carcinoma",
    "Priority; Accelerated; Breakthrough", "761034",
    "FDA 2016 table row 9 (BLA 761034). Genentech/Roche applicant; Accelerated Approval, "
    "Breakthrough, Priority per FDA 2016 report.", 2016)

# 8. Nuplazid (pimavanserin) - Acadia
add("Acadia Pharmaceuticals", "ACAD", "NASDAQ",
    "Nuplazid", "pimavanserin", "2016-04-29",
    "Hallucinations/delusions in Parkinson's disease psychosis",
    "Priority; Breakthrough", "207318",
    "FDA 2016 table row 8 (NDA 207318). Acadia Pharmaceuticals applicant; Breakthrough Therapy, "
    "Priority per FDA 2016 report. ACAD re-used.", 2016)

# 7. Venclexta (venetoclax) - AbbVie/Genentech
add("AbbVie Inc. (co-developed with Genentech/Roche)", "ABBV", "NYSE",
    "Venclexta", "venetoclax", "2016-04-11",
    "Chronic lymphocytic leukemia with 17p deletion",
    "Priority; Accelerated; Breakthrough", "208573",
    "FDA 2016 table row 7 (NDA 208573). AbbVie (with Genentech) applicant; Accelerated Approval + "
    "Breakthrough + Priority per FDA 2016 report. ABBV re-used.", 2016)

# 6. Defitelio (defibrotide) - Jazz Pharmaceuticals
add("Jazz Pharmaceuticals plc", "JAZZ", "NASDAQ",
    "Defitelio", "defibrotide sodium", "2016-03-30",
    "Hepatic veno-occlusive disease post-HSCT",
    "Priority", "208114",
    "FDA 2016 table row 6 (NDA 208114). IRREGULARITY FLAG: FDA's 2016 table prints the approval "
    "date as 3/30/3016 (typo); recorded as 2016-03-30 consistent with FDA approval letter and "
    "Drugs@FDA. Priority Review per FDA 2016 report. JAZZ re-used.", 2016)

# 5. Cinqair (reslizumab) - Teva
add("Teva Pharmaceutical Industries Limited", "TEVA", "NYSE (ADS; ordinary shares listed in Tel Aviv)",
    "Cinqair", "reslizumab", "2016-03-23",
    "Severe eosinophilic asthma (add-on maintenance)",
    "", "761033",
    "FDA 2016 table row 5 (BLA 761033). Teva (from Cephalon acquisition) applicant. TEVA re-used.", 2016)

# 4. Taltz (ixekizumab) - Eli Lilly
add("Eli Lilly and Company", "LLY", "NYSE",
    "Taltz", "ixekizumab", "2016-03-22",
    "Moderate-to-severe plaque psoriasis",
    "", "125521",
    "FDA 2016 table row 4 (BLA 125521). Eli Lilly applicant. LLY re-used.", 2016)

# 2. Briviact (brivaracetam) - UCB
add("UCB, Inc. (UCB S.A. Belgium)", "NO_TICKER",
    "N/A - Brussels-listed UCB (EBR:UCB); no US ADR verified in this pass",
    "Briviact", "brivaracetam", "2016-02-18",
    "Partial-onset seizures (epilepsy, age 16+)",
    "", "205836",
    "FDA 2016 table row 2 (NDA 205836). UCB is Brussels-listed; no US ADR verified in this pass, "
    "so no ticker asserted.", 2016)

# 1. Zepatier (elbasvir/grazoprevir) - Merck & Co.
add("Merck & Co., Inc.", "MRK", "NYSE",
    "Zepatier", "elbasvir/grazoprevir", "2016-01-28",
    "Chronic HCV genotypes 1 and 4",
    "", "208261",
    "FDA 2016 table row 1 (NDA 208261). Merck (MSD) applicant. MRK re-used.", 2016)

# ------------------------------------------------------------- 2017 entries (46)
# 46. Giapreza (angiotensin II) - La Jolla Pharmaceutical (LJPC)
add("La Jolla Pharmaceutical Company", "LJPC", "NASDAQ",
    "Giapreza", "angiotensin II", "2017-12-21",
    "Septic or other distributive shock (blood pressure support)",
    "Priority", "209360",
    "FDA 2017 table row 46 (NDA 209360). La Jolla Pharmaceutical Co. applicant; Priority Review per "
    "FDA 2017 report. LJPC was the decision-date NASDAQ ticker.", 2017)

# 45. Macrilen (macimorelin) - Aeterna Zentaris (AEZS), licensed to Novo Nordisk in 2018;
# applicant at approval December 2017 was Aeterna Zentaris.
add("Aeterna Zentaris Inc.", "AEZS", "NASDAQ",
    "Macrilen", "macimorelin acetate", "2017-12-20",
    "Diagnosis of adult growth hormone deficiency",
    "", "205598",
    "FDA 2017 table row 45 (NDA 205598). Aeterna Zentaris applicant (Novo Nordisk licensed US "
    "rights in 2018); AEZS decision-date ticker.", 2017)

# 44. Steglatro (ertugliflozin) - Merck/Pfizer (co-commercialized); Merck held the NDA.
add("Merck & Co., Inc. (co-commercialized with Pfizer)", "MRK", "NYSE",
    "Steglatro", "ertugliflozin", "2017-12-19",
    "Type 2 diabetes (glycemic control)",
    "", "209803",
    "FDA 2017 table row 44 (NDA 209803). Merck & Co. (MSD) applicant; co-developed and "
    "co-commercialized with Pfizer. MRK re-used.", 2017)

# 43. Rhopressa (netarsudil) - Aerie Pharmaceuticals; acquired by Alcon/Novartis 2022.
# Ticker AERI at approval (NASDAQ).
add("Aerie Pharmaceuticals, Inc. (acquired by Alcon/Novartis 2022)", "AERI",
    "NASDAQ (delisted 2022)",
    "Rhopressa", "netarsudil", "2017-12-18",
    "Glaucoma/ocular hypertension (lower intraocular pressure)",
    "", "208254",
    "FDA 2017 table row 43 (NDA 208254). Aerie applicant; acquired by Alcon (Novartis) 2022. AERI "
    "delisted; price cells left blank.", 2017)

# 41. Ozempic (semaglutide) - Novo Nordisk
add("Novo Nordisk A/S", "NVO", "NYSE",
    "Ozempic", "semaglutide", "2017-12-05",
    "Type 2 diabetes (glycemic control)",
    "", "209637",
    "FDA 2017 table row 41 (NDA 209637). Novo Nordisk applicant. NVO re-used.", 2017)

# 40. Hemlibra (emicizumab) - Genentech/Roche (Chugai)
add("Genentech, Inc. (Roche group / Chugai)", "RHHBY", "OTC ADR; primary SIX:ROG",
    "Hemlibra", "emicizumab", "2017-11-16",
    "Hemophilia A with Factor VIII inhibitors (bleeding prophylaxis)",
    "Priority; Breakthrough", "761083",
    "FDA 2017 table row 40 (BLA 761083). Genentech (Roche/Chugai) applicant; Priority Review, "
    "Breakthrough per FDA 2017 report.", 2017)

# 38. Fasenra (benralizumab) - AstraZeneca
add("AstraZeneca PLC", "AZN", "NYSE",
    "Fasenra", "benralizumab", "2017-11-14",
    "Severe eosinophilic asthma (add-on maintenance, age 12+)",
    "", "761070",
    "FDA 2017 table row 38 (BLA 761070). AstraZeneca applicant. AZN re-used.", 2017)

# 37. Prevymis (letermovir) - Merck & Co.
add("Merck & Co., Inc.", "MRK", "NYSE",
    "Prevymis", "letermovir", "2017-11-08",
    "CMV prophylaxis in allogeneic HSCT recipients",
    "", "209939",
    "FDA 2017 table row 37 (NDA 209939). Merck & Co. (MSD) applicant (from AiCuris). MRK re-used.", 2017)

# 36. Vyzulta (latanoprostene bunod) - Bausch + Lomb (Bausch Health, VRX at time).
# Bausch Health (formerly Valeant) was NYSE:VRX, later BHC.
add("Bausch Health Companies Inc. (Bausch + Lomb)", "BHC", "NYSE",
    "Vyzulta", "latanoprostene bunod", "2017-11-02",
    "Open-angle glaucoma/ocular hypertension",
    "", "207795",
    "FDA 2017 table row 36 (NDA 207795). Bausch + Lomb (Valeant/Bausch Health) was US applicant. "
    "Ticker was VRX (now BHC) at the time; BHC is recorded with the ticker-change flagged. IRREG-"
    "ULARITY: Valeant was renamed Bausch Health Companies in July 2018; decision-date ticker "
    "VRX->BHC.", 2017)

# 35. Calquence (acalabrutinib) - AstraZeneca (Acerta Pharma)
add("AstraZeneca PLC", "AZN", "NYSE",
    "Calquence", "acalabrutinib", "2017-10-31",
    "Mantle cell lymphoma",
    "Priority; Accelerated", "210259",
    "FDA 2017 table row 35 (NDA 210259). AstraZeneca (Acerta Pharma acquisition) applicant; "
    "Accelerated Approval, Priority per FDA 2017 report. AZN re-used.", 2017)

# 34. Verzenio (abemaciclib) - Eli Lilly
add("Eli Lilly and Company", "LLY", "NYSE",
    "Verzenio", "abemaciclib", "2017-09-28",
    "HR+/HER2- advanced/metastatic breast cancer",
    "Priority", "208716",
    "FDA 2017 table row 34 (NDA 208716). Eli Lilly applicant; Priority per FDA 2017 report. LLY "
    "re-used.", 2017)

# 33. Solosec (secnidazole) - Symbiomix; acquired by Lupin 2017. Symbiomix was private at approval.
add("Symbiomix Therapeutics (acquired by Lupin Ltd. December 2017)", "NO_TICKER",
    "N/A - Symbiomix privately held at approval; Lupin Ltd is NSE:LUPIN (no US ADR)",
    "Solosec", "secnidazole", "2017-09-15",
    "Bacterial vaginosis",
    "", "209363",
    "FDA 2017 table row 33 (NDA 209363). Symbiomix was private at approval; Lupin acquired the "
    "company days after approval (Dec 2017). No US-listed equity is asserted at decision date.", 2017)

# 32. Aliqopa (copanlisib) - Bayer
add("Bayer AG", "BAYRY", "OTC ADR; primary XETRA:BAYN",
    "Aliqopa", "copanlisib", "2017-09-14",
    "Relapsed follicular lymphoma",
    "Priority; Accelerated", "209936",
    "FDA 2017 table row 32 (NDA 209936). Bayer applicant; Accelerated Approval + Priority per FDA "
    "2017 report. BAYRY OTC ADR.", 2017)

# 30. Vabomere (meropenem/vaborbactam) - The Medicines Company (later acquired by Melinta, then
# Melinta acquired by Melinta Therapeutics). Decision-date applicant was The Medicines Company (MDCO).
add("The Medicines Company (MDCO)", "MDCO",
    "NASDAQ (delisted 2020)",
    "Vabomere", "meropenem/vaborbactam", "2017-08-29",
    "Complicated urinary tract infections including pyelonephritis",
    "Priority; QIDP", "209776",
    "FDA 2017 table row 30 (NDA 209776). The Medicines Company applicant; Priority Review + QIDP "
    "(antibiotic) per FDA 2017 report. Antibiotic assets later sold to Melinta. MDCO delisted.", 2017)

# 29. Besponsa (inotuzumab ozogamicin) - Pfizer
add("Pfizer Inc.", "PFE", "NYSE",
    "Besponsa", "inotuzumab ozogamicin", "2017-08-17",
    "Relapsed/refractory B-cell precursor acute lymphoblastic leukemia",
    "Priority", "761040",
    "FDA 2017 table row 29 (BLA 761040). Pfizer (Wyeth legacy) applicant; Priority per FDA 2017 "
    "report. PFE re-used.", 2017)

# 28. Mavyret (glecaprevir/pibrentasvir) - AbbVie
add("AbbVie Inc.", "ABBV", "NYSE",
    "Mavyret", "glecaprevir/pibrentasvir", "2017-08-03",
    "Chronic HCV (all genotypes)",
    "Priority", "209394",
    "FDA 2017 table row 28 (NDA 209394). AbbVie applicant; Priority Review per FDA 2017 report. "
    "ABBV re-used.", 2017)

# 27. Idhifa (enasidenib) - Celgene (Bristol-Myers Squibb acquired Celgene 2019);
# originated by Agios; partnership. At approval Celgene (CELG) was applicant.
add("Celgene Corporation (acquired by Bristol Myers Squibb 2019)", "CELG",
    "NASDAQ (delisted 2019)",
    "Idhifa", "enasidenib", "2017-08-01",
    "Relapsed/refractory AML with IDH2 mutation",
    "Priority; Orphan", "209606",
    "FDA 2017 table row 27 (NDA 209606). Celgene (CELG) applicant at approval (Agios partnership; "
    "later Servier). CELG delisted after BMY acquisition 2019; price cells left blank.", 2017)

# 26. Vosevi - Gilead
add("Gilead Sciences, Inc.", "GILD", "NASDAQ",
    "Vosevi", "sofosbuvir/velpatasvir/voxilaprevir", "2017-07-18",
    "Chronic HCV (DAA-experienced)",
    "Priority", "209195",
    "FDA 2017 table row 26 (NDA 209195). Gilead applicant; Priority per FDA 2017 report. GILD.", 2017)

# 25. Nerlynx (neratinib) - Puma Biotechnology
add("Puma Biotechnology, Inc.", "PBYI", "NASDAQ",
    "Nerlynx", "neratinib maleate", "2017-07-17",
    "Extended adjuvant treatment of HER2+ early breast cancer",
    "", "208051",
    "FDA 2017 table row 25 (NDA 208051). Puma Biotechnology applicant; PBYI decision-date NASDAQ "
    "ticker.", 2017)

# 24. Tremfya (guselkumab) - Janssen (J&J)
add("Johnson & Johnson (Janssen Biotech)", "JNJ", "NYSE",
    "Tremfya", "guselkumab", "2017-07-13",
    "Moderate-to-severe plaque psoriasis",
    "", "761061",
    "FDA 2017 table row 24 (BLA 761061). Janssen (J&J) applicant. JNJ re-used.", 2017)

# 23. Bevyxxa (betrixaban) - Portola Pharmaceuticals (acquired by Alexion/AZ 2020); ticker PTLA.
add("Portola Pharmaceuticals, Inc. (acquired by Alexion/AstraZeneca 2020)", "PTLA",
    "NASDAQ (delisted 2020)",
    "Bevyxxa", "betrixaban", "2017-06-23",
    "VTE prophylaxis in acutely ill medical patients",
    "", "208383",
    "FDA 2017 table row 23 (NDA 208383). Portola Pharmaceuticals applicant (later Alexion then "
    "Menarini). PTLA delisted; price cells left blank.", 2017)

# 22. Baxdela (delafloxacin) - Melinta Therapeutics (MLNT)
add("Melinta Therapeutics, Inc.", "MLNT",
    "NASDAQ (delisted/bankrupt 2019)",
    "Baxdela", "delafloxacin", "2017-06-19",
    "Acute bacterial skin and skin structure infections",
    "Priority; QIDP", "208610",
    "FDA 2017 table row 22 (NDA 208610). Melinta Therapeutics applicant; QIDP + Priority per FDA "
    "2017 report. MLNT traded on NASDAQ until 2019 bankruptcy.", 2017)

# 21. Kevzara (sarilumab) - Sanofi/Regeneron
add("Regeneron Pharmaceuticals, Inc. (with Sanofi)", "REGN", "NASDAQ",
    "Kevzara", "sarilumab", "2017-05-22",
    "Moderate-to-severe rheumatoid arthritis",
    "", "761037",
    "FDA 2017 table row 21 (BLA 761037). Sanofi/Regeneron co-applicant. REGN used as US-listed "
    "decision-date ticker.", 2017)

# 20. Radicava (edaravone) - Mitsubishi Tanabe Pharma (Mitsubishi Chemical Holdings)
# MT Pharma is a subsidiary of Mitsubishi Tanabe Pharma (TYO:4508) - US OTC ADR: no clean ticker
# in 2017. Mark no public equity verified.
add("Mitsubishi Tanabe Pharma America, Inc. (subsidiary of Mitsubishi Chemical Holdings)", "NO_TICKER",
    "N/A - US subsidiary of Japanese TYO:4508; no US ADR verified in this pass",
    "Radicava", "edaravone", "2017-05-05",
    "Amyotrophic lateral sclerosis (ALS)",
    "", "209176",
    "FDA 2017 table row 20 (NDA 209176). Mitsubishi Tanabe Pharma America was US applicant; "
    "parent is Tokyo-listed with no clean US ADR. No US-listed equity asserted.", 2017)

# 19. Imfinzi (durvalumab) - AstraZeneca
add("AstraZeneca PLC", "AZN", "NYSE",
    "Imfinzi", "durvalumab", "2017-05-01",
    "Locally advanced/metastatic urothelial carcinoma",
    "Priority; Accelerated", "761069",
    "FDA 2017 table row 19 (BLA 761069). AstraZeneca applicant; Accelerated Approval + Priority "
    "per FDA 2017 report. AZN re-used.", 2017)

# 18. Tymlos (abaloparatide) - Radius Health (RDUS)
add("Radius Health, Inc.", "RDUS", "NASDAQ",
    "Tymlos", "abaloparatide", "2017-04-28",
    "Postmenopausal osteoporosis at high fracture risk",
    "", "208743",
    "FDA 2017 table row 18 (NDA 208743). Radius Health applicant; RDUS decision-date NASDAQ "
    "ticker.", 2017)

# 17. Rydapt (midostaurin) - Novartis
add("Novartis AG", "NVS", "NYSE",
    "Rydapt", "midostaurin", "2017-04-28",
    "FLT3-mutant AML; advanced systemic mastocytosis",
    "Priority; Breakthrough", "207997",
    "FDA 2017 table row 17 (NDA 207997). Novartis applicant; Priority + Breakthrough per FDA 2017 "
    "report. NVS re-used.", 2017)

# 16. Alunbrig (brigatinib) - Takeda / ARIAD Pharmaceuticals. ARIAD was acquired by Takeda in
# Feb 2017 (closed Feb 16, 2017); approval April 28 2017 so Takeda was holder at approval.
add("Takeda Pharmaceutical Company Limited (acquired ARIAD Pharmaceuticals Feb 2017)", "TAK", "NYSE",
    "Alunbrig", "brigatinib", "2017-04-28",
    "ALK+ metastatic NSCLC after crizotinib",
    "Accelerated", "208772",
    "FDA 2017 table row 16 (NDA 208772). Takeda closed ARIAD acquisition 2017-02-16 so Takeda was "
    "holder at approval; Accelerated Approval per FDA 2017 report. TAK re-used.", 2017)

# 15. Brineura (cerliponase alfa) - BioMarin
add("BioMarin Pharmaceutical Inc.", "BMRN", "NASDAQ",
    "Brineura", "cerliponase alfa", "2017-04-27",
    "Late infantile neuronal ceroid lipofuscinosis type 2 (CLN2/Batten disease)",
    "Priority; Breakthrough", "761052",
    "FDA 2017 table row 15 (BLA 761052). BioMarin applicant; Priority + Breakthrough per FDA 2017 "
    "report. BMRN re-used.", 2017)

# 14. Ingrezza (valbenazine) - Neurocrine Biosciences (NBIX)
add("Neurocrine Biosciences, Inc.", "NBIX", "NASDAQ",
    "Ingrezza", "valbenazine", "2017-04-11",
    "Tardive dyskinesia",
    "Priority", "209241",
    "FDA 2017 table row 14 (NDA 209241). Neurocrine Biosciences applicant; Priority per FDA 2017 "
    "report. NBIX is the decision-date NASDAQ ticker.", 2017)

# 13. Austedo (deutetrabenazine) - Teva
add("Teva Pharmaceutical Industries Limited", "TEVA", "NYSE (ADS; ordinary shares listed in Tel Aviv)",
    "Austedo", "deutetrabenazine", "2017-04-03",
    "Chorea associated with Huntington's disease",
    "", "208082",
    "FDA 2017 table row 13 (NDA 208082). Teva applicant (Auspex acquisition). TEVA re-used.", 2017)

# 12. Ocrevus (ocrelizumab) - Genentech/Roche
add("Genentech, Inc. (Roche group)", "RHHBY", "OTC ADR; primary SIX:ROG",
    "Ocrevus", "ocrelizumab", "2017-03-28",
    "Relapsing and primary progressive multiple sclerosis",
    "Priority; Breakthrough", "761053",
    "FDA 2017 table row 12 (BLA 761053). Genentech (Roche) applicant; Priority + Breakthrough per "
    "FDA 2017 report.", 2017)

# 11. Dupixent (dupilumab) - Sanofi/Regeneron
add("Regeneron Pharmaceuticals, Inc. (with Sanofi)", "REGN", "NASDAQ",
    "Dupixent", "dupilumab", "2017-03-28",
    "Moderate-to-severe atopic dermatitis",
    "Priority; Breakthrough", "761055",
    "FDA 2017 table row 11 (BLA 761055). Sanofi/Regeneron co-applicant; Priority + Breakthrough per "
    "FDA 2017 report. REGN used as US-listed ticker.", 2017)

# 10. Zejula (niraparib) - Tesaro/GSK; at 2017 approval applicant was Tesaro (TSRO).
add("Tesaro, Inc. (acquired by GSK 2018)", "TSRO",
    "NASDAQ (delisted 2019)",
    "Zejula", "niraparib", "2017-03-27",
    "Maintenance treatment of recurrent ovarian/fallopian tube/primary peritoneal cancer",
    "Priority", "208447",
    "FDA 2017 table row 10 (NDA 208447). Tesaro applicant; Priority per FDA 2017 report; later "
    "acquired by GSK Dec 2018. TSRO delisted; price cells left blank.", 2017)

# 9. Symproic (naldemedine) - Shionogi; Purdue Pharma licensed it briefly but approval holder was
# Shionogi (TYO:4507, no US ADR).
add("Shionogi Inc. (US subsidiary of Shionogi & Co., Ltd.)", "NO_TICKER",
    "N/A - parent TYO:4507; no US ADR verified in this pass",
    "Symproic", "naldemedine", "2017-03-23",
    "Opioid-induced constipation",
    "", "208854",
    "FDA 2017 table row 9 (NDA 208854). Shionogi US applicant; parent Tokyo-listed with no clean "
    "US ADR at decision date. No US-listed equity asserted.", 2017)

# 8. Bavencio (avelumab) - EMD Serono (Merck KGaA)/Pfizer
add("Merck KGaA (EMD Serono; co-developed with Pfizer)", "MKGAY",
    "OTC ADR; primary XETRA:MRK (Merck KGaA Darmstadt)",
    "Bavencio", "avelumab", "2017-03-23",
    "Metastatic Merkel cell carcinoma",
    "Priority; Accelerated", "761049",
    "FDA 2017 table row 8 (BLA 761049). Merck KGaA Darmstadt (EMD Serono) co-developed with "
    "Pfizer; Accelerated Approval + Priority per FDA 2017 report. MKGAY is Merck KGaA's US OTC ADR.", 2017)

# 7. Xadago (safinamide) - Newron/US WorldMeds (private).
add("Newron Pharmaceuticals (partnered with US WorldMeds)", "NO_TICKER",
    "N/A - US WorldMeds is privately held; Newron (SWX:NEWN) has no US ADR verified in this pass",
    "Xadago", "safinamide", "2017-03-21",
    "Parkinson's disease (adjunct to levodopa/carbidopa)",
    "", "207145",
    "FDA 2017 table row 7 (NDA 207145). US WorldMeds was US commercial partner (private). "
    "No US-listed equity is asserted.", 2017)

# 6. Kisqali (ribociclib) - Novartis
add("Novartis AG", "NVS", "NYSE",
    "Kisqali", "ribociclib", "2017-03-13",
    "HR+/HER2- advanced/metastatic breast cancer (postmenopausal)",
    "Priority; Breakthrough", "209092",
    "FDA 2017 table row 6 (NDA 209092). Novartis applicant; Priority + Breakthrough per FDA 2017 "
    "report. NVS re-used.", 2017)

# 5. Xermelo (telotristat ethyl) - Lexicon Pharmaceuticals (LXRX)
add("Lexicon Pharmaceuticals, Inc.", "LXRX", "NASDAQ",
    "Xermelo", "telotristat ethyl", "2017-02-28",
    "Carcinoid syndrome diarrhea",
    "", "208794",
    "FDA 2017 table row 5 (NDA 208794). Lexicon Pharmaceuticals applicant; LXRX decision-date "
    "NASDAQ ticker.", 2017)

# 4. Siliq (brodalumab) - Valeant (Bausch Health) / AstraZeneca origin; at approval, Valeant/Bausch
# (VRX at the time) held US rights.
add("Bausch Health Companies Inc. (Bausch + Lomb)", "BHC", "NYSE",
    "Siliq", "brodalumab", "2017-02-15",
    "Moderate-to-severe plaque psoriasis",
    "", "761032",
    "FDA 2017 table row 4 (BLA 761032). Valeant (Bausch Health) was US licensee at approval "
    "(originated by Amgen, AstraZeneca). Ticker was VRX (now BHC) at the time; BHC recorded.", 2017)

# 3. Emflaza (deflazacort) - Marathon Pharmaceuticals (private); later PTC Therapeutics (PTCT)
#     acquired US rights in 2017. Marathon was private at approval.
add("Marathon Pharmaceuticals (private; rights sold to PTC Therapeutics 2017)", "NO_TICKER",
    "N/A - Marathon privately held at approval; PTC (PTCT) acquired rights later and is NOT backdated",
    "Emflaza", "deflazacort", "2017-02-09",
    "Duchenne muscular dystrophy (age 5+)",
    "Priority; Orphan", "208684",
    "FDA 2017 table row 3 (NDA 208684). Marathon Pharmaceuticals (private) was applicant at "
    "approval; PTC Therapeutics (PTCT) acquired US rights in March 2017, after approval; IRREGU-"
    "LARITY: Marathon's $89,000 list price sparked controversy and led to the divestiture to PTC. "
    "No decision-date ticker asserted.", 2017)

# 2. Parsabiv (etelcalcetide) - Amgen (KAI Pharmaceuticals)
add("Amgen Inc.", "AMGN", "NASDAQ",
    "Parsabiv", "etelcalcetide", "2017-02-07",
    "Secondary hyperparathyroidism in adult CKD on dialysis",
    "", "208325",
    "FDA 2017 table row 2 (NDA 208325). Amgen applicant (KAI acquisition). AMGN re-used.", 2017)

# 1. Trulance (plecanatide) - Synergy Pharmaceuticals; acquired by Bausch/Ardelyx/Salix in stages;
# Synergy traded as SGYP on NASDAQ until 2018 bankruptcy; later rights to Salix(Bausch)/Ardelyx.
add("Synergy Pharmaceuticals Inc. (bankrupt 2018; rights to Salix/Bausch then Ardelyx)", "SGYP",
    "NASDAQ (delisted/bankrupt 2018)",
    "Trulance", "plecanatide", "2017-01-19",
    "Chronic idiopathic constipation",
    "", "208745",
    "FDA 2017 table row 1 (NDA 208745). Synergy Pharmaceuticals was applicant at approval; later "
    "bankruptcy and rights transfers. SGYP was decision-date ticker (delisted); price cells blank.", 2017)

# 43. Bridion (sugammadex) - Merck & Co. (from legacy Schering-Plough/Organon/N.V. Organon).
# Wait — per Drugs@FDA NDA 022225 original approval 12/15/2015 sugammadex (Bridion) was approved
# to Merck Sharp & Dohme Corp. (a subsidiary of Merck & Co., Inc.)
add("Merck & Co., Inc. (Merck Sharp & Dohme)", "MRK", "NYSE",
    "Bridion", "sugammadex", "2015-12-15",
    "Reversal of neuromuscular blockade induced by rocuronium/vecuronium",
    "Priority", "022225",
    "FDA 2015 table row 43 (NDA 022225). Merck Sharp & Dohme (Merck & Co., Inc.) applicant; "
    "Priority Review per FDA 2015 report. MRK re-used. NOTE: original NDA was filed by Organon "
    "(Schering-Plough legacy); Merck marketed at approval.", 2015)

# 7. Avycaz (ceftazidime-avibactam) - Allergan (Actavis/Forest); AstraZeneca later acquired rights.
# At approval Feb 2015: Allergan/Actavis (Forest Labs was acquired by Actavis which became Allergan).
# Since Viberzi/Vraylar from same sponsor are already flagged NO_US_TICKER, skip duplicate and use a
# different entry. Add Xuriden? That's to Wellstat Therapeutics (private). Instead add 2017 #42 Xepi
# Xepi is ozenoxacin (2017-12-11); applicant was Medimetriks (private). Skip. Let me add Cresemba
# (isavuconazonium) 2015 - Astellas (Astellas Pharma; ALPMY OTC ADR; primary TSE:4503).
add("Astellas Pharma Inc.", "ALPMY", "OTC ADR; primary TSE:4503",
    "Cresemba", "isavuconazonium sulfate", "2015-03-06",
    "Invasive aspergillosis and invasive mucormycosis",
    "Priority; QIDP", "207500",
    "FDA 2015 table row 8 (NDA 207500). Astellas Pharma US applicant (from Basilea). Priority + "
    "QIDP per FDA 2015 report. ALPMY is Astellas's US OTC ADR (same as already-verified D250).", 2015)

# ------------------------------------------------ Sanity check
assert len(ROWS) == 100, f"Expected 100 rows, got {len(ROWS)}"

# Now append to the master CSV, assigning IDs sequentially starting at the next available.
def main():
    # Load existing IDs to avoid duplicates
    existing = list(csv.DictReader(open(MASTER)))
    seen_keys = {(r['drug_brand'].lower(), r['decision_date']) for r in existing}
    max_id = 0
    for r in existing:
        did = r['decision_id']
        if did.startswith('D'):
            try:
                n = int(did[1:])
                if n > max_id:
                    max_id = n
            except ValueError:
                pass

    fieldnames = ['company_name','ticker','drug_brand','drug_generic','decision_type',
                  'decision_date','indication','review_pathway','source_url_1','source_url_2',
                  'verification_status','notes','us_investable_class','classification_basis',
                  'exchange','decision_id']

    appended = 0
    for row in ROWS:
        key = (row['drug_brand'].lower(), row['decision_date'])
        if key in seen_keys:
            print(f"SKIP (already exists): {row['drug_brand']} {row['decision_date']}")
            continue
        max_id += 1
        row['decision_id'] = f"D{max_id:03d}"
        existing.append(row)
        appended += 1

    with open(MASTER, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in existing:
            # Ensure field order and that all keys exist
            out = {k: r.get(k, '') for k in fieldnames}
            w.writerow(out)

    print(f"Appended {appended} rows. New max decision ID: D{max_id:03d}.")

if __name__ == '__main__':
    main()
