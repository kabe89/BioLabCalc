"""
Module: biolabcalc.setup_wizard
Component: First-Run Portable Setup Wizard & Shared Lab Environment Initializer
Architectural Role: Guides bench researchers and automated CI/CD agents through
configuring shared lab drives (UNC paths, mapped drive letters, POSIX mounts),
validating file system permissions and SQLite locking, initializing the ELN & LIMS
database schema on shared network storage, and generating tailored config.yaml files.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import socket
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure package imports resolve when executed directly or standalone
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from biolabcalc.eln.config import (
    DEFAULT_CONFIG,
    dump_simple_yaml,
    load_config,
    anonymize_path,
    anonymize_ip,
)


# ============================================================================
# Network Path Detection
# ============================================================================

def detect_path_type(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Detect whether a designated path is a Windows UNC network share, mapped drive letter,
    POSIX network mount, or local filesystem path.

    Parameters:
        path: Filesystem path to analyze.

    Returns:
        Dictionary containing path classification details:
            - path: normalized string path
            - raw_path: original input string
            - is_network: bool (True for UNC, remote mapped drives, or POSIX mounts)
            - path_type: 'unc' | 'mapped_drive' | 'drive_letter' | 'posix_mount' | 'local'
            - details: human-readable explanation
            - server: hostname/IP if UNC path, else None
            - share: share name if UNC path, else None
            - drive_letter: drive prefix if Windows path (e.g. 'Z:'), else None
    """
    raw_str = str(path).strip()
    norm_path = os.path.normpath(raw_str)

    result: Dict[str, Any] = {
        "path": norm_path,
        "raw_path": raw_str,
        "is_network": False,
        "path_type": "local",
        "details": "Local workstation directory",
        "server": None,
        "share": None,
        "drive_letter": None,
    }

    if not raw_str:
        result["details"] = "Empty path (defaults to local workspace)"
        return result

    # 1. UNC Network Paths (e.g., \\server\share\... or //server/share/...)
    if raw_str.startswith(("\\\\", "//")) or raw_str.startswith("\\\\?\\UNC\\"):
        result["is_network"] = True
        result["path_type"] = "unc"

        # Strip leading slashes to parse server and share
        clean_unc = re.sub(r"^(?:\\\\|\/\/|\\\\[?]\/UNC\/)", "", raw_str)
        parts = [p for p in re.split(r"[\\/]+", clean_unc) if p]
        server = parts[0] if len(parts) > 0 else None
        share = parts[1] if len(parts) > 1 else None

        result["server"] = server
        result["share"] = share
        result["details"] = f"Windows UNC Network Share (Server: {server or 'unknown'}, Share: {share or 'unknown'})"
        return result

    # 2. Windows Drive Letters (e.g., Z:\..., D:/...)
    drive_match = re.match(r"^([a-zA-Z]):[\\/]?", raw_str)
    if drive_match:
        drive_letter = drive_match.group(1).upper() + ":"
        result["drive_letter"] = drive_letter

        # Check for remote drive type if running on Windows
        is_remote_drive = False
        if sys.platform == "win32":
            try:
                import ctypes
                drive_root = f"{drive_letter}\\"
                # DRIVE_REMOTE = 4 in Win32 API
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
                if drive_type == 4:
                    is_remote_drive = True
            except Exception:
                pass

        # In academic wet-lab environments, high drive letters (Z:, Y:, X:, W:, V:, U:, S:, R:, P:, N:, L:, K:, H:)
        # are mapped network shares for lab file servers / NAS.
        common_network_drives = {
            "Z:", "Y:", "X:", "W:", "V:", "U:", "T:", "S:", "R:", "Q:", "P:", "O:", "N:", "L:", "K:", "J:", "H:"
        }
        if is_remote_drive or drive_letter in common_network_drives:
            result["is_network"] = True
            result["path_type"] = "mapped_drive"
            result["details"] = f"Mapped Network Drive Letter ({drive_letter})"
        else:
            result["is_network"] = False
            result["path_type"] = "drive_letter"
            result["details"] = f"Local Windows Volume ({drive_letter})"
        return result

    # 3. POSIX Network Mounts (e.g., /mnt/labshare, /media/nas, /Volumes/SharedLab)
    posix_network_prefixes = (
        "/mnt/",
        "/media/",
        "/Volumes/",
        "/net/",
        "/share/",
        "/nfs/",
        "/smb/",
        "/var/mnt/",
    )
    for prefix in posix_network_prefixes:
        if raw_str.startswith(prefix):
            result["is_network"] = True
            result["path_type"] = "posix_mount"
            result["details"] = f"POSIX Network Mount / Distributed Volume ({prefix.strip('/')})"
            return result

    # 4. Standard Local Filesystem Path
    result["is_network"] = False
    result["path_type"] = "local"
    result["details"] = "Local filesystem directory"
    return result


