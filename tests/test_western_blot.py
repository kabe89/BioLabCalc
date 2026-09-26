import unittest
from biolabcalc.western_blot import (
    calculate_transfer_conditions,
    calculate_lysate_loading,
    calculate_antibody_dilution,
    plan_western_blot,
    troubleshoot_western_blot,
)
from biolabcalc.protocols import get_protocol
from biolabcalc.easy import western, wb_transfer, wb_loading, wb_troubleshoot

class TestWesternBlot(unittest.TestCase):
    def test_transfer_conditions_high_mw(self):
        # 120 kDa protein requires 10% MeOH + 0.05% SDS Towbin buffer
        res = calculate_transfer_conditions(target_mw_kda=120.0, transfer_system="wet_tank", membrane_type="pvdf")
        self.assertEqual(res.pore_size_um, 0.45)
        self.assertTrue(res.activation_required)
        self.assertIn("10% MeOH", res.transfer_buffer_name)
        self.assertIn("Methanol reduced to 10%", res.expert_tips[0])
        self.assertGreaterEqual(res.duration_minutes, 60)

    def test_transfer_conditions_low_mw(self):
        # 15 kDa protein requires 0.2 µm pore and no SDS
        res = calculate_transfer_conditions(target_mw_kda=15.0, transfer_system="wet_tank", membrane_type="pvdf")
        self.assertEqual(res.pore_size_um, 0.2)
        self.assertIn("Low-MW", res.transfer_buffer_name)

    def test_lysate_loading_standard_and_membrane(self):
        # Standard soluble protein (95°C denaturation)
        res_sol = calculate_lysate_loading(lysate_conc_mg_ml=2.0, target_protein_ug_per_lane=20.0, num_lanes=10, is_membrane_protein=False)
        self.assertEqual(res_sol.lysate_volume_per_lane_ul, 10.0)
        self.assertEqual(res_sol.denaturation_temperature_celsius, 95)
        self.assertEqual(res_sol.denaturation_time_minutes, 5)

        # Transmembrane receptor (70°C non-boiling denaturation)
        res_mem = calculate_lysate_loading(lysate_conc_mg_ml=2.0, target_protein_ug_per_lane=20.0, num_lanes=10, is_membrane_protein=True)
        self.assertEqual(res_mem.denaturation_temperature_celsius, 70)
        self.assertEqual(res_mem.denaturation_time_minutes, 10)
        self.assertIn("MEMBRANE PROTEIN", res_mem.notes[0])

    def test_antibody_dilution_and_blocking_compatibility(self):
        # Phospho-specific target forces 5% BSA and bans milk
        res_phos = calculate_antibody_dilution(membrane_area_cm2=56.0, is_phospho_target=True)
        self.assertIn("5% BSA", res_phos.blocking_agent)
        self.assertTrue(any("STRICTLY FORBIDDEN" in w for w in res_phos.compatibility_warnings))

        # Standard target uses 5% milk
        res_std = calculate_antibody_dilution(membrane_area_cm2=56.0, is_phospho_target=False)
        self.assertIn("5% Non-Fat Dry Milk", res_std.blocking_agent)

    def test_plan_western_blot(self):
        plan = plan_western_blot(
            target_protein_name="GluK2",
            target_mw_kda=102.5,
            is_phospho_target=True,
            is_membrane_protein=True,
        )
        self.assertEqual(plan.target_protein_name, "GluK2")
        self.assertIn("8%", plan.recommended_gel_percentage)
        self.assertEqual(plan.sample_prep.denaturation_temperature_celsius, 70)
        self.assertIn("5% BSA", plan.immunodetection.blocking_agent)
        self.assertIn("10% MeOH", plan.transfer_setup.transfer_buffer_name)

    def test_troubleshoot_western_blot(self):
        t_ghost = troubleshoot_western_blot("ghost_bands")
        self.assertIn("burnout", t_ghost.symptom)
        self.assertGreater(len(t_ghost.corrective_actions), 0)

        t_sig = troubleshoot_western_blot("no_signal")
        self.assertIn("No bands", t_sig.symptom)

    def test_western_protocol_lookup(self):
        proto = get_protocol("western_blotting")
        self.assertIn("Western Blotting", proto.title)
        self.assertEqual(proto.category, "Protein Analysis")
        self.assertEqual(len(proto.steps), 9)
        self.assertEqual(len(proto.troubleshooting), 5)

    def test_easy_western_helpers(self):
        plan = western("mTOR", 289.0, transfer="wet_tank")
        self.assertIn("Tris-Acetate", plan.recommended_gel_percentage)

        trans = wb_transfer(15.0)
        self.assertEqual(trans.pore_size_um, 0.2)

        load = wb_loading(lysate_conc="3.0 mg/mL", target_ug=15.0, is_membrane=True)
        self.assertEqual(load.denaturation_temperature_celsius, 70)

        tr = wb_troubleshoot("high_background")
        self.assertIn("background", tr.symptom)

if __name__ == '__main__':
    unittest.main()
