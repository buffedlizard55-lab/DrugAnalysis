# -*- coding: utf-8 -*-
"""
Appends 23 of FDA's 2019 novel drug approvals (decision IDs D278-D300).

FDA has taken its 2019 and 2020 "Novel Drug Approvals" web pages offline, so
this cohort is sourced from FDA's official annual report instead:

  Advancing Health Through Innovation: New Drug Therapy Approvals 2019
  https://www.fda.gov/media/133911/download

  * Appendix A - "CDER's Novel Approvals of 2019" supplies, for each drug:
    Approval Date | Trade Name | Active Ingredient(s) | Summary of FDA-approved
    use on Approval date | Dosage Form
  * Appendix B - "Novel Drug Designation Summary" supplies the review pathway
    (Priority / Accelerated Approval / Standard). This is the same official
    source that produced the review_pathway values for D001-D200, so these
    rows carry a real pathway whereas D201-D277 do not.

The applicant of record for every drug was then verified individually through
the openFDA Drugs@FDA API, e.g.
  api.fda.gov/drug/drugsfda.json?search=openfda.brand_name:"adakveo"&count=sponsor_name
and that query URL is stored as source_url_2 so each row can be re-run.

Prices were captured for the US-listed names only; thinly traded OTC ADRs
(Eisai ESALY, Daiichi Sankyo DSNKY, Astellas ALPMY, Bayer BAYRY) are marked
"Verified - foreign/OTC listing, price not captured" for the same reason the
2021-2026 foreign listings are.
"""
import csv
import os

HEADER = ["decision_id", "company_name", "ticker", "exchange", "drug_brand", "drug_generic",
          "decision_type", "decision_date", "indication", "review_pathway",
          "source_url_1", "source_url_2", "verification_status", "notes"]

REPORT = "https://www.fda.gov/media/133911/download"
OPENFDA = ("https://api.fda.gov/drug/drugsfda.json?search=openfda.brand_name:%22{brand}%22"
           "&count=sponsor_name")

