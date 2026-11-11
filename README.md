# BioLabCalc 🧬🔬

[![CI](https://github.com/your-username/biolabcalc/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/biolabcalc/actions)
[![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://pypi.org/project/biolabcalc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> A multifaceted Python library and built-in Excel extension for daily wet-lab molecular biology calculations, reaction optimization, in vitro transcription stoichiometry, PCR kinetics, protein quantification, thermodynamic primer design, fluorophore modifications, gel migration ladders, standardized solution recipes, and *E. coli* growth modeling.

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Core Modules & API Reference](#-core-modules--api-reference)
  - [1. Standardized Solution Prep & NanoDrop Predictor (`spectroscopy`)](#1-standardized-solution-prep--nanodrop-predictor)
  - [2. Fluorophore Modifications & Degree of Labeling (`fluorescence`)](#2-fluorophore-modifications--degree-of-labeling-dol)
  - [3. Gel Migration & Molecular Weight Ladders (`gels`)](#3-gel-migration--molecular-weight-ladders)
  - [4. E. coli Growth & Plasmid/Protein Yields (`ecoli_growth`)](#4-e-coli-growth-kinetics--expression-optimization)
  - [5. PCR Kinetics, Optimization & Master Mix (`pcr`)](#5-pcr-kinetics--protocol-optimization)
  - [6. In Vitro Transcription Stoichiometry (`transcription`)](#6-in-vitro-transcription-ivt-stoichiometry)
  - [7. Molecular Weight & Conversions (`molecular_weight`)](#7-molecular-weight--stoichiometry)
  - [8. Protein Quantification (`protein`)](#8-protein-quantification--yield-analysis)
  - [9. Primer Design & SantaLucia Thermodynamics (`primers`)](#9-primer-creator--thermodynamics)
  - [10. Interactive Drag-and-Drop Gel Annotator & MW Calculator (`interactive_gel`)](#10-interactive-drag-and-drop-gel-annotator--mw-calculator)
  - [11. Gel Labeling Add-on & Image Annotator (`gel_annotator`)](#11-gel-labeling-add-on--image-annotator)
  - [12. Molecular Cloning, Digestion & Assembly (`cloning`)](#12-molecular-cloning-digestion--assembly)
  - [13. Laboratory Buffer & Stock Recipes (`buffers`)](#13-laboratory-buffer--stock-recipes)
  - [14. Nucleic Acid Precipitation & Desalting (`precipitation`)](#14-nucleic-acid-precipitation--desalting)
  - [15. Built-in Excel Extension (`excel_extension`)](#15-built-in-excel-extension)
  - [16. Standard Laboratory Protocols Compendium (`protocols`)](#16-standard-laboratory-protocols-compendium-protocols)
- [Command-Line Interface (CLI)](#-command-line-interface-cli)
- [Interactive Excel Workbook Structure](#-interactive-excel-workbook-structure)
- [Scientific Formulations](#-scientific-formulations)
- [Running Tests](#-running-tests)
- [Legal & Compliance Notice](#-legal--compliance-notice)
- [License](#-license)

---

## 🌟 Overview

Bench biologists and bioinformaticians constantly encounter repetitive yet critical quantitative tasks:
* **Preparing standardized solutions** (e.g., *"How do I make 4 µM ssRNA in 500 µL, and what exact ng/µL concentration and A260 absorbance should I see on the NanoDrop?"*).
* **Fluorophore labeling & modifications** (mass shifts, spectral parameters, and Degree of Labeling [DOL] efficiency for FAM, Cy3, Cy5, Alexa Fluor, ATTO dyes, and quenchers).
* **Gel electrophoresis simulation & ladder alignment** (mapping DNA/protein band sizes to 1 kb, 100 bp, or prestained protein ladders and calculating relative migration distances $R_f$).
* **E. coli expression scheduling & yield prediction** (calculating doubling times, hours from inoculation to induction $OD_{600}$, and theoretical plasmid or recombinant protein yields).
* **Reaction optimization & troubleshooting** (evaluating in vitro transcription NTP consumption, PCR dNTP limits, touchdown profiles, and Pace et al. $A_{280}$ extinction coefficients).

**BioLabCalc** combines a clean Python scientific API, an instant terminal CLI tool, and a built-in Excel extension (`openpyxl`) that generates publication-grade, interactive laboratory notebooks containing live formulas.

---

## 🚀 Key Features

* **Standardized Solution & NanoDrop Predictor**: Computes required mass (µg, ng) and moles (nmol, pmol) for target solutions (e.g., $4\,\mu	ext{M}$ in $500\,\mu	ext{L}$), generates pipetting dilution recipes, and predicts exact NanoDrop readings ($A_{260}$, $A_{260}/A_{280}$, and $	ext{ng}/\mu	ext{L}$).
* **Fluorophore Modification & Degree of Labeling (DOL)**: Database of fluorophores (FAM, Cy3, Cy5, Alexa Fluor 488/546/594/647, Texas Red, TAMRA, ROX, ATTO 488/647N, BHQ quenchers) with exact MW additions, correction factors ($CF_{260}, CF_{280}$), and dye-to-biomolecule DOL calculations.
* **Gel Migration & Ladder Simulation**: Simulates band positions for 1 kb DNA, 100 bp DNA, low-range oligo, and prestained protein ladders using logarithmic relative mobility ($R_f = a - b \log_{10}(	ext{size})$) with ASCII lane diagrams.
* **E. coli Growth & Yield Modeling**: Computes doubling times across LB, 2xYT, TB, and M9 media at 18–37°C, projects hours to reach induction $OD_{600}$ (0.6–0.8), and predicts theoretical plasmid DNA yields (pUC, pET, pBR322) and recombinant protein yields.
* **PCR Protocol Optimization**: Computes polymerase-specific annealing temperatures ($T_a$), elongation times (Taq vs. Q5/Phusion vs. Kapa), generates touchdown PCR schedules, and suggests GC enhancers (DMSO, Betaine) for difficult templates.
* **IVT Stoichiometry**: Tracks per-NTP usage, residual concentrations, incorporation efficiency, inorganic pyrophosphate ($PP_i$) precipitation risks, and transcript turnover ratios.
* **Exact Molecular Weights**: Sequence-level average and monoisotopic weights for ssDNA, dsDNA, circular plasmids, RNA (5'-ppp, 5'-P, 5'-OH), and polypeptides.
* **Built-in Excel Extension**: Generates formatted, 7-tab interactive workbooks (`.xlsx`) with live formulas for lab bench use.

---

## 📦 Installation

### From PyPI (Recommended)
```bash
pip install biolabcalc
```

### From GitHub (Source / Development)
```bash
git clone https://github.com/your-username/biolabcalc.git
cd biolabcalc
pip install -e ".[dev]"
```

---

## ⚡ Quick Start

### ⏱️ 5-Minute Benchtop Cookbook (Everyday Lab Calculations)

BioLabCalc answers everyday wet-lab calculations via the command line, Python API, or the interactive wizard:

| Daily Laboratory Task | CLI Command / Python Code | Expected Output / Result |
| :--- | :--- | :--- |
| **Dilute Stock Solution** | `biolabcalc dilute -c1 "100 mM" -c2 "25 mM" -v2 "16 mL"` | Pipette 4.0 mL stock + 12.0 mL diluent |
| **Neutralize 100 mM NTPs (pH 7.5)** | `biolabcalc ntp-ph -v 4.0 -c 100 -V 16 -C 25 -f disodium_salt` | Add 108.5 µL of 5 M NaOH, QS to 16 mL |
| **Scale 10X PBS Recipe (500 mL)** | `biolabcalc buffer -b 10X_PBS -v 500` | 40.0 g NaCl, 1.0 g KCl, 7.2 g Na2HPO4, 1.2 g KH2PO4 |
| **Plan EcoRI + BamHI Double Digest** | `biolabcalc digest -m 1.0 -v 50 -e1 EcoRI -e2 BamHI -c 200` | 5 µL 10X rCutSmart, 5 µL DNA, 1 µL each enzyme, 38 µL water |
| **Check Overhang Compatibility** | `python -c "import biolabcalc as blc; print(blc.are_overhangs_compatible("BamHI", "BglII"))"` | Compatible cohesive ends (GATC) |
| **Precipitate Low-Yield RNA** | `biolabcalc precipitate -v 100 -t rna -a ethanol -s naoac` | Add 10 µL 3M NaOAc, 1 µL GlycoBlue, 300 µL 100% EtOH |
| **Interactive Guided Wizard** | `biolabcalc wizard` | Step-by-step prompted menu for bench calculations |
| **View Standard Wet-Lab Protocol** | `biolabcalc protocol -n t7_ivt_transcription` | Complete bench protocol with safety, tables, and troubleshooting |

```python
import biolabcalc.easy as easy

# 1. Quick C1*V1 = C2*V2 dilution
res = easy.dilute(c1="100 mM", c2="25 mM", v2="16 mL")
print(f"Pipette {res[v1]/1000} mL stock + {res[diluent_needed]/1000} mL water")

# 2. Scale 10X PBS buffer to 500 mL
pbs = easy.buffer("10X_PBS", volume="500 mL")

# 3. Quick primer check
p_info = easy.primer("ATGCCGTCCAGGCTGCTG", primer_conc="400 nM")
print(f"Tm: {p_info.tm_celsius}°C, GC: {p_info.gc_percent}%")
```


```python
import biolabcalc as blc

# 1. Standardized Solution & NanoDrop Predictor: 4 µM ssRNA in 500 µL
sol = blc.prepare_standard_solution(
    target_molarity_um=4.0,
    target_volume_ul=500.0,
    seq_type="rna",
    rna_length_nt=36,
)
print(f"Required Mass: {sol.required_mass_ug:.2f} µg ({sol.required_moles_nmol:.2f} nmol)")
print(f"NanoDrop Expected Conc: {sol.expected_nanodrop_ng_ul:.2f} ng/µL")
print(f"NanoDrop Expected A260: {sol.expected_nanodrop_a260_1cm:.3f} AU (A260/A280 ~ {sol.expected_a260_a280_ratio})")

# 2. Fluorophore Modification & Degree of Labeling (DOL)
dna = blc.calculate_dna_mw("ATGCCGTCCAGGCTGCTGGTC")
labeled = blc.apply_fluorophore_modification(dna, ["FAM"])
print(f"FAM-labeled DNA MW: {labeled.total_modified_mw:,.2f} Da (+{labeled.total_added_mw} Da)")

dol = blc.calculate_degree_of_labeling(
    absorbance_max_dye=0.75,
    absorbance_280=1.10,
    fluorophore_name="FAM",
    protein_extinction_coeff=45000,
)
print(f"Degree of Labeling: {dol.degree_of_labeling:.2f} ({dol.interpretation})")

# 3. Gel Electrophoresis Migration Simulation
sim = blc.simulate_gel([750, 2200, 4500], ladder_key="1kb_dna")
print(sim.ascii_visualization)

# 4. E. coli Growth & Induction Scheduling
growth = blc.calculate_ecoli_growth(initial_od600=0.05, target_od600=0.65, temperature_celsius=37.0, media="LB")
print(f"Time to Induction OD: {growth.formatted_time} ({growth.num_doublings} doublings)")

# 5. Generate Multi-Tab Interactive Excel Lab Notebook
blc.generate_lab_notebook_template("BioLab_Interactive_Notebook.xlsx")
```

---

## 🔬 Core Modules & API Reference

### 1. Standardized Solution Prep & NanoDrop Predictor
```python
from biolabcalc.spectroscopy import prepare_standard_solution

res = prepare_standard_solution(
    target_molarity_um=4.0,
    target_volume_ul=500.0,
    seq_type="rna",
    rna_length_nt=36,
    stock_conc_ng_ul=500.0,  # Optional: provides pipetting dilution recipe
)
```
**Output Highlights:**
- `required_mass_ug`: Total mass needed ($23.02\,\mu	ext{g}$).
- `required_moles_nmol`: Total moles ($2.000	ext{ nmol}$).
- `expected_nanodrop_ng_ul`: Target concentration reading ($46.03\,	ext{ng}/\mu	ext{L}$).
- `expected_nanodrop_a260_1cm`: Normalized $A_{260}$ reading ($1.151	ext{ AU}$).
- `expected_nanodrop_a260_1mm`: Physical pedestal reading ($0.1151	ext{ AU}$).
- `preparation_instructions`: Exact pipetting instructions for bench technicians.

### 2. Fluorophore Modifications & Degree of Labeling (DOL)
```python
from biolabcalc.fluorescence import apply_fluorophore_modification, calculate_degree_of_labeling

# Add fluorophores/quenchers to DNA, RNA, or protein
mod_res = apply_fluorophore_modification(base_dna_mw, ["FAM", "BHQ1"])

# Quantify labeling efficiency from spectrophotometer readings
dol = calculate_degree_of_labeling(
    absorbance_max_dye=0.65,
    absorbance_260=1.25,
    fluorophore_name="FAM",
    oligo_extinction_coeff=360000,
)
```

### 3. Gel Migration & Molecular Weight Ladders
```python
from biolabcalc.gels import simulate_gel

# LADDER OPTIONS: "1kb_dna", "100bp_dna", "low_range_ssdna", "protein_broad_range"
sim = simulate_gel(sample_sizes=[450, 1200, 3000], ladder_key="1kb_dna")
print(sim.ascii_visualization)
```

### 4. E. coli Growth Kinetics & Expression Optimization
```python
from biolabcalc.ecoli_growth import calculate_ecoli_growth, estimate_plasmid_yield, optimize_protein_induction

# Time to induction OD600
growth = calculate_ecoli_growth(initial_od600=0.05, target_od600=0.65, temperature_celsius=37.0, media="LB")

# Estimate plasmid prep yield from culture
plasmid = estimate_plasmid_yield(culture_volume_ml=5.0, final_od600=3.0, plasmid_type="pUC")

# Recombinant protein yield and induction condition advisor
prot = optimize_protein_induction(protein_mw_da=45000, culture_volume_ml=1000.0, final_od600=4.0)
```

### 5. PCR Kinetics & Protocol Optimization
```python
from biolabcalc.pcr import calculate_pcr_kinetics, optimize_pcr_protocol, build_master_mix

# Protocol optimization: annealing temp, extension time, touchdown schedule, additives
protocol = optimize_pcr_protocol(primer_fwd_tm=60.5, primer_rev_tm=60.0, amplicon_len_bp=800, polymerase="q5")

# Master mix pipetting table for N samples with 10% excess
master_mix = build_master_mix(num_reactions=24, excess_percent=10.0)
```

---

### 16. Standard Laboratory Protocols Compendium (`protocols`)

BioLabCalc includes a built-in catalog of 10 fully verified, easy-to-understand wet-lab molecular biology and biochemistry protocols. Each protocol provides comprehensive reagent formulation tables, materials lists, safety warnings, pro tips, time/temperature parameters, troubleshooting matrices, and literature citations. The complete consolidated manual is compiled in [`PROTOCOLS.md`](PROTOCOLS.md).

#### Built-in Protocols:
1. **`ntp_neutralization`**: 25 mM Neutralized NTP Mix Preparation (pH 7.5) with NaOH titration and logic checks.
2. **`t7_ivt_transcription`**: High-Yield T7 In Vitro Transcription of RNA with DNase I degradation.
3. **`ecoli_transformation`**: Heat-Shock Transformation of Chemically Competent *E. coli* (DH5α / BL21).
4. **`alkaline_lysis_miniprep`**: Alkaline Lysis Plasmid DNA Miniprep with silica spin column binding.
5. **`agarose_gel_electrophoresis`**: Submarine Agarose Gel Casting, Loading, and Imaging for DNA/RNA.
6. **`denaturing_urea_page`**: 7–8 M Urea-PAGE for Single-Nucleotide Resolution of Small RNAs and Aptamers.
7. **`ethanol_precipitation`**: Ethanol & Isopropanol Nucleic Acid Precipitation and Desalting.
8. **`gibson_assembly`**: Gibson Isothermal Assembly for 2–3 Overlapping DNA Fragments.
9. **`restriction_double_digest`**: Restriction Endonuclease Double Digest with rSAP Dephosphorylation.
10. **`bradford_protein_assay`**: Bradford / BCA Colorimetric Protein Assay with BSA Standard Curve.

#### Python API:
```python
from biolabcalc.protocols import list_protocols, get_protocol, export_all_protocols_markdown

# List all protocols or filter by category
protocols = list_protocols(category="RNA")

# Inspect a specific protocol
proto = get_protocol("t7_ivt_transcription")
print(f"{proto.title}: {proto.estimated_time}")

# Export consolidated markdown manual
export_all_protocols_markdown("PROTOCOLS.md")
```

#### CLI:
```bash
# List all protocols in the catalog
biolabcalc protocol --list

# Filter by category (e.g. RNA, Cloning, Electrophoresis)
biolabcalc protocol --category RNA

# Display full step-by-step instructions at the terminal
biolabcalc protocol -n ntp_neutralization

# Export complete PROTOCOLS.md manual
biolabcalc protocol --export PROTOCOLS.md
```

---

## 💻 Command-Line Interface (CLI)

```bash
# NanoDrop & Standardized Solution (e.g. 4 uM ssRNA in 500 uL)
biolabcalc nanodrop -u 4.0 -v 500 -t rna --length 36

# Fluorophore modification & spectral info
biolabcalc fluo -s ATGCCGTCCAGGCTGCTGGTC -d FAM

# Gel electrophoresis ladder simulation
biolabcalc gel -s 750 2200 4500 --ladder 1kb_dna

# PCR protocol optimization
biolabcalc pcr-opt --fwd-tm 60.5 --rev-tm 60.0 -l 800 -p q5 --gc 52.0

# E. coli growth & plasmid yield
biolabcalc ecoli --init-od 0.05 --target-od 0.65 --temp 37 --media LB --vol-ml 1000

# Annotate gel images, label lanes, and callout molecular weights
biolabcalc annotate-gel \
    --lanes "Ladder,Ctrl,Clone1,Clone2,Digest" \
    --ladder 1kb_dna \
    --ladder-lane 1 \
    --bands "3:850:Amplicon,4:850:Amplicon,5:3500:Vector" \
    --title "Colony PCR Screening" \
    --output "annotated_gel.png" \
    --excel "Experiment_Report.xlsx"

# Restriction enzyme digestion setup
biolabcalc digest --dna-ug 2.0 -e1 EcoRI -e2 BamHI --dna-conc 250

# DNA ligation molar ratio calculator (3:1 insert:vector)
biolabcalc ligate --vec-bp 4500 --ins-bp 1200 --vec-ng 50 --ratio 3.0

# Gibson Assembly / NEBuilder HiFi calculator
biolabcalc gibson --vec-bp 5000 --ins-bp 850 1500 --vec-ng 100

# Buffer recipe calculator (500 mL of 50X TAE)
biolabcalc buffer -b 50X_TAE -v 500

# Ethanol precipitation of nucleic acids
biolabcalc precipitate -v 100 -t dna -a ethanol -s naoac

# Launch interactive drag-and-drop gel tool in web browser
biolabcalc interactive-gel --port 8501

# Save standalone HTML application to share with lab members
biolabcalc interactive-gel --save-html "Interactive_Gel_Tool.html"

# Generate full interactive Excel lab notebook
biolabcalc excel-template -o "BioLab_Calculator.xlsx"
```

---

## 📊 Interactive Excel Workbook Structure

The generated workbook (`biolabcalc excel-template`) contains 7 specialized, styled sheets with live formulas:

1. **`IVT_Stoichiometry`**: Live IVT yield, per-NTP consumption (ATP, CTP, GTP, UTP), residual concentrations, pyrophosphate byproduct, and transcript turnover.
2. **`PCR_Optimization`**: Multi-sample master mix formulation table with dynamic excess multipliers and qPCR standard curve efficiency solver (`=10^(-1/slope)-1`).
3. **`Protein_Quantification`**: Direct $A_{280}$ Beer-Lambert calculator and BCA/Bradford standard curve regression (`SLOPE()`, `INTERCEPT()`) with unknown sample interpolation.
4. **`Primer_Design_Log`**: Formatted log for tracking primer names, sequences, $T_m$, GC%, 3' GC clamps, and amplicon lengths.
5. **`Solution_Prep_NanoDrop`**: Input target molarity and volume; auto-calculates required mass/moles, stock dilution pipetting volumes, and predicted NanoDrop readings ($A_{260}$, $A_{260}/A_{280}$, $	ext{ng}/\mu	ext{L}$).
6. **`Fluorophore_Modifications`**: Spectral property lookup and live Degree of Labeling (DOL) calculator.
7. **`Ecoli_Growth_Optimization`**: Inoculation-to-induction timeline calculator, doubling time tables, and plasmid/recombinant protein yield projections.

---

## 🧪 Running Tests

```bash
python -m unittest discover -s tests
```

All 114 automated tests pass with 100% test coverage across core mathematical, physical, and biochemical modules.

---

## 🚀 PyPI Publishing & Distribution

BioLabCalc is configured for automated Continuous Delivery to [PyPI](https://pypi.org/project/biolabcalc/) using GitHub Actions and PyPI Trusted Publishing (OIDC).

### Method 1: Automated Release via GitHub Actions (Recommended)
1. Ensure `__version__` in `src/biolabcalc/__init__.py` and `version` in `pyproject.toml` match your release tag (e.g. `0.2.0`).
2. Tag your commit and push to GitHub:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
   *Or create a new Release from the GitHub web interface.*
3. The `.github/workflows/publish.yml` workflow triggers automatically, builds the `.tar.gz` sdist and `.whl` binary wheel, validates metadata with `twine check`, and publishes the release directly to PyPI.

### Method 2: Manual Local Upload via Twine
To publish manually from your local development environment:
```bash
# 1. Install build and twine
pip install build twine

# 2. Build the distributions
python -m build

# 3. Verify integrity
twine check dist/*

# 4. Upload to TestPyPI (optional dry-run)
python scripts/release.py --test-pypi

# 5. Upload to production PyPI
python scripts/release.py --pypi
# Or:
twine upload dist/*
```


---

## ⚖️ Legal & Compliance Notice

BioLabCalc is developed for open scientific research. For full regulatory, export control, biosecurity, and dependency audit details, consult [LEGAL.md](LEGAL.md).

* **Research Use Only (RUO)**: BioLabCalc is designed solely for academic research and educational purposes. It is **not** certified, validated, or intended for human or animal clinical diagnostics, medical treatment, or therapeutic manufacturing.
* **Biosecurity & Export Control**: All algorithms are based on fundamental, publicly available scientific research (15 CFR § 734.7 & § 734.8; EAR99). The software contains no select agent design pipelines or dual-use biosecurity evasion mechanisms.
* **Permissive Dependencies**: All upstream dependencies (`openpyxl`, `matplotlib`, `Pillow`, `numpy`) use OSI-approved permissive licenses (MIT, PSF, HPND, BSD-3-Clause) with zero copyleft (GPL/AGPL) restrictions.
* **Trademark Notice**: All third-party registered trademarks (e.g. Gibson Assembly®, NanoDrop™, Coomassie®, Triton™, Tween®, Q5®, Phusion®) are the property of their respective owners and are referenced under nominative fair use without affiliation or endorsement.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
