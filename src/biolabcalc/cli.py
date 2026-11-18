"""Command-line interface (CLI) for BioLabCalc."""

from __future__ import annotations
import argparse
import dataclasses
import json
import os
import sys
from typing import Any, Callable, Dict

from . import __version__
from .units import UnitParser
from .easy import dilute, convert as easy_convert
from .molecular_weight import calculate_dna_mw, calculate_rna_mw, calculate_protein_mw
from .transcription import calculate_ivt_yield, optimize_transcription_time
from .pcr import calculate_pcr_kinetics, calculate_qpcr_efficiency, build_master_mix, optimize_pcr_protocol
from .protein import quantify_protein_a280, calculate_extinction_coefficient
from .western_blot import plan_western_blot, troubleshoot_western_blot
from .lab_report import get_active_report, new_lab_report
from .primers import design_primers, analyze_primer
from .fluorescence import apply_fluorophore_modification, calculate_degree_of_labeling, get_fluorophore
from .spectroscopy import prepare_standard_solution, assess_nanodrop_purity
from .gels import simulate_gel
from .ecoli_growth import calculate_ecoli_growth, estimate_plasmid_yield, optimize_protein_induction
try:
    from .excel_extension import generate_lab_notebook_template, batch_process_excel
except ImportError:
    generate_lab_notebook_template, batch_process_excel = None, None
try:
    from .gel_annotator import GelAnnotator
except ImportError:
    GelAnnotator = None
from .cloning import plan_restriction_digest, calculate_ligation, calculate_gibson_assembly, calculate_golden_gate_assembly
from .buffers import calculate_buffer_recipe, calculate_hepes_ivt_buffer, calculate_ntp_ph_adjustment, BUFFER_CATALOG, CustomBufferBuilder, list_custom_buffers
from .precipitation import calculate_precipitation, calculate_phenol_chloroform_extraction
from .interactive_gel import save_interactive_app, launch_interactive_annotator
from .batch_csv import process_batch_csv
from .seq_utils import clean_sequence, reverse_complement, translate_dna
from .sequence_store import (
    SequenceRecord,
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
    auto_annotate_plasmid,
    parse_genbank,
    export_genbank,
    get_plasmid,
    list_plasmids,
    delete_plasmid,
    STANDARD_PLASMID_CATALOG,
)
from .restriction_engine import (
    RestrictionCutSite,
    DigestedFragment,
    RestrictionDigestPrediction,
    predict_restriction_digest,
)
from .plasmid_engineering import (
    EngineeredPlasmidResult,
    engineer_plasmid,
)
from .interactive_plasmid import (
    save_plasmid_workbench_html,
    launch_plasmid_workbench,
)
from .easy import load_plasmid

LADDER_CHOICES = [
    "1kb_dna",
    "100bp_dna",
    "low_range_ssdna",
    "low_mw_dna",
    "high_mw_dna",
    "protein_broad_range",
    "ssdna_ladder",
    "ssrna_ladder",
    "rna_millennium",
    "low_range_rna",
    "low_range_ssrna",
    "microrna_ladder",
]

LADDER_ALIAS_MAP: Dict[str, str] = {
    "low_mw_dna": "100bp_dna",
    "high_mw_dna": "1kb_dna",
    "ssdna_ladder": "low_range_ssdna",
    "rna_millennium": "ssrna_ladder",
    "low_range_ssrna": "low_range_rna",
}



def _resolve_sequence(args: argparse.Namespace, seq_attr: str = "sequence", file_attr: str = "file") -> str:
    """Resolve sequence from command-line argument, file, or standard input."""
    fpath = getattr(args, file_attr, None)
    if fpath:
        if not os.path.exists(fpath):
            print(f"Error: Sequence file not found: '{fpath}'", file=sys.stderr)
            sys.exit(1)
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read().strip()
    val = getattr(args, seq_attr, None)
    if val == "-":
        return sys.stdin.read().strip()
    return val or ""


def _dump_json(obj: Any, compact: bool = False) -> None:
    """Serialize and print object as formatted or compact JSON."""
    if dataclasses.is_dataclass(obj):
        data = dataclasses.asdict(obj)
    elif hasattr(obj, "to_dict"):
        data = obj.to_dict()
    elif isinstance(obj, dict):
        data = obj
    elif hasattr(obj, "__dict__"):
        data = obj.__dict__
    else:
        data = obj
    indent = None if compact else 2
    print(json.dumps(data, indent=indent, default=str))


def _maybe_log_report(result: Any, args: argparse.Namespace) -> None:
    """If --log-report is specified, record the calculation result into a LabReport and export."""
    log_path = getattr(args, "log_report", None)
    if not log_path:
        return
    from .lab_report import LabReport, auto_record
    rep = LabReport.load_or_create(log_path, title=f"Experiment Report - {os.path.basename(log_path)}")
    sample_id = getattr(args, "sample", None) or "Sample-1"
    cmd_name = getattr(args, "command", "") or "Calculation"
    auto_record(result, report=rep, sample_id=sample_id, notes=f"CLI {cmd_name}")

    ext = os.path.splitext(log_path)[1].lower()
    if ext == ".json":
        rep.export_json(log_path)
    elif ext == ".csv":
        rep.export_csv(log_path)
    elif ext in (".xlsx", ".xls"):
        rep.export_excel(log_path)
    else:  # default to markdown
        rep.export_markdown(log_path)

    if not getattr(args, "quiet", False) and not getattr(args, "json", False):
        print(f"[+] Appended result to lab report: {log_path} ({len(rep.records)} total records)")



def run_wizard():
    """Interactive prompt wizard for common wet-lab workflows."""
    print()
    print("=" * 75)
    print("  BIOLABCALC INTERACTIVE BENCH CALCULATOR WIZARD")
    print("=" * 75)
    print("Select a calculation workflow:")
    print("  [1] Solution Dilution (C1*V1 = C2*V2)")
    print("  [2] NTP Solution Preparation & pH Adjustment (pH 7.5)")
    print("  [3] In Vitro Transcription (IVT) Stoichiometry & Yield")
    print("  [4] PCR Master Mix Formulation")
    print("  [5] Laboratory Buffer Formulation & Volume Scaling")
    print("  [6] Nucleic Acid Precipitation & Desalting")
    print("  [7] Molecular Weight & Molarity Calculation")
    print("  [8] Restriction Digest Planning")
    print("  [9] Ligation / Gibson Assembly Setup")
    print("  [10] Laboratory Unit & Stoichiometry Conversion")
    print("  [q] Quit")
    print("-" * 75)

    choice = input("Enter option [1-10]: ").strip().lower()
    if choice in ("q", "quit", "exit"):
        print("Exiting BioLabCalc Wizard.")
        return

    if choice == "1":
        print("\n--- Dilution Calculator (C1*V1 = C2*V2) ---")
        c1 = input("Enter Stock Conc C1 (e.g. '100 mM'): ").strip()
        c2 = input("Enter Target Conc C2 (e.g. '25 mM'): ").strip()
        v2 = input("Enter Target Volume V2 (e.g. '16 mL'): ").strip()
        res = dilute(c1=c1, c2=c2, v2=v2)
        conc_unit = "mg/mL" if ("/" in c1 or "/" in c2) else "mM"
        print(f"\n--> Take {res['v1'] / 1000.0:.3f} mL of stock and add {res['diluent_needed'] / 1000.0:.3f} mL diluent to reach {res['c2']} {conc_unit} in {v2}.")

    elif choice == "2":
        print("\n--- 25 mM NTP Solution Preparation & pH Adjustment ---")
        v1 = input("Stock volume in mL [4.0]: ").strip() or "4.0"
        c1 = input("Stock conc in mM [100.0]: ").strip() or "100.0"
        v2 = input("Target volume in mL [16.0]: ").strip() or "16.0"
        c2 = input("Target conc in mM [25.0]: ").strip() or "25.0"
        form = input("Form ('disodium_salt', 'pre_neutralized', 'free_acid') [disodium_salt]: ").strip() or "disodium_salt"
        res = calculate_ntp_ph_adjustment(
            initial_volume_ml=float(v1),
            initial_conc_mm=float(c1),
            target_volume_ml=float(v2),
            target_conc_mm=float(c2),
            starting_form=form,
        )
        print(f"\n--> Total NaOH (5M) required: {res.naoh_volume_ul.get('5M', 0.0)} µL")
        print(f"--> Approx diluent water: {res.water_volume_ml:.2f} mL (bring to {v2} mL mark)")
        for lc in res.logic_checks:
            print(f"  [*] {lc}")

    elif choice == "3":
        print("\n--- In Vitro Transcription (IVT) Stoichiometry & Yield ---")
        seq = input("Enter RNA/DNA template sequence [GGGAGACCCAAGCUGGCC]: ").strip() or "GGGAGACCCAAGCUGGCC"
        vol_str = input("Reaction volume in µL [20.0]: ").strip() or "20.0"
        yld_str = input("Measured yield in µg [50.0]: ").strip() or "50.0"
        vol = UnitParser.parse_volume(vol_str, "ul")
        yld = UnitParser.parse_mass(yld_str, "ug")
        res = calculate_ivt_yield(rna_seq=seq, reaction_volume_ul=vol, measured_yield_ug=yld)
        print(f"\n--> RNA Length: {res.rna_length} nt (MW: {res.rna_mw:,.1f} Da)")
        print(f"--> Yield: {res.rna_yield_ug:.1f} µg ({res.rna_yield_pmol:.2f} pmol)")
        turnover_str = f"{res.transcript_turnover_ratio:,.0f}x" if res.transcript_turnover_ratio is not None else "N/A"
        print(f"--> Transcript turnover: {turnover_str}")
        print(f"--> Limiting Reagent: {res.limiting_ntp}")

    elif choice == "4":
        print("\n--- PCR Master Mix Formulation ---")
        rxns = input("Number of reactions [10]: ").strip() or "10"
        vol = input("Reaction volume in µL [50.0]: ").strip() or "50.0"
        excess = input("Excess percentage [10.0]: ").strip() or "10.0"
        items = build_master_mix(num_reactions=int(rxns), reaction_volume_ul=float(vol), excess_percent=float(excess))
        total_vol = sum(it.total_volume_ul for it in items)
        print(f"\nMaster Mix for {rxns} reactions ({total_vol:.1f} µL total incl. {excess}% excess):")
        for item in items:
            print(f"  - {item.component}: {item.total_volume_ul:.2f} µL ({item.volume_per_reaction_ul:.2f} µL/rxn)")

    elif choice == "5":
        print("\n--- Laboratory Buffer Recipe ---")
        print(f"Available buffers: {list(BUFFER_CATALOG.keys())}")
        b_name = input("Buffer name [10X_PBS]: ").strip() or "10X_PBS"
        vol = input("Target volume in mL [1000]: ").strip() or "1000"
        res = calculate_buffer_recipe(b_name, target_volume_ml=float(vol))
        print(f"\nRecipe for {res.name} ({res.target_volume_ml:.0f} mL):")
        for c in res.components:
            print(f"  - {c.name}: {c.amount} {c.unit} ({c.molar_concentration})")

    elif choice == "6":
        print("\n--- Nucleic Acid Precipitation & Desalting ---")
        vol_str = input("Sample volume in µL [100.0]: ").strip() or "100.0"
        na = input("Nucleic acid ('dna' or 'rna') [dna]: ").strip() or "dna"
        alc = input("Alcohol ('ethanol' or 'isopropanol') [ethanol]: ").strip() or "ethanol"
        res = calculate_precipitation(sample_volume_ul=float(vol_str), nucleic_acid=na, alcohol=alc)
        print(f"\nPrecipitation protocol for {res.sample_volume_ul:.0f} µL {res.nucleic_acid_type}:")
        for k, v in res.reagent_summary.items():
            print(f"  - {k}: {v:.1f} µL")
        print(f"--> Incubation: {res.incubation_temp}")
        print(f"--> Centrifugation: {res.centrifugation_speed} for {res.centrifugation_time_min} min")

    elif choice == "7":
        print("\n--- Molecular Weight & Molarity Calculation ---")
        stype = input("Sequence type ('dna', 'rna', 'protein') [dna]: ").strip().lower() or "dna"
        seq = input("Sequence [ATGCGTACGTTAGC]: ").strip() or "ATGCGTACGTTAGC"
        if stype == "dna":
            mw_res = calculate_dna_mw(seq)
        elif stype == "rna":
            mw_res = calculate_rna_mw(seq)
        else:
            mw_res = calculate_protein_mw(seq)
        print(f"\n--> Sequence Length: {mw_res.length} {'nt' if stype in ('dna', 'rna') else 'aa'}")
        print(f"--> Average MW: {mw_res.average_mw:,.2f} Da")
        print(f"--> Monoisotopic MW: {mw_res.monoisotopic_mw:,.4f} Da")
        print(f"--> GC Content: {mw_res.gc_content:.1f}%")

    elif choice == "8":
        print("\n--- Restriction Digest Planning ---")
        dna_ug = input("DNA mass in µg [1.0]: ").strip() or "1.0"
        vol = input("Reaction volume in µL [50.0]: ").strip() or "50.0"
        e1 = input("Enzyme 1 [EcoRI]: ").strip() or "EcoRI"
        e2 = input("Enzyme 2 (optional, leave blank for single digest): ").strip() or None
        conc = input("DNA stock concentration in ng/µL (optional): ").strip()
        dna_conc = float(conc) if conc else None
        res = plan_restriction_digest(
            dna_mass_ug=float(dna_ug),
            reaction_volume_ul=float(vol),
            enzyme_1=e1,
            enzyme_2=e2,
            dna_conc_ng_ul=dna_conc,
        )
        print(f"\n--> Recommended Buffer: {res.recommended_buffer}")
        print(f"--> Incubation:         {res.incubation_temp_celsius}°C for {res.incubation_time_min} min")
        print("--> Pipetting Recipe:")
        for comp, amt in res.reagent_volumes.items():
            print(f"    - {comp}: {amt:.2f} µL")

    elif choice == "9":
        print("\n--- Ligation / Gibson Assembly Setup ---")
        sub_type = input("Choose setup ('1' for Ligation, '2' for Gibson Assembly) [1]: ").strip() or "1"
        if sub_type == "2":
            vec_bp = input("Vector length in bp [3000]: ").strip() or "3000"
            ins_bp_str = input("Insert length(s) in bp (space-separated) [1000]: ").strip() or "1000"
            vec_ng = input("Vector mass in ng [100.0]: ").strip() or "100.0"
            ratio = input("Insert:vector molar ratio [2.0]: ").strip() or "2.0"
            ins_bp = [int(x) for x in ins_bp_str.split()]
            res = calculate_gibson_assembly(
                vector_length_bp=int(vec_bp),
                insert_lengths_bp=ins_bp,
                vector_mass_ng=float(vec_ng),
                molar_ratio=float(ratio),
            )
            print(f"\n--> Vector: {res.vector_mass_ng:.1f} ng")
            for idx, (l, m) in enumerate(zip(res.insert_lengths_bp, res.insert_masses_ng), 1):
                print(f"--> Insert #{idx} ({l} bp): {m:.1f} ng")
            print(f"--> Total DNA Input: {res.total_dna_pmol:.3f} pmol")
            print(f"--> Protocol: {res.incubation_protocol}")
        else:
            vec_bp = input("Vector length in bp [3000]: ").strip() or "3000"
            ins_bp = input("Insert length in bp [1000]: ").strip() or "1000"
            vec_ng = input("Vector mass in ng [50.0]: ").strip() or "50.0"
            ratio = input("Insert:vector molar ratio [3.0]: ").strip() or "3.0"
            res = calculate_ligation(
                vector_length_bp=int(vec_bp),
                insert_length_bp=int(ins_bp),
                vector_mass_ng=float(vec_ng),
                molar_ratio=float(ratio),
            )
            print(f"\n--> Vector ({res.vector_length_bp} bp): {res.vector_mass_ng:.1f} ng ({res.vector_pmol:.3f} pmol)")
            print(f"--> Insert ({res.insert_length_bp} bp): {res.insert_mass_ng:.1f} ng ({res.insert_pmol:.3f} pmol)")
            print(f"--> Protocol: {res.incubation_guidelines}")

    elif choice == "10":
        print("\n--- Laboratory Unit & Stoichiometry Conversion ---")
        val = input("Input quantity with unit (e.g. '500 ng', '10 uM', '2.5 mL'): ").strip()
        to_u = input("Target unit (e.g. 'pmol', 'ng/ul', 'ul', 'g'): ").strip()
        mw_str = input("Molecular weight in Da (optional, required for mass <-> mole): ").strip()
        mw = float(mw_str) if mw_str else None
        res_val = easy_convert(val, to_u, mw=mw)
        print(f"\n--> Converted: {val} = {res_val} {to_u}")

    else:
        print("Feature available directly via CLI commands. Run 'biolabcalc --help'.")


# --- Subcommand Handler Functions ---

def handle_dilute(args: argparse.Namespace) -> None:
    res = dilute(c1=args.c1, v1=args.v1, c2=args.c2, v2=args.v2)
    conc_unit = "mM"
    for val in (args.c1, args.c2):
        if val and "/" in str(val):
            conc_unit = "mg/mL"
            break
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("DILUTION CALCULATOR (C1 * V1 = C2 * V2)")
        print("=" * 65)
    print(f"Stock Concentration (C1):    {res['c1']} {conc_unit}")
    print(f"Stock Volume to Add (V1):     {res['v1'] / 1000.0:.3f} mL ({res['v1']:,.1f} µL)")
    print(f"Target Concentration (C2):   {res['c2']} {conc_unit}")
    print(f"Final Total Volume (V2):      {res['v2'] / 1000.0:.3f} mL ({res['v2']:,.1f} µL)")
    print(f"Diluent Volume Needed:        {res['diluent_needed'] / 1000.0:.3f} mL ({res['diluent_needed']:,.1f} µL)")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_wizard(args: argparse.Namespace) -> None:
    run_wizard()


def handle_mw(args: argparse.Namespace) -> None:
    raw_seq = _resolve_sequence(args)
    if not raw_seq:
        print("Error: biolabcalc mw requires sequence via -s/--sequence, -f/--file, or stdin (-s -).", file=sys.stderr)
        sys.exit(1)
    is_circ = getattr(args, "circular", False)
    if args.type == "dna":
        is_ds = args.ds or is_circ
        res = calculate_dna_mw(raw_seq, double_stranded=is_ds, end_5=args.end_5, circular=is_circ)
    elif args.type == "rna":
        res = calculate_rna_mw(raw_seq, end_5=args.end_5, end_3=args.end_3, backbone=args.backbone)
    else:
        res = calculate_protein_mw(raw_seq)

    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 60)
    print(f"Sequence Type:       {res.seq_type}")
    print(f"Length:              {res.length}")
    print(f"Average MW:          {res.average_mw:,.2f} Da")
    print(f"Monoisotopic MW:     {res.monoisotopic_mw:,.4f} Da")
    if args.type == "rna":
        print(f"Terminal Chemistry:  5'-{res.end_5} | 3'-{res.end_3}")
        print(f"Backbone Linkage:    {res.backbone}")
    print(f"GC Content:          {res.gc_content:.1f}%")
    if not getattr(args, "quiet", False):
        print("=" * 60)


