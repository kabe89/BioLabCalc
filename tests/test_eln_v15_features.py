"""
Unit and integration tests for BioLabCalc v1.5.0 ELN features:
Purchase orders, consumable inventory synchronization, progress logs,
period rollup reports, and REST API endpoints with restart persistence.
"""

from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from typing import Any, Dict

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.api.app import TestClient, create_app
from biolabcalc.eln.services.progress_report_service import ProgressReportService
from biolabcalc.eln.services.purchase_service import PurchaseService
from biolabcalc.eln.storage.sqlite_store import SQLiteStore


class TestPurchaseService(unittest.TestCase):
    """Test suite verifying purchase order lifecycle, spend analytics, and persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_lims.db")
        self.store = SQLiteStore(self.db_path)
        self.service = PurchaseService(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_purchase_order_lifecycle_and_auto_stock(self) -> None:
        """Test full PO state machine: REQUESTED -> APPROVED -> ORDERED -> RECEIVED -> STOCKED."""
        order = self.service.create_order(
            item_name="Q5 High-Fidelity 2X Master Mix",
            catalog_number="M0492L",
            vendor="New England Biolabs",
            quantity=2,
            unit_price_usd=325.0,
            grant_code="NIH-R01-GM12345",
            requested_by="Dr. Elena Rostova",
            notes="Expedited shipping for Day 3 PCR",
        )
        self.assertIsNotNone(order)
        self.assertEqual(order["status"], "REQUESTED")
        self.assertEqual(order["total_cost_usd"], 650.0)

        po_id = order["order_id"]

        # Advance state
        appr = self.service.update_status(po_id, "APPROVED")
        self.assertEqual(appr["status"], "APPROVED")

        ord_res = self.service.update_status(po_id, "ORDERED")
        self.assertEqual(ord_res["status"], "ORDERED")

        rec_res = self.service.update_status(po_id, "RECEIVED")
        self.assertEqual(rec_res["status"], "RECEIVED")

        # 1-click receive and stock into inventory
        stock_res = self.service.receive_and_stock(
            order_id=po_id,
            location_id="Freezer_Alpha_Box_B07",
            lot_number="LOT-2026-NEB-001",
            aliquot_count=2,
        )
        self.assertIsNotNone(stock_res)
        self.assertEqual(stock_res["order"]["status"], "STOCKED")
        self.assertIn("tubes", stock_res)
        self.assertEqual(len(stock_res["tubes"]), 2)

    def test_spend_summary_and_csv_export(self) -> None:
        """Test financial spend analytics and CSV export generation."""
        self.service.create_order(
            item_name="T7 RNA Polymerase WT",
            catalog_number="T7-001",
            vendor="Biolabs",
            quantity=1,
            unit_price_usd=120.0,
            grant_code="NIH-R01-GM12345",
        )
        self.service.create_order(
            item_name="CleanCap AG",
            catalog_number="N-7413",
            vendor="TriLink",
            quantity=2,
            unit_price_usd=250.0,
            grant_code="LAB-DISCRETIONARY",
        )

        summary = self.service.get_spend_summary()
        self.assertGreaterEqual(summary["total_spend_usd"], 620.0)
        self.assertIn("NIH-R01-GM12345", summary["spend_by_grant"])
        self.assertIn("LAB-DISCRETIONARY", summary["spend_by_grant"])
        self.assertEqual(summary["spend_by_grant"]["LAB-DISCRETIONARY"], 500.0)

        csv_text = self.service.export_orders_csv()
        self.assertIn("Order ID", csv_text)
        self.assertIn("T7 RNA Polymerase WT", csv_text)
        self.assertIn("CleanCap AG", csv_text)

    def test_purchase_orders_restart_persistence(self) -> None:
        """Verify purchase orders and their stocked inventory persist across store restarts."""
        order = self.service.create_order(
            item_name="Precast Gels 4-20%",
            catalog_number="4561094",
            vendor="Bio-Rad",
            quantity=5,
            unit_price_usd=28.0,
            grant_code="CORE-FUNDS",
        )
        po_id = order["order_id"]
        self.service.receive_and_stock(order_id=po_id, location_id="Cold_Room_Shelf_2")

        # Simulate full application restart
        self.store.close()

        restarted_store = SQLiteStore(self.db_path)
        try:
            restarted_service = PurchaseService(restarted_store)
            retrieved = restarted_service.get_order(po_id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved["status"], "STOCKED")
            self.assertEqual(retrieved["total_cost_usd"], 140.0)

            all_orders = restarted_service.list_orders()
            self.assertEqual(len(all_orders), 1)
            self.assertEqual(all_orders[0]["item_name"], "Precast Gels 4-20%")
        finally:
            restarted_store.close()


class TestProgressReportService(unittest.TestCase):
    """Test suite verifying bench log entries, period rollup reports, and persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_lims.db")
        self.store = SQLiteStore(self.db_path)
        self.service = ProgressReportService(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_log_entry_creation_and_filtering(self) -> None:
        """Test creating log entries across categories and filtering by tag and category."""
        e1 = self.service.create_log_entry(
            category="bench_daily",
            title="Ni-NTA Column Elution B4-B8",
            content="Pooled 5.0 mL elution peak at 3.85 mg/mL.",
            author="Dr. Elena Rostova",
            tags=("purification", "fplc", "t7rnap"),
        )
        self.assertIsNotNone(e1)
        self.assertEqual(e1["category"], "bench_daily")

        e2 = self.service.create_log_entry(
            category="mouse_colony",
            title="Cohort M-001 Baseline Weighed",
            content="Baseline weight 25.2 g, healthy grooming.",
            author="Dr. Elena Rostova",
            tags=("in-vivo", "dosing"),
        )
        self.assertEqual(e2["category"], "mouse_colony")

        # Filter by category
        daily_entries = self.service.list_log_entries(category="bench_daily")
        self.assertEqual(len(daily_entries), 1)
        self.assertEqual(daily_entries[0]["title"], "Ni-NTA Column Elution B4-B8")

        colony_entries = self.service.list_log_entries(category="mouse_colony")
        self.assertEqual(len(colony_entries), 1)
        self.assertEqual(colony_entries[0]["title"], "Cohort M-001 Baseline Weighed")

    def test_progress_rollup_generation_and_export(self) -> None:
        """Test compiling period rollup reports and exporting in Markdown, HTML, and CSV."""
        self.service.create_log_entry(
            category="bench_daily",
            title="Day 1 Transformation",
            content="Transform BL21(DE3) with pET28a-T7RNAP.",
            created_at="2026-11-05T10:00:00",
        )
        self.service.create_log_entry(
            category="grant_milestone",
            title="Milestone 1 Completed",
            content="Construct verified by Sanger sequencing.",
            created_at="2026-11-12T14:30:00",
        )

        rollup = self.service.generate_rollup_report(
            start_date="2026-11-01",
            end_date="2026-11-30",
            author="Dr. Elena Rostova",
            grant_code="NIH-R01-GM12345",
        )
        self.assertIsNotNone(rollup)
        self.assertIn("summary_metrics", rollup)
        self.assertEqual(rollup["summary_metrics"]["total_entries"], 2)

        report_id = rollup["report_id"]

        # Export formats
        md_text = self.service.export_report(report_id, format="markdown")
        self.assertIn("Research Progress Report", md_text)
        self.assertIn("Day 1 Transformation", md_text)
        self.assertIn("Milestone 1 Completed", md_text)

        html_text = self.service.export_report(report_id, format="html")
        self.assertIn("<html", html_text)
        self.assertIn("Research Progress Report", html_text)

        csv_text = self.service.export_report(report_id, format="csv")
        self.assertIn("Report ID", csv_text)
        self.assertIn("Day 1 Transformation", csv_text)

    def test_progress_reports_restart_persistence(self) -> None:
        """Verify logs and rollup reports persist across store restarts."""
        entry = self.service.create_log_entry(
            category="troubleshooting",
            title="Sonication probe cavitation",
            content="Adjusted amplitude to 35% to avoid foaming.",
        )
        entry_id = entry["entry_id"]

        report = self.service.generate_rollup_report(
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        report_id = report["report_id"]

        # Simulate restart
        self.store.close()

        restarted_store = SQLiteStore(self.db_path)
        try:
            restarted_service = ProgressReportService(restarted_store)
            entries = restarted_service.list_log_entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["entry_id"], entry_id)

            retrieved_report = restarted_service.get_report(report_id)
            self.assertIsNotNone(retrieved_report)
            self.assertEqual(retrieved_report["report_id"], report_id)
        finally:
            restarted_store.close()


class TestV15APIRoutes(unittest.TestCase):
    """Test suite verifying REST API routes for purchases and progress reports via TestClient."""

    def setUp(self) -> None:
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_purchases_api_endpoints(self) -> None:
        """Test GET, POST, summary, and receive endpoints on /api/v1/purchases."""
        # Create order
        create_res = self.client.post(
            "/api/v1/purchases",
            payload={
                "item_name": "Phusion High-Fidelity DNA Polymerase",
                "catalog_number": "F530L",
                "vendor": "Thermo Fisher",
                "quantity": 1,
                "unit_price_usd": 210.0,
                "grant_code": "NIH-R01-GM12345",
            },
        )
        self.assertEqual(create_res["status_code"], 200)
        po_id = create_res["json"]["order"]["order_id"]

        # List orders
        list_res = self.client.get("/api/v1/purchases")
        self.assertEqual(list_res["status_code"], 200)
        orders = list_res["json"].get("orders", list_res["json"])
        self.assertGreaterEqual(len(orders), 1)

        # Summary
        summary_res = self.client.get("/api/v1/purchases/summary")
        self.assertEqual(summary_res["status_code"], 200)
        summary = summary_res["json"].get("summary", summary_res["json"])
        self.assertIn("total_spend_usd", summary)

        # Receive & stock
        recv_res = self.client.post(f"/api/v1/purchases/{po_id}/receive")
        self.assertEqual(recv_res["status_code"], 200)
        self.assertEqual(recv_res["json"]["order"]["status"], "STOCKED")

    def test_progress_reports_api_endpoints(self) -> None:
        """Test GET, POST, and export endpoints on /api/v1/logs and /api/v1/reports/progress."""
        # Create log entry
        log_res = self.client.post(
            "/api/v1/logs",
            payload={
                "category": "bench_daily",
                "title": "IPTG Induction at OD600 0.72",
                "content": "Added 0.5 mM IPTG, moved flask to 25°C shaker for 4 hours.",
                "author": "Dr. Elena Rostova",
            },
        )
        self.assertEqual(log_res["status_code"], 200)
        log_entry = log_res["json"]["log"]
        self.assertIn("entry_id", log_entry)

        # List logs
        list_res = self.client.get("/api/v1/logs?category=bench_daily")
        self.assertEqual(list_res["status_code"], 200)
        logs = list_res["json"].get("logs", list_res["json"])
        self.assertGreaterEqual(len(logs), 1)

        # Generate rollup
        rollup_res = self.client.post(
            "/api/v1/reports/progress",
            payload={
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "author": "Dr. Elena Rostova",
            },
        )
        self.assertEqual(rollup_res["status_code"], 200)
        rep = rollup_res["json"]["report"]
        report_id = rep["report_id"]

        # Export report
        export_res = self.client.get(f"/api/v1/reports/progress/{report_id}/export?format=markdown")
        self.assertEqual(export_res["status_code"], 200)


if __name__ == "__main__":
    unittest.main()
