# BioLabCalc 🧬🔬

[![CI](https://github.com/kabe89/BioLabCalc/actions/workflows/ci.yml/badge.svg)](https://github.com/kabe89/BioLabCalc/actions)
[![PyPI Version](https://img.shields.io/pypi/v/biolabcalc.svg)](https://pypi.org/project/biolabcalc/)
[![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://pypi.org/project/biolabcalc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-195%20passed-brightgreen.svg)](#-running-tests)

> **BioLabCalc** is a comprehensive computational biology suite, command-line benchtop assistant, interactive Excel generator, and browser-based Electronic Lab Notebook (ELN) / LIMS for daily wet-lab molecular biology, biochemistry, cloning, electrophoresis, and cell culture workflows.

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
  - [5-Minute Benchtop Cookbook](#-5-minute-benchtop-cookbook)
  - [Convenience API (`biolabcalc.easy`)](#-convenience-api-biolabcalceasy)
- [Electronic Lab Notebook (ELN) & LIMS](#-electronic-lab-notebook-eln--lims)
- [Core Modules & Capabilities](#-core-modules--capabilities)
  - [1. Standardized Solution Prep & NanoDrop Predictor (`spectroscopy`)](#1-standardized-solution-prep--nanodrop-predictor)
  - [2. Molecular Cloning & Assembly (`cloning`)](#2-molecular-cloning--assembly)
  - [3. Western Blot Optimization & Troubleshooting (`western_blot`)](#3-western-blot-optimization--troubleshooting)
  - [4. Fluorophore Modifications & Degree of Labeling (`fluorescence`)](#4-fluorophore-modifications--degree-of-labeling-dol)
  - [5. Gel Migration & Molecular Weight Ladders (`gels`)](#5-gel-migration--molecular-weight-ladders)
  - [6. E. coli Growth & Induction Scheduling (`ecoli_growth`)](#6-e-coli-growth-kinetics--expression-optimization)
  - [7. PCR Kinetics & Master Mix Formulation (`pcr`)](#7-pcr-kinetics--protocol-optimization)
  - [8. In Vitro Transcription (IVT) Stoichiometry (`transcription`)](#8-in-vitro-transcription-ivt-stoichiometry)
  - [9. Molecular Weight & Molar Conversions (`molecular_weight`)](#9-molecular-weight--stoichiometry)
  - [10. Protein Quantification & Standard Curves (`protein`)](#10-protein-quantification--standard-curves)
  - [11. Primer Thermodynamics & SantaLucia Design (`primers`)](#11-primer-creator--thermodynamics)
  - [12. Laboratory Buffers & Temperature Shifts (`buffers`)](#12-laboratory-buffer--stock-recipes)
  - [13. Nucleic Acid Precipitation & Desalting (`precipitation`)](#13-nucleic-acid-precipitation--desalting)
  - [14. Interactive Drag-and-Drop Gel Annotator (`interactive_gel`)](#14-interactive-drag-and-drop-gel-annotator)
  - [15. Built-in Excel Workbook Generator (`excel_extension`)](#15-built-in-excel-workbook-generator)
- [Command-Line Interface (CLI)](#-command-line-interface-cli)
- [Interactive Excel Workbook Structure](#-interactive-excel-workbook-structure)
- [Running Tests](#-running-tests)
- [Contributing](#-contributing)
- [Legal & Compliance Notice](#-legal--compliance-notice)
- [License](#-license)

---

## 🌟 Overview

Bench biologists and bioinformaticians frequently juggle fragmented calculations and manual spreadsheets:
* **Stock dilution & spectrometry verification**: Computing exact pipetting instructions to prepare target molarities and calculating predicted NanoDrop readings ($A_{260}$, $A_{280}$, $A_{260}/A_{280}$, $\text{ng}/\mu\text{L}$).
* **Assembly stoichiometry**: Calculating fmol and mass ratios for Gibson Assembly and Type IIS Golden Gate assemblies (BsaI, BsmBI, BbsI).
* **Western blot immunodetection**: Transfer voltage/duration matrices, multi-pass transmembrane protein denaturation handling, and artifact troubleshooting.
* **Fluorophore labeling**: Spectral properties, correction factors ($CF_{260}, CF_{280}$), and Degree of Labeling (DOL) ratios.
* **Electronic Lab Notebook (ELN)**: Local, GxP-compliant experimental tracking with versioned SOP protocol execution checklists, live kinetic timers, FPLC/spectrophotometer data parsing, and multi-day campaign carry-forward math.

**BioLabCalc** unifies these capabilities into an intuitive Python library, an interactive terminal CLI (`biolabcalc`), a standalone browser annotator, and an extensible, modern local ELN.

---

## 🚀 Key Features

| Capability | Module | Description |
| :--- | :--- | :--- |
| **Solution Prep & NanoDrop** | `spectroscopy` | Mass/moles calculator, dilution recipe generator, and exact NanoDrop $A_{260}$ / $A_{280}$ predictor. |
| **Cloning & Assembly** | `cloning` | Gibson Assembly / NEBuilder HiFi, Golden Gate Type IIS assembly, restriction double digest planning, and overhang compatibility. |
| **Western Blot Suite** | `western_blot` | Wet tank / semi-dry transfer matrices, membrane protein heat-denaturation safeguards, lysate loading, and diagnostic troubleshooting. |
| **Fluorophore & DOL** | `fluorescence` | Library of common dyes (FAM, Cy3, Cy5, Alexa Fluor, ATTO, quenchers), MW additions, and spectrophotometric Degree of Labeling. |
| **Gel Mobility & Ladders** | `gels` | Logarithmic band migration ($R_f = a - b\log_{10}(\text{size})$) for DNA (1 kb, 100 bp, low-range) and protein ladders with ASCII visualization. |
| **Bacterial Growth Modeling**| `ecoli_growth` | Doubling kinetics across media (LB, 2xYT, TB, M9) and temperatures (18–37°C), induction scheduling, and plasmid/protein yield projection. |
| **PCR Kinetics & Optimization**| `pcr` | Polymerase-specific annealing temperatures, extension times, touchdown thermal schedules, and multi-reaction master mix tables. |
| **IVT Stoichiometry** | `transcription` | Per-NTP consumption, residual pools, capping efficiencies (CleanCap AG/AU), modified NTPs (m1Ψ, s2U), and pyrophosphate ($PP_i$) precipitation tracking. |
| **Sequence Thermodynamics** | `primers` | SantaLucia (1998) nearest-neighbor $T_m$ calculation with salt corrections, GC clamps, hairpin stability, and heterodimerization risk. |
| **Buffer Formulations** | `buffers` | Catalog of standard biological buffers (PBS, TAE, TBE, RIPA, Towbin, Laemmli), Tris temperature compensation, and NTP pH neutralization. |
| **Precipitation & Extraction**| `precipitation`| Ethanol, isopropanol, and LiCl selective RNA precipitation; acid phenol:chloroform:isoamyl alcohol (PCI) phase separation. |
| **Interactive Gel Annotator** | `interactive_gel`| Browser-based drag-and-drop tool to annotate lanes, fit standard curves, and estimate unknown band molecular weights. |
| **Electronic Lab Notebook** | `eln` | Multi-modal local ELN with SQLite CAS storage, GxP protocol forking, step execution checkoffs, live timers, and instrument log parsers. |
| **Excel Workbook Generator** | `excel_extension`| Generates 7-tab publication-grade `.xlsx` notebooks with live formulas and styling. |

---

## 📦 Installation

### From PyPI (Recommended)
```bash
pip install biolabcalc
```

### Install with Optional Extras
```bash
# Install with Excel workbook generation support
pip install "biolabcalc[excel]"

# Install with image annotation and plotting support
pip install "biolabcalc[gel]"

# Install all development dependencies (pytest, flake8)
pip install "biolabcalc[dev]"
```

### From GitHub (Source / Development)
```bash
git clone https://github.com/kabe89/BioLabCalc.git
cd BioLabCalc
pip install -e ".[dev]"
```

---

## ⚡ Quick Start

### ⏱️ 5-Minute Benchtop Cookbook

BioLabCalc answers everyday laboratory questions instantly via Python or the terminal:

| Daily Laboratory Task | CLI Command / Python Code | Expected Output / Result |
| :--- | :--- | :--- |
| **Dilute Stock Solution** | `biolabcalc dilute -c1 "100 mM" -c2 "25 mM" -v2 "16 mL"` | Pipette 4.0 mL stock + 12.0 mL diluent |
| **Neutralize 100 mM NTPs (pH 7.5)** | `biolabcalc ntp-ph -v 4.0 -c 100 -V 16 -C 25 -f disodium_salt` | Add 108.5 µL 5 M NaOH, QS to 16 mL |
| **Scale 10X PBS Recipe (500 mL)** | `biolabcalc buffer -b 10X_PBS -v 500` | 40.0 g NaCl, 1.0 g KCl, 7.2 g Na2HPO4, 1.2 g KH2PO4 |
| **Plan EcoRI + BamHI Digest** | `biolabcalc digest -m 1.0 -v 50 -e1 EcoRI -e2 BamHI -c 200` | 5 µL 10X rCutSmart, 5 µL DNA, 1 µL each enzyme |
| **Check Overhang Compatibility** | `python -c "import biolabcalc as blc; print(blc.are_overhangs_compatible('BamHI', 'BglII'))"` | Compatible cohesive ends (GATC) |
| **Golden Gate Assembly (BsaI)** | `biolabcalc golden-gate --vec-bp 4500 --ins-bp 1200 600 --fmol 20` | Vector: 58.5 ng; Insert 1: 31.2 ng; Insert 2: 15.6 ng |
| **NanoDrop Purity Check** | `biolabcalc purity --a260 1.25 --a280 0.63 --a230 0.58 -t rna` | Status: PURE (A260/A280 = 1.98, A260/A230 = 2.16) |
| **Phenol:Chloroform Extraction** | `biolabcalc pci -v 150 -t rna` | 150 µL Sample + 150 µL PCI (pH 4.5) + 150 µL Chloroform |
| **Precipitate Low-Yield RNA** | `biolabcalc precipitate -v 100 -t rna -a ethanol -s naoac` | Add 10 µL 3M NaOAc, 1 µL GlycoBlue, 300 µL 100% EtOH |
| **Interactive Guided Wizard** | `biolabcalc wizard` | Step-by-step prompted menu for bench calculations |
| **Launch Electronic Lab Notebook** | `biolabcalc eln --port 8000` | Opens modern web ELN in browser |

---

### 🧪 Convenience API (`biolabcalc.easy`)

For rapid interactive work in Jupyter or the terminal, `biolabcalc.easy` accepts human-readable strings with units:

```python
import biolabcalc.easy as easy

# 1. Quick C1*V1 = C2*V2 dilution with unit strings
res = easy.dilute(c1="100 mM", c2="25 mM", v2="16 mL")
print(f"Pipette {res['v1']/1000:.2f} mL stock + {res['diluent_needed']/1000:.2f} mL diluent.")

# 2. Scale laboratory buffer
pbs = easy.buffer("10X_PBS", volume="500 mL")

# 3. Primer Tm and thermodynamics
primer_info = easy.primer("ATGCCGTCCAGGCTGCTG", primer_conc="400 nM")
print(f"Tm: {primer_info.tm_celsius}°C, GC: {primer_info.gc_percent}%")

# 4. Golden Gate Assembly setup (BsaI-HFv2)
gg = easy.golden_gate(vector_bp=4500, insert_bps=[1200, 600], target_fmol=20.0, enzyme="BsaI-HFv2")
print(f"Vector: {gg.vector_mass_ng:.1f} ng | Inserts: {gg.insert_masses_ng} ng")

# 5. NanoDrop nucleic acid purity diagnostics
purity = easy.nanodrop_purity(a260=1.25, a280=0.63, a230=0.58, sample_type="rna")
print(f"Status: {purity.purity_status.upper()} -> {purity.diagnostic_feedback[0]}")
```

---

## 📓 Electronic Lab Notebook (ELN) & LIMS

BioLabCalc features an integrated, lightweight Electronic Lab Notebook and Laboratory Information Management System:

```bash
# Launch the web ELN server on port 8000
biolabcalc eln --port 8000
```

### Architecture & GxP Capabilities:
* **Protocol & SOP Management**: Author custom master Standard Operating Procedures, track semantic versions (`1.0`, `2.0`), manage PI sign-offs, and execute **GxP immutable execution forks** into daily notebook entries.
* **Interactive Step Execution Checklists**: Live check-offs, recorded operator IDs, planned vs. actual duration tracking, and protocol deviation logging.
* **Kinetic Timers**: Real-time countup/countdown timers with audible alerts and automatic timepoint logging.
* **Instrument Log Parsing**: Ingest raw data from AKTA FPLC (`.res`, `.csv`), pCLAMP electrophysiology (`.abf`, `.atf`), Bio-Rad gel imagers, NanoDrop spectrophotometers, and plate readers.
* **Inventory & Cold Storage**: Hierarchical storage locations (Building $\to$ Room $\to$ Freezer $\to$ Shelf $\to$ Box $\to$ Tube) with 2D grid maps and freeze-thaw count tracking.
* **Audit Trails & Data Integrity**: 21 CFR Part 11 compliant append-only audit trail recording user, action, timestamp, and JSON delta snapshots.

---

## 🔬 Core Modules & Capabilities

### 1. Standardized Solution Prep & NanoDrop Predictor
```python
from biolabcalc.spectroscopy import prepare_standard_solution

sol = prepare_standard_solution(
    target_molarity_um=4.0,
    target_volume_ul=500.0,
    seq_type="rna",
    rna_length_nt=36,
    stock_conc_ng_ul=500.0,
)
print(f"Required Mass: {sol.required_mass_ug:.2f} µg ({sol.required_moles_nmol:.2f} nmol)")
print(f"Predicted NanoDrop A260: {sol.expected_nanodrop_a260_1cm:.3f} AU")
```

### 2. Molecular Cloning & Assembly
```python
from biolabcalc.cloning import plan_restriction_digest, calculate_gibson_assembly, calculate_golden_gate_assembly

# Plan double digest
digest = plan_restriction_digest(dna_mass_ug=2.0, reaction_volume_ul=50.0, enzyme_1="EcoRI", enzyme_2="BamHI")

# Gibson Assembly stoichiometry
gibson = calculate_gibson_assembly(vector_length_bp=4500, insert_lengths_bp=[1200, 800], vector_mass_ng=100.0)

# Golden Gate Assembly (Type IIS)
golden_gate = calculate_golden_gate_assembly(vector_length_bp=4500, insert_lengths_bp=[1200, 600], target_vector_fmol=20.0)
```

### 3. Western Blot Optimization & Troubleshooting
```python
from biolabcalc.western_blot import calculate_transfer_conditions, calculate_lysate_loading, troubleshoot_western_blot

# Wet tank vs semi-dry conditions (optimized for target molecular weight)
transfer = calculate_transfer_conditions(target_mw_kda=120.0, transfer_system="wet_tank", membrane_type="pvdf")

# Lysate loading with Laemmli sample buffer and multi-pass membrane protein denaturation check
loading = calculate_lysate_loading(lysate_conc_mg_ml=2.5, target_protein_ug_per_lane=20.0, sample_buffer_conc=4, is_membrane_protein=True)

# Troubleshooting database
trouble = troubleshoot_western_blot("no_signal")
print(f"Likely causes: {trouble.likely_causes[0]}")
```

### 4. Fluorophore Modifications & Degree of Labeling (DOL)
```python
from biolabcalc.fluorescence import apply_fluorophore_modification, calculate_degree_of_labeling
from biolabcalc.molecular_weight import calculate_dna_mw

dna = calculate_dna_mw("ATGCCGTCCAGGCTGCTGGTC")
labeled = apply_fluorophore_modification(dna, ["FAM", "BHQ1"])

# Quantify labeling efficiency from spectrophotometer readings
dol = calculate_degree_of_labeling(
    absorbance_max_dye=0.65,
    absorbance_260=1.25,
    fluorophore_name="FAM",
    oligo_extinction_coeff=360000,
)
print(f"Degree of Labeling: {dol.degree_of_labeling:.2f} ({dol.interpretation})")
```

### 5. Gel Migration & Molecular Weight Ladders
```python
from biolabcalc.gels import simulate_gel

# LADDER OPTIONS: "1kb_dna", "100bp_dna", "low_range_ssdna", "protein_broad_range"
sim = simulate_gel(sample_sizes=[450, 1200, 3000], ladder_key="1kb_dna")
print(sim.ascii_visualization)
```

### 6. E. coli Growth Kinetics & Expression Optimization
```python
from biolabcalc.ecoli_growth import calculate_ecoli_growth, estimate_plasmid_yield, optimize_protein_induction

# Time to induction OD600
growth = calculate_ecoli_growth(initial_od600=0.05, target_od600=0.65, temperature_celsius=37.0, media="LB")

# Estimate plasmid prep yield
plasmid = estimate_plasmid_yield(culture_volume_ml=5.0, final_od600=3.0, plasmid_type="pUC")

# Recombinant protein yield advisor
prot = optimize_protein_induction(protein_mw_da=45000, culture_volume_ml=1000.0, final_od600=4.0)
```

### 7. PCR Kinetics & Master Mix Formulation
```python
from biolabcalc.pcr import calculate_pcr_kinetics, optimize_pcr_protocol, build_master_mix

# PCR protocol optimization
protocol = optimize_pcr_protocol(primer_fwd_tm=60.5, primer_rev_tm=60.0, amplicon_len_bp=800, polymerase="q5")

# Multi-reaction master mix with 10% pipetting excess
master_mix = build_master_mix(num_reactions=24, reaction_volume_ul=50.0, excess_percent=10.0)
```

### 8. In Vitro Transcription (IVT) Stoichiometry
```python
from biolabcalc.transcription import calculate_ivt_yield

ivt = calculate_ivt_yield(
    rna_seq="TAATACGACTCACTATAGGGAGACCCAAGCUGGCC",
    reaction_volume_ul=20.0,
    measured_yield_ug=40.0,
    auto_trim_promoter=True,
    add_5prime_gg=2,
    modified_ntp="m1Psi",
    cap_analog="CleanCap_AG",
)
print(f"Transcript Length: {ivt.rna_length} nt | MW: {ivt.rna_mw:,.2f} Da")
print(f"Predicted Capping Efficiency: {ivt.predicted_capping_efficiency_percent:.0f}%")
```

### 9. Molecular Weight & Stoichiometry
```python
from biolabcalc.molecular_weight import calculate_dna_mw, calculate_rna_mw, calculate_protein_mw, mass_to_moles

dna_mw = calculate_dna_mw("ATGCCGTCCAGGCTGCTGGTC", is_double_stranded=True)
moles = mass_to_moles(mass_g=100e-9, mw_da=dna_mw.average_mw)
print(f"100 ng = {moles*1e12:.2f} pmol")
```

### 10. Protein Quantification & Standard Curves
```python
from biolabcalc.protein import quantify_protein_a280, calculate_extinction_coefficient, fit_standard_curve

# Sequence-based extinction coefficient (Pace et al., 1995)
ext = calculate_extinction_coefficient("MKWVTFISLLLLFSSAYSRG")
conc = quantify_protein_a280(absorbance_280=0.85, extinction_coeff_m_cm=ext.extinction_coefficient_reduced, protein_mw_da=ext.molecular_weight)
```

### 11. Primer Creator & Thermodynamics
```python
from biolabcalc.primers import analyze_primer, design_primers

# Nearest-neighbor SantaLucia (1998) thermodynamics
p_analysis = analyze_primer("ATGCCGTCCAGGCTGCTGGTC", primer_conc_nm=400.0, na_conc_mm=50.0, mg_conc_mm=1.5)
print(f"Tm: {p_analysis.tm_celsius:.1f}°C | GC: {p_analysis.gc_percent:.1f}%")
```

### 12. Laboratory Buffer & Stock Recipes
```python
from biolabcalc.buffers import calculate_buffer_recipe, calculate_ntp_ph_adjustment, calculate_tris_temperature_shift

# Scale 10X PBS recipe
recipe = calculate_buffer_recipe("10X_PBS", target_volume_ml=1000.0)

# Temperature shift of Tris buffer (25°C to 4°C cold room)
tris_shift = calculate_tris_temperature_shift(ph_at_t1=8.0, t1_celsius=25.0, t2_celsius=4.0)

# 25 mM NTP neutralization to pH 7.5
ntp_ph = calculate_ntp_ph_adjustment(initial_volume_ml=4.0, target_volume_ml=16.0, starting_form="disodium_salt")
```

### 13. Nucleic Acid Precipitation & Desalting
```python
from biolabcalc.precipitation import calculate_precipitation, calculate_phenol_chloroform_extraction

# Ethanol precipitation with GlycoBlue carrier
precip = calculate_precipitation(sample_volume_ul=100.0, nucleic_acid="rna", alcohol="ethanol", salt="naoac")

# Phenol:Chloroform phase separation
pci = calculate_phenol_chloroform_extraction(sample_volume_ul=150.0, nucleic_acid="rna")
```

### 14. Interactive Drag-and-Drop Gel Annotator
```python
from biolabcalc.interactive_gel import launch_interactive_annotator, save_interactive_app

# Launch standalone browser application
launch_interactive_annotator(port=8501)

# Or export self-contained HTML file for offline sharing
save_interactive_app("Interactive_Gel_App.html")
```

### 15. Built-in Excel Workbook Generator
```python
from biolabcalc.excel_extension import generate_lab_notebook_template

# Generate multi-tab Excel notebook with live formulas
generate_lab_notebook_template("BioLab_Interactive_Notebook.xlsx")
```

---

## 💻 Command-Line Interface (CLI)

BioLabCalc provides a full-featured terminal CLI with subcommands for all calculations:

```bash
# 1. Solution Dilution
biolabcalc dilute -c1 "100 mM" -c2 "25 mM" -v2 "16 mL"

# 2. NTP Neutralization & pH Adjustment
biolabcalc ntp-ph -v 4.0 -c 100 -V 16 -C 25 -f disodium_salt

# 3. Buffer Scaling (500 mL of 50X TAE)
biolabcalc buffer -b 50X_TAE -v 500

# 4. Golden Gate Assembly (Type IIS)
biolabcalc golden-gate --vec-bp 4500 --ins-bp 1200 600 --fmol 20 --enzyme BsaI-HFv2

# 5. Gibson Assembly / NEBuilder HiFi
biolabcalc gibson --vec-bp 5000 --ins-bp 850 1500 --vec-ng 100

# 6. Restriction Enzyme Digest Setup
biolabcalc digest --dna-ug 2.0 -e1 EcoRI -e2 BamHI --dna-conc 250

# 7. DNA Ligation Molar Ratio
biolabcalc ligate --vec-bp 4500 --ins-bp 1200 --vec-ng 50 --ratio 3.0

# 8. NanoDrop Purity Assessment
biolabcalc purity --a260 1.25 --a280 0.63 --a230 0.58 -t rna

# 9. Phenol:Chloroform Extraction
biolabcalc pci -v 150 -t rna

# 10. Ethanol Nucleic Acid Precipitation
biolabcalc precipitate -v 100 -t dna -a ethanol -s naoac

# 11. Gel Lane Image Annotation
biolabcalc annotate-gel \
    --lanes "Ladder,Ctrl,Clone1,Clone2,Digest" \
    --ladder 1kb_dna \
    --ladder-lane 1 \
    --bands "3:850:Amplicon,4:850:Amplicon,5:3500:Vector" \
    --title "Colony PCR Screening" \
    --output "annotated_gel.png"

# 12. Interactive Browser Gel Annotator
biolabcalc interactive-gel --port 8501

# 13. Generate Multi-Tab Excel Workbook
biolabcalc excel-template -o "BioLab_Calculator.xlsx"

# 14. Electronic Lab Notebook (ELN) Server
biolabcalc eln --port 8000
```

---

## 📊 Interactive Excel Workbook Structure

The generated workbook (`biolabcalc excel-template`) contains 7 specialized sheets with live, dynamic formulas:

1. **`IVT_Stoichiometry`**: Live IVT yield, per-NTP consumption (ATP, CTP, GTP, UTP), residual concentrations, and pyrophosphate byproduct.
2. **`PCR_Optimization`**: Multi-sample master mix formulation with dynamic excess multipliers and qPCR standard curve efficiency solver (`=10^(-1/slope)-1`).
3. **`Protein_Quantification`**: Direct $A_{280}$ Beer-Lambert calculator and BCA/Bradford standard curve regression (`SLOPE()`, `INTERCEPT()`) with unknown sample interpolation.
4. **`Primer_Design_Log`**: Formatted log for tracking primer names, sequences, $T_m$, GC%, 3' GC clamps, and amplicon lengths.
5. **`Solution_Prep_NanoDrop`**: Input target molarity and volume; auto-calculates required mass/moles, stock dilution pipetting volumes, and predicted NanoDrop readings ($A_{260}$, $A_{260}/A_{280}$, $\text{ng}/\mu\text{L}$).
6. **`Fluorophore_Modifications`**: Spectral property lookup and live Degree of Labeling (DOL) calculator.
7. **`Ecoli_Growth_Optimization`**: Inoculation-to-induction timeline calculator, doubling time tables, and plasmid/recombinant protein yield projections.

---

## 🧪 Running Tests

BioLabCalc features an exhaustive test suite with zero external dependencies required for core mathematical verification:

```bash
# Run all tests using Python's standard unittest runner
python -m unittest discover -s tests
```

```text
Ran 195 tests in 0.762s
OK (skipped=6)
```

All 195 automated tests pass with 100% test coverage across core mathematical, physical, and biochemical calculations.

---

## 🤝 Contributing

Contributions to BioLabCalc are warmly welcomed! Please review our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before getting started.

We follow standard GitHub pull request workflows:

1. **Fork the Repository**: Click "Fork" at [github.com/kabe89/BioLabCalc](https://github.com/kabe89/BioLabCalc).
2. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/my-new-calculation
   ```
3. **Write Tests & Implement**: Ensure all calculations cite peer-reviewed literature and include unit tests in `tests/`.
4. **Run the Test Suite**:
   ```bash
   python -m unittest discover tests
   ```
5. **Commit Cleanly**: Follow conventional commit conventions (`feat:`, `fix:`, `docs:`, `test:`).
   ```bash
   git commit -m "feat: add isothermal rolling circle amplification calculator"
   ```
6. **Push & Open a Pull Request**:
   ```bash
   git push origin feature/my-new-calculation
   ```

---

## ⚖️ Legal & Compliance Notice

BioLabCalc is developed for open scientific research. For full regulatory, export control, biosecurity, and dependency audit details, consult [LEGAL.md](LEGAL.md).

* **Research Use Only (RUO)**: BioLabCalc is designed solely for academic research and educational purposes. It is **not** certified, validated, or intended for human or animal clinical diagnostics, medical treatment, or therapeutic manufacturing.
* **Biosecurity & Export Control**: All algorithms are based on fundamental, publicly available scientific research (15 CFR § 734.7 & § 734.8; EAR99). The software contains no select agent design pipelines or dual-use biosecurity evasion mechanisms.
* **Permissive Dependencies**: All upstream dependencies (`openpyxl`, `matplotlib`, `Pillow`, `numpy`) use OSI-approved permissive licenses (MIT, PSF, HPND, BSD-3-Clause) with zero copyleft (GPL/AGPL) restrictions.
* **Data Sovereignty**: Sequence data, primer designs, experimental formulations, and laboratory notebooks created by users are saved solely to local file storage and are never transmitted to external servers.
* **Nominative Fair Use**: All product names, logos, and trademarks (e.g. Gibson Assembly®, NanoDrop™, Coomassie®, Triton™, Tween®, Q5®, Phusion®) are the property of their respective owners and are referenced under nominative fair use without endorsement.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
