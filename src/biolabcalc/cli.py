"""Command-line interface (CLI) for BioLabCalc."""

from __future__ import annotations
from .units import UnitParser
from .easy import dilute
import argparse
import sys
import os
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
from .excel_extension import generate_lab_notebook_template, batch_process_excel
from .gel_annotator import GelAnnotator
from .cloning import plan_restriction_digest, calculate_ligation, calculate_gibson_assembly, calculate_golden_gate_assembly
from .buffers import calculate_buffer_recipe, calculate_hepes_ivt_buffer, calculate_ntp_ph_adjustment, BUFFER_CATALOG, CustomBufferBuilder, list_custom_buffers
from .protocols import list_protocols, get_protocol, format_protocol_markdown, export_all_protocols_markdown, PROTOCOL_CATALOG
from .precipitation import calculate_precipitation, calculate_phenol_chloroform_extraction

from .interactive_gel import save_interactive_app, launch_interactive_annotator



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
    print("  [8] Standard Laboratory Protocols Compendium")
    print("  [q] Quit")
    print("-" * 75)

    choice = input("Enter option [1-8]: ").strip().lower()
    if choice in ("q", "quit", "exit"):
        print("Exiting BioLabCalc Wizard.")
        return

    if choice == "1":
        print("\n--- Dilution Calculator (C1*V1 = C2*V2) ---")
        c1 = input("Enter Stock Conc C1 (e.g. '100 mM'): ").strip()
        c2 = input("Enter Target Conc C2 (e.g. '25 mM'): ").strip()
        v2 = input("Enter Target Volume V2 (e.g. '16 mL'): ").strip()
        res = dilute(c1=c1, c2=c2, v2=v2)
        print(f"\n--> Take {res['v1'] / 1000.0:.3f} mL of stock and add {res['diluent_needed'] / 1000.0:.3f} mL diluent.")

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

    elif choice == "5":
        print("\n--- Laboratory Buffer Recipe ---")
        print(f"Available buffers: {list(BUFFER_CATALOG.keys())}")
        b_name = input("Buffer name [10X_PBS]: ").strip() or "10X_PBS"
        vol = input("Target volume in mL [1000]: ").strip() or "1000"
        res = calculate_buffer_recipe(b_name, target_volume_ml=float(vol))
        print(f"\nRecipe for {res.name} ({res.target_volume_ml:.0f} mL):")
        for c in res.components:
            print(f"  - {c.name}: {c.amount} {c.unit} ({c.molar_concentration})")

    elif choice == "8":
        print("\n--- Standard Protocols Compendium ---")
        protos = list_protocols()
        for idx, p in enumerate(protos, 1):
            print(f"  [{idx}] {p.protocol_id} - {p.title}")
        sel = input("\nEnter protocol number or ID [1]: ").strip() or "1"
        if sel.isdigit() and 1 <= int(sel) <= len(protos):
            p = protos[int(sel) - 1]
        else:
            p = get_protocol(sel)
        print("\n" + format_protocol_markdown(p))
    else:
        print("Feature available directly via CLI commands. Run 'biolabcalc --help'.")


