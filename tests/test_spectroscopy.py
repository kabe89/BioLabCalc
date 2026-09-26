import unittest
from biolabcalc.spectroscopy import prepare_standard_solution

class TestSpectroscopy(unittest.TestCase):
    def test_prepare_standard_solution_rna(self):
        # 4 µM of ssRNA at 500 µL
        res = prepare_standard_solution(
            target_molarity_um=4.0,
            target_volume_ul=500.0,
            seq_type="rna",
            rna_length_nt=36,
        )
        # 4 µM in 500 µL = 2.0 nmol = 2000 pmol
        self.assertAlmostEqual(res.required_moles_nmol, 2.0, places=2)
        self.assertAlmostEqual(res.required_moles_pmol, 2000.0, places=1)
        self.assertGreater(res.required_mass_ug, 20.0)
        self.assertGreater(res.actual_concentration_ng_ul, 0.0)
        self.assertAlmostEqual(res.expected_a260_a280_ratio, 2.00, places=2)

    def test_prepare_with_stock_dilution(self):
        res = prepare_standard_solution(
            target_molarity_um=2.0,
            target_volume_ul=100.0,
            seq_type="dsdna",
            rna_length_nt=500,
            stock_conc_ng_ul=1000.0,
        )
        self.assertIsNotNone(res.stock_volume_needed_ul)
        self.assertIsNotNone(res.buffer_volume_needed_ul)
        self.assertAlmostEqual(res.stock_volume_needed_ul + res.buffer_volume_needed_ul, 100.0, places=1)


    def test_invalid_molarity_volume(self):
        with self.assertRaises(ValueError):
            prepare_standard_solution(target_molarity_um=-2.0, target_volume_ul=100.0)
        with self.assertRaises(ValueError):
            prepare_standard_solution(target_molarity_um=2.0, target_volume_ul=-50.0)

if __name__ == '__main__':
    unittest.main()
