"""
Module: biolabcalc.eln.api.routes.sops
Component: Standard Operating Procedure (SOP) Versioning & Execution Forking REST Endpoints
Agent: @agent: eln-api-agent
Architectural Role: REST routes exposing master SOP protocol authoring, semantic versioning, PI approval,
and "Instantiate SOP into Daily Notebook Entry" execution forking with locked parameter state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.sop_service import get_sop_service
from ..auth import (
    PERM_SOP_APPROVE,
    PERM_SOP_CREATE,
    PERM_SOP_FORK,
    UserSession,
    get_auth_service,
)
from ..router import Router

router = Router(prefix="/api/sops")
sop_service = get_sop_service()
auth_service = get_auth_service()


@router.get("")
def list_sops(
    category: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """
    List master Standard Operating Procedures, optionally filtered by category or status.

    Agent: @agent: eln-api-agent
    Parameter category (Optional[str]): Category filter.
    Parameter status (Optional[str]): Status filter ('draft', 'approved', 'deprecated').
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    sops = sop_service.list_sops(category=category, status=status)
    return {"status": "success", "count": len(sops), "sops": [s.to_dict() for s in sops]}


@router.post("")
@auth_service.require_permission(PERM_SOP_CREATE)
def create_sop(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Create a new master SOP draft.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): SOP definition (sop_id, title, version, category, description, parameters, steps).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    sop = sop_service.create_sop(
        sop_id=payload["sop_id"],
        title=payload["title"],
        version=payload.get("version", "1.0"),
        category=payload.get("category", "Molecular Biology"),
        description=payload.get("description", ""),
        parameters=payload.get("parameters", {}),
        steps=payload.get("steps", []),
        created_by=user_id,
    )
    return {"status": "success", "sop": sop.to_dict()}


@router.get("/{sop_id}")
def get_sop(sop_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve master SOP by ID.

    Agent: @agent: eln-api-agent
    Parameter sop_id (str): SOP ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    sop = sop_service.get_sop(sop_id)
    if not sop:
        return {"status": "error", "message": f"SOP '{sop_id}' not found."}, 404
    return {"status": "success", "sop": sop.to_dict()}


@router.post("/{sop_id}/approve")
@auth_service.require_permission(PERM_SOP_APPROVE)
def approve_sop(sop_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Approve an SOP, locking it for regulated experimental execution.

    Agent: @agent: eln-api-agent
    Parameter sop_id (str): Target SOP ID.
    Parameter current_user (Optional[UserSession]): Authorizing PI.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "pi_admin"
    sop = sop_service.approve_sop(sop_id=sop_id, approver_id=user_id)
    return {"status": "success", "sop": sop.to_dict()}


@router.post("/{sop_id}/fork")
@auth_service.require_permission(PERM_SOP_FORK)
def fork_sop_for_entry(sop_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Instantiate SOP into Daily Notebook Entry, locking parameter state and creating execution checklist.

    Agent: @agent: eln-api-agent
    Parameter sop_id (str): Master SOP ID.
    Parameter payload (Dict[str, Any]): Fork parameters ('entry_id': str, optional 'parameter_overrides': dict).
    Parameter current_user (Optional[UserSession]): Operator executing fork.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    fork = sop_service.fork_sop_for_entry(
        sop_id=sop_id,
        entry_id=payload["entry_id"],
        forked_by=user_id,
        parameter_overrides=payload.get("parameter_overrides"),
    )
    return {"status": "success", "fork": fork.to_dict()}


@router.get("/forks/{fork_id}")
def get_sop_fork(fork_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve instantiated SOP fork and its interactive execution checklist.

    Agent: @agent: eln-api-agent
    Parameter fork_id (str): Fork ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    fork = sop_service.get_fork(fork_id)
    if not fork:
        return {"status": "error", "message": f"SOP Fork '{fork_id}' not found."}, 404
    return {"status": "success", "fork": fork.to_dict()}


@router.post("/forks/{fork_id}/checkoff")
def checkoff_step(fork_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Checkoff an instantiated SOP step with actual duration and deviation notes.

    Agent: @agent: eln-api-agent
    Parameter fork_id (str): Target SOP fork ID.
    Parameter payload (Dict[str, Any]): Checkoff parameters ('step_index': int, optional 'actual_duration_minutes', 'deviation_notes').
    Parameter current_user (Optional[UserSession]): Authenticated operator.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    fork = sop_service.checkoff_step(
        fork_id=fork_id,
        step_index=int(payload["step_index"]),
        completed_by=user_id,
        actual_duration_minutes=float(payload["actual_duration_minutes"]) if "actual_duration_minutes" in payload else None,
        deviation_notes=payload.get("deviation_notes", ""),
    )
    return {"status": "success", "fork": fork.to_dict()}
