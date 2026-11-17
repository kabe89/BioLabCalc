"""
Tests for Type IIS Golden Gate Overhang Fidelity Engine
"""

import os
import sys
import unittest
from dataclasses import FrozenInstanceError

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.cloning import (
    GoldenGateFidelityResult,
    evaluate_golden_gate_fidelity,
    recommend_golden_gate_overhangs,
)


class TestGoldenGateFidelity(unittest.TestCase):
    def test_orthogonal_moclo_overhangs(self):
        # MoClo standard overhangs (GGAG, TACT, AATG, GCTT)
        ohs = ("GGAG", "TACT", "AATG", "GCTT")
        res = evaluate_golden_gate_fidelity(ohs, enzyme="BsaI-HFv2")

        self.assertIsInstance(res, GoldenGateFidelityResult)
        self.assertGreaterEqual(res.assembly_fidelity_percent, 90.0)
        self.assertEqual(len(res.palindromic_overhangs), 0)
        self.assertEqual(len(res.collision_pairs), 0)
        self.assertIsInstance(res.overhangs, tuple)
        self.assertIsInstance(res.collision_pairs, tuple)
        self.assertIsInstance(res.palindromic_overhangs, tuple)
        self.assertIsInstance(res.mismatch_risks, tuple)
        self.assertIsInstance(res.recommended_overhangs, tuple)

    def test_palindromic_overhang_detection(self):
        # AATT is a self-complementary palindrome (AATT -> TTAA -> rc is AATT)
        ohs = ("AATT", "GGAG")
        res = evaluate_golden_gate_fidelity(ohs)

        self.assertIn("AATT", res.palindromic_overhangs)
        self.assertLess(res.assembly_fidelity_percent, 80.0)

    def test_reverse_complement_collision(self):
        # GGAG and CTCC are reverse complements
        ohs = ("GGAG", "CTCC")
        res = evaluate_golden_gate_fidelity(ohs)

        self.assertEqual(len(res.collision_pairs), 1)
        self.assertEqual(res.collision_pairs[0], ("GGAG", "CTCC"))
        self.assertLess(res.assembly_fidelity_percent, 70.0)

    def test_recommend_overhangs(self):
        recs = recommend_golden_gate_overhangs(5)
        self.assertIsInstance(recs, tuple)
        self.assertEqual(len(recs), 5)
        self.assertEqual(recs[0], "GGAG")
        self.assertEqual(recs[1], "TACT")

    def test_frozen_immutability(self):
        res = evaluate_golden_gate_fidelity(["GGAG", "TACT"])
        with self.assertRaises(FrozenInstanceError):
            res.enzyme = "Esp3I"
        with self.assertRaises(FrozenInstanceError):
            res.assembly_fidelity_percent = 99.9


if __name__ == "__main__":
    unittest.main()
