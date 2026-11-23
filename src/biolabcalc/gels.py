"""Gel electrophoresis molecular weight ladders, migration modeling (Rf), and band visualization."""

from __future__ import annotations
import html
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Literal, Sequence, Union
from .seq_utils import clean_sequence
from .molecular_weight import calculate_protein_mw

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


# -------------------------------------------------------------------------
# Enzyme-Supported SDS-PAGE Gel Simulation
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class ProteaseSpec:
    name: str
    recognition_motif: str
    cleavage_description: str
    optimal_temp_celsius: float
    preferred_buffer: str
    typical_incubation_hours: str


PROTEASE_ENZYME_CATALOG: Dict[str, ProteaseSpec] = {
    "TEV": ProteaseSpec(
        name="TEV",
        recognition_motif="ENLYFQ[G/S]",
        cleavage_description="Cleaves between Gln and Gly/Ser (ENLYFQ↓[G/S]) with stringent specificity.",
        optimal_temp_celsius=30.0,
        preferred_buffer="50 mM Tris-HCl pH 8.0, 0.5 mM EDTA, 1 mM DTT",
        typical_incubation_hours="2–4 h at 30°C or 16 h at 4°C",
    ),
    "HRV_3C": ProteaseSpec(
        name="HRV_3C",
        recognition_motif="LEVLFQ[G/P]",
        cleavage_description="Cleaves between Gln and Gly/Pro (LEVLFQ↓[G/P]); highly active at 4°C.",
        optimal_temp_celsius=4.0,
        preferred_buffer="50 mM Tris-HCl pH 7.0, 150 mM NaCl, 1 mM EDTA, 1 mM DTT",
        typical_incubation_hours="16 h (overnight) at 4°C",
    ),
    "Thrombin": ProteaseSpec(
        name="Thrombin",
        recognition_motif="LVPR[G/S]",
        cleavage_description="Cleaves between Arg and Gly/Ser (LVPR↓[G/S]).",
        optimal_temp_celsius=22.0,
        preferred_buffer="20 mM Tris-HCl pH 8.4, 150 mM NaCl, 2.5 mM CaCl2",
        typical_incubation_hours="2–16 h at 20–25°C",
    ),
    "Factor_Xa": ProteaseSpec(
        name="Factor_Xa",
        recognition_motif="I[E/D]GR",
        cleavage_description="Cleaves after Arg in IEGR or IDGR recognition motif (I[E/D]GR↓).",
        optimal_temp_celsius=25.0,
        preferred_buffer="20 mM Tris-HCl pH 8.0, 100 mM NaCl, 2 mM CaCl2",
        typical_incubation_hours="2–16 h at room temperature",
    ),
    "Enterokinase": ProteaseSpec(
        name="Enterokinase",
        recognition_motif="DDDDK",
        cleavage_description="Cleaves specifically after Lysine in Asp-Asp-Asp-Asp-Lys motif (DDDDK↓).",
        optimal_temp_celsius=25.0,
        preferred_buffer="20 mM Tris-HCl pH 8.0, 50 mM NaCl, 2 mM CaCl2",
        typical_incubation_hours="16 h at room temperature",
    ),
    "Ulp1_SUMO": ProteaseSpec(
        name="Ulp1_SUMO",
        recognition_motif="SUMO_GG",
        cleavage_description="Recognizes tertiary structure of SUMO and cleaves directly after C-terminal Gly-Gly.",
        optimal_temp_celsius=30.0,
        preferred_buffer="50 mM Tris-HCl pH 8.0, 150 mM NaCl, 1 mM DTT",
        typical_incubation_hours="1–2 h at 30°C or 16 h at 4°C",
    ),
    "Trypsin": ProteaseSpec(
        name="Trypsin",
        recognition_motif="[K/R](?!P)",
        cleavage_description="Digestive serine protease; cleaves after Lys or Arg unless followed by Proline.",
        optimal_temp_celsius=37.0,
        preferred_buffer="50 mM ammonium bicarbonate pH 8.0 or 50 mM Tris-HCl pH 8.0, 1 mM CaCl2",
        typical_incubation_hours="2–18 h at 37°C",
    ),
    "Chymotrypsin": ProteaseSpec(
        name="Chymotrypsin",
        recognition_motif="[F/Y/W](?!P)",
        cleavage_description="Cleaves after aromatic/hydrophobic residues (Phe, Tyr, Trp) unless followed by Proline.",
        optimal_temp_celsius=30.0,
        preferred_buffer="100 mM Tris-HCl pH 7.8, 10 mM CaCl2",
        typical_incubation_hours="2–4 h at 30°C",
    ),
    "LysC": ProteaseSpec(
        name="LysC",
        recognition_motif="K",
        cleavage_description="Endoproteinase Lys-C; cleaves specifically after Lysine (even when followed by Proline).",
        optimal_temp_celsius=37.0,
        preferred_buffer="25 mM Tris-HCl pH 8.5, 1 mM EDTA",
        typical_incubation_hours="2–18 h at 37°C",
    ),
    "PNGase_F": ProteaseSpec(
        name="PNGase_F",
        recognition_motif="N[^P][S/T]",
        cleavage_description="Peptide-N-glycosidase F; cleaves N-glycans from Asn at N-X-[S/T] sequons (-2.5 kDa/glycan).",
        optimal_temp_celsius=37.0,
        preferred_buffer="50 mM sodium phosphate pH 7.5, 1% NP-40",
        typical_incubation_hours="1–3 h at 37°C",
    ),
}


