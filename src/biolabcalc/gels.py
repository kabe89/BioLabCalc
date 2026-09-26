"""Gel electrophoresis molecular weight ladders, migration modeling (Rf), and band visualization."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

LADDER_CATALOG: Dict[str, Dict[str, Any]] = {
    "1kb_dna": {
        "name": "1 kb DNA Ladder",
        "type": "dsDNA",
        "unit": "bp",
        "bands": [10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500],
        "reference_bands": [3000],  # Often higher intensity reference
        "optimal_agarose_pct": 1.0,
    },
    "100bp_dna": {
        "name": "100 bp DNA Ladder",
        "type": "dsDNA",
        "unit": "bp",
        "bands": [1517, 1200, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100],
        "reference_bands": [500, 1000],
        "optimal_agarose_pct": 2.0,
    },
    "low_range_ssdna": {
        "name": "Low Range ssDNA/RNA Oligo Ladder",
        "type": "ssDNA/RNA",
        "unit": "nt",
        "bands": [100, 80, 60, 50, 40, 30, 20, 10],
        "reference_bands": [50],
        "optimal_agarose_pct": "12-15% PAGE",
    },
    "protein_broad_range": {
        "name": "Broad Range Prestained Protein Ladder",
        "type": "Protein",
        "unit": "kDa",
        "bands": [250, 150, 100, 75, 50, 37, 25, 20, 15, 10],
        "reference_bands": [75, 25],
        "optimal_agarose_pct": "10-12% SDS-PAGE",
    },
    "ssrna_ladder": {
        "name": "ssRNA High Range Ladder",
        "type": "ssRNA",
        "unit": "nt",
        "bands": [9000, 7000, 5000, 3000, 2000, 1500, 1000, 500],
        "reference_bands": [2000],
        "optimal_agarose_pct": "1.2% Formaldehyde/MOPS Denaturing Gel",
    },
    "low_range_rna": {
        "name": "Low Range ssRNA Ladder",
        "type": "ssRNA",
        "unit": "nt",
        "bands": [1000, 800, 600, 500, 400, 300, 200, 100, 50],
        "reference_bands": [500],
        "optimal_agarose_pct": "6-8% Urea-PAGE (7M Urea)",
    },
    "microrna_ladder": {
        "name": "microRNA / Small RNA Ladder",
        "type": "ssRNA",
        "unit": "nt",
        "bands": [50, 40, 30, 20, 10],
        "reference_bands": [30],
        "optimal_agarose_pct": "12-15% Urea-PAGE (7M Urea)",
    },
}

@dataclass(frozen=True)
class GelBand:
    size: float
    unit: str
    relative_migration_rf: float
    is_reference: bool
    label: str

@dataclass(frozen=True)
class GelLaneSimulation:
    ladder_name: str
    sample_sizes: List[float]
    ladder_bands: List[GelBand]
    sample_bands: List[GelBand]
    recommended_gel_percentage: str
    ascii_visualization: str

def calculate_rf(size: float, min_size: float, max_size: float) -> float:
    """Calculate relative mobility Rf using the logarithmic relationship Rf = a - b * log10(size)."""
    log_max = math.log10(max_size)
    log_min = math.log10(min_size)
    log_val = math.log10(max(min_size * 0.8, min(max_size * 1.2, size)))
    # Rf between 0.1 (top of gel) and 0.9 (bottom of gel)
    rf = 0.1 + 0.8 * ((log_max - log_val) / (log_max - log_min))
    return round(max(0.05, min(0.95, rf)), 3)

def simulate_gel(
    sample_sizes: List[float],
    ladder_key: str = "1kb_dna",
) -> GelLaneSimulation:
    """Simulate gel electrophoresis band positions relative to a standard molecular weight ladder."""
    lad_key = ladder_key.lower().replace("-", "_").replace(" ", "_")
    ladder_info = LADDER_CATALOG.get(lad_key, LADDER_CATALOG["1kb_dna"])
    bands = sorted(ladder_info["bands"], reverse=True)
    min_size = min(bands)
    max_size = max(bands)
    unit = ladder_info["unit"]

    ladder_bands: List[GelBand] = []
    for b in bands:
        rf = calculate_rf(b, min_size, max_size)
        is_ref = b in ladder_info["reference_bands"]
        ladder_bands.append(GelBand(b, unit, rf, is_ref, f"{b} {unit}{' *' if is_ref else ''}"))

    sample_bands: List[GelBand] = []
    for s in sample_sizes:
        rf = calculate_rf(s, min_size, max_size)
        sample_bands.append(GelBand(s, unit, rf, False, f"{s} {unit}"))

    # Generate ASCII visualization
    lines = []
    lines.append(f"┌─────────── Gel Migration Simulation ({ladder_info['name']}) ───────────┐")
    lines.append("│ Well │   Ladder Lane    │   Sample Lane(s)                     │")
    lines.append("├──────┼──────────────────┼──────────────────────────────────────┤")

    # 15 migration height bins
    for step in range(16):
        rf_center = 0.08 + (step * 0.055)
        # Find ladder bands near this rf
        lad_match = [b for b in ladder_bands if abs(b.relative_migration_rf - rf_center) < 0.035]
        smp_match = [b for b in sample_bands if abs(b.relative_migration_rf - rf_center) < 0.035]

        lad_str = f"== {lad_match[0].label:<10s} ==" if lad_match else "                  "
        smp_str = f"## {', '.join(b.label for b in smp_match):<30s} ##" if smp_match else "                                      "
        lines.append(f"│  {step:02d}  │{lad_str}│{smp_str}│")

    lines.append("└──────┴──────────────────┴──────────────────────────────────────┘")
    lines.append(f"Recommended Matrix: {ladder_info['optimal_agarose_pct']}")
    ascii_art = "\n".join(lines)

    return GelLaneSimulation(
        ladder_name=ladder_info["name"],
        sample_sizes=sample_sizes,
        ladder_bands=ladder_bands,
        sample_bands=sample_bands,
        recommended_gel_percentage=str(ladder_info["optimal_agarose_pct"]),
        ascii_visualization=ascii_art,
    )
