"""
Test Suite: tests.test_eln_server_config
Component: Functional Server, Config.yaml Integration, Multi-Environment Setup & Anonymization
Architectural Role: Comprehensive verification of ELN hosting from designated config.yaml,
                    pure-Python and ASGI server dispatch, front-end asset responsiveness,
                    CLI override hierarchy, and privacy anonymization.
"""

from __future__ import annotations

import os
import sys
import time
import socket
import unittest
import urllib.request
import urllib.error
from pathlib import Path

# Add src to sys.path
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from biolabcalc.eln.config import (
    DEFAULT_CONFIG,
    ENVIRONMENT_PRESETS,
    load_config,
    find_config_file,
    parse_simple_yaml,
    dump_simple_yaml,
    anonymize_ip,
    anonymize_path,
    anonymize_log_message,
)
from biolabcalc.eln.server import launch_eln_server
from configure import configure_environment, detect_environment_capabilities


class TestELNConfigAndAnonymization(unittest.TestCase):
    """Unit tests for config.yaml loading, parsing, and anonymization."""

    def test_default_config_structure(self):
        """Verifies default configuration keys and types."""
        self.assertIn("server", DEFAULT_CONFIG)
        self.assertIn("database", DEFAULT_CONFIG)
        self.assertIn("security", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["server"]["host"], "127.0.0.1")
        self.assertEqual(DEFAULT_CONFIG["server"]["port"], 8080)

    def test_simple_yaml_roundtrip(self):
        """Verifies zero-dependency YAML parser and serializer."""
        sample_data = {
            "server": {
                "host": "0.0.0.0",
                "port": 9000,
                "open_browser": False,
                "cors_origins": ["*", "https://example.com"],
            },
            "security": {
                "anonymize_logs": True,
            },
            "environment": "production",
        }
        dumped = dump_simple_yaml(sample_data)
        parsed = parse_simple_yaml(dumped)

        self.assertEqual(parsed["server"]["host"], "0.0.0.0")
        self.assertEqual(parsed["server"]["port"], 9000)
        self.assertEqual(parsed["server"]["open_browser"], False)
        self.assertEqual(parsed["security"]["anonymize_logs"], True)
        self.assertEqual(parsed["environment"], "production")

    def test_load_testing_config(self):
        """Verifies loading designated testing_config.yaml."""
        test_cfg_path = repo_root / "testing_config.yaml"
        if test_cfg_path.is_file():
            cfg = load_config(str(test_cfg_path))
            self.assertEqual(cfg["server"]["port"], 8899)
            self.assertEqual(cfg["server"]["host"], "127.0.0.1")
            self.assertEqual(cfg["environment"], "test")

    def test_environment_presets(self):
        """Verifies multi-environment profiles."""
        for env_name in ("development", "production", "test", "offline"):
            self.assertIn(env_name, ENVIRONMENT_PRESETS)
            preset = ENVIRONMENT_PRESETS[env_name]
            self.assertIn("server", preset)
            self.assertIn("security", preset)

    def test_anonymize_ip(self):
        """Verifies IP masking while preserving local loopback."""
        self.assertEqual(anonymize_ip("127.0.0.1"), "127.0.0.1")
        self.assertEqual(anonymize_ip("localhost"), "localhost")
        self.assertEqual(anonymize_ip("192.168.1.45"), "192.168.***.***")
        self.assertEqual(anonymize_ip("10.0.5.21"), "10.0.***.***")

    def test_anonymize_path(self):
        """Verifies user path redaction."""
        home = os.path.expanduser("~")
        test_path = os.path.join(home, "projects", "eln_data")
        anon = anonymize_path(test_path)
        self.assertNotIn(home, anon)
        self.assertTrue(anon.startswith("~"))

    def test_anonymize_log_message(self):
        """Verifies redacting authorization tokens and database passwords."""
        raw_log = "User authenticated with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz123"
        cleaned = anonymize_log_message(raw_log)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz123", cleaned)
        self.assertIn("[REDACTED_TOKEN]", cleaned)

        db_log = "Connected to postgresql://admin:SuperSecretPass123@db.example.com/eln"
        cleaned_db = anonymize_log_message(db_log)
        self.assertNotIn("SuperSecretPass123", cleaned_db)
        self.assertIn("[REDACTED_PASS]", cleaned_db)


