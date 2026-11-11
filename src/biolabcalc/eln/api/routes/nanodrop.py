"""
Module: biolabcalc.eln.api.routes.nanodrop
Component: NanoDrop Spectrophotometry & Purity Ratio REST Endpoints
Architectural Role: REST routes exposing NanoDrop UV-Vis microvolume absorbance recording (A260, A280, A230),
260/280 and 260/230 purity ratio determination, and sample concentration estimation.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...services.audit_service import get_audit_service
from ..auth import UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/nanodrop")
audit_service = get_audit_service()
auth_service = get_auth_service()


@dataclass
class NanoDropRecord:
    """
    Spectrophotometric absorbance measurement entry.

    Architectural Role: Quantifies A260, A280, A230, purity ratios, and sample concentration.
    """

    record_id: str
    sample_name: str
    sample_type: str  # protein, dsdna, rna, ssdna
    a260: float
    a280: float
    a230: Optional[float]
    ratio_260_280: float
    ratio_260_230: Optional[float]
    concentration_mg_ml: float
    concentration_ug_ml: float
    volume_ul: Optional[float]
    total_yield_ug: Optional[float]
    purity_flag: str  # pure, contaminated, warning
    construct_id: Optional[str]
    campaign_id: Optional[str]
    notes: str
    recorded_by: str
    recorded_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize NanoDrop record to dictionary."""
        return asdict(self)


class NanoDropRegistry:
    """In-memory repository for NanoDrop spectrophotometer measurements."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, NanoDropRecord] = {}

    def record_measurement(
        self,
        sample_name: str,
        a260: float,
        a280: float,
        a230: Optional[float] = None,
        sample_type: str = "protein",
        extinction_coeff: Optional[float] = None,
        molecular_weight: Optional[float] = None,
        volume_ul: Optional[float] = None,
        construct_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        notes: str = "",
        user_id: str = "active_researcher",
    ) -> NanoDropRecord:
        """Process and persist a spectrophotometer measurement."""
        with self._lock:
            record_id = f"ND-{uuid.uuid4().hex[:8].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()

            ratio_260_280 = round(a260 / a280, 2) if a280 > 0 else 0.0
            ratio_260_230 = round(a260 / a230, 2) if (a230 is not None and a230 > 0) else None

            # Concentration calculation based on sample type
            if sample_type == "protein":
                # If e280 and MW provided: A280 = e * c * l  =>  c (mg/mL) = (A280 * MW) / e280
                if extinction_coeff and molecular_weight and extinction_coeff > 0:
                    conc_mg_ml = (a280 * molecular_weight) / extinction_coeff
                else:
                    # Standard 1 A280 = 1 mg/mL approximation for mixed proteins
                    conc_mg_ml = a280
                conc_ug_ml = conc_mg_ml * 1000.0

                # Purity evaluation: pure protein 260/280 typically ~ 0.55 - 0.70
                if ratio_260_280 < 0.85:
                    purity_flag = "pure"
                elif ratio_260_280 < 1.1:
                    purity_flag = "warning"
                else:
                    purity_flag = "nucleic_acid_contamination"

            elif sample_type == "dsdna":
                # 1 OD260 = 50 ug/mL
                conc_ug_ml = a260 * 50.0
                conc_mg_ml = conc_ug_ml / 1000.0
                purity_flag = "pure" if (1.75 <= ratio_260_280 <= 1.95) else "warning"

            elif sample_type == "rna":
                # 1 OD260 = 40 ug/mL
                conc_ug_ml = a260 * 40.0
                conc_mg_ml = conc_ug_ml / 1000.0
                purity_flag = "pure" if (1.90 <= ratio_260_280 <= 2.15) else "warning"

            else:
                # ssDNA: 1 OD260 = 33 ug/mL
                conc_ug_ml = a260 * 33.0
                conc_mg_ml = conc_ug_ml / 1000.0
                purity_flag = "pure"

            total_yield_ug = round(conc_ug_ml * (volume_ul / 1000.0), 2) if volume_ul else None

            record = NanoDropRecord(
                record_id=record_id,
                sample_name=sample_name,
                sample_type=sample_type,
                a260=round(a260, 3),
                a280=round(a280, 3),
                a230=round(a230, 3) if a230 is not None else None,
                ratio_260_280=ratio_260_280,
                ratio_260_230=ratio_260_230,
                concentration_mg_ml=round(conc_mg_ml, 3),
                concentration_ug_ml=round(conc_ug_ml, 2),
                volume_ul=volume_ul,
                total_yield_ug=total_yield_ug,
                purity_flag=purity_flag,
                construct_id=construct_id,
                campaign_id=campaign_id,
                notes=notes,
                recorded_by=user_id,
                recorded_at=now_iso,
            )
            self._records[record_id] = record

            audit_service.record_event(
                entity_type="nanodrop",
                entity_id=record_id,
                action="RECORD_MEASUREMENT",
                performed_by=user_id,
                previous_state=None,
                new_state=record.to_dict(),
                metadata={"sample_name": sample_name, "conc_mg_ml": conc_mg_ml, "ratio_260_280": ratio_260_280},
            )
            return record

    def get_record(self, record_id: str) -> Optional[NanoDropRecord]:
        """Lookup record by ID."""
        with self._lock:
            return self._records.get(record_id)

    def list_records(self) -> List[NanoDropRecord]:
        """List all measurements."""
        with self._lock:
            return list(self._records.values())


_nanodrop_registry = NanoDropRegistry()


@router.post("/record")
def record_absorbance(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Record NanoDrop microvolume absorbance readings and calculate concentration and purity ratios.

    Parameter payload (Dict[str, Any]): Readings (sample_name, a260, a280, optional a230, sample_type, volume_ul, etc.).
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    rec = _nanodrop_registry.record_measurement(
        sample_name=payload["sample_name"],
        a260=float(payload["a260"]),
        a280=float(payload["a280"]),
        a230=float(payload["a230"]) if "a230" in payload and payload["a230"] is not None else None,
        sample_type=payload.get("sample_type", "protein"),
        extinction_coeff=float(payload["extinction_coeff"]) if "extinction_coeff" in payload else None,
        molecular_weight=float(payload["molecular_weight"]) if "molecular_weight" in payload else None,
        volume_ul=float(payload["volume_ul"]) if "volume_ul" in payload else None,
        construct_id=payload.get("construct_id"),
        campaign_id=payload.get("campaign_id"),
        notes=payload.get("notes", ""),
        user_id=user_id,
    )
    return {"status": "success", "measurement": rec.to_dict()}


@router.get("/{record_id}")
def get_nanodrop_record(record_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve single NanoDrop record by ID.

    Parameter record_id (str): Measurement ID.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    rec = _nanodrop_registry.get_record(record_id)
    if not rec:
        return {"status": "error", "message": f"NanoDrop record '{record_id}' not found."}, 404
    return {"status": "success", "measurement": rec.to_dict()}


@router.get("")
def list_nanodrop_records(current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    List all recorded NanoDrop measurements.

    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    records = _nanodrop_registry.list_records()
    return {"status": "success", "count": len(records), "measurements": [r.to_dict() for r in records]}
