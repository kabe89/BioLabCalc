import unittest
from biolabcalc.primers import analyze_primer, design_primers

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

    def test_design_primers(self):
        tmpl = "ATGCCGTCCAGGCTGCTGGTCTTCGACACCGAGACCACTGGGCTGCTGTCGGGCTCGGTGAGCCAGGCCCGCTGGGCCCGGGACCGCTTCAGCCGCGTCGTGCACATCGTGGACCCCA" * 4
        pairs = design_primers(tmpl, min_amplicon_bp=100, max_amplicon_bp=300, max_pairs=3)
        self.assertGreaterEqual(len(pairs), 1)
        p = pairs[0]
        self.assertLessEqual(p.tm_difference, 3.0)
        self.assertGreaterEqual(p.amplicon_length_bp, 100)

if __name__ == '__main__':
    unittest.main()
