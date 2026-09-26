import unittest
from biolabcalc.molecular_weight import (
    calculate_dna_mw, calculate_rna_mw, calculate_protein_mw,
    mass_to_moles, moles_to_mass, mass_to_copy_number, copy_number_to_mass, concentration_to_molarity
)

class TestMolecularWeight(unittest.TestCase):
    def test_dna_mw(self):
        res = calculate_dna_mw("ATGC", double_stranded=False)
        self.assertEqual(res.length, 4)
        self.assertAlmostEqual(res.average_mw, 1173.84, delta=0.5)

        res_ds = calculate_dna_mw("ATGC", double_stranded=True)
        self.assertGreater(res_ds.average_mw, res.average_mw * 1.9)

    def test_rna_mw(self):
        res = calculate_rna_mw("AUGC", end_5="triphosphate")
        self.assertEqual(res.seq_type, "RNA")
        self.assertAlmostEqual(res.average_mw, 1463.75, delta=0.5)

    def test_protein_mw(self):
        res = calculate_protein_mw("ACDEF")
        self.assertAlmostEqual(res.average_mw, 583.62, delta=0.5)

    def test_molar_conversions(self):
        val, unit = mass_to_moles(1.0, "ug", 1000.0)
        self.assertEqual(unit, "nmol")
        self.assertAlmostEqual(val, 1.0, places=3)

        m_val, m_unit = moles_to_mass(1.0, "nmol", 1000.0)
        self.assertEqual(m_unit, "µg")
        self.assertAlmostEqual(m_val, 1.0, places=3)

    def test_copy_number(self):
        copies = mass_to_copy_number(1.0, "ng", 300000.0)
        self.assertGreater(copies, 1e9)
        ng = copy_number_to_mass(copies, 300000.0, target_unit="ng")
        self.assertAlmostEqual(ng, 1.0, places=4)

if __name__ == '__main__':
    unittest.main()
