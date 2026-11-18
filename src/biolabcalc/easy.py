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
from .cloning import plan_restriction_digest, calculate_ligation, calculate_gibson_assembly, calculate_golden_gate_assembly, are_overhangs_compatible
from .buffers import (
    calculate_buffer_recipe,
    calculate_ntp_ph_adjustment,
    calculate_tris_temperature_shift,
    calculate_hepes_ivt_buffer,
    create_custom_buffer,
    CustomBufferBuilder,
    solve_buffer_equilibrium,
    BufferEquilibriumResult,
)
from .aptamers import (
    evaluate_rna_hairpin_thermo,
    analyze_counter_selex,
    SecondaryStructureThermoResult,
    SELEXEnrichmentResult,
)
from .allostery import (
    trace_allosteric_paths,
    AllostericNetworkResult,
)
from .precipitation import calculate_precipitation, calculate_phenol_chloroform_extraction
from .spectroscopy import prepare_standard_solution, assess_nanodrop_purity
from .ecoli_growth import calculate_ecoli_growth, calculate_inoculation_volume
from .lab_report import new_lab_report, get_active_report, record_measurement, auto_record, LabReport
from .western_blot import plan_western_blot, calculate_transfer_conditions, calculate_lysate_loading, calculate_antibody_dilution, troubleshoot_western_blot
from .workflows import cloning_workflow as _cloning_workflow, ivt_workflow as _ivt_workflow, CloningWorkflowResult, IVTWorkflowResult
from .sequence_store import SequenceRecord, save_sequence, get_sequence
from .plasmid import PlasmidRecord, STANDARD_PLASMID_CATALOG, get_plasmid, parse_genbank
from .restriction_engine import RestrictionDigestPrediction, predict_restriction_digest
from .plasmid_engineering import EngineeredPlasmidResult, engineer_plasmid, optimize_codons
from .interactive_plasmid import render_plasmid_map_svg



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
    sample_id_or_result: Any,
    parameter: Optional[str] = None,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    target: Optional[float] = None,
    tolerance_pct: Optional[float] = None,
    notes: str = "",
    report: Optional[LabReport] = None,
    sample_id: str = "Sample-1",
) -> Any:
    """Record an experimental measurement or auto-record calculation results into the active lab report."""
    if parameter is not None and value is not None and unit is not None:
        return record_measurement(
            sample_id=str(sample_id_or_result),
            parameter=parameter,
            value=value,
            unit=unit,
            target=target,
            tolerance_pct=tolerance_pct,
            notes=notes,
        )
    return auto_record(sample_id_or_result, report=report, sample_id=sample_id, notes=notes)


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


def dna_mw(
    sequence: str,
    double_stranded: bool = True,
    end_5: str = "hydroxyl",
) -> Any:
    """Calculate molecular weight, GC content, and base counts for single- or double-stranded DNA."""
    return calculate_dna_mw(seq=sequence, double_stranded=double_stranded, end_5=end_5)


def protein_mw(
    sequence: str,
    oxidized_cysteines: int = 0,
) -> Any:
    """Calculate average and monoisotopic molecular weight for a protein/peptide sequence."""
    return calculate_protein_mw(seq=sequence, oxidized_cysteines=oxidized_cysteines)


def pcr(
    amplicon_bp: int,
    template_ng: Union[str, float] = 5.0,
    cycles: int = 30,
    efficiency: float = 0.98,
    volume: Union[str, float] = "50 uL",
) -> Any:
    """Calculate PCR amplification kinetics, amplicon yield, and dNTP exhaustion."""
    tmpl_ng = UnitParser.parse_mass(template_ng, "ng")
    vol_ul = UnitParser.parse_volume(volume, "ul")
    return calculate_pcr_kinetics(
        amplicon_len_bp=amplicon_bp,
        template_ng=tmpl_ng,
        cycles=cycles,
        efficiency=efficiency,
        reaction_volume_ul=vol_ul,
    )


