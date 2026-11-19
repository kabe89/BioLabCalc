# CLI Subcommands & Core Module Map

BioLabCalc provides 46 CLI subcommands and 37 core computational modules. This document maps each CLI subcommand and core library module to its underlying implementation, handler, and public Python API.

---

## 🗺️ Subcommand Mapping Table

| CLI Subcommand | Primary Python Module | Handler in `cli.py` | Key Functions / Python API |
| :--- | :--- | :--- | :--- |
| `annotate-gel` | `biolabcalc.gel_annotator` | `handle_annotate_gel` | `GelAnnotator.annotate_gel` |
| `aptamer` | `biolabcalc.aptamers` | `handle_aptamer` | `design_aptamer, analyze_counter_selex` |
| `batch-csv` | `biolabcalc.batch_csv` | `handle_batch_csv` | `process_batch_csv` |
| `batch-excel` | `biolabcalc.excel_extension` | `handle_batch_excel` | `batch_process_excel` |
| `buffer` | `biolabcalc.buffers` | `handle_buffer` | `calculate_buffer_recipe` |
| `clone-gene` | `biolabcalc.plasmid_engineering` | `handle_clone_gene` | `engineer_plasmid, evaluate_codon_usage` |
| `convert` | `biolabcalc.units / easy` | `handle_convert` | `easy_convert` |
| `diagnostics` | `biolabcalc.diagnostics` | `handle_diagnostics` | `inspect_diagnostics` |
| `digest` | `biolabcalc.cloning / restriction_engine` | `handle_digest` | `plan_restriction_digest, predict_restriction_digest` |
| `dilute` | `biolabcalc.easy` | `handle_dilute` | `dilute(c1, c2, v2)` |
| `ecoli` | `biolabcalc.ecoli_growth` | `handle_ecoli` | `calculate_ecoli_growth, estimate_plasmid_yield` |
| `eln` | `biolabcalc.eln.server` | `handle_eln` | `launch_eln_server` |
| `excel-template` | `biolabcalc.excel_extension` | `handle_excel_template` | `generate_lab_notebook_template` |
| `fluo` | `biolabcalc.fluorescence` | `handle_fluo` | `apply_fluorophore_modification, calculate_degree_of_labeling` |
| `gel` | `biolabcalc.gels` | `handle_gel` | `simulate_gel` |
| `gibson` | `biolabcalc.cloning` | `handle_gibson` | `calculate_gibson_assembly` |
| `golden-gate` | `biolabcalc.cloning` | `handle_golden_gate` | `calculate_golden_gate_assembly` |
| `hepes` | `biolabcalc.buffers` | `handle_hepes` | `calculate_hepes_ivt_buffer` |
| `interactive` | `biolabcalc.cli` | `handle_wizard` | `run_wizard() (alias for wizard)` |
| `interactive-gel` | `biolabcalc.interactive_gel` | `handle_interactive_gel` | `launch_interactive_annotator, save_interactive_app` |
| `interactive-plasmid` | `biolabcalc.interactive_plasmid` | `handle_interactive_plasmid` | `render_plasmid_map_svg, save_plasmid_workbench_html` |
| `ivt` | `biolabcalc.transcription` | `handle_ivt` | `calculate_ivt_yield` |
| `ivt-time` | `biolabcalc.transcription` | `handle_ivt_time` | `optimize_transcription_time` |
| `ligate` | `biolabcalc.cloning` | `handle_ligate` | `calculate_ligation` |
| `mw` | `biolabcalc.molecular_weight` | `handle_mw` | `calculate_dna_mw, calculate_rna_mw, calculate_protein_mw` |
| `nanodrop` | `biolabcalc.spectroscopy` | `handle_nanodrop` | `prepare_standard_solution, assess_nanodrop_purity` |
| `ntp-ph` | `biolabcalc.buffers` | `handle_ntp_ph` | `calculate_ntp_ph_adjustment` |
| `pci` | `biolabcalc.precipitation` | `handle_pci` | `calculate_phenol_chloroform_extraction` |
| `pcr` | `biolabcalc.pcr` | `handle_pcr` | `calculate_pcr_kinetics` |
| `pcr-opt` | `biolabcalc.pcr` | `handle_pcr_opt` | `optimize_pcr_protocol` |
| `plasmid` | `biolabcalc.plasmid` | `handle_plasmid` | `load_plasmid, parse_genbank, export_genbank, auto_annotate_plasmid` |
| `plate` | `biolabcalc.workflows / automation` | `handle_plate` | `generate_pipetting_map` |
| `portable` | `biolabcalc.portable` | `handle_portable` | `check_portable_environment` |
| `precipitate` | `biolabcalc.precipitation` | `handle_precipitate` | `calculate_precipitation` |
| `primers` | `biolabcalc.primers` | `handle_primers` | `design_primers, analyze_primer` |
| `print-protocol` | `biolabcalc.printable_protocol / protocols` | `handle_print_protocol` | `format_protocol_markdown, format_protocol_html` |
| `protein` | `biolabcalc.protein` | `handle_protein` | `quantify_protein_a280, calculate_extinction_coefficient` |
| `purity` | `biolabcalc.spectroscopy` | `handle_purity` | `assess_nanodrop_purity` |
| `rc` | `biolabcalc.seq_utils` | `handle_rc` | `reverse_complement` |
| `report` | `biolabcalc.lab_report` | `handle_report` | `get_active_report, new_lab_report` |
| `scn` | `biolabcalc.workflows` | `handle_scn` | `build_scn_cloning_workflow` |
| `seq` | `biolabcalc.sequence_store` | `handle_seq` | `save_sequence, get_sequence, list_sequences, delete_sequence` |
| `setup` | `biolabcalc.setup_wizard` | `handle_setup` | `run_setup_wizard` |
| `translate` | `biolabcalc.seq_utils` | `handle_translate` | `translate_dna` |
| `western` | `biolabcalc.western_blot` | `handle_western` | `plan_western_blot, troubleshoot_western_blot` |
| `wizard` | `biolabcalc.cli` | `handle_wizard` | `run_wizard()` |

