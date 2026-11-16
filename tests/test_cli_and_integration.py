"""Comprehensive Integration and CLI Dispatch Test Suite for BioLabCalc v0.4.0.

Verifies:
1. CLI subcommands and aliases:
   - 'digest' with -m, -c, --sequence, --plasmid, --simulate-gel.
   - 'mw' with --circular.
   - 'pcr' with -v, -s.
   - 'seq' subcommands: save, list, get.
   - 'plasmid' subcommands: inspect, annotate, digest.
   - 'clone-gene' automated expression cloning subcommand.
   - 'interactive-plasmid' standalone HTML export.
2. High-level Easy API helpers:
   - save_seq, get_seq, load_plasmid, digest_map, clone_gene, codon_opt, plasmid_svg.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Ensure src is on sys.path
_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc import easy
from biolabcalc.cli import main
from biolabcalc.plasmid import STANDARD_PLASMID_CATALOG


class TestCliAndIntegration(unittest.TestCase):
    """Integration test suite covering CLI invocation dispatch and Easy QoL helpers."""

    def _run_cli(self, args_list: list[str]) -> tuple[str, str, int]:
        """Execute CLI main() with captured stdout and stderr."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exit_code = 0

        with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            with patch.object(sys, "argv", ["biolabcalc"] + args_list):
                try:
                    main()
                except SystemExit as e:
                    exit_code = e.code if isinstance(e.code, int) else 0

        return stdout_buf.getvalue(), stderr_buf.getvalue(), exit_code

    # -----------------------------------------------------------------------
    # 1. CLI: digest command upgrades (-m, -c, --sequence, --plasmid, --simulate-gel)
    # -----------------------------------------------------------------------

    def test_cli_digest_aliases_m_and_c(self):
        """Test digest command with -m alias for --dna-ug and -c alias for --dna-conc."""
        out, err, code = self._run_cli([
            "digest", "-m", "1.5", "-c", "100.0", "-e1", "EcoRI", "-e2", "BamHI", "-v", "50"
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("RESTRICTION DIGESTION SETUP", out)
        self.assertIn("EcoRI", out)
        self.assertIn("BamHI", out)
        self.assertIn("Recommended Buffer:", out)

    def test_cli_digest_insilico_plasmid(self):
        """Test digest command with --plasmid flag for in-silico digestion."""
        out, err, code = self._run_cli([
            "digest", "-p", "pUC19", "-e1", "EcoRI", "-e2", "HindIII", "-m", "1.0"
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("IN-SILICO RESTRICTION DIGEST PREDICTION: pUC19", out)
        self.assertIn("Cut Sites Found:      2", out)
        self.assertIn("Fragments Generated:  2", out)
        self.assertIn("Fragment Analysis & Stoichiometry:", out)

    def test_cli_digest_insilico_sequence(self):
        """Test digest command with --sequence / -s flag for custom sequence."""
        custom_seq = "GAATTC" + ("A" * 100) + "GGATCC" + ("C" * 200)
        out, err, code = self._run_cli([
            "digest", "-s", custom_seq, "-e1", "EcoRI", "-e2", "BamHI"
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("IN-SILICO RESTRICTION DIGEST PREDICTION", out)
        self.assertIn("Fragments Generated:  2", out)

    def test_cli_digest_simulate_gel(self):
        """Test digest command with --simulate-gel flag."""
        out, err, code = self._run_cli([
            "digest", "-p", "pUC19", "-e1", "EcoRI", "-e2", "HindIII", "--simulate-gel"
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("Virtual Agarose Gel Migration:", out)
        self.assertIn("Gel Migration Simulation", out)

    # -----------------------------------------------------------------------
    # 2. CLI: mw command with --circular
    # -----------------------------------------------------------------------

    def test_cli_mw_circular(self):
        """Test mw command with --circular flag."""
        seq = "GAATTCGGATCCAAGCTTGC"
        out_lin, _, code_lin = self._run_cli(["mw", "-s", seq, "--ds"])
        self.assertEqual(code_lin, 0)
        out_circ, _, code_circ = self._run_cli(["mw", "-s", seq, "--circular"])
        self.assertEqual(code_circ, 0)
        self.assertIn("Average MW:", out_circ)

    # -----------------------------------------------------------------------
    # 3. CLI: pcr command with -v/--volume and -s/--sequence
    # -----------------------------------------------------------------------

    def test_cli_pcr_with_sequence_and_volume(self):
        """Test pcr command with -s sequence and -v volume."""
        seq = "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGAC"
        out, err, code = self._run_cli([
            "pcr", "-s", seq, "-t", "10 ng", "-v", "25 uL", "-c", "25"
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("PCR KINETICS & REACTION STOICHIOMETRY", out)
        self.assertIn(f"Amplicon Length:            {len(seq)} bp", out)
        self.assertIn("Amplicon Yield:", out)

    # -----------------------------------------------------------------------
    # 4. CLI: seq subcommand (save, list, get)
    # -----------------------------------------------------------------------

    def test_cli_seq_subcommands(self):
        """Test seq subcommand operations: save, list, and get."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_store = tmp.name

        try:
            # 1. Save
            out_s, err_s, code_s = self._run_cli([
                "seq", "save", "-n", "MyTestOligo", "-s", "ATGCGATCGATC", "-t", "dna",
                "-d", "Test oligo description", "--file-path", tmp_store
            ])
            self.assertEqual(code_s, 0, err_s)
            self.assertIn("Saved sequence 'MyTestOligo'", out_s)

            # 2. List
            out_l, err_l, code_l = self._run_cli([
                "seq", "list", "--file-path", tmp_store
            ])
            self.assertEqual(code_l, 0, err_l)
            self.assertIn("MyTestOligo", out_l)

            # 3. Get
            out_g, err_g, code_g = self._run_cli([
                "seq", "get", "-n", "MyTestOligo", "--file-path", tmp_store
            ])
            self.assertEqual(code_g, 0, err_g)
            self.assertIn("SEQUENCE RECORD: MyTestOligo", out_g)
            self.assertIn("ATGCGATCGATC", out_g)
        finally:
            if os.path.exists(tmp_store):
                try:
                    os.remove(tmp_store)
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # 5. CLI: plasmid subcommand (inspect, annotate, digest)
    # -----------------------------------------------------------------------

    def test_cli_plasmid_inspect_and_annotate(self):
        """Test plasmid inspect and annotate subcommands."""
        # Inspect
        out_ins, err_ins, code_ins = self._run_cli([
            "plasmid", "inspect", "-p", "pUC19"
        ])
        self.assertEqual(code_ins, 0, err_ins)
        self.assertIn("PLASMID CONSTRUCT INSPECTOR: pUC19", out_ins)
        self.assertIn("2,686 bp", out_ins)
        self.assertIn("AmpR", out_ins)

        # Annotate
        out_ann, err_ann, code_ann = self._run_cli([
            "plasmid", "annotate", "-p", "pUC19"
        ])
        self.assertEqual(code_ann, 0, err_ann)
        self.assertIn("AUTOMATED PLASMID ANNOTATION: pUC19", out_ann)
        self.assertIn("Features Found:", out_ann)

        # Digest
        out_dig, err_dig, code_dig = self._run_cli([
            "plasmid", "digest", "-p", "pUC19", "-e", "EcoRI,HindIII"
        ])
        self.assertEqual(code_dig, 0, err_dig)
        self.assertIn("PLASMID DIGESTION PREDICTION: pUC19", out_dig)
        self.assertIn("Fragment Count:   2", out_dig)

    # -----------------------------------------------------------------------
    # 6. CLI: clone-gene subcommand
    # -----------------------------------------------------------------------

    def test_cli_clone_gene_subcommand(self):
        """Test clone-gene subcommand cloning EGFP into pET-28a(+)."""
        egfp = (
            "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGAT"
            "GCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTACGGCGTGCAGTGCTTCAGCCGC"
            "TACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAGCGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCC"
            "GAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGCATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGCTGGAGTACAACTACAACAGC"
            "CACAACGTCTATATCATGGCCGACAAGCAGAAGAACGGCATCAAGGTGAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAG"
            "AACACCCCCATCGGCGACGGCCCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTG"
            "GAGTTCGTGACCGCCGCCGGGATCACTCTCGGCATGGACGAGCTGTACAAGTAA"
        )
        with tempfile.NamedTemporaryFile(suffix=".gb", delete=False) as tmp_gb:
            out_gb_path = tmp_gb.name

        try:
            out, err, code = self._run_cli([
                "clone-gene", "-v", "pET-28a(+)", "-i", egfp, "-g", "EGFP",
                "--enzyme5", "BamHI", "--enzyme3", "XhoI", "-o", out_gb_path
            ])
            self.assertEqual(code, 0, err)
            self.assertIn("AUTOMATED GENE EXPRESSION CLONING: EGFP", out)
            self.assertIn("SYNCHRONIZED (IN-FRAME)", out)
            self.assertIn("Saved recombinant construct to GenBank file", out)
            self.assertTrue(os.path.exists(out_gb_path))
        finally:
            if os.path.exists(out_gb_path):
                try:
                    os.remove(out_gb_path)
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # 7. CLI: interactive-plasmid subcommand (--export-html)
    # -----------------------------------------------------------------------

    def test_cli_interactive_plasmid_export(self):
        """Test interactive-plasmid --export-html creates valid standalone HTML5."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_html:
            out_html_path = tmp_html.name

        try:
            out, err, code = self._run_cli([
                "interactive-plasmid", "-p", "pUC19", "--export-html", out_html_path
            ])
            self.assertEqual(code, 0, err)
            self.assertIn("Exported interactive plasmid workbench to:", out)
            self.assertTrue(os.path.exists(out_html_path))
            with open(out_html_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("<svg", content)
            self.assertIn("pUC19", content)
        finally:
            if os.path.exists(out_html_path):
                try:
                    os.remove(out_html_path)
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # 8. Easy API Helpers Verification
    # -----------------------------------------------------------------------

    def test_easy_helpers_full_lifecycle(self):
        """Test all newly added easy helpers in biolabcalc.easy."""
        # 1. save_seq and get_seq
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_store = tmp.name

        try:
            seq_id = easy.save_seq("TargetGene_01", "ATGGCCTTAGCTTAG", "dna", "Test description")
            rec = easy.get_seq(seq_id)
            self.assertEqual(rec.id, "TargetGene_01")
            self.assertEqual(rec.sequence, "ATGGCCTTAGCTTAG")
        finally:
            if os.path.exists(tmp_store):
                try:
                    os.remove(tmp_store)
                except Exception:
                    pass

        # 2. load_plasmid
        puc = easy.load_plasmid("pUC19")
        self.assertEqual(puc.name, "pUC19")
        self.assertEqual(puc.length, 2686)

        # 3. digest_map
        d_res = easy.digest_map("pUC19", ["EcoRI", "HindIII"])
        self.assertEqual(d_res.fragment_count, 2)
        lengths = sorted([f.length_bp for f in d_res.fragments])
        self.assertEqual(lengths, [51, 2635])

        # 4. codon_opt
        opt_seq = easy.codon_opt("ATGAAATTTTAA", host="ecoli")
        self.assertEqual(len(opt_seq), 12)
        self.assertTrue(opt_seq.startswith("ATG"))

        # 5. plasmid_svg
        svg_out = easy.plasmid_svg("pUC19")
        self.assertIn("<svg", svg_out)
        self.assertIn("pUC19", svg_out)

        # 6. clone_gene
        egfp = (
            "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGAT"
            "GCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTACGGCGTGCAGTGCTTCAGCCGC"
            "TACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAGCGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCC"
            "GAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGCATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGCTGGAGTACAACTACAACAGC"
            "CACAACGTCTATATCATGGCCGACAAGCAGAAGAACGGCATCAAGGTGAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAG"
            "AACACCCCCATCGGCGACGGCCCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTG"
            "GAGTTCGTGACCGCCGCCGGGATCACTCTCGGCATGGACGAGCTGTACAAGTAA"
        )
        clone_result = easy.clone_gene(
            vector="pET-28a(+)",
            insert=egfp,
            gene_name="EGFP",
            mode="restriction_ligation",
            enzyme_5="BamHI",
            enzyme_3="XhoI",
        )
        self.assertTrue(clone_result.in_frame)
        self.assertGreater(clone_result.assembled_plasmid.length, 5300)
        self.assertIn("EGFP", [f.name for f in clone_result.assembled_plasmid.features])


if __name__ == "__main__":
    unittest.main()
