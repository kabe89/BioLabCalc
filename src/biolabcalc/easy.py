"""Convenience module providing simple, one-line entry points for everyday wet-lab calculations.

Designed for maximum user-friendliness, forgiving input types, and intuitive defaults.
Accepts raw numbers or human-readable strings with units (e.g. '500 uL', '25 mM', '1.5 ug').
"""

from __future__ import annotations
import os
from typing import Union, Optional, Dict, Any, List
from .units import UnitParser
from .molecular_weight import calculate_dna_mw, calculate_rna_mw, calculate_protein_mw
from .transcription import calculate_ivt_yield, optimize_transcription_time
from .pcr import calculate_pcr_kinetics, build_master_mix, optimize_pcr_protocol
from .primers import analyze_primer
from .protein import quantify_protein_a280, quantify_protein_a205, calculate_extinction_coefficient
from .spectroscopy import prepare_standard_solution
from .cloning import plan_restriction_digest, calculate_ligation, calculate_gibson_assembly, calculate_golden_gate_assembly, are_overhangs_compatible
from .buffers import calculate_buffer_recipe, calculate_ntp_ph_adjustment, calculate_tris_temperature_shift, calculate_hepes_ivt_buffer, create_custom_buffer, CustomBufferBuilder
from .precipitation import calculate_precipitation, calculate_phenol_chloroform_extraction
from .spectroscopy import prepare_standard_solution, assess_nanodrop_purity
from .ecoli_growth import calculate_ecoli_growth, calculate_inoculation_volume
from .protocols import get_protocol, list_protocols
from .lab_report import new_lab_report, get_active_report, record_measurement, LabReport
from .western_blot import plan_western_blot, calculate_transfer_conditions, calculate_lysate_loading, calculate_antibody_dilution, troubleshoot_western_blot


def dilute(
    c1: Optional[Union[str, float]] = None,
    v1: Optional[Union[str, float]] = None,
    c2: Optional[Union[str, float]] = None,
    v2: Optional[Union[str, float]] = None,
) -> Dict[str, float]:
    """Solve the universal dilution equation C1 * V1 = C2 * V2 for any single missing variable.

    Provide any three parameters to solve for the fourth.
    Supports numbers or strings with units (e.g., c1='100 mM', c2='25 mM', v2='16 mL').
    """
    vals = [c1, v1, c2, v2]
    missing = [i for i, v in enumerate(vals) if v is None]
    if len(missing) != 1:
        raise ValueError(f"Exactly one parameter must be None to solve C1*V1 = C2*V2 (found {len(missing)} missing).")

    # If strings with units are provided, normalize
    # Parse concentrations to mM, volumes to uL
    c1_num = UnitParser.parse_concentration(c1, "mm") if c1 is not None else None
    c2_num = UnitParser.parse_concentration(c2, "mm") if c2 is not None else None
    v1_num = UnitParser.parse_volume(v1, "ul") if v1 is not None else None
    v2_num = UnitParser.parse_volume(v2, "ul") if v2 is not None else None

    idx = missing[0]
    if idx == 0:  # solve c1 = (c2 * v2) / v1
        res = (c2_num * v2_num) / v1_num
        return {"c1": round(res, 4), "v1": v1_num, "c2": c2_num, "v2": v2_num, "diluent_needed": round(v2_num - v1_num, 4)}
    elif idx == 1:  # solve v1 = (c2 * v2) / c1
        res = (c2_num * v2_num) / c1_num
        return {"c1": c1_num, "v1": round(res, 4), "c2": c2_num, "v2": v2_num, "diluent_needed": round(v2_num - res, 4)}
    elif idx == 2:  # solve c2 = (c1 * v1) / v2
        res = (c1_num * v1_num) / v2_num
        return {"c1": c1_num, "v1": v1_num, "c2": round(res, 4), "v2": v2_num, "diluent_needed": round(v2_num - v1_num, 4)}
    else:  # solve v2 = (c1 * v1) / c2
        res = (c1_num * v1_num) / c2_num
        return {"c1": c1_num, "v1": v1_num, "c2": c2_num, "v2": round(res, 4), "diluent_needed": round(res - v1_num, 4)}