# brand, generic, date, indication, pathway, [company, ticker, exchange, openfda sponsor,
#                                             status, notes]
ROWS_2019 = [
    ("Adakveo", "crizanlizumab-tmca", "2019-11-15", "Reduce vasoocclusive crises in sickle cell disease",
     "Priority",
     ["Novartis AG", "NVS", "NYSE (ADR)", "NOVARTIS PHARMS CORP", "Verified",
      "FDA Appendix B also flags Orphan and Breakthrough Therapy for Adakveo"]),
    ("Balversa", "erdafitinib", "2019-04-12",
     "Locally advanced or metastatic bladder cancer (FGFR-altered)", "Accelerated Approval",
     ["Johnson & Johnson (Janssen Biotech)", "JNJ", "NYSE", "JANSSEN BIOTECH", "Verified",
      "First-in-class and Breakthrough Therapy per FDA Appendix B"]),
    ("Brukinsa", "zanubrutinib", "2019-11-14", "Mantle cell lymphoma", "Accelerated Approval",
     ["BeOne Medicines (formerly BeiGene)", "ONC", "NASDAQ", "BEONE MEDICINES USA", "Verified",
      "openFDA lists the current applicant as BEONE MEDICINES USA - BeiGene renamed itself BeOne "
      "Medicines and changed its ticker from BGNE to ONC, so ONC is the symbol carrying this "
      "history. Accelerated Approval + Orphan per FDA Appendix B"]),
    ("Cablivi", "caplacizumab-yhdp", "2019-02-06",
     "Acquired thrombotic thrombocytopenic purpura", "Priority",
     ["Sanofi (Ablynx NV)", "SNY", "NASDAQ (ADR)", "ABLYNX NV", "Verified",
      "Sanofi acquired Ablynx in 2018; openFDA still lists Ablynx NV as the applicant of record. "
      "First-in-class + Orphan + Fast Track per FDA Appendix B"]),
    ("Caplyta", "lumateperone", "2019-12-20", "Schizophrenia", "Standard",
     ["Intra-Cellular Therapies, Inc. (acquired by J&J, 2025)", "ITCI",
      "formerly NASDAQ:ITCI, delisted 2025", "INTRA-CELLULAR", "Verified - FLAGGED IRREGULARITY",
      "Johnson & Johnson completed the acquisition in 2025 and ITCI is delisted, so the chart API "
      "no longer returns this price history. Fast Track per FDA Appendix B"]),
    ("Dayvigo", "lemborexant", "2019-12-20", "Insomnia", "Standard",
     ["Eisai Co., Ltd.", "ESALY", "OTC ADR; primary TSE:4523", "EISAI INC",
      "Verified - foreign/OTC listing, price not captured",
      "US OTC ADR only; the primary listing is Tokyo (4523.T). Price not captured for thin OTC "
      "ADRs, consistent with how the 2021-2026 foreign listings are handled"]),
    ("Enhertu", "fam-trastuzumab deruxtecan-nxki", "2019-12-20", "Metastatic breast cancer",
     "Accelerated Approval",
     ["Daiichi Sankyo Company, Limited", "DSNKY", "OTC ADR; primary TSE:4568", "DAIICHI SANKYO",
      "Verified - foreign/OTC listing, price not captured",
      "Co-developed with AstraZeneca; openFDA lists Daiichi Sankyo as applicant of record. "
      "Fast Track + Breakthrough + Accelerated Approval per FDA Appendix B"]),
    ("Evenity", "romosozumab-aqqg", "2019-04-09",
     "Osteoporosis in postmenopausal women at high risk of fracture", "Standard",
     ["Amgen Inc. (with UCB)", "AMGN", "NASDAQ", "AMGEN INC", "Verified",
      "Co-developed with UCB; openFDA lists Amgen as applicant of record. First-in-class per FDA "
      "Appendix B. NOTE: NOT filed in the EU until later and carries a CV-risk warning"]),
    ("Givlaari", "givosiran", "2019-11-20", "Acute hepatic porphyria", "Priority",
     ["Alnylam Pharmaceuticals, Inc.", "ALNY", "NASDAQ", "ALNYLAM PHARMS INC", "Verified",
      "First-in-class + Orphan + Breakthrough per FDA Appendix B"]),
    ("Inrebic", "fedratinib", "2019-08-16", "Certain types of myelofibrosis", "Priority",
     ["Bristol Myers Squibb Company (via Celgene)", "BMY", "NYSE", "BRISTOL-MYERS", "Verified",
      "Approved to Celgene, which BMS acquired in Nov 2019; openFDA now shows Bristol-Myers as the "
      "applicant of record. Orphan + Priority per FDA Appendix B"]),
    ("Mayzent", "siponimod", "2019-03-26", "Relapsing forms of multiple sclerosis", "Standard",
     ["Novartis AG", "NVS", "NYSE (ADR)", "NOVARTIS", "Verified", ""]),
    ("Nubeqa", "darolutamide", "2019-07-30", "Non-metastatic castration-resistant prostate cancer",
     "Priority",
     ["Bayer AG (with Orion)", "BAYRY", "OTC ADR; primary XETRA:BAYN", "BAYER HEALTHCARE",
      "Verified - foreign/OTC listing, price not captured",
      "Developed with Orion Corporation; openFDA lists Bayer Healthcare as applicant of record"]),
    ("Oxbryta", "voxelotor", "2019-11-25", "Sickle cell disease", "Accelerated Approval",
     ["Global Blood Therapeutics, Inc. (acquired by Pfizer, 2022)", "GBT",
      "formerly NASDAQ:GBT, delisted 2022", "GLOBAL BLOOD THERAPS",
      "Verified - FLAGGED IRREGULARITY (withdrawn)",
      "WITHDRAWN: Pfizer voluntarily withdrew Oxbryta from all markets in 2024 after the confirmatory "
      "HOPE-KIDS 2 study failed and a safety signal emerged. The accelerated approval was not "
      "confirmed. GBT is delisted so the chart API no longer returns this history"]),
    ("Padcev", "enfortumab vedotin-ejfv", "2019-12-18", "Refractory bladder cancer",
     "Accelerated Approval",
     ["Astellas Pharma Inc. (with Seagen)", "ALPMY", "OTC ADR; primary TSE:4503", "ASTELLAS",
      "Verified - foreign/OTC listing, price not captured",
      "Co-developed with Seagen (now part of Pfizer); openFDA lists Astellas as applicant of record. "
      "First-in-class + Breakthrough + Accelerated Approval per FDA Appendix B"]),
    ("Piqray", "alpelisib", "2019-05-24", "Advanced or metastatic breast cancer", "Priority",
     ["Novartis AG", "NVS", "NYSE (ADR)", "NOVARTIS", "Verified", ""]),
    ("Polivy", "polatuzumab vedotin-piiq", "2019-06-10",
     "Relapsed or refractory diffuse large B-cell lymphoma", "Accelerated Approval",
     ["Roche (Genentech, Inc.)", "RHHBY", "OTC Markets OTCQX", "GENENTECH", "Verified",
      "First-in-class + Orphan + Breakthrough + Accelerated Approval per FDA Appendix B"]),
    ("Reblozyl", "luspatercept-aamt", "2019-11-08", "Anemia associated with beta thalassemia",
     "Priority",
     ["Bristol Myers Squibb Company (applicant at approval: Celgene)", "BMY", "NYSE",
      "CELGENE CORP", "Verified - FLAGGED IRREGULARITY (ownership change)",
      "Approved to Celgene; BMS completed the Celgene acquisition in Nov 2019, one week after this "
      "approval, and openFDA still lists CELGENE CORP as the applicant of record. First-in-class + "
      "Orphan + Fast Track + Priority per FDA Appendix B"]),
    ("Skyrizi", "risankizumab-rzaa", "2019-04-23", "Moderate-to-severe plaque psoriasis", "Standard",
     ["AbbVie Inc.", "ABBV", "NYSE", "ABBVIE INC", "Verified", ""]),
    ("Trikafta", "elexacaftor, tezacaftor, ivacaftor", "2019-10-21", "Cystic fibrosis", "Priority",
     ["Vertex Pharmaceuticals Incorporated", "VRTX", "NASDAQ", "VERTEX PHARMS INC", "Verified",
      "Orphan + Fast Track + Breakthrough + Priority per FDA Appendix B"]),
    ("Turalio", "pexidartinib", "2019-08-02", "Symptomatic tenosynovial giant cell tumor",
     "Priority",
     ["Daiichi Sankyo Company, Limited", "DSNKY", "OTC ADR; primary TSE:4568", "DAIICHI SANKYO INC",
      "Verified - foreign/OTC listing, price not captured",
      "First-in-class + Orphan + Breakthrough + Priority per FDA Appendix B; carries a boxed "
      "warning for serious liver injury and is restricted to a REMS program"]),
    ("Ubrelvy", "ubrogepant", "2019-12-23", "Migraine with or without aura", "Standard",
     ["AbbVie Inc.", "ABBV", "NYSE", "ABBVIE", "Verified",
      "Ubrelvy was developed by Allergan, which AbbVie acquired in 2020"]),
    ("Vyndaqel", "tafamidis meglumine", "2019-05-03",
     "Cardiomyopathy caused by transthyretin-mediated amyloidosis", "Priority",
     ["Pfizer Inc. (applicant: FoldRx Pharmaceuticals)", "PFE", "NYSE", "FOLDRX PHARMS", "Verified",
      "openFDA lists FoldRx Pharmaceuticals (a Pfizer subsidiary) as the applicant of record. "
      "First-in-class + Orphan + Fast Track + Breakthrough + Priority per FDA Appendix B"]),
    ("Xpovio", "selinexor", "2019-07-03", "Relapsed or refractory multiple myeloma",
     "Accelerated Approval",
     ["Karyopharm Therapeutics Inc.", "KPTI", "NASDAQ", "KARYOPHARM THERAPS", "Verified",
      "First-in-class + Orphan + Fast Track + Accelerated Approval per FDA Appendix B"]),
]


def main():
    path = "data/fda_decisions_master.csv"
    rows = []
    n = 277
    for brand, generic, date, ind, pathway, meta in ROWS_2019:
        n += 1
        company, ticker, exchange, sponsor, status, notes = meta
        rows.append([f"D{n}", company, ticker, exchange, brand, generic, "Approval", date, ind,
                     pathway, REPORT, OPENFDA.format(brand=brand.lower()),
                     status, notes])
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)
    print(f"Appended {len(rows)} 2019 approval rows (D278-D{n}) to {path}")


if __name__ == "__main__":
    main()
