"""In vitro transcription (IVT) yield, NTP stoichiometry, and efficiency calculations."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Literal
from .seq_utils import clean_sequence, count_bases, reverse_complement
from .molecular_weight import calculate_rna_mw, calculate_dna_mw, AVOGADRO

PROMOTER_SEQUENCES: Dict[str, str] = {
    "T7": "TAATACGACTCACTATA",       # T7 Class III consensus (-17 to -1)
    "T7_short": "AATACGACTCACTATA", # 16-mer variant
    "SP6": "ATTTAGGTGACACTATA",      # SP6 consensus (-17 to -1)
    "T3": "AATTAACCCTCACTAAA",       # T3 consensus (-17 to -1)
}


@dataclass(frozen=True)
class InitiationAnalysis:
    initial_5prime_motif: str
    leading_g_count: int
    efficiency_rating: str
    relative_efficiency_percent: float
    abortive_cycling_risk: str
    recommendations: List[str]
    optimized_sequence: str
    added_leading_gs: int




@dataclass(frozen=True)
class TranscriptionTimeOptimizationResult:
    transcript_length_nt: int
    temperature_celsius: float
    recommended_time_hours: float
    recommended_time_range_hours: Tuple[float, float]
    plateau_time_hours: float
    use_pyrophosphatase: bool
    temperature_mode: str
    risk_of_3prime_heterogeneity: str
    risk_of_degradation: str
    kinetic_profile_summary: str
    time_course_predictions: List[Dict[str, Any]]
    guidelines: List[str]


def optimize_transcription_time(
    transcript_length_nt: int,
    temperature_celsius: float = 37.0,
    use_pyrophosphatase: bool = True,
    target_yield_ug: Optional[float] = None,
    reaction_volume_ul: float = 20.0,
) -> TranscriptionTimeOptimizationResult:
    """Model transcription kinetics and calculate optimal reaction incubation time.

    Balances maximal run-off yield against 3' non-templated additions (N+1/N+2),
    pyrophosphate precipitation, and thermal RNA degradation.

    Parameters
    ----------
    transcript_length_nt : int
        Length of the RNA transcript in nucleotides.
    temperature_celsius : float
        Incubation temperature in °C (default: 37.0°C).
    use_pyrophosphatase : bool
        Whether inorganic pyrophosphatase (IPP) is present (default: True).
    target_yield_ug : float, optional
        Target mass yield in µg.
    reaction_volume_ul : float
        Reaction volume in µL (default: 20.0 µL).
    """
    import math
    if transcript_length_nt <= 0:
        raise ValueError("Transcript length must be strictly positive.")

    temp = temperature_celsius
    ipp = use_pyrophosphatase

    # Length classes
    if transcript_length_nt < 120:
        base_time = 1.75
        time_range = (1.5, 2.0)
        plateau_time = 2.0 if ipp else 1.5
        risk_3p = "High if incubated > 2.5 h (T7 RNAP adds untemplated N+1/N+2 nucleotides once NTP:template ratio is elevated)"
        risk_deg = "Low"
        notes = [
            "Small transcripts (<120 nt, aptamers, sgRNAs) clear initiation rapidly and plateau within 1.5–2.0 hours.",
            "Do NOT incubate past 2.5 hours: prolonged incubation promotes untemplated 3' terminal nucleotide addition.",
        ]
    elif transcript_length_nt <= 1000:
        base_time = 2.0
        time_range = (2.0, 2.5)
        plateau_time = 2.5 if ipp else 2.0
        risk_3p = "Moderate"
        risk_deg = "Low to Moderate"
        notes = [
            "Intermediate transcripts (120–1000 nt) reach peak yield between 2.0 and 2.5 hours.",
            "Inorganic pyrophosphatase prevents magnesium pyrophosphate precipitation and sustains elongation.",
        ]
    else:
        base_time = 3.0
        time_range = (2.5, 3.5 if ipp else 3.0)
        plateau_time = 3.5 if ipp else 2.5
        risk_3p = "Low"
        risk_deg = "Moderate to High (thermal hydrolysis risks increase with transcript length)"
        notes = [
            "Long mRNAs (>1000 nt) require 2.5–3.5 hours for full processive elongation and maximum molar yield.",
            "Inclusion of RNase inhibitor (40 U per 20 µL rxn) is strongly advised for long incubations.",
        ]

    # Temperature adjustment
    if temp >= 40.0:
        temp_mode = "Elevated Temperature (resolves secondary structures / G-quadruplexes)"
        rec_time = max(1.0, round(base_time * 0.65, 2))
        time_range = (1.0, 1.5)
        plateau_time = 1.5
        notes.append("Elevated temperature (42°C) reduces T7 RNA polymerase half-life (~50 min); terminate at 1.0–1.5 hours.")
    elif temp <= 32.0:
        temp_mode = "Reduced Temperature (minimizes misfolding / preserves catalytic structures)"
        rec_time = round(base_time * 1.8, 2)
        time_range = (round(base_time * 1.5, 2), round(base_time * 2.2, 2))
        plateau_time = round(base_time * 2.0, 2)
        notes.append("Reduced temperature (30°C) slows elongation rate (~40% of 37°C rate); extend incubation to 4.0–5.0 hours.")
    else:
        temp_mode = "Standard Processive Temperature (37°C)"
        rec_time = base_time

    if not ipp:
        notes.append("WARNING: Without inorganic pyrophosphatase (IPP), free Mg2+ is rapidly depleted by PPi precipitate, arresting synthesis early.")

    # Time-course kinetic trajectory (fraction of maximum yield)
    time_points = [0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    time_course: List[Dict[str, Any]] = []
    for t in time_points:
        k = 1.6 if temp >= 40 else (0.6 if temp <= 32 else 1.2)
        if not ipp and t > 1.5:
            frac = min(1.0, 1.0 - math.exp(-k * min(t, 1.5)))
        else:
            frac = min(1.0, 1.0 - math.exp(-k * t))

        status = "Elongating"
        if frac >= 0.95:
            status = "Plateau (Optimal Stop)"
        elif frac >= 0.85:
            status = "Near Plateau"
        time_course.append({
            "time_hours": t,
            "estimated_percent_max_yield": round(frac * 100.0, 1),
            "reaction_phase": status,
        })

    summary = f"Recommended incubation: {rec_time:.2f} hours ({time_range[0]:.1f}–{time_range[1]:.1f} h) at {temp:.1f}°C."

    return TranscriptionTimeOptimizationResult(
        transcript_length_nt=transcript_length_nt,
        temperature_celsius=temp,
        recommended_time_hours=round(rec_time, 2),
        recommended_time_range_hours=(round(time_range[0], 2), round(time_range[1], 2)),
        plateau_time_hours=round(plateau_time, 2),
        use_pyrophosphatase=ipp,
        temperature_mode=temp_mode,
        risk_of_3prime_heterogeneity=risk_3p,
        risk_of_degradation=risk_deg,
        kinetic_profile_summary=summary,
        time_course_predictions=time_course,
        guidelines=notes,
    )


@dataclass(frozen=True)
class IVTResult:
    rna_length: int
    rna_sequence: str
    rna_mw: float
    reaction_volume_ul: float
    rna_yield_ug: float
    rna_yield_pmol: float
    theoretical_max_yield_ug: float
    limiting_ntp: str
    ntp_initial_mm: Dict[str, float]
    ntp_consumed_nmol: Dict[str, float]
    ntp_remaining_mm: Dict[str, float]
    ntp_incorporation_percent: Dict[str, float]
    overall_efficiency_percent: float
    pyrophosphate_released_nmol: float
    pyrophosphate_released_ug: float
    transcript_turnover_ratio: Optional[float] = None
    free_mg_initial_mm: float = 0.0
    promoter_detected: Optional[str] = None
    promoter_trimmed_nt: int = 0
    added_5prime_gs: int = 0
    initiation_efficiency_rating: str = "Optimal"
    initiation_recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cap_analog: Optional[str] = None
    predicted_capping_efficiency_percent: Optional[float] = None
    modified_ntp: Optional[str] = None
    modified_mw: Optional[float] = None
    recommended_incubation_hours: float = 2.0
    protons_released_nmol: float = 0.0
    buffer_recommendation: str = ""
    hepes_vs_tris_comparison: str = ""
    end_5: str = "triphosphate"
    end_3: str = "hydroxyl"
    backbone: str = "monophosphate"


def detect_and_trim_promoter(seq: str) -> tuple[str, Optional[str], int]:
    """Detect whether sequence contains a known bacteriophage promoter (T7, SP6, T3) and trim it.

    Supports sense/coding strands as well as reverse complement (antisense template) strands.

    Parameters
    ----------
    seq : str
        Input DNA template or RNA sequence.

    Returns
    -------
    tuple of (transcribed_sequence, promoter_name, trimmed_nt_count)
    """
    clean = clean_sequence(seq)
    clean_dna = clean.replace("U", "T")

    # Check forward sense strand
    for name, p_seq in PROMOTER_SEQUENCES.items():
        idx = clean_dna.find(p_seq)
        if idx != -1:
            transcribed = clean[idx + len(p_seq):]
            trimmed_nt = idx + len(p_seq)
            return transcribed, name, trimmed_nt

    # Check reverse complement (antisense template) strand
    rc_dna = reverse_complement(clean_dna, seq_type="dna")
    for name, p_seq in PROMOTER_SEQUENCES.items():
        idx = rc_dna.find(p_seq)
        if idx != -1:
            transcribed = rc_dna[idx + len(p_seq):]
            trimmed_nt = idx + len(p_seq)
            return transcribed, f"{name} (antisense template)", trimmed_nt

    return clean, None, 0


def evaluate_initiation_efficiency(
    rna_seq: str,
    target_leading_gs: int = 2,
) -> InitiationAnalysis:
    """Evaluate 5' terminal initiation efficiency, abortive cycling risk, and suggest GG additions."""
    clean = clean_sequence(rna_seq).replace("T", "U")
    if not clean:
        raise ValueError("RNA sequence cannot be empty.")

    motif_3 = clean[:min(3, len(clean))]

    leading_gs = 0
    for c in clean:
        if c == "G":
            leading_gs += 1
        else:
            break

    recs = []
    if leading_gs >= 3:
        rating = "Optimal"
        eff = 100.0
        risk = "Low"
        recs.append("5'-GGG leader provides optimal T7 promoter clearance and maximum run-off yield.")
    elif leading_gs == 2:
        rating = "High"
        eff = 85.0
        risk = "Low"
        recs.append("5'-GG leader provides high initiation efficiency (~85%); standard for RNA aptamers and Cas9 sgRNAs.")
    elif leading_gs == 1:
        rating = "Moderate"
        eff = 60.0
        risk = "Moderate"
        recs.append("Single 5'-G yields moderate initiation (~60%). Prepending one or two extra Guanines (5'-GG or 5'-GGG) will suppress abortive cycling and boost yield.")
    elif clean[0] == "A":
        rating = "Low"
        eff = 25.0
        risk = "High"
        recs.append("5'-Adenine initiation has poor T7 affinity (~25% efficiency) with high abortive cycling. Elevate starting ATP or prepend 5'-GG.")
    else:
        rating = "Poor"
        eff = 10.0
        risk = "Severe"
        recs.append(f"5'-{clean[0]} (pyrimidine) causes severe abortive cycling (<10% yield). Prepending 5'-GG or 5'-GGG is strongly recommended for viable transcription.")

    needed_gs = max(0, target_leading_gs - leading_gs)
    opt_seq = ("G" * needed_gs) + clean
    if needed_gs > 0:
        recs.append(f"Optimized sequence generated by prepending {needed_gs} Guanine(s) (5'-{'G'*needed_gs}...).")

    return InitiationAnalysis(
        initial_5prime_motif=motif_3,
        leading_g_count=leading_gs,
        efficiency_rating=rating,
        relative_efficiency_percent=eff,
        abortive_cycling_risk=risk,
        recommendations=recs,
        optimized_sequence=opt_seq,
        added_leading_gs=needed_gs,
    )


