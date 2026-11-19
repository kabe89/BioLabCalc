"""
Module: biolabcalc.eln.api.routes.theme
Component: Theme & Color Customization REST Endpoints
Architectural Role: Exposes active theme configuration retrieval and atomic persistence
to BIOLABCALC_HOME/theme.json for the ELN web frontend.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ....theme import BUILTIN_THEMES, get_theme, list_themes, load_active_theme, save_active_theme
from ..router import Router

router = Router(prefix="/api/theme")


@router.get("")
def get_current_theme() -> Dict[str, Any]:
    """Retrieve the active user theme configuration and available presets."""
    active = load_active_theme()
    return {
        "status": "success",
        "active_theme": {
            "name": active.name,
            "accent_hex": active.accent_hex,
            "bg_hex": active.bg_hex,
            "surface_hex": active.surface_hex,
            "ink_hex": active.ink_hex,
            "ink_muted_hex": active.ink_muted_hex,
            "hairline_hex": active.hairline_hex,
            "font_scale": active.font_scale,
        },
        "available_presets": list_themes(),
    }


@router.post("")
def update_theme(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update and atomically persist the active theme and custom accent color."""
    theme_name = str(data.get("theme", "minimal-light"))
    custom_accent = data.get("accent_hex")
    if custom_accent is not None:
        custom_accent = str(custom_accent)
    font_scale = 1.0
    try:
        if "font_scale" in data:
            font_scale = float(data["font_scale"])
    except (ValueError, TypeError):
        font_scale = 1.0

    saved_path = save_active_theme(theme_name, custom_accent=custom_accent, font_scale=font_scale)
    updated = load_active_theme()

    return {
        "status": "success",
        "message": "Theme persisted successfully",
        "saved_path": str(saved_path),
        "active_theme": {
            "name": updated.name,
            "accent_hex": updated.accent_hex,
            "bg_hex": updated.bg_hex,
            "surface_hex": updated.surface_hex,
            "ink_hex": updated.ink_hex,
            "ink_muted_hex": updated.ink_muted_hex,
            "hairline_hex": updated.hairline_hex,
            "font_scale": updated.font_scale,
        },
    }
