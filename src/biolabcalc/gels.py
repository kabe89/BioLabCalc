"""Gel electrophoresis molecular weight ladders, migration modeling (Rf), and band visualization."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Literal

@dataclass(frozen=True)
class GelTypographyConfig:
    """Universal typography and lane numbering formatting configuration across BioLabCalc."""
    font_family: str = "Arial, Helvetica, sans-serif"
    font_family_category: Literal["sans", "serif", "mono", "system"] = "sans"
    font_scale: float = 1.0
    show_lane_numbers: bool = True
    lane_number_style: Literal["circle", "square", "plain", "none"] = "circle"
    lane_number_format: Literal["numeric", "prefixed_L", "prefixed_lane", "alpha", "roman"] = "numeric"
    lane_number_start: int = 1
    bold_lane_numbers: bool = True
    bold_lane_names: bool = True
    bold_ladder_labels: bool = False
    bold_band_callouts: bool = True
    header_rotation: int = 45
    lane_font_size: float = 10.0
    lane_number_size: float = 9.0
    ladder_font_size: float = 8.5
    tag_font_size: float = 8.5
    title_font_size: float = 14.0
    subtitle_font_size: float = 10.0


def format_lane_number(index: int, style: Optional[GelTypographyConfig] = None) -> str:
    """Format a lane index according to GelTypographyConfig numbering scheme."""
    fmt = style.lane_number_format if style else "numeric"
    idx = index
    if fmt == "prefixed_L":
        return f"L{idx}"
    elif fmt == "prefixed_lane":
        return f"Lane {idx}"
    elif fmt == "alpha":
        res = ""
        n = idx
        while n > 0:
            n, rem = divmod(n - 1, 26)
            res = chr(65 + rem) + res
        return res or str(idx)
    elif fmt == "roman":
        val_map = [
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
        ]
        res = ""
        n = idx
        for val, rom in val_map:
            while n >= val:
                res += rom
                n -= val
        return res or str(idx)
    return str(idx)


@dataclass
class LaneMetadata:
    """Laboratory sample and reaction metadata for an electrophoresis gel lane."""
    lane_index: int
    sample_name: str
    sample_type: Literal["sample", "ladder", "negative_ctrl", "positive_ctrl", "blank"] = "sample"
    template_mass_ng: Optional[float] = None
    loading_volume_ul: Optional[float] = None
    reaction_conditions: str = ""
    expected_sizes_bp_or_kda: Tuple[float, ...] = ()
    observed_bands: Tuple[str, ...] = ()
    notes: str = ""
    custom_columns: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.expected_sizes_bp_or_kda, (list, set)):
            self.expected_sizes_bp_or_kda = tuple(self.expected_sizes_bp_or_kda)
        if isinstance(self.observed_bands, (list, set)):
            self.observed_bands = tuple(self.observed_bands)

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

    @property
    def rf(self) -> float:
        """Alias for relative_migration_rf."""
        return self.relative_migration_rf

    @property
    def size_bp(self) -> float:
        """Alias for band size in base pairs."""
        return self.size

    @property
    def length_bp(self) -> float:
        """Alias for band size in base pairs."""
        return self.size


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

    @property
    def bands(self) -> Tuple[GelBand, ...]:
        """Convenience alias for sample_bands."""
        return self.sample_bands

    @property
    def ladder(self) -> Tuple[GelBand, ...]:
        """Convenience alias for ladder_bands."""
        return self.ladder_bands

    @property
    def ladder_key(self) -> str:
        """Alias for ladder_name."""
        return self.ladder_name

    @property
    def ascii(self) -> str:
        """Alias for ascii_visualization."""
        return self.ascii_visualization

    @property
    def gel_percentage(self) -> str:
        """Alias for recommended_gel_percentage."""
        return self.recommended_gel_percentage

    def to_svg(self, style: Optional[GelTypographyConfig] = None) -> str:
        """Render high-contrast agarose/PAGE gel diagram with customizable typography."""
        import html
        st = style or GelTypographyConfig()
        scale = max(0.7, min(2.5, st.font_scale))
        font_family = html.escape(st.font_family)
        
        width = int(320 * scale)
        height = int(420 * scale)
        gel_top = int(65 * scale)
        gel_bottom = height - int(25 * scale)
        gel_height = gel_bottom - gel_top
        
        title_size = st.title_font_size * scale
        meta_size = st.subtitle_font_size * scale
        lane_size = st.lane_font_size * scale
        ladder_size = st.ladder_font_size * scale
        
        title_weight = "bold" if st.bold_lane_names else "600"
        lane_weight = "bold" if st.bold_lane_names else "normal"
        
        ladder_hdr = f"Ladder ({format_lane_number(1, st)})" if st.show_lane_numbers else "Ladder"
        sample_hdr = f"Sample ({format_lane_number(2, st)})" if st.show_lane_numbers else "Sample"

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
            f'<text x="{width / 2}" y="{int(32 * scale)}" fill="#E0E1DD" font-family="{font_family}" font-size="{title_size:.1f}" font-weight="{title_weight}" text-anchor="middle">{html.escape(self.ladder_name)}</text>',
            f'<text x="{width / 2}" y="{int(48 * scale)}" fill="#778DA9" font-family="{font_family}" font-size="{meta_size:.1f}" text-anchor="middle">Matrix: {html.escape(str(self.recommended_gel_percentage))}</text>',
            f'<rect x="{int(50 * scale)}" y="{int(58 * scale)}" width="{int(60 * scale)}" height="{int(8 * scale)}" rx="2" fill="#0D1B2A" stroke="#415A77" stroke-width="1"/>',
            f'<rect x="{int(170 * scale)}" y="{int(58 * scale)}" width="{int(80 * scale)}" height="{int(8 * scale)}" rx="2" fill="#0D1B2A" stroke="#415A77" stroke-width="1"/>',
            f'<text x="{int(80 * scale)}" y="{int(54 * scale)}" fill="#778DA9" font-family="{font_family}" font-size="{lane_size:.1f}" font-weight="{lane_weight}" text-anchor="middle">{html.escape(ladder_hdr)}</text>',
            f'<text x="{int(210 * scale)}" y="{int(54 * scale)}" fill="#778DA9" font-family="{font_family}" font-size="{lane_size:.1f}" font-weight="{lane_weight}" text-anchor="middle">{html.escape(sample_hdr)}</text>',
        ]

        for b in self.ladder_bands:
            y = gel_top + (b.relative_migration_rf * gel_height)
            band_h = max(2.0, (3.5 if b.is_reference else 2.0) * scale)
            color = "#F43F5E" if b.is_reference else "#38BDF8"
            glow_attr = ' filter="url(#glow)"' if b.is_reference else ''
            b_weight = "bold" if (b.is_reference or st.bold_ladder_labels) else "normal"
            svg.append(f'<rect x="{int(52 * scale)}" y="{y - band_h / 2:.1f}" width="{int(56 * scale)}" height="{band_h:.1f}" rx="1" fill="{color}"{glow_attr}/>')
            svg.append(f'<text x="{int(46 * scale)}" y="{y + 3 * scale:.1f}" fill="{color}" font-family="{font_family}" font-size="{ladder_size:.1f}" font-weight="{b_weight}" text-anchor="end">{b.size} {html.escape(str(b.unit))}</text>')

        for b in self.sample_bands:
            y = gel_top + (b.relative_migration_rf * gel_height)
            b_weight = "bold" if st.bold_band_callouts else "normal"
            svg.append(f'<rect x="{int(172 * scale)}" y="{y - 1.5 * scale:.1f}" width="{int(76 * scale)}" height="{max(2.0, 3.0 * scale):.1f}" rx="1" fill="#34D399" filter="url(#glow)"/>')
            svg.append(f'<text x="{int(254 * scale)}" y="{y + 3 * scale:.1f}" fill="#34D399" font-family="{font_family}" font-size="{ladder_size:.1f}" font-weight="{b_weight}">{b.size} {html.escape(str(b.unit))}</text>')

        svg.append('</svg>')
        return "\n".join(svg)

    def _repr_svg_(self) -> str:
        """Render high-contrast agarose/PAGE gel diagram for Jupyter notebook rich display."""
        return self.to_svg()

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
