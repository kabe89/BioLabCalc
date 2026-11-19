"""
Module: biolabcalc.eln.api.routes.progress_reports
Component: Custom Logging & Progress Reporting REST Endpoints
Architectural Role: REST routes for structured custom notebook entries, periodic research
progress report generation, multi-modal metric aggregation, and HTML/MD/CSV export.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.progress_report_service import get_progress_report_service
from ..auth import UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/v1")
report_service = get_progress_report_service()
auth_service = get_auth_service()


@router.get("/logs")
def list_logs(
    category: Optional[str] = None,
    author: Optional[str] = None,
    tag: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """List custom structured log entries with optional filters."""
    logs = report_service.list_log_entries(category=category, author=author, tag=tag)
    return {"status": "success", "count": len(logs), "logs": logs}


@router.post("/logs")
def create_log(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Create a new custom structured log entry."""
    user = current_user.username if current_user else payload.get("author", "active_researcher")
    entry = report_service.create_log_entry(
        title=payload["title"],
        category=payload.get("category", "bench_daily"),
        author=user,
        body_md=payload.get("body_md", ""),
        tags=payload.get("tags"),
        metrics=payload.get("metrics"),
        linked_entity_ids=payload.get("linked_entity_ids"),
    )
    return {"status": "success", "log": entry}


@router.get("/logs/{log_id}")
def get_log(log_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Retrieve an individual custom log entry."""
    entry = report_service.get_log_entry(log_id)
    if not entry:
        return {"status": "error", "message": f"Log entry '{log_id}' not found"}
    return {"status": "success", "log": entry}


@router.delete("/logs/{log_id}")
def delete_log(log_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Delete a custom log entry."""
    success = report_service.delete_log_entry(log_id)
    return {"status": "success" if success else "error", "deleted": success}


@router.get("/reports/progress")
def list_progress_reports(current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """List all periodic progress reports."""
    reports = report_service.list_progress_reports()
    return {"status": "success", "count": len(reports), "reports": reports}


@router.post("/reports/progress")
def generate_progress_report(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Generate periodic progress report by aggregating lab activities across date range."""
    user = current_user.username if current_user else payload.get("author", "active_researcher")
    title = payload.get("title") or "Progress Report"
    p_start = payload.get("period_start") or payload.get("start_date") or "1970-01-01"
    p_end = payload.get("period_end") or payload.get("end_date") or "2099-12-31"
    rep = report_service.generate_progress_report(
        title=title,
        period_start=p_start,
        period_end=p_end,
        created_by=user,
        template_type=payload.get("template_type", "standard"),
        summary_md=payload.get("summary_md", ""),
    )
    return {"status": "success", "report": rep}


@router.get("/reports/progress/{report_id}")
def get_progress_report(report_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Retrieve details of a single progress report."""
    rep = report_service.get_progress_report(report_id)
    if not rep:
        return {"status": "error", "message": f"Progress report '{report_id}' not found"}
    return {"status": "success", "report": rep}


@router.get("/reports/progress/{report_id}/export")
def export_progress_report(
    report_id: str, format: str = "html", current_user: Optional[UserSession] = None
) -> Dict[str, Any]:
    """Export progress report in HTML, Markdown, or CSV format."""
    try:
        exported = report_service.export_progress_report(report_id, format=format)
        return {"status": "success", "format": format, "report": exported}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
