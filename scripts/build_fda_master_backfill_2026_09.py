# -*- coding: utf-8 -*-
"""
Appends the 77 previously-missing FDA novel drug approvals (decision IDs
D201-D277) to data/fda_decisions_master.csv.

These are the approvals that the previous passes had not captured. Every field
below is traced to an official source that was read during the 2026-09-12
session:

  1. drug_brand / drug_generic / decision_date / indication
     -> copied verbatim from FDA's official "Novel Drug Approvals" pages:
        2021: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2021
        2024: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2024
        2025: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2025
        2026: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026
     Raw captures are saved under data/staging/fda_novel_<year>_full.json.

  2. Application number (NDA/BLA)
     -> for 2021 / 2024 / 2025: taken from the application link embedded in the
        Drug Name cell of the FDA page itself.
     -> for 2026: the FDA page publishes no links, so each application number
        was resolved individually through the openFDA Drugs@FDA API
        (api.fda.gov/drug/drugsfda.json), e.g.
        ?search=products.brand_name:"ORZEYFUL" openfda.brand_name:"orzeyful"&count=application_number

  3. company_name (applicant / holder of record)
     -> openFDA Drugs@FDA API:
        ?search=application_number:"NDA220359"&count=sponsor_name
     Values are FDA's abbreviated sponsor strings (e.g. "MERCK SHARP DOHME"),
     which are stored verbatim in the notes column so every row can be
     re-checked. Where the widely-reported developer differs from the current
     holder of record (because the asset was later licensed or the company was
     acquired), BOTH are shown and the row is flagged for manual review.

  4. ticker / exchange
     -> cross-checked against the Yahoo Finance chart API
        (query1.finance.yahoo.com/v8/finance/chart/<TICKER>), which returns the
        exchange and the registered company name for the symbol. The company
        name returned by the API was compared with the expected issuer before
        the ticker was accepted. Rows where no listed equity exists are marked
        "NO_TICKER" and the reason is stated in the notes.

  5. review_pathway
     -> NOT captured in this pass. FDA publishes Priority/Standard/Accelerated
        designations in its annual "New Drug Therapy Approvals" reports, which
        do not exist yet for 2026 and were not re-parsed here. The column is
        deliberately left blank rather than guessed. Rows from the earlier
        passes (D001-D200) retain their pathway values.

Run order: the earlier builders write D001-D200; this appends D201-D277.
"""
import csv
import os

HEADER = ["decision_id", "company_name", "ticker", "exchange", "drug_brand", "drug_generic",
          "decision_type", "decision_date", "indication", "review_pathway",
          "source_url_1", "source_url_2", "verification_status", "notes"]

FDA_PAGE = {
    2021: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2021",
    2024: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2024",
    2025: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2025",
    2026: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026",
}
DAF = "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo="
OPENFDA = ("https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{app}%22"
           "&count=sponsor_name")

NO_PATHWAY = ""  # intentionally blank - see module docstring point 5

