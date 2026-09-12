# -*- coding: utf-8 -*-
"""
Derives the price snapshot rows for the 77 new approval rows added 2026-09-12
and appends them to data/stock_price_snapshots.csv.

It does NOT re-request anything from the network: it reads the raw captures in
data/staging/prices_new_2026_09.py, which were taken verbatim from

    https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>?period1=..&period2=..&interval=1d

and applies one fixed, fully transparent rule set:

  close_before          close of the last trading day strictly BEFORE the decision date
  close_on_or_after     close ON the decision date; if that date was not a trading day
                        (or the bar had not been published yet), the close of the next
                        trading day is used and that is written into the notes
  close_few_days_later  close of the next trading day after close_on_or_after
  pct_change_on_decision  100 * (close_on_or_after / close_before - 1)

Rows whose ticker has no retrievable history are still written, with the price
cells blank and the reason recorded, so that the table stays one row per
decision and nothing is silently dropped.
"""
import csv
import datetime as dt
import importlib.util
import os

STAGING = os.path.join("data", "staging", "prices_new_2026_09.py")
MASTER = "data/fda_decisions_master.csv"
SNAPSHOTS = "data/stock_price_snapshots.csv"

HEADER = ["ticker", "company", "decision_date", "decision_type", "close_before", "date_before",
          "close_on_or_after", "date_on_or_after", "close_few_days_later", "date_few_days_later",
          "pct_change_on_decision", "source_url", "verification_status", "notes"]


def load_captures():
    spec = importlib.util.spec_from_file_location("prices_new_2026_09", STAGING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CAPTURES


def bar_date(epoch):
    """Yahoo daily bars are stamped at 13:30 UTC on the trading day."""
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).date()


def yahoo_url(ticker, decision):
    d = dt.datetime(int(decision[:4]), int(decision[5:7]), int(decision[8:10]),
                    tzinfo=dt.timezone.utc)
    return ("https://query1.finance.yahoo.com/v8/finance/chart/{}?period1={}&period2={}&interval=1d"
            .format(ticker, int(d.timestamp()) - 6 * 86400, int(d.timestamp()) + 6 * 86400))


def main():
    captures = load_captures()

    # company name per (ticker, decision_date) from the master table
    companies = {}
    with open(MASTER, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            companies[(r["ticker"].strip(), r["decision_date"].strip())] = r["company_name"].strip()

    rows = []
    for key in sorted(captures, key=lambda k: (captures[k]["decision"], k)):
        cap = captures[key]
        ticker = key.split("@")[0]
        decision = cap["decision"]
        d0 = dt.date(int(decision[:4]), int(decision[5:7]), int(decision[8:10]))
        company = companies.get((ticker, decision), "")
        url = yahoo_url(ticker, decision)

        bars = [(bar_date(e), c) for e, c in cap["series"] if c is not None]
        bars.sort()
        null_on = any(bar_date(e) == d0 and c is None for e, c in cap["series"])

        extra = []
        if cap.get("note"):
            extra.append(cap["note"])

        if not bars:
            rows.append([ticker, company, decision, "Approval", "", "", "", "", "", "", "", url,
                         "Verified - price unavailable",
                         " ".join([cap.get("unavailable", "No price history returned.")] + extra)])
            continue

        before = [b for b in bars if b[0] < d0]
        on = [b for b in bars if b[0] == d0]
        after = [b for b in bars if b[0] > d0]

        close_before, date_before = (before[-1][1], before[-1][0].isoformat()) if before else ("", "")
        if on:
            close_on, date_on = on[0][1], on[0][0].isoformat()
            later = [b for b in after if b[0] > on[0][0]]
        else:
            # decision date was not a trading day (or bar not yet published)
            nxt = after[0] if after else None
            if nxt is None:
                close_on, date_on = "", ""
                later = []
                if null_on:
                    extra.append("A daily bar exists for the decision date but its close had not "
                                 "been published when the capture was taken, so close_on_or_after "
                                 "and pct_change are left blank pending a re-fetch.")
                else:
                    extra.append("No trading day on or after the decision date fell inside the "
                                 "captured +/-6 day window.")
            else:
                close_on, date_on = nxt[1], nxt[0].isoformat()
                later = [b for b in after if b[0] > nxt[0]]
                extra.append("The decision date was not a trading day, so close_on_or_after is the "
                             "next trading day ({}) and pct_change is measured from the prior "
                             "close to that session.".format(date_on))
        close_later, date_later = (later[0][1], later[0][0].isoformat()) if later else ("", "")

        if close_before and close_on:
            pct = "{:.2f}".format(100.0 * (close_on / float(close_before) - 1.0))
            status = "Verified"
        else:
            pct = ""
            status = "Verified - incomplete (see notes)"

        rows.append([ticker, company, decision, "Approval", close_before, date_before,
                     close_on, date_on, close_later, date_later, pct, url, status,
                     " ".join(extra)])

    write_header = not os.path.exists(SNAPSHOTS)
    with open(SNAPSHOTS, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(HEADER)
        w.writerows(rows)
    print(f"Appended {len(rows)} new price snapshot rows to {SNAPSHOTS}")


if __name__ == "__main__":
    main()
