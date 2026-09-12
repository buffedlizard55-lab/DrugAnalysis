# -*- coding: utf-8 -*-
"""
Raw price captures for the 77 new approval rows added 2026-09-12.

Source (verbatim): Yahoo Finance chart API
  https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>?period1=..&period2=..&interval=1d

Each entry stores:
  name / exchange / currency  <- returned by the API, used to verify that the
                                ticker really belongs to the expected issuer
  decision                    <- the FDA decision date the window was requested for
  series                      <- the full (epoch, close) list returned for the
                                requested +/-6 calendar-day window

Nothing here is interpolated. Where the API returned no data (delisted symbols
whose history has been withdrawn) the entry is marked `unavailable` and the
price cells are left blank in the snapshot table.

Derivation convention (applied by build_stock_snapshots_new.py):
  close_before = close on the last trading day strictly BEFORE the decision date
  close_on     = close ON the decision date; if the date was not a trading day the
                 next trading day is used and this is stated in the notes
  close_later  = close on the next trading day AFTER close_on
"""

CAPTURES = {
    # ---------------- 2021 cohort ----------------
    "NVS@2021-12-22": {
        "name": "Novartis AG", "exchange": "NYSE", "currency": "USD", "decision": "2021-12-22",
        "series": [(1639665000, 86.07), (1639751400, 85.90), (1640010600, 85.35),
                   (1640097000, 85.99), (1640183400, 86.31), (1640269800, 86.66),
                   (1640615400, 87.61)],
    },
    "ARGX@2021-12-17": {
        "name": "argenx SE", "exchange": "NasdaqGS", "currency": "USD", "decision": "2021-12-17",
        "series": [(1639405800, 303.00), (1639492200, 301.54), (1639578600, 307.57),
                   (1639665000, 297.14), (1639751400, 310.26), (1640010600, 337.51),
                   (1640097000, 351.58), (1640183400, 349.58)],
    },
    "AZN@2021-12-17": {
        "name": "AstraZeneca PLC", "exchange": "NYSE", "currency": "USD", "decision": "2021-12-17",
        "series": [(1639405800, 109.16), (1639492200, 109.00), (1639578600, 111.44),
                   (1639665000, 114.18), (1639751400, 112.04), (1640010600, 113.12),
                   (1640097000, 113.88), (1640183400, 116.16)],
    },
    "TAK@2021-11-23": {
        "name": "Takeda Pharmaceutical Company Limited", "exchange": "NYSE", "currency": "USD",
        "decision": "2021-11-23",
        "series": [(1637159400, 14.05), (1637245800, 14.08), (1637332200, 14.01),
                   (1637591400, 13.81), (1637677800, 13.79), (1637764200, 13.65),
                   (1637937000, 13.53)],
    },
    "BMRN@2021-11-19": {
        "name": "BioMarin Pharmaceutical Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2021-11-19",
        "series": [(1636986600, 82.07), (1637073000, 81.30), (1637159400, 80.74),
                   (1637245800, 82.92), (1637332200, 91.47), (1637591400, 90.30),
                   (1637677800, 89.79), (1637764200, 89.57)],
    },
    "NVS@2021-10-29": {
        "name": "Novartis AG", "exchange": "NYSE", "currency": "USD", "decision": "2021-10-29",
        "series": [(1635168600, 83.36), (1635255000, 84.84), (1635341400, 82.73),
                   (1635427800, 83.31), (1635514200, 82.76), (1635773400, 84.05),
                   (1635859800, 83.75), (1635946200, 83.59)],
    },
    "CCXI@2021-10-07": {
        "name": None, "exchange": None, "currency": None, "decision": "2021-10-07", "series": [],
        "unavailable": "Yahoo Finance returned \"Data doesn't exist for startDate\" - ChemoCentryx "
                       "(CCXI) was acquired by Amgen in Oct 2022 and its history has been withdrawn "
                       "from the chart API.",
    },
    "MIRM@2021-09-29": {
        "name": "Mirum Pharmaceuticals, Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2021-09-29",
        "series": [(1632403800, 20.18), (1632490200, 18.49), (1632749400, 18.30),
                   (1632835800, 18.75), (1632922200, 18.67), (1633008600, 19.92),
                   (1633095000, 19.35), (1633354200, 17.64)],
    },
    "ABBV@2021-09-28": {
        "name": "AbbVie Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2021-09-28",
        "series": [(1632317400, 106.41), (1632403800, 107.36), (1632490200, 107.07),
                   (1632749400, 107.72), (1632835800, 107.34), (1632922200, 108.84),
                   (1633008600, 107.87), (1633095000, 109.09)],
    },
    "SGEN@2021-09-20": {
        "name": None, "exchange": None, "currency": None, "decision": "2021-09-20", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - Seagen "
                       "(SGEN) was acquired by Pfizer in Dec 2023 and its history has been withdrawn "
                       "from the chart API.",
    },
    "TAK@2021-09-15": {
        "name": "Takeda Pharmaceutical Company Limited", "exchange": "NYSE", "currency": "USD",
        "decision": "2021-09-15",
        "series": [(1631194200, 16.98), (1631280600, 16.89), (1631539800, 16.98),
                   (1631626200, 16.75), (1631712600, 17.00), (1631799000, 17.20),
                   (1631885400, 17.15), (1632144600, 17.06)],
    },
    "ASND@2021-08-25": {
        "name": "Ascendis Pharma A/S", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2021-08-25",
        "series": [(1629379800, 119.08), (1629466200, 120.45), (1629725400, 122.00),
                   (1629811800, 121.75), (1629898200, 123.665), (1629984600, 149.70),
                   (1630071000, 154.76), (1630330200, 154.28)],
    },
    "MRK@2021-08-13": {
        "name": "Merck & Co., Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2021-08-13",
        "series": [(1628515800, 75.32), (1628602200, 75.19), (1628688600, 75.21),
                   (1628775000, 76.04), (1628861400, 76.72), (1629120600, 77.93),
                   (1629207000, 78.83), (1629293400, 77.79)],
    },
    "SNY@2021-08-06": {
        "name": "Sanofi", "exchange": "NasdaqGS", "currency": "USD", "decision": "2021-08-06",
        "series": [(1627911000, 51.60), (1627997400, 51.50), (1628083800, 49.88),
                   (1628170200, 50.56), (1628256600, 50.85), (1628515800, 51.09),
                   (1628602200, 50.87), (1628688600, 50.65)],
    },
    "AZN@2021-07-30": {
        "name": "AstraZeneca PLC", "exchange": "NYSE", "currency": "USD", "decision": "2021-07-30",
        "series": [(1627306200, 113.58), (1627392600, 114.92), (1627479000, 113.62),
                   (1627565400, 115.28), (1627651800, 114.48), (1627911000, 114.76),
                   (1627997400, 115.32), (1628083800, 114.62)],
    },
    "KDMN@2021-07-16": {
        "name": None, "exchange": None, "currency": None, "decision": "2021-07-16", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - Kadmon "
                       "(KDMN) was acquired by Sanofi in Nov 2021 and its history has been withdrawn "
                       "from the chart API.",
    },
    "SNY@2021-07-16": {
        "name": "Sanofi", "exchange": "NasdaqGS", "currency": "USD", "decision": "2021-07-16",
        "series": [(1626096600, 52.43), (1626183000, 52.27), (1626269400, 52.34),
                   (1626355800, 51.52), (1626442200, 51.99), (1626701400, 51.15),
                   (1626787800, 51.40), (1626874200, 51.50)],
    },
    "JAZZ@2021-06-30": {
        "name": "Jazz Pharmaceuticals plc", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2021-06-30",
        "series": [(1624541400, 178.80), (1624627800, 181.08), (1624887000, 181.93),
                   (1624973400, 179.03), (1625059800, 177.64), (1625146200, 181.18),
                   (1625232600, 181.50)],
    },
    "BIIB@2021-06-07": {
        "name": "Biogen Inc.", "exchange": "NasdaqGS", "currency": "USD", "decision": "2021-06-07",
        "series": [(1622554200, 267.15), (1622640600, 269.35), (1622727000, 272.55),
                   (1622813400, 286.14), (1623072600, 395.85), (1623159000, 395.37),
                   (1623245400, 406.94), (1623331800, 414.71), (1623418200, 396.64)],
    },
    "GSK@2021-06-01": {
        "name": "GSK plc", "exchange": "NYSE", "currency": "USD", "decision": "2021-06-01",
        "series": [(1622035800, 38.71), (1622122200, 38.49), (1622208600, 38.77),
                   (1622554200, 38.35), (1622640600, 38.39), (1622727000, 38.71),
                   (1622813400, 38.90)],
        "note": "31 May 2021 (Memorial Day) was not a trading day; previous close is 28 May 2021.",
    },
    "ALKS@2021-05-28": {
        "name": "Alkermes plc", "exchange": "NasdaqGS", "currency": "USD", "decision": "2021-05-28",
        "series": [(1621863000, 22.14), (1621949400, 21.59), (1622035800, 22.31),
                   (1622122200, 22.56), (1622208600, 22.67), (1622554200, 23.15),
                   (1622640600, 23.30)],
    },
    "AMGN@2021-05-28": {
        "name": "Amgen Inc.", "exchange": "NasdaqGS", "currency": "USD", "decision": "2021-05-28",
        "series": [(1621863000, 247.75), (1621949400, 242.00), (1622035800, 238.55),
                   (1622122200, 235.31), (1622208600, 237.94), (1622554200, 233.58),
                   (1622640600, 235.16)],
    },
    "LNTH@2021-05-26": {
        "name": "Lantheus Holdings, Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2021-05-26",
        "series": [(1621517400, 21.27), (1621603800, 21.53), (1621863000, 21.25),
                   (1621949400, 20.25), (1622035800, 19.51), (1622122200, 22.78),
                   (1622208600, 24.25)],
    },
    "JNJ@2021-05-21": {
        "name": "Johnson & Johnson", "exchange": "NYSE", "currency": "USD", "decision": "2021-05-21",
        "series": [(1621258200, 170.39), (1621344600, 170.45), (1621431000, 170.08),
                   (1621517400, 171.07), (1621603800, 170.96), (1621863000, 170.55),
                   (1621949400, 170.08), (1622035800, 169.07)],
    },
    "APLS@2021-05-14": {
        "name": None, "exchange": None, "currency": None, "decision": "2021-05-14", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" for APLS "
                       "on this request. Apellis is still an active listing, so this looks like a "
                       "transient API failure rather than a delisting - flagged for a re-fetch.",
    },
    "ADCT@2021-04-23": {
        "name": "ADC Therapeutics SA", "exchange": "NYSE", "currency": "USD", "decision": "2021-04-23",
        "series": [(1618839000, 21.90), (1618925400, 22.97), (1619011800, 23.88),
                   (1619098200, 24.40), (1619184600, 23.25), (1619443800, 25.67),
                   (1619530200, 26.70), (1619616600, 26.29)],
    },
    "GSK@2021-04-22": {
        "name": "GSK plc", "exchange": "NYSE", "currency": "USD", "decision": "2021-04-22",
        "series": [(1618579800, 37.75), (1618839000, 37.98), (1618925400, 37.70),
                   (1619011800, 38.25), (1619098200, 37.68), (1619184600, 37.74),
                   (1619443800, 37.78), (1619530200, 37.73)],
    },
    "SUPN@2021-04-02": {
        "name": "Supernus Pharmaceuticals, Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2021-04-02",
        "series": [(1617024600, 25.65), (1617111000, 26.17), (1617197400, 26.18),
                   (1617283800, 26.72), (1617629400, 30.11), (1617715800, 29.10),
                   (1617802200, 28.25)],
        "note": "2 Apr 2021 was Good Friday (market closed); the next trading day is 5 Apr 2021.",
    },
    "VNDA@2021-03-18": {
        "name": "Vanda Pharmaceuticals Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2021-03-18",
        "series": [(1615559400, 17.91), (1615815000, 17.76), (1615901400, 17.52),
                   (1615987800, 17.52), (1616074200, 17.04), (1616160600, 17.47),
                   (1616419800, 17.47), (1616506200, 16.31)],
    },
    "AVEO@2021-03-10": {
        "name": None, "exchange": None, "currency": None, "decision": "2021-03-10", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - AVEO was "
                       "acquired by LG Chem in 2023 and its history has been withdrawn from the "
                       "chart API.",
    },

    # ---------------- 2024 cohort ----------------
    "NBIX@2024-12-13": {
        "name": "Neurocrine Biosciences, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2024-12-13",
        "series": [(1733754600, 129.12), (1733841000, 128.96), (1733927400, 128.22),
                   (1734013800, 126.79), (1734100200, 126.70), (1734359400, 133.05),
                   (1734445800, 136.69), (1734532200, 135.45)],
    },
    "CKPT@2024-12-13": {
        "name": None, "exchange": None, "currency": None, "decision": "2024-12-13", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - Checkpoint "
                       "Therapeutics was acquired by Sun Pharma in 2025 and its history has been "
                       "withdrawn from the chart API.",
    },
    "MRUS@2024-12-04": {
        "name": None, "exchange": None, "currency": None, "decision": "2024-12-04", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - Merus was "
                       "acquired by Genmab in 2025 and its history has been withdrawn from the "
                       "chart API.",
    },
    "BBIO@2024-11-22": {
        "name": "BridgeBio Pharma, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2024-11-22",
        "series": [(1731940200, 22.35), (1732026600, 22.54), (1732113000, 23.04),
                   (1732199400, 23.24), (1732285800, 23.42), (1732545000, 27.19),
                   (1732631400, 26.44), (1732717800, 27.49)],
    },

    # ---------------- 2025 cohort ----------------
    "VNDA@2025-12-30": {
        "name": "Vanda Pharmaceuticals Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2025-12-30",
        "series": [(1766586600, 6.91), (1766759400, 7.04), (1767018600, 7.20),
                   (1767105000, 7.03), (1767191400, 8.82), (1767364200, 8.25)],
    },

    # ---------------- 2026 cohort ----------------
    "SRRK@2026-09-11": {
        "name": "Scholar Rock Holding Corporation", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2026-09-11",
        "series": [(1788874200, 57.42), (1788960600, 54.62), (1789047000, 55.67),
                   (1789133400, None)],
        "note": "The 2026-09-11 daily bar was still open/null when captured (the API was read within "
                "minutes of the 16:00 ET closing bell on the approval day, and the company's press "
                "release went out at 18:25 ET the same day). close_on is therefore left blank - it "
                "must be re-fetched. close_before is the 2026-09-10 close.",
    },
    "AZN@2026-09-04": {
        "name": "AstraZeneca PLC", "exchange": "NYSE", "currency": "USD", "decision": "2026-09-04",
        "series": [(1788183000, 162.13), (1788269400, 162.47), (1788355800, 161.63),
                   (1788442200, 164.77), (1788528600, 162.70), (1788874200, 160.04),
                   (1788960600, 156.94)],
    },
    "IONS@2026-09-03": {
        "name": "Ionis Pharmaceuticals, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2026-09-03",
        "series": [(1787923800, 61.05), (1788183000, 60.36), (1788269400, 59.88),
                   (1788355800, 61.33), (1788442200, 58.13), (1788528600, 58.09),
                   (1788874200, 56.71)],
    },
    "REGN@2026-08-19": {
        "name": "Regeneron Pharmaceuticals, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2026-08-19",
        "series": [(1786627800, 805.97), (1786714200, 803.48), (1786973400, 805.93),
                   (1787059800, 810.24), (1787146200, 840.84), (1787232600, 826.64),
                   (1787319000, 834.04), (1787578200, 828.50)],
    },
    "BMY@2026-08-13": {
        "name": "Bristol-Myers Squibb Company", "exchange": "NYSE", "currency": "USD",
        "decision": "2026-08-13",
        "series": [(1786109400, 64.72), (1786368600, 64.84), (1786455000, 63.61),
                   (1786541400, 63.70), (1786627800, 64.65), (1786714200, 63.83),
                   (1786973400, 64.63), (1787059800, 66.05)],
    },
    "LNTH@2026-08-13": {
        "name": "Lantheus Holdings, Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2026-08-13",
        "series": [(1786109400, 100.95), (1786368600, 100.98), (1786455000, 100.68),
                   (1786541400, 100.73), (1786627800, 100.94), (1786714200, 100.95),
                   (1786973400, 100.91), (1787059800, 100.26)],
    },
    "OTLK@2026-07-24": {
        "name": "Outlook Therapeutics, Inc.", "exchange": "NasdaqCM", "currency": "USD",
        "decision": "2026-07-24",
        "series": [(1784554200, 1.38), (1784640600, 1.42), (1784727000, 1.34),
                   (1784813400, 1.32), (1784899800, 1.405), (1785159000, 1.065),
                   (1785245400, 0.904), (1785331800, 1.00)],
        "note": "IRREGULARITY FLAGGED: the stock ROSE 6.44% on the approval day itself (1.32 -> "
                "1.405) but then fell 24.2% and 15.1% over the next two sessions (1.405 -> 1.065 -> "
                "0.904), i.e. an approval followed by a ~35% two-session drawdown. The cause is NOT "
                "established here and must be checked manually (financing / company-specific news "
                "is the likely explanation) - it is deliberately not guessed.",
    },
    "NUVL@2026-07-22": {
        "name": "Nuvalent Inc", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2026-07-22",
        "series": [],
        "unavailable": "REJECTED AS UNRELIABLE - the API returned a degenerate series for this "
                       "window: four identical bars at 123.96 with zero volume, then nulls, and a "
                       "firstTradeDate of 2026-07-14. That is not a valid price history, so no "
                       "prices are recorded for this row rather than recording a fabricated number.",
    },
    "MRK@2026-07-15": {
        "name": "Merck & Co., Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2026-07-15",
        "series": [(1783603800, 125.07), (1783690200, 123.54), (1783949400, 124.03),
                   (1784035800, 120.78), (1784122200, 123.61), (1784208600, 127.63),
                   (1784295000, 127.50), (1784554200, 124.40)],
    },
    "CELC@2026-07-14": {
        "name": "Celcuity Inc.", "exchange": "NasdaqCM", "currency": "USD", "decision": "2026-07-14",
        "series": [(1783517400, 108.90), (1783603800, 113.51), (1783690200, 107.58),
                   (1783949400, 103.79), (1784035800, 111.05), (1784122200, 91.51),
                   (1784208600, 88.29), (1784295000, 88.38)],
    },
    "VERA@2026-07-07": {
        "name": "Vera Therapeutics, Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2026-07-07",
        "series": [(1782912600, 42.66), (1782999000, 41.20), (1783344600, 40.13),
                   (1783431000, 42.96), (1783517400, 42.43), (1783603800, 42.45),
                   (1783690200, 42.00)],
    },
    "VRDN@2026-06-26": {
        "name": "Viridian Therapeutics, Inc.", "exchange": "NasdaqCM", "currency": "USD",
        "decision": "2026-06-26",
        "series": [(1782135000, 17.63), (1782221400, 17.28), (1782307800, 17.32),
                   (1782394200, 17.39), (1782480600, 17.90), (1782739800, 18.79),
                   (1782826200, 18.37), (1782912600, 18.48)],
    },
    "ABBV@2026-05-27": {
        "name": "AbbVie Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2026-05-27",
        "series": [(1779370200, 214.50), (1779456600, 215.70), (1779802200, 213.12),
                   (1779888600, 215.40), (1779975000, 218.63), (1780061400, 217.72),
                   (1780320600, 212.93)],
    },
    "GILD@2026-05-22": {
        "name": "Gilead Sciences, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2026-05-22",
        "series": [(1779111000, 129.67), (1779197400, 130.50), (1779283800, 130.69),
                   (1779370200, 130.50), (1779456600, 134.36), (1779802200, 133.73),
                   (1779888600, 133.69)],
    },
    "AZN@2026-05-15": {
        "name": "AstraZeneca PLC", "exchange": "NYSE", "currency": "USD", "decision": "2026-05-15",
        "series": [(1778506200, 181.86), (1778592600, 184.54), (1778679000, 187.72),
                   (1778765400, 184.96), (1778851800, 181.58), (1779111000, 183.92),
                   (1779197400, 184.64), (1779283800, 187.46)],
    },
    "RIGL@2026-05-01": {
        "name": "Rigel Pharmaceuticals, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2026-05-01",
        "series": [(1777296600, 30.51), (1777383000, 30.56), (1777469400, 29.22),
                   (1777555800, 28.90), (1777642200, 29.40), (1777901400, 29.54),
                   (1777987800, 28.09), (1778074200, 26.67)],
        "note": "Ticker shown is the CURRENT holder (Rigel), but the applicant at the time of "
                "approval was Arvinas; Rigel only took over global rights on 2026-05-12. The move "
                "shown for the approval date therefore also reflects deal news - do not read it as "
                "a clean approval-day reaction.",
    },
    "MRK@2026-04-20": {
        "name": "Merck & Co., Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2026-04-20",
        "series": [(1776173400, 119.96), (1776259800, 117.90), (1776346200, 115.46),
                   (1776432600, 119.07), (1776691800, 117.10), (1776778200, 112.56),
                   (1776864600, 112.89), (1776951000, 114.62), (1777037400, 111.90)],
    },
    "LLY@2026-04-01": {
        "name": "Eli Lilly and Company", "exchange": "NYSE", "currency": "USD",
        "decision": "2026-04-01",
        "series": [(1774531800, 897.00), (1774618200, 878.24), (1774877400, 886.63),
                   (1774963800, 919.77), (1775050200, 954.52), (1775136600, 935.58),
                   (1775482200, 927.06)],
    },
    "NVO@2026-03-26": {
        "name": "Novo Nordisk A/S", "exchange": "NYSE", "currency": "USD", "decision": "2026-03-26",
        "series": [(1774013400, 36.53), (1774272600, 36.82), (1774359000, 36.89),
                   (1774445400, 36.33), (1774531800, 36.40), (1774618200, 36.04),
                   (1774877400, 35.29), (1774963800, 36.75)],
    },
    "CORT@2026-03-25": {
        "name": "Corcept Therapeutics Incorporated", "exchange": "NasdaqCM", "currency": "USD",
        "decision": "2026-03-25",
        "series": [(1773927000, 34.08), (1774013400, 34.64), (1774272600, 33.63),
                   (1774359000, 33.82), (1774445400, 40.47), (1774531800, 38.53),
                   (1774618200, 37.60), (1774877400, 38.12)],
    },
    "JNJ@2026-03-17": {
        "name": "Johnson & Johnson", "exchange": "NYSE", "currency": "USD", "decision": "2026-03-17",
        "series": [(1773235800, 242.99), (1773322200, 242.04), (1773408600, 241.52),
                   (1773667800, 243.19), (1773754200, 238.11), (1773840600, 237.28),
                   (1773927000, 237.60), (1774013400, 235.37)],
    },
    "GSK@2026-03-17": {
        "name": "GSK plc", "exchange": "NYSE", "currency": "USD", "decision": "2026-03-17",
        "series": [(1773235800, 55.15), (1773322200, 54.28), (1773408600, 53.39),
                   (1773667800, 53.77), (1773754200, 53.41), (1773840600, 52.06),
                   (1773927000, 52.37), (1774013400, 51.84)],
        "note": "FDA's own page records 2026-03-17 as the approval date; GSK announced it on "
                "2026-03-19. Both dates fall in the captured window.",
    },
}