def ntp_mix(
    initial_volume: Union[str, float] = "4.0 mL",
    initial_conc: Union[str, float] = "100.0 mM",
    target_volume: Union[str, float] = "16.0 mL",
    target_conc: Optional[Union[str, float]] = "25.0 mM",
    target_ph: float = 7.5,
    starting_form: str = "disodium_salt",
    species: str = "equimolar_mix",
    naoh_stock: Union[str, float] = "5.0 M",
) -> Any:
    """Convenience helper for preparing and neutralizing NTP working solutions."""
    v1_ml = UnitParser.parse_volume(initial_volume, "ml")
    c1_mm = UnitParser.parse_concentration(initial_conc, "mm")
    v2_ml = UnitParser.parse_volume(target_volume, "ml")
    c2_mm = UnitParser.parse_concentration(target_conc, "mm") if target_conc is not None else None
    base_m = UnitParser.parse_concentration(naoh_stock, "m")

    return calculate_ntp_ph_adjustment(
        initial_volume_ml=v1_ml,
        initial_conc_mm=c1_mm,
        target_volume_ml=v2_ml,
        target_conc_mm=c2_mm,
        target_ph=target_ph,
        starting_form=starting_form,
        ntp_species=species,
        naoh_stock_m=base_m,
    )


def primer(sequence: str, primer_conc: Union[str, float] = "400 nM", mg_conc: Union[str, float] = "1.5 mM") -> Any:
    """Analyze a single PCR primer (Tm, GC%, hairpin, self-dimer)."""
    p_nm = UnitParser.parse_concentration(primer_conc, "nm")
    mg_mm = UnitParser.parse_concentration(mg_conc, "mm")
    return analyze_primer(sequence, primer_conc_nm=p_nm, mg_conc_mm=mg_mm)


def ivt(
    rna_sequence: str,
    reaction_volume: Union[str, float] = "20 uL",
    measured_yield: Optional[Union[str, float]] = None,
    target_yield: Optional[Union[str, float]] = "50 ug",
) -> Any:
    """Calculate in vitro transcription yield, NTP stoichiometry, and efficiency."""
    vol_ul = UnitParser.parse_volume(reaction_volume, "ul")
    meas_ug = UnitParser.parse_mass(measured_yield, "ug") if measured_yield is not None else None
    tgt_ug = UnitParser.parse_mass(target_yield, "ug") if target_yield is not None else None

    return calculate_ivt_yield(
        rna_seq=rna_sequence,
        reaction_volume_ul=vol_ul,
        measured_yield_ug=meas_ug,
        target_yield_ug=tgt_ug,
    )


def buffer(name: str, volume: Union[str, float] = "1000 mL") -> Any:
    """Calculate scaled chemical recipe for common laboratory buffers."""
    vol_ml = UnitParser.parse_volume(volume, "ml")
    return calculate_buffer_recipe(name, target_volume_ml=vol_ml)


def golden_gate(
    vector_bp: int,
    insert_bps: List[int],
    target_fmol: float = 20.0,
    enzyme: str = "BsaI-HFv2",
    ratio: float = 2.0,
) -> Any:
    """Convenience one-liner for Golden Gate Assembly reaction design."""
    return calculate_golden_gate_assembly(
        vector_length_bp=vector_bp,
        insert_lengths_bp=insert_bps,
        target_vector_fmol=target_fmol,
        insert_to_vector_ratio=ratio,
        type_iis_enzyme=enzyme,
    )


def phenol_chloroform(
    sample_volume: Union[str, float],
    nucleic_acid: str = "rna",
    phenol_ph: Optional[float] = None,
) -> Any:
    """Convenience helper for Phenol:Chloroform phase separation and extraction."""
    vol_ul = UnitParser.parse_volume(sample_volume, "ul")
    return calculate_phenol_chloroform_extraction(
        sample_volume_ul=vol_ul,
        nucleic_acid=nucleic_acid,
        phenol_ph=phenol_ph,
    )


def nanodrop_purity(
    a260: float,
    a280: float,
    a230: float,
    sample_type: str = "rna",
) -> Any:
    """Assess nucleic acid purity and contaminant signatures from NanoDrop readings."""
    return assess_nanodrop_purity(a260=a260, a280=a280, a230=a230, sample_type=sample_type)


def hepes_buffer(
    volume: Union[str, float] = "50 mL",
    stock: int = 10,
    target_ph: float = 7.50,
) -> Any:
    """Calculate recipe for 10X (or 5X) HEPES-KOH IVT reaction buffer with temperature compensation."""
    vol_ml = UnitParser.parse_volume(volume, "ml")
    return calculate_hepes_ivt_buffer(
        target_volume_ml=vol_ml,
        stock_multiplier=stock,
        target_ph_37c=target_ph,
    )


def ivt_time(
    length_nt: int,
    temp_c: float = 37.0,
    ipp: bool = True,
) -> Any:
    """Calculate optimal in vitro transcription incubation time and kinetic profile."""
    return optimize_transcription_time(
        transcript_length_nt=length_nt,
        temperature_celsius=temp_c,
        use_pyrophosphatase=ipp,
    )


