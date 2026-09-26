import unittest
from biolabcalc.spectroscopy import prepare_standard_solution, calculate_nucleic_acid_e260
from biolabcalc.transcription import calculate_ivt_yield
from biolabcalc.molecular_weight import calculate_rna_mw
from biolabcalc.fluorescence import apply_fluorophore_modification, calculate_degree_of_labeling

class TestCustomRNASequence(unittest.TestCase):
    def setUp(self):
        # Concrete 36 nt RNA sequence
        self.seq_36 = "GGGAGACCCAAGCUGGCCUGUGUGUACAGCCGAAUG"

    def test_custom_rna_mw_and_e260(self):
        # 1. Triphosphorylated (IVT product)
        mw_ppp = calculate_rna_mw(self.seq_36, end_5="triphosphate")
        self.assertEqual(mw_ppp.length, 36)
        self.assertEqual(mw_ppp.base_counts, {"G": 13, "A": 8, "C": 9, "U": 6})
        self.assertAlmostEqual(mw_ppp.average_mw, 11883.03, delta=0.5)

        # 2. Hydroxyl (chemically synthesized oligo)
        mw_oh = calculate_rna_mw(self.seq_36, end_5="hydroxyl")
        self.assertAlmostEqual(mw_oh.average_mw, 11643.09, delta=0.5)

        # 3. Nearest-neighbor extinction coefficient (Puglisi & Tinoco 1989)
        e260 = calculate_nucleic_acid_e260(self.seq_36, seq_type="rna")
        self.assertEqual(e260, 351700)

    def test_custom_rna_nanodrop_prediction_4um_500ul(self):
        # Quadruple checking the exact user scenario: 4 µM ssRNA at 500 µL
        res = prepare_standard_solution(
            target_molarity_um=4.0,
            target_volume_ul=500.0,
            sequence=self.seq_36,
            seq_type="rna",
            end_5="triphosphate",
        )
        # Verify Moles: 4 µM * 500 µL = 2.0 nmol
        self.assertAlmostEqual(res.required_moles_nmol, 2.000, places=3)
        self.assertAlmostEqual(res.required_moles_pmol, 2000.0, places=1)

        # Verify Mass: 2.0 nmol * 11,883.03 g/mol = 23.766 µg
        self.assertAlmostEqual(res.required_mass_ug, 23.766, delta=0.01)
        self.assertAlmostEqual(res.required_mass_ng, 23766.1, delta=10.0)

        # Verify Physical Concentration: 23.766 µg / 500 µL = 47.53 ng/µL
        self.assertAlmostEqual(res.actual_concentration_ng_ul, 47.53, delta=0.05)

        # Verify NanoDrop A260 (10 mm path) via Beer-Lambert:
        # A = e * c * l = 351,700 * 4.0e-6 * 1.0 = 1.407 AU
        self.assertAlmostEqual(res.expected_nanodrop_a260_sequence_specific, 1.407, delta=0.005)

        # Verify NanoDrop physical 1 mm path reading: 1.407 * 0.1 = 0.1407 AU
        self.assertAlmostEqual(res.expected_nanodrop_a260_1mm, 0.1407, delta=0.001)

        # Verify Standard NanoDrop RNA-40 Mode Display:
        # NanoDrop reads A260 = 1.407, multiplies by 40 = 56.28 ng/µL
        self.assertAlmostEqual(res.expected_nanodrop_display_ng_ul_generic_mode, 56.28, delta=0.1)

        # Sequence-specific conversion factor: MW / e260 * 1000 = 11883.03 / 351700 * 1000 = 33.79 µg/mL/OD
        self.assertAlmostEqual(res.sequence_specific_conversion_factor, 33.79, delta=0.05)

    def test_custom_rna_stock_dilution(self):
        # Diluting from a 200 ng/µL stock solution
        res = prepare_standard_solution(
            target_molarity_um=4.0,
            target_volume_ul=500.0,
            sequence=self.seq_36,
            seq_type="rna",
            end_5="triphosphate",
            stock_conc_ng_ul=200.0,
        )
        # stock_vol = 23766.1 ng / 200.0 ng/µL = 118.83 µL
        self.assertAlmostEqual(res.stock_volume_needed_ul, 118.83, delta=0.1)
        # buffer_vol = 500 - 118.83 = 381.17 µL
        self.assertAlmostEqual(res.buffer_volume_needed_ul, 381.17, delta=0.1)
        self.assertAlmostEqual(res.stock_volume_needed_ul + res.buffer_volume_needed_ul, 500.0, delta=0.01)

    def test_custom_rna_stock_too_dilute(self):
        # Stock concentration 20 ng/µL is lower than target concentration 47.53 ng/µL
        res = prepare_standard_solution(
            target_molarity_um=4.0,
            target_volume_ul=500.0,
            sequence=self.seq_36,
            seq_type="rna",
            stock_conc_ng_ul=20.0,
        )
        self.assertIn("WARNING", res.preparation_instructions)

    def test_custom_rna_ivt_consumption(self):
        # In vitro transcription stoichiometry for this specific sequence
        # Sequence has: 13 G, 8 A, 9 C, 6 U (Total 36)
        ivt = calculate_ivt_yield(
            rna_seq=self.seq_36,
            reaction_volume_ul=20.0,
            measured_yield_ug=50.0,
            atp_mm=5.0, ctp_mm=5.0, gtp_mm=5.0, utp_mm=5.0,
        )
        # Moles synthesized = 50 µg / 11883.03 = 4.208 nmol of RNA
        self.assertAlmostEqual(ivt.rna_yield_pmol, 4207.7, delta=1.0)
        # Limiting base must be G because it is 13/36 = 36% of the transcript!
        self.assertEqual(ivt.limiting_ntp, "GTP")
        # GTP consumed = 4.208 nmol * 13 = 54.70 nmol
        self.assertAlmostEqual(ivt.ntp_consumed_nmol["GTP"], 54.70, delta=0.2)
        # ATP consumed = 4.208 * 8 = 33.66 nmol
        self.assertAlmostEqual(ivt.ntp_consumed_nmol["ATP"], 33.66, delta=0.2)

    def test_custom_rna_fluorophore_labeling(self):
        # Fluorophore addition to this specific RNA
        mw_rna = calculate_rna_mw(self.seq_36, end_5="hydroxyl")
        labeled = apply_fluorophore_modification(mw_rna, ["Cy5"])
        # Cy5 adds 793.0 Da
        self.assertAlmostEqual(labeled.total_modified_mw, mw_rna.average_mw + 793.0, delta=0.5)
        self.assertEqual(labeled.primary_fluorophore.name, "Cy5")

        # Test DOL calculation for this RNA
        e260 = calculate_nucleic_acid_e260(self.seq_36, seq_type="rna")
        dol = calculate_degree_of_labeling(
            absorbance_max_dye=0.80, # Cy5 peak at 650 nm
            absorbance_260=0.60,
            fluorophore_name="Cy5",
            oligo_extinction_coeff=e260,
        )
        self.assertGreater(dol.degree_of_labeling, 0.5)
        self.assertEqual(dol.molecule_type, "Oligonucleotide")

if __name__ == '__main__':
    unittest.main()
