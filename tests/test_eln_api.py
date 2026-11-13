"""
Module: tests.test_eln_api
Component: Redirect / Stub for tests.test_eln_services_and_api
Architectural Role: Forwarding stub pointing to canonical test_eln_services_and_api.
"""

import os
import sys

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# Consolidated into tests/test_eln_services_and_api.py to prevent redundant test execution.