# ---------------- 2019 cohort (backfilled from FDA's 2019 New Drug Therapy Approvals report) ----------------
CAPTURES.update({
    "NVS@2019-11-15": {
        "name": "Novartis AG", "exchange": "NYSE", "currency": "USD", "decision": "2019-11-15",
        "series": [(1573482600, 88.63), (1573569000, 89.29), (1573655400, 89.86),
                   (1573741800, 89.51), (1573828200, 90.04), (1574087400, 90.33),
                   (1574173800, 90.40), (1574260200, 90.53)],
    },
    "JNJ@2019-04-12": {
        "name": "Johnson & Johnson", "exchange": "NYSE", "currency": "USD", "decision": "2019-04-12",
        "series": [(1554730200, 136.14), (1554816600, 135.57), (1554903000, 135.58),
                   (1554989400, 135.21), (1555075800, 135.98), (1555335000, 136.52),
                   (1555421400, 138.02), (1555507800, 138.52)],
    },
    "ONC@2019-11-14": {
        "name": "BeOne Medicines AG", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2019-11-14",
        "series": [(1573223400, 199.44), (1573482600, 191.72), (1573569000, 196.31),
                   (1573655400, 197.30), (1573741800, 196.40), (1573828200, 198.25),
                   (1574087400, 196.01), (1574173800, 203.90)],
        "note": "Ticker ONC is the CURRENT symbol (BeiGene renamed to BeOne Medicines). The API "
                "reports 'BeOne Medicines AG' for ONC and its history extends back through the "
                "BeiGene era, so this is the approval-window history for the same issuer.",
    },
    "SNY@2019-02-06": {
        "name": "Sanofi", "exchange": "NasdaqGS", "currency": "USD", "decision": "2019-02-06",
        "series": [(1548945000, 43.45), (1549031400, 43.26), (1549290600, 43.75),
                   (1549377000, 43.60), (1549463400, 43.39), (1549549800, 42.51),
                   (1549636200, 42.64), (1549895400, 42.33)],
    },
    "ITCI@2019-12-20": {
        "name": None, "exchange": None, "currency": None, "decision": "2019-12-20", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - Intra-"
                       "Cellular Therapies (ITCI) was acquired by Johnson & Johnson in 2025 and its "
                       "history has been withdrawn from the chart API.",
    },
    "AMGN@2019-04-09": {
        "name": "Amgen Inc.", "exchange": "NasdaqGS", "currency": "USD", "decision": "2019-04-09",
        "series": [(1554298200, 192.92), (1554384600, 192.33), (1554471000, 195.41),
                   (1554730200, 194.88), (1554816600, 192.98), (1554903000, 193.89),
                   (1554989400, 192.11), (1555075800, 191.42)],
    },
    "ALNY@2019-11-20": {
        "name": "Alnylam Pharmaceuticals, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2019-11-20",
        "series": [(1573741800, 90.46), (1573828200, 92.05), (1574087400, 92.73),
                   (1574173800, 97.93), (1574260200, 108.21), (1574346600, 111.20),
                   (1574433000, 106.91), (1574692200, 112.42)],
    },
    "BMY@2019-08-16": {
        "name": "Bristol-Myers Squibb Company", "exchange": "NYSE", "currency": "USD",
        "decision": "2019-08-16",
        "series": [(1565616600, 46.51), (1565703000, 46.49), (1565789400, 45.64),
                   (1565875800, 45.75), (1565962200, 46.98), (1566221400, 47.46),
                   (1566307800, 47.63), (1566394200, 47.77)],
    },
    "NVS@2019-03-26": {
        "name": "Novartis AG", "exchange": "NYSE", "currency": "USD", "decision": "2019-03-26",
        "series": [(1553088600, 83.7634), (1553175000, 83.9247), (1553261400, 83.7097),
                   (1553520600, 83.6111), (1553607000, 85.1434), (1553693400, 85.2240),
                   (1553779800, 85.6900), (1553866200, 86.1469)],
    },
    "GBT@2019-11-25": {
        "name": None, "exchange": None, "currency": None, "decision": "2019-11-25", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - Global "
                       "Blood Therapeutics (GBT) was acquired by Pfizer in 2022 and its history has "
                       "been withdrawn from the chart API.",
    },
    "NVS@2019-05-24": {
        "name": "Novartis AG", "exchange": "NYSE", "currency": "USD", "decision": "2019-05-24",
        "series": [(1558359000, 82.01), (1558445400, 82.39), (1558531800, 83.91),
                   (1558618200, 84.44), (1558704600, 87.52), (1559050200, 86.92),
                   (1559136600, 85.81)],
    },
    "RHHBY@2019-06-10": {
        "name": "Roche Holding AG", "exchange": "OTC Markets OTCQX", "currency": "USD",
        "decision": "2019-06-10",
        "series": [(1559655000, 33.18), (1559741400, 33.27), (1559827800, 33.80),
                   (1559914200, 34.24), (1560173400, 34.22), (1560259800, 34.10),
                   (1560346200, 34.64), (1560432600, 34.72), (1560519000, 34.55)],
    },
    "BMY@2019-11-08": {
        "name": "Bristol-Myers Squibb Company", "exchange": "NYSE", "currency": "USD",
        "decision": "2019-11-08",
        "series": [(1572877800, 56.64), (1572964200, 56.39), (1573050600, 56.96),
                   (1573137000, 57.58), (1573223400, 58.02), (1573482600, 58.15),
                   (1573569000, 58.39), (1573655400, 58.79)],
    },
    "ABBV@2019-04-23": {
        "name": "AbbVie Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2019-04-23",
        "series": [(1555507800, 77.98), (1555594200, 77.57), (1555939800, 78.15),
                   (1556026200, 78.66), (1556112600, 78.67), (1556199000, 79.34),
                   (1556285400, 79.70)],
    },
    "VRTX@2019-10-21": {
        "name": "Vertex Pharmaceuticals Incorporated", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2019-10-21",
        "series": [(1571146200, 176.14), (1571232600, 176.09), (1571319000, 177.72),
                   (1571405400, 176.23), (1571664600, 183.53), (1571751000, 191.06),
                   (1571837400, 190.51), (1571923800, 194.47), (1572010200, 194.49)],
    },
    "ABBV@2019-12-23": {
        "name": "AbbVie Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2019-12-23",
        "series": [(1576593000, 90.08), (1576679400, 89.33), (1576765800, 88.77),
                   (1576852200, 89.29), (1577111400, 90.25), (1577197800, 89.85),
                   (1577370600, 89.83), (1577457000, 89.20)],
    },
    "PFE@2019-05-03": {
        "name": "Pfizer Inc.", "exchange": "NYSE", "currency": "USD", "decision": "2019-05-03",
        "series": [(1556544600, 37.5617), (1556631000, 38.5294), (1556717400, 38.6812),
                   (1556803800, 38.9089), (1556890200, 39.2695), (1557149400, 39.5161),
                   (1557235800, 38.7381), (1557322200, 38.8520)],
    },
    "KPTI@2019-07-03": {
        "name": "Karyopharm Therapeutics Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2019-07-03",
        "series": [(1561642200, 91.95), (1561728600, 89.85), (1561987800, 84.90),
                   (1562074200, 98.10), (1562160600, 133.44), (1562333400, 132.15),
                   (1562592600, 125.10)],
        "note": "4 Jul 2019 was a market holiday, so the next session after the approval is 5 Jul.",
    },
})

