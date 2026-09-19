#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expand the verified pre-1985 decision table backward through 1980.

v14 (2026-09-18) consumes only the committed openFDA Drugs@FDA extracts in
``data/raw/openfda_orig_decisions_1980_1984``.  It adds every TYPE 1/1-4
ORIG/AP application enumerated by those extracts for 1980, 1981, and 1982,
re-homes Hylorel from the v13 1983 boundary group to its actual 1982 approval
year, and regenerates the year-by-year era file.

The payload is authoritative for application number, date, product, chemical
type and review priority.  Human-readable indications, historical applicants,
and corporate lineage are kept as separately cited metadata.  Where an
approval-era label or original applicant could not be pinned, the row says so
explicitly; it never substitutes a guessed ticker or an unqualified current
label claim.

This builder is deliberately idempotent.  It can be rerun after v14 has
already been built, and it will replace the v14 rows rather than duplicate
them.  It aborts before writing if the committed payloads do not support the
expected enumeration or any derived row field.
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
RAW = DATA / "raw" / "openfda_orig_decisions_1980_1984"
DRUGSFDA = (
    "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
    "?event=overview.process&varApplNo={num}"
)
OPENFDA_Q = (
    "https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{appl}%22"
)

PAYLOAD_YEARS = (1980, 1981, 1982, 1983, 1984)


def load_payload(year: int) -> dict[str, dict]:
    path = RAW / f"decisions_{year}.json"
    if not path.exists():
        raise SystemExit(f"missing committed payload: {path}")
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload.get("decisions"), list):
        raise SystemExit(f"invalid payload shape: {path}")
    return {row["application_number"]: row for row in payload["decisions"]}


PAYLOADS = {year: load_payload(year) for year in PAYLOAD_YEARS}
ALL_PAYLOADS: dict[str, dict] = {}
for _year in PAYLOAD_YEARS:
    for _app, _row in PAYLOADS[_year].items():
        if _app in ALL_PAYLOADS:
            raise SystemExit(f"duplicate application across payload years: {_app}")
        ALL_PAYLOADS[_app] = _row


