"""
Module: biolabcalc.eln.services.progress_report_service
Component: Custom Logging & Automated Periodic Progress Reporting Service
Architectural Role: Core ELN service managing custom structured log entries across categories
(bench_daily, weekly_pi, mouse_colony, troubleshooting, grant_milestone) and automated period rollups.
"""

from __future__ import annotations

import csv
import html
import io
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..storage.sqlite_store import SQLiteStore, get_sqlite_store

logger = logging.getLogger("biolabcalc.eln.services.progress_report_service")


class ProgressReportService:
    """Thread-safe persistent service managing custom lab logs and periodic progress reports."""

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self._store = store or get_sqlite_store()
        self._lock = threading.RLock()

    # -------------------------------------------------------------------------
    # Custom Log Entries
    # -------------------------------------------------------------------------

    def create_log_entry(
        self,
        title: str,
        category: str = "bench_daily",
        author: str = "active_researcher",
        body_md: str = "",
        tags: Optional[Any] = None,
        metrics: Optional[Dict[str, Any]] = None,
        linked_entity_ids: Optional[List[str]] = None,
        content: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a custom log entry in the persistent store."""
        with self._lock:
            log_id = f"log_{uuid.uuid4().hex[:10]}"
            now_iso = created_at or datetime.now(timezone.utc).isoformat()
            final_body = content if (content is not None and not body_md) else body_md
            tags_list = list(tags) if tags is not None else []
            data = {
                "log_id": log_id,
                "entry_id": log_id,
                "category": category,
                "title": title,
                "author": author,
                "body_md": final_body,
                "tags": tags_list,
                "metrics": metrics or {},
                "linked_entity_ids": linked_entity_ids or [],
                "created_at": now_iso,
            }
            self._store.put_entity("custom_log_entry", log_id, data)
            logger.info(f"Created custom log entry '{title}' ({log_id}) in '{category}'")
            return data

    def get_log_entry(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a custom log entry by identifier."""
        return self._store.get_entity("custom_log_entry", log_id)

    def list_log_entries(
        self,
        category: Optional[str] = None,
        author: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List log entries with optional category, author, or tag filters."""
        entries = self._store.list_entities("custom_log_entry")
        if category:
            entries = [e for e in entries if e.get("category") == category]
        if author:
            entries = [e for e in entries if e.get("author") == author]
        if tag:
            entries = [e for e in entries if tag in e.get("tags", [])]
        return sorted(entries, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_log_entry(self, log_id: str) -> bool:
        """Delete custom log entry."""
        with self._lock:
            existing = self.get_log_entry(log_id)
            if not existing:
                return False
            self._store.delete_entity("custom_log_entry", log_id)
            logger.info(f"Deleted custom log entry {log_id}")
            return True

    # -------------------------------------------------------------------------
    # Progress Reports & Rollups
    # -------------------------------------------------------------------------

    def generate_progress_report(
        self,
        title: str = "Progress Report",
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        created_by: str = "active_researcher",
        template_type: str = "standard",
        summary_md: str = "",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        author: Optional[str] = None,
        grant_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate lab activities over a specified date range and generate progress report."""
        with self._lock:
            p_start = period_start or start_date or "1970-01-01"
            p_end = period_end or end_date or "2099-12-31"
            creator = author or created_by
            report_id = f"prep_{uuid.uuid4().hex[:10]}"
            now_iso = datetime.now(timezone.utc).isoformat()

            # Roll up multi-modal entities from SQLiteStore
            campaigns = self._store.list_entities("campaign")
            custom_logs = self._store.list_entities("custom_log_entry")
            mouse_obs = self._store.list_entities("mouse_observation")
            purchases = self._store.list_entities("purchase_order")

            # Date filtering helper
            def in_range(date_str: Optional[str]) -> bool:
                if not date_str:
                    return False
                d = date_str[:10]
                return p_start[:10] <= d <= p_end[:10]

            filtered_campaigns = [c for c in campaigns if in_range(c.get("created_at") or c.get("start_date"))]
            filtered_logs = [l for l in custom_logs if in_range(l.get("created_at"))]
            filtered_mouse = [m for m in mouse_obs if in_range(m.get("timestamp"))]
            filtered_purchases = [p for p in purchases if in_range(p.get("created_at") or p.get("ordered_at"))]

            if grant_code:
                filtered_purchases = [p for p in filtered_purchases if p.get("grant_code") == grant_code]

            total_spend = sum(float(p.get("total_cost_usd", 0.0)) for p in filtered_purchases)

            metrics_snapshot = {
                "campaigns_count": len(filtered_campaigns),
                "custom_logs_count": len(filtered_logs),
                "mouse_observations_count": len(filtered_mouse),
                "purchases_count": len(filtered_purchases),
                "total_purchases_usd": round(total_spend, 2),
                "rolled_up_entities": {
                    "campaign_ids": [c.get("campaign_id") for c in filtered_campaigns if c.get("campaign_id")],
                    "log_ids": [l.get("log_id") for l in filtered_logs if l.get("log_id")],
                    "mouse_observation_ids": [m.get("observation_id") for m in filtered_mouse if m.get("observation_id")],
                    "purchase_ids": [p.get("order_id") for p in filtered_purchases if p.get("order_id")],
                },
            }

            data = {
                "report_id": report_id,
                "title": title,
                "period_start": p_start,
                "period_end": p_end,
                "template_type": template_type,
                "summary_md": summary_md or f"Periodic progress report covering {p_start} to {p_end}.",
                "metrics_snapshot": metrics_snapshot,
                "summary_metrics": {
                    "total_entries": len(filtered_logs),
                    "campaigns_count": len(filtered_campaigns),
                    "purchases_count": len(filtered_purchases),
                    "total_purchases_usd": round(total_spend, 2),
                },
                "created_by": creator,
                "created_at": now_iso,
            }
            self._store.put_entity("progress_report", report_id, data)
            logger.info(f"Generated progress report '{title}' ({report_id})")
            return data

    generate_rollup_report = generate_progress_report

    def get_progress_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve progress report by identifier."""
        return self._store.get_entity("progress_report", report_id)

    get_report = get_progress_report

    def list_progress_reports(self) -> List[Dict[str, Any]]:
        """List all generated progress reports."""
        reports = self._store.list_entities("progress_report")
        return sorted(reports, key=lambda x: x.get("created_at", ""), reverse=True)

    def export_progress_report(self, report_id: str, format: str = "html") -> str:
        """Export progress report into printable HTML, Markdown, or CSV."""
        rep = self.get_progress_report(report_id)
        if not rep:
            raise ValueError(f"Progress report '{report_id}' not found.")

        m = rep.get("metrics_snapshot", {})
        esc = html.escape

        if format.lower() == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["Report ID", "Title", "Period Start", "Period End", "Metric", "Value"])
            writer.writerow([rep["report_id"], rep["title"], rep["period_start"], rep["period_end"], "Campaigns Count", m.get("campaigns_count", 0)])
            writer.writerow([rep["report_id"], rep["title"], rep["period_start"], rep["period_end"], "Custom Logs Count", m.get("custom_logs_count", 0)])
            writer.writerow([rep["report_id"], rep["title"], rep["period_start"], rep["period_end"], "Mouse Observations", m.get("mouse_observations_count", 0)])
            writer.writerow([rep["report_id"], rep["title"], rep["period_start"], rep["period_end"], "Purchases Count", m.get("purchases_count", 0)])
            writer.writerow([rep["report_id"], rep["title"], rep["period_start"], rep["period_end"], "Total Spend USD", m.get("total_purchases_usd", 0.0)])
            for lid in m.get("rolled_up_entities", {}).get("log_ids", []):
                l_entry = self.get_log_entry(lid)
                if l_entry:
                    writer.writerow([rep["report_id"], rep["title"], rep["period_start"], rep["period_end"], f"Log: {l_entry.get('title')}", l_entry.get("body_md", "")])
            return buf.getvalue()

        if format.lower() in ("md", "markdown"):
            md_lines = [
                f"# 📊 Research Progress Report: {rep['title']}",
                "",
                f"- **Reporting Period:** `{rep['period_start']}` to `{rep['period_end']}`",
                f"- **Author:** {rep['created_by']}",
                f"- **Generated:** {rep['created_at']}",
                "",
                "## Executive Summary",
                "",
                rep.get("summary_md", "No summary provided."),
                "",
                "## Period Metrics Rollup",
                "",
                "| Activity / Resource Category | Total Count / Amount |",
                "| :--- | :--- |",
                f"| Active Experimental Campaigns | {m.get('campaigns_count', 0)} |",
                f"| Custom Bench & Colony Logs | {m.get('custom_logs_count', 0)} |",
                f"| In-Vivo Mouse Observations | {m.get('mouse_observations_count', 0)} |",
                f"| Purchase Orders Processed | {m.get('purchases_count', 0)} |",
                f"| Total Purchase Expenditure | ${m.get('total_purchases_usd', 0.0):,.2f} USD |",
                "",
            ]
            log_ids = m.get("rolled_up_entities", {}).get("log_ids", [])
            if log_ids:
                md_lines.extend([
                    "## Rolled-Up Log Entries",
                    "",
                ])
                for lid in log_ids:
                    l_entry = self.get_log_entry(lid)
                    if l_entry:
                        md_lines.append(f"- **[{l_entry.get('category')}] {l_entry.get('title')}** ({l_entry.get('created_at', '')[:10]}): {l_entry.get('body_md', '')}")
                md_lines.append("")
            return "\n".join(md_lines)

        # Default HTML
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Progress Report: {esc(rep['title'])}</title>
<style>
  :root {{
    --bg: #FFFFFF;
    --surface: #F8FAFC;
    --ink: #0F172A;
    --ink-muted: #64748B;
    --hairline: #E2E8F0;
    --accent: #1D4ED8;
  }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--ink);
    margin: 0;
    padding: 24px;
    line-height: 1.5;
  }}
  .container {{ max-width: 860px; margin: 0 auto; }}
  .header {{
    border-bottom: 2px solid var(--ink);
    padding-bottom: 12px;
    margin-bottom: 20px;
  }}
  .btn-print {{
    background: var(--accent);
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    float: right;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin: 16px 0;
  }}
  .metric-card {{
    border: 1px solid var(--hairline);
    border-radius: 8px;
    padding: 12px;
    background: var(--surface);
    text-align: center;
  }}
  .metric-val {{ font-size: 22px; font-weight: 700; color: var(--accent); margin-top: 4px; }}
  .metric-lbl {{ font-size: 11px; text-transform: uppercase; color: var(--ink-muted); font-weight: 600; }}
  .section {{
    border: 1px solid var(--hairline);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
    background: var(--bg);
  }}
  @media print {{
    .btn-print {{ display: none !important; }}
    body {{ padding: 0; }}
    .section {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
<div class="container">
  <button class="btn-print" onclick="window.print()">🖨️ Print Report</button>
  <div class="header">
    <h1 style="margin: 0 0 6px 0; font-size: 22px;">📊 Research Progress Report: {esc(rep['title'])}</h1>
    <div style="font-size: 13px; color: var(--ink-muted);">
      <strong>Period:</strong> {esc(rep['period_start'])} to {esc(rep['period_end'])} • <strong>Author:</strong> {esc(rep['created_by'])}
    </div>
  </div>

  <div class="grid">
    <div class="metric-card">
      <div class="metric-lbl">Campaigns</div>
      <div class="metric-val">{m.get('campaigns_count', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="metric-lbl">Custom Logs</div>
      <div class="metric-val">{m.get('custom_logs_count', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="metric-lbl">Mouse Obs</div>
      <div class="metric-val">{m.get('mouse_observations_count', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="metric-lbl">Purchases</div>
      <div class="metric-val">{m.get('purchases_count', 0)}</div>
    </div>
    <div class="metric-card">
      <div class="metric-lbl">Spend (USD)</div>
      <div class="metric-val">${m.get('total_purchases_usd', 0.0):,.0f}</div>
    </div>
  </div>

  <div class="section">
    <h3 style="margin: 0 0 8px 0; font-size: 15px;">Executive Summary</h3>
    <div style="font-size: 14px; color: #334155; white-space: pre-wrap;">{esc(rep.get('summary_md', ''))}</div>
  </div>
</div>
</body>
</html>
"""

    export_report = export_progress_report


_progress_report_service_instance: Optional[ProgressReportService] = None
_progress_report_service_lock = threading.Lock()


def get_progress_report_service() -> ProgressReportService:
    """Retrieve singleton instance of ProgressReportService."""
    global _progress_report_service_instance
    if _progress_report_service_instance is None:
        with _progress_report_service_lock:
            if _progress_report_service_instance is None:
                _progress_report_service_instance = ProgressReportService()
    return _progress_report_service_instance