def handle_nanodrop(args: argparse.Namespace) -> None:
    nano_seq = _resolve_sequence(args)
    res = prepare_standard_solution(
        target_molarity_um=args.molarity_um,
        target_volume_ul=args.volume_ul,
        sequence=nano_seq,
        seq_type=args.type,
        rna_length_nt=args.length,
        stock_conc_ng_ul=args.stock_ng_ul,
        end_5=args.end_5,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 70)
        print("STANDARDIZED SOLUTION PREPARATION & NANODROP PREDICTIONS")
        print("=" * 70)
    print(f"Target Solution:            {res.target_molarity_um} µM in {res.target_volume_ul} µL ({res.seq_type})")
    if res.sequence and not res.sequence.startswith("("):
        print(f"Custom Sequence:            5'-{res.sequence}-3' (5'-{res.end_5})")
        print(f"Base Composition:           {dict(res.base_counts)}")
        print(f"Nearest-Neighbor ε260:      {res.sequence_extinction_coeff_260:,} M^-1 cm^-1")
        print(f"Sequence Conversion Factor: {res.sequence_specific_conversion_factor:.2f} µg/mL per OD260")
    print(f"Biomolecule MW:             {res.molecular_weight:,.2f} g/mol (Da)")
    print(f"Required Moles:             {res.required_moles_nmol:.3f} nmol ({res.required_moles_pmol:.1f} pmol)")
    print(f"Required Mass:              {res.required_mass_ug:.3f} µg ({res.required_mass_ng:.1f} ng)")
    print(f"Actual Physical Conc.:      {res.actual_concentration_ng_ul:.2f} ng/µL")
    if not getattr(args, "quiet", False):
        print("-" * 70)
        print("WHAT YOU SHOULD GET AT THE NANODROP:")
    print(f"  Expected A260 (10 mm path):     {res.expected_nanodrop_a260_sequence_specific:.3f} AU (Sequence-specific Beer-Lambert)")
    print(f"  Expected A260 (1 mm pedestal): {res.expected_nanodrop_a260_1mm:.4f} AU (Raw pedestal reading)")
    print(f"  Reading in NanoDrop RNA-40 Mode:{res.expected_nanodrop_display_ng_ul_generic_mode:.2f} ng/µL (A260 * 40)")
    print(f"  Reading in Custom ε260 Mode:   {res.actual_concentration_ng_ul:.2f} ng/µL (True concentration)")
    print(f"  Expected A260/A280 Ratio:      ~{res.expected_a260_a280_ratio:.2f} (Pure RNA)")
    if not getattr(args, "quiet", False):
        print("-" * 70)
    print(f"Protocol: {res.preparation_instructions}")
    if not getattr(args, "quiet", False):
        print("=" * 70)


def handle_fluo(args: argparse.Namespace) -> None:
    if args.info is not None:
        dye_name = args.info if args.info else args.dye
        if not dye_name:
            print("Error: Specify a dye name for --info (e.g. --info FAM or -d FAM)")
            sys.exit(1)
        fl = get_fluorophore(dye_name)
        if not getattr(args, "quiet", False):
            print("=" * 60)
            print(f"FLUOROPHORE DATABASE ENTRY: {fl.name} ({fl.common_name})")
            print("=" * 60)
        print(f"Added Molecular Weight:     {fl.added_mw:.2f} Da (Monoisotopic: {fl.added_monoisotopic:.2f} Da)")
        print(f"Excitation Maximum (λex):   {fl.excitation_max_nm} nm")
        print(f"Emission Maximum (λem):     {fl.emission_max_nm} nm ({fl.color_description})")
        print(f"Extinction Coeff (εmax):    {fl.extinction_coeff_m_cm:,} M^-1 cm^-1")
        print(f"Correction Factor CF260:    {fl.cf260:.2f}")
        print(f"Correction Factor CF280:    {fl.cf280:.2f}")
        if not getattr(args, "quiet", False):
            print("=" * 60)
    elif args.dol:
        if args.a_dye is None:
            print("Error: --a-dye is required for Degree of Labeling (--dol) calculation.")
            sys.exit(1)
        dye_name = args.dye or "FAM"
        res = calculate_degree_of_labeling(
            absorbance_max_dye=args.a_dye,
            absorbance_280=args.a280,
            absorbance_260=args.a260,
            fluorophore_name=dye_name,
            protein_extinction_coeff=args.prot_e280,
            oligo_extinction_coeff=args.dna_e260,
            pathlength_cm=args.pathlength,
        )
        if not getattr(args, "quiet", False):
            print("=" * 65)
            print(f"DEGREE OF LABELING (DOL) CALCULATION ({res.molecule_type.upper()})")
            print("=" * 65)
        print(f"Fluorophore:                {res.fluorophore_name}")
        print(f"Absorbance at Dye Amax:     {res.absorbance_max_dye:.3f} AU")
        print(f"Corrected Biomolecule Abs:  {res.absorbance_corrected_biomolecule:.4f} AU")
        print(f"Biomolecule Concentration:  {res.biomolecule_concentration_um:.2f} µM")
        print(f"Dye Concentration:          {res.dye_concentration_um:.2f} µM")
        print(f"Degree of Labeling (DOL):   {res.degree_of_labeling:.3f} dye / molecule")
        print(f"Labeling Efficiency:        {res.labeling_efficiency_percent:.1f}%")
        print(f"Interpretation:             {res.interpretation}")
        if not getattr(args, "quiet", False):
            print("=" * 65)
    else:
        if not args.sequence or not args.dye:
            print("Error: biolabcalc fluo requires -s/--sequence and -d/--dye (or use --info / --dol).")
            sys.exit(1)
        if args.type == "dna":
            base_res = calculate_dna_mw(args.sequence)
        elif args.type == "rna":
            base_res = calculate_rna_mw(args.sequence)
        else:
            base_res = calculate_protein_mw(args.sequence)
        mod_res = apply_fluorophore_modification(base_res, [args.dye])
        fl = mod_res.primary_fluorophore
        if not getattr(args, "quiet", False):
            print("=" * 60)
            print(f"FLUOROPHORE MODIFICATION: {fl.name}")
            print("=" * 60)
        print(f"Unmodified MW:       {mod_res.original_mw:,.2f} Da")
        print(f"Modified MW:         {mod_res.total_modified_mw:,.2f} Da (+{mod_res.total_added_mw} Da)")
        print(f"Excitation / Emission:{fl.excitation_max_nm} nm / {fl.emission_max_nm} nm ({fl.color_description})")
        print(f"Extinction Coeff:    {fl.extinction_coeff_m_cm:,} M^-1 cm^-1")
        print(f"Correction Factors:  CF260 = {fl.cf260:.2f} | CF280 = {fl.cf280:.2f}")
        if not getattr(args, "quiet", False):
            print("=" * 60)


def handle_gel(args: argparse.Namespace) -> None:
    lad_choice = LADDER_ALIAS_MAP.get(args.ladder, args.ladder)
    sim = simulate_gel(sample_sizes=args.sizes, ladder_key=lad_choice)
    print(sim.ascii_visualization)



