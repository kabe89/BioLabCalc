"""Unit tests for BioLabCalc CLI command dispatch, version, rc, translate, and extended ladders."""

from __future__ import annotations
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.cli import main, run_wizard, COMMAND_DISPATCH


class TestCliDispatch(unittest.TestCase):
    """Test suite covering CLI dispatch modularization, subcommands, and options."""

    def _run_cli(self, args_list: list[str], stdin_content: str | None = None) -> tuple[str, str, int]:
        """Helper to run CLI main() with captured stdout, stderr, and optional stdin."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exit_code = 0
        stdin_patch = (
            patch("sys.stdin", io.StringIO(stdin_content or ""))
            if stdin_content is not None
            else patch("sys.stdin", sys.stdin)
        )

        with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf), stdin_patch:
            with patch.object(sys, "argv", ["biolabcalc"] + args_list):
                try:
                    main()
                except SystemExit as e:
                    exit_code = e.code if isinstance(e.code, int) else 0

        return stdout_buf.getvalue(), stderr_buf.getvalue(), exit_code

    def test_cli_version(self):
        """Test biolabcalc --version and -V output."""
        out, err, code = self._run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("biolabcalc 0.3.5", out)

        out_v, err_v, code_v = self._run_cli(["-V"])
        self.assertEqual(code_v, 0)
        self.assertIn("biolabcalc 0.3.5", out_v)

    def test_cli_rc_dna_json(self):
        """Test biolabcalc rc -s ATGCGTACGTTAGC --json."""
        out, err, code = self._run_cli(["rc", "-s", "ATGCGTACGTTAGC", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["sequence"], "ATGCGTACGTTAGC")
        self.assertEqual(data["type"], "dna")
        self.assertEqual(data["reverse_complement"], "GCTAACGTACGCAT")

    def test_cli_rc_rna_json(self):
        """Test biolabcalc rc -s GGGAGACCCAAGCUGGCC -t rna --json."""
        out, err, code = self._run_cli(["rc", "-s", "GGGAGACCCAAGCUGGCC", "-t", "rna", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["sequence"], "GGGAGACCCAAGCUGGCC")
        self.assertEqual(data["type"], "rna")
        self.assertEqual(data["reverse_complement"], "GGCCAGCUUGGGUCUCCC")

    def test_cli_translate_single_frame_json(self):
        """Test biolabcalc translate -s ATGGCCATGGTGAAC -m 1 --json."""
        out, err, code = self._run_cli(["translate", "-s", "ATGGCCATGGTGAAC", "-m", "1", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["sequence"], "ATGGCCATGGTGAAC")
        self.assertEqual(data["frame"], 1)
        self.assertEqual(data["translation"], "MAMVN")
        self.assertEqual(data["length"], 5)

    def test_cli_translate_all_frames_json(self):
        """Test biolabcalc translate -s ATGGCCATGGTGAAC --all-frames --json."""
        out, err, code = self._run_cli(["translate", "-s", "ATGGCCATGGTGAAC", "--all-frames", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["sequence"], "ATGGCCATGGTGAAC")
        self.assertIn("translations", data)
        self.assertEqual(data["translations"]["+1"], "MAMVN")
        self.assertEqual(data["translations"]["+2"], "WPW*")
        self.assertEqual(data["translations"]["+3"], "GHGE")
        self.assertEqual(data["translations"]["-1"], "VHHGH")
        self.assertEqual(data["translations"]["-2"], "FTMA")
        self.assertEqual(data["translations"]["-3"], "SPWP")

    def test_cli_gel_ssrna_ladder(self):
        """Test biolabcalc gel -s 1500 -l ssrna_ladder."""
        out, err, code = self._run_cli(["gel", "-s", "1500", "-l", "ssrna_ladder"])
        self.assertEqual(code, 0)
        self.assertIn("ssRNA High Range Ladder", out)
        self.assertIn("1500.0 nt", out)

    def test_cli_gel_all_catalog_ladders(self):
        """Test gel subcommand with each of the 7 catalog ladders."""
        ladders = [
            "1kb_dna",
            "100bp_dna",
            "low_range_ssdna",
            "protein_broad_range",
            "ssrna_ladder",
            "low_range_rna",
            "microrna_ladder",
        ]
        for ladder in ladders:
            out, err, code = self._run_cli(["gel", "-s", "200", "-l", ladder])
            self.assertEqual(code, 0, f"Failed for ladder {ladder}: {err}")
            self.assertIn("Gel Migration Simulation", out)

    def test_cli_quiet_flag(self):
        """Test global quiet flag suppresses header banners and decorative bars."""
        out_normal, _, code1 = self._run_cli(["rc", "-s", "ATGCGTACGTTAGC"])
        self.assertEqual(code1, 0)
        self.assertIn("=", out_normal)
        self.assertIn("REVERSE COMPLEMENT", out_normal)

        out_quiet, _, code2 = self._run_cli(["rc", "-s", "ATGCGTACGTTAGC", "-q"])
        self.assertEqual(code2, 0)
        self.assertEqual(out_quiet.strip(), "GCTAACGTACGCAT")

        out_quiet_prefix, _, code3 = self._run_cli(["-q", "rc", "-s", "ATGCGTACGTTAGC"])
        self.assertEqual(code3, 0)
        self.assertEqual(out_quiet_prefix.strip(), "GCTAACGTACGCAT")

    def test_cli_translate_text_and_to_stop(self):
        """Test translate subcommand text formatting and --to-stop option."""
        out, _, code = self._run_cli(["translate", "-s", "ATGAAATTTTAAGGG", "-m", "1"])
        self.assertEqual(code, 0)
        self.assertIn("MKF*G", out)

        out_stop, _, code_stop = self._run_cli(["translate", "-s", "ATGAAATTTTAAGGG", "-m", "1", "--to-stop"])
        self.assertEqual(code_stop, 0)
        self.assertIn("MKF", out_stop)
        self.assertNotIn("MKF*", out_stop)

        out_all, _, code_all = self._run_cli(["translate", "-s", "ATGGCCATGGTGAAC", "--all-frames"])
        self.assertEqual(code_all, 0)
        self.assertIn("6-FRAME NUCLEOTIDE TRANSLATION", out_all)
        self.assertIn("Frame +1", out_all)
        self.assertIn("Frame -1", out_all)

    def test_command_dispatch_keys(self):
        """Test that COMMAND_DISPATCH dictionary contains all subcommands."""
        required_commands = [
            "dilute", "wizard", "interactive", "mw", "ivt", "pcr", "pcr-opt",
            "protein", "primers", "nanodrop", "fluo", "gel", "ecoli",
            "excel-template", "annotate-gel", "interactive-gel", "batch-excel",
            "digest", "ligate", "gibson", "buffer", "precipitate", "ntp-ph",
            "golden-gate", "purity", "pci", "ivt-time", "hepes", "western",
            "report", "eln", "convert", "batch-csv", "rc", "translate"
        ]
        for cmd in required_commands:
            self.assertIn(cmd, COMMAND_DISPATCH)
            self.assertTrue(callable(COMMAND_DISPATCH[cmd]))

    def test_wizard_extended_options(self):
        """Test newly added wizard options 8, 9, 10."""
        # Option 8: Restriction Digest
        with patch("builtins.input", side_effect=["8", "1.0", "50.0", "EcoRI", "", ""]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("Restriction Digest Planning", captured.getvalue())
            self.assertIn("Recommended Buffer:", captured.getvalue())

        # Option 9: Ligation Setup
        with patch("builtins.input", side_effect=["9", "1", "3000", "1000", "50.0", "3.0"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("Ligation / Gibson Assembly Setup", captured.getvalue())
            self.assertIn("Vector (3000 bp):", captured.getvalue())

        # Option 9: Gibson Assembly Setup
        with patch("builtins.input", side_effect=["9", "2", "3000", "1000", "100.0", "2.0"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("Ligation / Gibson Assembly Setup", captured.getvalue())
            self.assertIn("Vector:", captured.getvalue())

        # Option 10: Unit Conversion
        with patch("builtins.input", side_effect=["10", "500 ng", "pmol", "50000"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("Laboratory Unit & Stoichiometry Conversion", captured.getvalue())
            self.assertIn("10.0 pmol", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