def rna_mw(
    sequence: str,
    end_5: str = "triphosphate",
    end_3: str = "hydroxyl",
    backbone: str = "monophosphate",
) -> Any:
    """Calculate RNA molecular weight with customized 5', 3', and backbone chemistries."""
    return calculate_rna_mw(
        seq=sequence,
        end_5=end_5,
        end_3=end_3,
        backbone=backbone,
    )


def western(
    protein_name: str,
    mw_kda: float,
    is_phospho: bool = False,
    is_membrane: bool = False,
    transfer: str = "wet_tank",
    membrane: str = "pvdf",
) -> Any:
    """Plan a complete Western blot experiment (gel %, transfer conditions, sample prep, antibody volumes)."""
    return plan_western_blot(
        target_protein_name=protein_name,
        target_mw_kda=mw_kda,
        is_phospho_target=is_phospho,
        is_membrane_protein=is_membrane,
        transfer_system=transfer,
        membrane_type=membrane,
    )


def wb_transfer(
    mw_kda: float,
    system: str = "wet_tank",
    membrane: str = "pvdf",
) -> Any:
    """Calculate optimal transfer buffer, voltage, duration, and membrane pore size for a given MW."""
    return calculate_transfer_conditions(
        target_mw_kda=mw_kda,
        transfer_system=system,
        membrane_type=membrane,
    )


def wb_loading(
    lysate_conc: Union[str, float] = "2.5 mg/mL",
    target_ug: float = 20.0,
    num_lanes: int = 10,
    is_membrane: bool = False,
) -> Any:
    """Calculate lysate loading volume, sample buffer recipe, and denaturation temperature."""
    c_num = UnitParser.parse_concentration(lysate_conc, "mg/ml") if isinstance(lysate_conc, str) else lysate_conc
    return calculate_lysate_loading(
        lysate_conc_mg_ml=c_num,
        target_protein_ug_per_lane=target_ug,
        num_lanes=num_lanes,
        is_membrane_protein=is_membrane,
    )


def wb_troubleshoot(symptom: str) -> Any:
    """Diagnose Western blot artifacts, causes, and corrective actions (e.g. 'no_signal', 'ghost_bands')."""
    return troubleshoot_western_blot(symptom)


def new_report(
    title: str = "Laboratory Experiment Report",
    experimenter: str = "Researcher",
    project: str = "General",
    objective: str = "",
) -> LabReport:
    """Start a fresh electronic laboratory report session."""
    return new_lab_report(title=title, experimenter=experimenter, project=project, objective=objective)


def record(
    sample_id: str,
    parameter: str,
    value: float,
    unit: str,
    target: Optional[float] = None,
    tolerance_pct: Optional[float] = None,
    notes: str = "",
) -> Any:
    """Record an experimental measurement into the active lab report with optional target & QC evaluation."""
    return record_measurement(
        sample_id=sample_id,
        parameter=parameter,
        value=value,
        unit=unit,
        target=target,
        tolerance_pct=tolerance_pct,
        notes=notes,
    )


def export_report(filepath: str, title: Optional[str] = None) -> str:
    """Export the active lab report to Markdown (.md), Excel (.xlsx), CSV (.csv), or JSON (.json)."""
    rep = get_active_report()
    if title:
        rep.title = title
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".xlsx":
        return rep.to_excel(filepath)
    elif ext == ".csv":
        return rep.to_csv(filepath)
    elif ext == ".json":
        return rep.to_json(filepath)
    else:  # Default to markdown
        return rep.to_markdown(filepath)


def custom_buffer(
    name: str,
    components: List[Dict[str, Any]],
    ph: str = "7.5",
    volume: Union[str, float] = "1000 mL",
    save: bool = False,
) -> Any:
    """Quickly design, scale, and optionally save a custom laboratory buffer."""
    vol_ml = UnitParser.parse_volume(volume, "ml")
    return create_custom_buffer(
        name=name,
        components=components,
        ph=ph,
        target_volume_ml=vol_ml,
        save_to_disk=save,
    )


def buffer_builder(
    name: str,
    ph: str = "7.5",
    storage: str = "Room temperature or 4°C",
    safety: Optional[str] = None,
) -> CustomBufferBuilder:
    """Instantiate a fluent CustomBufferBuilder for constructing custom buffer recipes."""
    return CustomBufferBuilder(name=name, ph=ph, storage=storage, safety=safety)