PROTEASE_ALIAS_MAP: Dict[str, str] = {
    "tev": "TEV",
    "tev_protease": "TEV",
    "hrv": "HRV_3C",
    "hrv3c": "HRV_3C",
    "hrv_3c": "HRV_3C",
    "prescission": "HRV_3C",
    "thrombin": "Thrombin",
    "factor_xa": "Factor_Xa",
    "factorxa": "Factor_Xa",
    "enterokinase": "Enterokinase",
    "ek": "Enterokinase",
    "ulp1": "Ulp1_SUMO",
    "sumo": "Ulp1_SUMO",
    "sumo_protease": "Ulp1_SUMO",
    "ulp1_sumo": "Ulp1_SUMO",
    "trypsin": "Trypsin",
    "chymotrypsin": "Chymotrypsin",
    "lysc": "LysC",
    "lys_c": "LysC",
    "pngase": "PNGase_F",
    "pngase_f": "PNGase_F",
    "pngasef": "PNGase_F",
}


def get_protease_enzyme(name: str) -> Optional[ProteaseSpec]:
    """Retrieve protease enzyme specification by name or alias (case-insensitive)."""
    norm = name.strip().lower().replace("-", "_").replace(" ", "_")
    key = PROTEASE_ALIAS_MAP.get(norm, None)
    if key and key in PROTEASE_ENZYME_CATALOG:
        return PROTEASE_ENZYME_CATALOG[key]
    return PROTEASE_ENZYME_CATALOG.get(name.strip(), None)


@dataclass(frozen=True)
class SDSPageBand:
    mw_kda: float
    relative_migration_rf: float
    label: str
    intensity: float = 1.0
    is_cleaved: bool = False
    notes: str = ""


@dataclass(frozen=True)
class SDSPageLane:
    lane_index: int
    sample_name: str
    bands: Tuple[SDSPageBand, ...]
    condition: str = ""

    def __post_init__(self):
        if isinstance(self.bands, (list, set, tuple)):
            object.__setattr__(self, "bands", tuple(self.bands))


