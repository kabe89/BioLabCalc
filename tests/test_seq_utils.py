import unittest
from biolabcalc.seq_utils import clean_sequence, validate_sequence, reverse_complement, calculate_gc_content, count_bases, translate_dna

class TestSeqUtils(unittest.TestCase):
    def test_clean_sequence(self):
        self.assertEqual(clean_sequence(" atg cga\n123 "), "ATGCGA")
        self.assertEqual(clean_sequence("AUG-cga"), "AUGCGA")

    def test_validate_sequence(self):
        self.assertTrue(validate_sequence("ATGC", "dna"))
        self.assertTrue(validate_sequence("AUGC", "rna"))
        self.assertTrue(validate_sequence("MKWVTFISLL", "protein"))
        self.assertFalse(validate_sequence("ATGCX", "dna"))

    def test_reverse_complement(self):
        self.assertEqual(reverse_complement("ATGC"), "GCAT")
        self.assertEqual(reverse_complement("AUGC", seq_type="rna"), "GCAU")

    def test_calculate_gc_content(self):
        self.assertEqual(calculate_gc_content("ATGC"), 50.0)
        self.assertEqual(calculate_gc_content("GGCC"), 100.0)
        self.assertEqual(calculate_gc_content("AATT"), 0.0)

    def test_translate_dna(self):
        self.assertEqual(translate_dna("ATGAAATTTTAA"), "MKF*")
        self.assertEqual(translate_dna("AATGAAATTTTAA", frame=2), "MKF*")

if __name__ == '__main__':
    unittest.main()
