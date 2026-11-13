"""
Test Suite: tests.test_setup_wizard
Component: First-Run Portable Setup Wizard & Shared Lab Package Verification
Architectural Role: Comprehensive automated verification of network path detection
(UNC, drive letters, POSIX mounts), filesystem permission and SQLite locking validation,
database schema initialization, tailored config.yaml generation, and zero-install
portable packaging structure validation.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Bootstrap sys.path for standalone execution
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from biolabcalc.eln.config import load_config, parse_simple_yaml
from biolabcalc.setup_wizard import (
    detect_path_type,
    generate_tailored_config,
    init_shared_database,
    run_setup_wizard,
    validate_shared_path_permissions,
)
from package_portable import (
    create_portable_package,
    validate_portable_distribution,
)


class TestNetworkPathDetection(unittest.TestCase):
    """Test suite verifying classification of UNC, mapped drive, POSIX mount, and local paths."""

    def test_unc_path_detection_windows(self):
        """Verify Windows UNC backslash network share detection."""
        path = r"\\fileserver01\wetlab_data\lims_db"
        info = detect_path_type(path)
        self.assertTrue(info["is_network"])
        self.assertEqual(info["path_type"], "unc")
        self.assertEqual(info["server"], "fileserver01")
        self.assertEqual(info["share"], "wetlab_data")
        self.assertIn("UNC", info["details"])

    def test_unc_path_detection_forward_slashes(self):
        """Verify UNC forward-slash network share detection."""
        path = "//nas.med.university.edu/genomics/shared"
        info = detect_path_type(path)
        self.assertTrue(info["is_network"])
        self.assertEqual(info["path_type"], "unc")
        self.assertEqual(info["server"], "nas.med.university.edu")
        self.assertEqual(info["share"], "genomics")

    def test_mapped_network_drive_detection(self):
        """Verify academic wet-lab mapped network drive letters (Z:, Y:, X:, etc.)."""
        for letter in ["Z:", "Y:", "X:", "W:", "V:", "U:", "S:", "R:", "P:", "N:"]:
            path = f"{letter}\\LabSharedData\\eln"
            info = detect_path_type(path)
            self.assertTrue(info["is_network"], f"Failed for drive letter {letter}")
            self.assertEqual(info["path_type"], "mapped_drive")
            self.assertEqual(info["drive_letter"], letter)

    def test_local_drive_detection(self):
        """Verify standard local drive letter detection."""
        path = r"C:\Users\BenchResearcher\Documents"
        info = detect_path_type(path)
        self.assertEqual(info["drive_letter"], "C:")
        self.assertEqual(info["path_type"], "drive_letter")
        self.assertFalse(info["is_network"])

    def test_posix_network_mount_detection(self):
        """Verify Linux/macOS network mounts (/mnt/..., /media/..., /Volumes/...)."""
        posix_mounts = [
            "/mnt/labshare/biolabdata",
            "/media/bench_usb/eln_data",
            "/Volumes/WetLabShare/protocols",
            "/net/storage.cluster/lab",
            "/share/department/biocalc",
            "/nfs/shared/notebooks",
        ]
        for mount in posix_mounts:
            info = detect_path_type(mount)
            self.assertTrue(info["is_network"], f"Failed for POSIX mount {mount}")
            self.assertEqual(info["path_type"], "posix_mount")
            self.assertIn("POSIX", info["details"])

    def test_local_relative_and_empty_paths(self):
        """Verify relative local workspace directories."""
        info = detect_path_type("./.biolabcalc_data")
        self.assertFalse(info["is_network"])
        self.assertEqual(info["path_type"], "local")

        info_empty = detect_path_type("")
        self.assertFalse(info_empty["is_network"])
        self.assertEqual(info_empty["path_type"], "local")


class TestPermissionValidation(unittest.TestCase):
    """Test suite validating file creation, readback, deletion, and SQLite locking."""

    def test_permission_validation_success(self):
        """Verify comprehensive permission probe on a writable temporary directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            res = validate_shared_path_permissions(tmp_dir)
            self.assertTrue(res["valid"])
            self.assertTrue(res["writable"])
            self.assertTrue(res["readable"])
            self.assertTrue(res["deletable"])
            self.assertTrue(res["sqlite_lock_ok"])
            self.assertIsNone(res["error"])

    def test_permission_validation_nested_directory_creation(self):
        """Verify automatic creation of nested target path if not yet present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            nested = os.path.join(tmp_dir, "level1", "level2", "lab_data")
            self.assertFalse(os.path.exists(nested))

            res = validate_shared_path_permissions(nested)
            self.assertTrue(res["valid"])
            self.assertTrue(os.path.exists(nested))

    def test_permission_validation_empty_path(self):
        """Verify rejection of empty target path."""
        res = validate_shared_path_permissions("")
        self.assertFalse(res["valid"])
        self.assertIsNotNone(res["error"])

    def test_permission_validation_simulated_write_failure(self):
        """Verify graceful error reporting when file writing raises PermissionError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("builtins.open", side_effect=PermissionError("Simulated write lock")):
                res = validate_shared_path_permissions(tmp_dir)
                self.assertFalse(res["valid"])
                self.assertFalse(res["writable"])
                self.assertIn("Write permission denied", res["error"])

    def test_permission_validation_simulated_sqlite_lock_failure(self):
        """Verify detection when SQLite database locking fails on network mount."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("sqlite3.connect", side_effect=sqlite3.OperationalError("database is locked")):
                res = validate_shared_path_permissions(tmp_dir)
                self.assertFalse(res["valid"])
                self.assertFalse(res["sqlite_lock_ok"])
                self.assertIn("SQLite locking error", res["error"])


class TestDatabaseInitialization(unittest.TestCase):
    """Test suite verifying schema table initialization on designated shared directory."""

    def test_init_shared_database_tables_created(self):
        """Verify database file creation and full ELN/LIMS table initialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_info = init_shared_database(tmp_dir)

            self.assertTrue(db_info["initialized"])
            self.assertTrue(db_info["verified"])
            self.assertTrue(os.path.isfile(db_info["db_path"]))
            self.assertGreaterEqual(db_info["table_count"], 15)

            # Check core schema entities
            tables = set(db_info["tables_created"])
            expected_core_tables = {
                "users",
                "audit_logs",
                "storage_blobs",
                "sop_templates",
                "experimental_campaigns",
                "notebook_daily_entries",
                "notebook_timepoint_logs",
                "inventory_tubes",
            }
            self.assertTrue(
                expected_core_tables.issubset(tables),
                f"Missing expected core tables. Found: {tables}",
            )

            # Direct SQLite query to verify database is functional and readable
            conn = sqlite3.connect(db_info["db_path"])
            try:
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM users;")
                count = cur.fetchone()[0]
                self.assertEqual(count, 0)
            finally:
                conn.close()


