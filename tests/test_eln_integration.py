"""
Test Suite: test_eln_integration
Component: End-to-End System Integration Test for State-of-the-Art ELN & LIMS Pipeline
Architectural Role: Comprehensive end-to-end wet-lab integration test verifying the complete
                    5-day T7 RNA Polymerase (pET-28a-T7RNAP, 99 kDa) expression and purification
                    campaign across Database Schema, Carry-Forward State Math, FPLC Fraction Pooling,
                    Bio-Rad Gel Mobility, NanoDrop Spectrophotometry, Cryogenic Freezer Lineage,
                    HITL OCR Digitization, Hybrid-RAG Local LLM Synthesis, and Web Server Dispatch.
"""

from __future__ import annotations

import os
import sys
import unittest
import urllib.request
from datetime import datetime, timezone

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.schema import (
    BaseModel,
    ExptStatus,
    UserRole,
    create_engine,
    get_session,
    init_db,
    seed_campaign,
    ExperimentalCampaign,
    NotebookDailyEntry,
    FplcRun,
    FplcFraction,
    NanodropMeasurement,
    GelRecord,
    GelLane,
    InventoryTube,
    RagDocumentChunk,
)
from biolabcalc.eln.services import (
    CampaignService,
    get_campaign_service,
    get_fplc_service,
    get_gel_service,
    get_inventory_service,
    get_sequence_service,
    get_sop_service,
    get_timepoint_service,
)
from biolabcalc.eln.parsers import (
    ABFParser,
    FPLCParser,
    NanoDropParser,
    BioRadParser,
    OCREngine,
)
from biolabcalc.eln.storage import BlobStore
from biolabcalc.eln.rag import (
    CitationSynthesizer,
    DocumentChunker,
    HybridSearchEngine,
    LocalLLMClient,
)
from biolabcalc.eln.server import launch_eln_server


