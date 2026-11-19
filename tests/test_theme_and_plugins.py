"""
Unit tests for BioLabCalc Minimalist CSS Theme System and Plugin Loader.
Verifies ThemeConfig immutability, presets, atomic file persistence,
zero-dependency plugin discovery, and ELN REST theme endpoints.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from biolabcalc.plugins import (
    PluginRecord,
    STANDARD_PLUGIN_GROUPS,
    discover_plugins,
    get_plugins_dir,
    load_plugin_module,
)
from biolabcalc.theme import (
    BUILTIN_THEMES,
    ThemeConfig,
    get_theme,
    list_themes,
    load_active_theme,
    save_active_theme,
    to_css_variables,
)


class TestThemeConfigAndEngine(unittest.TestCase):
    """Test ThemeConfig dataclass, presets, CSS generation, and atomic persistence."""

    def test_builtin_presets_exist(self) -> None:
        themes = list_themes()
        self.assertIn("minimal-light", themes)
        self.assertIn("minimal-slate", themes)
        self.assertIn("bench-paper", themes)
        self.assertIn("colorblind-safe", themes)

        for name in themes:
            theme = BUILTIN_THEMES[name]
            self.assertEqual(theme.name, name)
            self.assertTrue(theme.accent_hex.startswith("#"))
            self.assertTrue(theme.bg_hex.startswith("#"))
            self.assertTrue(theme.surface_hex.startswith("#"))
            self.assertTrue(theme.ink_hex.startswith("#"))
            self.assertTrue(theme.hairline_hex.startswith("#"))

    def test_theme_immutability(self) -> None:
        theme = BUILTIN_THEMES["minimal-light"]
        with self.assertRaises((AttributeError, TypeError)):
            theme.accent_hex = "#FF0000"  # type: ignore

    def test_hex_normalization_and_font_scale(self) -> None:
        cfg = ThemeConfig(
            name="custom",
            accent_hex="2563eb",
            bg_hex="#fff",  # invalid 3-digit falls back to default
            surface_hex="#f8fafc",
            ink_hex="#0f172a",
            ink_muted_hex="#64748b",
            hairline_hex="#e2e8f0",
            font_scale=1.2,
        )
        self.assertEqual(cfg.accent_hex, "#2563EB")
        self.assertEqual(cfg.surface_hex, "#F8FAFC")
        self.assertEqual(cfg.font_scale, 1.2)

    def test_get_theme_override(self) -> None:
        custom = get_theme("minimal-light", custom_accent="#E11D48", font_scale=1.1)
        self.assertEqual(custom.name, "minimal-light")
        self.assertEqual(custom.accent_hex, "#E11D48")
        self.assertEqual(custom.font_scale, 1.1)

        # Fallback on unknown
        fallback = get_theme("non_existent_preset")
        self.assertEqual(fallback.name, "minimal-light")

    def test_to_css_variables(self) -> None:
        theme = BUILTIN_THEMES["minimal-slate"]
        css = to_css_variables(theme)
        self.assertIn(":root {", css)
        self.assertIn(f"--bg: {theme.bg_hex};", css)
        self.assertIn(f"--accent: {theme.accent_hex};", css)
        self.assertIn(f"--surface: {theme.surface_hex};", css)
        self.assertIn(f"--hairline: {theme.hairline_hex};", css)

    def test_atomic_theme_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_home = os.environ.get("BIOLABCALC_HOME")
            try:
                os.environ["BIOLABCALC_HOME"] = tmp_dir
                saved_path = save_active_theme("bench-paper", custom_accent="#059669")
                self.assertTrue(saved_path.is_file())

                loaded = load_active_theme()
                self.assertEqual(loaded.name, "bench-paper")
                self.assertEqual(loaded.accent_hex, "#059669")

                # Verify raw JSON format
                data = json.loads(saved_path.read_text(encoding="utf-8"))
                self.assertEqual(data["theme"], "bench-paper")
                self.assertEqual(data["accent_hex"], "#059669")
            finally:
                if old_home is not None:
                    os.environ["BIOLABCALC_HOME"] = old_home
                else:
                    os.environ.pop("BIOLABCALC_HOME", None)


class TestPluginDiscovery(unittest.TestCase):
    """Test zero-dependency plugin discovery and local plugin loading."""

    def test_standard_groups(self) -> None:
        self.assertIn("biolabcalc.plugins", STANDARD_PLUGIN_GROUPS)
        self.assertIn("biolabcalc.backbones", STANDARD_PLUGIN_GROUPS)
        self.assertIn("biolabcalc.enzymes", STANDARD_PLUGIN_GROUPS)

    def test_discover_plugins_safe_execution(self) -> None:
        # Should not raise exception even with empty entry points
        plugins = discover_plugins("biolabcalc.plugins")
        self.assertIsInstance(plugins, tuple)

    def test_local_directory_plugin_discovery_and_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_home = os.environ.get("BIOLABCALC_HOME")
            try:
                os.environ["BIOLABCALC_HOME"] = tmp_dir
                plugins_dir = get_plugins_dir()

                # Create a sample local plugin
                plugin_file = plugins_dir / "custom_test_plugin.py"
                plugin_file.write_text(
                    "PLUGIN_NAME = 'test_plug'\ndef get_val(): return 42\n",
                    encoding="utf-8",
                )

                discovered = discover_plugins("biolabcalc.plugins")
                names = [p.name for p in discovered]
                self.assertIn("custom_test_plugin", names)

                target_record = next(p for p in discovered if p.name == "custom_test_plugin")
                self.assertEqual(target_record.source, "local_file")

                # Test loading the module
                mod = load_plugin_module(target_record)
                self.assertIsNotNone(mod)
                self.assertEqual(getattr(mod, "PLUGIN_NAME", None), "test_plug")
                self.assertEqual(mod.get_val(), 42)
            finally:
                if old_home is not None:
                    os.environ["BIOLABCALC_HOME"] = old_home
                else:
                    os.environ.pop("BIOLABCALC_HOME", None)


class TestElnThemeRestRoutes(unittest.TestCase):
    """Test ELN /api/theme REST routes."""

    def test_get_and_post_theme_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            old_home = os.environ.get("BIOLABCALC_HOME")
            try:
                os.environ["BIOLABCALC_HOME"] = tmp_dir

                from biolabcalc.eln.api.routes.theme import get_current_theme, update_theme

                initial = get_current_theme()
                self.assertEqual(initial["status"], "success")
                self.assertIn("active_theme", initial)

                update_res = update_theme({"theme": "minimal-slate", "accent_hex": "#38BDF8"})
                self.assertEqual(update_res["status"], "success")
                self.assertEqual(update_res["active_theme"]["name"], "minimal-slate")
                self.assertEqual(update_res["active_theme"]["accent_hex"], "#38BDF8")

                subsequent = get_current_theme()
                self.assertEqual(subsequent["active_theme"]["name"], "minimal-slate")
                self.assertEqual(subsequent["active_theme"]["accent_hex"], "#38BDF8")
            finally:
                if old_home is not None:
                    os.environ["BIOLABCALC_HOME"] = old_home
                else:
                    os.environ.pop("BIOLABCALC_HOME", None)


if __name__ == "__main__":
    unittest.main()
