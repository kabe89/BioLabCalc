import os
import sys
import unittest

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.cloning import (
    ENZYME_DATABASE,
    RestrictionEnzyme,
    get_restriction_enzyme,
    plan_restriction_digest,
    calculate_ligation,
    calculate_gibson_assembly,
    calculate_golden_gate_assembly,
    are_overhangs_compatible,
)
from biolabcalc.molecular_weight import calculate_dna_mw


class TestCloning(unittest.TestCase):
    def test_get_restriction_enzyme(self):
        eco = get_restriction_enzyme("EcoRI")
        self.assertEqual(eco.recognition_site, "G^AATTC")
        self.assertEqual(eco.cut_type, "5' overhang")
        self.assertEqual(eco.overhang_sequence, "AATT")
        self.assertEqual(eco.incubation_temp_celsius, 37)
        self.assertEqual(eco.recognition_seq_clean, "GAATTC")
        self.assertEqual(eco.cut_offset_top, 1)
        self.assertEqual(eco.cut_offset_bottom, 5)
        self.assertFalse(eco.is_type_iis)
        self.assertEqual(eco.isoschizomers, ())

    def test_expanded_enzyme_database(self):
        # Database must contain 40+ enzymes
        self.assertGreaterEqual(len(ENZYME_DATABASE), 40)

        # Check classic palindromic cutters
        bam = get_restriction_enzyme("BamHI")
        self.assertEqual(bam.recognition_seq_clean, "GGATCC")
        self.assertEqual(bam.cut_offset_top, 1)
        self.assertEqual(bam.cut_offset_bottom, 5)

        # Check blunt cutters
        dpn = get_restriction_enzyme("DpnI")
        self.assertEqual(dpn.cut_type, "blunt")
        self.assertEqual(dpn.cut_offset_top, 2)
        self.assertEqual(dpn.cut_offset_bottom, 2)

        # Check 3' overhang cutter
        kpn = get_restriction_enzyme("KpnI")
        self.assertEqual(kpn.cut_type, "3' overhang")
        self.assertEqual(kpn.cut_offset_top, 5)
        self.assertEqual(kpn.cut_offset_bottom, 1)

        # Check rare 8-base cutters
        not_i = get_restriction_enzyme("NotI")
        self.assertEqual(not_i.recognition_seq_clean, "GCGGCCGC")
        pac = get_restriction_enzyme("PacI")
        self.assertEqual(pac.cut_type, "3' overhang")

        # Check Type IIS enzymes
        bsa = get_restriction_enzyme("BsaI-HFv2")
        self.assertTrue(bsa.is_type_iis)
        self.assertEqual(bsa.recognition_seq_clean, "GGTCTC")
        self.assertEqual(bsa.cut_offset_top, 7)
        self.assertEqual(bsa.cut_offset_bottom, 11)

        bsm = get_restriction_enzyme("BsmBI-v2")
        self.assertTrue(bsm.is_type_iis)
        self.assertEqual(bsm.incubation_temp_celsius, 42)

        paq = get_restriction_enzyme("PaqCI")
        self.assertTrue(paq.is_type_iis)
        self.assertEqual(paq.cut_offset_top, 11)
        self.assertEqual(paq.cut_offset_bottom, 15)

    def test_are_overhangs_compatible_bug06(self):
        # Blunt ends are compatible
        compat, msg = are_overhangs_compatible("EcoRV", "SmaI")
        self.assertTrue(compat)
        self.assertIn("blunt", msg.lower())

        # Incompatible cut types (5' overhang vs blunt)
        compat, msg = are_overhangs_compatible("EcoRI", "EcoRV")
        self.assertFalse(compat)
        self.assertIn("incompatible cut types", msg.lower())

        # Compatible classic sticky ends (BamHI and BglII both generate GATC 5' overhang)
        compat, msg = are_overhangs_compatible("BamHI", "BglII")
        self.assertTrue(compat)
        self.assertIn("identical", msg.lower())

        # Type IIS enzymes without explicit overhangs must NOT return True just for NNNN
        compat, msg = are_overhangs_compatible("BsaI-HFv2", "BsmBI-v2")
        self.assertFalse(compat)
        self.assertIn("variable overhangs", msg)

        # Type IIS enzymes with matching explicit overhangs
        compat, msg = are_overhangs_compatible("BsaI-HFv2", "BsmBI-v2", overhang_1="AGTC", overhang_2="AGTC")
        self.assertTrue(compat)
        self.assertIn("identical", msg.lower())

        # Type IIS with complementary overhangs
        compat, msg = are_overhangs_compatible("BsaI-HFv2", "BsaI-HFv2", overhang_1="ATCC", overhang_2="GGAT")
        self.assertTrue(compat)
        self.assertIn("complementary", msg.lower())

        # Type IIS with mismatching overhangs
        compat, msg = are_overhangs_compatible("BsaI-HFv2", "BsaI-HFv2", overhang_1="ATCC", overhang_2="TGCA")
        self.assertFalse(compat)
        self.assertIn("incompatible overhangs", msg.lower())

        # Incompatible overhang lengths
        compat, msg = are_overhangs_compatible("SapI", "BsaI-HFv2", overhang_1="ATC", overhang_2="ATCC")
        self.assertFalse(compat)
        self.assertIn("lengths", msg.lower())

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

        # Verify MW route consistency (BUG-07)
        expected_vec_mw = calculate_dna_mw(length=4000, double_stranded=True).average_mw
        expected_vec_pmol = (50.0 * 1e-9 / expected_vec_mw) * 1e12
        self.assertAlmostEqual(res.vector_pmol, expected_vec_pmol, places=3)

    def test_calculate_gibson_assembly(self):
        res = calculate_gibson_assembly(vector_length_bp=5000, insert_lengths_bp=[1000, 1500], vector_mass_ng=100.0)
        self.assertEqual(len(res.insert_masses_ng), 2)
        # Total pmol between 0.02 and 0.5 pmol
        self.assertTrue(0.02 <= res.total_dna_pmol <= 0.5)

        # Verify MW calculation consistency (BUG-07)
        expected_vec_mw = calculate_dna_mw(length=5000, double_stranded=True).average_mw
        expected_vec_pmol = (100.0 * 1e-9 / expected_vec_mw) * 1e12
        expected_ins1_mw = calculate_dna_mw(length=1000, double_stranded=True).average_mw
        expected_ins1_pmol = (res.insert_masses_ng[0] * 1e-9 / expected_ins1_mw) * 1e12
        self.assertAlmostEqual(res.total_dna_pmol, expected_vec_pmol + expected_ins1_pmol + (res.insert_masses_ng[1] * 1e-9 / calculate_dna_mw(length=1500, double_stranded=True).average_mw) * 1e12, places=2)

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

    def test_volume_overflow_checks_bug08(self):
        # Ligation volume overflow
        with self.assertRaises(ValueError) as ctx:
            calculate_ligation(
                vector_length_bp=4000,
                insert_length_bp=1000,
                vector_mass_ng=500.0,
                vector_conc_ng_ul=10.0,  # 50 µL vector alone in 20 µL rxn!
                reaction_volume_ul=20.0,
            )
        self.assertIn("Volume overflow", str(ctx.exception))

        # Gibson volume overflow
        with self.assertRaises(ValueError) as ctx:
            calculate_gibson_assembly(
                vector_length_bp=5000,
                insert_lengths_bp=[1000, 2000],
                vector_mass_ng=500.0,
                vector_conc_ng_ul=10.0,  # 50 µL vector alone in 20 µL rxn!
                reaction_volume_ul=20.0,
            )
        self.assertIn("Volume overflow", str(ctx.exception))

        # Golden Gate volume overflow
        with self.assertRaises(ValueError) as ctx:
            calculate_golden_gate_assembly(
                vector_length_bp=4000,
                insert_lengths_bp=[1000, 2000],
                vector_mass_ng=1000.0,
                vector_conc_ng_ul=10.0,  # 100 µL vector alone in 20 µL rxn!
                reaction_volume_ul=20.0,
            )
        self.assertIn("Volume overflow", str(ctx.exception))

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