# ---------------- 2020 cohort (from FDA's New Drug Therapy Approvals 2020 report) ----------------
CAPTURES.update({
    "BPMC@2020-01-09": {
        "name": None, "exchange": None, "currency": None, "decision": "2020-01-09", "series": [],
        "unavailable": "Yahoo Finance returned \"No data found, symbol may be delisted\" - Blueprint "
                       "Medicines (BPMC) was acquired by Sanofi in 2025 and its history has been "
                       "withdrawn from the chart API.",
    },
    "BMY@2020-03-25": {
        "name": "Bristol-Myers Squibb Company", "exchange": "NYSE", "currency": "USD",
        "decision": "2020-03-25",
        "series": [(1584624600, 48.79), (1584711000, 48.40), (1584970200, 46.40),
                   (1585056600, 49.24), (1585143000, 49.35), (1585229400, 52.25),
                   (1585315800, 52.79), (1585575000, 54.39)],
        "note": "Approved during the Mar-2020 COVID crash; the +6% move into 26 Mar cannot be "
                "separated from the market-wide rally of that week.",
    },
    "AZN@2020-04-10": {
        "name": "AstraZeneca PLC", "exchange": "NYSE", "currency": "USD", "decision": "2020-04-10",
        "series": [(1586179800, 88.62), (1586266200, 86.20), (1586352600, 87.70),
                   (1586439000, 89.32), (1586784600, 94.72), (1586871000, 97.36),
                   (1586957400, 96.06)],
        "note": "2020-04-10 was Good Friday - US markets were CLOSED. The first session after the "
                "approval is Mon 13 Apr, so the +6.0% move is measured to that session rather than "
                "to the approval date itself.",
    },
    "INCY@2020-04-17": {
        "name": "Incyte Corporation", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2020-04-17",
        "series": [(1586784600, 88.01), (1586871000, 91.28), (1586957400, 90.95),
                   (1587043800, 95.66), (1587130200, 100.00), (1587389400, 101.19),
                   (1587475800, 99.46), (1587562200, 100.97)],
    },
    "LLY@2020-05-08": {
        "name": "Eli Lilly and Company", "exchange": "NYSE", "currency": "USD",
        "decision": "2020-05-08",
        "series": [(1588599000, 153.28), (1588685400, 157.89), (1588771800, 156.68),
                   (1588858200, 152.97), (1588944600, 153.51), (1589203800, 158.55),
                   (1589290200, 157.72), (1589376600, 157.93)],
    },
    "GSK@2020-08-05": {
        "name": "GSK plc", "exchange": "NYSE", "currency": "USD", "decision": "2020-08-05",
        "series": [(1596115800, 40.25), (1596202200, 40.32), (1596461400, 41.29),
                   (1596547800, 41.24), (1596634200, 41.21), (1596720600, 40.97),
                   (1596807000, 40.79), (1597066200, 40.94)],
    },
    "RHHBY@2020-08-07": {
        "name": "Roche Holding AG", "exchange": "OTC Markets OTCQX", "currency": "USD",
        "decision": "2020-08-07",
        "series": [(1596461400, 44.16), (1596547800, 43.83), (1596634200, 43.40),
                   (1596720600, 43.43), (1596807000, 43.01), (1597066200, 42.80),
                   (1597152600, 42.17), (1597239000, 43.37)],
    },
    "GILD@2020-10-22": {
        "name": "Gilead Sciences, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2020-10-22",
        "series": [(1602855000, 62.00), (1603114200, 60.57), (1603200600, 60.55),
                   (1603287000, 60.21), (1603373400, 60.67), (1603459800, 60.79),
                   (1603719000, 59.96), (1603805400, 60.01)],
        "note": "Full approval of remdesivir ~3 weeks after the Oct-2020 US election-period "
                "volatility; the move is small and confounded.",
    },
    "ALNY@2020-11-23": {
        "name": "Alnylam Pharmaceuticals, Inc.", "exchange": "NasdaqGS", "currency": "USD",
        "decision": "2020-11-23",
        "series": [(1605623400, 129.30), (1605709800, 125.45), (1605796200, 123.81),
                   (1605882600, 124.70), (1606141800, 123.02), (1606228200, 125.66),
                   (1606314600, 125.45), (1606487400, 129.86)],
    },
    "RYTM@2020-11-25": {
        "name": "Rhythm Pharmaceuticals, Inc.", "exchange": "NasdaqGM", "currency": "USD",
        "decision": "2020-11-25",
        "series": [(1605796200, 21.83), (1605882600, 21.37), (1606141800, 22.00),
                   (1606228200, 23.20), (1606314600, 24.16), (1606487400, 29.27),
                   (1606746600, 30.95)],
        "note": "26 Nov 2020 was Thanksgiving (market holiday), so the next session after the "
                "approval is Fri 27 Nov, when the stock closed +21.1%.",
    },
})
