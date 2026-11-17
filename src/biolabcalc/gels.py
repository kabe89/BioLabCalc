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
    sample_sizes: Tuple[float, ...]
    ladder_bands: Tuple[GelBand, ...]
    sample_bands: Tuple[GelBand, ...]
    recommended_gel_percentage: str
    ascii_visualization: str

    def __post_init__(self):
        for field_name in ("sample_sizes", "ladder_bands", "sample_bands"):
            val = getattr(self, field_name, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, field_name, tuple(val))

    def _repr_svg_(self) -> str:
        """Render high-contrast agarose/PAGE gel diagram for Jupyter notebook rich display."""
        import html
        width = 320
        height = 420
        gel_top = 65
        gel_bottom = 395
        gel_height = gel_bottom - gel_top

        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
            '<defs>',
            '  <linearGradient id="gelBg" x1="0%" y1="0%" x2="0%" y2="100%">',
            '    <stop offset="0%" stop-color="#0B132B"/>',
            '    <stop offset="100%" stop-color="#1C2541"/>',
            '  </linearGradient>',
            '  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">',
            '    <feGaussianBlur stdDeviation="1.5" result="blur" />',
            '    <feMerge>',
            '      <feMergeNode in="blur"/>',
            '      <feMergeNode in="SourceGraphic"/>',
            '    </feMerge>',
            '  </filter>',
            '</defs>',
            f'<rect x="10" y="10" width="{width - 20}" height="{height - 20}" rx="8" fill="url(#gelBg)" stroke="#3A506B" stroke-width="2"/>',
            f'<text x="{width / 2}" y="32" fill="#E0E1DD" font-family="system-ui, sans-serif" font-size="12" font-weight="600" text-anchor="middle">{html.escape(self.ladder_name)}</text>',
            f'<text x="{width / 2}" y="48" fill="#778DA9" font-family="system-ui, sans-serif" font-size="9.5" text-anchor="middle">Matrix: {html.escape(str(self.recommended_gel_percentage))}</text>',
            '<rect x="50" y="58" width="60" height="8" rx="2" fill="#0D1B2A" stroke="#415A77" stroke-width="1"/>',
            '<rect x="170" y="58" width="80" height="8" rx="2" fill="#0D1B2A" stroke="#415A77" stroke-width="1"/>',
            '<text x="80" y="54" fill="#778DA9" font-family="system-ui, sans-serif" font-size="9" font-weight="bold" text-anchor="middle">Ladder</text>',
            '<text x="210" y="54" fill="#778DA9" font-family="system-ui, sans-serif" font-size="9" font-weight="bold" text-anchor="middle">Sample</text>',
        ]

        for b in self.ladder_bands:
            y = gel_top + (b.relative_migration_rf * gel_height)
            band_h = 3.5 if b.is_reference else 2.0
            color = "#F43F5E" if b.is_reference else "#38BDF8"
            glow_attr = ' filter="url(#glow)"' if b.is_reference else ''
            svg.append(f'<rect x="52" y="{y - band_h / 2:.1f}" width="56" height="{band_h}" rx="1" fill="{color}"{glow_attr}/>')
            svg.append(f'<text x="46" y="{y + 3:.1f}" fill="{color}" font-family="monospace" font-size="8" text-anchor="end">{b.size} {html.escape(str(b.unit))}</text>')

        for b in self.sample_bands:
            y = gel_top + (b.relative_migration_rf * gel_height)
            svg.append(f'<rect x="172" y="{y - 1.5:.1f}" width="76" height="3" rx="1" fill="#34D399" filter="url(#glow)"/>')
            svg.append(f'<text x="254" y="{y + 3:.1f}" fill="#34D399" font-family="monospace" font-size="8">{b.size} {html.escape(str(b.unit))}</text>')

        svg.append('</svg>')
        return "\n".join(svg)

def calculate_rf(size: float, min_size: float, max_size: float) -> float:
    """Calculate relative mobility Rf using the logarithmic relationship Rf = a - b * log10(size)."""
    if min_size <= 0 or max_size <= min_size:
        raise ValueError("max_size must be strictly greater than min_size > 0.")
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
