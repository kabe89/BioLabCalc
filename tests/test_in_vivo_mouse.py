"""Unit tests for in-vivo mouse experiment documentation, dosing, welfare monitoring, and ARRIVE 2.0 reporting."""

from __future__ import annotations
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.in_vivo import (
    MouseStrainModel,
    MouseSubject,
    MouseDoseCalculation,
    MouseObservation,
    MouseExperimentRecord,
    calculate_mouse_dose,
    evaluate_mouse_welfare,
    export_arrive_report_html,
    export_arrive_report_markdown,
)
from biolabcalc.easy import (
    calculate_mouse_dose as easy_mouse_dose,
    evaluate_mouse_welfare as easy_mouse_welfare,
)
from biolabcalc.eln.storage.sqlite_store import SQLiteStore
from biolabcalc.eln.services.in_vivo_service import InVivoService
from biolabcalc.eln.api.routes import in_vivo as in_vivo_routes
from biolabcalc.cli import main as cli_main


class TestInVivoMouse(unittest.TestCase):
    def test_mouse_dose_calculation_safe_and_warning(self):
        """Test exact injection volume calculation and route-specific safety thresholds."""
        # Standard IP dose in 25 g mouse: 10 mg/kg with 2 mg/mL stock -> 0.25 mg -> 125 µL (safe)
        d_safe = calculate_mouse_dose(weight_g=25.0, dose_mg_kg=10.0, stock_conc_mg_ml=2.0, route="IP")
        self.assertIsInstance(d_safe, MouseDoseCalculation)
        self.assertEqual(d_safe.calculated_dose_mg, 0.25)
        self.assertEqual(d_safe.injection_volume_ul, 125.0)
        self.assertTrue(d_safe.is_safe_volume)
        self.assertIsNone(d_safe.safety_warning)

        # Excessive IP volume (>500 µL)
        d_excess_ip = calculate_mouse_dose(weight_g=25.0, dose_mg_kg=50.0, stock_conc_mg_ml=1.0, route="IP")
        self.assertEqual(d_excess_ip.injection_volume_ul, 1250.0)
        self.assertFalse(d_excess_ip.is_safe_volume)
        self.assertIsNotNone(d_excess_ip.safety_warning)
        self.assertIn("exceeds", d_excess_ip.safety_warning)

        # IV route safety (max 200 µL)
        d_iv_safe = calculate_mouse_dose(weight_g=20.0, dose_mg_kg=5.0, stock_conc_mg_ml=1.5, route="IV")
        self.assertLess(d_iv_safe.injection_volume_ul, 100.0)
        self.assertTrue(d_iv_safe.is_safe_volume)

        d_iv_excess = calculate_mouse_dose(weight_g=25.0, dose_mg_kg=20.0, stock_conc_mg_ml=1.0, route="IV")
        self.assertFalse(d_iv_excess.is_safe_volume)

        # Validation errors
        with self.assertRaises(ValueError):
            calculate_mouse_dose(0.0, 10.0, 2.0)
        with self.assertRaises(ValueError):
            calculate_mouse_dose(25.0, -5.0, 2.0)
        with self.assertRaises(ValueError):
            calculate_mouse_dose(25.0, 10.0, 0.0)

    def test_evaluate_mouse_welfare_and_humane_endpoints(self):
        """Test welfare clinical scoring, weight loss thresholds, and humane endpoints."""
        # Normal tolerance (2% weight loss)
        obs_norm = evaluate_mouse_welfare(baseline_weight_g=25.0, current_weight_g=24.5, clinical_score=0)
        self.assertIsInstance(obs_norm, MouseObservation)
        self.assertAlmostEqual(obs_norm.weight_change_pct, -2.0, delta=0.1)
        self.assertFalse(obs_norm.is_humane_endpoint)
        self.assertEqual(obs_norm.clinical_score, 0)

        # Critical endpoint: 16% weight loss (exceeds default 15% threshold)
        obs_loss = evaluate_mouse_welfare(baseline_weight_g=25.0, current_weight_g=21.0, clinical_score=0)
        self.assertTrue(obs_loss.is_humane_endpoint)
        self.assertTrue(any("Excessive body weight loss" in r for r in obs_loss.endpoint_reasons))

        # Critical endpoint: severe clinical score (3/3)
        obs_score = evaluate_mouse_welfare(baseline_weight_g=25.0, current_weight_g=24.0, clinical_score=3)
        self.assertTrue(obs_score.is_humane_endpoint)
        self.assertTrue(any("Severe clinical score" in r for r in obs_score.endpoint_reasons))

        # Critical endpoint: moribund symptom
        obs_sym = evaluate_mouse_welfare(baseline_weight_g=25.0, current_weight_g=24.0, clinical_signs=["moribund"])
        self.assertTrue(obs_sym.is_humane_endpoint)
        self.assertTrue(any("moribund" in r for r in obs_sym.endpoint_reasons))

        # Invalid weights
        with self.assertRaises(ValueError):
            evaluate_mouse_welfare(0.0, 25.0)
        with self.assertRaises(ValueError):
            evaluate_mouse_welfare(25.0, -1.0)

    def test_export_arrive_report_html_and_markdown(self):
        """Test ARRIVE 2.0 Essential 10 HTML and Markdown export."""
        sub = MouseSubject("M01", "C57BL/6J", "M", "2026-01-01", "WT", "Cage-1", "", 25.5, "active", "Vehicle")
        obs = MouseObservation("obs_1", "M01", "2026-02-01", 25.0, 25.5, -2.0, 0, (), False, (), "Normal")
        exp = MouseExperimentRecord(
            experiment_id="exp_001",
            iacuc_protocol_number="IACUC-2026-001",
            title="Efficacy of Novel Inhibitor in Syngeneic Mouse Model",
            hypothesis_or_objective="Test tumor growth inhibition with minimal body weight toxicity.",
            primary_investigator="Dr. Sarah Connor",
            cohorts=("Vehicle", "Drug-10mg"),
            subjects=(sub,),
            observations=(obs,),
            harvested_tissue_tube_ids=("TUBE_FREEZER_101",),
        )

        html_rep = export_arrive_report_html(exp)
        self.assertIn("<!DOCTYPE html>", html_rep)
        self.assertIn("ARRIVE 2.0", html_rep)
        self.assertIn("IACUC-2026-001", html_rep)
        self.assertIn("Dr. Sarah Connor", html_rep)
        self.assertIn("TUBE_FREEZER_101", html_rep)
        self.assertIn("M01", html_rep)

        md_rep = export_arrive_report_markdown(exp)
        self.assertIn("# ARRIVE 2.0 In-Vivo Study Report", md_rep)
        self.assertIn("IACUC-2026-001", md_rep)
        self.assertIn("TUBE_FREEZER_101", md_rep)

    def test_in_vivo_service_persistence(self):
        """Test SQLite persistence of strains, subjects, observations, and experiment records."""
        store = SQLiteStore(":memory:")
        svc = InVivoService(store=store)

        # 1. Strain creation
        strain = svc.create_strain(
            name="C57BL/6J",
            rrid="RRID:IMSR_JAX:000664",
            stock_number="000664",
            genetic_background="C57BL/6J",
            modified_alleles=["WT"],
            vendor_or_source="Jackson Laboratory",
        )
        strain_id = strain["strain_id"]
        self.assertIsNotNone(svc.get_strain(strain_id))
        self.assertEqual(len(svc.list_strains()), 1)

        # 2. Subject enrollment
        sub = svc.create_subject(
            ear_tag="EAR_01",
            strain_id=strain_id,
            sex="F",
            baseline_weight_g=22.0,
            cohort="Cohort-A",
        )
        sub_id = sub["subject_id"]
        self.assertEqual(sub_id, "EAR_01")
        self.assertEqual(len(svc.list_subjects(cohort="Cohort-A")), 1)

        # 3. Longitudinal observation with humane endpoint
        obs_norm = svc.log_observation(subject_id=sub_id, weight_g=21.5, clinical_score=0)
        self.assertFalse(obs_norm["is_humane_endpoint"])

        # Severe weight loss (22.0 -> 18.0 = -18.2% loss)
        obs_crit = svc.log_observation(subject_id=sub_id, weight_g=18.0, clinical_score=1)
        self.assertTrue(obs_crit["is_humane_endpoint"])

        # Verify subject status transitioned to humane_endpoint
        updated_sub = svc.get_subject(sub_id)
        self.assertEqual(updated_sub["status"], "humane_endpoint")

        # 4. Experiment creation and tissue linking
        exp = svc.create_experiment(
            iacuc_protocol_number="IACUC-TEST-99",
            title="Preclinical Longevity Test",
            primary_investigator="Dr. Watson",
            cohorts=["Cohort-A"],
            subject_ids=[sub_id],
        )
        exp_id = exp["experiment_id"]
        svc.link_harvested_tissue(exp_id, "LIMS_TUBE_888")

        exp_fetched = svc.get_experiment(exp_id)
        self.assertIn("LIMS_TUBE_888", exp_fetched["harvested_tissue_tube_ids"])

        # 5. Export ARRIVE report
        rep_html = svc.export_arrive_report(exp_id, format="html")
        self.assertIn("IACUC-TEST-99", rep_html)
        self.assertIn("LIMS_TUBE_888", rep_html)

    def test_in_vivo_rest_routes(self):
        """Test ASGI route handlers for in-vivo REST endpoints."""
        res_strain = in_vivo_routes.create_strain({"name": "BALB/c", "genetic_background": "BALB/cAnNCrl"})
        self.assertEqual(res_strain["status"], "success")
        strain_id = res_strain["strain"]["strain_id"]

        res_strains = in_vivo_routes.list_strains()
        self.assertGreater(res_strains["count"], 0)

        res_sub = in_vivo_routes.create_subject({"ear_tag": "M_BALB_01", "strain_id": strain_id, "baseline_weight_g": 20.0})
        self.assertEqual(res_sub["status"], "success")

        res_obs = in_vivo_routes.log_observation({"subject_id": "M_BALB_01", "weight_g": 19.5, "clinical_score": 0})
        self.assertEqual(res_obs["status"], "success")

        res_exp = in_vivo_routes.create_experiment({
            "iacuc_protocol_number": "IACUC-BALB-01",
            "title": "BALB/c Immunization Study",
            "primary_investigator": "Dr. Pasteur",
            "subject_ids": ["M_BALB_01"],
        })
        self.assertEqual(res_exp["status"], "success")
        exp_id = res_exp["experiment"]["experiment_id"]

        res_harvest = in_vivo_routes.link_harvested_tissue(exp_id, {"tube_id": "TUBE_SPLEEN_01"})
        self.assertEqual(res_harvest["status"], "success")

        res_arrive = in_vivo_routes.export_arrive_report(exp_id, format="html")
        self.assertEqual(res_arrive["status"], "success")
        self.assertIn("IACUC-BALB-01", res_arrive["report"])

    def test_easy_and_cli_mouse_commands(self):
        """Test easy.py convenience wrappers and CLI commands."""
        # easy.py
        d = easy_mouse_dose(25.0, 10.0, 2.0, "IP")
        self.assertEqual(d.injection_volume_ul, 125.0)

        w = easy_mouse_welfare(25.0, 24.5)
        self.assertFalse(w.is_humane_endpoint)

        # CLI dose
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            cli_main(["mouse", "dose", "--weight", "25.0", "--dose", "10.0", "--conc", "2.0", "--route", "IP", "--json"])
        out_json = json.loads(buf.getvalue())
        self.assertEqual(out_json["injection_volume_ul"], 125.0)
        self.assertTrue(out_json["is_safe_volume"])

        # CLI welfare
        buf2 = io.StringIO()
        with patch("sys.stdout", buf2):
            cli_main(["mouse", "welfare", "--baseline", "25.0", "--weight", "20.0", "--clinical", "1", "--json"])
        out_json2 = json.loads(buf2.getvalue())
        self.assertTrue(out_json2["is_humane_endpoint"])

        # CLI arrive
        buf3 = io.StringIO()
        with patch("sys.stdout", buf3):
            cli_main(["mouse", "arrive", "--format", "html"])
        self.assertIn("ARRIVE 2.0 In-Vivo Study Report", buf3.getvalue())


if __name__ == "__main__":
    unittest.main()