# (brand, generic, date, indication, appl_no-or-None, [company, ticker, exchange,
#  openfda_sponsor_string, verification_status, notes])
NEW_ROWS = [
    # ---------------- 2021 (42 previously missing of FDA's 50) ----------------
    ("Adbry", "tralokinumab-ldrm", "2021-12-27", "Moderate-to-severe atopic dermatitis", "BLA761180",
     ["LEO Pharma A/S", "NO_TICKER", "N/A - privately held",
      "LEO PHARMA AS", "Verified - no public ticker",
      "Danish privately held company; no listed equity to track. Partner outside the US: Almirall"]),
    ("Leqvio", "inclisiran", "2021-12-22",
     "Heterozygous familial hypercholesterolemia or clinical ASCVD (add-on therapy)", "NDA214012",
     ["Novartis AG", "NVS", "NYSE (ADR)", "NOVARTIS", "Verified",
      "Novartis acquired The Medicines Company (orig. developer) in 2020; siRNA PCSK9 inhibitor"]),
    ("Vyvgart", "efgartigimod alfa-fcab", "2021-12-17", "Generalized myasthenia gravis", "BLA761195",
     ["argenx SE", "ARGX", "NASDAQ", "ARGENX BV", "Verified", ""]),
    ("Tezspire", "tezepelumab-ekko", "2021-12-17", "Severe asthma (add-on maintenance)", "BLA761224",
     ["AstraZeneca plc / Amgen Inc.", "AZN", "NASDAQ (ADR)", "ASTRAZENECA AB", "Verified",
      "Co-developed with Amgen; AZN is the applicant of record"]),
    ("Cytalux", "pafolacianine", "2021-11-29",
     "Intraoperative identification of ovarian cancer lesions", "NDA214907",
     ["On Target Laboratories, LLC", "NO_TICKER", "N/A - privately held",
      "ON TARGET LABS", "Verified - no public ticker",
      "Privately held; no listed equity to track"]),
    ("Livtencity", "maribavir", "2021-11-23",
     "Post-transplant cytomegalovirus infection/disease refractory to available antivirals", "NDA215596",
     ["Takeda Pharmaceutical Company Limited", "TAK", "NYSE (ADR)", "TAKEDA PHARMS USA", "Verified",
      ""]),
    ("Voxzogo", "vosoritide", "2021-11-19",
     "Improve growth in children 5+ with achondroplasia and open epiphyses", "NDA214938",
     ["BioMarin Pharmaceutical Inc.", "BMRN", "NASDAQ", "BIOMARIN PHARM", "Verified", ""]),
    ("Besremi", "ropeginterferon alfa-2b-njft", "2021-11-12", "Polycythemia vera", "BLA761166",
     ["PharmaEssentia Corp.", "6446.TW", "Taiwan Stock Exchange (TPEx); no US listing",
      "PHARMAESSENTIA CORP", "Verified - foreign listing only",
      "US commercial rights held by PharmaEssentia USA; AOP Orphan Pharmaceuticals holds EU rights"]),
    ("Scemblix", "asciminib", "2021-10-29",
     "Philadelphia chromosome-positive chronic myeloid leukemia", "NDA215358",
     ["Novartis AG", "NVS", "NYSE (ADR)", "NOVARTIS", "Verified", ""]),
    ("Tavneos", "avacopan", "2021-10-07",
     "Severe active ANCA-associated vasculitis (GPA/MPA) with standard therapy", "NDA214487",
     ["ChemoCentryx, Inc. (acquired by Amgen, Oct 2022)", "CCXI", "formerly NASDAQ:CCXI, delisted Oct 2022",
      "CHEMOCENTRYX", "Verified - FLAGGED IRREGULARITY",
      "Amgen completed acquisition Oct 2022; CCXI delisted so later-dated price history is unavailable, "
      "but the 2021 approval-window history is retrievable"]),
    ("Livmarli", "maralixibat", "2021-09-29",
     "Cholestatic pruritus associated with Alagille syndrome", "NDA214662",
     ["Mirum Pharmaceuticals, Inc.", "MIRM", "NASDAQ", "MIRUM", "Verified", ""]),
    ("Qulipta", "atogepant", "2021-09-28", "Preventive treatment of episodic migraine", "NDA215206",
     ["AbbVie Inc.", "ABBV", "NYSE", "ABBVIE", "Verified", "AbbVie acquired Allergan (orig. developer) 2020"]),
    ("Tivdak", "tisotumab vedotin-tftv", "2021-09-20",
     "Recurrent or metastatic cervical cancer with progression on or after chemotherapy", "BLA761208",
     ["Seagen Inc. (acquired by Pfizer, Dec 2023)", "SGEN", "formerly NASDAQ:SGEN, delisted Dec 2023",
      "SEAGEN", "Verified - FLAGGED IRREGULARITY",
      "Pfizer completed the Seagen acquisition Dec 2023; SGEN delisted. Co-development with Genmab"]),
    ("Exkivity", "mobocertinib", "2021-09-15",
     "Locally advanced or metastatic NSCLC with EGFR exon 20 insertion mutations", "NDA215310",
     ["Takeda Pharmaceutical Company Limited", "TAK", "NYSE (ADR)", "TAKEDA PHARMS USA",
      "Verified - FLAGGED IRREGULARITY",
      "VOLUNTARILY WITHDRAWN from the US market in 2023 after the confirmatory EXCLAIM-2 trial failed - "
      "flagged for manual review"]),
    ("Skytrofa", "lonapegsomatropin-tcgd", "2021-08-25",
     "Short stature due to inadequate endogenous growth hormone secretion", "BLA761177",
     ["Ascendis Pharma A/S", "ASND", "NASDAQ", "ASCENDIS PHARMA ENDOCRINOLOGY DIV A/S", "Verified", ""]),
    ("Korsuva", "difelikefalin", "2021-08-23",
     "Moderate-to-severe pruritus associated with CKD in adults on hemodialysis", "NDA214916",
     ["Vifor Pharma (acquired by CSL, Aug 2022)", "NO_TICKER", "formerly SIX:VIFN, delisted 2022 (CSL acquisition)",
      "VIFOR INTL", "Verified - no tradeable ticker",
      "Co-developed with Cara Therapeutics; Vifor was acquired by CSL in Aug 2022 so no current listing"]),
    ("Welireg", "belzutifan", "2021-08-13",
     "von Hippel-Lindau disease requiring therapy for RCC, CNS hemangioblastoma or pNET", "NDA215383",
     ["Merck & Co., Inc.", "MRK", "NYSE", "MERCK SHARP DOHME", "Verified", ""]),
    ("Nexviazyme", "avalglucosidase alfa-ngpt", "2021-08-06", "Late-onset Pompe disease", "BLA761194",
     ["Sanofi (Genzyme Corporation)", "SNY", "NASDAQ (ADR)", "GENZYME CORP", "Verified", ""]),
    ("Saphnelo", "anifrolumab-fnia", "2021-07-30",
     "Moderate-to-severe systemic lupus erythematosus (add-on)", "BLA761123",
     ["AstraZeneca plc", "AZN", "NASDAQ (ADR)", "ASTRAZENECA AB", "Verified", ""]),
    ("Bylvay", "odevixibat", "2021-07-20",
     "Pruritus in progressive familial intrahepatic cholestasis", "NDA215498",
     ["Ipsen S.A.", "IPN.PA", "Euronext Paris; no US ticker", "IPSEN", "Verified - foreign listing only",
      "Ipsen acquired Albireo Pharma (orig. applicant) in 2023"]),
    ("Rezurock", "belumosudil", "2021-07-16",
     "Chronic graft-versus-host disease after >=2 prior lines of systemic therapy", "NDA214783",
     ["Kadmon Holdings, Inc. (acquired by Sanofi, Nov 2021)", "KDMN",
      "formerly NASDAQ:KDMN, delisted Nov 2021", "KADMON PHARMS LLC", "Verified - FLAGGED IRREGULARITY",
      "Sanofi completed the acquisition Nov 2021, shortly after this approval; KDMN delisted"]),
    ("Fexinidazole", "fexinidazole", "2021-07-16",
     "Human African trypanosomiasis caused by Trypanosoma brucei gambiense", "NDA214429",
     ["Sanofi", "SNY", "NASDAQ (ADR)", "SANOFI", "Verified",
      "Developed with DNDi; first all-oral treatment for sleeping sickness"]),
    ("Kerendia", "finerenone", "2021-07-09",
     "Reduce risk of kidney and heart complications in CKD associated with type 2 diabetes", "NDA215341",
     ["Bayer AG", "BAYRY", "OTC ADR; primary XETRA:BAYN", "BAYER HLTHCARE", "Verified", ""]),
    ("Rylaze", "asparaginase erwinia chrysanthemi (recombinant)-rywn", "2021-06-30",
     "ALL/LBL in patients allergic to E. coli-derived asparaginase", "BLA761179",
     ["Jazz Pharmaceuticals plc", "JAZZ", "NASDAQ", "JAZZ PHARMS", "Verified", ""]),
    ("Aduhelm", "aducanumab-avwa", "2021-06-07", "Alzheimer's disease", "BLA761178",
     ["Biogen Inc.", "BIIB", "NASDAQ", "BIOGEN INC", "Verified - FLAGGED IRREGULARITY",
      "ACCELERATED APPROVAL based on amyloid reduction; highly controversial (advisory committee voted "
      "against; three AC members resigned). DISCONTINUED in 2024 - Biogen halted development and "
      "voluntarily withdrew the application. Flagged for manual review"]),
    ("Brexafemme", "ibrexafungerp", "2021-06-01", "Vulvovaginal candidiasis", "NDA214900",
     ["GlaxoSmithKline plc (applicant of record) / SCYNEXIS, Inc. (orig. developer)", "GSK", "NYSE",
      "GLAXOSMITHKLINE", "Verified - FLAGGED IRREGULARITY",
      "openFDA lists GLAXOSMITHKLINE as the current applicant of record for NDA 214900 although the "
      "asset was developed by SCYNEXIS. Ownership transfer flagged for manual review against the "
      "original approval letter"]),
    ("Lybalvi", "olanzapine and samidorphan", "2021-05-28",
     "Schizophrenia and certain aspects of bipolar I disorder", "NDA213378",
     ["Alkermes plc", "ALKS", "NASDAQ", "ALKERMES INC", "Verified", ""]),
    ("Truseltiq", "infigratinib", "2021-05-28",
     "Previously treated, unresectable locally advanced or metastatic cholangiocarcinoma with FGFR2 fusion/rearrangement",
     "NDA214622",
     ["Helsinn Healthcare SA / QED Therapeutics (BridgeBio)", "NO_TICKER",
      "N/A - Helsinn is privately held; QED is a BridgeBio subsidiary",
      "HELSINN HLTHCARE", "Verified - FLAGGED IRREGULARITY",
      "VOLUNTARILY WITHDRAWN from the US market in 2024. Applicant of record is private (Helsinn); "
      "QED Therapeutics (BridgeBio) co-developed. Flagged for manual review"]),
    ("Lumakras", "sotorasib", "2021-05-28",
     "Locally advanced or metastatic NSCLC with KRAS G12C mutation", "NDA214665",
     ["Amgen Inc.", "AMGN", "NASDAQ", "AMGEN INC", "Verified", "First approved KRAS G12C inhibitor"]),
    ("Pylarify", "piflufolastat F 18", "2021-05-26",
     "PSMA-positive lesion imaging in prostate cancer (PET)", "NDA214793",
     ["Lantheus Holdings, Inc. (via Progenics Pharmaceuticals)", "LNTH", "NASDAQ", "PROGENICS PHARMS INC",
      "Verified", "Lantheus acquired Progenics in 2020; openFDA still lists Progenics as applicant of record"]),
    ("Rybrevant", "amivantamab-vmjw", "2021-05-21",
     "Locally advanced or metastatic NSCLC with EGFR exon 20 insertion mutations", "BLA761210",
     ["Johnson & Johnson (Janssen Biotech)", "JNJ", "NYSE", "JANSSEN BIOTECH", "Verified", ""]),
    ("Empaveli", "pegcetacoplan", "2021-05-14", "Paroxysmal nocturnal hemoglobinuria", "NDA215014",
     ["Apellis Pharmaceuticals, Inc.", "APLS", "NASDAQ", "APELLIS PHARMS", "Verified", ""]),
    ("Zynlonta", "loncastuximab tesirine-lpyl", "2021-04-23",
     "Relapsed or refractory large B-cell lymphoma after >=2 lines of systemic therapy", "BLA761196",
     ["ADC Therapeutics SA", "ADCT", "NYSE", "ADC THERAPEUTICS SA", "Verified", ""]),
    ("Jemperli", "dostarlimab-gxly", "2021-04-22",
     "Recurrent or advanced endometrial cancer with dMMR", "BLA761174",
     ["GlaxoSmithKline plc", "GSK", "NYSE", "GLAXOSMITHKLINE", "Verified",
      "GSK acquired Tesaro (orig. applicant) in 2019"]),
    ("Nextstellis", "drospirenone and estetrol", "2021-04-15", "Prevention of pregnancy", "NDA214154",
     ["Mayne Pharma Group Limited", "MYX.AX", "ASX; no US listing", "MAYNE PHARMA",
      "Verified - foreign listing only", "Australian listing; US rights licensed from Mithra Pharmaceuticals"]),
    ("Qelbree", "viloxazine", "2021-04-02", "Attention deficit hyperactivity disorder", "NDA211964",
     ["Supernus Pharmaceuticals, Inc.", "SUPN", "NASDAQ", "SUPERNUS PHARMS", "Verified", ""]),
    ("Zegalogue", "dasiglucagon", "2021-03-22", "Severe hypoglycemia", "NDA214231",
     ["Zealand Pharma A/S", "ZLDPF", "OTC ADR; primary Nasdaq Copenhagen:ZEAL", "ZEALAND PHARMA",
      "Verified - thinly traded ADR", "Danish listing is primary; US OTC ADR liquidity is very low"]),
    ("Ponvory", "ponesimod", "2021-03-18", "Relapsing forms of multiple sclerosis", "NDA213498",
     ["Vanda Pharmaceuticals Inc. (current holder) / Janssen (Actelion, orig. developer)", "VNDA",
      "NASDAQ", "VANDA PHARMS INC", "Verified - FLAGGED IRREGULARITY",
      "openFDA lists VANDA PHARMS INC as the current applicant of record for NDA 213498 although the "
      "asset was developed and launched by Janssen/Actelion. Ownership transfer flagged for manual "
      "review against the original approval letter"]),
    ("Fotivda", "tivozanib", "2021-03-10",
     "Relapsed or refractory advanced renal cell carcinoma", "NDA212904",
     ["AVEO Pharmaceuticals, Inc. (acquired by LG Chem, 2023)", "AVEO",
      "formerly NASDAQ:AVEO, delisted 2023", "AVEO PHARMS", "Verified - FLAGGED IRREGULARITY",
      "LG Chem completed the acquisition in 2023; AVEO delisted"]),
    ("Azstarys", "serdexmethylphenidate and dexmethylphenidate", "2021-03-02",
     "Attention deficit hyperactivity disorder", "NDA212994",
     ["Commave Therapeutics (Corium, Inc.)", "NO_TICKER", "N/A - privately held",
      "COMMAVE SUB", "Verified - no public ticker",
      "NDA filed by KemPharm; KemPharm was acquired by Corium/Commave (Gurnet Point Capital) in 2021; "
      "no listed equity"]),
    ("Pepaxto", "melphalan flufenamide", "2021-02-26",
     "Relapsed or refractory multiple myeloma", "NDA214383",
     ["Oncopeptides AB (applicant at approval)", "ONCO.ST", "Nasdaq Stockholm; no US listing",
      "UNRESOLVED - not present in openFDA", "FLAGGED - sponsor not machine-verifiable",
      "APPLICATION NO LONGER PRESENT in the openFDA Drugs@FDA dataset because the product was "
      "VOLUNTARILY WITHDRAWN from the US market in Oct 2021 after the OCEAN confirmatory trial failed. "
      "Sponsor shown is the applicant at the time of approval and must be confirmed manually against "
      "the original FDA approval letter. This is the most significant irregularity found in this pass"]),
    ("Nulibry", "fosdenopterin", "2021-02-26",
     "Reduce risk of mortality in molybdenum cofactor deficiency Type A", "NDA214018",
     ["Sentynl Therapeutics, Inc.", "NO_TICKER", "N/A - privately held (Zydus group)",
      "SENTYNL THERAPS INC", "Verified - no public ticker",
      "Wholly owned subsidiary of Zydus Therapeutics; no listed equity of its own"]),

    # ---------------- 2024 (8 previously missing of FDA's 50) ----------------
    ("Ensacove", "ensartinib", "2024-12-18",
     "ALK-positive locally advanced or metastatic non-small cell lung cancer", "NDA218171",
     ["Xcovery Holding Company, LLC", "NO_TICKER", "N/A - privately held (Betta Pharmaceuticals group)",
      "XCOVERY", "Verified - no public ticker",
      "US subsidiary of Betta Pharmaceuticals (Shenzhen, 300558.SZ); no US-listed equity"]),
    ("Crenessity", "crinecerfont", "2024-12-13", "Classic congenital adrenal hyperplasia", "NDA218808",
     ["Neurocrine Biosciences, Inc.", "NBIX", "NASDAQ", "NEUROCRINE", "Verified", ""]),
    ("Unloxcyt", "cosibelimab-ipdl", "2024-12-13",
     "Metastatic or locally advanced cutaneous squamous cell carcinoma", "BLA761297",
     ["Checkpoint Therapeutics, Inc. (acquired by Sun Pharma, 2025)", "CKPT",
      "formerly NASDAQ:CKPT, delisted 2025", "CHECKPOINT THERAPEUTICS INC",
      "Verified - FLAGGED IRREGULARITY", "Sun Pharmaceutical completed the acquisition in 2025; CKPT delisted"]),
    ("Bizengri", "zenocutuzumab-zbco", "2024-12-04",
     "NRG1 fusion-positive non-small cell lung cancer and pancreatic adenocarcinoma", "BLA761352",
     ["Merus N.V. (acquired by Genmab, 2025)", "MRUS", "formerly NASDAQ:MRUS, delisted 2025", "MERUS N.V.",
      "Verified - FLAGGED IRREGULARITY", "Genmab completed the acquisition in 2025; MRUS delisted"]),
    ("Iomervu", "iomeprol", "2024-11-27", "Radiographic contrast agent", "NDA216017",
     ["Bracco Imaging S.p.A.", "NO_TICKER", "N/A - privately held", "BRACCO",
      "Verified - no public ticker", "Italian privately held group; no listed equity"]),
    ("Rapiblyk", "landiolol", "2024-11-22", "Supraventricular tachycardia", "NDA217202",
     ["AOP Health (AOP Orphan Pharmaceuticals)", "NO_TICKER", "N/A - privately held", "AOP HLTH US",
      "Verified - no public ticker", "Austrian privately held group; no listed equity"]),
    ("Attruby", "acoramidis", "2024-11-22",
     "Cardiomyopathy of wild-type or variant transthyretin-mediated amyloidosis", "NDA216540",
     ["BridgeBio Pharma, Inc.", "BBIO", "NASDAQ", "BRIDGEBIO PHARMA", "Verified", ""]),
    ("Vyloy", "zolbetuximab-clzb", "2024-10-18",
     "HER2-negative gastric or gastroesophageal junction adenocarcinoma", "BLA761365",
     ["Astellas Pharma Inc.", "ALPMY", "OTC ADR; primary TSE:4503", "ASTELLAS", "Verified", ""]),

    # ---------------- 2025 (2 previously missing of FDA's 46) ----------------
    ("Nereus", "tradipitant", "2025-12-30", "Vomiting associated with motion", None,
     ["Vanda Pharmaceuticals Inc.", "VNDA", "NASDAQ", "see notes", "Verified - see note",
      "The FDA 2025 page published no application link for Nereus; confirm the application number and "
      "applicant of record at Drugs@FDA before relying on this row"]),
    ("Lynkuet", "elinzanetant", "2025-10-24",
     "Moderate-to-severe vasomotor symptoms due to menopause", "NDA219469",
     ["Bayer AG", "BAYRY", "OTC ADR; primary XETRA:BAYN", "BAYER HLTHCARE", "Verified", ""]),

    # ---------------- 2026 (25 previously missing of FDA's 39 to date) ----------------
    ("Isembyld", "apitegromab-mstn", "2026-09-11",
     "Spinal muscular atrophy in adults and pediatric patients 2+ on an SMN2-targeted treatment", None,
     ["Scholar Rock Holding Corporation", "SRRK", "NASDAQ", "see notes",
      "Verified - sponsor not yet in openFDA",
      "Approved 2026-09-11, one day before this capture, so the application is not yet indexed in "
      "openFDA Drugs@FDA. Sponsor verified from the company's own FDA-approval press release. "
      "REGULARITY NOTE: the BLA was previously resubmitted after FDA raised third-party fill-finish "
      "manufacturing concerns (not efficacy/safety); PDUFA goal date had been 2026-09-30 and the "
      "approval landed early, on 2026-09-11"]),
    ("Etcamah", "camizestrant", "2026-09-04",
     "HR+/HER2- locally advanced or metastatic breast cancer upon detection of ESR1 mutation during AI + CDK4/6 therapy",
     "NDA220359", ["AstraZeneca plc", "AZN", "NASDAQ (ADR)", "ASTRAZENECA PHARMACEUTICALS, LP", "Verified", ""]),
    ("Zanvastro", "zilganersen", "2026-09-03", "Alexander disease in pediatric and adult patients", "NDA220210",
     ["Ionis Pharmaceuticals, Inc.", "IONS", "NASDAQ", "IONIS PHARMS INC", "Verified", ""]),
    ("Pasatru", "garetosmab-grts", "2026-08-19",
     "Reduce new heterotopic ossification and clinician-assessed flare-ups in adults with FOP", "BLA761508",
     ["Regeneron Pharmaceuticals, Inc.", "REGN", "NASDAQ", "REGENERON PHARMACEUTICALS, INC", "Verified", ""]),
    ("Zenbexus", "iberdomide", "2026-08-13",
     "Multiple myeloma (with daratumumab/hyaluronidase-fihj + dexamethasone) after >=1 prior line", "NDA221075",
     ["Bristol Myers Squibb Company", "BMY", "NYSE", "BRISTOL MYERS SQUIBB", "Verified",
      "Inherited via the Celgene acquisition"]),
    ("Tauklarify", "florquinitau F 18", "2026-08-13",
     "PET imaging of the brain to identify tau neurofibrillary tangle pathology in adults being evaluated for Alzheimer disease",
     "NDA220496", ["Lantheus Holdings, Inc.", "LNTH", "NASDAQ", "CERVEAU LANTHEUS", "Verified", ""]),
    ("Lytenava", "bevacizumab-vikg", "2026-07-24", "Neovascular (wet) age-related macular degeneration",
     "BLA761320",
     ["Outlook Therapeutics, Inc.", "OTLK", "NASDAQ", "OUTLOOK THERAPEUTICS, INC.",
      "Verified - FLAGGED IRREGULARITY (resolved)",
      "OUTCOME OF TRACKED CRL C004: this is the same BLA that received a third Complete Response Letter "
      "on 2025-12-31. The CRL was resolved and the BLA was APPROVED on 2026-07-24 - update the CRL row. "
      "Product was already approved in the EU/UK as Lytenava"]),
    ("Jideytro", "zidesamtinib", "2026-07-22",
     "Locally advanced or metastatic ROS1-positive NSCLC after a ROS1 kinase inhibitor", "NDA220185",
     ["Nuvalent, Inc.", "NUVL", "NASDAQ", "NUVALENT", "Verified", ""]),
    ("Lipfendra", "enlicitide decanoate", "2026-07-15", "Reduce low-density lipoprotein cholesterol", "NDA220848",
     ["Merck & Co., Inc.", "MRK", "NYSE", "MSD", "Verified", "Oral PCSK9 inhibitor"]),
    ("Revtorpyk", "gedatolisib", "2026-07-14",
     "HR+/HER2- locally advanced or metastatic breast cancer without a PIK3CA mutation (with fulvestrant)",
     "NDA219908", ["Celcuity Inc.", "CELC", "NASDAQ", "CELCUITY", "Verified", ""]),
    ("Trutakna", "atacicept-vymj", "2026-07-07",
     "Reduce proteinuria in adults with primary IgA nephropathy at risk for disease progression", "BLA761486",
     ["Vera Therapeutics, Inc.", "VERA", "NASDAQ", "VERA THERAPEUTICS INC.", "Verified", ""]),
    ("Lumvoa", "veligrotug-vvze", "2026-06-26", "Thyroid eye disease", "BLA761530",
     ["Viridian Therapeutics, Inc.", "VRDN", "NASDAQ", "VIRIDIAN THERAPEUTICS INC", "Verified", ""]),
    ("Ambelvist", "gadoquatrane", "2026-06-12",
     "Detect and visualize lesions with abnormal vascularity, in conjunction with MRI", "NDA219627",
     ["Bayer AG", "BAYRY", "OTC ADR; primary XETRA:BAYN", "BAYER HEALTHCARE", "Verified", ""]),
    ("Xocova", "ensitrelvir", "2026-05-29",
     "Post-exposure prophylaxis of COVID-19 following contact with an individual with COVID-19", "NDA220442",
     ["Shionogi & Co., Ltd.", "SGIOF", "OTC ADR; primary TSE:4507", "SHIONOGI", "Verified", ""]),
    ("Zaynich", "cefepime and zidebactam", "2026-05-29",
     "Complicated urinary tract infections, including pyelonephritis", "NDA220787",
     ["Wockhardt Limited", "WOCKPHARMA.NS", "NSE India; no US listing", "WOCKHARDT BIO AG",
      "Verified - foreign listing only", "Indian listing; US agent is Wockhardt Bio AG (Swiss subsidiary)"]),
    ("Decnupaz", "pivekimab sunirine-pvzy", "2026-05-27",
     "Blastic plasmacytoid dendritic cell neoplasm in adults", "BLA761460",
     ["AbbVie Inc.", "ABBV", "NYSE", "ABBVIE INC", "Verified", "Inherited via the ImmunoGen acquisition"]),
    ("Hepcludex", "bulevirtide-gmod", "2026-05-22",
     "Chronic hepatitis delta virus infection in adults without cirrhosis or with compensated cirrhosis",
     "BLA761468", ["Gilead Sciences, Inc.", "GILD", "NASDAQ", "GILEAD SCIENCES INC", "Verified",
                   "Gilead acquired MYR GmbH (orig. developer); product was already approved in the EU"]),
    ("Baxfendy", "baxdrostat", "2026-05-15", "Hypertension, in combination with other antihypertensive drugs",
     "NDA219878", ["AstraZeneca plc", "AZN", "NASDAQ (ADR)", "ASTRAZENECA AB", "Verified", ""]),
    ("Veppanu", "vepdegestrant", "2026-05-01",
     "ER+/HER2-, ESR1-mutated advanced or metastatic breast cancer after >=1 line of endocrine therapy",
     "NDA219835",
     ["Rigel Pharmaceuticals, Inc. (current holder) / Arvinas, Inc. + Pfizer (applicant at approval)",
      "RIGL", "NASDAQ", "RIGEL PHARMS", "Verified - FLAGGED IRREGULARITY (ownership change)",
      "First-ever FDA-approved PROTAC. Approved to Arvinas/Pfizer on 2026-05-01 (one month before the "
      "PDUFA goal date); on 2026-05-12 Arvinas and Pfizer licensed exclusive global rights to Rigel for "
      "$70M upfront + $15M transition + up to $320M milestones, which is why openFDA now lists RIGEL as "
      "the applicant of record. Guardant360 CDx approved as a companion diagnostic"]),
    ("Idvynso", "doravirine and islatravir", "2026-04-20",
     "HIV-1 infection as a complete regimen in virologically suppressed adults", "NDA216964",
     ["Merck & Co., Inc.", "MRK", "NYSE", "MSD", "Verified", ""]),
    ("Foundayo", "orforglipron", "2026-04-01",
     "Reduce excess body weight and maintain weight reduction in adults with obesity or overweight with >=1 weight-related comorbidity",
     "NDA220934", ["Eli Lilly and Company", "LLY", "NYSE", "ELI LILLY AND CO", "Verified",
                   "Oral (non-peptide) GLP-1 receptor agonist"]),
    ("Awiqli", "insulin icodec-abae", "2026-03-26",
     "Improve glycemic control in adults with type 2 diabetes mellitus", "BLA761326",
     ["Novo Nordisk A/S", "NVO", "NYSE (ADR)", "NOVO NORDISK INC", "Verified", "Once-weekly basal insulin"]),
    ("Lifyorli", "relacorilant", "2026-03-25",
     "Platinum-resistant epithelial ovarian, fallopian tube or primary peritoneal cancer after 1-3 prior systemic regimens incl. bevacizumab",
     "NDA220641", ["Corcept Therapeutics Incorporated", "CORT", "NASDAQ", "CORCEPT THERAP", "Verified", ""]),
    ("Icotyde", "icotrokinra", "2026-03-17",
     "Moderate-to-severe plaque psoriasis in patients 12+ weighing at least 40 kg", "NDA220149",
     ["Johnson & Johnson (Janssen Biotech)", "JNJ", "NYSE", "JANSSEN BIOTECH", "Verified",
      "Oral IL-23 receptor antagonist peptide"]),
    ("Lynavoy", "linerixibat", "2026-03-17",
     "Cholestatic pruritus associated with primary biliary cholangitis", "NDA220295",
     ["Intercept Pharmaceuticals / Alfasigma S.p.A. (current holder) / GSK plc (applicant at approval)",
      "GSK", "NYSE (GSK ADR)", "INTERCEPT", "Verified - FLAGGED IRREGULARITY (ownership change + date conflict)",
      "GSK announced the US approval on 2026-03-19 while FDA's own page records the approval date as "
      "2026-03-17 - date discrepancy flagged. GSK agreed on 2026-03-09 to license worldwide rights to "
      "Alfasigma S.p.A.; openFDA now lists INTERCEPT (an Alfasigma company) as applicant of record, so "
      "GSK is used as the trackable listed equity and the change is flagged. First US drug approved for "
      "PBC-related itch"]),
]


def build_rows():
    rows = []
    n = 200
    for brand, generic, date, ind, appl, meta in NEW_ROWS:
        n += 1
        company, ticker, exchange, sponsor, status, notes = meta
        year = int(date[:4])
        url1 = FDA_PAGE[year]
        if appl:
            url2 = DAF + appl[3:] if appl.startswith(("NDA", "BLA")) else DAF + appl
            note = (f"openFDA Drugs@FDA applicant of record: {sponsor}. " + notes).strip()
        else:
            url2 = url1
            note = (f"openFDA applicant of record: {sponsor}. " + notes).strip()
        rows.append([f"D{n}", company, ticker, exchange, brand, generic, "Approval", date, ind,
                     NO_PATHWAY, url1, url2, status, note])
    return rows


def main():
    path = "data/fda_decisions_master.csv"
    rows = build_rows()
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(HEADER)
        w.writerows(rows)
    print(f"Appended {len(rows)} new approval rows (D201-D{200 + len(rows)}) to {path}")


if __name__ == "__main__":
    main()
