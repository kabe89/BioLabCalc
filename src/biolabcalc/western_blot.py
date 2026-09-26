"""Western blotting experimental design, transfer conditions, antibody stoichiometry, and troubleshooting."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Literal


@dataclass(frozen=True)
class TransferConditionsResult:
    target_mw_kda: float
    transfer_system: str
    membrane_type: str
    pore_size_um: float
    activation_required: bool
    activation_instructions: str
    transfer_buffer_name: str
    transfer_buffer_recipe: Dict[str, str]
    voltage_or_current: str
    duration_minutes: int
    temperature_conditions: str
    expert_tips: List[str]


@dataclass(frozen=True)
class LysateLoadingResult:
    lysate_conc_mg_ml: float
    target_protein_ug_per_lane: float
    num_lanes: int
    lysate_volume_per_lane_ul: float
    sample_buffer_volume_per_lane_ul: float
    reducing_agent_volume_ul: float
    diluent_volume_ul: float
    total_volume_per_lane_ul: float
    master_mix_recipe: Dict[str, float]
    denaturation_temperature_celsius: int
    denaturation_time_minutes: int
    normalization_recommendation: str
    notes: List[str]


@dataclass(frozen=True)
class AntibodyDilutionResult:
    membrane_area_cm2: float
    incubation_volume_ml: float
    blocking_agent: str
    blocking_buffer_recipe: str
    primary_antibody_dilution: str
    primary_antibody_volume_ul: float
    primary_incubation: str
    secondary_antibody_dilution: str
    secondary_antibody_volume_ul: float
    secondary_incubation: str
    wash_buffer: str
    wash_schedule: str
    compatibility_warnings: List[str]


@dataclass(frozen=True)
class WesternBlotPlanResult:
    target_protein_name: str
    target_mw_kda: float
    recommended_gel_percentage: str
    running_conditions: str
    transfer_setup: TransferConditionsResult
    sample_prep: LysateLoadingResult
    immunodetection: AntibodyDilutionResult
    detection_substrate: str
    imaging_guidelines: str
    critical_checkpoints: List[str]


@dataclass(frozen=True)
class WesternTroubleshootingResult:
    symptom: str
    likely_causes: List[str]
    corrective_actions: List[str]
    preventative_protocol: str


TROUBLESHOOTING_DATABASE: Dict[str, WesternTroubleshootingResult] = {
    "no_signal": WesternTroubleshootingResult(
        symptom="No bands visible across the entire blot (including positive control and ladder)",
        likely_causes=[
            "Reversed transfer polarity: anode (+) and cathode (-) swapped; negatively charged proteins transferred into buffer tank instead of onto membrane.",
            "Sodium azide (NaN3) present in wash or antibody buffer: azide irreversibly inhibits HRP enzyme activity.",
            "PVDF membrane was not pre-activated in 100% methanol, preventing hydrophobic protein binding.",
            "Primary and secondary antibody species mismatch (e.g. rabbit primary with anti-mouse secondary).",
            "Proteins blew through membrane due to excessive transfer time, voltage, or oversized pore size (0.45 µm instead of 0.2 µm for small proteins).",
        ],
        corrective_actions=[
            "Verify transfer electrode polarity: Negative (black/cathode) -> Gel -> Membrane -> Positive (red/anode).",
            "Prepare fresh wash and antibody buffers without sodium azide (use ProClin or thimerosal if preservative needed).",
            "Always activate PVDF in 100% methanol for 1–2 min before equilibrating in transfer buffer.",
            "Confirm host species of secondary antibody precisely matches primary host (e.g. Goat anti-Rabbit for Rabbit IgG).",
            "Stain membrane with Ponceau S immediately post-transfer to verify successful protein transfer before blocking.",
        ],
        preventative_protocol="Include a pre-stained protein ladder and a validated positive control lane on every gel.",
    ),
    "high_background": WesternTroubleshootingResult(
        symptom="Uniform or patchy dark background obscuring bands",
        likely_causes=[
            "Milk blocking agent used with phospho-specific antibodies: casein in milk is heavily phosphorylated.",
            "Milk blocking agent used with biotin/streptavidin detection: milk contains endogenous biotin.",
            "Secondary antibody concentration too high (e.g. 1:1,000 instead of 1:10,000).",
            "Membrane allowed to dry out between wash or antibody incubation steps.",
            "Insufficient washing after primary or secondary antibody incubation.",
        ],
        corrective_actions=[
            "Switch to 5% BSA in TBST for phospho-specific antibodies or biotin-streptavidin systems.",
            "Titrate secondary antibody down to 1:5,000 or 1:10,000.",
            "Ensure membrane is fully submerged in wash buffer on an orbital shaker at all times.",
            "Perform at least 4 × 5 min washes with TBST (0.1% Tween-20) under vigorous shaking post-antibody steps.",
        ],
        preventative_protocol="Use 5% BSA in TBST for phospho-targets; increase Tween-20 to 0.1% in TBS wash buffer.",
    ),
    "ghost_bands": WesternTroubleshootingResult(
        symptom="White bands surrounded by dark halos ('ghost bands' or substrate burnout)",
        likely_causes=[
            "Excessive target protein loading or ultra-high HRP activity rapidly depleting ECL substrate at band location.",
            "ECL substrate burnout caused by high-sensitivity femtogram ECL reagent on an abundant protein.",
        ],
        corrective_actions=[
            "Reduce protein loading from 30–50 µg down to 5–10 µg per lane.",
            "Dilute secondary antibody 5-fold (e.g. from 1:2,000 to 1:10,000).",
            "Switch from ultra-sensitive ECL (Femto) to standard ECL (Pico / Clarity).",
        ],
        preventative_protocol="Avoid high-sensitivity femto ECL substrates for high-abundance proteins like actin, tubulin, or GAPDH.",
    ),
    "membrane_protein_aggregates": WesternTroubleshootingResult(
        symptom="Target protein remains trapped in well or forms high-MW smear at top of resolving gel",
        likely_causes=[
            "Multi-pass transmembrane proteins (e.g. AMPA/kainate receptors, GPCRs, ion channels, transporters) boiled at 95°C.",
            "Hydrophobic transmembrane helices denature into irreversible aggregates upon high-temperature boiling in SDS.",
        ],
        corrective_actions=[
            "Do NOT boil at 95°C! Incubate samples at 65°C–70°C for 10–15 minutes instead.",
            "Include 8 M urea in sample buffer if aggregates persist.",
            "Use freshly prepared DTT (100 mM final) or 5% beta-mercaptoethanol.",
        ],
        preventative_protocol="For all multi-pass transmembrane proteins, heat at 65°C–70°C for 10 min; never heat to 95°C–100°C.",
    ),
    "patchy_transfer": WesternTroubleshootingResult(
        symptom="Uneven transfer, blank spots, or swirl patterns on the membrane",
        likely_causes=[
            "Air bubbles trapped between polyacrylamide gel and transfer membrane during cassette assembly.",
            "Uneven cassette clamping pressure or worn transfer sponges.",
        ],
        corrective_actions=[
            "Roll out the sandwich gently with a glass pipette or blot roller in transfer buffer to expel all bubbles.",
            "Replace thin/compressed transfer sponges to ensure tight sandwich compression.",
            "Pre-equilibrate gel and membrane in transfer buffer for 10–15 min prior to assembly to prevent swelling during run.",
        ],
        preventative_protocol="Assemble transfer sandwich submerged in transfer buffer and roll out bubbles with uniform pressure.",
    ),
}


def calculate_transfer_conditions(
    target_mw_kda: float,
    transfer_system: Literal["wet_tank", "semi_dry", "fast_semi_dry"] = "wet_tank",
    membrane_type: Literal["pvdf", "nitrocellulose"] = "pvdf",
    gel_thickness_mm: float = 1.0,
) -> TransferConditionsResult:
    """Calculate optimal Western blot electrotransfer buffer, voltage, duration, and membrane parameters.

    Accounts for target molecular weight mobilization kinetics, SDS/methanol stoichiometry,
    pore size selection, and thermal management.

    Parameters
    ----------
    target_mw_kda : float
        Molecular weight of target protein in kDa.
    transfer_system : {'wet_tank', 'semi_dry', 'fast_semi_dry'}
        Electrotransfer apparatus type.
    membrane_type : {'pvdf', 'nitrocellulose'}
        Transfer membrane material.
    gel_thickness_mm : float
        Thickness of SDS-PAGE gel (default: 1.0 mm).
    """
    if target_mw_kda <= 0:
        raise ValueError("Target molecular weight must be positive.")

    # Pore size selection: < 20 kDa proteins require 0.2 µm to prevent blow-through
    pore_size = 0.2 if target_mw_kda < 25.0 else 0.45

    # PVDF vs Nitrocellulose activation
    is_pvdf = membrane_type.lower() == "pvdf"
    if is_pvdf:
        act_req = True
        act_inst = "Pre-wet in 100% methanol for 1–2 minutes, rinse in deionized water for 2 min, then equilibrate in 1X Transfer Buffer for ≥ 5 min."
    else:
        act_req = False
        act_inst = "Equilibrate directly in 1X Transfer Buffer for ≥ 10 minutes. Do NOT expose nitrocellulose to pure methanol."

    # Buffer formulation and stoichiometry: Towbin formulation customized to MW
    tips: List[str] = []
    if target_mw_kda >= 100.0:
        buf_name = "Towbin Transfer Buffer (High-MW Formulation: 10% MeOH + 0.05% SDS)"
        recipe = {
            "Tris base": "25 mM (3.03 g/L)",
            "Glycine": "192 mM (14.4 g/L)",
            "Methanol": "10% v/v (100 mL/L)",
            "SDS (Sodium Dodecyl Sulfate)": "0.05% w/v (0.5 g/L)",
            "pH": "8.3 (do NOT adjust with acid/base)",
        }
        tips.append("Methanol reduced to 10% to prevent polyacrylamide pore shrinkage during transfer.")
        tips.append("Trace SDS (0.05%) added to maintain net negative charge on large proteins and promote elution.")
        if transfer_system in ("semi_dry", "fast_semi_dry"):
            tips.append("WARNING: High-MW proteins (>100 kDa) transfer with poor efficiency in semi-dry systems. Wet tank transfer is strongly advised.")
    elif target_mw_kda < 25.0:
        buf_name = "Towbin Transfer Buffer (Low-MW Formulation: 20–25% MeOH, No SDS)"
        recipe = {
            "Tris base": "25 mM (3.03 g/L)",
            "Glycine": "192 mM (14.4 g/L)",
            "Methanol": "20% v/v (200 mL/L)",
            "SDS": "0.0% (omitted)",
            "pH": "8.3 (do NOT adjust)",
        }
        tips.append("SDS omitted and methanol maintained at 20% to strip SDS and maximize hydrophobic membrane retention.")
        tips.append("Use 0.2 µm pore membrane to prevent small protein 'blow-through' across the membrane.")
    else:
        buf_name = "Standard Towbin Transfer Buffer (20% MeOH, No SDS)"
        recipe = {
            "Tris base": "25 mM (3.03 g/L)",
            "Glycine": "192 mM (14.4 g/L)",
            "Methanol": "20% v/v (200 mL/L)",
            "SDS": "0.0% (omitted)",
            "pH": "8.3 (do NOT adjust)",
        }
        tips.append("Standard Towbin buffer suitable for proteins between 25 and 100 kDa.")

    # Voltage, current, duration, and temperature by system
    if transfer_system == "wet_tank":
        if target_mw_kda >= 120.0:
            volt_curr = "100 V constant (or 350 mA)"
            duration = 90
            temp_cond = "4°C cold room with magnetic stirrer and internal frozen ice block (prevent buffer overheating)."
            tips.append("Overnight alternative: 30 V constant for 14–16 hours at 4°C provides superior transfer for >150 kDa.")
        elif target_mw_kda < 25.0:
            volt_curr = "100 V constant"
            duration = 45
            temp_cond = "4°C cold room with ice block (short duration prevents blow-through)."
        else:
            volt_curr = "100 V constant"
            duration = 60
            temp_cond = "4°C cold room or room temp with ice block and stirring."
    elif transfer_system == "semi_dry":
        if target_mw_kda >= 100.0:
            volt_curr = "25 V constant (limit 2.0 mA/cm²)"
            duration = 45
            temp_cond = "Room temperature; monitor sandwich for overheating/drying."
        else:
            volt_curr = "15–20 V constant (1.5 mA/cm²)"
            duration = 25
            temp_cond = "Room temperature."
    else:  # fast_semi_dry (e.g. Trans-Blot Turbo)
        volt_curr = "2.5 A constant, up to 25 V"
        duration = 7 if target_mw_kda >= 80.0 else 5
        temp_cond = "Automated protocol inside rapid semi-dry cassette."

    return TransferConditionsResult(
        target_mw_kda=target_mw_kda,
        transfer_system=transfer_system,
        membrane_type=membrane_type.upper(),
        pore_size_um=pore_size,
        activation_required=act_req,
        activation_instructions=act_inst,
        transfer_buffer_name=buf_name,
        transfer_buffer_recipe=recipe,
        voltage_or_current=volt_curr,
        duration_minutes=duration,
        temperature_conditions=temp_cond,
        expert_tips=tips,
    )


def calculate_lysate_loading(
    lysate_conc_mg_ml: float,
    target_protein_ug_per_lane: float = 20.0,
    num_lanes: int = 10,
    sample_buffer_conc: int = 4,
    dtt_final_mm: float = 100.0,
    max_well_volume_ul: float = 30.0,
    is_membrane_protein: bool = False,
) -> LysateLoadingResult:
    """Calculate pipetting volumes, sample buffer dilution, and denaturation conditions for Western blot lysate loading.

    Parameters
    ----------
    lysate_conc_mg_ml : float
        Total protein concentration of cell/tissue lysate determined by BCA or Bradford assay (mg/mL = µg/µL).
    target_protein_ug_per_lane : float
        Target mass of protein to load per lane in µg (default: 20 µg; typical range: 10–30 µg).
    num_lanes : int
        Number of lanes/wells to prepare (default: 10).
    sample_buffer_conc : int
        Concentration of Laemmli sample buffer stock (4 for 4X, 2 for 2X, 6 for 6X).
    dtt_final_mm : float
        Target concentration of reducing agent DTT in 1X sample (default: 100.0 mM).
    max_well_volume_ul : float
        Maximum capacity of gel wells in µL (default: 30 µL).
    is_membrane_protein : bool
        Whether target is a multi-pass transmembrane protein (e.g. GluK2, AMPA receptors, GPCRs).
    """
    if lysate_conc_mg_ml <= 0:
        raise ValueError("Lysate concentration must be positive.")
    if target_protein_ug_per_lane <= 0:
        raise ValueError("Target protein loading must be positive.")
    if num_lanes <= 0:
        raise ValueError("Number of lanes must be positive.")

    # Volume of lysate containing target_protein_ug: V = mass / conc
    v_lysate_per_lane = target_protein_ug_per_lane / lysate_conc_mg_ml

    # Standardize lane volume to 20 µL (or appropriate scaled volume)
    target_total_vol = max(15.0, round(v_lysate_per_lane * (sample_buffer_conc / (sample_buffer_conc - 1)) + 5.0, 1))
    target_total_vol = min(target_total_vol, max_well_volume_ul)

    v_sb_per_lane = target_total_vol / sample_buffer_conc

    if v_lysate_per_lane + v_sb_per_lane > target_total_vol:
        target_total_vol = round(v_lysate_per_lane + v_sb_per_lane, 1)

    if target_total_vol > max_well_volume_ul:
        raise ValueError(
            f"Required lysate ({v_lysate_per_lane:.1f} µL) + sample buffer ({v_sb_per_lane:.1f} µL) = {target_total_vol:.1f} µL, "
            f"exceeding well capacity ({max_well_volume_ul:.1f} µL). Concentrate lysate via centrifugal filter."
        )

    v_diluent_per_lane = max(0.0, round(target_total_vol - v_lysate_per_lane - v_sb_per_lane, 2))

    # Master mix scaling factor (prepare for N + 1.5 lanes to account for pipetting loss)
    prep_factor = num_lanes + 1.5
    mm_recipe = {
        "Total Lysate": round(v_lysate_per_lane * prep_factor, 1),
        f"{sample_buffer_conc}X Laemmli Buffer": round(v_sb_per_lane * prep_factor, 1),
        "Diluent (Lysis Buffer or Water)": round(v_diluent_per_lane * prep_factor, 1),
        "Total Master Mix Volume": round(target_total_vol * prep_factor, 1),
    }

    # Denaturation temperature based on structural biology of target
    notes = []
    if is_membrane_protein:
        denat_temp = 70
        denat_time = 10
        notes.append(
            "CRITICAL MEMBRANE PROTEIN PROTOCOL: Target is a transmembrane receptor. Denature at 65°C–70°C for 10 min. "
            "Do NOT boil at 95°C (boiling causes irreversible aggregation of hydrophobic transmembrane domains, trapping them in the well)."
        )
    else:
        denat_temp = 95
        denat_time = 5
        notes.append("Standard soluble protein denaturation: Heat at 95°C for 5 minutes (or 70°C for 10 min).")

    notes.append(f"Load {target_total_vol:.1f} µL per lane to deliver exactly {target_protein_ug_per_lane:.1f} µg total protein.")

    norm_rec = (
        "Normalization Guidance: Housekeeping proteins (β-actin, GAPDH, α-tubulin) often saturate above 10–15 µg lysate loading. "
        "For quantitative publication-grade Westerns, validate loading linearity or employ Total Protein Normalization (TPN) via Revert 700 or Ponceau S."
    )

    return LysateLoadingResult(
        lysate_conc_mg_ml=lysate_conc_mg_ml,
        target_protein_ug_per_lane=target_protein_ug_per_lane,
        num_lanes=num_lanes,
        lysate_volume_per_lane_ul=round(v_lysate_per_lane, 2),
        sample_buffer_volume_per_lane_ul=round(v_sb_per_lane, 2),
        reducing_agent_volume_ul=round(v_sb_per_lane * 0.1, 2),
        diluent_volume_ul=v_diluent_per_lane,
        total_volume_per_lane_ul=round(target_total_vol, 1),
        master_mix_recipe=mm_recipe,
        denaturation_temperature_celsius=denat_temp,
        denaturation_time_minutes=denat_time,
        normalization_recommendation=norm_rec,
        notes=notes,
    )


def calculate_antibody_dilution(
    membrane_area_cm2: float = 56.0,
    primary_dilution_factor: int = 1000,
    secondary_dilution_factor: int = 5000,
    is_phospho_target: bool = False,
    detection_method: Literal["hrp_ecl", "fluorescence", "biotin_streptavidin"] = "hrp_ecl",
) -> AntibodyDilutionResult:
    """Calculate antibody volumes, blocking agent compatibility, and washing protocols for Western blot immunodetection.

    Parameters
    ----------
    membrane_area_cm2 : float
        Surface area of the transfer membrane in cm² (default: 56.0 cm² for standard 8x7 cm mini-gel).
    primary_dilution_factor : int
        Dilution ratio for primary antibody (e.g. 1000 for 1:1,000).
    secondary_dilution_factor : int
        Dilution ratio for secondary antibody (e.g. 5000 for 1:5,000).
    is_phospho_target : bool
        Whether the antibody detects phosphorylated residues (e.g. p-Ser, p-Thr, p-Tyr).
    detection_method : {'hrp_ecl', 'fluorescence', 'biotin_streptavidin'}
        Detection technology.
    """
    if membrane_area_cm2 <= 0:
        raise ValueError("Membrane area must be positive.")

    # Incubation volume: ~0.10–0.15 mL per cm² of membrane (minimum 5 mL for mini blot)
    vol_ml = max(5.0, round(membrane_area_cm2 * 0.12, 1))

    v_primary_ul = round((vol_ml * 1000.0) / primary_dilution_factor, 2)
    v_secondary_ul = round((vol_ml * 1000.0) / secondary_dilution_factor, 2)

    warnings: List[str] = []

    # Blocking agent compatibility checks
    if is_phospho_target:
        block_agent = "5% BSA (Bovine Serum Albumin) in 1X TBST"
        block_recipe = "Dissolve 2.5 g BSA in 50 mL 1X TBST (Tris-Buffered Saline + 0.1% Tween-20)."
        warnings.append(
            "PHOSPHO-TARGET RULE: Non-fat dry milk is STRICTLY FORBIDDEN. Milk contains abundant phosphoproteins (casein) "
            "that cross-react with phospho-antibodies, creating intense non-specific background or quenching the signal. Use 5% BSA."
        )
    elif detection_method == "biotin_streptavidin":
        block_agent = "5% BSA or 1% Fish Gelatin in 1X TBST"
        block_recipe = "Dissolve 2.5 g BSA in 50 mL 1X TBST."
        warnings.append("Milk contains endogenous free biotin that binds streptavidin. Use 5% BSA.")
    elif detection_method == "fluorescence":
        block_agent = "Commercial Fluorescent Blocker or 5% BSA in 1X TBS (omit Tween in blocking step)"
        block_recipe = "5% BSA in 1X TBS without Tween-20 (Tween can increase fluorescent membrane autofluorescence)."
        warnings.append("Low-fluorescence PVDF membrane (Immobilin-FL) is required to prevent background autofluorescence.")
    else:
        block_agent = "5% Non-Fat Dry Milk in 1X TBST"
        block_recipe = "Dissolve 2.5 g non-fat dry milk in 50 mL 1X TBST."

    # Sodium azide hazard with HRP
    if detection_method == "hrp_ecl":
        warnings.append(
            "HRP ENZYME HAZARD: Never add Sodium Azide (NaN3) to HRP-conjugated secondary antibodies or wash buffers. "
            "Azide irreversibly coordinates the heme iron in HRP, permanently abolishing peroxidase activity."
        )

    wash_buf = "1X TBST (20 mM Tris-HCl pH 7.6, 150 mM NaCl, 0.1% Tween-20)"
    wash_sched = "Wash 4 times for 5 minutes each with vigorous orbital shaking (~100 rpm) at room temperature."

    prim_inc = "Incubate overnight (14–16 h) at 4°C with gentle rocking (provides highest specificity and signal-to-noise ratio)."
    sec_inc = "Incubate for 1 hour at room temperature with gentle rocking, protected from light if fluorescent."

    return AntibodyDilutionResult(
        membrane_area_cm2=membrane_area_cm2,
        incubation_volume_ml=vol_ml,
        blocking_agent=block_agent,
        blocking_buffer_recipe=block_recipe,
        primary_antibody_dilution=f"1:{primary_dilution_factor:,}",
        primary_antibody_volume_ul=v_primary_ul,
        primary_incubation=prim_inc,
        secondary_antibody_dilution=f"1:{secondary_dilution_factor:,}",
        secondary_antibody_volume_ul=v_secondary_ul,
        secondary_incubation=sec_inc,
        wash_buffer=wash_buf,
        wash_schedule=wash_sched,
        compatibility_warnings=warnings,
    )


def plan_western_blot(
    target_protein_name: str,
    target_mw_kda: float,
    lysate_conc_mg_ml: float = 2.5,
    target_protein_ug_per_lane: float = 20.0,
    is_phospho_target: bool = False,
    is_membrane_protein: bool = False,
    transfer_system: Literal["wet_tank", "semi_dry", "fast_semi_dry"] = "wet_tank",
    membrane_type: Literal["pvdf", "nitrocellulose"] = "pvdf",
    detection_method: Literal["hrp_ecl", "fluorescence"] = "hrp_ecl",
    ecl_substrate_grade: Literal["standard_pico", "high_sensitivity_clarity", "ultra_femto"] = "high_sensitivity_clarity",
) -> WesternBlotPlanResult:
    """Generate a comprehensive, publication-grade Western blotting experiment plan.

    Covers SDS-PAGE resolution, lysate loading, Towbin transfer stoichiometry, antibody incubation,
    and chemiluminescent/fluorescent imaging.

    Parameters
    ----------
    target_protein_name : str
        Name of target biomarker or protein of interest (e.g. 'GluK2', 'Actin', 'p-ERK1/2').
    target_mw_kda : float
        Predicted or expected molecular weight in kDa.
    lysate_conc_mg_ml : float
        Lysate concentration determined by BCA/Bradford assay (mg/mL).
    target_protein_ug_per_lane : float
        Target total protein mass loaded per lane in µg (default: 20 µg).
    is_phospho_target : bool
        Whether detecting a phosphorylated epitope (enforces 5% BSA blocking).
    is_membrane_protein : bool
        Whether target is a transmembrane receptor (enforces 70°C non-boiling denaturation).
    transfer_system : {'wet_tank', 'semi_dry', 'fast_semi_dry'}
        Electrotransfer apparatus.
    membrane_type : {'pvdf', 'nitrocellulose'}
        Membrane polymer.
    detection_method : {'hrp_ecl', 'fluorescence'}
        Signal acquisition modality.
    ecl_substrate_grade : {'standard_pico', 'high_sensitivity_clarity', 'ultra_femto'}
        Sensitivity grade of ECL chemiluminescent substrate.
    """
    # 1. Gel percentage selection
    if target_mw_kda < 20.0:
        gel_pct = "15% Tris-Glycine SDS-PAGE (or 16.5% Tricine-PAGE for peptides <10 kDa)"
        run_cond = "80 V for 15 min through stacking gel; 130 V for 60 min through resolving gel."
    elif target_mw_kda < 50.0:
        gel_pct = "12% Tris-Glycine SDS-PAGE"
        run_cond = "80 V for 15 min through stacking gel; 120 V for 70 min through resolving gel."
    elif target_mw_kda < 100.0:
        gel_pct = "10% Tris-Glycine SDS-PAGE"
        run_cond = "80 V for 15 min through stacking gel; 120 V for 80 min through resolving gel."
    elif target_mw_kda < 200.0:
        gel_pct = "8% Tris-Glycine SDS-PAGE (or 4–12% Bis-Tris gradient gel)"
        run_cond = "80 V for 20 min; 100 V for 90–100 min (run cold at 4°C for high MW)."
    else:
        gel_pct = "6% Tris-Glycine SDS-PAGE (or 3–8% Tris-Acetate gel for >200 kDa)"
        run_cond = "70 V constant for 2.5–3 hours in cold room (4°C)."

    # 2. Transfer conditions
    transfer_res = calculate_transfer_conditions(
        target_mw_kda=target_mw_kda,
        transfer_system=transfer_system,
        membrane_type=membrane_type,
    )

    # 3. Lysate preparation
    sample_res = calculate_lysate_loading(
        lysate_conc_mg_ml=lysate_conc_mg_ml,
        target_protein_ug_per_lane=target_protein_ug_per_lane,
        is_membrane_protein=is_membrane_protein,
    )

    # 4. Antibody dilution and blocking
    ab_res = calculate_antibody_dilution(
        is_phospho_target=is_phospho_target,
        detection_method="hrp_ecl" if detection_method == "hrp_ecl" else "fluorescence",
    )

    # 5. Detection substrate and imaging
    if detection_method == "hrp_ecl":
        if ecl_substrate_grade == "ultra_femto":
            sub_name = "SuperSignal West Femto / Immobilon Western Chemiluminescent (Low Femtogram Sensitivity)"
            img_guide = "Femto substrate has rapid turnover. Image immediately in digital imager (auto-exposure) to avoid ghost bands."
        elif ecl_substrate_grade == "standard_pico":
            sub_name = "Standard ECL / Pierce ECL Western Blotting Substrate (Mid Picogram Sensitivity)"
            img_guide = "Signal duration ~1 hour. Ideal for high-abundance proteins (actin, tubulin, GAPDH)."
        else:
            sub_name = "Clarity Western ECL / SuperSignal West Pico Plus (Low Picogram Sensitivity)"
            img_guide = "Linear signal dynamic range >6 hours. Capture series of exposures (10s, 30s, 1m, 3m) using digital CCD imager."
    else:
        sub_name = "Near-Infrared Fluorescent Secondary Antibodies (IR_Dye 680RD / 800CW)"
        img_guide = "Scan on laser scanner (e.g. Odyssey CLx) at 700 nm and 800 nm channels simultaneously for multiplex normalization."

    checkpoints = [
        "1. Check protein loading parity across wells with pre-stained ladder and post-transfer Ponceau S staining.",
        "2. Ensure PVDF membrane activation in 100% methanol before transfer buffer equilibration.",
        "3. Confirm complete omission of sodium azide in all HRP antibody diluents.",
    ]
    if is_phospho_target:
        checkpoints.append("4. Verify 5% BSA blocking (do NOT use milk on phospho-blot).")
    if is_membrane_protein:
        checkpoints.append("5. Verify heating at 70°C for 10 min; do NOT boil at 95°C.")

    return WesternBlotPlanResult(
        target_protein_name=target_protein_name,
        target_mw_kda=target_mw_kda,
        recommended_gel_percentage=gel_pct,
        running_conditions=run_cond,
        transfer_setup=transfer_res,
        sample_prep=sample_res,
        immunodetection=ab_res,
        detection_substrate=sub_name,
        imaging_guidelines=img_guide,
        critical_checkpoints=checkpoints,
    )


def troubleshoot_western_blot(symptom_query: str) -> WesternTroubleshootingResult:
    """Look up diagnostic causes, actionable remedies, and preventative protocols for Western blot artifacts."""
    clean_q = symptom_query.lower().replace("-", "_").replace(" ", "_")

    if "no_signal" in clean_q or "blank" in clean_q or "white" in clean_q:
        return TROUBLESHOOTING_DATABASE["no_signal"]
    elif "background" in clean_q or "dark" in clean_q or "dirty" in clean_q:
        return TROUBLESHOOTING_DATABASE["high_background"]
    elif "ghost" in clean_q or "burnout" in clean_q or "hollow" in clean_q:
        return TROUBLESHOOTING_DATABASE["ghost_bands"]
    elif "membrane" in clean_q or "aggregate" in clean_q or "well" in clean_q or "smear" in clean_q:
        return TROUBLESHOOTING_DATABASE["membrane_protein_aggregates"]
    elif "patch" in clean_q or "bubble" in clean_q or "swirl" in clean_q:
        return TROUBLESHOOTING_DATABASE["patchy_transfer"]

    # Default to high background if generic
    for k, v in TROUBLESHOOTING_DATABASE.items():
        if k in clean_q:
            return v
    return TROUBLESHOOTING_DATABASE["no_signal"]
