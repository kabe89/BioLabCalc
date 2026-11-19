"""
Module: biolabcalc.theme
Component: Minimalist CSS Theme Engine & Color Customization
Architectural Role: Governs design tokens, color customization presets, WCAG AAA contrast,
and atomic theme persistence across the Electronic Lab Notebook (ELN), interactive gel/plasmid
visualizers, printable protocols, and reports.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from .profile import get_biolabcalc_home


_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _normalize_hex(hex_str: str, default: str = "#1D4ED8") -> str:
    """Validate and normalize a 6-digit hex color string."""
    if not hex_str or not isinstance(hex_str, str):
        return default
    s = hex_str.strip()
    if not s.startswith("#"):
        s = "#" + s
    if _HEX_RE.match(s):
        return s.upper()
    return default


@dataclass(frozen=True)
class ThemeConfig:
    """Immutable design token snapshot for BioLabCalc UI, visualizations, and printables."""

    name: str
    accent_hex: str
    bg_hex: str
    surface_hex: str
    ink_hex: str
    ink_muted_hex: str
    hairline_hex: str
    font_scale: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "accent_hex", _normalize_hex(self.accent_hex, "#1D4ED8"))
        object.__setattr__(self, "bg_hex", _normalize_hex(self.bg_hex, "#FFFFFF"))
        object.__setattr__(self, "surface_hex", _normalize_hex(self.surface_hex, "#F8FAFC"))
        object.__setattr__(self, "ink_hex", _normalize_hex(self.ink_hex, "#0F172A"))
        object.__setattr__(self, "ink_muted_hex", _normalize_hex(self.ink_muted_hex, "#64748B"))
        object.__setattr__(self, "hairline_hex", _normalize_hex(self.hairline_hex, "#E2E8F0"))
        try:
            scale = float(self.font_scale)
            if scale <= 0.2 or scale >= 5.0:
                scale = 1.0
        except (ValueError, TypeError):
            scale = 1.0
        object.__setattr__(self, "font_scale", scale)


BUILTIN_THEMES: Dict[str, ThemeConfig] = {
    "minimal-light": ThemeConfig(
        name="minimal-light",
        accent_hex="#1D4ED8",  # Cobalt accent
        bg_hex="#FFFFFF",      # Pure crisp white
        surface_hex="#F8FAFC", # Slate 50
        ink_hex="#0F172A",     # Slate 900 (WCAG AAA >= 7:1)
        ink_muted_hex="#64748B",
        hairline_hex="#E2E8F0", # 1px hairline border
        font_scale=1.0,
    ),
    "minimal-slate": ThemeConfig(
        name="minimal-slate",
        accent_hex="#38BDF8",  # Sky accent
        bg_hex="#0F172A",      # Slate 900 low-glare dark surface
        surface_hex="#1E293B", # Slate 800
        ink_hex="#F8FAFC",     # Slate 50 high contrast text
        ink_muted_hex="#94A3B8",
        hairline_hex="#334155",
        font_scale=1.0,
    ),
    "bench-paper": ThemeConfig(
        name="bench-paper",
        accent_hex="#166534",  # Forest bench accent
        bg_hex="#FAF9F6",      # Warm off-white paper
        surface_hex="#F3F0E6", # Lab parchment
        ink_hex="#1C1917",     # Stone 900
        ink_muted_hex="#78716C",
        hairline_hex="#E7E5E4",
        font_scale=1.0,
    ),
    "colorblind-safe": ThemeConfig(
        name="colorblind-safe",
        accent_hex="#D55E00",  # Okabe-Ito vermilion
        bg_hex="#FFFFFF",
        surface_hex="#F0F4F8",
        ink_hex="#111111",
        ink_muted_hex="#555555",
        hairline_hex="#D0D7DE",
        font_scale=1.0,
    ),
}


def list_themes() -> Tuple[str, ...]:
    """Return all available built-in theme preset identifiers."""
    return tuple(BUILTIN_THEMES.keys())


def get_theme(
    name: str = "minimal-light",
    custom_accent: Optional[str] = None,
    font_scale: float = 1.0,
) -> ThemeConfig:
    """
    Retrieve a ThemeConfig by name, optionally overriding the accent color and font scale.
    """
    preset = BUILTIN_THEMES.get(name) or BUILTIN_THEMES["minimal-light"]
    accent = _normalize_hex(custom_accent, preset.accent_hex) if custom_accent else preset.accent_hex

    return ThemeConfig(
        name=preset.name,
        accent_hex=accent,
        bg_hex=preset.bg_hex,
        surface_hex=preset.surface_hex,
        ink_hex=preset.ink_hex,
        ink_muted_hex=preset.ink_muted_hex,
        hairline_hex=preset.hairline_hex,
        font_scale=font_scale,
    )


def to_css_variables(theme: ThemeConfig) -> str:
    """
    Generate CSS custom property declarations (:root block) from a ThemeConfig.
    """
    return (
        ":root {\n"
        f"  --bg: {theme.bg_hex};\n"
        f"  --surface: {theme.surface_hex};\n"
        f"  --ink: {theme.ink_hex};\n"
        f"  --ink-muted: {theme.ink_muted_hex};\n"
        f"  --hairline: {theme.hairline_hex};\n"
        f"  --accent: {theme.accent_hex};\n"
        f"  --font-scale: {theme.font_scale:.2f};\n"
        "}"
    )


def get_theme_file_path() -> Path:
    """Return the canonical path to the user's theme.json configuration file."""
    return get_biolabcalc_home() / "theme.json"


