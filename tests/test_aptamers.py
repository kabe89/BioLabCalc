"""
Test Suite: tests.test_aptamers
Component: Subunit-Selective Aptamer & SELEX Thermodynamics Engine
Architectural Role: Comprehensive verification of Turner (2004) nearest-neighbor
RNA secondary structure folding, Dirichlet-smoothed Counter-SELEX enrichment,
and step-down Benjamini-Hochberg FDR adjustments.
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

# Bootstrap sys.path
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from biolabcalc.aptamers import (
    SecondaryStructureThermoResult,
    AptamerCandidateScore,
    SELEXEnrichmentResult,
    evaluate_rna_hairpin_thermo,
    analyze_counter_selex,
)
import biolabcalc.easy as ez


class TestAptamers(unittest.TestCase):
    """Unit tests for aptamers biophysics and Counter-SELEX enrichment."""

    def test_frozen_immutability_and_tuple_collections(self):
        """Verify strict @dataclass(frozen=True) and Tuple collection invariants."""
        thermo = evaluate_rna_hairpin_thermo("GCGAAAACGC")
        self.assertIsInstance(thermo, SecondaryStructureThermoResult)

        with self.assertRaises(FrozenInstanceError):
            thermo.delta_g_37 = -5.0  # type: ignore

        self.assertIsInstance(thermo.stems, tuple)
        self.assertIsInstance(thermo.loops, tuple)

        selex = analyze_counter_selex(
            target_counts={"GCGAAAACGC": 100, "UUUAAA": 5},
            counter_counts={"GCGAAAACGC": 5, "UUUAAA": 80},
        )
        self.assertIsInstance(selex, SELEXEnrichmentResult)

        with self.assertRaises(FrozenInstanceError):
            selex.mean_enrichment = 10.0  # type: ignore

        self.assertIsInstance(selex.top_candidates, tuple)
        for cand in selex.top_candidates:
            self.assertIsInstance(cand, AptamerCandidateScore)
            with self.assertRaises(FrozenInstanceError):
                cand.is_significant = False  # type: ignore

    def test_turner_hairpin_thermodynamics(self):
        """Verify Turner (2004) nearest-neighbor RNA hairpin evaluation."""
        seq = "GCGAAAACGC"
        res = evaluate_rna_hairpin_thermo(seq, temperature_celsius=37.0)

        self.assertEqual(res.sequence, "GCGAAAACGC")
        self.assertEqual(res.structure_dot_bracket, "(((....)))")
        self.assertLess(res.delta_g_37, 0.0)
        self.assertLess(res.delta_h, 0.0)
        self.assertLess(res.delta_s, 0.0)
        self.assertGreater(res.tm_celsius, 20.0)
        self.assertEqual(len(res.stems), 1)
        self.assertEqual(res.stems[0], (1, 10, 3))
        self.assertEqual(res.loops, ("AAAA",))

    def test_counter_selex_enrichment_and_bh_fdr(self):
        """Verify Dirichlet smoothing and Benjamini-Hochberg step-down adjusted p-values."""
        target = {
            "APT_HIGH": 500,
            "APT_MID": 50,
            "APT_BG": 5,
        }
        counter = {
            "APT_HIGH": 10,
            "APT_MID": 40,
            "APT_BG": 100,
        }
        res = analyze_counter_selex(target, counter, alpha_smoothing=1.0, fdr_threshold=0.05)
        self.assertEqual(res.total_candidates, 3)

        # APT_HIGH should be rank 1 and statistically significant
        top_cand = res.top_candidates[0]
        self.assertEqual(top_cand.sequence, "APT_HIGH")
        self.assertGreater(top_cand.fold_enrichment, 10.0)
        self.assertTrue(top_cand.is_significant)
        self.assertLessEqual(top_cand.p_value_adjusted, 0.05)

        # APT_BG should have fold enrichment < 1.0 and not be significant
        bg_cand = next(c for c in res.top_candidates if c.sequence == "APT_BG")
        self.assertLess(bg_cand.fold_enrichment, 1.0)
        self.assertFalse(bg_cand.is_significant)

    def test_easy_aptamer_wrappers(self):
        """Verify biolabcalc.easy aptamer functions."""
        th = ez.hairpin_thermo("GGCCAAAGGCC")
        self.assertIsInstance(th, SecondaryStructureThermoResult)
        self.assertLess(th.delta_g_37, 0.0)

        selex = ez.score_aptamer({"SEQ1": 200}, {"SEQ1": 5})
        self.assertIsInstance(selex, SELEXEnrichmentResult)
        self.assertEqual(len(selex.top_candidates), 1)


if __name__ == "__main__":
    unittest.main()
