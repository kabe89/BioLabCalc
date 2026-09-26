"""Spectrophotometry, NanoDrop absorbance predictions (A260/A280), and standardized solution formulation."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from .seq_utils import clean_sequence, count_bases
from .molecular_weight import (
    calculate_dna_mw,
    calculate_rna_mw,
    calculate_protein_mw,
    mass_to_copy_number,
    AVOGADRO,
)

# Standard empirical mass extinction coefficients at 260 nm (1 OD260 = X ug/mL in 1 cm path)
CONV_FACTOR_RNA_UG_ML: float = 40.0
CONV_FACTOR_SSDNA_UG_ML: float = 33.0
CONV_FACTOR_DSDNA_UG_ML: float = 50.0

# Nearest-neighbor extinction coefficients for RNA at 260 nm (M^-1 cm^-1)
# Ref: Puglisi, J. D., & Tinoco, I. (1989). Methods in Enzymology, 180, 304-325.
NN_E260_RNA: Dict[str, int] = {
    "AA": 27400, "AC": 21000, "AG": 25000, "AU": 24000,
    "CA": 21000, "CC": 14200, "CG": 17800, "CU": 16200,
    "GA": 25200, "GC": 17400, "GG": 21600, "GU": 21200,
    "UA": 24600, "UC": 17200, "UG": 20000, "UU": 19600,
}

MONO_E260_RNA: Dict[str, int] = {
    "A": 15400,
    "C": 7200,
    "G": 11500,
    "U": 9900,
}

# Nearest-neighbor extinction coefficients for DNA at 260 nm (M^-1 cm^-1)
# Ref: Cavaluzzi, M. J., & Borer, P. N. (2004). Nucleic Acids Res, 32(1), e13.
NN_E260_DNA: Dict[str, int] = {
    "AA": 27400, "AC": 21200, "AG": 25000, "AT": 22800,
    "CA": 21200, "CC": 14600, "CG": 18000, "CT": 15200,
    "GA": 25200, "GC": 17600, "GG": 21600, "GT": 20000,
    "TA": 23400, "TC": 16200, "TG": 19000, "TT": 16800,
}

MONO_E260_DNA: Dict[str, int] = {
    "A": 15400,
    "C": 7300,
    "G": 11700,
    "T": 8800,
}


def calculate_nucleic_acid_e260(seq: str, seq_type: str = "rna") -> int:
    """Calculate sequence-specific molar extinction coefficient at 260 nm (M^-1 cm^-1) using nearest-neighbor stacking."""
    is_rna = seq_type.lower() == "rna"
    cleaned = clean_sequence(seq)
    if is_rna:
        cleaned = cleaned.replace("T", "U")
        nn_dict = NN_E260_RNA
        mono_dict = MONO_E260_RNA
    else:
        cleaned = cleaned.replace("U", "T")
        nn_dict = NN_E260_DNA
        mono_dict = MONO_E260_DNA

    n = len(cleaned)
    if n == 0:
        return 0
    if n == 1:
        return mono_dict.get(cleaned, 10000)

    # Nearest-neighbor formula: sum(NN) - sum(internal monomers)
    e_sum = sum(nn_dict.get(cleaned[i:i+2], 20000) for i in range(n - 1))
    e_sub = sum(mono_dict.get(cleaned[i], 10000) for i in range(1, n - 1))
    return max(0, e_sum - e_sub)


@dataclass(frozen=True)
class SolutionRecipeResult:
    target_molarity_um: float
    target_volume_ul: float
    sequence: str
    seq_type: str
    end_5: str
    length_nt: int
    molecular_weight: float
    base_counts: Dict[str, int]
    sequence_extinction_coeff_260: int
    sequence_specific_conversion_factor: float  # µg/mL per OD260
    required_moles_nmol: float
    required_moles_pmol: float
    required_mass_ug: float
    required_mass_ng: float
    actual_concentration_ng_ul: float
    expected_nanodrop_a260_sequence_specific: float
    expected_nanodrop_a260_generic_factor: float
    expected_nanodrop_display_ng_ul_generic_mode: float
    expected_nanodrop_a260_1mm: float
    expected_a260_a280_ratio: float
    stock_volume_needed_ul: Optional[float] = None
    buffer_volume_needed_ul: Optional[float] = None
    preparation_instructions: str = ""


def prepare_standard_solution(
    target_molarity_um: float,
    target_volume_ul: float,
    sequence: Optional[str] = None,
    seq_type: str = "rna",
    rna_length_nt: Optional[int] = None,
    stock_conc_ng_ul: Optional[float] = None,
    end_5: str = "hydroxyl",
) -> SolutionRecipeResult:
    """Calculate the exact mass, moles, sequence-specific extinction coefficient, and predicted NanoDrop readings for preparing a standardized solution.

    Supports custom sequence inputs with exact nearest-neighbor hypochromicity calculations.
    """
    if target_molarity_um <= 0:
        raise ValueError(f"Target molarity must be greater than zero, got {target_molarity_um}.")
    if target_volume_ul <= 0:
        raise ValueError(f"Target volume must be greater than zero, got {target_volume_ul}.")
    clean_seq = clean_sequence(sequence) if sequence else ""
    seq_type_clean = seq_type.lower()

    if clean_seq:
        length = len(clean_seq)
        counts = count_bases(clean_seq)
        if seq_type_clean == "rna":
            clean_seq = clean_seq.replace("T", "U")
            mw_res = calculate_rna_mw(clean_seq, end_5="triphosphate" if end_5 == "triphosphate" else "hydroxyl")
            mw = mw_res.average_mw
            e260 = calculate_nucleic_acid_e260(clean_seq, seq_type="rna")
        elif seq_type_clean in ("dna", "ssdna"):
            clean_seq = clean_seq.replace("U", "T")
            mw_res = calculate_dna_mw(clean_seq, double_stranded=False, end_5=end_5)
            mw = mw_res.average_mw
            e260 = calculate_nucleic_acid_e260(clean_seq, seq_type="dna")
        elif seq_type_clean == "dsdna":
            clean_seq = clean_seq.replace("U", "T")
            mw_res = calculate_dna_mw(clean_seq, double_stranded=True, end_5=end_5)
            mw = mw_res.average_mw
            # True double-strand extinction: sum both strands with 20% hypochromicity
            e_sense = calculate_nucleic_acid_e260(clean_seq, seq_type="dna")
            comp_seq = reverse_complement(clean_seq, seq_type="dna")
            e_comp = calculate_nucleic_acid_e260(comp_seq, seq_type="dna")
            e260 = int(round(0.80 * (e_sense + e_comp)))
        else:
            mw_res = calculate_protein_mw(clean_seq)
            mw = mw_res.average_mw
            e260 = 0
    else:
        # Generic length-based approximation
        length = rna_length_nt or 100
        counts = {}
        if seq_type_clean == "rna":
            mw = length * 321.4 + (177.98 if end_5 == "triphosphate" else -61.96)
            e260 = length * 10000
        elif seq_type_clean in ("dna", "ssdna"):
            mw = length * 308.9 - 61.96
            e260 = length * 10000
        elif seq_type_clean == "dsdna":
            mw = length * 617.96 + 36.04
            e260 = length * 13200
        else:
            mw = length * 110.0 + 18.0
            e260 = 0

    # Total moles required: M (mol/L) * Vol (L)
    moles_nmol = (target_molarity_um * 1e-6) * (target_volume_ul * 1e-6) * 1e9
    moles_pmol = moles_nmol * 1000.0

    # Mass = moles (mol) * MW (g/mol)
    mass_grams = (moles_nmol * 1e-9) * mw
    mass_ug = mass_grams * 1e6
    mass_ng = mass_grams * 1e9

    # Actual physical concentration in ng/µL = mass_ng / volume_ul
    actual_conc_ng_ul = mass_ng / target_volume_ul

    # Sequence-specific conversion factor (µg/mL per OD260) = (MW / e260) * 1000
    conv_factor_seq = round((mw / e260) * 1000.0, 2) if e260 > 0 else 40.0

    # Expected NanoDrop A260 readings:
    # 1. Beer-Lambert sequence-specific: A = e * c * l  (where c is M, l is 1 cm)
    c_molar = target_molarity_um * 1e-6
    a260_seq = round(e260 * c_molar * 1.0, 3)

    # 2. Generic instrument factor conversion: A = conc / factor
    if seq_type_clean == "rna":
        gen_factor = CONV_FACTOR_RNA_UG_ML
        expected_ratio = 2.00
    elif seq_type_clean == "dsdna":
        gen_factor = CONV_FACTOR_DSDNA_UG_ML
        expected_ratio = 1.80
    elif seq_type_clean in ("dna", "ssdna"):
        gen_factor = CONV_FACTOR_SSDNA_UG_ML
        expected_ratio = 1.85
    else:
        gen_factor = 1000.0
        expected_ratio = 0.57

    a260_generic = round(actual_conc_ng_ul / gen_factor, 3)

    # If NanoDrop is operating in standard mode, it calculates displayed concentration as A260_measured * gen_factor
    nanodrop_display_ng_ul = round(a260_seq * gen_factor, 2)

    # 1 mm physical path absorbance
    a260_1mm = round(a260_seq * 0.1, 4)

    stock_vol: Optional[float] = None
    buff_vol: Optional[float] = None
    instructions: str = ""

    if stock_conc_ng_ul is not None and stock_conc_ng_ul > 0:
        stock_vol = mass_ng / stock_conc_ng_ul
        if stock_vol > target_volume_ul:
            buff_vol = 0.0
            instructions = (
                f"WARNING: Target concentration ({actual_conc_ng_ul:.1f} ng/µL) exceeds stock concentration "
                f"({stock_conc_ng_ul:.1f} ng/µL). Cannot prepare by dilution without concentrating the stock."
            )
        else:
            buff_vol = max(0.0, target_volume_ul - stock_vol)
            instructions = (
                f"Pipette {stock_vol:.2f} µL of stock ({stock_conc_ng_ul:.1f} ng/µL) into {buff_vol:.2f} µL "
                f"of nuclease-free water/buffer to yield {target_volume_ul:.1f} µL of {target_molarity_um:.2f} µM solution."
            )
    else:
        instructions = (
            f"Dissolve {mass_ug:.3f} µg ({mass_ng:.1f} ng, {moles_nmol:.3f} nmol) of lyophilized {seq_type_clean.upper()} in "
            f"{target_volume_ul:.1f} µL of buffer to achieve {target_molarity_um:.2f} µM."
        )

    return SolutionRecipeResult(
        target_molarity_um=target_molarity_um,
        target_volume_ul=target_volume_ul,
        sequence=clean_seq or f"({seq_type_clean.upper()} length ~{length} nt)",
        seq_type=seq_type_clean.upper(),
        end_5=end_5,
        length_nt=length,
        molecular_weight=round(mw, 2),
        base_counts=counts,
        sequence_extinction_coeff_260=e260,
        sequence_specific_conversion_factor=conv_factor_seq,
        required_moles_nmol=round(moles_nmol, 4),
        required_moles_pmol=round(moles_pmol, 2),
        required_mass_ug=round(mass_ug, 4),
        required_mass_ng=round(mass_ng, 2),
        actual_concentration_ng_ul=round(actual_conc_ng_ul, 2),
        expected_nanodrop_a260_sequence_specific=a260_seq,
        expected_nanodrop_a260_generic_factor=a260_generic,
        expected_nanodrop_display_ng_ul_generic_mode=nanodrop_display_ng_ul,
        expected_nanodrop_a260_1mm=a260_1mm,
        expected_a260_a280_ratio=expected_ratio,
        stock_volume_needed_ul=round(stock_vol, 2) if stock_vol is not None else None,
        buffer_volume_needed_ul=round(buff_vol, 2) if buff_vol is not None else None,
        preparation_instructions=instructions,
    )


def ng_per_ul_to_micromolar(conc_ng_ul: float, mw_g_mol: float) -> float:
    """Convert concentration from ng/µL (or µg/mL) to micromolar (µM)."""
    if mw_g_mol <= 0:
        raise ValueError("Molecular weight must be positive.")
    # (ng/µL) = (mg/L). Molarity = (g/L) / MW = (mg/L * 1e-3) / MW. In µM: M * 1e6 = (mg/L / MW) * 1000
    return round((conc_ng_ul / mw_g_mol) * 1000.0, 4)


def micromolar_to_ng_per_ul(conc_um: float, mw_g_mol: float) -> float:
    """Convert concentration from micromolar (µM) to ng/µL (or µg/mL)."""
    if mw_g_mol <= 0:
        raise ValueError("Molecular weight must be positive.")
    return round((conc_um * mw_g_mol) / 1000.0, 4)


@dataclass(frozen=True)
class NanoDropPurityResult:
    a260: float
    a280: float
    a230: float
    sample_type: str
    a260_a280_ratio: float
    a260_a230_ratio: float
    purity_status: str  # "Pure", "Marginal", "Contaminated"
    protein_contamination: bool
    salt_or_solvent_contamination: bool
    phenol_contamination_risk: bool
    corrected_a260: float
    corrected_concentration_ng_ul: float
    diagnostic_feedback: List[str]


def assess_nanodrop_purity(
    a260: float,
    a280: float,
    a230: float,
    sample_type: str = "rna",
) -> NanoDropPurityResult:
    """Assess nucleic acid purity from NanoDrop A260, A280, and A230 absorbance values.

    Parameters
    ----------
    a260 : float
        Absorbance at 260 nm (nucleic acid peak).
    a280 : float
        Absorbance at 280 nm (protein / aromatic peak).
    a230 : float
        Absorbance at 230 nm (salt / solvent / background peak).
    sample_type : str
        'rna' (ideal A260/A280 ~2.0) or 'dna' (ideal A260/A280 ~1.8).
    """
    if a260 < 0 or a280 < 0 or a230 < 0:
        raise ValueError("Absorbance values cannot be negative.")

    s_type = sample_type.lower()
    is_rna = "rna" in s_type

    r280 = round(a260 / a280, 2) if a280 > 0 else 0.0
    r230 = round(a260 / a230, 2) if a230 > 0 else 0.0

    target_r280 = 2.00 if is_rna else 1.80
    conv_factor = 40.0 if is_rna else 50.0

    feedback: List[str] = []
    prot_contam = False
    salt_contam = False
    phenol_risk = False

    min_acceptable_280 = 1.75 if is_rna else 1.65
    if r280 < min_acceptable_280:
        prot_contam = True
        feedback.append(
            f"Low A260/A280 ({r280:.2f} vs expected ~{target_r280:.2f}). Indicates protein carryover or acidic phenol."
        )
    elif r280 > 2.25:
        feedback.append(
            f"High A260/A280 ({r280:.2f}). Check for blanking drift or alkaline pH buffer shift."
        )

    if r230 < 1.80:
        salt_contam = True
        feedback.append(
            f"Low A260/A230 ({r230:.2f} vs expected 2.00–2.20). Indicates chaotropic salt (guanidinium thiocyanate/HCl), EDTA, carbohydrate, or alcohol carryover."
        )

    if r280 < 1.70 and r230 < 1.50:
        phenol_risk = True
        feedback.append(
            "CRITICAL: Both A260/A280 and A260/A230 are severely depressed. Strongly suggests residual phenol contamination (peak absorbance at 270 nm falsely elevates apparent A260). Perform chloroform extraction or ethanol precipitation before proceeding."
        )

    if not prot_contam and not salt_contam:
        purity_status = "Pure"
        feedback.append(f"Sample matches purity criteria for {s_type.upper()} (A260/A280 = {r280:.2f}, A260/A230 = {r230:.2f}).")
    elif prot_contam and salt_contam:
        purity_status = "Contaminated"
    else:
        purity_status = "Marginal"

    # Corrected A260 estimation
    corrected_a260 = max(0.0, round(a260 - (0.15 * a280 if prot_contam else 0.0), 3))
    corrected_conc = round(corrected_a260 * conv_factor, 2)

    return NanoDropPurityResult(
        a260=a260,
        a280=a280,
        a230=a230,
        sample_type=s_type.upper(),
        a260_a280_ratio=r280,
        a260_a230_ratio=r230,
        purity_status=purity_status,
        protein_contamination=prot_contam,
        salt_or_solvent_contamination=salt_contam,
        phenol_contamination_risk=phenol_risk,
        corrected_a260=corrected_a260,
        corrected_concentration_ng_ul=corrected_conc,
        diagnostic_feedback=feedback,
    )