# Metadata that cannot safely be inferred from the Drugs@FDA extract.  The
# builder below derives all regulatory fields from the payload and asserts the
# product brand against the aliases here.
V14_META = [
    # ------------------------------------------------------------------ 1980
    {
        "appl": "NDA018299", "brand": "Viroptic", "aliases": ["VIROPTIC"],
        "generic": "trifluridine", "company": "Monarch Pharmaceuticals (Drugs@FDA holder; original applicant lineage not pinned)",
        "lineage": "No ticker assigned: historical applicant/holder identity requires a separate primary-source corporate resolution.",
        "indication": "Treatment of primary keratoconjunctivitis and recurrent epithelial keratitis due to herpes simplex virus types 1 and 2 (per the Pfizer-hosted FDA label; label text is current/historical qualification is retained).",
        "milestone": "Topical anti-herpesvirus nucleoside analogue; approval-era FDA record is preserved even though the product is no longer a current mainstream therapy.",
        "citation": "FDA label: https://labeling.pfizer.com/ShowLabeling.aspx?id=700; NIH/NCATS approval record: https://drugs.ncats.io/substance/RMW9V5RW38. Original applicant is not guessed from the current holder.",
    },
    {
        "appl": "NDA018067", "brand": "Cinobac", "aliases": ["CINOBAC"],
        "generic": "cinoxacin", "company": "Eli Lilly and Company (original applicant; current Drugs@FDA holder Lilly)",
        "lineage": "Eli Lilly and Company (NYSE: LLY)",
        "indication": "Treatment of initial and recurrent urinary tract infections in adults caused by susceptible microorganisms (per the FDA label).",
        "milestone": "Synthetic quinolone-related antibacterial approved for urinary-tract infection treatment and prevention of recurrent UTI in selected patients.",
        "citation": "FDA label, NDA 018067: https://www.accessdata.fda.gov/drugsatfda_docs/label/2002/18067s29lbl.pdf.",
    },
    {
        "appl": "NDA018006", "brand": "Meclomen", "aliases": ["MECLOMEN"],
        "generic": "meclofenamate sodium", "company": "Parke-Davis (Warner-Lambert division; Drugs@FDA holder)",
        "lineage": "Warner-Lambert Co. historical lineage; ticker intentionally blank pending the project's period-specific EDGAR resolution queue.",
        "indication": "Relief of mild-to-moderate pain and signs and symptoms of rheumatoid arthritis, osteoarthritis, and dysmenorrhea (historical indication; approval-era label text is not present in the committed openFDA extract).",
        "milestone": "Fenamate nonsteroidal anti-inflammatory drug; this application is the 1980 TYPE 1 NME that disproved the former v12 Lithobid row's application/date premise.",
        "citation": "Contemporaneous clinical review: https://doi.org/10.7326/0003-4819-94-2-270; the application/date/class remain asserted directly against the committed FDA payload.",
    },
    {
        "appl": "NDA018069", "brand": "Vansil", "aliases": ["VANSIL"],
        "generic": "oxamniquine", "company": "Pfizer Inc. (current Drugs@FDA holder; historical development attribution retained with qualification)",
        "lineage": "Pfizer Inc. (NYSE: PFE)",
        "indication": "Treatment of Schistosoma mansoni infection (per the NIH/NCATS record for the original US product).",
        "milestone": "Oral antischistosomal therapy for S. mansoni; product is now previously marketed/discontinued in the United States.",
        "citation": "NIH/NCATS Inxight record: https://drugs.ncats.io/substance/7GIJ138H3K. No unverified original-applicant name is substituted for the payload holder.",
    },
    {
        "appl": "NDA018312", "brand": "Calderol", "aliases": ["CALDEROL"],
        "generic": "calcifediol", "company": "Organon USA Inc. (Drugs@FDA holder; approval-era corporate lineage separately flagged)",
        "lineage": "Organon historical lineage; no period-specific US ticker asserted.",
        "indication": "Vitamin-D metabolite product historically used for disorders involving calcium/phosphate balance; the approval-era indication wording is not available in the committed machine-readable payload.",
        "milestone": "Early US calcifediol product; the current/recent Rayaldee label must not be back-projected onto the 1980 approval without qualification.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/substance/T0WXW8F54E. The indication is deliberately qualified because current calcifediol labeling is not the 1980 label.",
    },
    {
        "appl": "NDA018021", "brand": "Asendin", "aliases": ["ASENDIN"],
        "generic": "amoxapine", "company": "Lederle Laboratories (American Cyanamid/Wyeth lineage; Drugs@FDA holder)",
        "lineage": "Wyeth historical lineage (NYSE: WYE); ticker is historical/successor context, not a claim about a 1980 listing class.",
        "indication": "Treatment of depressive illness, including depressive and major depressive disorders (per later FDA labeling for amoxapine; approval-era wording is qualified).",
        "milestone": "Tricyclic antidepressant with additional dopamine-receptor antagonism; later withdrawn from routine US marketing.",
        "citation": "FDA labeling search record for amoxapine; approval metadata is the committed Drugs@FDA application record. Approval-era label documents are not exposed in the v14 payload.",
    },
    {
        "appl": "NDA018202", "brand": "Cytadren", "aliases": ["CYTADREN"],
        "generic": "aminoglutethimide", "company": "Ciba-Geigy/Novartis lineage (current Drugs@FDA holder listed as Novartis)",
        "lineage": "Novartis AG (NYSE: NVS; current successor context, not a claim that NVS existed in 1980)",
        "indication": "Suppression of adrenal function in selected patients with Cushing syndrome (per the NIH/NCATS record and historical labeling).",
        "milestone": "Adrenocortical steroid-synthesis inhibitor; later used in endocrine oncology and now previously marketed in the United States.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/0O54ZQ14I9. Ciba-Geigy did not become Novartis until 1996; the lineage is explicitly time-qualified.",
    },
    {
        "appl": "NDA017543", "brand": "Ludiomil", "aliases": ["LUDIOMIL"],
        "generic": "maprotiline hydrochloride", "company": "Ciba-Geigy/Novartis lineage (current Drugs@FDA holder listed as Novartis)",
        "lineage": "Novartis AG (NYSE: NVS; current successor context, not a claim that NVS existed in 1980)",
        "indication": "Treatment of depressive illness, including depressive neurosis and major depressive disorder; relief of anxiety associated with depression (per FDA labeling).",
        "milestone": "Tetracyclic antidepressant with predominantly noradrenergic reuptake inhibition; later withdrawn from US marketing.",
        "citation": "FDA label: https://www.accessdata.fda.gov/drugsatfda_docs/label/2014/072285s021lbl.pdf.",
    },
    {
        "appl": "NDA050520", "brand": "Spectrobid", "aliases": ["SPECTROBID"],
        "generic": "bacampicillin hydrochloride", "company": "Pfizer Inc. (Drugs@FDA holder; historical US product)",
        "lineage": "Pfizer Inc. (NYSE: PFE)",
        "indication": "Treatment of susceptible bacterial infections; approval-era detailed indication wording is not available in the committed machine-readable payload.",
        "milestone": "Oral prodrug of ampicillin with improved bioavailability; previously marketed in the United States.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/8GM2J22278. The row does not infer a current indication from a non-US label.",
    },

    # ------------------------------------------------------------------ 1981
    {
        "appl": "NDA018163", "brand": "Restoril", "aliases": ["RESTORIL"],
        "generic": "temazepam", "company": "Sandoz/SpeCGx lineage (current Drugs@FDA holder SpeCGx LLC)",
        "lineage": "Historical applicant lineage not assigned a US ticker; current holder is preserved verbatim from the payload.",
        "indication": "Short-term treatment of insomnia, generally 7 to 10 days (per FDA label).",
        "milestone": "Benzodiazepine hypnotic; FDA approval and controlled-substance history are separately documented from the application payload.",
        "citation": "FDA label, NDA 018163: https://www.accessdata.fda.gov/drugsatfda_docs/label/2008/018163s058s059lbl.pdf.",
    },
    {
        "appl": "NDA050547", "brand": "Claforan", "aliases": ["CLAFORAN"],
        "generic": "cefotaxime sodium", "company": "Hoechst/Roussel lineage (current holder US Pharmaceutical Holdings II/SteriMax)",
        "lineage": "Sanofi S.A. (NASDAQ: SNY) successor context; original 1981 listing class is not asserted.",
        "indication": "Treatment of serious bacterial infections in multiple organ systems caused by susceptible microorganisms (per FDA Federal Register notice).",
        "milestone": "Third-generation cephalosporin; FDA later determined the product was not withdrawn for safety or effectiveness reasons.",
        "citation": "FDA Federal Register notice: https://www.federalregister.gov/documents/2019/07/03/2019-14172/determination-that-claforan-cefotaxime-sodium-for-injection-500-milligramsvial-1-gramvial-2.",
    },
    {
        "appl": "NDA018343", "brand": "Capoten", "aliases": ["CAPOTEN"],
        "generic": "captopril", "company": "E.R. Squibb & Sons lineage (current Drugs@FDA holder AARXION ANDA Holding)",
        "lineage": "Bristol Myers Squibb (NYSE: BMY) successor context; period-specific 1981 listing is not asserted.",
        "indication": "ACE-inhibitor treatment of hypertension; later FDA labeling also covers heart-failure and post-myocardial-infarction uses.",
        "milestone": "First widely used orally active ACE inhibitor; major therapeutic milestone in cardiovascular medicine.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/captopril. The row separates the historical developer lineage from the current payload holder.",
    },
    {
        "appl": "NDA017559", "brand": "Proventil", "aliases": ["PROVENTIL"],
        "generic": "albuterol", "company": "Schering Corporation (original product lineage; current holder not used to infer a ticker)",
        "lineage": "Schering-Plough/Merck lineage; no 1981 ticker asserted.",
        "indication": "Treatment or prevention of bronchospasm in reversible obstructive airway disease and prevention of exercise-induced bronchospasm (per FDA label).",
        "milestone": "Metered-dose beta-2 agonist bronchodilator; later HFA labeling preserves the core clinical use.",
        "citation": "FDA label: https://www.accessdata.fda.gov/drugsatfda_docs/nda/2013/020503Orig1s047.pdf.",
    },
    {
        "appl": "NDA017675", "brand": "Tenathan", "aliases": ["TENATHAN"],
        "generic": "bethanidine sulfate", "company": "A.H. Robins Co. (Drugs@FDA holder)",
        "lineage": "A.H. Robins historical lineage; later American Home Products/Wyeth context, but no period ticker is asserted.",
        "indication": "Treatment of hypertension (per the NIH/NCATS record).",
        "milestone": "Peripheral adrenergic-neuron-blocking antihypertensive; previously marketed and later discontinued.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/J4THI5N7O2.",
    },
    {
        "appl": "NDA018533", "brand": "Nizoral", "aliases": ["NIZORAL"],
        "generic": "ketoconazole", "company": "Janssen Pharmaceutica (Johnson & Johnson lineage; current Drugs@FDA holder)",
        "lineage": "Johnson & Johnson (NYSE: JNJ)",
        "indication": "Systemic treatment of serious fungal infections when other effective therapy is unavailable or not tolerated; later FDA safety action narrowed oral-tablet use.",
        "milestone": "First systemic azole antifungal widely used in the United States; current safety restrictions must not be back-projected into the 1981 approval wording.",
        "citation": "FDA safety communication context: https://www.fda.gov/drugs/drug-safety-and-availability/fda-drug-safety-communication-fda-limits-usage-nizoral-ketoconazole-oral-tablets.",
    },
    {
        "appl": "NDA018310", "brand": "Lymphazurin", "aliases": ["LYMPHAZURIN"],
        "generic": "isosulfan blue", "company": "US Surgical/Covidien lineage (current Drugs@FDA holder Covidien)",
        "lineage": "Medtronic plc (NYSE: MDT) successor context; no 1981 listing claim.",
        "indication": "Delineation of lymphatic vessels and lymph nodes draining the region of injection for lymphatic mapping (per FDA review).",
        "milestone": "Blue-dye lymphatic mapping agent later used as an adjunct to sentinel-node procedures.",
        "citation": "FDA clinical review, NDA 017858: https://www.accessdata.fda.gov/drugsatfda_docs/nda/2012/017858Orig1s035MedR.pdf.",
    },
    {
        "appl": "NDA018485", "brand": "Isoptin", "aliases": ["ISOPTIN"],
        "generic": "verapamil hydrochloride", "company": "Knoll Pharmaceuticals lineage (current Drugs@FDA holder Mt. Adams)",
        "lineage": "BASF/Knoll historical lineage; no period-specific US ticker asserted.",
        "indication": "Treatment of angina, arrhythmias, and essential hypertension (per FDA Federal Register notice; this application is the injectable product).",
        "milestone": "Non-dihydropyridine calcium-channel blocker; the payload distinguishes Isoptin injection from later oral verapamil applications.",
        "citation": "FDA Federal Register notice: https://www.federalregister.gov/documents/2021/05/19/2021-10552/determination-that-isoptin-verapamil-hydrochloride-tablets-40-milligrams-80-milligrams-and-120.",
    },
    {
        "appl": "NDA018240", "brand": "Tenormin", "aliases": ["TENORMIN"],
        "generic": "atenolol", "company": "ICI Pharmaceuticals lineage (current Drugs@FDA holder TWI Pharmaceuticals)",
        "lineage": "AstraZeneca plc (NASDAQ: AZN ADR) successor context; period-specific listing class is not asserted.",
        "indication": "Treatment of hypertension and angina; later FDA labeling also includes selected post-myocardial-infarction use.",
        "milestone": "Beta-1-selective adrenergic blocker that became a major cardiovascular therapy.",
        "citation": "NIH/NCBI clinical reference: https://www.ncbi.nlm.nih.gov/books/NBK539844/. The original ICI-to-AstraZeneca lineage is explicitly qualified.",
    },
    {
        "appl": "NDA050549", "brand": "Mezlin", "aliases": ["MEZLIN"],
        "generic": "mezlocillin sodium", "company": "Bayer Pharmaceuticals (original product lineage; current holder in payload)",
        "lineage": "Bayer AG (OTC: BAYRY ADR; primary Xetra listing; no claim that the ADR class reflects 1981).",
        "indication": "Treatment of serious bacterial infections caused by susceptible organisms; approval-era detailed organ-system wording is not in the committed payload.",
        "milestone": "Broad-spectrum ureidopenicillin; previously marketed in the United States.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/3CWW8B5904; pharmacology record: https://www.guidetopharmacology.org/GRAC/LigandDisplayForward?ligandId=12272.",
    },
    {
        "appl": "NDA017736", "brand": "Paxipam", "aliases": ["PAXIPAM"],
        "generic": "halazepam", "company": "Schering Corporation (Drugs@FDA holder)",
        "lineage": "Schering-Plough/Merck successor context; no period-specific 1981 ticker asserted.",
        "indication": "Relief of anxiety, nervousness, and tension associated with anxiety disorders (per the NIH/NCATS record).",
        "milestone": "Benzodiazepine anxiolytic; later withdrawn from US marketing.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/halazepam.",
    },
    {
        "appl": "NDA018148", "brand": "Nasalide", "aliases": ["NASALIDE"],
        "generic": "flunisolide", "company": "Ivax Research (current Drugs@FDA holder)",
        "lineage": "Ivax/Teva successor context; no period-specific ticker asserted.",
        "indication": "Topical treatment of symptoms of seasonal or perennial rhinitis when conventional treatment is unsatisfactory or not tolerated (per flunisolide nasal labeling).",
        "milestone": "Intranasal corticosteroid for allergic rhinitis; approval-era applicant/holder lineage is flagged separately.",
        "citation": "FDA-label-derived text: https://fda.report/DailyMed/3f3d300d-a843-4da8-90d1-7a1a4c283c51. The committed FDA payload controls the application/date/class.",
    },
    {
        "appl": "NDA018200", "brand": "Midamor", "aliases": ["MIDAMOR"],
        "generic": "amiloride hydrochloride", "company": "Merck Sharp & Dohme lineage (current Drugs@FDA holder Padagis US)",
        "lineage": "Merck & Co. (NYSE: MRK) successor context; no claim that the current holder was the 1981 applicant.",
        "indication": "Used with other diuretics to help prevent hypokalemia in hypertension or congestive heart failure (per the NIH/NCATS record).",
        "milestone": "Potassium-sparing diuretic that preserves potassium while increasing sodium/water excretion.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/7DZO8EB0Z3.",
    },
    {
        "appl": "NDA018276", "brand": "Xanax", "aliases": ["XANAX"],
        "generic": "alprazolam", "company": "The Upjohn Company (original applicant; current Drugs@FDA holder)",
        "lineage": "Upjohn/Pharmacia/Pfizer successor context; no 1981 period ticker asserted.",
        "indication": "Treatment of anxiety disorders and anxiety associated with depression (per the contemporaneous New York Times report and later FDA labeling).",
        "milestone": "Short-acting benzodiazepine anxiolytic; Upjohn's contemporaneous announcement documented the 1981 FDA approval and clinical-anxiety use.",
        "citation": "Contemporaneous report: https://www.nytimes.com/1981/11/03/business/upjohn-drug-gets-fda-approval.html; FDA SPL example: https://www.accessdata.fda.gov/spl/data/bfd71421-c03d-4025-a044-b20a7dc588a8/bfd71421-c03d-4025-a044-b20a7dc588a8.xml.",
    },
    {
        "appl": "NDA018484", "brand": "Prostin VR Pediatric", "aliases": ["PROSTIN VR PEDIATRIC"],
        "generic": "alprostadil", "company": "The Upjohn Company / Pharmacia lineage (current Drugs@FDA holder Pfizer)",
        "lineage": "Pfizer Inc. (NYSE: PFE) successor context; no 1981 period ticker asserted.",
        "indication": "Temporary maintenance of ductus arteriosus patency until corrective or palliative surgery in neonates with congenital heart defects (per the FDA label).",
        "milestone": "Prostaglandin E1 infusion became a foundational bridge therapy in ductal-dependent congenital heart disease.",
        "citation": "FDA/Pfizer label: https://labeling.pfizer.com/showlabeling.aspx?id=604.",
    },
    {
        "appl": "NDA018557", "brand": "Fansidar", "aliases": ["FANSIDAR"],
        "generic": "sulfadoxine/pyrimethamine", "company": "Roche lineage (current Drugs@FDA holder)",
        "lineage": "Roche Holding AG (OTC: RHHBY ADR; primary SIX listing; period class not asserted).",
        "indication": "Treatment of susceptible Plasmodium falciparum malaria when chloroquine resistance is suspected; prophylaxis was separately limited by labeling.",
        "milestone": "TYPE 1/4 antimalarial combination; the payload records the NME/new-combination classification directly.",
        "citation": "Label-derived clinical monograph: https://www.rxmed.com/b.main/b2.pharmaceutical/b2.1.monographs/cps-_monographs/CPS-_(General_Monographs-_F)/FANSIDAR.html. Regulatory class/date remain payload-derived.",
    },
    {
        "appl": "NDA018333", "brand": "Carafate", "aliases": ["CARAFATE"],
        "generic": "sucralfate", "company": "Marion Laboratories (original applicant; current Drugs@FDA holder AbbVie)",
        "lineage": "Marion/Merrell Dow lineage; current holder AbbVie (NYSE: ABBV) is kept as a holder context, not a claim about 1981 ownership.",
        "indication": "Short-term treatment of duodenal ulcer (per NIH/peer-reviewed clinical review of the FDA approval).",
        "milestone": "Locally acting mucosal-protective antiulcer therapy; the 1981 approval was for short-term duodenal-ulcer treatment.",
        "citation": "Peer-reviewed clinical review: https://accpjournals.onlinelibrary.wiley.com/doi/10.1002/j.1875-9114.1982.tb03176.x.",
    },
    {
        "appl": "NDA018422", "brand": "Lopid", "aliases": ["LOPID"],
        "generic": "gemfibrozil", "company": "Parke-Davis/Warner-Lambert lineage (current Drugs@FDA holder Pfizer)",
        "lineage": "Warner-Lambert historical lineage; ticker intentionally blank pending period-specific EDGAR resolution.",
        "indication": "Lipid-regulating treatment for selected severe hypertriglyceridemia and dyslipidemia when diet and other measures are inadequate (per NIH clinical reference; approval-era wording is qualified).",
        "milestone": "Fibric-acid lipid regulator; cardiovascular-outcome evidence later shaped its use and limitations.",
        "citation": "NIH/NCBI reference: https://www.ncbi.nlm.nih.gov/books/NBK545266/. The row does not guess a Warner-Lambert event ticker.",
    },
    {
        "appl": "NDA018045", "brand": "Emcyt", "aliases": ["EMCYT"],
        "generic": "estramustine phosphate sodium", "company": "Pharmacia & Upjohn (historical applicant/holder)",
        "lineage": "Pharmacia & Upjohn/Pfizer successor context; no 1981 period ticker asserted.",
        "indication": "Palliative treatment of patients with metastatic and/or progressive carcinoma of the prostate (per FDA label).",
        "milestone": "Conjugate of an estrogen moiety and nitrogen-mustard carbamate used in advanced prostate cancer.",
        "citation": "FDA label: https://www.accessdata.fda.gov/drugsatfda_docs/label/2008/018045s023lbl.pdf.",
    },
    {
        "appl": "NDA018207", "brand": "Desyrel", "aliases": ["DESYREL"],
        "generic": "trazodone hydrochloride", "company": "Pragma/Angelini-Mead Johnson lineage (current Drugs@FDA holder)",
        "lineage": "Historical applicant lineage not assigned a US ticker; no ticker is guessed from a later marketer.",
        "indication": "Treatment of depression, with or without anxiety (per FDA medical review).",
        "milestone": "Serotonin antagonist and reuptake inhibitor; one of the first non-tricyclic, non-MAOI antidepressants marketed in the United States.",
        "citation": "FDA medical review: https://www.accessdata.fda.gov/drugsatfda_docs/nda/2010/022411s000MedR.pdf.",
    },
    {
        "appl": "NDA018401", "brand": "Buprenex", "aliases": ["BUPRENEX"],
        "generic": "buprenorphine hydrochloride", "company": "Norwich Eaton Pharmaceuticals lineage (current Drugs@FDA holder Indivior)",
        "lineage": "Indivior plc (LSE: INDV) current successor context; no 1981 US ticker asserted.",
        "indication": "Management of pain severe enough to require an opioid analgesic and for which alternate treatments are inadequate (per FDA Federal Register notice).",
        "milestone": "Early US buprenorphine injection; the approval date was litigated and is pinned here to the FDA application record and later FDA notice.",
        "citation": "FDA Federal Register notice: https://www.federalregister.gov/documents/2023/11/22/2023-25857/determination-that-buprenex-buprenorphine-hydrochloride-injection-03-milligrammilliliter-was-not.",
    },
    {
        "appl": "NDA050545", "brand": "Pipracil", "aliases": ["PIPRACIL"],
        "generic": "piperacillin sodium", "company": "Lederle Laboratories (American Cyanamid/Wyeth lineage)",
        "lineage": "Wyeth historical lineage (NYSE: WYE); no claim that WYE was the 1981 listing class.",
        "indication": "Treatment of serious infections and prophylactic use in surgery (per FDA Federal Register notice).",
        "milestone": "Broad-spectrum ureidopenicillin with activity against serious susceptible bacterial infections.",
        "citation": "FDA Federal Register notice: https://www.federalregister.gov/documents/2003/10/29/03-27190/determination-that-pipracil-piperacillin-sodium-2-gram-3-gram-and-4-gram-vials-were-not-withdrawn.",
    },
    {
        "appl": "NDA018482", "brand": "Procardia", "aliases": ["PROCARDIA"],
        "generic": "nifedipine", "company": "Pfizer Inc. (current Drugs@FDA holder; historical development lineage)",
        "lineage": "Pfizer Inc. (NYSE: PFE)",
        "indication": "Management of vasospastic angina and chronic stable angina (per the Pfizer label); later formulations also carry hypertension indications.",
        "milestone": "Dihydropyridine calcium-channel blocker that became a major antianginal and antihypertensive therapy.",
        "citation": "Pfizer label: https://labeling.pfizer.com/ShowLabeling.aspx?id=541.",
    },

    # ------------------------------------------------------------------ 1982
    {
        "appl": "NDA017707", "brand": "MPI Indium DTPA In-111", "aliases": ["MPI INDIUM DTPA IN 111"],
        "generic": "indium In-111 pentetate disodium", "company": "Medi-Physics/GE HealthCare lineage (current Drugs@FDA holder GE HealthCare)",
        "lineage": "GE HealthCare Technologies (Nasdaq: GEHC) current successor context; original 1982 listing class is not asserted.",
        "indication": "Radionuclide cisternography to study cerebrospinal-fluid flow, diagnose CSF-circulation abnormalities or leakage, and assess CSF shunts (per the NIH/NCATS record).",
        "milestone": "Diagnostic radiopharmaceutical for CSF-flow imaging.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/WJZ06C0H8L; package-insert-derived record: https://medlibrary.org/lib/rx/meds/indium-dtpa-in-111/.",
    },
    {
        "appl": "NDA018467", "brand": "Hepatolite", "aliases": ["HEPATOLITE"],
        "generic": "technetium Tc-99m disofenin kit", "company": "Medi-Physics/GE radiopharmaceutical lineage (current Drugs@FDA holder Sun Pharmaceutical Industries)",
        "lineage": "No US ticker assigned: current holder and original radiopharmaceutical applicant are not treated as interchangeable.",
        "indication": "Hepatobiliary imaging agent used to evaluate gallbladder and biliary tract function; approval-era detailed wording is qualified.",
        "milestone": "Early Tc-99m hepatobiliary imaging kit in the US radiopharmaceutical record.",
        "citation": "FDA-label-derived source: https://s3-us-west-2.amazonaws.com/drugbank/fda_labels/DB09164.pdf?1444064671=; historical imaging review: https://tech.snmjournals.org/content/42/4/249.",
    },
    {
        "appl": "NDA018604", "brand": "Zovirax", "aliases": ["ZOVIRAX"],
        "generic": "acyclovir", "company": "Burroughs Wellcome (original applicant); current Drugs@FDA holder Bausch",
        "lineage": "GlaxoSmithKline plc (NYSE: GSK) successor context; no claim that GSK was the 1982 listing class.",
        "indication": "Management of initial genital herpes and limited non-life-threatening mucocutaneous herpes infections for the topical ointment formulation (per FDA label).",
        "milestone": "First US acyclovir application; antiviral nucleoside analogue that became a foundational herpes treatment.",
        "citation": "FDA label, NDA 018604: https://www.accessdata.fda.gov/drugsatfda_docs/label/2001/018604s018lbl.pdf.",
    },
    {
        "appl": "NDA018147", "brand": "Feldene", "aliases": ["FELDENE"],
        "generic": "piroxicam", "company": "Pfizer Inc. (current Drugs@FDA holder)",
        "lineage": "Pfizer Inc. (NYSE: PFE)",
        "indication": "Relief of signs and symptoms of osteoarthritis and rheumatoid arthritis (per FDA label).",
        "milestone": "Long-acting NSAID with an extended half-life; later labeling preserves the OA/RA indication.",
        "citation": "FDA label: https://www.accessdata.fda.gov/drugsatfda_docs/label/2016/018147s044lbl.pdf; Pfizer label: https://labeling.pfizer.com/showlabeling.aspx?id=569.",
    },
    {
        "appl": "NDA018445", "brand": "Dolobid", "aliases": ["DOLOBID"],
        "generic": "diflunisal", "company": "Merck & Co. (current Drugs@FDA holder)",
        "lineage": "Merck & Co. (NYSE: MRK)",
        "indication": "Mild-to-moderate acute pain and symptomatic relief of osteoarthritis and rheumatoid arthritis (per NIH LiverTox).",
        "milestone": "Salicylic-acid-derived NSAID with analgesic and anti-inflammatory activity.",
        "citation": "NIH LiverTox: https://www.ncbi.nlm.nih.gov/books/NBK548132.",
    },
    {
        "appl": "NDA018662", "brand": "Accutane", "aliases": ["ACCUTANE"],
        "generic": "isotretinoin", "company": "Hoffmann-La Roche (original applicant; current Drugs@FDA holder)",
        "lineage": "Roche Holding AG (OTC: RHHBY ADR; primary SIX listing; period class not asserted).",
        "indication": "Severe recalcitrant nodular acne unresponsive to conventional therapy, including systemic antibiotics (historical FDA indication).",
        "milestone": "First oral retinoid approved in the United States for severe nodular acne; teratogenicity later drove extensive risk-management controls.",
        "citation": "FDA patient/provider safety history: https://www.fda.gov/drugs/postmarket-drug-safety-information-patients-and-providers/accutane-isotretinoin; approval/date/class are payload-derived.",
    },
    {
        "appl": "NDA050577", "brand": "Zanosar", "aliases": ["ZANOSAR"],
        "generic": "streptozocin", "company": "Upjohn/Pfizer lineage (current Drugs@FDA holder Teva Pharmaceuticals USA)",
        "lineage": "Pfizer Inc. (NYSE: PFE) successor context; current holder is kept distinct from original developer.",
        "indication": "Treatment of metastatic islet-cell carcinoma of the pancreas, particularly symptomatic or progressive disease (historical FDA indication).",
        "milestone": "Nitrosourea antineoplastic with relative pancreatic islet-cell toxicity; renal toxicity limits use.",
        "citation": "NIH/HemOnc approval history: https://hemonc.org/wiki/Streptozocin_(Zanosar); current sponsor/approval fields are asserted from the FDA payload.",
    },
    {
        "appl": "NDA017944", "brand": "MPI DMSA Kidney Reagent", "aliases": ["MPI DMSA KIDNEY REAGENT"],
        "generic": "technetium Tc-99m succimer kit", "company": "Medi-Physics/GE HealthCare (current Drugs@FDA holder GE HealthCare)",
        "lineage": "GE HealthCare Technologies (Nasdaq: GEHC) current successor context; no 1982 period ticker asserted.",
        "indication": "Aid in scintigraphic evaluation of renal parenchymal disorders (per FDA Federal Register notice).",
        "milestone": "Renal-cortex imaging kit; FDA later confirmed it was not withdrawn for safety or effectiveness reasons.",
        "citation": "FDA Federal Register notice: https://www.federalregister.gov/documents/2022/03/14/2022-05324/determination-that-mpi-dmsa-kidney-reagent-technetium-tc-99m-succimer-kit-injectable-was-not.",
    },
    {
        "appl": "NDA018613", "brand": "Ovide", "aliases": ["OVIDE"],
        "generic": "malathion", "company": "Taro Pharmaceutical Industries (current Drugs@FDA holder)",
        "lineage": "Taro Pharmaceutical Industries (historical Nasdaq: TARO context; current listing status is not used for 1982).",
        "indication": "Treatment of scalp infection with head lice and their ova (per FDA Federal Register notice).",
        "milestone": "Topical organophosphate pediculicide; FDA later confirmed the product was not withdrawn for safety or effectiveness reasons.",
        "citation": "FDA Federal Register notice: https://www.federalregister.gov/documents/2021/05/14/2021-10166/determination-that-ovide-malathion-lotion-05-was-not-withdrawn-from-sale-for-reasons-of-safety-or.",
    },
    {
        "appl": "NDA018285", "brand": "Visken", "aliases": ["VISKEN"],
        "generic": "pindolol", "company": "Sandoz/Novartis lineage (current Drugs@FDA holder)",
        "lineage": "Novartis AG (NYSE: NVS; successor context, not a claim about the 1982 listing class).",
        "indication": "Treatment of systemic hypertension (per NIH LiverTox and contemporaneous medical literature).",
        "milestone": "Nonselective beta-adrenergic blocker with partial agonist activity.",
        "citation": "NIH LiverTox: https://www.ncbi.nlm.nih.gov/books/NBK548489; contemporaneous NEJM review: https://doi.org/10.1056/NEJM198304213081606.",
    },
    {
        "appl": "NDA018227", "brand": "Amidate", "aliases": ["AMIDATE"],
        "generic": "etomidate", "company": "Janssen/Pfizer-Hospira lineage (current Drugs@FDA holder Hospira)",
        "lineage": "Pfizer Inc. (NYSE: PFE) current successor context; original 1982 listing class is not asserted.",
        "indication": "Intravenous induction of general anesthesia and supplementation of subpotent anesthetic agents during short operative procedures (per FDA label-derived record).",
        "milestone": "Hemodynamically stable intravenous anesthetic induction agent.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/Z22628B598.",
    },
    {
        "appl": "NDA018587", "brand": "Wytensin", "aliases": ["WYTENSIN"],
        "generic": "guanabenz acetate", "company": "Wyeth-Ayerst (original applicant; current Drugs@FDA holder)",
        "lineage": "Wyeth historical lineage (NYSE: WYE); no claim that WYE was the 1982 listing class.",
        "indication": "Treatment of hypertension, alone or with a thiazide diuretic (per the NIH/NCATS record).",
        "milestone": "Central alpha-2 adrenergic agonist antihypertensive; later studied experimentally for other conditions but those are not counted as approved indications.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/GGD30112WC.",
    },
    {
        "appl": "NDA018123", "brand": "Factrel", "aliases": ["FACTREL"],
        "generic": "gonadorelin hydrochloride", "company": "Wyeth-Ayerst lineage (current Drugs@FDA holder Hikma)",
        "lineage": "Hikma Pharmaceuticals (LSE: HIK) current-holder context; no 1982 US ticker asserted.",
        "indication": "Diagnostic evaluation of pituitary gonadotroph function (per FDA approval documentation).",
        "milestone": "Synthetic gonadotropin-releasing hormone used as a diagnostic endocrine challenge.",
        "citation": "FDA approval documentation: https://www.accessdata.fda.gov/drugsatfda_docs/nda/97/020517_s002ap.pdf.",
    },
    {
        "appl": "NDA018536", "brand": "Xenon Xe-127", "aliases": ["XENON XE 127"],
        "generic": "xenon Xe-127", "company": "Mallinckrodt (Drugs@FDA holder)",
        "lineage": "Mallinckrodt historical radiopharmaceutical lineage; no period ticker asserted.",
        "indication": "Radioactive-gas diagnostic imaging product for pulmonary ventilation studies; approval-era label text was not retrieved and is explicitly flagged.",
        "milestone": "Early xenon ventilation radiopharmaceutical; later superseded in practice by other radionuclide/imaging approaches.",
        "citation": "Technical radiology reference: https://www.sciencedirect.com/topics/medicine-and-dentistry/xenon-127. The application/date/class/product are payload-derived; no unsupported indication detail is added.",
    },
    {
        "appl": "BLA018780", "brand": "Humulin R", "aliases": ["HUMULIN R PEN", "HUMULIN R"],
        "generic": "recombinant human insulin", "company": "Eli Lilly and Company (original applicant; current Drugs@FDA holder)",
        "lineage": "Eli Lilly and Company (NYSE: LLY)",
        "indication": "Treatment of diabetes mellitus requiring insulin (product-specific approval context; current Humulin labeling should be consulted for exact formulation wording).",
        "milestone": "First marketable recombinant-DNA pharmaceutical and first biosynthetic human insulin product in the United States.",
        "citation": "Smithsonian/National Museum of American History: https://americanhistory.si.edu/collections/object-groups/birth-of-biotech/recombinant-drugs; NSF historical account: https://www.nsf.gov/impacts/rdna-insulin.",
    },
    {
        "appl": "NDA018602", "brand": "Cardizem", "aliases": ["CARDIZEM"],
        "generic": "diltiazem hydrochloride", "company": "Marion Laboratories (original product lineage; current Drugs@FDA holder Bausch)",
        "lineage": "Marion/Merrell Dow historical lineage; no 1982 event ticker asserted.",
        "indication": "Management of chronic stable angina and angina due to coronary artery spasm (per FDA label); later formulations carry hypertension indications.",
        "milestone": "Non-dihydropyridine calcium-channel blocker and major antianginal therapy.",
        "citation": "FDA label, NDA 018602: https://www.accessdata.fda.gov/drugsatfda_docs/label/2010/018602s063lbl.pdf.",
    },
    {
        "appl": "BLA018663", "brand": "Chymodiactin", "aliases": ["CHYMODIACTIN"],
        "generic": "chymopapain", "company": "Smith Laboratories/Travenol lineage (current BLA holder DisCure Medical)",
        "lineage": "No public US ticker assigned: historical applicant and current holder are preserved separately.",
        "indication": "Treatment of documented herniated lumbar intervertebral discs whose symptoms/signs, particularly sciatica, did not respond to adequate conservative therapy (per FDA notice).",
        "milestone": "Enzymatic chemonucleolysis product derived from papaya latex; later withdrawn from sale for reasons other than safety/effectiveness under FDA's determination.",
        "citation": "FDA Federal Register notice: https://www.federalregister.gov/documents/2003/01/27/03-1742/determination-that-chymopapain-10000-unitsvial-injection-was-not-withdrawn-from-sale-for-reasons-of.",
    },
    {
        "appl": "NDA017892", "brand": "Halcion", "aliases": ["HALCION"],
        "generic": "triazolam", "company": "The Upjohn Company (original applicant; current Drugs@FDA holder Pfizer)",
        "lineage": "Pfizer Inc. (NYSE: PFE) successor context; no claim that Pfizer was the 1982 applicant.",
        "indication": "Short-term treatment of insomnia (generally 7 to 10 days under current labeling; original FDA approval history is documented by NIH).",
        "milestone": "Short-acting benzodiazepine hypnotic; later FDA/IOM review examined dose, duration, and safety evidence.",
        "citation": "NIH/National Academies review of FDA evidence: https://www.ncbi.nlm.nih.gov/books/NBK233862/ and historical introduction: https://www.ncbi.nlm.nih.gov/books/NBK233849/.",
    },
    {
        "appl": "NDA050551", "brand": "Cefobid", "aliases": ["CEFOBID"],
        "generic": "cefoperazone sodium", "company": "Pfizer Inc. (current Drugs@FDA holder; original product lineage)",
        "lineage": "Pfizer Inc. (NYSE: PFE)",
        "indication": "Treatment of susceptible respiratory, intra-abdominal, urinary-tract, skin, pelvic, bone/joint and other serious bacterial infections (per FDA label).",
        "milestone": "Third-generation cephalosporin with broad gram-negative coverage, including selected Pseudomonas activity.",
        "citation": "Pfizer FDA label: https://labeling.pfizer.com/ShowLabeling.aspx?id=1178.",
    },
    {
        "appl": "NDA018702", "brand": "Aclovate", "aliases": ["ACLOVATE"],
        "generic": "alclometasone dipropionate", "company": "Fougera Pharmaceuticals (Drugs@FDA holder)",
        "lineage": "No ticker assigned: historical topical-product ownership is not inferred from a later generic holder.",
        "indication": "Relief of inflammatory and pruritic manifestations of corticosteroid-responsive dermatoses (per NIH/NCATS record).",
        "milestone": "Low-to-medium potency topical corticosteroid, including pediatric use subject to labeling limits.",
        "citation": "NIH/NCATS record: https://drugs.ncats.io/drug/S56PQL4N1V.",
    },
    {
        "appl": "NDA018751", "brand": "Spectazole", "aliases": ["SPECTAZOLE"],
        "generic": "econazole nitrate", "company": "Ortho-Janssen lineage (current Drugs@FDA holder Alvogen)",
        "lineage": "Johnson & Johnson (NYSE: JNJ) historical product lineage; current holder is not treated as original applicant.",
        "indication": "Topical treatment of tinea pedis, tinea cruris, tinea corporis, tinea versicolor and cutaneous candidiasis (per FDA review).",
        "milestone": "Early US topical azole antifungal cream; FDA later reviewed the product as a comparator for newer econazole formulations.",
        "citation": "FDA clinical review: https://www.accessdata.fda.gov/drugsatfda_docs/nda/2013/205175Orig1s000CrossR.pdf; FDA utilization review: https://www.fda.gov/files/advisory%20committees/published/Spectazole-Ecoza-Safety-and-Utilization-Review.pdf.",
    },
    {
        "appl": "NDA018757", "brand": "Calcibind", "aliases": ["CALCIBIND"],
        "generic": "cellulose sodium phosphate", "company": "Mission Pharmacal (Drugs@FDA holder)",
        "lineage": "Mission Pharmacal (private); no public ticker assigned.",
        "indication": "Reduction of intestinal calcium absorption in selected hypercalciuria/kidney-stone settings; approval-era detailed label was not retrieved.",
        "milestone": "Nonabsorbable calcium-binding resin intended to reduce urinary calcium and recurrent stone formation.",
        "citation": "Pharmacology reference: https://go.drugbank.com/drugs/DB06776. The row leaves the exact approval-era wording qualified rather than importing a current label.",
    },
    {
        "appl": "NDA018714", "brand": "Biltricide", "aliases": ["BILTRICIDE"],
        "generic": "praziquantel", "company": "Bayer AG (current Drugs@FDA holder)",
        "lineage": "Bayer AG (OTC: BAYRY ADR; primary Xetra listing; period class not asserted).",
        "indication": "Treatment of schistosomiasis and clonorchiasis/opisthorchiasis due to specified parasites (per current FDA/DailyMed label; approval year is separately payload-derived).",
        "milestone": "Broad-spectrum anthelmintic that became a principal treatment for schistosomiasis.",
        "citation": "DailyMed/FDA label: https://dailymed.nlm.nih.gov/dailymed/fda/fdaDrugXsl.cfm?setid=34ce1cdd-648e-4f1e-8512-bf3d4cc22eb9.",
    },
    {
        "appl": "NDA018748", "brand": "Loprox", "aliases": ["LOPROX"],
        "generic": "ciclopirox", "company": "Hoechst/Eurofarma lineage (current Drugs@FDA holder Eurofarma)",
        "lineage": "No US ticker assigned: current and historical topical-antifungal holders are not conflated.",
        "indication": "Topical treatment of tinea pedis, tinea cruris, tinea corporis and cutaneous candidiasis (per FDA label/review).",
        "milestone": "Non-azole topical antifungal; the 1982 approval is documented in later FDA clinical-review tables.",
        "citation": "FDA clinical review/table: https://www.fda.gov/media/111545/download; FDA label: https://www.accessdata.fda.gov/drugsatfda_docs/label/2003/19824slr009_loprox_lbl.pdf.",
    },
]

