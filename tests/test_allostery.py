"""
Test Suite: tests.test_allostery
Component: Deterministic Allosteric Pathway Tracer & GNM Cross-Correlation Engine
Architectural Role: Comprehensive verification of pure-Python PDB parsing, GNM Kirchhoff
Laplacian computation, Jacobi eigenvalue decomposition, Yen's K-shortest communication routes,
PRS effector/sensor profiling, and automated site-directed mutagenesis primer generation.
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

from biolabcalc.allostery import (
    ResidueNode,
    AllostericPath,
    AllostericNetworkResult,
    parse_pdb_ca_coordinates,
    trace_allosteric_paths,
)
from biolabcalc.plasmid import get_plasmid
from biolabcalc.plasmid_engineering import generate_allosteric_mutagenesis_primers
from biolabcalc.primers import PrimerPair
import biolabcalc.easy as ez

SAMPLE_PDB = """
ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 20.00           C
ATOM      2  CA  GLY A   2      13.800  10.000  10.000  1.00 20.00           C
ATOM      3  CA  VAL A   3      17.600  10.000  10.000  1.00 20.00           C
ATOM      4  CA  LEU A   4      21.400  10.000  10.000  1.00 20.00           C
ATOM      5  CA  PHE A   5      25.200  10.000  10.000  1.00 20.00           C
ATOM      6  CA  ASP A   6      29.000  10.000  10.000  1.00 20.00           C
"""


class TestAllostery(unittest.TestCase):
    """Unit tests for allosteric pathway tracing and GNM network modeling."""

    def test_frozen_immutability_and_tuple_collections(self):
        """Verify strict @dataclass(frozen=True) and Tuple collection invariants."""
        res = trace_allosteric_paths(SAMPLE_PDB, source_resid=1, sink_resid=6, cutoff_angstroms=4.5, k_paths=2)
        self.assertIsInstance(res, AllostericNetworkResult)

        with self.assertRaises(FrozenInstanceError):
            res.source_resid = 2  # type: ignore

        self.assertIsInstance(res.paths, tuple)
        self.assertIsInstance(res.hotspot_residues, tuple)
        self.assertIsInstance(res.prs_effectors, tuple)
        self.assertIsInstance(res.prs_sensors, tuple)
        self.assertIsInstance(res.nodes, tuple)

        for p in res.paths:
            self.assertIsInstance(p, AllostericPath)
            self.assertIsInstance(p.path_residues, tuple)
            with self.assertRaises(FrozenInstanceError):
                p.total_cost = 0.0  # type: ignore

        for n in res.nodes:
            self.assertIsInstance(n, ResidueNode)
            with self.assertRaises(FrozenInstanceError):
                n.x = 99.0  # type: ignore

    def test_pdb_ca_parsing(self):
        """Verify pure-Python PDB parser extracting C-alpha atoms."""
        nodes = parse_pdb_ca_coordinates(SAMPLE_PDB)
        self.assertEqual(len(nodes), 6)
        self.assertEqual(nodes[0].resid, 1)
        self.assertEqual(nodes[0].resname, "ALA")
        self.assertEqual(nodes[0].chain, "A")
        self.assertEqual(nodes[0].x, 10.0)

    def test_allosteric_pathway_tracing(self):
        """Verify GNM Kirchhoff Laplacian, cross-correlations, and Yen's K-shortest paths."""
        res = trace_allosteric_paths(SAMPLE_PDB, source_resid=1, sink_resid=6, cutoff_angstroms=4.5, k_paths=2)

        self.assertEqual(res.source_resid, 1)
        self.assertEqual(res.sink_resid, 6)
        self.assertGreaterEqual(len(res.paths), 1)

        primary_path = res.paths[0]
        self.assertEqual(primary_path.path_residues, (1, 2, 3, 4, 5, 6))
        self.assertGreater(primary_path.total_cost, 0.0)
        self.assertIn(primary_path.bottleneck_residue, (2, 3, 4, 5))

        # Check PRS profiling
        self.assertGreater(len(res.prs_effectors), 0)
        self.assertGreater(len(res.prs_sensors), 0)

    def test_mutagenesis_primer_generation(self):
        """Verify integration connecting hotspot residues with plasmid engineering."""
        plasmid = get_plasmid("pUC19")
        res = trace_allosteric_paths(SAMPLE_PDB, source_resid=1, sink_resid=6, cutoff_angstroms=4.5, k_paths=2)

        primers = generate_allosteric_mutagenesis_primers(
            plasmid=plasmid,
            allosteric_result=res,
            target_amino_acid="A",
            flanking_bp=15,
        )
        self.assertIsInstance(primers, tuple)
        self.assertGreater(len(primers), 0)

        for p in primers:
            self.assertIsInstance(p, PrimerPair)
            self.assertGreater(p.forward_primer.tm_celsius, 50.0)
            self.assertGreater(p.reverse_primer.tm_celsius, 50.0)
            self.assertIn("GCG", p.forward_primer.sequence)

    def test_easy_allostery_wrapper(self):
        """Verify biolabcalc.easy.trace_allostery convenience wrapper."""
        res = ez.trace_allostery(SAMPLE_PDB, source_resid=1, sink_resid=3, cutoff=4.5)
        self.assertIsInstance(res, AllostericNetworkResult)
        self.assertEqual(len(res.paths), 1)
        self.assertEqual(res.paths[0].path_residues, (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
