"""
Module: biolabcalc.eln.api.routes.inventory
Component: Freezer Spatial Hierarchy, 2D Grid Occupancy & Lineage REST Endpoints
Agent: @agent: eln-api-agent
Architectural Role: REST routes exposing cold-chain spatial hierarchy (Room -> Unit -> Rack -> Box),
2D box grid slot occupancy matrices, audited tube moves, and sample lineage graph resolution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.inventory_service import get_inventory_service
from ..auth import PERM_INVENTORY_MOVE, PERM_INVENTORY_PLACE, UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/inventory")
inventory_service = get_inventory_service()
auth_service = get_auth_service()


@router.get("/hierarchy")
def get_spatial_hierarchy(current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve full multi-tier freezer spatial hierarchy (Room -> Storage Unit -> Rack -> Box).

    Agent: @agent: eln-api-agent
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    hierarchy = inventory_service.get_full_hierarchy()
    return {"status": "success", "hierarchy": hierarchy}


@router.get("/boxes/{box_id}/grid")
def get_box_grid(box_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve 2D grid matrix showing slot occupancy and tube summaries for a storage box.

    Agent: @agent: eln-api-agent
    Parameter box_id (str): Storage box ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    grid = inventory_service.get_box_grid(box_id)
    return {"status": "success", "box_grid": grid}


@router.post("/tubes")
@auth_service.require_permission(PERM_INVENTORY_PLACE)
def place_tube(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Place a new tube aliquot in an available box slot with validation.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Tube definition (box_id, slot, sample_name, volume_ul, concentration_mg_ml, barcode, construct_id, pool_id, etc.).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    tube = inventory_service.place_tube(
        box_id=payload["box_id"],
        slot=payload["slot"],
        sample_name=payload["sample_name"],
        volume_ul=float(payload["volume_ul"]),
        concentration_mg_ml=float(payload["concentration_mg_ml"]) if "concentration_mg_ml" in payload and payload["concentration_mg_ml"] is not None else None,
        barcode=payload.get("barcode"),
        construct_id=payload.get("construct_id"),
        pool_id=payload.get("pool_id"),
        daily_entry_id=payload.get("daily_entry_id"),
        campaign_id=payload.get("campaign_id"),
        nanodrop_id=payload.get("nanodrop_id"),
        notes=payload.get("notes", ""),
        user_id=user_id,
    )
    return {"status": "success", "tube": tube.to_dict()}


@router.post("/tubes/{tube_id}/move")
@auth_service.require_permission(PERM_INVENTORY_MOVE)
def move_tube(tube_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Relocate a tube to a new box coordinate with an immutable audit log entry.

    Agent: @agent: eln-api-agent
    Parameter tube_id (str): Tube identifier.
    Parameter payload (Dict[str, Any]): Relocation parameters (target_box_id, target_slot, reason).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    res = inventory_service.move_tube(
        tube_id=tube_id,
        target_box_id=payload["target_box_id"],
        target_slot=payload["target_slot"],
        user_id=user_id,
        reason=payload.get("reason", "Routine inventory relocation"),
    )
    return {"status": "success", "move_result": res}


@router.get("/tubes/{tube_id}/lineage")
def resolve_tube_lineage(tube_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Resolve complete upstream sample lineage tree for a given tube.

    Agent: @agent: eln-api-agent
    Parameter tube_id (str): Tube identifier.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    lineage = inventory_service.resolve_lineage(tube_id)
    return {"status": "success", "lineage": lineage}