V14_APPS = {row["appl"] for row in V14_META}
if len(V14_META) != 56:
    raise SystemExit(f"v14 metadata count changed: expected 56 rows, got {len(V14_META)}")
if len(V14_APPS) != len(V14_META):
    raise SystemExit("v14 metadata contains duplicate application numbers")


def normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def payload_for(appl: str) -> dict:
    try:
        return ALL_PAYLOADS[appl]
    except KeyError as exc:
        raise SystemExit(f"application {appl} is absent from the committed 1980-1984 payloads") from exc


def assert_metadata(meta: dict) -> dict:
    appl = meta["appl"]
    payload = payload_for(appl)
    date = payload["decision_date"]
    year = int(date[:4])
    if year not in (1980, 1981, 1982):
        raise SystemExit(f"{appl}: v14 row is not a 1980-1982 approval ({date})")
    if not str(payload.get("submission_class_code", "")).startswith("TYPE 1"):
        raise SystemExit(f"{appl}: expected TYPE 1/1-4 payload, got {payload.get('submission_class_code')!r}")
    products = payload.get("products") or []
    if not products:
        raise SystemExit(f"{appl}: payload has no products")
    payload_brand = products[0].get("brand_name", "")
    aliases = [meta["brand"], *meta.get("aliases", [])]
    if not any(normalize(alias) in normalize(payload_brand) or normalize(payload_brand) in normalize(alias) for alias in aliases):
        raise SystemExit(f"{appl}: brand metadata {meta['brand']!r} does not match payload {payload_brand!r}")

    code = payload.get("submission_class_code") or "NOT STATED"
    description = payload.get("submission_class_code_description") or "Chemical type not stated in the Drugs@FDA record"
    priority = payload.get("review_priority") or "NOT STATED"
    app_kind = appl[:3]
    decision_type = "APPROVAL (ORIGINAL BLA)" if app_kind == "BLA" else "APPROVAL (ORIGINAL NDA)"
    source_num = appl[3:]
    note = (
        f"v14 2026-09-18 added from the committed openFDA Drugs@FDA payload. "
        f"Payload: ORIG/AP {date}, {code}, {priority}, holder {payload.get('sponsor_name', '')}, "
        f"product {payload_brand} ({products[0].get('active_ingredients', '')}). "
        f"{meta['citation']}"
    )
    return {
        "decision_id": f"PRE1985-{year}-{meta['appl'][-2:]}",  # replaced by deterministic group numbering below
        "year": str(year),
        "application_number": f"{app_kind} {source_num}",
        "drug_brand": meta["brand"],
        "drug_generic": meta["generic"],
        "company_name": meta["company"],
        "corporate_lineage_and_ticker": meta["lineage"],
        "decision_type": decision_type,
        "decision_date": date,
        "chemical_type_code": code,
        "chemical_type_description": description,
        "review_priority": priority,
        "indication": meta["indication"],
        "regulatory_milestone": meta["milestone"],
        "source_url_1": payload.get("source_url_drugsatfda") or DRUGSFDA.format(num=source_num),
        "source_url_2": OPENFDA_Q.format(appl=appl),
        "verification_status": "Verified",
        "notes": note,
    }


