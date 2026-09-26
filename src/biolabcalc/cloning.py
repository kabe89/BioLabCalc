"""Molecular cloning utilities: restriction enzyme digests, buffer compatibility, ligation stoichiometry, and Gibson assembly."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

@dataclass(frozen=True)
class RestrictionEnzyme:
    name: str
    recognition_site: str
    cut_type: str  # "5' overhang", "3' overhang", "blunt"
    overhang_sequence: str
    incubation_temp_celsius: int
    heat_inactivation: str  # e.g. "65°C for 20 min" or "None"
    methylation_sensitivity: str
    standard_buffer: str
    buffer_activity_rcutsmart: int  # percentage
    notes: str

ENZYME_DATABASE: Dict[str, RestrictionEnzyme] = {
    "ECORI": RestrictionEnzyme("EcoRI", "G^AATTC", "5' overhang", "AATT", 37, "65°C for 20 min", "None", "rCutSmart", 100, "High fidelity High-Fidelity versions available."),
    "BAMHI": RestrictionEnzyme("BamHI", "G^GATCC", "5' overhang", "GATC", 37, "None (column clean-up required)", "None", "rCutSmart", 100, "High glycerol (>5%) causes star activity."),
    "HINDIII": RestrictionEnzyme("HindIII", "A^AGCTT", "5' overhang", "AGCT", 37, "80°C for 20 min", "None", "rCutSmart", 100, "Classic 5' overhang cloning enzyme."),
    "XHOI": RestrictionEnzyme("XhoI", "C^TCGAG", "5' overhang", "TCGA", 37, "65°C for 20 min", "None", "rCutSmart", 100, "Compatible with SalI overhangs."),
    "NDEI": RestrictionEnzyme("NdeI", "CA^TATG", "5' overhang", "TA", 37, "65°C for 20 min", "None", "rCutSmart", 100, "Includes ATG start codon in recognition site."),
    "NOTI": RestrictionEnzyme("NotI", "GC^GGCCGC", "5' overhang", "GGCC", 37, "65°C for 20 min", "CpG methylation sensitive", "rCutSmart", 100, "Rare 8-base cutter."),
    "SALI": RestrictionEnzyme("SalI", "G^TCGAC", "5' overhang", "TCGA", 37, "65°C for 20 min", "CpG methylation sensitive", "rCutSmart", 100, "Requires BSA or rCutSmart."),
    "NHEI": RestrictionEnzyme("NheI", "G^CTAGC", "5' overhang", "CTAG", 37, "65°C for 20 min", "None", "rCutSmart", 100, "Compatible with SpeI and XbaI."),
    "BGLII": RestrictionEnzyme("BglII", "A^GATCT", "5' overhang", "GATC", 37, "None (column clean-up required)", "dam methylation sensitive", "rCutSmart", 100, "Compatible with BamHI overhangs."),
    "DPNI": RestrictionEnzyme("DpnI", "GA^TC", "blunt", "", 37, "80°C for 20 min", "Requires Dam-methylation (Gm6ATC)", "rCutSmart", 100, "Selectively digests dam-methylated parent plasmid in site-directed mutagenesis."),
    "ECORV": RestrictionEnzyme("EcoRV", "GAT^ATC", "blunt", "", 37, "80°C for 20 min", "None", "rCutSmart", 100, "Blunt cutter."),
    "SMAI": RestrictionEnzyme("SmaI", "CCC^GGG", "blunt", "", 25, "65°C for 20 min", "CpG sensitive", "rCutSmart", 100, "Incubate at 25°C, not 37°C."),
    "XBAI": RestrictionEnzyme("XbaI", "T^CTAGA", "5' overhang", "CTAG", 37, "65°C for 20 min", "dam sensitive (if overlapping)", "rCutSmart", 100, "Check dam methylation when flanked by TC."),
    "BSAI": RestrictionEnzyme("BsaI-HFv2", "GGTCTC(1/5)", "5' overhang", "NNNN", 37, "80°C for 20 min", "None", "rCutSmart", 100, "Type IIS enzyme; primary choice for Golden Gate Assembly."),
    "BSAIHFV2": RestrictionEnzyme("BsaI-HFv2", "GGTCTC(1/5)", "5' overhang", "NNNN", 37, "80°C for 20 min", "None", "rCutSmart", 100, "Type IIS enzyme; primary choice for Golden Gate Assembly."),
    "BSMBI": RestrictionEnzyme("BsmBI-v2", "CGTCTC(1/5)", "5' overhang", "NNNN", 42, "80°C for 20 min", "None", "NEBuffer r3.1", 100, "Type IIS enzyme; incubate at 42°C for Golden Gate digestion phase."),
    "BSMBIV2": RestrictionEnzyme("BsmBI-v2", "CGTCTC(1/5)", "5' overhang", "NNNN", 42, "80°C for 20 min", "None", "NEBuffer r3.1", 100, "Type IIS enzyme; incubate at 42°C for Golden Gate digestion phase."),
    "ESP3I": RestrictionEnzyme("Esp3I", "CGTCTC(1/5)", "5' overhang", "NNNN", 37, "65°C for 20 min", "dam/dcm sensitive", "rCutSmart", 100, "Type IIS enzyme; isoschizomer of BsmBI."),
    "BBSI": RestrictionEnzyme("BbsI-HF", "GAAGAC(2/6)", "5' overhang", "NNNN", 37, "65°C for 20 min", "None", "rCutSmart", 100, "Type IIS enzyme; popular for mammalian CRISPR sgRNA cloning."),
    "BBSIHF": RestrictionEnzyme("BbsI-HF", "GAAGAC(2/6)", "5' overhang", "NNNN", 37, "65°C for 20 min", "None", "rCutSmart", 100, "Type IIS enzyme; popular for mammalian CRISPR sgRNA cloning."),
    "PAQCI": RestrictionEnzyme("PaqCI", "CACCTGC(4/8)", "5' overhang", "NNNN", 37, "65°C for 20 min", "None", "rCutSmart", 100, "Type IIS 7-base cutter with PaqCI activator."),
    "SAPI": RestrictionEnzyme("SapI", "GCTCTTC(1/4)", "5' overhang", "NNN", 37, "65°C for 20 min", "CpG sensitive", "rCutSmart", 100, "Type IIS enzyme with 3-bp overhang."),
}

def get_restriction_enzyme(name: str) -> RestrictionEnzyme:
    """Look up restriction enzyme details."""
    key = name.upper().replace("-", "").replace(" ", "").replace("_", "")
    if key in ENZYME_DATABASE:
        return ENZYME_DATABASE[key]
    for k, v in ENZYME_DATABASE.items():
        if key in v.name.upper():
            return v
    raise KeyError(f"Enzyme '{name}' not found. Available: {list(ENZYME_DATABASE.keys())}")

@dataclass(frozen=True)
class DigestSetupResult:
    enzyme_1: RestrictionEnzyme
    enzyme_2: Optional[RestrictionEnzyme]
    dna_mass_ug: float
    reaction_volume_ul: float
    recommended_buffer: str
    incubation_temp_celsius: int
    incubation_time_min: int
    heat_inactivation: str
    reagent_volumes: Dict[str, float]
    star_activity_warning: bool
    notes: List[str]

@dataclass(frozen=True)
class LigationSetupResult:
    vector_length_bp: int
    insert_length_bp: int
    vector_mass_ng: float
    insert_mass_ng: float
    molar_ratio_insert_to_vector: float
    vector_pmol: float
    insert_pmol: float
    reagent_volumes: Dict[str, float]
    incubation_guidelines: str

@dataclass(frozen=True)
class GibsonAssemblyResult:
    vector_length_bp: int
    insert_lengths_bp: List[int]
    vector_mass_ng: float
    insert_masses_ng: List[float]
    total_dna_pmol: float
    reagent_volumes: Dict[str, float]
    incubation_protocol: str

def plan_restriction_digest(
    dna_mass_ug: float,
    reaction_volume_ul: float = 50.0,
    enzyme_1: str = "EcoRI",
    enzyme_2: Optional[str] = None,
    dna_conc_ng_ul: Optional[float] = None,
    units_per_ug: float = 5.0,
) -> DigestSetupResult:
    """Plan a single or double restriction enzyme digestion setup with volume calculations and buffer compatibility."""
    if dna_mass_ug <= 0 or reaction_volume_ul <= 0:
        raise ValueError("DNA mass and reaction volume must be positive.")

    e1 = get_restriction_enzyme(enzyme_1)
    e2 = get_restriction_enzyme(enzyme_2) if enzyme_2 else None

    # Determine incubation temp (e.g. SmaI needs 25°C, others 37°C)
    if e2 and e1.incubation_temp_celsius != e2.incubation_temp_celsius:
        inc_temp = e1.incubation_temp_celsius
        temp_note = f"Sequential digest required: {e1.name} at {e1.incubation_temp_celsius}°C, then {e2.name} at {e2.incubation_temp_celsius}°C."
    else:
        inc_temp = e1.incubation_temp_celsius
        temp_note = f"Incubate at {inc_temp}°C for 60 minutes."

    # Heat inactivation
    if e2:
        if "None" in e1.heat_inactivation or "None" in e2.heat_inactivation:
            heat_inact = "Column clean-up or gel extraction required (one or both enzymes cannot be heat-inactivated)."
        else:
            heat_inact = f"{e1.name}: {e1.heat_inactivation} | {e2.name}: {e2.heat_inactivation}"
    else:
        heat_inact = e1.heat_inactivation

    # Calculate volumes
    buffer_vol = round(reaction_volume_ul / 10.0, 2)  # 10X buffer
    dna_vol = round((dna_mass_ug * 1000.0) / dna_conc_ng_ul, 2) if (dna_conc_ng_ul and dna_conc_ng_ul > 0) else round(dna_mass_ug * 10.0, 2)

    # Standard commercial enzyme concentration is 10-20 U/µL. 1 µL per reaction is standard safe volume
    e1_vol = 1.0
    e2_vol = 1.0 if e2 else 0.0

    total_enzyme_vol = e1_vol + e2_vol
    solutes = dna_vol + buffer_vol + total_enzyme_vol
    water_vol = round(reaction_volume_ul - solutes, 2)
    if water_vol < 0:
        raise ValueError(
            f"Volume overflow: Combined reagents ({solutes:.1f} µL) exceed reaction volume ({reaction_volume_ul:.1f} µL). "
            f"Concentrate DNA or increase reaction volume."
        )

    # Glycerol check: enzymes stored in 50% glycerol. Glycerol in reaction must not exceed 5% (i.e. enzyme vol <= 10% of rxn)
    max_enzyme_vol_allowed = reaction_volume_ul * 0.10
    star_warning = total_enzyme_vol > max_enzyme_vol_allowed

    notes = [temp_note]
    if e1.methylation_sensitivity != "None":
        notes.append(f"{e1.name}: {e1.methylation_sensitivity}")
    if e2 and e2.methylation_sensitivity != "None":
        notes.append(f"{e2.name}: {e2.methylation_sensitivity}")
    if star_warning:
        notes.append("WARNING: Enzyme volume exceeds 10% of reaction volume. Star activity risk due to high glycerol.")

    reagents = {
        "Nuclease-Free Water": max(0.0, water_vol),
        "10X rCutSmart Buffer": buffer_vol,
        "DNA Sample": dna_vol,
        f"{e1.name} (Enzyme 1)": e1_vol,
    }
    if e2:
        reagents[f"{e2.name} (Enzyme 2)"] = e2_vol

    return DigestSetupResult(
        enzyme_1=e1,
        enzyme_2=e2,
        dna_mass_ug=dna_mass_ug,
        reaction_volume_ul=reaction_volume_ul,
        recommended_buffer="1X rCutSmart Buffer",
        incubation_temp_celsius=inc_temp,
        incubation_time_min=60,
        heat_inactivation=heat_inact,
        reagent_volumes=reagents,
        star_activity_warning=star_warning,
        notes=notes,
    )

def calculate_ligation(
    vector_length_bp: int,
    insert_length_bp: int,
    vector_mass_ng: float = 50.0,
    molar_ratio: float = 3.0,
    vector_conc_ng_ul: Optional[float] = None,
    insert_conc_ng_ul: Optional[float] = None,
    reaction_volume_ul: float = 20.0,
) -> LigationSetupResult:
    """Calculate insert mass and reaction setup for sticky or blunt-end DNA ligation."""
    if vector_length_bp <= 0 or insert_length_bp <= 0 or vector_mass_ng <= 0:
        raise ValueError("Vector and insert dimensions and mass must be positive.")

    # Mass_insert = Mass_vector * (Length_insert / Length_vector) * Molar_Ratio
    insert_mass_ng = vector_mass_ng * (insert_length_bp / vector_length_bp) * molar_ratio

    # Moles calculation (dsDNA): mass_g / (len_bp * 617.96)
    vec_mw = vector_length_bp * 617.96 + 36.04
    ins_mw = insert_length_bp * 617.96 + 36.04
    vec_pmol = (vector_mass_ng * 1e-9 / vec_mw) * 1e12
    ins_pmol = (insert_mass_ng * 1e-9 / ins_mw) * 1e12

    # Pipetting volumes
    buf_vol = round(reaction_volume_ul / 10.0, 2)  # 10X T4 DNA Ligase Buffer (contains ATP)
    ligase_vol = 1.0  # 1 µL T4 DNA Ligase

    vec_vol = round(vector_mass_ng / vector_conc_ng_ul, 2) if (vector_conc_ng_ul and vector_conc_ng_ul > 0) else round(vector_mass_ng / 50.0, 2)
    ins_vol = round(insert_mass_ng / insert_conc_ng_ul, 2) if (insert_conc_ng_ul and insert_conc_ng_ul > 0) else round(insert_mass_ng / 25.0, 2)

    water_vol = round(reaction_volume_ul - (buf_vol + ligase_vol + vec_vol + ins_vol), 2)
    if water_vol < 0:
        water_vol = 0.0

    reagents = {
        "Nuclease-Free Water": max(0.0, water_vol),
        "10X T4 DNA Ligase Buffer": buf_vol,
        f"Digested Vector ({vector_mass_ng:.1f} ng)": vec_vol,
        f"Purified Insert ({insert_mass_ng:.1f} ng)": ins_vol,
        "T4 DNA Ligase (1 U/µL)": ligase_vol,
    }

    guidelines = (
        f"Incubate at 16°C overnight or 22°C (room temp) for 1-2 hours for sticky ends. "
        f"For blunt ends, incubate at 16°C overnight with 1 µL PEG 4000. Transform 2-5 µL into competent E. coli."
    )

    return LigationSetupResult(
        vector_length_bp=vector_length_bp,
        insert_length_bp=insert_length_bp,
        vector_mass_ng=round(vector_mass_ng, 1),
        insert_mass_ng=round(insert_mass_ng, 1),
        molar_ratio_insert_to_vector=molar_ratio,
        vector_pmol=round(vec_pmol, 3),
        insert_pmol=round(ins_pmol, 3),
        reagent_volumes=reagents,
        incubation_guidelines=guidelines,
    )

def calculate_gibson_assembly(
    vector_length_bp: int,
    insert_lengths_bp: List[int],
    vector_mass_ng: float = 100.0,
    molar_ratio: float = 2.0,
    vector_conc_ng_ul: Optional[float] = None,
    insert_concs_ng_ul: Optional[List[float]] = None,
    reaction_volume_ul: float = 20.0,
) -> GibsonAssemblyResult:
    """Calculate DNA fragment quantities and setup for isothermal Gibson Assembly / NEBuilder HiFi."""
    vec_mw = vector_length_bp * 617.96 + 36.04
    vec_pmol = (vector_mass_ng * 1e-9 / vec_mw) * 1e12

    insert_masses = []
    tot_pmol = vec_pmol

    for idx, ins_len in enumerate(insert_lengths_bp):
        ins_mw = ins_len * 617.96 + 36.04
        # Standard 2:1 ratio for 2-3 fragments, 1:1 for 4-6 fragments
        ins_mass = vector_mass_ng * (ins_len / vector_length_bp) * molar_ratio
        ins_pmol = (ins_mass * 1e-9 / ins_mw) * 1e12
        insert_masses.append(round(ins_mass, 1))
        tot_pmol += ins_pmol

    master_mix_vol = round(reaction_volume_ul / 2.0, 2)  # 2X Gibson Master Mix = 10 µL

    vec_vol = round(vector_mass_ng / vector_conc_ng_ul, 2) if (vector_conc_ng_ul and vector_conc_ng_ul > 0) else 2.0
    ins_vols = []
    for idx, imass in enumerate(insert_masses):
        c = insert_concs_ng_ul[idx] if (insert_concs_ng_ul and idx < len(insert_concs_ng_ul) and insert_concs_ng_ul[idx] > 0) else 50.0
        ins_vols.append(round(imass / c, 2))

    water_vol = round(reaction_volume_ul - (master_mix_vol + vec_vol + sum(ins_vols)), 2)

    reagents = {
        "2X Gibson Assembly Master Mix": master_mix_vol,
        "Nuclease-Free Water": max(0.0, water_vol),
        f"Linearized Vector ({vector_mass_ng:.1f} ng)": vec_vol,
    }
    for idx, (imass, ivol) in enumerate(zip(insert_masses, ins_vols), 1):
        reagents[f"Insert #{idx} ({imass:.1f} ng)"] = ivol

    protocol = (
        f"Incubate at 50°C for {'15 minutes' if len(insert_lengths_bp) <= 2 else '60 minutes'}. "
        f"Keep on ice, then transform 2 µL into high-efficiency competent cells."
    )
    if tot_pmol < 0.02:
        protocol += f" [Notice: Total DNA ({tot_pmol:.3f} pmol) is below recommended 0.02–0.5 pmol range; efficiency may be reduced.]"
    elif tot_pmol > 0.50:
        protocol += f" [Notice: Total DNA ({tot_pmol:.3f} pmol) exceeds recommended 0.50 pmol ceiling; risk of inhibitory carryover.]"

    return GibsonAssemblyResult(
        vector_length_bp=vector_length_bp,
        insert_lengths_bp=insert_lengths_bp,
        vector_mass_ng=round(vector_mass_ng, 1),
        insert_masses_ng=insert_masses,
        total_dna_pmol=round(tot_pmol, 3),
        reagent_volumes=reagents,
        incubation_protocol=protocol,
    )


def are_overhangs_compatible(enzyme_1: str, enzyme_2: str) -> Tuple[bool, str]:
    """Determine whether two restriction enzymes produce compatible cohesive (or blunt) ends."""
    e1 = get_restriction_enzyme(enzyme_1)
    e2 = get_restriction_enzyme(enzyme_2)

    if e1.cut_type == "blunt" and e2.cut_type == "blunt":
        return True, "Both enzymes generate blunt ends; universally compatible for blunt-end ligation."

    if e1.cut_type != e2.cut_type:
        return False, f"Incompatible cut types: {e1.name} generates {e1.cut_type}, whereas {e2.name} generates {e2.cut_type}."

    if e1.overhang_sequence == e2.overhang_sequence:
        return True, f"Compatible cohesive ends: both generate identical {e1.cut_type} ({e1.overhang_sequence})."

    # Complementary overhang check for non-palindromic or staggered cohesive ends
    from .seq_utils import reverse_complement
    if e1.overhang_sequence == reverse_complement(e2.overhang_sequence, seq_type="dna"):
        return True, f"Compatible complementary cohesive ends: {e1.name} ({e1.overhang_sequence}) pairs with {e2.name} ({e2.overhang_sequence})."

    return False, f"Incompatible overhangs: {e1.name} ({e1.overhang_sequence}) vs {e2.name} ({e2.overhang_sequence})."


def register_custom_enzyme(enzyme: RestrictionEnzyme) -> None:
    """Register a custom or proprietary restriction endonuclease into the global catalog."""
    key = enzyme.name.upper().replace("-", "").replace(" ", "").replace("_", "")
    ENZYME_DATABASE[key] = enzyme


@dataclass(frozen=True)
class GoldenGateResult:
    enzyme: str
    vector_length_bp: int
    insert_lengths_bp: List[int]
    vector_mass_ng: float
    vector_fmol: float
    insert_masses_ng: List[float]
    insert_fmols: List[float]
    insert_to_vector_ratio: float
    total_dna_mass_ng: float
    reaction_volume_ul: float
    reagent_volumes: Dict[str, float]
    thermocycling_protocol: List[str]
    notes: List[str]


def calculate_golden_gate_assembly(
    vector_length_bp: int,
    insert_lengths_bp: List[int],
    vector_mass_ng: Optional[float] = None,
    target_vector_fmol: float = 20.0,
    insert_to_vector_ratio: float = 2.0,
    type_iis_enzyme: str = "BsaI-HFv2",
    reaction_volume_ul: float = 20.0,
    vector_conc_ng_ul: Optional[float] = None,
    insert_concs_ng_ul: Optional[List[float]] = None,
) -> GoldenGateResult:
    """Calculate DNA amounts, molar stoichiometry, pipetting recipe, and cycling protocol for Golden Gate Assembly.

    Parameters
    ----------
    vector_length_bp : int
        Destination vector size in base pairs.
    insert_lengths_bp : List[int]
        List of insert sizes in base pairs.
    vector_mass_ng : float, optional
        Pre-weighed mass of vector DNA in ng (if omitted, calculated from target_vector_fmol).
    target_vector_fmol : float
        Target molar amount of vector in femtomoles (default: 20.0 fmol, standard for NEB Golden Gate).
    insert_to_vector_ratio : float
        Molar ratio of each insert to destination vector (default: 2.0 for 2:1).
    type_iis_enzyme : str
        Type IIS enzyme name (default: "BsaI-HFv2").
    reaction_volume_ul : float
        Total assembly reaction volume in microliters (default: 20.0 µL).
    vector_conc_ng_ul : float, optional
        Concentration of vector stock in ng/µL (default: 50.0 ng/µL).
    insert_concs_ng_ul : List[float], optional
        Concentration of each insert stock in ng/µL (default: 25.0 ng/µL each).
    """
    if vector_length_bp <= 0 or any(ins <= 0 for ins in insert_lengths_bp):
        raise ValueError("Vector and insert lengths must be strictly positive.")
    if reaction_volume_ul <= 0:
        raise ValueError("Reaction volume must be strictly positive.")

    # Molar calculation: 1 fmol = (ng * 1e6) / (bp * 650)
    # mass_ng = (fmol * bp * 650) / 1e6
    if vector_mass_ng is not None and vector_mass_ng > 0:
        v_mass = vector_mass_ng
        v_fmol = (v_mass * 1e6) / (vector_length_bp * 650.0)
    else:
        v_fmol = target_vector_fmol
        v_mass = (v_fmol * vector_length_bp * 650.0) / 1e6

    insert_masses: List[float] = []
    insert_fmols: List[float] = []
    for ins_len in insert_lengths_bp:
        ins_f = v_fmol * insert_to_vector_ratio
        ins_m = (ins_f * ins_len * 650.0) / 1e6
        insert_fmols.append(round(ins_f, 2))
        insert_masses.append(round(ins_m, 2))

    total_dna_ng = round(v_mass + sum(insert_masses), 2)

    # Reagents & pipetting volumes
    v_conc = vector_conc_ng_ul or 50.0
    v_vol = round(v_mass / v_conc, 2)

    ins_concs = insert_concs_ng_ul or ([25.0] * len(insert_lengths_bp))
    if len(ins_concs) < len(insert_lengths_bp):
        ins_concs.extend([25.0] * (len(insert_lengths_bp) - len(ins_concs)))

    ins_vols = [round(m / c, 2) for m, c in zip(insert_masses, ins_concs)]

    buffer_vol = round(0.10 * reaction_volume_ul, 2)  # 10X T4 DNA Ligase buffer
    enzyme_vol = 1.0  # Type IIS enzyme (typically 20 U)
    ligase_vol = 1.0  # T4 DNA Ligase (High Concentration)

    dna_and_enz_vol = v_vol + sum(ins_vols) + buffer_vol + enzyme_vol + ligase_vol
    water_vol = max(0.0, round(reaction_volume_ul - dna_and_enz_vol, 2))

    reagents = {
        "Destination Vector": v_vol,
    }
    for idx, (ins_v, ins_len) in enumerate(zip(ins_vols, insert_lengths_bp), 1):
        reagents[f"Insert #{idx} ({ins_len} bp)"] = ins_v
    reagents["T4 DNA Ligase Buffer (10X w/ 10 mM ATP)"] = buffer_vol
    reagents[f"Type IIS Enzyme ({type_iis_enzyme})"] = enzyme_vol
    reagents["T4 DNA Ligase (High Conc)"] = ligase_vol
    reagents["Nuclease-Free Water"] = water_vol

    # Cycling protocol
    enz_lower = type_iis_enzyme.lower()
    digest_temp = 42 if ("bsmbi" in enz_lower or "esp3i" in enz_lower) else 37

    cycling = [
        f"1. Assembly Cycling (30 cycles): {digest_temp}°C for 3 min (digestion) -> 16°C for 4 min (ligation)",
        "2. Terminal Digestion: 60°C for 5 min (cleaves residual linear or empty vector plasmids)",
        "3. Heat Inactivation: 80°C for 10 min (denatures enzymes before transformation)",
        "4. Transformation: Transform 2–5 µL into chemically competent or electrocompetent E. coli cells.",
    ]

    notes = [
        f"Target molar amount: {v_fmol:.1f} fmol vector : {v_fmol * insert_to_vector_ratio:.1f} fmol each insert ({insert_to_vector_ratio:.1f}:1 molar ratio).",
        "Ensure primers or synthesized fragments do not contain internal recognition sites for the chosen Type IIS enzyme.",
    ]
    if dna_and_enz_vol > reaction_volume_ul:
        notes.append(
            f"WARNING: Total reagent volume ({dna_and_enz_vol:.1f} µL) exceeds reaction volume ({reaction_volume_ul} µL). "
            "Concentrate DNA stocks or increase total reaction volume."
        )

    return GoldenGateResult(
        enzyme=type_iis_enzyme,
        vector_length_bp=vector_length_bp,
        insert_lengths_bp=insert_lengths_bp,
        vector_mass_ng=round(v_mass, 2),
        vector_fmol=round(v_fmol, 2),
        insert_masses_ng=insert_masses,
        insert_fmols=insert_fmols,
        insert_to_vector_ratio=insert_to_vector_ratio,
        total_dna_mass_ng=total_dna_ng,
        reaction_volume_ul=reaction_volume_ul,
        reagent_volumes=reagents,
        thermocycling_protocol=cycling,
        notes=notes,
    )
