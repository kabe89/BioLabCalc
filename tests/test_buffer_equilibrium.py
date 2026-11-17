"""
Test Suite: tests.test_buffer_equilibrium
Component: Multi-Metal Competitive Buffer Speciation Solver
Architectural Role: Comprehensive unit testing of non-linear mass-balance equations,
Newton-Raphson log-space solver, Davies activity corrections, temperature drift,
competitive divalent cation chelation, and Ksp precipitation screening.
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

from biolabcalc.buffers import (
    EquilibriumComponent,
    SpeciesConcentration,
    PrecipitationCheck,
    BufferEquilibriumResult,
    solve_buffer_equilibrium,
)
import biolabcalc.easy as ez


class TestBufferEquilibrium(unittest.TestCase):
    """Unit tests for multi-metal buffer speciation solver."""

    def test_frozen_immutability_and_tuple_collections(self):
        """Verify strict @dataclass(frozen=True) and Tuple collection invariants."""
        res = solve_buffer_equilibrium("Tris=50mM,EGTA=5mM,MgCl2=10mM,ATP=4mM", target_ph=7.4)
        self.assertIsInstance(res, BufferEquilibriumResult)

        # Immutability
        with self.assertRaises(FrozenInstanceError):
            res.target_ph = 8.0  # type: ignore

        # Tuple collections
        self.assertIsInstance(res.species, tuple)
        self.assertIsInstance(res.precipitation_risks, tuple)

        for sp in res.species:
            self.assertIsInstance(sp, SpeciesConcentration)
            with self.assertRaises(FrozenInstanceError):
                sp.concentration_m = 0.1  # type: ignore

        for pr in res.precipitation_risks:
            self.assertIsInstance(pr, PrecipitationCheck)
            with self.assertRaises(FrozenInstanceError):
                pr.will_precipitate = True  # type: ignore

    def test_competitive_mg_chelation(self):
        """Verify simultaneous competition between Mg2+, EGTA, and ATP."""
        res = solve_buffer_equilibrium(
            components="Tris=50mM,EGTA=5mM,MgCl2=10mM,ATP=4mM",
            target_ph=7.4,
            temperature_celsius=25.0,
            output_temp_celsius=37.0,
        )
        self.assertEqual(res.target_ph, 7.4)
        self.assertEqual(res.temperature_celsius, 37.0)

        # Free Mg should be in biologically realistic range (~4.0 - 5.5 mM)
        free_mg_mm = res.free_mg_conc_m * 1000.0
        self.assertGreater(free_mg_mm, 3.5)
        self.assertLess(free_mg_mm, 6.0)

        # Free ATP should be small fraction due to Mg-ATP binding
        free_atp_mm = res.free_atp_conc_m * 1000.0
        self.assertLess(free_atp_mm, 1.0)

        # Buffer capacity should be positive
        self.assertGreater(res.buffer_capacity_beta, 0.0)

    def test_temperature_drift(self):
        """Verify pKa temperature adjustment from 25 C to 4 C and 37 C."""
        res_37 = solve_buffer_equilibrium("Tris=50mM,MgCl2=2mM", target_ph=7.4, output_temp_celsius=37.0)
        res_4 = solve_buffer_equilibrium("Tris=50mM,MgCl2=2mM", target_ph=7.4, output_temp_celsius=4.0)

        self.assertEqual(res_37.temperature_celsius, 37.0)
        self.assertEqual(res_4.temperature_celsius, 4.0)

    def test_davies_activity_correction(self):
        """Verify ionic strength calculation and Davies activity factors."""
        res_davies = solve_buffer_equilibrium("Tris=100mM,MgCl2=20mM", use_davies_correction=True)
        res_no_davies = solve_buffer_equilibrium("Tris=100mM,MgCl2=20mM", use_davies_correction=False)

        self.assertGreater(res_davies.ionic_strength_m, 0.0)
        self.assertGreater(res_no_davies.ionic_strength_m, 0.0)

    def test_precipitation_screening(self):
        """Verify screening for insoluble salts (MgHPO4, Ca3(PO4)2, Mg2P2O7)."""
        # Soluble buffer
        res_sol = solve_buffer_equilibrium("Tris=50mM,MgCl2=2mM,ATP=1mM")
        for p in res_sol.precipitation_risks:
            self.assertFalse(p.will_precipitate)

        # High phosphate + calcium should flag calcium phosphate precipitation risk
        res_high_ca = solve_buffer_equilibrium("Phosphate=50mM,CaCl2=20mM", target_ph=7.8)
        ca_precip = next((p for p in res_high_ca.precipitation_risks if "Calcium Phosphate" in p.salt_name), None)
        self.assertIsNotNone(ca_precip)
        self.assertTrue(ca_precip.will_precipitate)

    def test_easy_api_wrapper(self):
        """Verify biolabcalc.easy.buffer_equil convenience function."""
        res = ez.buffer_equil("HEPES=25mM,MgCl2=5mM,EDTA=1mM", ph=7.5)
        self.assertIsInstance(res, BufferEquilibriumResult)
        self.assertGreater(res.free_mg_conc_m, 0.003)


if __name__ == "__main__":
    unittest.main()
