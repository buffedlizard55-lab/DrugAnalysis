# -*- coding: utf-8 -*-
"""
Appends the verified 2021-2023 novel drug approvals (D101-D200) to
data/fda_decisions_master.csv.

Sources (all verified during Sept 2026 agent session):
- data/staging/drugs_base.json   : brand, generic, approval date, application
  number, official label PDF URL, indication - captured from FDA's
  Novel Drug Approvals pages (fda.gov/drugs/novel-drug-approvals-fda/...).
- data/staging/sponsors.json     : current NDA/BLA holder per application
  number - verified via openFDA drugsfda API
  (api.fda.gov/drug/drugsfda.json?count=sponsor_name&search=application_number:"...").
- Original applicants where ownership changed - verified from the original
  approval letters at accessdata.fda.gov/drugsatfda_docs/appletter/.
- Review priority + Accelerated Approval status - verified from FDA's official
  annual "New Drug Therapy Approvals" reports (media/155227 for 2021,
  media/164429 for 2022, media/175253 for 2023), cross-checked against
  Drugs@FDA pages.
- Corporate events (acquisitions, delistings, withdrawals) - verified via
  company press releases / SEC filings / Reuters coverage recorded in the
  session notes of scripts/build_stock_snapshots_2021_2023.py.

Run order: build_fda_master.py (writes D001-D100), then this script
(reads the existing master, appends D101-D200, rewrites the file).
"""
import csv, json, os

HEADER = ["decision_id","company_name","ticker","exchange","drug_brand","drug_generic",
          "decision_type","decision_date","indication","review_pathway",
          "source_url_1","source_url_2","verification_status","notes"]

FDA_PAGES = {
    2021: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2021",
    2022: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2022",
    2023: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2023",
}

# Official FDA annual-report designation lists (verified from the PDF reports).
PRIORITY_2023 = set("Augtyro Columvi Daybue Defencath Elfabrio Elrexfio Epkinly Filspari Filsuvez Fruzaqla Izervay Jaypirca Joenja Lamzede Leqembi Loqtorzi Ogsiveo Orserdu Paxlovid Qalsody Rezzayo Rystiggo Skyclarys Sohonos Talvey Truqap Vanflyta Veopoz Xacduro Zurzuvae Zynyz".split())
AA_2023 = set("Columvi Elrexfio Epkinly Filspari Jaypirca Leqembi Qalsody Talvey Zynyz".split())
PRIORITY_2022 = set("Cibinqo Elahere Elucirem Enjaymo Kimmtrak Lunsumio Lytgobi Opdualag Pluvicto Pyrukynd Relyvrio Spevigo Sunlenca Tecvayli Terlivaz Tzield Vivjoa Vonjo Voquezna Xenpozyme Ztalmy".split())
AA_2022 = set("Elahere Krazati Lunsumio Lytgobi Tecvayli Vonjo".split())
# 2021: all eight drugs tracked here were Priority Review per the 2021 report.
AA_2021 = {"Amondys 45", "Tepmetko", "Ukoniq"}   # note: "Amondys 45" contains a space

