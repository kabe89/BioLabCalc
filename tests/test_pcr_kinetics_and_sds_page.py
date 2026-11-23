"""Unit tests for PCR kinetics cycle trajectory, protocol generator, and enzyme-supported SDS-PAGE simulation."""

from __future__ import annotations
import os
import sys
import unittest
from unittest.mock import patch
import io

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.pcr import (
    PCRPolymeraseProfile,
    PCR_POLYMERASE_CATALOG,
    get_pcr_polymerase,
    PCRCycleState,
    calculate_pcr_kinetics,
)
from biolabcalc.protocols import (
    LabProtocol,
    generate_pcr_protocol,
    format_protocol_html,
    format_protocol_markdown,
)
from biolabcalc.gels import (
    ProteaseSpec,
    PROTEASE_ENZYME_CATALOG,
    get_protease_enzyme,
    SDSPageBand,
    SDSPageLane,
    SDSPageSimulationResult,
    simulate_sds_page,
)
from biolabcalc.easy import (
    generate_pcr_protocol as easy_pcr_protocol,
    simulate_sds_page as easy_sds_page,
)
from biolabcalc.cli import main as cli_main


class TestPCRKineticsAndSDSPage(unittest.TestCase):
    def test_pcr_polymerase_catalog(self):
        """Verify all 6 standard PCR polymerases and case-insensitive aliases."""
        for poly_name in ("Q5", "Phusion", "KAPA_HiFi", "Taq", "OneTaq", "PrimeSTAR"):
            self.assertIn(poly_name, PCR_POLYMERASE_CATALOG)
            prof = PCR_POLYMERASE_CATALOG[poly_name]
            self.assertGreater(prof.fidelity_vs_taq, 0)
            self.assertGreater(prof.extension_rate_sec_per_kb, 0)
            self.assertGreater(prof.half_life_95c_min, 0)

        # Lookup aliases
        self.assertEqual(get_pcr_polymerase("q5").name, "Q5")
        self.assertEqual(get_pcr_polymerase("kapa-hifi").name, "KAPA_HiFi")
        self.assertEqual(get_pcr_polymerase("onetaq").name, "OneTaq")
        self.assertEqual(get_pcr_polymerase("primestar").name, "PrimeSTAR")
        self.assertEqual(get_pcr_polymerase("nonexistent_poly").name, "Taq")

    def test_pcr_kinetics_cycle_trajectory(self):
        """Test cycle-by-cycle exponential -> linear -> plateau modeling."""
        res = calculate_pcr_kinetics(
            amplicon_len_bp=800,
            template_ng=5.0,
            cycles=35,
            efficiency=0.95,
            polymerase="Q5",
        )
        self.assertEqual(len(res.cycle_trajectory), 35)
        first_cycle = res.cycle_trajectory[0]
        self.assertEqual(first_cycle.cycle, 1)
        self.assertEqual(first_cycle.phase, "exponential")
        self.assertAlmostEqual(first_cycle.primer_remaining_pct, 100.0, delta=1.0)

        last_cycle = res.cycle_trajectory[-1]
        self.assertEqual(last_cycle.cycle, 35)
        self.assertEqual(last_cycle.phase, "plateau")
        self.assertLess(last_cycle.effective_efficiency, first_cycle.effective_efficiency)
        self.assertLess(last_cycle.active_enzyme_fraction, 1.0)
        self.assertIsNotNone(res.optimal_cycle_cutoff)
        self.assertTrue(10 <= res.optimal_cycle_cutoff <= 35)

    def test_generate_pcr_protocol_standard_and_touchdown(self):
        """Test PCR protocol generation with master mix scaling and touchdown cycling."""
        # Standard protocol
        proto = generate_pcr_protocol(
            polymerase="Q5",
            amplicon_len_bp=1200,
            primer_fwd_tm=62.0,
            primer_rev_tm=61.5,
            num_reactions=8,
            reaction_volume_ul=50.0,
            touchdown=False,
        )
        self.assertIsInstance(proto, LabProtocol)
        self.assertIn("Q5", proto.title)
        self.assertIn("1200 bp", proto.title)
        self.assertTrue(any("Nuclease-Free Water" in r.name for r in proto.reagents))
        self.assertTrue(any("Buffer" in r.name for r in proto.reagents))
        self.assertTrue(any("DNA Polymerase" in r.name for r in proto.reagents))
        self.assertEqual(len(proto.steps), 3)

        # HTML and Markdown formatting
        html_out = format_protocol_html(proto)
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("Q5", html_out)
        self.assertIn("print", html_out)

        md_out = format_protocol_markdown(proto)
        self.assertIn("# ", md_out)
        self.assertIn("Reagents", md_out)

        # Touchdown protocol
        proto_td = generate_pcr_protocol(
            polymerase="Phusion",
            amplicon_len_bp=800,
            primer_fwd_tm=65.0,
            primer_rev_tm=58.0,
            touchdown=True,
        )
        self.assertEqual(len(proto_td.steps), 4)
        self.assertIn("Touchdown", proto_td.steps[1].title)

    def test_protease_catalog(self):
        """Verify all 10 proteases in PROTEASE_ENZYME_CATALOG."""
        for enz in ("TEV", "HRV_3C", "Thrombin", "Factor_Xa", "Enterokinase", "Ulp1_SUMO", "Trypsin", "Chymotrypsin", "LysC", "PNGase_F"):
            self.assertIn(enz, PROTEASE_ENZYME_CATALOG)
            spec = PROTEASE_ENZYME_CATALOG[enz]
            self.assertTrue(len(spec.recognition_motif) > 0)
            self.assertGreater(spec.optimal_temp_celsius, 0)

        # Alias resolution
        self.assertEqual(get_protease_enzyme("prescission").name, "HRV_3C")
        self.assertEqual(get_protease_enzyme("tev_protease").name, "TEV")
        self.assertEqual(get_protease_enzyme("sumo").name, "Ulp1_SUMO")
        self.assertEqual(get_protease_enzyme("pngase").name, "PNGase_F")
        self.assertIsNone(get_protease_enzyme("non_existent_enzyme"))

    def test_sds_page_simulation_intact_and_non_reducing(self):
        """Test SDS-PAGE simulation without protease under reducing and non-reducing conditions."""
        # Sequence with 2 Cysteines: MKWVTFISLLLLCFSSAYSRGVFRRDTHKSEIAHRFKDLGEC
        seq_cys = "MKWVTFISLLLLCFSSAYSRGVFRRDTHKSEIAHRFKDLGEC"

        # Reducing
        res_red = simulate_sds_page(seq_cys, reducing=True)
        self.assertIsInstance(res_red, SDSPageSimulationResult)
        self.assertTrue(res_red.reducing)
        self.assertEqual(len(res_red.sample_lanes), 1)
        lane_red = res_red.sample_lanes[0]
        self.assertEqual(len(lane_red.bands), 1)
        self.assertFalse(lane_red.bands[0].is_cleaved)

        # Non-reducing
        res_nonred = simulate_sds_page(seq_cys, reducing=False)
        self.assertFalse(res_nonred.reducing)
        lane_nonred = res_nonred.sample_lanes[0]
        # Should have compact monomer and disulfide dimer
        self.assertEqual(len(lane_nonred.bands), 2)
        band_labels = [b.label for b in lane_nonred.bands]
        self.assertTrue(any("monomer" in l for l in band_labels))
        self.assertTrue(any("dimer" in l for l in band_labels))

        # Sequence with 1 Cysteine: monomer with unpaired Cys and disulfide dimer
        seq_1cys = "MKWVTFISLLLLCFSSAYSRGVFRRDTHKSEIAHRFKDLGE"
        res_1cys = simulate_sds_page(seq_1cys, reducing=False)
        lane_1cys = res_1cys.sample_lanes[0]
        self.assertEqual(len(lane_1cys.bands), 2)
        mono_band = next(b for b in lane_1cys.bands if "monomer" in b.label)
        self.assertIn("Unpaired Cys", mono_band.notes)

        # Sequence with 0 Cysteines: unaffected by non-reducing
        seq_nocys = "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGE"
        res_nocys = simulate_sds_page(seq_nocys, reducing=False)
        self.assertEqual(len(res_nocys.sample_lanes[0].bands), 1)

    def test_sds_page_protease_cleavage(self):
        """Test TEV and Enterokinase protease cleavage and PNGase F deglycosylation."""
        # Construct protein with TEV cleavage site (ENLYFQG): Tag (30 aa) + ENLYFQG + Target (40 aa)
        tag = "MGSSHHHHHHSSGLVPRGSHMASMTGGQQM"
        tev_site = "ENLYFQG"
        target = "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGE"
        full_protein = tag + tev_site + target

        res_tev = simulate_sds_page(full_protein, enzyme="TEV")
        self.assertEqual(res_tev.enzyme, "TEV")
        lane = res_tev.sample_lanes[0]
        self.assertEqual(len(lane.bands), 2)
        for b in lane.bands:
            self.assertTrue(b.is_cleaved)
            self.assertGreater(b.mw_kda, 1.0)
            self.assertTrue(0.05 <= b.relative_migration_rf <= 0.95)

        # Uncleaved test
        res_uncut = simulate_sds_page(target, enzyme="TEV")
        self.assertEqual(len(res_uncut.sample_lanes[0].bands), 1)
        self.assertFalse(res_uncut.sample_lanes[0].bands[0].is_cleaved)

        # PNGase F test with N-glycosylation sequon (N-L-T)
        glyco_seq = "MKWVTFISLLLLFSSAYSRGVFRRDTHKSENLTAHRFKDLGE"
        res_pngase = simulate_sds_page(glyco_seq, enzyme="PNGase_F")
        self.assertEqual(res_pngase.enzyme, "PNGase_F")
        self.assertTrue(res_pngase.sample_lanes[0].bands[0].is_cleaved)

    def test_sds_page_svg_and_html_render(self):
        """Test SVG and HTML outputs of SDSPageSimulationResult."""
        seq = "MGSSHHHHHHENLYFQGMKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGE"
        res = simulate_sds_page(seq, enzyme="TEV")

        svg = res.to_svg()
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("Ladder", svg)
        self.assertIn("SDS-PAGE", svg)
        self.assertEqual(res._repr_svg_(), svg)

        html_card = res.to_html()
        self.assertIn("<table", html_card)
        self.assertIn("Cleaved", html_card)
        self.assertIn("Lane & Band Summary", html_card)
        self.assertEqual(res._repr_html_(), html_card)

    def test_easy_convenience_api(self):
        """Test high-level easy.py aliases."""
        p = easy_pcr_protocol(polymerase="Phusion", amplicon_len_bp=500, num_reactions=2)
        self.assertIsInstance(p, LabProtocol)
        self.assertIn("Phusion", p.title)

        s = easy_sds_page("MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGE")
        self.assertIsInstance(s, SDSPageSimulationResult)
        self.assertEqual(len(s.sample_lanes), 1)

    def test_cli_pcr_protocol_and_sds_page(self):
        """Test CLI command invocation for pcr-protocol and sds-page."""
        # pcr-protocol json
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            cli_main(["pcr-protocol", "--template-len", "600", "--polymerase", "Q5", "--json"])
        output = buf.getvalue()
        self.assertIn('"protocol_id":', output)
        self.assertIn("pcr_q5_600bp", output)

        # pcr-protocol with --amplicon alias
        buf_amp = io.StringIO()
        with patch("sys.stdout", buf_amp):
            cli_main(["pcr-protocol", "--amplicon", "800", "--polymerase", "Q5", "--json"])
        self.assertIn("pcr_q5_800bp", buf_amp.getvalue())

        # pcr with --polymerase flag
        buf_poly = io.StringIO()
        with patch("sys.stdout", buf_poly):
            cli_main(["pcr", "-l", "1000", "-t", "5 ng", "-p", "Q5"])
        self.assertIn("Polymerase:                 Q5", buf_poly.getvalue())

        # sds-page json
        buf2 = io.StringIO()
        with patch("sys.stdout", buf2):
            cli_main(["sds-page", "--seq", "MKWVTFISLLLLCFSSAYSRGVFRRDTHKSEIAHRFKDLGEC", "--json"])
        output2 = buf2.getvalue()
        self.assertIn('"ladder_name":', output2)
        self.assertIn("sample_lanes", output2)


if __name__ == "__main__":
    unittest.main()
