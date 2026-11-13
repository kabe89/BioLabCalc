import os
import sys
import mimetypes

# Fix Windows registry access permission error in sandboxed/restricted environments
try:
    if hasattr(mimetypes, "_mimetypes_read_windows_registry"):
        mimetypes._mimetypes_read_windows_registry = None
    mimetypes.init()
except Exception:
    mimetypes.inited = True

# Ensure src/ is in sys.path for pytest and test runners
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
