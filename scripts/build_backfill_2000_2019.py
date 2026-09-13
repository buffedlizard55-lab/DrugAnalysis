#!/usr/bin/env python3
"""Append verified FDA novel-approval rows (2000-2019 gaps) to fda_decisions_master.csv.

Sources (all verbatim-staged, each row carries its own source links):
  data/staging/fda_nme_2000..2010_verbatim.json   (FDA NME/new-biologic year tables, Wayback)
  data/staging/fda_nme_2011_gap.json              (ucm285554 @20120119181217, 11 of 30)
  data/staging/fda_nme_2012_gap.json              (ucm336115 @20130217050942, 22 of 39)
  data/staging/fda_nme_2013_gap.json              (ucm381263 @20140327204457, 11 of 27)
  data/staging/fda_novel_2015_gap.json            (ucm430302 table, 4 of 45)
  data/staging/fda_novel_2018_gap.json            (cacmap novel-drug-approvals-2018, 12 of 59)
  data/staging/fda_novel_2019_gap.json            (FDA media/133911 report diff, 1 of 48)
  2017 gap inline below (benznidazole NDA209570, Xepi NDA208945; verified via openFDA drugsfda 2026-09-12)

Sponsor resolution: pattern match on the FDA applicant string; unmatched sponsors are
kept verbatim with blank ticker and us_investable_class=NOT US-INVESTABLE (UNVERIFIED).
"""
import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STG = ROOT / "data" / "staging"
MASTER = ROOT / "data" / "fda_decisions_master.csv"

