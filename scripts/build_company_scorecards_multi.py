# -*- coding: utf-8 -*-
"""
Appends per-company scorecards for companies with TWO OR MORE tracked FDA
decisions (approvals 2021-2026 and/or CRLs) to data/company_scorecards.csv.

Scope note (important): for these multi-approval companies - mostly large
pharma - this scorecard tracks the NOVEL DRUG APPROVALS captured in this
project's verified dataset (data/fda_decisions_master.csv +
data/fda_crl_master.csv), NOT the company's full development pipeline
(hundreds of programs for the largest companies). Post-approval status
changes (withdrawals, accelerated-to-traditional conversions) are recorded
only where verified from FDA sources. This keeps every cell traceable to
an official source per the project's no-hallucination rule.

Run order: build_company_scorecards.py first, then this script.
"""
import csv
from collections import defaultdict

FDA_PAGES = {
    2021: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2021",
    2022: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2022",
    2023: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2023",
    2024: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2024",
    2025: "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2025",
}
FDA_REPORTS = {
    2021: "https://www.fda.gov/media/155227/download?attachment",
    2022: "https://www.fda.gov/media/164429/download?attachment",
    2023: "https://www.fda.gov/media/175253/download?attachment",
}

# Verified post-approval status annotations (from FDA sources / verified press).
STATUS = {
"Ukoniq": "VOLUNTARILY WITHDRAWN from US market Apr 2022 (updated UNITY-CL-01 data showed possible increased risk of death)",
"Relyvrio": "VOLUNTARILY WITHDRAWN from US market Apr 2024 after Phase 3 PHOENIX failed primary endpoint",
"Leqembi": "Accelerated approval converted to traditional approval Jul 2023",
}

# Verified accelerated->traditional conversion count per ticker (FDA-report-verified).
CONVERSIONS = {"4523.T": 1}   # Leqembi (Eisai), per FDA 2023 novel drug approvals report

# Listed-entity company name overrides where the master row's company_name
# leads with a non-listed partner (developer/licensee).
COMPANY_OVERRIDE = {
    "INVA": "Innoviva / Innoviva Specialty Therapeutics",
    "GSK": "GSK plc (incl. ViiV Healthcare)",
    "JNJ": "Johnson & Johnson (Janssen Biotech)",
    "4578.T": "Otsuka Holdings (incl. Taiho Oncology, Visterra)",
    "PLX": "Protalix BioTherapeutics (developer; applicant Chiesi)",
}

EXTRA_NOTES = {
"4523.T": "Leqembi is co-developed/co-commercialized with Biogen; Eisai was the BLA applicant",
"BIIB": "Also co-develops/co-commercializes Leqembi with Eisai (Leqembi row is credited to applicant Eisai, 4523.T); acquired Reata (Skyclarys, 2023) - Skyclarys row is credited to Reata (RETA) whose approval-window prices are unavailable",
"MRK.DE": "Merck KGaA (Darmstadt), operating as EMD Serono in the US - a different company from Merck & Co. (MRK); also acquired SpringWorks (Ogsiveo, closed Jul 2025) - Ogsiveo row is credited to SpringWorks (SWTX)",
"SWTX": "SpringWorks was independent at its Ogsiveo approval (Nov 2023); acquired by Merck KGaA (closed Jul 1 2025)",
"4578.T": "Scorecard tracks Otsuka Holdings (parent of Taiho/Janssen-partnered units); Visterra subsidiary approvals are also included",
"AZN": "Datroway is co-developed with Daiichi Sankyo; Beyfortus is commercialized in partnership with Sanofi; Wainua (Ionis-originated, eplontersen) is now held by AstraZeneca per openFDA",
"PFE": "Ngenla developed under the OPKO Health partnership",
"ROIV": "Vtama (Dermavant) entry predates the 2024 Organon US-rights acquisition; Roivant used as listed proxy",
"TAK": "Fruzaqla US rights in-licensed from HUTCHMED",
"IONS": "Wainua later licensed to/held by AstraZeneca per openFDA; Tryngolza and Dawnzera are Ionis-led approvals",
}

def main():
    decisions = list(csv.DictReader(open("data/fda_decisions_master.csv", encoding="utf-8")))
    crls = list(csv.DictReader(open("data/fda_crl_master.csv", encoding="utf-8")))

    by_ticker = defaultdict(list)
    for d in decisions:
        if d["ticker"] not in ("NO_TICKER", ""):
            by_ticker[d["ticker"]].append(d)
    for c in crls:
        if c["ticker"] not in ("NO_TICKER", ""):
            by_ticker[c["ticker"]].append(c)

    existing = list(csv.DictReader(open("data/company_scorecards.csv", encoding="utf-8")))
    existing_tickers = {r["ticker"] for r in existing}

    header = ["company_name","ticker","total_pipeline_programs_tracked","approved_count",
              "advanced_to_next_phase_count","paused_or_clinical_hold_count",
              "crl_rejected_count","phase_details","source_url_1","source_url_2",
              "verification_status","notes"]

    out = []
    for ticker, rows in sorted(by_ticker.items()):
        if len(rows) < 2 or ticker in existing_tickers:
            continue
        approvals = [r for r in rows if r.get("decision_type")]
        crl_rows = [r for r in rows if not r.get("decision_type")]
        company = COMPANY_OVERRIDE.get(ticker, rows[0]["company_name"].split(" (")[0].split(" / ")[0])
        years = sorted({int(r["decision_date"][:4]) if r.get("decision_date") else int(r["crl_date"][:4]) for r in rows})
        details = []
        for r in sorted(rows, key=lambda r: r.get("decision_date") or r.get("crl_date")):
            if r.get("decision_type"):
                st = STATUS.get(r["drug_brand"], "")
                details.append(f"{r['drug_brand']} ({r['indication']}): Approved {r['decision_date']} "
                               f"[{r['review_pathway']}]" + (f" - {st}" if st else ""))
            else:
                details.append(f"{r['drug_name']}: CRL {r['crl_date']} ({r['reason_category']})")
        note = ("Scorecard scope: FDA novel-drug decisions tracked in this project (2021-2026), not the full corporate pipeline. "
                "Post-approval advances counted only where FDA-verified (accelerated-to-traditional conversions).")
        if ticker in EXTRA_NOTES:
            note = EXTRA_NOTES[ticker] + ". " + note
        src1 = FDA_PAGES.get(years[0], FDA_PAGES[2025])
        src2 = FDA_REPORTS.get(years[-1], FDA_PAGES.get(years[-1], FDA_PAGES[2025]))
        out.append([
            company, ticker, len(rows), len(approvals),
            CONVERSIONS.get(ticker, 0), 0, len(crl_rows),
            " | ".join(details), src1, src2, "Verified", note,
        ])

    if out:
        with open("data/company_scorecards.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerows(out)
    print(f"Appended {len(out)} multi-approval scorecards")

if __name__ == "__main__":
    main()
