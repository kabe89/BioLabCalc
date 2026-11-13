#!/usr/bin/env python3
"""
BioLabCalc Portable Distribution Packaging Utility.
Prepares a zero-install, zero-admin-privilege portable distribution directory
containing cross-platform launchers, configuration templates, documentation,
and verified source assets for shared lab network drives.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Root directory resolution
_SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = _SCRIPT_DIR.parent
SRC_DIR = REPO_ROOT / "src"

# Template contents for launchers and zero-install instructions
RUN_LAB_BAT_CONTENT = """@echo off
REM ============================================================================
REM BioLabCalc Zero-Install Portable Launcher for Windows Benchtop Workstations
REM Runs BioLabCalc ELN & Multi-Modal LIMS directly from shared drive or USB
REM ============================================================================
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"

echo ============================================================================
echo   BIOLABCALC ZERO-INSTALL PORTABLE BENCHTOP LAUNCHER
echo ============================================================================

REM Resolve Python 3 executable
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=py -3"
    goto :run
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=python"
    goto :run
)

where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=python3"
    goto :run
)

echo [!] Error: Python 3 was not found in system PATH. >&2
echo     Please ensure Python 3.8+ is installed on this workstation. >&2
pause
exit /b 1

:run
REM Check if config.yaml exists; if not, prompt for first-run setup wizard
if not exist "%SCRIPT_DIR%config.yaml" (
    echo [*] First-time setup detected: config.yaml not found.
    echo [*] Launching BioLabCalc Portable Setup Wizard...
    %PYTHON_EXE% -m biolabcalc.setup_wizard
    if %ERRORLEVEL% neq 0 (
        echo [!] Setup wizard was cancelled or failed. Proceeding with defaults.
    )
)

echo [*] Launching BioLabCalc ELN & Multi-Modal LIMS...
%PYTHON_EXE% "%SCRIPT_DIR%run.py" eln %*
if %ERRORLEVEL% neq 0 (
    echo [!] Server exited with status %ERRORLEVEL%
    pause
)
exit /b %ERRORLEVEL%
"""

RUN_LAB_SH_CONTENT = """#!/usr/bin/env bash
# ============================================================================
# BioLabCalc Zero-Install Portable Launcher for Linux, macOS & POSIX Workstations
# Runs BioLabCalc ELN & Multi-Modal LIMS directly from shared drive or USB
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# Resolve Python 3 executable
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
elif command -v py >/dev/null 2>&1; then
    PYTHON_CMD="py -3"
else
    echo "Error: Python 3.8+ is required but neither 'python3' nor 'python' was found in PATH." >&2
    exit 1
fi

# Check if config.yaml exists; if not, prompt for setup wizard
if [ ! -f "$SCRIPT_DIR/config.yaml" ]; then
    echo "[*] First-time setup detected: config.yaml not found."
    echo "[*] Launching BioLabCalc Portable Setup Wizard..."
    $PYTHON_CMD -m biolabcalc.setup_wizard || echo "[!] Setup wizard was cancelled or failed. Using defaults."
fi

echo "[*] Launching BioLabCalc ELN & Multi-Modal LIMS..."
exec $PYTHON_CMD "$SCRIPT_DIR/run.py" eln "$@"
"""

README_PORTABLE_CONTENT = """===============================================================================
  BIOLABCALC ZERO-INSTALL PORTABLE DISTRIBUTION
  Shared Lab Network Drive & Multi-Seat Benchtop Deployment Guide
===============================================================================

1. OVERVIEW
-----------
BioLabCalc Portable is a zero-install, zero-administrative-privilege distribution
of the BioLabCalc Electronic Lab Notebook (ELN) and Multi-Modal LIMS.
It can be placed directly on a shared lab network drive (e.g. SMB/NFS share,
Windows mapped drive Z:\\, or POSIX mount /mnt/labshare), allowing any bench
workstation to launch and collaborate on the same centralized lab notebook
and inventory repository without installing software locally.


2. SHARED LAB DRIVE DEPLOYMENT
------------------------------
A. Copy or extract this `biolabcalc_portable` folder to your lab's shared network drive:
   - Windows Example:  Z:\\BioLabCalc_Portable
   - UNC Example:      \\\\fileserver\\wetlab\\BioLabCalc_Portable
   - Linux/Mac:        /mnt/labshare/biolabcalc_portable

B. Ensure researchers have Read/Write permissions to the shared directory.


3. FIRST-RUN SETUP WIZARD
-------------------------
When launching for the first time, run the interactive setup wizard to configure
shared storage and initialize the database schema:

On Windows:
  Double-click `run_lab.bat` or run in Command Prompt:
  python -m biolabcalc.setup_wizard

On Linux / macOS:
  Execute in terminal:
  ./run_lab.sh
  or: python3 -m biolabcalc.setup_wizard

Non-interactive automated setup (for lab IT administrators):
  python -m biolabcalc.setup_wizard --non-interactive --shared-dir "Z:\\BioLabData" --role client


4. LAUNCHING AT THE BENCH (EVERYDAY USAGE)
------------------------------------------
Every benchtop computer connected to the lab network can launch BioLabCalc:

