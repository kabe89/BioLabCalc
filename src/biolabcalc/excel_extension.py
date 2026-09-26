"""Built-in Excel extension for BioLabCalc: generating formatted lab workbooks, live formulas, and batch exports."""

from __future__ import annotations
import os
from typing import Dict, List, Optional, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .molecular_weight import calculate_dna_mw, calculate_rna_mw, calculate_protein_mw
from .transcription import IVTResult, calculate_ivt_yield
from .pcr import PCRResult, calculate_pcr_kinetics, build_master_mix
from .protein import ProteinYieldResult, calculate_extinction_coefficient, quantify_protein_a280
from .primers import PrimerPair, PrimerAnalysis, design_primers

# Typography and Styling Theme
NAVY_HEADER = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
BLUE_SUBHEADER = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
ACCENT_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
INPUT_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")  # Light yellow for inputs
CALC_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")   # Light green for calculated

WHITE_BOLD_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=16, bold=True, color="1F4E79")
SECTION_FONT = Font(name="Calibri", size=12, bold=True, color="1F4E79")
BOLD_FONT = Font(name="Calibri", size=11, bold=True)
REGULAR_FONT = Font(name="Calibri", size=11)
NOTE_FONT = Font(name="Calibri", size=9, italic=True, color="595959")

THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)
HEADER_BORDER = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="medium", color="1F4E79"),
    bottom=Side(style="medium", color="1F4E79"),
)


def _autofit_columns(ws, min_width=12, padding=3):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or "")
            lines = str(val).splitlines()
            val_len = max([len(l) for l in lines], default=0)
            if cell.number_format and "%" in cell.number_format:
                val_len += 3
            if val_len > max_len:
                max_len = val_len
        ws.column_dimensions[col_letter].width = max(min_width, max_len + padding)