def rehome_hylorel(row: dict) -> dict:
    """Move the v13 launch-era boundary row to its actual 1982 group."""
    if row.get("application_number", "").replace(" ", "") != "NDA018104":
        return row
    out = dict(row)
    out["decision_id"] = "PRE1985-1982-MOVED"
    out["year"] = "1982"
    out["notes"] = out["notes"].replace(
        "it is retained in this 1983 row-group as a launch-era landmark with the 1982-12-29 approval date, as first recorded in v12.",
        "the v13 launch-era grouping was a boundary artifact; v14 places the row in its actual 1982 approval group.",
    )
    if "v14 boundary correction" not in out["notes"]:
        out["notes"] = (
            out["notes"].rstrip()
            + " v14 boundary correction (2026-09-18): the row is re-homed from the v13 "
            + "1983 launch-era group to 1982 because the committed Drugs@FDA payload records "
            + "NDA018104 ORIG/AP on 1982-12-29. It remains retained, not dropped."
        )
    return out


def assign_ids(rows: list[dict]) -> None:
    """Assign IDs only to the new 1980-1982 groups; preserve v13 IDs."""
    counters: Counter[str] = Counter()
    for row in sorted(rows, key=lambda r: (int(r["year"]), r["decision_date"], r["application_number"])):
        year = row["year"]
        if year not in ("1980", "1981", "1982"):
            continue
        counters[year] += 1
        row["decision_id"] = f"PRE1985-{year}-{counters[year]:02d}"


