"""BioLabCalc: A multifaceted Python library and Excel extension for daily molecular biology research."""

import mimetypes
try:
    if hasattr(mimetypes, "_mimetypes_read_windows_registry"):
        mimetypes._mimetypes_read_windows_registry = None
    mimetypes.init()
except Exception:
    mimetypes.inited = True

__version__ = "1.1.0"

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
    dna_mw,
    protein_mw,
    pcr,
    digest,
    ligation,
    gibson,
    growth,
    convert,
    save_seq,
    get_seq,
    load_plasmid,
    digest_map,
    clone_gene,
    codon_opt,
    plasmid_svg,
    plate_serial_dilution,
    read_scn,
)

from .eln.parsers.biorad_parser import (
    BioRadParser,
    BioRadImage,
    ExposureMetadata,
)

from .automation import (
    WellTransfer,
    PlateMap,
    AutomationWorklist,
    design_serial_dilution_plate,
    design_pcr_setup_plate,
    export_echo_csv,
    export_opentrons_protocol,
    export_pylabrobot_json,
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
    RestrictionEnzyme,
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

from .sequence_store import (
    SequenceRecord,
    SequenceAnnotation,
    save_sequence,
    get_sequence,
    list_sequences,
    delete_sequence,
    import_fasta,
    export_fasta,
    DEFAULT_SEQUENCE_CATALOG,
)

from .plasmid import (
    PlasmidRecord,
    PlasmidFeature,
    extract_subsequence,
    rotate_origin,
    insert_subsequence,
    auto_annotate_plasmid,
    parse_genbank,
    export_genbank,
    save_plasmid,
    get_plasmid,
    list_plasmids,
    delete_plasmid,
    STANDARD_PLASMID_CATALOG,
)

from .restriction_engine import (
    RestrictionCutSite,
    DigestedFragment,
    RestrictionDigestPrediction,
    EnzymeScreenResult,
    find_restriction_sites,
    predict_restriction_digest,
    screen_restriction_enzymes,
)

from .plasmid_engineering import (
    CodonUsageAnalysis,
    evaluate_codon_usage,
    optimize_codons,
    ExpressionCassetteResult,
    design_expression_cassette,
    EngineeredPlasmidResult,
    engineer_plasmid,
)

from .tea_runtime import (
    BioLabModel,
    Msg,
    LoadPlasmidMsg,
    SelectEnzymesMsg,
    RunDigestMsg,
    InsertGeneMsg,
    SetViewModeMsg,
    UndoMsg,
    RedoMsg,
    Cmd,
    update,
    view,
    TEAStore,
)

from .interactive_plasmid import (
    render_plasmid_map_svg,
    get_plasmid_workbench_html,
    save_plasmid_workbench_html,
    launch_plasmid_workbench,
)

from .protocols import (
    LabProtocol,
    ProtocolReagent,
    ProtocolStep,
    TroubleshootingItem,
    PROTOCOL_CATALOG,
    list_protocols,
    get_protocol,
    format_protocol_markdown,
    export_all_protocols_markdown,
)

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
    # Sequences & Utilities
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
    # Easy API
    "rc",
    "translate",
    "gc",
    "dna_mw",
    "protein_mw",
    "pcr",
    "digest",
    "ligation",
    "gibson",
    "growth",
    "convert",
    "save_seq",
    "get_seq",
    "load_plasmid",
    "digest_map",
    "clone_gene",
    "codon_opt",
    "plasmid_svg",
    "plate_serial_dilution",
    "read_scn",
    "BioRadParser",
    "BioRadImage",
    "ExposureMetadata",
    "easy",
    # Biophysics & Molecular Weight
    "calculate_dna_mw",
    "calculate_rna_mw",
    "calculate_protein_mw",
    "mass_to_moles",
    "moles_to_mass",
    "mass_to_copy_number",
    "copy_number_to_mass",
    "concentration_to_molarity",
    "MolecularWeightResult",
    # Transcription & IVT
    "calculate_ivt_yield",
    "detect_and_trim_promoter",
    "evaluate_initiation_efficiency",
    "optimize_transcription_time",
    "PROMOTER_SEQUENCES",
    "InitiationAnalysis",
    "IVTResult",
    "TranscriptionTimeOptimizationResult",
    # PCR & Primers
    "calculate_pcr_kinetics",
    "calculate_qpcr_efficiency",
    "build_master_mix",
    "optimize_pcr_protocol",
    "PCRResult",
    "MasterMixItem",
    "PCROptimizationResult",
    "calculate_tm_santalucia",
    "calculate_tm_santaluicia",
    "analyze_primer",
    "design_primers",
    "check_heterodimer",
    "PrimerAnalysis",
    "PrimerPair",
    # Protein & Spectroscopy
    "calculate_extinction_coefficient",
    "quantify_protein_a280",
    "fit_standard_curve",
    "ExtinctionCoefficientResult",
    "ProteinYieldResult",
    "StandardCurveResult",
    "prepare_standard_solution",
    "assess_nanodrop_purity",
    "SolutionRecipeResult",
    "NanoDropPurityResult",
    # Fluorescence
    "get_fluorophore",
    "apply_fluorophore_modification",
    "calculate_degree_of_labeling",
    "Fluorophore",
    "LabeledMoleculeResult",
    "DegreeOfLabelingResult",
    "FLUOROPHORE_DATABASE",
    # Gels & Electrophoresis
    "simulate_gel",
    "calculate_rf",
    "GelLaneSimulation",
    "GelBand",
    "LADDER_CATALOG",
    # E. coli Growth & Expression
    "calculate_ecoli_growth",
    "calculate_inoculation_volume",
    "estimate_plasmid_yield",
    "optimize_protein_induction",
    "EcoliGrowthResult",
    "PlasmidYieldResult",
    "ProteinInductionResult",
    # Cloning & Assembly
    "get_restriction_enzyme",
    "plan_restriction_digest",
    "calculate_ligation",
    "calculate_gibson_assembly",
    "calculate_golden_gate_assembly",
    "GoldenGateResult",
    "are_overhangs_compatible",
    "register_custom_enzyme",
    "ENZYME_DATABASE",
    "RestrictionEnzyme",
    "DigestSetupResult",
    "LigationSetupResult",
    "GibsonAssemblyResult",
    # Buffers & Neutralization
    "calculate_buffer_recipe",
    "calculate_hepes_ivt_buffer",
    "HepesIVTBufferResult",
    "calculate_tris_temperature_shift",
    "create_custom_buffer",
    "register_custom_buffer",
    "save_custom_buffer_to_disk",
    "load_custom_buffers_from_disk",
    "list_custom_buffers",
    "delete_custom_buffer",
    "CustomBufferBuilder",
    "CustomBufferComponent",
    "calculate_ntp_ph_adjustment",
    "NTPNeutralizationResult",
    "BUFFER_CATALOG",
    "BufferRecipeResult",
    "BufferComponent",
    # Precipitation & Western Blot
    "calculate_precipitation",
    "calculate_phenol_chloroform_extraction",
    "PrecipitationProtocol",
    "PhenolChloroformProtocol",
    "plan_western_blot",
    "calculate_transfer_conditions",
    "calculate_lysate_loading",
    "calculate_antibody_dilution",
    "troubleshoot_western_blot",
    "WesternBlotPlanResult",
    "TransferConditionsResult",
    "LysateLoadingResult",
    "AntibodyDilutionResult",
    "WesternTroubleshootingResult",
    "TROUBLESHOOTING_DATABASE",
    # Lab Reports & Workflows
    "LabReport",
    "MeasurementRecord",
    "ParameterStatistics",
    "new_lab_report",
    "get_active_report",
    "record_measurement",
    "auto_record",
    "cloning_workflow",
    "ivt_workflow",
    "CloningWorkflowResult",
    "IVTWorkflowResult",
    # Excel Extension & Interactive Annotators
    "generate_lab_notebook_template",
    "batch_process_excel",
    "export_analysis_to_excel",
    "GelAnnotator",
    "get_interactive_html",
    "save_interactive_app",
    "calculate_ladder_standard_curve",
    "estimate_band_mw",
    "launch_interactive_annotator",
    "process_batch_csv",
    # ELN Subpackage
    "eln",
    # v0.4.0: Sequence Storage & Catalog
    "SequenceRecord",
    "SequenceAnnotation",
    "save_sequence",
    "get_sequence",
    "list_sequences",
    "delete_sequence",
    "import_fasta",
    "export_fasta",
    "DEFAULT_SEQUENCE_CATALOG",
    # v0.4.0: Circular Plasmid Storage & GenBank
    "PlasmidRecord",
    "PlasmidFeature",
    "extract_subsequence",
    "rotate_origin",
    "insert_subsequence",
    "auto_annotate_plasmid",
    "parse_genbank",
    "export_genbank",
    "save_plasmid",
    "get_plasmid",
    "list_plasmids",
    "delete_plasmid",
    "STANDARD_PLASMID_CATALOG",
    # v0.4.0: Restriction Engine & In-Silico Digest
    "RestrictionCutSite",
    "DigestedFragment",
    "RestrictionDigestPrediction",
    "EnzymeScreenResult",
    "find_restriction_sites",
    "predict_restriction_digest",
    "screen_restriction_enzymes",
    # v0.4.0: Plasmid Engineering & Expression Cloning
    "CodonUsageAnalysis",
    "evaluate_codon_usage",
    "optimize_codons",
    "ExpressionCassetteResult",
    "design_expression_cassette",
    "EngineeredPlasmidResult",
    "engineer_plasmid",
    # v0.4.0: TEA State Runtime
    "BioLabModel",
    "Msg",
    "LoadPlasmidMsg",
    "SelectEnzymesMsg",
    "RunDigestMsg",
    "InsertGeneMsg",
    "SetViewModeMsg",
    "UndoMsg",
    "RedoMsg",
    "Cmd",
    "update",
    "view",
    "TEAStore",
    # v0.4.0: Interactive Plasmid Map & Workbench
    "render_plasmid_map_svg",
    "get_plasmid_workbench_html",
    "save_plasmid_workbench_html",
    "launch_plasmid_workbench",
    # v0.4.0: Wet-Lab Standard Protocols Catalog
    "LabProtocol",
    "ProtocolReagent",
    "ProtocolStep",
    "TroubleshootingItem",
    "PROTOCOL_CATALOG",
    "list_protocols",
    "get_protocol",
    "format_protocol_markdown",
    "export_all_protocols_markdown",
    # v1.0.0: Microplate Automation & Liquid Handlers
    "WellTransfer",
    "PlateMap",
    "AutomationWorklist",
    "design_serial_dilution_plate",
    "design_pcr_setup_plate",
    "export_echo_csv",
    "export_opentrons_protocol",
    "export_pylabrobot_json",
    "plate_serial_dilution",
]
