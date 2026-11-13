"""Unit tests for BioLabCalc CLI commands and wizard."""

import io
import os
import sys
import unittest
from unittest.mock import patch

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

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

    def test_cli_dilute_aliases(self):
        """Test dilute command with --conc1, --conc2, --vol2 aliases."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "dilute", "--conc1", "100 mM", "--conc2", "25 mM", "--vol2", "16 mL"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("Stock Concentration (C1):    100.0 mM", output)
        self.assertIn("Target Concentration (C2):   25.0 mM", output)
        self.assertIn("Stock Volume to Add (V1):     4.000 mL", output)

    def test_cli_mw_aliases(self):
        """Test mw subcommand with --end5 and --end3 aliases."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "mw", "-s", "ATGCGATCGATC", "-t", "dna", "--end5", "triphosphate", "--end3", "hydroxyl"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("Sequence Type:       ssDNA", output)
        self.assertIn("Average MW:", output)

    def test_cli_nanodrop_aliases(self):
        """Test nanodrop command with -m, -l, --stock, and --end5 aliases."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "nanodrop", "-m", "4.0", "-v", "500.0", "-l", "120", "--stock", "800.0", "--end5", "triphosphate"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("Target Solution:            4.0 µM in 500.0 µL", output)
        self.assertIn("Actual Physical Conc.:", output)

    def test_cli_pcr_opt_aliases(self):
        """Test pcr-opt subcommand with --tm-fwd, --tm-rev, and --poly aliases."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "pcr-opt", "--tm-fwd", "60.0", "--tm-rev", "62.0", "-l", "850", "--poly", "q5"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("PCR PROTOCOL OPTIMIZATION", output)
        self.assertIn("Polymerase:                 Q5", output)

    def test_cli_ntp_ph_aliases(self):
        """Test ntp-ph subcommand with -v1, -c1, -v2, -c2, --ph, and --form aliases."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "ntp-ph", "-v1", "4.0", "-c1", "100.0", "-v2", "16.0", "-c2", "25.0", "--ph", "7.5", "--form", "disodium_salt"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("NTP SOLUTION PREPARATION & pH ADJUSTMENT", output)
        self.assertIn("Target Solution:      25.0 mM", output)

    def test_cli_precipitate_flags(self):
        """Test precipitate subcommand with -s licl, --carrier, and --no-carrier."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "precipitate", "-v", "100.0", "-s", "licl", "--carrier"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("NUCLEIC ACID PRECIPITATION PROTOCOL", output)
        self.assertIn("8 M Lithium Chloride", output)
        self.assertIn("Carrier Added:        1.0 µL of GlycoBlue or Glycogen", output)

        captured_no_carrier = io.StringIO()
        test_args_no = ["biolabcalc", "precipitate", "-v", "100.0", "--no-carrier"]
        with patch.object(sys, "argv", test_args_no), patch("sys.stdout", captured_no_carrier):
            main()
        self.assertIn("Carrier Added:        None", captured_no_carrier.getvalue())

    def test_cli_western_aliases_and_flags(self):
        """Test western subcommand with -target, --ug, --membrane-protein, and --membrane."""
        captured = io.StringIO()
        test_args = ["biolabcalc", "western", "-target", "GluK2", "-m", "102.5", "-c", "2.5", "--ug", "20.0", "--membrane-protein"]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("WESTERN BLOT EXPERIMENTAL PLAN: GluK2", output)
        self.assertIn("CRITICAL MEMBRANE PROTEIN PROTOCOL", output)

        captured_mem = io.StringIO()
        test_args_mem = ["biolabcalc", "western", "--target", "GluK2", "-m", "102.5", "--membrane"]
        with patch.object(sys, "argv", test_args_mem), patch("sys.stdout", captured_mem):
            main()
        self.assertIn("WESTERN BLOT EXPERIMENTAL PLAN: GluK2", captured_mem.getvalue())
        self.assertIn("CRITICAL MEMBRANE PROTEIN PROTOCOL", captured_mem.getvalue())

    def test_cli_fluo_info_and_dol(self):
        """Test fluo subcommand with --info and --dol modes."""
        captured_info = io.StringIO()
        with patch.object(sys, "argv", ["biolabcalc", "fluo", "--info", "FAM"]), patch("sys.stdout", captured_info):
            main()
        self.assertIn("FLUOROPHORE DATABASE ENTRY: 6-FAM", captured_info.getvalue())

        captured_dol_prot = io.StringIO()
        test_dol_p = ["biolabcalc", "fluo", "--dol", "-d", "ALEXA488", "--a-dye", "0.820", "--a280", "0.640", "--prot-e280", "210000"]
        with patch.object(sys, "argv", test_dol_p), patch("sys.stdout", captured_dol_prot):
            main()
        self.assertIn("DEGREE OF LABELING (DOL) CALCULATION (PROTEIN)", captured_dol_prot.getvalue())
        self.assertIn("Fluorophore:                Alexa Fluor 488", captured_dol_prot.getvalue())

        captured_dol_dna = io.StringIO()
        test_dol_d = ["biolabcalc", "fluo", "--dol", "-d", "CY3", "--a-dye", "1.150", "--a260", "0.980", "--dna-e260", "195000"]
        with patch.object(sys, "argv", test_dol_d), patch("sys.stdout", captured_dol_dna):
            main()
        self.assertIn("DEGREE OF LABELING (DOL) CALCULATION (OLIGONUCLEOTIDE)", captured_dol_dna.getvalue())
        self.assertIn("Fluorophore:                Cy3", captured_dol_dna.getvalue())

    def test_cli_report_aliases(self):
        """Test report subcommand with --obj, --conclusion, --val, --tol aliases."""
        captured = io.StringIO()
        test_args = [
            "biolabcalc", "report",
            "-t", "QC Run",
            "--obj", "Assay QC verification",
            "-s", "S1",
            "--param", "Yield",
            "--val", "45.0",
            "-u", "ug",
            "--target", "50.0",
            "--tol", "15.0",
            "--conclusion", "Meets acceptance criteria",
        ]
        with patch.object(sys, "argv", test_args), patch("sys.stdout", captured):
            main()
        output = captured.getvalue()
        self.assertIn("Assay QC verification", output)
        self.assertIn("Meets acceptance criteria", output)

    def test_cli_annotate_gel_invert_flag(self):
        """Test annotate-gel invert_colors flag behavior (Issue 10)."""
        import os
        import tempfile
        out_temp = os.path.join(tempfile.gettempdir(), "test_annotator_out.png")
        captured = io.StringIO()
        with patch("biolabcalc.cli.GelAnnotator") as mock_annotator:
            mock_inst = mock_annotator.synthetic.return_value
            mock_inst.render.return_value = out_temp
            with patch.object(sys, "argv", ["biolabcalc", "annotate-gel", "--lanes", "L1,L2", "-o", out_temp]), patch("sys.stdout", captured):
                main()
            mock_annotator.synthetic.assert_called_once()
            _, kwargs = mock_annotator.synthetic.call_args
            self.assertFalse(kwargs.get("invert_colors"))

        with patch("biolabcalc.cli.GelAnnotator") as mock_annotator:
            mock_inst = mock_annotator.synthetic.return_value
            mock_inst.render.return_value = out_temp
            with patch.object(sys, "argv", ["biolabcalc", "annotate-gel", "--lanes", "L1,L2", "--invert", "-o", out_temp]), patch("sys.stdout", captured):
                main()
            mock_annotator.synthetic.assert_called_once()
            _, kwargs = mock_annotator.synthetic.call_args
            self.assertTrue(kwargs.get("invert_colors"))

        if os.path.exists(out_temp):
            os.remove(out_temp)


if __name__ == "__main__":
    unittest.main()
