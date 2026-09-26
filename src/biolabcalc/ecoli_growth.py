"""E. coli growth kinetics, doubling times, IPTG induction scheduling, and plasmid/protein yield models."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Doubling times in minutes under standard aeration
DOUBLING_TIMES_MIN: Dict[Tuple[str, int], float] = {
    ("LB", 37): 20.0,
    ("LB", 30): 35.0,
    ("LB", 25): 60.0,
    ("LB", 18): 120.0,
    ("2XYT", 37): 18.0,
    ("TB", 37): 22.0,
    ("M9", 37): 50.0,
}

# Plasmid copy numbers per bacterium
PLASMID_COPY_NUMBERS: Dict[str, int] = {
    "pUC": 600,        # High-copy (pUC19, pBluescript, pCR-Blunt)
    "pET": 40,         # Medium-copy (pET-21, pET-28 with pBR322 origin)
    "pBR322": 25,      # Medium-copy
    "pACYC": 15,       # Low/medium-copy (pACYC184 with p15A origin)
    "pSC101": 5,       # Very low-copy
}

@dataclass(frozen=True)
class EcoliGrowthResult:
    initial_od600: float
    target_od600: float
    temperature_celsius: float
    media: str
    doubling_time_min: float
    growth_rate_per_hour: float
    num_doublings: float
    hours_to_target_od: float
    formatted_time: str
    target_cells_per_ml: float
    warnings: List[str]

@dataclass(frozen=True)
class PlasmidYieldResult:
    plasmid_type: str
    plasmid_length_bp: int
    culture_volume_ml: float
    final_od600: float
    total_bacterial_cells: float
    plasmid_copies_per_cell: int
    total_plasmid_copies: float
    theoretical_yield_ug: float
    typical_miniprep_yield_ug: float

@dataclass(frozen=True)
class ProteinInductionResult:
    protein_mw_da: float
    culture_volume_ml: float
    final_od600: float
    total_cellular_protein_mg: float
    expression_percent_of_total: float
    recombinant_protein_yield_mg: float
    recombinant_protein_nmol: float
    recombinant_protein_yield_ng: float
    recommended_conditions: str


def calculate_ecoli_growth(
    initial_od600: float = 0.05,
    target_od600: float = 0.60,
    temperature_celsius: float = 37.0,
    media: str = "LB",
) -> EcoliGrowthResult:
    """Calculate E. coli growth kinetics and time required to reach induction OD600."""
    if initial_od600 <= 0 or target_od600 <= 0:
        raise ValueError("OD600 values must be positive.")
    if target_od600 <= initial_od600:
        raise ValueError("Target OD600 must be greater than initial OD600.")
    if temperature_celsius < 8.0:
        raise ValueError(f"Temperature {temperature_celsius}°C is below E. coli minimum growth threshold (~8°C).")
    if temperature_celsius >= 44.5:
        raise ValueError(f"Temperature {temperature_celsius}°C exceeds E. coli thermal death boundary (~44.5°C). Exponential growth ceases.")

    med_clean = media.upper().replace(" ", "").replace("-", "")
    temp_round = int(round(temperature_celsius))
    if (med_clean, temp_round) in DOUBLING_TIMES_MIN:
        td = DOUBLING_TIMES_MIN[(med_clean, temp_round)]
    else:
        base_td = DOUBLING_TIMES_MIN.get((med_clean, 37), 20.0)
        q10 = 2.1
        if 36.5 <= temperature_celsius <= 39.5:
            td = base_td
        elif 15.0 <= temperature_celsius < 36.5:
            td = base_td * (q10 ** ((37.0 - temperature_celsius) / 10.0))
        elif 8.0 <= temperature_celsius < 15.0:
            td = base_td * (q10 ** ((37.0 - 15.0) / 10.0)) * 2.8
        else:  # Heat stress 39.5°C to 44.5°C
            heat_penalty = 1.0 + (temperature_celsius - 39.5) * 0.35
            td = base_td * heat_penalty
    td = round(td, 1)

    doublings = math.log2(target_od600 / initial_od600)
    total_min = doublings * td
    total_hours = total_min / 60.0

    hrs = int(total_hours)
    mins = int(round((total_hours - hrs) * 60))

    growth_rate = math.log(2) / (td / 60.0)
    cells_per_ml = target_od600 * 8.0e8

    warnings = []
    if target_od600 > 0.6:
        warnings.append(
            f"Photometric non-linearity warning: Target OD600 ({target_od600:.2f}) exceeds 0.6 AU. "
            "Spectrophotometer readings lose linearity above 0.6 due to multiple light scattering. "
            "Dilute culture 1:5 or 1:10 in fresh media for precise cell density measurement."
        )

    return EcoliGrowthResult(
        initial_od600=initial_od600,
        target_od600=target_od600,
        temperature_celsius=temperature_celsius,
        media=media,
        doubling_time_min=td,
        growth_rate_per_hour=round(growth_rate, 3),
        num_doublings=round(doublings, 2),
        hours_to_target_od=round(total_hours, 2),
        formatted_time=f"{hrs}h {mins}m",
        target_cells_per_ml=round(cells_per_ml, 2),
        warnings=warnings,
    )


def calculate_inoculation_volume(
    starter_od600: float,
    target_volume_ml: float,
    target_od600: float = 0.05,
) -> Dict[str, float]:
    """Calculate starter culture volume and fresh media needed to inoculate a new culture (C1*V1 = C2*V2)."""
    if starter_od600 <= 0 or target_volume_ml <= 0 or target_od600 <= 0:
        raise ValueError("OD600 values and volume must be strictly positive.")
    if starter_od600 <= target_od600:
        raise ValueError(f"Starter culture OD600 ({starter_od600}) must be greater than target initial OD600 ({target_od600}).")

    starter_vol_ml = (target_od600 * target_volume_ml) / starter_od600
    media_vol_ml = target_volume_ml - starter_vol_ml

    return {
        "starter_culture_volume_ml": round(starter_vol_ml, 3),
        "fresh_media_volume_ml": round(media_vol_ml, 3),
        "total_volume_ml": target_volume_ml,
    }


def estimate_plasmid_yield(
    culture_volume_ml: float = 5.0,
    final_od600: float = 3.0,
    plasmid_type: str = "pUC",
    plasmid_length_bp: int = 3000,
) -> PlasmidYieldResult:
    """Estimate theoretical and expected plasmid isolation yield from E. coli culture."""
    if culture_volume_ml <= 0 or final_od600 <= 0 or plasmid_length_bp <= 0:
        raise ValueError("Culture volume, OD600, and plasmid length must be strictly positive.")

    clean_p = plasmid_type.upper().replace("-", "").replace("_", "")
    copies_per_cell = 600
    for k, v in PLASMID_COPY_NUMBERS.items():
        if k.upper() in clean_p:
            copies_per_cell = v
            break

    total_cells = culture_volume_ml * final_od600 * 8.0e8
    total_copies = total_cells * copies_per_cell

    # Circular plasmid MW has no end groups (+36.04)
    mw = plasmid_length_bp * 617.96
    moles = total_copies / 6.02214076e23
    theoretical_ug = (moles * mw) * 1e6
    typical_miniprep_ug = theoretical_ug * 0.55

    return PlasmidYieldResult(
        plasmid_type=plasmid_type,
        plasmid_length_bp=plasmid_length_bp,
        culture_volume_ml=culture_volume_ml,
        final_od600=final_od600,
        total_bacterial_cells=round(total_cells, 2),
        plasmid_copies_per_cell=copies_per_cell,
        total_plasmid_copies=round(total_copies, 2),
        theoretical_yield_ug=round(theoretical_ug, 2),
        typical_miniprep_yield_ug=round(typical_miniprep_ug, 2),
    )


def optimize_protein_induction(
    protein_mw_da: float,
    culture_volume_ml: float = 1000.0,
    final_od600: float = 4.0,
    expression_percent_of_total: float = 15.0,
    temperature_celsius: float = 37.0,
) -> ProteinInductionResult:
    """Predict recombinant protein yield from E. coli overexpression and suggest optimal induction parameters."""
    if protein_mw_da <= 0 or culture_volume_ml <= 0 or final_od600 <= 0 or expression_percent_of_total <= 0:
        raise ValueError("Parameters must be strictly positive.")

    total_cellular_prot_mg = culture_volume_ml * final_od600 * 0.150
    recomb_mg = total_cellular_prot_mg * (expression_percent_of_total / 100.0)
    recomb_ug = recomb_mg * 1000.0
    recomb_ng = recomb_ug * 1000.0
    recomb_nmol = (recomb_mg * 1e-3 / protein_mw_da) * 1e9

    if temperature_celsius <= 20.0:
        cond = "Cold induction (16-20°C overnight with 0.1-0.2 mM IPTG): Maximizes folding & solubility."
    elif temperature_celsius <= 30.0:
        cond = "Moderate induction (28-30°C for 5-6h with 0.4 mM IPTG): Balanced yield and folding."
    else:
        cond = "Standard induction (37°C for 3-4h with 0.5-1.0 mM IPTG): Maximum expression rate; watch for inclusion bodies."

    return ProteinInductionResult(
        protein_mw_da=round(protein_mw_da, 2),
        culture_volume_ml=culture_volume_ml,
        final_od600=final_od600,
        total_cellular_protein_mg=round(total_cellular_prot_mg, 2),
        expression_percent_of_total=expression_percent_of_total,
        recombinant_protein_yield_mg=round(recomb_mg, 3),
        recombinant_protein_nmol=round(recomb_nmol, 2),
        recombinant_protein_yield_ng=round(recomb_ng, 1),
        recommended_conditions=cond,
    )
