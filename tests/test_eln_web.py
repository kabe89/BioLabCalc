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
        src_path = cls.repo_root / "src"
        import sys
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        try:
            from biolabcalc.eln.web import get_web_dir
            cls.web_dir = Path(get_web_dir())
        except Exception:
            cls.web_dir = src_path / "biolabcalc" / "eln" / "web"
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

    def test_xss_sanitization_patterns_in_frontend(self):
        """Verifies that user inputs and messages are handled via safe DOM properties."""
        app_js = (self.static_dir / "app.js").read_text(encoding="utf-8")
        self.assertIn("_escapeHtml", app_js, "app.js missing _escapeHtml sanitizer")
        self.assertIn("rag-no-results-query", app_js)
        self.assertIn("span.textContent = message", app_js)

        timer_js = (self.static_dir / "timer_widget.js").read_text(encoding="utf-8")
        self.assertIn("badgeEl.textContent = this.options.stepName", timer_js)

    def test_qol_ergonomics_in_frontend(self):
        """Verifies QoL improvements: tab persistence, hotkeys, table exports, preset chips."""
        app_js = (self.static_dir / "app.js").read_text(encoding="utf-8")
        html = (self.templates_dir / "index.html").read_text(encoding="utf-8")

        # Tab persistence
        self.assertIn("localStorage.setItem('eln_active_tab'", app_js)
        self.assertIn("localStorage.getItem('eln_active_tab'", app_js)

        # Global hotkeys & modal closing
        self.assertIn("closeAllModals()", app_js)
        self.assertIn("e.key === 'Escape'", app_js)
        self.assertIn("e.key === '/'", app_js)

        # Table exports (CSV and Markdown)
        self.assertIn("exportTableToCsv", app_js)
        self.assertIn("exportTableToMarkdown", app_js)
        self.assertIn("btn-export-timepoints-md", html)

        # Quick-fill preset chips
        self.assertIn("preset-chip", app_js)
        self.assertIn("preset-chip", html)
        self.assertIn("T7 20 µL IVT", html)

        # Sequence workspace transformation and export controls
        self.assertIn("btn-seq-rc", html)
        self.assertIn("btn-seq-rc", app_js)
        self.assertIn("btn-seq-translate", html)
        self.assertIn("btn-seq-translate", app_js)
        self.assertIn("btn-seq-copy", html)
        self.assertIn("btn-seq-copy", app_js)

        # Notebook note download control
        self.assertIn("btn-download-note", html)
        self.assertIn("btn-download-note", app_js)

        # Freezer LIMS sample search filter
        self.assertIn("freezer-sample-search", html)
        self.assertIn("freezer-sample-search", app_js)

    def test_cross_section_routing_elements(self):
        """Verifies cross-section reactive routing buttons in index.html and handlers in app.js."""
        html_file = self.templates_dir / "index.html"
        html = html_file.read_text(encoding="utf-8")

        required_buttons = [
            "btn-seq-send-gel",
            "btn-seq-send-nanodrop",
            "btn-seq-append-notebook",
            "btn-seq-store-freezer",
            "btn-gel-log-notebook",
            "btn-nanodrop-log-notebook",
            "btn-nanodrop-sync-freezer",
            "btn-timers-log-notebook",
            "btn-finalize-ocr",
        ]
        for btn_id in required_buttons:
            self.assertIn(btn_id, html, f"Missing required button ID in index.html: {btn_id}")

        app_js = (self.static_dir / "app.js").read_text(encoding="utf-8")
        required_methods = [
            "_initEventListeners",
            "_sendSequenceToGel",
            "_sendSequenceToNanoDrop",
            "_sendSequenceToNotebook",
            "_sendSequenceToFreezer",
            "_logGelBandToNotebook",
            "_logNanoDropToNotebook",
            "_syncNanoDropToFreezer",
            "_logTimepointsToNotebook",
            "_finalizeOcrToNotebook",
        ]
        for method_name in required_methods:
            self.assertIn(method_name, app_js, f"Missing required method in app.js: {method_name}")

        for btn_id in required_buttons:
            self.assertIn(btn_id, app_js, f"Missing event listener binding for {btn_id} in app.js")

    def test_get_web_dir_and_asset_loaders(self):
        """Verifies get_web_dir, get_template_path, and get_static_path resolution."""
        from biolabcalc.eln.web import get_web_dir, get_template_path, get_static_path, get_templates_dir, get_static_dir
        web_dir = get_web_dir()
        self.assertTrue(os.path.isdir(web_dir), f"Resolved web_dir does not exist: {web_dir}")
        self.assertTrue(os.path.isdir(get_templates_dir()))
        self.assertTrue(os.path.isdir(get_static_dir()))

        index_path = get_template_path("index.html")
        self.assertTrue(os.path.isfile(index_path), f"index.html not found: {index_path}")

        styles_path = get_static_path("styles.css")
        self.assertTrue(os.path.isfile(styles_path), f"styles.css not found: {styles_path}")


if __name__ == "__main__":
    unittest.main()
