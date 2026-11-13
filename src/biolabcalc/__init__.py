"""BioLabCalc: A multifaceted Python library and Excel extension for daily molecular biology research."""

import mimetypes
try:
    if hasattr(mimetypes, "_mimetypes_read_windows_registry"):
        mimetypes._mimetypes_read_windows_registry = None
    mimetypes.init()
except Exception:
    mimetypes.inited = True

__version__ = "0.3.5"

from .seq_utils import (
    clean_sequence,
    validate_sequence,
    reverse_complement,
    calculate_gc_content,
    count_bases,
    translate_dna,
    transcribe,
    reverse_transcribe,
    six_frame_translation,
    ORF,
    find_orfs,
    parse_fasta,
    format_fasta,
)

from .easy import (
    rc,
    translate,
    gc,
)

from .molecular_weight import (
    calculate_dna_mw,
    calculate_rna_mw,
    calculate_protein_mw,
    mass_to_moles,
    moles_to_mass,
    mass_to_copy_number,
    copy_number_to_mass,
    concentration_to_molarity,
    MolecularWeightResult,
)

from .transcription import (
    calculate_ivt_yield,
    optimize_transcription_time,
    detect_and_trim_promoter,
    evaluate_initiation_efficiency,
    PROMOTER_SEQUENCES,
    InitiationAnalysis,
    IVTResult,
    TranscriptionTimeOptimizationResult,
)

from .pcr import (
    calculate_pcr_kinetics,
    calculate_qpcr_efficiency,
    build_master_mix,
    optimize_pcr_protocol,
    PCRResult,
    MasterMixItem,
    PCROptimizationResult,
)

from .protein import (
    calculate_extinction_coefficient,
    quantify_protein_a280,
    fit_standard_curve,
    ExtinctionCoefficientResult,
    ProteinYieldResult,
    StandardCurveResult,
)

from .primers import (
    calculate_tm_santalucia,
    calculate_tm_santaluicia,
    analyze_primer,
    design_primers,
    check_heterodimer,
    PrimerAnalysis,
    PrimerPair,
)

from .fluorescence import (
    get_fluorophore,
    apply_fluorophore_modification,
    calculate_degree_of_labeling,
    Fluorophore,
    LabeledMoleculeResult,
    DegreeOfLabelingResult,
    FLUOROPHORE_DATABASE,
)

from .spectroscopy import (
    prepare_standard_solution,
    assess_nanodrop_purity,
    SolutionRecipeResult,
    NanoDropPurityResult,
)

from .gels import (
    simulate_gel,
    calculate_rf,
    GelLaneSimulation,
    GelBand,
    LADDER_CATALOG,
)

from .ecoli_growth import (
    calculate_ecoli_growth,
    calculate_inoculation_volume,
    estimate_plasmid_yield,
    optimize_protein_induction,
    EcoliGrowthResult,
    PlasmidYieldResult,
    ProteinInductionResult,
)

from .cloning import (
    get_restriction_enzyme,
    plan_restriction_digest,
    calculate_ligation,
    calculate_gibson_assembly,
    calculate_golden_gate_assembly,
    are_overhangs_compatible,
    register_custom_enzyme,
    ENZYME_DATABASE,
    DigestSetupResult,
    LigationSetupResult,
    GibsonAssemblyResult,
    GoldenGateResult,
)

from .buffers import (
    calculate_buffer_recipe,
    calculate_hepes_ivt_buffer,
    calculate_tris_temperature_shift,
    register_custom_buffer,
    create_custom_buffer,
    save_custom_buffer_to_disk,
    load_custom_buffers_from_disk,
    list_custom_buffers,
    delete_custom_buffer,
    CustomBufferBuilder,
    CustomBufferComponent,
    BUFFER_CATALOG,
    BufferRecipeResult,
    BufferComponent,
    calculate_ntp_ph_adjustment,
    NTPNeutralizationResult,
    HepesIVTBufferResult,
)

from .lab_report import (
    LabReport,
    MeasurementRecord,
    ParameterStatistics,
    new_lab_report,
    get_active_report,
    record_measurement,
    auto_record,
)

from .workflows import (
    cloning_workflow,
    ivt_workflow,
    CloningWorkflowResult,
    IVTWorkflowResult,
)

from .western_blot import (
    plan_western_blot,
    calculate_transfer_conditions,
    calculate_lysate_loading,
    calculate_antibody_dilution,
    troubleshoot_western_blot,
    WesternBlotPlanResult,
    TransferConditionsResult,
    LysateLoadingResult,
    AntibodyDilutionResult,
    WesternTroubleshootingResult,
    TROUBLESHOOTING_DATABASE,
)

