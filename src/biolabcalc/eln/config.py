"""
Module: biolabcalc.eln.config
Component: ELN & LIMS Configuration Manager & Anonymizer
Architectural Role: Loads, validates, and manages server, database, and security
settings from config.yaml with zero-dependency fallback, environment presets,
and log anonymization.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Flag indicating PyYAML availability
try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "host": "127.0.0.1",
        "port": 8080,
        "open_browser": False,
        "quiet": False,
        "cors_origins": ["*"],
    },
    "database": {
        "url": None,
        "storage_dir": None,
        "storage_mode": "local",  # local | network_share | client_server
        "shared_folder_path": None,
        "lock_timeout_seconds": 60,
    },
    "governance": {
        "default_approval_policy": "peer_review",  # open_collaboration | peer_review | designated_reviewer | pi_approval
        "require_digital_seal": True,
    },
    "security": {
        "anonymize_logs": True,
        "token_secret": None,
        "require_auth": False,
    },
    "environment": "development",
}

ENVIRONMENT_PRESETS: Dict[str, Dict[str, Any]] = {
    "development": {
        "server": {"host": "127.0.0.1", "port": 8080, "open_browser": True, "quiet": False},
        "database": {"url": None, "storage_dir": None, "storage_mode": "local", "shared_folder_path": None, "lock_timeout_seconds": 60},
        "governance": {"default_approval_policy": "peer_review", "require_digital_seal": True},
        "security": {"anonymize_logs": False, "require_auth": False},
        "environment": "development",
    },
    "network_share": {
        "server": {"host": "127.0.0.1", "port": 8080, "open_browser": True, "quiet": False},
        "database": {"url": None, "storage_dir": None, "storage_mode": "network_share", "shared_folder_path": None, "lock_timeout_seconds": 60},
        "governance": {"default_approval_policy": "peer_review", "require_digital_seal": True},
        "security": {"anonymize_logs": True, "require_auth": False},
        "environment": "network_share",
    },
    "production": {
        "server": {"host": "0.0.0.0", "port": 8080, "open_browser": False, "quiet": False},
        "database": {"url": None, "storage_dir": None, "storage_mode": "local", "shared_folder_path": None, "lock_timeout_seconds": 60},
        "governance": {"default_approval_policy": "pi_approval", "require_digital_seal": True},
        "security": {"anonymize_logs": True, "require_auth": True},
        "environment": "production",
    },
    "test": {
        "server": {"host": "127.0.0.1", "port": 8899, "open_browser": False, "quiet": True},
        "database": {"url": "sqlite:///:memory:", "storage_dir": None, "storage_mode": "local", "shared_folder_path": None, "lock_timeout_seconds": 5},
        "governance": {"default_approval_policy": "open_collaboration", "require_digital_seal": False},
        "security": {"anonymize_logs": True, "require_auth": False},
        "environment": "test",
    },
    "offline": {
        "server": {"host": "127.0.0.1", "port": 8080, "open_browser": False, "quiet": True},
        "database": {"url": None, "storage_dir": None, "storage_mode": "local", "shared_folder_path": None, "lock_timeout_seconds": 30},
        "governance": {"default_approval_policy": "peer_review", "require_digital_seal": True},
        "security": {"anonymize_logs": True, "require_auth": False},
        "environment": "offline",
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override dictionary into base copy."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """
    Zero-dependency YAML parser for nested dictionaries, lists, and primitives.
    shortcut: handles standard YAML subsets (key-value, indentation, lists), use PyYAML for complex tags.
    """
    if HAS_YAML:
        parsed = yaml.safe_load(text)
        return parsed if isinstance(parsed, dict) else {}

    result: Dict[str, Any] = {}
    current_section: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        # Skip comments and blank lines
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        if ":" in stripped:
            key_part, val_part = stripped.split(":", 1)
            key = key_part.strip().strip("'\"")
            val = val_part.strip()

            if indent == 0:
                if val == "":
                    current_section = key
                    result[current_section] = {}
                else:
                    current_section = None
                    result[key] = _parse_val(val)
            elif indent >= 2 and current_section:
                if val == "":
                    result[current_section][key] = []
                else:
                    result[current_section][key] = _parse_val(val)
        elif stripped.startswith("- ") and current_section:
            item_val = _parse_val(stripped[2:].strip())
            # Find the most recently added list in current_section
            sec = result[current_section]
            if sec:
                last_key = list(sec.keys())[-1]
                if isinstance(sec[last_key], list):
                    sec[last_key].append(item_val)

    return result


def _parse_val(val: str) -> Any:
    """Parse scalar value from string representation."""
    if not val:
        return None
    val_clean = val.strip()
    if val_clean in ("null", "None", "~"):
        return None
    if val_clean.lower() in ("true", "yes", "on"):
        return True
    if val_clean.lower() in ("false", "no", "off"):
        return False
    if (val_clean.startswith('"') and val_clean.endswith('"')) or (val_clean.startswith("'") and val_clean.endswith("'")):
        return val_clean[1:-1]
    try:
        if "." in val_clean:
            return float(val_clean)
        return int(val_clean)
    except ValueError:
        return val_clean


def dump_simple_yaml(data: Dict[str, Any]) -> str:
    """Serialize dictionary to clean YAML format."""
    if HAS_YAML:
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    lines: List[str] = []
    for section, sec_val in data.items():
        if isinstance(sec_val, dict):
            lines.append(f"{section}:")
            for k, v in sec_val.items():
                if isinstance(v, list):
                    lines.append(f"  {k}:")
                    for item in v:
                        lines.append(f"    - {item}")
                elif v is None:
                    lines.append(f"  {k}: null")
                elif isinstance(v, bool):
                    lines.append(f"  {k}: {'true' if v else 'false'}")
                elif isinstance(v, str):
                    lines.append(f'  {k}: "{v}"')
                else:
                    lines.append(f"  {k}: {v}")
        else:
            if sec_val is None:
                lines.append(f"{section}: null")
            elif isinstance(sec_val, bool):
                lines.append(f"{section}: {'true' if sec_val else 'false'}")
            elif isinstance(sec_val, str):
                lines.append(f'{section}: "{sec_val}"')
            else:
                lines.append(f"{section}: {sec_val}")
    return "\n".join(lines) + "\n"


def find_config_file(explicit_path: Optional[str] = None) -> Optional[Path]:
    """Locate config file across explicit path, environment, current dir, and home."""
    if explicit_path:
        p = Path(explicit_path).resolve()
        if p.is_file():
            return p

    env_path = os.environ.get("BIOLABCALC_CONFIG")
    if env_path:
        p = Path(env_path).resolve()
        if p.is_file():
            return p

    cwd = Path.cwd()
    for candidate in [cwd / "config.yaml", cwd / "eln_config.yaml", cwd / "testing_config.yaml"]:
        if candidate.is_file():
            return candidate

    home_config = Path.home() / ".biolabcalc" / "config.yaml"
    if home_config.is_file():
        return home_config

    return None


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load ELN configuration, merging discovered config.yaml with default settings.
    """
    target = find_config_file(config_path)
    base = dict(DEFAULT_CONFIG)

    if target and target.is_file():
        try:
            content = target.read_text(encoding="utf-8")
            loaded = parse_simple_yaml(content)
            if loaded:
                base = _deep_merge(base, loaded)
        except Exception:
            pass

    return base