def digest(
    dna_mass_ug: Union[str, float] = 1.0,
    enzyme_1: str = "EcoRI",
    enzyme_2: Optional[str] = None,
    dna_conc_ng_ul: Optional[Union[str, float]] = 200.0,
    volume: Union[str, float] = "50 uL",
) -> Any:
    """Plan single or double restriction enzyme digestion setup with buffer compatibility."""
    mass_ug = UnitParser.parse_mass(dna_mass_ug, "ug")
    conc_ng_ul = UnitParser.parse_concentration(dna_conc_ng_ul, "ng/ul") if dna_conc_ng_ul else 200.0
    vol_ul = UnitParser.parse_volume(volume, "ul")
    return plan_restriction_digest(
        dna_mass_ug=mass_ug,
        reaction_volume_ul=vol_ul,
        enzyme_1=enzyme_1,
        enzyme_2=enzyme_2,
        dna_conc_ng_ul=conc_ng_ul,
    )


def ligation(
    vector_bp: int,
    insert_bp: int,
    vector_ng: Union[str, float] = "50 ng",
    molar_ratio: float = 3.0,
    volume: Union[str, float] = "20 uL",
) -> Any:
    """Calculate cohesive or blunt end T4 DNA ligation reaction stoichiometry."""
    v_ng = UnitParser.parse_mass(vector_ng, "ng")
    vol_ul = UnitParser.parse_volume(volume, "ul")
    return calculate_ligation(
        vector_length_bp=vector_bp,
        insert_length_bp=insert_bp,
        vector_mass_ng=v_ng,
        molar_ratio=molar_ratio,
        reaction_volume_ul=vol_ul,
    )


def gibson(
    vector_bp: int,
    insert_bps: Union[int, List[int]],
    vector_ng: Union[str, float] = "100 ng",
    molar_ratio: float = 2.0,
    volume: Union[str, float] = "20 uL",
) -> Any:
    """Plan isothermal Gibson Assembly reaction stoichiometry."""
    v_ng = UnitParser.parse_mass(vector_ng, "ng")
    inserts = [insert_bps] if isinstance(insert_bps, int) else list(insert_bps)
    vol_ul = UnitParser.parse_volume(volume, "ul")
    return calculate_gibson_assembly(
        vector_length_bp=vector_bp,
        insert_lengths_bp=inserts,
        vector_mass_ng=v_ng,
        molar_ratio=molar_ratio,
        reaction_volume_ul=vol_ul,
    )


def growth(
    starter_od600: float = 3.0,
    target_od600: float = 0.05,
    target_volume_ml: Union[str, float] = "500 mL",
) -> Dict[str, float]:
    """Calculate bacterial culture inoculation volume and required fresh media."""
    vol_ml = UnitParser.parse_volume(target_volume_ml, "ml")
    return calculate_inoculation_volume(
        starter_od600=starter_od600,
        target_volume_ml=vol_ml,
        target_od600=target_od600,
    )


