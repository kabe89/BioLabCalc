"""Unit tests for BioLabCalc CLI commands and wizard."""

import io
import sys
import unittest
from unittest.mock import patch

from biolabcalc.cli import main, run_wizard


class TestCLI(unittest.TestCase):
    """Test suite covering biolabcalc command-line interface execution."""

    def test_cli_dilute_molar(self):
        """Test dilute command with molar concentration units."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "dilute", "-c1", "100 mM", "-c2", "25 mM", "-v2", "16 mL"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("DILUTION CALCULATOR", output)
        self.assertIn("Stock Concentration (C1):    100.0 mM", output)
        self.assertIn("Target Concentration (C2):   25.0 mM", output)
        self.assertIn("Stock Volume to Add (V1):     4.000 mL", output)

    def test_cli_dilute_mass(self):
        """Test dilute command with mass concentration units (mg/mL)."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "dilute", "-c1", "10 mg/mL", "-c2", "2 mg/mL", "-v2", "10 mL"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("DILUTION CALCULATOR", output)
        self.assertIn("Stock Concentration (C1):    10.0 mg/mL", output)
        self.assertIn("Target Concentration (C2):   2.0 mg/mL", output)

    def test_cli_mw_dna(self):
        """Test mw subcommand for DNA sequence."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "mw", "-s", "ATGCGATCGATC", "-t", "dna"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("Sequence Type:       ssDNA", output)
        self.assertIn("Average MW:", output)

    def test_cli_pcr_template_with_units(self):
        """Test pcr subcommand with template string containing units (e.g. '10 ng')."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "pcr", "-l", "500", "-t", "10 ng", "-c", "30"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("PCR KINETICS & REACTION STOICHIOMETRY", output)
        self.assertIn("Amplicon Length:            500 bp", output)
        self.assertIn("Initial Template:           10.0 ng", output)

    def test_cli_wizard_choices(self):
        """Test wizard options."""
        # Test option 1 (dilute)
        with patch("builtins.input", side_effect=["1", "100 mM", "25 mM", "16 mL"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("Dilution Calculator", captured.getvalue())

        # Test option 3 (IVT)
        with patch("builtins.input", side_effect=["3", "GGGAGACCCAAGCUGGCC", "20.0", "50.0"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("In Vitro Transcription", captured.getvalue())

        # Test option 4 (PCR master mix)
        with patch("builtins.input", side_effect=["4", "8", "50.0", "10.0"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("PCR Master Mix Formulation", captured.getvalue())

        # Test option 6 (Precipitation)
        with patch("builtins.input", side_effect=["6", "100.0", "dna", "ethanol"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("Nucleic Acid Precipitation", captured.getvalue())

        # Test option 7 (MW)
        with patch("builtins.input", side_effect=["7", "dna", "ACGT"]):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                run_wizard()
            self.assertIn("Molecular Weight & Molarity", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
