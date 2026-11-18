#!/usr/bin/env python3
"""
Verification script for BioLabCalc Wiki.
Delegates to the canonical update_wiki.py script with --check flag.
"""

import subprocess
import sys
from pathlib import Path


def verify_wiki() -> int:
    """Run canonical wiki verification and audit."""
    script_path = Path(__file__).resolve().parent / "update_wiki.py"
    cmd = [sys.executable, str(script_path), "--check"]
    res = subprocess.run(cmd)
    return res.returncode


if __name__ == "__main__":
    sys.exit(verify_wiki())
