"""Tests for printable benchtop protocol, master mix overage, and plate maps."""

import os
import tempfile
import unittest
import biolabcalc as blc
from biolabcalc.printable_protocol import (
    determine_pipette_tool,
    build_bench_master_mix,
    generate_plate_bench_sheet,
    render_bench_companion_html,
    GLPSignOffBlock,
)
from biolabcalc import easy


class TestPrintableProtocol(unittest.TestCase):

    def test_determine_pipette_tool(self):
        self.assertIn("P2", determine_pipette_tool(0.5))
        self.assertIn("P2", determine_pipette_tool(2.0))
        self.assertIn("P10", determine_pipette_tool(2.5))
        self.assertIn("P10", determine_pipette_tool(10.0))
        self.assertIn("P20", determine_pipette_tool(15.0))
        self.assertIn("P20", determine_pipette_tool(20.0))
        self.assertIn("P200", determine_pipette_tool(50.0))
        self.assertIn("P200", determine_pipette_tool(200.0))
        self.assertIn("P1000", determine_pipette_tool(500.0))

    def test_build_bench_master_mix_enzyme_last(self):
        reagents = [
            {"name": "Taq Polymerase", "stock_conc": "5 U/µL", "final_conc": "1.25 U", "vol_ul": 0.25, "category": "enzyme"},
            {"name": "Nuclease-Free Water", "stock_conc": "100%", "final_conc": "QS", "vol_ul": 17.5, "category": "water"},
            {"name": "10X Buffer", "stock_conc": "10X", "final_conc": "1X", "vol_ul": 2.5, "category": "buffer"},
            {"name": "Template DNA", "stock_conc": "10 ng/µL", "final_conc": "20 ng", "vol_ul": 2.0, "category": "template"},
            {"name": "dNTPs", "stock_conc": "10 mM", "final_conc": "200 µM", "vol_ul": 0.5, "category": "dntp"},
        ]

        mix = build_bench_master_mix(
            components=reagents,
            total_reactions=10,
            reaction_volume_ul=25.0,
            excess_percent=10.0,
            separate_template=True,
        )

        self.assertEqual(mix.total_reactions, 10)
        self.assertEqual(mix.multiplier, 11.0)  # 10 * 1.10 = 11

        # Master mix reagents (non-separate) should be sorted by addition priority
        mm_reagents = [r for r in mix.reagents if not r.is_separate_addition]
        self.assertEqual(mm_reagents[0].name, "Nuclease-Free Water (ddH2O)")  # Priority 1
        self.assertEqual(mm_reagents[1].name, "10X Buffer")                  # Priority 2
        self.assertEqual(mm_reagents[2].name, "dNTPs")                       # Priority 4
        self.assertEqual(mm_reagents[3].name, "Taq Polymerase")              # Priority 7 (Enzyme last!)

        # Scaled volume check: 19.75 * 11.0 = 217.25 uL
        self.assertGreater(mm_reagents[0].total_vol_ul, 100.0)
        # Polymerase scaled: 0.25 * 11.0 = 2.75 uL -> Pipette P10
        self.assertIn("P10", mm_reagents[3].pipette_recommendation)

    def test_plate_bench_sheet_96_well(self):
        samples = ["Clone-1", "Clone-2"]
        plate = generate_plate_bench_sheet(
            samples=samples,
            plate_type="96-well",
            controls=(("NTC", "control_neg"), ("PTC", "control_pos")),
        )

        self.assertEqual(plate.plate_type, "96-well")
        self.assertEqual(plate.total_wells, 96)
        self.assertEqual(plate.used_wells_count, 4)  # 2 controls + 2 samples
        self.assertEqual(plate.wells[0].well_id, "A1")
        self.assertEqual(plate.wells[0].sample_name, "NTC")
        self.assertEqual(plate.wells[1].well_id, "A2")
        self.assertEqual(plate.wells[1].sample_name, "PTC")
        self.assertEqual(plate.wells[2].well_id, "A3")
        self.assertEqual(plate.wells[2].sample_name, "Clone-1")

    def test_plate_bench_sheet_strip(self):
        samples = ["T1", "T2", "T3"]
        plate = generate_plate_bench_sheet(
            samples=samples,
            plate_type="8-strip",
            controls=(),
        )

        self.assertEqual(plate.plate_type, "8-strip")
        self.assertEqual(plate.used_wells_count, 3)

    def test_render_bench_companion_html(self):
        mix = build_bench_master_mix(
            components=[
                {"name": "Water", "stock_conc": "100%", "final_conc": "QS", "vol_ul": 18.0, "category": "water"},
                {"name": "Buffer", "stock_conc": "10X", "final_conc": "1X", "vol_ul": 2.0, "category": "buffer"},
            ],
            total_reactions=8,
            reaction_volume_ul=20.0,
            excess_percent=15.0,
        )
        plate = generate_plate_bench_sheet(
            samples=["S1", "S2"],
            plate_type="96-well",
            controls=(),
        )
        sign_off = GLPSignOffBlock(operator_name="Researcher Alice", project_id="PRJ-101")

        html_doc = render_bench_companion_html(
            title="Bradford Standard Master Mix",
            master_mix=mix,
            plate_map=plate,
            sign_off=sign_off,
            page_trim="8x10",
        )

        self.assertIn("Bradford Standard Master Mix", html_doc)
        self.assertIn("@media print", html_doc)
        self.assertIn("chamfer-notch", html_doc)
        self.assertIn("Researcher Alice", html_doc)
        self.assertIn("PRJ-101", html_doc)
        self.assertIn("Water", html_doc)

    def test_easy_print_protocol(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "protocol.html")
            html_res = easy.print_protocol(
                title="Colony PCR Protocol",
                reactions=12,
                overage=10.0,
                output_html_path=out_path,
            )

            self.assertTrue(os.path.exists(out_path))
            self.assertIn("Colony PCR Protocol", html_res)
            self.assertIn("96-WELL", html_res)


if __name__ == "__main__":
    unittest.main()
