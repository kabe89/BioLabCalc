"""
Module: biolabcalc.eln.api.routes.campaigns
Component: Experimental Campaign & Daily Entry REST Endpoints
Architectural Role: REST routes exposing campaign lifecycle state transitions, daily notebook entries,
cross-day carry-forward state math (harvest pellet weight to lysis buffer), daily rollups, and final yields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.campaign_service import get_campaign_service
from ..auth import (
    PERM_CAMPAIGN_COMPLETE,
    PERM_CAMPAIGN_CREATE,
    PERM_ENTRY_CREATE,
    PERM_ENTRY_EDIT,
    UserSession,
    get_auth_service,
)
from ..router import Router

router = Router(prefix="/api/campaigns")
campaign_service = get_campaign_service()
auth_service = get_auth_service()


@router.get("")
def list_campaigns(status: Optional[str] = None, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    List all experimental campaigns, optionally filtered by lifecycle status.

    Parameter status (Optional[str]): Status filter ('planned', 'in_progress', 'completed').
    Parameter current_user (Optional[UserSession]): Authenticated session.
    Return Type: Dict[str, Any]
    """
    campaigns = campaign_service.list_campaigns(status=status)
    return {"status": "success", "count": len(campaigns), "campaigns": [c.to_dict() for c in campaigns]}


@router.post("")
@auth_service.require_permission(PERM_CAMPAIGN_CREATE)
def create_campaign(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Create a new experimental campaign.

    Parameter payload (Dict[str, Any]): Campaign definition (title, description, construct_id, target_organism).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "pi_admin"
    campaign = campaign_service.create_campaign(
        title=payload["title"],
        description=payload.get("description", ""),
        construct_id=payload["construct_id"],
        created_by=user_id,
        target_organism=payload.get("target_organism", "E. coli BL21(DE3)"),
        start_date=payload.get("start_date"),
    )
    return {"status": "success", "campaign": campaign.to_dict()}


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve single campaign by ID.

    Parameter campaign_id (str): Unique campaign ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    campaign = campaign_service.get_campaign(campaign_id)
    if not campaign:
        return {"status": "error", "message": f"Campaign '{campaign_id}' not found."}, 404
    return {"status": "success", "campaign": campaign.to_dict()}


@router.post("/{campaign_id}/entries")
@auth_service.require_permission(PERM_ENTRY_CREATE)
def add_daily_entry(campaign_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Add a daily notebook entry to a campaign.

    Parameter campaign_id (str): Target campaign ID.
    Parameter payload (Dict[str, Any]): Daily entry fields (day_number, title, date, notes, state_inputs).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    entry = campaign_service.add_daily_entry(
        campaign_id=campaign_id,
        day_number=int(payload["day_number"]),
        title=payload["title"],
        created_by=user_id,
        date=payload.get("date"),
        sop_fork_id=payload.get("sop_fork_id"),
        state_inputs=payload.get("state_inputs"),
        notes=payload.get("notes", ""),
    )
    return {"status": "success", "entry": entry.to_dict()}


@router.put("/{campaign_id}/entries/{entry_id}")
@auth_service.require_permission(PERM_ENTRY_EDIT)
def update_daily_entry(
    campaign_id: str,
    entry_id: str,
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """
    Update state outputs, notes, or status for an existing daily notebook entry.

    Parameter campaign_id (str): Target campaign ID.
    Parameter entry_id (str): Daily entry ID.
    Parameter payload (Dict[str, Any]): Updates (state_outputs, notes, status).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    entry = campaign_service.update_daily_entry(
        campaign_id=campaign_id,
        entry_id=entry_id,
        updated_by=user_id,
        state_outputs=payload.get("state_outputs"),
        notes=payload.get("notes"),
        status=payload.get("status"),
    )
    return {"status": "success", "entry": entry.to_dict()}


@router.post("/{campaign_id}/carry-forward")
@auth_service.require_permission(PERM_ENTRY_EDIT)
def carry_forward_state(campaign_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Execute carry-forward state math across days (e.g. Day 2 harvest pellet weight -> Day 3 lysis buffer calculations).

    Parameter campaign_id (str): Target campaign ID.
    Parameter payload (Dict[str, Any]): Parameters (harvest_day, lysis_day, buffer_ratio_ml_per_g).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    harvest_day = int(payload.get("harvest_day", 2))
    lysis_day = int(payload.get("lysis_day", 3))
    buffer_ratio = float(payload.get("buffer_ratio_ml_per_g", 5.0))

    result = campaign_service.carry_forward_harvest_to_lysis(
        campaign_id=campaign_id,
        harvest_day=harvest_day,
        lysis_day=lysis_day,
        buffer_ratio_ml_per_g=buffer_ratio,
        user_id=user_id,
    )
    return {"status": "success", "carry_forward": result}


@router.get("/{campaign_id}/rollup/{day_number}")
def get_daily_rollup(campaign_id: str, day_number: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Generate automatic daily rollup summary for an experimental day.

    Parameter campaign_id (str): Target campaign ID.
    Parameter day_number (str): Ordinal day number.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    rollup = campaign_service.generate_daily_rollup(campaign_id=campaign_id, day_number=int(day_number))
    return {"status": "success", "rollup": rollup}


@router.post("/{campaign_id}/complete")
@auth_service.require_permission(PERM_CAMPAIGN_COMPLETE)
def complete_campaign(campaign_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Record final yield metrics and mark campaign completed.

    Parameter campaign_id (str): Target campaign ID.
    Parameter payload (Dict[str, Any]): Culmination metrics (yield_mg_total, culture_volume_l, theoretical_yield_mg, yield_ug_plasmid).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "pi_admin"
    campaign = campaign_service.complete_campaign(
        campaign_id=campaign_id,
        user_id=user_id,
        yield_mg_total=float(payload["yield_mg_total"]),
        culture_volume_l=float(payload["culture_volume_l"]),
        theoretical_yield_mg=float(payload["theoretical_yield_mg"]) if "theoretical_yield_mg" in payload else None,
        yield_ug_plasmid=float(payload["yield_ug_plasmid"]) if "yield_ug_plasmid" in payload else None,
    )
    return {"status": "success", "campaign": campaign.to_dict()}