# ============================================================================
# Permission & Filesystem Validation
# ============================================================================

def validate_shared_path_permissions(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Validate filesystem permissions on the designated shared path:
    1. Directory existence or automatic creation
    2. Write permissions: creates a temporary test file with binary payload
    3. Read permissions: reads back and verifies payload integrity
    4. Delete permissions: unlinks probe file
    5. Subdirectory creation & removal
    6. SQLite lock test: verifies SQLite file locking works properly (critical for SMB/NFS)

    Parameters:
        path: Path to validate.

    Returns:
        Dictionary with validation results:
            - valid: bool (True if all checks pass)
            - writable: bool
            - readable: bool
            - deletable: bool
            - sqlite_lock_ok: bool
            - path: normalized path string
            - error: error message string if failed, else None
    """
    target_str = str(path).strip()
    res: Dict[str, Any] = {
        "valid": False,
        "writable": False,
        "readable": False,
        "deletable": False,
        "sqlite_lock_ok": False,
        "path": target_str,
        "error": None,
    }

    if not target_str:
        res["error"] = "Target path cannot be empty."
        return res

    # 1. Ensure directory exists or can be created
    target_path = Path(target_str)
    try:
        os.makedirs(str(target_path), exist_ok=True)
    except (PermissionError, OSError) as e:
        res["error"] = f"Failed to access or create shared directory: {e}"
        return res

    probe_id = uuid.uuid4().hex[:8]
    probe_file = os.path.join(str(target_path), f".biolabcalc_perm_probe_{probe_id}.tmp")
    test_payload = b"BioLabCalc Shared Lab Permission & Integrity Probe\n"

    # 2. File Write Check
    try:
        with open(probe_file, "wb") as f:
            f.write(test_payload)
            f.flush()
            if hasattr(os, "fsync"):
                os.fsync(f.fileno())
        res["writable"] = True
    except (PermissionError, OSError) as e:
        res["error"] = f"Write permission denied on '{target_str}': {e}"
        return res

    # 3. File Read Check & Integrity Verification
    try:
        with open(probe_file, "rb") as f:
            content = f.read()
        if content != test_payload:
            res["error"] = "Data integrity mismatch during read-back verification."
            try:
                os.remove(probe_file)
            except Exception:
                pass
            return res
        res["readable"] = True
    except (PermissionError, OSError) as e:
        res["error"] = f"Read permission error on probe file: {e}"
        try:
            os.remove(probe_file)
        except Exception:
            pass
        return res

    # 4. File Delete Check
    try:
        os.remove(probe_file)
        res["deletable"] = True
    except (PermissionError, OSError) as e:
        res["error"] = f"Delete permission denied on probe file: {e}"
        return res

    # 5. Subdirectory Probe
    probe_dir = os.path.join(str(target_path), f".biolabcalc_dir_probe_{probe_id}")
    try:
        os.makedirs(probe_dir, exist_ok=True)
        os.rmdir(probe_dir)
    except (PermissionError, OSError) as e:
        res["error"] = f"Subdirectory creation/removal failed: {e}"
        return res

    # 6. SQLite File Locking Check (verifies file-locking protocol over SMB/NFS)
    test_db = os.path.join(str(target_path), f".biolabcalc_lock_test_{probe_id}.db")
    try:
        conn = sqlite3.connect(test_db, timeout=5.0)
        cur = conn.cursor()
        cur.execute("CREATE TABLE _test_lock (id INTEGER PRIMARY KEY, val TEXT);")
        cur.execute("INSERT INTO _test_lock (val) VALUES ('lock_ok');")
        conn.commit()
        cur.execute("SELECT val FROM _test_lock WHERE id = 1;")
        row = cur.fetchone()
        conn.close()
        if row and row[0] == "lock_ok":
            res["sqlite_lock_ok"] = True
        else:
            res["sqlite_lock_ok"] = False
            res["error"] = "SQLite lock test failed to retrieve committed data."
    except Exception as e:
        res["sqlite_lock_ok"] = False
        res["error"] = f"SQLite locking error on shared volume: {e}"
    finally:
        for f in [test_db, f"{test_db}-journal", f"{test_db}-wal", f"{test_db}-shm"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    if res["writable"] and res["readable"] and res["deletable"] and res["sqlite_lock_ok"]:
        res["valid"] = True
        res["error"] = None

    return res


# ============================================================================
# Database Schema Initialization
# ============================================================================

def init_shared_database(
    shared_dir: Union[str, Path],
    db_filename: str = "eln_lims.db",
) -> Dict[str, Any]:
    """
    Initialize the 21 ELN & LIMS database schema tables on the shared drive.
    Verifies that the database file is created, accessible, and properly structured.

    Parameters:
        shared_dir: Directory where the database file should reside.
        db_filename: Database filename (default: eln_lims.db).

    Returns:
        Dictionary containing initialization and verification details:
            - initialized: bool
            - db_path: absolute path to database file
            - db_url: SQLite connection URL
            - table_count: number of schema tables created
            - tables_created: list of table names
            - verified: bool (True if tables > 0 and db file exists)
            - size_bytes: file size in bytes
    """
    shared_path = Path(shared_dir).resolve()
    shared_path.mkdir(parents=True, exist_ok=True)

    db_file = shared_path / db_filename
    db_path_str = str(db_file)
    db_url = f"sqlite:///{db_path_str}"

    from biolabcalc.eln.schema.database import get_engine, init_db

    engine = get_engine(db_url)
    try:
        init_db(engine)
    finally:
        if hasattr(engine, "_local") and hasattr(engine._local, "conn") and engine._local.conn:
            try:
                engine._local.conn.close()
                engine._local.conn = None
            except Exception:
                pass

    if not db_file.exists():
        raise FileNotFoundError(f"Database file was not created at expected path: {db_file}")

    conn = sqlite3.connect(db_path_str)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

    return {
        "initialized": True,
        "db_path": db_path_str,
        "db_url": db_url,
        "table_count": len(tables),
        "tables_created": sorted(tables),
        "verified": len(tables) > 0,
        "size_bytes": db_file.stat().st_size if db_file.exists() else 0,
    }


# ============================================================================
# Tailored Configuration Generation
# ============================================================================

def generate_tailored_config(
    shared_dir: Union[str, Path],
    host: str = "127.0.0.1",
    port: int = 8080,
    role: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    anonymize: bool = True,
    open_browser: bool = False,
) -> Dict[str, Any]:
    """
    Generate tailored config.yaml dictionary and write it to disk.

    Parameters:
        shared_dir: Directory on shared network drive or local storage.
        host: Designated server host IP (e.g. 127.0.0.1 or 0.0.0.0).
        port: Listening TCP port (default: 8080).
        role: Deployment role ('client' / 'bench', 'server', 'standalone').
        output_path: Destination config.yaml file path.
        anonymize: Whether to enable log & IP anonymization.
        open_browser: Whether to auto-open browser on server start.

    Returns:
        Generated configuration dictionary.
    """
    path_info = detect_path_type(shared_dir)
    shared_path = Path(shared_dir).resolve()
    shared_path_str = str(shared_path)

    effective_role = (role or "client").lower().strip()
    if effective_role in ("server", "central", "host"):
        role_name = "server"
        effective_host = "0.0.0.0" if host in ("127.0.0.1", None) else host
        require_auth = True
        token_secret = secrets.token_hex(32)
        storage_mode = "client_server"
        lock_timeout = 120
        env_profile = "production"
    elif effective_role in ("standalone", "offline", "local"):
        role_name = "standalone"
        effective_host = host or "127.0.0.1"
        require_auth = False
        token_secret = None
        storage_mode = "local"
        lock_timeout = 60
        env_profile = "offline"
    else:
        # Default: Benchtop Client connected to shared drive
        role_name = "client"
        effective_host = host or "127.0.0.1"
        require_auth = False
        token_secret = None
        storage_mode = "network_share" if path_info["is_network"] else "local"
        lock_timeout = 90 if path_info["is_network"] else 60
        env_profile = "development"

    db_path = os.path.join(shared_path_str, "eln_lims.db")
    db_url = f"sqlite:///{db_path}"

    config_dict: Dict[str, Any] = {
        "server": {
            "host": effective_host,
            "port": int(port),
            "open_browser": bool(open_browser),
            "quiet": False,
            "cors_origins": ["*"],
        },
        "database": {
            "url": db_url,
            "storage_dir": shared_path_str,
            "storage_mode": storage_mode,
            "shared_folder_path": shared_path_str,
            "lock_timeout_seconds": lock_timeout,
        },
        "governance": {
            "default_approval_policy": "peer_review",
            "require_digital_seal": True,
        },
        "security": {
            "anonymize_logs": bool(anonymize),
            "token_secret": token_secret,
            "require_auth": require_auth,
        },
        "environment": env_profile,
    }

    # Write config file if output_path specified or default
    target_config = Path(output_path or "config.yaml").resolve()
    yaml_text = dump_simple_yaml(config_dict)
    header = (
        "# ============================================================================\n"
        "# BioLabCalc ELN & Multi-Modal LIMS Configuration [SHARED LAB DEPLOYMENT]\n"
        f"# Role: {role_name.upper()} ({path_info['details']})\n"
        f"# Shared Storage Path: {shared_path_str}\n"
        f"# Designated Server: http://{config_dict['server']['host']}:{config_dict['server']['port']}\n"
        "# ============================================================================\n\n"
    )

    try:
        target_config.parent.mkdir(parents=True, exist_ok=True)
        target_config.write_text(header + yaml_text, encoding="utf-8")
    except (PermissionError, OSError):
        import tempfile
        fallback = Path(tempfile.gettempdir()) / target_config.name
        fallback.write_text(header + yaml_text, encoding="utf-8")
        target_config = fallback

    config_dict["_config_path"] = str(target_config)
    return config_dict


# ============================================================================
# First-Run Setup Wizard Core Routine
# ============================================================================

def run_setup_wizard(
    non_interactive: bool = False,
    shared_dir: Optional[Union[str, Path]] = None,
    role: Optional[str] = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    config_output: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Interactive or programmatically callable first-run setup wizard for BioLabCalc.

    Workflow:
    1. Detects network paths (UNC, mapped drive letters, POSIX mounts).
    2. Validates filesystem write permissions and SQLite locking on designated shared path.
    3. Initializes the ELN & LIMS database schema on the shared drive (verifying creation).
    4. Generates a tailored config.yaml with storage_dir, server, and security settings.
    5. Returns a structured summary dictionary with verification details.

    Parameters:
        non_interactive: If True, uses arguments without interactive console prompts.
        shared_dir: Target directory on shared network drive or local storage.
        role: 'client' (benchtop), 'server' (shared central), or 'standalone'.
        host: Designated server host IP (default: 127.0.0.1).
        port: Designated server TCP port (default: 8080).
        config_output: Destination config.yaml file path (default: config.yaml).

    Returns:
        Dictionary containing setup status, configuration path, and verification details.
    """
    effective_role = role
    effective_shared_dir = shared_dir
    effective_host = host
    effective_port = port
    effective_config_path = Path(config_output or "config.yaml").resolve()

    if not non_interactive:
        print("=" * 78)
        print("   BIOLABCALC ZERO-INSTALL PORTABLE SETUP WIZARD")
        print("   Shared Lab Drive & Multi-Seat Benchtop Deployment")
        print("=" * 78)
        print("This wizard configures BioLabCalc for your shared wet-lab drive,")
        print("verifies network file permissions, and initializes the database schema.\n")

        # 1. Interactive Role Selection
        if not effective_role:
            print("Select Deployment Role:")
            print("  [1] Benchtop Client (runs local instance, shares data on network drive) [DEFAULT]")
            print("  [2] Shared Central Lab Server (binds to 0.0.0.0 for multi-client access)")
            print("  [3] Standalone Offline Researcher (local storage, isolated mode)")
            try:
                choice = input("Enter choice [1-3] (default: 1): ").strip()
            except (EOFError, KeyboardInterrupt):
                choice = "1"
            if choice == "2":
                effective_role = "server"
            elif choice == "3":
                effective_role = "standalone"
            else:
                effective_role = "client"

        # 2. Interactive Shared Directory Selection
        if not effective_shared_dir:
            default_candidate = "Z:\\BioLabData" if sys.platform == "win32" else "/mnt/labshare/biolabdata"
            print(f"\nEnter path to shared lab drive directory (e.g. Z:\\LabData, \\\\server\\share\\data, /mnt/labshare):")
            try:
                entered_dir = input(f"Shared Directory [{default_candidate}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                entered_dir = ""
            effective_shared_dir = entered_dir or default_candidate

        # 3. Interactive Server Host & Port Selection
        if effective_role == "server" and effective_host == "127.0.0.1":
            effective_host = "0.0.0.0"

        try:
            port_input = input(f"Server Port [{effective_port}]: ").strip()
            if port_input:
                effective_port = int(port_input)
        except (ValueError, EOFError, KeyboardInterrupt):
            pass

    else:
        # Non-interactive defaults
        if not effective_role:
            effective_role = "client"
        if not effective_shared_dir:
            candidate_dir = os.path.join(os.getcwd(), ".biolabcalc_data")
            test_perm = validate_shared_path_permissions(candidate_dir)
            if test_perm["valid"]:
                effective_shared_dir = candidate_dir
            else:
                import tempfile
                effective_shared_dir = os.path.join(tempfile.gettempdir(), ".biolabcalc_eln")

    # Step 1: Detect Network Path Type
    path_info = detect_path_type(effective_shared_dir)

    # Step 2: Validate File Permissions & Locking on Shared Directory
    perm_info = validate_shared_path_permissions(effective_shared_dir)
    if not perm_info["valid"]:
        error_msg = perm_info.get("error", "Permission check failed")
        if not non_interactive:
            print(f"\n[!] ERROR: Permission validation failed on '{effective_shared_dir}':")
            print(f"    {error_msg}")
        return {
            "status": "error",
            "error": error_msg,
            "permissions": perm_info,
            "path_info": path_info,
            "config_path": str(effective_config_path),
            "storage_dir": str(effective_shared_dir),
            "db_path": None,
            "database": None,
            "server": {"host": effective_host, "port": effective_port},
            "role": effective_role,
            "verification": {
                "permissions_verified": False,
                "config_written": False,
                "database_created": False,
                "tables_count": 0,
            },
        }

    # Step 3: Initialize Database Schema on Shared Drive
    try:
        db_info = init_shared_database(effective_shared_dir)
    except Exception as e:
        error_msg = f"Database schema initialization failed on '{effective_shared_dir}': {e}"
        if not non_interactive:
            print(f"\n[!] ERROR: {error_msg}")
        return {
            "status": "error",
            "error": error_msg,
            "permissions": perm_info,
            "path_info": path_info,
            "config_path": str(effective_config_path),
            "storage_dir": str(effective_shared_dir),
            "db_path": None,
            "database": None,
            "server": {"host": effective_host, "port": effective_port},
            "role": effective_role,
            "verification": {
                "permissions_verified": True,
                "config_written": False,
                "database_created": False,
                "tables_count": 0,
            },
        }

    # Step 4: Generate Tailored config.yaml
    cfg_data = generate_tailored_config(
        shared_dir=effective_shared_dir,
        host=effective_host,
        port=effective_port,
        role=effective_role,
        output_path=effective_config_path,
        anonymize=True,
    )
    if "_config_path" in cfg_data:
        effective_config_path = Path(cfg_data["_config_path"])

    # Step 5: Summary Output
    config_written = effective_config_path.exists()
    db_created = db_info.get("verified", False)

    if not non_interactive:
        print("\n" + "=" * 78)
        print("[OK] BIOLABCALC SETUP COMPLETED SUCCESSFULLY!")
        print("=" * 78)
        print(f"[*] Deployment Role:     {effective_role.upper()}")
        print(f"[*] Path Architecture:   {path_info['details']}")
        print(f"[*] Storage Directory:   {effective_shared_dir}")
        print(f"[*] Database File:       {db_info['db_path']} ({db_info['table_count']} tables verified)")
        print(f"[*] Configuration File:  {effective_config_path}")
        print(f"[*] Designated Server:   http://{cfg_data['server']['host']}:{cfg_data['server']['port']}")
        print("-" * 78)
        print("You can now launch BioLabCalc using:")
        print("  Windows: run_lab.bat   OR   python run.py eln")
        print("  Linux:   ./run_lab.sh  OR   python3 run.py eln")
        print("=" * 78 + "\n")

    return {
        "status": "success",
        "role": effective_role,
        "config_path": str(effective_config_path),
        "storage_dir": str(Path(effective_shared_dir).resolve()),
        "db_path": db_info.get("db_path"),
        "path_info": path_info,
        "permissions": perm_info,
        "database": db_info,
        "server": {
            "host": cfg_data["server"]["host"],
            "port": cfg_data["server"]["port"],
        },
        "verification": {
            "permissions_verified": perm_info.get("valid", False),
            "database_created": db_created,
            "config_written": config_written,
            "tables_count": db_info.get("table_count", 0),
        },
    }


# ============================================================================
# CLI Command Entrypoint
# ============================================================================

def main() -> int:
    """CLI entrypoint for running setup wizard directly."""
    parser = argparse.ArgumentParser(
        description="BioLabCalc Portable First-Run Setup Wizard & Shared Lab Initializer"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run wizard non-interactively using provided arguments or defaults",
    )
    parser.add_argument(
        "--shared-dir",
        default=None,
        help="Path to shared lab network directory (e.g. Z:\\LabData or /mnt/labshare)",
    )
    parser.add_argument(
        "--role",
        choices=["client", "bench", "server", "standalone"],
        default=None,
        help="Target deployment role",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host IP to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Server listening TCP port (default: 8080)",
    )
    parser.add_argument(
        "-c", "--config-output",
        default=None,
        help="Destination path for generated config.yaml",
    )

    args = parser.parse_args()
    summary = run_setup_wizard(
        non_interactive=args.non_interactive,
        shared_dir=args.shared_dir,
        role=args.role,
        host=args.host,
        port=args.port,
        config_output=args.config_output,
    )
    return 0 if summary.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