# Per-drug verified metadata: company, ticker, exchange, verification status, notes.
# "orig" = original applicant when different from current holder (letter-verified).
META = {
"Verquvo":  ("Merck & Co. (US) / Bayer AG (ex-US)","MRK","NYSE","Verified","Developed by Bayer; Merck & Co. holds US rights"),
"Cabenuva": ("ViiV Healthcare (GSK plc)","GSK","NYSE","Verified","First complete monthly injectable HIV regimen; ViiV is GSK's majority-owned HIV company"),
"Lupkynis": ("Aurinia Pharmaceuticals","AUPH","NASDAQ","Verified","First FDA-approved therapy for lupus nephritis"),
"Tepmetko": ("Merck KGaA (EMD Serono)","MRK.DE","Xetra (Frankfurt); no US ticker","Verified - foreign listing only","Merck KGaA (Darmstadt) is a different company from Merck & Co. (US); no primary US listing"),
"Ukoniq":   ("TG Therapeutics","TGTX","NASDAQ","Verified - FLAGGED IRREGULARITY","Accelerated approval Feb 2021; VOLUNTARILY WITHDRAWN from US market April 2022 after updated UNITY-CL-01 data showed possible increased risk of death - flagged for manual review"),
"Evkeeza":  ("Regeneron Pharmaceuticals","REGN","NASDAQ","Verified",""),
"Cosela":   ("Pharmacosmos Group (current holder) / G1 Therapeutics (applicant at approval)","GTHX","formerly NASDAQ:GTHX, delisted Sep 2024","Verified - FLAGGED IRREGULARITY","G1 Therapeutics acquired by Pharmacosmos (tender closed Sep 2024, $7.15/sh); GTHX delisted so approval-window price data is unavailable on Yahoo"),
"Amondys 45":("Sarepta Therapeutics","SRPT","NASDAQ","Verified","Third Sarepta exon-skipping PMO for Duchenne; accelerated approval"),
"Quviviq":  ("Idorsia Pharmaceuticals","IDIA.SW","SIX Swiss Exchange; no US ticker","Verified - foreign listing only","FDA approval Jan 7 2022; DEA scheduling delayed US launch (FR notice Apr 7 2022 per Drugs@FDA)"),
"Cibinqo":  ("Pfizer","PFE","NYSE","Verified",""),
"Kimmtrak": ("Immunocore Holdings","IMCR","NASDAQ","Verified","First bispecific TCR therapeutic; Orphan drug"),
"Vabysmo":  ("Roche Holding AG (Genentech)","RHHBY","OTC ADR; primary SIX:ROG","Verified",""),
"Enjaymo":  ("Recordati Rare Diseases (current holder) / Bioverativ, a Sanofi company (applicant at approval)","SNY","NASDAQ (Sanofi ADR)","Verified","Original applicant Bioverativ (Sanofi); rare-disease portfolio later divested to Recordati per openFDA sponsor record"),
"Pyrukynd": ("Agios Pharmaceuticals","AGIO","NASDAQ","Verified",""),
"Vonjo":    ("Swedish Orphan Biovitrum, SOBI (current holder) / CTI BioPharma (applicant at approval)","CTIC","formerly NASDAQ:CTIC, delisted 2023","Verified - FLAGGED IRREGULARITY","ACCELERATED APPROVAL; CTI BioPharma acquired by Sobi ($1.7B, closed 2023); CTIC delisted so approval-window price data is unavailable on Yahoo"),
"Ztalmy":   ("Immedica Pharma (current holder) / Marinus Pharmaceuticals (applicant at approval)","MRNS","formerly NASDAQ:MRNS, delisted Feb 2025","Verified - FLAGGED IRREGULARITY","Priority Review Voucher granted at approval (per approval letter); Marinus later acquired by Immedica ($0.55/sh tender, delisted Feb 2025) so approval-window price data is unavailable on Yahoo"),
"Opdualag": ("Bristol Myers Squibb","BMY","NYSE","Verified",""),
"Pluvicto": ("Novartis AG","NVS","NYSE","Verified","Novartis acquired the radioligand program via Advanced Accelerator Applications (2018)"),
"Vivjoa":   ("Mycovia Pharmaceuticals (private)","NO_TICKER","N/A","Verified - no public ticker","Mycovia Pharmaceuticals is privately held"),
"Camzyos":  ("Bristol Myers Squibb","BMY","NYSE","Verified","Asset acquired via MyoKardia buyout (2020)"),
"Voquezna": ("Phathom Pharmaceuticals","PHAT","NASDAQ","Verified",""),
"Mounjaro": ("Eli Lilly and Company","LLY","NYSE","Verified",""),
"Vtama":    ("Organon (current US rights) / Dermavant Sciences, a Roivant company (applicant at approval)","ROIV","NASDAQ (Roivant proxy)","Verified","Applicant at approval was Dermavant (Roivant subsidiary); Organon acquired Dermavant's Vtama US rights in 2024; ROIV used as the listed-equity proxy for the approval reaction"),
"Amvuttra": ("Alnylam Pharmaceuticals","ALNY","NASDAQ","Verified",""),
"Xenpozyme":("Sanofi (Genzyme)","SNY","NASDAQ (Sanofi ADR)","Verified",""),
"Spevigo":  ("Boehringer Ingelheim (private)","NO_TICKER","N/A","Verified - no public ticker","Boehringer Ingelheim is a privately held German company"),
"Daxxify":  ("Revance Therapeutics","RVNC","formerly NASDAQ:RVNC, delisted Feb 2025","Verified - FLAGGED IRREGULARITY","Revance later acquired by Crown Laboratories ($3.65/sh tender, closed Feb 6 2025); RVNC delisted so approval-window price data is unavailable on Yahoo"),
"Sotyktu":  ("Bristol Myers Squibb","BMY","NYSE","Verified",""),
"Rolvedon": ("Assertio Holdings (current holder) / Spectrum Pharmaceuticals (applicant at approval)","SPPI","formerly NASDAQ:SPPI, delisted 2023","Verified - FLAGGED IRREGULARITY","Spectrum acquired by Assertio (0.1783 ASRT/sh + CVR, closed Q3 2023); SPPI delisted so approval-window price data is unavailable on Yahoo"),
"Terlivaz": ("Mallinckrodt Pharmaceuticals","MNK","formerly NYSE:MNK, equity cancelled 2023","Verified - FLAGGED IRREGULARITY","Mallinckrodt's second Chapter 11 (filed Aug 28 2023) cancelled existing equity and NYSE suspended trading; approval-window price data unavailable on Yahoo"),
"Elucirem": ("Guerbet SA","GBT.PA","Euronext Paris; no US ticker","Verified - foreign listing only","Guerbet is listed on Euronext Paris"),
"Omlonti":  ("Ouvex (current holder per openFDA) / Santen Pharmaceutical (applicant at approval)","4536.T","Tokyo Stock Exchange; no US ADR","Verified - foreign listing only","Santen was the original applicant; US rights later transferred to Ouvex per openFDA sponsor record; Santen (4536.T) used for the approval reaction"),
"Relyvrio": ("Amylyx Pharmaceuticals","AMLX","NASDAQ","Verified - FLAGGED IRREGULARITY","VOLUNTARILY WITHDRAWN from US market April 2024 after Phase 3 PHOENIX trial failed primary endpoint - flagged for manual review"),
"Lytgobi":  ("Taiho Oncology (Otsuka Holdings)","4578.T","Tokyo Stock Exchange (parent Otsuka Holdings); no US ADR","Verified - foreign parent listing only","US applicant Taiho Oncology is part of Otsuka Holdings; Otsuka Holdings (4578.T) used as the listed proxy"),
"Imjudo":   ("AstraZeneca","AZN","NASDAQ (ADR)","Verified",""),
"Tecvayli": ("Janssen Biotech (Johnson & Johnson)","JNJ","NYSE","Verified","ACCELERATED APPROVAL"),
"Elahere":  ("AbbVie (current holder) / ImmunoGen (applicant at approval)","IMGN","formerly NASDAQ:IMGN, delisted Feb 2024","Verified - FLAGGED IRREGULARITY","ACCELERATED APPROVAL; ImmunoGen acquired by AbbVie ($10.1B, closed Feb 12 2024); IMGN delisted so approval-window price data is unavailable on Yahoo"),
"Tzield":   ("Sanofi (current holder) / Provention Bio (applicant at approval)","PRVB","formerly NASDAQ:PRVB, delisted 2023","Verified - FLAGGED IRREGULARITY","Provention Bio acquired by Sanofi ($2.9B, 2023); PRVB delisted so approval-window price data is unavailable on Yahoo"),
"Rezlidhia":("Rigel Pharmaceuticals","RIGL","NASDAQ","Verified",""),
"Krazati":  ("Bristol Myers Squibb (current holder) / Mirati Therapeutics (applicant at approval)","MRTX","formerly NASDAQ:MRTX, delisted Jan 2024","Verified - FLAGGED IRREGULARITY","ACCELERATED APPROVAL; Mirati acquired by Bristol Myers Squibb ($5.8B, closed Jan 2024); MRTX delisted so approval-window price data is unavailable on Yahoo"),
"Sunlenca": ("Gilead Sciences","GILD","NASDAQ","Verified",""),
"Lunsumio": ("Roche Holding AG (Genentech)","RHHBY","OTC ADR; primary SIX:ROG","Verified","ACCELERATED APPROVAL"),
"Xenoview": ("Polarean Imaging plc","POL.L","formerly LSE AIM:POL (later POLX), delisted Dec 2025","Verified - FLAGGED IRREGULARITY","Polarean delisted from AIM (Dec 23 2025) and re-registered as a private company; Yahoo no longer serves the approval-window series"),
"Briumvi":  ("TG Therapeutics","TGTX","NASDAQ","Verified",""),
"NexoBrid": ("MediWound","MDWD","NASDAQ (ADS)","Verified",""),
"Leqembi":  ("Eisai (applicant) in partnership with Biogen","4523.T","Tokyo Stock Exchange; no US ADR","Verified - foreign listing primary","ACCELERATED APPROVAL; converted to traditional approval July 2023; Eisai leads development, Biogen co-commercializes"),
"Brenzavvy":("TheracosBio (private)","NO_TICKER","N/A","Verified - no public ticker","TheracosBio is privately held"),
"Jaypirca": ("Eli Lilly and Company (LOXO Oncology at approval)","LLY","NYSE","Verified","ACCELERATED APPROVAL; developed by Loxo Oncology at Lilly (Drugs@FDA shows sponsor LOXO ONCOL)"),
"Orserdu":  ("Stemline Therapeutics (Menarini Group) (private)","NO_TICKER","N/A","Verified - no public ticker","Stemline/Menarini group companies are privately held; Radius Health originated elacestrant"),
"Jesduvroq":("GSK plc","GSK","NYSE","Verified","First oral HIF-PHI approved in the US for anemia of CKD in dialysis-dependent adults"),
"Lamzede":  ("Chiesi Farmaceutici (private)","NO_TICKER","N/A","Verified - no public ticker","Chiesi is a privately held Italian company"),
"Filspari": ("Travere Therapeutics","TVTX","NASDAQ","Verified","ACCELERATED APPROVAL"),
"Skyclarys":("Biogen (current holder) / Reata Pharmaceuticals (applicant at approval)","RETA","formerly NASDAQ:RETA, delisted Sep 2023","Verified - FLAGGED IRREGULARITY","Reata acquired by Biogen ($172.50/sh, ~$7.3B, closed Sep 26 2023); RETA delisted so approval-window price data is unavailable on Yahoo"),
"Zavzpret": ("Pfizer","PFE","NYSE","Verified",""),
"Daybue":   ("Acadia Pharmaceuticals","ACAD","NASDAQ","Verified","First drug approved for Rett syndrome"),
"Zynyz":    ("Incyte Corporation","INCY","NASDAQ","Verified","ACCELERATED APPROVAL"),
"Rezzayo":  ("Mundipharma (current holder) / Cidara Therapeutics (applicant at approval)","CDTX","formerly NASDAQ:CDTX, delisted Jan 2026","Verified - FLAGGED IRREGULARITY","Cidara originated rezafungin; Cidara later acquired by Merck & Co. ($221.50/sh tender, closed Jan 7 2026); CDTX delisted so approval-window price data is unavailable on Yahoo"),
"Joenja":   ("Pharming Group","PHAR","NASDAQ (ADS)","Verified",""),
"Qalsody":  ("Biogen","BIIB","NASDAQ","Verified","ACCELERATED APPROVAL; first therapy targeting a genetic cause (SOD1) of ALS"),
"Elfabrio": ("Chiesi Farmaceutici (applicant; private) with Protalix BioTherapeutics (developer)","PLX","NYSE American (Protalix proxy)","Verified","Chiesi (private) is the applicant; Protalix (PLX) developed and co-commercializes, used as listed-equity proxy"),
"Veozah":   ("Astellas Pharma","4503.T","Tokyo Stock Exchange; no US ADR","Verified - foreign listing primary",""),
"Miebo":    ("Bausch + Lomb","BLCO","NYSE","Verified",""),
"Epkinly":  ("Genmab","GMAB","NASDAQ (ADS)","Verified","ACCELERATED APPROVAL"),
"Xacduro":  ("Innoviva (Entasis Therapeutics, an Innoviva company)","INVA","NASDAQ","Verified","Entasis originated sulbactam-durlobactam; Innoviva is current holder"),
"Paxlovid": ("Pfizer","PFE","NYSE","Verified","First full FDA approval (NDA) of a COVID-19 oral antiviral; previously authorized under EUA"),
"Posluma":  ("Lantheus Holdings (Blue Earth Diagnostics subsidiary)","LNTH","NASDAQ","Verified",""),
"Inpefa":   ("Lexicon Pharmaceuticals","LXRX","NASDAQ","Verified",""),
"Columvi":  ("Roche Holding AG (Genentech)","RHHBY","OTC ADR; primary SIX:ROG","Verified","ACCELERATED APPROVAL"),
"Litfulo":  ("Pfizer","PFE","NYSE","Verified",""),
"Rystiggo": ("UCB","UCB.BR","Euronext Brussels; no US ticker","Verified - foreign listing only",""),
"Ngenla":   ("Pfizer (with OPKO Health partnership)","PFE","NYSE","Verified","Developed under Pfizer's growth-hormone partnership with OPKO Health (NASDAQ:OPK)"),
"Beyfortus":("AstraZeneca","AZN","NASDAQ (ADR)","Verified","Long-acting RSV antibody for infants; commercialized in partnership with Sanofi"),
"Vanflyta": ("Daiichi Sankyo","DSNKY","OTC ADR; primary TYO:4568","Verified - foreign listing primary",""),
"Xdemvy":   ("Tarsus Pharmaceuticals","TARS","NASDAQ","Verified",""),
"Zurzuvae": ("Biogen in partnership with Sage Therapeutics","BIIB","NASDAQ","Verified","Co-developed with Sage Therapeutics (NASDAQ:SAGE); Biogen leads US commercialization"),
"Izervay":  ("Astellas Pharma (current holder) / IVERIC bio (applicant at approval)","ISEE","formerly NASDAQ:ISEE, delisted Jul 2023","Verified - FLAGGED IRREGULARITY","IVERIC bio acquired by Astellas ($5.9B, closed Jul 2023); ISEE delisted so approval-window price data is unavailable on Yahoo"),
"Talvey":   ("Janssen Biotech (Johnson & Johnson)","JNJ","NYSE","Verified","ACCELERATED APPROVAL"),
"Elrexfio": ("Pfizer","PFE","NYSE","Verified","ACCELERATED APPROVAL"),
"Sohonos":  ("Ipsen S.A.","IPN.PA","Euronext Paris; no US ticker","Verified - foreign listing only",""),
"Veopoz":   ("Regeneron Pharmaceuticals","REGN","NASDAQ","Verified",""),
"Aphexda":  ("Ayrmid Pharma (current holder per openFDA) / BioLineRx (applicant at approval)","BLRX","NASDAQ (ADS, BioLineRx proxy)","Verified","BioLineRx was the applicant; US rights later transferred to Ayrmid per openFDA sponsor record; BLRX used for the approval reaction"),
"Ojjaara":  ("GSK plc","GSK","NYSE","Verified","Momelotinib added to GSK via Sierra Oncology acquisition (2022)"),
"Exxua":    ("Fabre Kramer Pharmaceuticals (private)","NO_TICKER","N/A","Verified - no public ticker","Fabre Kramer Pharmaceuticals is privately held"),
"Pombiliti":("Amicus Therapeutics (at approval; later acquired by BioMarin, closed Apr 2026)","FOLD","formerly NASDAQ:FOLD, delisted Apr 2026","Verified - FLAGGED IRREGULARITY","Amicus was independent at approval; BioMarin completed its $14.50/sh acquisition of Amicus in Apr 2026 and FOLD was delisted, so approval-window price data is unavailable on Yahoo"),
"Rivfloza": ("Novo Nordisk","NVO","NYSE (ADR)","Verified",""),
"Velsipity":("Pfizer","PFE","NYSE","Verified",""),
"Zilbrysq": ("UCB","UCB.BR","Euronext Brussels; no US ticker","Verified - foreign listing only","UCB received two novel drug approvals the same day (Zilbrysq and Bimzelx, Oct 17 2023)"),
"Bimzelx":  ("UCB","UCB.BR","Euronext Brussels; no US ticker","Verified - foreign listing only","UCB received two novel drug approvals the same day (Zilbrysq and Bimzelx, Oct 17 2023)"),
"Agamree":  ("Catalyst Pharmaceuticals","CPRX","NASDAQ","Verified - FLAGGED IRREGULARITY","Vamorolone in-licensed from Santhera Pharmaceuticals; Catalyst remains listed (Angelini Pharma acquisition pending 2026) but Yahoo's daily series does not extend back to Oct 2023, so approval-window price data could not be verified"),
"Omvoh":    ("Eli Lilly and Company","LLY","NYSE","Verified",""),
"Loqtorzi": ("Coherus BioSciences (now Coherus Oncology) with partner Junshi Biosciences","CHRS","NASDAQ","Verified","US applicant Coherus; originator Junshi Biosciences (HKEX/SSE:1877) co-developed"),
"Fruzaqla": ("Takeda Pharmaceutical Company","TAK","NYSE (ADR)","Verified","US rights in-licensed from HUTCHMED (NASDAQ/AIM:HCM)"),
"Defencath":("CorMedix","CRMD","NYSE American","Verified",""),
"Augtyro":  ("Bristol Myers Squibb","BMY","NYSE","Verified","Repotrectinib added to BMS via Turning Point Therapeutics acquisition (2022)"),
"Ryzneuta": ("Evive Biotechnology (private)","NO_TICKER","N/A","Verified - no public ticker","Evive Biotechnology is privately held (a subsidiary of Yifan Pharmaceutical)"),
"Truqap":   ("AstraZeneca","AZN","NASDAQ (ADR)","Verified",""),
"Ogsiveo":  ("SpringWorks Therapeutics (at approval; later acquired by Merck KGaA, closed Jul 2025)","SWTX","formerly NASDAQ:SWTX, delisted Jul 2025","Verified - FLAGGED IRREGULARITY","SpringWorks independent at approval; acquired by Merck KGaA ($47/sh, ~$3.9B, closed Jul 1 2025); SWTX delisted so approval-window price data is unavailable on Yahoo"),
"Fabhalta": ("Novartis AG","NVS","NYSE","Verified",""),
"Filsuvez": ("Chiesi Farmaceutici (current holder, private) / Amryt Pharma (applicant at approval)","NO_TICKER","N/A","Verified - no public ticker","Amryt was the applicant (Priority Review Voucher granted per approval letter); Amryt acquired by Chiesi in 2023 - both private at/after approval, no listed equity"),
"Wainua":   ("AstraZeneca (current holder per openFDA) / Ionis Pharmaceuticals (applicant at approval)","IONS","NASDAQ (Ionis proxy)","Verified","Ionis was the US applicant at approval; eplontersen license later held by AstraZeneca AB per openFDA; IONS used for the approval reaction"),
}