def assert_existing_row(row: dict) -> dict:
    appl = row["application_number"].replace(" ", "")
    payload = payload_for(appl)
    if payload["decision_date"] != row["decision_date"]:
        raise SystemExit(
            f"{row['decision_id']}: date {row['decision_date']} != payload {payload['decision_date']}"
        )
    payload_class = payload.get("submission_class_code") or "NOT STATED"
    if row["chemical_type_code"] != payload_class and row["chemical_type_code"] != "NOT STATED":
        raise SystemExit(
            f"{row['decision_id']}: class {row['chemical_type_code']!r} != payload {payload_class!r}"
        )
    payload_priority = payload.get("review_priority") or "NOT STATED"
    if row["review_priority"] != payload_priority and row["review_priority"] != "NOT STATED":
        raise SystemExit(
            f"{row['decision_id']}: priority {row['review_priority']!r} != payload {payload_priority!r}"
        )
    return {
        "decision_id": row["decision_id"],
        "application": appl,
        "date": payload["decision_date"],
        "class": payload_class,
        "priority": payload_priority,
        "holder": payload.get("sponsor_name", ""),
    }


def era_rows(final_rows: list[dict]) -> list[dict]:
    # 1980-1982 use the complete committed Drugs@FDA Type-1/1-4 enumeration as
    # the transparent proxy.  No independent official annual NME table was
    # found for those years, so the source text says exactly what is counted.
    fixed = {
        "1980": {
            "total_nmes_approved": "9",
            "orphan_drug_act_status": "The Orphan Drug Act had not yet been enacted; no orphan-law framework applied to these approvals.",
            "statutory_framework": "Pre-Orphan Drug Act federal NDA framework; the 1962 Kefauver-Harris amendments governed efficacy and safety review.",
            "landmark_approvals": "Viroptic, Meclomen, Vansil, Cytadren, Ludiomil, Spectrobid",
            "historical_significance": "The committed Drugs@FDA extract enumerates nine TYPE-1 original approvals. This is an application-level enumeration, not a claimed contemporaneous CDER annual NME statistic; no official pre-1985 annual NME table was located. v17 (2026-09-19) OFFICIAL SERIES LOCATED: FDA's History Office tabulation 'Summary of NDA Approvals & Receipts, 1938 to the present' publishes NME counts by year back to 1940 (captured verbatim in data/raw/source_captures_2026_09_19/fda_history_nda_nme_approvals_1938_2022.json; crosswalk in data/fda_official_series_crosswalk.csv; gap analysis in data/pre1985_nme_gap_analysis.csv). The earlier 'no official pre-1985 annual NME table was located' sentence in this field is SUPERSEDED. 1980 official: 12 NMEs (114 NDAs approved). The project enumerates 9 TYPE 1/1-4 applications, so the official series exceeds the Drugs@FDA enumeration by 3 - a sized, flagged gap. The 4 payload rows with no published class code are all strengths/dosage forms of already-marketed ingredients (leucovorin, hydrocortisone/tetracycline, IV electrolytes), so the 3 missing NMEs sit in applications absent from the ORIG/AP payload altogether (the gap class proven for 1985). Identification requires the 1989 CDER statistical typescript (pp. 152-199) cited by FDA's own page.",
            "primary_source_basis": "openFDA Drugs@FDA ORIG/AP enumeration 1980 (data/raw/openfda_orig_decisions_1980_1984/decisions_1980.json: 82 original approvals; 9 TYPE 1/1-4 applications). No independent official annual NME table was located for 1980.",
        },
        "1981": {
            "total_nmes_approved": "23",
            "orphan_drug_act_status": "The Orphan Drug Act had not yet been enacted; no orphan-law framework applied to these approvals.",
            "statutory_framework": "Pre-Orphan Drug Act federal NDA framework under the Kefauver-Harris amendments.",
            "landmark_approvals": "Capoten, Nizoral, Tenormin, Xanax, Prostin VR Pediatric, Carafate, Buprenex, Pipracil",
            "historical_significance": "The committed Drugs@FDA extract enumerates 23 TYPE-1/1-4 original approvals. This transparent application-level count must not be presented as a reconstructed contemporaneous annual NME statistic. v17 (2026-09-19) OFFICIAL SERIES LOCATED: FDA's History Office tabulation 'Summary of NDA Approvals & Receipts, 1938 to the present' publishes NME counts by year back to 1940 (captured verbatim in data/raw/source_captures_2026_09_19/fda_history_nda_nme_approvals_1938_2022.json; crosswalk in data/fda_official_series_crosswalk.csv; gap analysis in data/pre1985_nme_gap_analysis.csv). The earlier 'no official pre-1985 annual NME table was located' sentence in this field is SUPERSEDED. 1981 official: 27 NMEs (96 NDAs approved). The project enumerates 23 TYPE 1/1-4 applications - the single largest pre-1985 shortfall (4). Same gap class as 1980: the 11 blank-class payload rows are all marketed ingredients (furosemide, metronidazole, ibuprofen, dopamine, TMP-SMX, nitroglycerin, bupivacaine), none of them an NME, so the 4 missing NMEs are not visible in the payload. Flagged, not guessed.",
            "primary_source_basis": "openFDA Drugs@FDA ORIG/AP enumeration 1981 (data/raw/openfda_orig_decisions_1980_1984/decisions_1981.json: 71 original approvals; 23 TYPE 1/1-4 applications). No independent official annual NME table was located for 1981.",
        },
        "1982": {
            "total_nmes_approved": "25",
            "orphan_drug_act_status": "The Orphan Drug Act was enacted the following year; these 1982 approvals predate its January 1983 enactment.",
            "statutory_framework": "Pre-Orphan Drug Act federal NDA framework under the Kefauver-Harris amendments.",
            "landmark_approvals": "Zovirax, Accutane, Humulin, Cardizem, Halcion, Biltricide, MPI DMSA, Factrel",
            "historical_significance": "The committed Drugs@FDA extract enumerates 25 TYPE-1 original applications, including the first recombinant-DNA pharmaceutical approval cohort. The count is explicitly an application-level enumeration, not a claimed CDER annual NME statistic. v17 (2026-09-19) OFFICIAL SERIES LOCATED: FDA's History Office tabulation 'Summary of NDA Approvals & Receipts, 1938 to the present' publishes NME counts by year back to 1940 (captured verbatim in data/raw/source_captures_2026_09_19/fda_history_nda_nme_approvals_1938_2022.json; crosswalk in data/fda_official_series_crosswalk.csv; gap analysis in data/pre1985_nme_gap_analysis.csv). The earlier 'no official pre-1985 annual NME table was located' sentence in this field is SUPERSEDED. 1982 official: 28 NMEs (116 NDAs approved). The project enumerates 25 TYPE 1/1-4 applications (including the Humulin BLAs), shortfall 3. The 17 blank-class payload rows are again all marketed ingredients (furosemide, metronidazole, TMP-SMX, lithium carbonate, potassium iodide, clomiphene, aminocaproic acid, sodium nitroprusside, IV electrolytes).",
            "primary_source_basis": "openFDA Drugs@FDA ORIG/AP enumeration 1982 (data/raw/openfda_orig_decisions_1980_1984/decisions_1982.json: 103 original approvals; 25 TYPE 1/1-4 applications). FDA/NIH historical records are linked in the decision-row notes.",
        },
        "1983": {
            "total_nmes_approved": "14",
            "orphan_drug_act_status": "Enacted Jan 4, 1983 (P.L. 97-414); first approvals under the Act reached the market (Lithostat, May 1983 - first orphan-drug approval; Chenix orphan-designated 1984-09-21).",
            "statutory_framework": "Orphan Drug Act established 7-year market exclusivity, clinical research tax credits, and protocol assistance.",
            "landmark_approvals": "Sandimmune, Zantac, Vepesid, Zinacef, Tracrium, Lithostat, Chymex",
            "historical_significance": "Pink Sheet reporting pinned 14 NMEs for 1983; Drugs@FDA indexes 13 TYPE-1 applications. The table tracks those 13 plus the separately verified Furosemide oral-solution original application, whose chemical type/priority are not stated. v15 (2026-09-18): the year's full original-approval enumeration is now tracked — all 70 ORIG/AP NDA/BLA approvals in the committed payload (13 TYPE 1 here + 56 non-Type-1 originals in fda_original_non_nme_decisions.csv + this furosemide row), proven row-by-row in data/focus_years_1980_1985_audit.csv (the six-year audit; v16 superseded the v15 261-row 1983-1985 file). v17 (2026-09-19) OFFICIAL SERIES LOCATED: FDA's History Office tabulation 'Summary of NDA Approvals & Receipts, 1938 to the present' publishes NME counts by year back to 1940 (captured verbatim in data/raw/source_captures_2026_09_19/fda_history_nda_nme_approvals_1938_2022.json; crosswalk in data/fda_official_series_crosswalk.csv; gap analysis in data/pre1985_nme_gap_analysis.csv). The earlier 'no official pre-1985 annual NME table was located' sentence in this field is SUPERSEDED. 1983 official: 14 NMEs (94 NDAs approved) - and this is the figure the Pink Sheet citation of 1984-01-16 matches independently. IMPORTANT ACCURACY CORRECTION: the project's 14 rows for 1983 are NOT those 14 official NMEs. 13 rows are TYPE 1/1-4 applications; the 14th (Furosemide Oral Solution, NDA018413) is a non-NME boundary row - a live openFDA spot check on 2026-09-19 returns a furosemide ORIG-1 approval dated 1968-03-20, fifteen years before this application. So the effective TYPE 1/1-4 count for 1983 is 13 against an official 14: a shortfall of 1, not a match. The furosemide row stays in the table as a documented boundary row and must not be added to NME counts.",
            "primary_source_basis": "openFDA Drugs@FDA ORIG/AP enumeration 1983 (data/raw/openfda_orig_decisions_1980_1984/decisions_1983.json: 70 original approvals; 13 TYPE 1); Pink Sheet 1984-01-16 ('the last of 14 new molecular entities cleared by the agency during 1983'); FDA OOPD records.",
        },
        "1984": {
            "total_nmes_approved": "19",
            "orphan_drug_act_status": "First full year under the Orphan Drug Act; Pentam 300 and Orap are documented orphan-law milestones.",
            "statutory_framework": "Hatch-Waxman Act (P.L. 98-417, Sept. 24, 1984) created the Section 505(j) ANDA pathway and patent-term restoration.",
            "landmark_approvals": "Nicorette, Rocephin, Augmentin, Normodyne/Trandate, Norcuron, Orap, Inocor, Micronase, Sufenta",
            "historical_significance": "Drugs@FDA indexes 19 TYPE-1/1-4 original applications; the table tracks all 19 plus Trandate's separately verified TYPE-5 new-manufacturer application. The older unpinned secondary '22 NMEs' figure remains flagged rather than repeated as fact. v15 (2026-09-18): the year's full original-approval enumeration is now tracked — all 109 ORIG/AP NDA/BLA approvals in the committed payload (19 TYPE 1/1-4 here + Trandate + 89 non-Type-1 originals in fda_original_non_nme_decisions.csv), proven row-by-row in data/focus_years_1980_1985_audit.csv (the six-year audit; v16 superseded the v15 261-row 1983-1985 file). v17 (2026-09-19) OFFICIAL SERIES LOCATED: FDA's History Office tabulation 'Summary of NDA Approvals & Receipts, 1938 to the present' publishes NME counts by year back to 1940 (captured verbatim in data/raw/source_captures_2026_09_19/fda_history_nda_nme_approvals_1938_2022.json; crosswalk in data/fda_official_series_crosswalk.csv; gap analysis in data/pre1985_nme_gap_analysis.csv). The earlier 'no official pre-1985 annual NME table was located' sentence in this field is SUPERSEDED. 1984 official: 22 NMEs (142 NDAs approved - the largest NDA-approval year in FDA's own series). This CONFIRMS the previously 'unpinned secondary 22 NMEs figure': it is FDA's own published count. The project holds 20 rows for 1984: 19 TYPE 1/1-4 plus Trandate's TYPE 5 companion, so the effective shortfall against the official 22 is 3. The 17 blank-class payload rows are all marketed-ingredient formulations (furosemide, metronidazole, indomethacin, betamethasone dipropionate, methyldopa, fentanyl, allopurinol, tolazamide, fluocinonide).",
            "primary_source_basis": "openFDA Drugs@FDA ORIG/AP enumeration 1984 (data/raw/openfda_orig_decisions_1980_1984/decisions_1984.json: 109 original approvals; 19 TYPE 1/1-4); FDA OOPD and contemporaneous records are linked in the rows.",
        },
        "1985": {
            "total_nmes_approved": "31",
            "orphan_drug_act_status": "Orphan designations expanding; modern CDER NME Compilation baseline start year.",
            "statutory_framework": "Full implementation of Hatch-Waxman ANDA regulations; FDA's modern NME compilation begins with the 1985 cohort.",
            "landmark_approvals": "Protropin, Vasotec, Seldane, Marinol, Ridaura, Fortaz, Primaxin, Wellbutrin",
            "historical_significance": "Record post-1962 drug approval count of 31 NMEs per FDA's CDER NME Compilation; the existing master contains all 31, with four COMPILATION_ONLY rows documented in the verification report. v15 (2026-09-18) boundary audit: all 82 ORIG/AP payload decisions for 1985 are accounted for (27 master TYPE 1/1-4 matches + Temovate's companion TYPE 3 NDA019323 via the Compilation cross-reference + 54 published non-NME originals); the four master applications openFDA cannot enumerate (Seldane, Protropin, Suprol, Femstat) are pinned as a documented Drugs@FDA completeness gap in data/focus_years_1980_1985_audit.csv (the six-year audit; v16 superseded the v15 261-row 1983-1985 file). v17 (2026-09-19) OFFICIAL SERIES LOCATED: FDA's History Office tabulation 'Summary of NDA Approvals & Receipts, 1938 to the present' publishes NME counts by year back to 1940 (captured verbatim in data/raw/source_captures_2026_09_19/fda_history_nda_nme_approvals_1938_2022.json; crosswalk in data/fda_official_series_crosswalk.csv; gap analysis in data/pre1985_nme_gap_analysis.csv). The earlier 'no official pre-1985 annual NME table was located' sentence in this field is SUPERSEDED. 1985 official: 30 NMEs (100 NDAs approved). The Compilation's 31-row 1985 section therefore exceeds the official NME count by exactly 1. The Compilation's own landing page states its rule (Type 1/1-4 NDAs plus new biologics approved under a BLA; CBER products excluded), and Protropin/recombinant somatrem is the only 1985 row that is a biological product - recorded as the leading candidate for the +1 and NOT asserted (the workbook's own NDA/BLA column types all 31 rows 'NDA', so it cannot separate them). The 'record post-1962 count' framing in this field should also be read as a then-record: 30 exceeded the prior post-1962 peak (1982: 28) but was matched in 1991 and exceeded from 1996 (53). Tambocor's designation conflict (Compilation 'Priority' vs Drugs@FDA 'STANDARD') remains open; the 1985 medical review PDF is registered and Wayback-archived (five captures, 2021-2025) but returned HTTP 500 to every automated route tried on 2026-09-18 and 2026-09-19, so a human browser read is the last step (see data/pre1985_primary_captures_index.csv).",
            "primary_source_basis": "FDA CDER NME Compilation 1985-2025 (media/177921), fda_decisions_master.csv (1985 rows), and the committed openFDA 1985 extract.",
        },
    }
    fields = [
        "year", "total_nmes_approved", "official_fda_nme_count", "nme_comparable_rows",
        "official_series_delta", "verified_decisions_tracked", "priority_reviews",
        "standard_reviews", "orphan_drug_act_status", "statutory_framework",
        "landmark_approvals", "historical_significance", "primary_source_basis",
    ]
    output = []
    for year in ("1980", "1981", "1982", "1983", "1984", "1985"):
        group = [row for row in final_rows if row["year"] == year]
        if year == "1985":
            # 1985 is held in the master, not in the dedicated pre-1985 CSV.
            with (DATA / "fda_decisions_master.csv").open(newline="", encoding="utf-8") as fh:
                master = list(csv.DictReader(fh))
            group = [row for row in master if row.get("decision_date", "").startswith("1985-")]
        priority_field = "review_pathway" if year == "1985" else "review_priority"
        priorities = Counter(row.get(priority_field, "").upper() for row in group)
        base = fixed[year]
        # v17 (2026-09-19): official FDA NME counts (FDA History Office tabulation)
        # and the NME-comparable project enumeration.  total_nmes_approved keeps
        # the project's row count as first written; the official series lives in
        # its own fields so the two can never be confused again.
        v17_official = {"1980": 12, "1981": 27, "1982": 28, "1983": 14, "1984": 22, "1985": 30}
        v17_comparable = {"1980": 9, "1981": 23, "1982": 25, "1983": 13, "1984": 19, "1985": 31}
        comparable = v17_comparable[year]
        output.append({
            "year": year,
            "total_nmes_approved": base["total_nmes_approved"],
            "official_fda_nme_count": str(v17_official[year]),
            "nme_comparable_rows": str(comparable),
            "official_series_delta": str(comparable - v17_official[year]),
            "verified_decisions_tracked": str(len(group)),
            "priority_reviews": str(priorities.get("PRIORITY", 0)),
            "standard_reviews": str(priorities.get("STANDARD", 0)),
            "orphan_drug_act_status": base["orphan_drug_act_status"],
            "statutory_framework": base["statutory_framework"],
            "landmark_approvals": base["landmark_approvals"],
            "historical_significance": base["historical_significance"],
            "primary_source_basis": base["primary_source_basis"],
        })
    if [row["year"] for row in output] != ["1980", "1981", "1982", "1983", "1984", "1985"]:
        raise SystemExit("era rows are not in chronological order")
    # v17 pins: the official series and the derived delta must match the capture.
    v17_expect = {"1980": (12, 9, -3), "1981": (27, 23, -4), "1982": (28, 25, -3),
                  "1983": (14, 13, -1), "1984": (22, 19, -3), "1985": (30, 31, +1)}
    for row in output:
        official, comparable, delta = v17_expect[row["year"]]
        if (int(row["official_fda_nme_count"]), int(row["nme_comparable_rows"]),
                int(row["official_series_delta"])) != (official, comparable, delta):
            raise SystemExit(f"era {row['year']}: v17 official-series fields drift")
    return output


