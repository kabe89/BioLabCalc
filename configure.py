#!/usr/bin/env python3
"""
BioLabCalc ELN & Multi-Modal LIMS Environment Configuration Utility.
Sets up runtime configuration, server host/port binding, database URLs,
and security/anonymization presets across development, production, test, and offline bench modes.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

# Add src to sys.path
repo_root = Path(__file__).resolve().parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from biolabcalc.eln.config import (
    DEFAULT_CONFIG,
    ENVIRONMENT_PRESETS,
    dump_simple_yaml,
    load_config,
    _deep_merge,
)


def check_python_version() -> bool:
    """Check if Python version meets requirements (>= 3.8)."""
    major, minor = sys.version_info[:2]
    return major == 3 and minor >= 8


def check_port_available(host: str, port: int) -> bool:
    """Test whether target host and port can be bound."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        bind_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
        sock.bind((bind_host, port))
        sock.close()
        return True
    except (socket.error, OSError):
        return False


def detect_environment_capabilities() -> dict:
    """Audit installed packages and backend engines."""
    caps = {
        "uvicorn": False,
        "fastapi": False,
        "sqlalchemy": False,
        "pyyaml": False,
        "pillow": False,
        "openpyxl": False,
    }
    try:
        import uvicorn
        caps["uvicorn"] = True
    except ImportError:
        pass

    try:
        import fastapi
        caps["fastapi"] = True
    except ImportError:
        pass

    try:
        import sqlalchemy
        caps["sqlalchemy"] = True
    except ImportError:
        pass

    try:
        import yaml
        caps["pyyaml"] = True
    except ImportError:
        pass

    try:
        from PIL import Image
        caps["pillow"] = True
    except ImportError:
        pass

    try:
        import openpyxl
        caps["openpyxl"] = True
    except Exception:
        pass

    return caps


def configure_environment(
    env: str = "development",
    host: str | None = None,
    port: int | None = None,
    db_url: str | None = None,
    anonymize: bool | None = None,
    output_path: str = "config.yaml",
    force: bool = False,
    quiet: bool = False,
) -> dict:
    """Configure ELN server and generate designated config.yaml."""
    if not check_python_version():
        raise RuntimeError(f"Python 3.8+ required. Current version: {sys.version}")

    env_preset = ENVIRONMENT_PRESETS.get(env, ENVIRONMENT_PRESETS["development"])
    merged = _deep_merge(DEFAULT_CONFIG, env_preset)

    if host is not None:
        merged["server"]["host"] = host
    if port is not None:
        merged["server"]["port"] = int(port)
    if db_url is not None:
        merged["database"]["url"] = db_url
    if anonymize is not None:
        merged["security"]["anonymize_logs"] = bool(anonymize)

    out_file = Path(output_path).resolve()
    if out_file.exists() and not force:
        # Don't overwrite unless requested
        pass
    else:
        yaml_content = dump_simple_yaml(merged)
        header = (
            "# ============================================================================\n"
            f"# BioLabCalc ELN & LIMS Configuration [{env.upper()} ENVIRONMENT]\n"
            f"# Configured for server host: {merged['server']['host']}:{merged['server']['port']}\n"
            "# ============================================================================\n\n"
        )
        try:
            out_file.write_text(header + yaml_content, encoding="utf-8")
        except (PermissionError, OSError):
            import tempfile
            fallback = Path(tempfile.gettempdir()) / out_file.name
            fallback.write_text(header + yaml_content, encoding="utf-8")
            out_file = fallback

    if not quiet:
        caps = detect_environment_capabilities()
        print("=" * 72)
        print("  BIOLABCALC ELN & MULTI-MODAL LIMS ENVIRONMENT CONFIGURATION")
        print("=" * 72)
        print(f"[*] Environment Profile: {env.upper()}")
        print(f"[*] Designated Server:    http://{merged['server']['host']}:{merged['server']['port']}")
        print(f"[*] Database Target:      {merged['database']['url'] or 'Local SQLite (~/.biolabcalc_eln)'}")
        print(f"[*] Anonymization:        {'ENABLED (PII / IPs masked)' if merged['security']['anonymize_logs'] else 'DISABLED'}")
        print(f"[*] Config Output:        {out_file}")
        print("-" * 72)
        print("  Runtime Engine Detection:")
        print(f"  - Web Server:           {'High-Performance ASGI (Uvicorn/FastAPI)' if (caps['uvicorn'] and caps['fastapi']) else 'Pure-Python Standalone Server (Fallback)'}")
        print(f"  - Database ORM:         {'Full SQLAlchemy 2.0+ Engine' if caps['sqlalchemy'] else 'Zero-Dependency SQLite CAS Adapter'}")
        print(f"  - YAML Serialization:   {'PyYAML 6+' if caps['pyyaml'] else 'Zero-Dependency Simple YAML Engine'}")
        print(f"  - Scientific Imaging:   {'Pillow Engine Active' if caps['pillow'] else 'Vector SVG Engine Active'}")
        print("=" * 72)
        print("[OK] Environment successfully configured. Start ELN using:")
        print("    biolabcalc eln")
        print("=" * 72)

    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BioLabCalc ELN & Multi-Modal LIMS Environment Setup & Server Designator"
    )
    parser.add_argument(
        "--env",
        choices=["development", "production", "test", "offline"],
        default="development",
        help="Target environment profile (default: development)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Designated server host IP or interface to bind (e.g. 127.0.0.1, 0.0.0.0)",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=None,
        help="Designated server listening port (default: 8080)",
    )
    parser.add_argument(
        "--db",
        dest="db_url",
        default=None,
        help="Database connection URL",
    )
    parser.add_argument(
        "--anonymize",
        action="store_true",
        default=None,
        help="Enable IP, path, and telemetry anonymization",
    )
    parser.add_argument(
        "-o", "--output",
        default="config.yaml",
        help="Destination configuration file path (default: config.yaml)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite target config file if already present",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress banner output",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Perform diagnostic checks without writing configuration",
    )

    args = parser.parse_args()

    if args.check_only:
        caps = detect_environment_capabilities()
        print(f"[OK] Python 3.8+ compliant: {check_python_version()}")
        print(f"[*] Engine capabilities: {caps}")
        return 0

    try:
        configure_environment(
            env=args.env,
            host=args.host,
            port=args.port,
            db_url=args.db_url,
            anonymize=args.anonymize,
            output_path=args.output,
            force=args.force,
            quiet=args.quiet,
        )
        return 0
    except Exception as e:
        print(f"[!] Configuration failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
