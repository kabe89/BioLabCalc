import unittest
from biolabcalc.cloning import (
    get_restriction_enzyme,
    plan_restriction_digest,
    calculate_ligation,
    calculate_gibson_assembly,
    calculate_golden_gate_assembly,
)

class TestCloning(unittest.TestCase):
    def test_get_restriction_enzyme(self):
        eco = get_restriction_enzyme("EcoRI")
        self.assertEqual(eco.recognition_site, "G^AATTC")
        self.assertEqual(eco.cut_type, "5' overhang")
        self.assertEqual(eco.overhang_sequence, "AATT")
        self.assertEqual(eco.incubation_temp_celsius, 37)

    def test_plan_restriction_digest(self):
        res = plan_restriction_digest(dna_mass_ug=1.5, enzyme_1="EcoRI", enzyme_2="XhoI", dna_conc_ng_ul=200.0)
        self.assertEqual(res.enzyme_1.name, "EcoRI")
        self.assertEqual(res.enzyme_2.name, "XhoI")
        self.assertEqual(res.recommended_buffer, "1X rCutSmart Buffer")
        self.assertEqual(res.reagent_volumes["DNA Sample"], 7.5)
        self.assertFalse(res.star_activity_warning)

    def test_calculate_ligation(self):
        res = calculate_ligation(vector_length_bp=4000, insert_length_bp=1000, vector_mass_ng=50.0, molar_ratio=3.0)
        # Mass insert = 50 * (1000 / 4000) * 3 = 37.5 ng
        self.assertAlmostEqual(res.insert_mass_ng, 37.5, places=1)
        self.assertGreater(res.vector_pmol, 0.0)
        self.assertGreater(res.insert_pmol, 0.0)

    def test_calculate_gibson_assembly(self):
        res = calculate_gibson_assembly(vector_length_bp=5000, insert_lengths_bp=[1000, 1500], vector_mass_ng=100.0)
        self.assertEqual(len(res.insert_masses_ng), 2)
        # Total pmol between 0.02 and 0.5 pmol
        self.assertTrue(0.02 <= res.total_dna_pmol <= 0.5)

    def test_golden_gate_assembly_digest_temperature(self):
        # Esp3I is a 37°C enzyme
        res_esp3i = calculate_golden_gate_assembly(
            vector_length_bp=4000,
            insert_lengths_bp=[1000],
            type_iis_enzyme="Esp3I",
        )
        self.assertIn("37°C for 3 min", res_esp3i.thermocycling_protocol[0])

        # BsmBI is a 42°C enzyme
        res_bsmbi = calculate_golden_gate_assembly(
            vector_length_bp=4000,
            insert_lengths_bp=[1000],
            type_iis_enzyme="BsmBI-v2",
        )
        self.assertIn("42°C for 3 min", res_bsmbi.thermocycling_protocol[0])

    def test_restriction_digest_buffer_selection(self):
        # Single digest with BsmBI requires NEBuffer r3.1
        res_bsmbi = plan_restriction_digest(dna_mass_ug=1.0, enzyme_1="BsmBI")
        self.assertEqual(res_bsmbi.recommended_buffer, "1X NEBuffer r3.1 Buffer")
        self.assertIn("10X NEBuffer r3.1 Buffer", res_bsmbi.reagent_volumes)

        # Double digest with BsmBI (r3.1) and EcoRI (rCutSmart) selects compatible NEBuffer r3.1
        res_double = plan_restriction_digest(dna_mass_ug=1.0, enzyme_1="EcoRI", enzyme_2="BsmBI")
        self.assertEqual(res_double.recommended_buffer, "1X NEBuffer r3.1 Buffer")
        self.assertIn("10X NEBuffer r3.1 Buffer", res_double.reagent_volumes)

if __name__ == '__main__':
    unittest.main()