def calculate_ivt_yield(
    rna_seq: str,
    reaction_volume_ul: float = 20.0,
    measured_yield_ug: Optional[float] = None,
    target_yield_ug: Optional[float] = None,
    atp_mm: float = 5.0,
    ctp_mm: float = 5.0,
    gtp_mm: float = 5.0,
    utp_mm: float = 5.0,
    mg_conc_mm: float = 20.0,
    use_pyrophosphatase: bool = True,
    template_dna_ng: Optional[float] = None,
    template_dna_length_bp: Optional[int] = None,
    auto_trim_promoter: bool = True,
    add_5prime_gg: int = 0,
    cap_analog: Optional[str] = None,
    modified_ntp: Optional[str] = None,
    end_5: Literal["triphosphate", "monophosphate", "hydroxyl", "cap0", "cap1"] = "triphosphate",
    end_3: Literal["hydroxyl", "monophosphate", "diphosphate", "triphosphate", "cyclic_phosphate"] = "hydroxyl",
    backbone: Literal["monophosphate", "phosphorothioate"] = "monophosphate",
    temperature_celsius: float = 37.0,
    buffer_type: str = "hepes",
) -> IVTResult:
    """Calculate in vitro transcription yield, per-NTP consumption, efficiency, and PPi generation.

    Parameters
    ----------
    rna_seq : str
        Input template or RNA sequence (5' to 3').
    reaction_volume_ul : float
        Total IVT reaction volume in microliters (default: 20 µL).
    measured_yield_ug : float, optional
        Actual experimentally measured RNA yield in micrograms.
    target_yield_ug : float, optional
        Target or hypothetical RNA yield in micrograms.
    atp_mm, ctp_mm, gtp_mm, utp_mm : float
        Starting concentration of each ribonucleotide triphosphate in millimolar (default: 5.0 mM).
    mg_conc_mm : float
        Starting concentration of MgCl2 in millimolar (default: 20.0 mM).
    use_pyrophosphatase : bool
        Whether inorganic pyrophosphatase (IPP) is included to hydrolyze PPi precipitate (default: True).
    template_dna_ng : float, optional
        Amount of DNA template input in nanograms.
    template_dna_length_bp : float, optional
        Length of template plasmid/linear DNA in base pairs.
    auto_trim_promoter : bool
        Whether to detect and automatically trim upstream T7, SP6, or T3 promoters (default: True).
    add_5prime_gg : int
        Number of desired 5' Guanine residues (0-3). If sequence has fewer, prepends Gs to boost initiation.
    """
    cleaned_rna = clean_sequence(rna_seq).replace("T", "U")
    if not cleaned_rna:
        raise ValueError("RNA sequence cannot be empty.")

    warnings: List[str] = []

    # Promoter trimming
    promoter_name = None
    trimmed_nt = 0
    if auto_trim_promoter:
        trimmed_seq, promoter_name, trimmed_nt = detect_and_trim_promoter(cleaned_rna)
        if promoter_name:
            cleaned_rna = trimmed_seq.replace("T", "U")
            warnings.append(
                f"Detected and trimmed upstream {promoter_name} promoter sequence ({trimmed_nt} nt). "
                "Calculated transcript begins at +1 initiation site."
            )

    if not cleaned_rna:
        raise ValueError("Sequence contains only promoter with no downstream transcribed region.")

    # 5' GG optimization
    added_gs = 0
    if add_5prime_gg > 0:
        leading_gs = 0
        for c in cleaned_rna:
            if c == "G":
                leading_gs += 1
            else:
                break
        needed = max(0, add_5prime_gg - leading_gs)
        if needed > 0:
            cleaned_rna = ("G" * needed) + cleaned_rna
            added_gs = needed
            warnings.append(
                f"Prepended {needed} 5'-Guanine residue(s) to optimize T7 initiation and suppress abortive cycling."
            )

    init_eval = evaluate_initiation_efficiency(cleaned_rna)

    counts = count_bases(cleaned_rna)
    length = len(cleaned_rna)

    rna_mw_res = calculate_rna_mw(cleaned_rna, end_5=end_5, end_3=end_3, backbone=backbone)
    base_mw = rna_mw_res.average_mw

    # Modified nucleotide adjustments
    mod_str = (modified_ntp or "").lower().replace("-", "").replace("_", "")
    mod_delta_mw = 0.0
    mod_desc = None
    if mod_str in ("m1psi", "n1methylpseudouridine", "m1y"):
        mod_delta_mw = counts.get("U", 0) * 14.027
        mod_desc = "N1-methylpseudouridine (m1Ψ)"
    elif mod_str in ("5mou", "5methoxyuridine"):
        mod_delta_mw = counts.get("U", 0) * 30.026
        mod_desc = "5-methoxyuridine (5moU)"
    elif mod_str in ("m5c", "5methylcytidine"):
        mod_delta_mw = counts.get("C", 0) * 14.027
        mod_desc = "5-methylcytidine (m5C)"
    elif mod_str in ("psi", "pseudouridine"):
        mod_desc = "Pseudouridine (Ψ)"
    elif mod_str and mod_str != "none":
        warnings.append(f"Unrecognized modified NTP '{modified_ntp}'. Defaulting to standard unmodified MW.")

    # Cap analog adjustments
    cap_str = (cap_analog or "").lower().replace("-", "").replace("_", "")
    cap_delta_mw = 0.0
    capping_eff: Optional[float] = None
    cap_name: Optional[str] = None

    if cap_str in ("cleancapag", "cleancap_ag"):
        cap_name = "CleanCap AG (Cap-1)"
        capping_eff = 95.0
        cap_delta_mw = 696.5
        if not cleaned_rna.startswith("AG"):
            warnings.append(
                f"CleanCap AG requires a 5'-AG... initiation sequence. Sequence starts with '{cleaned_rna[:2]}', "
                "which may reduce capping efficiency. Consider mutating +1/+2 to AG or using CleanCap GG."
            )
    elif cap_str in ("cleancapgg", "cleancap_gg"):
        cap_name = "CleanCap GG (Cap-1)"
        capping_eff = 95.0
        cap_delta_mw = 696.5
        if not cleaned_rna.startswith("GG"):
            warnings.append(
                f"CleanCap GG requires a 5'-GG... initiation sequence. Sequence starts with '{cleaned_rna[:2]}'."
            )
    elif cap_str == "arca":
        cap_name = "ARCA (Cap-0)"
        capping_eff = 75.0
        cap_delta_mw = 509.3
        if gtp_mm > 1.5:
            warnings.append(
                f"ARCA capping requires lowering GTP concentration (typically 1.0 mM GTP : 4.0 mM ARCA, 4:1 ratio). "
                f"Current GTP is {gtp_mm} mM."
            )
    elif cap_str in ("m7g", "cap0"):
        cap_name = "m7G (Cap-0)"
        capping_eff = 70.0
        cap_delta_mw = 525.3
    elif cap_str and cap_str != "none":
        warnings.append(f"Unrecognized cap analog '{cap_analog}'.")

    mw = round(base_mw + mod_delta_mw + cap_delta_mw, 2)

    initial_ntp_mm = {
        "ATP": atp_mm,
        "CTP": ctp_mm,
        "GTP": gtp_mm,
        "UTP": utp_mm,
    }

    initial_ntp_nmol = {k: v * reaction_volume_ul for k, v in initial_ntp_mm.items()}

    base_counts = {
        "ATP": counts.get("A", 0),
        "CTP": counts.get("C", 0),
        "GTP": counts.get("G", 0),
        "UTP": counts.get("U", 0),
    }

    max_transcripts_nmol = {}
    for base, nmol_init in initial_ntp_nmol.items():
        n_per_tx = base_counts[base]
        if n_per_tx > 0:
            max_transcripts_nmol[base] = nmol_init / n_per_tx
        else:
            max_transcripts_nmol[base] = float("inf")

    limiting_ntp = min(max_transcripts_nmol, key=max_transcripts_nmol.get)
    max_rxn_transcripts_nmol = max_transcripts_nmol[limiting_ntp]
    theoretical_max_yield_ug = (max_rxn_transcripts_nmol * 1e-9) * mw * 1e6

    actual_yield_ug = measured_yield_ug if measured_yield_ug is not None else (target_yield_ug or 0.0)
    rna_synth_nmol = (actual_yield_ug * 1e-6 / mw) * 1e9
    rna_synth_pmol = rna_synth_nmol * 1000.0

    ntp_consumed_nmol = {base: base_counts[base] * rna_synth_nmol for base in ("ATP", "CTP", "GTP", "UTP")}
    ntp_remaining_mm = {}
    ntp_incorporation_pct = {}

    for base in ("ATP", "CTP", "GTP", "UTP"):
        init_nmol = initial_ntp_nmol[base]
        cons_nmol = ntp_consumed_nmol[base]
        rem_nmol = max(0.0, init_nmol - cons_nmol)
        ntp_remaining_mm[base] = round(rem_nmol / reaction_volume_ul, 3)
        pct = (cons_nmol / init_nmol * 100.0) if init_nmol > 0 else 0.0
        ntp_incorporation_pct[base] = round(min(100.0, pct), 2)

    overall_eff = round((actual_yield_ug / theoretical_max_yield_ug * 100.0), 2) if theoretical_max_yield_ug > 0 else 0.0

    ppi_released_nmol = max(0, length - 1) * rna_synth_nmol
    ppi_mw = 177.98
    ppi_released_ug = (ppi_released_nmol * 1e-9) * ppi_mw * 1e6

    turnover = None
    if template_dna_ng is not None and template_dna_length_bp is not None and template_dna_length_bp > 0:
        template_mw = template_dna_length_bp * 617.96 + 36.04
        template_nmol = (template_dna_ng * 1e-9 / template_mw) * 1e9
        if template_nmol > 0:
            turnover = round(rna_synth_nmol / template_nmol, 1)

    total_ntp_mm = atp_mm + ctp_mm + gtp_mm + utp_mm
    free_mg_initial = mg_conc_mm - total_ntp_mm

    if actual_yield_ug > theoretical_max_yield_ug * 1.02:
        warnings.append(
            f"Measured yield ({actual_yield_ug:.1f} µg) exceeds theoretical maximum ({theoretical_max_yield_ug:.1f} µg). "
            "Check for template carryover, incomplete digest, or spectrophotometer blank error."
        )

    if free_mg_initial < 1.0:
        warnings.append(
            f"Low initial free Mg2+ ({free_mg_initial:.1f} mM). Total NTPs ({total_ntp_mm:.1f} mM) nearly chelate all "
            f"Mg2+ ({mg_conc_mm:.1f} mM). T7 RNA polymerase typically requires 4–10 mM free Mg2+."
        )

    if not use_pyrophosphatase and ppi_released_nmol > (mg_conc_mm * reaction_volume_ul * 0.4):
        warnings.append(
            "High PPi release without inorganic pyrophosphatase (IPP) risks precipitating catalytic Mg2+ as Mg2P2O7, "
            "potentially stalling transcription before completion."
        )

    # Transcription time optimization
    time_res = optimize_transcription_time(
        transcript_length_nt=length,
        temperature_celsius=temperature_celsius,
        use_pyrophosphatase=use_pyrophosphatase,
        reaction_volume_ul=reaction_volume_ul,
    )

    # Proton stoichiometry: 1 H+ per incorporated NTP + 1 H+ per hydrolyzed PPi
    total_ntp_consumed = sum(ntp_consumed_nmol.values())
    protons_nmol = round(total_ntp_consumed + (ppi_released_nmol if use_pyrophosphatase else 0.0), 2)

    # Buffer analysis: HEPES-KOH vs Tris-HCl
    buf_clean = buffer_type.lower()
    if "hepes" in buf_clean:
        buf_rec = (
            f"40–80 mM HEPES-KOH (pH 7.5 at 37°C) provides optimal pKa (7.38 at 37°C) and robust buffering capacity "
            f"to neutralize the {protons_nmol:.1f} nmol of H+ generated without pH collapse. Potassium counterions stimulate T7 RNAP."
        )
        comp_summary = "HEPES-KOH maintains stable pH 7.3–7.5 throughout synthesis, outperforming Tris-HCl."
    else:
        buf_rec = (
            f"NOTICE: 40 mM Tris-HCl undergoes thermal pH depression (drops ~0.34 units to pH 7.56 at 37°C) and lacks buffering capacity "
            f"below pH 7.5. Accumulation of {protons_nmol:.1f} nmol H+ risks dropping pH < 7.0, inhibiting T7 polymerase. Switch to 40 mM HEPES-KOH."
        )
        comp_summary = "Tris-HCl is vulnerable to acidification; HEPES-KOH provides superior pH defense."

    return IVTResult(
        rna_length=length,
        rna_sequence=cleaned_rna,
        rna_mw=round(mw, 2),
        reaction_volume_ul=reaction_volume_ul,
        rna_yield_ug=round(actual_yield_ug, 2),
        rna_yield_pmol=round(rna_synth_pmol, 2),
        theoretical_max_yield_ug=round(theoretical_max_yield_ug, 2),
        limiting_ntp=limiting_ntp,
        ntp_initial_mm=initial_ntp_mm,
        ntp_consumed_nmol={k: round(v, 3) for k, v in ntp_consumed_nmol.items()},
        ntp_remaining_mm=ntp_remaining_mm,
        ntp_incorporation_percent=ntp_incorporation_pct,
        overall_efficiency_percent=overall_eff,
        pyrophosphate_released_nmol=round(ppi_released_nmol, 2),
        pyrophosphate_released_ug=round(ppi_released_ug, 2),
        transcript_turnover_ratio=turnover,
        free_mg_initial_mm=round(free_mg_initial, 2),
        promoter_detected=promoter_name,
        promoter_trimmed_nt=trimmed_nt,
        added_5prime_gs=added_gs,
        initiation_efficiency_rating=init_eval.efficiency_rating,
        initiation_recommendations=init_eval.recommendations,
        warnings=warnings,
        cap_analog=cap_name,
        predicted_capping_efficiency_percent=capping_eff,
        modified_ntp=mod_desc,
        modified_mw=mw if (mod_delta_mw > 0 or cap_delta_mw > 0) else None,
        recommended_incubation_hours=time_res.recommended_time_hours,
        protons_released_nmol=protons_nmol,
        buffer_recommendation=buf_rec,
        hepes_vs_tris_comparison=comp_summary,
        end_5=end_5,
        end_3=end_3,
        backbone=backbone,
    )