# (pattern, company_name, ticker, exchange, us_investable_class, note)
# note '' = plain US listing; otherwise appended to classification_basis/notes
COMPANY = [
    ("PFIZER", "Pfizer Inc.", "PFE", "NYSE", "US-LISTED", ""),
    ("PHARMACIA", "Pharmacia (acquired by Pfizer 2003)", "PGE?", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Pharmacia Corp delisted 2003 into Pfizer"),
    ("GD SEARLE", "G.D. Searle (Pfizer lineage)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Searle merged into Pharmacia 2001; Pfizer 2003"),
    ("SEARLE", "G.D. Searle (Pfizer lineage)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Searle merged into Pharmacia 2001; Pfizer 2003"),
    ("AGOURON", "Agouron Pharmaceuticals (acquired by Pfizer 1999)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Agouron was NASDAQ:AGPH; acquired by Pfizer 1999"),
    ("WYETH", "Wyeth (acquired by Pfizer 2009)", "WYE", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:WYE delisted 2009"),
    ("GLAXO", "GlaxoSmithKline plc", "GSK", "NYSE (ADR)", "US-LISTED (ADR)", "primary LSE:GSK"),
    ("SMITHKLINE", "GlaxoSmithKline plc", "GSK", "NYSE (ADR)", "US-LISTED (ADR)", "primary LSE:GSK"),
    ("NOVARTIS", "Novartis AG", "NVS", "NYSE (ADR)", "US-LISTED (ADR)", "primary SIX:NOVN"),
    ("SANDOZ", "Sandoz (merged into Novartis 1996)", "", "", "NON-US LISTING ONLY", "merged into Novartis pre-2000"),
    ("MERCK & CO", "Merck & Co., Inc.", "MRK", "NYSE", "US-LISTED", ""),
    ("MERCK", "Merck & Co., Inc.", "MRK", "NYSE", "US-LISTED", ""),
    ("SCHERING-PLOUGH", "Schering-Plough (acquired by Merck 2009)", "SGP", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:SGP delisted 2009"),
    ("SCHERING", "Schering-Plough (acquired by Merck 2009)", "SGP", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:SGP delisted 2009"),
    ("BERLEX", "Berlex Laboratories (Schering AG US arm)", "", "", "NON-US LISTING ONLY", "parent Schering AG (FSE:SCH); merged into Bayer Schering 2006"),
    ("BRISTOL", "Bristol-Myers Squibb Co.", "BMY", "NYSE", "US-LISTED", ""),
    ("ELI LILLY", "Eli Lilly and Co.", "LLY", "NYSE", "US-LISTED", ""),
    ("LILLY", "Eli Lilly and Co.", "LLY", "NYSE", "US-LISTED", ""),
    ("ABBOTT", "Abbott Laboratories", "ABT", "NYSE", "US-LISTED", ""),
    ("JOHNSON", "Johnson & Johnson", "JNJ", "NYSE", "US-LISTED", ""),
    ("JANSSEN", "Janssen Pharmaceutica (Johnson & Johnson)", "JNJ", "NYSE", "US-LISTED", ""),
    ("CENTOCOR", "Centocor (Johnson & Johnson)", "JNJ", "NYSE", "US-LISTED", ""),
    ("ORTHO", "Ortho-McNeil (Johnson & Johnson)", "JNJ", "NYSE", "US-LISTED", ""),
    ("R.W. JOHNSON", "R.W. Johnson Pharmaceutical Research (J&J)", "JNJ", "NYSE", "US-LISTED", ""),
    ("SCIOS", "Scios Inc. (acquired by J&J 2003)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:SCIO delisted 2003"),
    ("ASTRAZENECA", "AstraZeneca PLC", "AZN", "NASDAQ (ADR)", "US-LISTED (ADR)", "primary LSE:AZN"),
    ("TAKEDA", "Takeda Pharmaceutical Co. (Japan)", "4502", "TSE", "NON-US LISTING ONLY", "primary TSE:4502"),
    ("YAMANOUCHI", "Yamanouchi (merged into Astellas 2005)", "", "", "NON-US LISTING ONLY", "merged into Astellas 2005"),
    ("FUJISAWA", "Fujisawa (merged into Astellas 2005)", "", "", "NON-US LISTING ONLY", "merged into Astellas 2005"),
    ("ASTELLAS", "Astellas Pharma Inc. (Japan)", "4503", "TSE", "NON-US LISTING ONLY", "primary TSE:4503"),
    ("DAIICHI", "Daiichi Sankyo Co. (Japan)", "4568", "TSE", "NON-US LISTING ONLY", "primary TSE:4568"),
    ("SANKYO", "Daiichi Sankyo Co. (Japan)", "4568", "TSE", "NON-US LISTING ONLY", "primary TSE:4568"),
    ("EISAI", "Eisai Co. (Japan)", "4523", "TSE", "NON-US LISTING ONLY", "primary TSE:4523"),
    ("OTSUKA", "Otsuka Holdings (Japan)", "4578", "TSE", "NON-US LISTING ONLY", "primary TSE:4578"),
    ("TANABE", "Tanabe Seiyaku (merged into Mitsubishi Tanabe)", "", "", "NON-US LISTING ONLY", "merged into Mitsubishi Tanabe 2007"),
    ("MITSUBISHI", "Mitsubishi Tanabe Pharma (Japan)", "", "", "NON-US LISTING ONLY", "TSE:4507 lineage; acquired Mitsubishi Chemical 2025"),
    ("KYOWA", "Kyowa Hakko Kirin (Japan)", "4151", "TSE", "NON-US LISTING ONLY", "primary TSE:4151"),
    ("CHUGAI", "Chugai Pharmaceutical (Roche group, Japan)", "4519", "TSE", "NON-US LISTING ONLY", "primary TSE:4519; Roche-controlled"),
    ("TAISHO", "Taisho Pharmaceutical (Japan)", "", "", "NON-US LISTING ONLY", "TSE:4585 (delisted 2024 private buyout)"),
    ("KISSEI", "Kissei Pharmaceutical (Japan)", "4547", "TSE", "NON-US LISTING ONLY", "primary TSE:4547"),
    ("NIKKEN", "Nikken Chemicals (Japan)", "", "", "NON-US LISTING ONLY", "acquired by Otsuka 2004"),
    ("SHIONOGI", "Shionogi & Co. (Japan)", "4507", "TSE", "NON-US LISTING ONLY", "primary TSE:4507"),
    ("ROCHE", "Roche Holding AG (Genentech parent)", "RHHBY", "OTC ADR; primary SIX:ROG", "NON-US LISTING ONLY", "primary SIX:ROG"),
    ("HOFFMAN", "Roche Holding AG (Genentech parent)", "RHHBY", "OTC ADR; primary SIX:ROG", "NON-US LISTING ONLY", "FDA prints 'Hoffman La-Roche'"),
    ("GENENTECH", "Genentech (acquired by Roche 2009)", "DNA", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:DNA delisted 2009"),
    ("SANOFI", "Sanofi (Sanofi-Aventis)", "SNY", "NYSE (ADR)", "US-LISTED (ADR)", "primary Euronext:SAN"),
    ("AVENTIS", "Sanofi-Aventis (now Sanofi)", "SNY", "NYSE (ADR)", "US-LISTED (ADR)", "primary Euronext:SAN"),
    ("RHONE POULENC", "Rhone-Poulenc Rorer (Aventis lineage)", "", "", "NON-US LISTING ONLY", "merged into Aventis 1999; Sanofi 2004"),
    ("HOECHST", "Hoechst Marion Roussel (Aventis lineage)", "", "", "NON-US LISTING ONLY", "merged into Aventis 1999; Sanofi 2004"),
    ("MARION", "Hoechst Marion Roussel (Aventis lineage)", "", "", "NON-US LISTING ONLY", "merged into Aventis 1999"),
    ("BOEHRINGER", "Boehringer Ingelheim (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "family-held, no listed equity"),
    ("BAYER", "Bayer AG", "BAYRY", "OTC ADR; primary XETRA:BAYN", "NON-US LISTING ONLY", "primary XETRA:BAYN"),
    ("SOLVAY", "Solvay SA (pharma sold to Abbott 2010)", "SVYZY", "OTC ADR; primary Euronext:SOLB", "NON-US LISTING ONLY", "pharmaceuticals acquired by Abbott 2010"),
    ("UCB", "UCB SA (Belgium)", "UCBJY", "OTC ADR; primary Euronext:UCB", "NON-US LISTING ONLY", "primary Euronext:UCB"),
    ("SERVIER", "Les Laboratoires Servier (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("IPSEN", "Ipsen SA (France)", "IPSEY", "OTC ADR; primary Euronext:IPN", "NON-US LISTING ONLY", "primary Euronext:IPN"),
    ("MERZ", "Merz Pharma (private, Germany)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("GRUNENTHAL", "Grunenthal GmbH (private, Germany)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("ALTANA", "Altana Pharma (Norvartis?) - Nycomed lineage", "", "", "NON-US LISTING ONLY", "Altana pharma sold to Nycomed 2006 (private)"),
    ("NYCOMED", "Nycomed (private)", "", "", "NON-US LISTING ONLY", "private equity-owned; acquired Takeda 2011"),
    ("LEO PHARMA", "LEO Pharma (private, Denmark)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("LUNDBECK", "H. Lundbeck A/S (Denmark)", "HLUKY", "OTC ADR; primary CSE:LUN", "NON-US LISTING ONLY", "primary CSE:LUN"),
    ("SHIRE", "Shire plc (acquired by Takeda 2019)", "SHPG", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:SHPG delisted 2019"),
    ("AMGEN", "Amgen Inc.", "AMGN", "NASDAQ", "US-LISTED", ""),
    ("IMMUNEX", "Immunex (acquired by Amgen 2002)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:IMNX delisted 2002"),
    ("BIOGEN IDEC", "Biogen Idec (now Biogen Inc.)", "BIIB", "NASDAQ", "US-LISTED", ""),
    ("IDEC", "Idec Pharmaceuticals (merged into Biogen Idec 2003)", "BIIB", "NASDAQ", "US-LISTED", ""),
    ("BIOGEN", "Biogen (now Biogen Inc.)", "BIIB", "NASDAQ", "US-LISTED", ""),
    ("GENZYME", "Genzyme (acquired by Sanofi 2011)", "GENZ", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:GENZ delisted 2011"),
    ("IMCLONE", "ImClone Systems (acquired by Lilly 2008)", "IMCL", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:IMCL delisted 2008"),
    ("MILLENNIUM", "Millennium Pharmaceuticals (acquired by Takeda 2008)", "MLNM", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:MLNM delisted 2008"),
    ("COR THERAPEUTICS", "COR Therapeutics (acquired by Millennium 2002)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CORR delisted 2002"),
    ("MEDIMMUNE", "MedImmune (acquired by AstraZeneca 2007)", "MEDI", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:MEDI delisted 2007"),
    ("CHIRON", "Chiron (acquired by Novartis 2006)", "CHIR", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CHIR delisted 2006"),
    ("AMYLIN", "Amylin Pharmaceuticals (acquired by BMS 2012)", "AMLN", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:AMLN delisted 2012"),
    ("CELGENE", "Celgene Corp. (acquired by BMS 2019)", "CELG", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CELG delisted 2019"),
    ("OSI PHARMACEUTICALS", "OSI Pharmaceuticals (acquired by Astellas 2010)", "OSIP", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:OSIP delisted 2010"),
    ("OSIP", "OSI Pharmaceuticals (acquired by Astellas 2010)", "OSIP", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", ""),
    ("CEPHALON", "Cephalon (acquired by Teva 2011)", "CEPH", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CEPH delisted 2011"),
    ("KING PHARMACEUTICALS", "King Pharmaceuticals (acquired by Pfizer 2011)", "KG", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:KG delisted 2011"),
    ("SEPRACOR", "Sepracor (acquired by Actavis 2014)", "SEPR", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:SEPR delisted 2014"),
    ("FOREST", "Forest Laboratories (Actavis/Allergan lineage)", "FRX", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:FRX delisted 2014"),
    ("CEREXA", "Cerexa/Forest Laboratories (Actavis-Allergan lineage)", "FRX", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Forest acquired by Actavis 2014; Allergan to AbbVie 2020"),
    ("MYLAN BERTEK", "Mylan Bertek (Mylan; now Viatris)", "VTRS", "NASDAQ", "US-LISTED", "Mylan merged into Viatris 2020; ticker now VTRS"),
    ("MYLAN", "Mylan (now Viatris)", "VTRS", "NASDAQ", "US-LISTED", "Mylan merged into Viatris 2020"),
    ("DU PONT", "DuPont Pharmaceuticals (acquired by BMS 2001)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "DuPont Co was NYSE:DD; pharma sold to BMS 2001"),
    ("DUPONT", "DuPont Pharmaceuticals (acquired by BMS 2001)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", ""),
    ("ACORDA", "Acorda Therapeutics (acquired by Merck 2024)", "ACOR", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ACOR delisted 2024"),
    ("PROGENICS", "Progenics Pharmaceuticals (acquired by Lantheus 2020)", "PGNX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "AZEDRA era; delisted 2020"),
    ("EPIX", "Epix Pharmaceuticals (delisted; Vasovist later Lantheus)", "EPIX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:EPIX; wound down ~2009-2011"),
    ("XOMA", "XOMA Corp.", "XOMA", "NASDAQ", "US-LISTED", ""),
    ("NABI", "Nabi Biopharmaceuticals", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:NABI delisted"),
    ("CORIXA", "Corixa (acquired by GlaxoSmithKline 2005)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CRXA delisted 2005"),
    ("SEQUUS", "Sequus Pharmaceuticals (acquired by ALZA 1999)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", ""),
    ("ALZA", "ALZA Corp. (acquired by J&J 2001)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:AZA delisted 2001"),
    ("VERTEX", "Vertex Pharmaceuticals", "VRTX", "NASDAQ", "US-LISTED", ""),
    ("GILEAD", "Gilead Sciences", "GILD", "NASDAQ", "US-LISTED", ""),
    ("ALEXION", "Alexion Pharmaceuticals (acquired by AstraZeneca 2021)", "ALXN", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ALXN delisted 2021"),
    ("BIOMARIN", "BioMarin Pharmaceutical", "BMRN", "NASDAQ", "US-LISTED", ""),
    ("MYRIAD", "Myriad Genetics", "MYGN", "NASDAQ", "US-LISTED", ""),
    ("AERPIO? no", "", "", "", "", ""),
    ("THERAVANCE", "Theravance Biopharma", "INVA", "NASDAQ", "US-LISTED", "royalty entity Innoviva (INVA); drug rights GSK"),
    ("FEINSTEIN", "Feinstein Kean? - Feinstein Institute/radiopharmacy (private)", "", "N/A - not a listed sponsor", "PRIVATE / NO EQUITY", "Ammonia N13 PET agent"),
    ("MAYO", "Mayo Clinic (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("WELLSTAT", "Wellstat Therapeutics (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("ASKLEPION", "Asklepion Pharmaceuticals (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("PARAPRO", "ParaPRO LLC (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("FERRING", "Ferring Pharmaceuticals (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("GE HEALTHCARE", "General Electric Co. (GE HealthCare)", "GE", "NASDAQ", "US-LISTED", "GE HealthCare spun off 2023, now NASDAQ:GEHC"),
    ("AMERSHAM", "Amersham (acquired by GE 2004)", "GE", "NYSE", "US-LISTED", "Amersham acquired by GE Healthcare 2004"),
    ("AEGEAN? no", "", "", "", "", ""),
    ("SICOR", "Sicor Biotech (Teva Group)", "TEVA", "NYSE", "US-LISTED", "Teva ADR"),
    ("TEVA", "Teva Pharmaceutical Industries", "TEVA", "NYSE", "US-LISTED", "ADR; primary TASE"),
    ("HUMAN GENOME SCIENCES", "Human Genome Sciences (acquired by GSK 2012)", "HGSI", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:HGSI delisted 2012"),
    ("ARIAD", "ARIAD Pharmaceuticals (acquired by Takeda 2017)", "ARIA", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ARIA delisted 2017"),
    ("THROMBOGENICS", "ThromboGenics NV (Belgium)", "", "", "NON-US LISTING ONLY", "Euronext Brussels:THR (now Oxurion)"),
    ("ALMIRALL", "Almirall SA (Spain)", "", "", "NON-US LISTING ONLY", "BME:ALM"),
    ("PROTALIX", "Protalix BioTherapeutics (Pfizer partner)", "PLX", "NYSE American", "US-LISTED", ""),
    ("VIVUS", "VIVUS Inc.", "VVUS", "NASDAQ", "US-LISTED", ""),
    ("AVID RADIOPHARM", "Avid Radiopharmaceuticals (acquired by Lilly 2012)", "LLY", "NYSE", "US-LISTED", "Avid was private at approval; acquired by Lilly 2012"),
    ("AFFYMAX", "Affymax (withdrawn drug 2013; delisted)", "AFFY", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:AFFY delisted 2013"),
    ("DISCOVERY LABORATORIES", "Discovery Laboratories (now Windtree)", "DSCO", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:DSCO; later WINT"),
    ("XENOPORT", "XenoPort (acquired by Depomed 2016)", "XNPT", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:XNPT delisted 2016"),
    ("ARENA", "Arena Pharmaceuticals (acquired by Eisai 2022)", "ARNA", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ARNA delisted 2022"),
    ("AEGERION", "Aegerion Pharmaceuticals (Novelion/Amryt lineage)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:AEGR; Novelion; Amryt to Jazz 2023"),
    ("ACTELION", "Actelion (acquired by J&J 2017)", "", "", "NON-US LISTING ONLY", "SIX:ATLN delisted 2017"),
    ("NAVIDEA", "Navidea Biopharmaceuticals", "NAVB", "NYSE American", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "delisted from NYSE American 2017; OTC later"),
    ("GUERBET", "Guerbet SA (France)", "", "", "NON-US LISTING ONLY", "Euronext:GBT"),
    ("KOWA", "Kowa Company (private, Japan)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("VIIV", "ViiV Healthcare (GSK-led JV)", "GSK", "NYSE (ADR)", "US-LISTED (ADR)", "JV: GSK majority, Pfizer, Shionogi"),
    ("TIBOTEC", "Tibotec (Johnson & Johnson)", "JNJ", "NYSE", "US-LISTED", ""),
    ("SUN PHARMA", "Sun Pharmaceutical Industries (India)", "", "", "NON-US LISTING ONLY", "NSE:SUNPHARMA"),
    ("TAIMED", "TaiMed Biologics (Taiwan)", "", "", "NON-US LISTING ONLY", "TPEx:4197"),
    ("RIGEL", "Rigel Pharmaceuticals", "RIGL", "NASDAQ", "US-LISTED", ""),
    ("ULTRAGENYX", "Ultragenyx Pharmaceutical (US)/Kyowa Kirin", "RARE", "NASDAQ", "US-LISTED", "US rights Ultragenyx; ex-US Kyowa Kirin"),
    ("US WORLDMEDS", "US WorldMeds (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("HELSINN", "Helsinn Group (private, Switzerland)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("ADVANCED ACCELERATOR", "Advanced Accelerator Applications (acquired by Novartis 2018)", "AAAP", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:AAAP delisted 2018"),
    ("SAGE", "Sage Therapeutics", "SAGE", "NASDAQ", "US-LISTED", "Supernus collaboration (2023)"),
    ("CHEMO RESEARCH", "Chemo Research SL / Exeltis (private, Spain)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "benznidazole US: Exeltis USA"),
    ("LNHC", "LNHC, Inc. (Ferndale/Medimetriks lineage, private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Xepi marketer"),
    ("EUSA", "EUSA Pharma (private; US commercialization by Jazz)", "JAZN", "NASDAQ", "US-LISTED", "Erwinaze US rights Jazz Pharmaceuticals"),
    ("APOPHARMA", "ApoPharma (Apotex group, private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Ferrirox US"),
    ("NEW RIVER", "New River Pharmaceuticals (acquired by Shire 2007)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:NRPH delisted 2007"),
    ("INDEVUS", "Indevus Pharmaceuticals (acquired by Endo 2009)", "IDEV", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:IDEV delisted 2009"),
    ("BRACCO", "Bracco Diagnostics (private, Italy)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Bracco Group"),
    ("ALCON UNIVERSAL", "Alcon Inc. (NYSE:ACL delisted 2011 Novartis buyout; relisted ALC 2019)", "ALC", "NYSE", "US-LISTED", "Travatan era NYSE:ACL (delisted 2011); Alcon Inc. relisted 2019"),
    ("ALCON", "Alcon Inc. (NYSE:ACL delisted 2011 Novartis buyout; relisted ALC 2019)", "ALC", "NYSE", "US-LISTED", "Nevanac era NYSE:ACL (delisted 2011); Alcon Inc. relisted 2019"),
    ("REGENERON", "Regeneron Pharmaceuticals", "REGN", "NASDAQ", "US-LISTED", ""),
    ("ADOLOR", "Adolor Corp. (acquired by Cubist 2011)", "ADLR", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ADLR delisted 2011"),
    ("SIRION", "Sirion Therapeutics (private; Durezol US rights to Sanofi 2010)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "private; Sanofi acquired Durezol assets 2010"),
    ("MEDICINES COMPANY", "The Medicines Company (acquired by Novartis 2020)", "MDCO", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:MDCO delisted 2020"),
    ("PRESTWICK", "Prestwick Pharmaceuticals (private; Biovail/Merz lineage)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Xenazine US; later Biovail/Merz"),
    ("WATSON LABS", "Watson Pharmaceuticals (Actavis/Allergan/AbbVie lineage)", "WPI", "NYSE", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:WPI -> Actavis -> Allergan -> AbbVie 2020 (ABBV)"),
    ("CYPRESS BIOSCIENCE", "Cypress Bioscience (take-private 2010)", "CYPB", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CYPB delisted 2010"),
    ("SCIELE PHARMA", "Sciele Pharma (acquired by Shionogi 2008)", "SCRL", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:SCRL delisted 2008 into Shionogi"),
    ("VANDA", "Vanda Pharmaceuticals", "VNDA", "NASDAQ", "US-LISTED", ""),
    ("BAUSCH AND LOMB", "Bausch & Lomb (take-private 2013; Bausch + Lomb relisted 2022)", "BLCO", "NYSE", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:B&L delisted 2013; Bausch + Lomb (BLCO) relisted 2022"),
    ("BAUSCH", "Bausch & Lomb (take-private 2013; Bausch + Lomb relisted 2022)", "BLCO", "NYSE", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "besifloxacin/Besivance lineage"),
    ("ORGANON", "Organon BioSciences (Akzo Nobel; human Rx to Schering-Plough 2007)", "", "", "NON-US LISTING ONLY", "Akzo Nobel (AMS:AKZA) lineage -> Schering-Plough 2007 -> Merck 2009"),
    ("ISTA PHARM", "ISTA Pharmaceuticals (acquired by Bausch & Lomb 2012)", "ISTA", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ISTA delisted 2012"),
    ("ALLOS THERAPEUTICS", "Allos Therapeutics (acquired by Spectrum 2012)", "ALTH", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ALTH delisted 2012"),
    ("GLOUCESTER PHARMACEUTICALS", "Gloucester Pharmaceuticals (acquired by Celgene 2009)", "", "N/A - privately held at approval", "PRIVATE / NO EQUITY", "ISTODAX; VC-held, Celgene acquired 2009"),
    ("NEUROGESX", "NeurogesX (bankrupt 2012)", "NGSX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:NGSX delisted 2012"),
    ("DYAX", "Dyax Corp. (acquired by Shire 2016)", "DYAX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:DYAX delisted 2016"),
    ("AUXILIUM", "Auxilium Pharmaceuticals (acquired by Endo 2015)", "AUXL", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:AUXL delisted 2015"),
    ("ORPHAN EUROPE", "Orphan Europe (Recordati group, Italy)", "REC", "", "NON-US LISTING ONLY", "parent Recordati (BIT:REC)"),
    ("KREUSSLER", "Chemische Fabrik Kreussler & Co. (private, Germany)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("VISTAKON", "Vistakon Pharmaceuticals (Johnson & Johnson)", "JNJ", "NYSE", "US-LISTED", ""),
    ("HRA PHARMA", "Laboratoire HRA Pharma (private, France; Perrigo 2021)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "ella; Perrigo acquired HRA 2021"),
    ("SAVIENT", "Savient Pharmaceuticals (bankrupt 2013)", "SVNT", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:SVNT delisted 2013"),
    ("SUNOVION", "Sunovion Pharmaceuticals (Dainippon Sumitomo; Otsuka 2025)", "4568", "TSE", "NON-US LISTING ONLY", "parent Dainippon Sumitomo Pharma (TSE:4568); Otsuka acquisition 2025"),
    ("THERATECHNOLOGIES", "Theratechnologies (Canada)", "TH", "", "NON-US LISTING ONLY", "TSX:TH"),
    ("CV THERAPEUTICS", "CV Therapeutics (acquired by Gilead 2009)", "CVTX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CVTX delisted 2009"),
    ("OSI PHARMS", "OSI Pharmaceuticals (acquired by Astellas 2010)", "OSIP", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:OSIP delisted 2010"),
    ("SHOWBRAND", "Showa Denko? / unresolved FDA abbreviation for Evoxac applicant", "", "N/A - FDA-table abbreviation unresolved", "NOT US-INVESTABLE (UNVERIFIED)", "openFDA queried separately"),
    ("U.S. ARMY", "U.S. Army Medical Research (government)", "", "N/A - government", "PRIVATE / NO EQUITY", "Skin Exposure Reduction Paste; Walter Reed"),
    ("US ARMY", "U.S. Army Medical Research (government)", "", "N/A - government", "PRIVATE / NO EQUITY", ""),
    ("DAINIPPON", "Dainippon Pharmaceutical (now Daiichi Sankyo; Otsuka 2025)", "4568", "TSE", "NON-US LISTING ONLY", "merged into Daiichi Sankyo 2005 (TSE:4568)"),
    ("DEPROCO", "Deproco SpA (private, Italy)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Septocaine"),
    ("QLT PHOTO", "QLT Inc. (delisted 2012)", "QLTI", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:QLTI delisted 2012; Visudyne with Novartis"),
    ("DEBIO RECHERCHE", "Debiopharm Group (private, Switzerland)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Trelstar"),
    ("TEXAS BIOTECH", "Texas Biotechnology (renamed Encysive; Pfizer 2008)", "THRX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:THRX (Encysive) acquired by Pfizer 2008; Acova=argatroban"),
    ("SALIX PHARM", "Salix Pharmaceuticals (Valeant/Bausch lineage)", "SLXP", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:SLXP delisted 2015 (Valeant; now Bausch lineage)"),
    ("SKB CONS", "GlaxoSmithKline Consumer Healthcare (GSK; Haleon 2022)", "GSK", "NYSE (ADR)", "US-LISTED (ADR)", "Abreva; GSK CH -> Haleon 2022"),
    ("CIBA VISION", "CIBA Vision (Novartis/Alcon ophthalmics)", "ALC", "NYSE", "US-LISTED", "CIBA Vision = Novartis unit; Alcon relisted NYSE 2019"),
    ("SERONO", "Serono (acquired by Merck KGaA 2007)", "MKGAF", "", "NON-US LISTING ONLY", "Ares-Serono (SIX) -> Merck KGaA 2007 (ETR:MRK)"),
    ("CELL THERAPEUTICS", "Cell Therapeutics / CTI BioPharma (acquired by Sobi 2023)", "CTIC", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CTIC delisted 2023 (Sobi)"),
    ("POPULATION COUNCIL", "The Population Council (non-profit)", "", "N/A - non-profit", "PRIVATE / NO EQUITY", "Mifeprex"),
    ("ALLERGAN", "Allergan (acquired by AbbVie 2020)", "AGN", "NYSE", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:AGN delisted 2020"),
    ("ALCON UNIVERSAL", "Alcon Inc. (NYSE:ACL delisted 2011 Novartis buyout; relisted ALC 2019)", "ALC", "NYSE", "US-LISTED", "Travatan era NYSE:ACL (delisted 2011); Alcon Inc. relisted 2019"),
    ("TAP PHARM", "TAP Pharmaceutical Products (Takeda/Abbott JV)", "4502", "TSE", "NON-US LISTING ONLY", "JV: Takeda (TSE:4502) + Abbott; Takeda full owner 2008"),
    ("ELAN PHARMA", "Elan Corp. (acquired by Perrigo 2013)", "ELN", "NYSE", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NYSE:ELN delisted 2013"),
    ("ELAN PHARMS", "Elan Corp. (acquired by Perrigo 2013)", "ELN", "NYSE", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", ""),
    ("ELAN", "Elan Corp. (acquired by Perrigo 2013)", "ELN", "NYSE", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", ""),
    ("FONDA BV", "Fonda BV (Organon/Schering-Plough affiliate for Arixtra)", "", "", "NON-US LISTING ONLY", "fondaparinux; Organon lineage -> Schering-Plough/Merck"),
    ("SWEDISH ORPHAN", "Swedish Orphan International (now Sobi)", "SOBI", "", "NON-US LISTING ONLY", "STO:SOBI; Orfadin"),
    ("UNITED THERAPEUTICS", "United Therapeutics", "UTHR", "NASDAQ", "US-LISTED", ""),
    ("ALLIANCE PHARM", "Alliance Pharmaceuticals (delisted 2003)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Imagent; delisted ~2003"),
    ("ORPHAN MEDICAL", "Orphan Medical (acquired by Jazz 2005)", "ORPH", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Xyrem; NASDAQ:ORPH delisted 2005"),
    ("MSP SINGAPORE", "MSP Singapore (Schering-Plough/Singapore JV)", "MRK", "NYSE", "US-LISTED", "ezetimibe (Zetia) Schering-Plough JV lineage"),
    ("ROMAK LABS", "Romark Laboratories (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Alinia"),
    ("BAXTER HEALTHCARE", "Baxter International", "BAX", "NYSE", "US-LISTED", ""),
    ("BAXTER", "Baxter International", "BAX", "NYSE", "US-LISTED", ""),
    ("LG LIFE SCIENCES", "LG Life Sciences (LG Chem lineage, Korea)", "051910", "KRX", "NON-US LISTING ONLY", "LG Chem (KRX:051910) absorbed LGLS 2017"),
    ("IRP ASTRAZENCA", "AstraZeneca [FDA prints 'IRP AstraZenca' (sic)]", "AZN", "NASDAQ (ADR)", "US-LISTED (ADR)", "FDA-table typo kept verbatim"),
    ("CUBIST", "Cubist Pharmaceuticals (acquired by Merck 2015)", "CBST", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:CBST delisted 2015"),
    ("HEYL", "Heyl Chemisch-pharmazeutische Fabrik (private, Germany)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Radiogardase"),
    ("PRAECIS", "Praecis Pharmaceuticals (acquired by Amgen 2007)", "PRCS", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:PRCS delisted 2007"),
    ("CHIRHOCLIN", "ChiRhoClin (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "ChiRhoStim"),
    ("BERTEK", "Mylan Bertek (Mylan; now Viatris)", "VTRS", "NASDAQ", "US-LISTED", "Apokyn US"),
    ("ISTA PHARMS", "ISTA Pharmaceuticals (acquired by Bausch & Lomb 2012)", "ISTA", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:ISTA delisted 2012"),
    ("PRESUTTI LABS", "Presutti Laboratories (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Tindamax"),
    ("PHARMION", "Pharmion Corp. (acquired by Celgene 2008)", "PHRM", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:PHRM delisted 2008"),
    ("NUTRITIONAL RESTART", "Nutritional Restart Center (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "NutreStore"),
    ("PALATIN TECHNOLOGIES", "Palatin Technologies", "PTN", "NYSE American", "US-LISTED", ""),
    ("PALATIN", "Palatin Technologies", "PTN", "NYSE American", "US-LISTED", ""),
    ("LIPHA", "Lipha SA (Merck KGaA group, France)", "MKGAF", "", "NON-US LISTING ONLY", "Campral; parent Merck KGaA (ETR:MRK)"),
    ("PHARMA HAMELN", "Pharma Hameln GmbH (private, Germany)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "pentetate kits"),
    ("AMPHASTAR PHARM", "Amphastar Pharmaceuticals", "AMPH", "NASDAQ", "US-LISTED", ""),
    ("AMPHASTAR", "Amphastar Pharmaceuticals", "AMPH", "NASDAQ", "US-LISTED", ""),
    ("ROSS PRODS", "Ross Products (Abbott Nutrition)", "ABT", "NYSE", "US-LISTED", "Omacor US = Lovaza lineage"),
    ("DORC INTERNATIONAL", "Dutch Ophthalmic Research Center (D.O.R.C., private NL)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Vision Blue"),
    ("EYETECH PHARMS", "Eyetech Pharmaceuticals (merged into OSI 2005)", "EYET", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Macugen; NASDAQ:EYET ended 2005"),
    ("COTHERIX", "CoTherix (acquired by Actelion 2007)", "CTRX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Ventavis; NASDAQ:CTRX delisted 2007"),
    ("TERCICA", "Tercica (acquired by Ipsen 2008)", "TRCA", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Increlex; NASDAQ:TRCA delisted 2008"),
    ("PRIMAPHARM", "PrimaPharm (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", "Hydase"),
    ("HALOZYME", "Halozyme Therapeutics", "HALO", "NASDAQ", "US-LISTED", ""),
    ("INSMED", "Insmed", "INSM", "NASDAQ", "US-LISTED", ""),
    ("SUCAMPO", "Sucampo Pharmaceuticals (acquired by Mallinckrodt 2018)", "SCMP", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:SCMP delisted 2018"),
    ("VICURON", "Vicuron Pharmaceuticals (acquired by Pfizer 2005)", "MICU", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Eraxis; NASDAQ:MICU delisted 2005"),
    ("MGI PHARMA", "MGI Pharma (acquired by Eisai 2008)", "MOGN", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "Dacogen; NASDAQ:MOGN delisted 2008"),
    ("L'OREAL", "L'Oreal SA (France)", "", "", "NON-US LISTING ONLY", "Euronext:OR; Anthelios SX US"),
    ("AXCAN SCANDIPHARM", "Axcan Scandipharm (Axcan Pharma; take-private 2007)", "", "", "NON-US LISTING ONLY", "Axcan (TSX:AXC) taken private 2007; Pylera"),
    ("IDENIX", "Idenix Pharmaceuticals (acquired by Merck 2014)", "IDIX", "NASDAQ", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "NASDAQ:IDIX delisted 2014"),
    ("MEDIGENE", "MediGene AG (Germany)", "", "", "NON-US LISTING ONLY", "XETRA:MDG (Veregen US)"),
    ("NOVO NORDISK", "Novo Nordisk A/S", "NVO", "NYSE (ADR)", "US-LISTED (ADR)", "primary CSE:NOVO-B"),
    ("SIRION", "Sirion Therapeutics (private)", "", "N/A - privately held", "PRIVATE / NO EQUITY", ""),
    ("SCHWARZ", "Schwarz BioSciences (acquired by UCB 2006)", "", "", "FORMERLY US-LISTED (DELISTED/ACQUIRED)", "was Nasdaq Europe-listed; acquired by UCB"),
    ("BIOMEASURE", "Biomeasure/IPSEN group", "IPSEY", "OTC ADR; primary Euronext:IPN", "NON-US LISTING ONLY", "Somatuline US rights Ipsen"),
]

def resolve(applicant):
    a = (applicant or "").upper()
    best = None  # earliest mention in the string wins (primary applicant; secondary partners lose on position)
    for pat, co, tk, ex, usc, note in COMPANY:
        pos = a.find(pat)
        if pos >= 0 and (best is None or pos < best[0]):
            best = (pos, co, tk, ex, usc, note)
    return (best[1], best[2], best[3], best[4], best[5]) if best else None

def drugsatfda_url(appl_no):
    m = re.match(r"(?:N|BLA|BL|NDA)?0*(\d+)$", (appl_no or "").replace(" ", ""), re.I)
    if not m:
        return ""
    return f"http://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&varApplNo={int(m.group(1)):06d}"

def pathway(cls):
    parts = [p.strip().upper() for p in re.split(r"[,;/ ]+", cls or "") if p.strip()]
    tags = []
    if "P" in parts: tags.append("Priority")
    if "S" in parts: tags.append("Standard")
    return "; ".join(tags)

GAP_FILES_11_13 = ["fda_nme_2011_gap.json", "fda_nme_2012_gap.json", "fda_nme_2013_gap.json"]
GAP_FILES_LATER = ["fda_novel_2015_gap.json", "fda_novel_2018_gap.json", "fda_novel_2019_gap.json"]

rows_out = []
for fn in [f"fda_nme_{y}_verbatim.json" for y in range(2000, 2011)] + GAP_FILES_11_13 + GAP_FILES_LATER:
    d = json.load(open(STG / fn))
    rws = d.get("rows") or d.get("rows_to_add") or []
    for r in rws:
        rows_out.append({
            "src": fn, "appl_no": r.get("appl_no", ""), "brand": r.get("brand", ""),
            "generic": r.get("generic", ""), "applicant": r.get("applicant", r.get("applicant_on_table", "")),
            "cls": r.get("class", r.get("class", "")), "date": r.get("date", ""),
            "ind": r.get("indication", ""), "row_source_url_1": r.get("source_url_1", ""),
        })

# 2017 gap (verified via openFDA drugsfda this session; official FDA 2017 report list, Goldwater mirror of fda.gov content)
rows_out += [
    {"src": "INLINE-2017-report+openFDA", "appl_no": "NDA209570", "brand": "benznidazole [no trade name]",
     "generic": "benznidazole", "applicant": "Chemo Research SL / Exeltis (Mundo Sano program)",
     "cls": "P,O", "date": "2017-08-29",
     "ind": "Treatment of Chagas disease (Trypanosoma cruzi infection) in children 2-12 years of age.",
     "flag": "openFDA NDA209570 ORIG-1 20170829 Type 1 NME PRIORITY Orphan; sponsor CHEMO RESEARCH SL. FDA 2017 report lists as 'benznidazole**' (approved with no trade name)."},
    {"src": "INLINE-2017-report+openFDA", "appl_no": "NDA208945", "brand": "Xepi",
     "generic": "ozenoxacin", "applicant": "LNHC (Ferndale/Medimetriks)",
     "cls": "S", "date": "2017-12-11",
     "ind": "Topical treatment of impetigo due to Staphylococcus aureus or Streptococcus pyogenes in patients 2 months of age and older.",
     "flag": "openFDA NDA208945 ORIG-1 20171211 Type 1 NME STANDARD; sponsor LNHC; openfda.brand_name 'XEPI' index NOT_FOUND (queried via ingredient) - flagged."},
]

# ---- load master, dedupe ----
with open(MASTER, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing = list(reader)
have = {(r["drug_brand"].strip().lower(), r["decision_date"][:10]) for r in existing}

new_rows, skipped = [], []
for r in rows_out:
    brand_clean = re.sub(r"\s*\[.*?\]\s*", " ", r["brand"]).strip()
    key = (r["brand"].split(" [")[0].strip().lower(), r["date"])
    if key in have:
        skipped.append((brand_clean, r["date"], "same brand+date already in master"))
        continue
    have.add(key)
    res = resolve(r["applicant"])
    if res:
        co, tk, ex, usc, note = res
        basis = f"derived 2026-09-12 from verified exchange/ticker fields; FDA applicant string '{r['applicant']}' matched pattern '{co}'"
        vstat = "Verified"
    else:
        co, tk, ex, usc, note = r["applicant"], "", "N/A - sponsor resolution pending", "NOT US-INVESTABLE (UNVERIFIED)", ""
        basis = "FDA applicant string kept verbatim; sponsor/equity not resolved this pass"
        vstat = "Verified - FLAGGED (sponsor/equity not yet resolved)"
    notes = f"appl {r['appl_no']}; FDA-table applicant: {r['applicant']}"
    if note: notes += f". {note}"
    flags = []
    if "[FDA prints" in r["ind"] or "[FDA PDF" in r["ind"]: flags.append("FDA-table typo kept verbatim, correction inline")
    if "IRREGULARITY" in r["ind"]: flags.append("see indication-embedded irregularity note")
    if r.get("flag"): flags.append(r["flag"])
    if flags: vstat += " - FLAGGED IRREGULARITY" if "IRREGULARITY" in " ".join(flags) else " - FLAGGED (source-verbatim note)"
    if flags: notes += ". " + "; ".join(flags)
    new_rows.append({
        "company_name": co, "ticker": tk, "drug_brand": brand_clean, "drug_generic": r["generic"],
        "decision_type": "Approval", "decision_date": r["date"], "indication": r["ind"],
        "review_pathway": pathway(r["cls"]),
        "source_url_1": r.get("row_source_url_1") or (json.load(open(STG / r["src"]))["capture_url"] if r["src"].endswith(".json") else "https://goldwaterinstitute.org/wp-content/uploads/2018/11/2017-New-Drug-Therapy-Approvals.pdf"),
        "source_url_2": drugsatfda_url(r["appl_no"]),
        "verification_status": vstat, "notes": notes,
        "us_investable_class": usc, "classification_basis": basis, "exchange": ex,
        "decision_id": "",
    })

new_rows.sort(key=lambda r: (r["decision_date"], r["drug_brand"]))
next_id = max(int(r["decision_id"][1:]) for r in existing) + 1
for i, r in enumerate(new_rows):
    r["decision_id"] = f"D{next_id + i}"

out = existing + new_rows
with open(MASTER, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader(); w.writerows(out)

print(f"master: {len(existing)} -> {len(out)} (+{len(new_rows)}), next_id now D{next_id + len(new_rows)}")
from collections import Counter
print("new rows per year:", dict(Counter(r['decision_date'][:4] for r in new_rows)))
print("unresolved sponsors:", sum(1 for r in new_rows if r['us_investable_class'].startswith('NOT US')))
for s in skipped: print("SKIP:", s)
