"""
Tests for Jupyter Rich Representations (_repr_html_ and _repr_svg_)
"""

import os
import sys
import unittest

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.buffers import calculate_buffer_recipe, solve_buffer_equilibrium
from biolabcalc.easy import pcr
from biolabcalc.gels import simulate_gel
from biolabcalc.molecular_weight import calculate_dna_mw
from biolabcalc.plasmid import get_plasmid
from biolabcalc.plasmid_engineering import engineer_expression_plasmid
from biolabcalc.primers import analyze_primer, design_primers
from biolabcalc.restriction_engine import predict_restriction_digest
from biolabcalc.transcription import calculate_ivt_yield


class TestRichRepresentations(unittest.TestCase):
    def test_plasmid_repr_svg(self):
        plasmid = get_plasmid("pUC19")
        svg_str = plasmid._repr_svg_()
        self.assertIsInstance(svg_str, str)
        self.assertTrue(svg_str.strip().startswith("<svg"))
        self.assertTrue(svg_str.strip().endswith("</svg>"))
        self.assertIn("pUC19", svg_str)

    def test_gel_lane_simulation_repr_svg(self):
        sim = simulate_gel([1000, 2500, 5000], ladder_key="1kb_dna")
        svg_str = sim._repr_svg_()
        self.assertIsInstance(svg_str, str)
        self.assertTrue(svg_str.strip().startswith("<svg"))
        self.assertTrue(svg_str.strip().endswith("</svg>"))
        self.assertIn("1 kb DNA Ladder", svg_str)

    def test_molecular_weight_repr_html(self):
        res = calculate_dna_mw("ATGCGATCGATC")
        html_str = res._repr_html_()
        self.assertIsInstance(html_str, str)
        self.assertIn("Molecular Weight Analysis", html_str)
        self.assertIn("Average MW", html_str)

    def test_ivt_repr_html(self):
        res = calculate_ivt_yield(
            rna_seq="GGGAGACCCAAACCCGGG",
            reaction_volume_ul=20.0,
        )
        html_str = res._repr_html_()
        self.assertIsInstance(html_str, str)
        self.assertIn("IVT Yield & Efficiency", html_str)
        self.assertIn("Limiting NTP", html_str)

    def test_pcr_repr_html(self):
        res = pcr(
            amplicon_bp=500,
            template_ng=1.0,
            cycles=30,
        )
        html_str = res._repr_html_()
        self.assertIsInstance(html_str, str)
        self.assertIn("PCR Amplification Yield", html_str)
        self.assertIn("500 bp", html_str)

    def test_primer_analysis_and_pair_repr_html(self):
        pa = analyze_primer("GTAAAACGACGGCCAGT")
        html_pa = pa._repr_html_()
        self.assertIsInstance(html_pa, str)
        self.assertIn("Primer Analysis", html_pa)

        template = "ATGCCGTCCAGGCTGCTGGTCTTCGACACCGAGACCACTGGGCTGCTGTCGGGCTCGGTGAGCCAGGCCCGCTGGGCCCGGGACCGCTTCAGCCGCGTCGTGCACATCGTGGACCCCA" * 4
        pairs = design_primers(template, min_amplicon_bp=100, max_amplicon_bp=300, max_pairs=1)
        self.assertGreaterEqual(len(pairs), 1)
        html_pair = pairs[0]._repr_html_()
        self.assertIsInstance(html_pair, str)
        self.assertIn("PCR Primer Pair", html_pair)

    def test_buffer_repr_html(self):
        rec = calculate_buffer_recipe("10X_PBS", target_volume_ml=500)
        html_rec = rec._repr_html_()
        self.assertIsInstance(html_rec, str)
        self.assertIn("PBS", html_rec)

        equil = solve_buffer_equilibrium(
            components=[("Tris", 0.05), ("MgCl2", 0.01)],
            target_ph=7.5,
        )
        html_eq = equil._repr_html_()
        self.assertIsInstance(html_eq, str)
        self.assertIn("Multi-Metal Buffer Speciation", html_eq)

    def test_restriction_and_engineered_repr_html(self):
        plasmid = get_plasmid("pUC19")
        digest = predict_restriction_digest(plasmid, ["EcoRI", "BamHI"])
        html_dig = digest._repr_html_()
        self.assertIsInstance(html_dig, str)
        self.assertIn("Digest: pUC19", html_dig)

        eng = engineer_expression_plasmid(
            vector="pUC19",
            insert_seq="ATGAAGAAAACCGCCATCGCCATTGCCGTGGCCCTGGCCGGGTTTGCCACCGTCGCCCAGGCCTAA",
            gene_name="SignalPeptideTarget",
            mode="restriction_ligation",
            enzyme_5prime="EcoRI",
            enzyme_3prime="BamHI",
        )
        html_eng = eng._repr_html_()
        self.assertIsInstance(html_eng, str)
        self.assertIn("Engineered Plasmid", html_eng)


if __name__ == "__main__":
    unittest.main()
