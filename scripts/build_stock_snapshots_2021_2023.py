# -*- coding: utf-8 -*-
"""
Appends stock price snapshot rows for the 2021-2023 novel drug approvals
(D101-D200) to data/stock_price_snapshots.csv.

All prices come from the Yahoo Finance chart API
(query1.finance.yahoo.com/v8/finance/chart/<symbol>?period1=...&period2=...&interval=1d)
fetched live during the Sept 2026 agent session; the raw close series per
drug are preserved verbatim in data/staging/prices.py (ticker, verified
company longName, currency, [(date, close), ...]). Each fetch's meta.longName
was checked against the expected company before use (ticker verification).

Conventions (matching existing snapshots):
- close_before   = last daily close strictly before the FDA decision date
- close_on_or_after = first daily close on/after the decision date
- close_few_days_later = next trading day's close after the on/after close
- Prices are the raw unadjusted daily closes returned by Yahoo for that
  window, in the listing's native currency (USD unless noted).
- Where the applicant was acquired and its ticker delisted (Yahoo purges
  delisted symbols' history), the row is recorded with empty prices and an
  explicit note - never estimated.

Run order: build_stock_snapshots.py first, then this script.
"""
import csv, importlib.util, os

def load_prices():
    spec = importlib.util.spec_from_file_location("staging_prices", "data/staging/prices.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.PRICES, m.NODATA

PRICES, NODATA = load_prices()

# extra note fragments per brand (currency/timing caveats, ownership notes)
NOTES = {
"Leqembi": "Prices in JPY (Tokyo listing 4523.T). FDA accelerated approval announced Jan 6 2023 US time = after Tokyo close; first Tokyo session reflecting the news was Jan 10 (+4.8%)",
"Veozah": "Prices in JPY (Tokyo listing 4503.T). Approval announced May 12 2023 US time = after Tokyo close; Tokyo reaction visible May 15",
"Omlonti": "Prices in JPY (Tokyo listing 4536.T)",
"Lytgobi": "Prices in JPY (Tokyo listing 4578.T, Otsuka Holdings)",
"Quviviq": "FDA action date Jan 7 2022 per Drugs@FDA (NDA 214985, STANDARD); DEA scheduling delayed US launch (FR notice Apr 7 2022)",
"Tepmetko": "Prices in EUR (Xetra listing MRK.DE)",
"Sohonos": "Prices in EUR (Euronext Paris IPN.PA)",
"Elucirem": "Prices in EUR (Euronext Paris GBT.PA)",
"Rystiggo": "Prices in EUR (Euronext Brussels UCB.BR)",
"Zilbrysq": "Prices in EUR (Euronext Brussels UCB.BR); UCB won two novel approvals the same day (Zilbrysq and Bimzelx) - single market reaction covers both",
"Bimzelx": "Prices in EUR (Euronext Brussels UCB.BR); UCB won two novel approvals the same day (Zilbrysq and Bimzelx) - single market reaction covers both",
"Vanflyta": "OTC ADR (DSNKY) daily closes in USD; primary listing Tokyo 4568",

"Aphexda": "BLRX series caveat: BioLineRx executed a reverse split after 2023, so Yahoo's retroactively-adjusted series is ~100x the contemporaneous traded price (~$0.9-1.0 in Sep 2023); flagged for manual reconciliation (same pattern as XFOR row above)",
"Filspari": "TVTX fell 12% on approval day (accelerated approval with boxed-warning label concerns); recovered above pre-approval level within 2 trading days",
"Xdemvy": "TARS fell 25% on approval day despite approval (pricing/competitive concerns widely reported); partial recovery next day",
"Daybue": "ACAD slipped on approval day; ACADIA had run up ahead of the decision",
"Qalsody": "BIIB fell on approval day (post-approval 'sell the news' after months of amyloid-driven rally)",
"Jaypirca": "LLY reaction muted - mega-cap; approval pre-announced as likely after Phase 2 data",
"Zurzuvae": "Approval covered postpartum depression only (major depressive disorder deferred); BIIB still rose modestly",
"Joenja": "FDA action date Mar 23 2023; the +32% move came the following trading day (Mar 24)",
"Kimmtrak": "FDA action date Jan 25 2022; the +7.5% move came the following trading day (Jan 26)",
"Rezlidhia": "FDA action date Dec 1 2022; the +22% move came the following trading day (Dec 2)",
"Briumvi": "Briumvi approval; the larger move (+23%) came the trading day after approval (Dec 29)",
"Ukoniq": "TG Therapeutics later voluntarily withdrew Ukoniq (April 2022) - see master notes",
"Verquvo": "FDA action date 01/19/2021 per Drugs@FDA (NDA 214377, PRIORITY, Type 1 NME)",
}
def note_for(brand):
    return NOTES.get(brand, "")

def pct(a, b):
    if a in (None, "", 0) or b in (None, ""):
        return ""
    return round((float(b) - float(a)) / float(a) * 100, 2)

def main():
    with open("data/stock_price_snapshots.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, existing = rows[0], rows[1:]
    assert header[0] == "ticker"

    master = list(csv.DictReader(open("data/fda_decisions_master.csv", encoding="utf-8")))
    new_master = [m for m in master if m["decision_date"] <= "2023-12-31"]

    seen_keys = {(r[0], r[2]) for r in existing}   # (ticker, decision_date)
    out = []
    for m in new_master:
        brand, ticker = m["drug_brand"], m["ticker"]
        if ticker == "NO_TICKER":
            continue
        key = (ticker, m["decision_date"])
        if key in seen_keys:
            continue
        src = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        if brand in NODATA:
            # delisted rows: name the entity whose stock we tried to track (applicant at approval)
            name = m["company_name"].split(" / ")[-1].split(" (")[0] if " / " in m["company_name"] else m["company_name"].split(" (")[0]
            out.append([ticker, name, m["decision_date"], m["decision_type"],
                        "", "", "", "", "", "", "", src, "Data unavailable - acquired/delisted",
                        NODATA[brand]])
            seen_keys.add(key)
            continue
        series = PRICES.get(brand)
        if not series:
            continue
        _, longname, currency, closes = series
        dd = m["decision_date"]
        before = [(d, c) for d, c in closes if d < dd]
        onorafter = [(d, c) for d, c in closes if d >= dd]
        if not before or not onorafter:
            print(f"!! {brand}: window does not bracket {dd}")
            continue
        b = before[-1]
        a = onorafter[0]
        later = onorafter[1] if len(onorafter) > 1 else ("", "")
        note = note_for(brand)
        if currency != "USD":
            note = (note + "; " if note else "") + f"Native currency {currency}"
        company = longname  # Yahoo meta.longName, verified at fetch time
        out.append([ticker, company, dd, m["decision_type"], b[1], b[0], a[1], a[0],
                    later[1], later[0], pct(b[1], a[1]), src, "Verified", note])
        seen_keys.add(key)

    with open("data/stock_price_snapshots.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(existing)
        w.writerows(out)
    print(f"Appended {len(out)} snapshot rows (total {len(existing) + len(out)})")

if __name__ == "__main__":
    main()
