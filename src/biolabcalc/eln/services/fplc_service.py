"""
Module: biolabcalc.eln.services.fplc_service
Component: FPLC Chromatogram UV280 Peak Integration & Fraction Pooling Engine
Architectural Role: Core service performing trapezoidal numerical integration on FPLC UV280
chromatograms (Ve, peak height, peak area), baseline subtraction, and automated fraction pooling
stoichiometry (pooled volume, weighted mean UV280, estimated protein concentration, and cross-entity linkage).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .audit_service import get_audit_service
from .sequence_service import get_sequence_service


@dataclass
class PeakIntegrationResult:
    """
    Quantitative metrics derived from numerical integration of a chromatogram UV280 peak.

    Architectural Role: Encapsulates retention volume Ve, net peak height, trapezoidal area,
    and fraction of total chromatogram absorbance.
    """

    peak_id: str
    start_volume_ml: float
    end_volume_ml: float
    retention_volume_ve_ml: float
    peak_height_mau: float
    peak_area_mau_ml: float
    baseline_type: str
    total_area_mau_ml: Optional[float] = None
    area_percentage: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize peak integration result to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class FPLCFraction:
    """
    Representation of an individual collected FPLC fraction tube.

    Architectural Role: Maps fraction collector rack coordinates (e.g. B4) to volume and UV280.
    """

    fraction_id: str
    start_volume_ml: float
    end_volume_ml: float
    volume_ml: float
    uv280_mau: float

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize fraction to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class FractionPoolResult:
    """
    Stoichiometric and analytical summary of pooled FPLC fractions.

    Architectural Role: Links pooled elution volume, calculated mean UV280, estimated protein
    concentration (via Beer-Lambert Law), and downstream analytical entities (NanoDrop, Gel, Tubes).
    """

    pool_id: str
    campaign_id: str
    run_id: str
    fraction_ids: List[str]
    fraction_count: int
    total_volume_ml: float
    mean_uv280_mau: float
    construct_id: str
    extinction_coeff_m_cm: int
    molecular_weight_da: float
    pathlength_cm: float
    estimated_conc_mg_ml: float
    estimated_total_yield_mg: float
    created_by: str
    created_at: str
    linked_nanodrop_id: Optional[str] = None
    linked_gel_lane_id: Optional[str] = None
    linked_tube_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize fraction pool result to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


class FPLCService:
    """
    Service providing FPLC chromatogram numerical peak integration and fraction pooling calculations.

    Architectural Role: Executes Beer-Lambert spectrophotometric quantification, trapezoidal peak
    integration, and coordinates cross-pipeline entity linkage between chromatography, spectroscopy,
    gel electrophoresis, and freezer inventory.
    """

    def __init__(self) -> None:
        """
        Initialize FPLCService in-memory repository and audit link.

        """
        self._lock = threading.RLock()
        self._pools: Dict[str, FractionPoolResult] = {}
        self._audit_service = get_audit_service()
        self._sequence_service = get_sequence_service()

    def integrate_peak(
        self,
        chromatogram_data: List[Tuple[float, float]],
        start_volume_ml: float,
        end_volume_ml: float,
        baseline_type: str = "linear",
    ) -> PeakIntegrationResult:
        """
        Perform trapezoidal numerical integration on UV280 chromatogram within specified retention volume bounds.

        Mathematical Principles:
            - Extracts points where start_volume_ml <= V <= end_volume_ml.
            - Baseline subtraction:
                - 'linear': interpolates baseline linearly between start point and end point.
                - 'constant': uses minimum of start and end points as flat baseline.
            - Net UV: UV_net(V) = max(0.0, UV(V) - baseline(V))
            - Trapezoidal rule: Area = Sum_{i} [ (UV_{i} + UV_{i+1}) / 2 * (V_{i+1} - V_{i}) ] in mAU*mL.
            - Retention volume Ve: V at max(UV_net(V)).

        Parameter chromatogram_data (List[Tuple[float, float]]): List of (volume_ml, uv280_mau) coordinates.
        Parameter start_volume_ml (float): Elution volume beginning peak integration.
        Parameter end_volume_ml (float): Elution volume terminating peak integration.
        Parameter baseline_type (str): 'linear' or 'constant' (default: 'linear').
        Return Type: PeakIntegrationResult
        """
        if not chromatogram_data:
            raise ValueError("Chromatogram data cannot be empty.")
        if start_volume_ml >= end_volume_ml:
            raise ValueError("Start volume must be strictly less than end volume.")

        # Sort points by volume
        sorted_data = sorted(chromatogram_data, key=lambda pt: pt[0])

        # Filter slice
        peak_points = [pt for pt in sorted_data if start_volume_ml <= pt[0] <= end_volume_ml]
        if len(peak_points) < 2:
            raise ValueError(f"Insufficient data points ({len(peak_points)}) between {start_volume_ml} and {end_volume_ml} mL.")

        v_start, uv_start = peak_points[0]
        v_end, uv_end = peak_points[-1]

        # Calculate baseline function
        def get_baseline(v: float) -> float:
            if baseline_type == "linear":
                if abs(v_end - v_start) < 1e-9:
                    return uv_start
                slope = (uv_end - uv_start) / (v_end - v_start)
                return uv_start + slope * (v - v_start)
            else:
                return min(uv_start, uv_end)

        # Baseline subtraction and peak search
        max_net_uv = -1.0
        ve = peak_points[0][0]
        net_points: List[Tuple[float, float]] = []

        for v, uv in peak_points:
            base = get_baseline(v)
            net_uv = max(0.0, uv - base)
            net_points.append((v, net_uv))
            if net_uv > max_net_uv:
                max_net_uv = net_uv
                ve = v

        # Trapezoidal numerical integration
        peak_area = 0.0
        for i in range(len(net_points) - 1):
            v0, u0 = net_points[i]
            v1, u1 = net_points[i + 1]
            delta_v = v1 - v0
            trap_area = ((u0 + u1) / 2.0) * delta_v
            peak_area += trap_area

        # Calculate total chromatogram area if full run provided
        total_area = 0.0
        for i in range(len(sorted_data) - 1):
            v0, u0 = sorted_data[i]
            v1, u1 = sorted_data[i + 1]
            total_area += (max(0.0, u0) + max(0.0, u1)) / 2.0 * (v1 - v0)

        area_pct = round((peak_area / total_area) * 100.0, 2) if total_area > 0 else 100.0

        peak_id = f"PEAK-{uuid.uuid4().hex[:6].upper()}"
        return PeakIntegrationResult(
            peak_id=peak_id,
            start_volume_ml=round(start_volume_ml, 3),
            end_volume_ml=round(end_volume_ml, 3),
            retention_volume_ve_ml=round(ve, 3),
            peak_height_mau=round(max_net_uv, 2),
            peak_area_mau_ml=round(peak_area, 3),
            baseline_type=baseline_type,
            total_area_mau_ml=round(total_area, 3) if total_area > 0 else None,
            area_percentage=area_pct,
        )

    def pool_fractions(
        self,
        campaign_id: str,
        run_id: str,
        fractions: List[Dict[str, Any]],
        construct_id: str,
        user_id: str = "active_researcher",
        pathlength_cm: float = 1.0,
        extinction_coeff_m_cm: Optional[int] = None,
        molecular_weight_da: Optional[float] = None,
    ) -> FractionPoolResult:
        """
        Calculate pooled fraction volume, mean UV280, and estimated protein concentration via Beer-Lambert.

        Mathematical Principles:
            - Total Pooled Volume: V_total = Sum(V_i) (e.g. 5 fractions of 2.0 mL = 10.0 mL)
            - Weighted Mean UV280: Mean_UV = Sum(UV_i * V_i) / V_total (in mAU)
            - Beer-Lambert Law:
                A = Mean_UV / 1000.0  (convert mAU to AU)
                Molar Conc (M) = A / (e280 * pathlength)
                Conc (mg/mL) = Molar Conc * MW
                Estimated Total Yield (mg) = Conc (mg/mL) * V_total (mL)

        Parameter campaign_id (str): Target campaign ID.
        Parameter run_id (str): Chromatography run run ID.
        Parameter fractions (List[Dict[str, Any]]): List of fraction dicts with 'fraction_id', 'volume_ml', 'uv280_mau'.
        Parameter construct_id (str): Target construct ID for e280 and MW lookup.
        Parameter user_id (str): Operator ID.
        Parameter pathlength_cm (float): Optical pathlength (default: 1.0 cm).
        Parameter extinction_coeff_m_cm (Optional[int]): Manual override for e280.
        Parameter molecular_weight_da (Optional[float]): Manual override for MW.
        Return Type: FractionPoolResult
        """
        if not fractions:
            raise ValueError("Cannot pool an empty list of fractions.")

        total_vol = 0.0
        weighted_uv_sum = 0.0
        fraction_ids: List[str] = []

        for f in fractions:
            fid = str(f["fraction_id"])
            vol = float(f["volume_ml"])
            uv = float(f["uv280_mau"])
            if vol <= 0:
                raise ValueError(f"Fraction volume must be positive: fraction '{fid}' has volume {vol}.")
            total_vol += vol
            weighted_uv_sum += uv * vol
            fraction_ids.append(fid)

        mean_uv = weighted_uv_sum / total_vol

        # Lookup e280 and MW from construct registry if not explicitly provided
        e280 = extinction_coeff_m_cm
        mw = molecular_weight_da

        if e280 is None or mw is None:
            construct = self._sequence_service.get_sequence(construct_id)
            if construct:
                e280 = e280 or construct.extinction_coeff_m_cm
                mw = mw or construct.molecular_weight_da

        # Fallbacks if unregistered
        e280 = e280 if (e280 and e280 > 0) else 138500  # Default T7RNAP e280
        mw = mw if (mw and mw > 0) else 98856.0  # Default T7RNAP MW

        # Beer-Lambert: A = e * c * l  =>  c (M) = A / (e * l)
        absorbance_au = mean_uv / 1000.0
        molar_conc_m = absorbance_au / (e280 * pathlength_cm)
        conc_mg_ml = molar_conc_m * mw
        conc_mg_ml = max(0.0, conc_mg_ml)
        total_yield_mg = conc_mg_ml * total_vol

        first_frac = fraction_ids[0]
        last_frac = fraction_ids[-1]
        pool_id = f"POOL-{run_id}-{first_frac}-{last_frac}"
        now_iso = datetime.now(timezone.utc).isoformat()

        pool_result = FractionPoolResult(
            pool_id=pool_id,
            campaign_id=campaign_id,
            run_id=run_id,
            fraction_ids=fraction_ids,
            fraction_count=len(fraction_ids),
            total_volume_ml=round(total_vol, 2),
            mean_uv280_mau=round(mean_uv, 2),
            construct_id=construct_id,
            extinction_coeff_m_cm=e280,
            molecular_weight_da=round(mw, 2),
            pathlength_cm=pathlength_cm,
            estimated_conc_mg_ml=round(conc_mg_ml, 3),
            estimated_total_yield_mg=round(total_yield_mg, 3),
            created_by=user_id,
            created_at=now_iso,
        )

        with self._lock:
            self._pools[pool_id] = pool_result

            self._audit_service.record_event(
                entity_type="fplc_pool",
                entity_id=pool_id,
                action="POOL_FRACTIONS",
                performed_by=user_id,
                previous_state=None,
                new_state=pool_result.to_dict(),
                metadata={
                    "campaign_id": campaign_id,
                    "fraction_count": len(fraction_ids),
                    "total_volume_ml": total_vol,
                    "estimated_yield_mg": total_yield_mg,
                },
            )

        return pool_result

    def link_pool_to_entities(
        self,
        pool_id: str,
        user_id: str = "active_researcher",
        nanodrop_id: Optional[str] = None,
        gel_lane_id: Optional[str] = None,
        tube_ids: Optional[List[str]] = None,
    ) -> FractionPoolResult:
        """
        Link a pooled FPLC fraction to downstream NanoDrop measurements, gel lanes, and freezer tubes.

        Parameter pool_id (str): Target fraction pool ID.
        Parameter user_id (str): Operator ID.
        Parameter nanodrop_id (Optional[str]): NanoDrop record ID.
        Parameter gel_lane_id (Optional[str]): Gel lane tag identifier.
        Parameter tube_ids (Optional[List[str]]): List of storage tube identifiers.
        Return Type: FractionPoolResult
        """
        with self._lock:
            pool = self._pools.get(pool_id)
            if not pool:
                raise KeyError(f"Fraction pool '{pool_id}' not found.")

            prev_state = pool.to_dict()
            if nanodrop_id is not None:
                pool.linked_nanodrop_id = nanodrop_id
            if gel_lane_id is not None:
                pool.linked_gel_lane_id = gel_lane_id
            if tube_ids:
                for tid in tube_ids:
                    if tid not in pool.linked_tube_ids:
                        pool.linked_tube_ids.append(tid)

            self._audit_service.record_event(
                entity_type="fplc_pool",
                entity_id=pool_id,
                action="LINK_ENTITIES",
                performed_by=user_id,
                previous_state=prev_state,
                new_state=pool.to_dict(),
                metadata={"nanodrop_id": nanodrop_id, "gel_lane_id": gel_lane_id},
            )
            return pool

    def get_pool(self, pool_id: str) -> Optional[FractionPoolResult]:
        """
        Retrieve fraction pool result by ID.

        Parameter pool_id (str): Pool ID.
        Return Type: Optional[FractionPoolResult]
        """
        with self._lock:
            return self._pools.get(pool_id)

    def clear_for_testing(self) -> None:
        """
        Reset internal FPLC pool state. For unit testing harness use only.

        """
        with self._lock:
            self._pools.clear()


_global_fplc_service = FPLCService()


def get_fplc_service() -> FPLCService:
    """
    Get the process-level singleton instance of FPLCService.

    Return Type: FPLCService
    """
    return _global_fplc_service
