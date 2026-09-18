#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deprecated compatibility entry point.

The original v13 implementation is intentionally no longer executable as a
writer: it only covered 1983/1984 and would overwrite the v14 backward
expansion.  The authoritative, idempotent builder is now
``expand_pre1985_decisions_v14.py``; this filename forwards to it so old
session notes and shell commands cannot regenerate a stale 35-row table.
"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).with_name("expand_pre1985_decisions_v14.py")
    runpy.run_path(str(target), run_name="__main__")