---

## 📦 Core Python Modules Reference

All 37 core Python modules in `src/biolabcalc/` operate with **zero external dependencies** (`dependencies = []`), standard library math, and strict Python 3.8+ AST compatibility:

| Module | Primary Scientific & Architectural Role |
| :--- | :--- |
| `biolabcalc.allostery` | Graph-based allosteric communication pathway tracing via Kirchhoff Laplacian, GNM, and Yen's algorithm |
| `biolabcalc.aptamers` | SELEX counter-selection mathematical modeling, sequence enrichment, and aptamer structure scoring |
| `biolabcalc.automation` | Hamilton / Tecan automated liquid handler script generation, worklist formulation, and deck geometry |
| `biolabcalc.batch_csv` | High-throughput CSV batch calculator for dilution, PCR, and oligonucleotide preparation pipelines |
| `biolabcalc.buffers` | Physiological buffer formulations (Tris, PBS, HEPES, TAE, TBE), pH titration math, and custom recipe builder |
| `biolabcalc.cli` | Command-line interface entry point, argument parsing, interactive wizard, and subcommand dispatch |
| `biolabcalc.cloning` | Molecular cloning calculations: restriction digestion, ligation, Gibson assembly, and Golden Gate |
| `biolabcalc.diagnostics` | Runtime environment diagnostics, system dependency verification, and telemetry audit |
| `biolabcalc.easy` | High-level pythonic convenience wrapper exposing simplified, zero-friction calculation aliases |
| `biolabcalc.ecoli_growth` | Bacterial growth kinetics (Monod model, doubling time, OD600) and plasmid copy-number estimation |
| `biolabcalc.excel_extension` | Excel workbook integration, batch worksheet computation, and styled lab notebook generation |
| `biolabcalc.fluorescence` | Fluorophore labeling degree calculation (DOL), extinction correction, and fluorescence recovery |
| `biolabcalc.gel_annotator` | Agarose and SDS-PAGE gel image annotation, band detection, and publication figure generation |
| `biolabcalc.gels` | Gel electrophoresis migration simulation, molecular weight estimation, and RF curve fitting |
| `biolabcalc.interactive_gel` | Browser-based standalone interactive gel visualization, band quantification, and annotation app |
| `biolabcalc.interactive_plasmid` | Interactive vector plasmid map generator with circular/linear SVG rendering and annotation editor |
| `biolabcalc.lab_report` | Standardized laboratory experiment report builder with statistical analysis, HTML, and Excel export |
| `biolabcalc.molecular_weight` | High-precision molecular weight computation for single/double-stranded DNA, RNA, and proteins |
| `biolabcalc.pcr` | Polymerase chain reaction master mix formulation, cycling protocol design, and kinetics modeling |
| `biolabcalc.plasmid` | Circular plasmid storage, annotation indexing, Modulo-L coordinates, and GenBank I/O engine |
| `biolabcalc.plasmid_engineering` | Automated in-silico vector engineering, codon adaptation index (CAI), and gene insertion |
| `biolabcalc.precipitation` | Ethanol, isopropanol, and PEG nucleic acid precipitation recipe and yield calculations |
| `biolabcalc.primers` | Thermodynamic primer design, SantaLucia nearest-neighbor Tm, secondary structure, and hairpin checks |
| `biolabcalc.printable_protocol` | Bench-ready printable SOP protocol generators with high-contrast print layouts |
| `biolabcalc.profile` | Unified BioLabCalc home directory and storage profile resolution across env vars and config.yaml |
| `biolabcalc.protein` | Protein spectrophotometric quantification (A280, Bradford, BCA) and molar extinction calculation |
| `biolabcalc.protocols` | Structured laboratory experimental protocol definitions, timer tracking, and HTML print rendering |
| `biolabcalc.restriction_engine` | Restriction endonuclease cleavage prediction, isoschizomers, and fragment size determination |
| `biolabcalc.seq_utils` | Core nucleotide sequence utilities: validation, reverse complement, GC content, and 6-frame translation |
| `biolabcalc.sequence_store` | Structured sequence catalog, FASTA persistence, metadata indexing, and checksum verification |
| `biolabcalc.setup_wizard` | Interactive terminal setup assistant for initial configuration and profile creation |
| `biolabcalc.spectroscopy` | NanoDrop UV-Vis purity evaluation (A260/A280, A260/A230) and contaminant deconvolution |
| `biolabcalc.tea_runtime` | Traceable Experimental Architecture (TEA) runtime invariants and mathematical immutability guards |
| `biolabcalc.transcription` | In-vitro transcription (IVT) yield optimization, NTP stoichiometric tuning, and kinetics |
| `biolabcalc.units` | Biochemical unit conversions (molar, mass, volume, enzymatic units) with dimensional analysis |
| `biolabcalc.western_blot` | Western blot antibody dilution calculation, transfer buffer formulation, and troubleshooting |
| `biolabcalc.workflows` | Multi-step orchestrated laboratory workflows: SCN cloning pipelines and microplate liquid handling |

---

## 💡 Convenience Shortcuts (`biolabcalc.easy`)

For high-speed scripting and notebook use, `biolabcalc.easy` exports shortened functional aliases:

```python
import biolabcalc.easy as ez

# Quick translation and reverse complement
rc_seq = ez.rc("ATGCGTA")
aa_seq = ez.translate("ATGGCCATTGTA")

# Rapid molecular weight lookups
mw_dna = ez.dna_mw("ATGCGTA", double_stranded=True)
mw_prot = ez.protein_mw("MVKVY")

# Cloning & engineering
res = ez.clone_gene(vector="pET-28a(+)", insert_seq="ATG...", gene_name="GFP")
svg = ez.plasmid_svg("pUC19")

# Allosteric pathway tracing & SELEX
paths = ez.trace_allostery(sample_pdb, source_resid=1, sink_resid=6)
aptamer_score = ez.score_aptamer("GGGAGGACG...")
```