def handle_ivt(args: argparse.Namespace) -> None:
    raw_ivt_seq = _resolve_sequence(args)
    if not raw_ivt_seq:
        print("Error: biolabcalc ivt requires sequence via -s/--sequence, -f/--file, or stdin (-s -).", file=sys.stderr)
        sys.exit(1)
    vol = UnitParser.parse_volume(args.volume, "ul")
    yld = UnitParser.parse_mass(args.yield_ug, "ug")
    res = calculate_ivt_yield(
        rna_seq=raw_ivt_seq,
        reaction_volume_ul=vol,
        measured_yield_ug=yld,
        atp_mm=args.ntp_mm,
        ctp_mm=args.ntp_mm,
        gtp_mm=args.ntp_mm,
        utp_mm=args.ntp_mm,
        auto_trim_promoter=not getattr(args, "no_trim_promoter", False),
        add_5prime_gg=getattr(args, "add_gg", 0),
        cap_analog=getattr(args, "cap", None),
        modified_ntp=getattr(args, "mod_ntp", None),
        end_3=getattr(args, "end_3", "hydroxyl"),
        buffer_type=getattr(args, "buffer", "hepes"),
        temperature_celsius=getattr(args, "temp", 37.0),
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("IN VITRO TRANSCRIPTION (IVT) YIELD & STOICHIOMETRY")
        print("=" * 65)
    print(f"Transcribed RNA Length:     {res.rna_length} nt")
    print(f"RNA Molecular Weight:       {res.rna_mw:,.2f} Da")
    if res.promoter_detected:
        print(f"Promoter Trimmed:           {res.promoter_detected} ({res.promoter_trimmed_nt} nt removed)")
    if res.added_5prime_gs > 0:
        print(f"5' Guanines Added:          +{res.added_5prime_gs} G (5'-{res.rna_sequence[:5]}...)")
    if res.cap_analog:
        print(f"Cap Analog:                 {res.cap_analog} (Estimated Capping: {res.predicted_capping_efficiency_percent:.0f}%)")
    if res.modified_ntp:
        print(f"Modified Nucleotide:        {res.modified_ntp}")
    print(f"Initiation Rating:          {res.initiation_efficiency_rating}")
    print(f"Measured RNA Yield:         {res.rna_yield_ug:.2f} µg ({res.rna_yield_pmol:.1f} pmol)")
    print(f"Theoretical Maximum:        {res.theoretical_max_yield_ug:.2f} µg (Limiting: {res.limiting_ntp})")
    print(f"Incorporation Efficiency:   {res.overall_efficiency_percent:.1f}%")
    print(f"Pyrophosphate (PPi):        {res.pyrophosphate_released_ug:.2f} µg ({res.pyrophosphate_released_nmol:.2f} nmol)")
    print(f"Free Initial Mg2+:          {res.free_mg_initial_mm:.1f} mM")
    print(f"Protons (H+) Released:      {res.protons_released_nmol:.2f} nmol")
    print(f"Optimal Incubation Time:    ~{res.recommended_incubation_hours:.2f} hours at {args.temp:.0f}°C")
    print(f"Buffer Evaluation:          {res.hepes_vs_tris_comparison}")
    if res.warnings:
        if not getattr(args, "quiet", False):
            print("-" * 65)
            print("Warnings & Recommendations:")
        for w in res.warnings:
            print(f"  [!] {w}")
    for rec in res.initiation_recommendations:
        print(f"  [*] {rec}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_pcr(args: argparse.Namespace) -> None:
    vol = UnitParser.parse_volume(getattr(args, "volume", 50.0), "ul")
    tmpl = UnitParser.parse_mass(args.template_ng, "ng")
    amp_len = args.length
    if amp_len is None:
        raw_seq = _resolve_sequence(args)
        if raw_seq:
            amp_len = len(clean_sequence(raw_seq))
        else:
            print("Error: biolabcalc pcr requires -l/--length or -s/--sequence.", file=sys.stderr)
            sys.exit(1)
    res = calculate_pcr_kinetics(
        amplicon_len_bp=amp_len,
        template_ng=tmpl,
        cycles=args.cycles,
        reaction_volume_ul=vol,
    )

    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("PCR KINETICS & REACTION STOICHIOMETRY")
        print("=" * 65)
    print(f"Amplicon Length:            {res.amplicon_length_bp} bp (MW: {res.amplicon_mw:,.2f} Da)")
    print(f"Initial Template:           {res.template_initial_ng} ng ({res.template_initial_copies:,.0f} copies)")
    print(f"Cycles Run:                 {res.cycles_run} (Efficiency: {res.efficiency_percent:.1f}%)")
    print(f"Amplicon Yield:             {res.amplicon_yield_ng:.2f} ng ({res.amplicon_yield_pmol:.3f} pmol)")
    print(f"Limiting Reagent:           {res.limiting_reagent} ({res.limiting_dntp})")
    if res.dntp_exhaustion_cycle:
        print(f"Plateau Cycle:              Cycle {res.dntp_exhaustion_cycle}")
    print(f"Theoretical Max:            {res.theoretical_max_amplicon_ug:.2f} µg")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_pcr_opt(args: argparse.Namespace) -> None:
    res = optimize_pcr_protocol(
        primer_fwd_tm=args.fwd_tm,
        primer_rev_tm=args.rev_tm,
        amplicon_len_bp=args.length,
        polymerase=args.polymerase,
        gc_percent=args.gc,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 60)
        print("PCR PROTOCOL OPTIMIZATION")
        print("=" * 60)
    print(f"Polymerase:                 {res.polymerase.upper()}")
    print(f"Recommended Annealing Ta:   {res.annealing_temp_celsius:.1f} °C")
    print(f"Denaturation:               {res.denaturation_temp_celsius:.0f} °C")
    print(f"Extension Time:             {res.extension_time_seconds} sec at {res.extension_temp_celsius:.0f} °C")
    print(f"Touchdown Profile:          Start at {res.touchdown_initial_ta:.1f} °C for {res.touchdown_cycles} cycles")
    if res.recommended_additives:
        print("Additives:")
        for add in res.recommended_additives:
            print(f"  * {add}")
    print(f"Cycling Schedule:           {res.cycling_protocol_summary}")
    if not getattr(args, "quiet", False):
        print("=" * 60)


def handle_protein(args: argparse.Namespace) -> None:
    raw_prot_seq = _resolve_sequence(args)
    if not raw_prot_seq:
        print("Error: biolabcalc protein requires sequence via -s/--sequence, -f/--file, or stdin (-s -).", file=sys.stderr)
        sys.exit(1)
    res = quantify_protein_a280(
        seq=raw_prot_seq,
        a280_absorbance=args.a280,
        volume_ml=args.volume_ml,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("PROTEIN QUANTIFICATION (A280 BEER-LAMBERT)")
        print("=" * 65)
    print(f"Sequence Length:            {len(raw_prot_seq)} aa")
    print(f"Molecular Weight:           {res.molecular_weight:,.2f} Da")
    print(f"Molar Extinction ε280:      {res.extinction_coeff_m_cm:,} M^-1 cm^-1")
    print(f"Concentration:              {res.concentration_mg_ml:.4f} mg/mL ({res.concentration_ug_ml:.2f} µg/mL)")
    print(f"Molarity:                   {res.molarity_um:.2f} µM")
    print(f"Total Yield:                {res.total_yield_mg:.4f} mg ({res.total_yield_ug:,.1f} µg)")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_primers(args: argparse.Namespace) -> None:
    raw_prim_seq = _resolve_sequence(args)
    if not raw_prim_seq:
        print("Error: biolabcalc primers requires template sequence via -s/--sequence, -f/--file, or stdin (-s -).", file=sys.stderr)
        sys.exit(1)
    pairs = design_primers(
        raw_prim_seq,
        target_tm=args.target_tm,
    )
    if getattr(args, "json", False):
        _dump_json({"pairs_found": len(pairs), "pairs": [dataclasses.asdict(p) for p in pairs]}, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 70)
        print(f"THERMODYNAMIC PRIMER DESIGN RESULTS ({len(pairs)} pairs found)")
        print("=" * 70)
    for idx, p in enumerate(pairs, 1):
        print(f"Pair #{idx} (Score: {p.pair_quality_score}, Amplicon: {p.amplicon_length_bp} bp, ΔTm: {p.tm_difference:.1f}°C):")
        print(f"  Forward: {p.forward_primer.sequence} (Tm: {p.forward_primer.tm_celsius:.1f}°C, GC: {p.forward_primer.gc_percent:.1f}%, Clamp: {p.forward_primer.has_gc_clamp})")
        print(f"  Reverse: {p.reverse_primer.sequence} (Tm: {p.reverse_primer.tm_celsius:.1f}°C, GC: {p.reverse_primer.gc_percent:.1f}%, Clamp: {p.reverse_primer.has_gc_clamp})")
    if not getattr(args, "quiet", False):
        print("=" * 70)


def handle_ecoli(args: argparse.Namespace) -> None:
    g_res = calculate_ecoli_growth(
        initial_od600=args.init_od,
        target_od600=args.target_od,
        temperature_celsius=args.temp,
        media=args.media,
    )
    p_res = estimate_plasmid_yield(
        culture_volume_ml=args.vol_ml,
        final_od600=3.0,
        plasmid_type=args.plasmid,
    )
    _maybe_log_report(g_res, args)
    _maybe_log_report(p_res, args)
    if not getattr(args, "quiet", False):
        print("=" * 60)
        print("E. COLI GROWTH & PLASMID OPTIMIZATION")
        print("=" * 60)
    print(f"Doubling Time:              {g_res.doubling_time_min:.1f} min ({g_res.media} at {g_res.temperature_celsius}°C)")
    print(f"Time from OD {g_res.initial_od600} to {g_res.target_od600}:  {g_res.formatted_time} ({g_res.num_doublings} doublings)")
    print(f"Cell Density at Target OD:  {g_res.target_cells_per_ml:,.0f} cells/mL")
    if not getattr(args, "quiet", False):
        print("-" * 60)
    print(f"Estimated Plasmid Yield ({p_res.plasmid_type}, {p_res.culture_volume_ml:.0f} mL culture):")
    print(f"  Theoretical Yield:        {p_res.theoretical_yield_ug:,.1f} µg")
    print(f"  Typical Kit Recovery:     {p_res.typical_miniprep_yield_ug:,.1f} µg")
    if not getattr(args, "quiet", False):
        print("=" * 60)


def handle_excel_template(args: argparse.Namespace) -> None:
    if generate_lab_notebook_template is None:
        print("Error: Excel support is optional and requires openpyxl. Install with: pip install 'biolabcalc[excel]' or pip install openpyxl")
        sys.exit(1)
    path = generate_lab_notebook_template(args.output)
    print(f"Interactive Excel notebook template generated at: {path}")


def handle_annotate_gel(args: argparse.Namespace) -> None:
    if GelAnnotator is None:
        print("Error: Gel annotation requires matplotlib. Install with: pip install 'biolabcalc[gel]' or pip install matplotlib")
        sys.exit(1)
    lane_list = [l.strip() for l in args.lanes.split(",") if l.strip()]
    if args.image and os.path.exists(args.image):
        ann = GelAnnotator.from_image(args.image, title=args.title, gel_info=args.info, invert_colors=args.invert)
        ann.set_lanes(lane_list)
    else:
        ann = GelAnnotator.synthetic(num_lanes=len(lane_list), title=args.title, gel_info=args.info, invert_colors=args.invert)
        ann.set_lanes(lane_list)

    lad_choice = LADDER_ALIAS_MAP.get(args.ladder, args.ladder)
    ann.add_ladder(lane_index=args.ladder_lane, ladder_type=lad_choice, side=args.ladder_side)

    if args.bands:
        band_items = args.bands.split(",")
        for item in band_items:
            parts = item.strip().split(":")
            if len(parts) >= 2:
                l_idx = int(parts[0])
                s_val = float(parts[1])
                lbl = parts[2] if len(parts) > 2 else f"{s_val}"
                ann.add_band(lane_index=l_idx, size_bp_or_kda=s_val, label=lbl)

    from .gels import GelTypographyConfig

    typography = GelTypographyConfig(
        font_family=getattr(args, "font_family", "Arial, Helvetica, sans-serif"),
        font_scale=getattr(args, "font_scale", 1.0),
        show_lane_numbers=getattr(args, "show_lane_numbers", True),
        lane_number_style=getattr(args, "lane_number_style", "circle"),
        lane_number_format=getattr(args, "lane_number_format", "numeric"),
    )

    include_tbl = getattr(args, "include_table", False)
    img_out = ann.render(args.output, dpi=250, style=typography, include_table=include_tbl)
    print(f"Annotated gel figure saved to: {img_out}")

    if args.excel:
        xl_out = ann.embed_in_excel(args.excel, sheet_name="Annotated_Gel", style=typography)
        print(f"Gel figure and lane summary table embedded into Excel at: {xl_out}")


def handle_print_protocol(args: argparse.Namespace) -> None:
    from .printable_protocol import (
        build_bench_master_mix,
        generate_plate_bench_sheet,
        render_bench_companion_html,
        GLPSignOffBlock,
    )

    rxn_count = args.reactions
    overage_pct = args.overage

    samples = [s.strip() for s in args.samples.split(",") if s.strip()] if getattr(args, "samples", None) else []
    if not samples:
        samples = [f"Sample-{i+1}" for i in range(rxn_count)]

    template_type = getattr(args, "template", "pcr").lower()
    if template_type in ("pcr", "qpcr"):
        mix = build_bench_master_mix(
            components=[
                {"name": "Nuclease-Free Water", "stock_conc": "100%", "final_conc": "QS", "vol_ul": 14.0, "category": "water"},
                {"name": "5X Q5 Reaction Buffer", "stock_conc": "5X", "final_conc": "1X", "vol_ul": 5.0, "category": "buffer"},
                {"name": "dNTP Mix (10 mM each)", "stock_conc": "10 mM", "final_conc": "200 µM", "vol_ul": 0.5, "category": "dntp"},
                {"name": "Forward Primer (10 µM)", "stock_conc": "10 µM", "final_conc": "0.5 µM", "vol_ul": 1.25, "category": "primer"},
                {"name": "Reverse Primer (10 µM)", "stock_conc": "10 µM", "final_conc": "0.5 µM", "vol_ul": 1.25, "category": "primer"},
                {"name": "Template DNA (Separate)", "stock_conc": "50 ng/µL", "final_conc": "50 ng", "vol_ul": 2.5, "category": "template"},
                {"name": "Q5 High-Fidelity Polymerase", "stock_conc": "2 U/µL", "final_conc": "0.02 U/µL", "vol_ul": 0.5, "category": "enzyme"},
            ],
            total_reactions=rxn_count,
            reaction_volume_ul=25.0,
            excess_percent=overage_pct,
            separate_template=True,
        )
    elif template_type in ("digest", "restriction"):
        mix = build_bench_master_mix(
            components=[
                {"name": "Nuclease-Free Water", "stock_conc": "100%", "final_conc": "QS", "vol_ul": 38.0, "category": "water"},
                {"name": "10X rCutSmart Buffer", "stock_conc": "10X", "final_conc": "1X", "vol_ul": 5.0, "category": "buffer"},
                {"name": "Plasmid DNA (Separate)", "stock_conc": "200 ng/µL", "final_conc": "1 µg", "vol_ul": 5.0, "category": "template"},
                {"name": "Restriction Enzyme 1", "stock_conc": "20 U/µL", "final_conc": "20 U", "vol_ul": 1.0, "category": "enzyme"},
                {"name": "Restriction Enzyme 2", "stock_conc": "20 U/µL", "final_conc": "20 U", "vol_ul": 1.0, "category": "enzyme"},
            ],
            total_reactions=rxn_count,
            reaction_volume_ul=50.0,
            excess_percent=overage_pct,
            separate_template=True,
        )
    else:
        mix = build_bench_master_mix(
            components=[
                {"name": "Nuclease-Free Water", "stock_conc": "100%", "final_conc": "QS", "vol_ul": 15.0, "category": "water"},
                {"name": "2X Master Mix Buffer", "stock_conc": "2X", "final_conc": "1X", "vol_ul": 10.0, "category": "buffer"},
            ],
            total_reactions=rxn_count,
            reaction_volume_ul=25.0,
            excess_percent=overage_pct,
            separate_template=False,
        )

    plate = generate_plate_bench_sheet(
        samples=samples,
        plate_type=args.plate_type,
    )

    sign_off = GLPSignOffBlock(
        operator_name=getattr(args, "operator", "") or "",
        project_id=getattr(args, "project", "") or "",
        protocol_id=getattr(args, "protocol_id", "") or "SOP-BIO-01",
    )

    html_content = render_bench_companion_html(
        title=args.title,
        master_mix=mix,
        plate_map=plate,
        sign_off=sign_off,
        page_trim=args.trim_size,
    )

    out_file = args.output or "bench_protocol.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Printable benchtop protocol & plate sheet generated: {out_file}")
    print(f"  • Formulation: {rxn_count} reactions (+{overage_pct}% overage) -> {mix.master_mix_total_volume_ul:g} µL total mix ({mix.pipette_for_master_mix})")
    print(f"  • Plate Grid: {args.plate_type} with {plate.used_wells_count} wells mapped")
    print(f"  • Notebook Trim: {args.trim_size} with tamper-evident paste seams and GLP sign-off block")

    if getattr(args, "open_browser", False):
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(out_file)}")


def handle_interactive_gel(args: argparse.Namespace) -> None:
    if args.save_html:
        out_file = save_interactive_app(args.save_html)
        print(f"Interactive drag-and-drop gel annotator saved to: {out_file}")
        print(f"Open {out_file} in any web browser to use.")
    else:
        print(f"Starting BioLabCalc Interactive Drag-and-Drop Gel Annotator on port {args.port}...")
        launch_interactive_annotator(port=args.port, open_browser=not args.no_browser, blocking=True)


def handle_batch_excel(args: argparse.Namespace) -> None:
    if batch_process_excel is None:
        print("Error: Excel processing requires openpyxl. Install with: pip install 'biolabcalc[excel]' or pip install openpyxl")
        sys.exit(1)
    out_f = batch_process_excel(args.input, args.output)
    print(f"Batch sequence analysis complete! Results saved to: {out_f}")


def handle_digest(args: argparse.Namespace) -> None:
    seq_val = getattr(args, "sequence", None)
    plasmid_val = getattr(args, "plasmid", None)

    if seq_val or plasmid_val:
        if plasmid_val:
            target = load_plasmid(plasmid_val)
        else:
            target = clean_sequence(seq_val)

        enzymes = [args.enzyme_1]
        if args.enzyme_2:
            enzymes.append(args.enzyme_2)

        mass_ug = args.dna_ug if args.dna_ug is not None else 1.0
        vol_ul = args.volume if args.volume is not None else 50.0

        pred = predict_restriction_digest(
            seq_or_plasmid=target,
            enzymes=enzymes,
            dna_mass_ug=mass_ug,
            reaction_volume_ul=vol_ul,
        )
        _maybe_log_report(pred, args)
        if getattr(args, "json", False):
            _dump_json(pred, getattr(args, "compact", False))
            return

        if not getattr(args, "quiet", False):
            print("=" * 65)
            print(f"IN-SILICO RESTRICTION DIGEST PREDICTION: {pred.plasmid_name}")
            print("=" * 65)
        print(f"Substrate:            {pred.plasmid_name} ({pred.total_length_bp:,} bp, {pred.topology})")
        print(f"Restriction Enzymes:  {', '.join(pred.enzymes)}")
        print(f"Cut Sites Found:      {len(pred.cut_sites)}")
        print(f"Fragments Generated:  {pred.fragment_count}")
        if not getattr(args, "quiet", False):
            print("-" * 65)
            print("Fragment Analysis & Stoichiometry:")
            print(f"  {'#':2s} {'Length (bp)':12s} {'MW (Da)':12s} {'Mass (ng)':10s} {'Flanking Sites':25s}")
            print(f"  {'-'*2} {'-'*12} {'-'*12} {'-'*10} {'-'*25}")
        for frag in pred.fragments:
            flank = f"{frag.left_enzyme} / {frag.right_enzyme}"
            print(f"  {frag.fragment_id:2d} {frag.length_bp:10d} bp {frag.molecular_weight_da:10.1f} Da {frag.mass_ng:8.2f} ng {flank:25s}")

        if getattr(args, "simulate_gel", False):
            if not getattr(args, "quiet", False):
                print("-" * 65)
                print("Virtual Agarose Gel Migration:")
            frag_sizes = [float(f.length_bp) for f in pred.fragments]
            sim = simulate_gel(frag_sizes, ladder_key="1kb_dna")
            print(sim.ascii_visualization)

        if not getattr(args, "quiet", False):
            print("=" * 65)
        return

    mass_ug = args.dna_ug if args.dna_ug is not None else 1.0
    res = plan_restriction_digest(
        dna_mass_ug=mass_ug,
        reaction_volume_ul=args.volume,
        enzyme_1=args.enzyme_1,
        enzyme_2=args.enzyme_2,
        dna_conc_ng_ul=args.dna_conc,
    )

    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("RESTRICTION DIGESTION SETUP")
        print("=" * 65)
    print(f"Enzyme 1:             {res.enzyme_1.name} ({res.enzyme_1.recognition_site}, {res.enzyme_1.cut_type})")
    if res.enzyme_2:
        print(f"Enzyme 2:             {res.enzyme_2.name} ({res.enzyme_2.recognition_site}, {res.enzyme_2.cut_type})")
    print(f"Recommended Buffer:   {res.recommended_buffer}")
    print(f"Incubation:           {res.incubation_temp_celsius}°C for {res.incubation_time_min} min")
    print(f"Heat Inactivation:    {res.heat_inactivation}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Pipetting Recipe:")
    for comp, vol in res.reagent_volumes.items():
        print(f"  {comp:32s}: {vol:5.2f} µL")
    print(f"  Total Reaction Volume:          : {res.reaction_volume_ul:5.2f} µL")
    if res.notes:
        if not getattr(args, "quiet", False):
            print("Notes & Warnings:")
        for n in res.notes:
            print(f"  * {n}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_ligate(args: argparse.Namespace) -> None:
    res = calculate_ligation(
        vector_length_bp=args.vec_bp,
        insert_length_bp=args.ins_bp,
        vector_mass_ng=args.vec_ng,
        molar_ratio=args.ratio,
        reaction_volume_ul=args.volume,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("DNA LIGATION SETUP")
        print("=" * 65)
    print(f"Vector ({res.vector_length_bp} bp):         {res.vector_mass_ng} ng ({res.vector_pmol:.3f} pmol)")
    print(f"Insert ({res.insert_length_bp} bp):         {res.insert_mass_ng} ng ({res.insert_pmol:.3f} pmol)")
    print(f"Molar Ratio (Insert:Vector):{res.molar_ratio_insert_to_vector:.1f} : 1")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Pipetting Recipe:")
    for comp, vol in res.reagent_volumes.items():
        print(f"  {comp:35s}: {vol:5.2f} µL")
    print(f"Protocol: {res.incubation_guidelines}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_gibson(args: argparse.Namespace) -> None:
    res = calculate_gibson_assembly(
        vector_length_bp=args.vec_bp,
        insert_lengths_bp=args.ins_bp,
        vector_mass_ng=args.vec_ng,
        molar_ratio=args.ratio,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("GIBSON ASSEMBLY / NEBUILDER SETUP")
        print("=" * 65)
    print(f"Vector ({res.vector_length_bp} bp):         {res.vector_mass_ng} ng")
    for idx, (ins_len, ins_m) in enumerate(zip(res.insert_lengths_bp, res.insert_masses_ng), 1):
        print(f"Insert #{idx} ({ins_len} bp):         {ins_m} ng")
    print(f"Total DNA Input:            {res.total_dna_pmol:.3f} pmol (Optimal: 0.02 - 0.2 pmol)")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Pipetting Recipe:")
    for comp, vol in res.reagent_volumes.items():
        print(f"  {comp:35s}: {vol:5.2f} µL")
    print(f"Protocol: {res.incubation_protocol}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_buffer(args: argparse.Namespace) -> None:
    if getattr(args, "equil", None):
        from .buffers import solve_buffer_equilibrium
        res = solve_buffer_equilibrium(
            components=args.equil,
            target_ph=getattr(args, "ph", 7.4),
            temperature_celsius=getattr(args, "temp", 25.0),
            output_temp_celsius=getattr(args, "output_temp", getattr(args, "temp", 37.0)),
        )
        if getattr(args, "json", False):
            import dataclasses
            print(json.dumps(dataclasses.asdict(res), indent=2))
            return
        print("=" * 70)
        print("  BUFFER EQUILIBRIUM & COMPETITIVE SPECIATION ANALYSIS")
        print("=" * 70)
        print(f"Target pH:            {res.target_ph:.2f}")
        print(f"Temperature:          {res.temperature_celsius:.1f} °C")
        print(f"Ionic Strength (I):   {res.ionic_strength_m:.4f} M")
        print(f"Buffer Capacity (β):  {res.buffer_capacity_beta:.4f} M/pH")
        print(f"Free Mg2+:            {res.free_mg_conc_m * 1000.0:.3f} mM")
        print(f"Free Ca2+:            {res.free_ca_conc_m * 1000.0:.3f} mM")
        print(f"Free ATP:             {res.free_atp_conc_m * 1000.0:.3f} mM")
        print("\nPredicted Species Concentrations:")
        for sp in res.species:
            print(f"  - {sp.name:<28s}: {sp.concentration_m * 1000.0:8.3f} mM ({sp.fraction_of_total * 100.0:5.1f}%) [z={sp.charge:+d}]")
        if res.precipitation_risks:
            print("\nPrecipitation Screening:")
            for p in res.precipitation_risks:
                status = "⚠️ PRECIPITATION RISK" if p.will_precipitate else "✓ Soluble"
                print(f"  - {p.salt_name}: SI={p.saturation_index:.2f} ({status})")
        print("=" * 70)
        return

    if args.list or args.list_custom:
        if not getattr(args, "quiet", False):
            print("=" * 65)
            print("LABORATORY BUFFER CATALOG")
            print("=" * 65)
        if not args.list_custom:
            print("Standard Buffers:")
            for k, v in BUFFER_CATALOG.items():
                print(f"  - {k:18s}: {v.get('name', k)}")
        c_bufs = list_custom_buffers()
        if c_bufs:
            print("\nCustom User-Defined Buffers:")
            for cb in c_bufs:
                print(f"  * {cb}")
        elif args.list_custom:
            print("No custom buffers saved on disk yet. Create one with: biolabcalc buffer --custom")
        if not getattr(args, "quiet", False):
            print("=" * 65)
        return

    if args.custom:
        print("=" * 65)
        print("🧪 INTERACTIVE CUSTOM BUFFER BUILDER")
        print("=" * 65)
        b_name = input("Custom Buffer Name (e.g. HEPES-NaCl Lysis): ").strip()
        if not b_name:
            print("Buffer name is required.")
            return
        b_ph = input("Target pH (e.g. 7.5): ").strip() or "7.5"
        b_vol_s = input("Target Preparation Volume in mL [1000]: ").strip()
        b_vol = float(b_vol_s) if b_vol_s else 1000.0
        b_storage = input("Storage Conditions [Room temperature or 4°C]: ").strip() or "Room temperature or 4°C"

        builder = CustomBufferBuilder(name=b_name, ph=b_ph, storage=b_storage)

        print("\nAdd Components (type 'done' when finished):")
        while True:
            c_name = input("\nComponent Name (or 'done' to finish): ").strip()
            if not c_name or c_name.lower() == "done":
                break
            print("Component Type:")
            print("  1. Solid Chemical (specify target mM and molecular weight in g/mol)")
            print("  2. Concentrated Liquid Stock (specify target mM and stock mM)")
            print("  3. Percent Solution (specify % w/v or % v/v)")
            t_choice = input("Select type [1/2/3]: ").strip()

            if t_choice == "2":
                t_conc = float(input("  Target Concentration in mM (e.g. 150): ").strip())
                s_conc = float(input("  Stock Concentration in mM (e.g. 5000 for 5 M): ").strip())
                builder.add_liquid_stock(c_name, target_conc_mm=t_conc, stock_conc_mm=s_conc)
            elif t_choice == "3":
                pct = float(input("  Target Percent (e.g. 0.1 for 0.1%): ").strip())
                is_v = input("  Is this percent by volume (v/v)? [y/n]: ").strip().lower() != "n"
                builder.add_percent(c_name, target_percent=pct, is_volume=is_v)
            else:  # Default solid
                t_conc = float(input("  Target Concentration in mM (e.g. 50): ").strip())
                mw = float(input("  Molecular Weight in g/mol (e.g. 238.3 for HEPES): ").strip())
                builder.add_solid(c_name, target_conc_mm=t_conc, mw_g_mol=mw)

            print(f"  [+] Added {c_name} to {b_name}")

        res = builder.build(target_volume_ml=b_vol)

        save_q = input("\nSave this custom buffer to disk for future sessions? [y/n]: ").strip().lower()
        if save_q == "y":
            builder.save()
            print(f"[OK] Saved custom buffer '{b_name}' to disk storage!")

    elif args.buffer:
        res = calculate_buffer_recipe(args.buffer, args.volume_ml)
    else:
        print("Error: Specify a buffer name with -b / --buffer, or launch custom builder with --custom.")
        print("To list available buffers: biolabcalc buffer --list")
        return

    _maybe_log_report(res, args)
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print(f"BUFFER RECIPE: {res.name}")
        print("=" * 65)
    print(f"Target Volume:        {res.target_volume_ml:,.0f} mL ({res.target_volume_ml / 1000.0:.2f} L)")
    print(f"Target pH:            {res.ph_specification}")
    print(f"Storage:              {res.storage_conditions}")
    if res.safety_notes:
        print(f"Safety:               {res.safety_notes}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Reagent Formulations:")
    for c in res.components:
        cas_str = f"({c.cas_or_mw})" if c.cas_or_mw else ""
        print(f"  {c.name:28s}: {c.amount:8.3f} {c.unit}  [{c.molar_concentration}] {cas_str}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Preparation Instructions:")
    for idx, s in enumerate(res.preparation_steps, 1):
        print(f"  {idx}. {s}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_precipitate(args: argparse.Namespace) -> None:
    res = calculate_precipitation(
        sample_volume_ul=args.volume_ul,
        nucleic_acid=args.type,
        alcohol=args.alcohol,
        salt=args.salt,
        low_concentration_carrier=args.carrier,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print(f"NUCLEIC ACID PRECIPITATION PROTOCOL ({res.nucleic_acid_type})")
        print("=" * 65)
    print(f"Sample Volume:        {res.sample_volume_ul:.1f} µL")
    print(f"Salt Added:           {res.salt_type} ({res.salt_volume_ul:.1f} µL)")
    print(f"Alcohol Added:        {res.alcohol_type} ({res.alcohol_volume_ul:.1f} µL)")
    print(f"Carrier Added:        {res.carrier_added}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Procedure:")
    print(f"  1. Incubation:      {res.incubation_temp}")
    print(f"  2. Centrifuge:      Spin at {res.centrifugation_speed} for {res.centrifugation_time_min} min at 4°C.")
    print(f"  3. Supernatant:     Carefully aspirate supernatant without dislodging pellet.")
    print(f"  4. Wash:            Add {res.wash_volume_70pct_ethanol_ul:.0f} µL 70% ethanol, spin 5 min, remove supernatant.")
    print(f"  5. Dry:             {res.drying_instructions}")
    print(f"  6. Resuspend:       {res.resuspension_guidelines}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_ntp_ph(args: argparse.Namespace) -> None:
    res = calculate_ntp_ph_adjustment(
        initial_volume_ml=args.initial_vol,
        initial_conc_mm=args.initial_conc,
        target_volume_ml=args.target_vol,
        target_conc_mm=args.target_conc,
        target_ph=args.target_ph,
        starting_form=args.form,
        ntp_species=args.species,
        naoh_stock_m=args.base_molarity,
    )
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("NTP SOLUTION PREPARATION & pH ADJUSTMENT")
        print("=" * 65)
    print(f"Target Solution:      {res.target_conc_mm:.1f} mM {res.ntp_species} (Total Volume: {res.target_volume_ml:.1f} mL)")
    print(f"Target pH:            {res.target_ph:.2f}")
    print(f"Starting Stock:       {res.initial_volume_ml:.1f} mL @ {res.initial_conc_mm:.1f} mM ({res.starting_form})")
    print(f"Total NTP Quantity:   {res.total_ntp_mmol * 1000.0:,.1f} µmol ({res.total_ntp_mmol:.3f} mmol)")
    print(f"OH- Equivalents:      {res.naoh_equivalents:.3f} eq / mol NTP")
    print(f"Total NaOH Required:  {res.naoh_mmol * 1000.0:,.1f} µmol ({res.naoh_mmol:.4f} mmol)")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Calculated NaOH Volumes by Stock Concentration:")
    for stock_c, vol_ul in res.naoh_volume_ul.items():
        print(f"  {stock_c:5s} NaOH: {vol_ul:8.1f} µL ({vol_ul / 1000.0:.3f} mL)")
    print(f"Diluent Water (approx): {res.water_volume_ml:.3f} mL (bring to {res.target_volume_ml:.1f} mL mark)")
    if not getattr(args, "quiet", False):
        print("-" * 65)
    if res.warnings:
        print("WARNINGS & SAFETY:")
        for w in res.warnings:
            print(f"  [!] {w}")
        if not getattr(args, "quiet", False):
            print("-" * 65)
    print("LOGIC & ERROR CHECKS:")
    for lc in res.logic_checks:
        print(f"  [*] {lc}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("BENCH PROTOCOL & PIPETTING INSTRUCTIONS:")
    for s in res.preparation_steps:
        print(f"  {s}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_golden_gate(args: argparse.Namespace) -> None:
    res = calculate_golden_gate_assembly(
        vector_length_bp=args.vec_bp,
        insert_lengths_bp=args.ins_bp,
        target_vector_fmol=args.fmol,
        type_iis_enzyme=args.enzyme,
        insert_to_vector_ratio=args.ratio,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print(f"GOLDEN GATE ASSEMBLY SETUP ({res.enzyme})")
        print("=" * 65)
    print(f"Vector ({res.vector_length_bp} bp):         {res.vector_mass_ng:.1f} ng ({res.vector_fmol:.1f} fmol)")
    for idx, (ins_len, ins_m, ins_f) in enumerate(zip(res.insert_lengths_bp, res.insert_masses_ng, res.insert_fmols), 1):
        print(f"Insert #{idx} ({ins_len} bp):         {ins_m:.1f} ng ({ins_f:.1f} fmol)")
    print(f"Insert:Vector Molar Ratio:  {res.insert_to_vector_ratio:.1f} : 1")
    print(f"Total DNA Mass:             {res.total_dna_mass_ng:.1f} ng")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("1-Pot Pipetting Recipe:")
    for comp, vol in res.reagent_volumes.items():
        print(f"  {comp:35s}: {vol:5.2f} µL")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Thermocycling Schedule:")
    for step in res.thermocycling_protocol:
        print(f"  {step}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_purity(args: argparse.Namespace) -> None:
    res = assess_nanodrop_purity(
        a260=args.a260,
        a280=args.a280,
        a230=args.a230,
        sample_type=args.type,
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print(f"NANODROP NUCLEIC ACID PURITY ASSESSMENT ({res.sample_type})")
        print("=" * 65)
    print(f"Absorbance Readings:        A260 = {res.a260:.3f} | A280 = {res.a280:.3f} | A230 = {res.a230:.3f}")
    print(f"A260 / A280 Ratio:          {res.a260_a280_ratio:.2f} (Ideal: ~2.0 for RNA, ~1.8 for DNA)")
    print(f"A260 / A230 Ratio:          {res.a260_a230_ratio:.2f} (Ideal: 2.0 – 2.2)")
    print(f"Purity Status:              {res.purity_status.upper()}")
    print(f"Estimated True Conc.:       {res.corrected_concentration_ng_ul:.1f} ng/µL")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Diagnostic Observations:")
    for diag in res.diagnostic_feedback:
        print(f"  * {diag}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_pci(args: argparse.Namespace) -> None:
    res = calculate_phenol_chloroform_extraction(
        sample_volume_ul=args.volume,
        nucleic_acid=args.type,
        phenol_ph=args.ph,
    )
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print("PHENOL:CHLOROFORM EXTRACTION PROTOCOL")
        print("=" * 65)
    print(f"Reagent Grade:              {res.phenol_type}")
    print(f"Target Nucleic Acid:        {res.target_nucleic_acid}")
    print(f"Aqueous Phase Behavior:     {res.aqueous_phase_layer}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Pipetting Recipe:")
    for comp, vol in res.reagent_volumes.items():
        print(f"  {comp:35s}: {vol:5.2f} µL")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Protocol Steps:")
    for s in res.protocol_steps:
        print(f"  {s}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Safety Hazards:")
    for n in res.safety_notes:
        print(f"  [!] {n}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_ivt_time(args: argparse.Namespace) -> None:
    res = optimize_transcription_time(
        transcript_length_nt=args.length,
        temperature_celsius=args.temp,
        use_pyrophosphatase=not args.no_ipp,
    )
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 65)
        print(f"IVT TRANSCRIPTION TIME & KINETIC OPTIMIZATION ({args.length} nt)")
        print("=" * 65)
    print(f"Incubation Temperature:     {res.temperature_celsius:.1f} °C ({res.temperature_mode})")
    print(f"Recommended Reaction Time:  {res.recommended_time_hours:.2f} hours (Window: {res.recommended_time_range_hours[0]:.1f}–{res.recommended_time_range_hours[1]:.1f} h)")
    print(f"Plateau Time:               ~{res.plateau_time_hours:.2f} hours")
    print(f"3' Heterogeneity Hazard:    {res.risk_of_3prime_heterogeneity}")
    print(f"Degradation Hazard:         {res.risk_of_degradation}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Predicted Synthesis Trajectory:")
    for pt in res.time_course_predictions:
        print(f"  {pt['time_hours']:4.2f} h : {pt['estimated_percent_max_yield']:5.1f}% yield -> {pt['reaction_phase']}")
    if not getattr(args, "quiet", False):
        print("-" * 65)
        print("Benchtop Guidelines:")
    for g in res.guidelines:
        print(f"  * {g}")
    if not getattr(args, "quiet", False):
        print("=" * 65)


def handle_hepes(args: argparse.Namespace) -> None:
    vol_ml = UnitParser.parse_volume(args.volume, "ml")
    res = calculate_hepes_ivt_buffer(
        target_volume_ml=vol_ml,
        stock_multiplier=args.stock,
        target_ph_37c=args.ph,
    )
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return
    if not getattr(args, "quiet", False):
        print("=" * 70)
        print(f"{res.stock_multiplier}X HEPES-KOH IVT REACTION BUFFER RECIPE ({res.target_volume_ml:.1f} mL)")
        print("=" * 70)
    print(f"Target Reaction pH (37°C):   {res.target_ph_37c:.2f}")
    print(f"Preparation pH (25°C):       {res.preparation_ph_25c:.2f} (compensates for ΔpKa/ΔT = -0.014/°C)")
    if not getattr(args, "quiet", False):
        print("-" * 70)
        print("Component Formula & Concentrations:")
    for comp in res.components:
        print(f"  {comp.name:25s}: {comp.amount:6.3f} {comp.unit:4s} ({comp.molar_concentration})")
    if not getattr(args, "quiet", False):
        print("-" * 70)
    print(f"Buffer Advantage: {res.buffering_capacity_comparison}")
    if not getattr(args, "quiet", False):
        print("-" * 70)
        print("Preparation Steps:")
    for s in res.preparation_steps:
        print(f"  {s}")
    if not getattr(args, "quiet", False):
        print("=" * 70)


def handle_western(args: argparse.Namespace) -> None:
    if args.troubleshoot:
        t_res = troubleshoot_western_blot(args.troubleshoot)
        if not getattr(args, "quiet", False):
            print("=" * 70)
            print(f"WESTERN BLOT DIAGNOSTIC & TROUBLESHOOTING: {t_res.symptom}")
            print("=" * 70)
            print("Likely Root Causes:")
        for c in t_res.likely_causes:
            print(f"  * {c}")
        if not getattr(args, "quiet", False):
            print("-" * 70)
            print("Corrective Actions:")
        for a in t_res.corrective_actions:
            print(f"  [+] {a}")
        if not getattr(args, "quiet", False):
            print("-" * 70)
        print(f"Preventative Guideline: {t_res.preventative_protocol}")
        if not getattr(args, "quiet", False):
            print("=" * 70)
        return

    if args.mw is None:
        print("Error: Target molecular weight in kDa (--mw / -m) is required to plan a Western blot.", file=sys.stderr)
        sys.exit(1)

    mem_type = "pvdf"
    is_mem_prot = args.membrane_protein
    if args.membrane == "pvdf_flag":
        is_mem_prot = True
        mem_type = "pvdf"
    elif args.membrane in ("pvdf", "nitrocellulose"):
        mem_type = args.membrane

    plan = plan_western_blot(
        target_protein_name=args.name,
        target_mw_kda=args.mw,
        lysate_conc_mg_ml=args.conc,
        target_protein_ug_per_lane=args.load_ug,
        is_phospho_target=args.phospho,
        is_membrane_protein=is_mem_prot,
        transfer_system=args.transfer,
        membrane_type=mem_type,
    )

    if not getattr(args, "quiet", False):
        print("=" * 70)
        print(f"WESTERN BLOT EXPERIMENTAL PLAN: {plan.target_protein_name} ({plan.target_mw_kda:.1f} kDa)")
        print("=" * 70)
    print("1. GEL RESOLUTION & RUNNING CONDITIONS:")
    print(f"   Recommended Matrix:    {plan.recommended_gel_percentage}")
    print(f"   Running Parameters:    {plan.running_conditions}")
    if not getattr(args, "quiet", False):
        print("-" * 70)
    print(f"2. SAMPLE PREPARATION & LOADING (Target: {plan.sample_prep.target_protein_ug_per_lane:.1f} µg / lane):")
    print(f"   Lysate Stock Conc:     {plan.sample_prep.lysate_conc_mg_ml:.2f} mg/mL")
    print(f"   Per-Lane Volumes:      {plan.sample_prep.lysate_volume_per_lane_ul:.2f} µL Lysate + {plan.sample_prep.sample_buffer_volume_per_lane_ul:.2f} µL 4X Sample Buffer")
    print(f"   Total Lane Volume:     {plan.sample_prep.total_volume_per_lane_ul:.1f} µL")
    print(f"   Denaturation:          {plan.sample_prep.denaturation_temperature_celsius}°C for {plan.sample_prep.denaturation_time_minutes} minutes")
    for n in plan.sample_prep.notes:
        print(f"   * {n}")
    if not getattr(args, "quiet", False):
        print("-" * 70)
    print(f"3. ELECTROTRANSFER CONDITIONS ({plan.transfer_setup.transfer_system.upper()} -> {plan.transfer_setup.membrane_type}):")
    print(f"   Membrane Pore Size:    {plan.transfer_setup.pore_size_um} µm")
    print(f"   Membrane Activation:   {plan.transfer_setup.activation_instructions}")
    print(f"   Transfer Buffer:       {plan.transfer_setup.transfer_buffer_name}")
    for comp, amt in plan.transfer_setup.transfer_buffer_recipe.items():
        print(f"     - {comp:22s}: {amt}")
    print(f"   Transfer Run:          {plan.transfer_setup.voltage_or_current} for {plan.transfer_setup.duration_minutes} min ({plan.transfer_setup.temperature_conditions})")
    for tip in plan.transfer_setup.expert_tips:
        print(f"   * Tip: {tip}")
    if not getattr(args, "quiet", False):
        print("-" * 70)
    print("4. IMMUNODETECTION & BLOCKING:")
    print(f"   Blocking Solution:     {plan.immunodetection.blocking_agent}")
    print(f"   Primary Antibody:      {plan.immunodetection.primary_antibody_dilution} ({plan.immunodetection.primary_antibody_volume_ul:.1f} µL in {plan.immunodetection.incubation_volume_ml:.1f} mL)")
    print(f"   Primary Incubation:    {plan.immunodetection.primary_incubation}")
    print(f"   Secondary Antibody:    {plan.immunodetection.secondary_antibody_dilution} ({plan.immunodetection.secondary_antibody_volume_ul:.1f} µL in {plan.immunodetection.incubation_volume_ml:.1f} mL)")
    print(f"   Wash Protocol:         {plan.immunodetection.wash_schedule}")
    for w in plan.immunodetection.compatibility_warnings:
        print(f"   [!] {w}")
    if not getattr(args, "quiet", False):
        print("-" * 70)
    print("5. DETECTION & IMAGING:")
    print(f"   Substrate:             {plan.detection_substrate}")
    print(f"   Imaging Protocol:      {plan.imaging_guidelines}")
    if not getattr(args, "quiet", False):
        print("=" * 70)


def handle_report(args: argparse.Namespace) -> None:
    rep = get_active_report()
    if args.title != "Laboratory Experiment Report":
        rep.title = args.title
    if args.researcher != "Researcher":
        rep.experimenter = args.researcher
    if args.project != "General":
        rep.project = args.project
    if args.obj:
        rep.objective = args.obj

    if args.interactive:
        print("=" * 65)
        print("🔬 INTERACTIVE LABORATORY DATA RECORDER")
        print("=" * 65)
        t = input(f"Experiment Title [{rep.title}]: ").strip()
        if t: rep.title = t
        r = input(f"Researcher Name [{rep.experimenter}]: ").strip()
        if r: rep.experimenter = r
        p = input(f"Project ID [{rep.project}]: ").strip()
        if p: rep.project = p
        o = input("Experimental Objective (optional): ").strip()
        if o: rep.objective = o

        print("-" * 65)
        print("Enter measurements (press Ctrl+C or enter empty Sample ID to finish):")
        while True:
            s_id = input("\nSample ID (or Enter to finish): ").strip()
            if not s_id:
                break
            param = input("Parameter / Assay (e.g. Yield, A260, Conc): ").strip()
            val_s = input("Measured Value: ").strip()
            try:
                val = float(val_s)
            except ValueError:
                print("Invalid number, skipping.")
                continue
            unit = input("Unit (e.g. ug, ng/uL, AU): ").strip()
            tgt_s = input("Target / Expected Value (optional, Enter to skip): ").strip()
            tgt = float(tgt_s) if tgt_s else None
            tol_s = input("Tolerance % (optional, Enter to skip): ").strip()
            tol = float(tol_s) if tol_s else None
            notes = input("Bench Notes (optional): ").strip()

            rec = rep.add_record(s_id, param, val, unit, target=tgt, tolerance_pct=tol, notes=notes)
            print(f"  [+] Logged: {rec.sample_id} | {rec.parameter} = {rec.value} {rec.unit} -> QC: {rec.status}")

        c_text = input("\nAdd Conclusion / Key Takeaway (optional): ").strip()
        if c_text:
            rep.add_conclusion(c_text)

    elif args.sample and args.value is not None:
        param = args.param or "Measurement"
        rec = rep.add_record(
            sample_id=args.sample,
            parameter=param,
            value=args.value,
            unit=args.unit,
            target=args.target,
            tolerance_pct=args.tolerance,
            notes=args.notes,
        )
        print(f"Logged measurement: {rec.sample_id} | {rec.parameter} = {rec.value} {rec.unit} (Status: {rec.status})")

    if args.conclusion:
        rep.add_conclusion(args.conclusion)

    # Print summary markdown in terminal
    md_text = rep.to_markdown()
    print("\n" + md_text)

    if args.output:
        out_ext = os.path.splitext(args.output)[1].lower()
        if out_ext == ".xlsx":
            out_path = rep.to_excel(args.output)
        elif out_ext == ".csv":
            out_path = rep.to_csv(args.output)
        elif out_ext == ".json":
            out_path = rep.to_json(args.output)
        else:
            out_path = rep.to_markdown(args.output)
        print(f"[OK] Lab report successfully exported to: {args.output}")


def handle_eln(args: argparse.Namespace) -> None:
    if getattr(args, "generate_config", False):
        from .eln.config import dump_simple_yaml, DEFAULT_CONFIG
        out_path = "config.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(dump_simple_yaml(DEFAULT_CONFIG))
        print(f"[OK] Default ELN configuration generated: {out_path}")
        return

    from .eln.server import launch_eln_server
    open_browser = None if getattr(args, "no_browser", None) is None else (not args.no_browser)
    launch_eln_server(
        host=args.host,
        port=args.port,
        db_url=args.db_url,
        open_browser=open_browser,
        quiet=getattr(args, "quiet", False),
        config_path=getattr(args, "config", None),
        anonymize=getattr(args, "anonymize", None),
    )


def handle_diagnostics(args: argparse.Namespace) -> None:
    try:
        from .diagnostics import get_recent_failures, clear_failures
    except ImportError:
        print("[!] Diagnostics subsystem unavailable.")
        return

    if getattr(args, "clear", False):
        clear_failures()
        print("[OK] Diagnostic failure logs successfully cleared.")
        return

    limit = getattr(args, "tail", 10) or 10
    failures = get_recent_failures(limit=limit)

    if getattr(args, "json", False):
        _dump_json({"failures": failures, "count": len(failures)}, getattr(args, "compact", False))
        return

    if not failures:
        print("=" * 70)
        print("  BIOLABCALC SYSTEM DIAGNOSTICS: NO FAILURES RECORDED")
        print("=" * 70)
        print("[OK] All network connections, databases, and parsers operating normally.")
        print("=" * 70)
        return

    print("=" * 70)
    print(f"  BIOLABCALC SYSTEM DIAGNOSTICS: RECENT FAILURES (LAST {len(failures)})")
    print("=" * 70)
    for i, fail in enumerate(failures, 1):
        ts = fail.get("timestamp", "Unknown")
        sub = fail.get("subsystem", "GENERAL")
        err = fail.get("error_type", "Error")
        msg = fail.get("error_message", "")
        cause = fail.get("plain_english_cause", "")
        remedies = fail.get("remediation_suggestions", [])

        print(f"\n[{i}] {ts} | Subsystem: {sub} | Type: {err}")
        print(f"    Message: {msg}")
        if cause:
            print(f"    Cause:   {cause}")
        if remedies:
            print(f"    Remediation Guidance:")
            for r in remedies:
                print(f"      - {r}")
    print("\n" + "=" * 70)


def handle_setup(args: argparse.Namespace) -> None:
    try:
        from .setup_wizard import run_setup_wizard
        run_setup_wizard(
            non_interactive=getattr(args, "non_interactive", False),
            shared_dir=getattr(args, "shared_dir", None),
            role=getattr(args, "role", None),
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8080),
        )
    except Exception as e:
        print(f"[!] Setup wizard error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_portable(args: argparse.Namespace) -> None:
    from .eln.config import load_config
    cfg = load_config()
    db_cfg = cfg.get("database", {})
    sec_cfg = cfg.get("security", {})
    srv_cfg = cfg.get("server", {})
    gov_cfg = cfg.get("governance", {})

    print("=" * 70)
    print("  BIOLABCALC PORTABLE ENVIRONMENT & SHARED DRIVE STATUS")
    print("=" * 70)
    print(f"[*] Storage Mode:        {db_cfg.get('storage_mode', 'local')}")
    print(f"[*] Shared Folder:       {db_cfg.get('shared_folder_path') or 'Not configured (using local)'}")
    print(f"[*] Database URL:        {db_cfg.get('url') or 'Default local SQLite'}")
    print(f"[*] CAS Blob Storage:    {db_cfg.get('storage_dir') or '.biolabcalc_data'}")
    print(f"[*] Server Address:      http://{srv_cfg.get('host', '127.0.0.1')}:{srv_cfg.get('port', 8080)}")
    print(f"[*] Lock Timeout:        {db_cfg.get('lock_timeout_seconds', 60)}s")
    print(f"[*] Approval Policy:     {gov_cfg.get('default_approval_policy', 'peer_review')}")
    print(f"[*] Anonymized Logs:     {sec_cfg.get('anonymize_logs', True)}")
    print("=" * 70)



def handle_convert(args: argparse.Namespace) -> None:
    try:
        converted = easy_convert(args.val, args.to_unit, mw=args.mw)
        _maybe_log_report({"converted_result": converted}, args)
        if getattr(args, "json", False):
            _dump_json({
                "input": args.val,
                "target_unit": args.to_unit,
                "mw": args.mw,
                "result": converted
            }, getattr(args, "compact", False))
            return
        if not getattr(args, "quiet", False):
            print("=" * 60)
            print("LABORATORY UNIT & STOICHIOMETRY CONVERSION")
            print("=" * 60)
        print(f"Input Quantity:       {args.val}")
        print(f"Target Unit:          {args.to_unit}")
        if args.mw:
            print(f"Molecular Weight:     {args.mw:,.2f} Da (g/mol)")
        print(f"Converted Result:     {converted} {args.to_unit}")
        if not getattr(args, "quiet", False):
            print("=" * 60)
    except Exception as e:
        if getattr(args, "json", False):
            _dump_json({"error": str(e)}, getattr(args, "compact", False))
        else:
            print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)


def handle_batch_csv(args: argparse.Namespace) -> None:
    try:
        summary = process_batch_csv(
            input_path=args.input,
            output_path=args.output,
            delimiter=args.delimiter,
        )
        if getattr(args, "json", False):
            _dump_json(summary, getattr(args, "compact", False))
            return
        if not getattr(args, "quiet", False):
            print("=" * 65)
            print("BATCH CSV / TSV SEQUENCE ANALYSIS COMPLETE")
            print("=" * 65)
        print(f"Input File:           {summary['input_path']}")
        print(f"Output File:          {summary['output_path']}")
        print(f"Delimiter:            {repr(summary['delimiter'])}")
        print(f"Total Rows:           {summary['total_rows']}")
        print(f"Successfully Analyzed:{summary['success_count']}")
        print(f"Errors Encountered:   {summary['error_count']}")
        if not getattr(args, "quiet", False):
            print("=" * 65)
    except Exception as e:
        if getattr(args, "json", False):
            _dump_json({"error": str(e)}, getattr(args, "compact", False))
        else:
            print(f"Error during batch CSV processing: {e}", file=sys.stderr)
        sys.exit(1)


def handle_rc(args: argparse.Namespace) -> None:
    raw_seq = _resolve_sequence(args)
    if not raw_seq:
        print("Error: biolabcalc rc requires sequence via -s/--sequence, -f/--file, or stdin (-s -).", file=sys.stderr)
        sys.exit(1)
    rc_seq = reverse_complement(raw_seq, seq_type=args.type)
    if getattr(args, "json", False):
        _dump_json(
            {"sequence": raw_seq, "type": args.type, "reverse_complement": rc_seq},
            compact=getattr(args, "compact", False),
        )
        return
    if getattr(args, "quiet", False):
        print(rc_seq)
        return
    print("=" * 60)
    print("5' -> 3' REVERSE COMPLEMENT")
    print("=" * 60)
    print(f"Input Sequence ({args.type.upper()}):  {raw_seq}")
    print(f"Reverse Complement:  {rc_seq}")
    print("=" * 60)


def handle_translate(args: argparse.Namespace) -> None:
    raw_seq = _resolve_sequence(args)
    if not raw_seq:
        print("Error: biolabcalc translate requires sequence via -s/--sequence, -f/--file, or stdin (-s -).", file=sys.stderr)
        sys.exit(1)

    to_stop = getattr(args, "to_stop", False)

    if getattr(args, "all_frames", False):
        frames = [1, 2, 3, -1, -2, -3]
        translations = {
            f"+{f}" if f > 0 else str(f): translate_dna(raw_seq, frame=f, to_stop=to_stop)
            for f in frames
        }
        if getattr(args, "json", False):
            _dump_json(
                {
                    "sequence": raw_seq,
                    "translations": translations,
                    "frames": translations,
                    **translations,
                },
                compact=getattr(args, "compact", False),
            )
            return
        if getattr(args, "quiet", False):
            for f in frames:
                lbl = f"+{f}" if f > 0 else str(f)
                print(f"{lbl}: {translations[lbl]}")
            return
        print("=" * 65)
        print("6-FRAME NUCLEOTIDE TRANSLATION")
        print("=" * 65)
        print(f"Input Sequence: {raw_seq}")
        print("-" * 65)
        for f in frames:
            lbl = f"+{f}" if f > 0 else str(f)
            tr = translations[lbl]
            print(f"Frame {lbl:2s} ({len(tr)} aa): {tr}")
        print("=" * 65)
    else:
        frame = getattr(args, "frame", 1)
        prot = translate_dna(raw_seq, frame=frame, to_stop=to_stop)
        if getattr(args, "json", False):
            _dump_json(
                {
                    "sequence": raw_seq,
                    "frame": frame,
                    "translation": prot,
                    "protein": prot,
                    "length": len(prot),
                },
                compact=getattr(args, "compact", False),
            )
            return
        if getattr(args, "quiet", False):
            print(prot)
            return
        print("=" * 60)
        print(f"NUCLEOTIDE TRANSLATION (FRAME {frame:+d})")
        print("=" * 60)
        print(f"Input Sequence:       {raw_seq}")
        print(f"Reading Frame:        {frame:+d}")
        print(f"Protein Length:       {len(prot)} aa")
        print(f"Translated Sequence:  {prot}")
        print("=" * 60)


def handle_seq(args: argparse.Namespace) -> None:
    action = getattr(args, "seq_action", None)
    if action == "save":
        seq_text = _resolve_sequence(args)
        if not seq_text:
            print("Error: biolabcalc seq save requires sequence via -s/--sequence, -f/--file, or stdin.", file=sys.stderr)
            sys.exit(1)
        name = args.name or f"seq_{len(seq_text)}bp"
        rec = SequenceRecord(
            id=name,
            name=name,
            sequence=seq_text,
            seq_type=getattr(args, "type", "dna"),
            description=getattr(args, "desc", ""),
        )
        try:
            seq_id = save_sequence(rec, filepath=getattr(args, "file_path", None))
        except (PermissionError, OSError):
            import tempfile
            fallback = os.path.join(tempfile.gettempdir(), ".biolabcalc", "sequences.json")
            seq_id = save_sequence(rec, filepath=fallback)
        if not getattr(args, "quiet", False):
            print(f"Saved sequence '{seq_id}' ({rec.length} bp, {rec.seq_type.upper()}, MW: {rec.molecular_weight_da:,.1f} Da)")
        else:
            print(seq_id)

    elif action == "list":
        try:
            seqs = list_sequences(filepath=getattr(args, "file_path", None))
        except Exception:
            seqs = list(DEFAULT_SEQUENCE_CATALOG.values())
        if getattr(args, "json", False):
            _dump_json(seqs, getattr(args, "compact", False))
            return
        if not getattr(args, "quiet", False):
            print("=" * 70)
            print("SEQUENCE STORE & CATALOG")
            print("=" * 70)
            print(f"{'ID':20s} {'Type':8s} {'Length (bp/nt)':16s} {'GC %':8s} {'Description'}")
            print(f"{'-'*20} {'-'*8} {'-'*16} {'-'*8} {'-'*15}")
        for s in seqs:
            print(f"{s.id:20s} {s.seq_type.upper():8s} {s.length:<16d} {s.gc_percent:<8.1f} {s.description}")
        if not getattr(args, "quiet", False):
            print("=" * 70)

    elif action == "get":
        target_id = getattr(args, "id", None) or getattr(args, "name", None)
        if not target_id:
            print("Error: biolabcalc seq get requires sequence identifier via -n/--name or -i/--id.", file=sys.stderr)
            sys.exit(1)
        try:
            rec = get_sequence(target_id, filepath=getattr(args, "file_path", None))
        except Exception:
            import tempfile
            fallback = os.path.join(tempfile.gettempdir(), ".biolabcalc", "sequences.json")
            rec = get_sequence(target_id, filepath=fallback)
        if getattr(args, "json", False):
            _dump_json(rec, getattr(args, "compact", False))
            return
        if not getattr(args, "quiet", False):
            print("=" * 60)
            print(f"SEQUENCE RECORD: {rec.id}")
            print("=" * 60)
        print(f"ID:          {rec.id}")
        print(f"Name:        {rec.name}")
        print(f"Type:        {rec.seq_type.upper()}")
        print(f"Length:      {rec.length} bp/nt")
        print(f"GC Content:  {rec.gc_percent:.1f}%")
        print(f"MW:          {rec.molecular_weight_da:,.1f} Da")
        print(f"Sequence:    {rec.sequence}")
        if not getattr(args, "quiet", False):
            print("=" * 60)

    elif action == "delete":
        target_id = getattr(args, "id", None) or getattr(args, "name", None)
        if not target_id:
            print("Error: biolabcalc seq delete requires sequence identifier via -n/--name or -i/--id.", file=sys.stderr)
            sys.exit(1)
        try:
            ok = delete_sequence(target_id, filepath=getattr(args, "file_path", None))
        except Exception:
            import tempfile
            fallback = os.path.join(tempfile.gettempdir(), ".biolabcalc", "sequences.json")
            ok = delete_sequence(target_id, filepath=fallback)
        if ok:
            print(f"Deleted sequence '{target_id}' successfully.")
        else:
            print(f"Sequence '{target_id}' not found.")

    elif action == "import":
        if not args.file:
            print("Error: biolabcalc seq import requires fasta file path via -f/--file.", file=sys.stderr)
            sys.exit(1)
        imported = import_fasta(args.file, filepath=getattr(args, "file_path", None))
        print(f"Successfully imported {len(imported)} sequence(s) from '{args.file}'.")

    elif action == "export":
        out_path = getattr(args, "output", None) or "exported_sequences.fasta"
        export_fasta(filepath=getattr(args, "file_path", None), output_path=out_path)
        print(f"Successfully exported sequences to '{out_path}'.")

    else:
        print("Usage: biolabcalc seq {save,list,get,delete,import,export} [options]")


def handle_plasmid(args: argparse.Namespace) -> None:
    action = getattr(args, "plasmid_action", None)
    plasmid_arg = getattr(args, "plasmid", None)

    if action == "inspect":
        if not plasmid_arg:
            print("Error: biolabcalc plasmid inspect requires -p/--plasmid.", file=sys.stderr)
            sys.exit(1)
        rec = load_plasmid(plasmid_arg)
        if getattr(args, "json", False):
            _dump_json(rec, getattr(args, "compact", False))
            return
        if not getattr(args, "quiet", False):
            print("=" * 70)
            print(f"PLASMID CONSTRUCT INSPECTOR: {rec.name}")
            print("=" * 70)
        print(f"Name:             {rec.name}")
        print(f"Length:           {rec.length:,} bp")
        print(f"Topology:         {rec.topology.capitalize()}")
        print(f"GC Content:       {rec.gc_percent:.1f}%")
        print(f"Molecular Weight: {rec.molecular_weight_da / 1e6:.3f} MDa")
        print(f"Checksum:         {rec.checksum}")
        print(f"Features:         {len(rec.features)} annotated")
        if rec.features and not getattr(args, "quiet", False):
            print("-" * 70)
            print(f"  {'Feature Name':20s} {'Type':14s} {'Start':8s} {'End':8s} {'Strand':8s} {'Length'}")
            print(f"  {'-'*20} {'-'*14} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
            for f in rec.features:
                flen = f.get_length(rec.length)
                str_sign = "+1" if f.strand == 1 else "-1"
                print(f"  {f.name:20s} {f.feature_type:14s} {f.start:<8d} {f.end:<8d} {str_sign:8s} {flen} bp")
        if not getattr(args, "quiet", False):
            print("=" * 70)

    elif action == "annotate":
        if not plasmid_arg:
            print("Error: biolabcalc plasmid annotate requires -p/--plasmid.", file=sys.stderr)
            sys.exit(1)
        rec = load_plasmid(plasmid_arg) if isinstance(plasmid_arg, str) else plasmid_arg
        seq = getattr(rec, "sequence", str(rec))
        name = getattr(rec, "name", "Annotated_Plasmid")
        topology = getattr(rec, "topology", "circular")
        annotated = auto_annotate_plasmid(seq, name=name, topology=topology)
        if getattr(args, "json", False):
            _dump_json(annotated, getattr(args, "compact", False))
            return
        if not getattr(args, "quiet", False):
            print("=" * 70)
            print(f"AUTOMATED PLASMID ANNOTATION: {annotated.name}")
            print("=" * 70)
        print(f"Substrate:        {annotated.name} ({annotated.length:,} bp)")
        print(f"Features Found:   {len(annotated.features)}")
        for f in annotated.features:
            print(f"  * [{f.feature_type.upper()}] {f.name:18s} {f.start:6d}..{f.end:<6d} ({f.get_length(annotated.length)} bp) - {f.notes}")
        if not getattr(args, "quiet", False):
            print("=" * 70)


    elif action == "digest":
        if not plasmid_arg:
            print("Error: biolabcalc plasmid digest requires -p/--plasmid.", file=sys.stderr)
            sys.exit(1)
        rec = load_plasmid(plasmid_arg)
        enz_raw = getattr(args, "enzymes", "EcoRI")
        enz_list = [e.strip() for e in enz_raw.replace(",", " ").split() if e.strip()]
        ladder_choice = LADDER_ALIAS_MAP.get(getattr(args, "ladder", "1kb_dna"), getattr(args, "ladder", "1kb_dna"))
        pred = predict_restriction_digest(rec, enz_list, ladder_key=ladder_choice)
        if getattr(args, "json", False):
            _dump_json(pred, getattr(args, "compact", False))
            return
        if not getattr(args, "quiet", False):
            print("=" * 65)
            print(f"PLASMID DIGESTION PREDICTION: {rec.name}")
            print("=" * 65)
        print(f"Plasmid:          {rec.name} ({rec.length:,} bp)")
        print(f"Enzymes:          {', '.join(pred.enzymes)}")
        print(f"Fragment Count:   {pred.fragment_count}")
        for frag in pred.fragments:
            print(f"  Frag #{frag.fragment_id:2d}: {frag.length_bp:6d} bp | {frag.molecular_weight_da:9.1f} Da | {frag.mass_ng:5.1f} ng | Flanked: {frag.left_enzyme}/{frag.right_enzyme}")
        if not getattr(args, "quiet", False):
            print("=" * 65)

    elif action == "export":
        if not plasmid_arg:
            print("Error: biolabcalc plasmid export requires -p/--plasmid.", file=sys.stderr)
            sys.exit(1)
        rec = load_plasmid(plasmid_arg)
        out_path = getattr(args, "output", None) or f"{rec.name}.gb"
        export_genbank(rec, out_path)
        print(f"Exported plasmid '{rec.name}' to GenBank file '{out_path}'.")

    else:
        print("Usage: biolabcalc plasmid {inspect,annotate,digest,export} [options]")


def handle_clone_gene(args: argparse.Namespace) -> None:
    vec = getattr(args, "vector", "pET-28a(+)")
    insert = getattr(args, "insert", None)
    if not insert:
        print("Error: biolabcalc clone-gene requires -i/--insert sequence.", file=sys.stderr)
        sys.exit(1)
    if os.path.exists(insert):
        with open(insert, "r", encoding="utf-8") as f:
            insert = f.read()

    res = engineer_plasmid(
        vector=vec,
        insert_seq=insert,
        gene_name=getattr(args, "gene_name", "Target"),
        mode=getattr(args, "mode", "restriction_ligation"),
        enzyme_5prime=getattr(args, "enzyme5", "BamHI"),
        enzyme_3prime=getattr(args, "enzyme3", "XhoI"),
        host=getattr(args, "host", "ecoli"),
    )
    _maybe_log_report(res, args)
    if getattr(args, "json", False):
        _dump_json(res, getattr(args, "compact", False))
        return

    if not getattr(args, "quiet", False):
        print("=" * 70)
        print(f"AUTOMATED GENE EXPRESSION CLONING: {res.target_gene_name}")
        print("=" * 70)
    print(f"Vector:                {res.assembled_plasmid.name} ({res.assembled_plasmid.length:,} bp)")
    print(f"Insert Gene:           {res.target_gene_name}")
    print(f"Assembly Mode:         {res.mode}")
    print(f"Frame Synchronization: {'SYNCHRONIZED (IN-FRAME)' if res.in_frame else 'FRAME-SHIFT DETECTED'}")
    print(f"Expressed Protein:     {len(res.expressed_protein_seq)} aa (MW: {res.protein_mw_da:,.1f} Da)")
    print(f"Predicted Yield:       {res.predicted_expression_yield_mg_l:.1f} mg/L")
    if not getattr(args, "quiet", False):
        print("-" * 70)
        print("7-Point Validation Checklist:")
        print(f"  [{'PASS' if res.in_frame else 'FAIL'}] Reading Frame Continuity")
        print(f"  [{'PASS' if res.has_start_codon else 'FAIL'}] Valid Canonical Start Codon (ATG)")
        print(f"  [{'PASS' if res.has_stop_codon else 'FAIL'}] Valid Termination Stop Codon")
        print(f"  [{'PASS' if res.premature_stops == 0 else 'FAIL'}] Absence of Premature Internal Stop Codons")
        print(f"  [{'PASS' if res.rbs_or_kozak_ok else 'FAIL'}] Functional Ribosome Binding Site (RBS/Kozak)")
        print(f"  [{'PASS' if res.ori_intact else 'FAIL'}] Intact Origin of Replication")
        print(f"  [{'PASS' if res.marker_intact else 'FAIL'}] Preserved Antibiotic Selection Marker")
        if res.notes:
            print("Notes & Junctions:")
            for note in res.notes:
                print(f"  * {note}")
        print("=" * 70)

    out_gb = getattr(args, "output_gb", None)
    if out_gb:
        export_genbank(res.assembled_plasmid, out_gb)
        print(f"Saved recombinant construct to GenBank file: '{out_gb}'")


def handle_interactive_plasmid(args: argparse.Namespace) -> None:
    export_path = getattr(args, "export_html", None)
    if export_path:
        saved_path = save_plasmid_workbench_html(export_path)
        print(f"Exported interactive plasmid workbench to: '{saved_path}'")
        return

    port = getattr(args, "port", 8050)
    open_b = not getattr(args, "no_browser", False)
    print(f"Launching BioLabCalc Interactive Plasmid Workbench on port {port} ...")
    launch_plasmid_workbench(port=port, open_browser=open_b)


def handle_aptamer(args: argparse.Namespace) -> None:
    from .aptamers import evaluate_rna_hairpin_thermo, analyze_counter_selex
    if getattr(args, "seq", None):
        res = evaluate_rna_hairpin_thermo(args.seq, temperature_celsius=getattr(args, "temp", 37.0))
        if getattr(args, "json", False):
            import dataclasses
            print(json.dumps(dataclasses.asdict(res), indent=2))
            return
        print("=" * 70)
        print("  RNA/DNA APTAMER SECONDARY STRUCTURE THERMODYNAMICS (TURNER 2004)")
        print("=" * 70)
        print(f"Sequence:           {res.sequence}")
        print(f"Dot-Bracket:        {res.structure_dot_bracket}")
        print(f"Free Energy (ΔG°):  {res.delta_g_37:.2f} kcal/mol")
        print(f"Enthalpy (ΔH°):     {res.delta_h:.2f} kcal/mol")
        print(f"Entropy (ΔS°):      {res.delta_s:.2f} cal/(mol*K)")
        print(f"Melting Temp (Tm):  {res.tm_celsius:.1f} °C")
        if res.stems:
            print(f"Stems:              {res.stems}")
        if res.loops:
            print(f"Loops:              {res.loops}")
        print("=" * 70)
        return

    if getattr(args, "target_counts", None) and getattr(args, "counter_counts", None):
        def parse_counts(s: str) -> Dict[str, int]:
            d = {}
            for item in s.replace(";", ",").split(","):
                if ":" in item:
                    k, v = item.split(":", 1)
                    d[k.strip()] = int(v.strip())
                elif "=" in item:
                    k, v = item.split("=", 1)
                    d[k.strip()] = int(v.strip())
            return d

        t_counts = parse_counts(args.target_counts)
        c_counts = parse_counts(args.counter_counts)
        selex = analyze_counter_selex(
            target_counts=t_counts,
            counter_counts=c_counts,
            alpha_smoothing=getattr(args, "alpha", 1.0),
            fdr_threshold=getattr(args, "fdr", 0.05),
        )
        if getattr(args, "json", False):
            import dataclasses
            print(json.dumps(dataclasses.asdict(selex), indent=2))
            return
        print("=" * 70)
        print("  COUNTER-SELEX ENRICHMENT & SUBUNIT SELECTIVITY")
        print("=" * 70)
        print(f"Total Candidates:   {selex.total_candidates}")
        print(f"Mean Fold Enrich:   {selex.mean_enrichment:.2f}x")
        print(f"FDR Threshold:      {selex.fdr_threshold:.2f}")
        print("\nTop Candidate Rankings:")
        for cand in selex.top_candidates[:10]:
            sig_badge = "✓ SIG" if cand.is_significant else "  ns"
            print(f"  {cand.candidate_id}: {cand.sequence:<20s} Enrich={cand.fold_enrichment:6.2f}x  Adj-P={cand.p_value_adjusted:.4e}  Rank={cand.composite_rank_score:6.2f}  [{sig_badge}]")
        print("=" * 70)
        return

    print("Please specify an aptamer sequence with --seq or counts with --target-counts and --counter-counts.")


def handle_plate(args: argparse.Namespace) -> None:
    from .automation import (
        design_serial_dilution_plate,
        design_pcr_setup_plate,
        export_echo_csv,
        export_opentrons_protocol,
        export_pylabrobot_json,
    )

    plate_type = getattr(args, "type", "96-well") or "96-well"

    if getattr(args, "pcr_reactions", None):
        n_rxns = int(args.pcr_reactions)
        worklist = design_pcr_setup_plate(num_reactions=n_rxns, plate_type=plate_type)
    else:
        factor_raw = str(getattr(args, "dilution", "2.0") or "2.0")
        if ":" in factor_raw:
            factor_val = float(factor_raw.split(":")[-1])
        else:
            factor_val = float(factor_raw)

        start_conc = float(getattr(args, "start_conc", 100.0) or 100.0)
        points = int(getattr(args, "points", 8) or 8)
        replicates = int(getattr(args, "replicates", 3) or 3)
        worklist = design_serial_dilution_plate(
            start_conc=start_conc,
            dilution_factor=factor_val,
            num_points=points,
            replicates=replicates,
            plate_type=plate_type,
        )

    if getattr(args, "json", False):
        print(export_pylabrobot_json(worklist))
        return

    if getattr(args, "export_echo", None):
        export_echo_csv(worklist, args.export_echo)
        print(f"Exported Labcyte Echo pick list to: {args.export_echo}")

    if getattr(args, "export_opentrons", None):
        export_opentrons_protocol(worklist, args.export_opentrons)
        print(f"Exported Opentrons protocol script to: {args.export_opentrons}")

    if getattr(args, "export_pylabrobot", None):
        export_pylabrobot_json(worklist, args.export_pylabrobot)
        print(f"Exported PyLabRobot JSON worklist to: {args.export_pylabrobot}")

    print("=" * 70)
    print(f"  MICROPLATE AUTOMATION WORKLIST: {worklist.name}")
    print(f"  Format: {plate_type} | Total Transfers: {len(worklist.transfers)} | Volume: {worklist.total_volume_ul:.1f} µL")
    print("=" * 70)
    for note in worklist.notes:
        print(f"  • {note}")
    print(f"\n  First 5 Transfer Steps:")
    for t in worklist.transfers[:5]:
        print(f"    - {t.source_plate}:{t.source_well} -> {t.dest_plate}:{t.dest_well} ({t.volume_ul:.1f} µL) [{t.reagent_name}]")
    if len(worklist.transfers) > 5:
        print(f"    ... and {len(worklist.transfers) - 5} more transfer operations.")
    print("=" * 70)


def handle_scn(args: argparse.Namespace) -> None:
    from .eln.parsers.biorad_parser import BioRadParser

    input_path = args.input
    if not input_path:
        raise ValueError("--input argument is required for the scn subcommand.")

    with open(input_path, "rb") as f:
        raw_data = f.read()

    img = BioRadParser.parse(
        raw_data,
        auto_contrast=not getattr(args, "no_auto_contrast", False),
        invert=getattr(args, "invert", False),
        gamma=getattr(args, "gamma", 1.0),
    )

    if getattr(args, "output_png", None):
        out_png_dir = os.path.dirname(os.path.abspath(args.output_png))
        if out_png_dir and not os.path.exists(out_png_dir):
            os.makedirs(out_png_dir, exist_ok=True)
        with open(args.output_png, "wb") as f:
            f.write(img.preview_png_bytes)

    if getattr(args, "output_tiff", None):
        BioRadParser.export_tiff_16bit(img, args.output_tiff)

    lanes_data = []
    if getattr(args, "lanes", None) or getattr(args, "detect_bands", False):
        num_lanes = args.lanes or 6
        for l_idx in range(1, num_lanes + 1):
            lane_info: Dict[str, Any] = {
                "lane_index": l_idx,
                "profile": BioRadParser.extract_lane_profile(img, lane_index=l_idx, num_lanes=num_lanes),
            }
            if getattr(args, "detect_bands", False):
                lane_info["bands"] = BioRadParser.detect_lane_bands(img, lane_index=l_idx, num_lanes=num_lanes)
            lanes_data.append(lane_info)

    if getattr(args, "json", False):
        res = {
            "format": img.file_format,
            "width": img.width,
            "height": img.height,
            "bit_depth": img.bit_depth,
            "exposure_time_s": img.exposure.exposure_time_seconds,
            "instrument": img.exposure.instrument_model,
            "gain": img.exposure.gain,
            "saturated_pixels": img.saturated_pixel_count,
            "saturation_warning": img.saturation_warning,
        }
        if lanes_data:
            res["lanes"] = lanes_data
        _dump_json(res, getattr(args, "compact", False))
    else:
        print(f"Bio-Rad {img.file_format} Image: {img.width}x{img.height} (16-bit)")
        print(f"  Instrument: {img.exposure.instrument_model}")
        print(f"  Exposure Time: {img.exposure.exposure_time_seconds:.2f} s")
        print(f"  Application / Gain: {img.exposure.gain}")
        sat_warn = " ⚠️ WARNING: Signal saturated" if img.saturation_warning else ""
        print(f"  Saturated Pixels: {img.saturated_pixel_count}{sat_warn}")
        if getattr(args, "output_png", None):
            print(f"  Preview PNG exported to: {args.output_png}")
        if getattr(args, "output_tiff", None):
            print(f"  16-bit TIFF exported to: {args.output_tiff}")
        if lanes_data and getattr(args, "detect_bands", False):
            for l in lanes_data:
                print(f"  Lane {l['lane_index']}: {len(l['bands'])} bands detected")


COMMAND_DISPATCH: Dict[str, Callable[[argparse.Namespace], None]] = {
    "dilute": handle_dilute,
    "wizard": handle_wizard,
    "interactive": handle_wizard,
    "mw": handle_mw,
    "ivt": handle_ivt,
    "pcr": handle_pcr,
    "pcr-opt": handle_pcr_opt,
    "protein": handle_protein,
    "primers": handle_primers,
    "nanodrop": handle_nanodrop,
    "fluo": handle_fluo,
    "gel": handle_gel,
    "ecoli": handle_ecoli,
    "excel-template": handle_excel_template,
    "annotate-gel": handle_annotate_gel,
    "interactive-gel": handle_interactive_gel,
    "batch-excel": handle_batch_excel,
    "digest": handle_digest,
    "ligate": handle_ligate,
    "gibson": handle_gibson,
    "buffer": handle_buffer,
    "precipitate": handle_precipitate,
    "ntp-ph": handle_ntp_ph,
    "golden-gate": handle_golden_gate,
    "purity": handle_purity,
    "pci": handle_pci,
    "ivt-time": handle_ivt_time,
    "hepes": handle_hepes,
    "western": handle_western,
    "report": handle_report,
    "eln": handle_eln,
    "convert": handle_convert,
    "batch-csv": handle_batch_csv,
    "rc": handle_rc,
    "translate": handle_translate,
    "diagnostics": handle_diagnostics,
    "setup": handle_setup,
    "portable": handle_portable,
    "seq": handle_seq,
    "plasmid": handle_plasmid,
    "clone-gene": handle_clone_gene,
    "interactive-plasmid": handle_interactive_plasmid,
    "aptamer": handle_aptamer,
    "plate": handle_plate,
    "scn": handle_scn,
    "print-protocol": handle_print_protocol,
}



def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS, help="Suppress header banners and decorative bars")
    common.add_argument("--log-report", default=None, metavar="FILE", help="Append calculation results to a persistent LabReport file (.md, .json, .csv, .xlsx)")
    common.add_argument("--sample", default=None, metavar="ID", help="Sample identifier for --log-report (defaults to 'Sample-1')")

    parser = argparse.ArgumentParser(
        prog="biolabcalc",
        description="BioLabCalc: Multifaceted molecular biology stoichiometry, PCR, IVT, protein yield, fluorophore mods, gel ladders, and E. coli growth.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"biolabcalc {__version__}")
    parser.add_argument("-q", "--quiet", action="store_true", default=False, help="Suppress header banners and decorative bars")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 0. dilute
    p_dil = subparsers.add_parser("dilute", parents=[common], help="Solve C1*V1 = C2*V2 dilution calculation (e.g. -c1 '100 mM' -c2 '25 mM' -v2 '16 mL')")
    p_dil.add_argument("-c1", "--conc1", dest="c1", default=None, help="Stock concentration (e.g. '100 mM')")
    p_dil.add_argument("-v1", "--vol1", dest="v1", default=None, help="Stock volume (e.g. '4.0 mL')")
    p_dil.add_argument("-c2", "--conc2", dest="c2", default=None, help="Target working concentration (e.g. '25 mM')")
    p_dil.add_argument("-v2", "--vol2", dest="v2", default=None, help="Target final volume (e.g. '16 mL')")
    p_dil.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_dil.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 0b. wizard
    p_wiz = subparsers.add_parser("wizard", parents=[common], aliases=["interactive"], help="Interactive guided step-by-step wizard for bench calculations")

    # 1. mw
    p_mw = subparsers.add_parser("mw", parents=[common], help="Calculate molecular weight of DNA, RNA, or Protein")
    p_mw.add_argument("-s", "--sequence", default=None, help="Sequence string (or '-' for stdin)")
    p_mw.add_argument("-f", "--file", default=None, help="Path to sequence file (FASTA or plain text)")
    p_mw.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_mw.add_argument("--compact", action="store_true", help="Compact JSON without indentation")
    p_mw.add_argument("-t", "--type", choices=["dna", "rna", "protein"], default="dna", help="Sequence type")
    p_mw.add_argument("--ds", action="store_true", help="Double-stranded (for DNA)")
    p_mw.add_argument("--circular", action="store_true", help="Calculate MW for circular dsDNA/plasmids")
    p_mw.add_argument("--end-5", "--end5", dest="end_5", choices=["hydroxyl", "monophosphate", "triphosphate"], default="hydroxyl", help="5' phosphorylation state")

    p_mw.add_argument("--end-3", "--end3", dest="end_3", choices=["hydroxyl", "monophosphate", "diphosphate", "triphosphate", "cyclic_phosphate"], default="hydroxyl", help="3' terminal phosphorylation state")
    p_mw.add_argument("--backbone", choices=["monophosphate", "phosphorothioate"], default="monophosphate", help="Internucleotide backbone chemistry")

    # 2. ivt
    p_ivt = subparsers.add_parser("ivt", parents=[common], help="Calculate in vitro transcription yield and NTP stoichiometry")
    p_ivt.add_argument("-s", "--sequence", default=None, help="RNA or DNA template sequence (or '-' for stdin)")
    p_ivt.add_argument("-f", "--file", default=None, help="Path to sequence file (FASTA or plain text)")
    p_ivt.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_ivt.add_argument("--compact", action="store_true", help="Compact JSON without indentation")
    p_ivt.add_argument("-v", "--volume", default="20.0 uL", help="Reaction volume in µL (e.g. 20 or 20 uL)")
    p_ivt.add_argument("-y", "--yield-ug", default="40.0 ug", help="Measured RNA yield (e.g. 40 or 40 ug)")
    p_ivt.add_argument("--ntp-mm", type=float, default=5.0, help="Starting NTP concentration in mM")
    p_ivt.add_argument("--no-trim-promoter", action="store_true", help="Disable automatic detection and trimming of upstream promoters")
    p_ivt.add_argument("--add-gg", type=int, default=0, choices=[0, 1, 2, 3], help="Ensure at least N leading 5' Guanines (e.g. 2 for 5'-GG)")
    p_ivt.add_argument("--cap", choices=["CleanCap_AG", "CleanCap_GG", "ARCA", "m7G"], default=None, help="Co-transcriptional cap analog")
    p_ivt.add_argument("--mod-ntp", choices=["m1Psi", "Psi", "5moU", "m5C"], default=None, help="Modified nucleotide replacement (e.g. m1Psi)")
    p_ivt.add_argument("--end-3", choices=["hydroxyl", "monophosphate", "triphosphate"], default="hydroxyl", help="3' terminal phosphorylation state")
    p_ivt.add_argument("--buffer", choices=["hepes", "tris"], default="hepes", help="Reaction buffer system (default: hepes)")
    p_ivt.add_argument("--temp", type=float, default=37.0, help="Reaction incubation temperature in °C (default: 37.0)")

    # 3. pcr
    p_pcr = subparsers.add_parser("pcr", parents=[common], help="Calculate PCR kinetics and dNTP usage")
    p_pcr.add_argument("-l", "--length", type=int, default=None, help="Amplicon length in bp")
    p_pcr.add_argument("-s", "--sequence", default=None, help="Amplicon or template sequence string")
    p_pcr.add_argument("-v", "--volume", default="50.0 uL", help="Reaction volume in µL (default: 50 uL)")
    p_pcr.add_argument("-t", "--template-ng", required=True, help="Template input in ng (e.g. '10 ng', '0.5 ug', 10)")
    p_pcr.add_argument("-c", "--cycles", type=int, default=30, help="PCR cycles")
    p_pcr.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_pcr.add_argument("--compact", action="store_true", help="Compact JSON without indentation")


    # 4. pcr-opt
    p_pcr_opt = subparsers.add_parser("pcr-opt", parents=[common], help="Optimize PCR annealing temp, extension time, and cycling")
    p_pcr_opt.add_argument("--fwd-tm", "--tm-fwd", dest="fwd_tm", type=float, required=True, help="Forward primer Tm in °C")
    p_pcr_opt.add_argument("--rev-tm", "--tm-rev", dest="rev_tm", type=float, required=True, help="Reverse primer Tm in °C")
    p_pcr_opt.add_argument("-l", "--length", type=int, required=True, help="Amplicon length in bp")
    p_pcr_opt.add_argument("-p", "--polymerase", "--poly", dest="polymerase", default="taq", choices=["taq", "q5", "phusion", "kapa"], help="Polymerase type")
    p_pcr_opt.add_argument("--gc", type=float, default=50.0, help="Amplicon GC percentage")
    p_pcr_opt.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_pcr_opt.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 5. protein
    p_prot = subparsers.add_parser("protein", parents=[common], help="Quantify protein A280 concentration and yield")
    p_prot.add_argument("-s", "--sequence", default=None, help="Amino acid sequence (or '-' for stdin)")
    p_prot.add_argument("-f", "--file", default=None, help="Path to protein sequence file (FASTA or plain text)")
    p_prot.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_prot.add_argument("--compact", action="store_true", help="Compact JSON without indentation")
    p_prot.add_argument("-a", "--a280", type=float, required=True, help="Absorbance at 280 nm")
    p_prot.add_argument("-v", "--volume-ml", type=float, default=1.0, help="Purified volume in mL")

    # 6. primers
    p_prim = subparsers.add_parser("primers", parents=[common], help="Design forward and reverse primers")
    p_prim.add_argument("-s", "--sequence", required=True, help="Template DNA sequence")
    p_prim.add_argument("--target-tm", type=float, default=60.0, help="Target Tm in °C")

    # 7. nanodrop
    p_nano = subparsers.add_parser("nanodrop", parents=[common], help="Prepare standardized solutions (e.g. 4uM ssRNA at 500uL) and predict NanoDrop readings")
    p_nano.add_argument("-u", "-m", "--molarity-um", dest="molarity_um", type=float, required=True, help="Target molarity in µM (e.g. 4.0)")
    p_nano.add_argument("-v", "--volume-ul", type=float, required=True, help="Target volume in µL (e.g. 500.0)")
    p_nano.add_argument("-t", "--type", default="rna", choices=["rna", "dna", "ssdna", "dsdna", "protein"], help="Biomolecule type")
    p_nano.add_argument("-s", "--sequence", default=None, help="Sequence (optional)")
    p_nano.add_argument("-l", "--length", dest="length", type=int, default=100, help="Length in nt/bp (used if sequence omitted)")
    p_nano.add_argument("--stock-ng-ul", "--stock", dest="stock_ng_ul", type=float, default=None, help="Stock concentration in ng/µL (for dilution)")
    p_nano.add_argument("--end-5", "--end5", dest="end_5", choices=["hydroxyl", "monophosphate", "triphosphate"], default="hydroxyl", help="5' end state")

    # 8. fluo
    p_fluo = subparsers.add_parser("fluo", parents=[common], help="Calculate fluorophore modifications, dye properties, and Degree of Labeling (DOL)")
    p_fluo.add_argument("-s", "--sequence", default=None, help="Sequence for modification calculation")
    p_fluo.add_argument("-t", "--type", default="dna", choices=["dna", "rna", "protein"], help="Molecule type (default: dna)")
    p_fluo.add_argument("-d", "--dye", default=None, help="Dye name (e.g. FAM, Cy3, Cy5, Alexa488)")
    p_fluo.add_argument("--info", nargs="?", const="", default=None, help="Print spectral and physical information for a dye (e.g. --info FAM or with -d FAM)")
    p_fluo.add_argument("--dol", action="store_true", help="Calculate degree of labeling (DOL)")
    p_fluo.add_argument("--a-dye", type=float, default=None, help="Absorbance at dye absorbance maximum (for --dol)")
    p_fluo.add_argument("--a280", type=float, default=None, help="Absorbance at 280 nm for protein conjugate (for --dol)")
    p_fluo.add_argument("--a260", type=float, default=None, help="Absorbance at 260 nm for oligonucleotide conjugate (for --dol)")
    p_fluo.add_argument("--prot-e280", type=float, default=None, help="Protein molar extinction coefficient at 280 nm in M^-1 cm^-1 (for --dol)")
    p_fluo.add_argument("--dna-e260", type=float, default=None, help="Oligonucleotide molar extinction coefficient at 260 nm in M^-1 cm^-1 (for --dol)")
    p_fluo.add_argument("--pathlength", type=float, default=1.0, help="Pathlength in cm (default: 1.0)")

    # 9. gel
    p_gel = subparsers.add_parser("gel", parents=[common], help="Simulate gel electrophoresis migration against MW ladders")
    p_gel.add_argument("-s", "--sizes", nargs="+", type=float, required=True, help="Sample band sizes (bp or kDa)")
    p_gel.add_argument("-l", "--ladder", default="1kb_dna", choices=LADDER_CHOICES, help="MW ladder type")

    # 10. ecoli
    p_ecoli = subparsers.add_parser("ecoli", parents=[common], help="E. coli growth time to induction OD, plasmid yields, and protein expression")
    p_ecoli.add_argument("--init-od", type=float, default=0.05, help="Initial OD600")
    p_ecoli.add_argument("--target-od", type=float, default=0.60, help="Target induction OD600")
    p_ecoli.add_argument("--temp", type=float, default=37.0, help="Culture temperature in °C")
    p_ecoli.add_argument("--media", default="LB", choices=["LB", "2xYT", "TB", "M9"], help="Media type")
    p_ecoli.add_argument("--plasmid", default="pUC", help="Plasmid origin/copy (pUC, pET, pBR322)")
    p_ecoli.add_argument("--vol-ml", type=float, default=1000.0, help="Culture volume in mL")

    # 11. excel-template
    p_xl = subparsers.add_parser("excel-template", parents=[common], help="Generate an interactive multi-tab Excel lab notebook")
    p_xl.add_argument("-o", "--output", default="biolabcalc_notebook.xlsx", help="Output .xlsx path")

    # 12. annotate-gel
    p_ann = subparsers.add_parser("annotate-gel", parents=[common], help="Annotate gel images, label lanes, add MW ladders, and callout target bands")
    p_ann.add_argument("-i", "--image", default=None, help="Input gel image path (PNG, JPG, TIFF). If omitted, renders a synthetic gel.")
    p_ann.add_argument("-l", "--lanes", default="Ladder,Ctrl,Sample1,Sample2", help="Comma-separated lane names")
    p_ann.add_argument("--ladder", default="1kb_dna", choices=LADDER_CHOICES, help="Ladder type")
    p_ann.add_argument("--ladder-lane", type=int, default=1, help="Ladder lane number (1-based, default 1)")
    p_ann.add_argument("--ladder-side", default="left", choices=["left", "right"], help="Side for MW tick labels")
    p_ann.add_argument("-b", "--bands", default=None, help="Bands to annotate in format 'lane:size:label' separated by commas (e.g. '3:850:Amplicon,4:850:Amplicon')")
    p_ann.add_argument("-t", "--title", default="Agarose Gel Electrophoresis Analysis", help="Figure title")
    p_ann.add_argument("--info", default="1.0% Agarose in 1X TAE | 100V, 45 min", help="Gel conditions subtitle")
    p_ann.add_argument("-o", "--output", default="annotated_gel.png", help="Output annotated image path (.png)")
    p_ann.add_argument("--excel", default=None, help="Optional Excel file to embed annotated image and lane table")
    p_ann.add_argument("--invert", action="store_true", help="Invert colors (dark bands on light background)")
    p_ann.add_argument("--font-family", default="Arial, Helvetica, sans-serif", help="Font family for figure labels")
    p_ann.add_argument("--font-scale", type=float, default=1.0, help="Font scaling factor (default: 1.0)")
    p_ann.add_argument("--show-lane-numbers", action="store_true", default=True, help="Display lane number indicators (default: True)")
    p_ann.add_argument("--hide-lane-numbers", action="store_false", dest="show_lane_numbers", help="Hide lane number indicators")
    p_ann.add_argument("--lane-number-style", default="circle", choices=["circle", "square", "plain"], help="Style of lane number badge")
    p_ann.add_argument("--lane-number-format", default="numeric", choices=["numeric", "prefixed_L", "prefixed_lane", "alpha", "roman"], help="Numbering format scheme")
    p_ann.add_argument("--include-table", action="store_true", help="Render formatted lane sample designation table below the gel figure")

    # 13. interactive-gel
    p_int = subparsers.add_parser("interactive-gel", parents=[common], help="Launch the interactive drag-and-drop gel annotator and molecular weight calculator in browser")
    p_int.add_argument("-p", "--port", type=int, default=8501, help="Local port (default: 8501)")
    p_int.add_argument("--save-html", default=None, help="Save standalone HTML5 application file without running server")
    p_int.add_argument("--no-browser", action="store_true", help="Do not open web browser automatically")

    # 13b. print-protocol
    p_proto = subparsers.add_parser("print-protocol", parents=[common], help="Generate printable benchtop protocol with master mix overage, pipette tool recommendations, and plate map")
    p_proto.add_argument("-t", "--title", default="Q5 High-Fidelity PCR Amplification", help="Protocol or experiment title")
    p_proto.add_argument("-n", "--reactions", type=int, default=24, help="Total number of experimental reactions")
    p_proto.add_argument("--overage", type=float, default=10.0, help="Master mix overage percentage (default: 10.0)")
    p_proto.add_argument("--template", default="pcr", choices=["pcr", "qpcr", "digest", "custom"], help="Reaction template preset")
    p_proto.add_argument("--plate-type", default="96-well", choices=["96-well", "384-well", "24-tube", "8-strip"], help="Benchware plate/rack layout")
    p_proto.add_argument("-s", "--samples", default=None, help="Comma-separated sample names to map onto plate")
    p_proto.add_argument("--trim-size", default="8x10", choices=["8x10", "7.5x9.5", "full-page"], help="Laboratory notebook page trim guide")
    p_proto.add_argument("-o", "--output", default="bench_protocol.html", help="Output HTML document path")
    p_proto.add_argument("--operator", default="", help="Operator name for GLP compliance sign-off")
    p_proto.add_argument("--project", default="", help="Project or grant ID")
    p_proto.add_argument("--protocol-id", default="SOP-BIO-01", help="Internal SOP/protocol ID")
    p_proto.add_argument("--open-browser", action="store_true", help="Automatically open generated protocol in web browser")

    # 14. batch-excel
    p_batch = subparsers.add_parser("batch-excel", parents=[common], help="Batch process sequence tables from an Excel spreadsheet")
    p_batch.add_argument("-i", "--input", required=True, help="Input Excel file (.xlsx) with sequences")
    p_batch.add_argument("-o", "--output", default="batch_results.xlsx", help="Output annotated Excel file (.xlsx)")

    # 15. digest
    p_dig = subparsers.add_parser("digest", parents=[common], help="Plan restriction enzyme digestion with buffer compatibility and pipetting volumes")
    p_dig.add_argument("-m", "--dna-ug", type=float, default=None, help="DNA mass in µg")
    p_dig.add_argument("-c", "--dna-conc", type=float, default=None, help="DNA stock concentration in ng/µL")
    p_dig.add_argument("-v", "--volume", type=float, default=50.0, help="Total reaction volume in µL (default: 50)")
    p_dig.add_argument("-e1", "--enzyme-1", default="EcoRI", help="First restriction enzyme (e.g. EcoRI, BamHI, HindIII)")
    p_dig.add_argument("-e2", "--enzyme-2", default=None, help="Second restriction enzyme for double digest (optional)")
    p_dig.add_argument("-s", "--sequence", default=None, help="DNA nucleotide sequence for in-silico restriction digest")
    p_dig.add_argument("-p", "--plasmid", default=None, help="Plasmid name or record for in-silico restriction digest")
    p_dig.add_argument("--simulate-gel", action="store_true", help="Simulate and display virtual gel migration")


    # 16. ligate
    p_lig = subparsers.add_parser("ligate", parents=[common], help="Calculate DNA ligation insert mass and reaction setup")
    p_lig.add_argument("--vec-bp", type=int, required=True, help="Vector length in bp")
    p_lig.add_argument("--ins-bp", type=int, required=True, help="Insert length in bp")
    p_lig.add_argument("--vec-ng", type=float, default=50.0, help="Vector mass in ng (default: 50)")
    p_lig.add_argument("-r", "--ratio", type=float, default=3.0, help="Molar ratio insert:vector (default: 3.0)")
    p_lig.add_argument("-v", "--volume", type=float, default=20.0, help="Reaction volume in µL")

    # 17. gibson
    p_gib = subparsers.add_parser("gibson", parents=[common], help="Calculate Gibson Assembly / NEBuilder HiFi reaction setup")
    p_gib.add_argument("--vec-bp", type=int, required=True, help="Vector length in bp")
    p_gib.add_argument("--ins-bp", nargs="+", type=int, required=True, help="Insert lengths in bp (e.g. 800 1200)")
    p_gib.add_argument("--vec-ng", type=float, default=100.0, help="Vector mass in ng (default: 100)")
    p_gib.add_argument("-r", "--ratio", type=float, default=2.0, help="Molar ratio insert:vector (default: 2.0)")

    # 18. buffer
    p_buf = subparsers.add_parser("buffer", parents=[common], help="Calculate chemical masses and recipe for laboratory buffers")
    p_buf.add_argument("-b", "--buffer", default=None, help="Buffer name (e.g. 50X_TAE, 10X_PBS, 10X_HEPES_IVT, or custom buffer)")
    p_buf.add_argument("-v", "--volume-ml", type=float, default=1000.0, help="Target volume in mL (default: 1000)")
    p_buf.add_argument("--custom", action="store_true", help="Launch interactive custom buffer builder")
    p_buf.add_argument("--list", action="store_true", help="List all standard and custom buffers in the catalog")
    p_buf.add_argument("--list-custom", action="store_true", help="List custom buffers saved on disk")
    p_buf.add_argument("--equil", default=None, help="Solve competitive buffer speciation (e.g. 'Tris=50mM,EGTA=5mM,MgCl2=10mM,ATP=4mM')")
    p_buf.add_argument("--ph", type=float, default=7.4, help="Target pH for equilibrium speciation (default: 7.4)")
    p_buf.add_argument("--temp", type=float, default=25.0, help="Formulation temperature in Celsius (default: 25.0)")
    p_buf.add_argument("--output-temp", type=float, default=37.0, help="Output temperature in Celsius (default: 37.0)")
    p_buf.add_argument("--json", action="store_true", help="Output results in JSON format")

    # 19. precipitate
    p_prec = subparsers.add_parser("precipitate", parents=[common], help="Calculate ethanol/isopropanol nucleic acid precipitation recipe")
    p_prec.add_argument("-v", "--volume-ul", type=float, required=True, help="Sample volume in µL")
    p_prec.add_argument("-t", "--type", default="dna", choices=["dna", "rna"], help="Nucleic acid type")
    p_prec.add_argument("-a", "--alcohol", default="ethanol", choices=["ethanol", "isopropanol"], help="Alcohol type")
    p_prec.add_argument("-s", "--salt", default="naoac", choices=["naoac", "nh4oac", "licl", "nacl"], help="Salt type (naoac, nh4oac, licl, nacl)")
    p_prec.add_argument("--carrier", dest="carrier", action="store_true", default=True, help="Include glycogen carrier (default: True)")
    p_prec.add_argument("--no-carrier", dest="carrier", action="store_false", help="Do not include glycogen carrier")

    # 20. ntp-ph
    p_ntp = subparsers.add_parser("ntp-ph", parents=[common], help="Calculate NaOH requirement and protocol for NTP pH adjustment")
    p_ntp.add_argument("-v", "-v1", "--initial-vol", dest="initial_vol", type=float, default=4.0, help="Initial stock volume in mL (default: 4.0)")
    p_ntp.add_argument("-c", "-c1", "--initial-conc", dest="initial_conc", type=float, default=100.0, help="Initial stock concentration in mM (default: 100.0)")
    p_ntp.add_argument("-V", "-v2", "--target-vol", dest="target_vol", type=float, default=16.0, help="Target final volume in mL (default: 16.0)")
    p_ntp.add_argument("-C", "-c2", "--target-conc", dest="target_conc", type=float, default=25.0, help="Target final concentration in mM (default: 25.0)")
    p_ntp.add_argument("-p", "--target-ph", "--ph", dest="target_ph", type=float, default=7.5, help="Target pH (default: 7.5)")
    p_ntp.add_argument("-f", "--form", "--starting-form", dest="form", default="disodium_salt", choices=["disodium_salt", "pre_neutralized", "free_acid"], help="Starting stock chemical form")
    p_ntp.add_argument("-s", "--species", default="equimolar_mix", choices=["equimolar_mix", "ATP", "CTP", "GTP", "UTP"], help="NTP species")
    p_ntp.add_argument("-b", "--base-molarity", type=float, default=5.0, help="Molarity of NaOH stock in M (default: 5.0)")

    # 24. golden-gate
    p_gg = subparsers.add_parser("golden-gate", parents=[common], help="Calculate Golden Gate Assembly stoichiometry, pipetting, and cycling")
    p_gg.add_argument("--vec-bp", type=int, required=True, help="Destination vector length in bp")
    p_gg.add_argument("--ins-bp", type=int, nargs="+", required=True, help="Insert lengths in bp (e.g. 1000 500)")
    p_gg.add_argument("--fmol", type=float, default=20.0, help="Target vector fmol (default: 20.0)")
    p_gg.add_argument("--enzyme", default="BsaI-HFv2", help="Type IIS enzyme (e.g. BsaI-HFv2, BsmBI-v2, BbsI-HF)")
    p_gg.add_argument("--ratio", type=float, default=2.0, help="Insert:vector molar ratio (default: 2.0)")

    # 25. purity
    p_pur = subparsers.add_parser("purity", parents=[common], help="Assess nucleic acid NanoDrop A260/A280/A230 purity and contaminants")
    p_pur.add_argument("--a260", type=float, required=True, help="Absorbance at 260 nm")
    p_pur.add_argument("--a280", type=float, required=True, help="Absorbance at 280 nm")
    p_pur.add_argument("--a230", type=float, required=True, help="Absorbance at 230 nm")
    p_pur.add_argument("-t", "--type", choices=["rna", "dna"], default="rna", help="Nucleic acid type")

    # 26. pci
    p_pci = subparsers.add_parser("pci", parents=[common], help="Calculate Phenol:Chloroform:Isoamyl alcohol extraction volumes and protocol")
    p_pci.add_argument("-v", "--volume", type=float, required=True, help="Aqueous sample volume in µL")
    p_pci.add_argument("-t", "--type", choices=["rna", "dna"], default="rna", help="Target nucleic acid")
    p_pci.add_argument("--ph", type=float, default=None, help="Phenol pH (default: 4.5 for RNA, 8.0 for DNA)")
    p_pci.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_pci.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 27. ivt-time
    p_ivtt = subparsers.add_parser("ivt-time", parents=[common], help="Calculate optimal IVT incubation time and kinetic profile")
    p_ivtt.add_argument("-l", "--length", type=int, required=True, help="Transcript length in nucleotides")
    p_ivtt.add_argument("--temp", type=float, default=37.0, help="Incubation temperature in °C (default: 37.0)")
    p_ivtt.add_argument("--no-ipp", action="store_true", help="Omit inorganic pyrophosphatase (IPP)")
    p_ivtt.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_ivtt.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 28. hepes
    p_hep = subparsers.add_parser("hepes", parents=[common], help="Calculate 10X/5X HEPES-KOH IVT buffer recipe with temperature compensation")
    p_hep.add_argument("-v", "--volume", default="50 mL", help="Buffer stock volume (default: 50 mL)")
    p_hep.add_argument("--stock", type=int, default=10, help="Stock multiplier (e.g. 10 for 10X, default: 10)")
    p_hep.add_argument("--ph", type=float, default=7.50, help="Target reaction pH at 37°C (default: 7.50)")
    p_hep.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_hep.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 29. western
    p_wb = subparsers.add_parser("western", parents=[common], help="Plan Western blot experiment: SDS-PAGE, transfer, loading, and antibodies")
    p_wb.add_argument("-n", "--name", "-target", "--target", dest="name", default="Target Protein", help="Target protein name (e.g. GluK2, Actin, p-ERK)")
    p_wb.add_argument("-m", "--mw", type=float, default=None, help="Target molecular weight in kDa (e.g. 100.0)")
    p_wb.add_argument("-c", "--conc", type=float, default=2.5, help="Lysate total protein concentration in mg/mL (default: 2.5)")
    p_wb.add_argument("-l", "--load-ug", "--ug", dest="load_ug", type=float, default=20.0, help="Target protein mass per lane in µg (default: 20.0)")
    p_wb.add_argument("--phospho", action="store_true", help="Target is phosphorylated epitope (enforces 5%% BSA blocking; bans milk)")
    p_wb.add_argument("--membrane-protein", "--membrane_protein", dest="membrane_protein", action="store_true", help="Target is transmembrane receptor (enforces 70°C denaturation; bans 95°C boiling)")
    p_wb.add_argument("--transfer", choices=["wet_tank", "semi_dry", "fast_semi_dry"], default="wet_tank", help="Electrotransfer system (default: wet_tank)")
    p_wb.add_argument("--membrane", nargs="?", const="pvdf_flag", default="pvdf", help="Membrane type ('pvdf', 'nitrocellulose') or flag for membrane protein")
    p_wb.add_argument("--troubleshoot", default=None, help="Diagnose artifact: 'no_signal', 'high_background', 'ghost_bands', 'membrane_protein_aggregates', 'patchy_transfer'")

    # 30. report
    p_rep = subparsers.add_parser("report", parents=[common], help="Record experimental measurements and export formatted lab reports")
    p_rep.add_argument("-t", "--title", default="Laboratory Experiment Report", help="Report or experiment title")
    p_rep.add_argument("-r", "--researcher", default="Researcher", help="Researcher name")
    p_rep.add_argument("-p", "--project", default="General", help="Project or notebook ID")
    p_rep.add_argument("--obj", "--objective", dest="obj", default="", help="Experimental objective")
    p_rep.add_argument("-s", dest="sample", default=None, help="Sample ID (e.g. WT-1, Sample-A)")
    p_rep.add_argument("--param", default=None, help="Parameter or assay (e.g. Yield, A260, Conc)")
    p_rep.add_argument("-v", "--value", "--val", dest="value", type=float, default=None, help="Measured numeric value")
    p_rep.add_argument("-u", "--unit", default="", help="Measurement unit (e.g. ug, ng/uL, AU, bp)")
    p_rep.add_argument("--target", type=float, default=None, help="Target or expected value")
    p_rep.add_argument("--tolerance", "--tol", dest="tolerance", type=float, default=None, help="Acceptable QC deviation tolerance %%")
    p_rep.add_argument("--notes", default="", help="Bench observations or notes")
    p_rep.add_argument("--conclusion", default=None, help="Add conclusion or key takeaway")
    p_rep.add_argument("-o", "--output", default=None, help="Export report to file (.md, .xlsx, .csv, .json)")
    p_rep.add_argument("--interactive", action="store_true", help="Launch interactive terminal prompt to record measurements")

    # 31. eln
    p_eln = subparsers.add_parser("eln", parents=[common], help="Launch State-of-the-Art Electronic Lab Notebook (ELN) and Multi-Modal LIMS")
    p_eln.add_argument("-p", "--port", type=int, default=None, help="Web server port (default: 8080 or designated in config.yaml)")
    p_eln.add_argument("--host", default=None, help="Host address (default: 127.0.0.1 or designated in config.yaml)")
    p_eln.add_argument("--db-url", default=None, help="Database connection URL (defaults to SQLite local CAS)")
    p_eln.add_argument("--no-browser", action="store_true", default=None, help="Do not open web browser automatically")
    p_eln.add_argument("-c", "--config", default=None, help="Path to designated config.yaml configuration file")
    p_eln.add_argument("--anonymize", action="store_true", default=None, help="Enable log and metadata anonymization")
    p_eln.add_argument("--generate-config", action="store_true", help="Generate default config.yaml template in current directory and exit")

    # 26. convert (Universal unit & stoichiometry converter)
    p_conv = subparsers.add_parser("convert", parents=[common], help="Convert laboratory units and stoichiometry (mass, moles, concentration, volume)")
    p_conv.add_argument("-v", "--val", "--value", dest="val", required=True, help="Input value with unit (e.g. '500 ng', '10 uM', '2.5 mL')")
    p_conv.add_argument("-t", "--to", dest="to_unit", required=True, help="Target unit (e.g. 'pmol', 'ng/ul', 'ul', 'g')")
    p_conv.add_argument("--mw", type=float, default=None, help="Molecular weight in g/mol (Da) for mass <-> mole conversions")
    p_conv.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_conv.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 27. batch-csv (Zero-dependency CSV/TSV batch calculation)
    p_bcsv = subparsers.add_parser("batch-csv", parents=[common], help="High-throughput batch sequence analysis from CSV or TSV")
    p_bcsv.add_argument("-i", "--input", required=True, help="Path to input CSV or TSV file")
    p_bcsv.add_argument("-o", "--output", required=True, help="Path to output annotated CSV or TSV file")
    p_bcsv.add_argument("-d", "--delimiter", default=None, help="Explicit delimiter (e.g. ',' or '\\t')")
    p_bcsv.add_argument("--json", action="store_true", help="Output machine-readable JSON summary")
    p_bcsv.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 28. rc (Reverse complement)
    p_rc = subparsers.add_parser("rc", parents=[common], help="Calculate 5' -> 3' reverse complement of DNA or RNA")
    p_rc.add_argument("-s", "--sequence", default=None, help="Sequence string (or '-' for stdin)")
    p_rc.add_argument("-f", "--file", default=None, help="Path to sequence file (FASTA or plain text)")
    p_rc.add_argument("-t", "--type", choices=["dna", "rna"], default="dna", help="Sequence type (dna or rna)")
    p_rc.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_rc.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 29. translate (Translation)
    p_tr = subparsers.add_parser("translate", parents=[common], help="Translate DNA/RNA nucleotide sequence to amino acids")
    p_tr.add_argument("-s", "--sequence", default=None, help="Sequence string (or '-' for stdin)")
    p_tr.add_argument("-f", "--file", default=None, help="Path to sequence file (FASTA or plain text)")
    p_tr.add_argument("-m", "--frame", type=int, choices=[1, 2, 3, -1, -2, -3], default=1, help="Reading frame (+1, +2, +3, -1, -2, -3)")
    p_tr.add_argument("--all-frames", action="store_true", help="Translate across all 6 reading frames")
    p_tr.add_argument("--to-stop", action="store_true", help="Terminate translation upon first stop codon (*)")
    p_tr.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_tr.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 30. diagnostics (Failure Logging & System Health)
    p_diag = subparsers.add_parser("diagnostics", parents=[common], help="View plain-English diagnostic reports and remediation for recent system failures")
    p_diag.add_argument("--tail", type=int, default=10, help="Number of recent failure entries to display (default: 10)")
    p_diag.add_argument("--clear", action="store_true", help="Clear recorded diagnostic failure logs")
    p_diag.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    p_diag.add_argument("--compact", action="store_true", help="Compact JSON without indentation")

    # 31. setup (Interactive Shared Drive Setup Wizard)
    p_setup = subparsers.add_parser("setup", parents=[common], help="Configure laboratory shared network drive and deployment profile")
    p_setup.add_argument("--shared-dir", default=None, help="Path to shared network folder (UNC or mapped drive)")
    p_setup.add_argument("--role", default=None, help="Default researcher role")
    p_setup.add_argument("--host", default="127.0.0.1", help="Listening server host (default: 127.0.0.1)")
    p_setup.add_argument("-p", "--port", type=int, default=8080, help="Web server port (default: 8080)")
    p_setup.add_argument("--non-interactive", action="store_true", help="Execute setup non-interactively")

    # 32. portable (Portable Environment Status)
    p_port = subparsers.add_parser("portable", parents=[common], help="Inspect portable runtime status, shared drive mounts, and storage paths")

    # 33. seq (Sequence Store Management & FASTA I/O)
    p_seq = subparsers.add_parser("seq", parents=[common], help="Sequence store management, catalog, and FASTA I/O")
    seq_sub = p_seq.add_subparsers(dest="seq_action", help="Sequence operation")

    p_s_save = seq_sub.add_parser("save", parents=[common], help="Save a sequence to store")
    p_s_save.add_argument("-n", "--name", default=None, help="Sequence name / identifier")
    p_s_save.add_argument("-s", "--sequence", default=None, help="Sequence string (or '-' for stdin)")
    p_s_save.add_argument("-f", "--file", default=None, help="Sequence file")
    p_s_save.add_argument("-t", "--type", default="dna", choices=["dna", "rna", "protein"], help="Sequence modality")
    p_s_save.add_argument("-d", "--desc", default="", help="Description")
    p_s_save.add_argument("--file-path", default=None, help="Custom JSON store file path")

    p_s_list = seq_sub.add_parser("list", parents=[common], help="List all saved and catalog sequences")
    p_s_list.add_argument("--file-path", default=None, help="Custom JSON store file path")
    p_s_list.add_argument("--json", action="store_true", help="Output JSON")
    p_s_list.add_argument("--compact", action="store_true", help="Compact JSON")

    p_s_get = seq_sub.add_parser("get", parents=[common], help="Retrieve a sequence record")
    p_s_get.add_argument("-n", "--name", "-i", "--id", dest="name", required=True, help="Sequence identifier")
    p_s_get.add_argument("--file-path", default=None, help="Custom JSON store file path")
    p_s_get.add_argument("--json", action="store_true", help="Output JSON")
    p_s_get.add_argument("--compact", action="store_true", help="Compact JSON")

    p_s_del = seq_sub.add_parser("delete", parents=[common], help="Delete a sequence from store")
    p_s_del.add_argument("-n", "--name", "-i", "--id", dest="name", required=True, help="Sequence identifier")
    p_s_del.add_argument("--file-path", default=None, help="Custom JSON store file path")

    p_s_imp = seq_sub.add_parser("import", parents=[common], help="Import sequences from a FASTA file")
    p_s_imp.add_argument("-f", "--file", required=True, help="Path to FASTA file")
    p_s_imp.add_argument("--file-path", default=None, help="Custom JSON store file path")

    p_s_exp = seq_sub.add_parser("export", parents=[common], help="Export stored sequences to FASTA")
    p_s_exp.add_argument("-o", "--output", default="exported_sequences.fasta", help="Output FASTA path")
    p_s_exp.add_argument("--file-path", default=None, help="Custom JSON store file path")

    # 34. plasmid (Circular Plasmid Management, Annotation & GenBank)
    p_plas = subparsers.add_parser("plasmid", parents=[common], help="Plasmid construct inspection, annotation, digest, and GenBank export")
    plas_sub = p_plas.add_subparsers(dest="plasmid_action", help="Plasmid operation")

    p_p_ins = plas_sub.add_parser("inspect", parents=[common], help="Inspect plasmid metadata, features, and biophysics")
    p_p_ins.add_argument("-p", "--plasmid", required=True, help="Plasmid catalog name (e.g. pUC19, pET-28a(+)) or GenBank path")
    p_p_ins.add_argument("--json", action="store_true", help="Output JSON")
    p_p_ins.add_argument("--compact", action="store_true", help="Compact JSON")

    p_p_ann = plas_sub.add_parser("annotate", parents=[common], help="Auto-annotate plasmid features, ORFs, promoters, and markers")
    p_p_ann.add_argument("-p", "--plasmid", required=True, help="Plasmid catalog name or GenBank path")
    p_p_ann.add_argument("--json", action="store_true", help="Output JSON")
    p_p_ann.add_argument("--compact", action="store_true", help="Compact JSON")

    p_p_dig = plas_sub.add_parser("digest", parents=[common], help="In-silico restriction digest prediction")
    p_p_dig.add_argument("-p", "--plasmid", required=True, help="Plasmid catalog name or GenBank path")
    p_p_dig.add_argument("-e", "--enzymes", default="EcoRI", help="Enzyme name(s) (comma or space separated)")
    p_p_dig.add_argument("-l", "--ladder", default="1kb_dna", choices=LADDER_CHOICES, help="MW ladder")
    p_p_dig.add_argument("--json", action="store_true", help="Output JSON")
    p_p_dig.add_argument("--compact", action="store_true", help="Compact JSON")

    p_p_exp = plas_sub.add_parser("export", parents=[common], help="Export plasmid construct to GenBank format")
    p_p_exp.add_argument("-p", "--plasmid", required=True, help="Plasmid catalog name or GenBank path")
    p_p_exp.add_argument("-o", "--output", default=None, help="Output GenBank file path (.gb)")

    # 35. clone-gene (Automated Gene Expression Cloning)
    p_clone = subparsers.add_parser("clone-gene", parents=[common], help="Automated gene expression cloning with frame synchronization and 7-point validation")
    p_clone.add_argument("-v", "--vector", default="pET-28a(+)", help="Destination vector (catalog name e.g. pET-28a(+), or file)")
    p_clone.add_argument("-i", "--insert", required=True, help="Insert coding sequence or FASTA path")
    p_clone.add_argument("-g", "--gene-name", default="Target", help="Gene name")
    p_clone.add_argument("-m", "--mode", default="restriction_ligation", choices=["restriction_ligation", "gibson", "golden_gate"], help="Assembly method")
    p_clone.add_argument("--enzyme5", "-e1", default="BamHI", help="5' restriction enzyme in MCS (default: BamHI)")
    p_clone.add_argument("--enzyme3", "-e2", default="XhoI", help="3' restriction enzyme in MCS (default: XhoI)")
    p_clone.add_argument("--host", default="ecoli", choices=["ecoli", "human"], help="Expression host organism")
    p_clone.add_argument("-o", "--output-gb", default=None, help="Optional GenBank output path")
    p_clone.add_argument("--json", action="store_true", help="Output JSON")
    p_clone.add_argument("--compact", action="store_true", help="Compact JSON")

    # 36. interactive-plasmid (Workbench & SVG Map)
    p_iplas = subparsers.add_parser("interactive-plasmid", parents=[common], help="Launch interactive SVG plasmid workbench in browser or export HTML")
    p_iplas.add_argument("-p", "--plasmid", default="pUC19", help="Plasmid name or record (default: pUC19)")
    p_iplas.add_argument("--port", type=int, default=8050, help="Local port (default: 8050)")
    p_iplas.add_argument("--open-browser", action="store_true", default=True, help="Open browser on launch")
    p_iplas.add_argument("--no-browser", action="store_true", help="Do not open browser")
    p_iplas.add_argument("--export-html", "-o", default=None, help="Export standalone HTML workbench file without running server")

    # 37. aptamer (Aptamer Thermodynamics & Counter-SELEX)
    p_apt = subparsers.add_parser("aptamer", parents=[common], help="Evaluate RNA/DNA aptamer thermodynamics and Counter-SELEX sequencing enrichment")
    p_apt.add_argument("-s", "--seq", default=None, help="Aptamer sequence to fold and evaluate")
    p_apt.add_argument("-t", "--temp", type=float, default=37.0, help="Assay temperature in Celsius (default: 37.0)")
    p_apt.add_argument("--target-counts", default=None, help="Target subunit counts (e.g. 'seq1:120,seq2:45')")
    p_apt.add_argument("--counter-counts", default=None, help="Counter-target counts (e.g. 'seq1:10,seq2:80')")
    p_apt.add_argument("--alpha", type=float, default=1.0, help="Dirichlet smoothing parameter (default: 1.0)")
    p_apt.add_argument("--fdr", type=float, default=0.05, help="FDR threshold for Benjamini-Hochberg (default: 0.05)")
    p_apt.add_argument("--json", action="store_true", help="Output results in JSON format")

    # 38. plate (96/384-Well Microplate Automation & Liquid Handlers)
    p_plate = subparsers.add_parser("plate", parents=[common], help="Design 96/384-well microplate liquid handling worklists and export Echo/Opentrons protocols")
    p_plate.add_argument("--type", choices=["96-well", "384-well"], default="96-well", help="Microplate format (default: 96-well)")
    p_plate.add_argument("--dilution", default="2.0", help="Serial dilution factor or ratio (e.g. 2.0 or 1:2, default: 2.0)")
    p_plate.add_argument("--points", type=int, default=8, help="Number of dilution points (default: 8)")
    p_plate.add_argument("--replicates", type=int, default=3, help="Number of replicate rows (default: 3)")
    p_plate.add_argument("--start-conc", type=float, default=100.0, help="Initial stock concentration (default: 100.0)")
    p_plate.add_argument("--pcr-reactions", type=int, default=None, help="Design PCR setup plate for N reactions")
    p_plate.add_argument("--export-echo", default=None, help="Output file path for Labcyte Echo CSV pick list")
    p_plate.add_argument("--export-opentrons", default=None, help="Output file path for Opentrons Python protocol")
    p_plate.add_argument("--export-pylabrobot", default=None, help="Output file path for PyLabRobot JSON worklist")
    p_plate.add_argument("--json", action="store_true", help="Output worklist in JSON format")

    # 39. scn (Bio-Rad Image Lab .scn and Quantity One .1sc Gel Imager Parser)
    p_scn = subparsers.add_parser("scn", parents=[common], help="Parse Bio-Rad Image Lab (.scn) and Quantity One (.1sc) gel files, export PNG/TIFF, and run lane densitometry")
    p_scn.add_argument("-i", "--input", required=True, help="Input .scn or .1sc file path")
    p_scn.add_argument("--output-png", default=None, help="Output PNG preview file path")
    p_scn.add_argument("--output-tiff", default=None, help="Output 16-bit uncompressed TIFF file path")
    p_scn.add_argument("--lanes", type=int, default=None, help="Number of lanes for 1D densitometry profiling")
    p_scn.add_argument("--detect-bands", action="store_true", help="Perform band peak detection along each lane profile")
    p_scn.add_argument("--invert", action="store_true", help="Invert pixel intensities")
    p_scn.add_argument("--gamma", type=float, default=1.0, help="Gamma correction factor (default: 1.0)")
    p_scn.add_argument("--no-auto-contrast", action="store_true", help="Disable min-max percentile auto-contrast stretch")
    p_scn.add_argument("--json", action="store_true", help="Output metadata and densitometry results in JSON format")
    p_scn.add_argument("--compact", action="store_true", help="Compact JSON output without indentation")

    return parser



def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = COMMAND_DISPATCH.get(args.command)
    if not handler:
        parser.print_help()
        sys.exit(1)

    try:
        handler(args)
    except SystemExit:
        raise
    except Exception as exc:
        try:
            from .diagnostics import record_failure
            record_failure("CLI", exc, context={"command": args.command, "argv": argv or sys.argv[1:]})
        except Exception:
            pass
        if getattr(args, "json", False):
            _dump_json({"error": str(exc)}, getattr(args, "compact", False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)



if __name__ == "__main__":
    main()
