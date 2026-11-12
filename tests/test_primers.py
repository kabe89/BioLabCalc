import unittest
from biolabcalc.primers import (
    analyze_primer,
    design_primers,
    calculate_tm_santalucia,
    calculate_tm_santaluicia,
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

if __name__ == '__main__':
    unittest.main()
