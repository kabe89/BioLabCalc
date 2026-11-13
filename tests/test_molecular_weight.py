import os
import sys
import unittest

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

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

    def test_protein_mw_disulfide_clamping(self):
        # Sequence has 2 cysteines -> max 1 disulfide bond
        res_reduced = calculate_protein_mw("ACDEFCA", oxidized_cysteines=0)
        res_oxidized = calculate_protein_mw("ACDEFCA", oxidized_cysteines=2)
        self.assertAlmostEqual(res_reduced.average_mw - res_oxidized.average_mw, 2.016, delta=0.02)
        self.assertAlmostEqual(res_reduced.monoisotopic_mw - res_oxidized.monoisotopic_mw, 2.01565, places=3)

        # Clamping: requesting 10 oxidized cysteines when sequence only has 2 should yield same as 2
        res_clamped = calculate_protein_mw("ACDEFCA", oxidized_cysteines=10)
        self.assertEqual(res_clamped.average_mw, res_oxidized.average_mw)

        # Sequence with 0 cysteines
        res_no_cys = calculate_protein_mw("ADEFA", oxidized_cysteines=4)
        res_no_cys_base = calculate_protein_mw("ADEFA", oxidized_cysteines=0)
        self.assertEqual(res_no_cys.average_mw, res_no_cys_base.average_mw)

        # Negative oxidized cysteines should be treated as 0
        res_neg = calculate_protein_mw("ACDEFCA", oxidized_cysteines=-2)
        self.assertEqual(res_neg.average_mw, res_reduced.average_mw)

    def test_stoichiometry_mw_validation(self):
        with self.assertRaises(ValueError):
            mass_to_copy_number(1.0, "ng", mw=0.0)
        with self.assertRaises(ValueError):
            mass_to_copy_number(1.0, "ng", mw=-500.0)

        with self.assertRaises(ValueError):
            concentration_to_molarity(10.0, "ng/ul", mw=0.0)
        with self.assertRaises(ValueError):
            concentration_to_molarity(10.0, "ng/ul", mw=-100.0)

    def test_copy_number_to_mass_unit_validation(self):
        with self.assertRaises(ValueError):
            copy_number_to_mass(1e9, 50000.0, target_unit="unknown_unit")
        valid_res = copy_number_to_mass(1e9, 50000.0, target_unit="ug")
        self.assertGreater(valid_res, 0)

if __name__ == '__main__':
    unittest.main()
