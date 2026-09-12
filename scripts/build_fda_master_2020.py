# -*- coding: utf-8 -*-
"""
Appends 10 of FDA's 2020 novel drug approvals (decision IDs D301-D310).

FDA has taken its 2020 "New Drug Therapy Approvals" page offline. The live URL
404s, so this cohort is sourced from the Internet Archive's capture of that
same official FDA page (17 May 2024 snapshot):

  https://web.archive.org/web/20240517161353/https:/www.fda.gov/drugs/novel-drug-approvals-fda/new-drug-therapy-approvals-2020

  * Appendix A - "CDER's Novel Approvals of 2020" (53 drugs) supplies
    Approval Date | Trade Name | Active Ingredient(s) | approved use | dosage form
  * Appendix B - "Novel Drug Designation Summary" supplies the review pathway.
    Unlike the 2019 PDF (whose text layer had merged rows), the 2020 Appendix B
    is clean, so Priority / Accelerated Approval are read unambiguously.

Ten of the 53 were selected: those whose applicant is (or was) a liquid
US-listed name, so the price reaction could actually be measured. Every
applicant of record was verified individually via the openFDA Drugs@FDA API
(?search=openfda.brand_name:"..."&count=sponsor_name); that query URL is
stored as source_url_2.
"""
import csv

HEADER = ["decision_id", "company_name", "ticker", "exchange", "drug_brand", "drug_generic",
          "decision_type", "decision_date", "indication", "review_pathway",
          "source_url_1", "source_url_2", "verification_status", "notes"]

SRC = ("https://web.archive.org/web/20240517161353/https:/www.fda.gov/drugs/"
       "novel-drug-approvals-fda/new-drug-therapy-approvals-2020")
OPENFDA = ("https://api.fda.gov/drug/drugsfda.json?search=openfda.brand_name:%22{brand}%22"
           "&count=sponsor_name")

ROWS_2020 = [
    ("Ayvakit", "avapritinib", "2020-01-09", "Unresectable or metastatic gastrointestinal stromal tumor",
     "Priority",
     ["Blueprint Medicines Corporation (acquired by Sanofi, 2025)", "BPMC",
      "formerly NASDAQ:BPMC, delisted 2025", "BLUEPRINT MEDICINES",
      "Verified - FLAGGED IRREGULARITY",
      "Sanofi completed the Blueprint acquisition in 2025 and BPMC is delisted, so the chart API no "
      "longer returns this price history. FDA Appendix B also flags Orphan + Fast Track + "
      "Breakthrough Therapy. NOTE: Ayvakit's later GIST indication was narrowed after the "
      "confirmatory data disappointed"]),
    ("Zeposia", "ozanimod", "2020-03-25", "Relapsing forms of multiple sclerosis", "Standard",
     ["Bristol Myers Squibb Company (applicant: Celgene)", "BMY", "NYSE", "BRISTOL", "Verified",
      "Approved to Celgene and transferred to BMS with the Nov-2019 acquisition; openFDA now shows "
      "BRISTOL as the applicant of record. One of only a handful of 2020 novel drugs with NO "
      "expedited designations. CAVEAT: approved during the Mar-2020 COVID crash, so the +6% move "
      "into the next session is confounded by the market-wide rally that week"]),
    ("Koselugo", "selumetinib", "2020-04-10", "Neurofibromatosis type 1", "Priority",
     ["AstraZeneca PLC", "AZN", "NYSE", "ASTRAZENECA", "Verified - FLAGGED IRREGULARITY",
      "2020-04-10 was GOOD FRIDAY - US equity markets were closed, so there is no same-day close. "
      "The +6.0% move is measured to the next session (Mon 13 Apr). First-in-Class + Orphan + "
      "Breakthrough per FDA Appendix B"]),
    ("Pemazyre", "pemigatinib", "2020-04-17",
     "Locally advanced or metastatic cholangiocarcinoma", "Priority/Accelerated",
     ["Incyte Corporation", "INCY", "NASDAQ", "INCYTE CORP", "Verified",
      "Orphan + Breakthrough + Priority + Accelerated Approval per FDA Appendix B"]),
    ("Retevmo", "selpercatinib", "2020-05-08",
     "Metastatic non-small cell lung cancer and thyroid cancers", "Priority/Accelerated",
     ["Eli Lilly and Company (via Loxo Oncology)", "LLY", "NYSE", "ELI LILLY AND CO", "Verified",
      "Lilly acquired Loxo Oncology in 2019; openFDA lists ELI LILLY AND CO as applicant of record. "
      "Orphan + Breakthrough + Priority + Accelerated Approval per FDA Appendix B"]),
    ("Blenrep", "belantamab mafodotin-blmf", "2020-08-05", "Relapsed or refractory multiple myeloma",
     "Priority/Accelerated",
     ["GSK plc", "GSK", "NYSE", "GLAXOSMITHKLINE LLC", "Verified - FLAGGED IRREGULARITY (withdrawn)",
      "WITHDRAWN: the confirmatory DREAMM-3 trial failed and GSK withdrew Blenrep from the US "
      "market in Nov 2022 - the accelerated approval was never converted to full approval. First-in-"
      "Class + Orphan + Breakthrough + Priority + Accelerated per FDA Appendix B"]),
    ("Evrysdi", "risdiplam", "2020-08-07", "Spinal muscular atrophy", "Priority",
     ["Roche (Genentech, Inc.)", "RHHBY", "OTC Markets OTCQX", "GENENTECH INC", "Verified",
      "Orphan + Fast Track + Priority per FDA Appendix B"]),
    ("Veklury", "remdesivir", "2020-10-22", "COVID-19", "Priority",
     ["Gilead Sciences, Inc.", "GILD", "NASDAQ", "GILEAD SCIENCES INC", "Verified",
      "First-in-Class + Fast Track + Priority per FDA Appendix B. NOTE: this converted an existing "
      "Emergency Use Authorization into a full approval, so the market reaction is muted and is "
      "confounded by the late-Oct-2020 election-period volatility"]),
    ("Oxlumo", "lumasiran", "2020-11-23", "Primary hyperoxaluria type 1", "Priority",
     ["Alnylam Pharmaceuticals, Inc.", "ALNY", "NASDAQ", "ALNYLAM PHARMS INC", "Verified",
      "First-in-Class + Orphan + Breakthrough + Priority per FDA Appendix B"]),
    ("Imcivree", "setmelanotide", "2020-11-25",
     "Obesity and control of hunger associated with specific enzyme deficiencies incl. POMC deficiency",
     "Priority",
     ["Rhythm Pharmaceuticals, Inc.", "RYTM", "NASDAQ", "RHYTHM", "Verified",
      "First-in-Class + Orphan + Breakthrough + Priority per FDA Appendix B. Largest verified "
      "2020 reaction: +21.1% by the next session (26 Nov was Thanksgiving, so the next tradeable "
      "session was Fri 27 Nov)"]),
]


def main():
    path = "data/fda_decisions_master.csv"
    rows = []
    n = 300
    for brand, generic, date, ind, pathway, meta in ROWS_2020:
        n += 1
        company, ticker, exchange, sponsor, status, notes = meta
        rows.append([f"D{n}", company, ticker, exchange, brand, generic, "Approval", date, ind,
                     pathway, SRC, OPENFDA.format(brand=brand.lower()),
                     status, notes])
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"Appended {len(rows)} 2020 approval rows (D301-D{n}) to {path}")


if __name__ == "__main__":
    main()
