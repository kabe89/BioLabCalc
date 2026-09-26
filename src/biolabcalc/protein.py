"""Protein quantification, extinction coefficient calculation, standard curves, and yield tracking."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from .seq_utils import clean_sequence, count_bases
from .molecular_weight import calculate_protein_mw


@dataclass(frozen=True)
class ExtinctionCoefficientResult:
    sequence: str
    length: int
    molecular_weight: float
    extinction_coeff_m_cm: int
    a280_1mg_ml: float
    tryptophan_count: int
    tyrosine_count: int
    cystine_pairs: int


@dataclass(frozen=True)
class ProteinYieldResult:
    sample_name: str
    concentration_mg_ml: float
    concentration_ug_ml: float
    molarity_um: float
    volume_ml: float
    total_yield_mg: float
    total_yield_ug: float
    total_yield_ng: float
    extinction_coeff_m_cm: Optional[int] = None
    molecular_weight: Optional[float] = None


@dataclass(frozen=True)
class StandardCurveResult:
    assay_type: str
    slope: float
    intercept: float
    r_squared: float
    formula_str: str

    def predict(
        self,
        absorbance: float,
        dilution_factor: float = 1.0,
        volume_ml: float = 1.0,
        sample_name: str = "Unknown",
        protein_mw: Optional[float] = None,
    ) -> ProteinYieldResult:
        """Predict concentration and yield from sample absorbance using the standard curve."""
        if self.slope == 0:
            raise ValueError("Slope cannot be zero.")
        # y = mx + b  =>  x = (y - b) / m
        conc_ug_ml = ((absorbance - self.intercept) / self.slope) * dilution_factor
        conc_ug_ml = max(0.0, conc_ug_ml)
        conc_mg_ml = conc_ug_ml / 1000.0

        total_ug = conc_ug_ml * volume_ml
        total_mg = total_ug / 1000.0
        total_ng = total_ug * 1000.0

        mol_um = round((conc_mg_ml / protein_mw) * 1e6, 2) if (protein_mw and protein_mw > 0) else 0.0
        return ProteinYieldResult(
            sample_name=sample_name,
            concentration_mg_ml=round(conc_mg_ml, 4),
            concentration_ug_ml=round(conc_ug_ml, 2),
            molarity_um=mol_um,
            volume_ml=volume_ml,
            total_yield_mg=round(total_mg, 4),
            total_yield_ug=round(total_ug, 2),
            total_yield_ng=round(total_ng, 1),
            molecular_weight=protein_mw,
        )


def calculate_extinction_coefficient(
    seq: str,
    oxidized_cysteines: int = 0,
) -> ExtinctionCoefficientResult:
    """Calculate molar extinction coefficient at 280 nm based on Pace et al. (1995) / Gill & von Hippel.

    ε280 = (N_Trp * 5500) + (N_Tyr * 1490) + (N_cystine * 125) (M^-1 cm^-1)
    """
    clean_seq = clean_sequence(seq)
    counts = count_bases(clean_seq)
    length = len(clean_seq)
    if length == 0:
        return ExtinctionCoefficientResult("", 0, 0.0, 0, 0.0, 0, 0, 0)

    mw_res = calculate_protein_mw(clean_seq, oxidized_cysteines=oxidized_cysteines)
    n_trp = counts.get("W", 0)
    n_tyr = counts.get("Y", 0)
    n_cys = counts.get("C", 0)

    # Pairs of cystines (disulfide bonds)
    cystine_pairs = min(oxidized_cysteines, n_cys) // 2

    # Pace et al. 1995 values
    e280 = (n_trp * 5500) + (n_tyr * 1490) + (cystine_pairs * 125)
    # A280 for 0.1% (1 mg/mL) = ε280 / MW
    a280_1mg_ml = round(e280 / mw_res.average_mw, 3) if mw_res.average_mw > 0 else 0.0

    return ExtinctionCoefficientResult(
        sequence=clean_seq,
        length=length,
        molecular_weight=mw_res.average_mw,
        extinction_coeff_m_cm=e280,
        a280_1mg_ml=a280_1mg_ml,
        tryptophan_count=n_trp,
        tyrosine_count=n_tyr,
        cystine_pairs=cystine_pairs,
    )


def quantify_protein_a280(
    seq: str,
    a280_absorbance: float,
    volume_ml: float = 1.0,
    pathlength_cm: float = 1.0,
    dilution_factor: float = 1.0,
    oxidized_cysteines: int = 0,
    sample_name: str = "Sample",
) -> ProteinYieldResult:
    """Quantify protein concentration and total yield (mg, µg, ng) via A280 absorbance."""
    coeff = calculate_extinction_coefficient(seq, oxidized_cysteines=oxidized_cysteines)
    if coeff.extinction_coeff_m_cm == 0:
        raise ValueError("Sequence contains no Trp, Tyr, or Cystine residues; A280 extinction coefficient is zero.")

    # Beer-Lambert: A = ε * c * l  =>  c (M) = A / (ε * l)
    molar_conc = (a280_absorbance * dilution_factor) / (coeff.extinction_coeff_m_cm * pathlength_cm)
    molarity_um = molar_conc * 1e6

    # c (mg/mL) = c (M) * MW (g/mol) = (g/L) = (mg/mL)
    conc_mg_ml = molar_conc * coeff.molecular_weight
    conc_ug_ml = conc_mg_ml * 1000.0

    total_mg = conc_mg_ml * volume_ml
    total_ug = total_mg * 1000.0
    total_ng = total_ug * 1000.0

    return ProteinYieldResult(
        sample_name=sample_name,
        concentration_mg_ml=round(conc_mg_ml, 4),
        concentration_ug_ml=round(conc_ug_ml, 2),
        molarity_um=round(molarity_um, 2),
        volume_ml=volume_ml,
        total_yield_mg=round(total_mg, 4),
        total_yield_ug=round(total_ug, 2),
        total_yield_ng=round(total_ng, 1),
        extinction_coeff_m_cm=coeff.extinction_coeff_m_cm,
        molecular_weight=coeff.molecular_weight,
    )


def fit_standard_curve(
    standards: List[Tuple[float, float]],
    assay_type: str = "BCA",
) -> StandardCurveResult:
    """Fit a linear regression standard curve from standard concentration vs absorbance pairs.

    Parameters
    ----------
    standards : List of tuples (concentration_ug_ml, absorbance)
    assay_type : str
        e.g. 'BCA' or 'Bradford'
    """
    if len(standards) < 2:
        raise ValueError("At least two standard points are required.")

    xs = [s[0] for s in standards]
    ys = [s[1] for s in standards]
    n = len(standards)

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    ss_yy = sum((y - mean_y) ** 2 for y in ys)

    if ss_xx == 0:
        raise ValueError("Standard concentrations cannot all be identical.")

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    # Pearson r^2
    r2 = (ss_xy ** 2) / (ss_xx * ss_yy) if (ss_xx * ss_yy) > 0 else 0.0
    formula = f"Abs = {slope:.5f} * [conc] + {intercept:.5f} (R² = {r2:.4f})"

    return StandardCurveResult(
        assay_type=assay_type,
        slope=round(slope, 6),
        intercept=round(intercept, 6),
        r_squared=round(r2, 4),
        formula_str=formula,
    )


def calculate_protein_e205(seq: str) -> int:
    """Calculate protein backbone and residue extinction coefficient at 205 nm (M^-1 cm^-1).

    Reference: Anthis, N. J., & Clore, G. M. (2013). Sequence-specific determination of
    protein and peptide concentrations by absorbance at 205 nm. Protein Science, 22(6), 851-858.
    Crucial for quantifying peptides and proteins lacking aromatic residues (Trp/Tyr).
    """
    clean_seq = clean_sequence(seq).replace("*", "")
    n = len(clean_seq)
    if n == 0:
        return 0

    counts = count_bases(clean_seq)
    # Backbone peptide bond contribution: (N - 1) * 2780 M^-1 cm^-1
    e205 = (n - 1) * 2780

    # Side-chain contributions at 205 nm from Anthis & Clore Table 1
    side_chains = {
        "W": 20400, "F": 8600, "Y": 5400, "H": 5200, "M": 1830,
        "R": 1350,  "C": 690,  "K": 110,  "E": 80,   "D": 58,
        "Q": 30,    "N": 30,
    }
    for aa, count in counts.items():
        e205 += count * side_chains.get(aa, 0)
    return e205


def quantify_protein_a205(
    seq: str,
    a205_absorbance: float,
    volume_ml: float = 1.0,
    pathlength_cm: float = 1.0,
    dilution_factor: float = 1.0,
    sample_name: str = "Sample",
) -> ProteinYieldResult:
    """Quantify protein concentration via far-UV peptide backbone absorbance at 205 nm."""
    clean_seq = clean_sequence(seq).replace("*", "")
    mw_res = calculate_protein_mw(clean_seq)
    e205 = calculate_protein_e205(clean_seq)
    if e205 <= 0:
        raise ValueError("Calculated A205 extinction coefficient must be greater than zero.")

    molar_conc = (a205_absorbance * dilution_factor) / (e205 * pathlength_cm)
    molarity_um = molar_conc * 1e6

    conc_mg_ml = molar_conc * mw_res.average_mw
    conc_ug_ml = conc_mg_ml * 1000.0

    total_mg = conc_mg_ml * volume_ml
    total_ug = total_mg * 1000.0
    total_ng = total_ug * 1000.0

    return ProteinYieldResult(
        sample_name=sample_name,
        concentration_mg_ml=round(conc_mg_ml, 4),
        concentration_ug_ml=round(conc_ug_ml, 2),
        molarity_um=round(molarity_um, 2),
        volume_ml=volume_ml,
        total_yield_mg=round(total_mg, 4),
        total_yield_ug=round(total_ug, 2),
        total_yield_ng=round(total_ng, 1),
        extinction_coeff_m_cm=e205,
        molecular_weight=mw_res.average_mw,
    )