def main() -> None:
    decisions_path = DATA / "pre1985_fda_decisions.csv"
    era_path = DATA / "pre1985_era_analysis.csv"
    report_path = DATA / "staging" / "pre1985_expansion_report_v14.json"

    with decisions_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise SystemExit("pre1985 decision CSV has no header")
        existing = list(reader)

    old_hylorel_id = "PRE1985-1983-08"
    prior_v14_ids = {f"PRE1985-{year}-{number:02d}" for year in ("1980", "1981", "1982") for number in range(1, 26)}
    retained = []
    moved = []
    removed_duplicate_v14 = []
    for row in existing:
        is_hylorel = row["application_number"].replace(" ", "") == "NDA018104"
        if row["decision_id"] in prior_v14_ids and not is_hylorel:
            removed_duplicate_v14.append(row["decision_id"])
            continue
        if is_hylorel:
            previous_id = row["decision_id"]
            row = rehome_hylorel(row)
            moved.append({
                "from": old_hylorel_id if previous_id != old_hylorel_id else previous_id,
                "previous_current_id": previous_id,
                "to": row["decision_id"],
                "application": "NDA018104",
            })
        retained.append(row)

    # Re-assert all v13 rows, including Hylorel after the boundary move, against
    # the now-complete 1980-1984 payload set.
    assertions = []
    for row in retained:
        assertions.append(assert_existing_row(row))

    additions = []
    for meta in V14_META:
        row = assert_metadata(meta)
        additions.append(row)

    final_rows = retained + additions
    assign_ids(final_rows)
    final_rows.sort(key=lambda row: (int(row["year"]), row["decision_date"], row["decision_id"]))
    for move in moved:
        move["to"] = next(
            row["decision_id"] for row in final_rows
            if row["application_number"].replace(" ", "") == move["application"]
        )

    # Stable shape and application-level uniqueness.
    ids = [row["decision_id"] for row in final_rows]
    apps = [row["application_number"].replace(" ", "") for row in final_rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate decision IDs after v14 build")
    if len(apps) != len(set(apps)):
        raise SystemExit("duplicate application numbers after v14 build")
    expected_counts = {"1980": 9, "1981": 23, "1982": 25, "1983": 14, "1984": 20}
    actual_counts = Counter(row["year"] for row in final_rows)
    if {year: actual_counts.get(year, 0) for year in expected_counts} != expected_counts:
        raise SystemExit(f"v14 year counts mismatch: {dict(actual_counts)} != {expected_counts}")

    # The table must now cover exactly the payload TYPE 1/1-4 applications for
    # 1980-1982, with Hylorel included in the 1982 group.
    for year in (1980, 1981, 1982):
        payload_apps = {
            app for app, payload in PAYLOADS[year].items()
            if str(payload.get("submission_class_code", "")).startswith("TYPE 1")
        }
        table_apps = {
            row["application_number"].replace(" ", "")
            for row in final_rows if row["year"] == str(year)
        }
        if table_apps != payload_apps:
            raise SystemExit(f"{year}: table applications do not equal payload TYPE-1 enumeration")

    era = era_rows(final_rows)
    with decisions_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)
    with era_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(era[0].keys()))
        writer.writeheader()
        writer.writerows(era)

    report = {
        "version": "v14",
        "generated_utc": "2026-09-18",
        "method": "Committed openFDA Drugs@FDA ORIG/AP payloads; payload-derived date/class/priority/product fields asserted before write.",
        "moved": moved,
        "removed_duplicate_v14_rows_on_rerun": removed_duplicate_v14,
        "retained_assertions": assertions,
        "added": [
            {
                "decision_id": row["decision_id"],
                "application": row["application_number"].replace(" ", ""),
                "year": row["year"],
                "brand": row["drug_brand"],
                "date": row["decision_date"],
                "class": row["chemical_type_code"],
                "priority": row["review_priority"],
            }
            for row in additions
        ],
        "final_counts": dict(sorted(actual_counts.items())),
        "final_row_total": len(final_rows),
        "era_rows": era,
        "limitations": [
            "No official contemporaneous CDER annual NME table was located for 1980-1982; those era totals are explicitly labeled as the complete committed Drugs@FDA TYPE-1/1-4 application enumeration.",
            "1980s original submissions generally lack machine-readable application documents; indications are qualified and cited to later FDA labels, FDA/NIH records, or contemporaneous scientific sources.",
            "Corporate lineage and tickers are time-qualified; blank/uncertain beats assigning a modern ticker to a historical approval without period evidence.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)

    print(f"wrote {len(final_rows)} rows -> {decisions_path}")
    print(f"wrote {len(era)} era rows -> {era_path}")
    print("counts:", dict(sorted(actual_counts.items())))
    print("moved:", moved)
    print("added:", len(additions))
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
