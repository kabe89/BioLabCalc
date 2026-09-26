import unittest
from biolabcalc.precipitation import calculate_precipitation

class TestPrecipitation(unittest.TestCase):
    def test_dna_ethanol_naoac(self):
        res = calculate_precipitation(sample_volume_ul=100.0, nucleic_acid="dna", alcohol="ethanol", salt="naoac")
        self.assertEqual(res.sample_volume_ul, 100.0)
        # Salt 0.1 vol = 10 uL
        self.assertEqual(res.salt_volume_ul, 10.0)
        # Alcohol 2.5 * (100 + 10) = 275 uL
        self.assertEqual(res.alcohol_volume_ul, 275.0)
        self.assertEqual(res.centrifugation_time_min, 15)

    def test_rna_isopropanol(self):
        res = calculate_precipitation(sample_volume_ul=200.0, nucleic_acid="rna", alcohol="isopropanol")
        self.assertEqual(res.nucleic_acid_type, "RNA")
        self.assertEqual(res.centrifugation_time_min, 20)

if __name__ == '__main__':
    unittest.main()
