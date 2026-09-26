import unittest
from biolabcalc.ecoli_growth import calculate_ecoli_growth, estimate_plasmid_yield, optimize_protein_induction

class TestEcoliGrowth(unittest.TestCase):
    def test_growth_kinetics(self):
        res = calculate_ecoli_growth(initial_od600=0.05, target_od600=0.60, temperature_celsius=37.0, media="LB")
        # log2(0.60 / 0.05) = log2(12) ≈ 3.58 doublings * 20 min ≈ 71.7 min ≈ 1h 12m
        self.assertAlmostEqual(res.num_doublings, 3.58, delta=0.1)
        self.assertAlmostEqual(res.hours_to_target_od, 1.2, delta=0.2)

    def test_plasmid_yield(self):
        res = estimate_plasmid_yield(culture_volume_ml=5.0, final_od600=3.0, plasmid_type="pUC")
        self.assertGreater(res.typical_miniprep_yield_ug, 10.0)

    def test_protein_induction(self):
        res = optimize_protein_induction(protein_mw_da=35000, culture_volume_ml=1000.0, final_od600=4.0)
        self.assertGreater(res.recombinant_protein_yield_mg, 50.0)
        self.assertIn("37°C", res.recommended_conditions)


    def test_temperature_scaling(self):
        # 33°C is between 30°C (35 min) and 37°C (20 min)
        res_33 = calculate_ecoli_growth(initial_od600=0.05, target_od600=0.60, temperature_celsius=33.0, media="LB")
        self.assertGreater(res_33.doubling_time_min, 20.0)
        self.assertLess(res_33.doubling_time_min, 35.0)

if __name__ == '__main__':
    unittest.main()
