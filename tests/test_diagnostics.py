"""
Test Suite: tests.test_diagnostics
Component: Component 6 - Diagnostics & Failure Logging Specialist
Architectural Role: Comprehensive verification of operational failure interception,
                    sanitized error reporting, plain-English root-cause explanations,
                    actionable remediation advice, persistent human/machine log formatting,
                    and context-managed diagnostics capturing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Add src to sys.path so test suite runs standalone
_repo_root = Path(__file__).resolve().parent.parent
_src_dir = _repo_root / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from biolabcalc.diagnostics import (
    FailureDiagnosticsRecorder,
    DiagnosticCaptureContext,
    anonymize_path,
    sanitize_message,
    classify_error,
    get_sanitized_traceback,
    record_failure,
    get_recent_failures,
    clear_failures,
    capture_diagnostics,
    get_default_recorder,
    set_default_recorder,
)


class TestFailureDiagnostics(unittest.TestCase):
    """Unit tests for FailureDiagnosticsRecorder and diagnostics helpers."""

    def setUp(self):
        """Create a temporary directory for isolated file logging during tests."""
        self.temp_dir = tempfile.mkdtemp(prefix="biolabcalc_diag_test_")
        self.recorder = FailureDiagnosticsRecorder(log_dir=self.temp_dir)
        # Store previous default recorder and set isolated recorder
        self._prev_recorder = get_default_recorder()
        set_default_recorder(self.recorder)

    def tearDown(self):
        """Clean up temporary log directory and restore original recorder."""
        set_default_recorder(self._prev_recorder)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_permission_error(self):
        """Verifies recording of PermissionError with plain-English cause and advice."""
        err = PermissionError("[Errno 13] Permission denied: '/lab/data/samples.db'")
        record = record_failure("BLOB_STORE", err)

        self.assertEqual(record["subsystem"], "BLOB_STORE")
        self.assertEqual(record["error_type"], "PermissionError")
        self.assertIn("Permission denied", record["error_message"])
        self.assertIn("Write access denied on directory", record["plain_english_cause"])
        self.assertTrue(
            any(
                "Write access denied on directory; check file permissions or run with designated user"
                in step
                for step in record["remediation_suggestions"]
            )
        )
        self.assertTrue(len(record["sanitized_traceback"]) > 0)

    def test_record_timeout_error(self):
        """Verifies recording of TimeoutError with network drive remediation advice."""
        err = TimeoutError("Connection to network share //nas01/lims timed out")
        record = record_failure("NETWORK_DRIVE", err)

        self.assertEqual(record["subsystem"], "NETWORK_DRIVE")
        self.assertEqual(record["error_type"], "TimeoutError")
        self.assertIn("Network timeout", record["plain_english_cause"])
        self.assertTrue(
            any(
                "Check if network drive/VPN is connected or switch to offline mode" in step
                for step in record["remediation_suggestions"]
            )
        )

    def test_record_file_not_found_error(self):
        """Verifies recording of FileNotFoundError with file path and format check advice."""
        err = FileNotFoundError("[Errno 2] No such file or directory: 'protocol_v2.json'")
        record = record_failure("PARSER", err)

        self.assertEqual(record["subsystem"], "PARSER")
        self.assertEqual(record["error_type"], "FileNotFoundError")
        self.assertIn("could not be found", record["plain_english_cause"])
        self.assertTrue(
            any(
                "Verify file path and check format matches requirements" in step
                for step in record["remediation_suggestions"]
            )
        )

    def test_record_value_error_format(self):
        """Verifies recording of ValueError format errors with schema check advice."""
        err = ValueError("Invalid table format: expected 5 tab-separated columns, found 3")
        record = record_failure("PARSER", err)

        self.assertEqual(record["subsystem"], "PARSER")
        self.assertEqual(record["error_type"], "ValueError")
        self.assertIn("format", record["plain_english_cause"].lower())
        self.assertTrue(
            any(
                "Verify file path and check format matches requirements" in step
                for step in record["remediation_suggestions"]
            )
        )

    def test_record_lock_collision(self):
        """Verifies recording of database lock collisions with retry remediation advice."""
        err = BlockingIOError("Resource temporarily unavailable: database is locked")
        record = record_failure("DATABASE", err)

        self.assertEqual(record["subsystem"], "DATABASE")
        self.assertEqual(record["error_type"], "BlockingIOError")
        self.assertIn(
            "Another user or process is writing to the database; retry in a few moments",
            record["plain_english_cause"],
        )
        self.assertTrue(
            any(
                "Another user or process is writing to the database; retry in a few moments" in step
                for step in record["remediation_suggestions"]
            )
        )

    def test_plain_english_cause_and_remediation_suite(self):
        """Validates all 4 primary architectural plain-English cause and remediation mappings."""
        cases = [
            (
                "NETWORK_DRIVE",
                TimeoutError("Connection timed out"),
                "Check if network drive/VPN is connected or switch to offline mode",
            ),
            (
                "DATABASE",
                BlockingIOError("database is locked"),
                "Another user or process is writing to the database; retry in a few moments",
            ),
            (
                "BLOB_STORE",
                PermissionError("Access is denied"),
                "Write access denied on directory; check file permissions or run with designated user",
            ),
            (
                "PARSER",
                FileNotFoundError("missing_template.csv"),
                "Verify file path and check format matches requirements",
            ),
            (
                "PARSER",
                ValueError("malformed input format"),
                "Verify file path and check format matches requirements",
            ),
        ]

        for subsystem, exc, expected_remediation in cases:
            with self.subTest(subsystem=subsystem, error=type(exc).__name__):
                rec = self.recorder.record_failure(subsystem, exc)
                self.assertTrue(
                    any(expected_remediation in step for step in rec["remediation_suggestions"]),
                    f"Expected '{expected_remediation}' in suggestions: {rec['remediation_suggestions']}",
                )

    def test_custom_remediation_handling(self):
        """Verifies custom remediation steps are prioritized and prepended."""
        custom_step = "Run manual recovery script: ./scripts/recover_share.sh"
        rec = record_failure(
            "CLI",
            RuntimeError("Custom runner failure"),
            custom_remediation=custom_step,
        )
        self.assertEqual(rec["remediation_suggestions"][0], custom_step)

        custom_steps = ["Step A: Inspect VPN", "Step B: Re-mount NFS"]
        rec2 = record_failure(
            "NETWORK_DRIVE",
            TimeoutError("Share unavailable"),
            custom_remediation=custom_steps,
        )
        self.assertEqual(rec2["remediation_suggestions"][:2], custom_steps)

    def test_sanitization_usernames_and_paths(self):
        """Verifies local system usernames, sensitive home paths, and secrets are masked."""
        raw_msg = (
            "Failed accessing C:\\Users\\jdoe\\AppData\\Local\\secret.key "
            "with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123 and url postgresql://admin:supersecret@10.0.0.1:5432/lims"
        )
        clean_msg = sanitize_message(raw_msg)

        self.assertNotIn("jdoe", clean_msg)
        self.assertNotIn("C:\\Users\\jdoe", clean_msg)
        self.assertIn("~\\AppData\\Local\\secret.key", clean_msg)
        self.assertIn("Bearer [REDACTED_TOKEN]", clean_msg)
        self.assertIn("postgresql://admin:[REDACTED_PASS]@10.0.0.1:5432/lims", clean_msg)

    def test_real_traceback_anonymization(self):
        """Verifies traceback generated from real exception anonymizes internal user paths."""
        try:
            raise PermissionError("C:\\Users\\admin\\secure_file.txt cannot be opened")
        except PermissionError as exc:
            record = record_failure("CLI", exc)

        tb = record["sanitized_traceback"]
        self.assertNotIn("C:\\Users\\admin", tb)
        self.assertNotIn("C:\\Users\\admin", record["error_message"])

    def test_log_appending_and_jsonl_structure(self):
        """Verifies append operations to both failures.log and failures.jsonl."""
        clear_failures()
        record_failure("CLI", ValueError("Parameter 'volume' must be positive"))
        record_failure("DATABASE", TimeoutError("DB connection timed out"))

        log_path = self.recorder.log_path
        jsonl_path = self.recorder.jsonl_path

        self.assertTrue(log_path.is_file())
        self.assertTrue(jsonl_path.is_file())

        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("[CLI] ValueError:", log_content)
        self.assertIn("[DATABASE] TimeoutError:", log_content)
        self.assertIn("Remediation Suggestions:", log_content)

        jsonl_lines = [
            json.loads(line)
            for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(jsonl_lines), 2)
        self.assertEqual(jsonl_lines[0]["subsystem"], "CLI")
        self.assertEqual(jsonl_lines[0]["error_type"], "ValueError")
        self.assertEqual(jsonl_lines[1]["subsystem"], "DATABASE")
        self.assertEqual(jsonl_lines[1]["error_type"], "TimeoutError")

        # Verify ISO8601 UTC timestamp format
        self.assertTrue(jsonl_lines[0]["timestamp"].endswith("Z"))

    def test_get_recent_failures(self):
        """Verifies retrieving recent failures with limit and ordering."""
        clear_failures()
        for i in range(5):
            record_failure("PARSER", ValueError(f"Error {i}"))

        # Default limit=10 should return all 5
        recent = get_recent_failures(limit=10)
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0]["error_message"], "Error 0")
        self.assertEqual(recent[-1]["error_message"], "Error 4")

        # Limit=2 returns the last 2 recorded
        limited = get_recent_failures(limit=2)
        self.assertEqual(len(limited), 2)
        self.assertEqual(limited[0]["error_message"], "Error 3")
        self.assertEqual(limited[1]["error_message"], "Error 4")

        # Newest first
        reversed_recent = get_recent_failures(limit=3, newest_first=True)
        self.assertEqual(len(reversed_recent), 3)
        self.assertEqual(reversed_recent[0]["error_message"], "Error 4")
        self.assertEqual(reversed_recent[-1]["error_message"], "Error 2")

    def test_clear_failures(self):
        """Verifies clear_failures truncates both files and resets in-memory cache."""
        record_failure("CLI", RuntimeError("First failure"))
        record_failure("CLI", RuntimeError("Second failure"))
        self.assertEqual(len(get_recent_failures()), 2)

        clear_failures()

        self.assertEqual(len(get_recent_failures()), 0)
        self.assertEqual(self.recorder.log_path.read_text(encoding="utf-8"), "")
        self.assertEqual(self.recorder.jsonl_path.read_text(encoding="utf-8"), "")

    def test_capture_diagnostics_context_manager(self):
        """Verifies capture_diagnostics context manager records errors and supports reraise control."""
        clear_failures()

        # 1. Successful execution records nothing
        with capture_diagnostics("CLI"):
            val = 42 + 8
        self.assertEqual(val, 50)
        self.assertEqual(len(get_recent_failures()), 0)

        # 2. Re-raising context manager propagates exception while recording failure
        with self.assertRaises(ValueError):
            with capture_diagnostics("CLI", context={"input_file": "bad.csv"}):
                raise ValueError("Corrupted CSV structure")

        recent = get_recent_failures()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["subsystem"], "CLI")
        self.assertEqual(recent[0]["error_type"], "ValueError")
        self.assertEqual(recent[0]["context"]["input_file"], "bad.csv")

        # 3. Suppressed context manager (reraise=False) does not throw and exposes failure
        with capture_diagnostics("DATABASE", reraise=False) as diag:
            raise TimeoutError("Database handshake timed out")

        self.assertIsNotNone(diag.failure)
        self.assertEqual(diag.failure["error_type"], "TimeoutError")
        self.assertEqual(len(get_recent_failures()), 2)

    def test_isolated_instance(self):
        """Verifies that an independent FailureDiagnosticsRecorder instance operates in isolation."""
        with tempfile.TemporaryDirectory() as other_dir:
            other_rec = FailureDiagnosticsRecorder(log_dir=other_dir)
            other_rec.record_failure("BLOB_STORE", FileNotFoundError("Missing blob"))

            self.assertEqual(len(other_rec.get_recent_failures()), 1)
            self.assertTrue((Path(other_dir) / "failures.log").is_file())
            self.assertTrue((Path(other_dir) / "failures.jsonl").is_file())

            # Global/self.recorder should not be affected
            self.assertEqual(len(self.recorder.get_recent_failures()), 0)


if __name__ == "__main__":
    unittest.main()