def convert(
    val: Union[str, float, int],
    target_unit: str,
    mw: Optional[float] = None,
) -> float:
    """Universal laboratory unit and stoichiometry converter.

    Handles intra-domain conversions (volume, mass, moles, concentration)
    and cross-domain stoichiometry (mass <-> moles, molar <-> mass concentration)
    when molecular weight (mw) is provided.
    """
    num, unit = UnitParser._parse_raw(val)
    if not unit:
        raise ValueError(f"No unit specified on source value: '{val}'. Provide a string like '500 ng'.")
    u_src = unit.lower().replace("µ", "u")
    u_tgt = target_unit.lower().replace("µ", "u")

    # 1. Volume to Volume
    if u_src in UnitParser.VOLUME_FACTORS and u_tgt in UnitParser.VOLUME_FACTORS:
        return UnitParser.parse_volume(val, target_unit=u_tgt)

    # 2. Mass to Mass
    if u_src in UnitParser.MASS_FACTORS and u_tgt in UnitParser.MASS_FACTORS:
        return UnitParser.parse_mass(val, target_unit=u_tgt)

    # 3. Moles to Moles
    if u_src in UnitParser.MOLE_FACTORS and u_tgt in UnitParser.MOLE_FACTORS:
        return UnitParser.parse_moles(val, target_unit=u_tgt)

    # 4. Molar to Molar concentration
    if u_src in UnitParser.CONC_FACTORS and u_tgt in UnitParser.CONC_FACTORS:
        return UnitParser.parse_concentration(val, target_unit=u_tgt)

    # 5. Mass concentration to Mass concentration
    if u_src in UnitParser.MASS_CONC_FACTORS and u_tgt in UnitParser.MASS_CONC_FACTORS:
        return UnitParser.parse_concentration(val, target_unit=u_tgt)

    # Cross-domain conversions requiring MW
    if not mw or mw <= 0:
        raise ValueError(f"Cannot convert between '{unit}' and '{target_unit}' without molecular weight (mw).")

    # Mass -> Moles
    if u_src in UnitParser.MASS_FACTORS and u_tgt in UnitParser.MOLE_FACTORS:
        val_g = UnitParser.parse_mass(val, target_unit="g")
        moles = val_g / mw
        tgt_factor = UnitParser.MOLE_FACTORS[u_tgt]
        return round((moles * 1e9) / tgt_factor, 6)

    # Moles -> Mass
    if u_src in UnitParser.MOLE_FACTORS and u_tgt in UnitParser.MASS_FACTORS:
        val_mol = UnitParser.parse_moles(val, target_unit="mol")
        mass_g = val_mol * mw
        tgt_factor = UnitParser.MASS_FACTORS[u_tgt]
        return round((mass_g * 1e6) / tgt_factor, 6)

    # Molar concentration -> Mass concentration (e.g. uM -> ng/uL or mg/mL)
    if u_src in UnitParser.CONC_FACTORS and u_tgt in UnitParser.MASS_CONC_FACTORS:
        val_m = UnitParser.parse_concentration(val, target_unit="m")
        # 1 M = mw g/L = mw mg/mL
        val_mg_ml = val_m * mw
        tgt_factor = UnitParser.MASS_CONC_FACTORS[u_tgt]
        return round(val_mg_ml / tgt_factor, 6)

    # Mass concentration -> Molar concentration (e.g. ng/uL -> uM)
    if u_src in UnitParser.MASS_CONC_FACTORS and u_tgt in UnitParser.CONC_FACTORS:
        val_mg_ml = UnitParser.parse_concentration(val, target_unit="mg/ml")
        val_m = val_mg_ml / mw
        tgt_factor = UnitParser.CONC_FACTORS[u_tgt]
        return round((val_m * 1e3) / tgt_factor, 6)

    raise ValueError(f"Unsupported conversion between '{unit}' and '{target_unit}'.")


def batch_csv(
    input_path: str,
    output_path: str,
    delimiter: Optional[str] = None,
) -> Dict[str, Any]:
    """Process batch sequence list from CSV or TSV, calculating MW, GC%, and extinction coefficients."""
    from .batch_csv import process_batch_csv
    return process_batch_csv(input_path=input_path, output_path=output_path, delimiter=delimiter)


def rc(seq: str, seq_type: str = "dna") -> str:
    """Convenience shortcut for reverse complement of a DNA or RNA sequence."""
    from .seq_utils import reverse_complement
    return reverse_complement(seq, seq_type=seq_type)


def translate(seq: str, frame: int = 1, to_stop: bool = False) -> str:
    """Convenience shortcut for translating a DNA or RNA sequence."""
    from .seq_utils import translate_dna
    return translate_dna(seq, frame=frame, to_stop=to_stop)


def gc(seq: str) -> float:
    """Convenience shortcut for calculating GC percentage (0.0 to 100.0)."""
    from .seq_utils import calculate_gc_content
    return calculate_gc_content(seq)


def transcribe(seq: str) -> str:
    """Convenience shortcut for transcribing DNA sequence to RNA."""
    from .seq_utils import transcribe as _transcribe
    return _transcribe(seq)


def reverse_transcribe(seq: str) -> str:
    """Convenience shortcut for reverse transcribing RNA sequence to cDNA/DNA."""
    from .seq_utils import reverse_transcribe as _reverse_transcribe
    return _reverse_transcribe(seq)


def find_orfs(seq: str, min_aa: int = 30) -> List[Any]:
    """Convenience shortcut for identifying open reading frames (ORFs)."""
    from .seq_utils import find_orfs as _find_orfs
    return _find_orfs(seq, min_length_aa=min_aa)


def parse_fasta(text_or_path: str) -> List[Tuple[str, str]]:
    """Convenience shortcut for parsing FASTA text or file."""
    from .seq_utils import parse_fasta as _parse_fasta
    return _parse_fasta(text_or_path)


def format_fasta(header: str, seq: str, line_length: int = 60) -> str:
    """Convenience shortcut for formatting sequence as FASTA."""
    from .seq_utils import format_fasta as _format_fasta
    return _format_fasta(header, seq, line_length=line_length)


