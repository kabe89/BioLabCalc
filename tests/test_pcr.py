import unittest
from biolabcalc.pcr import calculate_pcr_kinetics, calculate_qpcr_efficiency, build_master_mix

class TestPCR(unittest.TestCase):
    def test_qpcr_efficiency(self):
        eff, pct = calculate_qpcr_efficiency(-3.322)
        self.assertAlmostEqual(pct, 100.0, delta=0.5)

    def test_pcr_kinetics(self):
        res = calculate_pcr_kinetics(
            amplicon_len_bp=500,
            template_ng=10.0,
            cycles=30,
            efficiency=1.0,
            reaction_volume_ul=50.0,
        )
        self.assertEqual(res.amplicon_length_bp, 500)
        self.assertGreater(res.amplicon_yield_ng, 1000.0)
        self.assertIn(res.limiting_dntp, ("dATP", "dTTP", "dCTP", "dGTP"))
        self.assertIsNotNone(res.dntp_exhaustion_cycle)

    def test_master_mix(self):
        mm = build_master_mix(num_reactions=10, reaction_volume_ul=50.0)
        self.assertEqual(len(mm), 7)
        water_item = mm[0]
        self.assertEqual(water_item.component, "Nuclease-Free Water")
        self.assertGreater(water_item.total_volume_ul, 0)

if __name__ == '__main__':
    unittest.main()
