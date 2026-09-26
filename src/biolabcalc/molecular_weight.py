"""Molecular weight calculations and stoichiometry conversions for DNA, RNA, and proteins."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Literal
from .seq_utils import clean_sequence, reverse_complement, count_bases

# Average molecular weights for nucleotide residues in a polymer (g/mol)
DNA_RESIDUE_MW: Dict[str, float] = {
    "A": 313.21,
    "C": 289.18,
    "G": 329.21,
    "T": 304.20,
}

RNA_RESIDUE_MW: Dict[str, float] = {
    "A": 329.21,
    "C": 305.18,
    "G": 345.21,
    "U": 306.17,
}

# Monoisotopic molecular weights for nucleotide residues (g/mol)
DNA_RESIDUE_MONOISOTOPIC: Dict[str, float] = {
    "A": 313.0576,
    "C": 289.0464,
    "G": 329.0525,
    "T": 304.0460,
}

RNA_RESIDUE_MONOISOTOPIC: Dict[str, float] = {
    "A": 329.0525,
    "C": 305.0413,
    "G": 345.0474,
    "U": 306.0253,
}

# Protein standard amino acid residue weights (average g/mol)
AMINO_ACID_MW: Dict[str, float] = {
    "A": 71.08,   "R": 156.19,  "N": 114.10,  "D": 115.09,
    "C": 103.14,  "E": 129.12,  "Q": 128.13,  "G": 57.05,
    "H": 137.14,  "I": 131.17,  "L": 131.17,  "K": 128.17,
    "M": 131.19,  "F": 147.18,  "P": 97.12,   "S": 87.08,
    "T": 101.11,  "W": 186.21,  "Y": 163.18,  "V": 99.13,
}

# Monoisotopic residue weights for amino acids (g/mol)
AMINO_ACID_MONOISOTOPIC: Dict[str, float] = {
    "A": 71.03711,   "R": 156.10111, "N": 114.04293, "D": 115.02694,
    "C": 103.00919,  "E": 129.04259, "Q": 128.05858, "G": 57.02146,
    "H": 137.05891,  "I": 131.09463, "L": 131.09463, "K": 128.09496,
    "M": 131.04049,  "F": 147.06841, "P": 97.05276,  "S": 87.03203,
    "T": 101.04768,  "W": 186.07931, "Y": 163.06333, "V": 99.06841,
}

AVOGADRO: float = 6.02214076e23


@dataclass(frozen=True)
class MolecularWeightResult:
    sequence: str
    seq_type: str
    length: int
    average_mw: float
    monoisotopic_mw: float
    base_counts: Dict[str, int]
    gc_content: float
    end_5: str = "hydroxyl"
    end_3: str = "hydroxyl"
    backbone: str = "monophosphate"
    formula_delta: str = ""


def calculate_dna_mw(
    seq: str,
    double_stranded: bool = False,
    end_5: Literal["hydroxyl", "monophosphate", "triphosphate"] = "hydroxyl",
    circular: bool = False,
) -> MolecularWeightResult:
    """Calculate the molecular weight of ssDNA or dsDNA.

    Parameters
    ----------
    seq : str
        DNA sequence (5' to 3').
    double_stranded : bool
        If True, calculates MW of double-stranded duplex.
    end_5 : {'hydroxyl', 'monophosphate', 'triphosphate'}
        Phosphorylation state at the 5' terminus.
    circular : bool
        If True, treats as circular DNA without terminal free ends.
    """
    clean_seq = clean_sequence(seq).replace("U", "T")
    counts = count_bases(clean_seq)
    length = len(clean_seq)
    if length == 0:
        return MolecularWeightResult("", "DNA", 0, 0.0, 0.0, {}, 0.0)

    avg_sum = sum(DNA_RESIDUE_MW.get(b, 308.9) * n for b, n in counts.items())
    mono_sum = sum(DNA_RESIDUE_MONOISOTOPIC.get(b, 308.8) * n for b, n in counts.items())

    if circular:
        strand_avg = avg_sum
        strand_mono = mono_sum
    else:
        if end_5 == "hydroxyl":
            adj_avg = -61.96
            adj_mono = -61.9558
        elif end_5 == "monophosphate":
            adj_avg = 18.02
            adj_mono = 18.0106
        elif end_5 == "triphosphate":
            adj_avg = 177.98
            adj_mono = 177.9430
        else:
            adj_avg = -61.96
            adj_mono = -61.9558

        strand_avg = avg_sum + adj_avg
        strand_mono = mono_sum + adj_mono

    if double_stranded:
        rc_seq = reverse_complement(clean_seq, seq_type="dna")
        rc_result = calculate_dna_mw(rc_seq, double_stranded=False, end_5=end_5, circular=circular)
        total_avg = strand_avg + rc_result.average_mw
        total_mono = strand_mono + rc_result.monoisotopic_mw
        all_counts = {
            "A": counts.get("A", 0) + rc_result.base_counts.get("A", 0),
            "C": counts.get("C", 0) + rc_result.base_counts.get("C", 0),
            "G": counts.get("G", 0) + rc_result.base_counts.get("G", 0),
            "T": counts.get("T", 0) + rc_result.base_counts.get("T", 0),
        }
        gc = round(((all_counts["G"] + all_counts["C"]) / (length * 2)) * 100.0, 2)
        return MolecularWeightResult(clean_seq, "dsDNA", length, round(total_avg, 2), round(total_mono, 4), all_counts, gc)

    gc = round(((counts.get("G", 0) + counts.get("C", 0)) / length) * 100.0, 2)
    return MolecularWeightResult(clean_seq, "ssDNA", length, round(strand_avg, 2), round(strand_mono, 4), counts, gc)


def calculate_rna_mw(
    seq: str,
    end_5: Literal["triphosphate", "monophosphate", "hydroxyl", "cap0", "cap1"] = "triphosphate",
    end_3: Literal["hydroxyl", "monophosphate", "diphosphate", "triphosphate", "cyclic_phosphate"] = "hydroxyl",
    backbone: Literal["monophosphate", "phosphorothioate"] = "monophosphate",
    phosphorothioate_count: Optional[int] = None,
) -> MolecularWeightResult:
    """Calculate the molecular weight of RNA with customizable 5' end, 3' end, and backbone chemistry.

    Supports native IVT transcripts (5'-triphosphate, 3'-hydroxyl), chemically synthesized
    oligos (5'-hydroxyl, 3'-hydroxyl), 3'-triphosphorylated RNAs (3'-triphosphate),
    monophosphate backbones, and phosphorothioate backbones.

    Parameters
    ----------
    seq : str
        RNA sequence (5' to 3').
    end_5 : {'triphosphate', 'monophosphate', 'hydroxyl', 'cap0', 'cap1'}
        5' terminal phosphorylation state. Default: 'triphosphate'.
    end_3 : {'hydroxyl', 'monophosphate', 'diphosphate', 'triphosphate', 'cyclic_phosphate'}
        3' terminal phosphorylation state. Default: 'hydroxyl'.
        Triphosphate ('triphosphate') adds +239.94 Da to the 3' terminus.
    backbone : {'monophosphate', 'phosphorothioate'}
        Internucleotide linkage chemistry. Default: 'monophosphate' (standard diester).
        Phosphorothioate replaces a non-bridging oxygen with sulfur (+16.07 Da per linkage).
    phosphorothioate_count : int, optional
        Specific count of phosphorothioate linkages (defaults to all length-1 if backbone='phosphorothioate').
    """
    clean_seq = clean_sequence(seq).replace("T", "U")
    counts = count_bases(clean_seq)
    length = len(clean_seq)
    if length == 0:
        return MolecularWeightResult("", "RNA", 0, 0.0, 0.0, {}, 0.0, end_5=end_5, end_3=end_3, backbone=backbone)

    avg_sum = sum(RNA_RESIDUE_MW.get(b, 321.4) * n for b, n in counts.items())
    mono_sum = sum(RNA_RESIDUE_MONOISOTOPIC.get(b, 321.3) * n for b, n in counts.items())

    # Baseline adjustment: 5'-hydroxyl and 3'-hydroxyl
    adj_avg = -61.96
    adj_mono = -61.9558

    # 5' end adjustment relative to 5'-hydroxyl
    e5_key = end_5.lower()
    if e5_key == "triphosphate":
        adj_avg += 239.94
        adj_mono += 239.8988
    elif e5_key == "monophosphate":
        adj_avg += 79.98
        adj_mono += 79.9663
    elif e5_key == "cap0":
        adj_avg += 749.24
        adj_mono += 749.1245
    elif e5_key == "cap1":
        adj_avg += 763.26
        adj_mono += 763.1402
    # e5_key == "hydroxyl" adds 0.0

    # 3' end adjustment relative to 3'-hydroxyl
    e3_key = end_3.lower()
    if e3_key == "triphosphate":
        adj_avg += 239.94
        adj_mono += 239.8990
    elif e3_key == "diphosphate":
        adj_avg += 159.96
        adj_mono += 159.9327
    elif e3_key == "monophosphate":
        adj_avg += 79.98
        adj_mono += 79.9663
    elif e3_key == "cyclic_phosphate":
        adj_avg += 61.96
        adj_mono += 61.9558
    # e3_key == "hydroxyl" adds 0.0

    # Backbone adjustment (monophosphate diester vs phosphorothioate)
    bb_key = backbone.lower()
    ps_count = 0
    if bb_key == "phosphorothioate" or (phosphorothioate_count is not None and phosphorothioate_count > 0):
        ps_count = phosphorothioate_count if phosphorothioate_count is not None else max(0, length - 1)
        adj_avg += ps_count * 16.066
        adj_mono += ps_count * 15.9772

    total_avg = avg_sum + adj_avg
    total_mono = mono_sum + adj_mono
    gc = round(((counts.get("G", 0) + counts.get("C", 0)) / length) * 100.0, 2)

    delta_notes = []
    if e5_key != "hydroxyl":
        delta_notes.append(f"5'-{end_5}")
    if e3_key != "hydroxyl":
        delta_notes.append(f"3'-{end_3}")
    if ps_count > 0:
        delta_notes.append(f"{ps_count} PS linkages")
    formula_delta = ", ".join(delta_notes) if delta_notes else "standard hydroxyl ends"

    return MolecularWeightResult(
        sequence=clean_seq,
        seq_type="RNA",
        length=length,
        average_mw=round(total_avg, 2),
        monoisotopic_mw=round(total_mono, 4),
        base_counts=counts,
        gc_content=gc,
        end_5=end_5,
        end_3=end_3,
        backbone=f"phosphorothioate ({ps_count} PS)" if ps_count > 0 else "monophosphate",
        formula_delta=formula_delta,
    )


def calculate_protein_mw(seq: str, oxidized_cysteines: int = 0) -> MolecularWeightResult:
    """Calculate molecular weight of a protein or peptide sequence.

    Parameters
    ----------
    seq : str
        One-letter amino acid sequence.
    oxidized_cysteines : int
        Number of cysteines involved in disulfide bonds (each pair loses 2.016 g/mol).
    """
    # Strip termination stop codon symbols (*) which have zero mass
    clean_seq = clean_sequence(seq).replace("*", "")
    counts = count_bases(clean_seq)
    length = len(clean_seq)
    if length == 0:
        return MolecularWeightResult("", "Protein", 0, 0.0, 0.0, {}, 0.0)

    avg_sum = sum(AMINO_ACID_MW.get(aa, 110.0) * n for aa, n in counts.items()) + 18.015
    mono_sum = sum(AMINO_ACID_MONOISOTOPIC.get(aa, 110.0) * n for aa, n in counts.items()) + 18.01056

    if oxidized_cysteines > 0:
        disulfide_bonds = oxidized_cysteines // 2
        avg_sum -= disulfide_bonds * 2.016
        mono_sum -= disulfide_bonds * 2.01565

    return MolecularWeightResult(clean_seq, "Protein", length, round(avg_sum, 2), round(mono_sum, 4), counts, 0.0)


MASS_TO_GRAMS: Dict[str, float] = {
    "g": 1.0,
    "mg": 1e-3,
    "ug": 1e-6,
    "µg": 1e-6,
    "ng": 1e-9,
    "pg": 1e-12,
    "fg": 1e-15,
}

MOLES_TO_BASE: Dict[str, float] = {
    "mol": 1.0,
    "mmol": 1e-3,
    "umol": 1e-6,
    "µmol": 1e-6,
    "nmol": 1e-9,
    "pmol": 1e-12,
    "fmol": 1e-15,
}


def mass_to_moles(mass_val: float, mass_unit: str, mw: float) -> tuple[float, str]:
    if mw <= 0:
        raise ValueError("Molecular weight must be positive.")
    unit_key = mass_unit.lower().strip()
    if unit_key not in MASS_TO_GRAMS:
        raise ValueError(f"Unsupported mass unit '{mass_unit}'. Supported: {list(MASS_TO_GRAMS.keys())}")
    grams = mass_val * MASS_TO_GRAMS[unit_key]
    base_moles = grams / mw

    if base_moles < 1e-12 * 0.9999:
        return base_moles * 1e15, "fmol"
    elif base_moles < 1e-9 * 0.9999:
        return base_moles * 1e12, "pmol"
    elif base_moles < 1e-6 * 0.9999:
        return base_moles * 1e9, "nmol"
    elif base_moles < 1e-3 * 0.9999:
        return base_moles * 1e6, "µmol"
    elif base_moles < 1.0 * 0.9999:
        return base_moles * 1e3, "mmol"
    return base_moles, "mol"


def moles_to_mass(mol_val: float, mol_unit: str, mw: float) -> tuple[float, str]:
    if mw <= 0:
        raise ValueError("Molecular weight must be positive.")
    unit_key = mol_unit.lower().strip()
    if unit_key not in MOLES_TO_BASE:
        raise ValueError(f"Unsupported molar unit '{mol_unit}'. Supported: {list(MOLES_TO_BASE.keys())}")
    base_moles = mol_val * MOLES_TO_BASE[unit_key]
    grams = base_moles * mw

    if grams < 1e-9 * 0.9999:
        return grams * 1e12, "pg"
    elif grams < 1e-6 * 0.9999:
        return grams * 1e9, "ng"
    elif grams < 1e-3 * 0.9999:
        return grams * 1e6, "µg"
    elif grams < 1.0 * 0.9999:
        return grams * 1e3, "mg"
    return grams, "g"


def mass_to_copy_number(mass_val: float, mass_unit: str, mw: float) -> float:
    unit_key = mass_unit.lower().strip()
    if unit_key not in MASS_TO_GRAMS:
        raise ValueError(f"Unsupported mass unit '{mass_unit}'. Supported: {list(MASS_TO_GRAMS.keys())}")
    grams = mass_val * MASS_TO_GRAMS[unit_key]
    moles = grams / mw
    return moles * AVOGADRO


def copy_number_to_mass(copies: float, mw: float, target_unit: str = "ng") -> float:
    moles = copies / AVOGADRO
    grams = moles * mw
    factor = MASS_TO_GRAMS.get(target_unit.lower(), 1e-9)
    return grams / factor


def concentration_to_molarity(conc_val: float, conc_unit: str, mw: float) -> tuple[float, str]:
    c_unit = conc_unit.lower().replace("µ", "u")
    if c_unit in ("ng/ul", "ug/ml", "mg/l"):
        g_per_l = conc_val * 1e-3
    elif c_unit in ("mg/ml", "ug/ul", "g/l"):
        g_per_l = conc_val * 1.0
    elif c_unit in ("ng/ml",):
        g_per_l = conc_val * 1e-6
    elif c_unit in ("g/ml", "kg/l"):
        g_per_l = conc_val * 1e3
    else:
        raise ValueError(f"Unsupported concentration unit '{conc_unit}'. Supported: ng/ul, ug/ml, mg/l, mg/ml, ug/ul, g/l, ng/ml, g/ml.")

    molar = g_per_l / mw
    if molar < 1e-9:
        return molar * 1e12, "pM"
    elif molar < 1e-6:
        return molar * 1e9, "nM"
    elif molar < 1e-3:
        return molar * 1e6, "µM"
    elif molar < 1.0:
        return molar * 1e3, "mM"
    return molar, "M"