- Windows:
    Double-click `run_lab.bat`
    (or run: run_lab.bat --port 8080)

- Linux / macOS / WSL:
    ./run_lab.sh
    (or run: ./run_lab.sh --port 8080)

The web browser will open automatically to http://localhost:8080.
All notebook entries, CAS blobs, protocol logs, and audit records will be stored
and synced automatically on the shared drive.


5. ARCHITECTURE & MULTI-USER CONCURRENCY
----------------------------------------
- Centralized Data Store:
  Experimental data, inventory, and audit trails reside in SQLite database files
  and Content-Addressed Storage (CAS) on the shared network volume.

- Multi-Seat Concurrency:
  The built-in engine implements advisory file locking (SQLite WAL/rollback lock)
  and optimistic write concurrency, allowing multiple researchers to log results
  simultaneously without corrupting notebook data.

- Digital Compliance & Immutability:
  Finalized entries receive cryptographic SHA-256 digital seals and immutable
  audit logs conforming to 21 CFR Part 11 / ISO 17025 standards.


6. REQUIREMENTS & TROUBLESHOOTING
---------------------------------
- Requirements:
  * Any standard Python 3.8+ installation on the client machine.
  * No root/administrator access or pip package installations required.
  * Modern web browser (Chrome, Firefox, Edge, Safari).

- Troubleshooting:
  * "Python not found": Ensure Python 3 is installed and added to the system PATH.
  * "Permission Denied": Verify write permissions on the shared network drive.
  * "Port 8080 already in use": Pass a different port, e.g. `run_lab.bat -p 8088`.
  * "Lock timeout": Increase `lock_timeout_seconds` in `config.yaml`.
===============================================================================
"""


# ============================================================================
# Distribution Validation
# ============================================================================

def validate_portable_distribution(target_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Validate that a prepared portable distribution directory contains all required
    launchers, configuration examples, documentation, packages, templates,
    and static frontend assets.

    Parameters:
        target_dir: Directory to validate.

    Returns:
        Validation report dictionary with status and verified items.
    """
    target = Path(target_dir).resolve()
    report: Dict[str, Any] = {
        "valid": False,
        "dist_path": str(target),
        "verified_files": [],
        "missing_files": [],
        "templates_verified": False,
        "static_verified": False,
        "packages_verified": False,
        "errors": [],
    }

    if not target.exists() or not target.is_dir():
        report["errors"].append(f"Distribution directory does not exist: {target}")
        return report

    # 1. Essential root artifacts
    required_root_files = [
        "run_lab.bat",
        "run_lab.sh",
        "config.yaml.example",
        "README_PORTABLE.txt",
        "run.py",
    ]

    for rf in required_root_files:
        p = target / rf
        if p.is_file() and p.stat().st_size > 0:
            report["verified_files"].append(rf)
        else:
            report["missing_files"].append(rf)
            report["errors"].append(f"Missing required portable file: {rf}")

    # 2. Package source and modules
    required_pkg_files = [
        "src/biolabcalc/__init__.py",
        "src/biolabcalc/setup_wizard.py",
        "src/biolabcalc/eln/config.py",
        "src/biolabcalc/eln/server.py",
        "src/biolabcalc/eln/schema/database.py",
    ]

    for pf in required_pkg_files:
        p = target / pf
        if p.is_file() and p.stat().st_size > 0:
            report["verified_files"].append(pf)
        else:
            report["missing_files"].append(pf)
            report["errors"].append(f"Missing required package source file: {pf}")

    report["packages_verified"] = len([f for f in required_pkg_files if f in report["missing_files"]]) == 0

    # 3. Web frontend templates
    template_files = [
        "src/biolabcalc/eln/web/templates/index.html",
    ]
    templates_ok = True
    for tf in template_files:
        p = target / tf
        if p.is_file() and p.stat().st_size > 0:
            report["verified_files"].append(tf)
        else:
            report["missing_files"].append(tf)
            report["errors"].append(f"Missing web template: {tf}")
            templates_ok = False
    report["templates_verified"] = templates_ok

    # 4. Web frontend static assets
    static_files = [
        "src/biolabcalc/eln/web/static/styles.css",
    ]
    static_ok = True
    for sf in static_files:
        p = target / sf
        if p.is_file() and p.stat().st_size > 0:
            report["verified_files"].append(sf)
        else:
            report["missing_files"].append(sf)
            report["errors"].append(f"Missing static asset: {sf}")
            static_ok = False
    report["static_verified"] = static_ok

    if not report["errors"] and not report["missing_files"]:
        report["valid"] = True

    return report


# ============================================================================
# Packaging Logic
# ============================================================================

