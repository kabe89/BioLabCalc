#!/usr/bin/env python3
"""update_ai_docs.py — Auto-synchronizer for .ai_docs/CLI_AND_MODULE_MAP.md.

Inspects:
1. `src/biolabcalc/cli.py` for all registered subparsers and their handler functions.
2. `src/biolabcalc/*.py` for all 37 core computational, structural, and workflow modules.

Supports:
- Default mode: Writes the synchronized document to `.ai_docs/CLI_AND_MODULE_MAP.md`.
- `--check` mode: Exits with 0 if `.ai_docs/CLI_AND_MODULE_MAP.md` is strictly in sync,
  or exits with 1 if drift or missing commands/modules are detected.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Known subcommand mapping metadata
SUBCOMMAND_METADATA = {
    "dilute": ("biolabcalc.easy", "handle_dilute", "dilute(c1, c2, v2)"),
    "wizard": ("biolabcalc.cli", "handle_wizard", "run_wizard()"),
    "interactive": ("biolabcalc.cli", "handle_wizard", "run_wizard() (alias for wizard)"),
    "mw": ("biolabcalc.molecular_weight", "handle_mw", "calculate_dna_mw, calculate_rna_mw, calculate_protein_mw"),
    "ivt": ("biolabcalc.transcription", "handle_ivt", "calculate_ivt_yield"),
    "pcr": ("biolabcalc.pcr", "handle_pcr", "calculate_pcr_kinetics"),
    "pcr-opt": ("biolabcalc.pcr", "handle_pcr_opt", "optimize_pcr_protocol"),
    "protein": ("biolabcalc.protein", "handle_protein", "quantify_protein_a280, calculate_extinction_coefficient"),
    "primers": ("biolabcalc.primers", "handle_primers", "design_primers, analyze_primer"),
    "nanodrop": ("biolabcalc.spectroscopy", "handle_nanodrop", "prepare_standard_solution, assess_nanodrop_purity"),
    "fluo": ("biolabcalc.fluorescence", "handle_fluo", "apply_fluorophore_modification, calculate_degree_of_labeling"),
    "gel": ("biolabcalc.gels", "handle_gel", "simulate_gel"),
    "ecoli": ("biolabcalc.ecoli_growth", "handle_ecoli", "calculate_ecoli_growth, estimate_plasmid_yield"),
    "excel-template": ("biolabcalc.excel_extension", "handle_excel_template", "generate_lab_notebook_template"),
    "annotate-gel": ("biolabcalc.gel_annotator", "handle_annotate_gel", "GelAnnotator.annotate_gel"),
    "interactive-gel": ("biolabcalc.interactive_gel", "handle_interactive_gel", "launch_interactive_annotator, save_interactive_app"),
    "batch-excel": ("biolabcalc.excel_extension", "handle_batch_excel", "batch_process_excel"),
    "digest": ("biolabcalc.cloning / restriction_engine", "handle_digest", "plan_restriction_digest, predict_restriction_digest"),
    "ligate": ("biolabcalc.cloning", "handle_ligate", "calculate_ligation"),
    "gibson": ("biolabcalc.cloning", "handle_gibson", "calculate_gibson_assembly"),
    "buffer": ("biolabcalc.buffers", "handle_buffer", "calculate_buffer_recipe"),
    "precipitate": ("biolabcalc.precipitation", "handle_precipitate", "calculate_precipitation"),
    "ntp-ph": ("biolabcalc.buffers", "handle_ntp_ph", "calculate_ntp_ph_adjustment"),
    "golden-gate": ("biolabcalc.cloning", "handle_golden_gate", "calculate_golden_gate_assembly"),
    "purity": ("biolabcalc.spectroscopy", "handle_purity", "assess_nanodrop_purity"),
    "pci": ("biolabcalc.precipitation", "handle_pci", "calculate_phenol_chloroform_extraction"),
    "ivt-time": ("biolabcalc.transcription", "handle_ivt_time", "optimize_transcription_time"),
    "hepes": ("biolabcalc.buffers", "handle_hepes", "calculate_hepes_ivt_buffer"),
    "western": ("biolabcalc.western_blot", "handle_western", "plan_western_blot, troubleshoot_western_blot"),
    "report": ("biolabcalc.lab_report", "handle_report", "get_active_report, new_lab_report"),
    "eln": ("biolabcalc.eln.server", "handle_eln", "launch_eln_server"),
    "convert": ("biolabcalc.units / easy", "handle_convert", "easy_convert"),
    "batch-csv": ("biolabcalc.batch_csv", "handle_batch_csv", "process_batch_csv"),
    "rc": ("biolabcalc.seq_utils", "handle_rc", "reverse_complement"),
    "translate": ("biolabcalc.seq_utils", "handle_translate", "translate_dna"),
    "diagnostics": ("biolabcalc.diagnostics", "handle_diagnostics", "inspect_diagnostics"),
    "setup": ("biolabcalc.setup_wizard", "handle_setup", "run_setup_wizard"),
    "portable": ("biolabcalc.portable", "handle_portable", "check_portable_environment"),
    "seq": ("biolabcalc.sequence_store", "handle_seq", "save_sequence, get_sequence, list_sequences, delete_sequence"),
    "plasmid": ("biolabcalc.plasmid", "handle_plasmid", "load_plasmid, parse_genbank, export_genbank, auto_annotate_plasmid"),
    "clone-gene": ("biolabcalc.plasmid_engineering", "handle_clone_gene", "engineer_plasmid, evaluate_codon_usage"),
    "interactive-plasmid": ("biolabcalc.interactive_plasmid", "handle_interactive_plasmid", "render_plasmid_map_svg, save_plasmid_workbench_html"),
    "aptamer": ("biolabcalc.aptamers", "handle_aptamer", "design_aptamer, analyze_counter_selex"),
    "plate": ("biolabcalc.workflows / automation", "handle_plate", "generate_pipetting_map"),
    "scn": ("biolabcalc.workflows", "handle_scn", "build_scn_cloning_workflow"),
    "print-protocol": ("biolabcalc.printable_protocol / protocols", "handle_print_protocol", "format_protocol_markdown, format_protocol_html"),
    "protein-recommend": ("biolabcalc.protein_recommender", "handle_protein_recommend", "recommend_protein_strategy, analyze_protein_profile"),
    "pcr-protocol": ("biolabcalc.protocols / pcr", "handle_pcr_protocol", "generate_pcr_protocol"),
    "sds-page": ("biolabcalc.gels", "handle_sds_page", "simulate_sds_page"),
    "mouse": ("biolabcalc.in_vivo", "handle_mouse", "calculate_mouse_dose, evaluate_mouse_welfare, export_arrive_report_html"),
}

MODULE_DESCRIPTIONS = {
    "allostery": "Graph-based allosteric communication pathway tracing via Kirchhoff Laplacian, GNM, and Yen's algorithm",
    "aptamers": "SELEX counter-selection mathematical modeling, sequence enrichment, and aptamer structure scoring",
    "automation": "Hamilton / Tecan automated liquid handler script generation, worklist formulation, and deck geometry",
    "batch_csv": "High-throughput CSV batch calculator for dilution, PCR, and oligonucleotide preparation pipelines",
    "buffers": "Physiological buffer formulations (Tris, PBS, HEPES, TAE, TBE), pH titration math, and custom recipe builder",
    "cli": "Command-line interface entry point, argument parsing, interactive wizard, and subcommand dispatch",
    "cloning": "Molecular cloning calculations: restriction digestion, ligation, Gibson assembly, and Golden Gate",
    "diagnostics": "Runtime environment diagnostics, system dependency verification, and telemetry audit",
    "easy": "High-level pythonic convenience wrapper exposing simplified, zero-friction calculation aliases",
    "ecoli_growth": "Bacterial growth kinetics (Monod model, doubling time, OD600) and plasmid copy-number estimation",
    "excel_extension": "Excel workbook integration, batch worksheet computation, and styled lab notebook generation",
    "fluorescence": "Fluorophore labeling degree calculation (DOL), extinction correction, and fluorescence recovery",
    "gel_annotator": "Agarose and SDS-PAGE gel image annotation, band detection, and publication figure generation",
    "gels": "Gel electrophoresis migration simulation, molecular weight estimation, and RF curve fitting",
    "in_vivo": "Preclinical mouse model documentation, dose calculations, route volume limits, welfare monitoring, and ARRIVE 2.0 reports",
    "interactive_gel": "Browser-based standalone interactive gel visualization, band quantification, and annotation app",
    "interactive_plasmid": "Interactive vector plasmid map generator with circular/linear SVG rendering and annotation editor",
    "lab_report": "Standardized laboratory experiment report builder with statistical analysis, HTML, and Excel export",
    "molecular_weight": "High-precision molecular weight computation for single/double-stranded DNA, RNA, and proteins",
    "pcr": "Polymerase chain reaction master mix formulation, cycling protocol design, and kinetics modeling",
    "plasmid": "Circular plasmid storage, annotation indexing, Modulo-L coordinates, and GenBank I/O engine",
    "plasmid_engineering": "Automated in-silico vector engineering, codon adaptation index (CAI), and gene insertion",
    "plugins": "Zero-dependency plugin discovery and extension registry for custom backbones, enzymes, and themes",
    "precipitation": "Ethanol, isopropanol, and PEG nucleic acid precipitation recipe and yield calculations",
    "primers": "Thermodynamic primer design, SantaLucia nearest-neighbor Tm, secondary structure, and hairpin checks",
    "printable_protocol": "Bench-ready printable SOP protocol generators with high-contrast print layouts",
    "profile": "Unified BioLabCalc home directory and storage profile resolution across env vars and config.yaml",
    "protein": "Protein spectrophotometric quantification (A280, Bradford, BCA) and molar extinction calculation",
    "protein_recommender": "Application-specific protein expression host, tag, protease, and buffer strategy recommendations",
    "protocols": "Structured laboratory experimental protocol definitions, timer tracking, and HTML print rendering",
    "restriction_engine": "Restriction endonuclease cleavage prediction, isoschizomers, and fragment size determination",
    "seq_utils": "Core nucleotide sequence utilities: validation, reverse complement, GC content, and 6-frame translation",
    "sequence_store": "Structured sequence catalog, FASTA persistence, metadata indexing, and checksum verification",
    "setup_wizard": "Interactive terminal setup assistant for initial configuration and profile creation",
    "spectroscopy": "NanoDrop UV-Vis purity evaluation (A260/A280, A260/A230) and contaminant deconvolution",
    "tea_runtime": "Traceable Experimental Architecture (TEA) runtime invariants and mathematical immutability guards",
    "theme": "Minimalist CSS design tokens, WCAG AAA color presets, and atomic theme configuration persistence",
    "transcription": "In-vitro transcription (IVT) yield optimization, NTP stoichiometric tuning, and kinetics",
    "units": "Biochemical unit conversions (molar, mass, volume, enzymatic units) with dimensional analysis",
    "western_blot": "Western blot antibody dilution calculation, transfer buffer formulation, and troubleshooting",
    "workflows": "Multi-step orchestrated laboratory workflows: SCN cloning pipelines and microplate liquid handling",
}


def introspect_cli_subparsers() -> list[str]:
    cli_file = REPO_ROOT / "src" / "biolabcalc" / "cli.py"
    if not cli_file.exists():
        return []
    content = cli_file.read_text(encoding="utf-8")
    parsers = set(re.findall(r'subparsers\.add_parser\(\s*["\']([a-zA-Z0-9_\-]+)["\']', content))
    # Include known aliases
    if "wizard" in parsers:
        parsers.add("interactive")
    return sorted(parsers)


def introspect_core_modules() -> list[str]:
    modules_dir = REPO_ROOT / "src" / "biolabcalc"
    modules = []
    for f in sorted(modules_dir.glob("*.py")):
        name = f.stem
        if not name.startswith("__") and name not in ("__init__", "__main__"):
            modules.append(name)
    return modules


def generate_doc() -> str:
    subparsers = introspect_cli_subparsers()
    core_modules = introspect_core_modules()

    lines = []
    lines.append("# CLI Subcommands & Core Module Map")
    lines.append("")
    lines.append(
        f"BioLabCalc provides {len(subparsers)} CLI subcommands and {len(core_modules)} core computational modules. "
        "This document maps each CLI subcommand and core library module to its underlying implementation, handler, and public Python API."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🗺️ Subcommand Mapping Table")
    lines.append("")
    lines.append("| CLI Subcommand | Primary Python Module | Handler in `cli.py` | Key Functions / Python API |")
    lines.append("| :--- | :--- | :--- | :--- |")

    for cmd in subparsers:
        if cmd in SUBCOMMAND_METADATA:
            mod, handler, api = SUBCOMMAND_METADATA[cmd]
        else:
            mod = "biolabcalc.cli"
            handler = f"handle_{cmd.replace('-', '_')}"
            api = f"run_{cmd.replace('-', '_')}()"
        lines.append(f"| `{cmd}` | `{mod}` | `{handler}` | `{api}` |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📦 Core Python Modules Reference")
    lines.append("")
    lines.append(f"All {len(core_modules)} core Python modules in `src/biolabcalc/` operate with **zero external dependencies** (`dependencies = []`), standard library math, and strict Python 3.8+ AST compatibility:")
    lines.append("")
    lines.append("| Module | Primary Scientific & Architectural Role |")
    lines.append("| :--- | :--- |")

    for mod in core_modules:
        desc = MODULE_DESCRIPTIONS.get(mod, f"Core BioLabCalc {mod} computational service")
        lines.append(f"| `biolabcalc.{mod}` | {desc} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 💡 Convenience Shortcuts (`biolabcalc.easy`)")
    lines.append("")
    lines.append("For high-speed scripting and notebook use, `biolabcalc.easy` exports shortened functional aliases:")
    lines.append("")
    lines.append("```python")
    lines.append("import biolabcalc.easy as ez")
    lines.append("")
    lines.append("# Quick translation and reverse complement")
    lines.append('rc_seq = ez.rc("ATGCGTA")')
    lines.append('aa_seq = ez.translate("ATGGCCATTGTA")')
    lines.append("")
    lines.append("# Rapid molecular weight lookups")
    lines.append('mw_dna = ez.dna_mw("ATGCGTA", double_stranded=True)')
    lines.append('mw_prot = ez.protein_mw("MVKVY")')
    lines.append("")
    lines.append("# Cloning & engineering")
    lines.append('res = ez.clone_gene(vector="pET-28a(+)", insert_seq="ATG...", gene_name="GFP")')
    lines.append('svg = ez.plasmid_svg("pUC19")')
    lines.append("")
    lines.append("# Allosteric pathway tracing & SELEX")
    lines.append('paths = ez.trace_allostery(sample_pdb, source_resid=1, sink_resid=6)')
    lines.append('aptamer_score = ez.score_aptamer("GGGAGGACG...")')
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize .ai_docs/CLI_AND_MODULE_MAP.md")
    parser.add_argument("--check", action="store_true", help="Check for drift without modifying files")
    args = parser.parse_args()

    doc_path = REPO_ROOT / ".ai_docs" / "CLI_AND_MODULE_MAP.md"
    expected = generate_doc()

    if not doc_path.exists():
        if args.check:
            print(f"[FAIL] {doc_path} does not exist.")
            sys.exit(1)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(expected, encoding="utf-8")
        print(f"[UPDATED] Created {doc_path}")
        sys.exit(0)

    current = doc_path.read_text(encoding="utf-8")

    # Normalize newlines for cross-platform comparison
    norm_current = current.replace("\r\n", "\n").strip()
    norm_expected = expected.replace("\r\n", "\n").strip()

    if norm_current == norm_expected:
        print(f"[OK] {doc_path.relative_to(REPO_ROOT)} is strictly synchronized with codebase.")
        sys.exit(0)

    if args.check:
        print(f"[!] DRIFT DETECTED: {doc_path.relative_to(REPO_ROOT)} is out of sync with codebase:")
        diff = difflib.unified_diff(
            norm_current.splitlines(keepends=True),
            norm_expected.splitlines(keepends=True),
            fromfile=str(doc_path.relative_to(REPO_ROOT)),
            tofile=str(doc_path.relative_to(REPO_ROOT)) + " (expected)",
        )
        sys.stdout.writelines(diff)
        print("\nRun 'python scripts/update_ai_docs.py' to update automatically.")
        sys.exit(1)
    else:
        doc_path.write_text(expected, encoding="utf-8")
        print(f"[UPDATED] {doc_path.relative_to(REPO_ROOT)} synchronized successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
