#!/usr/bin/env python3
"""
BioLabCalc Root Launcher / Entrypoint

Allows running BioLabCalc directly from a repository checkout or clone
without requiring the package to be pre-installed in site-packages.
"""

import os
import sys

# Ensure src/ is on sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Fix Windows registry access permission error in sandboxed/restricted environments
try:
    import mimetypes
    if hasattr(mimetypes, "_mimetypes_read_windows_registry"):
        mimetypes._mimetypes_read_windows_registry = None
    mimetypes.init()
except Exception:
    pass

from biolabcalc.cli import main

if __name__ == "__main__":
    main()
