"""
Module: biolabcalc.eln.services.gel_service
Component: Gel Electrophoresis Standard Curve Calibration, MW Estimation & Multi-Modal Entity Tagging
Architectural Role: Core service providing molecular weight ladder standard curve calibration
via linear regression of log10(MW) vs Rf, MW estimation for unknown sample bands with R^2 reporting,
and relational tagging of gel lanes to database entities (Primers, Constructs, FPLC Fractions,
NanoDrop samples, Timepoints).
"""

from __future__ import annotations

import math
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ...gels import LADDER_CATALOG
from .audit_service import get_audit_service


@dataclass
class LadderCalibrationResult:
    """
    Standard curve linear regression parameters calibrated from a molecular weight ladder.

    Architectural Role: Models log10(MW) = slope * Rf + intercept, providing R^2 calibration goodness of fit.
    """

    ladder_key: str
    slope: float
    intercept: float
    r_squared: float
    formula_str: str
    point_count: int

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize calibration to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class GelBandMeasurement:
    """
    Measurement and molecular weight estimate for a detected gel lane band.

    Architectural Role: Stores band migration Rf, estimated molecular weight, intensity, and label.
    """

    band_index: int
    rf: float
    estimated_mw: float
    intensity_au: Optional[float] = None
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize band measurement to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class GelLane:
    """
    Gel electrophoresis lane tagged with associated biological database entities.

    Architectural Role: Entity linking physical gel lanes with Primers, Constructs, FPLC Fractions,
    NanoDrop measurements, and Campaign Timepoints.
    """

    lane_number: int
    sample_name: str
    ladder_key: Optional[str] = None
    primer_id: Optional[str] = None
    construct_id: Optional[str] = None
    fplc_fraction_id: Optional[str] = None
    nanodrop_sample_id: Optional[str] = None
    timepoint_id: Optional[str] = None
    campaign_id: Optional[str] = None
    bands: List[GelBandMeasurement] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize gel lane to dictionary.

        Return Type: Dict[str, Any]
        """
        return {
            "lane_number": self.lane_number,
            "sample_name": self.sample_name,
            "ladder_key": self.ladder_key,
            "primer_id": self.primer_id,
            "construct_id": self.construct_id,
            "fplc_fraction_id": self.fplc_fraction_id,
            "nanodrop_sample_id": self.nanodrop_sample_id,
            "timepoint_id": self.timepoint_id,
            "campaign_id": self.campaign_id,
            "bands": [b.to_dict() for b in self.bands],
            "notes": self.notes,
        }


@dataclass
class GelRecord:
    """
    Complete gel electrophoresis record containing calibration standard curve and annotated lanes.

    Architectural Role: Container entity for gel image analysis, ladder calibration, and lane tagging.
    """

    gel_id: str
    title: str
    gel_type: str  # sds_page, agarose, urea_page
    percentage: float
    calibration: Optional[LadderCalibrationResult]
    lanes: List[GelLane] = field(default_factory=list)
    image_uri: Optional[str] = None
    created_by: str = "unknown"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize gel record to dictionary.

        Return Type: Dict[str, Any]
        """
        return {
            "gel_id": self.gel_id,
            "title": self.title,
            "gel_type": self.gel_type,
            "percentage": self.percentage,
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "lanes": [l.to_dict() for l in self.lanes],
            "image_uri": self.image_uri,
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


class GelService:
    """
    Service managing gel electrophoresis analysis, standard curve calibration, and entity tagging.

    Architectural Role: Provides mathematical linear regression for log10(MW) vs Rf, unknown band
    sizing, and relational database linkage across multi-modal analytical records.
    """

    def __init__(self) -> None:
        """
        Initialize GelService in-memory repository and audit ledger.

        """
        self._lock = threading.RLock()
        self._gels: Dict[str, GelRecord] = {}
        self._audit_service = get_audit_service()

    def calibrate_ladder(
        self,
        ladder_data: List[Tuple[float, float]],
        ladder_key: str = "protein_broad_range",
    ) -> LadderCalibrationResult:
        """
        Calibrate standard curve by linear regression of log10(known_mw) vs Rf.

        Mathematical Formulation:
            y = log10(known_mw)
            x = Rf (relative migration distance: 0.05 to 0.95)
            y = slope * x + intercept
            R^2 = 1 - (SS_res / SS_tot)

        Parameter ladder_data (List[Tuple[float, float]]): List of (known_mw, rf) pairs.
        Parameter ladder_key (str): Catalog reference key (default: protein_broad_range).
        Return Type: LadderCalibrationResult
        """
        if len(ladder_data) < 2:
            raise ValueError("At least 2 ladder bands are required for standard curve calibration.")

        xs: List[float] = []
        ys: List[float] = []

        for mw, rf in ladder_data:
            if mw <= 0:
                raise ValueError(f"Ladder band molecular weight must be positive: found {mw}.")
            if not (0.0 <= rf <= 1.0):
                raise ValueError(f"Rf must be in range [0.0, 1.0]: found {rf}.")
            xs.append(rf)
            ys.append(math.log10(mw))

        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n

        ss_xx = sum((x - mean_x) ** 2 for x in xs)
        ss_yy = sum((y - mean_y) ** 2 for y in ys)
        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))

        if ss_xx == 0:
            raise ValueError("All ladder bands have identical Rf values. Cannot compute regression.")

        slope = ss_xy / ss_xx
        intercept = mean_y - slope * mean_x

        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
        r_squared = 1.0 - (ss_res / ss_yy) if ss_yy > 0 else 1.0
        r_squared = max(0.0, min(1.0, r_squared))

        formula = f"log10(MW) = {slope:.4f} * Rf + {intercept:.4f} (R² = {r_squared:.4f})"

        return LadderCalibrationResult(
            ladder_key=ladder_key,
            slope=round(slope, 6),
            intercept=round(intercept, 6),
            r_squared=round(r_squared, 5),
            formula_str=formula,
            point_count=n,
        )

    def estimate_mw(
        self,
        rf: float,
        calibration: LadderCalibrationResult,
    ) -> Dict[str, Any]:
        """
        Estimate molecular weight of a band given its Rf and calibrated ladder standard curve.

        Mathematical Principles:
            log10(MW) = slope * Rf + intercept
            MW = 10^(slope * Rf + intercept)

        Parameter rf (float): Measured relative migration distance (0.0 to 1.0).
        Parameter calibration (LadderCalibrationResult): Active standard curve.
        Return Type: Dict[str, Any]
        """
        if not (0.0 <= rf <= 1.0):
            raise ValueError(f"Rf must be in range [0.0, 1.0]: found {rf}.")

        log_mw = calibration.slope * rf + calibration.intercept
        mw_est = 10.0 ** log_mw

        return {
            "rf": rf,
            "estimated_mw": round(mw_est, 2),
            "estimated_mw_kda": round(mw_est / 1000.0, 2) if mw_est > 1000 else round(mw_est, 2),
            "r_squared": calibration.r_squared,
            "formula": calibration.formula_str,
        }

    def register_gel(
        self,
        title: str,
        gel_type: str,
        percentage: float,
        ladder_data: Optional[List[Tuple[float, float]]] = None,
        ladder_key: str = "protein_broad_range",
        image_uri: Optional[str] = None,
        created_by: str = "active_researcher",
    ) -> GelRecord:
        """
        Register a new gel electrophoresis run, automatically computing ladder calibration if provided.

        Parameter title (str): Gel run title (e.g. 'T7RNAP Ni-NTA Elution SDS-PAGE').
        Parameter gel_type (str): Matrix type ('sds_page', 'agarose', 'urea_page').
        Parameter percentage (float): Gel percentage (e.g. 10.0% or 12.0%).
        Parameter ladder_data (Optional[List[Tuple[float, float]]]): Ladder points (known_mw, rf).
        Parameter ladder_key (str): Catalog key.
        Parameter image_uri (Optional[str]): Storage URI of gel documentation image.
        Parameter created_by (str): Operator ID.
        Return Type: GelRecord
        """
        with self._lock:
            gel_id = f"GEL-{uuid.uuid4().hex[:8].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()

            calibration: Optional[LadderCalibrationResult] = None
            if ladder_data and len(ladder_data) >= 2:
                calibration = self.calibrate_ladder(ladder_data, ladder_key=ladder_key)

            gel = GelRecord(
                gel_id=gel_id,
                title=title,
                gel_type=gel_type,
                percentage=percentage,
                calibration=calibration,
                lanes=[],
                image_uri=image_uri,
                created_by=created_by,
                created_at=now_iso,
            )
            self._gels[gel_id] = gel

            self._audit_service.record_event(
                entity_type="gel",
                entity_id=gel_id,
                action="CREATE",
                performed_by=created_by,
                previous_state=None,
                new_state=gel.to_dict(),
                metadata={"gel_type": gel_type, "percentage": percentage},
            )
            return gel

    def tag_lane(
        self,
        gel_id: str,
        lane_number: int,
        sample_name: str,
        bands_data: Optional[List[Dict[str, Any]]] = None,
        ladder_key: Optional[str] = None,
        primer_id: Optional[str] = None,
        construct_id: Optional[str] = None,
        fplc_fraction_id: Optional[str] = None,
        nanodrop_sample_id: Optional[str] = None,
        timepoint_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        notes: str = "",
        user_id: str = "active_researcher",
    ) -> GelLane:
        """
        Tag a gel lane with associated database entities and calculate estimated MW for detected bands.

        Parameter gel_id (str): Target gel record ID.
        Parameter lane_number (int): Ordinal lane index on gel.
        Parameter sample_name (str): Sample label.
        Parameter bands_data (Optional[List[Dict[str, Any]]]): Measured bands with 'rf' and optional 'intensity_au'.
        Parameter ladder_key (Optional[str]): Ladder identifier if this lane is the standard ladder.
        Parameter primer_id (Optional[str]): Linked primer entity.
        Parameter construct_id (Optional[str]): Linked construct entity.
        Parameter fplc_fraction_id (Optional[str]): Linked FPLC fraction or pool.
        Parameter nanodrop_sample_id (Optional[str]): Linked NanoDrop sample.
        Parameter timepoint_id (Optional[str]): Linked kinetic timepoint.
        Parameter campaign_id (Optional[str]): Linked master campaign.
        Parameter notes (str): Lane notes.
        Parameter user_id (str): Operator ID.
        Return Type: GelLane
        """
        with self._lock:
            gel = self._gels.get(gel_id)
            if not gel:
                raise KeyError(f"Gel record '{gel_id}' not found.")

            prev_state = gel.to_dict()

            measured_bands: List[GelBandMeasurement] = []
            if bands_data:
                for idx, b in enumerate(bands_data, start=1):
                    rf = float(b["rf"])
                    if gel.calibration:
                        mw_est = self.estimate_mw(rf, gel.calibration)["estimated_mw"]
                    else:
                        mw_est = 0.0

                    measured_bands.append(
                        GelBandMeasurement(
                            band_index=idx,
                            rf=rf,
                            estimated_mw=mw_est,
                            intensity_au=b.get("intensity_au"),
                            label=b.get("label", f"Band {idx}"),
                        )
                    )

            # Check if lane already exists in gel, replace or append
            existing_lane = next((l for l in gel.lanes if l.lane_number == lane_number), None)
            lane = GelLane(
                lane_number=lane_number,
                sample_name=sample_name,
                ladder_key=ladder_key,
                primer_id=primer_id,
                construct_id=construct_id,
                fplc_fraction_id=fplc_fraction_id,
                nanodrop_sample_id=nanodrop_sample_id,
                timepoint_id=timepoint_id,
                campaign_id=campaign_id,
                bands=measured_bands,
                notes=notes,
            )

            if existing_lane:
                gel.lanes = [l if l.lane_number != lane_number else lane for l in gel.lanes]
            else:
                gel.lanes.append(lane)

            self._audit_service.record_event(
                entity_type="gel",
                entity_id=gel_id,
                action="TAG_LANE",
                performed_by=user_id,
                previous_state=prev_state,
                new_state=gel.to_dict(),
                metadata={
                    "lane_number": lane_number,
                    "sample_name": sample_name,
                    "construct_id": construct_id,
                    "fplc_fraction_id": fplc_fraction_id,
                },
            )
            return lane

    def get_gel(self, gel_id: str) -> Optional[GelRecord]:
        """
        Retrieve gel record by ID.

        Parameter gel_id (str): Gel ID.
        Return Type: Optional[GelRecord]
        """
        with self._lock:
            return self._gels.get(gel_id)

    def clear_for_testing(self) -> None:
        """
        Reset internal gel state. For unit testing harness use only.

        """
        with self._lock:
            self._gels.clear()


_global_gel_service = GelService()


def get_gel_service() -> GelService:
    """
    Get the process-level singleton instance of GelService.

    Return Type: GelService
    """
    return _global_gel_service
