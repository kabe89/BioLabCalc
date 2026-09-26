import unittest
from biolabcalc.gels import simulate_gel, calculate_rf

class TestGels(unittest.TestCase):
    def test_calculate_rf(self):
        rf_large = calculate_rf(10000, 500, 10000)
        rf_small = calculate_rf(500, 500, 10000)
        self.assertLess(rf_large, rf_small)

    def test_simulate_gel(self):
        sim = simulate_gel([750, 2200], ladder_key="1kb_dna")
        self.assertEqual(len(sim.sample_bands), 2)
        self.assertIn("1 kb DNA Ladder", sim.ladder_name)
        self.assertTrue(len(sim.ascii_visualization) > 50)

if __name__ == '__main__':
    unittest.main()