def save_active_theme(
    theme: Union[ThemeConfig, str],
    custom_accent: Optional[str] = None,
    font_scale: float = 1.0,
) -> Path:
    """
    Persist the active user theme and custom accent atomically to BIOLABCALC_HOME/theme.json.
    """
    if isinstance(theme, str):
        cfg = get_theme(theme, custom_accent=custom_accent, font_scale=font_scale)
    else:
        if custom_accent:
            cfg = get_theme(theme.name, custom_accent=custom_accent, font_scale=font_scale)
        else:
            cfg = theme

    target_path = get_theme_file_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "theme": cfg.name,
        "accent_hex": cfg.accent_hex,
        "bg_hex": cfg.bg_hex,
        "surface_hex": cfg.surface_hex,
        "ink_hex": cfg.ink_hex,
        "ink_muted_hex": cfg.ink_muted_hex,
        "hairline_hex": cfg.hairline_hex,
        "font_scale": cfg.font_scale,
    }
    data = json.dumps(payload, indent=2)

    # Atomic write to sibling temp file
    temp_dir = str(target_path.parent)
    fd, temp_file_path = tempfile.mkstemp(dir=temp_dir, prefix=".theme_tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file_path, str(target_path))
    except Exception:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
        raise

    return target_path


def load_active_theme() -> ThemeConfig:
    """
    Load active user theme configuration with cascading resolution:
    1. BIOLABCALC_HOME/theme.json
    2. ui.theme & ui.accent_hex in config.yaml
    3. Fallback to minimal-light preset
    """
    theme_file = get_theme_file_path()
    if theme_file.is_file():
        try:
            content = theme_file.read_text(encoding="utf-8")
            data = json.loads(content)
            name = data.get("theme", "minimal-light")
            preset = BUILTIN_THEMES.get(name) or BUILTIN_THEMES["minimal-light"]
            accent = data.get("accent_hex") or preset.accent_hex
            scale = float(data.get("font_scale", 1.0))
            return ThemeConfig(
                name=name,
                accent_hex=accent,
                bg_hex=data.get("bg_hex", preset.bg_hex),
                surface_hex=data.get("surface_hex", preset.surface_hex),
                ink_hex=data.get("ink_hex", preset.ink_hex),
                ink_muted_hex=data.get("ink_muted_hex", preset.ink_muted_hex),
                hairline_hex=data.get("hairline_hex", preset.hairline_hex),
                font_scale=scale,
            )
        except Exception:
            pass

    # Fallback to config.yaml if present
    try:
        from .eln.config import find_config_file, load_config
        cfg_path = find_config_file()
        if cfg_path and cfg_path.is_file():
            cfg = load_config(str(cfg_path))
            ui_cfg = cfg.get("ui", {})
            name = ui_cfg.get("theme", "minimal-light")
            accent = ui_cfg.get("accent_hex")
            scale = float(ui_cfg.get("font_scale", 1.0))
            return get_theme(name, custom_accent=accent, font_scale=scale)
    except Exception:
        pass

    return BUILTIN_THEMES["minimal-light"]