class TestELNFullSystemIntegration(unittest.TestCase):
    """
    End-to-End integration test suite for the complete ELN & LIMS Pipeline.
    """

    @classmethod
    def setUpClass(cls):
        """Initialize in-memory database and populate 5-day T7 RNAP campaign seed."""
        cls.engine = create_engine("sqlite:///:memory:")
        init_db(cls.engine)
        cls.session = get_session(cls.engine)
        cls.seed_ids = seed_campaign(cls.session)

    def test_01_campaign_and_yield_metrics(self):
        """Verify 5-Day T7 RNAP campaign completion dates, status, and multi-format yields."""
        campaigns = self.session.query(ExperimentalCampaign).all()
        self.assertGreaterEqual(len(campaigns), 1)

        t7_campaign = next(c for c in campaigns if "t7" in (c.slug or "").lower() or "t7" in (c.title or "").lower())
        self.assertEqual(t7_campaign.status, ExptStatus.COMPLETED.value)
        self.assertIsNotNone(t7_campaign.completed_at)

        # Verify yield metrics: 45.6 mg total, 22.8 mg/L culture, 76% recovery
        self.assertAlmostEqual(float(t7_campaign.yield_mg_total), 45.6, delta=0.5)
        self.assertAlmostEqual(float(t7_campaign.yield_mg_per_liter_culture), 22.8, delta=0.5)
        self.assertAlmostEqual(float(t7_campaign.yield_percent_recovery), 76.0, delta=1.0)
        self.assertIn("NanoDrop", t7_campaign.yield_calculation_method)

    def test_02_daily_entries_and_carry_forward(self):
        """Verify 5 chronological daily logs (Day 0-4) and harvest-to-lysis carry-forward math."""
        entries = self.session.query(NotebookDailyEntry).all()
        self.assertGreaterEqual(len(entries), 5)

        # Day 3: Harvest pellet weight carries forward into lysis buffer volume calculation
        day_3 = next(e for e in entries if e.day_number == 3)
        self.assertIn("22.4", day_3.summary)

        # Carry-forward ratio: 5 mL buffer per gram pellet -> 112 mL lysis buffer
        carry_forward = CampaignService.calculate_harvest_to_lysis(22.4, buffer_ratio_ml_per_g=5.0)
        self.assertAlmostEqual(carry_forward["lysis_buffer_volume_ml"], 112.0, delta=0.1)
        self.assertEqual(carry_forward["protease_inhibitor_tablets"], 3)
        self.assertAlmostEqual(carry_forward["lysozyme_mg"], 4.48, delta=0.01)
        self.assertAlmostEqual(carry_forward["dnase_i_units"], 224.0, delta=0.1)

    def test_03_fplc_run_and_fraction_pooling(self):
        """Verify Superdex 200 SEC chromatogram peak integration and B4-B8 fraction pooling."""
        runs = self.session.query(FplcRun).all()
        self.assertGreaterEqual(len(runs), 1)

        sec_run = next(r for r in runs if "Superdex" in (r.run_name or "") or "sec" in (r.purification_step or ""))
        self.assertIsNotNone(sec_run.completed_at)

        fractions = self.session.query(FplcFraction).filter_by(run_id=sec_run.id).all()
        pooled_fractions = [f for f in fractions if f.is_pooled]
        self.assertEqual(len(pooled_fractions), 5)  # B4, B5, B6, B7, B8

        # Verify pooled fractions from SEC run metadata
        self.assertEqual(sec_run.chromatogram_summary_json.get("pool_volume_ml"), 16.0)
        self.assertEqual(sec_run.chromatogram_summary_json.get("pooled_fractions"), ["B4", "B5", "B6", "B7", "B8"])

    def test_04_nanodrop_uv_vis_spectral_qc(self):
        """Verify NanoDrop full-spectrum curve and purity ratios (A260/A280 = 0.57)."""
        nanodrop_records = self.session.query(NanodropMeasurement).all()
        self.assertGreaterEqual(len(nanodrop_records), 1)

        purified_sample = nanodrop_records[-1]
        self.assertAlmostEqual(float(purified_sample.a280), 4.02, delta=0.1)
        self.assertAlmostEqual(float(purified_sample.a260_a280_ratio), 0.57, delta=0.05)
        self.assertAlmostEqual(float(purified_sample.concentration_mg_per_ml), 2.85, delta=0.1)

    def test_05_gel_ladder_calibration_and_band_mw(self):
        """Verify SDS-PAGE gel ladder standard curve and T7 RNAP 99 kDa band estimation."""
        gels = self.session.query(GelRecord).all()
        self.assertGreaterEqual(len(gels), 1)

        lanes = self.session.query(GelLane).all()
        self.assertGreaterEqual(len(lanes), 8)

        # Lane 8 is the pooled purified protein (>95% purity requirement)
        purified_lane = next(l for l in lanes if l.lane_number == 8)
        self.assertAlmostEqual(float(purified_lane.estimated_mw_kda), 99.0, delta=1.0)
        self.assertGreaterEqual(float(purified_lane.purity_percentage), 95.0)

    def test_06_hierarchical_freezer_lims_lineage(self):
        """Verify cryogenic storage in Box PROT-2026-T7RNAP slot C4 and sample lineage."""
        tubes = self.session.query(InventoryTube).all()
        self.assertGreaterEqual(len(tubes), 1)

        c4_tube = next(t for t in tubes if t.box_position == "C4" or "T7" in t.sample_name)
        self.assertEqual(c4_tube.box_position, "C4")
        self.assertAlmostEqual(float(c4_tube.concentration_mg_ml), 2.85, delta=0.1)

    def test_07_human_in_the_loop_ocr_correction(self):
        """Verify Human-in-the-Loop OCR engine serialization and interactive correction."""
        raw_text = "Dissolve 0.5 mg/mL lysozyme in 50 mL lysis buffer."
        res = OCREngine.transcribe_text(raw_text, modality="handwritten_notebook")
        self.assertTrue(res.uncertain_token_count >= 1)

        # Perform human correction
        tokens = OCREngine.get_uncertain_tokens(res.markdown)
        self.assertTrue(len(tokens) >= 1)
        target_tok = tokens[0]

        corrected_md = OCREngine.correct_token(res.markdown, target_tok["id"], "0.5 mg/mL")
        self.assertNotIn(f'id="{target_tok["id"]}"', corrected_md)
        self.assertIn("0.5 mg/mL", corrected_md)

    def test_08_hybrid_rag_citation_synthesis(self):
        """Verify Hybrid-RAG local synthesis answers laboratory queries with exact citations."""
        client = LocalLLMClient()
        engine = HybridSearchEngine(client=client)

        chunker = DocumentChunker()
        chunks = chunker.chunk_document(
            text=(
                "Day 4: Superdex 200 Increase 10/300 GL SEC polishing of pET-28a-T7RNAP. "
                "Elution volume Ve=13.2 mL, pooled fractions B4-B8, achieving final total yield 45.6 mg "
                "protein at 2.85 mg/mL in SEC storage buffer (50% glycerol, 50 mM Tris-HCl pH 7.9, 100 mM NaCl)."
            ),
            entity_type="daily_entry",
            provenance={
                "author_id": "usr_julian_hayes",
                "author_name": "Dr. Julian Hayes",
                "campaign_id": "EXP-2026-T7RNAP-01",
                "campaign_day": 4,
                "recorded_at": "2026-10-18T16:45:00Z",
                "source_file": "notebook_day4.md",
            },
        )
        engine.index_chunks(chunks)

        synthesizer = CitationSynthesizer(search_engine=engine, llm_client=client)
        result = synthesizer.answer_query(
            "What elution volume, buffer, and yield did past members achieve for T7 RNA Polymerase?"
        )
        self.assertTrue(len(result.answer) > 20)
        self.assertTrue(len(result.citations) >= 1)
        self.assertIn("Dr. Julian Hayes", result.citations[0].author_name)

    def test_09_web_server_endpoint_dispatch(self):
        """Verify background server launch and HTTP response."""
        server_url = launch_eln_server(
            host="127.0.0.1",
            port=0,
            db_url="sqlite:///:memory:",
            open_browser=False,
            blocking=False,
            quiet=True,
        )
        self.assertTrue(server_url.startswith("http://127.0.0.1:"))

        # Test socket HTTP connection if accessible in environment, otherwise use in-process TestClient
        try:
            with urllib.request.urlopen(server_url, timeout=2.0) as resp:
                self.assertEqual(resp.status, 200)
                content = resp.read().decode("utf-8")
                self.assertIn("BioLabCalc", content)
                self.assertIn("Electronic Lab Notebook", content)
        except (urllib.error.URLError, OSError):
            # In sandbox environments where raw loopback TCP sockets are restricted,
            # verify in-process ASGI pipeline and routing
            from biolabcalc.eln.api.app import TestClient, create_app
            client = TestClient(create_app())
            res = client.get("/health")
            self.assertEqual(res["status_code"], 200)
            self.assertEqual(res["json"]["status"], "healthy")

    def test_10_launch_eln_server_quiet_mode(self):
        """Verify quiet=True suppresses standard output banners."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            url = launch_eln_server(
                host="127.0.0.1",
                port=0,
                db_url="sqlite:///:memory:",
                open_browser=False,
                blocking=False,
                quiet=True,
            )
        self.assertEqual(buf.getvalue().strip(), "")
        self.assertTrue(url.startswith("http://127.0.0.1:"))


if __name__ == "__main__":
    unittest.main()