@dataclass(frozen=True)
class SDSPageSimulationResult:
    ladder_name: str
    gel_percent: str
    reducing: bool
    enzyme: Optional[str]
    ladder_bands: Tuple[GelBand, ...]
    sample_lanes: Tuple[SDSPageLane, ...]
    cleavage_events: Tuple[str, ...]
    summary: str

    def __post_init__(self):
        for f in ("ladder_bands", "sample_lanes", "cleavage_events"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))

    def to_svg(self, style: Optional[GelTypographyConfig] = None) -> str:
        """Render high-contrast Coomassie/pre-stained SDS-PAGE gel diagram."""
        st = style or GelTypographyConfig()
        scale = max(0.7, min(2.5, st.font_scale))
        font_family = html.escape(st.font_family)

        num_lanes = 1 + len(self.sample_lanes)
        lane_width = int(75 * scale)
        gel_margin_x = int(60 * scale)
        width = max(int(360 * scale), gel_margin_x * 2 + num_lanes * lane_width)
        height = int(460 * scale)
        gel_top = int(75 * scale)
        gel_bottom = height - int(30 * scale)
        gel_height = gel_bottom - gel_top

        title_size = st.title_font_size * scale
        meta_size = st.subtitle_font_size * scale
        lane_size = st.lane_font_size * scale
        ladder_size = st.ladder_font_size * scale

        title_weight = "bold" if st.bold_lane_names else "600"
        lane_weight = "bold" if st.bold_lane_names else "normal"

        red_label = "Reducing (+DTT)" if self.reducing else "Non-Reducing (-DTT)"
        enz_label = f" • Protease: {self.enzyme}" if self.enzyme else ""
        sub_title = f"{self.gel_percent} SDS-PAGE • {red_label}{enz_label}"

        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
            '<defs>',
            '  <linearGradient id="sdsGelBg" x1="0%" y1="0%" x2="0%" y2="100%">',
            '    <stop offset="0%" stop-color="#0B132B"/>',
            '    <stop offset="100%" stop-color="#1E293B"/>',
            '  </linearGradient>',
            '  <filter id="sdsGlow" x="-20%" y="-20%" width="140%" height="140%">',
            '    <feGaussianBlur stdDeviation="1.5" result="blur" />',
            '    <feMerge>',
            '      <feMergeNode in="blur"/>',
            '      <feMergeNode in="SourceGraphic"/>',
            '    </feMerge>',
            '  </filter>',
            '</defs>',
            f'<rect x="10" y="10" width="{width - 20}" height="{height - 20}" rx="8" fill="url(#sdsGelBg)" stroke="#334155" stroke-width="2"/>',
            f'<text x="{width / 2}" y="{int(30 * scale)}" fill="#F8FAFC" font-family="{font_family}" font-size="{title_size:.1f}" font-weight="{title_weight}" text-anchor="middle">SDS-PAGE Gel Simulation</text>',
            f'<text x="{width / 2}" y="{int(48 * scale)}" fill="#94A3B8" font-family="{font_family}" font-size="{meta_size:.1f}" text-anchor="middle">{html.escape(sub_title)}</text>',
        ]

        # Draw wells and lane headers
        for idx in range(num_lanes):
            x = gel_margin_x + idx * lane_width
            well_w = int(52 * scale)
            well_h = int(7 * scale)
            svg.append(f'<rect x="{x}" y="{int(60 * scale)}" width="{well_w}" height="{well_h}" rx="2" fill="#020617" stroke="#475569" stroke-width="1"/>')
            hdr_text = "Ladder" if idx == 0 else self.sample_lanes[idx - 1].sample_name
            if len(hdr_text) > 10:
                hdr_text = hdr_text[:9] + "…"
            lane_num = format_lane_number(idx + 1, st) if st.show_lane_numbers else ""
            full_hdr = f"{hdr_text} ({lane_num})" if lane_num else hdr_text
            svg.append(f'<text x="{x + well_w / 2}" y="{int(56 * scale)}" fill="#CBD5E1" font-family="{font_family}" font-size="{lane_size:.1f}" font-weight="{lane_weight}" text-anchor="middle">{html.escape(full_hdr)}</text>')

        # Draw ladder bands (Lane 1)
        lad_x = gel_margin_x
        well_w = int(52 * scale)
        for b in self.ladder_bands:
            y = gel_top + (b.relative_migration_rf * gel_height)
            band_h = max(2.0, (3.5 if b.is_reference else 2.0) * scale)
            color = "#F43F5E" if b.is_reference else "#38BDF8"
            glow_attr = ' filter="url(#sdsGlow)"' if b.is_reference else ''
            b_weight = "bold" if (b.is_reference or st.bold_ladder_labels) else "normal"
            svg.append(f'<rect x="{lad_x + 2}" y="{y - band_h / 2:.1f}" width="{well_w - 4}" height="{band_h:.1f}" rx="1" fill="{color}"{glow_attr}/>')
            size_display = int(b.size) if float(b.size).is_integer() else b.size
            svg.append(f'<text x="{lad_x - int(5 * scale)}" y="{y + 3 * scale:.1f}" fill="{color}" font-family="{font_family}" font-size="{ladder_size:.1f}" font-weight="{b_weight}" text-anchor="end">{size_display} {html.escape(str(b.unit))}</text>')

        # Draw sample bands
        for lane_idx, lane in enumerate(self.sample_lanes):
            sx = gel_margin_x + (lane_idx + 1) * lane_width
            for b in lane.bands:
                y = gel_top + (b.relative_migration_rf * gel_height)
                band_h = max(2.0, (2.8 * b.intensity) * scale)
                color = "#34D399" if b.is_cleaved else "#60A5FA"
                svg.append(f'<rect x="{sx + 2}" y="{y - band_h / 2:.1f}" width="{well_w - 4}" height="{band_h:.1f}" rx="1" fill="{color}" filter="url(#sdsGlow)"/>')
                lbl = f"{b.mw_kda:.1f} kDa"
                svg.append(f'<text x="{sx + well_w + int(3 * scale)}" y="{y + 3 * scale:.1f}" fill="{color}" font-family="{font_family}" font-size="{ladder_size:.1f}" font-weight="normal">{html.escape(lbl)}</text>')

        svg.append('</svg>')
        return "\n".join(svg)

    def _repr_svg_(self) -> str:
        """Render SVG diagram for Jupyter notebooks."""
        return self.to_svg()

    def to_html(self) -> str:
        """Render publication-grade HTML summary with SVG gel and lane breakdown table."""
        svg_code = self.to_svg()
        events_html = "".join(f"<li style='margin-bottom: 4px;'>{html.escape(ev)}</li>" for ev in self.cleavage_events)
        
        table_rows = []
        for lane in self.sample_lanes:
            for b in lane.bands:
                status_badge = (
                    "<span style='background: #DCFCE7; color: #166534; font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600;'>Cleaved</span>"
                    if b.is_cleaved
                    else "<span style='background: #EFF6FF; color: #1D4ED8; font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600;'>Monomer</span>"
                )
                note_text = html.escape(b.notes or "-")
                table_rows.append(
                    f"<tr style='border-bottom: 1px solid #E2E8F0; font-size: 13px;'>"
                    f"<td style='padding: 6px 10px; font-weight: 600;'>{html.escape(lane.sample_name)}</td>"
                    f"<td style='padding: 6px 10px;'>{b.mw_kda:.2f} kDa</td>"
                    f"<td style='padding: 6px 10px;'>{b.relative_migration_rf:.3f}</td>"
                    f"<td style='padding: 6px 10px;'>{status_badge}</td>"
                    f"<td style='padding: 6px 10px; color: #64748B;'>{note_text}</td>"
                    f"</tr>"
                )

        events_section = (
            f"<h4 style='font-size: 14px; margin: 16px 0 6px 0; color: #1E293B;'>Cleavage & Modification Events</h4><ul style='font-size: 13px; color: #334155; padding-left: 20px; margin: 0;'>{events_html}</ul>"
            if events_html
            else ""
        )
        return (
            f"<div style='font-family: system-ui, -apple-system, sans-serif; max-width: 820px; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; background: #FFFFFF;'>"
            f"<h3 style='margin: 0 0 8px 0; font-size: 16px; color: #0F172A;'>SDS-PAGE Gel Simulation</h3>"
            f"<div style='color: #475569; font-size: 13px; margin-bottom: 14px;'><strong>Matrix:</strong> {html.escape(self.gel_percent)} • <strong>Condition:</strong> {'Reducing (+DTT)' if self.reducing else 'Non-Reducing (-DTT)'} • <strong>Protease:</strong> {html.escape(self.enzyme or 'None')}</div>"
            f"<div style='margin-bottom: 16px;'>{svg_code}</div>"
            f"<h4 style='font-size: 14px; margin: 16px 0 6px 0; color: #1E293B;'>Lane & Band Summary</h4>"
            f"<table style='width: 100%; border-collapse: collapse; text-align: left;'>"
            f"<thead><tr style='background: #F8FAFC; border-bottom: 2px solid #CBD5E1; font-size: 12px; color: #475569;'>"
            f"<th style='padding: 6px 10px;'>Sample</th><th style='padding: 6px 10px;'>MW (kDa)</th><th style='padding: 6px 10px;'>Rf</th><th style='padding: 6px 10px;'>State</th><th style='padding: 6px 10px;'>Notes</th>"
            f"</tr></thead><tbody>{''.join(table_rows)}</tbody></table>"
            f"{events_section}"
            f"</div>"
        )

    def _repr_html_(self) -> str:
        """Render HTML card for Jupyter notebooks."""
        return self.to_html()