from .precipitation import (
    calculate_precipitation,
    calculate_phenol_chloroform_extraction,
    PrecipitationProtocol,
    PhenolChloroformProtocol,
)

from .interactive_gel import (
    get_interactive_html,
    save_interactive_app,
    calculate_ladder_standard_curve,
    estimate_band_mw,
    launch_interactive_annotator,
)

from .batch_csv import process_batch_csv

try:
    from .gel_annotator import (
        GelAnnotator,
    )
except ImportError:
    GelAnnotator = None

try:
    from .excel_extension import (
        batch_process_excel,
        generate_lab_notebook_template,
        export_analysis_to_excel,
    )
except Exception:
    batch_process_excel = None
    generate_lab_notebook_template = None
    export_analysis_to_excel = None

from . import eln
from . import easy

__all__ = [
    "clean_sequence",
    "validate_sequence",
    "reverse_complement",
    "calculate_gc_content",
    "count_bases",
    "translate_dna",
    "transcribe",
    "reverse_transcribe",
    "six_frame_translation",
    "ORF",
    "find_orfs",
    "parse_fasta",
    "format_fasta",
    "rc",
    "translate",
    "gc",
    "easy",
    "calculate_dna_mw",
    "calculate_rna_mw",
    "calculate_protein_mw",
    "mass_to_moles",
    "moles_to_mass",
    "mass_to_copy_number",
    "copy_number_to_mass",
    "concentration_to_molarity",
    "MolecularWeightResult",
    "calculate_ivt_yield",
    "detect_and_trim_promoter",
    "evaluate_initiation_efficiency",
    "IVTResult",
    "calculate_pcr_kinetics",
    "calculate_qpcr_efficiency",
    "build_master_mix",
    "optimize_pcr_protocol",
    "PCRResult",
    "MasterMixItem",
    "PCROptimizationResult",
    "calculate_extinction_coefficient",
    "quantify_protein_a280",
    "fit_standard_curve",
    "ExtinctionCoefficientResult",
    "ProteinYieldResult",
    "StandardCurveResult",
    "calculate_tm_santalucia",
    "calculate_tm_santaluicia",
    "analyze_primer",
    "design_primers",
    "check_heterodimer",
    "PrimerAnalysis",
    "PrimerPair",
    "get_fluorophore",
    "apply_fluorophore_modification",
    "calculate_degree_of_labeling",
    "Fluorophore",
    "LabeledMoleculeResult",
    "DegreeOfLabelingResult",
    "FLUOROPHORE_DATABASE",
    "prepare_standard_solution",
    "SolutionRecipeResult",
    "simulate_gel",
    "calculate_rf",
    "GelLaneSimulation",
    "GelBand",
    "LADDER_CATALOG",
    "calculate_ecoli_growth",
    "calculate_inoculation_volume",
    "estimate_plasmid_yield",
    "optimize_protein_induction",
    "EcoliGrowthResult",
    "PlasmidYieldResult",
    "ProteinInductionResult",
    "generate_lab_notebook_template",
    "batch_process_excel",
    "get_restriction_enzyme",
    "plan_restriction_digest",
    "calculate_ligation",
    "calculate_gibson_assembly",
    "calculate_golden_gate_assembly",
    "GoldenGateResult",
    "are_overhangs_compatible",
    "ENZYME_DATABASE",
    "DigestSetupResult",
    "LigationSetupResult",
    "GibsonAssemblyResult",
    "calculate_buffer_recipe",
    "calculate_hepes_ivt_buffer",
    "HepesIVTBufferResult",
    "calculate_tris_temperature_shift",
    "create_custom_buffer",
    "calculate_ntp_ph_adjustment",
    "NTPNeutralizationResult",
    "BUFFER_CATALOG",
    "BufferRecipeResult",
    "BufferComponent",
    "calculate_precipitation",
    "calculate_phenol_chloroform_extraction",
    "PrecipitationProtocol",
    "PhenolChloroformProtocol",
    "plan_western_blot",
    "troubleshoot_western_blot",
    "WesternBlotPlanResult",
    "export_analysis_to_excel",
    "GelAnnotator",
    "get_interactive_html",
    "save_interactive_app",
    "calculate_ladder_standard_curve",
    "estimate_band_mw",
    "launch_interactive_annotator",
    "process_batch_csv",
    "eln",
    "auto_record",
    "cloning_workflow",
    "ivt_workflow",
    "CloningWorkflowResult",
    "IVTWorkflowResult",
]
