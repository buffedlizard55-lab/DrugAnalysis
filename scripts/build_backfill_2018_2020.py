#!/usr/bin/env python3
"""Append the 2018-2020 backfill (100 verified FDA novel-drug approvals) to the master list.

Every field in a new row traces to a capture in data/staging/:
  * drug / ingredient / date / indication / application number  -> archived official FDA
    novel-drug-approval tables (2018, 2020) or the FDA 2019 annual report PDF (Appendix A),
    both stored verbatim in data/staging/backfill_2018_2020_verbatim.json and
    data/staging/fda_novel_2019_full.json.
  * company_name / ticker / exchange                            -> one openFDA Drugs@FDA count
    query per drug (sponsor term recorded verbatim) plus, where a price was captured, the
    Yahoo Finance chart-API meta block (longName / fullExchangeName).
  * prices                                                      -> Yahoo chart API closes only.

Rules enforced here (the same rules the rest of the repository follows):
  * blank beats guessed - no date, price, pathway, ticker or company is inferred;
  * openFDA reports the CURRENT applicant of record, so where that holder plainly is not the
    company that received the 2018-2020 approval the row is flagged and no price is attributed;
  * drugs whose sponsor openFDA can no longer resolve are still recorded (the approval itself is
    verified by the FDA table) but with company_name = "applicant not machine-verifiable" and no
    ticker asserted.

Idempotent: rows already present (same brand + decision date) are skipped.
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "data", "fda_decisions_master.csv")
SNAPSHOTS = os.path.join(ROOT, "data", "stock_price_snapshots.csv")
STAGING = os.path.join(ROOT, "data", "staging", "backfill_2018_2020_verbatim.json")
STAGING19 = os.path.join(ROOT, "data", "staging", "fda_novel_2019_full.json")

FDA18 = ("https://web.archive.org/web/20240420232222/https://www.fda.gov/drugs/"
         "novel-drug-approvals-fda/novel-drug-approvals-2018")
FDA20 = ("https://web.archive.org/web/20240430031332/https://www.fda.gov/drugs/"
         "novel-drug-approvals-fda/novel-drug-approvals-2020")
FDA19 = "https://www.fda.gov/media/133911/download"
DAF = ("http://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
       "?event=overview.process&varApplNo=")
OPENFDA = ('https://api.fda.gov/drug/drugsfda.json?search=openfda.brand_name:'
           '%22{q}%22&count=sponsor_name')

# ---------------------------------------------------------------- verification wording
V_OK = "Verified"
V_YH = ("Verified (ticker + exchange confirmed 2026-09-12 via Yahoo Finance chart API "
        "meta: longName / fullExchangeName)")
V_HOLD = ("Verified - FLAGGED (openFDA reports a later holder; the issuer at the decision "
          "date was not re-verified in this pass)")
V_NOSPN = "Verified - FLAGGED (applicant of record not machine-verifiable today)"
V_EQ = "Verified - FLAGGED (no US-investable equity verified in this pass)"

# exchange strings drive scripts/classify_listing.py
EX_UNV = "No US-listed equity verified in this pass"
EX_NOSPN = "N/A - applicant not machine-verifiable; no listed equity verified in this pass"
EX_PRIV = "N/A - privately held; no listed equity"

# brand -> (company_name, ticker, exchange, review_pathway, verification_status, extra note)
# Ticker/exchange strings that are not marked "verified in this pass" are re-used from an
# existing row of the same issuer in data/fda_decisions_master.csv (row cited in the note).
EQ = {
    # ---------------- 2018 (FDA table rows 59-24) ----------------
    "Ultomiris": ("Alexion Pharmaceuticals (openFDA applicant of record: ALEXION PHARM)",
                  "NO_US_TICKER", EX_UNV, "", V_EQ,
                  "Alexion's former Nasdaq listing (ALXN) and its later acquisition were not "
                  "re-verified in this pass, so no ticker is asserted."),
    "Elzonris": ("Stemline Therapeutics (Menarini group)", "NO_TICKER", "N/A", "", V_OK,
                 "Private per this dataset's Stemline rows (D149)."),
    "Asparlas": ("Servier Pharmaceuticals (Les Laboratoires Servier)", "NO_TICKER", "N/A",
                 "", V_OK, "Private per this dataset's Servier rows (D033)."),
    "Motegrity": ("Takeda Pharmaceutical Company Limited", "TAK", "NYSE", "", V_OK,
                  "Ticker/exchange re-used from row D092 (same issuer, already verified)."),
    "Xospata": ("Astellas Pharma Inc.", "ALPMY", "OTC ADR; primary TSE:4503", "", V_OK,
                "Ticker/exchange re-used from row D250 (same issuer, already verified)."),
    "Firdapse": ("Catalyst Pharmaceuticals (openFDA applicant of record: CATALYST PHARMS)",
                 "NO_US_TICKER", EX_UNV, "", V_EQ,
                 "IRREGULARITY: FDA's archived 2018 table prints this approval date as "
                 "11/28/2028. The row sits between Xospata (11/28/2018) and Vitrakvi "
                 "(11/26/2018) and links the November 2018 press release, so 2018-11-28 is "
                 "recorded and the typo is flagged. Yahoo returned 'Data doesn't exist' for "
                 "CPRX over Nov 2018, so neither the ticker nor a price could be verified."),
    "Vitrakvi": ("Bayer HealthCare (openFDA applicant of record: BAYER HEALTHCARE)", "BAYRY",
                 "OTC ADR; primary XETRA:BAYN", "", V_HOLD,
                 "Ticker/exchange re-used from row D080 (Bayer AG). Larotrectinib was "
                 "developed by Loxo Oncology; openFDA's holder today is Bayer, and the 2018 "
                 "applicant was not re-read from the approval letter."),
    "Daurismo": ("Pfizer Inc.", "PFE", "NYSE", "", V_OK,
                 "Ticker/exchange re-used from row D037."),
    "Gamifant": ("Novimmune S.A.", "NO_TICKER", EX_PRIV, "", V_OK,
                 "FDA's page prints the ingredient twice ('emapalumab-lzsgemapalumab-lzsg'); "
                 "normalised to emapalumab-lzsg."),
    "Aemcolo": ("Applicant not machine-verifiable (openFDA has no record for 'aemcolo')",
                "NO_TICKER", EX_NOSPN, "", V_NOSPN,
                "Approval verified by FDA's 2018 table row 50 (NDA 210910); the applicant "
                "could not be resolved from openFDA on 2026-09-12, so none is asserted."),
    "Yupelri": ("Mylan Ireland Ltd (openFDA applicant of record)", "NO_US_TICKER", EX_UNV,
                "", V_EQ,
                "The applicant of record is an Irish Mylan group entity; the group's US "
                "listing was not re-verified in this pass."),
    "Lorbrena": ("Pfizer Inc.", "PFE", "NYSE", "", V_OK, "Ticker/exchange re-used from D037."),
    "Xofluza": ("Genentech, Inc. (Roche group)", "RHHBY", "OTC ADR; primary SIX:ROG", "",
                V_OK, "Ticker/exchange re-used from row D021."),
    "Talzenna": ("Pfizer Inc.", "PFE", "NYSE", "", V_OK, "Ticker/exchange re-used from D037."),
    "Tegsedi": ("Applicant not machine-verifiable (openFDA has no record for 'tegsedi' or "
                "'inotersen')", "NO_TICKER", EX_NOSPN, "", V_NOSPN,
                "Approval verified by FDA's 2018 table row 45 (NDA 211172). Inotersen is "
                "commonly attributed to Ionis Pharmaceuticals (NASDAQ:IONS, row D040), but "
                "openFDA returned no record on 2026-09-12, so no company or ticker is asserted."),
    "Revcovi": ("Chiesi Farmaceutici (Chiesi USA, Inc.)", "NO_TICKER", "N/A", "", V_OK,
                "Private per this dataset's Chiesi rows (D151)."),
    "Nuzyra": ("Paratek Pharmaceuticals (openFDA applicant of record: PARATEK PHARMS)",
               "NO_US_TICKER", EX_UNV, "", V_EQ,
               "Paratek's former Nasdaq listing (PRTK) was not re-verified in this pass."),
    "Seysara": ("Almirall, S.A.", "NO_US_TICKER",
                "Bolsa de Madrid (parent); no US-listed equity verified in this pass", "",
                V_OK, "Spanish issuer; no US ADR asserted."),
    "Libtayo": ("Regeneron Pharmaceuticals, Inc.", "REGN", "NASDAQ", "", V_OK,
                "Ticker/exchange re-used from row D060."),
    "Vizimpro": ("Pfizer Inc.", "PFE", "NYSE", "", V_OK, "Ticker/exchange re-used from D037."),
    "Emgality": ("Eli Lilly and Company", "LLY", "NYSE", "", V_OK,
                 "Ticker/exchange re-used from row D022."),
    "Copiktra": ("Secura Bio (openFDA applicant of record: SECURA)", "NO_TICKER", EX_PRIV,
                 "", V_HOLD,
                 "Duvelisib originated at Infinity Pharmaceuticals and moved to Verastem "
                 "Oncology before Secura Bio; openFDA's current holder is Secura, and the "
                 "2018 applicant was not re-read from the approval letter."),
    "Ajovy": ("Teva Pharmaceutical Industries Limited", "TEVA",
              "NYSE (ADS; ordinary shares listed in Tel Aviv)", "", V_YH,
              "Yahoo chart meta returned longName 'Teva Pharmaceutical Industries Limited', "
              "fullExchangeName 'NYSE'. Price window captured for this approval."),
    "Lumoxiti": ("Applicant not machine-verifiable (openFDA has no record for 'lumoxiti')",
                 "NO_TICKER", EX_NOSPN, "", V_NOSPN,
                 "Approval verified by FDA's 2018 table row 36 (BLA 761104); the applicant "
                 "could not be resolved from openFDA on 2026-09-12."),
    "Pifeltro": ("Merck & Co., Inc.", "MRK", "NYSE", "", V_OK,
                 "Ticker/exchange re-used from row D008."),
    "Xerava": ("Tetraphase Pharmaceuticals (openFDA applicant of record: TETRAPHASE PHARMS)",
               "NO_US_TICKER", EX_UNV, "", V_EQ,
               "Tetraphase's former Nasdaq listing (TTPH) was not re-verified in this pass."),
    "Takhzyro": ("Dyax Corp. (openFDA applicant of record)", "NO_US_TICKER", EX_UNV, "", V_EQ,
                 "openFDA still names Dyax Corp., which has no current listing of its own; "
                 "the group it now belongs to was not re-verified in this pass."),
    "Oxervate": ("Dompe Farmaceutici S.p.A.", "NO_TICKER", EX_PRIV, "", V_OK,
                 "FDA's page prints the brand as 'O [xervate]'; normalised to Oxervate."),
    "Diacomit": ("Laboratoires Biocodex", "NO_TICKER", EX_PRIV, "", V_OK, ""),
    "Galafold": ("Amicus Therapeutics, Inc.", "FOLD",
                 "formerly NASDAQ:FOLD, delisted Apr 2026", "", V_OK,
                 "Ticker/exchange re-used from row D184 (same issuer, already verified)."),
    "Annovera": ("Mayne Pharma Group Limited", "MYX.AX", "ASX; no US listing", "", V_OK,
                 "Ticker/exchange re-used from row D235 (same issuer, already verified)."),
    "Onpattro": ("Alnylam Pharmaceuticals, Inc.", "ALNY", "NASDAQ", "", V_OK,
                 "Ticker/exchange re-used from row D124."),
    "Poteligeo": ("Kyowa Kirin Co., Ltd.", "NO_US_TICKER",
                  "Tokyo Stock Exchange (parent); no US-listed equity verified in this pass",
                  "", V_OK, "Japanese issuer; no US ADR asserted."),
    "Mulpleta": ("Applicant of record returned by openFDA: 'VANCOCIN ITALIA' (unresolved)",
                 "NO_US_TICKER", EX_UNV, "", V_NOSPN,
                 "IRREGULARITY: openFDA's holder for lusutrombopag does not match the sponsor "
                 "commonly reported for the 2018 approval. Recorded verbatim; no company name "
                 "or ticker is asserted."),
    "Omegaven": ("Fresenius Kabi (Fresenius group)", "NO_US_TICKER",
                 "Frankfurt/Xetra (parent group); no US-listed equity verified in this pass",
                 "", V_OK, ""),
    "Orilissa": ("AbbVie Inc.", "ABBV", "NYSE", "", V_OK,
                 "Ticker/exchange re-used from row D053."),

    # ---------------- 2019 (FDA 2019 annual report, Appendix A) ----------------
    "Accrufer": ("Shield Therapeutics plc (openFDA applicant of record: SHIELD TX)",
                 "NO_US_TICKER", EX_UNV, "", V_EQ,
                 "Shield's London (AIM) listing and its later acquisition were not re-verified "
                 "in this pass."),
    "Aklief": ("Galderma Group AG", "GALD.SW", "SIX Swiss Exchange; no US ticker", "", V_OK,
               "Ticker/exchange re-used from row D031. Galderma had no listed equity at the "
               "2019 approval; the SIX listing cited is the one already verified in this "
               "dataset for the same issuer."),
    "Beovu": ("Novartis AG", "NVS", "NYSE", "", V_OK,
              "Ticker/exchange re-used from row D050. IRREGULARITY carried from "
              "data/staging/fda_novel_2019_full.json: the approval announcement and the "
              "Appendix A approval date differ; the Appendix A date (10/07/2019) is used."),
    "Egaten": ("Novartis AG", "NVS", "NYSE", "Priority Review", V_OK,
               "Ticker/exchange re-used from row D050. Pathway from Appendix B of the FDA 2019 "
               "report (unambiguous designation line)."),
    "ExEm Foam": ("Giskit Inc. (openFDA applicant of record: GISKIT)", "NO_US_TICKER",
                  EX_UNV, "", V_EQ,
                  "The openFDA term 'GISKIT' could not be resolved to a listed issuer in this "
                  "pass, so no ticker or venue is asserted."),
    "Fetroja": ("Shionogi & Co., Ltd.", "SGIOF", "OTC ADR; primary TSE:4507",
                "Priority Review", V_OK,
                "Ticker/exchange re-used from row D266. Pathway from Appendix B (unambiguous)."),
    "(no trade name)": ("Applicant not machine-verifiable - see notes", "NO_TICKER",
                        EX_NOSPN, "", V_NOSPN, ""),
    "Ibsrela": ("Ardelyx, Inc.", "ARDX", "NASDAQ", "", V_YH,
                "Yahoo chart meta returned longName 'Ardelyx, Inc.', fullExchangeName "
                "'NasdaqGM'. Price window captured for this approval."),
    "Jeuveau": ("Evolus, Inc.", "EOLS", "NASDAQ", "", V_YH,
                "Yahoo chart meta returned longName 'Evolus, Inc.', fullExchangeName "
                "'NasdaqGM'. Price window captured for this approval."),
    "Nourianz": ("Kyowa Kirin Co., Ltd.", "NO_US_TICKER",
                 "Tokyo Stock Exchange (parent); no US-listed equity verified in this pass",
                 "", V_OK, "Japanese issuer; no US ADR asserted."),
    "Recarbrio": ("Merck & Co., Inc.", "MRK", "NYSE", "", V_OK,
                  "Ticker/exchange re-used from row D008. Pathway left blank: Appendix B lists "
                  "Recarbrio under Priority Review but the PDF text layer merged the "
                  "Recarbrio/Reyvow designation line, so it is not asserted."),
    "Reyvow": ("Eli Lilly and Company", "LLY", "NYSE", "", V_OK,
               "Ticker/exchange re-used from row D022. Pathway left blank: Appendix B lists "
               "Reyvow under Priority Review but the merged Recarbrio/Reyvow text-layer line "
               "makes it ambiguous."),
    "Rinvoq": ("AbbVie Inc.", "ABBV", "NYSE", "", V_OK,
               "Ticker/exchange re-used from row D053. Pathway left blank: Appendix B lists "
               "Rinvoq under Priority Review but the PDF text layer merged the "
               "Rinvoq/Rozlytrek designation line."),
    "Rozlytrek": ("Genentech, Inc. (Roche group)", "RHHBY", "OTC ADR; primary SIX:ROG", "",
                  V_OK, "Ticker/exchange re-used from row D021. Pathway left blank: Appendix B "
                  "lists Rozlytrek under both Priority Review and Accelerated Approval, but the "
                  "merged Rinvoq/Rozlytrek text-layer line makes it ambiguous."),
    "Scenesse": ("Clivunel Inc. (openFDA applicant of record: CLIVUNEL INC)", "NO_US_TICKER",
                 EX_UNV, "", V_HOLD,
                 "IRREGULARITY: openFDA's holder for afamelanotide no longer matches the "
                 "sponsor reported at the 2019 approval. Recorded verbatim; the earlier holder "
                 "was not re-read from the approval letter, so none is asserted."),
    "Sunosi": ("Axsome Malta Ltd (openFDA applicant of record: AXSOME MALTA)", "NO_US_TICKER",
               EX_UNV, "", V_HOLD,
               "IRREGULARITY: openFDA now names an Axsome entity for solriamfetol, which is not "
               "the holder reported at the 2019 approval. No company/ticker is asserted and no "
               "price reaction is attributed."),
    "TissueBlue": ("Dutch Ophthalmic Research Center International B.V.", "NO_TICKER",
                   EX_PRIV, "Priority Review", V_OK,
                   "Pathway from Appendix B (unambiguous designation line)."),
    "Vyleesi": ("Cosette Pharmaceuticals (openFDA applicant of record: COSETTE)", "NO_TICKER",
                EX_PRIV, "", V_HOLD,
                "IRREGULARITY: openFDA's holder for bremelanotide is not the holder reported at "
                "the 2019 approval; the earlier holder was not re-read from the approval letter."),
    "Vyondys 53": ("Sarepta Therapeutics, Inc.", "SRPT", "NASDAQ",
                   "Priority Review + Accelerated Approval", V_YH,
                   "Ticker/exchange re-used from row D108 and re-confirmed 2026-09-12 via "
                   "Yahoo chart meta ('Sarepta Therapeutics, Inc.' / NasdaqGS). Pathway from "
                   "Appendix B (unambiguous). Price window captured for this approval."),
    "Wakix": ("Harmony Biosciences (openFDA applicant of record: HARMONY)", "NO_US_TICKER",
              EX_UNV, "Priority Review", V_EQ,
              "Pathway from Appendix B (unambiguous). The openFDA term 'HARMONY' could not be "
              "tied to a listing verified in this pass, so no ticker is asserted."),
    "Xcopri": ("SK Life Science, Inc. (SK group)", "NO_US_TICKER",
               "Korea Exchange (parent); no US-listed equity verified in this pass", "", V_OK,
               "Korean issuer; no US ADR asserted."),
    "Xenleta": ("Applicant of record returned by openFDA: 'HONG KONG' (unresolved)",
                "NO_US_TICKER", EX_UNV, "Priority Review", V_NOSPN,
                "IRREGULARITY: openFDA returns the sponsor term 'HONG KONG' for both brand "
                "'xenleta' and generic 'lefamulin'. It cannot be resolved to an issuer, so no "
                "company name or ticker is asserted. Pathway from Appendix B (unambiguous)."),

    # ---------------- 2020 (FDA table rows 50-1) ----------------
    "Margenza": ("MacroGenics, Inc. (openFDA applicant of record: MACROGENICS INC)",
                 "NO_US_TICKER", EX_UNV, "", V_EQ,
                 "MacroGenics' Nasdaq listing (MGNX) was not verified in this pass, so no "
                 "ticker is asserted."),
    "Klisyri": ("Almirall, S.A.", "NO_US_TICKER",
                "Bolsa de Madrid (parent); no US-listed equity verified in this pass", "",
                V_OK, "Spanish issuer; no US ADR asserted."),
    "Orladeyo": ("BioCryst Pharmaceuticals, Inc.", "BCRX", "NASDAQ", "", V_YH,
                 "Yahoo chart meta returned longName 'BioCryst Pharmaceuticals, Inc.', "
                 "fullExchangeName 'NasdaqGS'. Price window captured for this approval."),
    "Gallium 68 PSMA-11": ("Applicant not machine-verifiable (openFDA has no record for this "
                           "generic)", "NO_TICKER", EX_NOSPN, "", V_NOSPN,
                           "Approval verified by FDA's 2020 table row 47 (NDA 212642)."),
    "Danyelza": ("Y-mAb Therapeutics, Inc. (openFDA applicant of record)", "NO_US_TICKER",
                 EX_UNV, "", V_EQ,
                 "Yahoo returned 'No data found, symbol may be delisted' for YMAB over the "
                 "Nov 2020 window, so neither the listing nor a price could be verified."),
    "Zokinvy": ("Sentynl Therapeutics, Inc.", "NO_TICKER",
                "N/A - privately held (Zydus group)", "", V_HOLD,
                "Private per this dataset's Sentynl row (D242). Lonafarnib originated at Eiger "
                "BioPharmaceuticals; openFDA's holder today is Sentynl and the 2020 applicant "
                "was not re-read from the approval letter, so no price reaction is attributed."),
    "Inmazeb": ("Regeneron Pharmaceuticals, Inc.", "REGN", "NASDAQ", "", V_OK,
                "Ticker/exchange re-used from row D060."),
    "Gavreto": ("Rigel Pharmaceuticals, Inc. (openFDA applicant of record: RIGEL PHARMS)",
                "RIGL", "NASDAQ", "", V_HOLD,
                "Ticker/exchange re-used from row D139 for the CURRENT holder. IRREGULARITY: "
                "pralsetinib was not approved to Rigel in Sep 2020, so RIGL's price on the "
                "decision date is deliberately NOT captured - it would be the wrong issuer."),
    "Detectnet": ("Curium Pharma", "NO_TICKER", EX_PRIV, "", V_OK, ""),
    "Sogroya": ("Novo Nordisk A/S", "NVO", "NYSE", "", V_OK,
                "Ticker/exchange re-used from row D042."),
    "Winlevi": ("Sun Pharmaceutical Industries Ltd.", "SUNPHARMA.NS",
                "NSE/BSE India; no US ADR", "", V_OK,
                "Ticker/exchange re-used from row D003."),
    "Enspryng": ("Genentech, Inc. (Roche group)", "RHHBY", "OTC ADR; primary SIX:ROG", "",
                 V_OK, "Ticker/exchange re-used from row D021."),
    "Viltepso": ("Nippon Shinyaku Co., Ltd.", "NO_US_TICKER",
                 "Tokyo Stock Exchange (parent); no US-listed equity verified in this pass",
                 "", V_OK, "Japanese issuer; no US ADR asserted."),
    "Olinvyk": ("Trevena, Inc.", "TRVN",
                "formerly NASDAQ:TRVN; now quoted on OTC Markets - Yahoo history rejected",
                "", V_EQ,
                "IRREGULARITY: Yahoo identified 'Trevena, Inc.' on 'OTC Markets OTCPK' but "
                "returned Aug 2020 closes of 1450.00-1956.25 against a current price of 0.011 "
                "and a 52-week high of 1.50. The series is internally inconsistent (a large "
                "reverse-split factor appears to be applied to raw and adjusted closes alike), "
                "so it is REJECTED and no price is stored."),
    "Lampit": ("Bayer AG (Bayer HealthCare)", "BAYRY", "OTC ADR; primary XETRA:BAYN", "",
               V_OK, "Ticker/exchange re-used from row D080."),
    "Monjuvi": ("MorphoSys US Inc. (openFDA applicant of record)", "NO_US_TICKER", EX_UNV,
                "", V_EQ,
                "MorphoSys's listing status changed after this approval and was not re-verified "
                "in this pass, so no ticker is asserted."),
    "Xeglyze": ("Applicant not machine-verifiable (openFDA has no record for 'xeglyze')",
                "NO_TICKER", EX_NOSPN, "", V_NOSPN,
                "Approval verified by FDA's 2020 table row 29 (NDA 206966)."),
    "Inqovi": ("Taiho Oncology, Inc. (Otsuka Holdings group)", "4578.T",
               "TSE Japan (parent only)", "", V_OK,
               "Parent ticker/exchange re-used from row D082 (Otsuka Holdings)."),
    "Rukobia": ("ViiV Healthcare (GSK group)", "GSK", "NYSE", "", V_OK,
                "Ticker/exchange re-used from row D049 (GSK plc, which includes ViiV)."),
    "Byfavo": ("Acacia Pharma (openFDA applicant of record: ACACIA)", "NO_US_TICKER", EX_UNV,
               "", V_EQ, "The openFDA term 'ACACIA' was not tied to a verified listing here."),
    "Dojolvi": ("Ultragenyx Pharmaceutical Inc.", "RARE", "NASDAQ", "", V_YH,
                "Yahoo chart meta returned longName 'Ultragenyx Pharmaceutical Inc.', "
                "fullExchangeName 'NasdaqGS'. Price window captured for this approval."),
    "Zepzelca": ("Jazz Pharmaceuticals plc", "JAZZ", "NASDAQ", "", V_OK,
                 "Ticker/exchange re-used from row D224."),
    "Uplizna": ("Viela Bio, Inc. (openFDA applicant of record: VIELA BIO)", "NO_US_TICKER",
                EX_UNV, "", V_HOLD,
                "Viela Bio's Nasdaq listing ended after this approval; the successor holder was "
                "not re-verified in this pass, so no ticker is asserted."),
    "Tauvid": ("Avid Radiopharmaceuticals, Inc. (openFDA applicant of record)", "NO_US_TICKER",
               EX_UNV, "", V_EQ,
               "The applicant has no separate listing of its own; the parent relationship was "
               "not re-verified in this pass, so no ticker is asserted."),
    "Artesunate": ("Applicant not machine-verifiable (openFDA has no record for 'artesunate')",
                   "NO_TICKER", EX_NOSPN, "", V_NOSPN,
                   "Approval verified by FDA's 2020 table row 21 (NDA 213036)."),
    "Cerianna": ("GE Healthcare (openFDA applicant of record)", "NO_US_TICKER", EX_UNV, "",
                 V_EQ,
                 "GE Healthcare's listing (and its relationship to GE at the 2020 approval "
                 "date) was not verified in this pass, so no ticker is asserted."),
    "Qinlock": ("Deciphera Pharmaceuticals (openFDA applicant of record: DECIPHERA PHARMS)",
                "NO_US_TICKER", EX_UNV, "", V_EQ,
                "Deciphera's Nasdaq listing (DCPH) is not present elsewhere in this dataset and "
                "was not verified in this pass, so no ticker is asserted."),
    "Tabrecta": ("Novartis AG", "NVS", "NYSE", "", V_OK,
                 "Ticker/exchange re-used from row D050."),
    "Ongentys": ("Amneal Pharmaceuticals (openFDA applicant of record: AMNEAL)", "NO_US_TICKER",
                 EX_UNV, "", V_HOLD,
                 "Opicapone originated with BIAL; openFDA's holder today is Amneal and the 2020 "
                 "applicant was not re-read from the approval letter."),
    "Trodelvy": ("Immunomedics, Inc. (openFDA applicant of record)", "NO_US_TICKER", EX_UNV,
                 "Accelerated Approval", V_HOLD,
                 "Pathway is stated on FDA's own 2020 table row (link text: 'FDA grants "
                 "accelerated approval to sacituzumab govitecan-hziy'). Immunomedics' Nasdaq "
                 "listing ended shortly after this approval; the successor holder was not "
                 "re-verified in this pass."),
    "Tukysa": ("Seagen Inc. (acquired by Pfizer)", "SGEN",
               "formerly NASDAQ:SGEN, delisted Dec 2023", "", V_OK,
               "Ticker/exchange re-used from row D213 (same issuer, already verified)."),
    "Isturisa": ("Recordati S.p.A. (Recordati Rare Diseases)", "NO_US_TICKER",
                "Borsa Italiana (parent); no US-listed equity verified in this pass", "", V_OK,
                "IRREGULARITY for review: row D113 of this dataset attributes 'Recordati Rare "
                "Diseases (current holder)' to Sanofi's ADR (SNY). Recordati S.p.A. is a Milan-"
                "listed issuer, so D113's ticker/exchange should be re-examined."),
    "Sarclisa": ("Sanofi (Sanofi-Aventis U.S. LLC)", "SNY", "NASDAQ", "", V_OK,
                 "Ticker/exchange re-used from row D048."),
    "Nurtec ODT": ("Pfizer Inc. (openFDA applicant of record: PFIZER)", "PFE", "NYSE", "",
                  V_HOLD,
                  "Ticker/exchange re-used from row D037 for the CURRENT holder. IRREGULARITY: "
                  "rimegepant was not approved to Pfizer in Feb 2020, so PFE's price on the "
                  "decision date is deliberately NOT captured."),
    "Barhemsys": ("Applicant of record returned by openFDA: 'LXO IRELAND' (unresolved)",
                  "NO_US_TICKER", EX_UNV, "", V_NOSPN,
                  "IRREGULARITY: the openFDA term cannot be resolved to an issuer, so no "
                  "company name or ticker is asserted."),
    "Vyepti": ("H. Lundbeck A/S group (Lundbeck Seattle BioPharmaceuticals, Inc.)",
               "NO_US_TICKER",
               "Nasdaq Copenhagen (parent); no US-listed equity verified in this pass", "",
               V_OK, "Danish parent; no US ADR asserted."),
    "Nexletol": ("Esperion Therapeutics, Inc. (openFDA applicant of record)", "ESPR",
                 "formerly NASDAQ:ESPR; symbol returned no data on 2026-09-12", "", V_EQ,
                 "Yahoo returned 'No data found, symbol may be delisted' for ESPR over the Feb "
                 "2020 window, so no price is stored and the current listing status is "
                 "unverified."),
    "Pizensy": ("Applicant not machine-verifiable (openFDA has no record for 'pizensy')",
                "NO_TICKER", EX_NOSPN, "", V_NOSPN,
                "Approval verified by FDA's 2020 table row 4 (NDA 211281)."),
    "Tazverik": ("Epizyme, Inc. (openFDA applicant of record: EPIZYME INC)", "NO_US_TICKER",
                 EX_UNV, "", V_HOLD,
                 "Epizyme's Nasdaq listing ended after this approval; the successor holder was "
                 "not re-verified in this pass."),
    "Tepezza": ("Horizon Therapeutics Ireland (openFDA applicant of record)", "NO_US_TICKER",
                EX_UNV, "", V_HOLD,
                "Horizon's Nasdaq listing ended after this approval; the successor holder was "
                "not re-verified in this pass."),
}

# date corrections where the FDA source page itself is wrong (flagged in the row notes)
DATE_FIX = {"Firdapse": "2018-11-28"}   # FDA's archived 2018 table prints 11/28/2028

# generic-name normalisation for FDA page typos (verbatim strings kept in staging)
GENERIC_FIX = {
    "emapalumab-lzsgemapalumab-lzsg": "emapalumab-lzsg",
    "margetuximab (anti-HER2 mAb": "margetuximab",
}
# 2019 Appendix A rows carry no application number in the report PDF
APPL19 = {}

# rows whose openFDA query used generic_name instead of brand_name
GENERIC_QUERIES = {
    "(no trade name)": None,  # handled per-ingredient below
    "pretomanid": "pretomanid",
}

# ---------------------------------------------------------------- prices (Yahoo closes)
PRICES = [
    # ticker, company, decision_date, decision_type, close_before, date_before,
    # close_on, date_on, close_later, date_later, source_url, note
    ("SRPT", "Sarepta Therapeutics, Inc.", "2019-12-12", "Approval", 101.45, "2019-12-11",
     100.47, "2019-12-12", 135.35, "2019-12-16",
     "https://query1.finance.yahoo.com/v8/finance/chart/SRPT?period1=1575504000"
     "&period2=1576713600&interval=1d",
     "Vyondys 53 (golodirsen) approval. The session close on the decision day was DOWN 0.97% "
     "(100.47 vs 101.45) because FDA's approval was announced after the close; the next "
     "session (2019-12-13) closed at 132.05, +31.43% on the decision-day close, on 10.8m "
     "shares vs a 1.1m-share prior day. This row is the clearest example in the dataset of "
     "why decision-day close alone understates a reaction."),
    ("ARDX", "Ardelyx, Inc.", "2019-09-12", "Approval", 5.80, "2019-09-11", 6.28,
     "2019-09-12", 5.04, "2019-09-16",
     "https://query1.finance.yahoo.com/v8/finance/chart/ARDX?period1=1567641600"
     "&period2=1568851200&interval=1d",
     "Ibsrela (tenapanor) approval: +8.28% on the decision day (6.28 vs 5.80), then the move "
     "fully reversed - 5.31 on 2019-09-13 and 5.04 on 2019-09-16 (-13.10% vs the decision-day "
     "close). Approval-day pops in IBS-C faded as payers and analysts questioned commercial "
     "scope."),
    ("EOLS", "Evolus, Inc.", "2019-02-01", "Approval", 16.35, "2019-01-31", 18.33,
     "2019-02-01", 25.83, "2019-02-05",
     "https://query1.finance.yahoo.com/v8/finance/chart/EOLS?period1=1548374400"
     "&period2=1549584000&interval=1d",
     "Jeuveau (prabotulinumtoxinA-xvfs) approval: +12.11% on the decision day and +57.98% by "
     "2019-02-05 (25.83 vs 16.35), on volume that rose from 0.6m to 8.2m shares. First "
     "commercial-stage product for a company that had IPO'd in Feb 2018."),
    ("BCRX", "BioCryst Pharmaceuticals, Inc.", "2020-12-03", "Approval", 5.04, "2020-12-02",
     5.14, "2020-12-03", 7.22, "2020-12-07",
     "https://query1.finance.yahoo.com/v8/finance/chart/BCRX?period1=1606348800"
     "&period2=1607558400&interval=1d",
     "Orladeyo (berotralstat) approval: +1.98% on the decision day, then +40.86% by 2020-12-07 "
     "(7.22 vs 5.14) on 29.8m shares vs 10.4m on the decision day - the reaction built over "
     "the following sessions rather than landing on the approval date."),
    ("RARE", "Ultragenyx Pharmaceutical Inc.", "2020-06-30", "Approval", 73.66, "2020-06-29",
     78.22, "2020-06-30", 86.04, "2020-07-02",
     "https://query1.finance.yahoo.com/v8/finance/chart/RARE?period1=1592870400"
     "&period2=1594080000&interval=1d",
     "Dojolvi (triheptanoin) approval: +6.19% on the decision day and +17.79% by 2020-07-02 "
     "(86.04 vs 73.66)."),
    ("TEVA", "Teva Pharmaceutical Industries Limited", "2018-09-14", "Approval", 22.21,
     "2018-09-13", 22.85, "2018-09-14", 24.46, "2018-09-18",
     "https://query1.finance.yahoo.com/v8/finance/chart/TEVA?period1=1536278400"
     "&period2=1537488000&interval=1d",
     "Ajovy (fremanezumab-vfrm) approval: +2.88% on the decision day, +10.13% by 2018-09-18 "
     "(24.46 vs 22.21). TEVA is the NYSE ADS; the decision-day move is diluted by Teva's "
     "generic-portfolio newsflow, which is why migraine-franchise approvals read as small "
     "percentage moves at large-cap issuers."),
]


def norm_date(s):
    m, d, y = s.split("/")
    return "%s-%02d-%02d" % (y, int(m), int(d))


def load():
    st = json.load(open(STAGING, encoding="utf-8"))
    st19 = json.load(open(STAGING19, encoding="utf-8"))
    return st, st19


def main():
    st, st19 = load()
    rows = list(csv.DictReader(open(MASTER, encoding="utf-8-sig")))
    fields = list(rows[0].keys())
    have = {(r["drug_brand"].strip().lower(), r["decision_date"]) for r in rows}
    next_id = max(int(r["decision_id"][1:]) for r in rows) + 1

    new = []

    def add(brand, generic, date_iso, indication, source_url_1, source_url_2, note_src):
        nonlocal next_id
        if (brand.strip().lower(), date_iso) in have:
            return False
        if brand not in EQ:
            raise SystemExit("no equity mapping for %r - refusing to guess" % brand)
        company, ticker, exchange, pathway, verification, extra = EQ[brand]
        notes = [note_src]
        if extra:
            notes.append(extra)
        rid = "D%d" % next_id
        next_id += 1
        new.append({
            "decision_id": rid, "company_name": company, "ticker": ticker,
            "exchange": exchange, "drug_brand": brand, "drug_generic": generic,
            "decision_type": "Approval", "decision_date": date_iso,
            "indication": indication, "review_pathway": pathway,
            "source_url_1": source_url_1, "source_url_2": source_url_2,
            "verification_status": verification, "notes": " ".join(notes).strip(),
            "us_investable_class": "", "classification_basis": "",
        })
        return True

    added18 = added20 = added19 = 0
    for row_no, brand, generic, date, appl, indication in st["fda_2018_rows_verbatim"]:
        generic = GENERIC_FIX.get(generic, generic)
        n = add(brand, generic, DATE_FIX.get(brand, norm_date(date)), indication, DAF + appl,
                OPENFDA.format(q=brand.lower().replace(" ", "%20")),
                "FDA 2018 novel-drug-approvals table row %d (archived capture %s); "
                "Drugs@FDA application %s; openFDA applicant term queried 2026-09-12."
                % (row_no, FDA18, appl))
        added18 += n
    for row_no, brand, generic, date, appl, indication in st["fda_2020_rows_verbatim"]:
        generic = GENERIC_FIX.get(generic, generic)
        n = add(brand, generic, norm_date(date), indication, DAF + appl,
                OPENFDA.format(q=brand.lower().replace(" ", "%20")),
                "FDA 2020 novel-drug-approvals table row %d (archived capture %s); "
                "Drugs@FDA application %s; openFDA applicant term queried 2026-09-12."
                % (row_no, FDA20, appl))
        added20 += n

    # 2019: facts come from the Appendix A capture already staged verbatim
    want19 = {b for b in EQ if b not in
              {r[1] for r in st["fda_2018_rows_verbatim"]} and b not in
              {r[1] for r in st["fda_2020_rows_verbatim"]}}
    aa = st19["appendix_A_novel_approvals_2019"]["entries_captured_verbatim"]
    bb = st19["appendix_B_pathway_subset"]
    for date, brand, generic, indication, form in aa:
        if brand not in want19:
            continue
        if brand == "(no trade name)":
            # three separate ingredients share this label; resolve individually
            key = generic.strip().lower()
            if key not in ("fluorodopa f 18", "gallium ga 68 dotatoc", "pretomanid"):
                continue
            if key == "pretomanid":
                company = "Mylan Ireland Ltd (openFDA applicant of record)"
                ticker, exchange = "NO_US_TICKER", EX_UNV
                verification = V_HOLD
                note = ("IRREGULARITY: openFDA names MYLAN IRELAND LTD for pretomanid while an "
                        "earlier pass in this repository recorded the sponsor as TB Alliance. "
                        "The machine-verifiable openFDA term is used and the difference is "
                        "flagged; no listing is asserted for the Irish applicant entity.")
                url2 = ("https://api.fda.gov/drug/drugsfda.json?search=openfda.generic_name:"
                        "%22pretomanid%22&count=sponsor_name")
            else:
                company = ("Applicant not machine-verifiable (openFDA has no record for this "
                           "generic)")
                ticker, exchange = "NO_TICKER", EX_NOSPN
                verification = V_NOSPN
                note = ("openFDA returns no record for generic '%s' (queried 2026-09-12), so no "
                        "applicant is asserted. An earlier pass noted '%s' from the FDA report, "
                        "which was not machine-verified."
                        % (generic, "Curium" if "fluorodopa" in key
                           else "UIHC PET Imaging Center"))
                url2 = ("https://api.fda.gov/drug/drugsfda.json?search=openfda.generic_name:"
                        "%%22%s%%22&count=sponsor_name" % generic.lower().replace(" ", "%20"))
            if (brand.strip().lower(), norm_date(date)) in have:
                continue
            if ("%s (%s)" % (brand, generic)).strip().lower() in {
                    r[0] for r in have}:
                continue
            rid = "D%d" % next_id
            next_id += 1
            new.append({
                "decision_id": rid, "company_name": company, "ticker": ticker,
                "exchange": exchange, "drug_brand": "%s (%s)" % (brand, generic),
                "drug_generic": generic, "decision_type": "Approval",
                "decision_date": norm_date(date), "indication": indication,
                "review_pathway": "Priority Review" if generic == "pretomanid" else "",
                "source_url_1": FDA19, "source_url_2": url2,
                "verification_status": verification,
                "notes": ("FDA 2019 annual report Appendix A (no trade name assigned); %s. "
                          "Dosage form: %s." % (note, form)).strip(),
                "us_investable_class": "", "classification_basis": ""})
            added19 += 1
            continue
        eq = EQ[brand]
        company, ticker, exchange, pathway, verification, extra = eq
        if (brand.strip().lower(), norm_date(date)) in have:
            continue
        rid = "D%d" % next_id
        next_id += 1
        new.append({
            "decision_id": rid, "company_name": company, "ticker": ticker,
            "exchange": exchange, "drug_brand": brand, "drug_generic": generic,
            "decision_type": "Approval", "decision_date": norm_date(date),
            "indication": indication, "review_pathway": pathway,
            "source_url_1": FDA19,
            "source_url_2": OPENFDA.format(q=brand.lower().replace(" ", "%20")),
            "verification_status": verification,
            "notes": ("FDA 2019 annual report Appendix A (verbatim capture in "
                      "data/staging/fda_novel_2019_full.json); dosage form %s; openFDA "
                      "applicant term queried 2026-09-12.%s"
                      % (form, (" " + extra) if extra else "")).strip(),
            "us_investable_class": "", "classification_basis": ""})
        added19 += 1

    rows.extend(new)
    rows.sort(key=lambda r: (r["decision_date"], r["decision_id"]))
    with open(MASTER, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # ------------------------------------------------------------- price snapshots
    snaps = list(csv.DictReader(open(SNAPSHOTS, encoding="utf-8-sig")))
    sfields = list(snaps[0].keys())
    shave = {(s["ticker"], s["decision_date"]) for s in snaps}
    added_p = 0
    for (t, comp, ddate, dtype, cb, db, co, do, cl, dl, url, note) in PRICES:
        if (t, ddate) in shave:
            continue
        pct = "" if not cb else "%.2f%%" % ((co / cb - 1) * 100)
        snaps.append({
            "ticker": t, "company": comp, "decision_date": ddate, "decision_type": dtype,
            "close_before": cb, "date_before": db, "close_on_or_after": co,
            "date_on_or_after": do, "close_few_days_later": cl, "date_few_days_later": dl,
            "pct_change_on_decision": pct, "source_url": url, "verification_status":
            "Verified - Yahoo Finance chart API (query1.finance.yahoo.com), captured "
            "2026-09-12", "notes": note})
        added_p += 1
    snaps.sort(key=lambda s: (s["decision_date"], s["ticker"]))
    with open(SNAPSHOTS, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=sfields)
        w.writeheader()
        w.writerows(snaps)

    print("added 2018 rows:", added18)
    print("added 2019 rows:", added19)
    print("added 2020 rows:", added20)
    print("total new master rows:", len(new), "-> master now", len(rows))
    print("price snapshots added:", added_p, "-> total", len(snaps))


if __name__ == "__main__":
    main()
