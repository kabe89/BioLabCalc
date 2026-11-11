"""
Test Suite: biolabcalc.eln.web
Component: Phase 4 ELN & Multi-Modal LIMS Frontend Web Application
Architectural Role: Automated verification of HTML5 SPA templates, CSS stylesheets,
                    and interactive scientific canvas ES6 modules.
"""

import os
import unittest
from pathlib import Path


class TestElnWebFrontend(unittest.TestCase):
    """
    Verification tests for ELN Phase 4 frontend assets.
    @role Unit and Integration Test Case
    """

    @classmethod
    def setUpClass(cls):
        """Locates repository root and web static/templates directories."""
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.web_dir = cls.repo_root / "src" / "biolabcalc" / "eln" / "web"
        cls.templates_dir = cls.web_dir / "templates"
        cls.static_dir = cls.web_dir / "static"

    def test_file_structure_exists(self):
        """Verifies that all 9 required files exist on disk."""
        expected_files = [
            self.templates_dir / "index.html",
            self.static_dir / "styles.css",
            self.static_dir / "fplc_viewer.js",
            self.static_dir / "gel_canvas.js",
            self.static_dir / "spectrum_viewer.js",
            self.static_dir / "freezer_grid.js",
            self.static_dir / "timer_widget.js",
            self.static_dir / "ocr_corrector.js",
            self.static_dir / "app.js",
        ]
        for f in expected_files:
            self.assertTrue(f.exists(), f"Expected file does not exist: {f}")
            self.assertGreater(f.stat().st_size, 500, f"File is unexpectedly small: {f}")

    def test_index_html_tabs_and_elements(self):
        """Verifies that index.html contains all 8 required tabs and key UI components."""
        html_file = self.templates_dir / "index.html"
        html = html_file.read_text(encoding="utf-8")

        # 8 Navigation Tabs
        required_tabs = [
            'data-tab="notebook"',
            'data-tab="timers"',
            'data-tab="fplc"',
            'data-tab="gel"',
            'data-tab="nanodrop"',
            'data-tab="freezer"',
            'data-tab="ocr"',
            'data-tab="sequences"',
        ]
        for tab in required_tabs:
            self.assertIn(tab, html, f"Missing required navigation tab: {tab}")

        # Top Header Elements
        self.assertIn("campaign-select", html)
        self.assertIn("CAMP-2026-T7RNAP", html)
        self.assertIn("search-trigger-btn", html)
        self.assertIn("rag-search-modal", html)
        self.assertIn("theme-toggle-btn", html)
        self.assertIn("user-role-badge", html)
        self.assertIn("ws-status-badge", html)

        # Modals and Drawers
        self.assertIn("pool-fractions-modal", html)
        self.assertIn("tube-lineage-drawer", html)

    def test_styles_css_themes_and_classes(self):
        """Verifies CSS variables, light/dark themes, and component styles."""
        css_file = self.static_dir / "styles.css"
        css = css_file.read_text(encoding="utf-8")

        # Color system variables
        self.assertIn("--primary:", css)
        self.assertIn("--fplc-uv280:", css)
        self.assertIn("--fplc-cond:", css)
        self.assertIn("--fplc-grad:", css)
        self.assertIn("--gel-stain:", css)
        self.assertIn("--pass:", css)
        self.assertIn("--flag:", css)
        self.assertIn("--fail:", css)
        self.assertIn('[data-theme="dark"]', css)

        # Scientific canvas component selectors
        self.assertIn(".box-grid-9x9", css)
        self.assertIn(".box-grid-10x10", css)
        self.assertIn(".tube-drawer", css)
        self.assertIn(".uncertain-tag-pill", css)
        self.assertIn(".ocr-interactive-popover", css)

    def test_javascript_classes_exported(self):
        """Verifies that all interactive canvas classes are properly exported."""
        modules = [
            ("fplc_viewer.js", "class FPLCViewer"),
            ("gel_canvas.js", "class GelCanvasViewer"),
            ("spectrum_viewer.js", "class SpectrumViewer"),
            ("freezer_grid.js", "class FreezerGrid"),
            ("timer_widget.js", "class TimerWidget"),
            ("ocr_corrector.js", "class OCRCorrector"),
            ("app.js", "class AppController"),
        ]
        for filename, class_signature in modules:
            js_file = self.static_dir / filename
            content = js_file.read_text(encoding="utf-8")
            self.assertIn(
                class_signature,
                content,
                f"Missing {class_signature} in {filename}"
            )


if __name__ == "__main__":
    unittest.main()
