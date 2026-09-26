import unittest
from biolabcalc.fluorescence import get_fluorophore, apply_fluorophore_modification, calculate_degree_of_labeling
from biolabcalc.molecular_weight import calculate_dna_mw

class TestFluorescence(unittest.TestCase):
    def test_get_fluorophore(self):
        fl = get_fluorophore("FAM")
        self.assertEqual(fl.excitation_max_nm, 495)
        self.assertEqual(fl.emission_max_nm, 520)
        self.assertEqual(fl.cf260, 0.30)

        fl_cy5 = get_fluorophore("Cy5")
        self.assertEqual(fl_cy5.excitation_max_nm, 650)

    def test_apply_fluorophore_modification(self):
        dna = calculate_dna_mw("ATGC")
        mod = apply_fluorophore_modification(dna, ["FAM", "BHQ1"])
        self.assertAlmostEqual(mod.total_added_mw, 537.5 + 518.5, delta=0.5)
        self.assertAlmostEqual(mod.total_modified_mw, dna.average_mw + 537.5 + 518.5, delta=0.5)

    def test_degree_of_labeling(self):
        dol_res = calculate_degree_of_labeling(
            absorbance_max_dye=0.75,
            absorbance_280=1.10,
            fluorophore_name="FAM",
            protein_extinction_coeff=45000,
        )
        self.assertGreater(dol_res.degree_of_labeling, 0.0)
        self.assertEqual(dol_res.molecule_type, "Protein")

if __name__ == '__main__':
    unittest.main()
