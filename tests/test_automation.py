"""
Tests for 96/384-Well Microplate Designer and Liquid Handler Automation Engine
"""

import json
import os
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.automation import (
    AutomationWorklist,
    PlateMap,
    WellTransfer,
    design_pcr_setup_plate,
    design_serial_dilution_plate,
    export_echo_csv,
    export_opentrons_protocol,
    export_pylabrobot_json,
    get_plate_dimensions,
    index_to_well,
    well_to_index,
)


class TestAutomationEngine(unittest.TestCase):
    def test_plate_dimensions_and_coordinate_conversions(self):
        # 96-well
        self.assertEqual(get_plate_dimensions("96-well"), (8, 12))
        self.assertEqual(index_to_well(0, "96-well"), "A1")
        self.assertEqual(index_to_well(11, "96-well"), "A12")
        self.assertEqual(index_to_well(12, "96-well"), "B1")
        self.assertEqual(index_to_well(95, "96-well"), "H12")

        self.assertEqual(well_to_index("A1", "96-well"), 0)
        self.assertEqual(well_to_index("A12", "96-well"), 11)
        self.assertEqual(well_to_index("B1", "96-well"), 12)
        self.assertEqual(well_to_index("H12", "96-well"), 95)

        # 384-well
        self.assertEqual(get_plate_dimensions("384-well"), (16, 24))
        self.assertEqual(index_to_well(0, "384-well"), "A1")
        self.assertEqual(index_to_well(23, "384-well"), "A24")
        self.assertEqual(index_to_well(24, "384-well"), "B1")
        self.assertEqual(index_to_well(383, "384-well"), "P24")

        self.assertEqual(well_to_index("A1", "384-well"), 0)
        self.assertEqual(well_to_index("P24", "384-well"), 383)

        # Invalid index / well
        with self.assertRaises(ValueError):
            index_to_well(96, "96-well")
        with self.assertRaises(ValueError):
            well_to_index("Z1", "96-well")

    def test_column_major_indexing(self):
        # By column: index 0 is A1, index 1 is B1, index 7 is H1, index 8 is A2
        self.assertEqual(index_to_well(0, "96-well", by_row=False), "A1")
        self.assertEqual(index_to_well(1, "96-well", by_row=False), "B1")
        self.assertEqual(index_to_well(7, "96-well", by_row=False), "H1")
        self.assertEqual(index_to_well(8, "96-well", by_row=False), "A2")

        self.assertEqual(well_to_index("A1", "96-well", by_row=False), 0)
        self.assertEqual(well_to_index("B1", "96-well", by_row=False), 1)
        self.assertEqual(well_to_index("H1", "96-well", by_row=False), 7)
        self.assertEqual(well_to_index("A2", "96-well", by_row=False), 8)

    def test_plate_designer_validation_errors(self):
        with self.assertRaises(ValueError):
            design_serial_dilution_plate(dilution_factor=0.5)
        with self.assertRaises(ValueError):
            design_serial_dilution_plate(num_points=1)
        with self.assertRaises(ValueError):
            design_serial_dilution_plate(replicates=0)
        with self.assertRaises(ValueError):
            design_serial_dilution_plate(start_row="H", replicates=2)  # Exceeds row H

        with self.assertRaises(ValueError):
            design_pcr_setup_plate(num_reactions=0)
        with self.assertRaises(ValueError):
            design_pcr_setup_plate(num_reactions=100, plate_type="96-well")

    def test_plate_map_accessors(self):
        pm = PlateMap(
            plate_id="Test_Plate",
            well_contents=(("A1", "Sample_A"),),
            volumes_ul=(("A1", 50.0),),
            concentrations=(("A1", 10.0),),
        )
        self.assertEqual(pm.get_content("A1"), "Sample_A")
        self.assertEqual(pm.get_volume("A1"), 50.0)
        self.assertEqual(pm.get_concentration("A1"), 10.0)

        # Non-existent well returns defaults
        self.assertEqual(pm.get_content("B2"), "")
        self.assertEqual(pm.get_volume("B2"), 0.0)
        self.assertEqual(pm.get_concentration("B2"), 0.0)

    def test_serial_dilution_design(self):
        worklist = design_serial_dilution_plate(
            start_conc=100.0,
            dilution_factor=2.0,
            num_points=8,
            replicates=3,
            plate_type="96-well",
        )

        self.assertIsInstance(worklist, AutomationWorklist)
        self.assertIsInstance(worklist.transfers, tuple)
        self.assertIsInstance(worklist.plates, tuple)
        self.assertEqual(len(worklist.plates), 1)

        plate = worklist.plates[0]
        self.assertEqual(plate.plate_id, "Assay_Plate")
        self.assertEqual(plate.plate_type, "96-well")

        # Check concentrations
        # Replicate 1 in row A: A1=100, A2=50, A3=25, A4=12.5, A5=6.25, A6=3.125, A7=1.5625, A8=0.0
        self.assertAlmostEqual(plate.get_concentration("A1"), 100.0)
        self.assertAlmostEqual(plate.get_concentration("A2"), 50.0)
        self.assertAlmostEqual(plate.get_concentration("A8"), 0.0)
        self.assertIn("Standard_Point_1", plate.get_content("A1"))
        self.assertIn("Blank_Control", plate.get_content("A8"))

    def test_pcr_setup_design(self):
        worklist = design_pcr_setup_plate(
            num_reactions=24,
            master_mix_volume_ul=20.0,
            template_volume_ul=5.0,
            plate_type="96-well",
        )

        self.assertEqual(len(worklist.transfers), 48)  # 24 MM + 24 template
        plate = worklist.plates[0]
        self.assertEqual(plate.get_volume("A1"), 25.0)
        self.assertEqual(plate.get_content("A1"), "Reaction_1")

    def test_exporters(self):
        worklist = design_serial_dilution_plate(num_points=4, replicates=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Echo CSV
            echo_file = tmp / "echo.csv"
            echo_csv = export_echo_csv(worklist, echo_file)
            self.assertIn("Source Plate Name,Source Well,Destination Plate Name,Destination Well,Transfer Volume", echo_csv)
            self.assertTrue(echo_file.exists())

            # Opentrons Python protocol
            ot_file = tmp / "protocol.py"
            ot_py = export_opentrons_protocol(worklist, ot_file)
            self.assertIn("from opentrons import protocol_api", ot_py)
            self.assertIn("def run(protocol: protocol_api.ProtocolContext):", ot_py)
            self.assertTrue(ot_file.exists())

            # PyLabRobot JSON
            plr_file = tmp / "worklist.json"
            plr_json = export_pylabrobot_json(worklist, plr_file)
            parsed = json.loads(plr_json)
            self.assertIn("transfers", parsed)
            self.assertIn("plates", parsed)
            self.assertTrue(plr_file.exists())

    def test_frozen_immutability(self):
        worklist = design_serial_dilution_plate()
        with self.assertRaises(FrozenInstanceError):
            worklist.name = "Hacked"
        with self.assertRaises(FrozenInstanceError):
            worklist.transfers[0].volume_ul = 999.0
        with self.assertRaises(FrozenInstanceError):
            worklist.plates[0].plate_id = "Hacked"

    def test_repr_html(self):
        worklist = design_serial_dilution_plate(num_points=4, replicates=2)
        html_str = worklist._repr_html_()
        self.assertIsInstance(html_str, str)
        self.assertIn("Automation Worklist", html_str)
        self.assertIn("Assay_Plate", html_str)


if __name__ == "__main__":
    unittest.main()
