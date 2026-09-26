"""Fluorophore modifications, fluorescent oligonucleotide/protein labeling, and Degree of Labeling (DOL)."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from .molecular_weight import MolecularWeightResult

@dataclass(frozen=True)
class Fluorophore:
    name: str
    common_name: str
    added_mw: float
    added_monoisotopic: float
    excitation_max_nm: int
    emission_max_nm: int
    extinction_coeff_m_cm: int
    cf260: float  # Correction factor at 260 nm (A260_dye / Amax_dye)
    cf280: float  # Correction factor at 280 nm (A280_dye / Amax_dye)
    color_description: str

FLUOROPHORE_DATABASE: Dict[str, Fluorophore] = {
    "FAM": Fluorophore("6-FAM", "FAM", 537.5, 537.11, 495, 520, 75000, 0.30, 0.17, "Green"),
    "TET": Fluorophore("TET", "TET", 675.3, 674.96, 522, 539, 73000, 0.58, 0.20, "Yellow-Green"),
    "HEX": Fluorophore("HEX", "HEX", 744.1, 743.88, 535, 556, 73000, 0.30, 0.16, "Yellow-Orange"),
    "CY3": Fluorophore("Cy3", "Cyanine 3", 767.0, 766.36, 550, 570, 150000, 0.08, 0.05, "Orange-Red"),
    "CY5": Fluorophore("Cy5", "Cyanine 5", 793.0, 792.38, 650, 670, 250000, 0.05, 0.05, "Far-Red"),
    "ALEXA488": Fluorophore("Alexa Fluor 488", "AF488", 643.4, 642.99, 495, 519, 73000, 0.30, 0.11, "Bright Green"),
    "ALEXA546": Fluorophore("Alexa Fluor 546", "AF546", 1079.0, 1078.20, 556, 573, 112000, 0.21, 0.12, "Orange"),
    "ALEXA594": Fluorophore("Alexa Fluor 594", "AF594", 820.0, 819.12, 590, 617, 92000, 0.43, 0.56, "Red"),
    "ALEXA647": Fluorophore("Alexa Fluor 647", "AF647", 1250.0, 1249.20, 650, 665, 270000, 0.03, 0.03, "Far-Red"),
    "TEXAS_RED": Fluorophore("Texas Red-X", "Texas Red", 816.9, 816.28, 596, 620, 85000, 0.23, 0.18, "Deep Red"),
    "TAMRA": Fluorophore("TAMRA", "TAMRA", 527.5, 527.20, 557, 583, 65000, 0.32, 0.36, "Rose"),
    "ROX": Fluorophore("ROX", "ROX", 635.7, 635.26, 588, 608, 82000, 0.27, 0.30, "Red-Orange"),
    "ATTO488": Fluorophore("ATTO 488", "ATTO 488", 804.0, 803.22, 501, 523, 90000, 0.24, 0.10, "Green"),
    "ATTO647N": Fluorophore("ATTO 647N", "ATTO 647N", 843.5, 842.43, 644, 669, 150000, 0.06, 0.05, "Far-Red"),
    "BHQ1": Fluorophore("Black Hole Quencher 1", "BHQ-1", 518.5, 518.20, 534, 0, 34000, 0.35, 0.25, "Dark Quencher"),
    "BHQ2": Fluorophore("Black Hole Quencher 2", "BHQ-2", 562.6, 562.19, 579, 0, 38000, 0.28, 0.22, "Dark Quencher"),
}

@dataclass(frozen=True)
class LabeledMoleculeResult:
    original_sequence: str
    original_mw: float
    total_modified_mw: float
    total_modified_monoisotopic: float
    modifications: List[str]
    total_added_mw: float
    primary_fluorophore: Optional[Fluorophore]
    cf260: float
    cf280: float

@dataclass(frozen=True)
class DegreeOfLabelingResult:
    molecule_type: str
    fluorophore_name: str
    absorbance_max_dye: float
    absorbance_corrected_biomolecule: float
    biomolecule_concentration_um: float
    dye_concentration_um: float
    degree_of_labeling: float
    labeling_efficiency_percent: float
    interpretation: str

def get_fluorophore(name: str) -> Fluorophore:
    """Retrieve fluorophore metadata by common name or identifier."""
    key = name.upper().replace("-", "").replace(" ", "").replace("_", "")
    for k, v in FLUOROPHORE_DATABASE.items():
        if k == key or key in v.common_name.upper().replace("-", "").replace(" ", ""):
            return v
    raise KeyError(f"Fluorophore '{name}' not found. Available: {list(FLUOROPHORE_DATABASE.keys())}")

def apply_fluorophore_modification(
    base_result: MolecularWeightResult,
    modifications: List[str],
) -> LabeledMoleculeResult:
    """Apply one or more fluorophores/quenchers to an oligonucleotide or protein."""
    added_mw = 0.0
    added_mono = 0.0
    primary_fl: Optional[Fluorophore] = None
    applied_names: List[str] = []

    for mod in modifications:
        fl = get_fluorophore(mod)
        applied_names.append(fl.name)
        added_mw += fl.added_mw
        added_mono += fl.added_monoisotopic
        if primary_fl is None and fl.emission_max_nm > 0:
            primary_fl = fl

    if primary_fl is None and applied_names:
        primary_fl = get_fluorophore(modifications[0])

    tot_avg = base_result.average_mw + added_mw
    tot_mono = base_result.monoisotopic_mw + added_mono

    return LabeledMoleculeResult(
        original_sequence=base_result.sequence,
        original_mw=base_result.average_mw,
        total_modified_mw=round(tot_avg, 2),
        total_modified_monoisotopic=round(tot_mono, 4),
        modifications=applied_names,
        total_added_mw=round(added_mw, 2),
        primary_fluorophore=primary_fl,
        cf260=primary_fl.cf260 if primary_fl else 0.0,
        cf280=primary_fl.cf280 if primary_fl else 0.0,
    )

def calculate_degree_of_labeling(
    absorbance_max_dye: float,
    absorbance_280: Optional[float] = None,
    absorbance_260: Optional[float] = None,
    fluorophore_name: str = "FAM",
    protein_extinction_coeff: Optional[float] = None,
    oligo_extinction_coeff: Optional[float] = None,
    pathlength_cm: float = 1.0,
) -> DegreeOfLabelingResult:
    """Calculate the Degree of Labeling (DOL) - moles of dye per mole of protein or nucleic acid."""
    if absorbance_max_dye <= 0:
        raise ValueError("Dye absorbance at maximum wavelength must be greater than zero.")
    if pathlength_cm <= 0:
        raise ValueError("Pathlength must be strictly positive.")
    fl = get_fluorophore(fluorophore_name)

    if protein_extinction_coeff is not None and absorbance_280 is not None:
        mol_type = "Protein"
        # A_prot_corrected = A280 - (A_max * CF280)
        dye_contrib = absorbance_max_dye * fl.cf280
        a_corr = absorbance_280 - dye_contrib
        if a_corr <= 0:
            raise ValueError(
                f"Over-correction error: dye absorbance contribution at 280 nm ({dye_contrib:.4f} AU) "
                f"exceeds total measured A280 ({absorbance_280:.4f} AU). "
                f"Sample contains excess unincorporated free dye or protein concentration is below detection limit."
            )
        c_biomol = a_corr / (protein_extinction_coeff * pathlength_cm)
    elif oligo_extinction_coeff is not None and absorbance_260 is not None:
        mol_type = "Oligonucleotide"
        # A_oligo_corrected = A260 - (A_max * CF260)
        dye_contrib = absorbance_max_dye * fl.cf260
        a_corr = absorbance_260 - dye_contrib
        if a_corr <= 0:
            raise ValueError(
                f"Over-correction error: dye absorbance contribution at 260 nm ({dye_contrib:.4f} AU) "
                f"exceeds total measured A260 ({absorbance_260:.4f} AU). "
                f"Sample contains excess unincorporated free dye or oligonucleotide concentration is below detection limit."
            )
        c_biomol = a_corr / (oligo_extinction_coeff * pathlength_cm)
    else:
        raise ValueError("Must provide either (absorbance_280 and protein_extinction_coeff) or (absorbance_260 and oligo_extinction_coeff).")

    # c_dye = A_max / (e_dye * pathlength)
    c_dye = absorbance_max_dye / (fl.extinction_coeff_m_cm * pathlength_cm)
    dol = c_dye / c_biomol if c_biomol > 0 else 0.0
    eff_pct = min(100.0, dol * 100.0)

    if dol < 0.6:
        interp = "Under-labeled: low fluorescence signal expected."
    elif 0.8 <= dol <= 1.2:
        interp = "Optimally labeled: stoichiometric ~1:1 dye-to-molecule ratio."
    elif 1.2 < dol <= 2.5:
        interp = "Multi-labeled: multiple dyes incorporated per biomolecule."
    else:
        interp = "High labeling density: risk of self-quenching or precipitation."

    return DegreeOfLabelingResult(
        molecule_type=mol_type,
        fluorophore_name=fl.name,
        absorbance_max_dye=absorbance_max_dye,
        absorbance_corrected_biomolecule=round(a_corr, 4),
        biomolecule_concentration_um=round(c_biomol * 1e6, 2),
        dye_concentration_um=round(c_dye * 1e6, 2),
        degree_of_labeling=round(dol, 3),
        labeling_efficiency_percent=round(eff_pct, 1),
        interpretation=interp,
    )
