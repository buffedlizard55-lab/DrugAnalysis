#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility entry point for the pre-1985 historical build.

The authoritative builder is ``expand_pre1985_decisions_v14.py``.  This file
is retained because earlier README/session notes referenced it, but it now
forwards to the idempotent v14 builder instead of carrying a second stale,
hand-curated copy of the decision table.
"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).with_name("expand_pre1985_decisions_v14.py")
    runpy.run_path(str(target), run_name="__main__")
