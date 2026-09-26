import os
import unittest
from biolabcalc.buffers import calculate_buffer_recipe, calculate_ntp_ph_adjustment, BUFFER_CATALOG

class TestBuffers(unittest.TestCase):
    def test_50x_tae(self):
        res = calculate_buffer_recipe("50X_TAE", target_volume_ml=500.0)
        self.assertEqual(res.target_volume_ml, 500.0)
        tris_comp = [c for c in res.components if "Tris" in c.name][0]
        self.assertAlmostEqual(tris_comp.amount, 121.0, places=1)

    def test_10x_pbs(self):
        res = calculate_buffer_recipe("10X_PBS", target_volume_ml=1000.0)
        self.assertEqual(len(res.components), 4)
        nacl_comp = [c for c in res.components if c.name == "NaCl"][0]
        self.assertAlmostEqual(nacl_comp.amount, 80.0, places=1)

    def test_invalid_buffer(self):
        with self.assertRaises(KeyError):
            calculate_buffer_recipe("NON_EXISTENT_BUFFER_123")

    def test_ntp_ph_adjustment_disodium(self):
        res = calculate_ntp_ph_adjustment(
            initial_volume_ml=4.0,
            initial_conc_mm=100.0,
            target_volume_ml=16.0,
            target_conc_mm=25.0,
            target_ph=7.5,
            starting_form="disodium_salt",
            ntp_species="equimolar_mix",
        )
        self.assertAlmostEqual(res.total_ntp_mmol, 0.400, places=3)
        self.assertGreater(res.naoh_equivalents, 1.2)
        self.assertLess(res.naoh_equivalents, 1.5)
        self.assertIn("5M", res.naoh_volume_ul)
        self.assertAlmostEqual(res.initial_volume_ml + (res.naoh_mmol / 5.0) + res.water_volume_ml, 16.0, places=2)

    def test_ntp_ph_adjustment_pre_neutralized(self):
        res = calculate_ntp_ph_adjustment(
            initial_volume_ml=4.0,
            initial_conc_mm=100.0,
            target_volume_ml=16.0,
            target_conc_mm=25.0,
            target_ph=7.5,
            starting_form="pre_neutralized",
        )
        self.assertEqual(res.naoh_mmol, 0.0)
        self.assertEqual(res.water_volume_ml, 12.0)
        self.assertTrue(any("Do NOT add NaOH" in w for w in res.warnings))

    def test_ntp_ph_adjustment_errors(self):
        # Mass balance mismatch
        with self.assertRaises(ValueError):
            calculate_ntp_ph_adjustment(target_conc_mm=50.0)
        # Volume smaller than initial
        with self.assertRaises(ValueError):
            calculate_ntp_ph_adjustment(target_volume_ml=2.0)
        # Invalid pH
        with self.assertRaises(ValueError):
            calculate_ntp_ph_adjustment(target_ph=14.0)



    def test_custom_buffer_builder(self):
        from biolabcalc.buffers import CustomBufferBuilder, calculate_buffer_recipe
        b = CustomBufferBuilder("Test_Custom_Lysis", ph="7.6", storage="4°C")
        b.add_solid("Tris base", target_conc_mm=25.0, mw_g_mol=121.14)
        b.add_liquid_stock("NaCl", target_conc_mm=100.0, stock_conc_mm=5000.0)
        b.add_percent("Triton X-100", target_percent=0.2, is_volume=True)
        b.add_step("Mix components in water and adjust pH with HCl.")

        res = b.build(target_volume_ml=500.0)
        self.assertEqual(res.name, "Test_Custom_Lysis")
        self.assertEqual(res.target_volume_ml, 500.0)
        self.assertEqual(len(res.components), 3)

        # 25 mM Tris in 500 mL = 0.025 mol/L * 0.5 L * 121.14 = 1.514 g
        tris = [c for c in res.components if "Tris" in c.name][0]
        self.assertAlmostEqual(tris.amount, 1.514, places=2)

        # 100 mM NaCl from 5 M in 500 mL = (100 * 500) / 5000 = 10.0 mL
        nacl = [c for c in res.components if c.name == "NaCl"][0]
        self.assertAlmostEqual(nacl.amount, 10.0, places=1)

        # 0.2% v/v Triton in 500 mL = 1.0 mL
        triton = [c for c in res.components if "Triton" in c.name][0]
        self.assertAlmostEqual(triton.amount, 1.0, places=1)

    def test_create_custom_buffer_one_liner(self):
        from biolabcalc.buffers import create_custom_buffer
        res = create_custom_buffer(
            name="One_Liner_Buffer",
            components=[
                {"name": "HEPES", "type": "solid", "conc_mm": 40.0, "mw": 238.3},
                {"name": "KCl", "type": "solid", "conc_mm": 100.0, "mw": 74.55},
                {"name": "Glycerol", "type": "percent_v_v", "percent": 5.0},
            ],
            ph="7.5",
            target_volume_ml=200.0,
        )
        self.assertEqual(res.target_volume_ml, 200.0)
        self.assertEqual(len(res.components), 3)

    def test_save_load_delete_custom_buffer(self):
        import tempfile
        from biolabcalc.buffers import (
            CustomBufferBuilder,
            save_custom_buffer_to_disk,
            load_custom_buffers_from_disk,
            list_custom_buffers,
            delete_custom_buffer,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            temp_path = tf.name

        try:
            b = CustomBufferBuilder("Temp_Disk_Buffer", ph="8.0")
            b.add_solid("Glycine", target_conc_mm=100.0, mw_g_mol=75.07)
            save_custom_buffer_to_disk(b, filepath=temp_path)

            bufs = list_custom_buffers(filepath=temp_path)
            self.assertIn("TEMP_DISK_BUFFER", bufs)

            loaded = load_custom_buffers_from_disk(filepath=temp_path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, "Temp_Disk_Buffer")

            deleted = delete_custom_buffer("Temp_Disk_Buffer", filepath=temp_path)
            self.assertTrue(deleted)
            self.assertEqual(len(list_custom_buffers(filepath=temp_path)), 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_easy_custom_buffer_helper(self):
        from biolabcalc.easy import custom_buffer, buffer_builder
        res = custom_buffer(
            name="Easy_Binding",
            components=[{"name": "Tris", "type": "solid", "conc_mm": 10.0, "mw": 121.14}],
            volume="250 mL",
        )
        self.assertEqual(res.target_volume_ml, 250.0)

        bb = buffer_builder("Fluent_Buffer", ph="7.2")
        bb.add_solid("NaCl", 50.0, 58.44)
        rec = bb.build(100.0)
        self.assertEqual(rec.target_volume_ml, 100.0)

if __name__ == "__main__":
    unittest.main()
