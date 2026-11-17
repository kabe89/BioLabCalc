import os
import sys
import unittest

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from dataclasses import FrozenInstanceError

from biolabcalc.primers import (
    analyze_primer,
    design_primers,
    calculate_tm_santalucia,
    calculate_tm_santaluicia,
    calculate_dimer_dg,
    calculate_hairpin_dg,
)

class TestPrimers(unittest.TestCase):
    def test_analyze_primer(self):
        res = analyze_primer("GTAAAACGACGGCCAGT")
        self.assertEqual(res.length, 17)
        self.assertGreater(res.tm_celsius, 50.0)
        self.assertTrue(res.has_gc_clamp)
        self.assertGreater(res.quality_score, 50.0)

        # High dimer primer gets lower score
        p_dimer = analyze_primer("ATGCCGTCCAGGCTGCTGGTC")
        self.assertLess(p_dimer.quality_score, 50.0)

    def test_calculate_tm_santalucia_spelling_and_excess(self):
        seq = "GTAAAACGACGGCCAGT"
        tm_lucia, dh1, ds1, dg1 = calculate_tm_santalucia(seq)
        tm_alias, dh2, ds2, dg2 = calculate_tm_santaluicia(seq)
        self.assertEqual(tm_lucia, tm_alias)
        self.assertEqual(dh1, dh2)
        self.assertEqual(ds1, ds2)
        self.assertEqual(dg1, dg2)

        # Excess primer (default True, x=1.0) vs equimolar (False, x=4.0)
        tm_excess, _, _, _ = calculate_tm_santalucia(seq, is_excess_primer=True)
        tm_equimolar, _, _, _ = calculate_tm_santalucia(seq, is_excess_primer=False)
        self.assertEqual(tm_lucia, tm_excess)
        self.assertGreater(tm_excess, tm_equimolar)

    def test_design_primers(self):
        tmpl = "ATGCCGTCCAGGCTGCTGGTCTTCGACACCGAGACCACTGGGCTGCTGTCGGGCTCGGTGAGCCAGGCCCGCTGGGCCCGGGACCGCTTCAGCCGCGTCGTGCACATCGTGGACCCCA" * 4
        pairs = design_primers(tmpl, min_amplicon_bp=100, max_amplicon_bp=300, max_pairs=3)
        self.assertGreaterEqual(len(pairs), 1)
        p = pairs[0]
        self.assertLessEqual(p.tm_difference, 3.0)
        self.assertGreaterEqual(p.amplicon_length_bp, 100)
        self.assertIsInstance(p.heterodimer_dg_kcal, float)

    def test_thermodynamic_dimer_and_hairpin(self):
        seq1 = "ATGCCGTCCAGGCTGCTGGTC"
        seq2 = "GTAAAACGACGGCCAGT"
        dg, align, tp_dg = calculate_dimer_dg(seq1, seq2)
        self.assertIsInstance(dg, float)
        self.assertIsInstance(align, str)
        self.assertIn("5'", align)
        self.assertIn("3'", align)
        self.assertIsInstance(tp_dg, float)

        h_dg, struct_str = calculate_hairpin_dg("CGCGAAACGCG")
        self.assertIsInstance(h_dg, float)
        self.assertIsInstance(struct_str, str)

        res = analyze_primer(seq1)
        self.assertIsInstance(res.self_dimer_dg_kcal, float)
        self.assertIsInstance(res.hairpin_dg_kcal, float)
        self.assertIsInstance(res.three_prime_dg_kcal, float)
        self.assertIsInstance(res.alignment_ascii, str)

    def test_frozen_immutability(self):
        res = analyze_primer("GTAAAACGACGGCCAGT")
        with self.assertRaises(FrozenInstanceError):
            res.length = 99
        with self.assertRaises(FrozenInstanceError):
            res.self_dimer_dg_kcal = -100.0

if __name__ == '__main__':
    unittest.main()