class TestTailoredConfigGeneration(unittest.TestCase):
    """Test suite verifying tailored configuration generation across deployment roles."""

    def test_generate_client_role_config(self):
        """Verify benchtop client configuration settings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "config.yaml")
            cfg = generate_tailored_config(
                shared_dir=tmp_dir,
                host="127.0.0.1",
                port=8080,
                role="client",
                output_path=cfg_path,
                anonymize=True,
            )

            self.assertTrue(os.path.isfile(cfg_path))
            self.assertEqual(cfg["server"]["host"], "127.0.0.1")
            self.assertEqual(cfg["server"]["port"], 8080)
            self.assertFalse(cfg["security"]["require_auth"])
            self.assertTrue(cfg["security"]["anonymize_logs"])
            self.assertEqual(cfg["environment"], "development")
            self.assertEqual(cfg["database"]["storage_dir"], str(Path(tmp_dir).resolve()))

            # Verify saved file parses cleanly
            loaded = load_config(cfg_path)
            self.assertEqual(loaded["server"]["port"], 8080)

    def test_generate_server_role_config(self):
        """Verify shared central lab server configuration settings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "server_config.yaml")
            cfg = generate_tailored_config(
                shared_dir=tmp_dir,
                host="0.0.0.0",
                port=9000,
                role="server",
                output_path=cfg_path,
                anonymize=True,
            )

            self.assertEqual(cfg["server"]["host"], "0.0.0.0")
            self.assertEqual(cfg["server"]["port"], 9000)
            self.assertTrue(cfg["security"]["require_auth"])
            self.assertIsNotNone(cfg["security"]["token_secret"])
            self.assertEqual(len(cfg["security"]["token_secret"]), 64)
            self.assertEqual(cfg["environment"], "production")
            self.assertEqual(cfg["database"]["storage_mode"], "client_server")
            self.assertEqual(cfg["database"]["lock_timeout_seconds"], 120)

    def test_generate_standalone_role_config(self):
        """Verify standalone offline researcher configuration settings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "standalone_config.yaml")
            cfg = generate_tailored_config(
                shared_dir=tmp_dir,
                role="standalone",
                output_path=cfg_path,
            )

            self.assertEqual(cfg["database"]["storage_mode"], "local")
            self.assertEqual(cfg["environment"], "offline")
            self.assertFalse(cfg["security"]["require_auth"])


class TestSetupWizardExecution(unittest.TestCase):
    """Test suite verifying end-to-end execution of run_setup_wizard in non-interactive mode."""

    def test_non_interactive_setup_wizard_success(self):
        """Verify complete first-run setup wizard generation on temporary shared drive."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "eln_config.yaml")
            res = run_setup_wizard(
                non_interactive=True,
                shared_dir=tmp_dir,
                role="client",
                host="127.0.0.1",
                port=8080,
                config_output=cfg_path,
            )

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["role"], "client")
            self.assertEqual(res["storage_dir"], str(Path(tmp_dir).resolve()))
            self.assertTrue(res["verification"]["permissions_verified"])
            self.assertTrue(res["verification"]["database_created"])
            self.assertTrue(res["verification"]["config_written"])
            self.assertGreaterEqual(res["verification"]["tables_count"], 15)

            # Verify files exist on disk
            self.assertTrue(os.path.isfile(res["config_path"]))
            self.assertTrue(os.path.isfile(res["db_path"]))

            # Verify database can be accessed and contains schema
            conn = sqlite3.connect(res["db_path"])
            try:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [r[0] for r in cur.fetchall()]
                self.assertIn("experimental_campaigns", tables)
                self.assertIn("notebook_daily_entries", tables)
            finally:
                conn.close()

    def test_non_interactive_setup_wizard_server_profile(self):
        """Verify server role setup generates 0.0.0.0 binding and auth configuration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "central_config.yaml")
            res = run_setup_wizard(
                non_interactive=True,
                shared_dir=tmp_dir,
                role="server",
                host="0.0.0.0",
                port=8888,
                config_output=cfg_path,
            )

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["server"]["host"], "0.0.0.0")
            self.assertEqual(res["server"]["port"], 8888)

    def test_non_interactive_setup_wizard_permission_failure_handling(self):
        """Verify graceful error reporting when shared directory permission probe fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "biolabcalc.setup_wizard.validate_shared_path_permissions",
                return_value={
                    "valid": False,
                    "writable": False,
                    "readable": False,
                    "deletable": False,
                    "sqlite_lock_ok": False,
                    "error": "Simulated permission failure on shared lab volume",
                    "path": tmp_dir,
                },
            ):
                res = run_setup_wizard(
                    non_interactive=True,
                    shared_dir=tmp_dir,
                    role="client",
                )

                self.assertEqual(res["status"], "error")
                self.assertIn("Simulated permission failure", res["error"])
                self.assertFalse(res["verification"]["permissions_verified"])
                self.assertFalse(res["verification"]["config_written"])
                self.assertFalse(res["verification"]["database_created"])


