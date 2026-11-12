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

    def test_get_fluorophore_multiword_and_normalized(self):
        af488 = get_fluorophore("Alexa Fluor 488")
        self.assertEqual(af488.name, "Alexa Fluor 488")
        self.assertEqual(af488.excitation_max_nm, 495)

        af488_alias = get_fluorophore("AF488")
        self.assertEqual(af488_alias.name, "Alexa Fluor 488")

        af488_hyphen = get_fluorophore("alexa-fluor-488")
        self.assertEqual(af488_hyphen.name, "Alexa Fluor 488")

        texas = get_fluorophore("Texas Red")
        self.assertEqual(texas.common_name, "Texas Red")
        self.assertEqual(texas.excitation_max_nm, 596)

        bhq1 = get_fluorophore("Black Hole Quencher 1")
        self.assertEqual(bhq1.name, "Black Hole Quencher 1")
        self.assertEqual(bhq1.common_name, "BHQ-1")

        with self.assertRaises(KeyError):
            get_fluorophore("Unknown_Fluorophore_999")

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
