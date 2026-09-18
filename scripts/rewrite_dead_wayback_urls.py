#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rewrite the dead Wayback captures cited by the 2011-2014 master rows.

78 rows across 2011/2012/2013/2014 cited source_url_1 values wrapped as
  https://web.archive.org/web/20190207172014/http://wayback.archive-it.org/7993/...
(that 2019 capture no longer resolves; 40 of the rows pointed at the 2014 page
ucm429249.htm, 20 at the 2011 page ucm285489.htm, 18 at ucm370175.htm for
2012/2013). This script rewrites every such source_url_1 to the row-year's
official year-table capture ALREADY pinned in data/fda_year_source_register.csv
and used by the rows' same-year peers:

  2011  .../20120119181217/.../ucm285554.htm   (live-verified 2026-09-18)
  2012  .../20130217050942/.../ucm336115.htm   (live-verified 2026-09-18)
  2013  .../20140327204457/.../ucm381263.htm
  2014  .../20150123034253/.../ucm429247.htm   (live-verified 2026-09-18)

A dated provenance note is appended; no other field changes.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "fda_decisions_master.csv"
REGISTER = ROOT / "data" / "fda_year_source_register.csv"
DEAD = "20190207172014"


def main():
    reg = {r["year"]: r["official_source_url"]
           for r in csv.DictReader(open(REGISTER, newline="", encoding="utf-8-sig"))}
    with MASTER.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    n = 0
    for r in rows:
        u1 = r["source_url_1"]
        if DEAD in u1:
            y = r["decision_date"][:4]
            if y not in reg:
                print(f"no register URL for {r['decision_id']} year {y}; left unchanged")
                continue
            r["source_url_1"] = reg[y]
            note = ("source_url_1 rewritten 2026-09-18: the 2019 Wayback capture of the "
                    "archive-it wrapper no longer resolves; replaced with the year register's "
                    f"official capture for {y} "
                    "(2011/2014 captures live-verified 2026-09-18; 2012/2013 captures are the "
                    "ones already cited by the same-year rows and pinned in the register)")
            r["notes"] = (r["notes"] + " | " if r["notes"].strip() else "") + note
            n += 1
    with MASTER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"rewrote {n} dead capture URLs")
    remaining = sum(1 for r in rows if DEAD in r["source_url_1"])
    print("rows still citing the dead capture:", remaining)
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
