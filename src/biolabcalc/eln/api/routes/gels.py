"""
Module: biolabcalc.eln.api.routes.gels
Component: Gel Electrophoresis Calibration, MW Estimation & Multi-Modal Entity Tagging Endpoints
Architectural Role: REST routes exposing gel ladder standard curve calibration (linear regression of
log10(MW) vs Rf), band molecular weight estimation with R^2 reporting, and relational lane tagging.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ...services.gel_service import get_gel_service
from ..auth import PERM_GEL_TAG, UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/gels")
gel_service = get_gel_service()
auth_service = get_auth_service()


@router.post("/calibrate")
def calibrate_ladder(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Calibrate molecular weight ladder standard curve via linear regression of log10(MW) vs Rf.

    Parameter payload (Dict[str, Any]): Calibration input ('ladder_data': list of [known_mw, rf], optional 'ladder_key').
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    raw_data = payload["ladder_data"]
    ladder_pts: List[Tuple[float, float]] = [(float(pt[0]), float(pt[1])) for pt in raw_data]
    ladder_key = payload.get("ladder_key", "protein_broad_range")

    res = gel_service.calibrate_ladder(ladder_pts, ladder_key=ladder_key)
    return {"status": "success", "calibration": res.to_dict()}


@router.post("/estimate-mw")
def estimate_band_molecular_weight(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Estimate molecular weight of an unknown band given Rf and calibrated standard curve.

    Parameter payload (Dict[str, Any]): Estimation input ('rf': float, 'calibration': dict or ladder points).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    rf = float(payload["rf"])
    cal_dict = payload.get("calibration")
    if cal_dict and "slope" in cal_dict and "intercept" in cal_dict:
        from ...services.gel_service import LadderCalibrationResult

        calibration = LadderCalibrationResult(
            ladder_key=cal_dict.get("ladder_key", "custom"),
            slope=float(cal_dict["slope"]),
            intercept=float(cal_dict["intercept"]),
            r_squared=float(cal_dict.get("r_squared", 1.0)),
            formula_str=cal_dict.get("formula_str", ""),
            point_count=int(cal_dict.get("point_count", 0)),
        )
    elif "ladder_data" in payload:
        raw_data = payload["ladder_data"]
        pts: List[Tuple[float, float]] = [(float(pt[0]), float(pt[1])) for pt in raw_data]
        calibration = gel_service.calibrate_ladder(pts)
    else:
        raise ValueError("Must provide either 'calibration' dict or 'ladder_data' to estimate MW.")

    res = gel_service.estimate_mw(rf=rf, calibration=calibration)
    return {"status": "success", "result": res}


@router.post("")
@auth_service.require_permission(PERM_GEL_TAG)
def register_gel(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Register a new gel electrophoresis run with optional ladder calibration standard curve.

    Parameter payload (Dict[str, Any]): Gel parameters (title, gel_type, percentage, ladder_data, ladder_key, image_uri).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    ladder_data = payload.get("ladder_data")
    pts: Optional[List[Tuple[float, float]]] = None
    if ladder_data:
        pts = [(float(pt[0]), float(pt[1])) for pt in ladder_data]

    gel = gel_service.register_gel(
        title=payload["title"],
        gel_type=payload.get("gel_type", "sds_page"),
        percentage=float(payload.get("percentage", 10.0)),
        ladder_data=pts,
        ladder_key=payload.get("ladder_key", "protein_broad_range"),
        image_uri=payload.get("image_uri"),
        created_by=user_id,
    )
    return {"status": "success", "gel": gel.to_dict()}


@router.post("/{gel_id}/tag-lane")
@auth_service.require_permission(PERM_GEL_TAG)
def tag_gel_lane(gel_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Tag a gel lane with associated database entities (Primer, Construct, FPLC Fraction, NanoDrop, Timepoint).

    Parameter gel_id (str): Target gel ID.
    Parameter payload (Dict[str, Any]): Lane parameters (lane_number, sample_name, bands_data, primer_id, construct_id, fplc_fraction_id, etc.).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    lane = gel_service.tag_lane(
        gel_id=gel_id,
        lane_number=int(payload["lane_number"]),
        sample_name=payload["sample_name"],
        bands_data=payload.get("bands_data"),
        ladder_key=payload.get("ladder_key"),
        primer_id=payload.get("primer_id"),
        construct_id=payload.get("construct_id"),
        fplc_fraction_id=payload.get("fplc_fraction_id"),
        nanodrop_sample_id=payload.get("nanodrop_sample_id"),
        timepoint_id=payload.get("timepoint_id"),
        campaign_id=payload.get("campaign_id"),
        notes=payload.get("notes", ""),
        user_id=user_id,
    )
    return {"status": "success", "lane": lane.to_dict()}


@router.get("/{gel_id}")
def get_gel_record(gel_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve single gel record by ID.

    Parameter gel_id (str): Gel ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    gel = gel_service.get_gel(gel_id)
    if not gel:
        return {"status": "error", "message": f"Gel record '{gel_id}' not found."}, 404
    return {"status": "success", "gel": gel.to_dict()}
