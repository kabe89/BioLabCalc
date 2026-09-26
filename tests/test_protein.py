import unittest
from biolabcalc.protein import calculate_extinction_coefficient, quantify_protein_a280, fit_standard_curve

class TestProtein(unittest.TestCase):
    def test_extinction_coefficient(self):
        # 1 Trp (5500) + 1 Tyr (1490) = 6990
        res = calculate_extinction_coefficient("MWY")
        self.assertEqual(res.extinction_coeff_m_cm, 6990)
        self.assertEqual(res.tryptophan_count, 1)
        self.assertEqual(res.tyrosine_count, 1)

    def test_quantify_a280(self):
        res = quantify_protein_a280("MWY", a280_absorbance=0.699, volume_ml=2.0)
        # c (M) = 0.699 / 6990 = 0.0001 M = 100 µM
        self.assertAlmostEqual(res.molarity_um, 100.0, places=1)
        self.assertGreater(res.total_yield_mg, 0.0)

    def test_standard_curve(self):
        stds = [(0, 0.0), (100, 0.2), (200, 0.4), (400, 0.8)]
        curve = fit_standard_curve(stds, assay_type="BCA")
        self.assertAlmostEqual(curve.r_squared, 1.0, places=2)
        pred = curve.predict(0.6, volume_ml=1.0)
        self.assertAlmostEqual(pred.concentration_ug_ml, 300.0, delta=5.0)

if __name__ == '__main__':
    unittest.main()