def record_result(
    result: Any,
    report: Optional[LabReport] = None,
    sample_id: str = "Sample-1",
    notes: str = "",
) -> List[Any]:
    """Universal auto-record convenience helper: automatically logs any calculation result into a LabReport."""
    return auto_record(result, report=report, sample_id=sample_id, notes=notes)


def cloning_workflow(
    primer_fwd: Optional[str] = None,
    primer_rev: Optional[str] = None,
    amplicon_len_bp: int = 1000,
    template_ng: float = 10.0,
    vector_length_bp: int = 3000,
    insert_length_bp: Optional[int] = None,
    enzyme_1: str = "EcoRI",
    enzyme_2: Optional[str] = "BamHI",
    dna_mass_ug: float = 1.0,
    assembly_method: str = "ligation",
    molar_ratio: float = 3.0,
    target_od600: float = 0.6,
    report: Optional[LabReport] = None,
    sample_id: str = "Clone-1",
    notes: str = "Molecular cloning workflow",
) -> CloningWorkflowResult:
    """Convenience shortcut for executing an end-to-end molecular cloning workflow pipeline."""
    return _cloning_workflow(
        primer_fwd=primer_fwd,
        primer_rev=primer_rev,
        amplicon_len_bp=amplicon_len_bp,
        template_ng=template_ng,
        vector_length_bp=vector_length_bp,
        insert_length_bp=insert_length_bp,
        enzyme_1=enzyme_1,
        enzyme_2=enzyme_2,
        dna_mass_ug=dna_mass_ug,
        assembly_method=assembly_method,
        molar_ratio=molar_ratio,
        target_od600=target_od600,
        report=report,
        sample_id=sample_id,
        notes=notes,
    )


