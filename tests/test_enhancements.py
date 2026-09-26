import unittest
from biolabcalc.units import UnitParser
from biolabcalc.seq_utils import reverse_complement, translate_dna, clean_sequence
from biolabcalc.molecular_weight import calculate_protein_mw
from biolabcalc.spectroscopy import ng_per_ul_to_micromolar, micromolar_to_ng_per_ul
from biolabcalc.protein import calculate_protein_e205, quantify_protein_a205
from biolabcalc.fluorescence import calculate_degree_of_labeling
from biolabcalc.ecoli_growth import calculate_inoculation_volume, calculate_ecoli_growth
from biolabcalc.cloning import are_overhangs_compatible, plan_restriction_digest
from biolabcalc.buffers import calculate_tris_temperature_shift
from biolabcalc.precipitation import calculate_precipitation

class TestEnhancements(unittest.TestCase):
    def test_unit_parser_volume(self):
        self.assertAlmostEqual(UnitParser.parse_volume("500 uL", "ml"), 0.5)
        self.assertAlmostEqual(UnitParser.parse_volume("0.5 mL", "ul"), 500.0)
        self.assertAlmostEqual(UnitParser.parse_volume(200.0, "ul"), 200.0)

    def test_unit_parser_concentration(self):
        self.assertAlmostEqual(UnitParser.parse_concentration("25 mM", "um"), 25000.0)
        self.assertAlmostEqual(UnitParser.parse_concentration("10 uM", "mm"), 0.01)

    def test_unit_parser_mass(self):
        self.assertAlmostEqual(UnitParser.parse_mass("1.5 ug", "ng"), 1500.0)
        self.assertAlmostEqual(UnitParser.parse_mass("500 ng", "ug"), 0.5)

    def test_iupac_complement_symmetry(self):
        # S (C/G) must complement to S (G/C); W (A/T) must complement to W (T/A)
        self.assertEqual(reverse_complement("SS"), "SS")
        self.assertEqual(reverse_complement("WW"), "WW")
        self.assertEqual(reverse_complement("ASW", seq_type="rna"), "WSU")
        self.assertEqual(reverse_complement("ASW", seq_type="dna"), "WST")

    def test_fasta_header_cleaning(self):
        seq_with_header = ">gi|1234567|ref|NC_000001.1| Homo sapiens\nATGCATGC\nATGC"
        cleaned = clean_sequence(seq_with_header)
        self.assertEqual(cleaned, "ATGCATGCATGC")

    def test_translate_dna_reverse_and_to_stop(self):
        dna = "ATGCCTTAA" # Met Pro Stop
        trans_stop = translate_dna(dna, frame=1, to_stop=True)
        self.assertEqual(trans_stop, "MP")
        # Reverse frame
        trans_rev = translate_dna("TTAAGGCAT", frame=-1, to_stop=True) # RevComp: ATGCCTTAA -> MP
        self.assertEqual(trans_rev, "MP")

    def test_protein_mw_stop_codon(self):
        res_no_stop = calculate_protein_mw("MVK")
        res_with_stop = calculate_protein_mw("MVK*")
        self.assertEqual(res_no_stop.average_mw, res_with_stop.average_mw)

    def test_concentration_conversions(self):
        # 1000 ng/µL of 10,000 g/mol protein = 100 µM
        um = ng_per_ul_to_micromolar(1000.0, 10000.0)
        self.assertAlmostEqual(um, 100.0)
        back_ng = micromolar_to_ng_per_ul(100.0, 10000.0)
        self.assertAlmostEqual(back_ng, 1000.0)

    def test_protein_a205_quantification(self):
        # Protein lacking aromatics (e.g. poly-Ala or peptide without W/Y)
        seq = "AAAAAAAAAA" # 10 Alanines
        e205 = calculate_protein_e205(seq)
        self.assertGreater(e205, 0)
        res = quantify_protein_a205(seq, a205_absorbance=0.5, volume_ml=1.0)
        self.assertGreater(res.concentration_mg_ml, 0.0)

    def test_dol_overcorrection_guard(self):
        # When dye absorbance over-corrects A280
        with self.assertRaises(ValueError):
            calculate_degree_of_labeling(
                absorbance_max_dye=2.0, # High dye
                absorbance_280=0.1,    # Low total A280 -> negative corrected A280
                protein_extinction_coeff=20000.0,
                fluorophore_name="FAM",
            )

    def test_ecoli_inoculation_volume(self):
        res = calculate_inoculation_volume(starter_od600=3.0, target_volume_ml=500.0, target_od600=0.05)
        # (0.05 * 500) / 3.0 = 8.333 mL
        self.assertAlmostEqual(res["starter_culture_volume_ml"], 8.333, places=2)
        self.assertAlmostEqual(res["fresh_media_volume_ml"], 491.667, places=2)

    def test_ecoli_temperature_bounds(self):
        with self.assertRaises(ValueError):
            calculate_ecoli_growth(temperature_celsius=5.0) # Below 8°C
        with self.assertRaises(ValueError):
            calculate_ecoli_growth(temperature_celsius=48.0) # Thermal death > 44.5°C

    def test_cloning_overhang_compatibility(self):
        compat, note = are_overhangs_compatible("BamHI", "BglII")
        self.assertTrue(compat)
        self.assertIn("Compatible", note)

    def test_cloning_volume_overflow(self):
        with self.assertRaises(ValueError):
            plan_restriction_digest(
                dna_mass_ug=5.0,
                reaction_volume_ul=20.0,
                dna_conc_ng_ul=50.0, # 5000 ng / 50 = 100 µL DNA in 20 µL rxn!
            )

    def test_tris_temperature_shift(self):
        # pH 8.00 at 25°C should shift to ~8.63 at 4°C
        shifted = calculate_tris_temperature_shift(measured_ph=8.00, measured_temp_c=25.0, target_temp_c=4.0)
        self.assertAlmostEqual(shifted, 8.63, places=1)

    def test_precipitation_volume_warning(self):
        # 500 µL sample + 50 µL salt + 1375 µL ethanol = 1925 µL (>1500 µL)
        res = calculate_precipitation(sample_volume_ul=500.0, alcohol="ethanol")
        self.assertIsNotNone(res.vessel_warning)
        self.assertIn("exceeds standard 1.5 mL", res.vessel_warning)

if __name__ == '__main__':
    unittest.main()