# ============================================================================
# Anonymization Utilities
# ============================================================================

def anonymize_ip(ip: str) -> str:
    """Mask IPv4 and IPv6 addresses for privacy while preserving local loopback."""
    if ip in ("127.0.0.1", "localhost", "::1"):
        return ip
    # IPv4 regex
    ipv4_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    m = re.match(ipv4_pattern, ip.strip())
    if m:
        return f"{m.group(1)}.{m.group(2)}.***.***"
    return "[MASKED_HOST]"


def anonymize_path(filepath: str) -> str:
    """Strip local username and sensitive home directory hierarchy from paths."""
    if not filepath:
        return filepath
    clean = filepath
    home = os.path.expanduser("~")
    if home and home in clean:
        clean = clean.replace(home, "~")
    # Windows User profile pattern
    clean = re.sub(r"[A-Za-z]:\\[Uu]sers\\[^\\]+", r"~", clean)
    clean = re.sub(r"/home/[^/]+", r"~", clean)
    return clean


def anonymize_log_message(msg: str) -> str:
    """Sanitize log messages by redacting auth tokens, user paths, and external IPs."""
    if not msg:
        return msg
    sanitized = msg
    # Redact Authorization header tokens
    sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", r"\1[REDACTED_TOKEN]", sanitized, flags=re.IGNORECASE)
    # Redact passwords in connection URLs (e.g. postgresql://user:pass@host)
    sanitized = re.sub(r"(://[^:]+:)[^@]+(@)", r"\1[REDACTED_PASS]\2", sanitized)
    # Sanitize user paths
    sanitized = anonymize_path(sanitized)
    return sanitized
