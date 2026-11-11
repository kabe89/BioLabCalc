"""
Module: biolabcalc.eln.api.routes.fplc
Component: FPLC Peak Integration & Fraction Pooling REST Endpoints
Agent: @agent: eln-api-agent
Architectural Role: REST routes exposing trapezoidal peak integration on UV280 chromatograms,
automated fraction pooling stoichiometry, and multi-modal entity linkage.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ...services.fplc_service import get_fplc_service
from ..auth import PERM_FPLC_POOL, UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/fplc")
fplc_service = get_fplc_service()
auth_service = get_auth_service()


@router.post("/integrate")
def integrate_chromatogram_peak(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Perform trapezoidal numerical integration on a UV280 chromatogram curve.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Integration parameters (chromatogram_data, start_volume_ml, end_volume_ml, baseline_type).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    raw_points = payload["chromatogram_data"]
    # Ensure tuples of float
    pts: List[Tuple[float, float]] = [(float(pt[0]), float(pt[1])) for pt in raw_points]
    start_v = float(payload["start_volume_ml"])
    end_v = float(payload["end_volume_ml"])
    base_type = payload.get("baseline_type", "linear")

    res = fplc_service.integrate_peak(
        chromatogram_data=pts,
        start_volume_ml=start_v,
        end_volume_ml=end_v,
        baseline_type=base_type,
    )
    return {"status": "success", "peak": res.to_dict()}


@router.post("/pool")
@auth_service.require_permission(PERM_FPLC_POOL)
def pool_fractions(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Pool selected FPLC fractions and calculate total volume, weighted mean UV280, and estimated concentration.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Pooling parameters (campaign_id, run_id, fractions, construct_id, pathlength_cm).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    res = fplc_service.pool_fractions(
        campaign_id=payload["campaign_id"],
        run_id=payload["run_id"],
        fractions=payload["fractions"],
        construct_id=payload["construct_id"],
        user_id=user_id,
        pathlength_cm=float(payload.get("pathlength_cm", 1.0)),
        extinction_coeff_m_cm=int(payload["extinction_coeff_m_cm"]) if "extinction_coeff_m_cm" in payload else None,
        molecular_weight_da=float(payload["molecular_weight_da"]) if "molecular_weight_da" in payload else None,
    )
    return {"status": "success", "pool": res.to_dict()}


@router.post("/link")
@auth_service.require_permission(PERM_FPLC_POOL)
def link_pool_entities(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Link fraction pool to downstream NanoDrop records, gel lanes, and freezer tube barcodes.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Link parameters (pool_id, nanodrop_id, gel_lane_id, tube_ids).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    res = fplc_service.link_pool_to_entities(
        pool_id=payload["pool_id"],
        user_id=user_id,
        nanodrop_id=payload.get("nanodrop_id"),
        gel_lane_id=payload.get("gel_lane_id"),
        tube_ids=payload.get("tube_ids"),
    )
    return {"status": "success", "pool": res.to_dict()}


@router.get("/pools/{pool_id}")
def get_fraction_pool(pool_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve fraction pool by ID.

    Agent: @agent: eln-api-agent
    Parameter pool_id (str): Pool ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    pool = fplc_service.get_pool(pool_id)
    if not pool:
        return {"status": "error", "message": f"Fraction pool '{pool_id}' not found."}, 404
    return {"status": "success", "pool": pool.to_dict()}