def ivt_workflow(
    rna_seq: str,
    reaction_volume_ul: float = 20.0,
    target_yield_ug: Optional[float] = None,
    template_dna_ng: Optional[float] = 1000.0,
    buffer_type: str = "hepes",
    target_buffer_volume_ml: float = 50.0,
    precipitation_alcohol: str = "ethanol",
    precipitation_salt: str = "naoac",
    report: Optional[LabReport] = None,
    sample_id: str = "IVT-Batch-1",
    notes: str = "IVT synthesis workflow",
) -> IVTWorkflowResult:
    """Convenience shortcut for executing an end-to-end In Vitro Transcription synthesis workflow."""
    return _ivt_workflow(
        rna_seq=rna_seq,
        reaction_volume_ul=reaction_volume_ul,
        target_yield_ug=target_yield_ug,
        template_dna_ng=template_dna_ng,
        buffer_type=buffer_type,
        target_buffer_volume_ml=target_buffer_volume_ml,
        precipitation_alcohol=precipitation_alcohol,
        precipitation_salt=precipitation_salt,
        report=report,
        sample_id=sample_id,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# v0.4.0 High-Level Easy Helpers
# ---------------------------------------------------------------------------

def save_seq(name: str, seq: str, seq_type: str = "dna", description: str = "") -> str:
    """Save a DNA, RNA, or protein sequence to the persistent user sequence store.
    
    Args:
        name: Unique sequence identifier or gene name.
        seq: Nucleotide or amino acid sequence string.
        seq_type: Sequence modality ('dna', 'rna', or 'protein').
        description: Freeform description or biological notes.
        
    Returns:
        The sequence ID under which the record was saved.
    """
    rec = SequenceRecord(
        id=name,
        name=name,
        sequence=seq,
        seq_type=seq_type,
        description=description,
    )
    try:
        return save_sequence(rec)
    except (PermissionError, OSError):
        import tempfile
        fallback_path = os.path.join(tempfile.gettempdir(), ".biolabcalc", "sequences.json")
        return save_sequence(rec, filepath=fallback_path)


def get_seq(name_or_id: str) -> SequenceRecord:
    """Retrieve a sequence record from the user store or default catalog.
    
    Args:
        name_or_id: Sequence ID, catalog key, or record name.
        
    Returns:
        SequenceRecord entity.
    """
    try:
        return get_sequence(name_or_id)
    except (KeyError, PermissionError, OSError):
        import tempfile
        fallback_path = os.path.join(tempfile.gettempdir(), ".biolabcalc", "sequences.json")
        return get_sequence(name_or_id, filepath=fallback_path)


def load_plasmid(name_or_gb: str) -> PlasmidRecord:
    """Load a plasmid construct from standard catalog, user store, or GenBank file/string.
    
    Args:
        name_or_gb: Catalog identifier ('pUC19', 'pET-28a(+)'), file path, or GenBank text.
        
    Returns:
        Immutable PlasmidRecord entity.
    """
    if name_or_gb in STANDARD_PLASMID_CATALOG:
        return STANDARD_PLASMID_CATALOG[name_or_gb]

    if name_or_gb.strip().startswith("LOCUS") or "ORIGIN" in name_or_gb:
        return parse_genbank(name_or_gb)

    if "\n" not in name_or_gb and "\r" not in name_or_gb and len(name_or_gb) < 260:
        try:
            if os.path.exists(name_or_gb):
                return parse_genbank(name_or_gb)
        except OSError:
            pass

    try:
        return get_plasmid(name_or_gb)
    except (KeyError, PermissionError, OSError):
        import tempfile
        fallback_path = os.path.join(tempfile.gettempdir(), ".biolabcalc", "plasmids.json")
        return get_plasmid(name_or_gb, filepath=fallback_path)



def digest_map(
    plasmid_or_seq: Any,
    enzymes: Union[List[str], str],
    ladder: str = "1kb_dna",
) -> RestrictionDigestPrediction:
    """Perform in-silico restriction digest prediction and virtual gel simulation.
    
    Args:
        plasmid_or_seq: PlasmidRecord, sequence string, or catalog name ('pUC19').
        enzymes: Single enzyme name or list of restriction enzymes (e.g. ['EcoRI', 'HindIII']).
        ladder: Ladder catalog identifier for virtual gel migration (default: '1kb_dna').
        
    Returns:
        RestrictionDigestPrediction containing fragments, cut sites, and virtual gel bands.
    """
    target = load_plasmid(plasmid_or_seq) if (isinstance(plasmid_or_seq, str) and plasmid_or_seq in STANDARD_PLASMID_CATALOG) else plasmid_or_seq
    enz_list = [enzymes] if isinstance(enzymes, str) else list(enzymes)
    return predict_restriction_digest(target, enz_list, ladder_key=ladder)



def clone_gene(
    vector: Any,
    insert: str,
    gene_name: str = "Target",
    mode: str = "restriction_ligation",
    enzyme_5: str = "BamHI",
    enzyme_3: str = "XhoI",
) -> EngineeredPlasmidResult:
    """Automated gene expression cloning with reading frame synchronization and 7-point validation.
    
    Args:
        vector: Destination vector (PlasmidRecord, catalog name e.g. 'pET-28a(+)', or sequence).
        insert: Insert coding sequence (DNA CDS or amino acid sequence).
        gene_name: Identifier for the cloned gene.
        mode: Cloning assembly strategy ('restriction_ligation', 'gibson', 'golden_gate').
        enzyme_5: 5' restriction enzyme in MCS (default: 'BamHI').
        enzyme_3: 3' restriction enzyme in MCS (default: 'XhoI').
        
    Returns:
        EngineeredPlasmidResult with assembled PlasmidRecord, translation, and validation checklist.
    """
    vec_target = load_plasmid(vector) if (isinstance(vector, str) and vector in STANDARD_PLASMID_CATALOG) else vector
    return engineer_plasmid(
        vector=vec_target,
        insert_seq=insert,
        gene_name=gene_name,
        mode=mode,
        enzyme_5prime=enzyme_5,
        enzyme_3prime=enzyme_3,
    )


def codon_opt(seq: str, host: str = "ecoli") -> str:
    """Optimize a coding sequence or reverse-translate a protein using preferred host codons.
    
    Args:
        seq: Nucleotide CDS or amino acid sequence string.
        host: Host expression system ('ecoli', 'human').
        
    Returns:
        Optimized nucleotide coding sequence string.
    """
    return optimize_codons(seq, host=host)


def plasmid_svg(plasmid: Any, output_path: Optional[str] = None) -> str:
    """Generate a circular vector map in SVG format and optionally save to disk.
    
    Args:
        plasmid: PlasmidRecord, sequence, or catalog name.
        output_path: Optional file path to write SVG output (e.g. 'plasmid_map.svg').
        
    Returns:
        Raw SVG XML string.
    """
    target = load_plasmid(plasmid) if (isinstance(plasmid, str) and plasmid in STANDARD_PLASMID_CATALOG) else plasmid
    svg_str = render_plasmid_map_svg(target)
    if output_path:
        abs_p = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        with open(abs_p, "w", encoding="utf-8") as f:
            f.write(svg_str)
    return svg_str


def buffer_equil(
    components: Union[str, Dict[str, Any], Sequence[Any]],
    ph: float = 7.4,
    temp: float = 25.0,
    output_temp: float = 37.0,
    use_davies: bool = True,
) -> BufferEquilibriumResult:
    """Solve multi-metal competitive buffer speciation, chelation, and precipitation risks.
    
    Args:
        components: Recipe string (e.g. 'Tris=50mM,EGTA=5mM,MgCl2=10mM,ATP=4mM') or dictionary.
        ph: Target buffer pH (default: 7.4).
        temp: Formulation temperature in Celsius (default: 25.0).
        output_temp: Experimental assay temperature in Celsius (default: 37.0).
        use_davies: Enable Davies ionic strength activity corrections (default: True).
        
    Returns:
        BufferEquilibriumResult containing free metal ion concentrations and precipitation risks.
    """
    return solve_buffer_equilibrium(
        components=components,
        target_ph=ph,
        temperature_celsius=temp,
        output_temp_celsius=output_temp,
        use_davies_correction=use_davies,
    )


def score_aptamer(
    target_counts: Dict[str, int],
    counter_counts: Dict[str, int],
    alpha: float = 1.0,
    fdr_threshold: float = 0.05,
    round_number: int = 1,
) -> SELEXEnrichmentResult:
    """Analyze high-throughput Counter-SELEX sequencing counts with Benjamini-Hochberg FDR.
    
    Args:
        target_counts: Dictionary mapping aptamer sequences to counts against target subunit.
        counter_counts: Dictionary mapping aptamer sequences to counts against counter-target.
        alpha: Dirichlet pseudo-count smoothing parameter (default: 1.0).
        fdr_threshold: False discovery rate cutoff (default: 0.05).
        round_number: Selection cycle round number (default: 1).
        
    Returns:
        SELEXEnrichmentResult containing ranked, FDR-adjusted aptamer candidate scores.
    """
    return analyze_counter_selex(
        target_counts=target_counts,
        counter_counts=counter_counts,
        alpha_smoothing=alpha,
        fdr_threshold=fdr_threshold,
        round_number=round_number,
    )


def hairpin_thermo(
    sequence: str,
    temp: float = 37.0,
) -> SecondaryStructureThermoResult:
    """Evaluate secondary structure RNA/DNA hairpin folding thermodynamics using Turner (2004).
    
    Args:
        sequence: RNA or DNA nucleotide sequence string.
        temp: Temperature in Celsius (default: 37.0).
        
    Returns:
        SecondaryStructureThermoResult with dot-bracket structure, delta G, delta H, delta S, and Tm.
    """
    return evaluate_rna_hairpin_thermo(sequence, temperature_celsius=temp)


def trace_allostery(
    pdb_text_or_path: Union[str, Path],
    source_resid: int,
    sink_resid: int,
    cutoff: float = 7.0,
    k_paths: int = 5,
) -> AllostericNetworkResult:
    """Trace deterministic allosteric communication pathways and PRS effector/sensor profiles.
    
    Args:
        pdb_text_or_path: PDB file path or raw PDB formatted string.
        source_resid: Source residue sequence number (1-based).
        sink_resid: Target/effector residue sequence number (1-based).
        cutoff: GNM contact distance threshold in Angstroms (default: 7.0).
        k_paths: Number of top communication paths to extract via Yen's algorithm (default: 5).
        
    Returns:
        AllostericNetworkResult with identified routes, bottleneck residues, and PRS profiles.
    """
    return trace_allosteric_paths(
        pdb_text_or_path=pdb_text_or_path,
        source_resid=source_resid,
        sink_resid=sink_resid,
        cutoff_angstroms=cutoff,
        k_paths=k_paths,
    )


def plate_serial_dilution(
    start_conc: float = 100.0,
    dilution_factor: float = 2.0,
    points: int = 8,
    replicates: int = 3,
    plate_type: str = "96-well",
) -> Any:
    """Design a 96/384-well serial dilution plate and generate automation worklist."""
    from .automation import design_serial_dilution_plate
    return design_serial_dilution_plate(
        start_conc=start_conc,
        dilution_factor=dilution_factor,
        num_points=points,
        replicates=replicates,
        plate_type=plate_type,
    )


def print_protocol(
    title: str = "Benchtop Protocol",
    reactions: int = 16,
    overage: float = 10.0,
    reagents: Optional[List[Dict[str, Any]]] = None,
    samples: Optional[List[str]] = None,
    plate_type: str = "96-well",
    trim_size: str = "8x10",
    output_html_path: Optional[str] = "bench_protocol.html",
) -> str:
    """Generate a printable HTML benchtop protocol and plate layout for physical lab notebook tape-in.

    Follows the 7-stage thermodynamic 'Enzyme-Last' addition hierarchy, calculates master mix overage,
    and assigns recommended air-displacement pipetting tools (P2 to P1000).

    Args:
        title: Protocol header title.
        reactions: Total number of reaction wells.
        overage: Master mix excess percentage (default: 10.0%).
        reagents: Optional list of reagent dicts with name, stock, final, volume_ul, category.
        samples: Optional list of sample identifiers to map onto the plate grid.
        plate_type: '96-well', '384-well', '24-tube', or '8-strip'.
        trim_size: '8x10', '7.5x9.5', or 'full-page'.
        output_html_path: File path to save the self-contained HTML document.

    Returns:
        HTML string of the complete printable protocol.
    """
    from .printable_protocol import (
        build_bench_master_mix,
        generate_plate_bench_sheet,
        render_bench_companion_html,
        GLPSignOffBlock,
    )

    if reagents is None:
        reagents = [
            {"name": "Nuclease-Free Water", "stock_conc": "100%", "final_conc": "QS", "vol_ul": 14.0, "category": "water"},
            {"name": "5X Reaction Buffer", "stock_conc": "5X", "final_conc": "1X", "vol_ul": 5.0, "category": "buffer"},
            {"name": "dNTP Mix (10 mM each)", "stock_conc": "10 mM", "final_conc": "200 µM", "vol_ul": 0.5, "category": "dntp"},
            {"name": "Forward Primer (10 µM)", "stock_conc": "10 µM", "final_conc": "0.5 µM", "vol_ul": 1.25, "category": "primer"},
            {"name": "Reverse Primer (10 µM)", "stock_conc": "10 µM", "final_conc": "0.5 µM", "vol_ul": 1.25, "category": "primer"},
            {"name": "Template DNA (Separate)", "stock_conc": "50 ng/µL", "final_conc": "50 ng", "vol_ul": 2.5, "category": "template"},
            {"name": "DNA Polymerase", "stock_conc": "2 U/µL", "final_conc": "0.02 U/µL", "vol_ul": 0.5, "category": "enzyme"},
        ]

    if samples is None:
        samples = [f"Sample-{i+1}" for i in range(reactions)]

    mix = build_bench_master_mix(
        components=reagents,
        total_reactions=reactions,
        reaction_volume_ul=25.0,
        excess_percent=overage,
        separate_template=True,
    )

    plate = generate_plate_bench_sheet(
        samples=samples,
        plate_type=plate_type,
    )

    html_out = render_bench_companion_html(
        title=title,
        master_mix=mix,
        plate_map=plate,
        sign_off=GLPSignOffBlock(),
        page_trim=trim_size,
    )

    if output_html_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_html_path)), exist_ok=True)
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_out)

    return html_out


def read_scn(
    source: Union[bytes, str, Path],
    auto_contrast: bool = True,
    invert: bool = False,
    gamma: float = 1.0,
) -> Any:
    """
    Read and parse a Bio-Rad Image Lab .scn or legacy Quantity One .1sc file.
    
    Args:
        source: Raw bytes, file path (str or Path) to a .scn / .1sc file.
        auto_contrast: Automatically rescale 16-bit dynamic range based on 1st/99th percentiles.
        invert: Invert grayscale palette (useful for chemiluminescent blots).
        gamma: Gamma adjustment factor (default 1.0 = linear).
        
    Returns:
        BioRadImage frozen domain object.
    """
    from .eln.parsers.biorad_parser import BioRadParser
    return BioRadParser.parse(source, auto_contrast=auto_contrast, invert=invert, gamma=gamma)





