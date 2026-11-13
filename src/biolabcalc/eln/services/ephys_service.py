"""
Module: biolabcalc.eln.services.ephys_service
Component: Electrophysiology Current Analysis & Patch-Clamp Service
Architectural Role: Ingests Axon ABF/ATF electrophysiology recordings and tabular current
traces, computes kinetic and steady-state current metrics (holding current, peak inward/outward
currents, steady-state currents, current density pA/pF), and produces vector SVG trace previews.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union

from ..parsers.abf_parser import ABFData, ABFParser
from ..storage.preview_generator import PreviewGenerator, PreviewResult


class EphysService:
    """Service governing electrophysiology current recordings and kinetic analysis."""

    def __init__(self) -> None:
        pass

    def parse_and_analyze_abf(
        self,
        source: Union[bytes, str],
        cell_capacitance_pf: Optional[float] = None,
        target_thumbnail_points: int = 150,
    ) -> Dict[str, Any]:
        """
        Parse raw ABF or ATF bytes/path and calculate comprehensive current metrics.

        Args:
            source (Union[bytes, str]): Raw file binary or text, or filesystem path.
            cell_capacitance_pf (Optional[float]): Membrane capacitance for current density calculation.
            target_thumbnail_points (int): Resampling point count for web SVG preview.

        Returns:
            Dict[str, Any]: Dictionary containing parsed sweep metadata, current metrics, and SVG trace.
        """
        raw_bytes = source.encode("utf-8") if isinstance(source, str) and not source.endswith((".abf", ".atf")) else source
        abf_data = ABFParser.parse(raw_bytes, target_thumbnail_points=target_thumbnail_points)
        return self.analyze_abf_data(abf_data, cell_capacitance_pf=cell_capacitance_pf)

    def analyze_abf_data(
        self,
        abf_data: ABFData,
        cell_capacitance_pf: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Extract electrophysiological current metrics from parsed ABFData.

        Args:
            abf_data (ABFData): Parsed ABF data object.
            cell_capacitance_pf (Optional[float]): Optional cell capacitance in picofarads.

        Returns:
            Dict[str, Any]: Analytical summary metrics and SVG visualization.
        """
        # Find primary current channel (typically units containing 'pA' or 'nA' or name containing 'I' or 'Current')
        current_ch_idx: Optional[int] = None
        current_ch_name: Optional[str] = None
        current_unit = "pA"

        for idx, (name, unit) in enumerate(zip(abf_data.channel_names, abf_data.channel_units)):
            unit_lower = unit.lower()
            name_lower = name.lower()
            if "pa" in unit_lower or "na" in unit_lower or "current" in name_lower:
                current_ch_idx = idx
                current_ch_name = name
                current_unit = unit
                break

        if current_ch_name is None and abf_data.channel_names:
            current_ch_name = abf_data.channel_names[0]
            current_unit = abf_data.channel_units[0] if abf_data.channel_units else "pA"

        sweeps = abf_data.sweeps_data.get(current_ch_name, [])

        sweep_metrics: List[Dict[str, Any]] = []
        all_peak_inward: List[float] = []
        all_peak_outward: List[float] = []
        all_holding: List[float] = []
        all_steady: List[float] = []

        dt_s = abf_data.sample_interval_us * 1e-6

        for sweep_idx, sweep in enumerate(sweeps):
            if not sweep:
                continue
            # Baseline / holding current: average of first 10% of points
            baseline_len = max(1, int(len(sweep) * 0.1))
            holding_curr = sum(sweep[:baseline_len]) / baseline_len

            # Steady-state current: average of last 10% of points
            ss_len = max(1, int(len(sweep) * 0.1))
            ss_curr = sum(sweep[-ss_len:]) / ss_len

            # Peak inward current (maximum negative excursion relative to holding)
            min_val = min(sweep)
            inward_peak = min(0.0, min_val - holding_curr)

            # Peak outward current (maximum positive excursion relative to holding)
            max_val = max(sweep)
            outward_peak = max(0.0, max_val - holding_curr)

            all_holding.append(holding_curr)
            all_steady.append(ss_curr)
            all_peak_inward.append(inward_peak)
            all_peak_outward.append(outward_peak)

            sweep_metrics.append({
                "sweep_number": sweep_idx + 1,
                "holding_current": round(holding_curr, 2),
                "steady_state_current": round(ss_curr, 2),
                "peak_inward_current": round(inward_peak, 2),
                "peak_outward_current": round(outward_peak, 2),
                "unit": current_unit,
            })

        avg_holding = round(sum(all_holding) / len(all_holding), 2) if all_holding else 0.0
        max_inward = round(min(all_peak_inward), 2) if all_peak_inward else 0.0
        max_outward = round(max(all_peak_outward), 2) if all_peak_outward else 0.0
        avg_steady = round(sum(all_steady) / len(all_steady), 2) if all_steady else 0.0

        current_density: Optional[float] = None
        if cell_capacitance_pf and cell_capacitance_pf > 0:
            dominant_peak = max_inward if abs(max_inward) > abs(max_outward) else max_outward
            current_density = round(dominant_peak / cell_capacitance_pf, 2)

        # Generate SVG trace representation
        svg_preview: Optional[str] = None
        if abf_data.thumbnails and current_ch_name in abf_data.thumbnails:
            thumb_sweeps = abf_data.thumbnails[current_ch_name]
            if thumb_sweeps:
                x_pts = [pt[0] for pt in thumb_sweeps[0]]
                y_series = {f"Sweep {i+1}": [pt[1] for pt in s] for i, s in enumerate(thumb_sweeps[:5])}
                try:
                    res = PreviewGenerator.generate_trace_preview_svg(
                        x_data=x_pts,
                        y_series=y_series,
                        title=f"Electrophysiology Currents ({abf_data.protocol_name})",
                        x_label="Time (s)",
                        y_label=f"Current ({current_unit})",
                    )
                    svg_preview = res.preview_bytes.decode("utf-8")
                except Exception:
                    svg_preview = None

        return {
            "status": "success",
            "protocol_name": abf_data.protocol_name,
            "operation_mode": abf_data.operation_mode,
            "sweep_count": abf_data.sweep_count,
            "holding_potential_mv": abf_data.holding_potential_mv,
            "primary_channel": current_ch_name,
            "current_unit": current_unit,
            "metrics": {
                "holding_current": avg_holding,
                "peak_inward_current": max_inward,
                "peak_outward_current": max_outward,
                "steady_state_current": avg_steady,
                "cell_capacitance_pf": cell_capacitance_pf,
                "current_density": current_density,
                "current_density_unit": f"{current_unit}/pF" if current_density else None,
            },
            "sweeps": sweep_metrics,
            "svg_preview": svg_preview,
        }

    def analyze_raw_trace(
        self,
        time_points: List[float],
        current_values: List[float],
        unit: str = "pA",
        holding_potential_mv: float = -70.0,
        cell_capacitance_pf: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Analyze arbitrary numerical current trace.
        """
        if not current_values or not time_points:
            raise ValueError("Time points and current values must not be empty.")

        baseline_n = max(1, int(len(current_values) * 0.1))
        holding = sum(current_values[:baseline_n]) / baseline_n
        ss_n = max(1, int(len(current_values) * 0.1))
        steady = sum(current_values[-ss_n:]) / ss_n

        min_val = min(current_values)
        max_val = max(current_values)
        peak_inward = min(0.0, min_val - holding)
        peak_outward = max(0.0, max_val - holding)

        current_density = None
        if cell_capacitance_pf and cell_capacitance_pf > 0:
            dominant = peak_inward if abs(peak_inward) > abs(peak_outward) else peak_outward
            current_density = round(dominant / cell_capacitance_pf, 2)

        return {
            "status": "success",
            "holding_potential_mv": holding_potential_mv,
            "unit": unit,
            "points_count": len(current_values),
            "metrics": {
                "holding_current": round(holding, 2),
                "peak_inward_current": round(peak_inward, 2),
                "peak_outward_current": round(peak_outward, 2),
                "steady_state_current": round(steady, 2),
                "cell_capacitance_pf": cell_capacitance_pf,
                "current_density": current_density,
            },
        }


_EPHYS_SERVICE: Optional[EphysService] = None


def get_ephys_service() -> EphysService:
    """Return singleton instance of EphysService."""
    global _EPHYS_SERVICE
    if _EPHYS_SERVICE is None:
        _EPHYS_SERVICE = EphysService()
    return _EPHYS_SERVICE