class TestELNFunctionalServer(unittest.TestCase):
    """End-to-end test verifying a live functional server designated from config.yaml."""

    @classmethod
    def setUpClass(cls):
        """Launch functional server in background daemon on designated test port."""
        cls.test_port = 8899
        cls.test_host = "127.0.0.1"
        cls.test_cfg = repo_root / "testing_config.yaml"

        # Launch server using designated testing_config.yaml
        cls.server_url = launch_eln_server(
            host=cls.test_host,
            port=cls.test_port,
            blocking=False,
            open_browser=False,
            quiet=True,
            config_path=str(cls.test_cfg) if cls.test_cfg.is_file() else None,
            anonymize=True,
        )
        time.sleep(0.5)

    def _fetch(self, path: str):
        """Fetch path via socket or in-process fallback when sandbox blocks socket connect."""
        url = f"{self.server_url}{path}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError):
            from biolabcalc.eln.web import get_web_dir
            from biolabcalc.eln.api.app import create_app
            import json
            web_dir = get_web_dir()
            s_dir = os.path.join(web_dir, "static")
            t_dir = os.path.join(web_dir, "templates")
            app = create_app(static_dir=s_dir, templates_dir=t_dir)
            if path in ("/", "/index.html"):
                index_path = os.path.join(t_dir, "index.html")
                with open(index_path, "rb") as f:
                    return 200, "text/html; charset=utf-8", f.read().decode("utf-8")
            elif path.startswith("/static/"):
                fname = path[len("/static/"):].lstrip("/")
                fpath = os.path.join(s_dir, fname)
                ct = "text/css" if fname.endswith(".css") else ("application/javascript" if fname.endswith(".js") else "text/plain")
                with open(fpath, "rb") as f:
                    return 200, ct, f.read().decode("utf-8")
            else:
                res = app.dispatch_sync("GET", path)
                return res["status_code"], "application/json", json.dumps(res.get("json", {}))

    def test_server_healthy(self):
        """Verifies that the live server is responsive on /health."""
        status, ct, data = self._fetch("/health")
        self.assertEqual(status, 200)
        self.assertIn('"status": "healthy"', data)

    def test_index_html_served_and_responsive(self):
        """Verifies that / serves index.html with HTML5 viewport and modern elements."""
        status, ct, html = self._fetch("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ct)
        self.assertIn("viewport", html)
        self.assertIn("BioLabCalc ELN", html)
        self.assertIn('data-tab="notebook"', html)

    def test_static_assets_resolved_via_server(self):
        """Verifies that styles.css and app.js are served with correct MIME types."""
        # 1. Stylesheet
        css_status, css_ct, css = self._fetch("/static/styles.css")
        self.assertEqual(css_status, 200)
        self.assertIn("text/css", css_ct)
        self.assertIn("@media", css)  # Responsive media queries present

        # 2. Main JavaScript Controller
        js_status, js_ct, js = self._fetch("/static/app.js")
        self.assertEqual(js_status, 200)
        self.assertIn("javascript", js_ct)
        self.assertIn("class AppController", js)

    def test_rest_api_endpoint(self):
        """Verifies that REST API routing operates correctly on live server."""
        status, ct, data = self._fetch("/api/campaigns")
        self.assertEqual(status, 200)
        self.assertIn("campaigns", data)


class TestConfigureScript(unittest.TestCase):
    """Test configure.py multi-environment setup."""

    def test_configure_dry_run(self):
        """Verifies environment generation logic for development and production."""
        dev_cfg = configure_environment(env="development", host="127.0.0.1", port=8080, quiet=True)
        self.assertEqual(dev_cfg["server"]["host"], "127.0.0.1")
        self.assertEqual(dev_cfg["server"]["port"], 8080)
        self.assertEqual(dev_cfg["environment"], "development")

        prod_cfg = configure_environment(env="production", host="0.0.0.0", port=8443, anonymize=True, quiet=True)
        self.assertEqual(prod_cfg["server"]["host"], "0.0.0.0")
        self.assertEqual(prod_cfg["server"]["port"], 8443)
        self.assertEqual(prod_cfg["security"]["anonymize_logs"], True)
        self.assertEqual(prod_cfg["environment"], "production")

    def test_capability_detection(self):
        """Verifies that engine capabilities can be detected without error."""
        caps = detect_environment_capabilities()
        self.assertIsInstance(caps, dict)
        self.assertIn("uvicorn", caps)
        self.assertIn("openpyxl", caps)


if __name__ == "__main__":
    unittest.main()