class TestPortablePackaging(unittest.TestCase):
    """Test suite verifying portable distribution creation, dry-run simulation, and asset validation."""

    def test_portable_packaging_dry_run(self):
        """Verify dry-run simulation returns manifest without modifying filesystem."""
        result = create_portable_package(dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertTrue(result["valid"])
        self.assertGreater(result["file_count"], 10)

        manifest = result["manifest"]
        expected_manifest_files = [
            "run_lab.bat",
            "run_lab.sh",
            "config.yaml.example",
            "README_PORTABLE.txt",
            "run.py",
        ]
        for ef in expected_manifest_files:
            self.assertIn(ef, manifest)

    def test_portable_packaging_build_and_structure_verification(self):
        """Verify full portable package creation in temporary directory and inspect contents."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            dist_output = os.path.join(tmp_dir, "biolabcalc_portable")
            result = create_portable_package(
                output_dir=dist_output,
                dry_run=False,
                clean=True,
            )

            self.assertEqual(result["status"], "success")
            self.assertTrue(result["valid"])

            val = result.get("validation", {})
            self.assertTrue(val.get("valid"))
            self.assertTrue(val.get("templates_verified"))
            self.assertTrue(val.get("static_verified"))
            self.assertTrue(val.get("packages_verified"))
            self.assertEqual(len(val.get("missing_files", [])), 0)

            # Verify launchers exist and call 'run.py eln'
            bat_path = Path(dist_output) / "run_lab.bat"
            self.assertTrue(bat_path.is_file())
            bat_content = bat_path.read_text(encoding="utf-8")
            self.assertIn("run.py", bat_content)
            self.assertIn("eln", bat_content)

            sh_path = Path(dist_output) / "run_lab.sh"
            self.assertTrue(sh_path.is_file())
            sh_content = sh_path.read_text(encoding="utf-8")
            self.assertIn("run.py", sh_content)
            self.assertIn("eln", sh_content)

            # Verify README_PORTABLE.txt instructions
            readme_path = Path(dist_output) / "README_PORTABLE.txt"
            self.assertTrue(readme_path.is_file())
            readme_content = readme_path.read_text(encoding="utf-8")
            self.assertIn("BIOLABCALC ZERO-INSTALL PORTABLE DISTRIBUTION", readme_content)
            self.assertIn("SHARED LAB DRIVE DEPLOYMENT", readme_content)
            self.assertIn("SETUP WIZARD", readme_content)

            # Verify config.yaml.example
            cfg_example_path = Path(dist_output) / "config.yaml.example"
            self.assertTrue(cfg_example_path.is_file())

            # Verify web templates and static assets
            index_html = Path(dist_output) / "src" / "biolabcalc" / "eln" / "web" / "templates" / "index.html"
            self.assertTrue(index_html.is_file())
            styles_css = Path(dist_output) / "src" / "biolabcalc" / "eln" / "web" / "static" / "styles.css"
            self.assertTrue(styles_css.is_file())

            # Verify setup wizard is included
            wizard_py = Path(dist_output) / "src" / "biolabcalc" / "setup_wizard.py"
            self.assertTrue(wizard_py.is_file())

    def test_validate_portable_distribution_on_empty_dir(self):
        """Verify validator flags missing files on an empty or invalid directory."""
        with tempfile.TemporaryDirectory() as empty_dir:
            val = validate_portable_distribution(empty_dir)
            self.assertFalse(val["valid"])
            self.assertGreater(len(val["missing_files"]), 0)
            self.assertGreater(len(val["errors"]), 0)


if __name__ == "__main__":
    unittest.main()