def main():
    parser = argparse.ArgumentParser(
        prog="biolabcalc",
        description="BioLabCalc: Multifaceted molecular biology stoichiometry, PCR, IVT, protein yield, fluorophore mods, gel ladders, and E. coli growth.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 0. dilute
    p_dil = subparsers.add_parser("dilute", help="Solve C1*V1 = C2*V2 dilution calculation (e.g. -c1 '100 mM' -c2 '25 mM' -v2 '16 mL')")
    p_dil.add_argument("-c1", default=None, help="Stock concentration (e.g. '100 mM')")
    p_dil.add_argument("-v1", default=None, help="Stock volume (e.g. '4.0 mL')")
    p_dil.add_argument("-c2", default=None, help="Target working concentration (e.g. '25 mM')")
    p_dil.add_argument("-v2", default=None, help="Target final volume (e.g. '16 mL')")

    # 0b. wizard
    p_wiz = subparsers.add_parser("wizard", aliases=["interactive"], help="Interactive guided step-by-step wizard for bench calculations")

    # 1. mw
    p_mw = subparsers.add_parser("mw", help="Calculate molecular weight of DNA, RNA, or Protein")
    p_mw.add_argument("-s", "--sequence", required=True, help="Sequence string")
    p_mw.add_argument("-t", "--type", choices=["dna", "rna", "protein"], default="dna", help="Sequence type")
    p_mw.add_argument("--ds", action="store_true", help="Double-stranded (for DNA)")
    p_mw.add_argument("--end-5", choices=["hydroxyl", "monophosphate", "triphosphate"], default="hydroxyl", help="5' phosphorylation state")
    p_mw.add_argument("--end-3", choices=["hydroxyl", "monophosphate", "diphosphate", "triphosphate", "cyclic_phosphate"], default="hydroxyl", help="3' terminal phosphorylation state")
    p_mw.add_argument("--backbone", choices=["monophosphate", "phosphorothioate"], default="monophosphate", help="Internucleotide backbone chemistry")

    # 2. ivt
    p_ivt = subparsers.add_parser("ivt", help="Calculate in vitro transcription yield and NTP stoichiometry")
    p_ivt.add_argument("-s", "--sequence", required=True, help="RNA or DNA template sequence (promoter auto-trimmed)")
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
    p_pcr = subparsers.add_parser("pcr", help="Calculate PCR kinetics and dNTP usage")
    p_pcr.add_argument("-l", "--length", type=int, required=True, help="Amplicon length in bp")
    p_pcr.add_argument("-t", "--template-ng", type=float, required=True, help="Template input in ng")
    p_pcr.add_argument("-c", "--cycles", type=int, default=30, help="PCR cycles")

    # 4. pcr-opt
    p_pcr_opt = subparsers.add_parser("pcr-opt", help="Optimize PCR annealing temp, extension time, and cycling")
    p_pcr_opt.add_argument("--fwd-tm", type=float, required=True, help="Forward primer Tm in °C")
    p_pcr_opt.add_argument("--rev-tm", type=float, required=True, help="Reverse primer Tm in °C")
    p_pcr_opt.add_argument("-l", "--length", type=int, required=True, help="Amplicon length in bp")
    p_pcr_opt.add_argument("-p", "--polymerase", default="taq", choices=["taq", "q5", "phusion", "kapa"], help="Polymerase type")
    p_pcr_opt.add_argument("--gc", type=float, default=50.0, help="Amplicon GC percentage")

    # 5. protein
    p_prot = subparsers.add_parser("protein", help="Quantify protein A280 concentration and yield")
    p_prot.add_argument("-s", "--sequence", required=True, help="Amino acid sequence")
    p_prot.add_argument("-a", "--a280", type=float, required=True, help="Absorbance at 280 nm")
    p_prot.add_argument("-v", "--volume-ml", type=float, default=1.0, help="Purified volume in mL")

    # 6. primers
    p_prim = subparsers.add_parser("primers", help="Design forward and reverse primers")
    p_prim.add_argument("-s", "--sequence", required=True, help="Template DNA sequence")
    p_prim.add_argument("--target-tm", type=float, default=60.0, help="Target Tm in °C")

    # 7. nanodrop
    p_nano = subparsers.add_parser("nanodrop", help="Prepare standardized solutions (e.g. 4uM ssRNA at 500uL) and predict NanoDrop readings")
    p_nano.add_argument("-u", "--molarity-um", type=float, required=True, help="Target molarity in µM (e.g. 4.0)")
    p_nano.add_argument("-v", "--volume-ul", type=float, required=True, help="Target volume in µL (e.g. 500.0)")
    p_nano.add_argument("-t", "--type", default="rna", choices=["rna", "dna", "ssdna", "dsdna", "protein"], help="Biomolecule type")
    p_nano.add_argument("-s", "--sequence", default=None, help="Sequence (optional)")
    p_nano.add_argument("--length", type=int, default=100, help="Length in nt/bp (used if sequence omitted)")
    p_nano.add_argument("--stock-ng-ul", type=float, default=None, help="Stock concentration in ng/µL (for dilution)")
    p_nano.add_argument("--end-5", choices=["hydroxyl", "monophosphate", "triphosphate"], default="hydroxyl", help="5' end state")

    # 8. fluo
    p_fluo = subparsers.add_parser("fluo", help="Calculate fluorophore modifications and Degree of Labeling (DOL)")
    p_fluo.add_argument("-s", "--sequence", required=True, help="Sequence")
    p_fluo.add_argument("-t", "--type", default="dna", choices=["dna", "rna", "protein"], help="Molecule type")
    p_fluo.add_argument("-d", "--dye", required=True, help="Dye name (e.g. FAM, Cy3, Cy5, Alexa488)")

    # 9. gel
    p_gel = subparsers.add_parser("gel", help="Simulate gel electrophoresis migration against MW ladders")
    p_gel.add_argument("-s", "--sizes", nargs="+", type=float, required=True, help="Sample band sizes (bp or kDa)")
    p_gel.add_argument("-l", "--ladder", default="1kb_dna", choices=["1kb_dna", "100bp_dna", "low_range_ssdna", "protein_broad_range"], help="MW ladder type")

    # 10. ecoli
    p_ecoli = subparsers.add_parser("ecoli", help="E. coli growth time to induction OD, plasmid yields, and protein expression")
    p_ecoli.add_argument("--init-od", type=float, default=0.05, help="Initial OD600")
    p_ecoli.add_argument("--target-od", type=float, default=0.60, help="Target induction OD600")
    p_ecoli.add_argument("--temp", type=float, default=37.0, help="Culture temperature in °C")
    p_ecoli.add_argument("--media", default="LB", choices=["LB", "2xYT", "TB", "M9"], help="Media type")
    p_ecoli.add_argument("--plasmid", default="pUC", help="Plasmid origin/copy (pUC, pET, pBR322)")
    p_ecoli.add_argument("--vol-ml", type=float, default=1000.0, help="Culture volume in mL")

    # 11. excel-template
    p_xl = subparsers.add_parser("excel-template", help="Generate an interactive multi-tab Excel lab notebook")
    p_xl.add_argument("-o", "--output", default="biolabcalc_notebook.xlsx", help="Output .xlsx path")

    # 12. annotate-gel
    p_ann = subparsers.add_parser("annotate-gel", help="Annotate gel images, label lanes, add MW ladders, and callout target bands")
    p_ann.add_argument("-i", "--image", default=None, help="Input gel image path (PNG, JPG, TIFF). If omitted, renders a synthetic gel.")
    p_ann.add_argument("-l", "--lanes", default="Ladder,Ctrl,Sample1,Sample2", help="Comma-separated lane names")
    p_ann.add_argument("--ladder", default="1kb_dna", choices=["1kb_dna", "100bp_dna", "low_range_ssdna", "protein_broad_range"], help="Ladder type")
    p_ann.add_argument("--ladder-lane", type=int, default=1, help="Ladder lane number (1-based, default 1)")
    p_ann.add_argument("--ladder-side", default="left", choices=["left", "right"], help="Side for MW tick labels")
    p_ann.add_argument("-b", "--bands", default=None, help="Bands to annotate in format 'lane:size:label' separated by commas (e.g. '3:850:Amplicon,4:850:Amplicon')")
    p_ann.add_argument("-t", "--title", default="Agarose Gel Electrophoresis Analysis", help="Figure title")
    p_ann.add_argument("--info", default="1.0% Agarose in 1X TAE | 100V, 45 min", help="Gel conditions subtitle")
    p_ann.add_argument("-o", "--output", default="annotated_gel.png", help="Output annotated image path (.png)")
    p_ann.add_argument("--excel", default=None, help="Optional Excel file to embed annotated image and lane table")
    p_ann.add_argument("--invert", action="store_true", help="Invert colors (dark bands on light background)")

    # 13. interactive-gel
    p_int = subparsers.add_parser("interactive-gel", help="Launch the interactive drag-and-drop gel annotator and molecular weight calculator in browser")
    p_int.add_argument("-p", "--port", type=int, default=8501, help="Local port (default: 8501)")
    p_int.add_argument("--save-html", default=None, help="Save standalone HTML5 application file without running server")
    p_int.add_argument("--no-browser", action="store_true", help="Do not open web browser automatically")

    # 14. batch-excel
    p_batch = subparsers.add_parser("batch-excel", help="Batch process sequence tables from an Excel spreadsheet")
    p_batch.add_argument("-i", "--input", required=True, help="Input Excel file (.xlsx) with sequences")
    p_batch.add_argument("-o", "--output", default="batch_results.xlsx", help="Output annotated Excel file (.xlsx)")

    # 15. digest
    p_dig = subparsers.add_parser("digest", help="Plan restriction enzyme digestion with buffer compatibility and pipetting volumes")
    p_dig.add_argument("--dna-ug", type=float, required=True, help="DNA mass in µg")
    p_dig.add_argument("-v", "--volume", type=float, default=50.0, help="Total reaction volume in µL (default: 50)")
    p_dig.add_argument("-e1", "--enzyme-1", default="EcoRI", help="First restriction enzyme (e.g. EcoRI, BamHI, HindIII)")
    p_dig.add_argument("-e2", "--enzyme-2", default=None, help="Second restriction enzyme for double digest (optional)")
    p_dig.add_argument("--dna-conc", type=float, default=None, help="DNA stock concentration in ng/µL")

    # 16. ligate
    p_lig = subparsers.add_parser("ligate", help="Calculate DNA ligation insert mass and reaction setup")
    p_lig.add_argument("--vec-bp", type=int, required=True, help="Vector length in bp")
    p_lig.add_argument("--ins-bp", type=int, required=True, help="Insert length in bp")
    p_lig.add_argument("--vec-ng", type=float, default=50.0, help="Vector mass in ng (default: 50)")
    p_lig.add_argument("-r", "--ratio", type=float, default=3.0, help="Molar ratio insert:vector (default: 3.0)")
    p_lig.add_argument("-v", "--volume", type=float, default=20.0, help="Reaction volume in µL")

    # 17. gibson
    p_gib = subparsers.add_parser("gibson", help="Calculate Gibson Assembly / NEBuilder HiFi reaction setup")
    p_gib.add_argument("--vec-bp", type=int, required=True, help="Vector length in bp")
    p_gib.add_argument("--ins-bp", nargs="+", type=int, required=True, help="Insert lengths in bp (e.g. 800 1200)")
    p_gib.add_argument("--vec-ng", type=float, default=100.0, help="Vector mass in ng (default: 100)")
    p_gib.add_argument("-r", "--ratio", type=float, default=2.0, help="Molar ratio insert:vector (default: 2.0)")

    # 18. buffer
    p_buf = subparsers.add_parser("buffer", help="Calculate chemical masses and recipe for laboratory buffers")
    p_buf.add_argument("-b", "--buffer", default=None, help="Buffer name (e.g. 50X_TAE, 10X_PBS, 10X_HEPES_IVT, or custom buffer)")
    p_buf.add_argument("-v", "--volume-ml", type=float, default=1000.0, help="Target volume in mL (default: 1000)")
    p_buf.add_argument("--custom", action="store_true", help="Launch interactive custom buffer builder")
    p_buf.add_argument("--list", action="store_true", help="List all standard and custom buffers in the catalog")
    p_buf.add_argument("--list-custom", action="store_true", help="List custom buffers saved on disk")

    # 19. precipitate
    p_prec = subparsers.add_parser("precipitate", help="Calculate ethanol/isopropanol nucleic acid precipitation recipe")
    p_prec.add_argument("-v", "--volume-ul", type=float, required=True, help="Sample volume in µL")
    p_prec.add_argument("-t", "--type", default="dna", choices=["dna", "rna"], help="Nucleic acid type")
    p_prec.add_argument("-a", "--alcohol", default="ethanol", choices=["ethanol", "isopropanol"], help="Alcohol type")
    p_prec.add_argument("-s", "--salt", default="naoac", choices=["naoac", "nh4oac", "licl", "nacl"], help="Salt type")

    # 20. ntp-ph
    p_ntp = subparsers.add_parser("ntp-ph", help="Calculate NaOH requirement and protocol for NTP pH adjustment")
    p_ntp.add_argument("-v", "--initial-vol", type=float, default=4.0, help="Initial stock volume in mL (default: 4.0)")
    p_ntp.add_argument("-c", "--initial-conc", type=float, default=100.0, help="Initial stock concentration in mM (default: 100.0)")
    p_ntp.add_argument("-V", "--target-vol", type=float, default=16.0, help="Target final volume in mL (default: 16.0)")
    p_ntp.add_argument("-C", "--target-conc", type=float, default=25.0, help="Target final concentration in mM (default: 25.0)")
    p_ntp.add_argument("-p", "--target-ph", type=float, default=7.5, help="Target pH (default: 7.5)")
    p_ntp.add_argument("-f", "--form", default="disodium_salt", choices=["disodium_salt", "pre_neutralized", "free_acid"], help="Starting stock chemical form")
    p_ntp.add_argument("-s", "--species", default="equimolar_mix", choices=["equimolar_mix", "ATP", "CTP", "GTP", "UTP"], help="NTP species")
    p_ntp.add_argument("-b", "--base-molarity", type=float, default=5.0, help="Molarity of NaOH stock in M (default: 5.0)")

    # 21. protocol
    p_proto = subparsers.add_parser("protocol", help="View and export standardized wet-lab protocols")
    p_proto.add_argument("-n", "--name", default=None, help="Protocol ID or name (e.g. t7_ivt_transcription, ntp_neutralization, ecoli_transformation)")
    p_proto.add_argument("-l", "--list", action="store_true", help="List all available protocols")
    p_proto.add_argument("-c", "--category", default=None, help="Filter listed protocols by category (e.g. RNA, Cloning, Electrophoresis)")
    p_proto.add_argument("-e", "--export", default=None, help="Export consolidated protocols markdown to specified file path")
    # 24. golden-gate
    p_gg = subparsers.add_parser("golden-gate", help="Calculate Golden Gate Assembly stoichiometry, pipetting, and cycling")
    p_gg.add_argument("--vec-bp", type=int, required=True, help="Destination vector length in bp")
    p_gg.add_argument("--ins-bp", type=int, nargs="+", required=True, help="Insert lengths in bp (e.g. 1000 500)")
    p_gg.add_argument("--fmol", type=float, default=20.0, help="Target vector fmol (default: 20.0)")
    p_gg.add_argument("--enzyme", default="BsaI-HFv2", help="Type IIS enzyme (e.g. BsaI-HFv2, BsmBI-v2, BbsI-HF)")
    p_gg.add_argument("--ratio", type=float, default=2.0, help="Insert:vector molar ratio (default: 2.0)")

    # 25. purity
    p_pur = subparsers.add_parser("purity", help="Assess nucleic acid NanoDrop A260/A280/A230 purity and contaminants")
    p_pur.add_argument("--a260", type=float, required=True, help="Absorbance at 260 nm")
    p_pur.add_argument("--a280", type=float, required=True, help="Absorbance at 280 nm")
    p_pur.add_argument("--a230", type=float, required=True, help="Absorbance at 230 nm")
    p_pur.add_argument("-t", "--type", choices=["rna", "dna"], default="rna", help="Nucleic acid type")

    # 26. pci
    p_pci = subparsers.add_parser("pci", help="Calculate Phenol:Chloroform:Isoamyl alcohol extraction volumes and protocol")
    p_pci.add_argument("-v", "--volume", type=float, required=True, help="Aqueous sample volume in µL")
    p_pci.add_argument("-t", "--type", choices=["rna", "dna"], default="rna", help="Target nucleic acid")
    p_pci.add_argument("--ph", type=float, default=None, help="Phenol pH (default: 4.5 for RNA, 8.0 for DNA)")
    # 27. ivt-time
    p_ivtt = subparsers.add_parser("ivt-time", help="Calculate optimal IVT incubation time and kinetic profile")
    p_ivtt.add_argument("-l", "--length", type=int, required=True, help="Transcript length in nucleotides")
    p_ivtt.add_argument("--temp", type=float, default=37.0, help="Incubation temperature in °C (default: 37.0)")
    p_ivtt.add_argument("--no-ipp", action="store_true", help="Omit inorganic pyrophosphatase (IPP)")

    # 28. hepes
    p_hep = subparsers.add_parser("hepes", help="Calculate 10X/5X HEPES-KOH IVT buffer recipe with temperature compensation")
    p_hep.add_argument("-v", "--volume", default="50 mL", help="Buffer stock volume (default: 50 mL)")
    p_hep.add_argument("--stock", type=int, default=10, help="Stock multiplier (e.g. 10 for 10X, default: 10)")
    p_hep.add_argument("--ph", type=float, default=7.50, help="Target reaction pH at 37°C (default: 7.50)")

    # 29. western
    p_wb = subparsers.add_parser("western", help="Plan Western blot experiment: SDS-PAGE, transfer, loading, and antibodies")
    p_wb.add_argument("-n", "--name", default="Target Protein", help="Target protein name (e.g. GluK2, Actin, p-ERK)")
    p_wb.add_argument("-m", "--mw", type=float, default=None, help="Target molecular weight in kDa (e.g. 100.0)")
    p_wb.add_argument("-c", "--conc", type=float, default=2.5, help="Lysate total protein concentration in mg/mL (default: 2.5)")
    p_wb.add_argument("-l", "--load-ug", type=float, default=20.0, help="Target protein mass per lane in µg (default: 20.0)")
    p_wb.add_argument("--phospho", action="store_true", help="Target is phosphorylated epitope (enforces 5% BSA blocking; bans milk)")
    p_wb.add_argument("--membrane-protein", action="store_true", help="Target is transmembrane receptor (enforces 70°C denaturation; bans 95°C boiling)")
    p_wb.add_argument("--transfer", choices=["wet_tank", "semi_dry", "fast_semi_dry"], default="wet_tank", help="Electrotransfer system (default: wet_tank)")
    p_wb.add_argument("--membrane", choices=["pvdf", "nitrocellulose"], default="pvdf", help="Membrane type (default: pvdf)")
    p_wb.add_argument("--troubleshoot", default=None, help="Diagnose artifact: 'no_signal', 'high_background', 'ghost_bands', 'membrane_protein_aggregates', 'patchy_transfer'")

    # 30. report
    p_rep = subparsers.add_parser("report", help="Record experimental measurements and export formatted lab reports")
    p_rep.add_argument("-t", "--title", default="Laboratory Experiment Report", help="Report or experiment title")
    p_rep.add_argument("-r", "--researcher", default="Researcher", help="Researcher name")
    p_rep.add_argument("-p", "--project", default="General", help="Project or notebook ID")
    p_rep.add_argument("--obj", default="", help="Experimental objective")
    p_rep.add_argument("-s", "--sample", default=None, help="Sample ID (e.g. WT-1, Sample-A)")
    p_rep.add_argument("--param", default=None, help="Parameter or assay (e.g. Yield, A260, Conc)")
    p_rep.add_argument("-v", "--value", type=float, default=None, help="Measured numeric value")
    p_rep.add_argument("-u", "--unit", default="", help="Measurement unit (e.g. ug, ng/uL, AU, bp)")
    p_rep.add_argument("--target", type=float, default=None, help="Target or expected value")
    p_rep.add_argument("--tolerance", type=float, default=None, help="Acceptable QC deviation tolerance %")
    p_rep.add_argument("--notes", default="", help="Bench observations or notes")
    p_rep.add_argument("--conclusion", default=None, help="Add conclusion or key takeaway")
    p_rep.add_argument("-o", "--output", default=None, help="Export report to file (.md, .xlsx, .csv, .json)")
    p_rep.add_argument("--interactive", action="store_true", help="Launch interactive terminal prompt to record measurements")



    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "dilute":
        res = dilute(c1=args.c1, v1=args.v1, c2=args.c2, v2=args.v2)
        print("=" * 65)
        print("DILUTION CALCULATOR (C1 * V1 = C2 * V2)")
        print("=" * 65)
        print(f"Stock Concentration (C1):    {res['c1']} mM")
        print(f"Stock Volume to Add (V1):     {res['v1'] / 1000.0:.3f} mL ({res['v1']:,.1f} µL)")
        print(f"Target Concentration (C2):   {res['c2']} mM")
        print(f"Final Total Volume (V2):      {res['v2'] / 1000.0:.3f} mL ({res['v2']:,.1f} µL)")
        print(f"Diluent Volume Needed:        {res['diluent_needed'] / 1000.0:.3f} mL ({res['diluent_needed']:,.1f} µL)")
        print("=" * 65)
        return

    elif args.command in ("wizard", "interactive"):
        run_wizard()
        return

    if args.command == "mw":
        if args.type == "dna":
            res = calculate_dna_mw(args.sequence, double_stranded=args.ds, end_5=args.end_5)
        elif args.type == "rna":
            res = calculate_rna_mw(args.sequence, end_5=args.end_5, end_3=args.end_3, backbone=args.backbone)
        else:
            res = calculate_protein_mw(args.sequence)
        print("=" * 60)
        print(f"Sequence Type:       {res.seq_type}")
        print(f"Length:              {res.length}")
        print(f"Average MW:          {res.average_mw:,.2f} Da")
        print(f"Monoisotopic MW:     {res.monoisotopic_mw:,.4f} Da")
        if args.type == "rna":
            print(f"Terminal Chemistry:  5'-{res.end_5} | 3'-{res.end_3}")
            print(f"Backbone Linkage:    {res.backbone}")
        print(f"GC Content:          {res.gc_content:.1f}%")
        print("=" * 60)

    elif args.command == "nanodrop":
        res = prepare_standard_solution(
            target_molarity_um=args.molarity_um,
            target_volume_ul=args.volume_ul,
            sequence=args.sequence,
            seq_type=args.type,
            rna_length_nt=args.length,
            stock_conc_ng_ul=args.stock_ng_ul,
            end_5=args.end_5,
        )
        print("=" * 70)
        print(f"STANDARDIZED SOLUTION PREPARATION & NANODROP PREDICTIONS")
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
        print("-" * 70)
        print("WHAT YOU SHOULD GET AT THE NANODROP:")
        print(f"  Expected A260 (10 mm path):     {res.expected_nanodrop_a260_sequence_specific:.3f} AU (Sequence-specific Beer-Lambert)")
        print(f"  Expected A260 (1 mm pedestal): {res.expected_nanodrop_a260_1mm:.4f} AU (Raw pedestal reading)")
        print(f"  Reading in NanoDrop RNA-40 Mode:{res.expected_nanodrop_display_ng_ul_generic_mode:.2f} ng/µL (A260 * 40)")
        print(f"  Reading in Custom ε260 Mode:   {res.actual_concentration_ng_ul:.2f} ng/µL (True concentration)")
        print(f"  Expected A260/A280 Ratio:      ~{res.expected_a260_a280_ratio:.2f} (Pure RNA)")
        print("-" * 70)
        print(f"Protocol: {res.preparation_instructions}")
        print("=" * 70)

    elif args.command == "fluo":
        if args.type == "dna":
            base_res = calculate_dna_mw(args.sequence)
        elif args.type == "rna":
            base_res = calculate_rna_mw(args.sequence)
        else:
            base_res = calculate_protein_mw(args.sequence)
        mod_res = apply_fluorophore_modification(base_res, [args.dye])
        fl = mod_res.primary_fluorophore
        print("=" * 60)
        print(f"FLUOROPHORE MODIFICATION: {fl.name}")
        print("=" * 60)
        print(f"Unmodified MW:       {mod_res.original_mw:,.2f} Da")
        print(f"Modified MW:         {mod_res.total_modified_mw:,.2f} Da (+{mod_res.total_added_mw} Da)")
        print(f"Excitation / Emission:{fl.excitation_max_nm} nm / {fl.emission_max_nm} nm ({fl.color_description})")
        print(f"Extinction Coeff:    {fl.extinction_coeff_m_cm:,} M^-1 cm^-1")
        print(f"Correction Factors:  CF260 = {fl.cf260:.2f} | CF280 = {fl.cf280:.2f}")
        print("=" * 60)

    elif args.command == "gel":
        sim = simulate_gel(sample_sizes=args.sizes, ladder_key=args.ladder)
        print(sim.ascii_visualization)

    elif args.command == "ivt":
        vol = UnitParser.parse_volume(args.volume, "ul")
        yld = UnitParser.parse_mass(args.yield_ug, "ug")
        res = calculate_ivt_yield(
            rna_seq=args.sequence,
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
            print("-" * 65)
            print("Warnings & Recommendations:")
            for w in res.warnings:
                print(f"  [!] {w}")
        for rec in res.initiation_recommendations:
            print(f"  [*] {rec}")
        print("=" * 65)

    elif args.command == "pcr":
        vol = UnitParser.parse_volume(getattr(args, "volume", 50.0), "ul")
        tmpl = UnitParser.parse_mass(args.template_ng, "ng")
        res = calculate_pcr_kinetics(
            amplicon_len_bp=args.length,
            template_ng=tmpl,
            cycles=args.cycles,
            reaction_volume_ul=vol,
        )
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
        print("=" * 65)

    elif args.command == "primers":
        pairs = design_primers(
            args.sequence,
            target_tm=args.target_tm,
        )
        print("=" * 70)
        print(f"THERMODYNAMIC PRIMER DESIGN RESULTS ({len(pairs)} pairs found)")
        print("=" * 70)
        for idx, p in enumerate(pairs, 1):
            print(f"Pair #{idx} (Score: {p.pair_quality_score}, Amplicon: {p.amplicon_length_bp} bp, ΔTm: {p.tm_difference:.1f}°C):")
            print(f"  Forward: {p.forward_primer.sequence} (Tm: {p.forward_primer.tm_celsius:.1f}°C, GC: {p.forward_primer.gc_percent:.1f}%, Clamp: {p.forward_primer.has_gc_clamp})")
            print(f"  Reverse: {p.reverse_primer.sequence} (Tm: {p.reverse_primer.tm_celsius:.1f}°C, GC: {p.reverse_primer.gc_percent:.1f}%, Clamp: {p.reverse_primer.has_gc_clamp})")
        print("=" * 70)

    elif args.command == "protein":
        res = quantify_protein_a280(
            seq=args.sequence,
            a280_absorbance=args.a280,
            volume_ml=args.volume_ml,
        )
        print("=" * 65)
        print("PROTEIN QUANTIFICATION (A280 BEER-LAMBERT)")
        print("=" * 65)
        print(f"Sequence Length:            {len(args.sequence)} aa")
        print(f"Molecular Weight:           {res.molecular_weight:,.2f} Da")
        print(f"Molar Extinction ε280:      {res.extinction_coeff_m_cm:,} M^-1 cm^-1")
        print(f"Concentration:              {res.concentration_mg_ml:.4f} mg/mL ({res.concentration_ug_ml:.2f} µg/mL)")
        print(f"Molarity:                   {res.molarity_um:.2f} µM")
        print(f"Total Yield:                {res.total_yield_mg:.4f} mg ({res.total_yield_ug:,.1f} µg)")
        print("=" * 65)

    elif args.command == "pcr-opt":
        res = optimize_pcr_protocol(
            primer_fwd_tm=args.fwd_tm,
            primer_rev_tm=args.rev_tm,
            amplicon_len_bp=args.length,
            polymerase=args.polymerase,
            gc_percent=args.gc,
        )
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
        print("=" * 60)

    elif args.command == "ecoli":
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
        print("=" * 60)
        print("E. COLI GROWTH & PLASMID OPTIMIZATION")
        print("=" * 60)
        print(f"Doubling Time:              {g_res.doubling_time_min:.1f} min ({g_res.media} at {g_res.temperature_celsius}°C)")
        print(f"Time from OD {g_res.initial_od600} to {g_res.target_od600}:  {g_res.formatted_time} ({g_res.num_doublings} doublings)")
        print(f"Cell Density at Target OD:  {g_res.target_cells_per_ml:,.0f} cells/mL")
        print("-" * 60)
        print(f"Estimated Plasmid Yield ({p_res.plasmid_type}, {p_res.culture_volume_ml:.0f} mL culture):")
        print(f"  Theoretical Yield:        {p_res.theoretical_yield_ug:,.1f} µg")
        print(f"  Typical Kit Recovery:     {p_res.typical_miniprep_yield_ug:,.1f} µg")
        print("=" * 60)

    elif args.command == "annotate-gel":
        lane_list = [l.strip() for l in args.lanes.split(",") if l.strip()]
        if args.image and os.path.exists(args.image):
            ann = GelAnnotator.from_image(args.image, title=args.title, gel_info=args.info, invert_colors=args.invert)
            ann.set_lanes(lane_list)
        else:
            ann = GelAnnotator.synthetic(num_lanes=len(lane_list), title=args.title, gel_info=args.info, invert_colors=args.invert or True)
            ann.set_lanes(lane_list)

        ann.add_ladder(lane_index=args.ladder_lane, ladder_type=args.ladder, side=args.ladder_side)

        if args.bands:
            # Parse 'lane:size:label'
            band_items = args.bands.split(",")
            for item in band_items:
                parts = item.strip().split(":")
                if len(parts) >= 2:
                    l_idx = int(parts[0])
                    s_val = float(parts[1])
                    lbl = parts[2] if len(parts) > 2 else f"{s_val}"
                    ann.add_band(lane_index=l_idx, size_bp_or_kda=s_val, label=lbl)

        img_out = ann.render(args.output, dpi=250)
        print(f"Annotated gel figure saved to: {img_out}")

        if args.excel:
            xl_out = ann.embed_in_excel(args.excel, sheet_name="Annotated_Gel")
            print(f"Gel figure and lane summary table embedded into Excel at: {xl_out}")
    elif args.command == "golden-gate":
        res = calculate_golden_gate_assembly(
            vector_length_bp=args.vec_bp,
            insert_lengths_bp=args.ins_bp,
            target_vector_fmol=args.fmol,
            type_iis_enzyme=args.enzyme,
            insert_to_vector_ratio=args.ratio,
        )
        print("=" * 65)
        print(f"GOLDEN GATE ASSEMBLY SETUP ({res.enzyme})")
        print("=" * 65)
        print(f"Vector ({res.vector_length_bp} bp):         {res.vector_mass_ng:.1f} ng ({res.vector_fmol:.1f} fmol)")
        for idx, (ins_len, ins_m, ins_f) in enumerate(zip(res.insert_lengths_bp, res.insert_masses_ng, res.insert_fmols), 1):
            print(f"Insert #{idx} ({ins_len} bp):         {ins_m:.1f} ng ({ins_f:.1f} fmol)")
        print(f"Insert:Vector Molar Ratio:  {res.insert_to_vector_ratio:.1f} : 1")
        print(f"Total DNA Mass:             {res.total_dna_mass_ng:.1f} ng")
        print("-" * 65)
        print("1-Pot Pipetting Recipe:")
        for comp, vol in res.reagent_volumes.items():
            print(f"  {comp:35s}: {vol:5.2f} µL")
        print("-" * 65)
        print("Thermocycling Schedule:")
        for step in res.thermocycling_protocol:
            print(f"  {step}")
        print("=" * 65)

    elif args.command == "purity":
        res = assess_nanodrop_purity(
            a260=args.a260,
            a280=args.a280,
            a230=args.a230,
            sample_type=args.type,
        )
        print("=" * 65)
        print(f"NANODROP NUCLEIC ACID PURITY ASSESSMENT ({res.sample_type})")
        print("=" * 65)
        print(f"Absorbance Readings:        A260 = {res.a260:.3f} | A280 = {res.a280:.3f} | A230 = {res.a230:.3f}")
        print(f"A260 / A280 Ratio:          {res.a260_a280_ratio:.2f} (Ideal: ~2.0 for RNA, ~1.8 for DNA)")
        print(f"A260 / A230 Ratio:          {res.a260_a230_ratio:.2f} (Ideal: 2.0 – 2.2)")
        print(f"Purity Status:              {res.purity_status.upper()}")
        print(f"Estimated True Conc.:       {res.corrected_concentration_ng_ul:.1f} ng/µL")
        print("-" * 65)
        print("Diagnostic Observations:")
        for diag in res.diagnostic_feedback:
            print(f"  * {diag}")
        print("=" * 65)

    elif args.command == "pci":
        res = calculate_phenol_chloroform_extraction(
            sample_volume_ul=args.volume,
            nucleic_acid=args.type,
            phenol_ph=args.ph,
        )
        print("=" * 65)
        print("PHENOL:CHLOROFORM EXTRACTION PROTOCOL")
        print("=" * 65)
        print(f"Reagent Grade:              {res.phenol_type}")
        print(f"Target Nucleic Acid:        {res.target_nucleic_acid}")
        print(f"Aqueous Phase Behavior:     {res.aqueous_phase_layer}")
        print("-" * 65)
        print("Pipetting Recipe:")
        for comp, vol in res.reagent_volumes.items():
            print(f"  {comp:35s}: {vol:5.2f} µL")
        print("-" * 65)
        print("Protocol Steps:")
        for s in res.protocol_steps:
            print(f"  {s}")
        print("-" * 65)
        print("Safety Hazards:")
        for n in res.safety_notes:
            print(f"  [!] {n}")
        print("=" * 65)
    elif args.command == "ivt-time":
        res = optimize_transcription_time(
            transcript_length_nt=args.length,
            temperature_celsius=args.temp,
            use_pyrophosphatase=not args.no_ipp,
        )
        print("=" * 65)
        print(f"IVT TRANSCRIPTION TIME & KINETIC OPTIMIZATION ({args.length} nt)")
        print("=" * 65)
        print(f"Incubation Temperature:     {res.temperature_celsius:.1f} °C ({res.temperature_mode})")
        print(f"Recommended Reaction Time:  {res.recommended_time_hours:.2f} hours (Window: {res.recommended_time_range_hours[0]:.1f}–{res.recommended_time_range_hours[1]:.1f} h)")
        print(f"Plateau Time:               ~{res.plateau_time_hours:.2f} hours")
        print(f"3' Heterogeneity Hazard:    {res.risk_of_3prime_heterogeneity}")
        print(f"Degradation Hazard:         {res.risk_of_degradation}")
        print("-" * 65)
        print("Predicted Synthesis Trajectory:")
        for pt in res.time_course_predictions:
            print(f"  {pt['time_hours']:4.2f} h : {pt['estimated_percent_max_yield']:5.1f}% yield -> {pt['reaction_phase']}")
        print("-" * 65)
        print("Benchtop Guidelines:")
        for g in res.guidelines:
            print(f"  * {g}")
        print("=" * 65)

    elif args.command == "hepes":
        vol_ml = UnitParser.parse_volume(args.volume, "ml")
        res = calculate_hepes_ivt_buffer(
            target_volume_ml=vol_ml,
            stock_multiplier=args.stock,
            target_ph_37c=args.ph,
        )
        print("=" * 70)
        print(f"{res.stock_multiplier}X HEPES-KOH IVT REACTION BUFFER RECIPE ({res.target_volume_ml:.1f} mL)")
        print("=" * 70)
        print(f"Target Reaction pH (37°C):   {res.target_ph_37c:.2f}")
        print(f"Preparation pH (25°C):       {res.preparation_ph_25c:.2f} (compensates for ΔpKa/ΔT = -0.014/°C)")
        print("-" * 70)
        print("Component Formula & Concentrations:")
        for comp in res.components:
            print(f"  {comp.name:25s}: {comp.amount:6.3f} {comp.unit:4s} ({comp.molar_concentration})")
        print("-" * 70)
        print(f"Buffer Advantage: {res.buffering_capacity_comparison}")
        print("-" * 70)
        print("Preparation Steps:")
        for s in res.preparation_steps:
            print(f"  {s}")
        print("=" * 70)
    elif args.command == "western":
        if args.troubleshoot:
            t_res = troubleshoot_western_blot(args.troubleshoot)
            print("=" * 70)
            print(f"WESTERN BLOT DIAGNOSTIC & TROUBLESHOOTING: {t_res.symptom}")
            print("=" * 70)
            print("Likely Root Causes:")
            for c in t_res.likely_causes:
                print(f"  * {c}")
            print("-" * 70)
            print("Corrective Actions:")
            for a in t_res.corrective_actions:
                print(f"  [+] {a}")
            print("-" * 70)
            print(f"Preventative Guideline: {t_res.preventative_protocol}")
            print("=" * 70)
            return

        if args.mw is None:
            print("Error: Target molecular weight in kDa (--mw / -m) is required to plan a Western blot.")
            sys.exit(1)

        plan = plan_western_blot(
            target_protein_name=args.name,
            target_mw_kda=args.mw,
            lysate_conc_mg_ml=args.conc,
            target_protein_ug_per_lane=args.load_ug,
            is_phospho_target=args.phospho,
            is_membrane_protein=args.membrane_protein,
            transfer_system=args.transfer,
            membrane_type=args.membrane,
        )

        print("=" * 70)
        print(f"WESTERN BLOT EXPERIMENTAL PLAN: {plan.target_protein_name} ({plan.target_mw_kda:.1f} kDa)")
        print("=" * 70)
        print("1. GEL RESOLUTION & RUNNING CONDITIONS:")
        print(f"   Recommended Matrix:    {plan.recommended_gel_percentage}")
        print(f"   Running Parameters:    {plan.running_conditions}")
        print("-" * 70)
        print(f"2. SAMPLE PREPARATION & LOADING (Target: {plan.sample_prep.target_protein_ug_per_lane:.1f} µg / lane):")
        print(f"   Lysate Stock Conc:     {plan.sample_prep.lysate_conc_mg_ml:.2f} mg/mL")
        print(f"   Per-Lane Volumes:      {plan.sample_prep.lysate_volume_per_lane_ul:.2f} µL Lysate + {plan.sample_prep.sample_buffer_volume_per_lane_ul:.2f} µL 4X Sample Buffer")
        print(f"   Total Lane Volume:     {plan.sample_prep.total_volume_per_lane_ul:.1f} µL")
        print(f"   Denaturation:          {plan.sample_prep.denaturation_temperature_celsius}°C for {plan.sample_prep.denaturation_time_minutes} minutes")
        for n in plan.sample_prep.notes:
            print(f"   * {n}")
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
        print("-" * 70)
        print("4. IMMUNODETECTION & BLOCKING:")
        print(f"   Blocking Solution:     {plan.immunodetection.blocking_agent}")
        print(f"   Primary Antibody:      {plan.immunodetection.primary_antibody_dilution} ({plan.immunodetection.primary_antibody_volume_ul:.1f} µL in {plan.immunodetection.incubation_volume_ml:.1f} mL)")
        print(f"   Primary Incubation:    {plan.immunodetection.primary_incubation}")
        print(f"   Secondary Antibody:    {plan.immunodetection.secondary_antibody_dilution} ({plan.immunodetection.secondary_antibody_volume_ul:.1f} µL in {plan.immunodetection.incubation_volume_ml:.1f} mL)")
        print(f"   Wash Protocol:         {plan.immunodetection.wash_schedule}")
        for w in plan.immunodetection.compatibility_warnings:
            print(f"   [!] {w}")
        print("-" * 70)
        print("5. DETECTION & IMAGING:")
        print(f"   Substrate:             {plan.detection_substrate}")
        print(f"   Imaging Protocol:      {plan.imaging_guidelines}")
        print("=" * 70)

    elif args.command == "report":
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
            print(f"[✓] Lab report successfully exported to: {args.output}")

    elif args.command == "interactive-gel":
        if args.save_html:
            out_file = save_interactive_app(args.save_html)
            print(f"Interactive drag-and-drop gel annotator saved to: {out_file}")
            print(f"Open {out_file} in any web browser to use.")
        else:
            print(f"Starting BioLabCalc Interactive Drag-and-Drop Gel Annotator on port {args.port}...")
            launch_interactive_annotator(port=args.port, open_browser=not args.no_browser, blocking=True)

    elif args.command == "batch-excel":
        out_f = batch_process_excel(args.input, args.output)
        print(f"Batch sequence analysis complete! Results saved to: {out_f}")

    elif args.command == "digest":
        res = plan_restriction_digest(
            dna_mass_ug=args.dna_ug,
            reaction_volume_ul=args.volume,
            enzyme_1=args.enzyme_1,
            enzyme_2=args.enzyme_2,
            dna_conc_ng_ul=args.dna_conc,
        )
        print("=" * 65)
        print("RESTRICTION DIGESTION SETUP")
        print("=" * 65)
        print(f"Enzyme 1:             {res.enzyme_1.name} ({res.enzyme_1.recognition_site}, {res.enzyme_1.cut_type})")
        if res.enzyme_2:
            print(f"Enzyme 2:             {res.enzyme_2.name} ({res.enzyme_2.recognition_site}, {res.enzyme_2.cut_type})")
        print(f"Recommended Buffer:   {res.recommended_buffer}")
        print(f"Incubation:           {res.incubation_temp_celsius}°C for {res.incubation_time_min} min")
        print(f"Heat Inactivation:    {res.heat_inactivation}")
        print("-" * 65)
        print("Pipetting Recipe:")
        for comp, vol in res.reagent_volumes.items():
            print(f"  {comp:32s}: {vol:5.2f} µL")
        print(f"  Total Reaction Volume:          : {res.reaction_volume_ul:5.2f} µL")
        if res.notes:
            print("Notes & Warnings:")
            for n in res.notes:
                print(f"  * {n}")
        print("=" * 65)

    elif args.command == "ligate":
        res = calculate_ligation(
            vector_length_bp=args.vec_bp,
            insert_length_bp=args.ins_bp,
            vector_mass_ng=args.vec_ng,
            molar_ratio=args.ratio,
            reaction_volume_ul=args.volume,
        )
        print("=" * 65)
        print("DNA LIGATION SETUP")
        print("=" * 65)
        print(f"Vector ({res.vector_length_bp} bp):         {res.vector_mass_ng} ng ({res.vector_pmol:.3f} pmol)")
        print(f"Insert ({res.insert_length_bp} bp):         {res.insert_mass_ng} ng ({res.insert_pmol:.3f} pmol)")
        print(f"Molar Ratio (Insert:Vector):{res.molar_ratio_insert_to_vector:.1f} : 1")
        print("-" * 65)
        print("Pipetting Recipe:")
        for comp, vol in res.reagent_volumes.items():
            print(f"  {comp:35s}: {vol:5.2f} µL")
        print(f"Protocol: {res.incubation_guidelines}")
        print("=" * 65)

    elif args.command == "gibson":
        res = calculate_gibson_assembly(
            vector_length_bp=args.vec_bp,
            insert_lengths_bp=args.ins_bp,
            vector_mass_ng=args.vec_ng,
            molar_ratio=args.ratio,
        )
        print("=" * 65)
        print("GIBSON ASSEMBLY / NEBUILDER SETUP")
        print("=" * 65)
        print(f"Vector ({res.vector_length_bp} bp):         {res.vector_mass_ng} ng")
        for idx, (ins_len, ins_m) in enumerate(zip(res.insert_lengths_bp, res.insert_masses_ng), 1):
            print(f"Insert #{idx} ({ins_len} bp):         {ins_m} ng")
        print(f"Total DNA Input:            {res.total_dna_pmol:.3f} pmol (Optimal: 0.02 - 0.2 pmol)")
        print("-" * 65)
        print("Pipetting Recipe:")
        for comp, vol in res.reagent_volumes.items():
            print(f"  {comp:35s}: {vol:5.2f} µL")
        print(f"Protocol: {res.incubation_protocol}")
        print("=" * 65)

    elif args.command == "buffer":
        if args.list or args.list_custom:
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
                print(f"[✓] Saved custom buffer '{b_name}' to disk storage!")

        elif args.buffer:
            res = calculate_buffer_recipe(args.buffer, args.volume_ml)
        else:
            print("Error: Specify a buffer name with -b / --buffer, or launch custom builder with --custom.")
            print("To list available buffers: biolabcalc buffer --list")
            return

        print("=" * 65)
        print(f"BUFFER RECIPE: {res.name}")
        print("=" * 65)
        print(f"Target Volume:        {res.target_volume_ml:,.0f} mL ({res.target_volume_ml / 1000.0:.2f} L)")
        print(f"Target pH:            {res.ph_specification}")
        print(f"Storage:              {res.storage_conditions}")
        if res.safety_notes:
            print(f"Safety:               {res.safety_notes}")
        print("-" * 65)
        print("Reagent Formulations:")
        for c in res.components:
            cas_str = f"({c.cas_or_mw})" if c.cas_or_mw else ""
            print(f"  {c.name:28s}: {c.amount:8.3f} {c.unit}  [{c.molar_concentration}] {cas_str}")
        print("-" * 65)
        print("Preparation Instructions:")
        for idx, s in enumerate(res.preparation_steps, 1):
            print(f"  {idx}. {s}")
        print("=" * 65)

    elif args.command == "ntp-ph":
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
        print("=" * 65)
        print("NTP SOLUTION PREPARATION & pH ADJUSTMENT")
        print("=" * 65)
        print(f"Target Solution:      {res.target_conc_mm:.1f} mM {res.ntp_species} (Total Volume: {res.target_volume_ml:.1f} mL)")
        print(f"Target pH:            {res.target_ph:.2f}")
        print(f"Starting Stock:       {res.initial_volume_ml:.1f} mL @ {res.initial_conc_mm:.1f} mM ({res.starting_form})")
        print(f"Total NTP Quantity:   {res.total_ntp_mmol * 1000.0:,.1f} µmol ({res.total_ntp_mmol:.3f} mmol)")
        print(f"OH- Equivalents:      {res.naoh_equivalents:.3f} eq / mol NTP")
        print(f"Total NaOH Required:  {res.naoh_mmol * 1000.0:,.1f} µmol ({res.naoh_mmol:.4f} mmol)")
        print("-" * 65)
        print("Calculated NaOH Volumes by Stock Concentration:")
        for stock_c, vol_ul in res.naoh_volume_ul.items():
            print(f"  {stock_c:5s} NaOH: {vol_ul:8.1f} µL ({vol_ul / 1000.0:.3f} mL)")
        print(f"Diluent Water (approx): {res.water_volume_ml:.3f} mL (bring to {res.target_volume_ml:.1f} mL mark)")
        print("-" * 65)
        if res.warnings:
            print("WARNINGS & SAFETY:")
            for w in res.warnings:
                print(f"  [!] {w}")
            print("-" * 65)
        print("LOGIC & ERROR CHECKS:")
        for lc in res.logic_checks:
            print(f"  [*] {lc}")
        print("-" * 65)
        print("BENCH PROTOCOL & PIPETTING INSTRUCTIONS:")
        for s in res.preparation_steps:
            print(f"  {s}")
        print("=" * 65)

    elif args.command == "protocol":
        if args.export:
            export_all_protocols_markdown(args.export)
            print(f"Exported {len(PROTOCOL_CATALOG)} protocols to '{args.export}' successfully.")
        elif args.list or not args.name:
            protos = list_protocols(args.category)
            print("=" * 85)
            print("BIOLABCALC STANDARD LABORATORY PROTOCOLS CATALOG")
            print("=" * 85)
            print(f"{'Protocol ID':30s} {'Category':25s} {'Est. Time':16s} Title")
            print("-" * 85)
            for p in protos:
                print(f"{p.protocol_id:30s} {p.category:25s} {p.estimated_time:16s} {p.title}")
            print("=" * 85)
            print("Run 'biolabcalc protocol -n <protocol_id>' to display complete bench protocol.")
        else:
            p = get_protocol(args.name)
            print(format_protocol_markdown(p))

    elif args.command == "precipitate":
        res = calculate_precipitation(
            sample_volume_ul=args.volume_ul,
            nucleic_acid=args.type,
            alcohol=args.alcohol,
            salt=args.salt,
        )
        print("=" * 65)
        print(f"NUCLEIC ACID PRECIPITATION PROTOCOL ({res.nucleic_acid_type})")
        print("=" * 65)
        print(f"Sample Volume:        {res.sample_volume_ul:.1f} µL")
        print(f"Salt Added:           {res.salt_type} ({res.salt_volume_ul:.1f} µL)")
        print(f"Alcohol Added:        {res.alcohol_type} ({res.alcohol_volume_ul:.1f} µL)")
        print(f"Carrier Added:        {res.carrier_added}")
        print("-" * 65)
        print("Procedure:")
        print(f"  1. Incubation:      {res.incubation_temp}")
        print(f"  2. Centrifuge:      Spin at {res.centrifugation_speed} for {res.centrifugation_time_min} min at 4°C.")
        print(f"  3. Supernatant:     Carefully aspirate supernatant without dislodging pellet.")
        print(f"  4. Wash:            Add {res.wash_volume_70pct_ethanol_ul:.0f} µL 70% ethanol, spin 5 min, remove supernatant.")
        print(f"  5. Dry:             {res.drying_instructions}")
        print(f"  6. Resuspend:       {res.resuspension_guidelines}")
        print("=" * 65)

    elif args.command == "excel-template":
        path = generate_lab_notebook_template(args.output)
        print(f"Interactive Excel notebook template generated at: {path}")

if __name__ == "__main__":
    main()