def simulate_sds_page(
    protein_sequences: Union[str, Sequence[str], Dict[str, str]],
    enzyme: Optional[str] = None,
    gel_percent: str = "4-20%",
    reducing: bool = True,
    ladder_key: str = "protein_broad_range",
) -> SDSPageSimulationResult:
    """Simulate SDS-PAGE gel electrophoresis band migration, protease cleavage, and redox states.

    Parameters
    ----------
    protein_sequences : str, Sequence[str], or Dict[str, str]
        Target protein amino acid sequence(s) or dictionary mapping sample names to sequences.
    enzyme : str, optional
        Protease enzyme name (e.g. 'TEV', 'HRV_3C', 'Thrombin', 'Factor_Xa', 'Enterokinase',
        'Ulp1_SUMO', 'Trypsin', 'Chymotrypsin', 'LysC', 'PNGase_F').
    gel_percent : str, default '4-20%'
        Polyacrylamide gel concentration (e.g. '4-20%', '10%', '12%', '15%').
    reducing : bool, default True
        Whether reducing agent (+DTT/+BME) is present. If False, models disulfide multimers and compact monomers.
    ladder_key : str, default 'protein_broad_range'
        Pre-stained protein molecular weight ladder key from LADDER_CATALOG.

    Returns
    -------
    SDSPageSimulationResult
        Frozen dataclass with lane bands, Rf migration coordinates, cleavage details, and SVG/HTML renderers.
    """
    lad_key = ladder_key.lower().replace("-", "_").replace(" ", "_")
    ladder_info = LADDER_CATALOG.get(lad_key, LADDER_CATALOG["protein_broad_range"])
    ladder_sizes = sorted(ladder_info["bands"], reverse=True)
    min_size = min(ladder_sizes)
    max_size = max(ladder_sizes)
    unit = ladder_info["unit"]

    lad_bands = []
    for b in ladder_sizes:
        rf = calculate_rf(b, min_size, max_size)
        is_ref = b in ladder_info.get("reference_bands", [])
        lad_bands.append(GelBand(b, unit, rf, is_ref, f"{b} {unit}"))

    # Normalize samples dictionary
    samples_dict: Dict[str, str] = {}
    if isinstance(protein_sequences, str):
        samples_dict["Sample 1"] = protein_sequences
    elif isinstance(protein_sequences, dict):
        samples_dict = {str(k): str(v) for k, v in protein_sequences.items()}
    elif isinstance(protein_sequences, (list, tuple, set)):
        samples_dict = {f"Sample {i+1}": str(seq) for i, seq in enumerate(protein_sequences)}
    else:
        samples_dict["Sample 1"] = str(protein_sequences)

    protease: Optional[ProteaseSpec] = get_protease_enzyme(enzyme) if enzyme else None
    cleavage_events: List[str] = []
    sample_lanes: List[SDSPageLane] = []

    for lane_num, (sample_name, raw_seq) in enumerate(samples_dict.items(), 1):
        seq = clean_sequence(raw_seq.upper())
        if not seq:
            continue

        cys_count = seq.count("C")
        intact_mw_da = calculate_protein_mw(seq).average_mw
        intact_mw_kda = intact_mw_da / 1000.0

        lane_bands: List[SDSPageBand] = []

        if protease is None:
            # No protease specified: intact protein
            if reducing:
                rf = calculate_rf(intact_mw_kda, min_size, max_size)
                lane_bands.append(
                    SDSPageBand(
                        mw_kda=round(intact_mw_kda, 2),
                        relative_migration_rf=rf,
                        label=f"{sample_name} (intact)",
                        intensity=1.0,
                        is_cleaved=False,
                        notes="Intact monomer under reducing conditions",
                    )
                )
            else:
                # Non-reducing
                if cys_count > 0:
                    if cys_count >= 2:
                        apparent_monomer_kda = intact_mw_kda * 0.95
                        mono_notes = f"Compact monomer ({cys_count} Cys intra-chain disulfides)"
                    else:
                        apparent_monomer_kda = intact_mw_kda
                        mono_notes = f"Unpaired Cys ({cys_count} Cys; monomer)"
                    rf_mono = calculate_rf(apparent_monomer_kda, min_size, max_size)
                    lane_bands.append(
                        SDSPageBand(
                            mw_kda=round(apparent_monomer_kda, 2),
                            relative_migration_rf=rf_mono,
                            label=f"{sample_name} (monomer)",
                            intensity=0.8,
                            is_cleaved=False,
                            notes=mono_notes,
                        )
                    )
                    dimer_kda = intact_mw_kda * 2.0
                    rf_dimer = calculate_rf(dimer_kda, min_size, max_size)
                    lane_bands.append(
                        SDSPageBand(
                            mw_kda=round(dimer_kda, 2),
                            relative_migration_rf=rf_dimer,
                            label=f"{sample_name} (dimer)",
                            intensity=0.5,
                            is_cleaved=False,
                            notes="Covalent disulfide-linked dimer (non-reducing)",
                        )
                    )
                    cleavage_events.append(f"[{sample_name}] Non-reducing: {cys_count} Cys detected; modeled compact monomer ({apparent_monomer_kda:.1f} kDa) and disulfide dimer ({dimer_kda:.1f} kDa).")
                else:
                    rf = calculate_rf(intact_mw_kda, min_size, max_size)
                    lane_bands.append(
                        SDSPageBand(
                            mw_kda=round(intact_mw_kda, 2),
                            relative_migration_rf=rf,
                            label=f"{sample_name} (intact)",
                            intensity=1.0,
                            is_cleaved=False,
                            notes="Zero Cys residues; unaffected by reducing agent",
                        )
                    )
        else:
            # Protease digestion or deglycosylation
            if protease.name == "PNGase_F":
                # N-linked deglycosylation at N-X-[S/T] (where X != P)
                glycan_sites = [m.start() for m in re.finditer(r"N[^P][ST]", seq)]
                num_sites = len(glycan_sites)
                if num_sites > 0:
                    cleaved_mw_kda = intact_mw_kda
                    rf = calculate_rf(cleaved_mw_kda, min_size, max_size)
                    lane_bands.append(
                        SDSPageBand(
                            mw_kda=round(cleaved_mw_kda, 2),
                            relative_migration_rf=rf,
                            label=f"{sample_name} (deglycosylated)",
                            intensity=1.0,
                            is_cleaved=True,
                            notes=f"Deglycosylated ({num_sites} N-glycans removed, ~{num_sites * 2.5:.1f} kDa shift)",
                        )
                    )
                    cleavage_events.append(f"[{sample_name}] PNGase F removed {num_sites} N-glycans (predicted -{num_sites * 2.5:.1f} kDa mobility shift down to {cleaved_mw_kda:.1f} kDa).")
                else:
                    rf = calculate_rf(intact_mw_kda, min_size, max_size)
                    lane_bands.append(
                        SDSPageBand(
                            mw_kda=round(intact_mw_kda, 2),
                            relative_migration_rf=rf,
                            label=f"{sample_name} (untreated)",
                            intensity=1.0,
                            is_cleaved=False,
                            notes="No N-X-[S/T] glycosylation sequons detected",
                        )
                    )
                    cleavage_events.append(f"[{sample_name}] No N-X-[S/T] sequons found; PNGase F causes no mobility shift.")
            else:
                # Polypeptide endopeptidase cleavage
                cut_positions: List[int] = []
                if protease.name == "TEV":
                    # ENLYFQ[GS] -> cut after Q (offset 6)
                    for m in re.finditer(r"ENLYFQ[GS]", seq):
                        cut_positions.append(m.start() + 6)
                elif protease.name == "HRV_3C":
                    # LEVLFQ[GP] -> cut after Q (offset 6)
                    for m in re.finditer(r"LEVLFQ[GP]", seq):
                        cut_positions.append(m.start() + 6)
                elif protease.name == "Thrombin":
                    # LVPR[GS] -> cut after R (offset 4)
                    for m in re.finditer(r"LVPR[GS]", seq):
                        cut_positions.append(m.start() + 4)
                elif protease.name == "Factor_Xa":
                    # I[ED]GR -> cut after R (offset 4)
                    for m in re.finditer(r"I[ED]GR", seq):
                        cut_positions.append(m.start() + 4)
                elif protease.name == "Enterokinase":
                    # DDDDK -> cut after K (offset 5)
                    for m in re.finditer(r"DDDDK", seq):
                        cut_positions.append(m.start() + 5)
                elif protease.name == "Ulp1_SUMO":
                    # Recognizes SUMO C-terminal GG junction
                    for m in re.finditer(r"GG", seq[:150]):
                        cut_positions.append(m.start() + 2)
                elif protease.name == "Trypsin":
                    # [KR](?!P) -> cut after K or R unless followed by P
                    for m in re.finditer(r"[KR](?!P)", seq):
                        cut_positions.append(m.start() + 1)
                elif protease.name == "Chymotrypsin":
                    # [FYW](?!P) -> cut after F, Y, W unless followed by P
                    for m in re.finditer(r"[FYW](?!P)", seq):
                        cut_positions.append(m.start() + 1)
                elif protease.name == "LysC":
                    # K -> cut after K
                    for m in re.finditer(r"K", seq):
                        cut_positions.append(m.start() + 1)

                cut_positions = sorted(set(cut_positions))
                if cut_positions:
                    cuts = [0] + cut_positions + [len(seq)]
                    fragments = [seq[cuts[i]:cuts[i+1]] for i in range(len(cuts) - 1)]
                    fragments = [f for f in fragments if len(f) >= 5]  # Filter out <5 aa peptides

                    frag_mws = []
                    for f_idx, frag in enumerate(fragments, 1):
                        f_mw = calculate_protein_mw(frag).average_mw / 1000.0
                        frag_mws.append(f_mw)
                        if f_mw >= 1.0:  # Peptides < 1 kDa migrate off standard SDS-PAGE
                            rf = calculate_rf(f_mw, min_size, max_size)
                            lane_bands.append(
                                SDSPageBand(
                                    mw_kda=round(f_mw, 2),
                                    relative_migration_rf=rf,
                                    label=f"Frag {f_idx} ({f_mw:.1f} kDa)",
                                    intensity=round(max(0.4, min(1.2, len(frag) / max(1, len(seq)))), 2),
                                    is_cleaved=True,
                                    notes=f"{protease.name} fragment ({len(frag)} aa)",
                                )
                            )

                    frag_desc = ", ".join(f"{mw:.1f} kDa" for mw in frag_mws)
                    cleavage_events.append(
                        f"[{sample_name}] {protease.name} cleaved {len(cut_positions)} site(s) into {len(fragments)} fragments: {frag_desc}."
                    )
                else:
                    rf = calculate_rf(intact_mw_kda, min_size, max_size)
                    lane_bands.append(
                        SDSPageBand(
                            mw_kda=round(intact_mw_kda, 2),
                            relative_migration_rf=rf,
                            label=f"{sample_name} (uncleaved)",
                            intensity=1.0,
                            is_cleaved=False,
                            notes=f"No {protease.name} recognition motif ({protease.recognition_motif}) detected",
                        )
                    )
                    cleavage_events.append(
                        f"[{sample_name}] Zero {protease.name} recognition motifs found; protein remains uncleaved at {intact_mw_kda:.1f} kDa."
                    )

        sample_lanes.append(
            SDSPageLane(
                lane_index=lane_num,
                sample_name=sample_name,
                bands=tuple(lane_bands),
                condition=f"{'Reducing' if reducing else 'Non-reducing'}{f' + {protease.name}' if protease else ''}",
            )
        )

    summary_text = (
        f"Simulated {len(sample_lanes)} lane(s) on a {gel_percent} SDS-PAGE gel "
        f"under {'reducing (+DTT)' if reducing else 'non-reducing (-DTT)'} conditions"
        f"{f' with {protease.name} protease digestion' if protease else ''}."
    )

    return SDSPageSimulationResult(
        ladder_name=ladder_info["name"],
        gel_percent=gel_percent,
        reducing=reducing,
        enzyme=protease.name if protease else None,
        ladder_bands=tuple(lad_bands),
        sample_lanes=tuple(sample_lanes),
        cleavage_events=tuple(cleavage_events),
        summary=summary_text,
    )
