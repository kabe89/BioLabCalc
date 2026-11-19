"""PCR reaction optimization, dNTP stoichiometry, amplification efficiency, and master mix setup."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from .seq_utils import clean_sequence, count_bases
from .molecular_weight import calculate_dna_mw, mass_to_copy_number, copy_number_to_mass, AVOGADRO


@dataclass(frozen=True)
class PCRPolymeraseProfile:
    name: str
    fidelity_vs_taq: float
    extension_rate_sec_per_kb: int
    annealing_offset_celsius: float
    denaturation_temp_celsius: float
    extension_temp_celsius: float
    half_life_95c_min: float
    buffer_conc: str
    mgcl2_default_mm: float
    recommended_dntp_mm: float
    fidelity_desc: str


PCR_POLYMERASE_CATALOG: Dict[str, PCRPolymeraseProfile] = {
    "Q5": PCRPolymeraseProfile(
        name="Q5",
        fidelity_vs_taq=280.0,
        extension_rate_sec_per_kb=25,
        annealing_offset_celsius=1.0,
        denaturation_temp_celsius=98.0,
        extension_temp_celsius=72.0,
        half_life_95c_min=60.0,
        buffer_conc="5X",
        mgcl2_default_mm=2.0,
        recommended_dntp_mm=0.2,
        fidelity_desc="Ultra-high fidelity (~280X Taq); ideal for molecular cloning and mutagenesis.",
    ),
    "Phusion": PCRPolymeraseProfile(
        name="Phusion",
        fidelity_vs_taq=50.0,
        extension_rate_sec_per_kb=25,
        annealing_offset_celsius=1.0,
        denaturation_temp_celsius=98.0,
        extension_temp_celsius=72.0,
        half_life_95c_min=60.0,
        buffer_conc="5X",
        mgcl2_default_mm=1.5,
        recommended_dntp_mm=0.2,
        fidelity_desc="High fidelity (~50X Taq); fast processivity and high yield.",
    ),
    "KAPA_HiFi": PCRPolymeraseProfile(
        name="KAPA_HiFi",
        fidelity_vs_taq=100.0,
        extension_rate_sec_per_kb=15,
        annealing_offset_celsius=-2.0,
        denaturation_temp_celsius=95.0,
        extension_temp_celsius=72.0,
        half_life_95c_min=90.0,
        buffer_conc="5X",
        mgcl2_default_mm=2.5,
        recommended_dntp_mm=0.3,
        fidelity_desc="High fidelity (~100X Taq); engineered for extreme GC/AT-rich templates and NGS libraries.",
    ),
    "Taq": PCRPolymeraseProfile(
        name="Taq",
        fidelity_vs_taq=1.0,
        extension_rate_sec_per_kb=60,
        annealing_offset_celsius=-3.0,
        denaturation_temp_celsius=95.0,
        extension_temp_celsius=72.0,
        half_life_95c_min=40.0,
        buffer_conc="10X",
        mgcl2_default_mm=1.5,
        recommended_dntp_mm=0.2,
        fidelity_desc="Standard fidelity (1X baseline); routine analytical PCR and colony screening.",
    ),
    "OneTaq": PCRPolymeraseProfile(
        name="OneTaq",
        fidelity_vs_taq=2.0,
        extension_rate_sec_per_kb=60,
        annealing_offset_celsius=-3.0,
        denaturation_temp_celsius=95.0,
        extension_temp_celsius=68.0,
        half_life_95c_min=40.0,
        buffer_conc="5X",
        mgcl2_default_mm=1.8,
        recommended_dntp_mm=0.2,
        fidelity_desc="Optimized Taq blend with hot-start aptamer (~2X Taq); robust across GC/AT extremes.",
    ),
    "PrimeSTAR": PCRPolymeraseProfile(
        name="PrimeSTAR",
        fidelity_vs_taq=40.0,
        extension_rate_sec_per_kb=30,
        annealing_offset_celsius=-2.0,
        denaturation_temp_celsius=98.0,
        extension_temp_celsius=72.0,
        half_life_95c_min=60.0,
        buffer_conc="5X",
        mgcl2_default_mm=1.5,
        recommended_dntp_mm=0.2,
        fidelity_desc="High fidelity (~40X Taq) with exceptional elongation through difficult secondary structures.",
    ),
}


def get_pcr_polymerase(name: str = "Taq") -> PCRPolymeraseProfile:
    """Retrieve PCR polymerase profile by name or alias (case-insensitive)."""
    norm = name.strip().lower().replace("-", "_").replace(" ", "_")
    alias_map = {
        "q5": "Q5",
        "phusion": "Phusion",
        "kapa": "KAPA_HiFi",
        "kapa_hifi": "KAPA_HiFi",
        "kapahifi": "KAPA_HiFi",
        "taq": "Taq",
        "standard_taq": "Taq",
        "onetaq": "OneTaq",
        "one_taq": "OneTaq",
        "primestar": "PrimeSTAR",
        "prime_star": "PrimeSTAR",
    }
    key = alias_map.get(norm, "Taq")
    return PCR_POLYMERASE_CATALOG.get(key, PCR_POLYMERASE_CATALOG["Taq"])


@dataclass(frozen=True)
class PCRCycleState:
    cycle: int
    amplicon_copies: float
    amplicon_ng: float
    effective_efficiency: float
    phase: str
    primer_remaining_pct: float
    dntp_remaining_pct: float
    active_enzyme_fraction: float


@dataclass(frozen=True)
class PCRResult:
    amplicon_length_bp: int
    amplicon_mw: float
    template_initial_copies: float
    template_initial_ng: float
    amplicon_yield_ng: float
    amplicon_yield_pmol: float
    amplicon_final_copies: float
    cycles_run: int
    efficiency: float
    efficiency_percent: float
    dntp_initial_nmol: Dict[str, float]
    dntp_consumed_nmol: Dict[str, float]
    dntp_remaining_um: Dict[str, float]
    limiting_dntp: str
    dntp_exhaustion_cycle: Optional[int]
    theoretical_max_amplicon_ug: float
    limiting_reagent: str = "dNTPs"
    cycle_trajectory: Tuple[PCRCycleState, ...] = ()
    polymerase: str = "Taq"
    optimal_cycle_cutoff: Optional[int] = None

    def __post_init__(self):
        if isinstance(self.cycle_trajectory, (list, set, tuple)):
            object.__setattr__(self, "cycle_trajectory", tuple(self.cycle_trajectory))

    @property
    def length_bp(self) -> int:
        """Alias for amplicon length in base pairs."""
        return self.amplicon_length_bp

    @property
    def size_bp(self) -> int:
        """Alias for amplicon length in base pairs."""
        return self.amplicon_length_bp

    @property
    def length(self) -> int:
        """Alias for amplicon length in base pairs."""
        return self.amplicon_length_bp

    @property
    def size(self) -> int:
        """Alias for amplicon length in base pairs."""
        return self.amplicon_length_bp

    @property
    def mw(self) -> float:
        """Alias for amplicon molecular weight in Daltons."""
        return self.amplicon_mw

    @property
    def molecular_weight(self) -> float:
        """Alias for amplicon molecular weight in Daltons."""
        return self.amplicon_mw

    @property
    def yield_ng(self) -> float:
        """Alias for amplicon yield in ng."""
        return self.amplicon_yield_ng

    @property
    def yield_pmol(self) -> float:
        """Alias for amplicon yield in pmol."""
        return self.amplicon_yield_pmol

    @property
    def cycles(self) -> int:
        """Alias for cycles_run."""
        return self.cycles_run

    def _repr_html_(self) -> str:
        """Render clean HTML summary for Jupyter notebooks."""
        import html
        return (
            f'<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #E2E8F0; '
            f'border-radius: 8px; padding: 14px; max-width: 580px; background: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
            f'<h3 style="margin: 0; font-size: 15px; color: #0F172A;">PCR Amplification Yield</h3>'
            f'<span style="background: #EFF6FF; color: #1D4ED8; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px;">{self.cycles_run} Cycles • {self.efficiency_percent:.1f}% Eff</span>'
            f'</div>'
            f'<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">Amplicon Size</td><td style="text-align: right; font-weight: 600;">{self.amplicon_length_bp:,} bp ({self.amplicon_mw:,.1f} Da)</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">Yield (Mass / Moles)</td><td style="text-align: right; font-weight: 600; color: #2563EB;">{self.amplicon_yield_ng:,.1f} ng ({self.amplicon_yield_pmol:,.2f} pmol)</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">Template → Amplicon Copies</td><td style="text-align: right;">{self.template_initial_copies:.2e} → {self.amplicon_final_copies:.2e}</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">Theoretical Max</td><td style="text-align: right;">{self.theoretical_max_amplicon_ug:,.2f} µg</td></tr>'
            f'<tr><td style="padding: 4px 0; color: #64748B;">Limiting Factor</td><td style="text-align: right; font-weight: 600; color: #D97706;">{html.escape(self.limiting_reagent)} ({html.escape(self.limiting_dntp)})</td></tr>'
            f'</table>'
            f'</div>'
        )


@dataclass(frozen=True)
class MasterMixItem:
    component: str
    volume_per_reaction_ul: float
    total_volume_ul: float
    final_concentration: str

    @property
    def name(self) -> str:
        """Alias for component name."""
        return self.component

    @property
    def volume_ul(self) -> float:
        """Alias for volume_per_reaction_ul."""
        return self.volume_per_reaction_ul

    @property
    def per_rxn_ul(self) -> float:
        """Alias for volume_per_reaction_ul."""
        return self.volume_per_reaction_ul

    @property
    def total_ul(self) -> float:
        """Alias for total_volume_ul."""
        return self.total_volume_ul

    @property
    def conc(self) -> str:
        """Alias for final_concentration."""
        return self.final_concentration


# Ergonomic class aliases
PCRReaction = PCRResult
PCRMasterMix = MasterMixItem


def calculate_qpcr_efficiency(slope: float) -> tuple[float, float]:
    """Calculate PCR amplification efficiency from standard curve slope (Ct vs log10 copy number).

    Parameters
    ----------
    slope : float
        Slope of the linear regression line (ideally -3.322 for 100% efficiency).

    Returns
    -------
    tuple of (efficiency_fraction, efficiency_percent)
        e.g., (1.00, 100.0)
    """
    if slope >= 0:
        raise ValueError("Standard curve slope must be negative.")
    if slope < -6.0 or slope > -2.0:
        raise ValueError(f"qPCR slope ({slope:.3f}) is outside plausible biological amplification range (-6.0 to -2.0).")
    eff = (10.0 ** (-1.0 / slope)) - 1.0
    return round(eff, 4), round(eff * 100.0, 2)


def calculate_pcr_kinetics(
    amplicon_len_bp: int,
    template_ng: float,
    template_total_len_bp: Optional[int] = None,
    cycles: int = 30,
    efficiency: float = 1.0,
    reaction_volume_ul: float = 50.0,
    dntp_conc_mm: float = 0.2,
    amplicon_gc_pct: float = 50.0,
    forward_primer_nm: float = 400.0,
    reverse_primer_nm: float = 400.0,
    polymerase: str = "Taq",
    cycle_denat_sec: float = 30.0,
) -> PCRResult:
    """Model PCR amplification kinetics, cycle-by-cycle trajectory, dNTP/primer consumption, and plateau limits."""
    if amplicon_len_bp <= 0:
        raise ValueError("Amplicon length must be greater than zero.")
    if template_ng <= 0:
        raise ValueError("Template mass must be greater than zero.")
    if cycles <= 0:
        raise ValueError("Number of cycles must be positive.")
    if efficiency < 0 or efficiency > 1.0:
        raise ValueError("Efficiency must be between 0.0 and 1.0.")
    if reaction_volume_ul <= 0:
        raise ValueError("Reaction volume must be positive.")
    if amplicon_gc_pct < 0.0 or amplicon_gc_pct > 100.0:
        raise ValueError("Amplicon GC percentage must be between 0.0 and 100.0.")
    if forward_primer_nm <= 0 or reverse_primer_nm <= 0:
        raise ValueError("Primer concentrations must be positive numbers.")
    if dntp_conc_mm <= 0:
        raise ValueError("dNTP concentration must be positive.")

    poly_profile = get_pcr_polymerase(polymerase)

    # Calculate double-stranded DNA MW via centralized calculate_dna_mw
    amplicon_mw = calculate_dna_mw(length=amplicon_len_bp, double_stranded=True).molecular_weight
    templ_len = template_total_len_bp or amplicon_len_bp
    templ_mw = calculate_dna_mw(length=templ_len, double_stranded=True).molecular_weight

    # Initial template copy number
    n0 = mass_to_copy_number(template_ng, "ng", templ_mw)

    # Initial dNTP nmol in reaction: vol (µL) * conc (mM = nmol/µL)
    initial_dntp_nmol = {
        "dATP": dntp_conc_mm * reaction_volume_ul,
        "dCTP": dntp_conc_mm * reaction_volume_ul,
        "dGTP": dntp_conc_mm * reaction_volume_ul,
        "dTTP": dntp_conc_mm * reaction_volume_ul,
    }

    # dNTPs per double-stranded amplicon molecule
    gc_frac = amplicon_gc_pct / 100.0
    at_frac = 1.0 - gc_frac
    dntp_per_amplicon = {
        "dATP": amplicon_len_bp * at_frac,
        "dCTP": amplicon_len_bp * gc_frac,
        "dGTP": amplicon_len_bp * gc_frac,
        "dTTP": amplicon_len_bp * at_frac,
    }

    # Max amplicons limited by each dNTP (guard against 0 consumption when at_frac or gc_frac is 0)
    max_amplicons_nmol = {
        base: (initial_dntp_nmol[base] / dntp_per_amplicon[base])
        if dntp_per_amplicon[base] > 0
        else float("inf")
        for base in initial_dntp_nmol
    }
    limiting_dntp = min(max_amplicons_nmol, key=max_amplicons_nmol.get)
    max_dntp_amplicon_nmol = max_amplicons_nmol[limiting_dntp]
    max_dntp_copies = max_dntp_amplicon_nmol * 1e-9 * AVOGADRO

    # Max amplicons limited by primers
    min_primer_nm = min(forward_primer_nm, reverse_primer_nm)
    primer_nmol = (min_primer_nm * 1e-9) * (reaction_volume_ul * 1e-6) * 1e9
    max_primer_copies = primer_nmol * 1e-9 * AVOGADRO

    limiting_reagent = "dNTPs"
    if max_primer_copies < max_dntp_copies:
        max_amplicon_copies = max_primer_copies
        limiting_reagent = "Primers"
    else:
        max_amplicon_copies = max_dntp_copies

    theoretical_max_ug = (max_amplicon_copies / AVOGADRO) * amplicon_mw * 1e6

    # Model cycle-by-cycle exponential -> linear -> plateau kinetics
    trajectory: List[PCRCycleState] = []
    exhaustion_cycle: Optional[int] = None
    optimal_cutoff: Optional[int] = None
    current_copies = n0
    amplicon_copies_produced = 0.0

    for c in range(1, cycles + 1):
        # Enzyme thermal inactivation at 95°C (exponential decay)
        denat_mins = (c * cycle_denat_sec) / 60.0
        active_enzyme = 2.0 ** (-denat_mins / max(1.0, poly_profile.half_life_95c_min))

        # Primer and dNTP depletion factors
        primer_rem_pct = max(0.0, (1.0 - (amplicon_copies_produced / max(1.0, max_primer_copies))) * 100.0)
        dntp_rem_pct = max(0.0, (1.0 - (amplicon_copies_produced / max(1.0, max_dntp_copies))) * 100.0)

        # Product re-annealing inhibition (KI ~ 0.5 * max_primer_copies)
        ki = 0.5 * max_primer_copies
        reanneal_factor = 1.0 / (1.0 + (amplicon_copies_produced / max(1.0, ki)))

        effective_eff = (
            efficiency
            * min(1.0, primer_rem_pct / 100.0)
            * min(1.0, dntp_rem_pct / 100.0)
            * active_enzyme
            * reanneal_factor
        )

        if effective_eff >= 0.70 * efficiency:
            phase = "exponential"
        elif effective_eff >= 0.08 * efficiency:
            phase = "linear"
        else:
            phase = "plateau"

        delta_copies = current_copies * effective_eff
        if exhaustion_cycle is None and (
            amplicon_copies_produced + delta_copies >= 0.95 * max_amplicon_copies
            or primer_rem_pct <= 5.0
            or dntp_rem_pct <= 5.0
        ):
            exhaustion_cycle = c

        if amplicon_copies_produced + delta_copies >= max_amplicon_copies:
            delta_copies = max(0.0, max_amplicon_copies - amplicon_copies_produced)
            amplicon_copies_produced = max_amplicon_copies
            phase = "plateau"
            if exhaustion_cycle is None:
                exhaustion_cycle = c

        amplicon_copies_produced += delta_copies
        current_copies += delta_copies

        cycle_ng = copy_number_to_mass(amplicon_copies_produced, amplicon_mw, target_unit="ng")
        trajectory.append(
            PCRCycleState(
                cycle=c,
                amplicon_copies=round(amplicon_copies_produced, 2),
                amplicon_ng=round(cycle_ng, 4 if cycle_ng < 0.1 else 2),
                effective_efficiency=round(effective_eff, 4),
                phase=phase,
                primer_remaining_pct=round(primer_rem_pct, 1),
                dntp_remaining_pct=round(dntp_rem_pct, 1),
                active_enzyme_fraction=round(active_enzyme, 3),
            )
        )

        if optimal_cutoff is None and (amplicon_copies_produced >= 0.90 * max_amplicon_copies or phase == "plateau"):
            optimal_cutoff = c

    final_copies = amplicon_copies_produced
    amplicon_pmol = (final_copies / AVOGADRO) * 1e12
    amplicon_ng = copy_number_to_mass(final_copies, amplicon_mw, target_unit="ng")
    amplicon_ng_disp = round(amplicon_ng, 4 if amplicon_ng < 0.1 else 2)
    amplicon_pmol_disp = round(amplicon_pmol, 5 if amplicon_pmol < 0.01 else 3)

    # dNTP consumption
    amplicon_nmol = amplicon_pmol / 1000.0
    dntp_consumed_nmol = {
        base: dntp_per_amplicon[base] * amplicon_nmol
        for base in initial_dntp_nmol
    }

    dntp_remaining_um = {}
    for base in initial_dntp_nmol:
        rem_nmol = max(0.0, initial_dntp_nmol[base] - dntp_consumed_nmol[base])
        dntp_remaining_um[base] = round((rem_nmol / reaction_volume_ul) * 1000.0, 2)

    return PCRResult(
        amplicon_length_bp=amplicon_len_bp,
        amplicon_mw=round(amplicon_mw, 2),
        template_initial_copies=round(n0, 2),
        template_initial_ng=template_ng,
        amplicon_yield_ng=amplicon_ng_disp,
        amplicon_yield_pmol=amplicon_pmol_disp,
        amplicon_final_copies=round(final_copies, 2),
        cycles_run=cycles,
        efficiency=round(efficiency, 3),
        efficiency_percent=round(efficiency * 100.0, 1),
        dntp_initial_nmol={k: round(v, 3) for k, v in initial_dntp_nmol.items()},
        dntp_consumed_nmol={k: round(v, 4) for k, v in dntp_consumed_nmol.items()},
        dntp_remaining_um=dntp_remaining_um,
        limiting_dntp=limiting_dntp,
        dntp_exhaustion_cycle=exhaustion_cycle,
        theoretical_max_amplicon_ug=round(theoretical_max_ug, 2),
        limiting_reagent=limiting_reagent,
        cycle_trajectory=tuple(trajectory),
        polymerase=poly_profile.name,
        optimal_cycle_cutoff=optimal_cutoff,
    )


def build_master_mix(
    num_reactions: int,
    reaction_volume_ul: float = 50.0,
    buffer_conc: str = "5X",
    dntp_stock_mm: float = 10.0,
    dntp_final_mm: float = 0.2,
    fwd_primer_stock_um: float = 10.0,
    fwd_primer_final_um: float = 0.4,
    rev_primer_stock_um: float = 10.0,
    rev_primer_final_um: float = 0.4,
    poly_units_per_rxn: float = 1.0,
    poly_stock_units_per_ul: float = 2.0,
    template_volume_ul: float = 2.0,
    excess_percent: float = 10.0,
) -> List[MasterMixItem]:
    """Generate a master mix pipetting table for N reactions with excess allowance."""
    multiplier = num_reactions * (1.0 + (excess_percent / 100.0))

    # Buffer (case-insensitive)
    buf_factor = float(buffer_conc.upper().replace("X", "").strip())
    buffer_vol = reaction_volume_ul / buf_factor

    # dNTPs (10 mM stock to 0.2 mM final)
    dntp_vol = (dntp_final_mm * reaction_volume_ul) / dntp_stock_mm

    # Primers
    fwd_vol = (fwd_primer_final_um * reaction_volume_ul) / fwd_primer_stock_um
    rev_vol = (rev_primer_final_um * reaction_volume_ul) / rev_primer_stock_um

    # Polymerase
    poly_vol = poly_units_per_rxn / poly_stock_units_per_ul

    # Water
    water_vol = reaction_volume_ul - (buffer_vol + dntp_vol + fwd_vol + rev_vol + poly_vol + template_volume_ul)
    if water_vol < 0:
        raise ValueError("Sum of component volumes exceeds total reaction volume.")

    items = [
        MasterMixItem("Nuclease-Free Water", round(water_vol, 2), round(water_vol * multiplier, 2), "-"),
        MasterMixItem(f"{buffer_conc} PCR Buffer", round(buffer_vol, 2), round(buffer_vol * multiplier, 2), "1X"),
        MasterMixItem("dNTP Mix (10 mM each)", round(dntp_vol, 2), round(dntp_vol * multiplier, 2), f"{dntp_final_mm} mM"),
        MasterMixItem("Forward Primer", round(fwd_vol, 2), round(fwd_vol * multiplier, 2), f"{fwd_primer_final_um} µM"),
        MasterMixItem("Reverse Primer", round(rev_vol, 2), round(rev_vol * multiplier, 2), f"{rev_primer_final_um} µM"),
        MasterMixItem("DNA Polymerase", round(poly_vol, 2), round(poly_vol * multiplier, 2), f"{poly_units_per_rxn} U"),
        MasterMixItem("Template DNA (add per tube)", round(template_volume_ul, 2), round(template_volume_ul * num_reactions, 2), "Variable"),
    ]
    return items


@dataclass(frozen=True)
class PCROptimizationResult:
    annealing_temp_celsius: float
    denaturation_temp_celsius: float
    extension_time_seconds: int
    extension_temp_celsius: float
    polymerase: str
    amplicon_len_bp: int
    gc_percent: float
    touchdown_initial_ta: float
    touchdown_cycles: int
    recommended_additives: Tuple[str, ...]
    cycling_protocol_summary: str

    def __post_init__(self):
        if isinstance(self.recommended_additives, (list, set, tuple)):
            object.__setattr__(self, "recommended_additives", tuple(self.recommended_additives))


def optimize_pcr_protocol(
    primer_fwd_tm: float,
    primer_rev_tm: float,
    amplicon_len_bp: int,
    polymerase: str = "taq",
    gc_percent: float = 50.0,
) -> PCROptimizationResult:
    """Optimize PCR annealing temperature, extension time, touchdown schedule, and GC additives."""
    poly = polymerase.lower()
    min_tm = min(primer_fwd_tm, primer_rev_tm)
    max_tm = max(primer_fwd_tm, primer_rev_tm)

    if poly in ("q5", "phusion"):
        ta = min_tm + 1.0
        ext_rate_sec_per_kb = 25
        denat_temp = 98.0
        ext_temp = 72.0
    elif poly in ("kapa", "platinum"):
        ta = min_tm - 2.0
        ext_rate_sec_per_kb = 15
        denat_temp = 95.0
        ext_temp = 72.0
    else:  # Standard Taq
        ta = min_tm - 3.0
        ext_rate_sec_per_kb = 60
        denat_temp = 95.0
        ext_temp = 68.0 if poly == "one_taq" else 72.0

    ext_time = max(15, int(math.ceil((amplicon_len_bp / 1000.0) * ext_rate_sec_per_kb)))
    td_initial = max_tm + 3.0
    td_cycles = 10

    additives = []
    if gc_percent >= 65.0:
        additives.append("High GC detected (≥65%): Add 3% to 5% DMSO or 1.0 M Betaine to reduce secondary structure.")
    elif gc_percent <= 35.0:
        additives.append("Low GC detected (≤35%): Consider lowering annealing temperature or increasing primer concentration.")
    if abs(primer_fwd_tm - primer_rev_tm) > 3.0:
        additives.append(f"Mismatched primer Tms (ΔTm = {abs(primer_fwd_tm - primer_rev_tm):.1f}°C): Touchdown PCR strongly recommended.")

    summary = (
        f"1x Initial Denat: {denat_temp:.0f}°C for 2 min | "
        f"30-35x [Denat: {denat_temp:.0f}°C 20s, Anneal: {ta:.1f}°C 20s, Ext: {ext_temp:.0f}°C {ext_time}s] | "
        f"1x Final Ext: {ext_temp:.0f}°C 5 min"
    )

    return PCROptimizationResult(
        annealing_temp_celsius=round(ta, 1),
        denaturation_temp_celsius=denat_temp,
        extension_time_seconds=ext_time,
        extension_temp_celsius=ext_temp,
        polymerase=polymerase,
        amplicon_len_bp=amplicon_len_bp,
        gc_percent=gc_percent,
        touchdown_initial_ta=round(td_initial, 1),
        touchdown_cycles=td_cycles,
        recommended_additives=additives,
        cycling_protocol_summary=summary,
    )