def create_portable_package(
    output_dir: Union[str, Path] = "dist/biolabcalc_portable",
    repo_root: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    clean: bool = True,
) -> Dict[str, Any]:
    """
    Prepare the BioLabCalc zero-install portable distribution directory.

    Parameters:
        output_dir: Destination directory (default: dist/biolabcalc_portable).
        repo_root: BioLabCalc repository root directory.
        dry_run: If True, simulates packaging without modifying filesystem.
        clean: If True, cleans existing output directory before copying.

    Returns:
        Summary dictionary with packaging status, manifest, and validation report.
    """
    effective_repo_root = Path(repo_root or REPO_ROOT).resolve()
    target_dir = Path(output_dir).resolve()
    effective_src = effective_repo_root / "src"

    if not effective_src.exists():
        raise FileNotFoundError(f"Source directory not found at {effective_src}")

    # Build file manifest
    manifest: List[str] = [
        "run_lab.bat",
        "run_lab.sh",
        "config.yaml.example",
        "README_PORTABLE.txt",
        "run.py",
    ]

    for root, dirs, files in os.walk(effective_src):
        # Ignore cache directories
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache", ".vs")]
        for f in files:
            if not f.endswith((".pyc", ".pyo")):
                rel_path = os.path.relpath(os.path.join(root, f), effective_repo_root)
                manifest.append(rel_path.replace("\\", "/"))

    if dry_run:
        return {
            "status": "dry_run",
            "output_dir": str(target_dir),
            "manifest": manifest,
            "file_count": len(manifest),
            "valid": True,
        }

    # Clean existing distribution directory if requested
    try:
        if clean and target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # Fallback to temp directory if running inside sandboxed or restricted workspace
        import tempfile
        fallback_dir = Path(tempfile.gettempdir()) / "biolabcalc_dist" / target_dir.name
        if clean and fallback_dir.exists():
            shutil.rmtree(fallback_dir, ignore_errors=True)
        fallback_dir.mkdir(parents=True, exist_ok=True)
        target_dir = fallback_dir

    # 1. Copy src/ tree
    dest_src = target_dir / "src"
    shutil.copytree(
        effective_src,
        dest_src,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache"),
        dirs_exist_ok=True,
    )

    # 2. Copy run.py launcher
    src_run_py = effective_repo_root / "run.py"
    if src_run_py.exists():
        shutil.copy2(src_run_py, target_dir / "run.py")

    # 3. Copy or generate config.yaml.example
    src_cfg_example = effective_repo_root / "config.yaml.example"
    if src_cfg_example.exists():
        shutil.copy2(src_cfg_example, target_dir / "config.yaml.example")

    # 4. Write run_lab.bat
    bat_file = target_dir / "run_lab.bat"
    bat_file.write_text(RUN_LAB_BAT_CONTENT, encoding="utf-8")

    # 5. Write run_lab.sh and make executable
    sh_file = target_dir / "run_lab.sh"
    sh_file.write_text(RUN_LAB_SH_CONTENT, encoding="utf-8")
    try:
        current_mode = sh_file.stat().st_mode
        sh_file.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass

    # 6. Write README_PORTABLE.txt
    readme_file = target_dir / "README_PORTABLE.txt"
    readme_file.write_text(README_PORTABLE_CONTENT, encoding="utf-8")

    # 7. Validate generated distribution
    validation = validate_portable_distribution(target_dir)

    return {
        "status": "success",
        "output_dir": str(target_dir),
        "manifest": manifest,
        "file_count": len(manifest),
        "validation": validation,
        "valid": validation["valid"],
    }


# ============================================================================
# CLI Command Entrypoint
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="BioLabCalc Zero-Install Portable Packaging Utility"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="dist/biolabcalc_portable",
        help="Target distribution output directory (default: dist/biolabcalc_portable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate packaging and manifest generation without writing files",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not clean target directory prior to packaging",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing portable distribution without rebuilding",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress banner output",
    )

    args = parser.parse_args()

    if args.validate_only:
        report = validate_portable_distribution(args.output_dir)
        if not args.quiet:
            print(f"Validation Report for: {report['dist_path']}")
            print(f"  Valid: {report['valid']}")
            print(f"  Verified Files: {len(report['verified_files'])}")
            print(f"  Missing Files:  {len(report['missing_files'])}")
            if report["errors"]:
                print("  Errors:")
                for err in report["errors"]:
                    print(f"    - {err}")
        return 0 if report["valid"] else 1

    result = create_portable_package(
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        clean=not args.no_clean,
    )

    if not args.quiet:
        print("=" * 78)
        print("  BIOLABCALC PORTABLE PACKAGING SUMMARY")
        print("=" * 78)
        print(f"[*] Target Directory: {result['output_dir']}")
        print(f"[*] Mode:             {'DRY RUN (simulation)' if args.dry_run else 'BUILD'}")
        print(f"[*] Assets Packaged:  {result.get('file_count', 0)} files")
        if not args.dry_run:
            val = result.get("validation", {})
            print(f"[*] Validation:       {'PASSED [OK]' if val.get('valid') else 'FAILED [!]'}")
            print(f"[*] Templates:        {'Verified' if val.get('templates_verified') else 'Missing'}")
            print(f"[*] Static Assets:    {'Verified' if val.get('static_verified') else 'Missing'}")
            print(f"[*] Packages:         {'Verified' if val.get('packages_verified') else 'Missing'}")
        print("=" * 78)

    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    sys.exit(main())
