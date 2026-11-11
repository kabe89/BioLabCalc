"""
Module: biolabcalc.eln.api.routes.timepoints
Component: Kinetic Timepoint & Real-Time Countdown Timer REST Endpoints
Agent: @agent: eln-api-agent
Architectural Role: REST routes exposing second-resolution kinetic timepoint recording, elapsed delta t0
calculations, SOP planned duration deviation monitoring, and active live countdown timers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.timepoint_service import get_timepoint_service
from ..auth import PERM_TIMEPOINT_RECORD, UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/timepoints")
timepoint_service = get_timepoint_service()
auth_service = get_auth_service()


@router.get("/{entry_id}")
def get_entry_timepoints(entry_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Get all kinetic timepoints recorded for a given daily notebook entry.

    Agent: @agent: eln-api-agent
    Parameter entry_id (str): Daily notebook entry ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    timepoints = timepoint_service.get_entry_timepoints(entry_id)
    return {"status": "success", "count": len(timepoints), "timepoints": [tp.to_dict() for tp in timepoints]}


@router.post("")
@auth_service.require_permission(PERM_TIMEPOINT_RECORD)
def record_timepoint(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Record a kinetic timepoint with second resolution and duration deviation logging.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Timepoint parameters (entry_id, step_name, t0, timestamp, planned_duration_seconds, parameters, notes).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    tp = timepoint_service.record_timepoint(
        entry_id=payload["entry_id"],
        step_name=payload["step_name"],
        t0=payload["t0"],
        timestamp=payload.get("timestamp"),
        planned_duration_seconds=float(payload["planned_duration_seconds"]) if "planned_duration_seconds" in payload else None,
        parameters=payload.get("parameters"),
        notes=payload.get("notes", ""),
        created_by=user_id,
    )
    return {"status": "success", "timepoint": tp.to_dict()}


@router.post("/timers/start")
def start_live_timer(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Start an active live countdown timer.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Timer parameters (name, target_duration_seconds, entry_id, metadata).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    timer = timepoint_service.start_live_timer(
        name=payload["name"],
        target_duration_seconds=float(payload["target_duration_seconds"]),
        entry_id=payload.get("entry_id"),
        metadata=payload.get("metadata"),
    )
    return {"status": "success", "timer": timer.tick()}


@router.get("/timers")
def list_active_timers(current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    List all active live timers with real-time computed countdown states.

    Agent: @agent: eln-api-agent
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    timers = timepoint_service.list_active_timers()
    return {"status": "success", "count": len(timers), "timers": timers}


@router.post("/timers/{timer_id}/stop")
def stop_live_timer(timer_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Stop and finalize an active live timer.

    Agent: @agent: eln-api-agent
    Parameter timer_id (str): Target timer ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    stopped = timepoint_service.stop_live_timer(timer_id)
    if not stopped:
        return {"status": "error", "message": f"Timer '{timer_id}' not found."}, 404
    return {"status": "success", "timer": stopped}
