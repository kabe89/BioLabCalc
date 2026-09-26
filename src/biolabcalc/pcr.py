"""PCR reaction optimization, dNTP stoichiometry, amplification efficiency, and master mix setup."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional
from .seq_utils import clean_sequence, count_bases
from .molecular_weight import calculate_dna_mw, mass_to_copy_number, copy_number_to_mass, AVOGADRO


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


@dataclass(frozen=True)
class MasterMixItem:
    component: str
    volume_per_reaction_ul: float
    total_volume_ul: float
    final_concentration: str


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
) -> PCRResult:
    """Model PCR amplification kinetics, dNTP/primer consumption, and plateau limits."""
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

    # Double stranded DNA MW approx: len * 617.96 + 36.04
    amplicon_mw = amplicon_len_bp * 617.96 + 36.04
    templ_len = template_total_len_bp or amplicon_len_bp
    templ_mw = templ_len * 617.96 + 36.04

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

    # Max amplicons limited by each dNTP
    max_amplicons_nmol = {
        base: (initial_dntp_nmol[base] / dntp_per_amplicon[base])
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

    # Model exponential growth cycle-by-cycle until plateau or cycles finish
    exhaustion_cycle: Optional[int] = None
    current_copies = n0
    amplicon_copies_produced = 0.0

    for c in range(1, cycles + 1):
        delta_copies = current_copies * efficiency
        if amplicon_copies_produced + delta_copies >= max_amplicon_copies:
            amplicon_copies_produced = max_amplicon_copies
            exhaustion_cycle = c
            current_copies = n0 + amplicon_copies_produced
            break
        amplicon_copies_produced += delta_copies
        current_copies += delta_copies

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
    recommended_additives: List[str]
    cycling_protocol_summary: str


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
