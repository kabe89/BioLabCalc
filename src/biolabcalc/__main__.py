"""
BioLabCalc Top-Level Module Execution Entrypoint

Enables direct execution via:
  python -m biolabcalc [args]
  python src/biolabcalc [args]
  python -m biolabcalc.cli [args]
"""

import os
import sys

# Ensure the parent 'src' directory is in sys.path so 'biolabcalc' can be imported
package_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(package_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

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
