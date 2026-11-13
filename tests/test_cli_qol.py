"""Tests for BioLabCalc CLI Quality-of-Life improvements."""

from __future__ import annotations
import unittest
from unittest.mock import patch
import sys
import io
import json
import tempfile
import os

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.cli import main


class TestCliQoL(unittest.TestCase):
    """Test suite covering CLI JSON formatting, file inputs, piping, convert, and batch-csv."""

    def _run_cli(self, args_list: list[str], stdin_content: str | None = None) -> tuple[str, str, int]:
        """Helper to run CLI main() with captured stdout, stderr, and optional stdin."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exit_code = 0
        stdin_patch = patch("sys.stdin", io.StringIO(stdin_content or "")) if stdin_content is not None else patch("sys.stdin", sys.stdin)

        with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf), stdin_patch:
            with patch("sys.argv", ["biolabcalc"] + args_list):
                try:
                    main()
                except SystemExit as e:
                    exit_code = e.code if isinstance(e.code, int) else 1

        return stdout_buf.getvalue(), stderr_buf.getvalue(), exit_code

    def test_cli_mw_json_and_compact(self):
        # Pretty JSON
        out, err, code = self._run_cli(["mw", "-s", "ATGCGTACGTTAGC", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["length"], 14)
        self.assertIn("average_mw", data)
        self.assertIn("\n", out.strip())  # Multiline pretty JSON

        # Compact JSON
        out_comp, err_comp, code_comp = self._run_cli(["mw", "-s", "ATGCGTACGTTAGC", "--json", "--compact"])
        self.assertEqual(code_comp, 0)
        data_comp = json.loads(out_comp)
        self.assertEqual(data_comp["length"], 14)
        self.assertNotIn("\n", out_comp.strip())  # Single-line compact JSON

    def test_cli_mw_from_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".fasta") as f:
            f.write(">test_seq\nATGCGTACGTTAGC\n")
            fpath = f.name
        try:
            out, err, code = self._run_cli(["mw", "-f", fpath, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual(data["length"], 14)
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    def test_cli_mw_from_stdin(self):
        out, err, code = self._run_cli(["mw", "-s", "-", "--json"], stdin_content="ATGCGTACGTTAGC")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["length"], 14)

    def test_cli_dilute_json(self):
        out, err, code = self._run_cli(["dilute", "-c1", "100 mM", "-c2", "25 mM", "-v2", "16 mL", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["c1"], 100.0)
        self.assertEqual(data["c2"], 25.0)
        self.assertAlmostEqual(data["v1"], 4000.0)  # 4.0 mL = 4000 uL
        self.assertAlmostEqual(data["diluent_needed"], 12000.0)

    def test_cli_ivt_json(self):
        out, err, code = self._run_cli(["ivt", "-s", "GGGAGACCCAAGCUGGCC", "-v", "20 uL", "-y", "40 ug", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["rna_length"], 18)
        self.assertEqual(data["rna_yield_ug"], 40.0)
        self.assertIn("limiting_ntp", data)

    def test_cli_pcr_json(self):
        out, err, code = self._run_cli(["pcr", "-l", "850", "-t", "10 ng", "-c", "30", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["amplicon_length_bp"], 850)
        self.assertEqual(data["cycles_run"], 30)

    def test_cli_protein_json(self):
        prot_seq = "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTFSYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITHGMDELYK"
        out, err, code = self._run_cli(["protein", "-s", prot_seq, "-a", "1.25", "-v", "2.0", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["molecular_weight"] > 20000, True)
        self.assertIn("concentration_mg_ml", data)

    def test_cli_convert_subcommand(self):
        # Human-readable format
        out, err, code = self._run_cli(["convert", "-v", "500 ng", "-t", "pmol", "--mw", "50000"])
        self.assertEqual(code, 0)
        self.assertIn("10.0 pmol", out)

        # JSON format
        out_j, err_j, code_j = self._run_cli(["convert", "-v", "10 uM", "-t", "nM", "--json"])
        self.assertEqual(code_j, 0)
        data = json.loads(out_j)
        self.assertEqual(data["result"], 10000.0)

    def test_cli_batch_csv_subcommand(self):
        csv_text = "id,sequence,type\nseqA,ATGCGTACGTTAGC,dna\nseqB,GGGAGACCCAAGCUGGCC,rna\n"
        with tempfile.TemporaryDirectory() as td:
            in_file = os.path.join(td, "batch_in.csv")
            out_file = os.path.join(td, "batch_out.csv")
            with open(in_file, "w", encoding="utf-8") as f:
                f.write(csv_text)

            out, err, code = self._run_cli(["batch-csv", "-i", in_file, "-o", out_file, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual(data["total_rows"], 2)
            self.assertEqual(data["success_count"], 2)
            self.assertTrue(os.path.exists(out_file))


if __name__ == "__main__":
    unittest.main()