def pathway(brand, yr):
    if yr == 2021:
        prio, aa = True, brand in AA_2021          # all 8 tracked 2021 drugs were Priority per FDA 2021 report
    elif yr == 2022:
        prio, aa = brand in PRIORITY_2022, brand in AA_2022
    else:
        prio, aa = brand in PRIORITY_2023, brand in AA_2023
    if aa:
        return "Priority/Accelerated" if prio else "Standard/Accelerated"
    return "Priority" if prio else "Standard"

def main():
    with open("data/staging/drugs_base.json", encoding="utf-8") as f:
        base = json.load(f)["drugs"]
    drugs = [d for d in base if d["yr"] in (2021, 2022, 2023)]
    drugs.sort(key=lambda d: (d["date"], d["brand"]))

    existing = list(csv.DictReader(open("data/fda_decisions_master.csv", encoding="utf-8")))
    assert len(existing) == 100, f"expected 100 existing rows, found {len(existing)}"
    last_id = existing[-1]["decision_id"]
    n = int(last_id[1:])

    rows = [[r[k] for k in HEADER] for r in existing]
    for d in drugs:
        brand = d["brand"]
        company, ticker, exchange, vstatus, notes = META[brand]
        yr = d["yr"]
        pw = pathway(brand, yr)
        aa = pw.endswith("Accelerated")
        n += 1
        rows.append([
            f"D{n:03d}", company, ticker, exchange, brand, d["generic"],
            "Approval (Accelerated)" if aa else "Approval", d["date"], d["ind"], pw,
            d["label"], FDA_PAGES[yr], vstatus, notes,
        ])

    with open("data/fda_decisions_master.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows (D001-D{n:03d}); new: {len(drugs)}")

if __name__ == "__main__":
    main()
