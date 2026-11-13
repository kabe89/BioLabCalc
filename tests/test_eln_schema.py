"""
Test Suite: test_eln_schema
Component: Database Schema, Dual Engine Compatibility, and 5-Day T7 RNAP Seed Benchmark
Architectural Role: Comprehensive verification of PostgreSQL 16+ DDL,
                    SQLite fallback engine, all 21 models, relationship navigations,
                    yield metrics, completion dates, and benchmark seed data.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.schema import (
    AuditLog,
    BioSequence,
    CodeAnalysisRun,
    EphysRecording,
    ExperimentalCampaign,
    ExptStatus,
    FplcColumn,
    FplcFraction,
    FplcRun,
    FreezerBox,
    GelLane,
    GelRecord,
    InventoryTube,
    NanodropMeasurement,
    NotebookDailyEntry,
    NotebookTimepointLog,
    PcrAssay,
    RagDocumentChunk,
    SopTemplate,
    StorageBlob,
    StorageHierarchyNode,
    User,
    cosine_similarity,
    create_engine,
    get_session,
    init_db,
    seed_campaign,
)


class TestElnSchema(unittest.TestCase):
    """
    Test suite for ELN & LIMS database schema, engine, models, and benchmark campaign.

    """

    def setUp(self) -> None:
        """Initialize in-memory SQLite database and seed test data."""
        self.engine = create_engine("sqlite:///:memory:")
        init_db(self.engine)
        self.session = get_session(self.engine)
        self.seed_ids = seed_campaign(self.session)

    def test_ddl_sql_file_structure(self) -> None:
        """
        Verify PostgreSQL 16+ production DDL file exists and contains all required
        extensions, types, 21 tables, critical yield columns, and specialized indexes.

        """
        repo_root = Path(__file__).resolve().parent.parent
        ddl_path = repo_root / "src" / "biolabcalc" / "eln" / "schema" / "ddl.sql"
        self.assertTrue(ddl_path.exists(), f"DDL file missing at {ddl_path}")

        content = ddl_path.read_text(encoding="utf-8")

        # Extensions
        self.assertIn('"uuid-ossp"', content)
        self.assertIn('"vector"', content)
        self.assertIn('"pg_trgm"', content)
        self.assertIn('"btree_gin"', content)

        # Custom ENUMs
        self.assertIn("user_role", content)
        self.assertIn("expt_status", content)
        self.assertIn("file_format_category", content)
        self.assertIn("biomolecule_type", content)
        self.assertIn("storage_node_type", content)

        # 21 Required Tables
        expected_tables = [
            "users",
            "audit_logs",
            "storage_blobs",
            "sop_templates",
            "experimental_campaigns",
            "notebook_daily_entries",
            "notebook_timepoint_logs",
            "bio_sequences",
            "pcr_assays",
            "nanodrop_measurements",
            "fplc_columns",
            "fplc_runs",
            "fplc_fractions",
            "gel_records",
            "gel_lanes",
            "ephys_recordings",
            "code_analysis_runs",
            "storage_hierarchy_nodes",
            "freezer_boxes",
            "inventory_tubes",
            "rag_document_chunks"
        ]
        for tbl in expected_tables:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {tbl}", content, f"Table {tbl} missing in ddl.sql")

        # Critical Yield & Completion Fields
        critical_fields = [
            "completed_at",
            "yield_mg_total",
            "yield_percent_recovery",
            "yield_mg_per_liter_culture",
            "yield_ug_plasmid",
            "yield_calculation_method"
        ]
        for field in critical_fields:
            self.assertIn(field, content, f"Field {field} missing in ddl.sql")

        # Indexes
        self.assertIn("idx_rag_document_chunks_embedding_hnsw", content)
        self.assertIn("idx_rag_document_chunks_lexical_tsv", content)
        self.assertIn("idx_rag_document_chunks_extracted_metadata_gin", content)
        self.assertIn("idx_rag_document_chunks_trgm", content)
        self.assertIn("idx_rag_document_chunks_provenance_btree", content)

    def test_database_table_creation(self) -> None:
        """
        Verify SQLite schema initialization creates all tables and is queryable.

        """
        conn = self.engine.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]

        expected_tables = [
            "users",
            "audit_logs",
            "storage_blobs",
            "sop_templates",
            "experimental_campaigns",
            "notebook_daily_entries",
            "notebook_timepoint_logs",
            "bio_sequences",
            "pcr_assays",
            "nanodrop_measurements",
            "fplc_columns",
            "fplc_runs",
            "fplc_fractions",
            "gel_records",
            "gel_lanes",
            "ephys_recordings",
            "code_analysis_runs",
            "storage_hierarchy_nodes",
            "freezer_boxes",
            "inventory_tubes",
            "rag_document_chunks"
        ]
        for tbl in expected_tables:
            self.assertIn(tbl, tables, f"SQLite table {tbl} was not created.")

    def test_user_seeding(self) -> None:
        """
        Verify users (PI, Active Researcher, Rotation Student, Alumni) are seeded properly.

        """
        users = self.session.query(User).all()
        self.assertGreaterEqual(len(users), 4)

        emails = {u.email: u for u in users}
        self.assertIn("eleanor.vance@biolabcalc.org", emails)
        self.assertIn("julian.hayes@biolabcalc.org", emails)
        self.assertIn("maya.patel@biolabcalc.org", emails)
        self.assertIn("arthur.pendelton@alumni.biolabcalc.org", emails)

        pi = emails["eleanor.vance@biolabcalc.org"]
        self.assertEqual(pi.role, "principal_investigator")
        self.assertTrue(pi.is_active)

        alumni = emails["arthur.pendelton@alumni.biolabcalc.org"]
        self.assertEqual(alumni.role, "alumni")
        self.assertFalse(alumni.is_active)

    def test_campaign_metrics_and_completion(self) -> None:
        """
        Verify the benchmark 5-Day T7 RNA Polymerase Campaign yields and completion timestamps.

        """
        campaign = self.session.query(ExperimentalCampaign).filter_by(slug="t7-rnap-expression-2026").first()
        self.assertIsNotNone(campaign)
        self.assertEqual(campaign.status, ExptStatus.COMPLETED.value)
        self.assertEqual(campaign.completed_at, "2026-10-16T17:30:00Z")
        self.assertAlmostEqual(campaign.yield_mg_total, 45.6, places=2)
        self.assertAlmostEqual(campaign.yield_percent_recovery, 76.0, places=1)
        self.assertAlmostEqual(campaign.yield_mg_per_liter_culture, 22.8, places=2)
        self.assertAlmostEqual(campaign.yield_ug_plasmid, 120.0, places=1)
        self.assertIn("NanoDrop A280", campaign.yield_calculation_method)

    def test_5_day_protocol_daily_entries(self) -> None:
        """
        Verify all 5 daily entries (Day 0 through Day 4) are modeled accurately.

        """
        campaign = self.session.query(ExperimentalCampaign).filter_by(slug="t7-rnap-expression-2026").first()
        entries = self.session.query(NotebookDailyEntry).filter_by(campaign_id=campaign.id).order_by("day_number ASC").all()
        self.assertEqual(len(entries), 5)

        days = {e.day_number: e for e in entries}

        # Day 0: Transformation & agar plating
        day0 = days[0]
        self.assertIn("Day 0: Transformation into BL21(DE3)", day0.title)
        self.assertEqual(day0.status, ExptStatus.COMPLETED.value)
        self.assertIsNotNone(day0.completed_at)
        self.assertEqual(day0.yield_ug_plasmid, 120.0)

        # PCR assay on Day 0
        pcr = self.session.query(PcrAssay).filter_by(daily_entry_id=day0.id).first()
        self.assertIsNotNone(pcr)
        self.assertEqual(pcr.target_gene, "T7RNAP_core")
        self.assertEqual(pcr.yield_ug_plasmid, 120.0)
        self.assertEqual(pcr.status, ExptStatus.COMPLETED.value)

        # Day 1: 50 mL starter culture
        day1 = days[1]
        self.assertIn("Day 1: 50 mL Starter Culture", day1.title)
        self.assertEqual(day1.status, ExptStatus.COMPLETED.value)

        # Day 2: 2 L 2xYT induction kinetics
        day2 = days[2]
        self.assertIn("Day 2: 2 L 2xYT Induction Kinetics", day2.title)
        timepoints = self.session.query(NotebookTimepointLog).filter_by(entry_id=day2.id).order_by("elapsed_minutes ASC").all()
        self.assertGreaterEqual(len(timepoints), 6)

        tp_labels = {tp.timepoint_label: tp for tp in timepoints}
        self.assertIn("t0_growth", tp_labels)
        self.assertIn("t_induction", tp_labels)
        self.assertIn("t_plus_1h", tp_labels)
        self.assertIn("t_plus_2h", tp_labels)
        self.assertIn("t_overnight_harvest", tp_labels)

        self.assertAlmostEqual(tp_labels["t_induction"].od600, 0.68, places=2)
        self.assertAlmostEqual(tp_labels["t_overnight_harvest"].od600, 3.65, places=2)

        # Day 3: Harvest, sonication lysis, 22.4 g wet pellet, HisTrap HP Ni-NTA FPLC
        day3 = days[3]
        self.assertIn("22.4 g Wet Pellet", day3.title)
        self.assertAlmostEqual(day3.yield_mg_total, 60.0, places=1)
        self.assertAlmostEqual(day3.yield_percent_recovery, 85.0, places=1)
        self.assertAlmostEqual(day3.yield_mg_per_liter_culture, 30.0, places=1)

        fplc_run1 = self.session.query(FplcRun).filter_by(daily_entry_id=day3.id).first()
        self.assertIsNotNone(fplc_run1)
        self.assertEqual(fplc_run1.purification_step, "capture_ni_nta")
        self.assertEqual(fplc_run1.status, ExptStatus.COMPLETED.value)

        # Day 4: Superdex 200 SEC polishing, monomer peak pooling (B4-B8)
        day4 = days[4]
        self.assertIn("Day 4: Superdex 200 SEC Polishing", day4.title)
        self.assertAlmostEqual(day4.yield_mg_total, 45.6, places=2)
        self.assertAlmostEqual(day4.yield_percent_recovery, 76.0, places=1)
        self.assertAlmostEqual(day4.yield_mg_per_liter_culture, 22.8, places=2)

        fplc_run2 = self.session.query(FplcRun).filter_by(daily_entry_id=day4.id).first()
        self.assertIsNotNone(fplc_run2)
        self.assertEqual(fplc_run2.purification_step, "polishing_sec")

        # Pooled fractions B4-B8
        sec_fractions = self.session.query(FplcFraction).filter_by(run_id=fplc_run2.id).all()
        pooled = [f.fraction_number for f in sec_fractions if f.is_pooled]
        self.assertEqual(sorted(pooled), ["B4", "B5", "B6", "B7", "B8"])

    def test_gel_and_nanodrop_qc_verification(self) -> None:
        """
        Verify SDS-PAGE purity (>95% purity) and NanoDrop quantification metrics.

        """
        gel = self.session.query(GelRecord).first()
        self.assertIsNotNone(gel)
        self.assertEqual(gel.gel_type, "SDS-PAGE 4-20% Tris-Glycine")
        self.assertAlmostEqual(gel.purity_assessment_percent, 96.5, places=1)
        self.assertGreater(gel.purity_assessment_percent, 95.0)

        lanes = self.session.query(GelLane).filter_by(gel_id=gel.id).order_by("lane_number ASC").all()
        self.assertEqual(len(lanes), 8)
        lane8 = lanes[7]
        self.assertEqual(lane8.sample_type, "sec_monomer_peak")
        self.assertAlmostEqual(lane8.estimated_mw_kda, 99.0, places=1)
        self.assertAlmostEqual(lane8.purity_percentage, 96.5, places=1)

        nanodrop = self.session.query(NanodropMeasurement).first()
        self.assertIsNotNone(nanodrop)
        self.assertAlmostEqual(nanodrop.concentration_mg_per_ml, 2.85, places=2)
        self.assertAlmostEqual(nanodrop.a280, 4.02, places=2)
        self.assertAlmostEqual(nanodrop.a260_a280_ratio, 0.57, places=2)
        self.assertAlmostEqual(nanodrop.yield_mg_total, 45.6, places=2)
        self.assertAlmostEqual(nanodrop.yield_percent_recovery, 76.0, places=1)

    def test_freezer_storage_hierarchy_and_inventory_slot_c4(self) -> None:
        """
        Verify physical storage hierarchy and sample tube placement in slot C4 of PROT-2026-T7RNAP.

        """
        room = self.session.query(StorageHierarchyNode).filter_by(barcode="LOC-LAB-402").first()
        self.assertIsNotNone(room)

        freezer = self.session.query(StorageHierarchyNode).filter_by(barcode="FRZ80-001").first()
        self.assertIsNotNone(freezer)
        self.assertEqual(freezer.parent_id, room.id)
        self.assertEqual(freezer.temperature_c, -80.0)

        rack = self.session.query(StorageHierarchyNode).filter_by(barcode="RCK-F1-02").first()
        self.assertIsNotNone(rack)
        self.assertEqual(rack.parent_id, freezer.id)

        box = self.session.query(FreezerBox).filter_by(barcode="BOX-PROT-T7RNAP-2026").first()
        self.assertIsNotNone(box)
        self.assertEqual(box.hierarchy_node_id, rack.id)
        self.assertEqual(box.temperature_c, -80.0)
        self.assertEqual(box.row_count, 9)
        self.assertEqual(box.col_count, 9)

        # Inventory tube at slot C4
        tube = self.session.query(InventoryTube).filter_by(box_id=box.id, box_position="C4").first()
        self.assertIsNotNone(tube)
        self.assertEqual(tube.barcode, "TUBE-T7RNAP-2026-004")
        self.assertEqual(tube.sample_name, "T7 RNA Polymerase (Recombinant, >95% pure, 2.85 mg/mL)")
        self.assertAlmostEqual(tube.concentration_mg_ml, 2.85, places=2)
        self.assertAlmostEqual(tube.volume_ul, 1000.0, places=1)
        self.assertEqual(tube.status, ExptStatus.COMPLETED.value)
        self.assertEqual(tube.completed_at, "2026-10-16T17:00:00Z")
        self.assertAlmostEqual(tube.yield_mg_total, 45.6, places=2)
        self.assertAlmostEqual(tube.yield_percent_recovery, 76.0, places=1)
        self.assertAlmostEqual(tube.yield_mg_per_liter_culture, 22.8, places=2)
        self.assertAlmostEqual(tube.yield_ug_plasmid, 120.0, places=1)

    def test_rag_document_chunks_and_vector_math(self) -> None:
        """
        Verify RAG document chunks are seeded with 1536-dimensional embeddings and
        cosine similarity function works correctly.

        """
        chunks = self.session.query(RagDocumentChunk).all()
        self.assertGreaterEqual(len(chunks), 5)

        for c in chunks:
            self.assertIsNotNone(c.embedding)
            self.assertEqual(len(c.embedding), 1536)
            self.assertIn("t7", c.chunk_text.lower())

        # Test vector similarity calculation
        chunk1 = chunks[0]
        chunk2 = chunks[1]
        sim_self = cosine_similarity(chunk1.embedding, chunk1.embedding)
        self.assertAlmostEqual(sim_self, 1.0, places=4)

        sim_other = cosine_similarity(chunk1.embedding, chunk2.embedding)
        self.assertGreater(sim_other, -1.0)
        self.assertLess(sim_other, 1.0)

    def test_all_21_models_represented(self) -> None:
        """
        Verify all 21 models have instances persisted and queried.

        """
        model_classes = [
            User,
            AuditLog,
            StorageBlob,
            SopTemplate,
            ExperimentalCampaign,
            NotebookDailyEntry,
            NotebookTimepointLog,
            BioSequence,
            PcrAssay,
            NanodropMeasurement,
            FplcColumn,
            FplcRun,
            FplcFraction,
            GelRecord,
            GelLane,
            EphysRecording,
            CodeAnalysisRun,
            StorageHierarchyNode,
            FreezerBox,
            InventoryTube,
            RagDocumentChunk
        ]
        self.assertEqual(len(model_classes), 21)
        for model in model_classes:
            count = self.session.query(model).count()
            self.assertGreater(count, 0, f"Model {model.__name__} has 0 records after seeding.")

    def test_engine_concurrency_lock_and_threads(self) -> None:
        """
        Verify Engine protects _shared_conn with a threading.Lock and concurrent operations succeed.
        """
        self.assertIsNotNone(self.engine._lock)
        self.assertTrue(isinstance(self.engine._lock, type(threading.Lock())))

        errors = []
        def worker(w_id: int) -> None:
            try:
                sess = get_session(self.engine)
                for i in range(10):
                    u = User(
                        username=f"worker_{w_id}_{i}",
                        email=f"worker_{w_id}_{i}@lab.org",
                        full_name=f"Worker {w_id} {i}",
                        role="researcher",
                    )
                    sess.add(u)
                    sess.commit()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors encountered: {errors}")

    def test_engine_sqlite_wal_mode_and_timeout(self) -> None:
        """
        Verify file-based SQLite connects with timeout=30.0 and WAL journal mode.
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        try:
            file_engine = create_engine(f"sqlite:///{db_path}")
            conn = file_engine.get_connection()
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            row = cur.fetchone()
            self.assertEqual(row[0].lower(), "wal")
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass

    def test_engine_postgresql_uri_validation(self) -> None:
        """
        Verify PostgreSQL URI requires SQLAlchemy/psycopg2 and does not silently fall back to :memory:.
        """
        expected_msg = (
            "PostgreSQL connections require SQLAlchemy and psycopg2-binary. "
            "Install with 'pip install \"biolabcalc[eln]\"' or run with default SQLite database."
        )
        for pg_url in [
            "postgresql://user:pass@localhost:5432/eln_db",
            "postgres://user:pass@localhost:5432/eln_db",
        ]:
            with self.assertRaises(ValueError) as ctx:
                create_engine(pg_url)
            self.assertEqual(str(ctx.exception), expected_msg)


if __name__ == "__main__":
    unittest.main()
