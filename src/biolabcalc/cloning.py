"""Molecular cloning utilities: restriction enzyme digests, buffer compatibility, ligation stoichiometry, and Gibson assembly."""

from __future__ import annotations
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from .molecular_weight import calculate_dna_mw
from .seq_utils import reverse_complement


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
    recognition_seq_clean: str = ""
    cut_offset_top: int = 0
    cut_offset_bottom: int = 0
    is_type_iis: bool = False
    isoschizomers: Tuple[str, ...] = ()


ENZYME_DATABASE: Dict[str, RestrictionEnzyme] = {
    "ECORI": RestrictionEnzyme(
        "EcoRI", "G^AATTC", "5' overhang", "AATT", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "High-Fidelity versions available.", recognition_seq_clean="GAATTC", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "BAMHI": RestrictionEnzyme(
        "BamHI", "G^GATCC", "5' overhang", "GATC", 37, "None (column clean-up required)", "None", "rCutSmart", 100,
        "High glycerol (>5%) causes star activity.", recognition_seq_clean="GGATCC", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "HINDIII": RestrictionEnzyme(
        "HindIII", "A^AGCTT", "5' overhang", "AGCT", 37, "80°C for 20 min", "None", "rCutSmart", 100,
        "Classic 5' overhang cloning enzyme.", recognition_seq_clean="AAGCTT", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "XHOI": RestrictionEnzyme(
        "XhoI", "C^TCGAG", "5' overhang", "TCGA", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Compatible with SalI overhangs.", recognition_seq_clean="CTCGAG", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=("PaeR7I",)
    ),
    "NDEI": RestrictionEnzyme(
        "NdeI", "CA^TATG", "5' overhang", "TA", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Includes ATG start codon in recognition site.", recognition_seq_clean="CATATG", cut_offset_top=2, cut_offset_bottom=4,
        is_type_iis=False, isoschizomers=()
    ),
    "NOTI": RestrictionEnzyme(
        "NotI", "GC^GGCCGC", "5' overhang", "GGCC", 37, "65°C for 20 min", "CpG methylation sensitive", "rCutSmart", 100,
        "Rare 8-base cutter.", recognition_seq_clean="GCGGCCGC", cut_offset_top=2, cut_offset_bottom=6,
        is_type_iis=False, isoschizomers=()
    ),
    "SALI": RestrictionEnzyme(
        "SalI", "G^TCGAC", "5' overhang", "TCGA", 37, "65°C for 20 min", "CpG methylation sensitive", "rCutSmart", 100,
        "Requires BSA or rCutSmart.", recognition_seq_clean="GTCGAC", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "NHEI": RestrictionEnzyme(
        "NheI", "G^CTAGC", "5' overhang", "CTAG", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Compatible with SpeI and XbaI.", recognition_seq_clean="GCTAGC", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "BGLII": RestrictionEnzyme(
        "BglII", "A^GATCT", "5' overhang", "GATC", 37, "None (column clean-up required)", "dam methylation sensitive", "rCutSmart", 100,
        "Compatible with BamHI overhangs.", recognition_seq_clean="AGATCT", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "DPNI": RestrictionEnzyme(
        "DpnI", "GA^TC", "blunt", "", 37, "80°C for 20 min", "Requires Dam-methylation (Gm6ATC)", "rCutSmart", 100,
        "Selectively digests dam-methylated parent plasmid in site-directed mutagenesis.", recognition_seq_clean="GATC",
        cut_offset_top=2, cut_offset_bottom=2, is_type_iis=False, isoschizomers=()
    ),
    "ECORV": RestrictionEnzyme(
        "EcoRV", "GAT^ATC", "blunt", "", 37, "80°C for 20 min", "None", "rCutSmart", 100,
        "Blunt cutter.", recognition_seq_clean="GATATC", cut_offset_top=3, cut_offset_bottom=3,
        is_type_iis=False, isoschizomers=("Eco32I",)
    ),
    "SMAI": RestrictionEnzyme(
        "SmaI", "CCC^GGG", "blunt", "", 25, "65°C for 20 min", "CpG sensitive", "rCutSmart", 100,
        "Incubate at 25°C, not 37°C.", recognition_seq_clean="CCCGGG", cut_offset_top=3, cut_offset_bottom=3,
        is_type_iis=False, isoschizomers=()
    ),
    "XBAI": RestrictionEnzyme(
        "XbaI", "T^CTAGA", "5' overhang", "CTAG", 37, "65°C for 20 min", "dam sensitive (if overlapping)", "rCutSmart", 100,
        "Check dam methylation when flanked by TC.", recognition_seq_clean="TCTAGA", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "KPNI": RestrictionEnzyme(
        "KpnI", "GGTAC^C", "3' overhang", "GTAC", 37, "None (column clean-up required)", "None", "rCutSmart", 100,
        "Generates 3' overhang.", recognition_seq_clean="GGTACC", cut_offset_top=5, cut_offset_bottom=1,
        is_type_iis=False, isoschizomers=()
    ),
    "SACI": RestrictionEnzyme(
        "SacI", "GAGCT^C", "3' overhang", "AGCT", 37, "None (column clean-up required)", "None", "rCutSmart", 100,
        "Generates 3' overhang.", recognition_seq_clean="GAGCTC", cut_offset_top=5, cut_offset_bottom=1,
        is_type_iis=False, isoschizomers=()
    ),
    "PSTI": RestrictionEnzyme(
        "PstI", "CTGCA^G", "3' overhang", "TGCA", 37, "80°C for 20 min", "None", "rCutSmart", 100,
        "Generates 3' overhang.", recognition_seq_clean="CTGCAG", cut_offset_top=5, cut_offset_bottom=1,
        is_type_iis=False, isoschizomers=()
    ),
    "SPHI": RestrictionEnzyme(
        "SphI", "GCATG^C", "3' overhang", "CATG", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Generates 3' overhang.", recognition_seq_clean="GCATGC", cut_offset_top=5, cut_offset_bottom=1,
        is_type_iis=False, isoschizomers=("PaeI",)
    ),
    "SPEI": RestrictionEnzyme(
        "SpeI", "A^CTAGT", "5' overhang", "CTAG", 37, "80°C for 20 min", "None", "rCutSmart", 100,
        "Compatible with NheI, XbaI, and AvrII.", recognition_seq_clean="ACTAGT", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=("BcuI",)
    ),
    "AGEI": RestrictionEnzyme(
        "AgeI", "A^CCGGT", "5' overhang", "CCGG", 37, "65°C for 20 min", "CpG sensitive", "rCutSmart", 100,
        "Commonly used for fluorescent protein fusions.", recognition_seq_clean="ACCGGT", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=("BshTI",)
    ),
    "AVRII": RestrictionEnzyme(
        "AvrII", "C^CTAGG", "5' overhang", "CTAG", 37, "None (column clean-up required)", "None", "rCutSmart", 100,
        "Compatible with SpeI, NheI, and XbaI.", recognition_seq_clean="CCTAGG", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=("BlnI",)
    ),
    "PACI": RestrictionEnzyme(
        "PacI", "TTAAT^TAA", "3' overhang", "TAAT", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Rare 8-base cutter with AT-rich target.", recognition_seq_clean="TTAATTAA", cut_offset_top=5, cut_offset_bottom=3,
        is_type_iis=False, isoschizomers=()
    ),
    "ASCI": RestrictionEnzyme(
        "AscI", "GG^CGCGCC", "5' overhang", "CGCG", 37, "80°C for 20 min", "CpG sensitive", "rCutSmart", 100,
        "Rare 8-base cutter with GC-rich target.", recognition_seq_clean="GGCGCGCC", cut_offset_top=2, cut_offset_bottom=6,
        is_type_iis=False, isoschizomers=("PalAI",)
    ),
    "FSEI": RestrictionEnzyme(
        "FseI", "GGCCGG^CC", "3' overhang", "CCGG", 37, "65°C for 20 min", "CpG sensitive", "rCutSmart", 100,
        "Rare 8-base cutter with 3' overhang.", recognition_seq_clean="GGCCGGCC", cut_offset_top=6, cut_offset_bottom=2,
        is_type_iis=False, isoschizomers=()
    ),
    "SFII": RestrictionEnzyme(
        "SfiI", "GGCCNNNN^NGGCC", "3' overhang", "NNN", 50, "None (column clean-up required)", "None", "rCutSmart", 100,
        "Requires two recognition sites to cleave; incubate at 50°C.", recognition_seq_clean="GGCCNNNNNGGCC", cut_offset_top=8, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "PMEI": RestrictionEnzyme(
        "PmeI", "GTTT^AAAC", "blunt", "", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Rare 8-base blunt cutter.", recognition_seq_clean="GTTTAAAC", cut_offset_top=4, cut_offset_bottom=4,
        is_type_iis=False, isoschizomers=("MssI",)
    ),
    "SWAI": RestrictionEnzyme(
        "SwaI", "ATTT^AAAT", "blunt", "", 25, "65°C for 20 min", "None", "rCutSmart", 100,
        "Rare 8-base blunt cutter; incubate at 25°C.", recognition_seq_clean="ATTTAAAT", cut_offset_top=4, cut_offset_bottom=4,
        is_type_iis=False, isoschizomers=("SmiI",)
    ),
    "NCOI": RestrictionEnzyme(
        "NcoI", "C^CATGG", "5' overhang", "CATG", 37, "None (column clean-up required)", "None", "rCutSmart", 100,
        "Contains ATG start codon in recognition site.", recognition_seq_clean="CCATGG", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=()
    ),
    "BSPEI": RestrictionEnzyme(
        "BspEI", "T^CCGGA", "5' overhang", "CCGG", 37, "80°C for 20 min", "dam sensitive", "rCutSmart", 100,
        "Sensitive to dam methylation if preceded by GG.", recognition_seq_clean="TCCGGA", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=("AccIII",)
    ),
    "MFEI": RestrictionEnzyme(
        "MfeI", "C^AATTG", "5' overhang", "AATT", 37, "None (column clean-up required)", "None", "rCutSmart", 100,
        "Compatible with EcoRI overhangs.", recognition_seq_clean="CAATTG", cut_offset_top=1, cut_offset_bottom=5,
        is_type_iis=False, isoschizomers=("MunI",)
    ),
    "CLAI": RestrictionEnzyme(
        "ClaI", "AT^CGAT", "5' overhang", "CG", 37, "65°C for 20 min", "dam sensitive (if overlapping)", "rCutSmart", 100,
        "Blocked by dam methylation if overlapping GATC.", recognition_seq_clean="ATCGAT", cut_offset_top=2, cut_offset_bottom=4,
        is_type_iis=False, isoschizomers=("Bsp106I",)
    ),
    "DRAI": RestrictionEnzyme(
        "DraI", "TTT^AAA", "blunt", "", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "6-base blunt cutter.", recognition_seq_clean="TTTAAA", cut_offset_top=3, cut_offset_bottom=3,
        is_type_iis=False, isoschizomers=()
    ),
    "SCAI": RestrictionEnzyme(
        "ScaI", "AGT^ACT", "blunt", "", 37, "80°C for 20 min", "None", "rCutSmart", 100,
        "Often cuts within ampicillin resistance gene (bla).", recognition_seq_clean="AGTACT", cut_offset_top=3, cut_offset_bottom=3,
        is_type_iis=False, isoschizomers=("AssI",)
    ),
    "PVUI": RestrictionEnzyme(
        "PvuI", "CGAT^CG", "3' overhang", "AT", 37, "None (column clean-up required)", "CpG sensitive", "rCutSmart", 100,
        "Often cuts within ampicillin resistance gene.", recognition_seq_clean="CGATCG", cut_offset_top=4, cut_offset_bottom=2,
        is_type_iis=False, isoschizomers=("Ple19I",)
    ),
    "PVUII": RestrictionEnzyme(
        "PvuII", "CAG^CTG", "blunt", "", 37, "None (column clean-up required)", "None", "rCutSmart", 100,
        "Blunt cutter.", recognition_seq_clean="CAGCTG", cut_offset_top=3, cut_offset_bottom=3,
        is_type_iis=False, isoschizomers=()
    ),
    "STUI": RestrictionEnzyme(
        "StuI", "AGG^CCT", "blunt", "", 37, "None (column clean-up required)", "dcm sensitive", "rCutSmart", 100,
        "Blunt cutter; sensitive to dcm methylation if flanked.", recognition_seq_clean="AGGCCT", cut_offset_top=3, cut_offset_bottom=3,
        is_type_iis=False, isoschizomers=("AatI",)
    ),
    # Type IIS enzymes
    "BSAI": RestrictionEnzyme(
        "BsaI-HFv2", "GGTCTC(1/5)", "5' overhang", "NNNN", 37, "80°C for 20 min", "None", "rCutSmart", 100,
        "Type IIS enzyme; primary choice for Golden Gate Assembly.", recognition_seq_clean="GGTCTC", cut_offset_top=7, cut_offset_bottom=11,
        is_type_iis=True, isoschizomers=("Eco31I", "BsaI")
    ),
    "BSAIHFV2": RestrictionEnzyme(
        "BsaI-HFv2", "GGTCTC(1/5)", "5' overhang", "NNNN", 37, "80°C for 20 min", "None", "rCutSmart", 100,
        "Type IIS enzyme; primary choice for Golden Gate Assembly.", recognition_seq_clean="GGTCTC", cut_offset_top=7, cut_offset_bottom=11,
        is_type_iis=True, isoschizomers=("Eco31I", "BsaI")
    ),
    "BSMBI": RestrictionEnzyme(
        "BsmBI-v2", "CGTCTC(1/5)", "5' overhang", "NNNN", 42, "80°C for 20 min", "None", "NEBuffer r3.1", 100,
        "Type IIS enzyme; incubate at 42°C for Golden Gate digestion phase.", recognition_seq_clean="CGTCTC", cut_offset_top=7, cut_offset_bottom=11,
        is_type_iis=True, isoschizomers=("Esp3I", "BsmBI")
    ),
    "BSMBIV2": RestrictionEnzyme(
        "BsmBI-v2", "CGTCTC(1/5)", "5' overhang", "NNNN", 42, "80°C for 20 min", "None", "NEBuffer r3.1", 100,
        "Type IIS enzyme; incubate at 42°C for Golden Gate digestion phase.", recognition_seq_clean="CGTCTC", cut_offset_top=7, cut_offset_bottom=11,
        is_type_iis=True, isoschizomers=("Esp3I", "BsmBI")
    ),
    "ESP3I": RestrictionEnzyme(
        "Esp3I", "CGTCTC(1/5)", "5' overhang", "NNNN", 37, "65°C for 20 min", "dam/dcm sensitive", "rCutSmart", 100,
        "Type IIS enzyme; isoschizomer of BsmBI.", recognition_seq_clean="CGTCTC", cut_offset_top=7, cut_offset_bottom=11,
        is_type_iis=True, isoschizomers=("BsmBI", "BsmBI-v2")
    ),
    "BBSI": RestrictionEnzyme(
        "BbsI-HF", "GAAGAC(2/6)", "5' overhang", "NNNN", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Type IIS enzyme; popular for mammalian CRISPR sgRNA cloning.", recognition_seq_clean="GAAGAC", cut_offset_top=8, cut_offset_bottom=12,
        is_type_iis=True, isoschizomers=("BpiI", "BbsI")
    ),
    "BBSIHF": RestrictionEnzyme(
        "BbsI-HF", "GAAGAC(2/6)", "5' overhang", "NNNN", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Type IIS enzyme; popular for mammalian CRISPR sgRNA cloning.", recognition_seq_clean="GAAGAC", cut_offset_top=8, cut_offset_bottom=12,
        is_type_iis=True, isoschizomers=("BpiI", "BbsI")
    ),
    "PAQCI": RestrictionEnzyme(
        "PaqCI", "CACCTGC(4/8)", "5' overhang", "NNNN", 37, "65°C for 20 min", "None", "rCutSmart", 100,
        "Type IIS 7-base cutter with PaqCI activator.", recognition_seq_clean="CACCTGC", cut_offset_top=11, cut_offset_bottom=15,
        is_type_iis=True, isoschizomers=("AarI",)
    ),
    "SAPI": RestrictionEnzyme(
        "SapI", "GCTCTTC(1/4)", "5' overhang", "NNN", 37, "65°C for 20 min", "CpG sensitive", "rCutSmart", 100,
        "Type IIS enzyme with 3-bp overhang.", recognition_seq_clean="GCTCTTC", cut_offset_top=8, cut_offset_bottom=11,
        is_type_iis=True, isoschizomers=("BpuEI",)
    ),
}


def get_restriction_enzyme(name: str) -> RestrictionEnzyme:
    """Look up restriction enzyme details with flexible alias, casing, and High-Fidelity (-HF) matching."""
    norm = name.upper().replace("-", "").replace(" ", "").replace("_", "")
    # 1. Exact match in keys
    if norm in ENZYME_DATABASE:
        return ENZYME_DATABASE[norm]
    # 2. Match without HF / v2 suffixes (e.g. ECORIHF -> ECORI, BAMHIHF -> BAMHI)
    stripped = re.sub(r'(HFV2|HF|V2)$', '', norm)
    if stripped in ENZYME_DATABASE:
        return ENZYME_DATABASE[stripped]
    # 3. Match against values by canonical name or alias
    for k, v in ENZYME_DATABASE.items():
        v_norm = v.name.upper().replace("-", "").replace(" ", "").replace("_", "")
        if norm == v_norm or stripped == v_norm or v_norm in norm or norm in v_norm:
            return v
        for iso in v.isoschizomers:
            iso_norm = iso.upper().replace("-", "").replace(" ", "").replace("_", "")
            if norm == iso_norm or stripped == iso_norm:
                return v
    raise KeyError(f"Enzyme '{name}' not found. Available: {sorted(set(e.name for e in ENZYME_DATABASE.values()))}")


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
    notes: Tuple[str, ...]

    def __post_init__(self):
        if isinstance(self.notes, (list, set, tuple)):
            object.__setattr__(self, "notes", tuple(self.notes))


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
    insert_lengths_bp: Tuple[int, ...]
    vector_mass_ng: float
    insert_masses_ng: Tuple[float, ...]
    total_dna_pmol: float
    reagent_volumes: Dict[str, float]
    incubation_protocol: str

    def __post_init__(self):
        for f in ("insert_lengths_bp", "insert_masses_ng"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


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

    # Determine compatible buffer
    if e2 is None:
        chosen_buffer = e1.standard_buffer
    elif e1.standard_buffer == e2.standard_buffer:
        chosen_buffer = e1.standard_buffer
    elif "NEBuffer r3.1" in (e1.standard_buffer, e2.standard_buffer) and "rCutSmart" in (e1.standard_buffer, e2.standard_buffer):
        chosen_buffer = "NEBuffer r3.1"
    else:
        chosen_buffer = e1.standard_buffer
        notes.append(
            f"Double digest advisory: {e1.name} standard buffer ({e1.standard_buffer}) and "
            f"{e2.name} standard buffer ({e2.standard_buffer}) may be incompatible. "
            "Sequential digestion or separate buffer optimization recommended."
        )

    buffer_name = f"{chosen_buffer} Buffer" if not chosen_buffer.endswith("Buffer") else chosen_buffer

    reagents = {
        "Nuclease-Free Water": max(0.0, water_vol),
        f"10X {buffer_name}": buffer_vol,
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
        recommended_buffer=f"1X {buffer_name}",
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
    if reaction_volume_ul <= 0:
        raise ValueError("Reaction volume must be strictly positive.")

    # Mass_insert = Mass_vector * (Length_insert / Length_vector) * Molar_Ratio
    insert_mass_ng = vector_mass_ng * (insert_length_bp / vector_length_bp) * molar_ratio

    # Moles calculation (dsDNA) unified through calculate_dna_mw
    vec_mw = calculate_dna_mw(length=vector_length_bp, double_stranded=True).average_mw
    ins_mw = calculate_dna_mw(length=insert_length_bp, double_stranded=True).average_mw
    vec_pmol = (vector_mass_ng * 1e-9 / vec_mw) * 1e12
    ins_pmol = (insert_mass_ng * 1e-9 / ins_mw) * 1e12

    # Pipetting volumes
    buf_vol = round(reaction_volume_ul / 10.0, 2)  # 10X T4 DNA Ligase Buffer (contains ATP)
    ligase_vol = 1.0  # 1 µL T4 DNA Ligase

    vec_vol = round(vector_mass_ng / vector_conc_ng_ul, 2) if (vector_conc_ng_ul and vector_conc_ng_ul > 0) else round(vector_mass_ng / 50.0, 2)
    ins_vol = round(insert_mass_ng / insert_conc_ng_ul, 2) if (insert_conc_ng_ul and insert_conc_ng_ul > 0) else round(insert_mass_ng / 25.0, 2)

    solutes = buf_vol + ligase_vol + vec_vol + ins_vol
    water_vol = round(reaction_volume_ul - solutes, 2)
    if water_vol < 0:
        raise ValueError(
            f"Volume overflow: Combined reagents ({solutes:.1f} µL) exceed reaction volume ({reaction_volume_ul:.1f} µL). "
            f"Concentrate DNA or increase reaction volume."
        )

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
    if vector_length_bp <= 0 or not insert_lengths_bp or any(ins <= 0 for ins in insert_lengths_bp) or vector_mass_ng <= 0:
        raise ValueError("Vector and insert dimensions and mass must be strictly positive.")
    if reaction_volume_ul <= 0:
        raise ValueError("Reaction volume must be strictly positive.")

    # Moles calculation unified through calculate_dna_mw
    vec_mw = calculate_dna_mw(length=vector_length_bp, double_stranded=True).average_mw
    vec_pmol = (vector_mass_ng * 1e-9 / vec_mw) * 1e12

    insert_masses = []
    tot_pmol = vec_pmol

    for idx, ins_len in enumerate(insert_lengths_bp):
        ins_mw = calculate_dna_mw(length=ins_len, double_stranded=True).average_mw
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

    solutes = master_mix_vol + vec_vol + sum(ins_vols)
    water_vol = round(reaction_volume_ul - solutes, 2)
    if water_vol < 0:
        raise ValueError(
            f"Volume overflow: Combined reagents ({solutes:.1f} µL) exceed reaction volume ({reaction_volume_ul:.1f} µL). "
            f"Concentrate DNA or increase reaction volume."
        )

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


def are_overhangs_compatible(
    enzyme_1: str,
    enzyme_2: str,
    overhang_1: Optional[str] = None,
    overhang_2: Optional[str] = None,
) -> Tuple[bool, str]:
    """Determine whether two restriction enzymes produce compatible cohesive (or blunt) ends.

    Supports Type IIS enzymes where variable overhangs must be provided explicitly.
    """
    e1 = get_restriction_enzyme(enzyme_1)
    e2 = get_restriction_enzyme(enzyme_2)

    if e1.cut_type == "blunt" and e2.cut_type == "blunt":
        return True, "Both enzymes generate blunt ends; universally compatible for blunt-end ligation."

    if e1.cut_type != e2.cut_type:
        return False, f"Incompatible cut types: {e1.name} generates {e1.cut_type}, whereas {e2.name} generates {e2.cut_type}."

    is_iis_1 = e1.is_type_iis or "N" in e1.overhang_sequence
    is_iis_2 = e2.is_type_iis or "N" in e2.overhang_sequence

    if is_iis_1 or is_iis_2:
        if overhang_1 is None or overhang_2 is None:
            return False, "Type IIS enzymes generate sequence-dependent variable overhangs; supply explicit overhangs to check compatibility."
        oh1 = overhang_1.upper()
        oh2 = overhang_2.upper()
    else:
        oh1 = (overhang_1 or e1.overhang_sequence).upper()
        oh2 = (overhang_2 or e2.overhang_sequence).upper()

    if len(oh1) != len(oh2):
        return False, f"Incompatible overhang lengths: {len(oh1)} bp vs {len(oh2)} bp."

    if oh1 == oh2:
        return True, f"Compatible cohesive ends: both generate identical {e1.cut_type} ({oh1})."

    rc_oh2 = reverse_complement(oh2, seq_type="dna")
    if oh1 == rc_oh2:
        return True, f"Compatible complementary cohesive ends: {e1.name} ({oh1}) pairs with {e2.name} ({oh2})."

    return False, f"Incompatible overhangs: {e1.name} ({oh1}) vs {e2.name} ({oh2})."


def register_custom_enzyme(enzyme: RestrictionEnzyme) -> None:
    """Register a custom or proprietary restriction endonuclease into the global catalog."""
    key = enzyme.name.upper().replace("-", "").replace(" ", "").replace("_", "")
    ENZYME_DATABASE[key] = enzyme


@dataclass(frozen=True)
class GoldenGateResult:
    enzyme: str
    vector_length_bp: int
    insert_lengths_bp: Tuple[int, ...]
    vector_mass_ng: float
    vector_fmol: float
    insert_masses_ng: Tuple[float, ...]
    insert_fmols: Tuple[float, ...]
    insert_to_vector_ratio: float
    total_dna_mass_ng: float
    reaction_volume_ul: float
    reagent_volumes: Dict[str, float]
    thermocycling_protocol: Tuple[str, ...]
    notes: Tuple[str, ...]

    def __post_init__(self):
        for f in ("insert_lengths_bp", "insert_masses_ng", "insert_fmols", "thermocycling_protocol", "notes"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


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

    # Moles calculation unified through calculate_dna_mw:
    # 1 fmol = (ng * 1e6) / MW
    vec_mw = calculate_dna_mw(length=vector_length_bp, double_stranded=True).average_mw
    if vector_mass_ng is not None and vector_mass_ng > 0:
        v_mass = vector_mass_ng
        v_fmol = (v_mass * 1e6) / vec_mw
    else:
        v_fmol = target_vector_fmol
        v_mass = (v_fmol * vec_mw) / 1e6

    insert_masses: List[float] = []
    insert_fmols: List[float] = []
    for ins_len in insert_lengths_bp:
        ins_mw = calculate_dna_mw(length=ins_len, double_stranded=True).average_mw
        ins_f = v_fmol * insert_to_vector_ratio
        ins_m = (ins_f * ins_mw) / 1e6
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

    dna_and_enz_vol = round(v_vol + sum(ins_vols) + buffer_vol + enzyme_vol + ligase_vol, 2)
    water_vol = round(reaction_volume_ul - dna_and_enz_vol, 2)
    if water_vol < 0:
        raise ValueError(
            f"Volume overflow: Combined reagents ({dna_and_enz_vol:.1f} µL) exceed reaction volume ({reaction_volume_ul:.1f} µL). "
            f"Concentrate DNA stocks or increase total reaction volume."
        )

    reagents = {
        "Destination Vector": v_vol,
    }
    for idx, (ins_v, ins_len) in enumerate(zip(ins_vols, insert_lengths_bp), 1):
        reagents[f"Insert #{idx} ({ins_len} bp)"] = ins_v
    reagents["T4 DNA Ligase Buffer (10X w/ 10 mM ATP)"] = buffer_vol
    reagents[f"Type IIS Enzyme ({type_iis_enzyme})"] = enzyme_vol
    reagents["T4 DNA Ligase (High Conc)"] = ligase_vol
    reagents["Nuclease-Free Water"] = max(0.0, water_vol)

    # Cycling protocol
    enz_lower = type_iis_enzyme.lower()
    digest_temp = 42 if "bsmbi" in enz_lower else 37

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


# ============================================================================
# Type IIS Golden Gate Overhang Fidelity Matrix (GoldenHinges Benchmark)
# ============================================================================

@dataclass(frozen=True)
class GoldenGateFidelityResult:
    overhangs: Tuple[str, ...]
    enzyme: str
    assembly_fidelity_percent: float
    collision_pairs: Tuple[Tuple[str, str], ...]
    palindromic_overhangs: Tuple[str, ...]
    mismatch_risks: Tuple[Tuple[str, str, float], ...]  # (overhang1, overhang2, risk_pct)
    recommended_overhangs: Tuple[str, ...] = ()

    def __post_init__(self):
        for f in ("overhangs", "collision_pairs", "palindromic_overhangs", "mismatch_risks", "recommended_overhangs"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


# High-fidelity orthogonal 4-bp overhang catalog (Potapov et al. 2018, Pryor et al. 2020, MoClo standards)
STANDARD_GOLDEN_GATE_OVERHANGS: Tuple[str, ...] = (
    "GGAG",  # Promoters / 5' UTR (MoClo fusion site A)
    "TACT",  # Signal peptide / Start (MoClo fusion site B)
    "AATG",  # CDS / N-terminal tag (MoClo fusion site C)
    "AGGT",  # Internal domain / CDS continuation
    "GCTT",  # C-terminal tag (MoClo fusion site D)
    "CGCT",  # Terminator / 3' UTR (MoClo fusion site E)
    "TGCC",  # Resistance / Backbone junction (MoClo fusion site F)
    "ACTA",  # Orthogonal junction 7
    "TTAC",  # Orthogonal junction 8
    "CCAA",  # Orthogonal junction 9
    "ATCC",  # Orthogonal junction 10
    "CTGA",  # Orthogonal junction 11
)


def recommend_golden_gate_overhangs(n_junctions: int) -> Tuple[str, ...]:
    """
    Recommend a high-fidelity orthogonal set of 4-bp Type IIS Golden Gate overhangs.
    
    Parameters:
        n_junctions (int): Number of assembly junctions needed (typically 2 to 12).
        
    Returns:
        Tuple[str, ...]: Orthogonal, non-palindromic 4-bp overhangs.
    """
    if n_junctions <= 0:
        return ()
    return STANDARD_GOLDEN_GATE_OVERHANGS[: min(n_junctions, len(STANDARD_GOLDEN_GATE_OVERHANGS))]


def evaluate_golden_gate_fidelity(
    overhangs: Sequence[str],
    enzyme: str = "BsaI-HFv2",
) -> GoldenGateFidelityResult:
    """
    Evaluate Type IIS Golden Gate assembly fidelity across a set of 4-bp overhangs.
    
    Scores set for:
    1. Palindromic self-ligation (e.g. AATT, AGCT, GATC, CATG).
    2. Reverse-complement collisions between distinct junctions.
    3. T4 DNA ligase single-mismatch or G:T wobble cross-talk.
    4. Overall predicted assembly fidelity percentage (0-100%).
    """
    clean_ohs = tuple(oh.upper().strip() for oh in overhangs if oh.strip())
    n = len(clean_ohs)

    palindromes: List[str] = []
    collisions: List[Tuple[str, str]] = []
    mismatch_risks: List[Tuple[str, str, float]] = []

    comp_map = {"A": "T", "T": "A", "C": "G", "G": "C"}

    def rc(s: str) -> str:
        return "".join(comp_map.get(b, "N") for b in reversed(s))

    def hamming_dist(s1: str, s2: str) -> int:
        return sum(1 for a, b in zip(s1, s2) if a != b)

    penalty = 0.0

    # 1. Check palindromes
    for oh in clean_ohs:
        if len(oh) == 4 and oh == rc(oh):
            palindromes.append(oh)
            penalty += 35.0  # Severe penalty: self-ligates in reverse orientation

    # 2. Check RC collisions and mismatches
    seen_rc: Dict[str, str] = {}
    for i in range(n):
        oh_i = clean_ohs[i]
        rc_i = rc(oh_i)

        for j in range(i + 1, n):
            oh_j = clean_ohs[j]
            rc_j = rc(oh_j)

            # Direct duplicate
            if oh_i == oh_j:
                collisions.append((oh_i, oh_j))
                penalty += 45.0
            # Reverse-complement collision
            elif oh_i == rc_j:
                collisions.append((oh_i, oh_j))
                penalty += 40.0
            else:
                # Mismatch cross-talk
                d_direct = hamming_dist(oh_i, oh_j)
                d_rc = hamming_dist(oh_i, rc_j)
                min_d = min(d_direct, d_rc)

                if min_d == 1:
                    # 1-bp mismatch cross-talk (e.g. G:T wobble or single transition)
                    risk_pct = 12.5
                    mismatch_risks.append((oh_i, oh_j, risk_pct))
                    penalty += 8.0
                elif min_d == 2:
                    risk_pct = 2.0
                    if (oh_i, oh_j) not in [(m[0], m[1]) for m in mismatch_risks]:
                        mismatch_risks.append((oh_i, oh_j, risk_pct))
                    penalty += 1.5

    fidelity = max(0.0, min(100.0, 100.0 - penalty))

    rec = recommend_golden_gate_overhangs(n)

    return GoldenGateFidelityResult(
        overhangs=clean_ohs,
        enzyme=enzyme,
        assembly_fidelity_percent=round(fidelity, 1),
        collision_pairs=tuple(collisions),
        palindromic_overhangs=tuple(palindromes),
        mismatch_risks=tuple(mismatch_risks),
        recommended_overhangs=rec,
    )

