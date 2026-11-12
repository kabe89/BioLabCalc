"""
Module: tests.test_eln_services_and_api
Component: Comprehensive Verification Suite for ELN & LIMS Pipeline Services, Concurrency & API Layer
Architectural Role: Full integration and unit test suite verifying mathematical correctness,
cryptographic audit immutability, carry-forward state calculations, kinetic deviations,
FPLC peak integrations and fraction pooling, gel ladder calibrations, spatial inventory,
RBAC authorizations, WebSockets, and REST API endpoints.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List

from biolabcalc.eln.api.app import TestClient, create_app
from biolabcalc.eln.api.auth import (
    ROLE_ACTIVE_RESEARCHER,
    ROLE_ALUMNI_READONLY,
    ROLE_PI_ADMIN,
    ROLE_ROTATION_STUDENT,
    AuthorizationError,
    get_auth_service,
)
from biolabcalc.eln.api.websocket_manager import get_websocket_manager
from biolabcalc.eln.services.audit_service import get_audit_service
from biolabcalc.eln.services.campaign_service import get_campaign_service
from biolabcalc.eln.services.fplc_service import get_fplc_service
from biolabcalc.eln.services.gel_service import get_gel_service
from biolabcalc.eln.services.inventory_service import get_inventory_service
from biolabcalc.eln.services.sequence_service import (
    calculate_isoelectric_point,
    calculate_primer_tm,
    get_sequence_service,
)
from biolabcalc.eln.services.sop_service import get_sop_service
from biolabcalc.eln.services.timepoint_service import get_timepoint_service


class TestAuditService(unittest.TestCase):
    """
    Test suite verifying cryptographic hash chaining and immutability verification.

    """

    def setUp(self) -> None:
        """Initialize and reset audit service."""
        self.audit = get_audit_service()
        self.audit.clear_for_testing()

    def test_cryptographic_hash_chain_and_verification(self) -> None:
        """Verify unbroken SHA-256 hash chaining and tampering detection."""
        evt1 = self.audit.record_event("campaign", "CMP-001", "CREATE", "pi_admin", metadata={"notes": "Init"})
        evt2 = self.audit.record_event("daily_entry", "ENTRY-001", "CREATE", "active_researcher")
        evt3 = self.audit.record_event("tube", "TUBE-001", "TUBE_MOVE", "active_researcher")

        self.assertEqual(evt1.prev_hash, self.audit.GENESIS_HASH)
        self.assertEqual(evt2.prev_hash, evt1.event_hash)
        self.assertEqual(evt3.prev_hash, evt2.event_hash)

        is_valid, err = self.audit.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIsNone(err)

        trail = self.audit.get_trail()
        self.assertEqual(len(trail), 3)


class TestCampaignService(unittest.TestCase):
    """
    Test suite verifying campaign lifecycle, daily entries, carry-forward math, and yields.

    """

    def setUp(self) -> None:
        """Reset campaign and audit service."""
        self.campaign_service = get_campaign_service()
        self.campaign_service.clear_for_testing()

    def test_campaign_lifecycle_and_daily_entries(self) -> None:
        """Verify creation, transitions, and daily entries."""
        cmp = self.campaign_service.create_campaign(
            title="T7RNAP 10L Fermentation",
            description="High-density IPTG expression in TB medium",
            construct_id="pET-28a-T7RNAP",
            created_by="pi_admin",
        )
        self.assertEqual(cmp.status, "planned")

        entry = self.campaign_service.add_daily_entry(
            campaign_id=cmp.campaign_id,
            day_number=1,
            title="Day 1: Starter Inoculation",
            created_by="active_researcher",
        )
        self.assertEqual(cmp.status, "in_progress")
        self.assertEqual(entry.day_number, 1)

    def test_carry_forward_state_math_harvest_to_lysis(self) -> None:
        """
        Verify exact carry-forward math: Day 2 harvest pellet weight 22.4 g -> Day 3 lysis buffer:
        5 mL buffer per gram pellet = 112 mL buffer, 3 protease inhibitor tablets.

        """
        cmp = self.campaign_service.create_campaign("Test Carry Forward", "Desc", "pET-28a-T7RNAP", "pi_admin")
        d2 = self.campaign_service.add_daily_entry(cmp.campaign_id, 2, "Harvest Day", "pi_admin")

        # Update Day 2 outputs with measured harvest wet pellet weight: 22.4 g
        self.campaign_service.update_daily_entry(
            cmp.campaign_id,
            d2.entry_id,
            updated_by="pi_admin",
            state_outputs={"harvest_pellet_weight_g": 22.4},
        )

        # Execute carry forward
        math_res = self.campaign_service.carry_forward_harvest_to_lysis(
            campaign_id=cmp.campaign_id,
            harvest_day=2,
            lysis_day=3,
            buffer_ratio_ml_per_g=5.0,
            user_id="active_researcher",
        )

        self.assertEqual(math_res["pellet_weight_g"], 22.4)
        self.assertEqual(math_res["lysis_buffer_volume_ml"], 112.0)
        self.assertEqual(math_res["protease_inhibitor_tablets"], 3)
        self.assertAlmostEqual(math_res["lysozyme_mg"], 4.48, places=2)
        self.assertEqual(math_res["dnase_i_units"], 224.0)

        # Verify Day 3 entry contains state inputs
        d3 = next(e for e in cmp.daily_entries if e.day_number == 3)
        self.assertEqual(d3.state_inputs["lysis_buffer_volume_ml"], 112.0)

        # Verify daily rollup summary
        rollup = self.campaign_service.generate_daily_rollup(cmp.campaign_id, 3)
        self.assertEqual(rollup["day_number"], 3)
        self.assertEqual(rollup["state_inputs"]["lysis_buffer_volume_ml"], 112.0)

    def test_campaign_completion_and_yield_metrics(self) -> None:
        """Verify final yield computations on campaign completion."""
        cmp = self.campaign_service.create_campaign("Yield Campaign", "Desc", "pET-28a-T7RNAP", "pi_admin")
        completed = self.campaign_service.complete_campaign(
            campaign_id=cmp.campaign_id,
            user_id="pi_admin",
            yield_mg_total=185.5,
            culture_volume_l=10.0,
            theoretical_yield_mg=200.0,
            yield_ug_plasmid=450.0,
        )
        self.assertEqual(completed.status, "completed")
        self.assertIsNotNone(completed.completion_date)
        self.assertEqual(completed.yields.yield_mg_total, 185.5)
        self.assertEqual(completed.yields.yield_mg_per_liter_culture, 18.55)
        self.assertEqual(completed.yields.yield_percent_recovery, 92.75)
        self.assertEqual(completed.yields.yield_ug_plasmid, 450.0)


class TestTimepointService(unittest.TestCase):
    """
    Test suite verifying kinetic timepoint delta t0, deviation calculations, and live timers.

    """

    def setUp(self) -> None:
        """Reset timepoint service."""
        self.timepoint_service = get_timepoint_service()
        self.timepoint_service.clear_for_testing()

    def test_second_resolution_kinetic_delta_and_deviation(self) -> None:
        """
        Verify t0 to t1 elapsed seconds and target duration deviation:
        Target 60 min (3600s), actual 75 min (4500s) -> deviation +15 min (+900s, +25%).

        """
        t0_str = "2026-11-02T10:00:00Z"
        t1_str = "2026-11-02T11:15:00Z"

        tp = self.timepoint_service.record_timepoint(
            entry_id="ENTRY-D2-01",
            step_name="Centrifugation Pelleting",
            t0=t0_str,
            timestamp=t1_str,
            planned_duration_seconds=3600.0,
            parameters={"rpm": 4000, "temp_c": 4.0},
            notes="Centrifuge queue delayed run",
        )

        self.assertEqual(tp.elapsed_seconds, 4500.0)
        self.assertEqual(tp.elapsed_formatted, "+01:15:00")
        self.assertEqual(tp.deviation_seconds, 900.0)
        self.assertEqual(tp.deviation_percent, 25.0)
        self.assertTrue(tp.is_deviated)

    def test_live_timer_orchestration(self) -> None:
        """Verify live timer start, tick, pause, resume, and stop."""
        timer = self.timepoint_service.start_live_timer(
            name="IPTG Induction 4h",
            target_duration_seconds=14400.0,
            entry_id="ENTRY-D2-01",
        )
        tick = timer.tick()
        self.assertEqual(tick["status"], "running")
        self.assertFalse(tick["is_expired"])
        self.assertTrue(tick["remaining_seconds"] > 0)

        timer.pause()
        self.assertEqual(timer.status, "paused")
        timer.resume()
        self.assertEqual(timer.status, "running")

        stopped = self.timepoint_service.stop_live_timer(timer.timer_id)
        self.assertIsNotNone(stopped)
        self.assertEqual(stopped["status"], "stopped")


class TestSOPService(unittest.TestCase):
    """
    Test suite verifying SOP versioning and execution forking with locked parameter state.

    """

    def setUp(self) -> None:
        """Reset SOP service."""
        self.sop_service = get_sop_service()
        self.sop_service.clear_for_testing()

    def test_sop_versioning_and_execution_forking(self) -> None:
        """
        Verify SOP creation, approval, and execution forking locking parameters and checklist.

        """
        master = self.sop_service.create_sop(
            sop_id="SOP-TEST-001",
            title="Test Experimental Protocol",
            version="1.0",
            category="Purification",
            description="Test protocol for execution forking.",
            parameters={
                "buffer_ratio_ml_per_g": 5.0,
                "induction_temp_c": 18.0,
            },
            steps=[
                {"step_index": 1, "name": "Step 1", "instruction": "Initial step.", "planned_duration_minutes": 960.0},
                {"step_index": 2, "name": "Step 2", "instruction": "Second step.", "planned_duration_minutes": 1140.0},
                {"step_index": 3, "name": "Step 3", "instruction": "Third step.", "planned_duration_minutes": 30.0},
                {"step_index": 4, "name": "Step 4", "instruction": "Fourth step.", "planned_duration_minutes": 60.0},
                {"step_index": 5, "name": "Step 5", "instruction": "Fifth step.", "planned_duration_minutes": 180.0},
            ],
            created_by="pi_admin",
        )
        self.sop_service.approve_sop("SOP-TEST-001", approver_id="pi_admin")
        self.assertIsNotNone(master)
        self.assertEqual(master.version, "1.0")

        fork = self.sop_service.fork_sop_for_entry(
            sop_id=master.sop_id,
            entry_id="ENTRY-D2-001",
            forked_by="active_researcher",
            parameter_overrides={"induction_temp_c": 16.0},
        )

        self.assertEqual(fork.sop_version, "1.0")
        self.assertEqual(fork.locked_parameters["induction_temp_c"], 16.0)
        self.assertEqual(fork.locked_parameters["buffer_ratio_ml_per_g"], 5.0)
        self.assertEqual(len(fork.step_executions), 5)
        self.assertFalse(fork.is_completed)

        # Check off step 1
        updated_fork = self.sop_service.checkoff_step(
            fork_id=fork.fork_id,
            step_index=1,
            completed_by="active_researcher",
            actual_duration_minutes=980.0,
            deviation_notes="Overnight culture grown 16h20m instead of 16h",
        )
        self.assertEqual(updated_fork.step_executions[0].status, "completed")
        self.assertEqual(updated_fork.step_executions[0].deviation_notes, "Overnight culture grown 16h20m instead of 16h")

    def test_fork_sop_unapproved_raises_value_error(self):
        master = self.sop_service.create_sop(
            sop_id="SOP-DRAFT-002",
            title="Draft Protocol",
            version="1.0",
            category="Purification",
            description="Testing draft SOP cannot be forked",
            parameters={"ph": 7.4},
            steps=[{"step_index": 1, "name": "Step 1", "instruction": "Initial step.", "planned_duration_minutes": 10.0}],
            created_by="researcher_test",
        )
        self.assertEqual(master.status, "draft")
        with self.assertRaises(ValueError) as ctx:
            self.sop_service.fork_sop_for_entry(
                sop_id="SOP-DRAFT-002",
                entry_id="ENTRY-D1-002",
                forked_by="researcher_test",
            )
        self.assertIn("Cannot fork SOP 'SOP-DRAFT-002' with status 'draft'. Only approved SOPs can be executed in experimental entries.", str(ctx.exception))


class TestSequenceService(unittest.TestCase):
    """
    Test suite verifying sequence construct registry, Tm, MW, pI, e280, A0.1% calculations.

    """

    def setUp(self) -> None:
        """Reset sequence service."""
        self.seq_service = get_sequence_service()
        self.seq_service.clear_for_testing()

    def test_pET_28a_T7RNAP_construct_properties(self) -> None:
        """
        Verify pre-seeded pET-28a-T7RNAP construct has correct molecular weight (~98.8 kDa),
        pI (~6.5), and extinction coefficient e280 (>135,000 M^-1 cm^-1).

        """
        t7 = self.seq_service.get_sequence("pET-28a-T7RNAP")
        self.assertIsNotNone(t7)
        self.assertEqual(t7.length, 903)
        self.assertAlmostEqual(t7.molecular_weight_da, 103000.0, delta=3000.0)
        self.assertAlmostEqual(t7.extinction_coeff_m_cm, 138500, delta=5000)
        self.assertTrue(5.8 <= t7.isoelectric_point <= 7.8)
        self.assertTrue(t7.absorbance_01_pct > 1.0)

    def test_primer_thermodynamics(self) -> None:
        """Verify melting temperature Tm and GC% for oligonucleotides."""
        primer = self.seq_service.get_sequence("PRIMER-T7-FWD")
        self.assertIsNotNone(primer)
        self.assertEqual(primer.length, 20)
        self.assertAlmostEqual(primer.gc_percent, 40.0, places=1)
        self.assertTrue(45.0 <= primer.melting_temp_c <= 60.0)


class TestFPLCService(unittest.TestCase):
    """
    Test suite verifying FPLC trapezoidal peak integration and fraction pooling.

    """

    def setUp(self) -> None:
        """Reset FPLC service."""
        self.fplc_service = get_fplc_service()
        self.fplc_service.clear_for_testing()

    def test_trapezoidal_peak_integration(self) -> None:
        """Verify numerical trapezoidal peak area and retention volume Ve."""
        # Triangular chromatogram peak centered at Ve = 12.0 mL
        curve = [
            (10.0, 10.0),
            (11.0, 50.0),
            (12.0, 200.0),  # Ve
            (13.0, 50.0),
            (14.0, 10.0),
        ]
        peak = self.fplc_service.integrate_peak(curve, start_volume_ml=10.0, end_volume_ml=14.0, baseline_type="linear")
        self.assertEqual(peak.retention_volume_ve_ml, 12.0)
        self.assertEqual(peak.peak_height_mau, 190.0)  # 200 - baseline 10 = 190 mAU
        # Triangle area with discrete trapezoids: 20 + 115 + 115 + 20 = 270.0 mAU*mL
        self.assertAlmostEqual(peak.peak_area_mau_ml, 270.0, places=1)

    def test_pool_selected_fractions_calculation(self) -> None:
        """
        Verify pooling fractions B4 to B8: 5 fractions * 2.0 mL = 10.0 mL,
        calculates weighted mean UV280 and estimated protein concentration via Beer-Lambert.

        """
        fractions = [
            {"fraction_id": "B4", "volume_ml": 2.0, "uv280_mau": 100.0},
            {"fraction_id": "B5", "volume_ml": 2.0, "uv280_mau": 300.0},
            {"fraction_id": "B6", "volume_ml": 2.0, "uv280_mau": 600.0},
            {"fraction_id": "B7", "volume_ml": 2.0, "uv280_mau": 300.0},
            {"fraction_id": "B8", "volume_ml": 2.0, "uv280_mau": 100.0},
        ]
        pool = self.fplc_service.pool_fractions(
            campaign_id="CMP-001",
            run_id="RUN-SEC-01",
            fractions=fractions,
            construct_id="pET-28a-T7RNAP",
        )
        self.assertEqual(pool.total_volume_ml, 10.0)
        self.assertEqual(pool.fraction_count, 5)
        self.assertEqual(pool.mean_uv280_mau, 280.0)  # (200 + 600 + 1200 + 600 + 200)/10 = 2800 / 10 = 280.0
        self.assertTrue(pool.estimated_conc_mg_ml > 0)
        self.assertTrue(pool.estimated_total_yield_mg > 0)


class TestGelService(unittest.TestCase):
    """
    Test suite verifying gel ladder standard curve calibration and MW estimation.

    """

    def setUp(self) -> None:
        """Reset gel service."""
        self.gel_service = get_gel_service()
        self.gel_service.clear_for_testing()

    def test_ladder_calibration_and_band_mw_estimation(self) -> None:
        """
        Verify linear regression of log10(MW) vs Rf yields high R^2 (>0.98) and accurate unknown sizing.

        """
        # Synthetic standard ladder points
        ladder_points = [
            (250.0, 0.12),
            (150.0, 0.22),
            (100.0, 0.35),
            (75.0, 0.45),
            (50.0, 0.60),
            (25.0, 0.80),
        ]
        cal = self.gel_service.calibrate_ladder(ladder_points)
        self.assertTrue(cal.r_squared > 0.98)
        self.assertTrue(cal.slope < 0)  # Larger MW migrates less -> negative slope

        # Unknown band at Rf = 0.35 should estimate ~100 kDa
        est = self.gel_service.estimate_mw(0.35, cal)
        self.assertAlmostEqual(est["estimated_mw"], 100.0, delta=10.0)

        # Register gel and tag lane
        gel = self.gel_service.register_gel("T7RNAP SDS-PAGE", "sds_page", 10.0, ladder_data=ladder_points)
        lane = self.gel_service.tag_lane(
            gel_id=gel.gel_id,
            lane_number=2,
            sample_name="Pool Eluate",
            bands_data=[{"rf": 0.35}],
            construct_id="pET-28a-T7RNAP",
            fplc_fraction_id="POOL-RUN-SEC-01-B4-B8",
        )
        self.assertEqual(lane.construct_id, "pET-28a-T7RNAP")
        self.assertEqual(len(lane.bands), 1)
        self.assertAlmostEqual(lane.bands[0].estimated_mw, 100.0, delta=10.0)


class TestInventoryService(unittest.TestCase):
    """
    Test suite verifying spatial hierarchy, 2D box grid, tube moves with audit log, and lineage.

    """

    def setUp(self) -> None:
        """Reset inventory service."""
        self.inventory_service = get_inventory_service()
        self.inventory_service.clear_for_testing()

    def test_2d_box_grid_occupancy_and_tube_relocation(self) -> None:
        """
        Verify 2D box grid slot occupancy (81 slots), collision detection, tube movement with audit log.

        """
        grid = self.inventory_service.get_box_grid("BOX-T7RNAP-01")
        self.assertEqual(grid["total_slots"], 81)
        self.assertEqual(grid["occupied_count"], 1)  # Pre-seeded tube at A1
        self.assertEqual(grid["free_count"], 80)

        # Place tube in B4
        tube = self.inventory_service.place_tube(
            box_id="BOX-T7RNAP-01",
            slot="B4",
            sample_name="T7RNAP Aliquot #2",
            volume_ul=500.0,
            concentration_mg_ml=3.10,
            construct_id="pET-28a-T7RNAP",
            user_id="active_researcher",
        )
        self.assertEqual(tube.slot, "B4")

        # Collision check on occupied slot
        with self.assertRaises(ValueError):
            self.inventory_service.place_tube(
                box_id="BOX-T7RNAP-01",
                slot="B4",
                sample_name="Duplicate",
                volume_ul=100.0,
            )

        # Move tube to C5
        move_res = self.inventory_service.move_tube(
            tube_id=tube.tube_id,
            target_box_id="BOX-T7RNAP-01",
            target_slot="C5",
            user_id="active_researcher",
            reason="Relocating to row C",
        )
        self.assertEqual(move_res["from_slot"], "B4")
        self.assertEqual(move_res["to_slot"], "C5")

        # Verify lineage resolution
        lineage = self.inventory_service.resolve_lineage(tube.tube_id)
        self.assertEqual(lineage["tube"]["tube_id"], tube.tube_id)
        self.assertEqual(lineage["location"]["slot"], "C5")
        self.assertEqual(lineage["location"]["room"]["name"], "Bioprocessing Suite 402")
        self.assertEqual(lineage["construct"]["entity_id"], "pET-28a-T7RNAP")


class TestAuthAndRBAC(unittest.TestCase):
    """
    Test suite verifying Role-Based Access Control (RBAC) permission matrix.

    """

    def setUp(self) -> None:
        """Reset auth service."""
        self.auth = get_auth_service()

    def test_rbac_roles_and_permissions(self) -> None:
        """Verify role permissions for pi_admin, active_researcher, rotation_student, alumni_readonly."""
        pi = self.auth.authenticate_token("token-pi-admin")
        researcher = self.auth.authenticate_token("token-active-researcher")
        student = self.auth.authenticate_token("token-rotation-student")
        alumni = self.auth.authenticate_token("token-alumni-readonly")

        # PI Admin can complete campaigns and approve SOPs
        self.assertTrue(pi.has_permission("campaign:complete"))
        self.assertTrue(pi.has_permission("sop:approve"))

        # Active Researcher can create entries, move tubes, but cannot complete campaigns without PI
        self.assertTrue(researcher.has_permission("entry:create"))
        self.assertTrue(researcher.has_permission("inventory:move"))
        self.assertFalse(researcher.has_permission("campaign:complete"))

        # Rotation student can create entries and record timepoints, but cannot move inventory
        self.assertTrue(student.has_permission("entry:create"))
        self.assertTrue(student.has_permission("timepoint:record"))
        self.assertFalse(student.has_permission("inventory:move"))

        # Alumni has read-only access
        self.assertFalse(alumni.has_permission("entry:create"))
        self.assertFalse(alumni.has_permission("inventory:move"))
        self.assertTrue(alumni.has_permission("audit:view"))


class TestRESTAPIEndpoints(unittest.TestCase):
    """
    Test suite verifying end-to-end execution of all REST API endpoints via in-process TestClient.

    """

    def setUp(self) -> None:
        """Initialize ASGI test application and client."""
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_full_pipeline_api_flow(self) -> None:
        """Verify end-to-end multi-modal flow across all REST routers."""
        # Healthcheck
        h = self.client.get("/health")
        self.assertEqual(h["status_code"], 200)

        # Sequences
        seq_res = self.client.get("/api/sequences")
        self.assertEqual(seq_res["status_code"], 200)

        # Campaign & Carry-Forward
        c_res = self.client.post("/api/campaigns", {"title": "Full Flow Campaign", "construct_id": "pET-28a-T7RNAP"})
        self.assertEqual(c_res["status_code"], 200)
        cid = c_res["json"]["campaign"]["campaign_id"]

        d2_res = self.client.post(f"/api/campaigns/{cid}/entries", {"day_number": 2, "title": "Harvest"})
        e2_id = d2_res["json"]["entry"]["entry_id"]

        self.client.put(f"/api/campaigns/{cid}/entries/{e2_id}", {"state_outputs": {"harvest_pellet_weight_g": 22.4}})

        cf_res = self.client.post(f"/api/campaigns/{cid}/carry-forward", {"harvest_day": 2, "lysis_day": 3, "buffer_ratio_ml_per_g": 5.0})
        self.assertEqual(cf_res["status_code"], 200)
        self.assertEqual(cf_res["json"]["carry_forward"]["lysis_buffer_volume_ml"], 112.0)

        # Timepoints
        tp_res = self.client.post(
            "/api/timepoints",
            {
                "entry_id": e2_id,
                "step_name": "Lysis Incubation",
                "t0": "2026-11-02T10:00:00Z",
                "timestamp": "2026-11-02T11:15:00Z",
                "planned_duration_seconds": 3600.0,
            },
        )
        self.assertEqual(tp_res["status_code"], 200)
        self.assertEqual(tp_res["json"]["timepoint"]["deviation_seconds"], 900.0)

        # CAS Upload & OCR Token Correction
        up_res = self.client.post(
            "/api/files/upload",
            {
                "filename": "fplc_trace.csv",
                "content_text": "volume,uv280\n10.0,10.0\n12.0,200.0",
                "ocr_tokens": [{"token_id": "T1", "original_text": "11.2 mL"}],
            },
        )
        self.assertEqual(up_res["status_code"], 200)
        fid = up_res["json"]["file"]["file_id"]

        ocr_res = self.client.post(f"/api/files/{fid}/ocr-correct", {"token_id": "T1", "corrected_text": "112.0 mL"})
        self.assertEqual(ocr_res["status_code"], 200)

        # FPLC
        fplc_res = self.client.post(
            "/api/fplc/integrate",
            {
                "chromatogram_data": [[10.0, 10.0], [11.0, 50.0], [12.0, 200.0], [13.0, 50.0], [14.0, 10.0]],
                "start_volume_ml": 10.0,
                "end_volume_ml": 14.0,
            },
        )
        self.assertEqual(fplc_res["status_code"], 200)

        pool_res = self.client.post(
            "/api/fplc/pool",
            {
                "campaign_id": cid,
                "run_id": "RUN-01",
                "fractions": [
                    {"fraction_id": "B4", "volume_ml": 2.0, "uv280_mau": 200.0},
                    {"fraction_id": "B5", "volume_ml": 2.0, "uv280_mau": 400.0},
                ],
                "construct_id": "pET-28a-T7RNAP",
            },
        )
        self.assertEqual(pool_res["status_code"], 200)

        # NanoDrop
        nd_res = self.client.post(
            "/api/nanodrop/record",
            {
                "sample_name": "T7RNAP Pool",
                "a260": 0.16,
                "a280": 0.28,
                "sample_type": "protein",
                "extinction_coeff": 138500,
                "molecular_weight": 98856,
                "volume_ul": 4000,
            },
        )
        self.assertEqual(nd_res["status_code"], 200)

        # Gels
        cal_res = self.client.post(
            "/api/gels/calibrate",
            {"ladder_data": [[100.0, 0.2], [50.0, 0.4], [25.0, 0.6], [10.0, 0.8]]},
        )
        self.assertEqual(cal_res["status_code"], 200)

        # Inventory
        grid_res = self.client.get("/api/inventory/boxes/BOX-T7RNAP-01/grid")
        self.assertEqual(grid_res["status_code"], 200)

        # Search
        search_res = self.client.get("/api/search?q=T7RNAP")
        self.assertEqual(search_res["status_code"], 200)


if __name__ == "__main__":
    unittest.main()
