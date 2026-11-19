"""
Unit and regression tests verifying all audit remediations (ERR-01 through ERR-12).

Tests:
1. Python 3.8 AST syntax compliance across all src/ modules.
2. Long multiline PDB coordinate string handling in allostery (no Errno 36).
3. LabReport HTML export with @media print CSS and Excel export.
4. format_protocol_html() with @media print and print CSS in interactive apps.
5. ELN SQLite persistence roundtrip across service restarts.
"""

from __future__ import annotations

import ast
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


class TestAuditRegressions(unittest.TestCase):
    """Regression test suite guarding against previously identified audit defects."""

    def test_python38_ast_compliance(self) -> None:
        """Verify all python source files in src/ parse cleanly under Python 3.8 AST."""
        src_dir = REPO_ROOT / "src"
        py_files = sorted(src_dir.glob("**/*.py"))
        self.assertGreater(len(py_files), 30, "Expected at least 30 Python source files in src/")

        failures = []
        for p in py_files:
            source = p.read_text(encoding="utf-8")
            try:
                ast.parse(source, filename=str(p), feature_version=(3, 8))
            except SyntaxError as e:
                failures.append(f"{p.relative_to(REPO_ROOT)}:{e.lineno}: {e}")

        self.assertEqual(failures, [], f"Python 3.8 syntax errors found:\n" + "\n".join(failures))

    def test_allostery_long_multiline_pdb_parsing(self) -> None:
        """Verify multiline PDB strings (>300 chars) are parsed without Errno 36 File name too long."""
        from biolabcalc.allostery import parse_pdb_ca_coordinates, trace_allosteric_paths

        multiline_pdb = (
            "HEADER    ALLOSTERY TEST PDB LONG STRING\n"
            "ATOM      1  CA  MET A   1      10.000  10.000  10.000  1.00 20.00           C\n"
            "ATOM      2  CA  ALA A   2      13.800  10.000  10.000  1.00 20.00           C\n"
            "ATOM      3  CA  VAL A   3      17.600  10.000  10.000  1.00 20.00           C\n"
            "ATOM      4  CA  LEU A   4      21.400  10.000  10.000  1.00 20.00           C\n"
            "ATOM      5  CA  ILE A   5      25.200  10.000  10.000  1.00 20.00           C\n"
            "ATOM      6  CA  PHE A   6      29.000  10.000  10.000  1.00 20.00           C\n"
            "ATOM      7  CA  TRP A   7      32.800  10.000  10.000  1.00 20.00           C\n"
            "ATOM      8  CA  TYR A   8      36.600  10.000  10.000  1.00 20.00           C\n"
            "ATOM      9  CA  ASP A   9      40.400  10.000  10.000  1.00 20.00           C\n"
            "ATOM     10  CA  GLU A  10      44.200  10.000  10.000  1.00 20.00           C\n"
            "END\n"
        )
        self.assertGreater(len(multiline_pdb), 500)

        # Direct coordinate parsing
        nodes = parse_pdb_ca_coordinates(multiline_pdb)
        self.assertEqual(len(nodes), 10)
        self.assertEqual(nodes[0].resname, "MET")
        self.assertEqual(nodes[-1].resname, "GLU")

        # Full pathway tracing
        result = trace_allosteric_paths(
            multiline_pdb,
            source_resid=1,
            sink_resid=6,
            cutoff_angstroms=4.5,
            k_paths=2,
        )
        self.assertIsNotNone(result)
        self.assertGreater(len(result.paths), 0)

    def test_lab_report_html_and_excel_exports(self) -> None:
        """Verify LabReport exports HTML with @media print and Excel workbook."""
        from biolabcalc.lab_report import LabReport

        report = LabReport(
            title="Audit Regression Quality Report",
            experimenter="Audit QA",
            objective="Testing printable HTML and Excel generation.",
        )
        report.add_record("Sample_1", "Yield", 450.5, "ng/uL", notes="Sample A")
        report.add_record("Sample_1", "A260/A280", 1.87, "ratio")

        # HTML Export
        html_content = report.to_html()
        self.assertIn("@media print", html_content)
        self.assertIn("window.print()", html_content)
        self.assertIn("Audit Regression Quality Report", html_content)
        self.assertIn("450.5", html_content)

        # Excel Export (if openpyxl installed)
        try:
            import openpyxl  # noqa: F401
            has_openpyxl = True
        except ImportError:
            has_openpyxl = False

        if has_openpyxl:
            with tempfile.TemporaryDirectory() as td:
                out_xlsx = os.path.join(td, "report.xlsx")
                saved_path = report.to_excel(out_xlsx)
                self.assertTrue(os.path.exists(saved_path))
                self.assertGreater(os.path.getsize(saved_path), 1000)

    def test_printable_protocol_html_and_media_print(self) -> None:
        """Verify format_protocol_html generates @media print styling and window.print()."""
        from biolabcalc.protocols import list_protocols, format_protocol_html

        protocols = list_protocols()
        self.assertGreater(len(protocols), 0)
        proto = protocols[0]
        self.assertIsNotNone(proto)

        html_out = format_protocol_html(proto)
        self.assertIn("@media print", html_out)
        self.assertIn("window.print()", html_out)
        self.assertIn(proto.title, html_out)

    def test_eln_server_persistence_restart_roundtrip(self) -> None:
        """Verify ELN CampaignService persists and restores across service restarts via SQLite."""
        temp_dir = tempfile.mkdtemp(prefix="biolabcalc_reg_test_")
        old_storage = os.environ.get("BIOLABCALC_STORAGE_DIR")
        os.environ["BIOLABCALC_STORAGE_DIR"] = temp_dir

        try:
            from biolabcalc.eln.storage.sqlite_store import SQLiteStore
            from biolabcalc.eln.services.campaign_service import CampaignService

            db_file = os.path.join(temp_dir, "eln_lims.db")
            store1 = SQLiteStore(db_file)
            svc1 = CampaignService(store=store1)

            # Create campaign
            cmp1 = svc1.create_campaign(
                title="T7RNAP Purification Roundtrip",
                description="Testing persistent disk state across simulated server reboots.",
                construct_id="pET-28a-T7RNAP",
                created_by="audit_agent",
            )
            cid = cmp1.campaign_id

            # Add daily entry
            entry1 = svc1.add_daily_entry(
                campaign_id=cid,
                day_number=1,
                title="Cell Lysis & Clarification",
                created_by="audit_agent",
                notes="Pellet weight 12.4g, lysed with 60 mL Lysis Buffer.",
            )
            eid = entry1.entry_id

            # Simulate complete server restart: create brand new store and service instance
            del svc1
            del store1

            store2 = SQLiteStore(db_file)
            svc2 = CampaignService(store=store2)

            restored_cmp = svc2.get_campaign(cid)
            self.assertIsNotNone(restored_cmp, f"Campaign {cid} was not restored after simulated restart")
            self.assertEqual(restored_cmp.title, "T7RNAP Purification Roundtrip")
            self.assertEqual(restored_cmp.construct_id, "pET-28a-T7RNAP")
            self.assertEqual(len(restored_cmp.daily_entries), 1)
            self.assertEqual(restored_cmp.daily_entries[0].entry_id, eid)
            self.assertEqual(restored_cmp.daily_entries[0].title, "Cell Lysis & Clarification")
            self.assertIn("Pellet weight 12.4g", restored_cmp.daily_entries[0].notes)

        finally:
            if old_storage is not None:
                os.environ["BIOLABCALC_STORAGE_DIR"] = old_storage
            else:
                os.environ.pop("BIOLABCALC_STORAGE_DIR", None)
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
