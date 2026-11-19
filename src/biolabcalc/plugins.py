"""
Module: biolabcalc.plugins
Component: Zero-Dependency Plugin Discovery & Extension Registry
Architectural Role: Discovers and registers external lab plugins, custom backbones,
enzymes, themes, and protocols via importlib.metadata entry_points and local
BIOLABCALC_HOME/plugins/ directories.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .profile import get_biolabcalc_home

logger = logging.getLogger(__name__)

STANDARD_PLUGIN_GROUPS: Tuple[str, ...] = (
    "biolabcalc.plugins",
    "biolabcalc.backbones",
    "biolabcalc.enzymes",
    "biolabcalc.themes",
    "biolabcalc.protocols",
    "biolabcalc.eln_parsers",
)


@dataclass(frozen=True)
class PluginRecord:
    """Descriptor for a discovered or loaded BioLabCalc plugin extension."""

    name: str
    group: str
    source: str  # "entry_point" or "local_file"
    path_or_module: str
    loaded: bool
    description: str = ""
    error: Optional[str] = None


def get_plugins_dir() -> Path:
    """Return the user's local plugins directory in BIOLABCALC_HOME/plugins/."""
    p = get_biolabcalc_home() / "plugins"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get_entry_points(group: str) -> List[Any]:
    """Retrieve entry points safely across Python 3.8 through 3.15."""
    try:
        from importlib.metadata import entry_points
    except ImportError:
        return []

    try:
        eps = entry_points(group=group)
        return list(eps)
    except TypeError:
        # Fallback for Python 3.8 and 3.9 dict-returning interface
        try:
            all_eps = entry_points()
            if isinstance(all_eps, dict):
                return list(all_eps.get(group, []))
            return [ep for ep in all_eps if getattr(ep, "group", None) == group]
        except Exception:
            return []
    except Exception:
        return []


def discover_plugins(group: str = "biolabcalc.plugins") -> Tuple[PluginRecord, ...]:
    """
    Discover all installed plugins from python entry points and the local plugins directory.
    """
    records: List[PluginRecord] = []
    seen_names = set()

    # 1. Discover via entry points
    for ep in _get_entry_points(group):
        ep_name = getattr(ep, "name", str(ep))
        ep_val = getattr(ep, "value", "")
        seen_names.add(ep_name)
        records.append(
            PluginRecord(
                name=ep_name,
                group=group,
                source="entry_point",
                path_or_module=ep_val,
                loaded=False,
                description=f"Entry point {group}:{ep_name}",
            )
        )

    # 2. Discover via local directory BIOLABCALC_HOME/plugins/
    plugins_dir = get_plugins_dir()
    if plugins_dir.is_dir():
        for item in sorted(plugins_dir.iterdir()):
            if item.name.startswith((".", "_")):
                continue
            if item.suffix == ".py":
                plugin_name = item.stem
                if plugin_name not in seen_names:
                    seen_names.add(plugin_name)
                    records.append(
                        PluginRecord(
                            name=plugin_name,
                            group=group,
                            source="local_file",
                            path_or_module=str(item.resolve()),
                            loaded=False,
                            description=f"Local Python plugin: {item.name}",
                        )
                    )
            elif item.is_dir() and (item / "plugin.json").is_file():
                plugin_name = item.name
                manifest_path = item / "plugin.json"
                desc = "Local directory plugin"
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    desc = data.get("description", desc)
                except Exception:
                    pass
                if plugin_name not in seen_names:
                    seen_names.add(plugin_name)
                    records.append(
                        PluginRecord(
                            name=plugin_name,
                            group=group,
                            source="local_file",
                            path_or_module=str(manifest_path.resolve()),
                            loaded=False,
                            description=desc,
                        )
                    )

    return tuple(records)


def load_plugin_module(record: PluginRecord) -> Optional[Any]:
    """
    Load and execute a plugin module from an entry point or local .py file.
    """
    if record.source == "entry_point":
        try:
            for ep in _get_entry_points(record.group):
                if getattr(ep, "name", None) == record.name:
                    return ep.load()
        except Exception as e:
            logger.warning("Failed to load entry point plugin %s: %s", record.name, e)
            return None

    elif record.source == "local_file" and record.path_or_module.endswith(".py"):
        p = Path(record.path_or_module)
        if not p.is_file():
            return None
        try:
            module_name = f"biolabcalc_plugin_{record.name}"
            spec = importlib.util.spec_from_file_location(module_name, str(p))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)
                return mod
        except Exception as e:
            logger.warning("Failed to load local plugin %s: %s", record.name, e)
            return None

    return None