def generate_lab_notebook_template(output_path: str) -> str:
    """Create a comprehensive, publication-ready multi-sheet Excel lab notebook template with live formulas."""
    wb = openpyxl.Workbook()
    # Sheet 1: IVT Reaction & Stoichiometry
    ws_ivt = wb.active
    ws_ivt.title = "IVT_Stoichiometry"
    ws_ivt.views.sheetView[0].showGridLines = True

    ws_ivt.cell(row=1, column=1, value="In Vitro Transcription (IVT) Stoichiometry & Yield Calculator").font = TITLE_FONT
    ws_ivt.cell(row=2, column=1, value="Interactive reaction worksheet. Enter values in light-yellow cells; green cells compute automatically.").font = NOTE_FONT

    # Input Section
    ws_ivt.cell(row=4, column=1, value="1. Reaction Setup Parameters").font = SECTION_FONT
    headers_setup = ["Parameter", "Value", "Unit", "Description / Notes"]
    for col_idx, h in enumerate(headers_setup, 1):
        c = ws_ivt.cell(row=5, column=col_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    setup_rows = [
        ("Reaction Volume", 20.0, "µL", "Total IVT reaction volume"),
        ("Template DNA Mass", 1000.0, "ng", "Input linearized plasmid or PCR template"),
        ("Template DNA Length", 3500, "bp", "Total base pairs of template plasmid"),
        ("Transcript Length", 1200, "nt", "Length of target synthesized RNA"),
        ("Transcript GC Content", 52.0, "%", "Approximate or exact GC percentage"),
        ("Measured RNA Yield", 45.0, "µg", "Post-purification quantified yield"),
        ("Starting ATP Conc.", 5.0, "mM", "Nucleotide starting concentration"),
        ("Starting CTP Conc.", 5.0, "mM", "Nucleotide starting concentration"),
        ("Starting GTP Conc.", 5.0, "mM", "Nucleotide starting concentration"),
        ("Starting UTP Conc.", 5.0, "mM", "Nucleotide starting concentration"),
    ]

    for idx, (param, val, unit, desc) in enumerate(setup_rows, 6):
        c1 = ws_ivt.cell(row=idx, column=1, value=param)
        c2 = ws_ivt.cell(row=idx, column=2, value=val)
        c3 = ws_ivt.cell(row=idx, column=3, value=unit)
        c4 = ws_ivt.cell(row=idx, column=4, value=desc)
        c1.font = BOLD_FONT
        c2.font = REGULAR_FONT
        c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4):
            cell.border = THIN_BORDER

    # Results Section with Formulas
    ws_ivt.cell(row=17, column=1, value="2. Stoichiometry & Yield Metrics (Calculated)").font = SECTION_FONT
    headers_results = ["Metric", "Excel Formula / Value", "Unit", "Significance"]
    for col_idx, h in enumerate(headers_results, 1):
        c = ws_ivt.cell(row=18, column=col_idx, value=h)
        c.fill = BLUE_SUBHEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    results_rows = [
        ("RNA Molecular Weight (approx)", "=B9*321.4+177.98", "g/mol", "Triphosphorylated 5' IVT transcript"),
        ("RNA Synthesized", "=B11", "µg", "Total mass synthesized"),
        ("RNA Amount (pmol)", "=(B20*1000000)/B19", "pmol", "Molar yield of RNA transcripts"),
        ("Total NTPs Initial per Base", "=B6*B12", "nmol", "Total moles available per NTP species"),
        ("Theoretical Max RNA Yield", "=(B22/(B9*0.25))*B19/1000", "µg", "Upper bound yield limited by NTP supply"),
        ("Incorporation Efficiency", "=(B20/B23)*100", "%", "Percent of limiting NTP converted to RNA"),
        ("Pyrophosphate (PPi) Released", "=(B21*(B9-1))/1000", "nmol", "Byproduct; can precipitate Mg2+"),
        ("Transcript Turnover Ratio", "=B21/((B7*1000)/(B8*617.96+36.04))", "RNA / DNA", "RNA copies produced per template"),
    ]

    for idx, (metric, formula, unit, sig) in enumerate(results_rows, 19):
        c1 = ws_ivt.cell(row=idx, column=1, value=metric)
        c2 = ws_ivt.cell(row=idx, column=2, value=formula)
        c3 = ws_ivt.cell(row=idx, column=3, value=unit)
        c4 = ws_ivt.cell(row=idx, column=4, value=sig)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = CALC_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4):
            cell.border = THIN_BORDER

    _autofit_columns(ws_ivt)

    # Sheet 2: PCR Optimization & Master Mix
    ws_pcr = wb.create_sheet(title="PCR_Optimization")
    ws_pcr.views.sheetView[0].showGridLines = True

    ws_pcr.cell(row=1, column=1, value="PCR Master Mix Setup & Amplification Stoichiometry").font = TITLE_FONT
    ws_pcr.cell(row=2, column=1, value="Dynamic master mix multiplier table and amplification efficiency calculator.").font = NOTE_FONT

    ws_pcr.cell(row=4, column=1, value="1. Master Mix Formulation").font = SECTION_FONT
    ws_pcr.cell(row=5, column=1, value="Number of Reactions:").font = BOLD_FONT
    c_n = ws_pcr.cell(row=5, column=2, value=12)
    c_n.font = BOLD_FONT
    c_n.fill = INPUT_FILL
    ws_pcr.cell(row=5, column=3, value="Excess Multiplier:").font = BOLD_FONT
    c_ex = ws_pcr.cell(row=5, column=4, value=1.10)
    c_ex.font = BOLD_FONT
    c_ex.fill = INPUT_FILL

    mm_headers = ["Reagent Component", "Stock Conc.", "Final Conc.", "1x Vol (µL)", "Master Mix Total (µL)"]
    for col_idx, h in enumerate(mm_headers, 1):
        c = ws_pcr.cell(row=7, column=col_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    mm_components = [
        ("Nuclease-Free Water", "-", "-", 34.5, "=D8**"),
        ("5X PCR Buffer", "5X", "1X", 10.0, "=D9**"),
        ("dNTP Mix", "10 mM each", "0.2 mM each", 1.0, "=D10**"),
        ("Forward Primer", "10 µM", "0.4 µM", 2.0, "=D11**"),
        ("Reverse Primer", "10 µM", "0.4 µM", 2.0, "=D12**"),
        ("DNA Polymerase", "2 U/µL", "1 U", 0.5, "=D13**"),
        ("Template DNA (add per tube)", "-", "-", 2.0, "Add 2.0 µL to each tube"),
    ]

    for idx, (reagent, stock, final_c, vol1, form_tot) in enumerate(mm_components, 8):
        c1 = ws_pcr.cell(row=idx, column=1, value=reagent)
        c2 = ws_pcr.cell(row=idx, column=2, value=stock)
        c3 = ws_pcr.cell(row=idx, column=3, value=final_c)
        c4 = ws_pcr.cell(row=idx, column=4, value=vol1)
        c5 = ws_pcr.cell(row=idx, column=5, value=form_tot)
        c1.font = BOLD_FONT
        c2.font = REGULAR_FONT
        c3.font = REGULAR_FONT
        c4.font = REGULAR_FONT
        c4.alignment = Alignment(horizontal="right")
        c5.font = BOLD_FONT
        if isinstance(form_tot, str) and form_tot.startswith("="): c5.fill = CALC_FILL
        c5.alignment = Alignment(horizontal="right")
        for cell in (c1, c2, c3, c4, c5):
            cell.border = THIN_BORDER

    ws_pcr.cell(row=15, column=1, value="Total Reaction Volume").font = BOLD_FONT
    ws_pcr.cell(row=15, column=4, value="=SUM(D8:D14)").font = BOLD_FONT
    ws_pcr.cell(row=15, column=5, value="=SUM(E8:E13)").font = BOLD_FONT

    # qPCR Efficiency Calculator
    ws_pcr.cell(row=17, column=1, value="2. qPCR Standard Curve Efficiency").font = SECTION_FONT
    ws_pcr.cell(row=18, column=1, value="Slope (Ct vs log10 qty)").font = BOLD_FONT
    c_slope = ws_pcr.cell(row=18, column=2, value=-3.322)
    c_slope.fill = INPUT_FILL
    c_slope.font = BOLD_FONT

    ws_pcr.cell(row=19, column=1, value="Amplification Factor (1+E)").font = BOLD_FONT
    c_amp = ws_pcr.cell(row=19, column=2, value="=10^(-1/B18)")
    c_amp.fill = CALC_FILL
    c_amp.font = BOLD_FONT

    ws_pcr.cell(row=20, column=1, value="Efficiency (%)").font = BOLD_FONT
    c_eff = ws_pcr.cell(row=20, column=2, value="=(B19-1)*100")
    c_eff.fill = CALC_FILL
    c_eff.font = BOLD_FONT

    _autofit_columns(ws_pcr)

    # Sheet 3: Protein Quantification
    ws_prot = wb.create_sheet(title="Protein_Quantification")
    ws_prot.views.sheetView[0].showGridLines = True

    ws_prot.cell(row=1, column=1, value="Protein Quantification & Standard Curve Calculator").font = TITLE_FONT
    ws_prot.cell(row=2, column=1, value="Direct A280 Beer-Lambert calculations and colorimetric assay (BCA/Bradford) interpolation.").font = NOTE_FONT

    # A280 Direct Section
    ws_prot.cell(row=4, column=1, value="1. Direct A280 Method (NanoDrop / UV Spectrophotometer)").font = SECTION_FONT
    a280_headers = ["Parameter", "Input Value", "Unit", "Notes"]
    for col_idx, h in enumerate(a280_headers, 1):
        c = ws_prot.cell(row=5, column=col_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    a280_rows = [
        ("Protein MW", 45000.0, "g/mol (Da)", "From sequence or database"),
        ("Extinction Coeff (ε280)", 43824, "M^-1 cm^-1", "Pace et al. 1995 formula"),
        ("Absorbance at 280 nm", 0.850, "AU", "Pathlength-corrected reading"),
        ("Path Length", 1.0, "cm", "1.0 for cuvette, 0.1 for 1mm NanoDrop"),
        ("Sample Volume", 2.5, "mL", "Total volume of purified stock"),
        ("Dilution Factor", 1.0, "X", "Sample dilution before reading"),
    ]

    for idx, (param, val, unit, note) in enumerate(a280_rows, 6):
        c1 = ws_prot.cell(row=idx, column=1, value=param)
        c2 = ws_prot.cell(row=idx, column=2, value=val)
        c3 = ws_prot.cell(row=idx, column=3, value=unit)
        c4 = ws_prot.cell(row=idx, column=4, value=note)
        c1.font = BOLD_FONT
        c2.font = REGULAR_FONT
        c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4):
            cell.border = THIN_BORDER

    # Calculated A280 yields
    ws_prot.cell(row=13, column=1, value="Concentration (mg/mL)").font = BOLD_FONT
    ws_prot.cell(row=13, column=2, value="=(B8*B11)/(B7*B9)*B6").font = BOLD_FONT
    ws_prot.cell(row=13, column=2).fill = CALC_FILL

    ws_prot.cell(row=14, column=1, value="Concentration (µg/mL)").font = BOLD_FONT
    ws_prot.cell(row=14, column=2, value="=B13*1000").font = BOLD_FONT
    ws_prot.cell(row=14, column=2).fill = CALC_FILL

    ws_prot.cell(row=15, column=1, value="Total Yield (mg)").font = BOLD_FONT
    ws_prot.cell(row=15, column=2, value="=B13*B10").font = BOLD_FONT
    ws_prot.cell(row=15, column=2).fill = CALC_FILL

    ws_prot.cell(row=16, column=1, value="Total Yield (ng)").font = BOLD_FONT
    ws_prot.cell(row=16, column=2, value="=B15*1000000").font = BOLD_FONT
    ws_prot.cell(row=16, column=2).fill = CALC_FILL

    for r in range(13, 17):
        for c in range(1, 5):
            ws_prot.cell(row=r, column=c).border = THIN_BORDER

    # Colorimetric BCA / Bradford Standard Curve Section
    ws_prot.cell(row=18, column=1, value="2. Colorimetric Standard Curve (BCA / Bradford)").font = SECTION_FONT
    sc_headers = ["Standard BSA (µg/mL)", "Absorbance (AU)", "Unknown Sample ID", "Sample Abs (AU)", "Calc. Conc. (µg/mL)", "Sample Vol (mL)", "Total Yield (mg)", "Total Yield (ng)"]
    for col_idx, h in enumerate(sc_headers, 1):
        c = ws_prot.cell(row=19, column=col_idx, value=h)
        c.fill = BLUE_SUBHEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    standards = [(0, 0.05), (125, 0.18), (250, 0.32), (500, 0.58), (750, 0.85), (1000, 1.12)]
    samples = [("Elution_Fraction_1", 0.65, 1.5), ("Elution_Fraction_2", 0.42, 2.0), ("Wash_2", 0.08, 5.0)]

    for idx, (std_conc, std_abs) in enumerate(standards, 20):
        c1 = ws_prot.cell(row=idx, column=1, value=std_conc)
        c2 = ws_prot.cell(row=idx, column=2, value=std_abs)
        c1.fill = INPUT_FILL
        c2.fill = INPUT_FILL
        c1.alignment = Alignment(horizontal="right")
        c2.alignment = Alignment(horizontal="right")
        c1.border = THIN_BORDER
        c2.border = THIN_BORDER

    for s_idx, (s_name, s_abs, s_vol) in enumerate(samples, 20):
        c3 = ws_prot.cell(row=s_idx, column=3, value=s_name)
        c4 = ws_prot.cell(row=s_idx, column=4, value=s_abs)
        # Using linear regression: x = (y - intercept) / slope
        # In Excel: SLOPE(known_y, known_x), INTERCEPT(known_y, known_x)
        c5 = ws_prot.cell(row=s_idx, column=5, value=f"=(D{s_idx}-INTERCEPT(0:5, 0:5))/SLOPE(0:5, 0:5)")
        c6 = ws_prot.cell(row=s_idx, column=6, value=s_vol)
        c7 = ws_prot.cell(row=s_idx, column=7, value=f"=(E{s_idx}*F{s_idx})/1000")
        c8 = ws_prot.cell(row=s_idx, column=8, value=f"=G{s_idx}*1000000")

        c3.font = BOLD_FONT
        c4.fill = INPUT_FILL
        c4.alignment = Alignment(horizontal="right")
        c5.fill = CALC_FILL
        c5.alignment = Alignment(horizontal="right")
        c6.fill = INPUT_FILL
        c6.alignment = Alignment(horizontal="right")
        c7.fill = CALC_FILL
        c7.alignment = Alignment(horizontal="right")
        c8.fill = CALC_FILL
        c8.alignment = Alignment(horizontal="right")

        for cell in (c3, c4, c5, c6, c7, c8):
            cell.border = THIN_BORDER

    _autofit_columns(ws_prot)

    # Sheet 4: Primer Design Log
    ws_prim = wb.create_sheet(title="Primer_Design_Log")
    ws_prim.views.sheetView[0].showGridLines = True

    ws_prim.cell(row=1, column=1, value="Oligonucleotide Primer Design & Thermodynamic Tracking").font = TITLE_FONT
    ws_prim.cell(row=2, column=1, value="Record and evaluate candidate PCR and sequencing primers.").font = NOTE_FONT

    prim_headers = ["Primer ID", "Target Gene / Region", "Direction", "Sequence (5' -> 3')", "Length (nt)", "Tm (°C)", "GC (%)", "3' GC Clamp", "Dimer Score", "Amplicon (bp)"]
    for col_idx, h in enumerate(prim_headers, 1):
        c = ws_prim.cell(row=4, column=col_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    sample_primers = [
        ("GluK2_Exon1_F", "GluK2 Kainate Receptor", "Forward", "ATGCCGTCCAGGCTGCTGGTC", 21, 62.4, 61.9, "Yes (2)", 1, 485),
        ("GluK2_Exon1_R", "GluK2 Kainate Receptor", "Reverse", "TCACTTGTCGTCGTCATCCTT", 21, 58.7, 47.6, "No (0)", 0, 485),
        ("AMPA_GluA1_F", "AMPA GluA1 Subunit", "Forward", "GCGAACCCCTTTGTGTACAG", 20, 59.8, 55.0, "Yes (1)", 0, 320),
        ("AMPA_GluA1_R", "AMPA GluA1 Subunit", "Reverse", "GGTGGTTTTCCAGCACATCT", 20, 59.2, 50.0, "Yes (1)", 0, 320),
    ]

    for idx, row_data in enumerate(sample_primers, 5):
        for c_idx, val in enumerate(row_data, 1):
            cell = ws_prim.cell(row=idx, column=c_idx, value=val)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if c_idx in (5, 6, 7, 9, 10):
                cell.alignment = Alignment(horizontal="right")
            elif c_idx in (1, 2, 3, 8):
                cell.alignment = Alignment(horizontal="center")

    _autofit_columns(ws_prim)


    # Sheet 5: Standardized Solution Prep & NanoDrop Predictor
    ws_sol = wb.create_sheet(title="Solution_Prep_NanoDrop")
    ws_sol.views.sheetView[0].showGridLines = True
    ws_sol.cell(row=1, column=1, value="Standardized Solution Prep & NanoDrop Absorbance Predictor").font = TITLE_FONT
    ws_sol.cell(row=2, column=1, value="Calculates exact required mass, moles, pipetting volumes, and what you should observe at the NanoDrop.").font = NOTE_FONT

    ws_sol.cell(row=4, column=1, value="1. Target Solution Parameters").font = SECTION_FONT
    sol_headers = ["Parameter", "Input Value", "Unit", "Description / Guidance"]
    for c_idx, h in enumerate(sol_headers, 1):
        c = ws_sol.cell(row=5, column=c_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    sol_inputs = [
        ("Target Molarity", 4.0, "µM", "Desired final concentration (e.g. 4.0 µM)"),
        ("Target Volume", 500.0, "µL", "Desired final total volume (e.g. 500.0 µL)"),
        ("Biomolecule Type", "ssRNA", "-", "ssRNA (40 µg/mL/AU), dsDNA (50), ssDNA (33)"),
        ("Transcript Length", 36, "nt", "Number of nucleotides or amino acids"),
        ("Molecular Weight", 11883.0, "g/mol (Da)", "Calculated or entered MW"),
        ("Stock Solution Conc.", 500.0, "ng/µL", "Concentration of stock if diluting (optional)"),
    ]
    for idx, (p, v, u, d) in enumerate(sol_inputs, 6):
        c1 = ws_sol.cell(row=idx, column=1, value=p)
        c2 = ws_sol.cell(row=idx, column=2, value=v)
        c3 = ws_sol.cell(row=idx, column=3, value=u)
        c4 = ws_sol.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_sol.cell(row=13, column=1, value="2. Stoichiometry & Required Quantities").font = SECTION_FONT
    sol_res_headers = ["Metric", "Formula / Calculated Value", "Unit", "Interpretation"]
    for c_idx, h in enumerate(sol_res_headers, 1):
        c = ws_sol.cell(row=14, column=c_idx, value=h)
        c.fill = BLUE_SUBHEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    sol_results = [
        ("Required Amount (Moles)", "=(B6*B7)/1000", "nmol", "= Molarity * Volume"),
        ("Required Amount (pmol)", "=B15*1000", "pmol", "Molar quantity in tube"),
        ("Required Mass (µg)", "=(B15*B10)/1000", "µg", "= nmol * MW / 1000"),
        ("Required Mass (ng)", "=B17*1000", "ng", "Total nanograms needed"),
        ("Target Concentration", "=B18/B7", "ng/µL", "Direct concentration of solution"),
        ("Stock Volume to Pipette", "=IF(B11>0, B18/B11, 0)", "µL", "Pipette this volume of stock"),
        ("Buffer Volume to Add", "=IF(B11>0, B7-B20, B7)", "µL", "Add buffer up to target volume"),
    ]
    for idx, (m, f_val, u, interp) in enumerate(sol_results, 15):
        c1 = ws_sol.cell(row=idx, column=1, value=m)
        c2 = ws_sol.cell(row=idx, column=2, value=f_val)
        c3 = ws_sol.cell(row=idx, column=3, value=u)
        c4 = ws_sol.cell(row=idx, column=4, value=interp)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = CALC_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_sol.cell(row=23, column=1, value="3. What You Should Get at the NanoDrop").font = SECTION_FONT
    nano_headers = ["NanoDrop Readout", "Expected Value", "Unit", "Standard Bench Range"]
    for c_idx, h in enumerate(nano_headers, 1):
        c = ws_sol.cell(row=24, column=c_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    nano_rows = [
        ("Nucleic Acid Concentration", "=B19", "ng/µL", "Should match target concentration within ±5%"),
        ("A260 (10 mm normalized)", "=B19/40.0", "AU", "Normalized absorbance at 260 nm"),
        ("A260 (1 mm physical pedestal)", "=B26*0.1", "AU", "Raw instrument reading on 1 mm pedestal"),
        ("A260 / A280 Ratio", 2.00, "-", "Pure RNA: ~2.00 (Pure dsDNA: ~1.80)"),
        ("A260 / A230 Ratio", 2.10, "-", "Pure sample range: 2.00 to 2.20"),
    ]
    for idx, (r, f_val, u, b_range) in enumerate(nano_rows, 25):
        c1 = ws_sol.cell(row=idx, column=1, value=r)
        c2 = ws_sol.cell(row=idx, column=2, value=f_val)
        c3 = ws_sol.cell(row=idx, column=3, value=u)
        c4 = ws_sol.cell(row=idx, column=4, value=b_range)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        if isinstance(f_val, str) and f_val.startswith("="):
            c2.fill = CALC_FILL
        else:
            c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    _autofit_columns(ws_sol)

    # Sheet 6: Fluorophore Modifications & DOL
    ws_fl = wb.create_sheet(title="Fluorophore_Modifications")
    ws_fl.views.sheetView[0].showGridLines = True
    ws_fl.cell(row=1, column=1, value="Fluorophore Modifications & Degree of Labeling (DOL)").font = TITLE_FONT
    ws_fl.cell(row=2, column=1, value="Spectral properties, mass additions, and DOL efficiency calculator.").font = NOTE_FONT

    fl_headers = ["Dye ID", "Common Name", "Added MW (Da)", "Ex (nm)", "Em (nm)", "ε_max (M^-1 cm^-1)", "CF260", "CF280", "Color / Channel"]
    for c_idx, h in enumerate(fl_headers, 1):
        c = ws_fl.cell(row=4, column=c_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    fl_catalog = [
        ("FAM", "6-FAM", 537.5, 495, 520, 75000, 0.30, 0.17, "Green (FITC channel)"),
        ("Cy3", "Cyanine 3", 767.0, 550, 570, 150000, 0.08, 0.05, "Orange-Red (TRITC channel)"),
        ("Cy5", "Cyanine 5", 793.0, 650, 670, 250000, 0.05, 0.05, "Far-Red (Cy5 channel)"),
        ("AF488", "Alexa Fluor 488", 643.4, 495, 519, 73000, 0.30, 0.11, "Bright Green"),
        ("AF647", "Alexa Fluor 647", 1250.0, 650, 665, 270000, 0.03, 0.03, "Far-Red"),
        ("TexasRed", "Texas Red-X", 816.9, 596, 620, 85000, 0.23, 0.18, "Deep Red"),
        ("TAMRA", "TAMRA", 527.5, 557, 583, 65000, 0.32, 0.36, "Rose"),
        ("BHQ-1", "Black Hole Quencher 1", 518.5, 534, 0, 34000, 0.35, 0.25, "Dark Quencher (FAM/TET)"),
    ]
    for idx, row_v in enumerate(fl_catalog, 5):
        for c_idx, v in enumerate(row_v, 1):
            cell = ws_fl.cell(row=idx, column=c_idx, value=v)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if c_idx in (3, 4, 5, 6, 7, 8):
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="center")

    # DOL Calculator section
    ws_fl.cell(row=15, column=1, value="Degree of Labeling (DOL) Calculator").font = SECTION_FONT
    dol_inputs = [
        ("Selected Dye", "FAM", "-", "Choose fluorophore from table above"),
        ("Dye Extinction Coeff (ε_dye)", 75000, "M^-1 cm^-1", "Molar extinction coefficient"),
        ("Dye Correction Factor (CF)", 0.30, "-", "CF260 for oligos, CF280 for proteins"),
        ("Biomolecule Extinction Coeff", 360000, "M^-1 cm^-1", "ε260 (oligo) or ε280 (protein)"),
        ("Absorbance at Dye Max (A_max)", 0.650, "AU", "Peak absorbance of attached dye"),
        ("Absorbance at 260 or 280 nm", 1.250, "AU", "Total absorbance of labeled conjugate"),
        ("Corrected Biomolecule Abs", "=B21-(B20*B18)", "AU", "A_corrected = A_total - (A_max * CF)"),
        ("Biomolecule Conc (µM)", "=(B22/B19)*1000000", "µM", "= A_corr / ε_biomol"),
        ("Dye Conc (µM)", "=(B20/B17)*1000000", "µM", "= A_max / ε_dye"),
        ("Degree of Labeling (DOL)", "=B24/B23", "moles dye / mol", "Target: ~0.8 to 1.2 for single 5'/3' label"),
    ]
    for idx, (p, v, u, d) in enumerate(dol_inputs, 16):
        c1 = ws_fl.cell(row=idx, column=1, value=p)
        c2 = ws_fl.cell(row=idx, column=2, value=v)
        c3 = ws_fl.cell(row=idx, column=3, value=u)
        c4 = ws_fl.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        if isinstance(v, str) and v.startswith("="):
            c2.fill = CALC_FILL
        else:
            c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    _autofit_columns(ws_fl)

    # Sheet 7: E. coli Growth & Expression Optimization
    ws_ec = wb.create_sheet(title="Ecoli_Growth_Optimization")
    ws_ec.views.sheetView[0].showGridLines = True
    ws_ec.cell(row=1, column=1, value="E. coli Culture Growth & Expression Optimization").font = TITLE_FONT
    ws_ec.cell(row=2, column=1, value="Inoculation scheduling, doubling times, plasmid yields, and recombinant protein production.").font = NOTE_FONT

    ws_ec.cell(row=4, column=1, value="1. Growth Kinetics & Induction Schedule").font = SECTION_FONT
    ec_inputs = [
        ("Initial Inoculation OD600", 0.05, "AU", "Starting density after dilution"),
        ("Target Induction OD600", 0.65, "AU", "Mid-log phase target (0.6 - 0.8)"),
        ("Culture Medium", "LB", "-", "LB (20 min), 2xYT (18 min), TB (22 min), M9 (50 min)"),
        ("Growth Temperature", 37.0, "°C", "37°C standard, 30°C slow, 18°C cold"),
        ("Doubling Time (td)", 20.0, "min", "Generation time under aeration"),
        ("Culture Volume", 1000.0, "mL", "Total shake flask or bioreactor volume"),
    ]
    for idx, (p, v, u, d) in enumerate(ec_inputs, 5):
        c1 = ws_ec.cell(row=idx, column=1, value=p)
        c2 = ws_ec.cell(row=idx, column=2, value=v)
        c3 = ws_ec.cell(row=idx, column=3, value=u)
        c4 = ws_ec.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_ec.cell(row=12, column=1, value="2. Growth Outputs (Calculated)").font = SECTION_FONT
    ec_results = [
        ("Required Doublings", "=LOG(B6/B5, 2)", "generations", "Number of cell divisions"),
        ("Time to Induction (Minutes)", "=B13*B9", "minutes", "= doublings * doubling time"),
        ("Time to Induction (Hours)", "=B14/60", "hours", "Plan your lab schedule"),
        ("Cell Count at Induction", "=B6*800000000", "cells/mL", "~8.0e8 cells/mL per 1.0 OD600"),
        ("Total Cells in Culture", "=B16*B10", "total cells", "Total biomass in vessel"),
    ]
    for idx, (m, f_val, u, interp) in enumerate(ec_results, 13):
        c1 = ws_ec.cell(row=idx, column=1, value=m)
        c2 = ws_ec.cell(row=idx, column=2, value=f_val)
        c3 = ws_ec.cell(row=idx, column=3, value=u)
        c4 = ws_ec.cell(row=idx, column=4, value=interp)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = CALC_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_ec.cell(row=19, column=1, value="3. Plasmid & Protein Yield Projections").font = SECTION_FONT
    ec_proj = [
        ("Plasmid Copy Number (pUC)", 600, "copies/cell", "High-copy pUC vector (~500-700)"),
        ("Plasmid Size", 3000, "bp", "Double-stranded plasmid length"),
        ("Theoretical Plasmid Yield", "=(B17*B20*1853916)/(6.02214e23)*1e6", "µg", "Max theoretical DNA yield"),
        ("Typical Column Kit Recovery", "=B22*0.55", "µg", "~50-60% typical silica recovery"),
        ("Target Protein MW", 45000, "Da", "Recombinant protein molecular weight"),
        ("Expression Level (% of total)", 15.0, "%", "Typical T7 / BL21(DE3) expression (10-25%)"),
        ("Recombinant Protein Yield", "=(B10*B6*0.150)*(B25/100)", "mg", "Estimated total expressed protein"),
        ("Recombinant Protein (nmol)", "=(B26*1000/B24)*1000", "nmol", "Molar quantity of protein"),
    ]
    for idx, (p, v, u, d) in enumerate(ec_proj, 20):
        c1 = ws_ec.cell(row=idx, column=1, value=p)
        c2 = ws_ec.cell(row=idx, column=2, value=v)
        c3 = ws_ec.cell(row=idx, column=3, value=u)
        c4 = ws_ec.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        if isinstance(v, str) and v.startswith("="):
            c2.fill = CALC_FILL
        else:
            c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    _autofit_columns(ws_ec)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path


def export_analysis_to_excel(
    output_path: str,
    ivt_results: Optional[List[IVTResult]] = None,
    pcr_results: Optional[List[PCRResult]] = None,
    protein_results: Optional[List[ProteinYieldResult]] = None,
    primer_pairs: Optional[List[PrimerPair]] = None,
) -> str:
    """Export live calculation results from Python objects directly into a styled multi-tab Excel workbook."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active

    if ivt_results:
        ws = wb.create_sheet(title="IVT_Results")
        ws.views.sheetView[0].showGridLines = True
        ws.cell(row=1, column=1, value="In Vitro Transcription Analysis Results").font = TITLE_FONT
        headers = ["Length (nt)", "MW (g/mol)", "Rxn Vol (µL)", "Yield (µg)", "Yield (pmol)", "Theo. Max (µg)", "Limiting NTP", "Efficiency (%)", "PPi Released (µg)", "Turnover"]
        for c_idx, h in enumerate(headers, 1):
            c = ws.cell(row=3, column=c_idx, value=h)
            c.fill = NAVY_HEADER
            c.font = WHITE_BOLD_FONT
            c.alignment = Alignment(horizontal="center")
            c.border = HEADER_BORDER
        for r_idx, res in enumerate(ivt_results, 4):
            vals = [
                res.rna_length, res.rna_mw, res.reaction_volume_ul, res.rna_yield_ug,
                res.rna_yield_pmol, res.theoretical_max_yield_ug, res.limiting_ntp,
                res.overall_efficiency_percent, res.pyrophosphate_released_ug,
                res.transcript_turnover_ratio or "-"
            ]
            for c_idx, val in enumerate(vals, 1):
                c = ws.cell(row=r_idx, column=c_idx, value=val)
                c.font = REGULAR_FONT
                c.border = THIN_BORDER
                c.alignment = Alignment(horizontal="right" if isinstance(val, (int, float)) else "center")
        _autofit_columns(ws)

    if pcr_results:
        ws = wb.create_sheet(title="PCR_Results")
        ws.views.sheetView[0].showGridLines = True
        ws.cell(row=1, column=1, value="PCR Amplification & Stoichiometry Results").font = TITLE_FONT
        headers = ["Amplicon (bp)", "Amplicon MW", "Template (ng)", "Cycles", "Yield (ng)", "Yield (pmol)", "Efficiency (%)", "Limiting dNTP", "Exhaustion Cycle", "Theo. Max (µg)"]
        for c_idx, h in enumerate(headers, 1):
            c = ws.cell(row=3, column=c_idx, value=h)
            c.fill = NAVY_HEADER
            c.font = WHITE_BOLD_FONT
            c.alignment = Alignment(horizontal="center")
            c.border = HEADER_BORDER
        for r_idx, res in enumerate(pcr_results, 4):
            vals = [
                res.amplicon_length_bp, res.amplicon_mw, res.template_initial_ng, res.cycles_run,
                res.amplicon_yield_ng, res.amplicon_yield_pmol, res.efficiency_percent,
                res.limiting_dntp, res.dntp_exhaustion_cycle or "No plateau", res.theoretical_max_amplicon_ug
            ]
            for c_idx, val in enumerate(vals, 1):
                c = ws.cell(row=r_idx, column=c_idx, value=val)
                c.font = REGULAR_FONT
                c.border = THIN_BORDER
                c.alignment = Alignment(horizontal="right" if isinstance(val, (int, float)) else "center")
        _autofit_columns(ws)

    if protein_results:
        ws = wb.create_sheet(title="Protein_Results")
        ws.views.sheetView[0].showGridLines = True
        ws.cell(row=1, column=1, value="Protein Quantification Results").font = TITLE_FONT
        headers = ["Sample Name", "Conc (mg/mL)", "Conc (µg/mL)", "Molarity (µM)", "Volume (mL)", "Total Yield (mg)", "Total Yield (µg)", "Total Yield (ng)"]
        for c_idx, h in enumerate(headers, 1):
            c = ws.cell(row=3, column=c_idx, value=h)
            c.fill = NAVY_HEADER
            c.font = WHITE_BOLD_FONT
            c.alignment = Alignment(horizontal="center")
            c.border = HEADER_BORDER
        for r_idx, res in enumerate(protein_results, 4):
            vals = [
                res.sample_name, res.concentration_mg_ml, res.concentration_ug_ml,
                res.molarity_um, res.volume_ml, res.total_yield_mg, res.total_yield_ug, res.total_yield_ng
            ]
            for c_idx, val in enumerate(vals, 1):
                c = ws.cell(row=r_idx, column=c_idx, value=val)
                c.font = REGULAR_FONT
                c.border = THIN_BORDER
                c.alignment = Alignment(horizontal="right" if isinstance(val, (int, float)) else "left")
        _autofit_columns(ws)

    if primer_pairs:
        ws = wb.create_sheet(title="Designed_Primers")
        ws.views.sheetView[0].showGridLines = True
        ws.cell(row=1, column=1, value="Automated Primer Design Results").font = TITLE_FONT
        headers = ["Rank", "Amplicon (bp)", "ΔTm (°C)", "Fwd Primer (5'->3')", "Fwd Tm (°C)", "Fwd GC%", "Fwd Clamp", "Rev Primer (5'->3')", "Rev Tm (°C)", "Rev GC%", "Rev Clamp", "Score"]
        for c_idx, h in enumerate(headers, 1):
            c = ws.cell(row=3, column=c_idx, value=h)
            c.fill = NAVY_HEADER
            c.font = WHITE_BOLD_FONT
            c.alignment = Alignment(horizontal="center")
            c.border = HEADER_BORDER
        for r_idx, p in enumerate(primer_pairs, 4):
            vals = [
                r_idx - 3, p.amplicon_length_bp, p.tm_difference,
                p.forward_primer.sequence, p.forward_primer.tm_celsius, p.forward_primer.gc_percent, "Yes" if p.forward_primer.has_gc_clamp else "No",
                p.reverse_primer.sequence, p.reverse_primer.tm_celsius, p.reverse_primer.gc_percent, "Yes" if p.reverse_primer.has_gc_clamp else "No",
                p.pair_quality_score
            ]
            for c_idx, val in enumerate(vals, 1):
                c = ws.cell(row=r_idx, column=c_idx, value=val)
                c.font = REGULAR_FONT
                c.border = THIN_BORDER
                c.alignment = Alignment(horizontal="right" if isinstance(val, (int, float)) else "center")
        _autofit_columns(ws)

    # Remove the initial blank sheet if other sheets were created
    if len(wb.sheetnames) > 1 and default_sheet in wb.worksheets:
        wb.remove(default_sheet)


    # Sheet 5: Standardized Solution Prep & NanoDrop Predictor
    ws_sol = wb.create_sheet(title="Solution_Prep_NanoDrop")
    ws_sol.views.sheetView[0].showGridLines = True
    ws_sol.cell(row=1, column=1, value="Standardized Solution Prep & NanoDrop Absorbance Predictor").font = TITLE_FONT
    ws_sol.cell(row=2, column=1, value="Calculates exact required mass, moles, pipetting volumes, and what you should observe at the NanoDrop.").font = NOTE_FONT

    ws_sol.cell(row=4, column=1, value="1. Target Solution Parameters").font = SECTION_FONT
    sol_headers = ["Parameter", "Input Value", "Unit", "Description / Guidance"]
    for c_idx, h in enumerate(sol_headers, 1):
        c = ws_sol.cell(row=5, column=c_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    sol_inputs = [
        ("Target Molarity", 4.0, "µM", "Desired final concentration (e.g. 4.0 µM)"),
        ("Target Volume", 500.0, "µL", "Desired final total volume (e.g. 500.0 µL)"),
        ("Biomolecule Type", "ssRNA", "-", "ssRNA (40 µg/mL/AU), dsDNA (50), ssDNA (33)"),
        ("Transcript Length", 36, "nt", "Number of nucleotides or amino acids"),
        ("Molecular Weight", 11883.0, "g/mol (Da)", "Calculated or entered MW"),
        ("Stock Solution Conc.", 500.0, "ng/µL", "Concentration of stock if diluting (optional)"),
    ]
    for idx, (p, v, u, d) in enumerate(sol_inputs, 6):
        c1 = ws_sol.cell(row=idx, column=1, value=p)
        c2 = ws_sol.cell(row=idx, column=2, value=v)
        c3 = ws_sol.cell(row=idx, column=3, value=u)
        c4 = ws_sol.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_sol.cell(row=13, column=1, value="2. Stoichiometry & Required Quantities").font = SECTION_FONT
    sol_res_headers = ["Metric", "Formula / Calculated Value", "Unit", "Interpretation"]
    for c_idx, h in enumerate(sol_res_headers, 1):
        c = ws_sol.cell(row=14, column=c_idx, value=h)
        c.fill = BLUE_SUBHEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    sol_results = [
        ("Required Amount (Moles)", "=(B6*B7)/1000", "nmol", "= Molarity * Volume"),
        ("Required Amount (pmol)", "=B15*1000", "pmol", "Molar quantity in tube"),
        ("Required Mass (µg)", "=(B15*B10)/1000", "µg", "= nmol * MW / 1000"),
        ("Required Mass (ng)", "=B17*1000", "ng", "Total nanograms needed"),
        ("Target Concentration", "=B18/B7", "ng/µL", "Direct concentration of solution"),
        ("Stock Volume to Pipette", "=IF(B11>0, B18/B11, 0)", "µL", "Pipette this volume of stock"),
        ("Buffer Volume to Add", "=IF(B11>0, B7-B20, B7)", "µL", "Add buffer up to target volume"),
    ]
    for idx, (m, f_val, u, interp) in enumerate(sol_results, 15):
        c1 = ws_sol.cell(row=idx, column=1, value=m)
        c2 = ws_sol.cell(row=idx, column=2, value=f_val)
        c3 = ws_sol.cell(row=idx, column=3, value=u)
        c4 = ws_sol.cell(row=idx, column=4, value=interp)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = CALC_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_sol.cell(row=23, column=1, value="3. What You Should Get at the NanoDrop").font = SECTION_FONT
    nano_headers = ["NanoDrop Readout", "Expected Value", "Unit", "Standard Bench Range"]
    for c_idx, h in enumerate(nano_headers, 1):
        c = ws_sol.cell(row=24, column=c_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    nano_rows = [
        ("Nucleic Acid Concentration", "=B19", "ng/µL", "Should match target concentration within ±5%"),
        ("A260 (10 mm normalized)", "=B19/40.0", "AU", "Normalized absorbance at 260 nm"),
        ("A260 (1 mm physical pedestal)", "=B26*0.1", "AU", "Raw instrument reading on 1 mm pedestal"),
        ("A260 / A280 Ratio", 2.00, "-", "Pure RNA: ~2.00 (Pure dsDNA: ~1.80)"),
        ("A260 / A230 Ratio", 2.10, "-", "Pure sample range: 2.00 to 2.20"),
    ]
    for idx, (r, f_val, u, b_range) in enumerate(nano_rows, 25):
        c1 = ws_sol.cell(row=idx, column=1, value=r)
        c2 = ws_sol.cell(row=idx, column=2, value=f_val)
        c3 = ws_sol.cell(row=idx, column=3, value=u)
        c4 = ws_sol.cell(row=idx, column=4, value=b_range)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        if isinstance(f_val, str) and f_val.startswith("="):
            c2.fill = CALC_FILL
        else:
            c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    _autofit_columns(ws_sol)

    # Sheet 6: Fluorophore Modifications & DOL
    ws_fl = wb.create_sheet(title="Fluorophore_Modifications")
    ws_fl.views.sheetView[0].showGridLines = True
    ws_fl.cell(row=1, column=1, value="Fluorophore Modifications & Degree of Labeling (DOL)").font = TITLE_FONT
    ws_fl.cell(row=2, column=1, value="Spectral properties, mass additions, and DOL efficiency calculator.").font = NOTE_FONT

    fl_headers = ["Dye ID", "Common Name", "Added MW (Da)", "Ex (nm)", "Em (nm)", "ε_max (M^-1 cm^-1)", "CF260", "CF280", "Color / Channel"]
    for c_idx, h in enumerate(fl_headers, 1):
        c = ws_fl.cell(row=4, column=c_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    fl_catalog = [
        ("FAM", "6-FAM", 537.5, 495, 520, 75000, 0.30, 0.17, "Green (FITC channel)"),
        ("Cy3", "Cyanine 3", 767.0, 550, 570, 150000, 0.08, 0.05, "Orange-Red (TRITC channel)"),
        ("Cy5", "Cyanine 5", 793.0, 650, 670, 250000, 0.05, 0.05, "Far-Red (Cy5 channel)"),
        ("AF488", "Alexa Fluor 488", 643.4, 495, 519, 73000, 0.30, 0.11, "Bright Green"),
        ("AF647", "Alexa Fluor 647", 1250.0, 650, 665, 270000, 0.03, 0.03, "Far-Red"),
        ("TexasRed", "Texas Red-X", 816.9, 596, 620, 85000, 0.23, 0.18, "Deep Red"),
        ("TAMRA", "TAMRA", 527.5, 557, 583, 65000, 0.32, 0.36, "Rose"),
        ("BHQ-1", "Black Hole Quencher 1", 518.5, 534, 0, 34000, 0.35, 0.25, "Dark Quencher (FAM/TET)"),
    ]
    for idx, row_v in enumerate(fl_catalog, 5):
        for c_idx, v in enumerate(row_v, 1):
            cell = ws_fl.cell(row=idx, column=c_idx, value=v)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if c_idx in (3, 4, 5, 6, 7, 8):
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="center")

    # DOL Calculator section
    ws_fl.cell(row=15, column=1, value="Degree of Labeling (DOL) Calculator").font = SECTION_FONT
    dol_inputs = [
        ("Selected Dye", "FAM", "-", "Choose fluorophore from table above"),
        ("Dye Extinction Coeff (ε_dye)", 75000, "M^-1 cm^-1", "Molar extinction coefficient"),
        ("Dye Correction Factor (CF)", 0.30, "-", "CF260 for oligos, CF280 for proteins"),
        ("Biomolecule Extinction Coeff", 360000, "M^-1 cm^-1", "ε260 (oligo) or ε280 (protein)"),
        ("Absorbance at Dye Max (A_max)", 0.650, "AU", "Peak absorbance of attached dye"),
        ("Absorbance at 260 or 280 nm", 1.250, "AU", "Total absorbance of labeled conjugate"),
        ("Corrected Biomolecule Abs", "=B21-(B20*B18)", "AU", "A_corrected = A_total - (A_max * CF)"),
        ("Biomolecule Conc (µM)", "=(B22/B19)*1000000", "µM", "= A_corr / ε_biomol"),
        ("Dye Conc (µM)", "=(B20/B17)*1000000", "µM", "= A_max / ε_dye"),
        ("Degree of Labeling (DOL)", "=B24/B23", "moles dye / mol", "Target: ~0.8 to 1.2 for single 5'/3' label"),
    ]
    for idx, (p, v, u, d) in enumerate(dol_inputs, 16):
        c1 = ws_fl.cell(row=idx, column=1, value=p)
        c2 = ws_fl.cell(row=idx, column=2, value=v)
        c3 = ws_fl.cell(row=idx, column=3, value=u)
        c4 = ws_fl.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        if isinstance(v, str) and v.startswith("="):
            c2.fill = CALC_FILL
        else:
            c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    _autofit_columns(ws_fl)

    # Sheet 7: E. coli Growth & Expression Optimization
    ws_ec = wb.create_sheet(title="Ecoli_Growth_Optimization")
    ws_ec.views.sheetView[0].showGridLines = True
    ws_ec.cell(row=1, column=1, value="E. coli Culture Growth & Expression Optimization").font = TITLE_FONT
    ws_ec.cell(row=2, column=1, value="Inoculation scheduling, doubling times, plasmid yields, and recombinant protein production.").font = NOTE_FONT

    ws_ec.cell(row=4, column=1, value="1. Growth Kinetics & Induction Schedule").font = SECTION_FONT
    ec_inputs = [
        ("Initial Inoculation OD600", 0.05, "AU", "Starting density after dilution"),
        ("Target Induction OD600", 0.65, "AU", "Mid-log phase target (0.6 - 0.8)"),
        ("Culture Medium", "LB", "-", "LB (20 min), 2xYT (18 min), TB (22 min), M9 (50 min)"),
        ("Growth Temperature", 37.0, "°C", "37°C standard, 30°C slow, 18°C cold"),
        ("Doubling Time (td)", 20.0, "min", "Generation time under aeration"),
        ("Culture Volume", 1000.0, "mL", "Total shake flask or bioreactor volume"),
    ]
    for idx, (p, v, u, d) in enumerate(ec_inputs, 5):
        c1 = ws_ec.cell(row=idx, column=1, value=p)
        c2 = ws_ec.cell(row=idx, column=2, value=v)
        c3 = ws_ec.cell(row=idx, column=3, value=u)
        c4 = ws_ec.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_ec.cell(row=12, column=1, value="2. Growth Outputs (Calculated)").font = SECTION_FONT
    ec_results = [
        ("Required Doublings", "=LOG(B6/B5, 2)", "generations", "Number of cell divisions"),
        ("Time to Induction (Minutes)", "=B13*B9", "minutes", "= doublings * doubling time"),
        ("Time to Induction (Hours)", "=B14/60", "hours", "Plan your lab schedule"),
        ("Cell Count at Induction", "=B6*800000000", "cells/mL", "~8.0e8 cells/mL per 1.0 OD600"),
        ("Total Cells in Culture", "=B16*B10", "total cells", "Total biomass in vessel"),
    ]
    for idx, (m, f_val, u, interp) in enumerate(ec_results, 13):
        c1 = ws_ec.cell(row=idx, column=1, value=m)
        c2 = ws_ec.cell(row=idx, column=2, value=f_val)
        c3 = ws_ec.cell(row=idx, column=3, value=u)
        c4 = ws_ec.cell(row=idx, column=4, value=interp)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        c2.fill = CALC_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    ws_ec.cell(row=19, column=1, value="3. Plasmid & Protein Yield Projections").font = SECTION_FONT
    ec_proj = [
        ("Plasmid Copy Number (pUC)", 600, "copies/cell", "High-copy pUC vector (~500-700)"),
        ("Plasmid Size", 3000, "bp", "Double-stranded plasmid length"),
        ("Theoretical Plasmid Yield", "=(B17*B20*1853916)/(6.02214e23)*1e6", "µg", "Max theoretical DNA yield"),
        ("Typical Column Kit Recovery", "=B22*0.55", "µg", "~50-60% typical silica recovery"),
        ("Target Protein MW", 45000, "Da", "Recombinant protein molecular weight"),
        ("Expression Level (% of total)", 15.0, "%", "Typical T7 / BL21(DE3) expression (10-25%)"),
        ("Recombinant Protein Yield", "=(B10*B6*0.150)*(B25/100)", "mg", "Estimated total expressed protein"),
        ("Recombinant Protein (nmol)", "=(B26*1000/B24)*1000", "nmol", "Molar quantity of protein"),
    ]
    for idx, (p, v, u, d) in enumerate(ec_proj, 20):
        c1 = ws_ec.cell(row=idx, column=1, value=p)
        c2 = ws_ec.cell(row=idx, column=2, value=v)
        c3 = ws_ec.cell(row=idx, column=3, value=u)
        c4 = ws_ec.cell(row=idx, column=4, value=d)
        c1.font = BOLD_FONT
        c2.font = BOLD_FONT
        if isinstance(v, str) and v.startswith("="):
            c2.fill = CALC_FILL
        else:
            c2.fill = INPUT_FILL
        c2.alignment = Alignment(horizontal="right")
        c3.font = REGULAR_FONT
        c4.font = NOTE_FONT
        for cell in (c1, c2, c3, c4): cell.border = THIN_BORDER

    _autofit_columns(ws_ec)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path


def batch_process_excel(input_path: str, output_path: str) -> str:
    """Read a batch table of sequences from an input Excel file, calculate properties, and write an annotated output workbook."""
    in_wb = openpyxl.load_workbook(input_path)
    in_ws = in_wb.active

    out_wb = openpyxl.Workbook()
    out_ws = out_wb.active
    out_ws.title = "Batch_Analysis_Results"
    out_ws.views.sheetView[0].showGridLines = True

    out_ws.cell(row=1, column=1, value="BioLabCalc Batch Sequence Analysis").font = TITLE_FONT
    headers = ["Row", "Identifier", "Type", "Sequence", "Length", "MW (Da)", "GC (%)", "Extinction Coeff", "100 ng Moles (pmol)"]
    for c_idx, h in enumerate(headers, 1):
        c = out_ws.cell(row=3, column=c_idx, value=h)
        c.fill = NAVY_HEADER
        c.font = WHITE_BOLD_FONT
        c.alignment = Alignment(horizontal="center")
        c.border = HEADER_BORDER

    # Scan rows starting from row 2
    row_count = 0
    for r_idx in range(2, in_ws.max_row + 1):
        row_cells = [in_ws.cell(row=r_idx, column=c).value for c in range(1, min(6, in_ws.max_column + 1))]
        if not any(row_cells):
            continue

        seq_id = str(row_cells[0] or f"Seq_{r_idx-1}").strip()
        raw_seq = str(row_cells[1] or "").strip()
        seq_type = str(row_cells[2] or "DNA").strip().lower() if len(row_cells) > 2 else "dna"

        if not raw_seq:
            continue

        row_count += 1
        out_r = 3 + row_count

        try:
            if "rna" in seq_type:
                mw_obj = calculate_rna_mw(raw_seq)
                e_coeff = f"{mw_obj.length * 10000} M^-1 cm^-1"
                st = "RNA"
            elif "prot" in seq_type or "aa" in seq_type:
                mw_obj = calculate_protein_mw(raw_seq)
                c_obj = calculate_extinction_coefficient(raw_seq)
                e_coeff = f"{c_obj.extinction_coeff_m_cm} M^-1 cm^-1"
                st = "Protein"
            else:
                mw_obj = calculate_dna_mw(raw_seq, double_stranded=False)
                e_coeff = f"{mw_obj.length * 9000} M^-1 cm^-1"
                st = "ssDNA"

            pmol_100ng = round((100.0 * 1e-9 / mw_obj.average_mw) * 1e12, 2) if mw_obj.average_mw > 0 else 0.0

            vals = [
                row_count, seq_id, st, mw_obj.sequence, mw_obj.length,
                mw_obj.average_mw, mw_obj.gc_content, e_coeff, pmol_100ng
            ]
        except Exception as e:
            vals = [row_count, seq_id, seq_type, raw_seq, 0, 0, 0, f"Error: {e}", 0]

        for c_idx, val in enumerate(vals, 1):
            c = out_ws.cell(row=out_r, column=c_idx, value=val)
            c.font = REGULAR_FONT
            c.border = THIN_BORDER
            c.alignment = Alignment(horizontal="right" if isinstance(val, (int, float)) else "left")

    _autofit_columns(out_ws)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    out_wb.save(output_path)
    return output_path
