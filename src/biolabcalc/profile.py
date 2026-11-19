"""
Module: biolabcalc.profile
Component: Centralized BioLabCalc Profile and Storage Directory Resolver
Architectural Role: Unifies storage directory discovery across all core calculators,
custom catalogs (buffers, plasmids, sequences), and the ELN/LIMS database.

Precedence:
1. BIOLABCALC_HOME environment variable
2. BIOLABCALC_STORAGE_DIR environment variable
3. database.storage_dir in discovered config.yaml
4. Default ~/.biolabcalc directory (with tempdir fallback)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def get_biolabcalc_home() -> Path:
    """
    Resolve and return the canonical BioLabCalc profile and data directory.

    Evaluated dynamically at runtime so tests and workflows can redirect
    storage via environment variables without process restarts.
    """
    env_home = os.environ.get("BIOLABCALC_HOME")
    if env_home and env_home.strip():
        p = Path(env_home.strip()).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    env_storage = os.environ.get("BIOLABCALC_STORAGE_DIR")
    if env_storage and env_storage.strip():
        p = Path(env_storage.strip()).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Check for config.yaml storage_dir if config exists
    try:
        from .eln.config import find_config_file, load_config
        cfg_path = find_config_file()
        if cfg_path and cfg_path.is_file():
            cfg = load_config(str(cfg_path))
            storage = cfg.get("database", {}).get("storage_dir")
            if storage and str(storage).strip():
                p = Path(str(storage).strip()).expanduser().resolve()
                p.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass

    # Default to ~/.biolabcalc with safe fallback for restricted sandbox environments
    try:
        p = Path.home() / ".biolabcalc"
        p.mkdir(parents=True, exist_ok=True)
        # Probe writability in sandboxed environments
        probe_file = p / ".probe_write"
        probe_file.write_text("probe", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        return p
    except (PermissionError, OSError):
        import tempfile
        p = Path(tempfile.gettempdir()) / ".biolabcalc"
        p.mkdir(parents=True, exist_ok=True)
        return p


def get_profile_dir() -> Path:
    """Convenience alias for get_biolabcalc_home()."""
    return get_biolabcalc_home()
